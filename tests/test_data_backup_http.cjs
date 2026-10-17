'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),os=require('node:os'),net=require('node:net');
const {fork}=require('node:child_process'),{once}=require('node:events');
const platform=require('../scripts/platform.cjs'),{maintenance}=require('../lib/data-backup.cjs'),graph=require('../public/vision/flow-graph.js');
const root=path.resolve(__dirname,'..'),temp=fs.mkdtempSync(path.join(os.tmpdir(),'sieans-backup-http-')),data=path.join(temp,'source'),models=path.join(temp,'external-models');
const python=process.env.VISION_PYTHON||path.join(root,'.venv',process.platform==='win32'?'Scripts/python.exe':'bin/python');
let current,port,logs='';const delay=ms=>new Promise(resolve=>setTimeout(resolve,ms));
async function until(check,label){const end=Date.now()+30000;while(Date.now()<end){if(await check())return;await delay(100);}throw Error('Timed out '+label+'\n'+logs);}
async function request(route,method='GET',body){const r=await fetch('http://127.0.0.1:'+port+'/api/vision/'+route,{method,headers:{'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body),signal:AbortSignal.timeout(3000)});return {status:r.status,body:await r.json()};}
async function start(directory){const config=JSON.parse(fs.readFileSync(path.join(directory,'deployment.json'),'utf8'));current=fork(path.join(root,'server.cjs'),[],{cwd:root,windowsHide:true,stdio:['ignore','pipe','pipe','ipc'],env:platform.runtimeEnv(directory,config)});current.done=new Promise(resolve=>current.once('exit',code=>resolve(code)));current.stdout.on('data',b=>logs+=b);current.stderr.on('data',b=>logs+=b);await until(async()=>{if(current.exitCode!==null)throw Error(logs);try{return (await request('version')).status===200;}catch{return false;}},'server');}
async function stop(){if(!current)return;const child=current;child.send({type:'sieans-shutdown'});await until(()=>child.exitCode!==null,'shutdown');assert.equal(await child.done,0);current=null;}
async function execute(project){const r=await request('runtime/jobs','POST',{project,allowScripts:true});assert.equal(r.status,202,JSON.stringify(r));let job;await until(async()=>{job=(await request('runtime/jobs/'+r.body.id)).body;return job.state!=='running';},'job');assert.equal(job.state,'completed',JSON.stringify(job));return job;}
async function main(){
 const listener=net.createServer();listener.listen(0,'127.0.0.1');await once(listener,'listening');port=listener.address().port;await new Promise(resolve=>listener.close(resolve));
 platform.configure({'data-dir':data,python,features:'core',port:String(port),'models-dir':models});fs.writeFileSync(path.join(models,'backup-path.onnx'),'listing-fixture');
 await start(data);
 const project=graph.normalize({version:1,id:'backup-persistence',name:'备份恢复验收',variables:{count:0},variableTypes:{count:'integer'},steps:[{id:'increment',operation:'script',params:{code:'def run(ctx):\n    return dict(result=dict(count=ctx["vars"]["flow"]["count"]+1))\n',outputBindings:[{field:'count',scope:'flow',name:'count'}]}}]});
 assert.equal((await request('project','PUT',project)).status,200);const first=await execute(project);assert.equal(first.variables.flow.count,1);
 const created=await request('training/datasets','POST',{id:'backup-parts',task:'detect',names:['part'],demo:true});assert.equal(created.status,201,JSON.stringify(created));
 const annotation=(await request('training/datasets/backup-parts/annotations/load','POST',{name:'part-0.png',split:'train'})).body;assert.equal(annotation.records.length,1);
 const archive=path.join(temp,'complete.zip');await assert.rejects(maintenance({command:'backup','data-dir':data,output:archive,python},platform),/占用/);assert.equal(fs.existsSync(archive),false);
 await stop();const secret=fs.readFileSync(path.join(data,'.config.runtime.json'));
 const saved=await maintenance({command:'backup','data-dir':data,output:archive,python},platform);assert.equal(saved.models,'external');
 const target=path.join(temp,'restored');const restored=await maintenance({command:'restore','data-dir':target,archive,python},platform);assert.equal(restored.sha256,saved.sha256);assert.deepEqual(fs.readFileSync(path.join(target,'.config.runtime.json')),secret);
 await start(target);assert.equal((await request('project')).body.id,project.id);assert.equal((await request('history/'+first.id)).body.variables.flow.count,1);assert.equal((await execute(project)).variables.flow.count,2);
 assert((await request('models')).body.models.includes('backup-path.onnx'));
 const restoredAnnotation=(await request('training/datasets/backup-parts/annotations/load','POST',{name:'part-0.png',split:'train'})).body;assert.deepEqual(restoredAnnotation.records,annotation.records);assert.equal(restoredAnnotation.image,annotation.image);
 await stop();assert.equal(fs.existsSync(path.join(data,'.sieans-runtime.lock')),false);
 console.log('PASS backup HTTP: active lock refusal, saved project/variables/history, training images and labels, Node-RED credential secret, external model relocation, restored runtime increment. Data: '+temp);
}
main().catch(error=>{console.error(error,logs);process.exitCode=1;}).finally(async()=>{await stop();});
