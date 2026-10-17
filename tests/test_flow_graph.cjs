const {test}=require('node:test');
const assert=require('node:assert/strict');
const graph=require('../public/vision/flow-graph.js');
const node=(id,operation='preprocess')=>({id,operation,params:{},position:{x:50,y:50}});
const edge=(from,to)=>({id:from+'-'+to,from,to});
const diamond=()=>graph.normalize({version:2,name:'branches',steps:[node('join','geometry'),node('right','geometry'),node('left')],edges:[edge('source','left'),edge('source','right'),edge('left','join'),edge('right','join')]});
test('legacy projects become an equivalent chain and preserve stable IDs',()=>{
  const p=graph.normalize({version:1,name:'old',steps:[node('a'),node('b','geometry')]});assert.equal(p.version,2);assert.deepEqual(p.edges.map(e=>[e.from,e.to]),[['source','a'],['a','b']]);assert.deepEqual(graph.normalize(p),p);
});
test('position and array order do not determine execution; branches keep separate pixels',async()=>{
  const p=diamond(),calls=[];
  await graph.run(p,'raw',async(s,input)=>{calls.push([s.id,input]);return {annotatedImage:s.id+'-pixels'};});
  assert.deepEqual(calls,[['right','raw'],['left','raw'],['join','left-pixels']]);
  p.steps.reverse();p.steps.forEach(s=>s.position={x:900,y:10});
  const seen=[];await graph.run(p,'raw',async(s,input)=>{seen.push([s.id,input]);return {annotatedImage:s.id+'-pixels'};});assert.deepEqual(seen.at(-1),['join','left-pixels']);
});
test('joins explicitly select image parent; overlays are not downstream input',async()=>{
  const p=diamond();p.steps[0].imageFrom='right';const calls=[];
  await graph.run(p,'raw',async(s,input)=>{calls.push([s.id,input]);return {annotatedImage:'overlay'};});assert.deepEqual(calls.at(-1),['join','raw']);
});
test('cycles, self edges, duplicates and dangling endpoints are rejected without mutating graph',()=>{
  const p=diamond(),before=JSON.stringify(p);
  for(const e of [edge('join','left'),edge('left','left'),edge('source','left'),edge('missing','join')])assert.throws(()=>graph.connect(p,e));
  assert.equal(JSON.stringify(p),before);
});
test('edge removal repairs image source; removing a node removes all related edges',()=>{
  let p=diamond();p=graph.disconnect(p,'left-join');assert.equal(p.steps[0].imageFrom,'right');
  p=graph.remove(p,'right');assert.equal(p.steps[0].imageFrom,null);assert.ok(p.edges.every(e=>e.from!=='right'&&e.to!=='right'));assert.throws(()=>graph.order(p),/未连接/);
});
test('execute selected includes ancestors, excludes unrelated descendants',async()=>{
  const seen=[];await graph.run(diamond(),'raw',async s=>{seen.push(s.id);return {annotatedImage:'image'};},{target:'left'});assert.deepEqual(seen,['left']);
});
test('unconnected draft nodes block full run, but not independent selected branch',async()=>{
  const p=diamond();p.steps.push(node('draft'));let calls=0;
  await assert.rejects(graph.run(p,'raw',async()=>{calls++;}),/未连接/);assert.equal(calls,0);
  const results=await graph.run(p,'raw',async()=>({annotatedImage:'img'}),{target:'left'});assert.equal(results.length,1);
});
test('auto layout for 50-way branch remains saveable',()=>{
  const steps=Array.from({length:50},(_,i)=>node('n'+i));const p=graph.normalize({version:2,name:'wide',steps,edges:steps.map(s=>edge('source',s.id))});assert.doesNotThrow(()=>graph.normalize(graph.layout(p)));
});
test('failure and stop prevent downstream calls',async()=>{
  const p=diamond(),seen=[];await assert.rejects(graph.run(p,'raw',async s=>{seen.push(s.id);throw Error('failed');}),/failed/);assert.equal(seen.length,1);
  let stop=false;const done=await graph.run(p,'raw',async()=>({annotatedImage:'img'}),{onResult:()=>stop=true,cancelled:()=>stop});assert.equal(done.length,1);
});
test('real branch demonstration runs through Python engine in dependency order',async()=>{
  const fs=require('node:fs'),path=require('node:path'),vision=require('../lib/vision-client.cjs');
  const demo=JSON.parse(fs.readFileSync(path.join(__dirname,'../public/vision/samples/demos.json'),'utf8')).find(x=>x.id==='branches');
  const steps=demo.steps.map((s,i)=>({...s,id:String(i),imageFrom:demo.imageParents[i]<0?'source':String(demo.imageParents[i])}));
  const p=graph.normalize({version:2,name:'demo',steps,edges:demo.connections.map(([from,to],i)=>({id:'e'+i,from:from<0?'source':String(from),to:String(to)}))});
  const image=fs.readFileSync(path.join(__dirname,'../public/vision/samples/parts.png')).toString('base64');
  try{const results=await graph.run(p,image,(s,input)=>vision.run({operation:s.operation,params:s.params,image:input}));assert.deepEqual(results.map(x=>x.id),['1','2','0']);assert.equal(results.at(-1).output.result.count,3);assert.ok(results[1].output.result.count>=1);}finally{vision.stop();}
});
