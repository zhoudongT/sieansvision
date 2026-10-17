const {test,after}=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),os=require('node:os');
const {Runtime}=require('../lib/runtime.cjs'),{OperatorPlugins}=require('../lib/operator-plugins.cjs');
const {createOperatorBridge}=require('../lib/operator-bridge.cjs');
const graph=require('../public/vision/flow-graph.js'),vision=require('../lib/vision-client.cjs'),industrial=require('../lib/industrial-client.cjs');
const samples=path.join(__dirname,'../public/vision/samples'),demos=JSON.parse(fs.readFileSync(path.join(samples,'demos-rigid.json')));
const cloudOf=d=>JSON.parse(fs.readFileSync(path.join(samples,d.cloud)));
const create=()=>{const dir=fs.mkdtempSync(path.join(os.tmpdir(),'sieans-rigid-'));return new Runtime(dir,vision,new OperatorPlugins(dir));};
const project=d=>graph.normalize({version:1,id:d.id,name:d.name,steps:d.steps.map((s,i)=>({...structuredClone(s),id:'r'+i}))});
async function execute(runtime,p,input={}){const j=runtime.start({project:p,...input});await runtime.jobs.get(j.id).promise;return runtime.poll(j.id);}
after(async()=>{vision.stop();await industrial.stop();});

test('all rigid demos execute real plugins, Open3D and local Modbus with typed variable bindings',async()=>{
 for(const demo of demos){
  const runtime=create(),p=project(demo),job=await execute(runtime,p,{cloud:cloudOf(demo)});assert.equal(job.state,'completed',job.error);
  assert.equal(job.variables.flow.frameCalibration.model,'sieans-rigid-v1');
  if(demo.id==='rigid-points'||demo.id==='rigid-outlier')assert(Math.abs(job.results[1].output.result.items[0].targetX-280)<1e-8);
  if(demo.id==='rigid-outlier'){assert.equal(job.results[0].output.result.inlierCount,7);assert.equal(job.results[0].output.result.rejectedCount,1);}
  if(demo.id==='rigid-cloud'){assert.equal(job.results[1].output.cloud.frame,'fixture-base');assert(Math.abs(job.results[2].output.result.sizeX-100)<1e-8);}
  if(demo.id==='rigid-check'){assert.equal(job.results[1].output.result.passed,false);assert(Math.abs(job.results[1].output.result.maximumError-2)<1e-8);}
  if(demo.id==='rigid-modbus'){assert(Math.abs(job.variables.flow.fixtureX-280)<1e-8);assert.equal(job.results[3].output.result.value,280);assert.equal(job.results[3].output.result.simulated,true);}
 }
});

test('model binds all variable scopes and failed frame reuse rolls back earlier edits',async()=>{
 const runtime=create(),p=project(demos[0]);p.steps[0].params.outputBindings=['global','flow','module'].map(scope=>({scope,name:'frameCalibration',field:'calibration'}));
 let job=await execute(runtime,p);assert.equal(job.state,'completed',job.error);assert.deepEqual(job.variables.global.frameCalibration,job.variables.modules.r0.frameCalibration);
 const model=job.variables.flow.frameCalibration;
 const bad=project(demos[2]);bad.steps[0]={id:'edit',operation:'variables',params:{scope:'global',name:'rigidUncommitted',value:1}};bad.steps[1].params.arguments.calibration=model;
 bad.edges=[{id:'e0',from:'source',to:'edit'},{id:'e1',from:'edit',to:'r1'},{id:'e2',from:'r1',to:'r2'}];bad.steps[1].imageFrom='edit';
 job=await execute(runtime,bad,{cloud:{...cloudOf(demos[2]),frame:'wrong'}});assert.equal(job.state,'failed');assert.match(job.error,/坐标系/);assert.equal(runtime.snapshot(bad).global.rigidUncommitted,undefined);
});

test('Node-RED bridge clears old projection channels and preserves transformed cloud/colour metadata',async()=>{
 const runtime=create(),bridge=createOperatorBridge(runtime.plugins),fit=await bridge.run({...demos[0].steps[0].params});
 const input=cloudOf(demos[0]);input.intrinsics={fx:100};input.extrinsics={old:true};
 const output=await bridge.run({...demos[2].steps[1].params,arguments:{calibration:fit.result.calibration},cloud:input,image:'old-image'});
 assert.equal(output.image,'');assert.equal(output.depth,null);assert.equal(output.cloud.frame,'fixture-base');assert.deepEqual(output.cloud.colors,input.colors);assert.equal(output.cloud.intrinsics,undefined);
});
