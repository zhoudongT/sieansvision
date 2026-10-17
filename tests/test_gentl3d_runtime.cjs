'use strict';
const {test,after}=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),{execFileSync}=require('node:child_process');
const camera=require('../lib/camera-client.cjs'),vision=require('../lib/vision-client.cjs'),{Runtime}=require('../lib/runtime.cjs'),{frame}=require('../lib/frame.cjs');
const root=path.resolve(__dirname,'..'),python=process.env.VISION_PYTHON||path.join(root,'.venv',process.platform==='win32'?'Scripts/python.exe':'bin/python');
after(()=>{camera.stop();vision.stop();});
for(const integer of [false,true])test('Harvesters-decoded '+(integer?'uint16':'float32')+' planar XYZ and confidence feed Open3D, scripts and typed variables',async()=>{
 const packet=frame(JSON.parse(execFileSync(python,['tests/gentl3d_fixture.py',...(integer?['--integer']:[])],{cwd:root,windowsHide:true,maxBuffer:5000000})));
 assert.equal(packet.depth,null);assert.equal(packet.cloud.points.length,189);
 const runtime=new Runtime(fs.mkdtempSync(path.join(os.tmpdir(),'sieans-gentl3d-')),vision);
 const project={version:1,name:'GenTL synthetic multipart runtime test',variables:{width:0},variableTypes:{width:'number'},steps:[
  {id:'crop',operation:'cloud_filter',params:{method:'crop',minimum:[10,-20,390],maximum:[18,3,410]}},
  {id:'measure',operation:'cloud_measure',params:{}},
  {id:'save',operation:'variables',params:{scope:'flow',name:'width',value:{$ref:'results.measure.sizeX'}}},
  {id:'script',operation:'script',params:{timeoutMs:5000,code:'def run(ctx):\n    c=ctx["cloud"]\n    return dict(result=dict(count=len(c["points"]),unit=c["unit"],width=ctx["vars"]["flow"]["width"]))',outputBindings:[{field:'count',scope:'global',name:'pointCount'},{field:'unit',scope:'module',name:'unit'}]}}
 ]};
 const start=runtime.start({project,...packet,allowScripts:true});await runtime.jobs.get(start.id).promise;const job=runtime.poll(start.id);
 assert.equal(job.state,'completed',job.error);assert.equal(job.results[0].output.cloud.points.length,189);
 assert.equal(job.results[1].output.result.sizeY,22);assert.equal(job.variables.flow.width,7.5);
 assert.equal(job.variables.global.pointCount,189);assert.equal(job.variables.modules.script.unit,'mm');
 assert.equal(job.results[3].output.result.width,7.5);
});
for(const coordinateFormat of ['Coord3D_ABC32f','Coord3D_ABC16'])test(coordinateFormat+' missing GenTL producer fails through real worker without fabricated point cloud',async()=>{
 const runtime=new Runtime(fs.mkdtempSync(path.join(os.tmpdir(),'sieans-gentl3d-missing-')),vision);
 const project={version:1,name:'GenTL missing-producer rollback',steps:[
  {id:'before',operation:'variables',params:{scope:'flow',name:'pending',value:1}},
  {id:'camera',operation:'camera_capture',params:{driver:'gentl',dataMode:'pointcloud',providerId:'sieans-no-such-provider',deviceId:'fixture',coordinateFormat,timeoutMs:5000}},
  {id:'after',operation:'variables',params:{scope:'flow',name:'ran',value:1}}
 ]};
 const start=runtime.start({project});await runtime.jobs.get(start.id).promise;const job=runtime.poll(start.id);
 assert.equal(job.state,'failed');assert.match(job.error,/GenTL/);assert.equal(job.results.length,2);assert.deepEqual(runtime.snapshot(project).flow,{});
});
