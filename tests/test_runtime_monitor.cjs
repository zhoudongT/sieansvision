'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),os=require('node:os');
const {RuntimeMonitor}=require('../lib/runtime-monitor.cjs'),{Runtime}=require('../lib/runtime.cjs'),layout=require('../public/vision/hmi-layout.js'),chart=require('../public/vision/monitor-chart.js');
const folder=()=>fs.mkdtempSync(path.join(os.tmpdir(),'sieans-monitor-'));
const base=(id,type,extra={})=>({id,type,label:id,x:0,y:0,w:6,h:4,color:'#1095bd',fontSize:16,binding:{source:'flow',path:'temperature'},...extra});
const alarm=(extra={})=>base('alarm','alarm',{comparison:'gte',threshold:10,hysteresis:2,stableSamples:2,severity:'warning',...extra});
const trend=(extra={})=>base('trend','trend',{capacity:20,precision:2,unit:'°C',...extra});
const project=(components=[alarm(),trend()],extra={})=>({version:1,id:'monitor-test',name:'Monitor',steps:[],hmi:layout.normalize({...layout.empty(),components}),...extra});
const state=(value,status='completed',extra={})=>({variables:{flow:{temperature:value},global:{},modules:{}},results:[],status:{state:status},...extra});
async function run(runtime,p){const start=runtime.start({project:p});await runtime.jobs.get(start.id).promise;return runtime.poll(start.id);}

