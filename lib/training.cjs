'use strict';
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),readline=require('node:readline');
const {spawn}=require('node:child_process');
const root=path.resolve(__dirname,'..');
const validId=value=>typeof value==='string'&&/^[a-z][a-z0-9_-]{0,39}$/.test(value)&&! /^(con|prn|aux|nul|com[0-9]|lpt[0-9])$/i.test(value);
function inside(parent,file){const rel=path.relative(fs.realpathSync(parent),fs.realpathSync(file));if(rel==='..'||rel.startsWith('..'+path.sep)||path.isAbsolute(rel))throw Error('路径不能离开受管目录');return file;}
function integer(value,low,high,label){if(!Number.isInteger(value)||value<low||value>high)throw Error(label+'范围应为 '+low+'–'+high);return value;}
function terminate(child){if(process.platform==='win32')spawn('taskkill',['/PID',String(child.pid),'/T','/F'],{windowsHide:true,stdio:'ignore'});else child.kill();}
class Training{
 constructor(directory,models,runtime){
  this.directory=path.join(directory,'training');this.datasets=path.join(this.directory,'datasets');this.runs=path.join(this.directory,'jobs');this.models=models;this.runtime=runtime;this.owner=Symbol('training');this.child=null;this.working=false;
  for(const dir of [this.datasets,this.runs,this.models])fs.mkdirSync(dir,{recursive:true});
  this.stateFile=path.join(this.directory,'latest.json');this.job=fs.existsSync(this.stateFile)?JSON.parse(fs.readFileSync(this.stateFile,'utf8')):null;
  if(this.job&&['running','stopping'].includes(this.job.state)){this.job.state='interrupted';this.job.error='服务中断了训练，保留产物供检查；请重新创建训练任务';this.persist();}
 }
 persist(){fs.writeFileSync(this.stateFile+'.tmp',JSON.stringify(this.job));fs.renameSync(this.stateFile+'.tmp',this.stateFile);}
 dataset(id){if(!validId(id))throw Error('数据集目录名需为小写字母开头的 1–40 位字母、数字、横线或下划线');const folder=path.join(this.datasets,id);inside(this.datasets,folder);const manifest=inside(folder,path.join(folder,'dataset.json'));const data=JSON.parse(fs.readFileSync(manifest,'utf8'));if(data.id!==id||!['detect','segment'].includes(data.task)||!Array.isArray(data.names))throw Error('数据集定义无效');return {...data,folder};}
 status(){return {busy:this.working,datasetRoot:this.datasets,datasets:fs.readdirSync(this.datasets).filter(validId).flatMap(id=>{try{return [this.dataset(id)];}catch{return [];}}),models:fs.readdirSync(this.models).filter(n=>n.endsWith('.pt')),job:this.job?structuredClone(this.job):null};}
 async lock(action){if(this.working)throw Error('训练模块正在处理其他任务');this.runtime.reserve(this.owner);this.working=true;try{return await action();}finally{this.working=false;this.runtime.release(this.owner);}}
 worker(request,onEvent=()=>{}){
  const python=process.env.VISION_PYTHON||path.join(root,'.venv',process.platform==='win32'?'Scripts/python.exe':'bin/python');
  fs.mkdirSync(path.join(this.directory,'config'),{recursive:true});
  return new Promise((resolve,reject)=>{
   const child=spawn(python,['-u',path.join(root,'vision/training.py')],{cwd:root,windowsHide:true,env:{...process.env,PYTHONIOENCODING:'utf-8',YOLO_CONFIG_DIR:path.join(this.directory,'config'),YOLO_AUTOINSTALL:'false',YOLO_OFFLINE:'true',OPENCV_IO_MAX_IMAGE_PIXELS:'16000000',OMP_NUM_THREADS:'2',CUBLAS_WORKSPACE_CONFIG:process.env.CUBLAS_WORKSPACE_CONFIG||':4096:8'}});this.child=child;
   let done=null,error='',stderr='';const timeout=request.action==='annotation_suggest'?120000:6*3600000;const timer=setTimeout(()=>{error=request.action==='annotation_suggest'?'候选生成超过 2 分钟上限':'训练操作超过 6 小时上限';terminate(child);},timeout);timer.unref();
   child.stderr.on('data',b=>stderr=(stderr+b.toString()).slice(-3000));
   readline.createInterface({input:child.stdout}).on('line',line=>{if(!line.startsWith('SIEANS_TRAIN:'))return;try{const event=JSON.parse(line.slice(13));if(event.kind==='error')error=String(event.message);else if(event.kind==='complete')done=event;onEvent(event);}catch(e){error='训练事件无法读取：'+e.message;terminate(child);}});
   child.stdin.on('error',()=>{});child.stdin.write(JSON.stringify(request)+'\n');
   child.once('error',e=>{error='无法启动训练环境：'+e.message;});
   child.once('close',code=>{clearTimeout(timer);if(this.child===child)this.child=null;if(code===0&&done&&!error)resolve(done);else reject(Error(error||'训练进程中断：'+stderr));});
  });
 }
 async create(body){
  if(!validId(body.id))throw Error('请填写有效数据集目录名');if(!['detect','segment'].includes(body.task))throw Error('请选择目标检测或实例分割');
  if(!Array.isArray(body.names)||!body.names.length||body.names.length>100||body.names.some(n=>typeof n!=='string'||!n.trim()||n.length>80)||new Set(body.names).size!==body.names.length)throw Error('类别名称需要 1–100 项，不允许空值或重复');
  return this.lock(async()=>{
   const folder=path.join(this.datasets,body.id);if(fs.existsSync(folder))throw Error('数据集目录已存在，请使用新名称');
   if(body.demo===true){if(body.names.length!==1||body.names[0]!=='part')throw Error('合成示例只使用 part 类别');await this.worker({action:'demo',folder,task:body.task});}
   else for(const kind of ['images','labels'])for(const split of ['train','val'])fs.mkdirSync(path.join(folder,kind,split),{recursive:true});
   const manifest={id:body.id,task:body.task,names:body.names,demo:body.demo===true,createdAt:Date.now()};fs.writeFileSync(path.join(folder,'dataset.json'),JSON.stringify(manifest),{flag:'wx'});return {...manifest,folder};
  });
 }
 check(id){const d=this.dataset(id);return this.lock(()=>this.worker({action:'check',...d}));}
 annotate(id,action,body={}){const dataset=this.dataset(id);if(!['list','load','save','upload','suggest','history','history_load'].includes(action))throw Error('未知标注操作');const request={...body,...dataset,action:'annotation_'+action};
  if(action==='suggest'){
   if(typeof body.model!=='string'||! /^[a-zA-Z0-9_-][a-zA-Z0-9_.-]{0,120}\.pt$/.test(body.model))throw Error('请选择本地可信 .pt 模型');
   request.modelPath=inside(this.models,path.join(this.models,body.model));if(!fs.statSync(request.modelPath).isFile()||fs.statSync(request.modelPath).size>250000000)throw Error('模型需为不超过 250 MB 的本地文件');
  }
  return this.lock(()=>this.worker(request));}
 start(body){
  if(this.working)throw Error('训练模块正在处理其他任务');const dataset=this.dataset(body.datasetId);
  if(typeof body.model!=='string'||path.basename(body.model)!==body.model||!body.model.endsWith('.pt'))throw Error('请选择本地可信 .pt 基础模型');
  const modelPath=inside(this.models,path.join(this.models,body.model));if(!fs.statSync(modelPath).isFile()||fs.statSync(modelPath).size>250000000)throw Error('基础模型需为不超过 250 MB 的本地文件');
  const config={epochs:integer(body.epochs??20,1,300,'训练轮次'),imageSize:integer(body.imageSize??320,64,640,'训练尺寸'),batch:integer(body.batch??2,1,8,'批量大小'),seed:integer(body.seed??0,0,2147483647,'随机种子'),learningRate:body.learningRate??.001};
  config.device=body.device??'cpu';if(typeof config.device!=='string'||! /^(cpu|auto|cuda:\d{1,2})$/.test(config.device))throw Error('请选择 CPU、自动或 CUDA 显卡编号');
  if(config.imageSize%32)throw Error('训练尺寸须为 32 的倍数');if(typeof config.learningRate!=='number'||!Number.isFinite(config.learningRate)||config.learningRate<=0||config.learningRate>.1)throw Error('学习率须大于 0 且不超过 0.1');
  this.runtime.reserve(this.owner);this.working=true;
  const id=crypto.randomUUID(),jobFolder=path.join(this.runs,id);
  try{fs.mkdirSync(jobFolder);this.job={id,state:'running',startedAt:Date.now(),datasetId:dataset.id,task:dataset.task,demo:dataset.demo,model:body.model,config,device:null,requestedDevice:config.device,epoch:0,metrics:[],error:null};this.persist();}catch(error){this.working=false;this.runtime.release(this.owner);throw error;}
  this.promise=this.worker({action:'train',...dataset,jobFolder,modelPath,config},event=>{
   if(event.kind==='dataset')this.job.dataset=event.summary;
   if(event.kind==='device')for(const key of ['device','requestedDevice','deviceName','deviceReason'])this.job[key]=event[key];
   if(event.kind==='phase')this.job.phase=event.message;
   if(event.kind==='epoch'){this.job.epoch=event.epoch;this.job.metrics.push({epoch:event.epoch,...event.metrics});}
   this.persist();
  }).then(event=>{if(this.job.state==='stopping')return;const checkpoint=inside(jobFolder,event.checkpoint);if(path.basename(checkpoint)!=='best.pt'||fs.statSync(checkpoint).size>250000000)throw Error('模型产物无效');this.job.checkpoint=checkpoint;this.job.sha256=event.sha256;this.job.state='completed';}).catch(error=>{if(this.job.state!=='stopping'){this.job.state='failed';this.job.error=error.message;}}).finally(()=>{if(this.job.state==='stopping')this.job.state='cancelled';this.job.endedAt=Date.now();try{this.persist();}finally{this.working=false;this.runtime.release(this.owner);}});
  return structuredClone(this.job);
 }
 cancel(id){if(!this.job||this.job.id!==id||!['running','stopping'].includes(this.job.state))throw Error('没有对应的运行中训练');this.job.state='stopping';this.persist();if(this.child)terminate(this.child);return structuredClone(this.job);}
 publish(id,name){
  if(this.working||this.runtime.busy)throw Error('执行期间不可安装训练模型');if(!this.job||this.job.id!==id||this.job.state!=='completed')throw Error('只能安装完整训练成功的模型');
  if(typeof name!=='string'||!/^trained-[a-z0-9_-]{1,60}\.pt$/.test(name))throw Error('名称格式：trained-字母数字横线.pt');
  const source=inside(path.join(this.runs,id),this.job.checkpoint),bytes=fs.readFileSync(source);if(crypto.createHash('sha256').update(bytes).digest('hex')!==this.job.sha256)throw Error('训练模型校验失败');
  const target=path.join(this.models,name);fs.writeFileSync(target,bytes,{flag:'wx'});this.job.published=name;this.persist();return {name,task:this.job.task,demo:this.job.demo};
 }
 async stop(){if(this.job&&this.child&&this.job.state==='running')this.cancel(this.job.id);else if(this.child)terminate(this.child);await this.promise;}
}
module.exports={Training};
