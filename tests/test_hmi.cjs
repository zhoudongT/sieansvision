const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),os=require('node:os'),path=require('node:path');
const hmi=require('../public/vision/hmi-layout.js'),graph=require('../public/vision/flow-graph.js'),{Runtime}=require('../lib/runtime.cjs');
const value=(extra={})=>({id:'count',type:'value',label:'检测数量',x:0,y:0,w:3,h:2,color:'#1095bd',fontSize:24,precision:0,unit:'个',binding:{source:'flow',path:'count'},...extra});
const layout=(components=[value()])=>({...hmi.empty(),components});
const project=(steps=[],extra={})=>graph.normalize({version:1,id:'hmi-test',name:'画面测试',steps,...extra});
const runtime=()=>new Runtime(fs.mkdtempSync(path.join(os.tmpdir(),'sieans-hmi-')),{});
async function run(r,p){const job=r.start({project:p});await r.jobs.get(job.id).promise;return r.poll(job.id);}
test('layout round-trips through project normalization and graph changes; legacy has no forced layout',()=>{
 const p=project([{id:'a',operation:'variables',params:{name:'count',value:3}}],{hmi:layout()});assert.deepEqual(p.hmi,layout());assert.deepEqual(graph.layout(p).hmi,p.hmi);assert.deepEqual(graph.remove(p,'a').hmi,p.hmi);assert.equal(project().hmi,undefined);
});
test('layout rejects oversized, duplicate, malformed and unsafe configurations',()=>{
 for(const patch of [{x:11,w:2},{h:30},{y:-1},{fontSize:100},{color:'url(javascript:x)'},{type:'html'},{binding:{source:'flow',path:'constructor.x'}},{precision:9}])assert.throws(()=>hmi.normalize(layout([value(patch)])));
 assert.throws(()=>hmi.normalize(layout([value(),value()])));assert.throws(()=>hmi.normalize({...layout(),components:Array(51).fill(value())}));assert.throws(()=>hmi.normalize({...layout(),rowHeight:1}));
});
test('input contracts restrict write scopes/names, finite limits and allowed actions',()=>{
 const input=value({type:'input',dataType:'number',minimum:0,maximum:10});assert.equal(hmi.normalize(layout([input])).components[0].dataType,'number');
 for(const patch of [{binding:{source:'result',path:'count',nodeId:'a'}},{binding:{source:'flow',path:'nested.count'}},{minimum:11},{maximum:Infinity},{dataType:'object'}])assert.throws(()=>hmi.normalize(layout([{...input,...patch}])));
 assert.throws(()=>hmi.normalize(layout([value({type:'button',action:'eval'})])));
});
test('binding reads all scopes, nested results and status; unavailable/skipped results stay unknown',()=>{
 const state={variables:{global:{count:1},flow:{count:2},modules:{a:{count:3}}},results:[{id:'a',output:{result:{nested:{count:4}}}},{id:'skip',skipped:true,output:{result:{passed:true}}}],status:{elapsedMs:5}};
 assert.equal(hmi.read({source:'global',path:'count'},state),1);assert.equal(hmi.read({source:'flow',path:'count'},state),2);assert.equal(hmi.read({source:'module',nodeId:'a',path:'count'},state),3);assert.equal(hmi.read({source:'result',nodeId:'a',path:'nested.count'},state),4);assert.equal(hmi.read({source:'status',path:'elapsedMs'},state),5);
 assert.equal(hmi.read({source:'result',nodeId:'skip',path:'passed'},state),undefined);assert.equal(hmi.read({source:'flow',path:'constructor'},state),undefined);assert.equal(hmi.read({source:'module',nodeId:'missing',path:'x'},state),undefined);
});
test('dragging snaps to the 12-column grid and clamps within page bounds',()=>{
 assert.deepEqual(hmi.move(value(),9.9,-4,layout()),value({x:9,y:0}));assert.deepEqual(hmi.move(value(),1.6,99,layout()),value({x:2,y:8}));
});
test('runtime view isolates projects, suppresses unchanged large results and always refreshes variables',async()=>{
 const r=runtime(),p=project([{id:'set',operation:'variables',params:{name:'count',value:3}}]);
 assert.equal(r.view(p).status.state,'idle');await run(r,p);const view=r.view(p);assert.equal(view.status.state,'completed');assert.equal(view.variables.flow.count,3);assert.equal(view.results[0].output.result.value,3);
 const same=r.view(p,view.version);assert.equal(same.results,undefined);const state=r.snapshot(p);state.flow.count=4;r.update(p,state,state.revision);assert.equal(r.view(p,view.version).variables.flow.count,4);
 const other=project([],{id:'other'});assert.equal(r.view(other).status.state,'idle');assert.deepEqual(r.view(other).results,[]);assert.deepEqual(r.view(other).variables.flow,{});
});
test('new failures/cancellations replace prior success, and reload has no stale result payload',async()=>{
 const r=runtime(),p=project([{id:'set',operation:'variables',params:{name:'count',value:3}}]);await run(r,p);const previous=r.view(p).version;
 p.steps[0].params.value={$ref:'flow.missing'};await run(r,p);const failed=r.view(p,previous);assert.equal(failed.status.state,'failed');assert(failed.results[0].error);assert.equal(hmi.read({source:'result',nodeId:'set',path:'value'},failed),undefined);
 p.steps=[{id:'wait',operation:'delay',params:{milliseconds:30000},imageFrom:'source'}];p.edges=[{id:'e',from:'source',to:'wait'}];const job=r.start({project:p});r.cancel(job.id);await r.jobs.get(job.id).promise;assert.equal(r.view(p).status.state,'cancelled');assert.deepEqual(r.view(p).results,[]);
 const reloaded=new Runtime(path.dirname(r.variables.file),{});assert.equal(reloaded.view(p).status.state,'idle');assert.equal(reloaded.view(p).variables.flow.count,3);
});
