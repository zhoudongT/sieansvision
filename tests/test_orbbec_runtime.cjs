'use strict';
const {test,after}=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),{execFileSync}=require('node:child_process');
const camera=require('../lib/camera-client.cjs'),vision=require('../lib/vision-client.cjs'),{Runtime}=require('../lib/runtime.cjs'),{frame}=require('../lib/frame.cjs');
const root=path.resolve(__dirname,'..'),python=process.env.VISION_PYTHON||path.join(root,'.venv',process.platform==='win32'?'Scripts/python.exe':'bin/python');
after(()=>{camera.stop();vision.stop();});
test('native Orbbec software frames pass frame validation, Open3D, Python and variable bindings',async()=>{
 const packet=JSON.parse(execFileSync(python,['tests/orbbec_fixture.py'],{cwd:root,windowsHide:true,maxBuffer:5000000,stdio:['ignore','pipe','pipe']}));
 const checked=frame(packet);assert.equal(checked.depth.scaleMeters,.0005);assert.equal(checked.cloud.points.length,191);
 const runtime=new Runtime(fs.mkdtempSync(path.join(os.tmpdir(),'sieans-orbbec-')),vision);
 const project={version:1,name:'Orbbec SDK software frame test',steps:[
  {id:'crop',operation:'cloud_filter',params:{method:'crop',minimum:[-2000,-2000,900],maximum:[2000,2000,1500]}},
  {id:'measure',operation:'cloud_measure',params:{}},
  {id:'save',operation:'variables',params:{scope:'flow',name:'width',value:{$ref:'results.measure.sizeX'}}},
  {id:'script',operation:'script',params:{code:'def run(ctx):\n    import base64,cv2,numpy as np\n    d=ctx["depth"]\n    raw=cv2.imdecode(np.frombuffer(base64.b64decode(d["image"].split(",")[1]),np.uint8),cv2.IMREAD_UNCHANGED)\n    return dict(result=dict(raw=int(raw[-1,-1]),mm=float(raw[-1,-1])*d["scaleMeters"]*1000))',timeoutMs:5000}}
 ]};
 const start=runtime.start({project,...checked,allowScripts:true});await runtime.jobs.get(start.id).promise;const job=runtime.poll(start.id);
 assert.equal(job.state,'completed',job.error);assert.equal(job.results[0].output.cloud.points.length,190);
 assert.equal(job.variables.flow.width,1500);assert.equal(job.results[3].output.result.raw,4000);assert.equal(job.results[3].output.result.mm,2000);
});
test('Orbbec subprocess discovery keeps SDK output out of response and missing-device failure rolls back',async()=>{
 const providers=await camera.run({operation:'camera_providers',params:{}});assert.equal(providers.result.orbbec,'2.1.2');
 const list=await camera.run({operation:'camera_list',params:{driver:'orbbec',timeoutMs:10000}});assert.equal(list.result.simulated,false);assert(Array.isArray(list.result.items));
 const project={version:1,name:'Orbbec missing-device transaction',steps:[
  {id:'before',operation:'variables',params:{scope:'flow',name:'pending',value:1}},
  {id:'camera',operation:'camera_capture',params:{driver:'orbbec',deviceId:'sieans-nonexistent-device-test',enableColor:false,timeoutMs:10000}},
  {id:'after',operation:'variables',params:{scope:'flow',name:'ran',value:1}}
 ]};
 const runtime=new Runtime(fs.mkdtempSync(path.join(os.tmpdir(),'sieans-orbbec-missing-')),vision);
 const start=runtime.start({project});await runtime.jobs.get(start.id).promise;const job=runtime.poll(start.id);
 assert.equal(job.state,'failed');assert.match(job.error,/不存在/);assert.equal(job.results.length,2);assert.deepEqual(runtime.snapshot(project).flow,{});
 const recovered=await camera.run({operation:'camera_providers',params:{}});assert.equal(recovered.result.orbbec,'2.1.2');
});
