'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),os=require('node:os'),net=require('node:net');
const {spawn}=require('node:child_process'),{once}=require('node:events'),bcrypt=require('bcryptjs'),graph=require('../public/vision/flow-graph.js');
const root=path.resolve(__dirname,'..'),directory=fs.mkdtempSync(path.join(os.tmpdir(),'sieans-serial-http-')),delay=ms=>new Promise(r=>setTimeout(r,ms));
let server,port,logs='',token='';const credentials='Basic '+Buffer.from('serial-test:local-serial-test').toString('base64');
async function request(route,method='GET',body,auth=true){const res=await fetch(`http://127.0.0.1:${port}${route}`,{method,headers:{'Content-Type':'application/json',...(auth?{Authorization:route.startsWith('/editor')?'Bearer '+token:credentials}:{})},body:body===undefined?undefined:JSON.stringify(body),signal:AbortSignal.timeout(20000)});const text=await res.text();let value;try{value=JSON.parse(text);}catch{value=text;}return {status:res.status,body:value};}
async function completed(id){for(let i=0;i<150;i++){const job=(await request('/api/vision/runtime/jobs/'+id)).body;if(job.state!=='running')return job;await delay(30);}throw Error('Serial runtime did not finish');}
async function main(){
 const reserved=net.createServer();reserved.listen(0,'127.0.0.1');await once(reserved,'listening');port=reserved.address().port;await new Promise(r=>reserved.close(r));
 server=spawn(process.execPath,['server.cjs'],{cwd:root,windowsHide:true,env:{...process.env,HOST:'127.0.0.1',PORT:String(port),MACHINE_DATA_DIR:directory,ADMIN_USER:'serial-test',ADMIN_PASSWORD_HASH:bcrypt.hashSync('local-serial-test',4)}});server.stdout.on('data',b=>logs+=b);server.stderr.on('data',b=>logs+=b);
 let ready=false;for(let i=0;i<100;i++){if(server.exitCode!==null)throw Error(logs);try{if((await request('/health')).status===200){ready=true;break;}}catch{}await delay(100);}assert(ready,logs);
 assert.equal((await request('/api/vision/runtime/jobs','POST',{},false)).status,401);
 const ports=await request('/api/vision/industrial/ports');assert.equal(ports.status,200);assert(Array.isArray(ports.body.ports));
 const demos=JSON.parse(fs.readFileSync(path.join(root,'public/vision/samples/demos-serial.json'))),expected=['SIEANS-SERIAL-00042',{count:3,passed:true,width:12.5},[83,73,69,65,78,83,0,255]];
 for(const [index,demo] of demos.entries()){
  const steps=demo.steps.map((s,i)=>({...s,id:'n'+i}));for(const b of demo.bindings)steps[b.step].params[b.param]={$ref:`results.n${b.source}.${b.field}`};
  const project=graph.normalize({version:1,id:'serial-demo-'+index,name:demo.name,steps});assert.equal((await request('/api/vision/project','PUT',project)).status,200);assert.deepEqual((await request('/api/vision/project')).body.steps,project.steps);
  const image='data:image/png;base64,'+fs.readFileSync(path.join(root,'public/vision/samples',demo.image)).toString('base64');
  const start=await request('/api/vision/runtime/jobs','POST',{project,image});assert.equal(start.status,202,JSON.stringify(start));const job=await completed(start.body.id);assert.equal(job.state,'completed',job.error);assert.deepEqual(job.variables.flow.serialReply,expected[index]);assert.equal(job.archive.state,'saved');
 }
 const waiting=graph.normalize({version:1,id:'serial-cancel-http',name:'Waiting serial',variables:{original:1},steps:[{id:'before',operation:'variables',params:{scope:'flow',name:'original',value:2}},{id:'wait',operation:'serial_exchange',params:{connection:'simulator',value:'no-terminator',txFraming:'raw',rxFraming:'crlf',timeoutMs:10000}}]});
 const wait=await request('/api/vision/runtime/jobs','POST',{project:waiting});assert.equal(wait.status,202);await request('/api/vision/runtime/jobs/'+wait.body.id+'/cancel','POST');assert.equal((await completed(wait.body.id)).state,'cancelled');
 assert.equal((await request('/api/vision/runtime/variables/read','POST',{project:waiting})).body.flow.original,1);
 const login=await fetch(`http://127.0.0.1:${port}/editor/auth/token`,{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:new URLSearchParams({client_id:'node-red-admin',grant_type:'password',scope:'*',username:'serial-test',password:'local-serial-test'})});assert.equal(login.status,200);token=(await login.json()).access_token;assert(token);
 const params={connection:'simulator',mode:'exchange',encoding:'structured',txFraming:'length16le',rxFraming:'length16le',timeoutMs:2000};
 const flows=[{id:'serial-test-tab',type:'tab',label:'Serial test'},
  {id:'in',type:'http in',url:'/serial-test',method:'post',upload:false,wires:[['serial']]},
  {id:'serial',type:'machine-serial_exchange',valueSource:'message',params:JSON.stringify(params),wires:[['out']]},
  {id:'out',type:'http response',statusCode:'200',headers:{'content-type':'application/json'},wires:[]},
  {id:'catch',type:'catch',scope:['serial'],uncaught:false,wires:[['error']]},
  {id:'error',type:'function',func:'msg.statusCode=400;msg.payload={error:msg.error.message};return msg;',outputs:1,wires:[['error-out']]},
  {id:'error-out',type:'http response',statusCode:'',headers:{'content-type':'application/json'},wires:[]}];
 for(const [i,n] of flows.entries())if(n.type!=='tab'){n.z='serial-test-tab';n.x=100+i*80;n.y=100;}
 assert.equal((await request('/editor/flows','POST',flows)).status,204);await delay(200);
 const out=await request('/serial-test','POST',{count:42,passed:true});assert.equal(out.status,200,JSON.stringify(out));assert.deepEqual(out.body.value,{count:42,passed:true});assert.equal(out.body.protocol,'Serial');assert.equal(out.body.simulated,true);
 flows.find(n=>n.id==='serial').valueSource='constant';flows.find(n=>n.id==='serial').params=JSON.stringify({...params,value:{count:7},dtr:false,rts:false,clearInput:true});assert.equal((await request('/editor/flows','POST',flows)).status,204);await delay(100);assert.deepEqual((await request('/serial-test','POST',{ignored:true})).body.value,{count:7});
 flows.find(n=>n.id==='serial').params=JSON.stringify({...params,value:3,rxFraming:'eof'});assert.equal((await request('/editor/flows','POST',flows)).status,204);await delay(100);const error=await request('/serial-test','POST',{});assert.equal(error.status,400);assert.match(error.body.error,/EOF/);
 console.log('PASS: authenticated serial API, port enumeration, 3 loopback demos, persistence/history, cancellation/rollback; real Node-RED message/constant serial flows and Catch errors');
}
main().catch(error=>{console.error(error,logs);process.exitCode=1;}).finally(async()=>{if(server&&server.exitCode===null){const done=once(server,'exit');server.kill();await done;}console.log('Serial HTTP test data: '+directory);});
