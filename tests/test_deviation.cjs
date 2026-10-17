'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),os=require('node:os');
const {Runtime}=require('../lib/runtime.cjs'),{OperatorPlugins}=require('../lib/operator-plugins.cjs');
const graph=require('../public/vision/flow-graph.js');
test('three deviation demos run Open3D in real plugin workers with reference table bindings',async t=>{
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'sieans-deviation-'));t.after(()=>fs.rmSync(dir,{recursive:true,force:true}));
 const runtime=new Runtime(dir,{},new OperatorPlugins(dir)),folder=path.join(__dirname,'../public/vision/samples');
 for(const demo of require('../public/vision/samples/demos-deviation.json')){
  const cloud=JSON.parse(fs.readFileSync(path.join(folder,demo.cloud))),project=graph.normalize({version:1,id:demo.id,name:demo.name,variables:demo.variables,steps:demo.steps});
  const job=runtime.start({project,cloud});await runtime.jobs.get(job.id).promise;const done=runtime.poll(job.id);
  assert.equal(done.state,'completed',done.error);const result=done.results[0].output.result;
  const expected=demo.id.endsWith('pass');assert.equal(result.passed,expected);assert.equal(done.variables.flow.deviationOK,expected);
  if(demo.id.endsWith('missing')){assert.equal(result.forwardOutsideCount,0);assert.equal(result.reverseOutsideCount,1);}
  if(demo.id.endsWith('shift'))assert.equal(result.outsideCount,18);
  assert.deepEqual(done.results[0].output.cloud.points,cloud.points);
 }
});
