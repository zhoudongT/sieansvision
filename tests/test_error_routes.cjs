'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),os=require('node:os'),path=require('node:path');
const graph=require('../public/vision/flow-graph.js'),{Runtime}=require('../lib/runtime.cjs');
const node=(id,operation,params={})=>({id,operation,params});
const edge=(from,to,when)=>({id:from+'-'+to,from,to,...(when?{when}:{})});
const runtime=vision=>new Runtime(fs.mkdtempSync(path.join(os.tmpdir(),'sieans-errors-')),vision||{run:async()=>{throw Error('camera unavailable');}});
const project=(steps,edges,extra={})=>graph.normalize({version:2,id:'errors',name:'Error routes',steps,edges,...extra});
async function execute(r,p,extra={}){const {id}=r.start({project:p,...extra});await r.jobs.get(id).promise;return r.poll(id);}
function recovery(){return project([node('inspect','geometry'),node('ok','variables',{name:'route',value:'OK'}),node('ng','variables',{name:'route',value:{$ref:'results.inspect.error'}}),node('merge','branch_merge'),node('after','variables',{name:'finished',value:true})],[edge('source','inspect'),edge('inspect','ok','success'),edge('inspect','ng','error'),edge('ok','merge'),edge('ng','merge'),edge('merge','after')]);}

test('failure enters error route, skips normal work, carries error fields and rejoins',async()=>{
 const r=runtime(),p=recovery(),job=await execute(r,p,{image:'source'});assert.equal(job.state,'completed',job.error);assert.equal(job.variables.flow.route,'camera unavailable');assert.equal(job.variables.flow.finished,true);assert.equal(job.results.find(x=>x.id==='inspect').handled,true);assert.equal(job.results.find(x=>x.id==='ok').skipped,true);assert.equal(job.results.find(x=>x.id==='merge').inputFrom,'ng');
 const archived=await r.history.get(job.id);assert.equal(archived.results[0].handled,true);assert.equal(archived.results[0].error,'camera unavailable');
});
test('successful operation activates success/default routes and skips recovery',async()=>{
 const p=recovery(),r=runtime({run:async()=>({result:{count:3},elapsedMs:0})}),job=await execute(r,p,{image:'source'});assert.equal(job.state,'completed');assert.equal(job.variables.flow.route,'OK');assert.equal(job.results.find(x=>x.id==='ng').skipped,true);assert.equal(job.results.find(x=>x.id==='merge').inputFrom,'ok');
 delete p.edges.find(e=>e.to==='ok').when;assert.equal((await execute(r,p,{image:'source'})).variables.flow.route,'OK');
});
test('failed variable write restores its transaction and keeps earlier successful writes',async()=>{
 const p=project([node('before','variables',{name:'prior',value:8}),node('bad','variables',{name:'count',value:'invalid'}),node('recover','variables',{name:'restored',value:{$ref:'flow.count'}})],[edge('source','before'),edge('before','bad'),edge('bad','recover','error')],{variables:{count:5},variableTypes:{count:'integer'}});
 const job=await execute(runtime(),p);assert.equal(job.state,'completed',job.error);assert.deepEqual(job.variables.flow,{count:5,prior:8,restored:5});assert.match(job.results[1].error,/类型不匹配/);
});
test('unhandled handler failure rolls back the whole run, and selected run does not swallow error',async()=>{
 const p=recovery();p.steps.find(s=>s.id==='ng').params.value={$ref:'flow.missing'};const r=runtime(),job=await execute(r,p,{image:'source'});assert.equal(job.state,'failed');assert.deepEqual(r.snapshot(p).flow,{});
 const selected=await execute(runtime(),recovery(),{image:'source',target:'inspect'});assert.equal(selected.state,'failed');assert.equal(selected.results[0].handled,undefined);
});
test('cancelled waits do not enter recovery, and inactive branches cannot activate an error route',async()=>{
 const p=project([node('wait','delay',{milliseconds:30000}),node('recover','variables',{name:'wrong',value:1})],[edge('source','wait'),edge('wait','recover','error')]),r=runtime(),start=r.start({project:p});r.cancel(start.id);await r.jobs.get(start.id).promise;assert.equal(r.poll(start.id).state,'cancelled');assert.equal(r.poll(start.id).results.length,0);
 const skipped=project([node('c','condition',{left:0,right:1}),node('bad','geometry'),node('recover','variables',{name:'wrong',value:1})],[edge('source','c'),edge('c','bad','true'),edge('bad','recover','error')]);const job=await execute(runtime(),skipped);assert.equal(job.state,'completed');assert.equal(job.results.filter(r=>r.skipped).length,2);assert.equal(job.variables.flow.wrong,undefined);
});
test('error route propagates original image/cloud and supports chained handlers',async()=>{
 const cloud={unit:'mm',points:[[1,2,3]]};let seen;
 const r=runtime({run:async request=>{if(request.operation==='geometry')throw Error('bad image');seen=request;return {result:{count:1},cloud,elapsedMs:0};}});
 const p=project([node('bad','geometry'),node('cloud','cloud_measure')],[edge('source','bad'),edge('bad','cloud','error')]);const job=await execute(r,p,{image:'source',cloud});assert.equal(job.state,'completed',job.error);assert.equal(seen.image,'source');assert.deepEqual(seen.cloud,cloud);
 const chained=project([node('a','condition',{comparison:'gt',left:'bad',right:1}),node('b','delay',{milliseconds:-1}),node('c','variables',{name:'error',value:{$ref:'results.b.error'}})],[edge('source','a'),edge('a','b','error'),edge('b','c','error')]);const result=await execute(runtime(),chained);assert.equal(result.state,'completed');assert.equal(result.results.filter(r=>r.handled).length,2);assert.match(result.variables.flow.error,/整数毫秒/);
});
test('error route schema rejects source errors and client execution cannot bypass the server',async()=>{
 const p=recovery();p.edges[0].when='error';assert.throws(()=>graph.normalize(p),/数据源/);delete p.edges[0].when;await assert.rejects(graph.run(p,'source',async()=>({})),/服务器/);
});