test('alarm/trend contracts reject invalid types, bounds and unused hysteresis',()=>{
 for(const patch of [{capacity:19},{capacity:1001},{precision:7},{binding:{source:'source',path:''}}])assert.throws(()=>project([trend(patch)]));
 for(const patch of [{stableSamples:0},{stableSamples:101},{hysteresis:-1},{comparison:'exec'},{severity:'fatal'},{threshold:'10'},{comparison:'eq',hysteresis:1},{threshold:Infinity}])assert.throws(()=>project([alarm(patch)]));
 assert.equal(project([alarm({comparison:'is_false',hysteresis:0})]).hmi.components[0].threshold,undefined);
});
test('confirmed high alarm latches across hysteresis; acknowledgment never clears active condition',()=>{
 const m=new RuntimeMonitor(folder()),p=project();for(const v of [9,11,11])m.observe(p,state(v));let view=m.view(p.id);assert.equal(view.events.length,1);assert.equal(view.widgets.alarm.active,true);const id=view.events[0].id;
 const revision=view.revision;m.acknowledge(p.id,id,'已检查');view=m.view(p.id);assert.equal(view.widgets.alarm.active,true);assert.equal(view.events[0].returnedAt,null);assert.equal(view.events[0].comment,'已检查');assert.equal(view.revision,revision+1);
 m.acknowledge(p.id,id);assert.equal(m.view(p.id).revision,view.revision);for(const v of [9,8,7,7])m.observe(p,state(v));view=m.view(p.id);assert.equal(view.widgets.alarm.active,false);assert.ok(view.events[0].returnedAt);assert.ok(view.events[0].acknowledgedAt);assert.equal(view.events.length,1);
});
test('unknown/failed samples reset pending confirmation and never silently clear an active alarm',()=>{
 const m=new RuntimeMonitor(folder()),p=project([alarm()]);m.observe(p,state(12));m.observe(p,state(undefined));m.observe(p,state(12));assert.equal(m.view(p.id).events.length,0);m.observe(p,state(12));assert.equal(m.view(p.id).events.length,1);
 m.observe(p,state(0,'failed'));const view=m.view(p.id);assert.equal(view.widgets.alarm.active,true);assert.equal(view.widgets.alarm.quality,'invalid');assert.match(view.widgets.alarm.reason,/未成功/);
});
test('low alarms, boolean alarms and typed status comparisons retain their own lifecycle',()=>{
 const m=new RuntimeMonitor(folder()),p=project([alarm({comparison:'lt',threshold:0,hysteresis:1,stableSamples:1}),alarm({id:'boolean',comparison:'is_true',hysteresis:0,stableSamples:1,binding:{source:'flow',path:'flag'}}),alarm({id:'failed',comparison:'eq',threshold:'failed',hysteresis:0,stableSamples:1,binding:{source:'status',path:'state'}})]);
 m.observe(p,state(-1,'completed',{variables:{flow:{temperature:-1,flag:true}}}));assert.equal(m.view(p.id).events.length,2);m.observe(p,state(.5));assert.equal(m.view(p.id).widgets.alarm.active,true);m.observe(p,state(1,'failed'));assert.equal(m.view(p.id).widgets.failed.active,true);assert.equal(m.view(p.id).widgets.alarm.active,true);
 m.observe(p,state(1));assert.equal(m.view(p.id).widgets.alarm.active,false);
});
test('trend gaps preserve invalid data; client reads and restart do not add samples',()=>{
 const dir=folder(),m=new RuntimeMonitor(dir),p=project([trend()]);for(const value of [0,2,undefined,'3',Infinity])m.observe(p,state(value));m.observe(p,state(5,'failed'));let view=m.view(p.id);assert.deepEqual(view.widgets.trend.samples.map(s=>s.value),[0,2,null,null,null,null]);const count=view.widgets.trend.samples.length;
 m.view(p.id);assert.equal(new RuntimeMonitor(dir).view(p.id).widgets.trend.samples.length,count);
});
test('configuration changes retire the previous alarm; removed widgets retain event history',()=>{
 const m=new RuntimeMonitor(folder()),p=project([alarm({stableSamples:1})]);m.observe(p,state(12));p.hmi.components[0].threshold=20;m.observe(p,state(12));let view=m.view(p.id);assert.equal(view.widgets.alarm.active,false);assert.match(view.events[0].endReason,/配置/);assert.ok(view.events[0].returnedAt);
 p.hmi.components=[];m.observe(p,state(0));view=m.view(p.id);assert.deepEqual(view.widgets,{});assert.equal(view.events.length,1);
});
test('retention bounds trend points and events while exposing discard counts',()=>{
 const m=new RuntimeMonitor(folder());m.persist=next=>{m.state=next;};const p=project([alarm({comparison:'is_true',hysteresis:0,stableSamples:1}),trend()]);for(let i=0;i<410;i++)m.observe(p,state(i%2===0));let view=m.view(p.id);assert.equal(view.events.length,200);assert.equal(view.discardedEvents,5);assert.equal(view.widgets.trend.samples.length,20);assert.equal(view.discardedSamples,390);
 const many=project(Array.from({length:10},(_,i)=>trend({id:'t'+i,capacity:1000})));for(let i=0;i<510;i++)m.observe(many,state(i));view=m.view(p.id);assert.equal(Object.values(view.widgets).reduce((n,w)=>n+w.samples.length,0),5000);assert.ok(view.discardedSamples>=100);
 for(let i=0;i<25;i++)m.observe(project([trend()],{id:'p'+i}),state(i),{time:i+1000});assert.equal(Object.keys(m.state.projects).length,20);
});
test('runtime collects only committed variables and reports monitor I/O failure separately',async()=>{
 const r=new Runtime(folder(),{}),p=project([alarm({stableSamples:1}),trend()],{steps:[{id:'set',operation:'variables',params:{name:'temperature',value:12}}]});let job=await run(r,p);assert.equal(job.state,'completed');assert.equal(job.monitor.widgets.alarm.active,true);
 p.steps.push({id:'bad',operation:'delay',params:{milliseconds:-1}});job=await run(r,p);assert.equal(job.state,'failed');assert.equal(job.monitor.widgets.alarm.active,true);assert.equal(job.monitor.widgets.trend.samples.at(-1).quality,'invalid');
 p.steps.pop();p.steps[0].params.value=15;const persist=r.monitor.persist.bind(r.monitor),revision=r.monitor.state.revision;r.monitor.persist=()=>{throw Error('disk full');};job=await run(r,p);assert.equal(job.state,'completed');assert.equal(job.variables.flow.temperature,15);assert.match(job.monitor.error,/disk full/);assert.equal(r.monitor.state.revision,revision);assert.match((await r.history.get(job.id)).monitorWarning,/disk full/);r.monitor.persist=persist;await run(r,p);assert.equal(r.view(p).monitor.error,'');
});
test('global changes update registered projects without resampling unrelated flow bindings',async()=>{
 const r=new Runtime(folder(),{}),a=project([trend({binding:{source:'global',path:'temperature'}})],{id:'a'}),b=project([alarm({stableSamples:1,binding:{source:'global',path:'temperature'}}),trend()],{id:'b',variables:{temperature:3}});
 await run(r,b);const before=r.monitor.view('b').widgets.trend.samples.length;const initial=r.snapshot(a);let writes=0;const persist=r.monitor.persist.bind(r.monitor);r.monitor.persist=next=>{writes++;persist(next);};initial.global.temperature=12;r.update(a,initial,initial.revision);assert.equal(writes,1);const view=r.monitor.view('b');assert.equal(view.widgets.alarm.active,true);assert.equal(view.widgets.trend.samples.length,before);
});
test('result bindings do not reuse previous outputs on failure, skip or manual variable edits',async()=>{
 const r=new Runtime(folder(),{}),p=project([trend({binding:{source:'result',nodeId:'set',path:'value'}})],{steps:[{id:'set',operation:'variables',params:{name:'temperature',value:4}}]});await run(r,p);const before=r.monitor.view(p.id).widgets.trend.samples.length,snapshot=r.snapshot(p);snapshot.flow.temperature=7;r.update(p,snapshot,snapshot.revision);assert.equal(r.monitor.view(p.id).widgets.trend.samples.length,before);
 p.steps[0].params.value={$ref:'flow.missing'};await run(r,p);assert.equal(r.monitor.view(p.id).widgets.trend.samples.at(-1).value,null);
});
test('chart keeps gaps and isolated points and handles flat/extreme finite numeric ranges',()=>{
 const samples=[{time:1,value:2,quality:'good'},{time:2,value:null,quality:'invalid'},{time:3,value:3,quality:'good'}];let plot=chart.plot(samples);assert.equal(plot.paths.length,2);assert.equal(plot.dots.length,2);
 for(const values of [[0,0],[Number.MAX_VALUE,-Number.MAX_VALUE],[1e308,1e308]]){plot=chart.plot(values.map((value,time)=>({value,time,quality:'good'})));assert.ok(plot.paths.every(p=>! /NaN|Infinity/.test(p)));assert.ok(Number.isFinite(plot.low)&&Number.isFinite(plot.high)&&Number.isFinite(plot.middle));}
 assert.deepEqual(chart.plot([{time:1,value:null,quality:'invalid'}]).paths,[]);
});
test('acknowledgments are project-scoped and restart preserves confirmation and recovery',()=>{
 const dir=folder(),m=new RuntimeMonitor(dir),p=project([alarm({stableSamples:1})]);m.observe(p,state(12));const event=m.view(p.id).events[0];assert.throws(()=>m.acknowledge('other',event.id),/不存在/);assert.throws(()=>m.acknowledge(p.id,'../bad'),/参数/);m.acknowledge(p.id,event.id);m.observe(p,state(0));const restored=new RuntimeMonitor(dir).view(p.id).events[0];assert.ok(restored.acknowledgedAt);assert.ok(restored.returnedAt);
});

