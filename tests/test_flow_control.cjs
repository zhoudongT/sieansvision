'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path');
const graph=require('../public/vision/flow-graph.js'),control=require('../lib/flow-control.cjs'),{Runtime}=require('../lib/runtime.cjs');
const n=(id,operation,params={})=>({id,operation,params});
const edge=(from,to,when)=>({id:from+'-'+to,from,to,...(when?{when}:{})});
const project=(steps,edges)=>graph.normalize({version:2,id:'conditions',name:'Conditions',steps,edges});
const runtime=vision=>new Runtime(fs.mkdtempSync(path.join(os.tmpdir(),'sieans-control-')),vision||{run:async()=>{throw Error('Unexpected vision invocation');}});
async function execute(r,p,options={}){const start=r.start({project:p,...options});await r.jobs.get(start.id).promise;return r.poll(start.id);}
function branches(value=true){return project([
 n('condition','condition',{comparison:'is_true',left:value}),
 n('yes','variables',{scope:'flow',name:'route',value:'OK'}),
 n('no','variables',{scope:'flow',name:'route',value:'NG'}),
 n('merge','branch_merge'),n('save','variables',{scope:'flow',name:'mergedRoute',value:{$ref:'results.merge.value.value'}})
],[edge('source','condition'),edge('condition','yes','true'),edge('condition','no','false'),edge('yes','merge'),edge('no','merge'),edge('merge','save')]);}

