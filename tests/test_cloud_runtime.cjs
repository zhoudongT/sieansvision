const {test,after}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path');
const {Runtime}=require('../lib/runtime.cjs');
const {cloud:validate}=require('../lib/frame.cjs');
const graph=require('../public/vision/flow-graph.js');
const vision=require('../lib/vision-client.cjs');
const runtime=()=>new Runtime(fs.mkdtempSync(path.join(os.tmpdir(),'sieans-cloud-test-')),vision);
const source={unit:'mm',frame:'fixture',points:[[0,0,0],[1,1,1],[10,10,10]]};
const node=(id,operation,params={})=>({id,operation,params});
async function run(r,p,extra={}){const start=r.start({project:p,cloud:source,...extra});await r.jobs.get(start.id).promise;return r.poll(start.id);}
after(()=>vision.stop());

test('cloud frames stay isolated across branches, joins use chosen source',async()=>{
 const p=graph.normalize({version:2,name:'cloud branches',steps:[node('join','cloud_measure'),node('crop','cloud_filter',{method:'crop',minimum:[-.1,-.1,-.1],maximum:[2,2,2]}),node('full','cloud_measure')],edges:[{id:'1',from:'source',to:'crop'},{id:'2',from:'source',to:'full'},{id:'3',from:'crop',to:'join'},{id:'4',from:'full',to:'join'}]});
 const job=await run(runtime(),p);assert.equal(job.state,'completed',job.error);
 assert.equal(job.results.find(r=>r.id==='full').output.result.sizeX,10);
 assert.equal(job.results.find(r=>r.id==='join').output.result.sizeX,1);
 assert.equal(source.points.length,3);
});
test('Python receives cloud, passes it downstream and binds 3D measurement to variables',async()=>{
 const p=graph.normalize({version:1,name:'cloud script',steps:[node('py','script',{code:'def run(ctx):\n    c=ctx["cloud"]\n    c["points"]=[[x+10,y,z] for x,y,z in c["points"]]\n    return {"result":{"points":len(c["points"])},"cloud":c}'}),node('size','cloud_measure'),node('var','variables',{scope:'flow',name:'width',value:{$ref:'results.size.sizeX'}})]});
 const job=await run(runtime(),p,{allowScripts:true});assert.equal(job.state,'completed',job.error);assert.equal(job.variables.flow.width,10);assert.equal(job.results[1].output.result.minimum[0],10);
});
test('missing or invalid 3D input yields node error and rolls back variables',async()=>{
 const p=graph.normalize({version:1,name:'empty cloud',steps:[node('set','variables',{scope:'global',name:'bad',value:1}),node('cloud','cloud_measure')]});
 const r=runtime(),job=await run(r,p,{cloud:null});assert.equal(job.state,'failed');assert.equal(job.results.at(-1).id,'cloud');assert.match(job.error,/点云/);assert.deepEqual(r.snapshot(p).global,{});
 assert.throws(()=>validate({unit:'mm',points:[[1,NaN,3]]}),/有限/);
 assert.throws(()=>validate({unit:'mm',points:[[true,0,1]]}),/有限/);
});
test('all bundled 3D demos execute through production runtime',async()=>{
 const dir=path.join(__dirname,'../public/vision/samples');const demos=JSON.parse(fs.readFileSync(path.join(dir,'demos-3d.json')));
 for(const demo of demos){
  const input=await vision.run({operation:'cloud_import',name:demo.cloud,content:fs.readFileSync(path.join(dir,demo.cloud)).toString('base64'),unit:'mm'});
  const steps=demo.steps.map((s,i)=>({...structuredClone(s),id:String(i)}));
  for(const binding of demo.bindings||[])steps[binding.step].params[binding.param]={$ref:'results.'+binding.source+'.'+binding.field};
  const p=graph.normalize({version:demo.connections?2:1,name:demo.name,steps,...(demo.connections?{edges:demo.connections.map(([from,to,when],i)=>({id:'edge-'+i,from:from<0?'source':String(from),to:String(to),...(when?{when}:{})}))}:{})});
  const job=await run(runtime(),p,{cloud:input.cloud});assert.equal(job.state,'completed',demo.id+': '+job.error);
  const result=job.results.at(-1).output.result;
  if(demo.id==='cloud-box')assert.equal(result.sizeX,20);
  if(demo.id==='cloud-clusters')assert.equal(result.count,2);
  if(demo.id==='cloud-volume')assert.equal(result.estimatedVolume,1000);
  if(demo.id==='cloud-icp')assert.ok(result.rmsError<1e-6);
  if(demo.id==='cloud-depth')assert.equal(result.sizeX,190);
  if(demo.id.startsWith('cloud-global')){
   const accepted=demo.id==='cloud-global',registration=job.results.find(r=>r.id==='0').output;
   assert.equal(registration.result.found,accepted);assert.equal(registration.result.passed,accepted);
   assert.equal(job.variables.flow.registrationRoute,accepted?'ALIGNED':'REVIEW');
   assert.equal(!!job.results.find(r=>r.id==='2').skipped,!accepted);
   assert.equal(registration.cloud.frame,accepted?'fixture':'camera');
   assert.equal(Object.hasOwn(registration.result,'transformation'),accepted);
   if(accepted)assert.ok(registration.result.rmsError<.5);else assert.deepEqual(registration.cloud,input.cloud);
  }
 }
});

test('registration resolves selected method and ignores hidden unused parameter bindings',async()=>{
 const dir=path.join(__dirname,'../public/vision/samples');
 const demo=JSON.parse(fs.readFileSync(path.join(dir,'demos-3d.json'))).find(d=>d.id==='cloud-global');
 const cloud=JSON.parse(fs.readFileSync(path.join(dir,demo.cloud)));
 const params={...demo.steps[0].params,method:{$ref:'flow.registrationMethod'},initialTransform:{$ref:'flow.missing'}};
 const p=graph.normalize({version:1,name:'global hidden parameter',variables:{registrationMethod:'global'},steps:[node('register','cloud_register',params)]});
 const job=await run(runtime(),p,{cloud});assert.equal(job.state,'completed',job.error);assert.equal(job.results[0].output.result.found,true);
 const local=graph.normalize({version:1,name:'local hidden parameter',steps:[node('register','cloud_register',{method:'icp',targetCloud:source,voxelSize:{$ref:'flow.missing'},minFitness:{$ref:'flow.missing'}})]});
 const old=await run(runtime(),local);assert.equal(old.state,'completed',old.error);assert.equal(old.results[0].output.result.fitness,1);
});
