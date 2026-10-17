'use strict';
const {test,after}=require('node:test'),assert=require('node:assert/strict');
const net=require('node:net'),tls=require('node:tls'),fs=require('node:fs'),path=require('node:path'),os=require('node:os'),{spawnSync}=require('node:child_process');
const io=require('../lib/mqtt-client.cjs'),sim=require('../lib/mqtt-simulator.cjs'),industrial=require('../lib/industrial-client.cjs');
const {Runtime}=require('../lib/runtime.cjs'),graph=require('../public/vision/flow-graph.js');
const params={connection:'simulator',topic:'tests/message',encoding:'structured',qos:1,timeoutMs:1500};
const publish=(p={})=>io.run({operation:'mqtt_publish',params:{...params,value:{count:3,passed:true},retain:true,...p}});
const receive=(p={},signal)=>io.run({operation:'mqtt_receive',params:{...params,...p}},{signal});
async function broker(options={},tlsOptions){
 const {Aedes}=await import('aedes'),broker=await Aedes.createBroker(options),sockets=new Set();broker.on('error',()=>{});broker.on('clientError',()=>{});
 const handle=socket=>{sockets.add(socket);socket.on('error',()=>{});socket.on('close',()=>sockets.delete(socket));broker.handle(socket);};
 const server=tlsOptions?tls.createServer(tlsOptions,handle):net.createServer(handle);server.on('tlsClientError',()=>{});await new Promise(r=>server.listen(0,'127.0.0.1',r));
 return {broker,port:server.address().port,async close(){const closed=new Promise(r=>server.close(r));for(const socket of sockets)socket.destroy();await new Promise(r=>broker.close(r));await closed;}};
}
after(()=>io.stop());
test('simulator lifecycle, QoS 0/1/2, text/structured/bytes and retained deletion use real packets',async()=>{
 const [a,b]=await Promise.all([sim.start(),sim.start()]);assert.equal(a.port,b.port);assert.equal(a.host,'127.0.0.1');
 for(const qos of [0,1,2])for(const [encoding,value] of [['text','工件 A\nOK'],['structured',{count:3,items:[{width:12.5}],passed:true}],['bytes',[0,128,255]]]){
  const topic=`tests/${qos}/${encoding}`,sent=await publish({qos,encoding,value,topic});assert.equal(sent.result.acknowledged,qos>0);assert.equal(sent.result.delivery,qos?'broker_acknowledged':'sent');
  const got=await receive({qos,encoding,topic});assert.deepEqual(got.result.value,value);assert.equal(got.result.retained,true);assert.equal(got.result.qos,qos);assert.equal(got.result.simulated,true);
 }
 await publish({topic:'tests/null',value:null});assert.equal((await receive({topic:'tests/null'})).result.value,null);
 await publish({topic:'tests/clear',encoding:'text',value:'hello'});await publish({topic:'tests/clear',encoding:'text',value:''});await assert.rejects(receive({topic:'tests/clear',timeoutMs:100}),/超时/);
 await sim.stop();assert.equal(sim.status().running,false);await sim.start();await assert.rejects(receive({timeoutMs:100,topic:'tests/1/text'}),/超时/);
});
test('fresh-message wildcard subscription ignores retained values and has concurrent publisher',async()=>{
 const b=await broker();const p={connection:'broker',host:'127.0.0.1',port:b.port,topic:'line/inspection'};
 try{
  await publish({...p,value:{count:1}});
  const subscribed=new Promise(r=>b.broker.once('subscribe',r));const pending=receive({...p,topic:'line/+',acceptRetained:false,qos:2});await subscribed;
  await publish({...p,value:{count:7},retain:false,qos:2});const result=await pending;
  assert.deepEqual(result.result.value,{count:7});assert.equal(result.result.topic,'line/inspection');assert.equal(result.result.retained,false);assert.equal(result.result.simulated,false);
 }finally{await b.close();}
});
test('invalid topics, ranges, encoding, unsafe data and authentication configuration fail before connect',async()=>{
 for(const p of [{topic:'x/+'},{qos:3},{retain:'true'},{timeoutMs:0},{encoding:'other'},{encoding:'bytes',value:[256]},{encoding:'text',value:3},{value:{n:Infinity}},{value:{n:Number.MAX_SAFE_INTEGER+1}},{value:JSON.parse('{"__proto__":1}')},{value:'x'.repeat(65537)}])await assert.rejects(publish(p));
 for(const topic of ['x/#/y','x/a+','$share/group/topic','x\u0000'])await assert.rejects(receive({topic}));
 await assert.rejects(publish({connection:'broker',username:'u',passwordEnv:'SIEANS_TEST_UNSET_MQTT_SECRET'}),/未设置/);
 await assert.rejects(publish({connection:'broker',security:'tls',clientCertificate:'not-a-file'}),/成对/);
 assert.equal(io.activeCount(),0);
});
test('decode errors are explicit and never return undecoded message bytes as text',async()=>{
 await publish({encoding:'bytes',value:[255,254],topic:'tests/badutf'});await assert.rejects(receive({encoding:'text',topic:'tests/badutf'}),/UTF-8/);
 await publish({encoding:'text',value:'not structured',topic:'tests/badformat'});await assert.rejects(receive({topic:'tests/badformat'}),/结构化/);
 assert.deepEqual((await receive({encoding:'bytes',topic:'tests/badutf'})).result.value,[255,254]);
 assert.throws(()=>io.decode(Buffer.alloc(65537),'bytes'),/64 KiB/);
});
test('client IDs are exclusive only within the same broker; task limit and abort release resources',async()=>{
 await sim.start();const controllers=Array.from({length:8},()=>new AbortController());
 const pending=controllers.map((c,i)=>receive({topic:'never/'+i,clientId:'test-client-'+i,timeoutMs:5000},c.signal).then(()=>assert.fail('unexpected receive'),e=>assert.match(e.message,/取消/)));
 await assert.rejects(receive(),/上限/);controllers.forEach(c=>c.abort());await Promise.all(pending);assert.equal(io.activeCount(),0);
 const controller=new AbortController(),one=receive({topic:'never',clientId:'exclusive'},controller.signal).catch(e=>assert.match(e.message,/取消/));
 await assert.rejects(receive({clientId:'exclusive'}),/标识正在使用/);controller.abort();await one;
 const pre=new AbortController();pre.abort();await assert.rejects(receive({},pre.signal),/取消/);
 await assert.rejects(receive({topic:'never',clientId:'exclusive',timeoutMs:100}),/超时/);assert.equal(io.activeCount(),0);
});
test('username/password environment authentication and refusal make no automatic reconnect',async()=>{
 let attempts=0;const b=await broker({authenticate(_client,user,password,done){attempts++;done(null,user==='operator'&&password?.toString()==='local-test-password');}});
 process.env.SIEANS_TEST_MQTT_PASS='local-test-password';const p={connection:'broker',host:'127.0.0.1',port:b.port,username:'operator',passwordEnv:'SIEANS_TEST_MQTT_PASS'};
 try{await publish(p);assert.equal((await receive(p)).result.value.count,3);const before=attempts;await assert.rejects(publish({...p,username:'invalid'}),/连接|通信/);await new Promise(r=>setTimeout(r,150));assert.equal(attempts,before+1);}
 finally{delete process.env.SIEANS_TEST_MQTT_PASS;await b.close();}
});
test('TLS verifies CA/host and supports required client certificates',async()=>{
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'sieans-mqtt-tls-')),python=process.env.VISION_PYTHON||path.resolve('.venv',process.platform==='win32'?'Scripts/python.exe':'bin/python');
 const generated=spawnSync(python,[path.join(__dirname,'mqtt_certs.py'),dir],{encoding:'utf8',windowsHide:true});assert.equal(generated.status,0,generated.stderr);
 const read=name=>fs.readFileSync(path.join(dir,name)),options={key:read('server-key.pem'),cert:read('server.pem'),ca:read('ca.pem'),requestCert:true,rejectUnauthorized:true};
 const b=await broker({},options),p={connection:'broker',host:'127.0.0.1',port:b.port,security:'tls',caFile:path.join(dir,'ca.pem'),clientCertificate:path.join(dir,'client.pem'),privateKey:path.join(dir,'client-key.pem')};
 try{await publish(p);assert.equal((await receive(p)).result.value.count,3);await assert.rejects(publish({...p,caFile:''}),/连接|通信/);await assert.rejects(publish({...p,clientCertificate:'',privateKey:''}),/连接|通信/);}
 finally{await b.close();}
 const wrong=await broker({},{...options,key:read('wronghost-key.pem'),cert:read('wronghost.pem')});try{await assert.rejects(publish({...p,port:wrong.port}),/连接|通信/);}finally{await wrong.close();}
});
test('lost publish acknowledgement reports uncertain effects without retry',async()=>{
 let writes=0;const b=await broker({authorizePublish(client,_packet,done){writes++;client.conn.destroy();done(Error('drop'));}});
 try{await assert.rejects(publish({connection:'broker',host:'127.0.0.1',port:b.port,qos:1}),/可能.*接收.*不能回滚/);assert.equal(writes,1);}finally{await b.close();}
});
test('runtime binds MQTT to three variable scopes and rolls back variables but not publication',async()=>{
 const rt=new Runtime(fs.mkdtempSync(path.join(os.tmpdir(),'sieans-mqtt-runtime-')),{run(){throw Error('unexpected vision call');}});
 const node=(id,operation,p)=>({id,operation,params:p});
 const p=graph.normalize({version:1,name:'MQTT variables',steps:[node('pub','mqtt_publish',{...params,value:{count:3},retain:true}),node('sub','mqtt_receive',params),...['global','flow','module'].map(scope=>node(scope,'variables',{scope,name:'count',value:{$ref:'results.sub.value.count'}}))]});
 const frame={unit:'mm',points:[[1,2,3]]};const run=rt.start({project:p,cloud:frame});await rt.jobs.get(run.id).promise;const done=rt.poll(run.id);assert.equal(done.state,'completed',done.error);assert.equal(done.variables.flow.count,3);assert.equal(done.variables.global.count,3);assert.equal(done.variables.modules.module.count,3);assert.deepEqual(done.results[2].output.cloud,frame);
 p.steps.splice(2,0,node('bad','variables',{scope:'flow',name:'bad',value:{$ref:'flow.absent'}}));p.steps[0].params.value={count:9};const badGraph=graph.normalize({...p,version:1,edges:undefined});const failed=rt.start({project:badGraph});await rt.jobs.get(failed.id).promise;assert.equal(rt.poll(failed.id).state,'failed');assert.equal(rt.snapshot(p).flow.count,3);assert.equal((await receive()).result.value.count,9);
 assert(industrial.operations.has('mqtt_publish'));
});
