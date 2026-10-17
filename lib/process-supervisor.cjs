'use strict';
// These deadlines cover the camera's 30 s read + 2 s worker termination,
// followed by history, protocol and Node-RED shutdown. Only our spawned child
// is signalled; no PID lookup or attachment to unrelated services is allowed.
const SHUTDOWN_GRACE_MS=45000,SERVICE_STOP_SECONDS=60,PREVIEW_STOP_MS=50000;
async function supervise(child,{graceMs=SHUTDOWN_GRACE_MS,control=process}={}){
 if(!Number.isInteger(graceMs)||graceMs<1||graceMs>60000)throw Error('停止等待时间无效');
 let stopping=false,timer;
 const stop=()=>{
  if(stopping||child.exitCode!==null||child.signalCode!==null)return;
  stopping=true;
  if(child.connected)child.send({type:'sieans-shutdown'},()=>{});
  timer=setTimeout(()=>child.kill('SIGKILL'),graceMs);timer.unref();
 };
 const message=m=>{if(m?.type==='sieans-shutdown')stop();};
 control.once('SIGINT',stop);control.once('SIGTERM',stop);
 if(control.send){control.on('message',message);control.once('disconnect',stop);}
 try{
  await new Promise((resolve,reject)=>{
   child.once('error',reject);child.once('exit',(code,signal)=>code===0?resolve():reject(Error('服务退出：'+(code??signal))));
  });
 }finally{
  clearTimeout(timer);control.removeListener('SIGINT',stop);control.removeListener('SIGTERM',stop);control.removeListener('message',message);control.removeListener('disconnect',stop);
  if(control.connected)control.disconnect();
 }
}
module.exports={supervise,SHUTDOWN_GRACE_MS,SERVICE_STOP_SECONDS,PREVIEW_STOP_MS};
