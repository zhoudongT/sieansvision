const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),os=require('node:os'),path=require('node:path'),crypto=require('node:crypto');
const {RunHistory,archiveRecord}=require('../lib/run-history.cjs'),{Runtime}=require('../lib/runtime.cjs'),{ContinuousRun}=require('../lib/continuous-run.cjs'),graph=require('../public/vision/flow-graph.js');
const directory=()=>fs.mkdtempSync(path.join(os.tmpdir(),'sieans-history-'));
const project=(extra={})=>graph.normalize({version:1,id:'history',name:'历史验证',steps:[{id:'set',operation:'variables',params:{name:'count',value:1,mode:'increment'}}],...extra});
const record=(time=1,extra={})=>({version:1,id:crypto.randomUUID(),project:project(),plannedStepIds:['set'],state:'completed',origin:'manual',startedAt:time,endedAt:time+5,framesSaved:false,variablesCommitted:true,variables:{revision:1,global:{},globalTypes:{},flow:{count:1},modules:{set:{}}},results:[{id:'set',output:{result:{passed:false,count:1},elapsedMs:1}}],...extra});
async function run(runtime,p,request={}){const accepted=runtime.start({project:p,...request});await runtime.jobs.get(accepted.id).promise;return runtime.poll(accepted.id);}

test('archive persists exact project/result/log/variable snapshots and restores after restart',async()=>{
 const folder=directory(),history=new RunHistory(folder),item=record();item.results[0].output.logs='检测完成';const meta=await history.store(item);
 item.project.name='edited';item.results[0].output.result.count=99;
 const restored=new RunHistory(folder),saved=await restored.get(meta.id);assert.equal(saved.project.name,'历史验证');assert.equal(saved.results[0].output.result.count,1);assert.equal(saved.results[0].output.logs,'检测完成');assert.equal(saved.variables.flow.count,1);
 const list=restored.list();assert.equal(list.total,1);assert.equal(list.items[0].inspectionFailures,1);assert.equal(list.items[0].state,'completed');assert.equal(list.items[0].finishedSteps,1);assert.equal(list.items[0].elapsedMs,5);
 list.items[0].projectName='mutated';assert.equal(restored.list().items[0].projectName,'历史验证');await assert.rejects(restored.store(saved),/不可覆盖/);
});

test('frame retention is explicit and never strips result fields, logs or reference parameters',()=>{
 const job=record();job.results[0].output={result:{passed:true,cloudCount:1},logs:'note',image:'processing-image',maskImage:'binary-mask',annotatedImage:'image',cloud:{points:[[1,2,3]],unit:'mm'},depth:{width:1}};
 const p=project();p.steps[0].reference='reference-image';const source={image:'source',cloud:null,depth:null};
 const lean=archiveRecord(job,p,p.steps,source,job.variables);assert.equal(lean.input,undefined);assert.equal(lean.results[0].output.maskImage,undefined);assert.equal(lean.results[0].output.image,undefined);assert.equal(lean.results[0].output.annotatedImage,undefined);assert.equal(lean.results[0].output.cloud,undefined);assert.equal(lean.results[0].output.depth,undefined);assert.equal(lean.results[0].output.logs,'note');assert.equal(lean.project.steps[0].reference,'reference-image');assert.equal(job.results[0].output.annotatedImage,'image');
 p.history={includeFrames:true};const full=archiveRecord(job,p,p.steps,source,job.variables);assert.equal(full.input.image,'source');assert.equal(full.results[0].output.maskImage,'binary-mask');assert.equal(full.results[0].output.cloud.unit,'mm');assert.equal(full.results[0].output.depth.width,1);assert(full.framesSaved);
 for(const history of [{includeFrames:1},{includeFrames:false,unknown:true},[],null])assert.throws(()=>graph.normalize({...p,history}),/保留设置/);
 assert.deepEqual(graph.normalize(p).history,{includeFrames:true});
});

