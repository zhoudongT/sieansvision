'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),os=require('node:os'),net=require('node:net');
const {fork,spawnSync}=require('node:child_process'),{once}=require('node:events');
const source=path.resolve(__dirname,'..'),root=path.resolve(process.env.SIEANS_RELEASE_ROOT||source);
const data=fs.mkdtempSync(path.join(os.tmpdir(),'sieans-deployment-http-')),models=path.join(data,'external models');
const python=process.env.VISION_PYTHON||path.join(root,'.venv',process.platform==='win32'?'Scripts/python.exe':'bin/python');
const launcher=path.join(root,'scripts/platform.cjs'),graph=require(path.join(root,'public/vision/flow-graph.js'));
const delay=ms=>new Promise(resolve=>setTimeout(resolve,ms));let port,current,serverPid,logs='';
function alive(pid){try{process.kill(pid,0);return true;}catch(e){if(e.code==='ESRCH')return false;throw e;}}
async function until(check,label,limit=15000){const end=Date.now()+limit;while(Date.now()<end){if(await check())return;await delay(80);}throw Error('Timed out: '+label+'\n'+logs);}
async function request(route,method='GET',body){const response=await fetch(`http://127.0.0.1:${port}${route}`,{method,headers:{'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body),signal:AbortSignal.timeout(2000)});return {status:response.status,body:await response.json()};}
function launch(){const child=fork(launcher,['start','--data-dir',data],{cwd:os.tmpdir(),windowsHide:true,stdio:['ignore','pipe','pipe','ipc'],env:{...process.env,ADMIN_PASSWORD_HASH:''}});child.stdout.on('data',b=>logs+=b);child.stderr.on('data',b=>logs+=b);child.done=new Promise(resolve=>child.once('exit',(code,signal)=>resolve({code,signal})));return child;}
async function start(){current=launch();await until(async()=>{if(current.exitCode!==null)throw Error(logs);try{return (await request('/health')).status===200;}catch{return false;}},'healthy packaged server',30000);serverPid=JSON.parse(fs.readFileSync(path.join(data,'.sieans-runtime.lock'),'utf8')).pid;assert.notEqual(serverPid,current.pid);}
async function stop(){const child=current;child.send({type:'sieans-shutdown'});await until(()=>child.exitCode!==null,'launcher graceful exit');assert.deepEqual(await child.done,{code:0,signal:null});await until(()=>!alive(serverPid)&&!fs.existsSync(path.join(data,'.sieans-runtime.lock')),'server cleanup');current=null;}
async function execute(project,extra={}){const accepted=await request('/api/vision/runtime/jobs','POST',{project,...extra});assert.equal(accepted.status,202,JSON.stringify(accepted));let job=accepted.body;await until(async()=>{job=(await request('/api/vision/runtime/jobs/'+job.id)).body;return job.state!=='running';},'job complete',30000);assert.equal(job.state,'completed',JSON.stringify(job));assert.equal(job.archive.state,'saved');return job;}
async function main(){
 const reserved=net.createServer();reserved.listen(0,'127.0.0.1');await once(reserved,'listening');port=reserved.address().port;await new Promise(resolve=>reserved.close(resolve));
 const configured=spawnSync(process.execPath,[launcher,'configure','--data-dir',data,'--python',python,'--features','core','--port',String(port),'--models-dir',models],{encoding:'utf8',windowsHide:true,env:{...process.env,ADMIN_PASSWORD_HASH:''}});assert.equal(configured.status,0,configured.stderr);
 fs.writeFileSync(path.join(models,'deployment-path-test.onnx'),'path listing fixture, not an inference model');
 await start();assert.deepEqual((await request('/api/vision/models')).body.models,['deployment-path-test.onnx']);
 assert.equal((await request('/api/vision/version')).body.version,require(path.join(root,'package.json')).version);
 const duplicate=launch();await until(()=>duplicate.exitCode!==null,'duplicate refusal');assert.notEqual((await duplicate.done).code,0);assert.match(logs,/运行目录已被服务占用/);assert.equal(JSON.parse(fs.readFileSync(path.join(data,'.sieans-runtime.lock'),'utf8')).pid,serverPid);
 const project=graph.normalize({version:1,id:'deployment-persistence',name:'部署保存与恢复',variables:{count:0},variableTypes:{count:'integer'},steps:[{id:'script',operation:'script',params:{code:'def run(ctx):\n    return dict(result=dict(count=ctx["vars"]["flow"]["count"]+1, passed=True))\n',outputBindings:[{field:'count',scope:'flow',name:'count'},{field:'passed',scope:'module',name:'passed'}]}}]});
 assert.equal((await request('/api/vision/project','PUT',project)).status,200);
 const first=await execute(project,{allowScripts:true});assert.equal(first.variables.flow.count,1);assert.equal(first.variables.modules.script.passed,true);
 if(process.env.SIEANS_DEPLOY_TEST_FULL==='1'){
  const image='data:image/png;base64,'+fs.readFileSync(path.join(root,'public/vision/samples/parts.png')).toString('base64');
  const vision=graph.normalize({version:1,id:'deployment-image',name:'发布包 2D 检测',steps:[{id:'find',operation:'geometry',params:{threshold:127,minArea:50}}]});
  assert.equal((await execute(vision,{image})).results[0].output.result.count,3);
  const cloud=graph.normalize({version:1,id:'deployment-cloud',name:'发布包 3D 测量',steps:[{id:'box',operation:'cloud_measure',params:{}}]});
  const measured=await execute(cloud,{cloud:{unit:'mm',points:[[0,0,0],[20,10,5],[0,10,5],[20,0,0]]}});assert.equal(measured.results[0].output.result.sizeX,20);
  const demo=(file,index=0)=>{
   const sample=JSON.parse(fs.readFileSync(path.join(root,'public/vision/samples',file),'utf8'))[index];
   const steps=sample.steps.map((s,i)=>({...s,id:'demo'+i}));
   for(const b of sample.bindings||[])steps[b.step].params[b.param]={$ref:'results.demo'+b.source+'.'+b.field};
   return graph.normalize({version:1,id:'packaged-'+sample.id,name:sample.name,steps});
  };
  assert.equal((await execute(demo('demos-plugins.json'),{image})).variables.flow.brightnessOK,true);
  assert.equal((await execute(demo('demos-industrial.json'),{image})).variables.flow.plcCount,3);
  assert.equal((await execute(demo('demos-cameras.json'))).variables.flow.cameraCount,3);
  assert.equal((await execute(demo('demos-cameras.json',1))).variables.flow.topWidth,185.25);
  const grid='data:image/png;base64,'+fs.readFileSync(path.join(root,'public/vision/samples/intrinsics-grid.png')).toString('base64');
  const calibrated=await execute(demo('demos-intrinsics.json',2),{image:grid});assert(Math.abs(calibrated.variables.flow.cameraCalibration.fx-710)<.1);
  const rigidCloud=JSON.parse(fs.readFileSync(path.join(root,'public/vision/samples/rigid-source.json')));
  const rigid=await execute(demo('demos-rigid.json',2),{cloud:rigidCloud});assert.equal(rigid.results[1].output.cloud.frame,'fixture-base');assert(Math.abs(rigid.results[2].output.result.sizeX-100)<1e-8);
  const sessionStart=await request('/api/vision/cameras/session','POST',{params:{driver:'simulator',deviceId:'synthetic-parts',timeoutMs:1000},intervalMs:100});assert.equal(sessionStart.status,202);
  await until(async()=>(await request('/api/vision/cameras/session')).body.state==='running','packaged continuous camera');
  const continuousCamera=demo('demos-cameras.json');continuousCamera.steps[0].params={driver:'session',sessionId:sessionStart.body.id,framePolicy:'next',timeoutMs:1000};
  const frame=await execute(continuousCamera);assert.equal(frame.variables.flow.cameraCount,3);assert(frame.results[0].output.result.frameSequence>0);
  assert.equal((await request('/api/vision/cameras/session/'+sessionStart.body.id+'/stop','POST')).body.state,'stopped');
  const samples=JSON.parse(fs.readFileSync(path.join(root,'public/vision/samples/demos.json'))),eventDemo=samples.find(d=>d.id==='mqtt-event-trigger');
  const eventProject={version:1,id:'packaged-event',name:eventDemo.name,variables:eventDemo.variables,steps:eventDemo.steps.map((s,i)=>({...s,id:'evt'+i}))};
  const subscribed=await request('/api/vision/runtime/mqtt-trigger','POST',{project:eventProject,connection:{connection:'simulator',topic:'sieans/release',encoding:'structured',qos:1}});assert.equal(subscribed.status,202,subscribed.body.error);
  await until(async()=>(await request('/api/vision/runtime/mqtt-trigger')).body.state==='subscribed','packaged MQTT subscription');
  assert.equal((await request('/api/vision/runtime/mqtt-trigger/test-message','POST')).status,200);
  await until(async()=>(await request('/api/vision/runtime/mqtt-trigger')).body.completed===1,'packaged event job');
  assert.equal((await request('/api/vision/runtime/view','POST',{project:eventProject})).body.variables.flow.partCount,3);
  await request('/api/vision/runtime/mqtt-trigger/'+subscribed.body.id+'/stop','POST');
  await until(async()=>(await request('/api/vision/runtime/mqtt-trigger')).body.state==='stopped','packaged event stop');
  const hmi=samples.find(d=>d.id==='hmi-multipage');assert.equal(hmi.hmi.pages.length,4);const pages={version:1,id:'packaged-pages',name:hmi.name,hmi:hmi.hmi,variables:hmi.variables,steps:hmi.steps.map((s,i)=>({...s,id:'page'+i}))};
  assert.equal((await request('/api/vision/project','PUT',pages)).status,200);assert.equal((await request('/api/vision/project')).body.hmi.pages.length,4);
  assert.equal((await request('/api/vision/project','PUT',project)).status,200);
 }
 await stop();await start();assert.equal((await request('/api/vision/project')).body.id,project.id);assert.equal((await request('/api/vision/history/'+first.id)).body.variables.flow.count,1);
 assert.equal((await execute(project,{allowScripts:true})).variables.flow.count,2);
 // Shutdown cancels manual jobs, waits for archive, and does not commit staged variables.
 const workerFile=path.join(data,'test-python-worker.pid');
 const slow=graph.normalize({version:1,id:project.id,name:'停止时回滚',variables:{count:0},steps:[{id:'write',operation:'variables',params:{name:'count',value:999}},{id:'wait',operation:'script',params:{timeoutMs:30000,code:'import os,time\nfrom pathlib import Path\ndef run(ctx):\n    Path('+JSON.stringify(workerFile)+').write_text(str(os.getpid()))\n    time.sleep(30)\n    return dict(result=dict(done=True))\n'}}]});
 const pending=await request('/api/vision/runtime/jobs','POST',{project:slow,allowScripts:true});assert.equal(pending.status,202);await until(()=>fs.existsSync(workerFile),'active Python worker');const workerPid=Number(fs.readFileSync(workerFile,'utf8'));assert.ok(alive(workerPid));
 await stop();await until(()=>!alive(workerPid),'Python child cleanup');await start();const history=(await request('/api/vision/history/'+pending.body.id)).body;assert.equal(history.state,'cancelled');assert.equal(history.variablesCommitted,false);assert.equal(history.variables.flow.count,2);
 // Closing supervisor IPC requests graceful launcher/server shutdown.
 const disconnected=current;disconnected.disconnect();await until(()=>disconnected.exitCode!==null,'supervisor disconnection');assert.equal((await disconnected.done).code,0);current=null;
 await until(()=>!alive(serverPid)&&!fs.existsSync(path.join(data,'.sieans-runtime.lock')),'disconnected server cleanup');
 await start();
 // An OS-forced process-tree termination may retain a stale lock. Restart must recover it.
 const killed=current;killed.kill('SIGKILL');await killed.done;current=null;await until(()=>!alive(serverPid),'orphan server exit');
 await start();assert.equal((await request('/api/vision/runtime/variables/read','POST',{project})).body.flow.count,2);await stop();
 console.log('PASS deployment: external paths, duplicate lock, version, Python, project/variable/history persistence, cancellation rollback, launcher/server exit'+(process.env.SIEANS_DEPLOY_TEST_FULL==='1'?', packaged 2D/3D/plugins/Modbus/cameras/intrinsics/rigid/MQTT events/HMI pages':''));
}
main().catch(error=>{console.error(error,logs);process.exitCode=1;}).finally(async()=>{if(current&&current.exitCode===null){current.kill('SIGKILL');await current.done;}if(serverPid)await until(()=>!alive(serverPid),'test server final cleanup').catch(error=>{console.error(error.message);process.exitCode=1;});console.log('Deployment test data: '+data);});
