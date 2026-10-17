'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),os=require('node:os'),net=require('node:net');
const {spawn}=require('node:child_process'),{once}=require('node:events');
const root=path.resolve(__dirname,'..'),data=fs.mkdtempSync(path.join(os.tmpdir(),'sieans-circle-http-'));let server,logs='',port;
const delay=ms=>new Promise(resolve=>setTimeout(resolve,ms));
async function start(){logs='';server=spawn(process.execPath,['server.cjs'],{cwd:root,windowsHide:true,stdio:['ignore','pipe','pipe','ipc'],env:{...process.env,PORT:String(port),HOST:'127.0.0.1',MACHINE_DATA_DIR:data,ADMIN_PASSWORD_HASH:''}});server.stdout.on('data',b=>logs+=b);server.stderr.on('data',b=>logs+=b);for(let i=0;i<150&&!logs.includes('http://127.0.0.1:'+port);i++){if(server.exitCode!==null)throw Error(logs);await delay(100);}assert(logs.includes('http://127.0.0.1:'+port),logs);}
async function stop(){if(server?.exitCode===null){const exited=once(server,'exit');server.send({type:'sieans-shutdown'});await Promise.race([exited,delay(10000)]);assert.notEqual(server.exitCode,null,'owned server should stop');}}
async function json(route,method='GET',body){const r=await fetch('http://127.0.0.1:'+port+'/api/vision/'+route,{method,headers:{'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body),signal:AbortSignal.timeout(15000)});return {status:r.status,body:await r.json()};}
async function execute(project,image){const r=await json('runtime/jobs','POST',{project,image});assert.equal(r.status,202,r.body.error);for(let i=0;i<400;i++){const job=(await json('runtime/jobs/'+r.body.id)).body;if(job.state!=='running')return job;await delay(30);}throw Error('job timeout');}
async function main(){
 const listener=net.createServer();listener.listen(0,'127.0.0.1');await once(listener,'listening');port=listener.address().port;await new Promise(resolve=>listener.close(resolve));await start();
 const plugin=(await json('plugins')).body.plugins.find(p=>p.id==='sieans-circle');assert.equal(plugin.enabled,true);assert.equal(plugin.operators.length,2);
 const op=plugin.operators.find(o=>o.id==='caliper');assert.equal(op.parameters.find(p=>p.key==='polarity').choices.length,3);assert.equal(op.parameters.find(p=>p.key==='probeCount').type,'integer');assert.equal(op.outputs.find(o=>o.key==='items').type,'array');assert.equal(op.outputs.find(o=>o.key==='circle').required,false);
 const demos=JSON.parse(fs.readFileSync(path.join(root,'public/vision/samples/demos-circle.json'))),demo=demos[5];
 const project={version:1,id:'circle-http',name:demo.name,hmi:structuredClone(demo.hmi),steps:demo.steps.map((s,i)=>({...s,id:'c'+i}))},image='data:image/png;base64,'+fs.readFileSync(path.join(root,'public/vision/samples',demo.image)).toString('base64');
 for(const b of demo.hmiBindings)project.hmi.components[b.component].binding.nodeId='c'+b.step;
 assert.equal((await json('project','PUT',project)).status,200);const saved=(await json('project')).body;let job=await execute(saved,image);assert.equal(job.state,'completed',job.error);assert.equal(job.variables.flow.ringOK,true);assert(job.variables.flow.centerOffset<.12);assert.equal(job.results[2].output.image,image);
 const model=job.variables.flow.innerCircle;const history=(await json('history/'+job.id)).body;assert.equal(history.results[2].output.result.passed,true);
 await stop();await start();const restored=(await json('project')).body;assert.equal(restored.hmi.components[3].binding.nodeId,'c2');assert.equal(restored.hmi.components[3].binding.path,'items');assert.equal(restored.steps[2].params.arguments.innerCircle.$ref,'flow.innerCircle');assert.deepEqual((await json('runtime/view','POST',{project:restored})).body.variables.flow.innerCircle,model);
 job=await execute(restored,image);assert.equal(job.state,'completed',job.error);
 const mismatch=structuredClone(restored);mismatch.steps[2].params.arguments.outerCircle={...job.variables.flow.outerCircle,imageSha256:'0'.repeat(64)};job=await execute(mismatch,image);assert.equal(job.state,'failed');assert.match(job.error,/同一原始图像/);assert.equal((await json('runtime/view','POST',{project:restored})).body.variables.flow.ringOK,true);
 console.log('PASS circle HTTP: two-operator form metadata, 3-node image pipeline, circle/model bindings, table results/history, saved project, persistent models, service restart, cross-image refusal and rollback');
}
main().catch(error=>{console.error(error,logs);process.exitCode=1;}).finally(()=>stop().catch(error=>{console.error(error);process.exitCode=1;}));
