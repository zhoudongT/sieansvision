'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path');
const {Runtime}=require('../lib/runtime.cjs'),{ContinuousRun}=require('../lib/continuous-run.cjs');
const graph=require('../public/vision/flow-graph.js');
const folder=()=>fs.mkdtempSync(path.join(os.tmpdir(),'sieans-continuous-'));
const step=(id,operation,params={})=>({id,operation,params});
const counter=()=>graph.normalize({version:1,id:'cycle-counter',name:'连续计数',steps:[step('counter','variables',{scope:'flow',name:'count',mode:'increment',value:1})]});
function setup(vision={}){const directory=folder(),runtime=new Runtime(directory,vision),runner=new ContinuousRun(runtime,directory);return {directory,runtime,runner};}
async function until(predicate){const end=Date.now()+3000;while(!predicate()){if(Date.now()>end)throw Error('condition timed out');await new Promise(r=>setTimeout(r,5));}}

test('finite cycles commit separately, preserve input snapshot and reserve the runtime between jobs',async()=>{
  const {runner,runtime}=setup(),project=counter(),s=runner.start({project,intervalMs:100,maxCycles:3});
  project.steps[0].params.value=100;
  await until(()=>runner.state.state==='waiting');
  assert.equal(runtime.active,null);assert.equal(runtime.busy,true);
  assert.throws(()=>runtime.start({project}),/其他任务/);
  assert.throws(()=>runtime.update(project,{global:{},flow:{},modules:{}},0),/执行期间/);
  assert.throws(()=>runner.start({project}),/其他任务/);
  await runner.promise;
  assert.equal(runner.status().state,'completed');assert.equal(runner.status().completedCycles,3);
  assert.equal(runtime.snapshot(project).flow.count,3);assert.equal(runtime.busy,false);
  assert.equal(runner.status().id,s.id);assert.equal(runner.request,null);
});
test('a slow cycle never overlaps and a stop during the interval starts no additional job',async()=>{
  let release,calls=0;const {runner}=setup({run:()=>{calls++;return new Promise(r=>release=r);}});
  const project=graph.normalize({version:1,id:'slow',name:'slow',steps:[step('vision','geometry')]});
  const s=runner.start({project,image:'fixture',intervalMs:100,maxCycles:0});await until(()=>calls===1);
  await new Promise(r=>setTimeout(r,150));assert.equal(calls,1);
  release({result:{count:3},elapsedMs:0,annotatedImage:'fixture'});await until(()=>runner.state.state==='waiting');
  runner.stop(s.id);await runner.promise;
  assert.equal(calls,1);assert.equal(runner.status().state,'stopped');assert.equal(runner.status().completedCycles,1);
});
test('stop cancels an active cycle and rolls back only its variable writes',async()=>{
  const {runner,runtime}=setup();const project=counter();project.steps.push(step('wait','delay',{milliseconds:30000}));
  // Re-normalize as a legacy sequence to add the dependency for this fixture.
  const p=graph.normalize({version:1,id:project.id,name:project.name,steps:project.steps});
  const s=runner.start({project:p,intervalMs:100});await until(()=>runtime.active?.activeStep==='wait');
  runner.stop(s.id);await runner.promise;
  assert.equal(runner.status().cancelledCycles,1);assert.equal(runner.status().completedCycles,0);
  assert.deepEqual(runtime.snapshot(p).flow,{});assert.equal(runtime.busy,false);
});
test('first failure stops repetitions, preserving earlier successful transactions',async()=>{
  let calls=0;const {runner,runtime}=setup({run:async()=>{if(++calls===2)throw Error('camera lost');return {result:{},elapsedMs:0};}});
  const p=graph.normalize({version:1,id:'failure',name:'failure',steps:[...counter().steps,step('check','geometry')]});
  runner.start({project:p,image:'fixture',intervalMs:100});await runner.promise;
  assert.equal(runner.status().state,'failed');assert.equal(runner.status().completedCycles,1);
  assert.equal(runner.status().failedCycles,1);assert.match(runner.status().error,/camera lost/);
  assert.equal(calls,2);assert.equal(runtime.snapshot(p).flow.count,1);assert.equal(runtime.busy,false);
});
test('preflight rejects limits, selected targets and untrusted scripts before reserving',()=>{
  const {runner,runtime}=setup();
  for(const args of [{intervalMs:0},{intervalMs:100.1},{intervalMs:3600001},{maxCycles:-1},{maxCycles:1.5},{target:'counter'}]){
    assert.throws(()=>runner.start({project:counter(),...args}));assert.equal(runtime.busy,false);
  }
  const script=graph.normalize({version:1,id:'script',name:'script',steps:[step('script','script',{code:'def run(ctx): return {}'})]});
  assert.throws(()=>runner.start({project:script}),/可信/);assert.equal(runtime.busy,false);
});
test('immediate stop before first execution causes no effects',async()=>{
  const {runner,runtime}=setup(),project=counter();const state=runner.start({project,intervalMs:100});
  runner.stop(state.id);await runner.promise;
  assert.equal(runner.state.startedCycles,0);assert.deepEqual(runtime.snapshot(project).flow,{});assert.equal(runtime.busy,false);
});
test('stale stop IDs cannot stop a newer session',async()=>{
  const {runner}=setup();const first=runner.start({project:counter(),maxCycles:1,intervalMs:100});await runner.promise;
  const second=runner.start({project:counter(),intervalMs:100});assert.throws(()=>runner.stop(first.id),/会话已变化/);
  assert.equal(runner.busy,true);runner.stop(second.id);await runner.promise;
});
test('restart preserves summary and marks unfinished work interrupted without resuming devices',async()=>{
  const {runner,runtime,directory}=setup();runner.start({project:counter(),maxCycles:2,intervalMs:100});await runner.promise;
  const reloaded=new ContinuousRun(new Runtime(directory,{}),directory);assert.equal(reloaded.status().completedCycles,2);assert.equal(reloaded.busy,false);assert.equal(reloaded.project,null);
  const interrupted={...runner.state,state:'waiting',nextAt:Date.now()+10000,version:1};fs.writeFileSync(runner.file,JSON.stringify(interrupted));
  const recovered=new ContinuousRun(new Runtime(directory,{}),directory);
  assert.equal(recovered.status().state,'interrupted');assert.equal(recovered.busy,false);assert.equal(recovered.promise,null);
  assert.equal(runtime.snapshot(counter()).flow.count,2);assert.equal(JSON.parse(fs.readFileSync(runner.file)).state,'interrupted');
  assert.equal(JSON.parse(fs.readFileSync(runner.file)).project,undefined);
});
test('record write failures stop scheduling and release the runtime lease',async()=>{
  const {runner,runtime}=setup();let writes=0;const persist=runner.persist.bind(runner);
  runner.persist=()=>{if(++writes===2)throw Error('disk unavailable');persist();};
  runner.start({project:counter(),intervalMs:100});await runner.promise;
  assert.equal(runner.state.state,'failed');assert.match(runner.state.error,/disk unavailable/);assert.equal(runner.state.completedCycles,1);assert.equal(runtime.busy,false);
});
