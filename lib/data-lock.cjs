'use strict';
const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),crypto=require('node:crypto');
function acquire(directory){
 const marker=path.join(directory,'.sieans-restore-incomplete');
 const check=()=>{if(fs.existsSync(marker))throw Error('数据恢复尚未完成，拒绝启动或备份：'+marker);};check();
 fs.mkdirSync(directory,{recursive:true});const file=path.join(directory,'.sieans-runtime.lock');
 const owner={pid:process.pid,host:os.hostname(),token:crypto.randomUUID(),createdAt:new Date().toISOString()};
 for(let attempt=0;attempt<2;attempt++){
  try{fs.writeFileSync(file,JSON.stringify(owner),{flag:'wx',mode:0o600});try{check();}catch(error){fs.unlinkSync(file);throw error;}return ()=>{try{if(JSON.parse(fs.readFileSync(file,'utf8')).token===owner.token)fs.unlinkSync(file);}catch{}};}
  catch(error){
   if(error.code!=='EEXIST')throw error;
   const recovery=file+'.recovery';let guard;
   try{guard=fs.openSync(recovery,'wx',0o600);}catch{throw Error('运行目录正在恢复或恢复被中断，请检查锁：'+recovery);}
   try{
    if(!fs.existsSync(file))continue;
    let previous;try{previous=JSON.parse(fs.readFileSync(file,'utf8'));}catch{throw Error('运行目录锁损坏，请确认没有运行中的服务后处理：'+file);}
    if(previous.host!==os.hostname()||!Number.isSafeInteger(previous.pid)||previous.pid<=0)throw Error('运行目录由其他主机或未知进程占用：'+directory);
    let alive=true;try{process.kill(previous.pid,0);}catch(e){if(e.code==='ESRCH')alive=false;}
    if(alive)throw Error('运行目录已被服务占用（PID '+previous.pid+'）：'+directory);
    // Serialize recovery, re-reading under the guard so another starter's live lock cannot be moved.
    fs.renameSync(file,file+'.stale-'+crypto.randomUUID());
   }finally{fs.closeSync(guard);fs.unlinkSync(recovery);}
  }
 }
 throw Error('无法取得运行目录锁，请重试');
}
module.exports={acquire};
