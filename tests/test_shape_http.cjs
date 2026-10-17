'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),os=require('node:os'),net=require('node:net');
const {spawn}=require('node:child_process'),{once}=require('node:events');
const root=path.resolve(__dirname,'..'),data=fs.mkdtempSync(path.join(os.tmpdir(),'sieans-shape-http-'));let server,logs='',port;
const delay=ms=>new Promise(resolve=>setTimeout(resolve,ms));
async function start(){logs='';server=spawn(process.execPath,['server.cjs'],{cwd:root,windowsHide:true,stdio:['ignore','pipe','pipe','ipc'],env:{...process.env,PORT:String(port),HOST:'127.0.0.1',MACHINE_DATA_DIR:data,ADMIN_PASSWORD_HASH:'',OPERATOR_PASSWORD_HASH:''}});server.stdout.on('data',b=>logs+=b);server.stderr.on('data',b=>logs+=b);for(let i=0;i<200&&!logs.includes('http://127.0.0.1:'+port);i++){if(server.exitCode!==null)throw Error(logs);await delay(100);}assert(logs.includes('http://127.0.0.1:'+port),logs);}
async function stop(){if(server?.exitCode===null){const exited=once(server,'exit');server.send({type:'sieans-shutdown'});await Promise.race([exited,delay(15000)]);assert.notEqual(server.exitCode,null,'owned server should stop');}}
async function json(route,method='GET',body){const r=await fetch('http://127.0.0.1:'+port+'/api/vision/'+route,{method,headers:{'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body),signal:AbortSignal.timeout(15000)});return {status:r.status,body:await r.json()};}
async function execute(project,image){const r=await json('runtime/jobs','POST',{project,image});assert.equal(r.status,202,r.body.error);for(let i=0;i<500;i++){const job=(await json('runtime/jobs/'+r.body.id)).body;if(job.state!=='running')return job;await delay(30);}throw Error('job timeout');}
async function main(){
 const listener=net.createServer();listener.listen(0,'127.0.0.1');await once(listener,'listening');port=listener.address().port;await new Promise(resolve=>listener.close(resolve));await start();
 const plugin=(await json('plugins')).body.plugins.find(p=>p.id==='sieans-shape');assert.equal(plugin.enabled,true);assert.equal(plugin.operators.length,2);
 const op=plugin.operators.find(o=>o.id==='match');assert.equal(op.parameters.find(p=>p.key==='model').type,'object');assert.equal(op.parameters.find(p=>p.key==='checkHoles').type,'boolean');assert.equal(op.outputs.find(o=>o.key==='items').type,'array');
 const demos=JSON.parse(fs.readFileSync(path.join(root,'public/vision/samples/demos-shape.json'))),demo=demos[0];
 const project={version:1,id:'shape-http',name:demo.name,hmi:structuredClone(demo.hmi),steps:demo.steps.map((s,i)=>({...s,id:'s'+i}))},image='data:image/png;base64,'+fs.readFileSync(path.join(root,'public/vision/samples',demo.image)).toString('base64');
 for(const b of demo.hmiBindings)project.hmi.components[b.component].binding.nodeId='s'+b.step;
 assert.equal((await json('project','PUT',project)).status,200);let saved=(await json('project')).body,job=await execute(saved,image);assert.equal(job.state,'completed',job.error);assert.equal(job.variables.flow.shapeCount,3);assert.equal(job.variables.flow.shapeOK,true);assert.equal(job.results[1].output.result.items.length,4);
 const model=job.variables.flow.silhouette;assert.equal((await json('history/'+job.id)).body.results[1].output.result.count,3);
 const page=await fetch('http://127.0.0.1:'+port+'/vision/samples/demos-shape.json');assert.equal(page.status,200);assert.equal((await page.json()).length,5);
 await stop();await start();saved=(await json('project')).body;assert.equal(saved.steps[1].params.arguments.model.$ref,'flow.silhouette');assert.equal(saved.hmi.components[3].binding.path,'items');assert.deepEqual((await json('runtime/view','POST',{project:saved})).body.variables.flow.silhouette,model);
 const reuse={...structuredClone(saved),version:1,steps:[{...structuredClone(saved.steps[1]),params:{...structuredClone(saved.steps[1].params),arguments:{model:{$ref:'flow.silhouette'},roiX:200,minimumCount:3,maximumCount:3}}}],edges:[]};
 job=await execute(reuse,image);assert.equal(job.state,'completed',job.error);assert.equal(job.results[0].output.result.count,3);
 const invalid=structuredClone(saved);invalid.steps[1].params.arguments.model={kind:'invalid'};job=await execute(invalid,image);assert.equal(job.state,'failed');assert.match(job.error,/轮廓建模/);assert.deepEqual((await json('runtime/view','POST',{project:saved})).body.variables.flow.silhouette,model);
 console.log('PASS silhouette HTTP: discover/form metadata, real teach/match, HMI table, saved model/history, restart reuse and invalid model rollback');
}
main().catch(error=>{console.error(error);process.exitCode=1;}).finally(stop);
