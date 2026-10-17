'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),os=require('node:os');
const {OperatorPlugins}=require('../lib/operator-plugins.cjs'),{Runtime}=require('../lib/runtime.cjs');
const graph=require('../public/vision/flow-graph.js');
const samples=path.join(__dirname,'../public/vision/samples');
const imageOf=name=>'data:image/png;base64,'+fs.readFileSync(path.join(samples,name)).toString('base64');
function setup(t){const dir=fs.mkdtempSync(path.join(os.tmpdir(),'sieans-quality-'));t.after(()=>fs.rmSync(dir,{recursive:true,force:true}));return {dir,plugins:new OperatorPlugins(dir)};}
const params=arguments_=>({pluginId:'sieans-image-quality',pluginVersion:'1.0.0',operatorId:'inspect',arguments:arguments_});
test('four image quality demos run real OpenCV and preserve images for downstream inspection',async t=>{
 const {dir,plugins}=setup(t),runtime=new Runtime(dir,{},plugins);let sharpness;
 for(const demo of require('../public/vision/samples/demos-image-quality.json')){
  const image=imageOf(demo.image),project=graph.normalize({version:1,id:demo.id,name:demo.name,steps:[...demo.steps,{id:'brightness',operation:'plugin',params:{pluginId:'sieans-inspection',pluginVersion:'1.0.0',operatorId:'brightness',arguments:{}}}]});
  const job=runtime.start({project,image});await runtime.jobs.get(job.id).promise;const done=runtime.poll(job.id);assert.equal(done.state,'completed',done.error);
  const result=done.results[0].output.result;assert.equal(result.passed,demo.id==='quality-sharp');assert.equal(done.variables.flow.captureOK,result.passed);assert.equal(done.results[1].output.annotatedImage,image);
  if(demo.id==='quality-sharp'){sharpness=result.sharpness;assert.equal(result.darkPercent,0);assert.equal(result.brightPercent,0);}
  if(demo.id==='quality-blur')assert(result.sharpness<sharpness/10);
  if(demo.id==='quality-dark')assert.equal(result.darkPercent,100);
  if(demo.id==='quality-bright')assert.equal(result.brightPercent,100);
 }
});
test('ROI boundaries, contradictory thresholds and inclusive limits are enforced',async t=>{
 const {plugins}=setup(t),image=imageOf('quality-sharp.png');
 const run=async args=>(await plugins.run(params(args),{image})).data.result;
 const result=await run({roiX:12,roiY:12,roiWidth:12,roiHeight:12,minimumSharpness:0});assert.equal(result.sharpness,0);assert.equal(result.pixelCount,144);assert.equal(result.passed,true);
 await assert.rejects(run({roiX:320}),/区域/);await assert.rejects(run({roiWidth:2}),/区域/);
 await assert.rejects(run({darkThreshold:100,brightThreshold:100}),/阈值/);
 const darkImage=imageOf('quality-dark.png');
 const out=(await plugins.run(params({minimumSharpness:0,maximumDarkPercent:100}),{image:darkImage})).data.result;assert.equal(out.passed,true);
});
