'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),os=require('node:os'),path=require('node:path'),crypto=require('node:crypto');
const {spawn}=require('node:child_process'),{once}=require('node:events');
const trainingDevice=process.env.TEST_TRAIN_DEVICE||'cpu';
const root=path.resolve(__dirname,'..'),port=Number(process.env.SIEANS_TEST_HTTP_PORT||1904),url=`http://127.0.0.1:${port}`,data=fs.mkdtempSync(path.join(os.tmpdir(),'sieans-training-http-')),models=path.join(data,'models');fs.mkdirSync(models);
for(const name of ['yolo11n.pt','yolo11n-seg.pt'])fs.copyFileSync(path.join(root,'models',name),path.join(models,name));
const server=spawn(process.execPath,['server.cjs'],{cwd:root,windowsHide:true,stdio:['ignore','pipe','pipe','ipc'],env:{...process.env,PORT:String(port),HOST:'127.0.0.1',MACHINE_DATA_DIR:data,VISION_MODEL_DIR:models,ADMIN_PASSWORD_HASH:''}});
let logs='';server.stdout.on('data',b=>logs+=b);server.stderr.on('data',b=>logs+=b);const delay=ms=>new Promise(r=>setTimeout(r,ms));
async function json(route,method='GET',body){const r=await fetch(url+'/api/vision/'+route,{method,headers:{'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body),signal:AbortSignal.timeout(60000)});return {status:r.status,body:await r.json()};}
async function waitJob(id,condition=j=>!['running','stopping'].includes(j.state)){for(let i=0;i<1800;i++){const j=(await json('training')).body.job;assert.equal(j.id,id);if(condition(j))return j;await delay(100);}throw Error('Training acceptance timeout');}
async function main(){
 for(let i=0;i<150&&!logs.includes(`http://127.0.0.1:${port}`);i++){if(server.exitCode!==null)throw Error(logs);await delay(100);}assert.ok(logs.includes(`http://127.0.0.1:${port}`),logs);
 assert.equal((await json('training/datasets','POST',{id:'../escape',task:'detect',names:['part']})).status,400);
 assert.equal((await json('training/datasets','POST',{id:'invalid',task:'detect',names:['a','a']})).status,400);
 for(const task of ['detect','segment']){
  const id='demo-'+task,created=await json('training/datasets','POST',{id,task,names:['part'],demo:true});assert.equal(created.status,201,created.body.error);
  const check=await json('training/datasets/'+id+'/check','POST',{});assert.equal(check.status,200,check.body.error);assert.equal(check.body.summary.splits.train.images,12);assert.equal(check.body.summary.splits.val.images,4);
  const annotationRoute='training/datasets/'+id+'/annotations/';
  const listed=await json(annotationRoute+'list','POST',{});assert.equal(listed.body.items.length,16);
  const frame=await json(annotationRoute+'load','POST',{name:'part-0.png',split:'train'});assert.equal(frame.status,200,frame.body.error);assert.equal(frame.body.records.length,1);assert.match(frame.body.image,/^data:image\/png;base64,/);
  if(task==='detect')frame.body.records[0].box[0]+=.001;else frame.body.records[0].points[0][0]+=.001;
  const saved=await json(annotationRoute+'save','POST',{name:'part-0.png',split:'train',records:frame.body.records,revision:frame.body.revision});assert.equal(saved.status,200,saved.body.error);
  assert.equal((await json(annotationRoute+'save','POST',{name:'part-0.png',split:'train',records:[],revision:frame.body.revision})).status,409);
  assert.equal((await json(annotationRoute+'load','POST',{name:'../escape.png',split:'train'})).status,400);
  assert.equal((await json('training/jobs','POST',{datasetId:id,device:trainingDevice,model:task==='detect'?'yolo11n.pt':'yolo11n-seg.pt',epochs:1,imageSize:65})).status,400);
  const start=await json('training/jobs','POST',{datasetId:id,device:trainingDevice,model:task==='detect'?'yolo11n.pt':'yolo11n-seg.pt',epochs:1,imageSize:64,batch:2});assert.equal(start.status,202,start.body.error);
  assert.equal((await json('runtime/jobs','POST',{project:{version:1,name:'locked',steps:[{id:'v',operation:'variables',params:{name:'value',value:1}}]}})).status,409);
  assert.equal((await json('training/jobs','POST',{datasetId:id,device:trainingDevice,model:'yolo11n.pt'})).status,409);
  const job=await waitJob(start.body.id);assert.equal(job.state,'completed',job.error);assert.equal(job.epoch,1);assert.equal(job.device,trainingDevice);assert.equal(job.metrics.length,1);assert.ok(Object.keys(job.metrics[0]).some(k=>k.startsWith('train/')));assert.ok(Object.keys(job.metrics[0]).some(k=>k.includes('mAP')));
  const name='trained-'+task+'.pt',published=await json('training/jobs/'+job.id+'/publish','POST',{name});assert.equal(published.status,200,published.body.error);assert.equal(published.body.task,task);
  assert.equal((await json('training/jobs/'+job.id+'/publish','POST',{name})).status,400);
  assert.equal((await json('training/jobs/'+job.id+'/publish','POST',{name:'../evil.pt'})).status,400);
  assert.equal(crypto.createHash('sha256').update(fs.readFileSync(path.join(models,name))).digest('hex'),job.sha256);
  const image='data:image/png;base64,'+fs.readFileSync(path.join(created.body.folder,'images/val/part-0.png')).toString('base64');
  const prediction=await json('run','POST',{operation:task==='detect'?'yolo':'yolo_segment',image,params:{device:trainingDevice,model:name,confidence:.001,imageSize:64}});assert.equal(prediction.status,200,prediction.body.error);assert.ok(prediction.body.result.count>0);assert.equal(prediction.body.result.device,trainingDevice);assert.ok(prediction.body.result.items.every(item=>item.label==='part'));
  if(task==='segment'){assert.match(prediction.body.maskImage,/^data:image\/png;base64,/);assert.ok(prediction.body.result.unionAreaPixels>0);}
  console.log('PASS: '+task+' annotation read/save/conflict, actual training from edited labels, metrics, exclusion, checkpoint install and trained inference');
 }
 const wrong=await json('training/jobs','POST',{datasetId:'demo-segment',device:trainingDevice,model:'yolo11n.pt',epochs:1,imageSize:64,batch:2});assert.equal(wrong.status,202);assert.equal((await waitJob(wrong.body.id)).state,'failed');
 const cancel=await json('training/jobs','POST',{datasetId:'demo-detect',device:trainingDevice,model:'yolo11n.pt',epochs:300,imageSize:64,batch:2});assert.equal(cancel.status,202);
 await waitJob(cancel.body.id,j=>j.phase==='训练与验证'||j.state==='failed');assert.equal((await json('training/jobs/'+cancel.body.id+'/cancel','POST',{})).status,202);
 const stopped=await waitJob(cancel.body.id);assert.equal(stopped.state,'cancelled');assert.equal((await json('training')).body.busy,false);assert.equal((await json('training/jobs/'+cancel.body.id+'/publish','POST',{name:'trained-cancelled.pt'})).status,400);
 const after=await json('runtime/jobs','POST',{project:{version:1,name:'unlocked',steps:[{id:'v',operation:'variables',params:{name:'value',value:1}}]}});assert.equal(after.status,202);
 console.log('PASS: task mismatch, active cancellation of real training process tree, no cancelled publication and runtime lock release');
}
main().catch(e=>{console.error(e.message,logs);process.exitCode=1;}).finally(async()=>{if(server.exitCode===null){server.send({type:'sieans-shutdown'});await Promise.race([once(server,'exit'),delay(5000)]);if(server.exitCode===null)server.kill();}console.log('Training test data: '+data);});
