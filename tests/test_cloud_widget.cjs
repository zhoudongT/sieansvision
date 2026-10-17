'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),os=require('node:os');
const viewer=require('../public/vision/cloud-viewer.js'),hmi=require('../public/vision/hmi-layout.js'),{Runtime}=require('../lib/runtime.cjs'),{OperatorRuntime}=require('../lib/operator-runtime.cjs');
function component(extra={}){return {id:'cloud',type:'cloud',label:'点云',x:0,y:0,w:12,h:6,color:'#1095bd',fontSize:20,maxPoints:100,pointSize:2,initialView:'iso',binding:{source:'result',nodeId:'code',path:''},...extra};}
test('cloud preview is bounded, detached, color-aligned and preserves full bounds',()=>{
 const cloud={unit:'mm',frame:'fixture',points:Array.from({length:1001},(_,i)=>[i,i%11,0]),colors:Array.from({length:1001},(_,i)=>[i%2,0,1]),secret:'not exported'};const before=structuredClone(cloud),p=viewer.preview(cloud,100);
 assert(p.points.length<=100);assert.equal(p.sourcePointCount,1001);assert.deepEqual(p.bounds,[[0,0,0],[1000,10,0]]);assert.equal(p.secret,undefined);for(let i=0;i<p.points.length;i++)assert.deepEqual(p.colors[i],cloud.colors[p.points[i][0]]);p.points[0][0]=99;assert.deepEqual(cloud,before);
 for(const patch of [{unit:'px'},{points:[[NaN,0,0]]},{colors:[[1,0,0]]},{colors:Array(1001).fill([255,0,0])}])assert.throws(()=>viewer.preview({...cloud,...patch},100));
 assert.throws(()=>viewer.preview(cloud,99));assert.throws(()=>viewer.preview(cloud,30001));
 const narrowed=viewer.preview({...cloud,bounds:[[0,0,0],[1,1,0]]},100);assert.equal(narrowed.bounds[1][0],1000);
});
test('orthographic axes, positive-Z top occlusion, aspect fit and degenerate clouds remain finite',()=>{
 const cloud=viewer.preview({unit:'mm',points:[[-10,-5,0],[10,5,2],[0,0,0],[0,0,2]]},100);const camera={...viewer.orientation('top'),zoom:1,pan:[0,0]},p=viewer.project(cloud,camera,400,200);
 assert(p.every(p=>Number.isFinite(p.x)&&Number.isFinite(p.y)&&p.x>=0&&p.x<=400&&p.y>=0&&p.y<=200));assert(p.findIndex(p=>p.index===2)<p.findIndex(p=>p.index===3),'higher Z must draw after lower Z in top view');
 const center=p.find(p=>p.index===2);assert(Math.abs(center.x-200)<1e-9);assert(Math.abs(center.y-100)<1e-9);const shifted=viewer.project(cloud,{...camera,pan:[30,-10]},400,200).find(p=>p.index===2);assert.equal(shifted.x,230);assert(Math.abs(shifted.y-90)<1e-9);
 assert.deepEqual(viewer.project(cloud,camera,0,200),[]);assert(viewer.project(viewer.preview({unit:'m',points:[[0,0,0]]},100),camera,100,100).every(p=>Number.isFinite(p.x)&&Number.isFinite(p.y)));
});
test('cloud HMI contracts reject variable data paths and malformed display settings',()=>{
 const layout={...hmi.empty(),components:[component()]};assert.equal(hmi.normalize(layout).components[0].type,'cloud');
 for(const patch of [{maxPoints:30001},{maxPoints:3.5},{pointSize:0},{initialView:'perspective'},{binding:{source:'flow',path:'cloud'}},{binding:{source:'result',nodeId:'code',path:'secret'}}])assert.throws(()=>hmi.normalize({...layout,components:[component(patch)]}));
});
test('operator exposes only the bound bounded cloud channel and keeps full calculation payload',async()=>{
 const data=fs.mkdtempSync(path.join(os.tmpdir(),'sieans-cloud-widget-')),runtime=new Runtime(data,{}),operator=new OperatorRuntime(data,runtime,{busy:false},{busy:false});
 const project={version:1,id:'cloud-widget',name:'点云权限',hmi:{...hmi.empty(),components:[component()]},steps:[{id:'code',operation:'script',params:{code:'def run(ctx):\n    return dict(cloud=dict(unit="mm",frame="camera",points=[[i,i%7,0] for i in range(1001)],colors=[[1,0,0] for i in range(1001)],secret="metadata-secret"),result=dict(secret="result-secret"))\n'}},{id:'hidden',operation:'script',params:{code:'def run(ctx):\n    return dict(cloud=dict(unit="mm",points=[[9000,9000,9000]]),result=dict(secret="hidden-node"))\n'}}]};
 fs.writeFileSync(path.join(data,'vision-project.json'),JSON.stringify(project));operator.publish({draftHash:operator.summary().draft.draftHash,allowScripts:true},'admin');const j=operator.run({version:operator.load().version});await runtime.jobs.get(j.id).promise;assert.equal(runtime.poll(j.id).state,'completed',runtime.poll(j.id).error);
 const state=operator.publicState();assert.equal(state.results.length,1);const preview=state.results[0].output.cloud;assert(preview.points.length<=100);assert.equal(preview.sourcePointCount,1001);assert.equal(preview.secret,undefined);assert.deepEqual(state.results[0].output.result,{});assert.equal(runtime.poll(j.id).results[0].output.cloud.points.length,1001);assert(!JSON.stringify(state).includes('metadata-secret'));assert(!JSON.stringify(state).includes('result-secret'));assert(!JSON.stringify(state).includes('hidden-node'));
});
