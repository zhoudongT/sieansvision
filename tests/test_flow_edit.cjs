const {test}=require('node:test'),assert=require('node:assert/strict');
const Graph=require('../public/vision/flow-graph.js'),Edit=require('../public/vision/flow-edit-model.js');
const make=()=>Graph.normalize({version:1,id:'project',name:'编辑测试',steps:[
  {id:'a',operation:'preprocess',name:'灰度预处理',params:{method:'gray'}},
  {id:'b',operation:'geometry',params:{nested:[{$ref:'results.a.count'},{$ref:'flow.limit'}]},variables:{threshold:3}}
]});
test('copy rewrites internal references, keeps upstream inputs and isolates state',()=>{
  const original=make();let index=0;const copied=Edit.copy(original,['a','b']);
  const {project,ids}=Edit.paste(original,copied,()=>`copy-${++index}`);
  assert.deepEqual(ids,['copy-1','copy-2']);assert.equal(project.steps[2].imageFrom,'source');
  assert.equal(project.steps[3].imageFrom,'copy-1');assert.equal(project.steps[3].params.nested[0].$ref,'results.copy-1.count');
  assert.equal(project.steps[3].params.nested[1].$ref,'flow.limit');
  const order=Graph.plan(project).map(s=>s.id);assert.equal(order.length,4);assert.ok(order.indexOf('a')<order.indexOf('b'));assert.ok(order.indexOf('copy-1')<order.indexOf('copy-2'));
  project.steps[3].variables.threshold=100;assert.equal(original.steps[1].variables.threshold,3);
  assert.equal(original.steps.length,2);assert.equal(project.steps[2].name,'灰度预处理 副本');
});
test('copy a leaf preserves its existing parent; cross-flow and deleted references fail atomically',()=>{
  let index=0;const p=make(),clip=Edit.copy(p,['b']);
  const pasted=Edit.paste(p,clip,()=>`n-${++index}`).project;assert.equal(pasted.steps.at(-1).imageFrom,'a');
  assert.throws(()=>Edit.paste({...p,id:'different'},clip,()=>`n-${++index}`),/当前流程/);
  const deleted=Graph.remove(p,'a');assert.throws(()=>Edit.paste(deleted,clip,()=>`n-${++index}`),/已删除/);
  assert.equal(deleted.steps.length,1);
});
test('insertion preserves condition at original source and routes chosen input through new node',()=>{
  const p=make();p.steps[0].operation='condition';p.edges[1].when='false';
  p.steps.push({id:'new',operation:'preprocess',params:{},position:{x:300,y:200},imageFrom:null});
  let i=0;const next=Edit.insert(p,p.edges[1].id,'new',()=>`insert-${++i}`);
  assert.equal(next.edges.find(e=>e.to==='new').when,'false');
  assert.equal(next.edges.find(e=>e.to==='b').when,'always');assert.equal(next.steps[1].imageFrom,'new');
  assert.equal(next.steps[2].imageFrom,'a');assert.equal(p.steps[1].imageFrom,'a');
});
test('inserting into dependency edge does not replace another selected image parent',()=>{
  const p=make();p.steps.push({id:'side',operation:'geometry',params:{},position:{x:300,y:200},imageFrom:'source'});
  p.edges.push({id:'side-in',from:'source',to:'side'},{id:'dependency',from:'side',to:'b'});
  p.steps.push({id:'new',operation:'preprocess',params:{},position:{x:300,y:300},imageFrom:null});
  let i=0;const next=Edit.insert(p,'dependency','new',()=>`insert-${++i}`);assert.equal(next.steps[1].imageFrom,'a');
  assert.throws(()=>Edit.insert(next,'side-in','new',()=>`insert-${++i}`),/尚未连接/);
});
test('group removal cleans links and output node; undo/redo restores exact snapshots and branches',()=>{
  const p=make();p.outputNode='b';const h=new Edit.History();h.reset(p);
  const removed=Edit.remove(p,['a','b']);h.record(removed);assert.equal(removed.steps.length,0);assert.equal(removed.edges.length,0);assert.equal(removed.outputNode,null);
  assert.deepEqual(h.undo(),p);assert.deepEqual(h.redo(),removed);h.undo();
  const renamed=structuredClone(p);renamed.steps[0].name='新名字';h.record(renamed);assert.equal(h.canRedo,false);assert.deepEqual(h.undo(),p);
});
test('history limits memory and rejects invalid saved module names',()=>{
  const h=new Edit.History(2);h.reset({n:0});h.record({n:1});h.record({n:2});h.record({n:3});assert.deepEqual(h.undo(),{n:2});assert.deepEqual(h.undo(),{n:1});assert.equal(h.canUndo,false);
  const p=make();p.steps[0].name={bad:true};assert.throws(()=>Graph.normalize(p),/模块名称/);
});
