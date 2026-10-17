const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),os=require('node:os'),net=require('node:net');
const {spawn}=require('node:child_process'),{once}=require('node:events'),bcrypt=require('bcryptjs'),graph=require('../public/vision/flow-graph.js');
const root=path.resolve(__dirname,'..'),directory=fs.mkdtempSync(path.join(os.tmpdir(),'sieans-history-http-')),delay=ms=>new Promise(r=>setTimeout(r,ms));
let server,port,logs='';const credentials='Basic '+Buffer.from('history-test:temporary-local-test').toString('base64');
async function start(){
 const reserved=net.createServer();reserved.listen(0,'127.0.0.1');await once(reserved,'listening');port=reserved.address().port;await new Promise(r=>reserved.close(r));
 server=spawn(process.execPath,['server.cjs'],{cwd:root,windowsHide:true,env:{...process.env,HOST:'127.0.0.1',PORT:String(port),MACHINE_DATA_DIR:directory,ADMIN_USER:'history-test',ADMIN_PASSWORD_HASH:bcrypt.hashSync('temporary-local-test',4)}});
 server.stdout.on('data',b=>logs+=b);server.stderr.on('data',b=>logs+=b);
 for(let i=0;i<100;i++){if(server.exitCode!==null)throw Error(logs);try{const res=await fetch(`http://127.0.0.1:${port}/health`,{signal:AbortSignal.timeout(500)});if(res.ok)return;}catch{}await delay(100);}throw Error('History test server did not start: '+logs);
}
async function stop(){if(server&&server.exitCode===null){const exited=once(server,'exit');server.kill();await exited;}}
async function request(route,method='GET',body,auth=true){const res=await fetch(`http://127.0.0.1:${port}${route}`,{method,headers:{'Content-Type':'application/json',...(auth?{Authorization:credentials}:{})},body:body===undefined?undefined:JSON.stringify(body),signal:AbortSignal.timeout(30000)});const text=await res.text();let value;try{value=JSON.parse(text);}catch{value=text;}return {status:res.status,body:value};}
async function execute(project,extra={}){const response=await request('/api/vision/runtime/jobs','POST',{project,...extra});assert.equal(response.status,202,JSON.stringify(response));let job=response.body;
 for(let i=0;i<200&&job.state==='running';i++){await delay(30);job=(await request('/api/vision/runtime/jobs/'+job.id)).body;}assert.notEqual(job.state,'running');return job;
}
async function main(){
 await start();assert.equal((await request('/api/vision/history','GET',undefined,false)).status,401);assert.equal((await request('/api/vision/history')).body.total,0);
 const image='data:image/png;base64,'+fs.readFileSync(path.join(root,'public/vision/samples/parts.png')).toString('base64'),cloud={unit:'mm',points:[[1,2,3],[4,5,6]]};
 const p=graph.normalize({version:1,id:'trace-http',name:'图像检测与归档',history:{includeFrames:true},variables:{count:0},variableTypes:{count:'integer'},steps:[{id:'find',operation:'geometry',params:{threshold:127,minArea:50}},{id:'script',operation:'script',params:{code:'def run(ctx):\n    count=ctx["results"]["find"]["count"]\n    v=ctx["vars"]\n    v["flow"]["count"]=count\n    print("inspection finished")\n    return dict(result=dict(count=count,passed=False),variables=v)'}}]});
 assert.equal((await request('/api/vision/project','PUT',p)).status,200);assert.deepEqual((await request('/api/vision/project')).body.history,{includeFrames:true});
 const done=await execute(p,{image,cloud,allowScripts:true});assert.equal(done.state,'completed');assert.equal(done.archive.state,'saved');
 const list=(await request('/api/vision/history?projectId=trace-http&state=completed&limit=1')).body;assert.equal(list.total,1);assert.equal(list.items[0].inspectionFailures,1);assert.equal(list.items[0].framesSaved,true);assert.equal(list.items[0].finishedSteps,2);
 const detail=await request('/api/vision/history/'+done.id);assert.equal(detail.status,200);assert.equal(detail.body.input.image,image);assert.deepEqual(detail.body.input.cloud,cloud);assert.equal(detail.body.results[1].output.annotatedImage,image);assert(detail.body.results[1].output.result.count>0);assert.equal(detail.body.variables.flow.count,detail.body.results[1].output.result.count);assert.match(detail.body.results[1].output.logs,/inspection finished/);
 const bad=graph.normalize({version:1,id:'trace-http',name:'失败与回滚',steps:[{id:'change',operation:'variables',params:{name:'count',value:100}},{id:'bad',operation:'variables',params:{name:'missing',value:{$ref:'flow.no_such_value'}}}]});const failed=await execute(bad);assert.equal(failed.state,'failed');
 const failure=(await request('/api/vision/history/'+failed.id)).body;assert.equal(failure.variablesCommitted,false);assert.equal(failure.variables.flow.count,detail.body.variables.flow.count);assert.equal(failure.input,undefined);assert.equal(failure.results[0].output.annotatedImage,undefined);assert.match(failure.results[1].error,/不存在/);
 const slow=graph.normalize({version:1,id:'trace-http',name:'取消检测',steps:[{id:'wait',operation:'delay',params:{milliseconds:30000}}]});const accepted=await request('/api/vision/runtime/jobs','POST',{project:slow});await request('/api/vision/runtime/jobs/'+accepted.body.id+'/cancel','POST');let cancelled;
 for(let i=0;i<100;i++){await delay(20);cancelled=(await request('/api/vision/runtime/jobs/'+accepted.body.id)).body;if(cancelled.state!=='running')break;}assert.equal(cancelled.state,'cancelled');assert.equal(cancelled.archive.state,'saved');
 const filtered=(await request('/api/vision/history?state=failed&after='+failure.startedAt+'&before='+failure.startedAt)).body;assert.equal(filtered.total,1);assert.equal(filtered.items[0].id,failed.id);
 assert.equal((await request('/api/vision/history?limit=101')).status,400);assert.equal((await request('/api/vision/history/bad-id')).status,400);assert.equal((await request('/api/vision/history/00000000-0000-0000-0000-000000000000')).status,404);
 await stop();await start();assert.equal((await request('/api/vision/history')).body.total,3);assert.equal((await request('/api/vision/runtime/jobs/'+done.id)).status,404);assert.deepEqual((await request('/api/vision/history/'+done.id)).body,detail.body);assert.equal((await request('/api/vision/history/'+done.id,'GET',undefined,false)).status,401);
 const file=path.join(directory,'run-history',done.id+'.data.json');fs.appendFileSync(file,' ');assert.equal((await request('/api/vision/history/'+done.id)).status,409);
 console.log('PASS: authenticated history filters/details, real image/script output, optional frames, failure rollback, cancellation, settings persistence, server restart and corruption detection');
}
main().catch(error=>{console.error(error,logs);process.exitCode=1;}).finally(async()=>{await stop();console.log('History HTTP data: '+directory);});
