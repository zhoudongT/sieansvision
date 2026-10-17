const {test,after}=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),os=require('node:os');
const camera=require('../lib/camera-client.cjs'),vision=require('../lib/vision-client.cjs');
const {CameraSession,settings}=require('../lib/camera-session.cjs'),{Runtime}=require('../lib/runtime.cjs');
const {ContinuousRun}=require('../lib/continuous-run.cjs');
const delay=ms=>new Promise(r=>setTimeout(r,ms));
const folder=()=>fs.mkdtempSync(path.join(os.tmpdir(),'sieans-camera-session-'));
const config=(extra={})=>({params:{driver:'simulator',deviceId:'synthetic-parts',timeoutMs:1000},intervalMs:100,...extra});
async function ready(manager){for(let i=0;i<200;i++){const s=manager.status();if(s.state==='running')return s;if(s.state==='failed')throw Error(s.error);await delay(20);}throw Error('session did not become ready');}
function read(id,extra={}){return {driver:'session',sessionId:id,framePolicy:'next',timeoutMs:1000,...extra};}
after(async()=>{await camera.stop();camera.setSessions(null);vision.stop();});

test('session and frame settings are bounded; background triggering is rejected',()=>{
 assert.equal(settings(config()).reconnectAttempts,0);
 for(const body of [config({intervalMs:1}),config({reconnectAttempts:6}),config({reconnectMs:false}),{...config(),params:{driver:'session'}},{...config(),params:{driver:'gentl',trigger:'software'}},{...config(),unknown:true}])assert.throws(()=>settings(body));
});

test('real persistent worker supplies increasing next frames, bounded cache, reuse and shared single-shot resource lock',async()=>{
 const manager=new CameraSession(folder(),camera);camera.setSessions(manager);
 try{
  const s=manager.start(config());await ready(manager);await delay(260);assert(manager.status().received>=3);assert(manager.status().overwritten>=2);
  const before=manager.status().sequence,out=await camera.run({operation:'camera_capture',params:read(s.id)});
  assert(out.result.frameSequence>before);assert.equal(out.result.reusedFrame,false);assert(out.annotatedImage.startsWith('data:image/png;base64,'));
  const latest=await manager.capture(read(s.id,{framePolicy:'latest',maxAgeMs:1000}));assert.equal(latest.result.frameSequence,out.result.frameSequence);assert.equal(latest.result.reusedFrame,true);
  await assert.rejects(camera.run({operation:'camera_list',params:{driver:'simulator'}}),/正在进行/);
  assert.throws(()=>manager.start(config()),/先停止/);
  await assert.rejects(manager.capture(read('stale-session')),/编号/);
  assert.equal((await manager.stop(s.id)).state,'stopped');assert.equal(manager.status().buffered,false);
  assert.equal((await camera.run({operation:'camera_list',params:{driver:'simulator'}})).result.items.length,1);
 }finally{await manager.shutdown();camera.setSessions(null);}
});

test('stale cache is rejected; new-frame cancellation/timeout does not close the device or return stale data',async()=>{
 const manager=new CameraSession(folder(),camera);camera.setSessions(manager);
 try{
  const s=manager.start(config({intervalMs:2000}));await ready(manager);await delay(20);
  await assert.rejects(manager.capture(read(s.id,{framePolicy:'latest',maxAgeMs:1})),/过期/);
  const c=new AbortController(),pending=manager.capture(read(s.id),{signal:c.signal});c.abort();await assert.rejects(pending,/取消/);assert.equal(manager.status().waiting,false);assert.equal(manager.status().active,true);
  const waiting=manager.capture(read(s.id,{timeoutMs:100}));await assert.rejects(manager.capture(read(s.id)),/已有采集/);await assert.rejects(waiting,/超时/);assert.equal(manager.status().active,true);
  const stopped=manager.capture(read(s.id));const rejected=assert.rejects(stopped,/停止/);await manager.stop(s.id);await rejected;
 }finally{await manager.shutdown();camera.setSessions(null);}
});