test('conditions compare types strictly and reject invalid numeric/boolean operands',()=>{
 assert.equal(control.condition({left:1,right:'1'}).passed,false);assert.equal(control.condition({left:null,right:null}).passed,true);
 for(const [comparison,left,right,expected] of [['ne',1,2,true],['gt',3,2,true],['gte',3,3,true],['lt',1,2,true],['lte',2,2,true],['contains','标签-123','123',true],['is_false',false,undefined,true],['is_true',true,undefined,true]])assert.equal(control.condition({comparison,left,right}).passed,expected);
 for(const p of [{left:[],right:[]},{comparison:'gt',left:'3',right:2},{comparison:'contains',left:1,right:'1'},{comparison:'is_true',left:1},{comparison:'gt',left:Infinity,right:0},{comparison:'eval',left:true}])assert.throws(()=>control.condition(p));
});
test('exclusive routes skip inactive writes and merge active result in either direction',async()=>{
 const r=runtime();let p=branches(true),job=await execute(r,p);assert.equal(job.state,'completed',job.error);assert.equal(job.variables.flow.route,'OK');assert.equal(job.variables.flow.mergedRoute,'OK');assert.equal(job.results.find(x=>x.id==='no').skipped,true);assert.equal(job.results.find(x=>x.id==='merge').inputFrom,'yes');
 p.steps[0].params.left=false;p.steps.reverse();job=await execute(r,p);assert.equal(job.state,'completed',job.error);assert.equal(job.variables.flow.route,'NG');assert.equal(job.variables.flow.mergedRoute,'NG');assert.equal(job.results.find(x=>x.id==='yes').skipped,true);assert.equal(job.results.find(x=>x.id==='merge').inputFrom,'no');
});
test('inactive branches never resolve bad bindings or invoke scripts/cameras/protocols',async()=>{
 const p=project([n('c','condition',{left:0,right:1}),n('camera','camera_capture',{driver:'invalid'}),n('script','script',{code:'raise Exception("must not run")'}),n('io','modbus_write',{value:{$ref:'flow.missing'}})],[edge('source','c'),edge('c','camera','true'),edge('camera','script'),edge('script','io')]);
 const job=await execute(runtime(),p,{allowScripts:true});assert.equal(job.state,'completed',job.error);assert.equal(job.results.filter(x=>x.skipped).length,3);
});
test('ordinary AND join skips while explicit exclusive merge accepts the active input',async()=>{
 const p=branches();p.steps.push(n('all','variables',{name:'unwanted',value:1}));p.edges.push(edge('yes','all'),edge('no','all'));p.steps.at(-1).imageFrom='yes';
 const job=await execute(runtime(),p);assert.equal(job.state,'completed',job.error);assert.equal(job.results.find(x=>x.id==='all').skipped,true);assert.equal(job.variables.flow.unwanted,undefined);
});
test('ambiguous merge fails and rolls back earlier variables',async()=>{
 const p=branches();p.edges.find(e=>e.to==='no').when='always';const r=runtime(),job=await execute(r,p);assert.equal(job.state,'failed');assert.match(job.error,/恰好一路/);assert.deepEqual(r.snapshot(p).flow,{});
});
test('nested all-skipped merge does not resurrect a skipped branch',async()=>{
 const p=project([n('c','condition',{left:1,right:0}),n('a','condition',{left:0,right:0}),n('b','delay',{milliseconds:30000}),n('merge','branch_merge'),n('v','variables',{name:'never',value:1})],[edge('source','c'),edge('c','a','true'),edge('a','b','true'),edge('a','merge','false'),edge('b','merge'),edge('merge','v')]);
 const job=await execute(runtime(),p);assert.equal(job.state,'completed',job.error);assert.equal(job.results.filter(x=>x.skipped).length,4);assert.equal(job.variables.flow.never,undefined);
});
test('selected non-matching branch skips and excludes the other branch',async()=>{
 const job=await execute(runtime(),branches(false),{target:'yes'});assert.equal(job.state,'completed',job.error);assert.deepEqual(job.results.map(x=>x.id),['condition','yes']);assert.equal(job.results[1].skipped,true);
});
test('bindings to inactive results fail rather than reusing a prior run',async()=>{
 const p=branches(false);p.steps.at(-1).params.value={$ref:'results.yes.value'};const r=runtime(),job=await execute(r,p);assert.equal(job.state,'failed');assert.match(job.error,/引用不存在/);assert.deepEqual(r.snapshot(p).flow,{});
});
test('unary condition ignores unused right binding including bound comparison method',async()=>{
 const p=project([n('c','condition',{comparison:{$ref:'flow.method'},left:true,right:{$ref:'flow.missing'}})],[edge('source','c')]);p.variables={method:'is_true'};
 const job=await execute(runtime(),p);assert.equal(job.state,'completed',job.error);assert.equal(job.results[0].output.result.passed,true);
});
test('merge passes the actual active branch image and cloud, not configured inactive parent',async()=>{
 const cloud={points:[[1,2,3]],unit:'mm'};let received;
 const r=runtime({run:async request=>{if(request.operation==='preprocess')return {result:{},annotatedImage:'changed-'+request.params.method,elapsedMs:0};received=request;return {result:{},elapsedMs:0};}});
 const p=project([n('c','condition',{left:false,right:true}),n('yes','preprocess',{method:'grayscale'}),n('no','preprocess',{method:'threshold'}),n('merge','branch_merge'),n('inspect','cloud_measure')],[edge('source','c'),edge('c','yes','true'),edge('c','no','false'),edge('yes','merge'),edge('no','merge'),edge('merge','inspect')]);
 assert.equal(p.steps[3].imageFrom,'yes');const job=await execute(r,p,{image:'source',cloud});assert.equal(job.state,'completed',job.error);assert.equal(received.image,'changed-threshold');assert.deepEqual(received.cloud,cloud);
});
test('delay cancels promptly and rolls back variables; next job can execute',async()=>{
 const p=project([n('v','variables',{name:'count',value:1}),n('wait','delay',{milliseconds:30000})],[edge('source','v'),edge('v','wait')]);const r=runtime(),began=Date.now(),job=r.start({project:p});assert.equal(r.poll(job.id).activeStep,'wait');r.cancel(job.id);await r.jobs.get(job.id).promise;assert.equal(r.poll(job.id).state,'cancelled');assert(Date.now()-began<2000);assert.deepEqual(r.snapshot(p).flow,{});p.steps[1].params.milliseconds=5;assert.equal((await execute(r,p)).state,'completed');
});
test('guard schema rejects unsupported conditions and guarded edges from ordinary nodes',()=>{
 const p=branches();p.edges[0].when='true';assert.throws(()=>graph.normalize(p),/条件判断/);delete p.edges[0].when;p.edges[1].when='maybe';assert.throws(()=>graph.normalize(p),/连线条件/);
});
test('delay rejects fractional, negative, oversized and string durations',async()=>{
 for(const milliseconds of [-1,30001,1.5,'5'])await assert.rejects(control.delay({milliseconds}),/整数毫秒/);
});
