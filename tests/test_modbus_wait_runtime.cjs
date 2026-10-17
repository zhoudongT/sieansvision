'use strict';
const {test,after}=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path'),net=require('node:net');
const {Runtime}=require('../lib/runtime.cjs'),{ContinuousRun}=require('../lib/continuous-run.cjs');
const graph=require('../public/vision/flow-graph.js'),io=require('../lib/industrial-client.cjs'),vision=require('../lib/vision-client.cjs');
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const step=(id,operation,params)=>({id,operation,params});
const waiting=extra=>({transport:'simulator',area:'holding',address:0,comparison:'eq',expectedValue:123,waitTimeoutMs:1000,pollIntervalMs:20,...extra});
function setup(){const dir=fs.mkdtempSync(path.join(os.tmpdir(),'sieans-trigger-'));return {dir,r:new Runtime(dir,vision)};}
async function run(r,project,extra={}){const job=r.start({project,...extra});await r.jobs.get(job.id).promise;return r.poll(job.id);}
after(async()=>{vision.stop();await io.stop();});

test('trigger forwards the image to real detection and binds signal and count into variables',async()=>{
 const {r}=setup(),p=graph.normalize({version:1,name:"PLC trigger test",steps:[step('wait','modbus_wait',waiting({stableMs:40})),step('detect','geometry',{feature:'contours',threshold:127,minArea:50}),step('save','variables',{name:'count',value:{$ref:'results.detect.count'}})]});
 const image='data:image/png;base64,'+fs.readFileSync(path.join(__dirname,'../public/vision/samples/parts.png')).toString('base64');
 const job=await run(r,p,{image});assert.equal(job.state,'completed',job.error);assert.equal(job.results[0].output.result.triggered,true);assert.equal(job.variables.flow.count,3);
});

test('timeout error prevents downstream execution and rolls back prior variables',async()=>{
 const {r}=setup(),p=graph.normalize({version:1,name:"PLC trigger test",variables:{count:0},steps:[step('before','variables',{name:'count',value:9}),step('wait','modbus_wait',waiting({expectedValue:-1,waitTimeoutMs:100})),step('after','variables',{name:'ran',value:true})]});
 const job=await run(r,p);assert.equal(job.state,'failed');assert.match(job.error,/等待 Modbus 信号超时/);assert.equal(job.results.length,2);assert.deepEqual(r.snapshot(p).flow,{count:0});
});

test('timeout continue reports false and can select an explicit timeout branch',async()=>{
 const {r}=setup(),p=graph.normalize({version:2,name:"PLC branch test",steps:[step('wait','modbus_wait',waiting({expectedValue:-1,waitTimeoutMs:100,onTimeout:'continue'})),step('check','condition',{comparison:'is_true',left:{$ref:'results.wait.triggered'}}),step('yes','variables',{name:'route',value:'detect'}),step('no','variables',{name:'route',value:'timeout'})],edges:[{id:'a',from:'source',to:'wait'},{id:'b',from:'wait',to:'check'},{id:'c',from:'check',to:'yes',when:'true'},{id:'d',from:'check',to:'no',when:'false'}]});
 const job=await run(r,p);assert.equal(job.state,'completed',job.error);assert.equal(job.variables.flow.route,'timeout');assert.equal(job.results.find(x=>x.id==='yes').skipped,true);
});

test('boolean signal ignores an unused comparison binding',async()=>{
 const {r}=setup(),p=graph.normalize({version:1,name:"PLC trigger test",steps:[step('wait','modbus_wait',waiting({area:'discrete',comparison:'is_true',expectedValue:{$ref:'flow.missing'}}))]});
 const job=await run(r,p);assert.equal(job.state,'completed',job.error);assert.equal(job.results[0].output.result.value,true);
});

test('continuous trigger retains endpoint ownership and stop cancels an in-flight read',async()=>{
 const sockets=new Set();let received;const request=new Promise(resolve=>received=resolve);
 const server=net.createServer(socket=>{sockets.add(socket);socket.on('error',()=>{});socket.on('data',received);socket.on('close',()=>sockets.delete(socket));});
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const {r,dir}=setup(),runner=new ContinuousRun(r,dir),params=waiting({transport:'tcp',host:'127.0.0.1',port:server.address().port,timeoutMs:5000,waitTimeoutMs:600000});
 const p=graph.normalize({version:1,name:"PLC trigger test",steps:[step('before','variables',{name:'count',value:9}),step('wait','modbus_wait',params),step('after','variables',{name:'ran',value:true})]});
 try{
  const started=runner.start({project:p,intervalMs:100,maxCycles:2});await request;
  await assert.rejects(io.run({operation:'modbus_read',params}),/端点正在使用/);
  const began=Date.now();runner.stop(started.id);await runner.promise;
  assert.ok(Date.now()-began<1500);assert.equal(runner.state.cancelledCycles,1);assert.equal(runner.state.completedCycles,0);assert.deepEqual(r.snapshot(p).flow,{});assert.equal(r.busy,false);
  for(let i=0;i<100&&io.activeCount();i++)await sleep(10);
  assert.equal(io.activeCount(),0);
 }finally{if(runner.busy){runner.stop(runner.state.id);await runner.promise;}for(const s of sockets)s.destroy();await new Promise(resolve=>server.close(resolve));}
});

test('continuous level mode runs a bounded number of complete inspections',async()=>{
 const {r,dir}=setup(),runner=new ContinuousRun(r,dir),p=graph.normalize({version:1,name:"PLC trigger test",steps:[step('wait','modbus_wait',waiting()),step('count','variables',{name:'cycles',mode:'increment',value:1})]});
 runner.start({project:p,intervalMs:100,maxCycles:2});await runner.promise;
 assert.equal(runner.state.completedCycles,2);assert.equal(r.snapshot(p).flow.cycles,2);assert.equal(r.busy,false);
});
