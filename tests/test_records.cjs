const {test,after}=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),os=require('node:os');
const {Runtime}=require('../lib/runtime.cjs'),{OperatorPlugins}=require('../lib/operator-plugins.cjs'),{createOperatorBridge}=require('../lib/operator-bridge.cjs');
const {ContinuousRun}=require('../lib/continuous-run.cjs'),graph=require('../public/vision/flow-graph.js'),vision=require('../lib/vision-client.cjs');
const samples=path.join(__dirname,'../public/vision/samples'),demos=JSON.parse(fs.readFileSync(path.join(samples,'demos-records.json')));
function make(){const dir=fs.mkdtempSync(path.join(os.tmpdir(),'sieans-records-'));return new Runtime(dir,vision,new OperatorPlugins(dir));}
function project(d){
 const steps=structuredClone(d.steps).map((s,i)=>({...s,id:'d'+i}));
 for(const b of d.bindings||[])steps[b.step].params[b.param]={$ref:'results.d'+b.source+'.'+b.field};
 const p={version:d.connections?2:1,id:d.id,name:d.name,variables:d.variables||{},steps};
 if(d.connections)p.edges=d.connections.map(([from,to,when],i)=>({id:'e'+i,from:from<0?'source':'d'+from,to:'d'+to,...(when?{when}:{})}));
 if(d.hmi){p.hmi=structuredClone(d.hmi);for(const b of d.hmiBindings||[])p.hmi.components[b.component].binding.nodeId='d'+b.step;}
 return graph.normalize(p);
}
async function run(runtime,p,extra={}){const job=runtime.start({project:p,...extra});await runtime.jobs.get(job.id).promise;return runtime.poll(job.id);}
after(()=>vision.stop());

test('continuous OpenCV record pipeline preserves typed history and HMI bindings while retaining only three samples',async()=>{
 const runtime=make(),p=project(demos[0]),image='data:image/png;base64,'+fs.readFileSync(path.join(samples,demos[0].image)).toString('base64');
 const continuous=new ContinuousRun(runtime,path.dirname(runtime.variables.file));continuous.start({project:p,image,intervalMs:100,maxCycles:5});await continuous.promise;
 assert.equal(continuous.status().state,'completed',continuous.status().error);const vars=runtime.snapshot(p).flow;
 assert.deepEqual(vars.inspectionRecords.map(r=>r.sequence),[3,4,5]);assert.equal(vars.meanCount,3);assert.equal(vars.recordCount,3);assert(vars.inspectionRecords.every(r=>r.count===3&&r.passed===true));
 assert.equal(p.hmi.components[3].binding.path,'inspectionRecords');
});

test('filter, stable sort, selected maximum and numerical statistics run without an image or script trust',async()=>{
 const job=await run(make(),project(demos[1]));assert.equal(job.state,'completed',job.error);
 assert.deepEqual(job.variables.flow.sortedRecords.map(r=>r.width),[12,8,6]);assert.equal(job.results[2].output.result.record.width,12);assert(Math.abs(job.results[3].output.result.summary.mean-26/3)<1e-12);
});

test('one-record-per-run sampling gates real handeye fitting until six poses and rolls back out-of-range sample',async()=>{
 const runtime=make(),p=project(demos[2]);let job;
 for(let count=1;count<=8;count++){
  job=await run(runtime,p);assert.equal(job.state,'completed',job.error);assert.equal(job.variables.flow.poseCount,count);
  assert.equal(job.results.at(-1).skipped===true,count<6);
  if(count>=6)assert(Math.abs(job.variables.flow.handeyeCalibration.translation[0]-30)<1e-8);
 }
 assert.equal(Object.hasOwn(job.variables.flow.poseRows[0],'sampleId'),false);
 job=await run(runtime,p);assert.equal(job.state,'failed');assert.match(job.error,/索引越界/);assert.equal(runtime.snapshot(p).flow.poseCount,8);assert.equal(runtime.snapshot(p).flow.sampleIndex,8);
});

test('output collections bind all scopes; failed duplicate append preserves committed collection',async()=>{
 const runtime=make(),p=graph.normalize({version:1,id:'records-scopes',name:'记录变量范围',variables:{rows:[]},steps:[{id:'append',operation:'plugin',params:{pluginId:'sieans-records',pluginVersion:'1.0.0',operatorId:'append',arguments:{records:{$ref:'flow.rows'},record:{id:1,value:7},keyField:'id'},outputBindings:[{scope:'flow',name:'rows',field:'records'},{scope:'global',name:'recordRows',field:'records'},{scope:'module',name:'recordRows',field:'records'}]}}]});
 let job=await run(runtime,p);assert.equal(job.state,'completed',job.error);assert.deepEqual(job.variables.global.recordRows,job.variables.modules.append.recordRows);
 job=await run(runtime,p);assert.equal(job.state,'failed');assert.match(job.error,/已存在/);assert.deepEqual(runtime.snapshot(p).flow.rows,[{id:1,value:7}]);
});

test('Node-RED operator bridge transforms records and preserves attached image/cloud channels',async()=>{
 const bridge=createOperatorBridge(make().plugins),cloud={unit:'mm',points:[[1,2,3]]};
 const out=await bridge.run({pluginId:'sieans-records',pluginVersion:'1.0.0',operatorId:'build',arguments:{fields:{value:4,passed:true}},image:'input',cloud});
 assert.deepEqual(out.result.record,{value:4,passed:true});assert.equal(out.image,'input');assert.deepEqual(out.cloud,cloud);
});
