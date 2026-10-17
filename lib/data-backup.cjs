'use strict';
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const {spawn}=require('node:child_process');
const {acquire}=require('./data-lock.cjs');
const root=path.resolve(__dirname,'..'),markerName='.sieans-restore-incomplete';
function noLinks(value){
 const absolute=path.resolve(value);let current=absolute;
 for(;;){try{if(fs.lstatSync(current).isSymbolicLink())throw Error('不允许符号链接或目录联接：'+current);}catch(e){if(e.code!=='ENOENT')throw e;}const parent=path.dirname(current);if(parent===current)break;current=parent;}
 return absolute;
}
function worker(python,request,onProgress){
 return new Promise((resolve,reject)=>{
  const child=spawn(python,['-I','-X','utf8',path.join(root,'deploy/data_backup.py')],{stdio:['pipe','pipe','pipe'],windowsHide:true});
  let pending='',errorText='',result,reported,protocolError;
  const fail=message=>{protocolError=Error(message);child.kill();};
  child.stdout.setEncoding('utf8');child.stderr.setEncoding('utf8');
  child.stdout.on('data',chunk=>{
   pending+=chunk;if(pending.length>65536){fail('备份工作进程响应过大');return;}
   let end;while((end=pending.indexOf('\n'))>=0){const line=pending.slice(0,end);pending=pending.slice(end+1);if(!line.trim())continue;
    try{const row=JSON.parse(line);if(row.event==='result'){if(result)throw Error('重复结果');result=row.data;}else if(row.event==='error')reported=row.error;else if(row.event==='progress')onProgress?.(row);else throw Error('未知响应');}catch{fail('备份工作进程响应无效');return;}
   }
  });
  child.stderr.on('data',chunk=>{errorText=(errorText+chunk).slice(-2000);});
  child.once('error',reject);child.stdin.on('error',()=>{});
  child.once('close',code=>{if(protocolError)reject(protocolError);else if(code!==0||!result||pending.trim())reject(Error(reported||errorText||'备份工作进程失败'));else resolve(result);});
  child.stdin.end(JSON.stringify(request));
 });
}
async function maintenance(o,platform){
 const progress=row=>console.log(({backup:'正在备份',verify:'正在校验',restore:'正在恢复'}[row.phase]||row.phase)+'：'+row.files+' 个文件，'+row.bytes+' / '+row.totalBytes+' 字节');
 const fallback=path.join(root,'.venv',process.platform==='win32'?'Scripts/python.exe':'bin/python');
 if(o.command==='backup'){
  const data=noLinks(platform.directory(o['data-dir']));if(!fs.statSync(data).isDirectory())throw Error('数据来源必须为目录');
  if(!o.output)throw Error('备份需要 --output 指定新 ZIP 文件');noLinks(o.output);
  const deployment=path.join(data,'deployment.json');const config=fs.existsSync(deployment)?platform.validate(platform.readDeployment(deployment)):{};
  const python=platform.pythonInfo(o.python||config.python||fallback).executable;
  const release=acquire(data);
  try{return await worker(python,{action:'backup',data,output:path.resolve(o.output),models:o['models-dir']?path.resolve(o['models-dir']):config.models,programVersion:require('../package.json').version},progress);}finally{release();}
 }
 if(!o.archive)throw Error('请用 --archive 指定备份 ZIP');
 const archive=noLinks(o.archive),python=platform.pythonInfo(o.python||fallback).executable;
 const info=await worker(python,{action:'inspect',archive},progress);
 if(o.command==='backup-info')return info;
 const target=noLinks(platform.directory(o['data-dir']));
 if(fs.existsSync(target))throw Error('恢复目标必须是尚不存在的新目录：'+target);
 // mkdir without recursive creation of the leaf makes ownership unambiguous.
 fs.mkdirSync(path.dirname(target),{recursive:true,mode:0o700});noLinks(path.dirname(target));fs.mkdirSync(target,{mode:0o700});
 const release=acquire(target),marker=path.join(target,markerName),token=crypto.randomUUID();
 try{
  fs.writeFileSync(marker,JSON.stringify({token,archiveSha256:info.sha256,startedAt:new Date().toISOString()}),{flag:'wx',mode:0o600});
  const result=await worker(python,{action:'restore',archive,target,expectedSha256:info.sha256},progress);
  const original=path.join(target,'deployment.json');let old={};
  if(fs.existsSync(original)){old=platform.readDeployment(original);if(!old||old.version!==1)throw Error('备份部署配置版本无效');}
  const receiptDir=path.join(target,'.sieans-restore-'+token);fs.mkdirSync(receiptDir,{mode:0o700});
  if(fs.existsSync(original))fs.renameSync(original,path.join(receiptDir,'deployment-original.json'));
  // Old absolute paths may come from another OS. Validate the regenerated
  // configuration, retaining only portable user settings from the original.
  const portable={features:old.features,port:old.port,adminUser:old.adminUser,passwordHash:old.passwordHash,operatorUser:old.operatorUser,operatorPasswordHash:old.operatorPasswordHash};
  platform.configure({...o,'data-dir':target,'models-dir':result.modelsPath,host:o.host??'127.0.0.1'},python,portable);
  fs.writeFileSync(path.join(receiptDir,'receipt.json'),JSON.stringify({...result,completedAt:new Date().toISOString()},null,2)+'\n',{flag:'wx',mode:0o600});
  if(JSON.parse(fs.readFileSync(marker,'utf8')).token!==token)throw Error('恢复标记被修改，请人工检查目标目录');
  fs.unlinkSync(marker);return {...result,dataDirectory:target,serviceStarted:false};
 }catch(error){throw Error(error.message+'；恢复未完成，目标目录保留恢复标记，服务不会启动：'+target);}finally{release();}
}
module.exports={maintenance,worker,noLinks};