test('success, failure and cancellation archive committed values rather than rolled-back working copies',async()=>{
 const folder=directory(),runtime=new Runtime(folder,{}),p=project();const good=await run(runtime,p);assert.equal(good.archive.state,'saved');assert.equal((await runtime.history.get(good.id)).variables.flow.count,1);
 const bad=project({steps:[...p.steps,{id:'bad',operation:'variables',params:{name:'x',value:{$ref:'flow.missing'}}}]});const failed=await run(runtime,bad);assert.equal(failed.state,'failed');const archived=await runtime.history.get(failed.id);assert.equal(archived.variablesCommitted,false);assert.equal(archived.variables.flow.count,1);assert.equal(archived.results[0].output.result.value,2);assert.match(archived.results[1].error,/不存在/);
 const slow=project({steps:[...p.steps,{id:'delay',operation:'delay',params:{milliseconds:30000}}]});const start=runtime.start({project:slow});runtime.cancel(start.id);await runtime.jobs.get(start.id).promise;
 const cancelled=await runtime.history.get(start.id);assert.equal(cancelled.state,'cancelled');assert.equal(cancelled.variablesCommitted,false);assert.equal(cancelled.variables.flow.count,1);assert.equal(runtime.busy,false);
 assert.equal(new Runtime(folder,{}).history.list().total,3);
});

test('history remains available after live job cache eviction and preserves selected execution scope',async()=>{
 const runtime=new Runtime(directory(),{}),p=project({steps:[{id:'a',operation:'variables',params:{name:'count',value:1}},{id:'b',operation:'variables',params:{name:'count',value:2}}]});
 const first=await run(runtime,p,{target:'a'});for(let i=0;i<4;i++)await run(runtime,p);assert.throws(()=>runtime.poll(first.id),/已过期/);const old=await runtime.history.get(first.id);assert.deepEqual(old.plannedStepIds,['a']);assert.equal(old.project.steps.length,2);assert.equal(old.results.length,1);assert.equal(runtime.history.list().total,5);
});

test('retention prunes oldest records by count and detail bytes, including concurrent stores',async()=>{
 const folder=directory(),history=new RunHistory(folder,{maxRecords:2});const items=[record(3),record(1),record(2)];await Promise.all(items.map(i=>history.store(i)));
 assert.deepEqual(history.list().items.map(i=>i.startedAt),[3,2]);assert.equal(fs.existsSync(history.file(items[1].id,'data')),false);assert.equal(new RunHistory(folder).list().total,2);
 const one=record(1),bytes=Buffer.byteLength(JSON.stringify(one));const small=new RunHistory(directory(),{maxBytes:bytes+50});await small.store(one);const next=record(2);await small.store(next);assert.equal(small.list().total,1);assert.equal(small.list().items[0].id,next.id);assert(small.list().storedBytes<=bytes+50);
 await assert.rejects(new RunHistory(directory(),{maxRecordBytes:100}).store(record()),/上限/);await assert.rejects(new RunHistory(directory(),{maxBytes:100}).store(record()),/容量/);
});

test('filters use project/state/start time, pagination is stable and malformed queries are rejected',async()=>{
 const history=new RunHistory(directory());for(let i=1;i<=5;i++)await history.store(record(i,{state:i%2?'completed':'failed',project:project({id:i===5?'other':'history'})}));
 assert.deepEqual(history.list({projectId:'history',state:'completed',after:2,before:4}).items.map(i=>i.startedAt),[3]);assert.deepEqual(history.list({offset:1,limit:2}).items.map(i=>i.startedAt),[4,3]);assert.equal(history.list({offset:20}).items.length,0);
 for(const query of [{offset:-1},{offset:1.2},{limit:101},{limit:0},{state:'running'},{after:'oops'},{after:'Infinity'},{after:5,before:2},{projectId:[]}])assert.throws(()=>history.list(query));
});

