const {test}=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),os=require('node:os');
const {Runtime}=require('../lib/runtime.cjs'),{OperatorPlugins}=require('../lib/operator-plugins.cjs'),{createOperatorBridge}=require('../lib/operator-bridge.cjs');
const graph=require('../public/vision/flow-graph.js'),samples=path.join(__dirname,'../public/vision/samples');
const demos=JSON.parse(fs.readFileSync(path.join(samples,'demos-handeye.json'))),truth=JSON.parse(fs.readFileSync(path.join(samples,'handeye-ground-truth.json')));
const make=()=>{const dir=fs.mkdtempSync(path.join(os.tmpdir(),'sieans-handeye-'));return new Runtime(dir,{},new OperatorPlugins(dir));};
const imageOf=d=>'data:image/png;base64,'+fs.readFileSync(path.join(samples,d.image)).toString('base64');
const project=d=>graph.normalize({version:1,id:d.id,name:d.name,steps:d.steps.map((s,i)=>({...structuredClone(s),id:'h'+i}))});
async function execute(runtime,p,image){const j=runtime.start({project:p,image});await runtime.jobs.get(j.id).promise;return runtime.poll(j.id);}

test('four handeye demonstrations execute real Python and compatible rigid-point conversion',async()=>{
 for(const demo of demos){
  const runtime=make(),p=project(demo),job=await execute(runtime,p,imageOf(demo));assert.equal(job.state,'completed',job.error);
  if(demo.id==='handeye-pose'){assert.equal(job.results[0].output.result.cornerCount,54);assert.equal(job.results[0].output.image===imageOf(demo),true);assert.equal(job.results[0].output.annotatedImage!==imageOf(demo),true);}
  else{
   assert.equal(job.variables.flow.handeyeCalibration.targetFrame,'tool0');assert(Math.abs(job.variables.flow.handeyeCalibration.translation[0]-30)<1e-8);
   if(demo.id==='handeye-fit'||demo.id==='handeye-drift')assert.equal(job.results[1].output.result.passed,demo.id==='handeye-fit');
   if(demo.id==='handeye-point'){
    const expected=truth.cameraToTool.slice(0,3).map(row=>row[0]*10+row[1]*20+row[2]*30+row[3]);
    for(const [i,key]of ['targetX','targetY','targetZ'].entries())assert(Math.abs(job.results[1].output.result.items[0][key]-expected[i])<1e-8);
   }
  }
 }
});

test('handeye model binds all scopes and degenerate acquisition rolls back new variables',async()=>{
 const runtime=make(),p=project(demos[1]);p.steps[0].params.outputBindings.push({scope:'global',name:'cameraTool',field:'calibration'},{scope:'module',name:'cameraTool',field:'calibration'});
 let job=await execute(runtime,p);assert.equal(job.state,'completed',job.error);assert.deepEqual(job.variables.global.cameraTool,job.variables.modules.h0.cameraTool);
 const bad=structuredClone(demos[1]);bad.id='handeye-bad';for(const row of bad.steps[0].params.arguments.poses)row.robotRx=row.robotRy=row.robotRz=0;
 bad.steps.unshift({operation:'variables',params:{scope:'global',name:'handeyeUncommitted',value:1}});const failed=project(bad);
 job=await execute(runtime,failed);assert.equal(job.state,'failed');assert.match(job.error,/激励不足/);assert.equal(runtime.snapshot(failed).global.handeyeUncommitted,undefined);
});

test('Node-RED bridge transfers fitted model/reference into independent validation',async()=>{
 const bridge=createOperatorBridge(make().plugins),fit=await bridge.run({...demos[1].steps[0].params});
 const checked=await bridge.run({...demos[1].steps[1].params,arguments:{poses:truth.poses.slice(8),calibration:fit.result.calibration,reference:fit.result.reference}});
 assert.equal(checked.result.passed,true);assert.equal(checked.result.sampleCount,3);
});
