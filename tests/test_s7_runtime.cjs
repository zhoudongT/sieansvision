const {test,after}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path'),net=require('node:net');
const {Runtime}=require('../lib/runtime.cjs');
const graph=require('../public/vision/flow-graph.js');
const io=require('../lib/industrial-client.cjs'),sim=require('../lib/s7-simulator.cjs'),vision=require('../lib/vision-client.cjs');
const runtime=()=>new Runtime(fs.mkdtempSync(path.join(os.tmpdir(),'sieans-s7-test-')),vision);
const node=(id,operation,params)=>({id,operation,params});
const params={connection:'simulator',area:'db',dbNumber:1};
async function run(r,p,extra={}){const started=r.start({project:p,...extra});await r.jobs.get(started.id).promise;return r.poll(started.id);}
after(async()=>{vision.stop();await io.stop();});

test('S7 simulator lifecycle, real TCP transactions and reset',async()=>{
 const a=await sim.start(),b=await sim.start();assert.equal(a.port,b.port);assert.equal(a.host,'127.0.0.1');
 assert.equal((await io.run({operation:'s7_read',params})).result.value,123);
 await io.run({operation:'s7_write',params:{...params,value:999}});
 const out=await io.run({operation:'s7_read',params});assert.equal(out.result.value,999);assert.equal(out.result.simulated,true);
 await sim.stop();assert.equal(sim.status().running,false);
 assert.equal((await io.run({operation:'s7_read',params})).result.value,123);
});
test('S7 readback binds global, flow and module variables without images',async()=>{
 const p=graph.normalize({version:1,name:'S7 variables',steps:[node('write','s7_write',{...params,byteOffset:12,dataType:'float32',value:12.5}),node('read','s7_read',{...params,byteOffset:12,dataType:'float32'}),...['global','flow','module'].map(scope=>node(scope,'variables',{scope,name:'measured',value:{$ref:'results.read.value'}}))]});
 const job=await run(runtime(),p);assert.equal(job.state,'completed',job.error);assert.equal(job.variables.global.measured,12.5);assert.equal(job.variables.flow.measured,12.5);assert.equal(job.variables.modules.module.measured,12.5);
});
test('S7 device writes persist after later failure while variable transaction rolls back',async()=>{
 const r=runtime(),p=graph.normalize({version:1,name:'S7 effects',steps:[node('v','variables',{scope:'flow',name:'temporary',value:5}),node('w','s7_write',{...params,byteOffset:30,value:888}),node('bad','s7_read',{...params,dbNumber:99})]});
 const job=await run(r,p);assert.equal(job.state,'failed');assert.deepEqual(r.snapshot(p).flow,{});assert.equal(job.results[1].output.result.acknowledged,true);
 assert.equal((await io.run({operation:'s7_read',params:{...params,byteOffset:30}})).result.value,888);
});
test('S7 endpoint locking, cancellation and bounded unresponsive peer timeout',async()=>{
 const sockets=new Set(),server=net.createServer(s=>{sockets.add(s);s.on('close',()=>sockets.delete(s));});await new Promise(r=>server.listen(0,'127.0.0.1',r));
 const p={connection:'plc',host:'127.0.0.1',port:server.address().port,timeoutMs:100};
 try{
  const started=Date.now(),pending=io.run({operation:'s7_read',params:p});
  await assert.rejects(io.run({operation:'s7_read',params:p}),/端点正在使用/);
  await assert.rejects(pending,/超时/);assert(Date.now()-started<3000);
  // Endpoint remains locked until the killed worker closes; a different peer key tests immediate abort.
  const controller=new AbortController();controller.abort();await assert.rejects(io.run({operation:'s7_write',params:p},{signal:controller.signal}),/取消/);
 }finally{for(const s of sockets)s.destroy();await new Promise(r=>server.close(r));}
});
test('all S7 demonstration chains execute real vision and S7 protocols',async()=>{
 const directory=path.join(__dirname,'../public/vision/samples'),demos=JSON.parse(fs.readFileSync(path.join(directory,'demos-s7.json')));
 for(const demo of demos){const steps=demo.steps.map((s,i)=>({...s,params:structuredClone(s.params),id:'n'+i}));for(const b of demo.bindings||[])steps[b.step].params[b.param]={$ref:`results.${steps[b.source].id}.${b.field}`};
  const p=graph.normalize({version:1,name:demo.name,steps}),image=fs.readFileSync(path.join(directory,demo.image)).toString('base64');
  const job=await run(runtime(),p,{image});assert.equal(job.state,'completed',job.error);
  if(demo.id==='s7-vision')assert.equal(job.variables.flow.s7Count,3);else if(demo.id==='s7-floats')assert.deepEqual(job.results.at(-1).output.result.values,[12.5,-3.25]);else assert.equal(job.results.at(-1).output.result.value,168);
 }
});
test('cancelling an active S7 write ends the worker and rolls back pending variables',async()=>{
 let accepted;const connected=new Promise(r=>accepted=r),sockets=new Set();
 const server=net.createServer(s=>{sockets.add(s);s.on('data',accepted);s.on('close',()=>sockets.delete(s));});await new Promise(r=>server.listen(0,'127.0.0.1',r));
 const r=runtime(),p=graph.normalize({version:1,name:'S7 cancel',steps:[node('v','variables',{scope:'flow',name:'pending',value:42}),node('w','s7_write',{connection:'plc',host:'127.0.0.1',port:server.address().port,timeoutMs:5000,value:1})]});
 const started=r.start({project:p});let timer;
 try{
  await Promise.race([connected,new Promise((_,reject)=>{timer=setTimeout(()=>reject(Error('S7 worker did not connect')),3000);})]);
  r.cancel(started.id);await r.jobs.get(started.id).promise;
  const job=r.poll(started.id);assert.equal(job.state,'cancelled');assert.match(job.error,/不能回滚/);assert.deepEqual(r.snapshot(p).flow,{});
 }finally{clearTimeout(timer);for(const s of sockets)s.destroy();await new Promise(resolve=>server.close(resolve));}
});
