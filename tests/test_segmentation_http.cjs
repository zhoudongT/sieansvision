'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),os=require('node:os'),path=require('node:path');
const {spawn}=require('node:child_process'),{once}=require('node:events');
const root=path.resolve(__dirname,'..'),port=Number(process.env.SIEANS_TEST_HTTP_PORT||1902),url=`http://127.0.0.1:${port}`;
const data=fs.mkdtempSync(path.join(os.tmpdir(),'sieans-segment-http-'));
const server=spawn(process.execPath,['server.cjs'],{cwd:root,windowsHide:true,stdio:['ignore','pipe','pipe','ipc'],env:{...process.env,PORT:String(port),HOST:'127.0.0.1',MACHINE_DATA_DIR:data,ADMIN_PASSWORD_HASH:''}});
let logs='';server.stdout.on('data',b=>logs+=b);server.stderr.on('data',b=>logs+=b);
const delay=ms=>new Promise(r=>setTimeout(r,ms));
async function json(route,method='GET',body){const r=await fetch(url+route,{method,headers:{'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body),signal:AbortSignal.timeout(60000)});return {status:r.status,body:await r.json()};}
async function main(){
 for(let i=0;i<150&&!logs.includes(`http://127.0.0.1:${port}`);i++){if(server.exitCode!==null)throw Error(logs);await delay(100);}
 assert.ok(logs.includes(`http://127.0.0.1:${port}`),logs);
 const compute=await json('/api/vision/compute?refresh=1');assert.equal(compute.status,200,compute.body.error);assert.ok(compute.body.devices.some(d=>d.id==='cpu'));if(process.env.TEST_COMPUTE_DEVICE?.startsWith('cuda:'))assert.ok(compute.body.devices.some(d=>d.id===process.env.TEST_COMPUTE_DEVICE));
 const image='data:image/jpeg;base64,'+fs.readFileSync(path.join(root,'public/vision/samples/segmentation-bus.jpg')).toString('base64');
 const params={device:process.env.TEST_COMPUTE_DEVICE||'cpu',model:'yolo11n-seg.pt',output:'mask',classes:[5]};
 const direct=await json('/api/vision/run','POST',{operation:'yolo_segment',image,params});assert.equal(direct.status,200,direct.body.error);assert.equal(direct.body.result.count,1);assert.equal(direct.body.result.device,params.device);assert.match(direct.body.maskImage,/^data:image\/png;base64,/);
 assert.equal((await json('/api/vision/run','POST',{operation:'yolo_segment',image,params:{model:'yolo11n.pt'}})).status,400);
 const project={version:1,name:'分割 HTTP',steps:[{id:'seg',operation:'yolo_segment',params},{id:'measure',operation:'geometry',params:{minArea:100}},{id:'area',operation:'variables',params:{name:'area',value:{$ref:'results.seg.unionAreaPixels'}}}]};
 assert.equal((await json('/api/vision/project','PUT',project)).status,200);assert.deepEqual((await json('/api/vision/project')).body.steps[0].params,params);
 const accepted=await json('/api/vision/runtime/jobs','POST',{project,image});assert.equal(accepted.status,202,accepted.body.error);let job=accepted.body;
 for(let i=0;i<600&&job.state==='running';i++){await delay(100);job=(await json('/api/vision/runtime/jobs/'+job.id)).body;}
 assert.equal(job.state,'completed',job.error);assert.equal(job.results[1].output.result.count,1);assert.equal(job.variables.flow.area,direct.body.result.unionAreaPixels);
 const flows=[{id:'seg-test',type:'tab',label:'Segmentation acceptance'}];
 for(const output of ['mask','overlay']){
  flows.push({id:output+'-in',type:'http in',z:'seg-test',url:'/seg-'+output,method:'post',wires:[[output+'-seg']]},
   {id:output+'-seg',type:'machine-yolo_segment',z:'seg-test',params:JSON.stringify({...params,output}),wires:[[output+'-capture'],[]]},
   {id:output+'-capture',type:'function',z:'seg-test',func:'msg.segmentation={result:msg.payload,image:msg.image,mask:msg.vision.maskImage};return msg;',outputs:1,wires:[[output+'-geometry']]},
   {id:output+'-geometry',type:'machine-geometry',z:'seg-test',params:'{"minArea":100}',wires:[[output+'-result'],[]]},
   {id:output+'-result',type:'function',z:'seg-test',func:'msg.payload={segmentation:msg.segmentation,geometry:msg.payload};return msg;',outputs:1,wires:[['response']]});
 }
 flows.push({id:'response',type:'http response',z:'seg-test',statusCode:'200',headers:{'content-type':'application/json'},wires:[]});
 flows.filter(n=>n.z).forEach((n,i)=>Object.assign(n,{x:100+(i%5)*180,y:100+Math.floor(i/5)*100}));
 const offset=logs.length,r=await fetch(url+'/editor/flows',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(flows)});assert.equal(r.status,204);
 for(let i=0;i<100&&!logs.slice(offset).includes('Started flows');i++)await delay(100);
 assert.ok(logs.slice(offset).includes('Started flows'),logs.slice(offset));
 for(const mode of ['mask','overlay']){const out=await json('/seg-'+mode,'POST',{image});assert.equal(out.status,200);const segment=out.body.segmentation;assert.equal(segment.result.count,1);assert.equal(segment.result.device,params.device);assert.ok(segment.image===(mode==='mask'?segment.mask:image),'Node-RED image routing '+mode);if(mode==='mask')assert.equal(out.body.geometry.count,1);}
 console.log('PASS: segmentation HTTP, invalid model, project persistence, runtime mask/measurement/variable chain and real Node-RED mask/overlay routes');
}
main().catch(e=>{console.error(e.message,logs);process.exitCode=1;}).finally(async()=>{
 if(server.exitCode===null){server.send({type:'sieans-shutdown'});await Promise.race([once(server,'exit'),delay(5000)]);if(server.exitCode===null)server.kill();}
});
