'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path');
const {OperatorPlugins}=require('../lib/operator-plugins.cjs');
const {Runtime}=require('../lib/runtime.cjs');
const graph=require('../public/vision/flow-graph.js');
function fixture(t){const dir=fs.mkdtempSync(path.join(os.tmpdir(),'sieans-relations-'));t.after(()=>fs.rmSync(dir,{recursive:true,force:true}));return {dir,plugins:new OperatorPlugins(dir)};}
const params=(id,args={})=>({pluginId:'sieans-relations',pluginVersion:'1.0.0',operatorId:id,arguments:args});
test('real Python: perpendicular/intersecting/parallel 2D lines and invalid geometry',async t=>{
 const {plugins}=fixture(t),run=async args=>(await plugins.run(params('lines-2d',args),{})).data.result;
 let r=await run({});assert.equal(r.angleDegrees,90);assert.equal(r.parallel,false);assert.equal(r.items[0].value,50);assert.equal(r.items[1].value,0);
 r=await run({entities:[{x1:0,y1:0,x2:1,y2:0},{x1:3,y1:7,x2:2,y2:7}]});assert.equal(r.parallel,true);assert.equal(r.items[0].value,7);
 await assert.rejects(run({entities:[{x1:0,y1:0,x2:0,y2:0},{x1:0,y1:1,x2:1,y2:1}]}),/端点/);
 await assert.rejects(run({entities:[]}),/行数/);
});
test('real Python: normalized/reversed plane normals, oblique planes, degeneracy',async t=>{
 const {plugins}=fixture(t),run=async entities=>(await plugins.run(params('planes-3d',{entities}),{})).data.result;
 let r=await run([{a:0,b:0,c:2,d:0},{a:0,b:0,c:-3,d:30}]);assert.equal(r.parallel,true);assert.equal(r.items[0].value,10);
 r=await run([{a:0,b:0,c:1,d:0},{a:1,b:0,c:1,d:0}]);assert(Math.abs(r.angleDegrees-45)<1e-10);assert.equal(r.items.length,1);assert.equal(r.parallel,false);
 await assert.rejects(run([{a:0,b:0,c:0,d:1},{a:0,b:0,c:1,d:0}]),/法向量/);
});
test('demo projects execute through runtime and bind measured values',async t=>{
 const {dir,plugins}=fixture(t),runtime=new Runtime(dir,{},plugins);
 const demos=require('../public/vision/samples/demos-relations.json');
 for(const demo of demos.filter(d=>d.steps.length===1)){const project=graph.normalize({version:1,id:demo.id,name:demo.name,variables:demo.variables||{},steps:demo.steps});const job=runtime.start({project});await runtime.jobs.get(job.id).promise;const done=runtime.poll(job.id);assert.equal(done.state,'completed',done.error);assert.equal(done.variables.flow.measuredAngle,demo.id.endsWith('lines-2d')?90:0);}
});
test('near-parallel thresholds suppress unstable intersections and distinguish reference distances',async t=>{
 const {plugins}=fixture(t);
 const run=async(id,arguments_)=>(await plugins.run(params(id,arguments_),{})).data.result;
 const slope=Math.tan(.01*Math.PI/180);
 const entities=[{x1:0,y1:0,x2:100,y2:0},{x1:0,y1:10,x2:100,y2:10+100*slope}];
 let r=await run('lines-2d',{entities,parallelTolerance:.02});
 assert.equal(r.parallel,true);assert.equal(r.items.length,2);assert.equal(r.items[0].value,10);
 r=await run('lines-2d',{entities,parallelTolerance:.001});
 assert.equal(r.parallel,false);assert(Math.abs(r.items[0].value+10/slope)<1e-5);assert.equal(r.items[1].value,0);
 const planes=[{a:0,b:0,c:1,d:-100},{a:slope,b:0,c:1,d:-110}];
 r=await run('planes-3d',{entities:planes,parallelTolerance:.02});
 assert.equal(r.parallel,true);assert(Math.abs(r.angleDegrees-.01)<1e-10);assert(Math.abs(r.items[0].value-10)<1e-4);
 r=await run('planes-3d',{entities:planes,parallelTolerance:.001});
 assert.equal(r.parallel,false);assert.equal(r.items.length,1);
});
test('demo assets and form declarations remain complete',t=>{
 const {readPackage}=require('../lib/operator-plugins.cjs');
 const manifest=readPackage(path.join(__dirname,'../operator-plugins/sieans-relations')).manifest;
 const demos=require('../public/vision/samples/demos-relations.json');
 for(const demo of demos){assert(demo.category);assert(demo.expected);assert(fs.existsSync(path.join(__dirname,'../public/vision/samples',demo.image)));assert(manifest.operators.some(o=>o.id===demo.steps.at(-1).params.operatorId));}
 for(const op of manifest.operators){const table=op.parameters.find(p=>p.key==='entities');assert.equal(table.minimumRows,2);assert.equal(table.maximumRows,2);assert(table.columns.every(c=>c.type==='number'));}
});
test('angle inspection rejects inverted limits and produces a bound quality result',async t=>{
 const {dir,plugins}=fixture(t);
 const run=async arguments_=>(await plugins.run(params('lines-2d',arguments_),{})).data.result;
 assert.equal((await run({minimumAngle:90,maximumAngle:90})).passed,true);
 assert.equal((await run({minimumAngle:0,maximumAngle:89})).passed,false);
 await assert.rejects(run({minimumAngle:20,maximumAngle:10}),/上下限/);
 const runtime=new Runtime(dir,{},plugins),project=graph.normalize({version:1,id:'angle-quality',name:'角度公差判定',steps:[{id:'measure',operation:'plugin',params:{...params('lines-2d',{maximumAngle:45}),outputBindings:[{scope:'flow',name:'angleOK',field:'passed'}]}}]});
 const job=runtime.start({project});await runtime.jobs.get(job.id).promise;
 const done=runtime.poll(job.id);assert.equal(done.state,'completed',done.error);assert.equal(done.variables.flow.angleOK,false);
});
test('individual geometry table cells resolve all three variable scopes and upstream nested results',async t=>{
 const {dir,plugins}=fixture(t),runtime=new Runtime(dir,{},plugins);
 const project=graph.normalize({version:1,id:'cell-bindings',name:'逐单元格绑定',variables:{planeOffset:-10},steps:[
  {id:'g',operation:'variables',params:{scope:'global',name:'normalZ',mode:'set',value:2}},
  {id:'m',operation:'plugin',params:{...params('planes-3d'),outputBindings:[{scope:'module',name:'normalX',field:'angleDegrees'}]}},
  {id:'relation',operation:'plugin',variables:{normalX:0},params:params('planes-3d',{entities:[{a:{$ref:'module.normalX'},b:0,c:1,d:0},{a:{$ref:'results.m.angleDegrees'},b:0,c:{$ref:'global.normalZ'},d:{$ref:'flow.planeOffset'}}]})}
 ]});
 const job=runtime.start({project});await runtime.jobs.get(job.id).promise;const done=runtime.poll(job.id);assert.equal(done.state,'completed',done.error);
 assert.equal(done.results[2].output.result.items[0].value,5);
});
test('table cell editor switches between typed fixed values and reference controls',()=>{
 const vm=require('node:vm');
 class Element{constructor(tag,text){this.tag=tag;this.text=text;this.children=[];this.attributes={};}append(...items){this.children.push(...items);}replaceChildren(...items){this.children=items;}setAttribute(k,v){this.attributes[k]=v;}}
 const refs=[],context=vm.createContext({structuredClone,formEl:(tag,text)=>new Element(tag,text),formType:v=>v&&typeof v==='object'&&v.$ref?'reference':typeof v,
  referenceEditor:(v,change,label)=>{const node=new Element('reference');refs.push({v,change,label});return node;}});
 vm.runInContext(fs.readFileSync(path.join(__dirname,'../public/vision/plugin-ui.js'),'utf8'),context);
 const holder=new Element('div'),values=[{x:12}],field={label:'坐标',columns:[{key:'x',label:'X',type:'number',default:3}],maximumRows:2};let changes=0;
 const walk=node=>[node,...node.children.flatMap(walk)];
 context.renderRecordParameter(holder,field,values,()=>changes++);
 walk(holder).find(n=>n.text==='绑定变量或结果').onclick();assert.equal(values[0].x.$ref,'flow.');assert.equal(refs.length,1);
 refs[0].change({$ref:'results.fit.line.start.0'});assert.equal(values[0].x.$ref,'results.fit.line.start.0');
 walk(holder).find(n=>n.text==='使用固定值').onclick();assert.equal(values[0].x,3);assert.equal(changes,3);
 assert(walk(holder).some(n=>n.tag==='input'&&n.value===3));
});
test('caliper corner demo survives generated node IDs and measures real fitted edges',async t=>{
 const {dir,plugins}=fixture(t),runtime=new Runtime(dir,{},plugins);
 const {remapResultReferences}=require('../public/vision/data-presentation.js');
 const demo=require('../public/vision/samples/demos-relations.json').find(d=>d.id==='caliper-corner-relations');
 const ids=Object.fromEntries(demo.steps.map((s,i)=>[s.id,'generated'+i]));
 const steps=demo.steps.map(s=>({...s,id:ids[s.id],params:remapResultReferences(s.params,ids)}));
 assert.equal(demo.steps[2].params.arguments.entities[0].x1.$ref,'results.vertical.line.start.0');
 const image='data:image/png;base64,'+fs.readFileSync(path.join(__dirname,'../public/vision/samples',demo.image)).toString('base64');
 const project=graph.normalize({version:1,id:demo.id,name:demo.name,steps});const job=runtime.start({project,image});await runtime.jobs.get(job.id).promise;const done=runtime.poll(job.id);
 assert.equal(done.state,'completed',done.error);assert.equal(done.variables.flow.cornerOK,true);
 const out=done.results[2].output.result;assert(Math.abs(out.angleDegrees-90)<.01);
 assert(Math.abs(out.items[0].value-159.5)<.1);assert(Math.abs(out.items[1].value-119.5)<.1);
});
test('complete inspection chain gates poor images and missing edges before geometric references are read',async t=>{
 const {dir,plugins}=fixture(t),runtime=new Runtime(dir,{},plugins);
 const {remapResultReferences}=require('../public/vision/data-presentation.js');
 for(const demo of require('../public/vision/samples/demos-inspection-chain.json')){
  const ids=Object.fromEntries(demo.steps.map((s,i)=>[s.id,'node'+i]));
  const steps=demo.steps.map(s=>({...s,id:ids[s.id],params:remapResultReferences(s.params,ids)}));
  const edges=demo.connections.map(([from,to,when],i)=>({id:'edge'+i,from:from<0?'source':steps[from].id,to:steps[to].id,...(when?{when}:{})}));
  const hmi=structuredClone(demo.hmi);for(const b of demo.hmiBindings)hmi.components[b.component].binding.nodeId=steps[b.step].id;
  const project=graph.normalize({version:2,id:demo.id,name:demo.name,variables:demo.variables,variableTypes:demo.variableTypes,steps,edges,hmi});
  const image='data:image/png;base64,'+fs.readFileSync(path.join(__dirname,'../public/vision/samples',demo.image)).toString('base64');
  const job=runtime.start({project,image});await runtime.jobs.get(job.id).promise;const done=runtime.poll(job.id);assert.equal(done.state,'completed',done.error);
  const pass=demo.id.endsWith('pass'),dark=demo.id.endsWith('dark')||demo.id.endsWith('blur'),horizontalMissing=demo.id.endsWith('horizontal-missing');
  assert.equal(done.variables.flow.inspectionRoute,pass?'检测完成':dark?'采图不合格':horizontalMissing?'未找到第二条边缘':'未找到第一条边缘');
  assert.equal(done.variables.flow.cornerOK,pass);assert.equal(!!done.results.find(r=>r.id===ids.corner)?.skipped,!pass);
  if(dark)assert.equal(done.results.find(r=>r.id===ids.vertical).skipped,true);
  if(!pass&&!horizontalMissing)assert.equal(done.results.find(r=>r.id===ids.horizontal).skipped,true);
  const layout=require('../public/vision/hmi-layout.js'),state=runtime.view(project);
  assert.equal(layout.read(hmi.components.find(c=>c.id==='corner').binding,state),pass);
  assert(Array.isArray(layout.read(hmi.components.find(c=>c.id==='qualityDetails').binding,state)));
  if(pass){
   assert.equal(layout.read(hmi.components.find(c=>c.id==='geometryDetails').binding,state).length,3);
   const darkImage='data:image/png;base64,'+fs.readFileSync(path.join(__dirname,'../public/vision/samples/caliper-corner-dark.png')).toString('base64');
   const next=runtime.start({project,image:darkImage});await runtime.jobs.get(next.id).promise;const rejected=runtime.poll(next.id);assert.equal(rejected.state,'completed',rejected.error);assert.equal(rejected.variables.flow.cornerOK,false);
   assert.equal(layout.read(hmi.components.find(c=>c.id==='geometryDetails').binding,runtime.view(project)),undefined);
  }
 }
});
