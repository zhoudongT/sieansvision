'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),os=require('node:os');
const {Runtime}=require('../lib/runtime.cjs'),{OperatorPlugins}=require('../lib/operator-plugins.cjs'),{createOperatorBridge}=require('../lib/operator-bridge.cjs');
const graph=require('../public/vision/flow-graph.js'),samples=path.join(__dirname,'../public/vision/samples'),demos=JSON.parse(fs.readFileSync(path.join(samples,'demos-heightfield.json')));
const cloudOf=demo=>JSON.parse(fs.readFileSync(path.join(samples,demo.cloud))),project=demo=>{const p={version:1,id:demo.id,name:demo.name,steps:demo.steps.map((s,i)=>({...s,id:'h'+i})),hmi:structuredClone(demo.hmi)};for(const b of demo.hmiBindings)p.hmi.components[b.component].binding.nodeId='h'+b.step;return graph.normalize(p);};
const make=()=>{const dir=fs.mkdtempSync(path.join(os.tmpdir(),'sieans-heightfield-'));return new Runtime(dir,{},new OperatorPlugins(dir));};
async function execute(r,p,cloud){const job=r.start({project:p,cloud});await r.jobs.get(job.id).promise;return r.poll(job.id);}
test('five heightfield demos execute real independent datum and visible-surface integration',async()=>{
 for(const demo of demos){const r=make(),p=project(demo),cloud=cloudOf(demo),original=structuredClone(cloud),job=await execute(r,p,cloud);assert.equal(job.state,'completed',job.error);const output=job.results.at(-1).output,result=output.result;
  assert.deepEqual(cloud,original);assert.deepEqual(output.cloud.points,original.points);assert.equal(output.cloud.unit,'mm');assert.equal(output.cloud.frame,cloud.frame);assert.equal(output.cloud.colors.length,cloud.points.length);
  assert.equal(result.passed,!['heightfield-missing','heightfield-layered'].includes(demo.id));
  const hmi=require('../public/vision/hmi-layout.js');assert.equal(hmi.read(p.hmi.components[3].binding,job),result.passed);assert.equal(hmi.read(p.hmi.components[4].binding,job).length,result.items.length);
  if(demo.id==='heightfield-block'){assert(Math.abs(result.positiveVolume-32)<1e-8);assert.equal(job.variables.flow.heightCoverage,1);assert(Math.abs(result.maximumHeight-2)<1e-8);}
  if(demo.id==='heightfield-missing'){assert.equal(result.missingCells,10);assert.equal(result.validCells,90);assert(Math.abs(result.positiveVolume-24)<1e-8);}
  if(demo.id==='heightfield-signed')assert(Math.abs(result.netVolume-22)<1e-8);
  if(demo.id==='heightfield-layered'){assert.equal(result.spreadRejectedCells,1);assert.equal(result.items.length,1);}
 }
});
test('datum binds all scopes and unit mismatch rolls back pending variables',async()=>{
 const r=make(),p=project(demos[0]);p.steps[0].params.outputBindings.push({scope:'global',name:'heightPlane',field:'plane'},{scope:'module',name:'heightPlane',field:'plane'});
 let job=await execute(r,p,cloudOf(demos[0]));assert.equal(job.state,'completed',job.error);assert.deepEqual(job.variables.global.heightPlane,job.variables.modules.h0.heightPlane);const before=structuredClone(job.variables.global.heightPlane);
 const bad=project(demos[0]);bad.id=p.id;bad.steps[1].params.arguments.plane={...before,unit:'m'};bad.steps[0].params.outputBindings.push({scope:'global',name:'uncommitted',field:'plane'});
 job=await execute(r,bad,cloudOf(demos[0]));assert.equal(job.state,'failed');assert.match(job.error,/单位或坐标系/);assert.equal(r.snapshot(p).global.uncommitted,undefined);assert.deepEqual(r.snapshot(p).global.heightPlane,before);
});
test('Node-RED bridge shares datum, retains original geometry and rejects invalid grids',async()=>{
 const r=make(),bridge=createOperatorBridge(r.plugins),demo=demos[0],cloud=cloudOf(demo);const fitted=await bridge.run({...demo.steps[0].params});
 const out=await bridge.run({...demo.steps[1].params,cloud,arguments:{plane:fitted.result.plane,minimumPositiveVolume:31.99,maximumPositiveVolume:32.01}});assert.equal(out.result.passed,true);assert.deepEqual(out.cloud.points,cloud.points);
 await assert.rejects(bridge.run({...demo.steps[1].params,cloud,arguments:{plane:fitted.result.plane,cellsU:512,cellsV:512}}),/65536/);
});
