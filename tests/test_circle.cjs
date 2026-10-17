'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),os=require('node:os');
const {Runtime}=require('../lib/runtime.cjs'),{OperatorPlugins}=require('../lib/operator-plugins.cjs'),{createOperatorBridge}=require('../lib/operator-bridge.cjs');
const graph=require('../public/vision/flow-graph.js'),samples=path.join(__dirname,'../public/vision/samples'),demos=JSON.parse(fs.readFileSync(path.join(samples,'demos-circle.json')));
const imageOf=demo=>'data:image/png;base64,'+fs.readFileSync(path.join(samples,demo.image)).toString('base64');
const make=()=>{const dir=fs.mkdtempSync(path.join(os.tmpdir(),'sieans-circle-'));return new Runtime(dir,{},new OperatorPlugins(dir));};
const project=demo=>{const p={version:1,id:demo.id,name:demo.name,steps:demo.steps.map((s,i)=>({...s,id:'c'+i}))};if(demo.hmi){p.hmi=structuredClone(demo.hmi);for(const b of demo.hmiBindings)p.hmi.components[b.component].binding.nodeId='c'+b.step;}return graph.normalize(p);};
async function execute(runtime,p,image){const job=runtime.start({project:p,image});await runtime.jobs.get(job.id).promise;return runtime.poll(job.id);}
test('seven circle demos execute real raster measurement and two-circle bindings',async()=>{
 for(const demo of demos){const runtime=make(),p=project(demo),image=imageOf(demo),job=await execute(runtime,p,image);assert.equal(job.state,'completed',job.error);
  const result=job.results.at(-1).output.result,passed=!['circle-oversize','circle-no-edge','circle-ring-offset'].includes(demo.id);assert.equal(result.passed,passed,demo.id);
  for(const node of job.results){assert.equal(node.output.image,image);assert.notEqual(node.output.annotatedImage,image);}
  if(demo.id==='circle-hole'){assert(Math.abs(result.diameter-16.08)<.02);assert(Math.abs(result.centerX-321.35)<.1);}
  if(demo.id==='circle-outliers'){assert(result.rejectedCount>3);assert(result.items.some(r=>r.valid&&!r.inlier));}
  if(demo.id==='circle-no-edge'){assert.equal(result.circle,undefined);assert.equal(result.found,false);}
  if(demo.id==='circle-ring')assert(result.centerDistance<.12);
  if(demo.id==='circle-ring-offset')assert(Math.abs(result.centerDistance-.7)<.02);
  if(p.hmi){const layout=require('../public/vision/hmi-layout.js');assert.equal(layout.read(p.hmi.components[1].binding,job),passed);assert.equal(layout.read(p.hmi.components[3].binding,job).length,result.items.length);}
 }
});
test('circle output supports all variable scopes, input preservation and rollback',async()=>{
 const runtime=make(),p=project(demos[0]);p.steps[0].params.outputBindings.push({scope:'global',name:'measuredCircle',field:'circle'},{scope:'module',name:'diameter',field:'diameter'});
 p.steps.push({id:'brightness',operation:'plugin',params:{pluginId:'sieans-inspection',pluginVersion:'1.0.0',operatorId:'brightness',arguments:{}}});
 p.edges.push({id:'brightness-edge',from:'c0',to:'brightness',fromPort:'bottom',toPort:'top'});
 const image=imageOf(demos[0]);let job=await execute(runtime,p,image);assert.equal(job.state,'completed',job.error);assert(Math.abs(job.variables.modules.c0.diameter-16.08)<.02);assert.equal(job.variables.global.measuredCircle.unit,'mm');assert.equal(job.results[1].output.annotatedImage,image);const previous=structuredClone(job.variables.global.measuredCircle);
 const bad=project(demos[4]);bad.id=p.id;bad.steps[0].params.outputBindings=[{scope:'global',name:'measuredCircle',field:'circle'}];bad.steps.unshift({id:'stage',operation:'variables',params:{scope:'flow',name:'uncommitted',value:1}});
 bad.version=1;job=await execute(runtime,bad,imageOf(demos[4]));assert.equal(job.state,'failed');assert.equal(runtime.snapshot(bad).flow.uncommitted,undefined);assert.deepEqual(runtime.snapshot(bad).global.measuredCircle,previous);
});
test('Node-RED bridge shares original frame and rejects cross-image circle models',async()=>{
 const bridge=createOperatorBridge(make().plugins),demo=demos[5],image=imageOf(demo);
 const inner=await bridge.run({...demo.steps[0].params,image}),outer=await bridge.run({...demo.steps[1].params,image});
 const checked=await bridge.run({...demo.steps[2].params,image,arguments:{innerCircle:inner.result.circle,outerCircle:outer.result.circle,maximumCenterDistance:.2,minimumWall:3.8,maximumWall:4.3}});assert.equal(checked.result.passed,true);assert.equal(checked.image,image);assert.notEqual(checked.annotatedImage,image);
 const other=await bridge.run({...demo.steps[0].params,image:imageOf(demos[6])});await assert.rejects(bridge.run({...demo.steps[2].params,arguments:{innerCircle:other.result.circle,outerCircle:outer.result.circle}}),/同一原始图像/);
 await assert.rejects(bridge.run({...demo.steps[2].params,image:imageOf(demos[0]),arguments:{innerCircle:inner.result.circle,outerCircle:outer.result.circle}}),/当前输入图像不一致/);
});
