'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),os=require('node:os'),{spawn}=require('node:child_process'),{once}=require('node:events');
const root=path.resolve(__dirname,'..'),data=fs.mkdtempSync(path.join(os.tmpdir(),'sieans-assist-')),port=Number(process.env.SIEANS_TEST_HTTP_PORT||1908);
const server=spawn(process.execPath,['server.cjs'],{cwd:root,windowsHide:true,stdio:['ignore','pipe','pipe','ipc'],env:{...process.env,PORT:String(port),HOST:'127.0.0.1',MACHINE_DATA_DIR:data,ADMIN_PASSWORD_HASH:''}});
let logs='';server.stdout.on('data',b=>logs+=b);server.stderr.on('data',b=>logs+=b);
const delay=ms=>new Promise(r=>setTimeout(r,ms));
async function call(route,body){const response=await fetch('http://127.0.0.1:'+port+'/api/vision/'+route,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body),signal:AbortSignal.timeout(120000)});return {status:response.status,body:await response.json()};}
async function main(){
 for(let i=0;i<150&&!logs.includes('http://127.0.0.1:'+port);i++){if(server.exitCode!==null)throw Error(logs);await delay(100);}assert.ok(logs.includes('http://127.0.0.1:'+port),logs);
 const image='data:image/jpeg;base64,'+fs.readFileSync(path.join(root,'public/vision/samples/segmentation-bus.jpg')).toString('base64');
 for(const task of ['detect','segment']){
  const created=await call('training/datasets',{id:'assist-'+task,task,names:['bus','person']});assert.equal(created.status,201,created.body.error);
  const route='training/datasets/assist-'+task+'/annotations/';assert.equal((await call(route+'upload',{name:'bus.jpg',split:'train',image})).status,200);
  const loaded=await call(route+'load',{name:'bus.jpg',split:'train'}),base={name:'bus.jpg',split:'train',revision:loaded.body.revision,confidence:.25,device:process.env.TEST_COMPUTE_DEVICE||'cpu',model:task==='detect'?'yolo11n.pt':'yolo11n-seg.pt'};
  const proposed=await call(route+'suggest',base);assert.equal(proposed.status,200,proposed.body.error);assert.ok(proposed.body.proposals.length>0);assert.equal(proposed.body.device,base.device);assert.equal(proposed.body.revision,base.revision);
  const unchanged=await call(route+'load',{name:'bus.jpg',split:'train'});assert.equal(unchanged.body.hasLabel,false);assert.equal(unchanged.body.revision,base.revision);assert.deepEqual(unchanged.body.records,[]);
  assert.equal((await call(route+'suggest',{...base,revision:'stale'})).status,409);assert.equal((await call(route+'suggest',{...base,model:'../escape.pt'})).status,400);
  assert.equal((await call(route+'suggest',{...base,model:task==='detect'?'yolo11n-seg.pt':'yolo11n.pt'})).status,400);
  const proposal=proposed.body.proposals.find(p=>p.label==='person'),record={classId:1,...(proposal.box?{box:proposal.box}:{points:proposal.points})};
  assert.equal((await call(route+'save',{...base,records:[record]})).status,200);const saved=await call(route+'load',{name:'bus.jpg',split:'train'});assert.equal(saved.body.hasLabel,true);assert.equal(saved.body.records.length,1);assert.equal(saved.body.records[0].classId,1);
  assert.equal((await call(route+'suggest',base)).status,409);
  assert.equal((await call(route+'history',{...base,revision:saved.body.revision})).body.entries.length,0);
  const background=await call(route+'save',{...base,revision:saved.body.revision,records:[]});assert.equal(background.status,200);
  const history=await call(route+'history',{...base,revision:background.body.revision});assert.equal(history.status,200);assert.equal(history.body.entries.length,1);
  const previous=await call(route+'history_load',{...base,revision:background.body.revision,historyId:history.body.entries[0].id});assert.equal(previous.status,200);assert.equal(previous.body.records.length,1);
  assert.deepEqual((await call(route+'load',{name:'bus.jpg',split:'train'})).body.records,[]);
  assert.equal((await call(route+'save',{...base,revision:background.body.revision,records:previous.body.records})).status,200);
  assert.equal((await call(route+'history_load',{...base,revision:background.body.revision,historyId:history.body.entries[0].id})).status,409);
 }
 console.log('PASS: actual detection/segmentation candidate HTTP, explicit save, class remapping, read-only inference, stale revision and model containment/task validation, history read/explicit restore/background backup/conflict');
}
main().catch(error=>{console.error(error,logs);process.exitCode=1;}).finally(async()=>{if(server.exitCode===null){server.send({type:'sieans-shutdown'});await Promise.race([once(server,'exit'),delay(5000)]);if(server.exitCode===null)server.kill();}});
