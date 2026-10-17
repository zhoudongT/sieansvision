const {test}=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path'),{spawnSync}=require('node:child_process');
const {OperatorPlugins,readPackage}=require('../lib/operator-plugins.cjs');
const {Runtime}=require('../lib/runtime.cjs');
const graph=require('../public/vision/flow-graph.js');
const temp=()=>fs.mkdtempSync(path.join(os.tmpdir(),'sieans-plugins-'));
function fixture(dir,{id='test-operator',version='1.0.0',apiVersion=1,code='def run(ctx):\n    return dict(result=dict(value=ctx["params"]["value"]*2))',outputs=[{key:'value',label:'结果',type:'number',required:true}]}={}){
 const folder=path.join(dir,'operator-plugins',id);fs.mkdirSync(folder,{recursive:true});
 const manifest={id,version,apiVersion,name:'测试插件',description:'仅用于隔离测试',license:'MIT',operators:[{id:'double',name:'倍增',description:'数值处理',input:'none',entry:'main.py',timeoutMs:1500,parameters:[{key:'value',label:'输入',type:'number',minimum:0,maximum:100,required:true,default:2}],outputs}]};
 fs.writeFileSync(path.join(folder,'operator-plugin.json'),JSON.stringify(manifest));fs.writeFileSync(path.join(folder,'main.py'),code);return {folder,manifest};
}
const params=(args={},extra={})=>({pluginId:'test-operator',pluginVersion:'1.0.0',operatorId:'double',arguments:args,...extra});
test('rescanning discovers additions, preserves disabled state and rejects changes during execution',async()=>{
 const dir=temp(),registry=new OperatorPlugins(dir,{bundled:path.join(dir,'empty')});
 assert.equal(registry.list().length,0);
 const {folder}=fixture(dir);registry.reload();
 assert.equal((await registry.run(params(),{})).data.result.value,4);
 registry.setEnabled('test-operator',false);registry.reload();
 await assert.rejects(registry.run(params(),{}),/停用/);
 registry.setEnabled('test-operator',true);
 const pending=registry.run(params(),{});
 assert.throws(()=>registry.reload(),/正在执行/);
 await pending;registry.reload();
 fs.writeFileSync(path.join(folder,'main.py'),'def run(ctx):\n    return dict(result=dict(value=99))');
 assert.equal((await registry.run(params(),{})).data.result.value,4);
 registry.reload();assert.equal((await registry.run(params(),{})).data.result.value,99);
 fs.rmSync(folder,{recursive:true});registry.reload();
 await assert.rejects(registry.run(params(),{}),/未安装/);
 fs.rmSync(dir,{recursive:true});
});
test('declared table columns validate row types, bounds and shape before Python execution',async()=>{
 const dir=temp(),{folder,manifest}=fixture(dir,{code:'def run(ctx):\n    return dict(result=dict(value=sum(r["x"] for r in ctx["params"]["points"])))'});
 manifest.operators[0].parameters=[{key:'points',label:'点位',type:'array',required:true,minimumRows:2,maximumRows:3,columns:[{key:'x',label:'X',type:'number',minimum:0,maximum:10,default:0}],default:[{x:2},{x:3}]}];
 fs.writeFileSync(path.join(folder,'operator-plugin.json'),JSON.stringify(manifest));
 const registry=new OperatorPlugins(dir);
 assert.equal((await registry.run(params(),{})).data.result.value,5);
 for(const points of [[{x:2}],[{x:2},{x:'3'}],[{x:2},{x:11}],[{x:2},null],[{x:2},{x:3,y:4}]])await assert.rejects(registry.run(params({points}),{}));
 for(const mutate of [m=>m.operators[0].parameters[0].columns[0].type='array',m=>m.operators[0].parameters[0].maximumRows=1,m=>m.operators[0].parameters[0].columns.push({key:'x',label:'重复',type:'number'})]){
  const m=structuredClone(manifest);mutate(m);fs.writeFileSync(path.join(folder,'operator-plugin.json'),JSON.stringify(m));assert.throws(()=>readPackage(folder));
 }
});
test('planar calibration, metric measurements and variable-bound calibration execute in real plugin processes',async()=>{
 const samples=path.join(__dirname,'../public/vision/samples');
 for(const demo of JSON.parse(fs.readFileSync(path.join(samples,'demos-plugins.json'))).filter(d=>d.id.startsWith('planar-'))){
  const dir=temp(),runtime=new Runtime(dir,{},new OperatorPlugins(dir));
  const p=project(demo.steps.map((s,i)=>({...s,id:'p'+i}))),image='data:image/png;base64,'+fs.readFileSync(path.join(samples,demo.image)).toString('base64');
  const job=await run(runtime,p,{image});assert.equal(job.state,'completed',job.error);
  assert.equal(job.results[0].output.result.inlierCount,demo.id==='planar-outlier'?8:9);
  assert(Math.abs(job.variables.flow.measuredLength-(demo.id==='planar-perimeter'?180:60))<.0001);
  assert.equal(job.variables.flow.planeCalibration.model,'sieans-plane-homography-v1');
  assert(job.results[1].output.annotatedImage.startsWith('data:image/png;base64,'));
 }
});
const step=(id,operation,p)=>({id,operation,params:p});
test('normal inspection demos execute with typed results, colored clouds and bound quality variables',async()=>{
 const samples=path.join(__dirname,'../public/vision/samples');
 for(const demo of JSON.parse(fs.readFileSync(path.join(samples,'demos-plugins.json'))).filter(d=>d.id.startsWith('normals-'))){
  const dir=temp(),runtime=new Runtime(dir,{},new OperatorPlugins(dir));
  const p=project(demo.steps.map((s,i)=>({...s,id:'normal'+i}))),cloud=JSON.parse(fs.readFileSync(path.join(samples,demo.cloud)));
  const job=await run(runtime,p,{cloud});assert.equal(job.state,'completed',job.error);
  const output=job.results[0].output,r=output.result;
  assert.equal(job.variables.flow.slopeOK,demo.id==='normals-pass');
  assert.equal(job.variables.flow.invalidNormals,demo.id==='normals-invalid'?121:0);
  assert.equal(r.outsideCount,demo.id==='normals-fail'?121:0);
  assert.deepEqual(output.cloud.points,cloud.points);assert.equal(output.cloud.frame,cloud.frame);
  if(demo.id!=='normals-invalid')assert(Math.abs(r.meanSlopeDegrees-30)<1e-8);
  else assert.equal(r.meanSlopeDegrees,undefined);
 }
});
const project=steps=>graph.normalize({version:1,id:'plugin-test',name:'插件测试',steps});
async function run(runtime,p,options={}){const job=runtime.start({project:p,...options});await runtime.jobs.get(job.id).promise;return runtime.poll(job.id);}
test('discovery loads compatible metadata without executing code; invalid packages have diagnostics',()=>{
 const dir=temp(),marker=path.join(dir,'executed');fixture(dir,{code:`open(${JSON.stringify(marker)},'w').write('x')`});fixture(dir,{id:'bad-api',apiVersion:2});
 const registry=new OperatorPlugins(dir);assert.equal(fs.existsSync(marker),false);assert.equal(registry.list().find(p=>p.id==='bad-api').status,'加载失败');assert.equal(registry.get(params()).op.id,'double');
});
test('manifest rejects unsafe entries, duplicate names, bad bounds and default types',()=>{
 const dir=temp(),{folder,manifest}=fixture(dir);
 for(const mutate of [m=>m.operators[0].entry='../outside.py',m=>m.operators[0].parameters.push({...m.operators[0].parameters[0]}),m=>m.operators[0].parameters[0].minimum=101,m=>m.operators[0].parameters[0].default='2',m=>m.operators[0].outputs[0].key='__proto__']){
  const m=structuredClone(manifest);mutate(m);fs.writeFileSync(path.join(folder,'operator-plugin.json'),JSON.stringify(m));assert.throws(()=>readPackage(folder));
 }
});
test('disabled and incompatible versions fail before earlier variable or device actions',()=>{
 const dir=temp();fixture(dir);const registry=new OperatorPlugins(dir),runtime=new Runtime(dir,{},registry);
 const p=project([step('v','variables',{scope:'global',name:'count',value:9}),step('op','plugin',params())]);
 registry.setEnabled('test-operator',false);assert.throws(()=>runtime.start({project:p}),/停用/);assert.deepEqual(runtime.snapshot(p).global,{});
 assert.equal(new OperatorPlugins(dir).list().find(p=>p.id==='test-operator').enabled,false);
 registry.setEnabled('test-operator',true);p.steps[1].params.pluginVersion='2.0.0';assert.throws(()=>runtime.start({project:p}),/版本不匹配/);assert.equal(runtime.active,null);
});
test('real external Python plugin consumes upstream binding and maps results into all scopes',async()=>{
 const dir=temp();fixture(dir);const runtime=new Runtime(dir,{},new OperatorPlugins(dir));
 const p=project([step('start','variables',{scope:'flow',name:'source',value:6}),step('op','plugin',params({value:{$ref:'results.start.value'}},{outputBindings:['flow','global','module'].map(scope=>({scope,name:'answer',field:'value'}))})),step('read','variables',{scope:'flow',name:'downstream',value:{$ref:'results.op.value'}})]);
 const job=await run(runtime,p);assert.equal(job.state,'completed',job.error);assert.equal(job.variables.flow.downstream,12);assert.equal(job.variables.global.answer,12);assert.equal(job.variables.modules.op.answer,12);
});
test('input/result contracts reject types, ranges, unknown arguments and malformed plugin output; roll back variables',async()=>{
 const dir=temp();fixture(dir);let runtime=new Runtime(dir,{},new OperatorPlugins(dir));
 for(const args of [{value:'4'},{value:101},{typo:5}]){const p=project([step('set','variables',{scope:'global',name:'bad',value:1}),step('op','plugin',params(args))]);const job=await run(runtime,p);assert.equal(job.state,'failed');assert.deepEqual(runtime.snapshot(p).global,{});}
 fixture(dir,{code:'def run(ctx):\n    return dict(result=dict(value="wrong"))'});runtime=new Runtime(dir,{},new OperatorPlugins(dir));const job=await run(runtime,project([step('op','plugin',params())]));assert.equal(job.state,'failed');assert.match(job.error,/类型/);
});
test('plugin timeout and cancellation release runtime and roll back earlier assignments',async()=>{
 const dir=temp();fixture(dir,{code:'import time\ndef run(ctx):\n    time.sleep(10)\n    return dict(result=dict(value=1))'});const runtime=new Runtime(dir,{},new OperatorPlugins(dir));
 const p=project([step('set','variables',{scope:'flow',name:'bad',value:1}),step('op','plugin',params())]);let job=await run(runtime,p);assert.equal(job.state,'failed');assert.match(job.error,/超时/);assert.deepEqual(runtime.snapshot(p).flow,{});
 job=runtime.start({project:p});runtime.cancel(job.id);await runtime.jobs.get(job.id).promise;assert.equal(runtime.poll(job.id).state,'cancelled');assert.equal(runtime.active,null);assert.deepEqual(runtime.snapshot(p).flow,{});
});
test('bundled OpenCV brightness and point centroid return known values and enforce input channel',async()=>{
 const dir=temp(),runtime=new Runtime(dir,{},new OperatorPlugins(dir));const base={pluginId:'sieans-inspection',pluginVersion:'1.0.0'};
 let p=project([step('op','plugin',{...base,operatorId:'brightness',arguments:{minimumMean:0,maximumMean:255}})]);
 let job=await run(runtime,p);assert.equal(job.state,'failed');assert.match(job.error,/输入图像/);
 const image='data:image/png;base64,'+fs.readFileSync(path.join(__dirname,'../public/vision/samples/parts.png')).toString('base64');
 job=await run(runtime,p,{image});assert.equal(job.state,'completed',job.error);assert.equal(job.results[0].output.result.pixelCount,700*420);assert.equal(job.results[0].output.result.passed,true);
 const generated=await require('../lib/script-runner.cjs').run('import cv2, numpy as np, base64\ndef run(ctx):\n    _, data = cv2.imencode(".png", np.array([[0,64],[128,192]], dtype=np.uint8))\n    return dict(result=dict(image="data:image/png;base64,"+base64.b64encode(data).decode()))',{});
 job=await run(runtime,p,{image:generated.data.result.image});assert.equal(job.state,'completed',job.error);assert.equal(job.results[0].output.result.meanIntensity,96);assert(Math.abs(job.results[0].output.result.intensityDeviation-Math.sqrt(5120))<1e-10);
 p=project([step('op','plugin',{...base,operatorId:'centroid',arguments:{targetX:1,targetY:2,targetZ:3,tolerance:0}})]);
 job=await run(runtime,p,{cloud:{unit:'mm',points:[[0,0,0],[2,4,6]]}});assert.equal(job.state,'completed',job.error);assert.deepEqual(job.results[0].output.result.centroid,[1,2,3]);assert.equal(job.results[0].output.result.distanceToTarget,0);assert.equal(job.results[0].output.result.passed,true);
});
test('local installation validates and copies entries without running them, refuses overwrite',()=>{
 const source=temp(),target=temp(),{folder}=fixture(source);const command=path.join(__dirname,'../scripts/operator-plugin.cjs');const options={env:{...process.env,MACHINE_DATA_DIR:target},encoding:'utf8',windowsHide:true};
 let result=spawnSync(process.execPath,[command,'install',folder],options);assert.equal(result.status,0,result.stderr);assert.equal(new OperatorPlugins(target).get(params()).op.name,'倍增');
 result=spawnSync(process.execPath,[command,'install',folder],options);assert.equal(result.status,1);assert.match(result.stderr,/已安装/);
});
test('duplicate plugin IDs disable all copies instead of silently selecting a version',()=>{
 const dir=temp(),{folder}=fixture(dir);fs.cpSync(folder,path.join(dir,'operator-plugins','second-copy'),{recursive:true});
 const registry=new OperatorPlugins(dir);assert.throws(()=>registry.get(params()),/未安装/);assert.equal(registry.list().filter(p=>p.id==='test-operator'&&p.enabled).length,0);
});
test('plugin can explicitly clear cloud and depth without restoring stale upstream data',async()=>{
 const dir=temp();fixture(dir,{code:'def run(ctx):\n    return dict(result=dict(value=1), cloud=None, depth=None)'});
 const runtime=new Runtime(dir,{},new OperatorPlugins(dir));
 const p=project([step('op','plugin',params()),step('check','script',{code:'def run(ctx):\n    return dict(result=dict(hasCloud=ctx["cloud"] is not None, hasDepth=ctx["depth"] is not None))'})]);
 const job=await run(runtime,p,{cloud:{unit:'mm',points:[[0,0,0]]},allowScripts:true});assert.equal(job.state,'completed',job.error);assert.equal(job.results[1].output.result.hasCloud,false);assert.equal(job.results[1].output.result.hasDepth,false);
});
