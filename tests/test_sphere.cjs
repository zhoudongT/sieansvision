'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),os=require('node:os');
const {Runtime}=require('../lib/runtime.cjs'),{OperatorPlugins}=require('../lib/operator-plugins.cjs');
const {createOperatorBridge}=require('../lib/operator-bridge.cjs');
const graph=require('../public/vision/flow-graph.js');
const samples=path.join(__dirname,'../public/vision/samples');
const demos=JSON.parse(fs.readFileSync(path.join(samples,'demos-sphere.json')));
const cloudOf=demo=>JSON.parse(fs.readFileSync(path.join(samples,demo.cloud)));
const create=()=>{const dir=fs.mkdtempSync(path.join(os.tmpdir(),'sieans-sphere-'));return new Runtime(dir,{},new OperatorPlugins(dir));};
async function execute(runtime,project,cloud){const job=runtime.start({project,cloud});await runtime.jobs.get(job.id).promise;return runtime.poll(job.id);}
test('sphere demonstrations use actual Python processes and preserve geometry, units and variable models',async()=>{
 for(const demo of demos){
  const runtime=create(),cloud=cloudOf(demo),project=graph.normalize({version:1,id:demo.id,name:demo.name,steps:demo.steps.map((s,i)=>({...s,id:'sphere'+i}))});
  const job=await execute(runtime,project,cloud);assert.equal(job.state,'completed',job.error);
  const out=job.results.at(-1).output,r=out.result;
  assert.equal(r.passed,demo.id==='sphere-fit');assert.deepEqual(out.cloud.points,cloud.points);assert.equal(out.cloud.frame,cloud.frame);assert.equal(r.unit,'mm');
  if(['sphere-inspect','sphere-chain'].includes(demo.id)){assert.equal(r.outsideCount,2);assert.equal(job.variables.flow.sphereDefects,2);assert.deepEqual(out.cloud.colors[20],[1,.15,.1]);assert.deepEqual(out.cloud.colors[180],[1,.15,.1]);}
  if(demo.id==='sphere-fit'){assert.equal(r.uniqueInlierCount,600);assert.equal(r.outsideCount,40);assert(Math.abs(job.variables.flow.sphereDiameter-20)<1e-8);assert.equal(job.variables.flow.sphereReference.model,'sieans-sphere-v1');}
  if(demo.id==='sphere-narrow'){assert.equal(r.found,false);assert.equal(r.sphere,undefined);assert.equal(job.variables.flow.sphereFound,false);assert.deepEqual(out.cloud.colors[0],[.6,.6,.6]);}
  if(demo.id==='sphere-size'){assert.equal(r.found,true);assert(Math.abs(job.variables.flow.sphereDiameter-22)<1e-8);}
 }
});
test('sphere model binds all variable scopes and failed model reuse rolls back changes',async()=>{
 const runtime=create(),demo=demos[0],cloud=cloudOf(demo),fit={...demo.steps[0],id:'fit',params:{...demo.steps[0].params,outputBindings:['global','flow','module'].map(scope=>({scope,field:'sphere',name:'ball'}))}};
 const project=graph.normalize({version:1,id:'sphere-scopes',name:'球面范围',steps:[fit]});
 let job=await execute(runtime,project,cloud);assert.equal(job.state,'completed',job.error);
 assert.deepEqual(job.variables.global.ball,job.variables.flow.ball);assert.deepEqual(job.variables.modules.fit.ball,job.variables.flow.ball);
 const bad=structuredClone(demos[1].steps[0]);bad.id='inspect';bad.params.arguments.sphere.frame='wrong';
 const failure=graph.normalize({version:1,id:'sphere-failure',name:'错误基准',steps:[{id:'set',operation:'variables',params:{scope:'flow',name:'uncommitted',value:1}},bad]});
 job=await execute(runtime,failure,cloud);assert.equal(job.state,'failed');assert.match(job.error,/坐标系/);assert.equal(runtime.snapshot(failure).flow.uncommitted,undefined);
});
test('Node-RED bridge passes fitted sphere and original coordinates to radial inspection',async()=>{
 const runtime=create(),bridge=createOperatorBridge(runtime.plugins),demo=demos[2],cloud=cloudOf(demo);
 const fitted=await bridge.run({...demo.steps[0].params,cloud});assert.equal(fitted.result.passed,true);assert.equal(fitted.result.sphere.frame,cloud.frame);
 const inspected=await bridge.run({...demo.steps[1].params,arguments:{sphere:fitted.result.sphere,detailMode:'outside'},cloud:fitted.cloud});
 assert.equal(inspected.result.passed,false);assert.equal(inspected.result.outsideCount,2);assert.deepEqual(inspected.cloud.points,cloud.points);
});
