const {test,after}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path'),net=require('node:net');
const {Runtime}=require('../lib/runtime.cjs');
const graph=require('../public/vision/flow-graph.js');
const io=require('../lib/industrial-client.cjs'),sim=require('../lib/modbus-simulator.cjs'),vision=require('../lib/vision-client.cjs');
const runtime=()=>new Runtime(fs.mkdtempSync(path.join(os.tmpdir(),'sieans-io-test-')),vision);
const node=(id,operation,params)=>({id,operation,params});
async function run(r,p,extra={}){const started=r.start({project:p,...extra});await r.jobs.get(started.id).promise;return r.poll(started.id);}
after(async()=>{vision.stop();await io.stop();});

test('simulator lifecycle uses real localhost TCP and resets on restart',async()=>{
 const a=await sim.start(),b=await sim.start();assert.equal(a.port,b.port);assert.equal(a.host,'127.0.0.1');
 let out=await io.run({operation:'modbus_read',params:{transport:'simulator',address:0}});assert.equal(out.result.value,123);assert.equal(out.result.simulated,true);
 await io.run({operation:'modbus_write',params:{transport:'simulator',address:0,value:88}});
 out=await io.run({operation:'modbus_read',params:{transport:'simulator',address:0}});assert.equal(out.result.value,88);
 await sim.stop();assert.equal(sim.status().running,false);await sim.start();
 out=await io.run({operation:'modbus_read',params:{transport:'simulator',address:0}});assert.equal(out.result.value,123);
});
test('Modbus results bind flow variables without requiring an image',async()=>{
 const r=runtime(),p=graph.normalize({version:1,name:'PLC pipeline',steps:[node('w','modbus_write',{transport:'simulator',address:12,dataType:'float32',value:12.5}),node('r','modbus_read',{transport:'simulator',address:12,dataType:'float32'}),node('v','variables',{scope:'flow',name:'measured',value:{$ref:'results.r.value'}})]});
 const job=await run(r,p);assert.equal(job.state,'completed',job.error);assert.equal(job.variables.flow.measured,12.5);
});
test('later failure rolls back variables but does not claim to undo a device write',async()=>{
 const r=runtime(),p=graph.normalize({version:1,name:'external effects',steps:[node('v','variables',{scope:'global',name:'test',value:1}),node('w','modbus_write',{transport:'simulator',address:20,value:999}),node('fail','modbus_read',{transport:'simulator',address:500})]});
 const job=await run(r,p);assert.equal(job.state,'failed');assert.deepEqual(r.snapshot(p).global,{});
 const out=await io.run({operation:'modbus_read',params:{transport:'simulator',address:20}});assert.equal(out.result.value,999);
 assert.equal(job.results[1].output.result.acknowledged,true);
});
test('endpoint lock and cancellation terminate an unresponsive transaction',async()=>{
 const sockets=new Set(),server=net.createServer(socket=>{sockets.add(socket);socket.on('error',error=>{assert.equal(error.code,'ECONNRESET');});socket.on('close',()=>sockets.delete(socket));});await new Promise(r=>server.listen(0,'127.0.0.1',r));
 const params={transport:'tcp',host:'127.0.0.1',port:server.address().port,timeoutMs:5000};
 const controller=new AbortController(),pending=io.run({operation:'modbus_read',params},{signal:controller.signal});
 try{
  await assert.rejects(io.run({operation:'modbus_read',params}),/端点正在使用/);
  controller.abort();await assert.rejects(pending,/取消/);
 }finally{for(const socket of sockets)socket.destroy();await new Promise(r=>server.close(r));}
});
test('vision to Modbus to variables demonstration executes real vision and protocol',async()=>{
 const directory=path.join(__dirname,'../public/vision/samples'),demos=JSON.parse(fs.readFileSync(path.join(directory,'demos-industrial.json')));
 for(const demo of demos){const steps=demo.steps.map((s,i)=>({...s,params:structuredClone(s.params),id:'n'+i}));for(const b of demo.bindings||[])steps[b.step].params[b.param]={$ref:`results.${steps[b.source].id}.${b.field}`};
  const p=graph.normalize({version:demo.connections?2:1,name:demo.name,steps,...(demo.connections?{edges:demo.connections.map(([from,to,when],i)=>({id:'e'+i,from:from<0?'source':steps[from].id,to:steps[to].id,...(when?{when}:{})}))}:{})}),image=demo.camera?'':fs.readFileSync(path.join(directory,demo.image)).toString('base64');
  const job=await run(runtime(),p,{image});
  if(demo.id==='plc-wait-stop'){assert.equal(job.state,'failed');assert.match(job.error,/等待 Modbus 信号超时/);assert.equal(job.results.length,2);continue;}
  assert.equal(job.state,'completed',job.error);
  if(demo.id==='modbus-vision')assert.equal(job.variables.flow.plcCount,3);
  else if(demo.id==='modbus-float')assert.deepEqual(job.results.at(-1).output.result.values,[12.5,-3.25]);
  else if(demo.id==='plc-trigger-camera'){assert.equal(job.results[1].output.result.triggered,true);assert.equal(job.variables.flow.triggeredCount,3);}
  else if(demo.id==='plc-edge-timeout'){assert.equal(job.variables.flow.triggerRoute,'TIMEOUT');assert.equal(job.results.find(x=>x.id==='n3').skipped,true);}
  else assert.fail('新增演示需要明确验收断言：'+demo.id);
 }
});
test('cancelled PLC write reports uncertain external state and rolls back variables',async()=>{
 let markSent;const sent=new Promise(r=>markSent=r),sockets=new Set();
 // Killing the cancelled adapter may reset the intentionally unresponsive peer.
 const server=net.createServer(socket=>{sockets.add(socket);socket.on('error',error=>{assert.equal(error.code,'ECONNRESET');});socket.on('data',markSent);socket.on('close',()=>sockets.delete(socket));});await new Promise(r=>server.listen(0,'127.0.0.1',r));
 const r=runtime(),p=graph.normalize({version:1,name:'cancel writing',steps:[node('v','variables',{scope:'flow',name:'test',value:42}),node('w','modbus_write',{transport:'tcp',host:'127.0.0.1',port:server.address().port,timeoutMs:5000,value:1})]});
 const started=r.start({project:p});
 try{await sent;r.cancel(started.id);await r.jobs.get(started.id).promise;const job=r.poll(started.id);assert.equal(job.state,'cancelled');assert.match(job.error,/不能回滚/);assert.deepEqual(r.snapshot(p).flow,{});}
 finally{for(const socket of sockets)socket.destroy();await new Promise(resolve=>server.close(resolve));}
});
