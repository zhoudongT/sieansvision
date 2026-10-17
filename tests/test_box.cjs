'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),os=require('node:os');
const {Runtime}=require('../lib/runtime.cjs'),{OperatorPlugins}=require('../lib/operator-plugins.cjs'),{createOperatorBridge}=require('../lib/operator-bridge.cjs');
const graph=require('../public/vision/flow-graph.js'),layout=require('../public/vision/hmi-layout.js'),samples=path.join(__dirname,'../public/vision/samples'),demos=JSON.parse(fs.readFileSync(path.join(samples,'demos-box.json')));
const cloudOf=d=>JSON.parse(fs.readFileSync(path.join(samples,d.cloud)));
const make=()=>{const dir=fs.mkdtempSync(path.join(os.tmpdir(),'sieans-box-'));return new Runtime(dir,{},new OperatorPlugins(dir));};
function project(demo){const p={version:1,id:demo.id,name:demo.name,steps:demo.steps.map((s,i)=>({...structuredClone(s),id:'b'+i})),hmi:structuredClone(demo.hmi)};for(const b of demo.hmiBindings)p.hmi.components[b.component].binding.nodeId='b'+b.step;return graph.normalize(p);}
async function execute(r,p,cloud){const start=r.start({project:p,cloud});await r.jobs.get(start.id).promise;return r.poll(start.id);}

test('four oriented-box demos preserve full input and expose meaningful HMI dimensions and tolerances',async()=>{
 assert.equal(new Set(demos.map(d=>d.name)).size,4);
 for(const d of demos){const runtime=make(),p=project(d),cloud=cloudOf(d),job=await execute(runtime,p,cloud);assert.equal(job.state,'completed',job.error);const result=job.results[0].output.result;
  assert.equal(result.passed,d.id!=='box-oversize');assert(Math.abs(result.length-(d.id==='box-meters'?.02:d.id==='box-equal'?10:d.id==='box-oversize'?22:20))<1e-5);
  assert.deepEqual(job.results[0].output.cloud,cloud);assert.equal(result.corners.length,8);assert.equal(result.items.length,3);assert.equal(result.axes.length,3);
  assert.equal(layout.read(p.hmi.components[0].binding,job),result.length);assert.equal(layout.read(p.hmi.components[1].binding,job),result.passed);assert.deepEqual(layout.read(p.hmi.components[3].binding,job),result.items);
  assert.equal(result.unit,cloud.unit);assert.equal(result.nearEqualDimensions,d.id==='box-equal');
 }
});

test('oriented dimensions bind three variable scopes and degenerate replacement rolls back',async()=>{
 const runtime=make(),p=project(demos[0]),cloud=cloudOf(demos[0]);p.steps[0].params.outputBindings.push({scope:'global',name:'boxCorners',field:'corners'},{scope:'module',name:'width',field:'width'});
 let job=await execute(runtime,p,cloud);assert.equal(job.state,'completed',job.error);assert(Math.abs(job.variables.modules.b0.width-10)<1e-5);assert.equal(job.variables.global.boxCorners.length,8);const old=structuredClone(job.variables.global.boxCorners);
 p.version=1;p.steps.unshift({id:'temporary',operation:'variables',params:{scope:'flow',name:'uncommitted',value:42}});job=await execute(runtime,p,{unit:'mm',points:[[0,0,0],[1,0,0],[0,1,0],[1,1,0]]});assert.equal(job.state,'failed');assert.match(job.error,/共面/);assert.equal(runtime.snapshot(p).flow.uncommitted,undefined);assert.deepEqual(runtime.snapshot(p).global.boxCorners,old);
});

test('Node-RED bridge exposes enclosing volume without changing data or inventing orientation on a plane',async()=>{
 const bridge=createOperatorBridge(make().plugins),p=demos[0].steps[0].params,cloud=cloudOf(demos[0]),out=await bridge.run({...p,cloud});assert.equal(out.result.found,true);assert(Math.abs(out.result.boundingBoxVolume-1000)<.001);assert.deepEqual(out.cloud,cloud);assert.equal(out.result.method,'convex-hull-optimized');
 await assert.rejects(bridge.run({...p,cloud:{unit:'mm',points:[[0,0,0],[1,0,0],[0,1,0],[1,1,0]]}}),/共面/);
});
