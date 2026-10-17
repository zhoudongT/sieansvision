'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),os=require('node:os'),{spawn}=require('node:child_process'),{once}=require('node:events');
const root=path.resolve(__dirname,'..'),port=Number(process.env.SIEANS_TEST_HTTP_PORT||1914),data=fs.mkdtempSync(path.join(os.tmpdir(),'sieans-subflow-http-'));
const server=spawn(process.execPath,['server.cjs'],{cwd:root,windowsHide:true,stdio:['ignore','pipe','pipe','ipc'],env:{...process.env,PORT:String(port),HOST:'127.0.0.1',MACHINE_DATA_DIR:data,ADMIN_PASSWORD_HASH:''}});
let logs='';server.stdout.on('data',b=>logs+=b);server.stderr.on('data',b=>logs+=b);const delay=ms=>new Promise(r=>setTimeout(r,ms));
async function json(route,method='GET',body){const r=await fetch('http://127.0.0.1:'+port+'/api/vision/'+route,{method,headers:{'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body),signal:AbortSignal.timeout(60000)});return {status:r.status,body:await r.json()};}
async function execute(project,input={}){const started=await json('runtime/jobs','POST',{project,...input});assert.equal(started.status,202,started.body.error);let job=started.body;for(let i=0;i<600&&job.state==='running';i++){await delay(50);job=(await json('runtime/jobs/'+job.id)).body;}return job;}
async function main(){
 for(let i=0;i<150&&!logs.includes('http://127.0.0.1:'+port);i++){if(server.exitCode!==null)throw Error(logs);await delay(100);}assert.ok(logs.includes('http://127.0.0.1:'+port),logs);
 const demos=JSON.parse(fs.readFileSync(path.join(root,'public/vision/samples/demos.json'),'utf8')).filter(d=>d.id.startsWith('subflow-')||d.id.startsWith('loop-'));
 for(const demo of demos){
  const steps=demo.steps.map((s,i)=>({...s,id:'n'+i,params:structuredClone(s.params)}));for(const b of demo.bindings||[])steps[b.step].params[b.param]={$ref:'results.n'+b.source+'.'+b.field};const project={version:demo.connections?2:1,id:demo.id,name:demo.name,steps,subflows:demo.subflows,...(demo.connections?{edges:demo.connections.map(([from,to,when],i)=>({id:'e'+i,from:from<0?'source':'n'+from,to:'n'+to,...(when?{when}:{})}))}:{})};
  assert.equal((await json('project','PUT',project)).status,200);const saved=(await json('project')).body;assert.equal(saved.subflows.length,1);assert.equal(saved.steps[0].operation,steps[0].operation);
  const input=demo.cloud?{cloud:JSON.parse(fs.readFileSync(path.join(root,'public/vision/samples',demo.cloud),'utf8'))}:{image:'data:image/png;base64,'+fs.readFileSync(path.join(root,'public/vision/samples',demo.image)).toString('base64')};const job=await execute(saved,input);assert.equal(job.state,'completed',job.error);
  if(demo.id==='subflow-reuse'){assert.equal(job.variables.flow.count,3);assert.equal(job.results[0].output.result.trace.length,2);}
  if(demo.id==='loop-until'){assert.equal(job.variables.flow.rounds,3);assert.equal(job.results[0].output.result.stoppedEarly,true);}
  if(demo.id==='loop-limit'){assert.equal(job.variables.flow.alarm,true);assert.equal(job.results[0].handled,true);assert.equal(job.variables.modules.n0._subflow,undefined);}
  if(demo.id==='loop-cloud'){assert.equal(job.variables.flow.width,20);assert.equal(job.results[0].output.result.iterations.length,3);}
 }
 const script={version:1,id:'script-subflow',name:'Script nested',steps:[{id:'call',operation:'subflow',params:{subflowId:'python'}}],subflows:[{version:1,id:'python',name:'Python',steps:[{id:'script',operation:'script',params:{code:'def run(ctx):\n    return {"result": {"value": 7}, "variables": {"global": {"nested": 7}}}'}}],outputNode:'script'}]};
 assert.equal((await json('runtime/jobs','POST',{project:script})).status,400);const job=await execute(script,{allowScripts:true});assert.equal(job.state,'completed',job.error);assert.equal(job.variables.global.nested,7);assert.equal(job.results[0].output.result.value.value,7);
 console.log('PASS: reusable 2D inspection, bounded until loop, exhausted-loop recovery, real Open3D loop, persisted definitions and nested Python trust/variables');
}
main().catch(error=>{console.error(error,logs);process.exitCode=1;}).finally(async()=>{if(server.exitCode===null){server.send({type:'sieans-shutdown'});await Promise.race([once(server,'exit'),delay(5000)]);if(server.exitCode===null)server.kill();}});
