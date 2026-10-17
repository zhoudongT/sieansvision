'use strict';
const {spawn}=require('node:child_process');
const fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'..');
let child=null,info=null,starting=null;
function status(){return {running:!!child&&child.exitCode===null&&!!info,starting:!!starting,...(info||{})};}
function start(){
 if(status().running)return Promise.resolve(status());
 if(starting)return starting;
 const local=path.join(root,'.venv',process.platform==='win32'?'Scripts/python.exe':'bin/python');
 const python=process.env.VISION_PYTHON||(fs.existsSync(local)?local:'python3');
 starting=new Promise((resolve,reject)=>{
  const process=spawn(python,['-X','utf8','-u',path.join(root,'industrial/s7_simulator.py')],{cwd:root,windowsHide:true});child=process;let out='',errors='',settled=false;
  const finish=error=>{if(settled)return;settled=true;clearTimeout(timer);if(error){process.kill();reject(error);}else resolve(status());};
  const timer=setTimeout(()=>finish(Error('S7 模拟器启动超时')),10000);
  process.stdout.on('data',data=>{out+=data;const at=out.indexOf('\n');if(at>=0&&!settled){try{const value=JSON.parse(out.slice(0,at));if(!value.ready||value.host!=='127.0.0.1'||!Number.isInteger(value.port)||value.port<1||value.port>65535)throw Error('模拟器启动响应无效');info=value;finish();}catch(error){finish(error);}}});
  process.stderr.on('data',data=>errors=(errors+data).slice(-2000));
  process.on('error',finish);process.stdin.on('error',finish);
  process.on('close',code=>{if(child===process){child=null;info=null;}finish(Error('模拟器已退出 '+code+'：'+errors));});
 }).finally(()=>starting=null);
 return starting;
}
async function stop(){
 if(starting)try{await starting;}catch{}
 const process=child;if(!process)return status();
 await new Promise(resolve=>{const timer=setTimeout(()=>process.kill(),1000);process.once('close',()=>{clearTimeout(timer);resolve();});process.stdin.end();});
 return status();
}
module.exports={status,start,stop};

