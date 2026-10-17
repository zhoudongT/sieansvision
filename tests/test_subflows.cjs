'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),os=require('node:os');
const graph=require('../public/vision/flow-graph.js'),{Runtime}=require('../lib/runtime.cjs');
const n=(id,operation,params={})=>({id,operation,params}),e=(from,to,when)=>({id:from+'-'+to,from,to,...(when?{when}:{})});
const def=(id,steps,extra={})=>({version:1,id,name:id,steps,outputNode:steps.at(-1)?.id,...extra});
const p=(steps,subflows,extra={})=>graph.normalize({version:1,id:'macro-project',name:'Macros',steps,subflows,...extra});
const runtime=vision=>new Runtime(fs.mkdtempSync(path.join(os.tmpdir(),'sieans-subflow-')),vision||{run:async()=>{throw Error('unexpected vision');}});
async function run(r,project,options={}){const {id}=r.start({project,...options});await r.jobs.get(id).promise;return r.poll(id);}
const counter=()=>def('counter',[n('inc','variables',{name:'count',mode:'increment',value:1}),n('done','condition',{comparison:'gte',left:{$ref:'flow.count'},right:{$ref:'flow.limit'}})],{variables:{count:0,limit:3}});

test('reusable definitions isolate caller flow/modules and expose typed input/output',async()=>{
 const project=p([n('a','subflow',{subflowId:'counter',arguments:{count:4,limit:5}}),n('b','subflow',{subflowId:'counter'}),n('out','variables',{name:'value',value:{$ref:'results.a.value.passed'}})],[counter()],{variables:{count:99}});
 const job=await run(runtime(),project);assert.equal(job.state,'completed',job.error);assert.equal(job.variables.flow.count,99);assert.equal(job.variables.flow.value,true);assert.equal(job.variables.modules.a._subflow.flow.count,5);assert.equal(job.variables.modules.b._subflow.flow.count,1);assert.equal(job.results[0].output.result.trace.length,2);
});
test('fixed and conditional loops preserve per-invocation state and expose iteration index',async()=>{
 const project=p([n('loop','loop',{subflowId:'counter',iterations:10,mode:'until',stopField:'passed',stopValue:true})],[counter()]);
 const job=await run(runtime(),project);assert.equal(job.state,'completed',job.error);const output=job.results[0].output.result;assert.equal(output.completedIterations,3);assert.equal(output.stoppedEarly,true);assert.equal(output.variables._iteration,3);assert.equal(output.trace.length,6);
 project.steps[0].params.mode='count';project.steps[0].params.iterations=5;const fixed=await run(runtime(),project);assert.equal(fixed.results[0].output.result.completedIterations,5);assert.equal(fixed.results[0].output.result.variables.count,5);
});
test('state preservation is explicit and per call site across runs',async()=>{
 const project=p([n('a','subflow',{subflowId:'counter',stateMode:'preserve'}),n('b','subflow',{subflowId:'counter'})],[counter()]),r=runtime();await run(r,project);const second=await run(r,project);assert.equal(second.variables.modules.a._subflow.flow.count,2);assert.equal(second.variables.modules.b._subflow.flow.count,1);
});
test('nested global writes commit with root and are rolled back when parent later fails',async()=>{
 const global=def('global',[n('write','variables',{scope:'global',name:'total',mode:'increment',value:1})]),outer=def('outer',[n('inner','loop',{subflowId:'global',iterations:2})]);
 const project=p([n('call','subflow',{subflowId:'outer'})],[global,outer]),r=runtime(),job=await run(r,project);assert.equal(job.state,'completed',job.error);assert.equal(job.variables.global.total,2);
 project.steps.push(n('bad','delay',{milliseconds:-1}));project.version=1;const failed=await run(r,project);assert.equal(failed.state,'failed');assert.equal(r.snapshot(graph.normalize(project)).global.total,2);
});
test('subflow failure can route to parent recovery without leaking child global/module writes',async()=>{
 const definition=def('bad',[n('g','variables',{scope:'global',name:'leak',value:1}),n('fail','delay',{milliseconds:-1})]);
 const project=graph.normalize({version:2,id:'recover',name:'Recovery',subflows:[definition],steps:[n('call','subflow',{subflowId:'bad'}),n('handler','variables',{name:'caught',value:{$ref:'results.call.failed'}})],edges:[e('source','call'),e('call','handler','error')]});
 const job=await run(runtime(),project);assert.equal(job.state,'completed',job.error);assert.equal(job.variables.global.leak,undefined);assert.equal(job.variables.modules.call._subflow,undefined);assert.equal(job.variables.flow.caught,true);assert.equal(job.results[0].output.result.trace.length,2);
});
test('until exhaustion and nonboolean stop fields fail with trace and no state publication',async()=>{
 const project=p([n('call','loop',{subflowId:'counter',mode:'until',iterations:2})],[counter()]),r=runtime();let job=await run(r,project);assert.equal(job.state,'failed');assert.match(job.error,/最大轮数/);assert.equal(job.results[0].output.result.trace.length,4);assert.deepEqual(r.snapshot(project).modules.call,{});
 project.steps[0].params.stopField='left';job=await run(r,project);assert.equal(job.state,'failed');assert.match(job.error,/开关/);
});
test('nested image pipeline supports original versus previous frames and cloud propagation',async()=>{
 const seen=[],cloud={unit:'mm',points:[[1,2,3]]},r=runtime({run:async request=>{seen.push(request.image);return {result:{},annotatedImage:request.image+'-processed',elapsedMs:0};}});
 const project=p([n('loop','loop',{subflowId:'image',iterations:3})],[def('image',[n('pre','preprocess')])]);let job=await run(r,project,{image:'raw',cloud});assert.equal(job.state,'completed',job.error);assert.deepEqual(seen,['raw','raw-processed','raw-processed-processed']);assert.deepEqual(job.results[0].output.cloud,cloud);
 seen.length=0;project.steps[0].params.frameMode='original';job=await run(r,project,{image:'raw',cloud});assert.equal(job.state,'completed');assert.deepEqual(seen,['raw','raw','raw']);
});
test('cancel propagates into nested delay and releases runtime without partial variables',async()=>{
 const project=p([n('loop','loop',{subflowId:'wait',iterations:100})],[def('wait',[n('g','variables',{scope:'global',name:'leak',value:1}),n('wait','delay',{milliseconds:30000})])]),r=runtime(),start=r.start({project});
 await new Promise(resolve=>setTimeout(resolve,20));assert.equal(r.poll(start.id).activeStep,'loop');assert.deepEqual(r.poll(start.id).activePath,['loop','wait']);r.cancel(start.id);await r.jobs.get(start.id).promise;assert.equal(r.poll(start.id).state,'cancelled');assert.deepEqual(r.snapshot(project).global,{});assert.equal(r.busy,false);
});
test('nested script trust and plugin preflight happen before any root operation',()=>{
 const project=p([n('write','variables',{name:'root',value:1}),n('call','subflow',{subflowId:'script'})],[def('script',[n('python','script',{code:'result={}'})])]),r=runtime();assert.throws(()=>r.start({project}),/可信 Python/);assert.deepEqual(r.snapshot(project).flow,{});
 project.subflows[0].steps[0].operation='plugin';project.subflows[0].steps[0].params={};assert.throws(()=>r.start({project}),/插件/);
});
test('schema rejects recursive/missing definitions and runtime enforces bounded work',async()=>{
 const recursive=def('self',[n('call','subflow',{subflowId:'self'})]);assert.throws(()=>p([n('x','subflow',{subflowId:'self'})],[recursive]),/递归/);assert.throws(()=>p([n('x','subflow',{subflowId:'missing'})],[]),/不存在/);
 const draft=p([n('x','subflow',{})],[]);assert.throws(()=>runtime().start({project:draft}),/选择子流程/);
 const body=def('large',Array.from({length:10},(_,i)=>n('v'+i,'variables',{name:'v',value:i}))),project=p([n('loop','loop',{subflowId:'large',iterations:100})],[body]);const job=await run(runtime(),project);assert.equal(job.state,'failed');assert.match(job.error,/1000/);
 for(const iterations of [0,101,1.5,'2']){project.steps[0].params.iterations=iterations;assert.match((await run(runtime(),project)).error,/1–100/);}
});

