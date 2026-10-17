'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),os=require('node:os'),net=require('node:net');
const {spawn}=require('node:child_process'),{once}=require('node:events'),bcrypt=require('bcryptjs'),graph=require('../public/vision/flow-graph.js');
const root=path.resolve(__dirname,'..'),directory=fs.mkdtempSync(path.join(os.tmpdir(),'sieans-mqtt-http-')),delay=ms=>new Promise(r=>setTimeout(r,ms));
let server,port,logs='',token='';const credentials='Basic '+Buffer.from('mqtt-test:local-mqtt-test').toString('base64');
async function request(route,method='GET',body,auth=true){const res=await fetch(`http://127.0.0.1:${port}${route}`,{method,headers:{'Content-Type':'application/json',...(auth?{Authorization:route.startsWith('/editor')?'Bearer '+token:credentials}:{})},body:body===undefined?undefined:JSON.stringify(body),signal:AbortSignal.timeout(20000)});const text=await res.text();let value;try{value=JSON.parse(text);}catch{value=text;}return {status:res.status,body:value};}
async function completed(id){for(let i=0;i<150;i++){const job=(await request('/api/vision/runtime/jobs/'+id)).body;if(job.state!=='running')return job;await delay(30);}throw Error('MQTT runtime did not finish');}
async function main(){
 const reserved=net.createServer();reserved.listen(0,'127.0.0.1');await once(reserved,'listening');port=reserved.address().port;await new Promise(r=>reserved.close(r));
 server=spawn(process.execPath,['server.cjs'],{cwd:root,windowsHide:true,env:{...process.env,HOST:'127.0.0.1',PORT:String(port),MACHINE_DATA_DIR:directory,ADMIN_USER:'mqtt-test',ADMIN_PASSWORD_HASH:bcrypt.hashSync('local-mqtt-test',4)}});server.stdout.on('data',b=>logs+=b);server.stderr.on('data',b=>logs+=b);
 let ready=false;for(let i=0;i<100;i++){if(server.exitCode!==null)throw Error(logs);try{if((await request('/health')).status===200){ready=true;break;}}catch{}await delay(100);}assert(ready,logs);
 const endpoint='/api/vision/industrial/mqtt/simulator';assert.equal((await request(endpoint,'GET',undefined,false)).status,401);assert.equal((await request(endpoint+'/start','POST',{},false)).status,401);assert.equal((await request(endpoint+'/start','POST')).body.running,true);
 const demos=JSON.parse(fs.readFileSync(path.join(root,'public/vision/samples/demos-mqtt.json'))),expected=[3,'SIEANS 工件 A · 合格',[83,73,69,65,78,83,0,255]];
 for(const [index,demo] of demos.entries()){
  const steps=demo.steps.map((s,i)=>({...s,id:'n'+i}));for(const b of demo.bindings)steps[b.step].params[b.param]={$ref:`results.n${b.source}.${b.field}`};
  const project=graph.normalize({version:1,id:'mqtt-demo-'+index,name:demo.name,steps});assert.equal((await request('/api/vision/project','PUT',project)).status,200);assert.deepEqual((await request('/api/vision/project')).body.steps,project.steps);
  const image='data:image/png;base64,'+fs.readFileSync(path.join(root,'public/vision/samples',demo.image)).toString('base64');
  const started=await request('/api/vision/runtime/jobs','POST',{project,image});assert.equal(started.status,202,JSON.stringify(started));const job=await completed(started.body.id);assert.equal(job.state,'completed',job.error);assert.deepEqual(job.variables.flow.mqttValue,expected[index]);assert.equal(job.archive.state,'saved');
 }
 const waiting=graph.normalize({version:1,id:'mqtt-cancel-http',name:'Waiting MQTT',steps:[{id:'receive',operation:'mqtt_receive',params:{connection:'simulator',topic:'never/http',timeoutMs:30000}}]});
 const wait=await request('/api/vision/runtime/jobs','POST',{project:waiting});assert.equal(wait.status,202);assert.equal((await request(endpoint+'/stop','POST')).status,409);await request('/api/vision/runtime/jobs/'+wait.body.id+'/cancel','POST');assert.equal((await completed(wait.body.id)).state,'cancelled');assert.equal((await request(endpoint+'/stop','POST')).body.running,false);
 // Authenticate the real Node-RED editor API and deploy into the isolated test data directory.
 const login=await fetch(`http://127.0.0.1:${port}/editor/auth/token`,{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:new URLSearchParams({client_id:'node-red-admin',grant_type:'password',scope:'*',username:'mqtt-test',password:'local-mqtt-test'})});assert.equal(login.status,200);token=(await login.json()).access_token;assert(token);
 const params={connection:'simulator',topic:'tests/nodered',encoding:'structured',retain:true,qos:2,timeoutMs:2000};
 const flows=[{id:'mqtt-test-tab',type:'tab',label:'MQTT test'},
  {id:'in',type:'http in',url:'/mqtt-test',method:'post',upload:false,wires:[['pub']]},
  {id:'pub',type:'machine-mqtt_publish',valueSource:'message',params:JSON.stringify(params),wires:[['sub']]},
  {id:'sub',type:'machine-mqtt_receive',params:JSON.stringify(params),wires:[['out']]},
  {id:'out',type:'http response',statusCode:'200',headers:{'content-type':'application/json'},wires:[]},
  {id:'catch',type:'catch',scope:['pub','sub'],uncaught:false,wires:[['error']]},
  {id:'error',type:'function',func:'msg.statusCode=400;msg.payload={error:msg.error.message};return msg;',outputs:1,wires:[['error-out']]},
  {id:'error-out',type:'http response',statusCode:'',headers:{'content-type':'application/json'},wires:[]}];
 for(const [i,n] of flows.entries())if(n.type!=='tab'){n.z='mqtt-test-tab';n.x=100+i*80;n.y=100;}
 const deployed=await request('/editor/flows','POST',flows);assert.equal(deployed.status,204,JSON.stringify(deployed));await delay(200);
 const out=await request('/mqtt-test','POST',{count:42,passed:true});assert.equal(out.status,200,JSON.stringify(out));assert.deepEqual(out.body.value,{count:42,passed:true});assert.equal(out.body.qos,2);assert.equal(out.body.retained,true);
 flows.find(n=>n.id==='pub').valueSource='constant';flows.find(n=>n.id==='pub').params=JSON.stringify({...params,value:{count:7}});assert.equal((await request('/editor/flows','POST',flows)).status,204);await delay(100);assert.deepEqual((await request('/mqtt-test','POST',{ignored:true})).body.value,{count:7});
 flows.find(n=>n.id==='pub').params=JSON.stringify({...params,topic:'bad/+',value:0});assert.equal((await request('/editor/flows','POST',flows)).status,204);await delay(100);const error=await request('/mqtt-test','POST',{});assert.equal(error.status,400);assert.match(error.body.error,/通配符/);
 assert.equal((await request(endpoint+'/stop','POST')).body.running,false);
 console.log('PASS: authenticated MQTT API, 3 real demonstration chains, project persistence, variables/history, cancellation, simulator lock, real Node-RED message/constant publishing, receiving and Catch errors');
}
main().catch(error=>{console.error(error,logs);process.exitCode=1;}).finally(async()=>{if(server&&server.exitCode===null){const done=once(server,'exit');server.kill();await done;}console.log('MQTT HTTP test data: '+directory);});
