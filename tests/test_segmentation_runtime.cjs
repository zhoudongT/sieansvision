'use strict';
const {test,after}=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path'),vm=require('node:vm');
const {Runtime}=require('../lib/runtime.cjs'),graph=require('../public/vision/flow-graph.js');
const vision=require('../lib/vision-client.cjs');
const samples=path.join(__dirname,'../public/vision/samples');
const image='data:image/jpeg;base64,'+fs.readFileSync(path.join(samples,'segmentation-bus.jpg')).toString('base64');
const cloud={unit:'mm',frame:'fixture',points:[[0,0,0],[1,2,3]]};
const node=(id,operation,params={})=>({id,operation,params});
const make=(engine=vision)=>new Runtime(fs.mkdtempSync(path.join(os.tmpdir(),'sieans-segmentation-')),engine);
async function run(runtime,project,extra={}){const start=runtime.start({project,image,cloud,...extra});await runtime.jobs.get(start.id).promise;return runtime.poll(start.id);}
after(()=>vision.stop());

test('real segmentation mask feeds measurement; overlay and source branches preserve original input',async()=>{
 const requests=[];const runtime=make({run:async request=>{requests.push(request);return vision.run(request);}});
 const steps=[node('seg','yolo_segment',{output:{$ref:'flow.display'},classes:[5],overlayAlpha:{$ref:'flow.unused'}}),node('geometry','geometry',{minArea:100}),node('sourceGeometry','geometry',{minArea:101}),node('area','variables',{name:'maskArea',value:{$ref:'results.seg.unionAreaPixels'}})];
 const p=graph.normalize({version:2,name:'分割分支',variables:{display:'mask',maskArea:0},variableTypes:{maskArea:'integer'},steps,edges:[{id:'a',from:'source',to:'seg'},{id:'b',from:'seg',to:'geometry'},{id:'c',from:'source',to:'sourceGeometry'},{id:'d',from:'geometry',to:'area'},{id:'e',from:'seg',to:'area'}]});
 const job=await run(runtime,p);assert.equal(job.state,'completed',job.error);
 const segment=job.results.find(r=>r.id==='seg').output;
 assert.equal(segment.result.count,1);assert.ok(job.variables.flow.maskArea>200000);assert.equal(job.variables.flow.maskArea,segment.result.unionAreaPixels);
 const measured=requests.find(r=>r.operation==='geometry'&&r.params.minArea===100),original=requests.find(r=>r.operation==='geometry'&&r.params.minArea===101);assert.ok(measured.image===segment.maskImage,'measurement receives mask');assert.ok(original.image===image,'parallel branch receives original');assert.deepEqual(measured.cloud,cloud);
 assert.equal(job.results.find(r=>r.id==='geometry').output.result.count,1);
 const lean=await runtime.history.get(job.id);assert.equal(lean.results[0].output.maskImage,undefined);assert.equal(lean.results[0].output.result.unionAreaPixels,segment.result.unionAreaPixels);
 const overlay=graph.normalize({version:1,name:'原图保留',steps:[node('seg','yolo_segment',{output:'overlay',classes:[5]}),node('geometry','geometry',{minArea:100})]});
 requests.length=0;const next=await run(make({run:async request=>{requests.push(request);return vision.run(request);}}),overlay);
 assert.equal(next.state,'completed',next.error);assert.equal(requests[1].image,image);assert.notEqual(next.results[0].output.annotatedImage,image);
});

test('bundled v8/v11 demonstrations execute and retain masks only when frame retention is enabled',async()=>{
 const demos=JSON.parse(fs.readFileSync(path.join(samples,'demos-segmentation.json')));
 for(const demo of demos){
  const steps=demo.steps.map((s,i)=>({...structuredClone(s),id:String(i)}));
  for(const b of demo.bindings||[])steps[b.step].params[b.param]={$ref:'results.'+b.source+'.'+b.field};
  const p=graph.normalize({version:1,name:demo.name,variables:demo.variables,variableTypes:demo.variableTypes,history:{includeFrames:true},steps});
  const runtime=make(),job=await run(runtime,p);assert.equal(job.state,'completed',demo.id+': '+job.error);
  const segmentation=job.results[0].output;assert.ok(segmentation.result.items.every(item=>item.contours.length&&item.areaPixels>0));
  if(demo.id==='segmentation-measure'){assert.equal(segmentation.result.count,1);assert.equal(job.results[1].output.result.count,1);assert.equal(job.variables.flow.maskAreaPixels,segmentation.result.unionAreaPixels);}
  else{const labels=segmentation.result.items.map(item=>item.label);assert.ok(labels.includes('bus'));assert.ok(labels.includes('person'));}
  assert.equal((await runtime.history.get(job.id)).results[0].output.maskImage,segmentation.maskImage);
 }
});

test('wrong model rolls back variables; empty segmentation remains a valid zero-target result',async()=>{
 const runtime=make(),p=graph.normalize({version:1,name:'分割失败回滚',variables:{count:7},steps:[node('set','variables',{name:'count',value:99}),node('seg','yolo_segment',{model:'yolo11n.pt'})]});
 const job=await run(runtime,p);assert.equal(job.state,'failed');assert.match(job.error,/分割模型/);assert.equal(runtime.snapshot(p).flow.count,7);
 const empty=graph.normalize({version:1,name:'无目标',steps:[node('seg','yolo_segment',{classes:[],output:'mask'}),node('geometry','geometry',{minArea:1})]});
 const blank=await run(make(),empty);assert.equal(blank.state,'completed',blank.error);assert.equal(blank.results[0].output.result.count,0);assert.equal(blank.results[1].output.result.count,0);
});

test('input preview follows resolved mask mode and drops stale mask on overlay',()=>{
 const context=vm.createContext({project:{steps:[{id:'seg',operation:'yolo_segment'}]}});
 vm.runInContext(fs.readFileSync(path.join(__dirname,'../public/vision/input-preview.js'),'utf8'),context);
 context.item={id:'seg',output:{result:{output:'mask'},maskImage:'mask',annotatedImage:'display'}};
 vm.runInContext('rememberFrame(item)',context);assert.equal(vm.runInContext('framePreviews.get("seg")',context),'mask');
 context.item.output.result.output='overlay';vm.runInContext('rememberFrame(item)',context);assert.equal(vm.runInContext('framePreviews.has("seg")',context),false);
});
