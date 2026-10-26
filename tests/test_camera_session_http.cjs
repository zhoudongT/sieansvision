const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),os=require('node:os'),bcrypt=require('bcryptjs');
const {spawn}=require('node:child_process'),{once}=require('node:events');
const root=path.resolve(__dirname,'..'),data=fs.mkdtempSync(path.join(os.tmpdir(),'sieans-camera-session-http-')),port=Number(process.env.SIEANS_TEST_HTTP_PORT||1920);
const password='camera-session-test',authorization='Basic '+Buffer.from('admin:'+password).toString('base64');
let server,logs='';const delay=ms=>new Promise(r=>setTimeout(r,ms));
async function start(){logs='';server=spawn(process.execPath,['server.cjs'],{cwd:root,windowsHide:true,stdio:['ignore','pipe','pipe','ipc'],env:{...process.env,PORT:String(port),HOST:'127.0.0.1',MACHINE_DATA_DIR:data,ADMIN_USER:'admin',ADMIN_PASSWORD_HASH:bcrypt.hashSync(password,4)}});server.stdout.on('data',b=>logs+=b);server.stderr.on('data',b=>logs+=b);for(let i=0;i<150&&!logs.includes('http://127.0.0.1:'+port);i++){if(server.exitCode!==null)throw Error(logs);await delay(100);}assert(logs.includes('http://127.0.0.1:'+port),logs);}
async function stop(){if(server?.exitCode===null){const exited=once(server,'exit');server.send({type:'sieans-shutdown'});await Promise.race([exited,delay(10000)]);assert.notEqual(server.exitCode,null,'owned test server must exit');}}
async function json(route,method='GET',body){const r=await fetch(`http://127.0.0.1:${port}/api/vision/${route}`,{method,headers:{'Content-Type':'application/json',authorization},body:body===undefined?undefined:JSON.stringify(body),signal:AbortSignal.timeout(60000)});return {status:r.status,body:await r.json()};}
async function ready(){for(let i=0;i<200;i++){const s=(await json('cameras/session')).body;if(s.state==='running')return s;if(s.state==='failed')throw Error(s.error);await delay(30);}throw Error('session not ready');}
async function jobDone(id){for(let i=0;i<300;i++){const j=(await json('runtime/jobs/'+id)).body;if(j.state!=='running')return j;await delay(30);}throw Error('job timeout');}
async function main(){
 await start();assert.equal((await fetch(`http://127.0.0.1:${port}/api/vision/cameras/session`)).status,401);
 const config={params:{driver:'simulator',deviceId:'synthetic-parts',timeoutMs:1000},intervalMs:1000,reconnectAttempts:0};
 const started=await json('cameras/session','POST',config);assert.equal(started.status,202,started.body.error);const s=await ready();
 assert.equal((await json('cameras/session','POST',config)).status,409);
 const read={driver:'session',sessionId:s.id,framePolicy:'next',timeoutMs:2000,maxAgeMs:5000};
 assert.equal((await json('cameras/run','POST',{operation:'camera_capture',params:{driver:'simulator'}})).status,400);
 const preview=await json('cameras/run','POST',{operation:'camera_capture',params:{...read,framePolicy:'latest'}});assert.equal(preview.status,200);assert.equal(preview.body.result.sessionId,s.id);
 const demo=JSON.parse(fs.readFileSync(path.join(root,'public/vision/samples/demos.json'))).find(d=>d.id==='camera-session-2d');
 const project={version:1,id:'camera-session-http',name:demo.name,steps:demo.steps.map((step,i)=>({...step,id:'n'+i,params:step.operation==='camera_capture'?read:step.params}))};
 assert.equal((await json('project','PUT',project)).status,200);
 const run=await json('runtime/jobs','POST',{project});assert.equal(run.status,202,run.body.error);
 assert.equal((await json('cameras/session/'+s.id+'/stop','POST')).status,409);
 const job=await jobDone(run.body.id);assert.equal(job.state,'completed',job.error);assert.equal(job.results[1].output.result.count,3);assert(job.results[0].output.result.frameSequence>preview.body.result.frameSequence);
 const second=await json('cameras/run','POST',{operation:'camera_capture',params:read});assert.equal(second.status,200);assert(second.body.result.frameSequence>job.results[0].output.result.frameSequence);
 assert.equal((await json('cameras/session/stale/stop','POST')).status,409);
 const stopped=await json('cameras/session/'+s.id+'/stop','POST');assert.equal(stopped.body.state,'stopped');assert.equal(stopped.body.buffered,false);
 assert.equal((await json('cameras/run','POST',{operation:'camera_capture',params:read})).status,400);
 assert.equal((await json('cameras/run','POST',{operation:'camera_capture',params:{driver:'simulator'}})).status,200);
 await json('cameras/session','POST',config);const restartSession=await ready();
 const interrupted={version:1,id:'camera-stop-rollback',name:'停止取帧回滚',steps:[{id:'change',operation:'variables',params:{scope:'global',name:'mustRollbackCamera',value:1}},{id:'cam',operation:'camera_capture',params:{...read,sessionId:restartSession.id}}]};
 assert.equal((await json('runtime/jobs','POST',{project:interrupted})).status,202);
 await stop();await start();
 const restored=(await json('cameras/session')).body;assert.equal(restored.state,'stopped');assert.equal(restored.active,false);assert.equal(restored.buffered,false);assert.equal(restored.config.intervalMs,1000);
 const saved=(await json('project')).body;assert.equal(saved.steps[0].params.sessionId,s.id);
 const view=(await json('runtime/view','POST',{project:interrupted})).body;assert.equal(view.variables.global.mustRollbackCamera,undefined);
 assert.equal((await json('cameras/run','POST',{operation:'camera_capture',params:read})).status,400);
 const auto=await json('cameras/session','POST',{...config,autoStart:true,intervalMs:100});assert.equal(auto.status,202);await ready();
 const durable={...read,sessionId:auto.body.bindingId};
 project.steps[0].params=durable;assert.equal((await json('project','PUT',project)).status,200);
 await stop();await start();const running=await ready();assert.notEqual(running.id,auto.body.id);assert.equal(running.bindingId,auto.body.bindingId);
 assert.equal((await json('cameras/run','POST',{operation:'camera_providers',params:{}})).status,200);
 const savedAuto=(await json('project')).body;
 const autoRun=await json('runtime/jobs','POST',{project:savedAuto});assert.equal(autoRun.status,202);
 assert.equal((await jobDone(autoRun.body.id)).state,'completed');assert.equal((await json('cameras/session')).body.active,true);
 console.log('PASS: authenticated session lifecycle, shared camera lock, cache preview, next-frame OpenCV demo, runtime stop exclusion, cross-client read/stop, stale ID rejection, graceful shutdown with waiting-job rollback and configuration-only restart');
 console.log('PASS: opt-in automatic connection on real server restart, saved project stable binding, provider metadata while connected and connection retained after job completion');
}
main().catch(e=>{console.error(e,logs);process.exitCode=1;}).finally(()=>stop().catch(e=>{console.error(e);process.exitCode=1;}));