test('definition depth and output repair are deterministic and unused stop bindings are ignored',async()=>{
 const definitions=[def('last',[n('v','variables',{name:'x',value:1})])];for(let i=3;i>=0;i--)definitions.unshift(def('level'+i,[n('call','subflow',{subflowId:definitions[0].id})]));assert.throws(()=>p([n('call','subflow',{subflowId:'level0'})],definitions),/4 层/);
 const body=graph.normalize(counter());assert.equal(graph.remove(body,'done').outputNode,'inc');assert.equal(graph.remove(graph.remove(body,'done'),'inc').outputNode,null);
 const project=p([n('loop','loop',{subflowId:'counter',iterations:2,mode:'count',stopField:{$ref:'flow.missing'},stopValue:{$ref:'flow.missing'}})],[counter()]);assert.equal((await run(runtime(),project)).state,'completed');
 project.steps[0].params.arguments={_iteration:99};assert.match((await run(runtime(),project)).error,/只读轮次/);
});


test('selected output annotation is displayed while downstream gets unpainted pixels',async()=>{
 const inputs=[],r=runtime({run:async request=>{inputs.push(request.image);return {result:{count:3},annotatedImage:'overlay',elapsedMs:0};}}),project=p([n('call','subflow',{subflowId:'inspect'}),n('next','geometry')],[def('inspect',[n('find','geometry')])]);
 const job=await run(r,project,{image:'raw'});assert.equal(job.state,'completed',job.error);assert.deepEqual(inputs,['raw','raw']);assert.equal(job.results[0].output.annotatedImage,'overlay');assert.equal(job.results[0].output.image,'raw');
});

test('continuous root jobs preserve an explicit call-site state without nested commits or owner deadlock',async()=>{
 const {ContinuousRun}=require('../lib/continuous-run.cjs'),r=runtime(),runner=new ContinuousRun(r,path.dirname(r.variables.file));
 const project=p([n('loop','loop',{subflowId:'counter',iterations:2,stateMode:'preserve'})],[counter()]);runner.start({project,intervalMs:100,maxCycles:2});await runner.promise;
 assert.equal(runner.status().state,'completed');assert.equal(runner.status().completedCycles,2);assert.equal(r.snapshot(project).modules.loop._subflow.flow.count,4);assert.equal(r.snapshot(project).revision,2);assert.equal(r.busy,false);
});
