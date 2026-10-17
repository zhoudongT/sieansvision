'use strict';
const {spawn}=require('node:child_process'),fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const {StringDecoder}=require('node:string_decoder');
const {frame}=require('./frame.cjs');
const root=path.resolve(__dirname,'..');
const live=new Set(['opening','running','reconnecting','stopping']);
const integer=(v,label,min,max)=>{if(!Number.isInteger(v)||v<min||v>max)throw Error(label+'范围为 '+min+'–'+max);return v;};
function settings(body){
 if(!body||typeof body!=='object'||Array.isArray(body)||Object.keys(body).some(k=>!['params','intervalMs','reconnectAttempts','reconnectMs'].includes(k)))throw Error('连续采集配置无效');
 const p=body.params;
 if(!p||typeof p!=='object'||Array.isArray(p)||!['simulator','rgbd_simulator','uvc','gentl','realsense','orbbec'].includes(p.driver))throw Error('请选择支持连续连接的相机驱动');
 if(Buffer.byteLength(JSON.stringify(p))>100000)throw Error('相机参数超过 100 KB');
 integer(p.timeoutMs??5000,'采集超时',100,30000);
 const s={params:structuredClone(p),intervalMs:integer(body.intervalMs??100,'最短采集间隔 (ms)',50,60000),reconnectAttempts:integer(body.reconnectAttempts??0,'重连总次数',0,5),reconnectMs:integer(body.reconnectMs??1000,'重连间隔 (ms)',200,60000)};
 if((p.trigger||'freerun')!=='freerun')throw Error('连续相机会话仅支持自由采集；软件/外部触发请使用单帧采集，避免后台重复触发');
 return s;
}
class CameraSession{
 constructor(directory,resources){
  this.file=path.join(directory,'camera-session.json');this.resources=resources;this.state={state:'idle'};this.latest=null;this.child=null;this.waiter=null;this.closed=Promise.resolve();
  if(fs.existsSync(this.file)){
   if(fs.statSync(this.file).size>200000)throw Error('连续相机会话记录过大');
   const saved=JSON.parse(fs.readFileSync(this.file,'utf8'));
   if(saved.version!==1||!saved.session||typeof saved.session.state!=='string')throw Error('连续相机会话记录损坏');
   this.state=saved.session;
   if(live.has(this.state.state)){this.state.state='interrupted';this.state.error='服务曾在采集中退出；设备不会自动重开，缓存帧不恢复';this.state.endedAt=Date.now();this.persist();}
  }
 }
 get busy(){return !!this.child;}
 status(){return {...structuredClone(this.state),active:this.busy,buffered:!!this.latest,waiting:!!this.waiter,frameAgeMs:this.latest?Math.max(0,Date.now()-this.latest.at):null};}
 persist(){fs.mkdirSync(path.dirname(this.file),{recursive:true});const temp=this.file+'.tmp';fs.writeFileSync(temp,JSON.stringify({version:1,session:this.state}));fs.renameSync(temp,this.file);}
 start(body){
  if(this.busy)throw Error('连续相机会话正在运行，请先停止');
  const config=settings(body),resource={kill:()=>this.child?.kill()},release=this.resources.reserve(config.params,resource);
  const previous=this.state;
  this.state={id:crypto.randomUUID(),state:'opening',config,startedAt:Date.now(),endedAt:null,sequence:0,received:0,consumed:0,reused:0,overwritten:0,reconnects:0,lastFrameAt:null,error:''};this.latest=null;this.lastConsumed=0;
  try{this.persist();}catch(error){this.state=previous;release();throw error;}
  const local=path.join(root,'.venv',process.platform==='win32'?'Scripts/python.exe':'bin/python');
  let child;
  try{child=spawn(process.env.VISION_PYTHON||(fs.existsSync(local)?local:'python3'),['-X','utf8','-u',path.join(root,'cameras/session_worker.py')],{cwd:root,windowsHide:true});}catch(error){release();this.state.state='failed';this.state.error=error.message;this.persist();throw error;}
  this.child=child;let resolveClosed;this.closed=new Promise(r=>resolveClosed=r);
  let output='',bytes=0,logs='',lastSaved=Date.now();const decoder=new StringDecoder('utf8');
  const heartbeat=()=>{clearTimeout(this.watchdog);const wait=this.state.state==='reconnecting'?config.reconnectMs:this.state.state==='running'?config.intervalMs:0;this.watchdog=setTimeout(()=>this.fail('相机驱动长时间无响应，已结束会话；未自动重开设备'),(config.params.timeoutMs??5000)+wait+2500);};
  child.stderr.on('data',b=>{logs=(logs+b.toString()).slice(-2000);});
  child.stdin.on('error',error=>{if(this.state.state!=='stopping')this.fail('相机控制通道错误：'+error.message);});
  child.on('error',error=>this.fail('连续相机进程启动失败：'+error.message));
  child.stdout.on('data',chunk=>{
   if(this.child!==child||['stopping','failed'].includes(this.state.state))return;
   try{
    output+=decoder.write(chunk);bytes+=chunk.length;
    let newline;
    while((newline=output.indexOf('\n'))>=0){
     const line=output.slice(0,newline);output=output.slice(newline+1);bytes=Buffer.byteLength(output);
     if(Buffer.byteLength(line)>35_000_000)throw Error('相机帧超过 35 MB');
     const message=JSON.parse(line);
     if(message.event==='reconnecting'){
      this.latest=null;this.state.state='reconnecting';this.state.reconnects=message.attempt;this.state.error=String(message.error||'设备断开').slice(0,2000);this.persist();
     }else if(message.event==='error')throw Error(String(message.error||'采集失败'));
     else if(message.event==='frame'){
      const data=message.data;if(!data||!data.result||typeof data.result!=='object')throw Error('相机输出帧结构无效');
      frame({image:data.annotatedImage,cloud:data.cloud,depth:data.depth});
      if(this.latest&&this.latest.sequence>this.lastConsumed)this.state.overwritten++;
      const at=Date.now(),sequence=++this.state.sequence;
      this.latest={data,at,sequence};this.state.received++;this.state.lastFrameAt=at;
      const changed=this.state.state!=='running';this.state.state='running';this.state.error='';
      if(changed||at-lastSaved>=5000){this.persist();lastSaved=at;}
      if(this.waiter){const waiter=this.waiter;this.waiter=null;waiter.resolve(this.deliver('next'));}
     }else throw Error('未知相机会话消息');
     heartbeat();
    }
    if(bytes>35_000_000)throw Error('相机会话帧未结束或超过限制');
   }catch(error){this.fail(error.message);}
  });
  child.on('close',code=>{
   if(this.child!==child)return;
   clearTimeout(this.watchdog);clearTimeout(this.killTimer);this.child=null;release();this.latest=null;
   if(this.state.state==='stopping')this.state.state='stopped';
   else if(this.state.state!=='failed'){this.state.state='failed';this.state.error='相机进程退出 ('+code+')'+(logs?'：'+logs:'');}
   this.state.endedAt=Date.now();this.rejectWaiter(Error(this.state.error||'连续相机已停止'));
   try{this.persist();}catch(error){this.state.state='failed';this.state.error='会话记录写入失败：'+error.message;}
   resolveClosed(this.status());
  });
  heartbeat();child.stdin.write(JSON.stringify(config)+'\n');return this.status();
 }
 rejectWaiter(error){const waiter=this.waiter;this.waiter=null;waiter?.reject(error);}
 fail(message){
  if(!this.child||this.state.state==='stopping')return;
  this.state.state='failed';this.state.error=String(message).slice(0,2000);this.latest=null;clearTimeout(this.watchdog);
  this.rejectWaiter(Error(this.state.error));this.child.kill();
 }
 deliver(policy){
  const latest=this.latest;if(!latest)throw Error('连续相机尚无有效图像');
  const reused=latest.sequence<=this.lastConsumed;
  this.state.consumed++;if(reused)this.state.reused++;this.lastConsumed=latest.sequence;
  return {...structuredClone(latest.data),result:{...structuredClone(latest.data.result),sessionId:this.state.id,frameSequence:latest.sequence,frameAgeMs:Math.max(0,Date.now()-latest.at),framePolicy:policy,reusedFrame:reused}};
 }
 async capture(params,{signal}={}){
  if(!params||typeof params!=='object'||Object.keys(params).some(k=>!['driver','sessionId','framePolicy','maxAgeMs','timeoutMs'].includes(k))||params.driver!=='session')throw Error('连续相机读取参数无效');
  if(typeof params.sessionId!=='string'||params.sessionId!==this.state.id)throw Error('连续相机会话不存在或编号已变化，请重新选择当前会话');
  const policy=params.framePolicy??'next',age=integer(params.maxAgeMs??1000,'最大缓存帧龄 (ms)',1,60000),timeout=integer(params.timeoutMs??5000,'等待图像超时 (ms)',100,30000);
  if(!['next','latest'].includes(policy))throw Error('缓存读取策略无效');
  if(signal?.aborted)throw Error('采集已取消');
  if(!this.child||!['opening','running','reconnecting'].includes(this.state.state))throw Error(this.state.error||'连续相机未运行，请先建立连接');
  if(this.waiter)throw Error('已有采集请求在等待新帧，请稍后重试');
  if(policy==='latest'){
   if(!this.latest)throw Error('连续相机尚无有效图像');
   if(Date.now()-this.latest.at>age)throw Error('缓存图像过期，未交给检测算子');
   return this.deliver(policy);
  }
  return new Promise((resolve,reject)=>{
   const cleanup=()=>{clearTimeout(timer);signal?.removeEventListener('abort',cancel);if(this.waiter===waiter)this.waiter=null;};
   const waiter={resolve:value=>{cleanup();resolve(value);},reject:error=>{cleanup();reject(error);}};
   const cancel=()=>waiter.reject(Error('采集已取消；后台相机连接仍保持'));
   const timer=setTimeout(()=>waiter.reject(Error('等待连续相机新帧超时；后台连接仍保持')),timeout);
   this.waiter=waiter;signal?.addEventListener('abort',cancel,{once:true});
  });
 }
 async stop(id){
  if(id!==this.state.id)throw Error('连续相机会话编号已变化，请刷新');
  if(!this.child)return this.status();
  if(this.state.state!=='stopping'){
   this.state.state='stopping';clearTimeout(this.watchdog);this.latest=null;this.rejectWaiter(Error('连续相机正在停止'));
   this.child.stdin.end('stop\n');this.killTimer=setTimeout(()=>this.child?.kill(),(this.state.config.params.timeoutMs??5000)+2000);
  }
  return this.closed;
 }
 async shutdown(){if(this.child)await this.stop(this.state.id);}
}
module.exports={CameraSession,settings};
