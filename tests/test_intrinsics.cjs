const {test}=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),os=require('node:os');
const {Runtime}=require('../lib/runtime.cjs'),{OperatorPlugins}=require('../lib/operator-plugins.cjs');
const {createOperatorBridge}=require('../lib/operator-bridge.cjs');
const graph=require('../public/vision/flow-graph.js');
const samples=path.join(__dirname,'../public/vision/samples');
const demos=JSON.parse(fs.readFileSync(path.join(samples,'demos-intrinsics.json')));
const imageOf=d=>'data:image/png;base64,'+fs.readFileSync(path.join(samples,d.image)).toString('base64');
const setup=()=>{const dir=fs.mkdtempSync(path.join(os.tmpdir(),'sieans-intrinsics-'));return new Runtime(dir,{},new OperatorPlugins(dir));};
const project=d=>graph.normalize({version:1,id:d.id,name:d.name,steps:d.steps.map((s,i)=>({...structuredClone(s),id:'step'+i}))});
async function run(runtime,p,image){const j=runtime.start({project:p,image});await runtime.jobs.get(j.id).promise;return runtime.poll(j.id);}

test('all intrinsic demos execute actual plugin; corrected pixels reach downstream while corner overlay does not',async()=>{
 for(const demo of demos){
  const runtime=setup(),p=project(demo),image=imageOf(demo);
  p.steps.push({id:'brightness',operation:'plugin',params:{pluginId:'sieans-inspection',pluginVersion:'1.0.0',operatorId:'brightness',arguments:{}}});
  p.edges.push({id:'to-brightness',from:p.steps.at(-2).id,to:'brightness'});
  const job=await run(runtime,p,image);assert.equal(job.state,'completed',job.error);
  if(demo.id==='intrinsics-corners'){
   assert.equal(job.results[0].output.result.cornerCount,54);assert.notEqual(job.results[0].output.annotatedImage,image);
   assert.equal(job.results.at(-1).output.annotatedImage,image);
  }else{
   assert(Math.abs(job.variables.flow.cameraCalibration.fx-710)<.1);
   if(demo.id==='intrinsics-undistort'){
    assert.notEqual(job.results[1].output.annotatedImage,image);
    assert.equal(job.results.at(-1).output.annotatedImage===job.results[1].output.annotatedImage,true);
   }
  }
 }
});

test('capture accumulates across saved variable rounds and failed duplicate capture preserves committed points',async()=>{
 const runtime=setup(),p=project(demos[0]),args=p.steps[0].params;
 p.variables={calibrationPoints:[]};args.arguments.points={$ref:'flow.calibrationPoints'};
 args.outputBindings=[{scope:'flow',name:'calibrationPoints',field:'points'}];
 let job=await run(runtime,p,imageOf(demos[0]));assert.equal(job.state,'completed',job.error);assert.equal(job.variables.flow.calibrationPoints.length,54);
 args.arguments.view=2;job=await run(runtime,p,imageOf(demos[0]));assert.equal(job.state,'completed',job.error);assert.equal(job.variables.flow.calibrationPoints.length,108);
 job=await run(runtime,p,imageOf(demos[0]));assert.equal(job.state,'failed');assert.match(job.error,/编号已存在/);
 assert.equal(runtime.snapshot(p).flow.calibrationPoints.length,108);
});

test('Node-RED operator bridge supports intrinsic result and variable input without exposing implementation source',async()=>{
 const plugins=new OperatorPlugins(fs.mkdtempSync(path.join(os.tmpdir(),'sieans-intrinsics-'))),bridge=createOperatorBridge(plugins);
 const result=await bridge.run({...demos[1].steps[0].params});
 assert.equal(result.result.calibration.model,'pinhole-opencv5');
 const corrected=await bridge.run({...demos[2].steps[1].params,arguments:{calibration:result.result.calibration},image:imageOf(demos[2])});
 assert(corrected.image.startsWith('data:image/png;base64,'));
});
