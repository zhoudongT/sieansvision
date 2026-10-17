'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),os=require('node:os'),path=require('node:path'),net=require('node:net');
const {Runtime}=require('../lib/runtime.cjs'),{MqttTrigger,settings}=require('../lib/mqtt-trigger.cjs'),transport=require('../lib/mqtt-client.cjs'),simulator=require('../lib/mqtt-simulator.cjs');
const project=()=>({version:1,id:'event-test',name:'事件消息检测',variables:{count:0},steps:[{id:'copy',operation:'variables',params:{scope:'flow',name:'value',value:{$ref:'flow.mqttEvent.value'}}},{id:'counter',operation:'variables',params:{scope:'flow',name:'count',mode:'increment',value:1}}]});
const input=()=>({project:project(),connection:{connection:'simulator',topic:'sieans/event',encoding:'structured',qos:1},reconnectMs:200,capacity:10,maxAgeMs:30000});
async function until(fn,ms=5000){const end=Date.now()+ms;while(!fn()){if(Date.now()>end)throw Error('condition timed out');await new Promise(r=>setTimeout(r,10));}}
function setup(t){const directory=fs.mkdtempSync(path.join(os.tmpdir(),'sieans-mqtt-trigger-')),runtime=new Runtime(directory,{}),runner=new MqttTrigger(runtime,directory);t.after(async()=>{await runner.shutdown();await transport.stop();});return {directory,runtime,runner};}
const publish=value=>transport.run({operation:'mqtt_publish',params:{connection:'simulator',topic:'sieans/event',encoding:'structured',value,qos:1,retain:false}});

