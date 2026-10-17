const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),os=require('node:os');
const {spawn}=require('node:child_process'),{once}=require('node:events');
const root=path.resolve(__dirname,'..'),data=fs.mkdtempSync(path.join(os.tmpdir(),'sieans-rigid-http-')),port=Number(process.env.SIEANS_TEST_HTTP_PORT||1920);
let server,logs='';const delay=ms=>new Promise(r=>setTimeout(r,ms));
async function start(){logs='';server=spawn(process.execPath,['server.cjs'],{cwd:root,windowsHide:true,stdio:['ignore','pipe','pipe','ipc'],env:{...process.env,PORT:String(port),HOST:'127.0.0.1',MACHINE_DATA_DIR:data,ADMIN_PASSWORD_HASH:''}});server.stdout.on('data',b=>logs+=b);server.stderr.on('data',b=>logs+=b);for(let i=0;i<150&&!logs.includes('http://127.0.0.1:'+port);i++){if(server.exitCode!==null)throw Error(logs);await delay(100);}assert(logs.includes('http://127.0.0.1:'+port),logs);}
async function stop(){if(server?.exitCode===null){const exited=once(server,'exit');server.send({type:'sieans-shutdown'});await Promise.race([exited,delay(8000)]);assert.notEqual(server.exitCode,null);}}
async function json(route,method='GET',body){const r=await fetch(`http://127.0.0.1:${port}/api/vision/${route}`,{method,headers:{'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body),signal:AbortSignal.timeout(60000)});return {status:r.status,body:await r.json()};}
async function execute(project,cloud){const r=await json('runtime/jobs','POST',{project,cloud});assert.equal(r.status,202,r.body.error);for(let i=0;i<400;i++){const j=(await json('runtime/jobs/'+r.body.id)).body;if(j.state!=='running')return j;await delay(30);}throw Error('job timeout');}
async function main(){
 await start();const samples=path.join(root,'public/vision/samples'),demos=JSON.parse(fs.readFileSync(path.join(samples,'demos-rigid.json'))),demo=demos[2],cloud=JSON.parse(fs.readFileSync(path.join(samples,demo.cloud)));
 const registry=(await json('plugins')).body.plugins.find(p=>p.id==='sieans-rigid');assert.equal(registry.enabled,true);assert.equal(registry.operators.length,4);assert.equal(registry.operators[0].parameters.find(f=>f.key==='pairs').columns.length,6);
 const project={version:1,id:'rigid-http',name:demo.name,steps:demo.steps.map((s,i)=>({...s,id:'n'+i}))};
 assert.equal((await json('project','PUT',project)).status,200);let saved=(await json('project')).body;
 let job=await execute(saved,cloud);assert.equal(job.state,'completed',job.error);assert.equal(job.results[1].output.cloud.frame,'fixture-base');assert(Math.abs(job.results[2].output.result.sizeZ-100)<1e-8);
 const calibration=job.variables.flow.frameCalibration;assert.equal(calibration.sourceUnit,'mm');
 const invalid=structuredClone(saved);invalid.steps[1].params.arguments.calibration={...calibration,sourceFrame:'wrong'};
 job=await execute(invalid,cloud);assert.equal(job.state,'failed');assert.match(job.error,/坐标系/);
 await stop();await start();saved=(await json('project')).body;const view=(await json('runtime/view','POST',{project:saved})).body;assert.deepEqual(view.variables.flow.frameCalibration,calibration);
 job=await execute(saved,cloud);assert.equal(job.state,'completed',job.error);
 console.log('PASS: HTTP four-operator discovery, six-column point forms, project/rigid-model persistence, variable-bound cloud conversion, actual Open3D dimensions, frame mismatch rejection and server restart');
}
main().catch(e=>{console.error(e,logs);process.exitCode=1;}).finally(()=>stop().catch(e=>{console.error(e);process.exitCode=1;}));
