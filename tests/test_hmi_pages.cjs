'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),os=require('node:os'),path=require('node:path');
const hmi=require('../public/vision/hmi-layout.js'),graph=require('../public/vision/flow-graph.js'),{Runtime}=require('../lib/runtime.cjs');
const text=(id)=>({id,type:'text',label:id,x:0,y:0,w:3,h:1,color:'#1095bd',fontSize:18});
const navigate=(id,targetPageId)=>({...text(id),type:'button',action:'navigate',targetPageId});
const page=(id,components=[])=>({id,...hmi.empty(),title:id,components});
const document=(pages,extra={})=>({version:2,title:'多页监控',defaultPageId:pages[0]?.id,pages,...extra});
const project=layout=>graph.normalize({version:1,id:'page-project',name:'Pages',variables:{temperature:0},steps:[{id:'set',operation:'variables',params:{name:'temperature',mode:'increment',value:2}}],hmi:layout});
const monitor=(id,type)=>({...text(id),type,h:4,binding:{source:'flow',path:'temperature'},...(type==='trend'?{capacity:20,precision:1,unit:'°C'}:{comparison:'gte',threshold:2,hysteresis:0,stableSamples:1,severity:'warning'})});
async function run(r,p){const start=r.start({project:p});await r.jobs.get(start.id).promise;return r.poll(start.id);}

test('legacy single pages normalize unchanged and convert without mutating existing component IDs',()=>{
 const legacy={...hmi.empty(),components:[text('title')]},before=JSON.stringify(legacy);assert.deepEqual(hmi.normalize(legacy),legacy);const converted=hmi.document(legacy);assert.equal(converted.version,2);assert.equal(converted.defaultPageId,'main');assert.equal(converted.pages[0].components[0].id,'title');assert.equal(JSON.stringify(legacy),before);assert.deepEqual(hmi.allComponents(converted),legacy.components);
});
test('multi-page schemas round-trip through project normalization and preserve ordered navigation targets',()=>{
 const layout=document([page('overview',[navigate('to-settings','settings')]),page('settings',[navigate('back','overview')])]),normalized=hmi.normalize(layout);assert.deepEqual(project(normalized).hmi,normalized);assert.deepEqual(hmi.normalize(normalized),normalized);assert.equal(hmi.pages(normalized)[1].id,'settings');
});
test('duplicate page/component IDs, missing default/targets and unsafe page IDs fail before save',()=>{
 const layouts=[document([]),document([page('a'),page('a')]),document([page('__proto__')]),document([page('a')],{defaultPageId:'missing'}),document([page('a',[text('same')]),page('b',[text('same')])]),document([page('a',[navigate('bad','missing')])])];for(const layout of layouts)assert.throws(()=>hmi.normalize(layout));assert.throws(()=>hmi.normalize({...hmi.empty(),components:[navigate('bad','other')]}),/目标不存在/);
});
test('page, component and monitor totals are bounded independently',()=>{
 assert.throws(()=>hmi.normalize(document(Array.from({length:21},(_,i)=>page('p'+i)))),/20/);
 const many=Array.from({length:5},(_,p)=>page('p'+p,Array.from({length:41},(_,i)=>text('t'+p+'-'+i))));assert.throws(()=>hmi.normalize(document(many)),/200/);
 const alarms=[page('a',Array.from({length:26},(_,i)=>monitor('a'+i,'alarm'))),page('b',Array.from({length:25},(_,i)=>monitor('b'+i,'trend')))];assert.throws(()=>hmi.normalize(document(alarms)),/50/);
});
test('page copy assigns independent widget IDs and rewrites self-navigation only',()=>{
 const original=document([page('main',[navigate('self','main'),navigate('other','settings'),text('label')]),page('settings')]),before=JSON.stringify(original),copied=hmi.copyPage(original,'main','duplicate');assert.equal(copied.pages.length,3);const widgets=copied.pages[2].components;assert.equal(widgets[0].targetPageId,'duplicate');assert.equal(widgets[1].targetPageId,'settings');assert.notEqual(widgets[2].id,'label');assert.equal(JSON.stringify(original),before);widgets[2].label='changed';assert.equal(original.pages[0].components[2].label,'label');
});
test('page deletion protects remaining navigation and repairs the default page',()=>{
 const layout=document([page('main',[navigate('go','settings')]),page('settings')]);assert.throws(()=>hmi.removePage(layout,'settings'),/跳转/);const removed=hmi.removePage(layout,'main');assert.equal(removed.defaultPageId,'settings');assert.equal(removed.pages.length,1);assert.throws(()=>hmi.removePage(removed,'settings'),/至少/);
});
test('all pages are sampled on the server and page movement/renaming does not recreate alarm events',async()=>{
 const layout=document([page('overview',[text('title')]),page('hidden',[monitor('alarm','alarm'),monitor('trend','trend')])]),p=project(layout),r=new Runtime(fs.mkdtempSync(path.join(os.tmpdir(),'sieans-pages-')),{});let job=await run(r,p);assert.equal(job.state,'completed',job.error);assert.equal(job.monitor.widgets.alarm.active,true);assert.equal(job.monitor.widgets.trend.samples.length,1);const eventId=job.monitor.events[0].id;
 p.hmi.pages[0].title='生产总览';const alarm=p.hmi.pages[1].components.shift();p.hmi.pages[0].components.push(alarm);job=await run(r,p);assert.equal(job.monitor.events[0].id,eventId);assert.equal(job.monitor.events.length,1);assert.equal(job.monitor.widgets.trend.samples.length,2);assert.equal(job.variables.flow.temperature,4);
 const revision=r.monitor.state.revision;r.view(p);r.view(p);assert.equal(r.monitor.state.revision,revision);assert.equal(p.hmi.defaultPageId,'overview');
});
test('single-page monitor state survives conversion to a multi-page document',async()=>{
 const p=project({...hmi.empty(),components:[monitor('alarm','alarm')]}),r=new Runtime(fs.mkdtempSync(path.join(os.tmpdir(),'sieans-page-migrate-')),{});const first=await run(r,p);p.hmi=hmi.document(p.hmi);p.hmi.pages.push(page('extra'));const second=await run(r,p);assert.equal(second.monitor.events[0].id,first.monitor.events[0].id);assert.equal(second.monitor.events.length,1);
});
test('page badges include active or unacknowledged alarms without double counting or unrelated events',()=>{
 const p=page('alarms',[monitor('alarm','alarm')]),events=[{componentId:'alarm',returnedAt:null,acknowledgedAt:null},{componentId:'alarm',returnedAt:3,acknowledgedAt:null},{componentId:'alarm',returnedAt:3,acknowledgedAt:4},{componentId:'other',returnedAt:null}];assert.equal(hmi.alarmCount(p,{events}),2);assert.equal(hmi.alarmCount(page('empty'),{events}),0);
});