test('trigger settings validate bounds, reserved variables, keys and secure connection options',()=>{
 const body=input();assert.equal(settings(body).c.acceptRetained,false);assert.equal(settings(body).c.options.rejectUnauthorized,undefined);
 for(const patch of [{capacity:0},{maxAgeMs:99},{reconnectMs:0},{variable:'constructor'},{keyField:'x.__proto__'},{overflow:'silently'}])assert.throws(()=>settings({...body,...patch}));
 assert.throws(()=>settings({...body,connection:{connection:'broker',security:'tls',privateKey:'missing'}}),/成对/);
 const canonical=settings({...body,connection:{...body.connection,extra:'x'.repeat(100000),password:'must-not-be-stored'}}).publicConnection;assert.equal(canonical.extra,undefined);assert.equal(canonical.password,undefined);
});
test('real subscriptions execute queued messages serially with transactional event inputs and history',async t=>{
 const {runtime,runner}=setup(t),body=input();runner.start(body);await until(()=>runner.ready);body.project.steps[1].params.value=100;
 await Promise.all([publish({id:1,count:3}),publish({id:2,count:5})]);await until(()=>runner.state.completed===2);
 assert.equal(runtime.snapshot(project()).flow.count,2);assert.ok([1,2].includes(runtime.snapshot(project()).flow.value.id));assert.equal(runtime.busy,true);
 assert.throws(()=>runtime.start({project:project()}),/其他任务/);assert.throws(()=>runner.stop('old-id'),/已变化/);
 const history=runtime.history.records;assert.equal(history.length,2);const record=await runtime.history.get(history[0].id);assert.equal(record.origin,'mqtt');assert.equal(record.trigger.kind,'mqtt');assert.equal(record.trigger.message.topic,'sieans/event');
 runner.stop(runner.state.id);await runner.finishPromise;assert.equal(runtime.busy,false);assert.equal(transport.activeCount(),0);
});
test('retained messages default to excluded; business dedup requires an explicit scalar key',async t=>{
 const {runner}=setup(t);await transport.run({operation:'mqtt_publish',params:{connection:'simulator',topic:'sieans/event',encoding:'structured',value:{id:'old'},retain:true}});
 runner.start({...input(),keyField:'id'});await until(()=>runner.ready);await until(()=>runner.state.dropped===1);assert.equal(runner.state.completed,0);
 await publish({id:'new'});await until(()=>runner.state.completed===1);await publish({id:'new'});await until(()=>runner.state.duplicates===1);await publish({missing:true});await until(()=>runner.state.invalid===1);assert.equal(runner.state.completed,1);
});
test('malformed messages are rejected and later valid messages still run',async t=>{
 const {runner}=setup(t);runner.start(input());await until(()=>runner.ready);
 await transport.run({operation:'mqtt_publish',params:{connection:'simulator',topic:'sieans/event',encoding:'text',value:'not-structured'}});await until(()=>runner.state.invalid===1);await publish(12);await until(()=>runner.state.completed===1);
});
test('queue overflow stops and cancels the active transaction instead of retrying device effects',async t=>{
 const {runtime,runner}=setup(t),body=input();body.capacity=1;body.project.steps.unshift({id:'delay',operation:'delay',params:{milliseconds:2000}});runner.start(body);await until(()=>runner.ready);
 await publish(1);await until(()=>runner.state.lastJobId);await publish(2);await until(()=>runner.queue.length===1);await publish(3);await until(()=>runner.state.state==='failed');
 assert.match(runner.state.error,/队列已满/);assert.equal(runtime.snapshot(project()).flow.count,0);assert.equal(runner.state.dropped,2);assert.equal(runtime.busy,false);assert.equal(runtime.jobs.get(runner.state.lastJobId).state,'cancelled');
});
test('drop-oldest and expiry are bounded and explicitly counted',async t=>{
 const {runner,runtime}=setup(t),body=input();body.capacity=1;body.overflow='dropOldest';body.maxAgeMs=100;body.project.steps.unshift({id:'delay',operation:'delay',params:{milliseconds:300}});runner.start(body);await until(()=>runner.ready);
 await publish(1);await until(()=>runner.state.lastJobId);await publish(2);await publish(3);await until(()=>runner.state.completed===1&&runner.state.expired===1);assert.equal(runner.state.dropped,1);assert.equal(runtime.snapshot(project()).flow.value,1);
});
test('failed typed input rolls back event and flow variables and does not replay queued messages',async t=>{
 const {runner,runtime}=setup(t),body=input();body.project.variables.value=0;body.project.variableTypes={value:'number'};runner.start(body);await until(()=>runner.ready);await publish({bad:true});await until(()=>runner.state.state==='failed');assert.equal(runtime.snapshot(project()).flow.mqttEvent,undefined);assert.equal(runtime.snapshot(project()).flow.count,0);
});
test('persistence failures stop subscription and release the runtime; restart never replays queue',async t=>{
 const {runner,runtime,directory}=setup(t);runner.start(input());await until(()=>runner.ready);const saved=JSON.parse(fs.readFileSync(runner.file));saved.queued=3;fs.writeFileSync(runner.file,JSON.stringify(saved));const restored=new MqttTrigger(new Runtime(directory,{}),directory);assert.equal(restored.state.state,'interrupted');assert.equal(restored.state.dropped,3);assert.equal(restored.busy,false);assert.equal(restored.project,null);
 runner.persist=()=>{throw Error('disk full');};await publish(1);await until(()=>runner.state.state==='failed');assert.match(runner.state.error,/disk full/);assert.equal(runtime.busy,false);
});
test('actual broker disconnect reconnects and resubscribes without replaying the last completed event',async t=>{
 const {Aedes}=await import('aedes'),sockets=new Set();let broker,server,port;
 async function startBroker(){broker=await Aedes.createBroker();server=net.createServer(socket=>{sockets.add(socket);socket.on('close',()=>sockets.delete(socket));socket.on('error',()=>{});broker.handle(socket);});await new Promise(r=>server.listen(port||0,'127.0.0.1',r));port=server.address().port;}
 async function stopBroker(){const closed=new Promise(r=>server.close(r));for(const socket of sockets)socket.destroy();await new Promise(r=>broker.close(r));await closed;}
 await startBroker();const {runner}=setup(t);t.after(stopBroker);const body=input();body.connection={...body.connection,connection:'broker',host:'127.0.0.1',port};runner.start(body);await until(()=>runner.ready);
 const send=value=>transport.run({operation:'mqtt_publish',params:{...body.connection,value,retain:false}});await send(1);await until(()=>runner.state.completed===1);await stopBroker();await until(()=>runner.state.state==='reconnecting');await startBroker();await until(()=>runner.ready);await send(2);await until(()=>runner.state.completed===2);assert.ok(runner.state.reconnects>=1);
});
test('immediate stop while connecting and stopping an empty subscription leave no client or runtime lease',async t=>{
 const {runner,runtime}=setup(t);runner.start(input());runner.stop(runner.state.id);await runner.finishPromise;assert.equal(runtime.busy,false);assert.equal(transport.activeCount(),0);assert.equal(runner.state.completed,0);
 runner.start(input());await until(()=>runner.ready);runner.stop(runner.state.id);await runner.finishPromise;assert.equal(runtime.busy,false);assert.equal(transport.activeCount(),0);
});
test('a client ID collision fails before subscribing and releases only the new runtime lease',async t=>{
 const {runner,runtime}=setup(t),controller=new AbortController(),waiting=transport.run({operation:'mqtt_receive',params:{connection:'simulator',topic:'never',clientId:'collision',timeoutMs:30000}},{signal:controller.signal});waiting.catch(()=>{});
 assert.throws(()=>runner.start({...input(),connection:{...input().connection,clientId:'collision'}}),/客户端标识正在使用/);assert.equal(runtime.busy,false);assert.equal(transport.activeCount(),1);controller.abort();await assert.rejects(waiting,/取消/);assert.equal(transport.activeCount(),0);
});