test('restart reapplies retention after interrupted cleanup and continuous rounds retain independent snapshots',async()=>{
 const folder=directory(),runtime=new Runtime(folder,{}),runner=new ContinuousRun(runtime,folder),p=project();runner.start({project:p,intervalMs:100,maxCycles:3});await runner.promise;
 const records=runtime.history.list().items;assert.equal(records.length,3);assert(records.every(r=>r.origin==='continuous'));
 const values=[];for(const row of records)values.push((await runtime.history.get(row.id)).variables.flow.count);assert.deepEqual(values,[3,2,1]);
 const reloaded=new RunHistory(folder,{maxRecords:1});assert.equal(reloaded.list().total,1);assert.equal(reloaded.list().items[0].id,records[0].id);await assert.rejects(reloaded.get(records[2].id),/不存在/);
});

test('incomplete summary writes recover from details, corrupt files remain visible as diagnostics',async()=>{
 const folder=directory(),history=new RunHistory(folder),item=record();await history.store(item);fs.unlinkSync(history.file(item.id,'meta'));
 const recovered=new RunHistory(folder);assert.equal(recovered.list().total,1);assert.deepEqual(await recovered.get(item.id),item);
 const corrupt=crypto.randomUUID();fs.writeFileSync(history.file(corrupt,'data'),'incomplete');const again=new RunHistory(folder);assert.equal(again.list().total,1);assert(again.list().warnings.some(w=>w.includes('无法恢复')));assert(fs.existsSync(history.file(corrupt,'data')));
});

test('tampered details and path traversal fail instead of returning unverified records',async()=>{
 const history=new RunHistory(directory()),item=record();await history.store(item);const file=history.file(item.id,'data'),text=fs.readFileSync(file,'utf8');fs.writeFileSync(file,text.replace('历史验证','损坏记录'));
 await assert.rejects(history.get(item.id),e=>e.status===409&&/校验/.test(e.message));
 for(const id of ['../outside','x',item.id+'/../x'])await assert.rejects(history.get(id),e=>e.status===400);
 await assert.rejects(history.get(crypto.randomUUID()),e=>e.status===404);
});

test('runtime stays busy while archiving and both poll/view notify archive completion',async()=>{
 const runtime=new Runtime(directory(),{}),p=project();let release;runtime.history.store=()=>new Promise(resolve=>release=resolve);
 const start=runtime.start({project:p});assert.equal(start.state,'running');await new Promise(resolve=>setImmediate(resolve));assert.equal(runtime.poll(start.id).archive.state,'writing');const writing=runtime.view(p);assert.equal(writing.status.state,'running');assert.equal(writing.status.archive.state,'writing');assert(runtime.busy);assert.throws(()=>runtime.start({project:p}),/其他任务/);
 release();await runtime.jobs.get(start.id).promise;assert.equal(runtime.poll(start.id).state,'completed');const done=runtime.view(p,writing.version);assert.equal(done.status.archive.state,'saved');assert.notEqual(done.version,writing.version);assert(done.results);assert.equal(runtime.busy,false);
});

test('archive I/O failure is explicit, preserves committed variables and stops continuous repeats',async()=>{
 const folder=directory(),runtime=new Runtime(folder,{}),p=project();fs.writeFileSync(path.join(folder,'run-history'),'not-a-directory');const job=await run(runtime,p);
 assert.equal(job.state,'completed');assert.equal(job.archive.state,'failed');assert.match(job.archive.error,/归档失败/);assert.equal(runtime.snapshot(p).flow.count,1);assert.equal(runtime.view(p).status.archive.state,'failed');assert.equal(runtime.busy,false);
 const runner=new ContinuousRun(runtime,folder);runner.start({project:p,intervalMs:100,maxCycles:5});await runner.promise;assert.equal(runner.state.state,'failed');assert.equal(runner.state.completedCycles,1);assert.equal(runner.state.startedCycles,1);assert.match(runner.state.error,/归档失败/);assert.equal(runtime.snapshot(p).flow.count,2);assert.equal(runtime.busy,false);
});
