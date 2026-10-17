const {test,after}=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),os=require('node:os');
const {Runtime}=require('../lib/runtime.cjs'),camera=require('../lib/camera-client.cjs'),vision=require('../lib/vision-client.cjs');
const params={driver:'simulator',deviceId:'synthetic-parts',timeoutMs:5000};
const project=()=>({version:1,name:'Camera pipeline',steps:[{id:'camera',operation:'camera_capture',params},{id:'detect',operation:'geometry',params:{feature:'contours',threshold:127,minArea:50}},{id:'save',operation:'variables',params:{scope:'flow',name:'count',value:{$ref:'results.detect.count'}}}]});
const runtime=()=>new Runtime(fs.mkdtempSync(path.join(os.tmpdir(),'sieans-camera-')),vision);
async function run(r,p,extra={}){const job=r.start({project:p,...extra});await r.jobs.get(job.id).promise;return r.poll(job.id);}
after(()=>{camera.stop();vision.stop();});
test('camera list, inspect and capture expose typed metadata and a real PNG',async()=>{
 const list=await camera.run({operation:'camera_list',params});assert.equal(list.result.items[0].deviceId,params.deviceId);
 const info=await camera.run({operation:'camera_inspect',params});assert(info.result.items.some(x=>x.name==='Width'));
 const captured=await camera.run({operation:'camera_capture',params});assert.equal(captured.result.width,640);assert.match(captured.annotatedImage,/^data:image\/png;base64,iVBOR/);assert.equal(captured.result.simulated,true);
});
test('camera generates pipeline input without uploaded image and feeds variables',async()=>{
 const job=await run(runtime(),project());assert.equal(job.state,'completed',job.error);assert.equal(job.variables.flow.count,3);assert.equal(job.results[0].output.result.outputBits,8);
});
test('new 2D capture clears old source cloud instead of leaking stale 3D data',async()=>{
 const p=project();p.steps=[p.steps[0],{id:'measure',operation:'cloud_measure',params:{}}];
 const job=await run(runtime(),p,{cloud:{points:[[0,0,0],[1,1,1]],unit:'mm'}});assert.equal(job.state,'failed');assert.match(job.error,/输入点云/);
});
test('camera failure rolls back variables and does not run detection',async()=>{
 const p=project();p.steps[0].params={driver:'simulator',deviceId:'missing'};p.steps.unshift({id:'change',operation:'variables',params:{scope:'global',name:'pending',value:1}});
 const r=runtime(),job=await run(r,p);assert.equal(job.state,'failed');assert.equal(job.results.length,2);assert.deepEqual(r.snapshot(p).global,{});
});
test('camera lock, process cancellation and subsequent recovery',async()=>{
 const c=new AbortController(),pending=camera.run({operation:'camera_capture',params},{signal:c.signal});
 pending.catch(()=>{});await assert.rejects(camera.run({operation:'camera_list',params}),/正在进行/);c.abort();await assert.rejects(pending,/采集已取消/);
 // Wait for actual child close to release lock, not just Promise rejection.
 let out;for(let i=0;i<40;i++){try{out=await camera.run({operation:'camera_list',params});break;}catch(error){if(!error.message.includes('正在进行'))throw error;await new Promise(r=>setTimeout(r,25));}}
 assert.equal(out.result.items.length,1);
});
