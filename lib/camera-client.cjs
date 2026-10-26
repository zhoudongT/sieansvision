'use strict';
const {spawn}=require('node:child_process'),fs=require('node:fs'),path=require('node:path');
const {StringDecoder}=require('node:string_decoder');
const {frame}=require('./frame.cjs');
const root=path.resolve(__dirname,'..'),active=new Map();
const operations=new Set(['camera_capture','camera_list','camera_inspect','camera_providers']);
const physicalDrivers=new Set(['uvc','gentl','realsense','orbbec']);
let sessions=null;

function reserve(params,resource){
 const key=['simulator','rgbd_simulator'].includes(params.driver)?'simulator':'physical';
 if(active.has(key))throw Error('相机采集或枚举正在进行，请等待完成');
 active.set(key,resource);return ()=>{if(active.get(key)===resource)active.delete(key);};
}

function canonical(value){
 return Array.isArray(value)?value.map(canonical):value&&typeof value==='object'?Object.fromEntries(Object.keys(value).sort().map(key=>[key,canonical(value[key])])):value;
}

/** Drop session-read keys so params can open/keep a long-lived GenTL/UVC session. */
function physicalParams(params){
 const skip=new Set(['sessionId','framePolicy','maxAgeMs']);
 const out={};
 for(const [key,value] of Object.entries(params||{})){
  if(!skip.has(key))out[key]=value;
 }
 return out;
}

function samePhysical(a,b){
 return JSON.stringify(canonical(physicalParams(a)))===JSON.stringify(canonical(physicalParams(b)));
}

/**
 * Freerun physical captures keep one SDK session open across flow runs.
 * First call opens the device; later calls grab from the live buffer (~tens of ms).
 * Software/external trigger stays one-shot (session rejects non-freerun).
 */
async function capturePersistent(params,{signal}={}){
 if(!sessions)throw Error('连续相机会话未初始化');
 const physical=physicalParams(params);
 if((physical.trigger||'freerun')!=='freerun')return null;
 let status=sessions.status();
 if(sessions.busy&&!samePhysical(status.config?.params,physical)){
  await sessions.stop(status.id);
  status=sessions.status();
 }
 if(!sessions.busy){
  sessions.start({
   params:physical,
   intervalMs:50,
   reconnectAttempts:2,
   reconnectMs:1000,
   autoStart:false,
  });
  status=sessions.status();
 }
 const sessionId=sessions.bindingId||status.id;
 // First frame after open: wait for next. Warm session: use latest cache (fast).
 // Prefer a fresh frame per flow run; still tens of ms once the SDK session is warm.
 const policy=params.framePolicy||'next';
 return sessions.capture({
  driver:'session',
  sessionId,
  framePolicy:policy,
  maxAgeMs:params.maxAgeMs??Math.max(params.timeoutMs??5000,1000),
  timeoutMs:params.timeoutMs??5000,
 },{signal});
}

async function run(request,{signal}={}){
 if(!request||!operations.has(request.operation)||!request.params||typeof request.params!=='object'||Array.isArray(request.params))throw Error('相机请求格式无效');
 if(request.params.driver==='session'){
  if(request.operation!=='camera_capture'||!sessions)throw Error('连续相机会话仅支持采集，请在相机管理中建立连接');
  return sessions.capture(request.params,{signal});
 }
 // Persist freerun GenTL/UVC/… across flow runs instead of open+grab+close each time.
 if(request.operation==='camera_capture'&&physicalDrivers.has(request.params.driver)&&sessions){
  const persistent=await capturePersistent(request.params,{signal});
  if(persistent)return persistent;
 }
 const timeout=request.params.timeoutMs??5000;
 if(!Number.isInteger(timeout)||timeout<100||timeout>30000)throw Error('相机超时必须为 100–30000 ms');
 const input=JSON.stringify(request);if(Buffer.byteLength(input)>100000)throw Error('相机参数超过 100 KB');
 if(signal?.aborted)throw Error('采集已取消');
 // Conservative process-wide lock prevents aliases/backends opening one camera twice.
 // Provider metadata only reads configured CTI paths; it never opens hardware.
 const key=request.operation==='camera_providers'?Symbol('providers'):['simulator','rgbd_simulator'].includes(request.params.driver)?'simulator':'physical';
 if(active.has(key))throw Error('相机采集或枚举正在进行，请等待完成');
 const local=path.join(root,'.venv',process.platform==='win32'?'Scripts/python.exe':'bin/python');
 return new Promise((resolve,reject)=>{
  const child=spawn(process.env.VISION_PYTHON||(fs.existsSync(local)?local:'python3'),['-X','utf8','-u',path.join(root,'cameras/worker.py')],{cwd:root,windowsHide:true});
  active.set(key,child);let output='',bytes=0,settled=false;const decoder=new StringDecoder('utf8');
  const finish=(error,data)=>{if(settled)return;settled=true;clearTimeout(timer);signal?.removeEventListener('abort',cancel);if(error){child.kill();reject(error);}else resolve(data);};
  const caution=request.operation==='camera_capture'?'；已发出的触发和相机参数修改不会回滚，未自动重试':'';
  const cancel=()=>finish(Error('采集已取消'+caution));
  const timer=setTimeout(()=>finish(Error('相机操作超时'+caution)),timeout+2000);
  signal?.addEventListener('abort',cancel,{once:true});
  child.stdout.on('data',data=>{bytes+=data.length;if(bytes>35_000_000)return finish(Error('相机输出超过 35 MB，请降低分辨率或增加点云采样步长'));output+=decoder.write(data);});
  child.stderr.resume();
  child.on('error',error=>finish(Error('相机进程启动失败：'+error.message)));
  child.stdin.on('error',error=>finish(error));
  child.on('close',code=>{if(active.get(key)===child)active.delete(key);if(settled)return;try{if(code!==0)throw Error('相机驱动进程异常退出'+caution);const response=JSON.parse(output+decoder.end());if(!response.ok)throw Error(response.error+caution);if(request.operation==='camera_capture'){const checked=frame({image:response.data.annotatedImage,cloud:response.data.cloud,depth:response.data.depth});response.data.cloud=checked.cloud;response.data.depth=checked.depth;}finish(null,response.data);}catch(error){finish(error);}});
  child.stdin.end(input);
 });
}
async function stop(){await sessions?.shutdown();for(const child of active.values())child.kill();}
module.exports={run,stop,operations,reserve,activeCount:()=>active.size,setSessions(value){sessions=value;},physicalParams,samePhysical};
