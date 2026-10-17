'use strict';
const {test,after}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),os=require('node:os');
const {Runtime}=require('../lib/runtime.cjs'),{ContinuousRun}=require('../lib/continuous-run.cjs'),vision=require('../lib/vision-client.cjs'),frame=require('../lib/frame.cjs'),graph=require('../public/vision/flow-graph.js');
const samples=path.join(__dirname,'../public/vision/samples'),demos=JSON.parse(fs.readFileSync(path.join(samples,'demos-depth-file.json')));
const content=name=>'data:image/png;base64,'+fs.readFileSync(path.join(samples,name)).toString('base64');
const imported=demo=>vision.run({operation:'depth_import',content:content(demo.depthFile),params:demo.depthParams,name:demo.depthFile});
function project(demo){const p={version:1,id:demo.id,name:demo.name,steps:demo.steps.map((s,i)=>({...structuredClone(s),id:'d'+i})),hmi:structuredClone(demo.hmi)};for(const b of demo.bindings)p.steps[b.step].params[b.param]={$ref:'results.d'+b.source+'.'+b.field};for(const b of demo.hmiBindings)p.hmi.components[b.component].binding.nodeId='d'+b.step;return graph.normalize(p);}
after(()=>vision.stop());

test('three depth-file demos project actual PNG16, crop and measure while retaining original depth',async()=>{
 for(const [i,demo] of demos.entries()){
  const input=await imported(demo);frame.depth(input.depth);frame.cloud(input.cloud);assert.equal(input.depth.image,content(demo.depthFile));assert.equal(input.cloud.unit,'mm');assert.equal(input.result.invalidDepthPixels,2);
  const runtime=new Runtime(fs.mkdtempSync(path.join(os.tmpdir(),'sieans-depth-file-')),vision),p=project(demo),start=runtime.start({project:p,cloud:input.cloud,depth:input.depth});await runtime.jobs.get(start.id).promise;const job=runtime.poll(start.id);
  assert.equal(job.state,'completed',job.error);assert.equal(job.results[0].output.result.pointCount,i===1?50:200);assert(Math.abs(job.variables.flow.topWidth-(i===1?175.5:185.25))<1e-8);
  // Cloud measurements do not echo depth themselves, so inspect it through the next script frame.
  p.version=1;p.steps.push({id:'raw',operation:'script',params:{code:'def run(ctx):\n    d=ctx["depth"]\n    return dict(result=dict(width=d["width"],same=d["image"]==ctx["params"]["original"]))',arguments:{original:input.depth.image}}});
  const again=runtime.start({project:p,cloud:input.cloud,depth:input.depth,allowScripts:true});await runtime.jobs.get(again.id).promise;const raw=runtime.poll(again.id);assert.equal(raw.state,'completed',raw.error);assert.deepEqual(raw.results.at(-1).output.result,{width:64,same:true});
 }
});

test('continuous depth input is a private frame snapshot and survives every cycle',async()=>{
 const input=await imported(demos[0]),directory=fs.mkdtempSync(path.join(os.tmpdir(),'sieans-depth-continuous-')),runtime=new Runtime(directory,vision),continuous=new ContinuousRun(runtime,directory);
 const p=project(demos[0]);p.version=1;p.steps.push({id:'inspect',operation:'script',params:{code:'def run(ctx):\n    return dict(result=dict(depth=ctx["depth"]["scaleMeters"],width=ctx["depth"]["width"]))'}});
 continuous.start({project:p,cloud:input.cloud,depth:input.depth,allowScripts:true,maxCycles:2,intervalMs:100});input.depth.scaleMeters=1;input.cloud.points[0][2]=99999;
 await continuous.promise;assert.equal(continuous.status().state,'completed',continuous.status().error);assert.equal(continuous.status().completedCycles,2);
 const last=runtime.poll(continuous.status().lastJobId);assert.equal(last.results.at(-1).output.result.depth,.001);assert.equal(last.results.at(-1).output.result.width,64);assert.equal(last.variables.flow.topWidth,185.25);
});

test('depth importer rejects display PNGs and malformed metadata through real engine protocol',async()=>{
 await assert.rejects(vision.run({operation:'depth_import',name:'parts.png',content:content('parts.png'),params:demos[0].depthParams}),/16 位灰度/);
 await assert.rejects(imported({...demos[0],depthParams:{...demos[0].depthParams,projection:'radial'}}),/光轴 Z/);
 await assert.rejects(vision.run({operation:'depth_import',name:'x',content:42,params:demos[0].depthParams}),/文件格式/);
});
