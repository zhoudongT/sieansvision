'use strict';
// Always starts an isolated local server with an empty Node-RED flow and simulators.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),os=require('node:os'),net=require('node:net');
const {fork}=require('node:child_process'),{once}=require('node:events');
const root=path.resolve(__dirname,'..'),delay=ms=>new Promise(r=>setTimeout(r,ms));
function options(args){const o={cycles:220,warmup:20,maxRssGrowthMiB:256,report:path.resolve('artifacts','runtime-soak-'+Date.now()+'.json')};for(let i=0;i<args.length;i+=2){const key={'--cycles':'cycles','--warmup':'warmup','--max-rss-growth-mib':'maxRssGrowthMiB','--report':'report'}[args[i]];if(!key||args[i+1]===undefined)throw Error('参数：--cycles N --warmup N --max-rss-growth-mib N --report 新文件');o[key]=key==='report'?path.resolve(args[i+1]):Number(args[i+1]);}if(!Number.isInteger(o.cycles)||o.cycles<5||o.cycles>10000||!Number.isInteger(o.warmup)||o.warmup<1||o.warmup>=o.cycles||!Number.isInteger(o.maxRssGrowthMiB)||o.maxRssGrowthMiB<16||o.maxRssGrowthMiB>4096)throw Error('轮次 5–10000，预热 1–轮次减一，内存增长预算 16–4096 MiB');if(fs.existsSync(o.report))throw Error('验收回执已存在，不覆盖');return o;}
function project(sessionId,mode){
 const component=(id,type,y,binding,extra)=>({id,type,label:id,x:0,y,w:12,h:2,color:'#1095bd',fontSize:18,binding,...extra});
 return {version:1,id:'runtime-soak',name:'隔离模拟压力流程',variables:{cycle:0,signal:0},variableTypes:{cycle:'integer',signal:'integer'},hmi:{version:1,title:'压力监控',rows:4,rowHeight:60,components:[component('trend','trend',0,{source:'flow',path:'cycle'},{capacity:20,precision:0,unit:''}),component('alarm','alarm',2,{source:'flow',path:'signal'},{comparison:'gt',threshold:2,hysteresis:0,stableSamples:1,severity:'warning'})]},steps:[
  {id:'camera',operation:'camera_capture',params:{driver:'session',sessionId,framePolicy:'next',timeoutMs:5000}},
  {id:'find',operation:'geometry',params:{threshold:127,minArea:50}},
  {id:'brightness',operation:'plugin',params:{pluginId:'sieans-inspection',pluginVersion:'1.0.0',operatorId:'brightness',arguments:{minimumMean:0,maximumMean:255}}},
  {id:'counter',operation:'script',params:{code:'def run(ctx):\n    v=ctx["vars"]\n    n=v["global"].get("count",0)+1\n    v["global"]["count"]=n\n    v["module"]["cycle"]=n\n    v["flow"]["cycle"]=n\n    v["flow"]["signal"]=n%4\n    return dict(result=dict(cycle=n),variables=v)'}},
  {id:'write',operation:'modbus_write',params:{transport:'simulator',area:'holding',address:10,dataType:'uint16',value:{$ref:'results.counter.cycle'}}},
  {id:'read',operation:'modbus_read',params:{transport:'simulator',area:'holding',address:10,dataType:'uint16',count:1}},
  {id:'guard',operation:'script',params:{code:mode==='failed'?'def run(ctx):\n    raise ValueError("soak injected failure")':mode==='cancelled'?'import time\ndef run(ctx):\n    time.sleep(3)\n    return dict(result={})':'def run(ctx):\n    return dict(result=dict(ok=True))'}}]};
}
async function run(o){
 const data=fs.mkdtempSync(path.join(os.tmpdir(),'sieans-runtime-soak-'));fs.writeFileSync(path.join(data,'flows.json'),'[]');
 const reserved=net.createServer();reserved.listen(0,'127.0.0.1');await once(reserved,'listening');const port=reserved.address().port;await new Promise(r=>reserved.close(r));
 const child=fork(path.join(root,'server.cjs'),[],{cwd:root,windowsHide:true,stdio:['ignore','pipe','pipe','ipc'],env:{...process.env,HOST:'127.0.0.1',PORT:String(port),MACHINE_DATA_DIR:data,ADMIN_PASSWORD_HASH:'',OPERATOR_PASSWORD_HASH:''}});let logs='',closed=false;child.stdout.on('data',b=>logs=(logs+b).slice(-12000));child.stderr.on('data',b=>logs=(logs+b).slice(-12000));const exited=new Promise(resolve=>child.once('exit',(code,signal)=>{closed=true;resolve({code,signal});}));
 const report={version:1,startedAt:new Date().toISOString(),status:'running',config:o,dataDirectory:data,scope:'Node process metrics on '+process.platform+'; simulated persistent camera, OpenCV, Python/plugin, Modbus, variable rollback, history and monitor bounds',completed:0,failed:0,cancelled:0,samples:[],checks:[],limitations:['Finite synthetic run; not field endurance or physical device/GPU accuracy','RSS covers Node process only, not Python/SDK/GPU memory','Configured growth budget is an acceptance threshold, not a leak diagnosis']};let sessionId,baseline,knownPids=[];
 async function api(route,method='GET',body){const response=await fetch(`http://127.0.0.1:${port}/api/vision/`+route,{method,headers:{'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body),signal:AbortSignal.timeout(15000)});const result=await response.json();if(!response.ok)throw Error(route+': '+result.error);return result;}
 async function until(fn,label,ms=30000){const end=Date.now()+ms;while(Date.now()<end){if(await fn())return;await delay(20);}throw Error('等待超时：'+label);}
 async function quiet(expectedCamera=1){let d;await until(async()=>{d=await api('diagnostics');return !d.runtime.busy&&d.resources.visionPending===0&&d.resources.scriptChildren===0&&d.resources.industrialChildren===0&&d.resources.activePlugins===0&&d.resources.mqttRequests===0&&d.resources.socketRequests===0&&d.resources.cameraReservations===expectedCamera;},'资源释放',5000);return d;}
 try{
  await until(async()=>{if(closed)throw Error(logs);try{await api('diagnostics');return true;}catch{return false;}},'服务器启动');
  const session=await api('cameras/session','POST',{params:{driver:'simulator',deviceId:'synthetic-parts',timeoutMs:5000},intervalMs:50});sessionId=session.id;await until(async()=>(await api('cameras/session')).state==='running','相机模拟会话');
  knownPids=[(await api('diagnostics')).processes.cameraPid].filter(Number.isInteger);
  for(let i=1;i<=o.cycles;i++){
   const mode=i%25===0?'cancelled':i%10===0?'failed':'completed',p=project(sessionId,mode),accepted=await api('runtime/jobs','POST',{project:p,allowScripts:true});let job,cancelSent=false;
   await until(async()=>{job=await api('runtime/jobs/'+accepted.id);if(mode==='cancelled'&&!cancelSent&&job.activeStep==='guard'){const d=await api('diagnostics');if(d.resources.scriptChildren>0){await api('runtime/jobs/'+job.id+'/cancel','POST');cancelSent=true;}}return job.state!=='running';},'作业完成',30000);
   assert.equal(job.state,mode,job.error);assert.equal(job.archive.state,'saved');assert.equal(job.results.find(r=>r.id==='find').output.result.count,3);assert.equal(job.results.find(r=>r.id==='brightness').output.result.passed,true);assert.equal(job.results.find(r=>r.id==='read').output.result.value,report.completed+1);
   report[mode==='completed'?'completed':mode==='failed'?'failed':'cancelled']++;
   const view=await api('runtime/view','POST',{project:p});assert.equal(view.variables.global.count||0,report.completed);assert.equal(view.variables.flow.cycle,report.completed);assert.equal(view.variables.modules.counter.cycle,report.completed);assert(view.monitor.widgets.trend.samples.length<=20);assert(view.monitor.events.length<=200);
   if(i%20===0)for(const event of view.monitor.events.filter(e=>!e.acknowledgedAt))await api('runtime/monitor/ack','POST',{projectId:p.id,id:event.id,comment:'isolated soak acknowledgement'});
   const d=await quiet();assert(d.runtime.cachedJobs<=3);assert.equal(d.history.records,Math.min(i,200));assert(d.history.bytes<=d.history.byteLimit);assert.equal(d.history.warnings,0);assert.equal(d.resources.visionChildren,1);
   knownPids=[...new Set([...knownPids,...d.processes.visionPids])];const sample={iteration:i,state:mode,rssBytes:d.process.rssBytes,heapUsedBytes:d.process.heapUsedBytes,cachedJobs:d.runtime.cachedJobs,historyRecords:d.history.records,visionChildren:d.resources.visionChildren};report.samples.push(sample);
   if(i===o.warmup)baseline=sample;if(i>o.warmup)assert(sample.rssBytes-baseline.rssBytes<=o.maxRssGrowthMiB*1024*1024,'Node RSS 超过配置的增长预算');
   if(i%20===0||i===o.cycles)process.stdout.write(`Soak ${i}/${o.cycles}: success=${report.completed} injected-failure=${report.failed} cancelled=${report.cancelled}, RSS=${(sample.rssBytes/1048576).toFixed(1)} MiB\n`);
  }
  report.cameraBeforeStop=await api('cameras/session');await api('cameras/session/'+sessionId+'/stop','POST');await until(async()=>!(await api('diagnostics')).sessions.cameraProcess,'相机释放',10000);report.finalDiagnostics=await quiet(0);report.cameraAfterStop=await api('cameras/session');
  report.baseline=baseline;report.maxRssBytes=Math.max(...report.samples.slice(o.warmup).map(s=>s.rssBytes));report.checks=['known OpenCV and brightness results','three scoped-variable execution and rollback','Modbus write/read without claiming external rollback','cached jobs <= 3 and history <= 200 / byte budget','trend <= 20 and alarm event acknowledgement','child/resource counts return to idle per cycle','persistent camera stopped and released','Node RSS within configured post-warmup growth budget'];report.status='passed';
 }catch(error){report.status='failed';report.error=error.message;report.logs=logs;process.exitCode=1;}
 finally{
  let timer;try{if(!closed&&child.connected)child.send({type:'sieans-shutdown'});const result=await Promise.race([exited,new Promise((_,reject)=>{timer=setTimeout(()=>reject(Error('自有测试服务停止超时')),45000);})]);assert.equal(result.code,0);report.serverStopped=true;}catch(error){report.status='failed';report.shutdownError=error.message;process.exitCode=1;}finally{clearTimeout(timer);}
  for(const pid of knownPids){let alive=true;for(let i=0;i<100;i++){try{process.kill(pid,0);}catch(error){if(error.code==='ESRCH'){alive=false;break;}throw error;}await delay(20);}if(alive){report.status='failed';report.shutdownError='自有子进程仍存在：'+pid;process.exitCode=1;}}
  report.endedAt=new Date().toISOString();report.sourceVersion=require('../package.json').version;fs.mkdirSync(path.dirname(o.report),{recursive:true});fs.writeFileSync(o.report,JSON.stringify(report,null,2),{flag:'wx'});process.stdout.write(`Soak ${report.status}: ${o.report}\n`);
 }
 return report;
}
module.exports={options,project,run};
if(require.main===module){let o;try{o=options(process.argv.slice(2));}catch(error){console.error(error.message);process.exitCode=1;}if(o)run(o).catch(error=>{console.error(error);process.exitCode=1;});}
