'use strict';
const {test,after}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),os=require('node:os');
const {Runtime}=require('../lib/runtime.cjs'),{ContinuousRun}=require('../lib/continuous-run.cjs'),io=require('../lib/industrial-client.cjs'),vision=require('../lib/vision-client.cjs'),graph=require('../public/vision/flow-graph.js');
const defaults={connection:'simulator',nodeId:'ns=2;s=SIEANS.Count',timeoutMs:3000,waitTimeoutMs:5000,publishingIntervalMs:20,comparison:'eq',expectedValue:0,onTimeout:'error',triggerMode:'level'};
const step=(id,operation,params)=>({id,operation,params}),wait=(params={})=>step('wait','opcua_wait',{...defaults,...params});
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
async function drained(){for(let i=0;i<200&&io.activeCount();i++)await sleep(20);assert.equal(io.activeCount(),0);}
async function reset(){await drained();await io.run({operation:'opcua_write',params:{connection:'simulator',nodeId:defaults.nodeId,dataType:'UInt32',value:0}});}
function runtime(){return new Runtime(fs.mkdtempSync(path.join(os.tmpdir(),'sieans-opcua-wait-')),vision);}
async function execute(r,steps){const started=r.start({project:{version:1,id:'opcua-wait',name:'UA 订阅触发',steps}});await r.jobs.get(started.id).promise;return r.poll(started.id);}
after(async()=>{vision.stop();await io.stop();});

test('OPC UA subscription gates actual camera/detection and all variable scopes',async()=>{
 await reset();const r=runtime(),job=await execute(r,[wait(),step('camera','camera_capture',{driver:'simulator'}),step('find','geometry',{threshold:127,minArea:50}),step('save','variables',{scope:'flow',name:'count',value:{$ref:'results.find.count'}}),step('global','variables',{scope:'global',name:'ready',value:{$ref:'results.wait.triggered'}}),step('module','variables',{scope:'module',name:'sample',value:{$ref:'results.wait.notificationCount'}})]);
 assert.equal(job.state,'completed',job.error);assert.equal(job.variables.flow.count,3);assert.equal(job.variables.global.ready,true);assert.equal(job.variables.modules.module.sample,1);assert.equal(job.results[0].output.result.quality,'good');
});

test('initial matching notification does not become rising edge; timeout can branch or roll back',async()=>{
 await reset();let r=runtime(),job=await execute(r,[wait({triggerMode:'rising',waitTimeoutMs:1000,onTimeout:'continue'}),step('save','variables',{scope:'flow',name:'triggered',value:{$ref:'results.wait.triggered'}})]);
 assert.equal(job.state,'completed',job.error);assert.equal(job.variables.flow.triggered,false);assert.equal(job.results[0].output.result.timedOut,true);assert.equal(job.results[0].output.result.timeoutConnectionVerified,true);
 r=runtime();job=await execute(r,[step('temp','variables',{scope:'global',name:'pending',value:42}),wait({expectedValue:99,waitTimeoutMs:1000}),step('camera','camera_capture',{driver:'simulator'})]);assert.equal(job.state,'failed');assert.match(job.error,/信号超时/);assert.equal(r.snapshot({version:1,id:'opcua-wait',name:'snapshot',steps:[]}).global.pending,undefined);assert(!job.results.some(row=>row.id==='camera'));
});

test('wait holds endpoint lock and cancellation does not execute downstream or retain variables',async()=>{
 await reset();const r=runtime(),start=r.start({project:{version:1,id:'opcua-cancel',name:'cancel',steps:[step('temp','variables',{scope:'flow',name:'pending',value:1}),wait({expectedValue:99,waitTimeoutMs:30000}),step('camera','camera_capture',{driver:'simulator'})]}});
 for(let i=0;i<200&&!io.activeCount();i++)await sleep(20);assert.equal(io.activeCount(),1);
 await assert.rejects(io.run({operation:'opcua_read',params:{connection:'simulator',nodeId:defaults.nodeId}}),/端点正在使用/);
 r.cancel(start.id);await r.jobs.get(start.id).promise;const job=r.poll(start.id);assert.equal(job.state,'cancelled');assert(!job.results.some(row=>row.id==='camera'));assert.equal(r.snapshot({version:1,id:'opcua-cancel',name:'snapshot',steps:[]}).flow.pending,undefined);await drained();
});

test('continuous calls establish their own bounded subscription and do not block the next cycle',async()=>{
 await reset();const r=runtime(),continuous=new ContinuousRun(r,fs.mkdtempSync(path.join(os.tmpdir(),'sieans-opcua-cycles-')));
 continuous.start({project:{version:1,id:'opcua-cycles',name:'cycles',steps:[wait()]},intervalMs:100,maxCycles:2});await continuous.promise;assert.equal(continuous.status().state,'completed',continuous.status().error);assert.equal(continuous.status().completedCycles,2);await drained();
});

test('Node-RED wait node keeps input channels and delegates cancellation on close',async()=>{
 await reset();let Constructor;require('../plugins/node-red-contrib-machine/nodes/industrial.js')({settings:{machineIndustrial:io},nodes:{registerType(name,C){if(name==='machine-opcua_wait')Constructor=C;},createNode(n){n.handlers={};n.on=(name,fn)=>n.handlers[name]=fn;n.status=()=>{};}}});assert(Constructor);
 const node=new Constructor({params:JSON.stringify(defaults)}),msg={image:'kept',cloud:{unit:'mm',points:[[0,0,0]]}},sent=[];let error;await node.handlers.input(msg,value=>sent.push(value),e=>error=e);assert.equal(error,undefined);assert.equal(sent[0].payload.triggered,true);assert.equal(sent[0].image,'kept');assert.deepEqual(sent[0].cloud,msg.cloud);
 const waiting=new Constructor({params:JSON.stringify({...defaults,expectedValue:99,waitTimeoutMs:30000})});const pending=waiting.handlers.input({},()=>assert.fail('closed node sent output'),e=>error=e);for(let i=0;i<200&&!io.activeCount();i++)await sleep(10);waiting.handlers.close();await pending;assert.match(error.message,/取消/);await drained();
});