test('same SDK session drives three continuous real OpenCV jobs with fresh frames and flow variables',async()=>{
 const dir=folder(),manager=new CameraSession(dir,camera);camera.setSessions(manager);
 try{
  const s=manager.start(config());await ready(manager);
  const runtime=new Runtime(dir,vision),continuous=new ContinuousRun(runtime,dir);
  const project={version:1,id:'camera-session-count',name:'连续连接检测',steps:[{id:'cam',operation:'camera_capture',params:read(s.id)},{id:'geometry',operation:'geometry',params:{feature:'contours',threshold:127,minArea:50}},{id:'count',operation:'variables',params:{scope:'flow',name:'count',value:{$ref:'results.geometry.count'}}}]};
  continuous.start({project,maxCycles:3,intervalMs:100});await continuous.promise;
  assert.equal(continuous.status().state,'completed',continuous.status().error);assert.equal(runtime.snapshot(project).flow.count,3);
  const records=runtime.history.list({projectId:project.id}).items;
  assert.equal(records.length,3);assert.equal(manager.status().consumed,3);assert(manager.status().sequence>=4);
 }finally{await manager.shutdown();camera.setSessions(null);}
});

test('RGB-D session retains raw depth and calibrated clouds across multiple reads',async()=>{
 const manager=new CameraSession(folder(),camera);camera.setSessions(manager);
 try{
  const s=manager.start(config({params:{driver:'rgbd_simulator',deviceId:'synthetic-rgbd',timeoutMs:1000}}));await ready(manager);
  const one=await manager.capture(read(s.id)),two=await manager.capture(read(s.id));assert(two.result.frameSequence>one.result.frameSequence);
  assert.equal(one.depth.format,'png16');assert.equal(one.cloud.unit,'mm');assert.equal(one.depth.width,64);assert.deepEqual(one.cloud.points,two.cloud.points);
 }finally{await manager.shutdown();camera.setSessions(null);}
});

test('failure retries are bounded, resource is released, and interrupted records never reopen devices',async()=>{
 const dir=folder(),manager=new CameraSession(dir,camera);
 const state=manager.start(config({params:{driver:'simulator',deviceId:'missing',timeoutMs:1000},reconnectAttempts:2,reconnectMs:200}));
 await manager.closed;assert.equal(manager.status().state,'failed');assert.equal(manager.status().reconnects,2);assert.match(manager.status().error,/不存在/);assert.equal(manager.busy,false);
 assert.equal((await camera.run({operation:'camera_list',params:{driver:'simulator'}})).result.items.length,1);
 fs.writeFileSync(path.join(dir,'camera-session.json'),JSON.stringify({version:1,session:{...state,state:'running'}}));
 const restored=new CameraSession(dir,camera);assert.equal(restored.status().state,'interrupted');assert.equal(restored.status().buffered,false);assert.equal(restored.busy,false);
});

test('Node-RED camera node reads the same persistent SDK session and publishes typed frame metadata',async()=>{
 const {EventEmitter}=require('node:events');let CameraNode;
 const manager=new CameraSession(folder(),camera);camera.setSessions(manager);
 try{
  const s=manager.start(config());await ready(manager);
  require('../plugins/node-red-contrib-machine/nodes/camera.js')({settings:{machineCameras:camera},nodes:{createNode(node){EventEmitter.call(node);node.status=()=>{};},registerType(_name,constructor){CameraNode=constructor;}}});
  Object.setPrototypeOf(CameraNode.prototype,EventEmitter.prototype);const node=new CameraNode({params:JSON.stringify(read(s.id))});
  let sent;await new Promise((resolve,reject)=>node.emit('input',{},msg=>sent=msg,error=>error?reject(error):resolve()));
  assert.equal(sent.camera.sessionId,s.id);assert.equal(sent.payload.frameSequence,sent.camera.frameSequence);assert(sent.image.startsWith('data:image/png;base64,'));
  node.emit('close');assert.equal(manager.status().active,true);
 }finally{await manager.shutdown();camera.setSessions(null);}
});
