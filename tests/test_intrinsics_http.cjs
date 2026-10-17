const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),os=require('node:os');
const {spawn}=require('node:child_process'),{once}=require('node:events');
const root=path.resolve(__dirname,'..'),data=fs.mkdtempSync(path.join(os.tmpdir(),'sieans-intrinsics-http-')),port=Number(process.env.SIEANS_TEST_HTTP_PORT||1920);
let server,logs='';const delay=ms=>new Promise(r=>setTimeout(r,ms));
async function start(){logs='';server=spawn(process.execPath,['server.cjs'],{cwd:root,windowsHide:true,stdio:['ignore','pipe','pipe','ipc'],env:{...process.env,PORT:String(port),HOST:'127.0.0.1',MACHINE_DATA_DIR:data,ADMIN_PASSWORD_HASH:''}});server.stdout.on('data',b=>logs+=b);server.stderr.on('data',b=>logs+=b);for(let i=0;i<150&&!logs.includes('http://127.0.0.1:'+port);i++){if(server.exitCode!==null)throw Error(logs);await delay(100);}assert(logs.includes('http://127.0.0.1:'+port),logs);}
async function stop(){if(server?.exitCode===null){const exited=once(server,'exit');server.send({type:'sieans-shutdown'});await Promise.race([exited,delay(7000)]);assert.notEqual(server.exitCode,null,'Owned HTTP server must exit');}}
async function json(route,method='GET',body){const r=await fetch(`http://127.0.0.1:${port}/api/vision/${route}`,{method,headers:{'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body),signal:AbortSignal.timeout(60000)});return {status:r.status,body:await r.json()};}
async function execute(project,image){const r=await json('runtime/jobs','POST',{project,image});assert.equal(r.status,202,r.body.error);for(let i=0;i<400;i++){const j=await json('runtime/jobs/'+r.body.id);if(j.body.state!=='running')return j.body;await delay(30);}throw Error('job timeout');}
async function main(){
 await start();const demos=JSON.parse(fs.readFileSync(path.join(root,'public/vision/samples/demos-intrinsics.json'))),demo=demos[2];
 const registry=(await json('plugins')).body.plugins.find(p=>p.id==='sieans-intrinsics');assert.equal(registry.enabled,true);assert.equal(registry.operators.length,3);
 const project={version:1,id:'intrinsics-http',name:demo.name,steps:demo.steps.map((s,i)=>({...s,id:'node'+i}))};
 const image='data:image/png;base64,'+fs.readFileSync(path.join(root,'public/vision/samples',demo.image)).toString('base64');
 assert.equal((await json('project','PUT',project)).status,200);let saved=(await json('project')).body;
 let job=await execute(saved,image);assert.equal(job.state,'completed',job.error);assert(Math.abs(job.variables.flow.cameraCalibration.fx-710)<.1);
 assert(job.results[1].output.annotatedImage.startsWith('data:image/png;base64,'));
 const bad=structuredClone(saved);bad.steps[1].params.arguments.calibration={...job.variables.flow.cameraCalibration,width:800};
 job=await execute(bad,image);assert.equal(job.state,'failed');assert.match(job.error,/尺寸/);
 await stop();await start();saved=(await json('project')).body;assert.equal(saved.steps[0].params.arguments.points.length,432);
 const view=(await json('runtime/view','POST',{project:saved})).body;assert(Math.abs(view.variables.flow.cameraCalibration.fx-710)<.1);
 job=await execute(saved,image);assert.equal(job.state,'completed',job.error);
 console.log('PASS: HTTP plugin discovery, forms metadata, saved 432-row table, intrinsic solve, variable-bound correction, invalid dimensions rejected, restart persistence and re-execution');
}
main().catch(e=>{console.error(e,logs);process.exitCode=1;}).finally(()=>stop().catch(e=>{console.error(e);process.exitCode=1;}));
