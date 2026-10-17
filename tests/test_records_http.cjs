const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),os=require('node:os');
const {spawn}=require('node:child_process'),{once}=require('node:events');
const root=path.resolve(__dirname,'..'),data=fs.mkdtempSync(path.join(os.tmpdir(),'sieans-records-http-')),port=Number(process.env.SIEANS_TEST_HTTP_PORT||1920);
let server,logs='';const delay=ms=>new Promise(r=>setTimeout(r,ms));
async function start(){logs='';server=spawn(process.execPath,['server.cjs'],{cwd:root,windowsHide:true,stdio:['ignore','pipe','pipe','ipc'],env:{...process.env,PORT:String(port),HOST:'127.0.0.1',MACHINE_DATA_DIR:data,ADMIN_PASSWORD_HASH:''}});server.stdout.on('data',b=>logs+=b);server.stderr.on('data',b=>logs+=b);for(let i=0;i<150&&!logs.includes('http://127.0.0.1:'+port);i++){if(server.exitCode!==null)throw Error(logs);await delay(100);}assert(logs.includes('http://127.0.0.1:'+port),logs);}
async function stop(){if(server?.exitCode===null){const exited=once(server,'exit');server.send({type:'sieans-shutdown'});await Promise.race([exited,delay(8000)]);assert.notEqual(server.exitCode,null);}}
async function json(route,method='GET',body){const r=await fetch(`http://127.0.0.1:${port}/api/vision/${route}`,{method,headers:{'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body),signal:AbortSignal.timeout(60000)});return {status:r.status,body:await r.json()};}
async function execute(project,image){const r=await json('runtime/jobs','POST',{project,image});assert.equal(r.status,202,r.body.error);for(let i=0;i<400;i++){const j=(await json('runtime/jobs/'+r.body.id)).body;if(j.state!=='running')return j;await delay(30);}throw Error('job timeout');}
async function main(){
 await start();const plugin=(await json('plugins')).body.plugins.find(p=>p.id==='sieans-records');assert.equal(plugin.enabled,true);assert.equal(plugin.operators.length,7);assert.equal(plugin.operators.find(op=>op.id==='append').parameters.find(p=>p.key==='keyField').required,false);
 const demo=JSON.parse(fs.readFileSync(path.join(root,'public/vision/samples/demos-records.json')))[0],steps=structuredClone(demo.steps).map((s,i)=>({...s,id:'d'+i}));for(const b of demo.bindings)steps[b.step].params[b.param]={$ref:'results.d'+b.source+'.'+b.field};
 const hmi=structuredClone(demo.hmi);for(const b of demo.hmiBindings)hmi.components[b.component].binding.nodeId='d'+b.step;
 const project={version:1,id:'records-http',name:demo.name,variables:demo.variables,steps,hmi};const image='data:image/png;base64,'+fs.readFileSync(path.join(root,'public/vision/samples/parts.png')).toString('base64');
 assert.equal((await json('project','PUT',project)).status,200);const saved=(await json('project')).body;
 const continuous=await json('runtime/continuous','POST',{project:saved,image,intervalMs:100,maxCycles:5});assert.equal(continuous.status,202,continuous.body.error);
 let session;for(let i=0;i<500;i++){session=(await json('runtime/continuous')).body;if(!session.busy)break;await delay(30);}assert.equal(session.state,'completed',session.error);
 const view=(await json('runtime/view','POST',{project:saved})).body;assert.deepEqual(view.variables.flow.inspectionRecords.map(r=>r.sequence),[3,4,5]);assert.equal(view.variables.flow.meanCount,3);
 await stop();await start();const restored=(await json('project')).body;assert.equal(restored.hmi.components[3].binding.path,'inspectionRecords');assert.deepEqual((await json('runtime/view','POST',{project:restored})).body.variables.flow.inspectionRecords,view.variables.flow.inspectionRecords);
 let job=await execute(restored,image);assert.equal(job.state,'completed',job.error);assert.deepEqual(job.variables.flow.inspectionRecords.map(r=>r.sequence),[4,5,6]);
 const full=structuredClone(restored);full.steps[4].params.arguments.overflow='error';job=await execute(full,image);assert.equal(job.state,'failed');assert.match(job.error,/已满/);
 const after=(await json('runtime/view','POST',{project:restored})).body;assert.equal(after.variables.flow.sequence,6);assert.deepEqual(after.variables.flow.inspectionRecords.map(r=>r.sequence),[4,5,6]);
 console.log('PASS: HTTP seven-operator discovery, optional key form metadata, five OpenCV record cycles, HMI table project, persistent typed records, restart continuation and full-capacity transaction rollback');
}
main().catch(e=>{console.error(e,logs);process.exitCode=1;}).finally(()=>stop().catch(e=>{console.error(e);process.exitCode=1;}));
