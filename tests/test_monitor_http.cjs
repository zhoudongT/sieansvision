'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),os=require('node:os'),{spawn}=require('node:child_process'),{once}=require('node:events');
const root=path.resolve(__dirname,'..'),port=Number(process.env.SIEANS_TEST_HTTP_PORT||1916),data=fs.mkdtempSync(path.join(os.tmpdir(),'sieans-monitor-http-'));let server,logs='';const delay=ms=>new Promise(r=>setTimeout(r,ms));
async function start(){logs='';server=spawn(process.execPath,['server.cjs'],{cwd:root,windowsHide:true,stdio:['ignore','pipe','pipe','ipc'],env:{...process.env,PORT:String(port),HOST:'127.0.0.1',MACHINE_DATA_DIR:data,ADMIN_PASSWORD_HASH:''}});server.stdout.on('data',b=>logs+=b);server.stderr.on('data',b=>logs+=b);for(let i=0;i<150&&!logs.includes('http://127.0.0.1:'+port);i++){if(server.exitCode!==null)throw Error(logs);await delay(100);}assert.ok(logs.includes('http://127.0.0.1:'+port),logs);}
async function stop(){if(server?.exitCode===null){server.send({type:'sieans-shutdown'});await Promise.race([once(server,'exit'),delay(5000)]);if(server.exitCode===null)throw Error('Monitor HTTP test server did not exit');}}
async function json(route,method='GET',body){const r=await fetch('http://127.0.0.1:'+port+'/api/vision/'+route,{method,headers:{'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body),signal:AbortSignal.timeout(60000)});return {status:r.status,body:await r.json()};}
async function view(project,since){const response=await json('runtime/view','POST',{project,since});assert.equal(response.status,200,response.body.error);return response.body;}
async function main(){
 await start();const demo=JSON.parse(fs.readFileSync(path.join(root,'public/vision/samples/demos.json'),'utf8')).find(d=>d.id==='monitor-temperature'),project={version:1,id:'monitor-http',name:demo.name,variables:demo.variables,hmi:demo.hmi,steps:demo.steps.map((s,i)=>({...s,id:'n'+i}))};
 assert.equal((await json('project','PUT',project)).status,200);assert.equal((await json('project')).body.hmi.components.find(c=>c.type==='trend').capacity,120);
 const initial=await view(project);assert.deepEqual(initial.monitor.events,[]);
 const continuous=await json('runtime/continuous','POST',{project,intervalMs:100,maxCycles:10});assert.equal(continuous.status,202,continuous.body.error);let status;
 for(let i=0;i<200;i++){await delay(50);status=(await json('runtime/continuous')).body;if(!['running','waiting','stopping'].includes(status.state))break;}assert.equal(status.state,'completed',status.error);assert.equal(status.completedCycles,10);
 let current=await view(project);assert.equal(current.variables.flow.temperature,20);assert.equal(current.monitor.widgets['temperature-trend'].samples.length,10);assert.equal(current.monitor.events.length,1);assert.equal(current.monitor.widgets['temperature-alarm'].active,true);
 const event=current.monitor.events[0],previousVersion=current.version;
 assert.equal((await json('runtime/monitor/ack','POST',{projectId:'other',id:event.id})).status,400);
 const ack=await json('runtime/monitor/ack','POST',{projectId:project.id,id:event.id,comment:'已检查测试设备'});assert.equal(ack.status,200,ack.body.error);assert.ok(ack.body.events[0].acknowledgedAt);assert.equal(ack.body.events[0].returnedAt,null);
 const secondClient=await view(project,previousVersion);assert.notEqual(secondClient.version,previousVersion);assert.ok(secondClient.monitor.events[0].acknowledgedAt);assert.equal(secondClient.monitor.widgets['temperature-alarm'].active,true);
 for(let i=0;i<2;i++){const values=(await json('runtime/variables/read','POST',{project})).body;values.flow.temperature=0;assert.equal((await json('runtime/variables','PUT',{project,values,revision:values.revision})).status,200);}
 current=await view(project);assert.equal(current.monitor.widgets['temperature-alarm'].active,false);assert.ok(current.monitor.events[0].returnedAt);assert.equal(current.monitor.widgets['temperature-trend'].samples.length,12);
 const bad=structuredClone(project);bad.steps.push({id:'fail',operation:'delay',params:{milliseconds:-1}});const failed=await json('runtime/jobs','POST',{project:bad});assert.equal(failed.status,202);for(let i=0;i<100;i++){const job=(await json('runtime/jobs/'+failed.body.id)).body;if(job.state!=='running'){assert.equal(job.state,'failed');break;}await delay(20);}
 current=await view(project);assert.equal(current.monitor.widgets['temperature-trend'].samples.at(-1).value,null);const samples=current.monitor.widgets['temperature-trend'].samples.length,revision=current.monitor.revision;
 for(let i=0;i<3;i++)assert.equal((await view(project)).monitor.revision,revision);
 await stop();await start();current=await view(project);assert.equal(current.status.state,'idle');assert.equal(current.monitor.widgets['temperature-trend'].samples.length,samples);assert.equal(current.monitor.events[0].id,event.id);assert.ok(current.monitor.events[0].acknowledgedAt);assert.ok(current.monitor.events[0].returnedAt);
 console.log('PASS: unattended continuous sampling, HMI configuration persistence, cross-client acknowledgment, active-condition retention, recovery, failure gaps, read-only polling and server restart');
}
main().catch(error=>{console.error(error,logs);process.exitCode=1;}).finally(()=>stop().catch(error=>{console.error(error);process.exitCode=1;}));
