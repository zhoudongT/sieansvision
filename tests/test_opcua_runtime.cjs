const {test,after}=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),net=require('node:net');
const {Runtime}=require('../lib/runtime.cjs'),graph=require('../public/vision/flow-graph.js');
const io=require('../lib/industrial-client.cjs'),sim=require('../lib/opcua-simulator.cjs'),vision=require('../lib/vision-client.cjs');
const runtime=()=>new Runtime(fs.mkdtempSync(path.join(os.tmpdir(),'sieans-opcua-test-')),vision);
const node=(id,operation,params)=>({id,operation,params});
const p=(params={})=>({connection:'simulator',nodeId:'ns=2;s=SIEANS.Count',...params});
async function run(r,project,extra={}){const started=r.start({project,...extra});await r.jobs.get(started.id).promise;return r.poll(started.id);}
after(async()=>{vision.stop();await io.stop();});

test('OPC UA simulator starts once, browses root and resets on restart',async()=>{
 const [a,b]=await Promise.all([sim.start(),sim.start()]);assert.equal(a.endpoint,b.endpoint);assert.equal(a.host,'127.0.0.1');
 const root=await io.run({operation:'opcua_browse',params:p({nodeId:'i=85'})});assert(root.result.items.some(i=>i.browseName==='SIEANS'));
 await io.run({operation:'opcua_write',params:p({dataType:'UInt32',value:12})});assert.equal((await io.run({operation:'opcua_read',params:p()})).result.value,12);
 await sim.stop();assert.equal(sim.status().running,false);assert.equal((await io.run({operation:'opcua_read',params:p()})).result.value,0);
});

test('OPC UA values feed variables without an input image',async()=>{
 const project=graph.normalize({version:1,name:'OPC values',steps:[node('write','opcua_write',p({dataType:'UInt32',value:55})),node('read','opcua_read',p()),node('save','variables',{scope:'flow',name:'value',value:{$ref:'results.read.value'}})]});
 const job=await run(runtime(),project);assert.equal(job.state,'completed',job.error);assert.equal(job.variables.flow.value,55);assert.equal(job.results[1].output.result.quality,'good');
});

test('OPC UA write remains external when downstream failure rolls back variables',async()=>{
 const r=runtime(),project=graph.normalize({version:1,name:'external write',steps:[node('v','variables',{scope:'global',name:'changed',value:1}),node('write','opcua_write',p({dataType:'UInt32',value:99})),node('bad','opcua_read',p({nodeId:'ns=2;s=missing'}))]});
 const job=await run(r,project);assert.equal(job.state,'failed');assert.deepEqual(r.snapshot(project).global,{});assert.equal((await io.run({operation:'opcua_read',params:p()})).result.value,99);
});

test('OPC UA endpoint lock and cancellation bound an unresponsive peer',async()=>{
 let connected;const ready=new Promise(resolve=>connected=resolve),sockets=new Set();const server=net.createServer(socket=>{sockets.add(socket);connected();socket.on('close',()=>sockets.delete(socket));});await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const params={endpoint:`opc.tcp://127.0.0.1:${server.address().port}/`,nodeId:'ns=2;s=Count',dataType:'UInt32',value:1,timeoutMs:10000},controller=new AbortController();
 const pending=io.run({operation:'opcua_write',params},{signal:controller.signal});pending.catch(()=>{});
 let timer;
 try{await Promise.race([ready,new Promise((_,reject)=>timer=setTimeout(()=>reject(Error('No peer connection')),5000))]);await assert.rejects(io.run({operation:'opcua_read',params}),/端点正在使用/);controller.abort();await assert.rejects(pending,/不能回滚/);}
 finally{clearTimeout(timer);controller.abort();for(const socket of sockets)socket.destroy();await new Promise(resolve=>server.close(resolve));}
});

test('both OPC UA demos execute real vision and protocol transactions',async()=>{
 const directory=path.join(__dirname,'../public/vision/samples'),demos=JSON.parse(fs.readFileSync(path.join(directory,'demos-opcua.json')));
 for(const demo of demos){const steps=demo.steps.map((s,i)=>({...s,id:'n'+i,params:structuredClone(s.params)}));for(const b of demo.bindings||[])steps[b.step].params[b.param]={$ref:`results.n${b.source}.${b.field}`};
  const project=graph.normalize({version:1,name:demo.name,steps}),image=fs.readFileSync(path.join(directory,demo.image)).toString('base64');const job=await run(runtime(),project,{image});assert.equal(job.state,'completed',job.error);
  if(demo.id==='opcua-vision')assert.equal(job.variables.flow.uaCount,3);else assert.deepEqual(job.results.at(-1).output.result.value,[12.5,-3.25,8]);
 }
});
