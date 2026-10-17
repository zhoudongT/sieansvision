'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),os=require('node:os');
const {Runtime}=require('../lib/runtime.cjs'),{OperatorPlugins}=require('../lib/operator-plugins.cjs'),{createOperatorBridge}=require('../lib/operator-bridge.cjs');
const graph=require('../public/vision/flow-graph.js'),layout=require('../public/vision/hmi-layout.js');
const samples=path.join(__dirname,'../public/vision/samples'),demos=JSON.parse(fs.readFileSync(path.join(samples,'demos-shape.json')));
const imageOf=demo=>'data:image/png;base64,'+fs.readFileSync(path.join(samples,demo.image)).toString('base64');
const make=()=>{const dir=fs.mkdtempSync(path.join(os.tmpdir(),'sieans-shape-'));return new Runtime(dir,{},new OperatorPlugins(dir));};
const project=demo=>{const p={version:1,id:demo.id,name:demo.name,steps:demo.steps.map((s,i)=>({...structuredClone(s),id:'s'+i})),hmi:structuredClone(demo.hmi)};for(const b of demo.hmiBindings)p.hmi.components[b.component].binding.nodeId='s'+b.step;return graph.normalize(p);};
async function execute(runtime,p,image){const job=runtime.start({project:p,image});await runtime.jobs.get(job.id).promise;return runtime.poll(job.id);}

test('five real silhouette demos use model binding, preserve input and expose table/HMI results',async()=>{
 for(const demo of demos){const runtime=make(),p=project(demo),image=imageOf(demo),job=await execute(runtime,p,image);assert.equal(job.state,'completed',job.error);
  const r=job.results[1].output.result,passed=['shape-multi','shape-dark'].includes(demo.id);assert.equal(r.passed,passed,demo.id);
  assert.equal(job.variables.flow.shapeOK,passed);assert.equal(job.variables.flow.silhouette.kind,'sieans-silhouette');
  for(const node of job.results){assert.equal(node.output.image,image);assert.notEqual(node.output.annotatedImage,image);}
  assert.equal(layout.read(p.hmi.components[0].binding,job),r.count);assert.equal(layout.read(p.hmi.components[1].binding,job),passed);assert.deepEqual(layout.read(p.hmi.components[3].binding,job),r.items);
  if(demo.id==='shape-multi'){assert.equal(r.count,3);assert.equal(r.items.length,4);assert.equal(r.items.filter(row=>!row.matched).length,1);}
  if(demo.id==='shape-empty'){assert.equal(r.count,0);assert.deepEqual(r.items,[]);}
  if(demo.id==='shape-unique-guard'){assert.equal(r.found,true);assert.equal(r.passed,false);}
 }
});

test('shape model crosses frames, supports three scopes and rolls back failed model replacement',async()=>{
 const runtime=make(),p=project(demos[0]),image=imageOf(demos[0]);
 p.steps[0].params.outputBindings.push({scope:'global',name:'sharedShape',field:'model'});
 p.steps[1].params.outputBindings.push({scope:'module',name:'count',field:'count'});
 let job=await execute(runtime,p,image);assert.equal(job.state,'completed',job.error);assert.equal(job.variables.modules.s1.count,3);
 const old=structuredClone(job.variables.global.sharedShape);
 const only=graph.normalize({version:1,id:p.id,name:'复用轮廓模型',steps:[{...structuredClone(p.steps[1]),params:{...structuredClone(p.steps[1].params),arguments:{model:{$ref:'global.sharedShape'},roiX:200}}}]});
 job=await execute(runtime,only,imageOf(demos[1]));assert.equal(job.state,'completed',job.error);assert.equal(job.results[0].output.result.count,0);assert.equal(job.results[0].output.result.candidateCount,1);
 const bad=project(demos[0]);bad.steps[0].params.outputBindings.push({scope:'global',name:'sharedShape',field:'model'});bad.steps[1].params.arguments.model={kind:'bad'};
 job=await execute(runtime,bad,image);assert.equal(job.state,'failed');assert.match(job.error,/轮廓建模/);assert.deepEqual(runtime.snapshot(bad).global.sharedShape,old);
 const ambiguous=project(demos[0]);ambiguous.steps[0].params.arguments={};job=await execute(runtime,ambiguous,image);assert.equal(job.state,'failed');assert.match(job.error,/恰好/);
});

test('Node-RED bridge passes taught model into new image and enforces field contracts',async()=>{
 const bridge=createOperatorBridge(make().plugins),demo=demos[0],image=imageOf(demo);
 const trained=await bridge.run({...demo.steps[0].params,image});assert.equal(trained.result.model.version,1);
 const checked=await bridge.run({...demo.steps[1].params,image,arguments:{model:trained.result.model,roiX:200,minimumCount:3,maximumCount:3}});
 assert.equal(checked.result.count,3);assert.equal(checked.image,image);assert.equal(checked.result.passed,true);
 const changed=await bridge.run({...demo.steps[1].params,image:imageOf(demos[1]),arguments:{model:trained.result.model,roiX:200}});assert.equal(changed.result.count,0);
 await assert.rejects(bridge.run({...demo.steps[1].params,image,arguments:{model:trained.result.model,minimumCount:0}}),/最小值/);
});
