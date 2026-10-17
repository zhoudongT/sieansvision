const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),os=require('node:os');
const {spawn}=require('node:child_process'),{once}=require('node:events');
const root=path.resolve(__dirname,'..'),data=fs.mkdtempSync(path.join(os.tmpdir(),'sieans-handeye-http-')),port=Number(process.env.SIEANS_TEST_HTTP_PORT||1920);
let server,logs='';const delay=ms=>new Promise(r=>setTimeout(r,ms));
async function start(){logs='';server=spawn(process.execPath,['server.cjs'],{cwd:root,windowsHide:true,stdio:['ignore','pipe','pipe','ipc'],env:{...process.env,PORT:String(port),HOST:'127.0.0.1',MACHINE_DATA_DIR:data,ADMIN_PASSWORD_HASH:''}});server.stdout.on('data',b=>logs+=b);server.stderr.on('data',b=>logs+=b);for(let i=0;i<150&&!logs.includes('http://127.0.0.1:'+port);i++){if(server.exitCode!==null)throw Error(logs);await delay(100);}assert(logs.includes('http://127.0.0.1:'+port),logs);}
async function stop(){if(server?.exitCode===null){const exited=once(server,'exit');server.send({type:'sieans-shutdown'});await Promise.race([exited,delay(8000)]);assert.notEqual(server.exitCode,null);}}
async function json(route,method='GET',body){const r=await fetch(`http://127.0.0.1:${port}/api/vision/${route}`,{method,headers:{'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body),signal:AbortSignal.timeout(60000)});return {status:r.status,body:await r.json()};}
async function execute(project){const r=await json('runtime/jobs','POST',{project});assert.equal(r.status,202,r.body.error);for(let i=0;i<400;i++){const j=(await json('runtime/jobs/'+r.body.id)).body;if(j.state!=='running')return j;await delay(30);}throw Error('job timeout');}
async function main(){
 await start();const demo=JSON.parse(fs.readFileSync(path.join(root,'public/vision/samples/demos-handeye.json')))[1];
 const plugin=(await json('plugins')).body.plugins.find(p=>p.id==='sieans-handeye');assert.equal(plugin.enabled,true);assert.equal(plugin.operators.length,3);assert.equal(plugin.operators[1].parameters.find(f=>f.key==='poses').columns.length,12);
 const project={version:1,id:'handeye-http',name:demo.name,steps:demo.steps.map((s,i)=>({...s,id:'p'+i}))};assert.equal((await json('project','PUT',project)).status,200);
 let saved=(await json('project')).body,job=await execute(saved);assert.equal(job.state,'completed',job.error);assert.equal(job.results[1].output.result.passed,true);
 const calibration=job.variables.flow.handeyeCalibration;assert(Math.abs(calibration.translation[2]-80)<1e-8);
 const bad=structuredClone(saved);bad.steps[1].params.arguments.poses[0].robotX+=10;job=await execute(bad);assert.equal(job.state,'completed');assert.equal(job.results[1].output.result.passed,false);
 await stop();await start();saved=(await json('project')).body;const restored=(await json('runtime/view','POST',{project:saved})).body;assert.deepEqual(restored.variables.flow.handeyeCalibration,calibration);
 job=await execute(saved);assert.equal(job.state,'completed',job.error);assert.equal(job.results[1].output.result.passed,true);
 console.log('PASS: HTTP three-operator discovery, twelve-column pose schema, model/reference variable binding, independent drift rejection, saved project/model and owned server restart');
}
main().catch(e=>{console.error(e,logs);process.exitCode=1;}).finally(()=>stop().catch(e=>{console.error(e);process.exitCode=1;}));
