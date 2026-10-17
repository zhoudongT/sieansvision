'use strict';
const {spawn}=require('node:child_process');
const fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'..');
const children=new Set();
function run(code,context,{timeoutMs=5000,signal}={}){
  if(typeof code!=='string'||Buffer.byteLength(code)>100_000)return Promise.reject(Error('脚本必须是 100 KB 以内的字符串'));
  if(!Number.isInteger(timeoutMs)||timeoutMs<100||timeoutMs>30000)return Promise.reject(Error('脚本超时必须是 100–30000 ms'));
  if(signal?.aborted)return Promise.reject(Error('脚本已取消'));
  const local=path.join(root,'.venv',process.platform==='win32'?'Scripts/python.exe':'bin/python');
  const python=process.env.VISION_PYTHON||(fs.existsSync(local)?local:'python3');
  return new Promise((resolve,reject)=>{
    const child=spawn(python,['-I','-X','utf8','-u',path.join(root,'vision/script_worker.py')],{cwd:root,windowsHide:true,env:{...process.env,PYTHONIOENCODING:'utf-8'}});
    children.add(child);child.once('close',()=>children.delete(child));
    let output='',bytes=0,errors='',finished=false;
    const finish=(error,data)=>{if(finished)return;finished=true;clearTimeout(timer);signal?.removeEventListener('abort',cancel);if(error){child.kill();reject(error);}else resolve(data);};
    const cancel=()=>finish(Error('脚本已取消'));signal?.addEventListener('abort',cancel,{once:true});
    const timer=setTimeout(()=>finish(Error('Python 脚本执行超时（'+timeoutMs+' ms）')),timeoutMs);
    child.stdout.on('data',data=>{bytes+=data.length;if(bytes>2_000_000)return finish(Error('脚本输出超过 2 MB'));output+=data.toString('utf8');});
    child.stderr.on('data',data=>{errors=(errors+data.toString('utf8')).slice(-4000);});
    child.on('error',error=>finish(error));child.stdin.on('error',error=>finish(error));
    child.on('close',code=>{if(finished)return;try{if(code!==0)throw Error('脚本进程退出：'+errors);const response=JSON.parse(output);if(!response.ok)throw Error(response.error+'\n'+(response.trace||''));finish(null,response);}catch(error){finish(error);}});
    child.stdin.end(JSON.stringify({code,context}));
  });
}
module.exports={run,activeCount:()=>children.size};