test('cancelled jobs produce trend gaps and status alarms without committing variables',async()=>{
 const r=new Runtime(folder(),{}),p=project([trend(),alarm({comparison:'eq',threshold:'cancelled',hysteresis:0,stableSamples:1,binding:{source:'status',path:'state'}})],{variables:{temperature:0},steps:[{id:'set',operation:'variables',params:{name:'temperature',value:12}},{id:'wait',operation:'delay',params:{milliseconds:30000}}]});
 const job=r.start({project:p});r.cancel(job.id);await r.jobs.get(job.id).promise;const status=r.poll(job.id);assert.equal(status.state,'cancelled');assert.equal(r.snapshot(p).flow.temperature,0);assert.equal(status.monitor.widgets.trend.samples[0].quality,'invalid');assert.equal(status.monitor.widgets.alarm.active,true);
});
test('monitor storage failure stops later continuous cycles while retaining completed variables and history warning',async()=>{
 const {ContinuousRun}=require('../lib/continuous-run.cjs'),r=new Runtime(folder(),{}),runner=new ContinuousRun(r,path.dirname(r.variables.file)),p=project([trend()],{steps:[{id:'set',operation:'variables',params:{name:'temperature',value:12}}]});
 r.monitor.persist=()=>{throw Error('disk full');};runner.start({project:p,intervalMs:100,maxCycles:3});await runner.promise;assert.equal(runner.status().state,'failed');assert.equal(runner.status().completedCycles,1);assert.match(runner.status().error,/disk full/);assert.equal(r.snapshot(p).flow.temperature,12);assert.equal(r.busy,false);
 const records=r.history.list();assert.equal(records.total,1);const job=[...r.jobs.values()][0];assert.match((await r.history.get(job.id)).monitorWarning,/disk full/);
});
test('project retention never evicts active alarms to admit another monitoring project',()=>{
 const m=new RuntimeMonitor(folder());m.persist=next=>{m.state=next;};for(let i=0;i<20;i++)m.observe(project([alarm({stableSamples:1})],{id:'active'+i}),state(12),{time:i+1});
 assert.throws(()=>m.observe(project([alarm({stableSamples:1})],{id:'overflow'}),state(12)),/活动报警/);assert.equal(Object.keys(m.state.projects).length,20);assert.equal(m.view('active0').widgets.alarm.active,true);assert.equal(m.view('overflow').events.length,0);
});
