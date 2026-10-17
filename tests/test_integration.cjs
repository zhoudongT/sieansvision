const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const net = require('node:net');
const { spawn } = require('node:child_process');
const { once } = require('node:events');
const root = path.resolve(__dirname, '..');
let port,url,server;
const globalDemo=process.env.TEST_3D==='true'?JSON.parse(fs.readFileSync(path.join(root,'public/vision/samples/demos-3d.json'))).find(d=>d.id==='cloud-global'):null;
const globalCloud=globalDemo?JSON.parse(fs.readFileSync(path.join(root,'public/vision/samples',globalDemo.cloud))):null;
const dataDir = fs.mkdtempSync(path.join(os.tmpdir(), 'machine-vision-test-'));
let logs = '';
const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
async function boundedExit(promise,ms){let timer;try{await Promise.race([promise,new Promise(resolve=>{timer=setTimeout(resolve,ms);})]);}finally{clearTimeout(timer);}}
async function json(route, method='GET', body) {
  const response = await fetch(url+route, {method, headers:{'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body),signal:AbortSignal.timeout(30000)});
  return {status:response.status,body:await response.json()};
}
async function main() {
  const listener=net.createServer();listener.listen(0,'127.0.0.1');await once(listener,'listening');port=listener.address().port;await new Promise(resolve=>listener.close(resolve));url=`http://127.0.0.1:${port}`;
  server=spawn(process.execPath,['server.cjs'],{cwd:root,windowsHide:true,stdio:['ignore','pipe','pipe','ipc'],env:{...process.env,PORT:String(port),HOST:'127.0.0.1',MACHINE_DATA_DIR:dataDir,ADMIN_PASSWORD_HASH:'',OPERATOR_PASSWORD_HASH:''}});
  server.stdout.on('data',b=>logs+=b);server.stderr.on('data',b=>logs+=b);
  let ready=false;
  for(let i=0;i<80;i++){if(server.exitCode!==null)throw Error(logs);try{ready=logs.includes('http://127.0.0.1:'+port)&&(await fetch(url+'/health')).ok;if(ready)break;}catch{}await delay(200);}
  assert(ready,logs);
  assert.equal((await json('/api/vision/dashboard')).body.bases[0].id,'dashboard-base');
  const image='data:image/png;base64,'+fs.readFileSync(path.join(root,'public/vision/samples/codes.png')).toString('base64');
  const direct=await json('/api/vision/run','POST',{operation:'barcode',image});
  assert.equal(direct.status,200);
  assert.equal(direct.body.result.count,2);
  const failure=await json('/api/vision/run','POST',{operation:'geometry',image:'invalid'});
  assert.equal(failure.status,400);
  assert(failure.body.error);
  const project={version:1,name:'integration',steps:[{id:'barcode',operation:'barcode',params:{}}]};
  assert.equal((await json('/api/vision/project','PUT',project)).status,200);
  assert.equal((await json('/api/vision/project')).body.steps[0].operation,'barcode');
  assert.equal((await json('/api/vision/project','PUT',{version:99})).status,400);
  const graph=require('../public/vision/flow-graph.js');
  const connected=graph.normalize({version:1,name:'graph persistence',steps:[{id:'first',operation:'preprocess',params:{method:'grayscale'}},{id:'last',operation:'geometry',params:{}}]});
  connected.steps[0].position={x:460,y:90};connected.steps.reverse();
  assert.equal((await json('/api/vision/project','PUT',connected)).status,200);
  const restored=(await json('/api/vision/project')).body;
  assert.equal(restored.version,2);assert.deepEqual(restored.edges,connected.edges);assert.deepEqual(restored.steps,connected.steps);assert.deepEqual(graph.order(restored).map(s=>s.id),['first','last']);
  const cyclic=structuredClone(connected);cyclic.edges.push({id:'cycle',from:'last',to:'first'});
  assert.equal((await json('/api/vision/project','PUT',cyclic)).status,400);
  assert.deepEqual((await json('/api/vision/project')).body.edges,connected.edges);
  const scripted=graph.normalize({version:1,id:'runtime-http',name:'scripted',steps:[{id:'read',operation:'barcode',params:{}},{id:'script',operation:'script',params:{timeoutMs:3000,code:'def run(ctx):\n    n=ctx["results"]["read"]["count"]\n    v=ctx["vars"]\n    v["flow"]["count"]=n\n    return {"result":{"count":n},"variables":v}'}}]});
  assert.equal((await json('/api/vision/runtime/jobs','POST',{project:scripted,image})).status,400);
  const started=await json('/api/vision/runtime/jobs','POST',{project:scripted,image,allowScripts:true});assert.equal(started.status,202,JSON.stringify(started.body));
  let job=started.body;for(let i=0;i<100&&job.state==='running';i++){await delay(50);job=(await json('/api/vision/runtime/jobs/'+started.body.id)).body;}
  assert.equal(job.state,'completed',JSON.stringify(job));assert.equal(job.results.at(-1).output.result.count,2);
  const values=await json('/api/vision/runtime/variables/read','POST',{project:scripted});assert.equal(values.body.flow.count,2);
  assert.equal((await json('/api/vision/runtime/variables','PUT',{project:scripted,revision:values.body.revision-1,values:values.body})).status,409);
  assert.equal((await json('/api/vision/project','PUT',scripted)).status,200);
  assert.equal((await json('/api/vision/project')).body.id,scripted.id);
  const branched=graph.normalize({version:2,id:'condition-http',name:'Conditional HTTP',steps:[
    {id:'c',operation:'condition',params:{comparison:'eq',left:3,right:3}},
    {id:'yes',operation:'variables',params:{name:'route',value:'OK'}},
    {id:'no',operation:'variables',params:{name:'route',value:'RECHECK'}},
    {id:'merge',operation:'branch_merge',params:{}}
  ],edges:[{id:'a',from:'source',to:'c'},{id:'b',from:'c',to:'yes',when:'true'},{id:'c',from:'c',to:'no',when:'false'},{id:'d',from:'yes',to:'merge'},{id:'e',from:'no',to:'merge'}]});
  assert.equal((await json('/api/vision/project','PUT',branched)).status,200);
  const branchSaved=(await json('/api/vision/project')).body;assert.deepEqual(branchSaved.edges,branched.edges);
  for(const [expected,route,skipped] of [[3,'OK','no'],[4,'RECHECK','yes']]){
    branchSaved.steps[0].params.right=expected;const start=await json('/api/vision/runtime/jobs','POST',{project:branchSaved});assert.equal(start.status,202);let current=start.body;
    for(let i=0;i<100&&current.state==='running';i++){await delay(30);current=(await json('/api/vision/runtime/jobs/'+current.id)).body;}
    assert.equal(current.state,'completed',current.error);assert.equal(current.variables.flow.route,route);assert.equal(current.results.find(row=>row.id===skipped).skipped,true);assert.equal(current.results.at(-1).output.result.value.value,route);
  }
  console.log('PASS: conditional flow persistence, both branches, skipped nodes and exclusive merge over HTTP');
  const plugins=(await json('/api/vision/plugins')).body.plugins;assert.equal(plugins.find(p=>p.id==='sieans-inspection').operators.length,2);
  const plugged=graph.normalize({version:1,id:'plugin-http',name:'Plugin HTTP',steps:[{id:'plugin',operation:'plugin',params:{pluginId:'sieans-inspection',pluginVersion:'1.0.0',operatorId:'brightness',arguments:{minimumMean:0,maximumMean:255},outputBindings:[{field:'passed',scope:'flow',name:'brightnessOK'}]}}]});
  assert.equal((await json('/api/vision/project','PUT',plugged)).status,200);assert.equal((await json('/api/vision/project')).body.steps[0].params.pluginVersion,'1.0.0');
  assert.equal((await json('/api/vision/plugins/sieans-inspection','PUT',{enabled:false})).status,200);
  assert.equal((await json('/api/vision/runtime/jobs','POST',{project:plugged,image})).status,400);
  assert.equal((await json('/api/vision/plugins/sieans-inspection','PUT',{enabled:true})).status,200);
  let pluginJob=(await json('/api/vision/runtime/jobs','POST',{project:plugged,image})).body;
  for(let i=0;i<100&&pluginJob.state==='running';i++){await delay(30);pluginJob=(await json('/api/vision/runtime/jobs/'+pluginJob.id)).body;}
  assert.equal(pluginJob.state,'completed',pluginJob.error);assert.equal(pluginJob.variables.flow.brightnessOK,true);
  const waiting=graph.normalize({version:1,id:'plugin-lock',name:'Lock plugins',steps:[{id:'delay',operation:'delay',params:{milliseconds:30000}}]});
  const waitingJob=(await json('/api/vision/runtime/jobs','POST',{project:waiting})).body;
  assert.equal((await json('/api/vision/plugins/sieans-inspection','PUT',{enabled:false})).status,409);
  await json('/api/vision/runtime/jobs/'+waitingJob.id+'/cancel','POST');
  for(let i=0;i<100;i++){if((await json('/api/vision/runtime/jobs/'+waitingJob.id)).body.state!=='running')break;await delay(30);}
  console.log('PASS: plugin discovery, enable/disable, pinned project persistence, actual Python execution, typed variable binding and active-job lock');
  const hmiLayout=require('../public/vision/hmi-layout.js');
  plugged.hmi={...hmiLayout.empty(),components:[{id:'number',type:'value',label:'亮度',x:0,y:0,w:4,h:2,color:'#1095bd',fontSize:24,precision:2,unit:'',binding:{source:'result',nodeId:'plugin',path:'meanIntensity'}}]};
  assert.equal((await json('/api/vision/project','PUT',plugged)).status,200);
  assert.deepEqual((await json('/api/vision/project')).body.hmi,plugged.hmi);
  const view=(await json('/api/vision/runtime/view','POST',{project:plugged})).body;assert.equal(view.status.state,'completed');assert.equal(view.variables.flow.brightnessOK,true);assert.equal(typeof hmiLayout.read(plugged.hmi.components[0].binding,view),'number');
  const unchanged=(await json('/api/vision/runtime/view','POST',{project:plugged,since:view.version})).body;assert.equal(unchanged.results,undefined);assert.equal(unchanged.status.id,view.status.id);
  const invalidHmi=structuredClone(plugged);invalidHmi.hmi.components[0].type='html';assert.equal((await json('/api/vision/project','PUT',invalidHmi)).status,400);assert.deepEqual((await json('/api/vision/project')).body.hmi,plugged.hmi);
  console.log('PASS: HMI layout persistence, invalid layout rejection, cross-client runtime view and unchanged result suppression');
  for(const [id,expected] of [['color-regions',2],['color-to-blobs',1],['surface-deviations',2],['normals-pass',0],['normals-fail',121],['normals-invalid',0]]){
    const demo=JSON.parse(fs.readFileSync(path.join(root,'public/vision/samples/demos-plugins.json'),'utf8')).find(d=>d.id===id);
    const p=graph.normalize({version:1,id:'inspection-'+id,name:demo.name,steps:demo.steps.map((s,i)=>({...s,id:'node'+i}))});
    const request={project:p,...(demo.cloud?{cloud:JSON.parse(fs.readFileSync(path.join(root,'public/vision/samples',demo.cloud),'utf8'))}:{image:'data:image/png;base64,'+fs.readFileSync(path.join(root,'public/vision/samples',demo.image)).toString('base64')})};
    const start=await json('/api/vision/runtime/jobs','POST',request);assert.equal(start.status,202,JSON.stringify(start.body));let current=start.body;
    for(let i=0;i<200&&current.state==='running';i++){await delay(50);current=(await json('/api/vision/runtime/jobs/'+current.id)).body;}
    assert.equal(current.state,'completed',current.error);const output=current.results.at(-1).output,result=output.result;
    if(id.startsWith('normals-')){
      assert.equal(result.outsideCount,expected);assert.equal(result.pointCount,121);
      assert.equal(current.variables.flow.slopeOK,id==='normals-pass');assert.equal(current.variables.flow.invalidNormals,id==='normals-invalid'?121:0);
      assert.deepEqual(output.cloud.points,request.cloud.points);
      assert.deepEqual(output.cloud.colors[0],id==='normals-pass'?[.1,.75,.4]:id==='normals-fail'?[1,.15,.1]:[.6,.6,.6]);
      if(id==='normals-invalid')assert.equal(result.meanSlopeDegrees,undefined);else assert(Math.abs(result.meanSlopeDegrees-30)<1e-8);
    }else if(id==='surface-deviations'){
      assert.equal(result.outsideCount,expected);assert.equal(result.pointCount,121);assert.equal(result.passed,false);
      assert.equal(current.variables.flow.surfaceDefects,2);assert.equal(output.cloud.points.length,121);assert.deepEqual(output.cloud.colors[24],[1,.15,.1]);
    }else{
      assert.equal(result.count,expected);assert.equal(result.passed,true);assert.match(output.annotatedImage,/^data:image\/png;base64,/);
      assert.equal(result.areaPixels,id==='color-regions'?16800:12000);
      if(id==='color-regions')assert.equal(current.variables.flow.redCount,2);
      else assert.equal(result.items[0].centerX,109.5);
    }
    assert.equal((await json('/api/vision/project','PUT',p)).status,200);
    assert.deepEqual((await json('/api/vision/project')).body.steps.map(s=>s.params),p.steps.map(s=>s.params));
  }
  console.log('PASS: HSV wrap and variable binding, color mask to blob pipeline, 3D tolerance colors/results and project roundtrips');
  const planarDemo=JSON.parse(fs.readFileSync(path.join(root,'public/vision/samples/demos-plugins.json'))).find(d=>d.id==='planar-perimeter');
  const planarProject=graph.normalize({version:1,id:'planar-http',name:planarDemo.name,steps:planarDemo.steps.map((step,i)=>({...step,id:'plane'+i}))});
  const planarImage='data:image/png;base64,'+fs.readFileSync(path.join(root,'public/vision/samples/planar-calibration.png')).toString('base64');
  const planarStart=await json('/api/vision/runtime/jobs','POST',{project:planarProject,image:planarImage});assert.equal(planarStart.status,202,JSON.stringify(planarStart));let planarJob=planarStart.body;
  for(let i=0;i<200&&planarJob.state==='running';i++){await delay(30);planarJob=(await json('/api/vision/runtime/jobs/'+planarJob.id)).body;}
  assert.equal(planarJob.state,'completed',planarJob.error);assert(Math.abs(planarJob.variables.flow.measuredLength-180)<.0001);
  assert.equal(planarJob.results[1].output.result.items.length,4);assert.equal(planarJob.results[1].output.result.points.length,4);
  assert.equal((await json('/api/vision/project','PUT',planarProject)).status,200);assert.deepEqual((await json('/api/vision/project')).body.steps[0].params.arguments.points,planarProject.steps[0].params.arguments.points);
  const planarStored=(await json('/api/vision/runtime/variables/read','POST',{project:planarProject})).body;assert.equal(planarStored.flow.planeCalibration.model,'sieans-plane-homography-v1');
  const invalidPlanar=structuredClone(planarProject);invalidPlanar.steps[0].params.arguments.points[0].pixelX='bad';const invalidStart=await json('/api/vision/runtime/jobs','POST',{project:invalidPlanar,image:planarImage});let invalidJob=invalidStart.body;
  for(let i=0;i<100&&invalidJob.state==='running';i++){await delay(30);invalidJob=(await json('/api/vision/runtime/jobs/'+invalidJob.id)).body;}
  assert.equal(invalidJob.state,'failed');assert.match(invalidJob.error,/类型/);assert.equal((await json('/api/vision/runtime/variables/read','POST',{project:planarProject})).body.revision,planarStored.revision);
  console.log('PASS: planar calibration table persistence, typed row validation, metric perimeter and bound calibration variables');
  const caliperDemos=JSON.parse(fs.readFileSync(path.join(root,'public/vision/samples/demos-caliper.json')));
  for(const demo of caliperDemos){
    const p=graph.normalize({version:1,id:'http-'+demo.id,name:demo.name,steps:demo.steps.map((s,i)=>({...s,id:'caliper'+i}))});
    const input='data:image/png;base64,'+fs.readFileSync(path.join(root,'public/vision/samples',demo.image)).toString('base64');
    let started=await json('/api/vision/runtime/jobs','POST',{project:p,image:input});assert.equal(started.status,202);let job=started.body;
    for(let i=0;i<200&&job.state==='running';i++){await delay(30);job=(await json('/api/vision/runtime/jobs/'+job.id)).body;}
    assert.equal(job.state,'completed',job.error);const out=job.results[0].output;
    assert.equal(out.result.passed,['caliper-line','caliper-width-pass'].includes(demo.id));assert.equal(out.image,input);assert.match(out.annotatedImage,/^data:image\/jpeg;base64,/);
    if(demo.id.includes('width'))assert(Math.abs(job.variables.flow.measuredWidth-(demo.id.endsWith('pass')?8.04:8.6))<.015);
    assert.equal((await json('/api/vision/project','PUT',p)).status,200);assert.deepEqual((await json('/api/vision/project')).body.steps[0].params,p.steps[0].params);
  }
  console.log('PASS: caliper HTTP demos, pass/fail/no-edge diagnostics, frame separation, variables and project persistence');
  const sphereDemos=JSON.parse(fs.readFileSync(path.join(root,'public/vision/samples/demos-sphere.json')));
  for(const demo of sphereDemos){
    const p=graph.normalize({version:1,id:'http-'+demo.id,name:demo.name,steps:demo.steps.map((s,i)=>({...s,id:'sphere'+i}))});
    const cloud=JSON.parse(fs.readFileSync(path.join(root,'public/vision/samples',demo.cloud)));
    let start=await json('/api/vision/runtime/jobs','POST',{project:p,cloud});assert.equal(start.status,202);let job=start.body;
    for(let i=0;i<200&&job.state==='running';i++){await delay(30);job=(await json('/api/vision/runtime/jobs/'+job.id)).body;}
    assert.equal(job.state,'completed',job.error);const out=job.results.at(-1).output;
    assert.equal(out.result.passed,demo.id==='sphere-fit');assert.deepEqual(out.cloud.points,cloud.points);assert.equal(out.cloud.frame,cloud.frame);
    if(['sphere-inspect','sphere-chain'].includes(demo.id))assert.equal(job.variables.flow.sphereDefects,2);
    if(demo.id==='sphere-narrow')assert.equal(out.result.sphere,undefined);
    assert.equal((await json('/api/vision/project','PUT',p)).status,200);assert.deepEqual((await json('/api/vision/project')).body.steps.map(s=>s.params),p.steps.map(s=>s.params));
  }
  console.log('PASS: sphere HTTP fit/inspect chains, signed defects, narrow-cap rejection, diameter failure and model persistence');
  const cylinderDemos=JSON.parse(fs.readFileSync(path.join(root,'public/vision/samples/demos-cylinder.json')));
  for(const demo of cylinderDemos){
    const p=graph.normalize({version:1,id:'http-'+demo.id,name:demo.name,steps:demo.steps.map((s,i)=>({...s,id:'cylinder'+i}))});
    const cloud=JSON.parse(fs.readFileSync(path.join(root,'public/vision/samples',demo.cloud)));
    let start=await json('/api/vision/runtime/jobs','POST',{project:p,cloud});assert.equal(start.status,202);let job=start.body;
    for(let i=0;i<200&&job.state==='running';i++){await delay(30);job=(await json('/api/vision/runtime/jobs/'+job.id)).body;}
    assert.equal(job.state,'completed',job.error);const out=job.results.at(-1).output;
    assert.equal(out.result.passed,demo.id==='cylinder-fit');assert.deepEqual(out.cloud.points,cloud.points);assert.equal(out.cloud.frame,cloud.frame);
    if(['cylinder-inspect','cylinder-chain'].includes(demo.id))assert.equal(job.variables.flow.cylinderDefects,2);
    if(demo.id==='cylinder-narrow')assert.equal(out.result.cylinder,undefined);
    assert.equal((await json('/api/vision/project','PUT',p)).status,200);assert.deepEqual((await json('/api/vision/project')).body.steps.map(s=>s.params),p.steps.map(s=>s.params));
  }
  console.log('PASS: cylinder HTTP fit/inspect chains, signed defects, narrow-arc rejection, diameter failure and model persistence');
  const typedProject=graph.normalize({version:1,id:'typed-http',name:'固定类型 HTTP',variables:{count:0},variableTypes:{count:'integer'},steps:[{id:'typed',operation:'variables',params:{scope:'flow',name:'count',value:3},variables:{ok:false},variableTypes:{ok:'boolean'}}]});
  assert.equal((await json('/api/vision/project','PUT',typedProject)).status,200);
  const savedTyped=(await json('/api/vision/project')).body;assert.deepEqual(savedTyped.variableTypes,{count:'integer'});assert.deepEqual(savedTyped.steps[0].variableTypes,{ok:'boolean'});
  let typedStart=await json('/api/vision/runtime/jobs','POST',{project:typedProject});assert.equal(typedStart.status,202);let typedJob=typedStart.body;
  for(let i=0;i<100&&typedJob.state==='running';i++){await delay(30);typedJob=(await json('/api/vision/runtime/jobs/'+typedJob.id)).body;}
  assert.equal(typedJob.state,'completed',typedJob.error);assert.equal(typedJob.variables.flow.count,3);
  let typedState=(await json('/api/vision/runtime/variables/read','POST',{project:typedProject})).body;
  const invalidTyped=structuredClone(typedState);invalidTyped.flow.count='4';
  const rejectedTyped=await json('/api/vision/runtime/variables','PUT',{project:typedProject,values:invalidTyped,revision:typedState.revision});assert.equal(rejectedTyped.status,409);assert.match(rejectedTyped.body.error,/flow.count 类型不匹配/);
  assert.equal((await json('/api/vision/runtime/variables/read','POST',{project:typedProject})).body.revision,typedState.revision);
  typedState.global.testTypedFlag=true;typedState.globalTypes.testTypedFlag='boolean';
  let definedGlobal=await json('/api/vision/runtime/variables','PUT',{project:typedProject,values:typedState,revision:typedState.revision});assert.equal(definedGlobal.status,200);
  const otherTyped=graph.normalize({version:1,id:'typed-other',name:'跨工程类型',steps:[{id:'bad',operation:'variables',params:{scope:'global',name:'testTypedFlag',value:1}}]});
  let globalJob=(await json('/api/vision/runtime/jobs','POST',{project:otherTyped})).body;
  for(let i=0;i<100&&globalJob.state==='running';i++){await delay(30);globalJob=(await json('/api/vision/runtime/jobs/'+globalJob.id)).body;}
  assert.equal(globalJob.state,'failed');assert.match(globalJob.error,/global.testTypedFlag 类型不匹配/);
  typedState=(await json('/api/vision/runtime/variables/read','POST',{project:typedProject})).body;delete typedState.globalTypes.testTypedFlag;delete typedState.global.testTypedFlag;
  assert.equal((await json('/api/vision/runtime/variables','PUT',{project:typedProject,values:typedState,revision:typedState.revision})).status,200);
  console.log('PASS: fixed flow/module type persistence, integer assignment, HMI-style write rejection and cross-project global contracts');
  const repeated=graph.normalize({version:1,id:'continuous-http',name:'模拟相机连续检测',steps:[
    {id:'camera',operation:'camera_capture',params:{driver:'simulator',deviceId:'synthetic-parts',trigger:'freerun',timeoutMs:5000}},
    {id:'detect',operation:'geometry',params:{feature:'contours',minArea:50}},
    {id:'cycles',operation:'variables',params:{scope:'flow',name:'cycles',mode:'increment',value:1}}
  ]});
  const continuousStart=await json('/api/vision/runtime/continuous','POST',{project:repeated,intervalMs:100,maxCycles:3});assert.equal(continuousStart.status,202,JSON.stringify(continuousStart.body));
  let continuous=continuousStart.body;
  for(let i=0;i<200&&continuous.busy;i++){await delay(30);continuous=(await json('/api/vision/runtime/continuous')).body;}
  assert.equal(continuous.state,'completed',continuous.error);assert.equal(continuous.completedCycles,3);
  const continuousView=(await json('/api/vision/runtime/view','POST',{project:repeated})).body;
  assert.equal(continuousView.variables.flow.cycles,3);assert.equal(continuousView.results[1].output.result.count,3);assert.equal(continuousView.continuous.id,continuousStart.body.id);
  assert.equal((await json('/api/vision/runtime/continuous/project')).body.project.id,repeated.id);
  const endless=(await json('/api/vision/runtime/continuous','POST',{project:repeated,intervalMs:5000,maxCycles:0})).body;
  for(let i=0;i<200;i++){continuous=(await json('/api/vision/runtime/continuous')).body;if(continuous.state==='waiting')break;await delay(30);}
  assert.equal(continuous.state,'waiting');
  assert.equal((await json('/api/vision/runtime/jobs','POST',{project:repeated})).status,409);
  assert.equal((await json('/api/vision/project','PUT',repeated)).status,409);
  assert.equal((await json('/api/vision/plugins/sieans-inspection','PUT',{enabled:false})).status,409);
  assert.equal((await json('/api/vision/cameras/run','POST',{operation:'camera_capture',params:{driver:'simulator'}})).status,409);
  const loopVars=(await json('/api/vision/runtime/variables/read','POST',{project:repeated})).body;
  assert.equal((await json('/api/vision/runtime/variables','PUT',{project:repeated,values:loopVars,revision:loopVars.revision})).status,409);
  assert.equal((await json('/api/vision/runtime/continuous/'+continuousStart.body.id+'/stop','POST')).status,409);
  assert.equal((await json('/api/vision/runtime/continuous/'+endless.id+'/stop','POST')).status,202);
  for(let i=0;i<100;i++){continuous=(await json('/api/vision/runtime/continuous')).body;if(!continuous.busy)break;await delay(10);}
  assert.equal(continuous.state,'stopped');assert.equal(continuous.completedCycles,1);
  const summary=JSON.parse(fs.readFileSync(path.join(dataDir,'continuous-run.json'),'utf8'));assert.equal(summary.state,'stopped');assert.equal(summary.project,undefined);
  console.log('PASS: server-owned repeated camera acquisition, state/variables across clients, runtime locks during interval, stale stop rejection and durable stopped summary');
  if(process.env.TEST_3D==='true'){
    const content=fs.readFileSync(path.join(root,'public/vision/samples/cloud-box.json')).toString('base64');
    const imported=await json('/api/vision/run','POST',{operation:'cloud_import',name:'part.json',content,unit:'mm'});
    assert.equal(imported.status,200,JSON.stringify(imported.body));
    const cloudProject={version:1,name:'3D HTTP test',steps:[{id:'dimensions',operation:'cloud_measure',params:{}}]};
    const accepted=await json('/api/vision/runtime/jobs','POST',{project:cloudProject,cloud:imported.body.cloud});
    assert.equal(accepted.status,202,JSON.stringify(accepted.body));
    let cloudJob=accepted.body;for(let i=0;i<200&&cloudJob.state==='running';i++){await delay(50);cloudJob=(await json('/api/vision/runtime/jobs/'+accepted.body.id)).body;}
    assert.equal(cloudJob.state,'completed',JSON.stringify(cloudJob));assert.equal(cloudJob.results[0].output.result.sizeX,20);
    assert.equal((await json('/api/vision/project','PUT',cloudProject)).status,200);
    assert.equal((await json('/api/vision/project')).body.steps[0].operation,'cloud_measure');
    assert.equal((await json('/api/vision/run','POST',{operation:'cloud_import',name:'bad.exe',content})).status,400);
    console.log('PASS: 3D import HTTP, runtime point-cloud job, 3D project persistence, invalid file rejection');
    for(const rejected of [false,true]){
      const params={...globalDemo.steps[0].params,...(rejected?{maxRmsError:.01}:{})};
      const response=await json('/api/vision/run','POST',{operation:'cloud_register',cloud:globalCloud,params});
      assert.equal(response.status,200,JSON.stringify(response.body));assert.equal(response.body.result.found,!rejected);
      assert.equal(Object.hasOwn(response.body.result,'transformation'),!rejected);
      if(rejected)assert.deepEqual(response.body.cloud,globalCloud);else assert.equal(response.body.cloud.frame,'fixture');
    }
    const registrationProject={version:1,name:'Global registration HTTP',steps:[{id:'register',operation:'cloud_register',params:globalDemo.steps[0].params}]};
    assert.equal((await json('/api/vision/project','PUT',registrationProject)).status,200);
    assert.deepEqual((await json('/api/vision/project')).body.steps[0].params,globalDemo.steps[0].params);
    console.log('PASS: global registration HTTP quality pass/reject and reference/threshold project persistence');
  }
  const flows=[
    {id:'test-flow',type:'tab',label:'Integration'},
    {id:'http-in',type:'http in',z:'test-flow',url:'/test-vision',method:'post',upload:false,wires:[['barcode-node']]},
    {id:'barcode-node',type:'machine-barcode',z:'test-flow',name:'ZXing integration',params:'{}',wires:[['http-out'],[]]},
    {id:'http-out',type:'http response',z:'test-flow',statusCode:'200',headers:{'content-type':'application/json'},wires:[]},
    {id:'catch',type:'catch',z:'test-flow',scope:['barcode-node'],uncaught:false,wires:[['http-out']]}
  ];
  if(process.env.TEST_INDUSTRIAL==='true'){
    assert.equal((await json('/api/vision/industrial/simulator/start','POST')).status,200);
    const write=await json('/api/vision/industrial/run','POST',{operation:'modbus_write',params:{transport:'simulator',address:10,value:321}});assert.equal(write.status,200,JSON.stringify(write.body));
    const read=await json('/api/vision/industrial/run','POST',{operation:'modbus_read',params:{transport:'simulator',address:10}});assert.equal(read.body.result.value,321);assert.equal(read.body.result.simulated,true);
    const ioProject={version:1,name:'PLC HTTP pipeline',steps:[{id:'read',operation:'modbus_read',params:{transport:'simulator',address:10}},{id:'save',operation:'variables',params:{scope:'flow',name:'plcValue',value:{$ref:'results.read.value'}}}]};
    const start=await json('/api/vision/runtime/jobs','POST',{project:ioProject});assert.equal(start.status,202,JSON.stringify(start.body));let current=start.body;
    for(let i=0;i<100&&current.state==='running';i++){await delay(50);current=(await json('/api/vision/runtime/jobs/'+current.id)).body;}
    assert.equal(current.state,'completed',JSON.stringify(current));assert.equal(current.variables.flow.plcValue,321);
    assert.equal((await json('/api/vision/project','PUT',ioProject)).status,200);
    assert.equal((await json('/api/vision/project')).body.steps[0].operation,'modbus_read');
    assert.equal((await json('/api/vision/industrial/run','POST',{operation:'modbus_write',params:{transport:'simulator',area:'input',value:4}})).status,400);
    flows.push({id:'io-http',type:'http in',z:'test-flow',url:'/test-io',method:'post',upload:false,wires:[['io-node']]},{id:'io-node',type:'machine-modbus_read',z:'test-flow',params:JSON.stringify({transport:'simulator',address:10}),wires:[['io-out']]},{id:'io-out',type:'http response',z:'test-flow',statusCode:'200',headers:{'content-type':'application/json'},wires:[]});
    console.log('PASS: Modbus HTTP write/read, runtime result variable binding, persistence and invalid area rejection');
    const waitParams={transport:'simulator',address:10,comparison:'eq',expectedValue:321,stableMs:40,pollIntervalMs:20,waitTimeoutMs:1000};
    const waited=await json('/api/vision/industrial/run','POST',{operation:'modbus_wait',params:waitParams});assert.equal(waited.status,200,JSON.stringify(waited));assert.equal(waited.body.result.triggered,true);
    const waitProject={version:1,name:'PLC trigger HTTP',steps:[{id:'wait',operation:'modbus_wait',params:waitParams},{id:'save',operation:'variables',params:{name:'triggerValue',value:{$ref:'results.wait.value'}}}]};
    assert.equal((await json('/api/vision/project','PUT',waitProject)).status,200);assert.equal((await json('/api/vision/project')).body.steps[0].operation,'modbus_wait');
    const waitingJob=await json('/api/vision/runtime/jobs','POST',{project:waitProject});assert.equal(waitingJob.status,202);let waitState=waitingJob.body;
    for(let i=0;i<100&&waitState.state==='running';i++){await delay(50);waitState=(await json('/api/vision/runtime/jobs/'+waitState.id)).body;}
    assert.equal(waitState.state,'completed',JSON.stringify(waitState));assert.equal(waitState.variables.flow.triggerValue,321);
    flows.push({id:'wait-http',type:'http in',z:'test-flow',url:'/test-wait',method:'post',wires:[['wait-node']]},{id:'wait-node',type:'machine-modbus_wait',z:'test-flow',params:JSON.stringify(waitParams),wires:[['wait-out']]},{id:'wait-out',type:'http response',z:'test-flow',statusCode:'200',wires:[]});
  }
  if(process.env.TEST_S7==='true'){
    assert.equal((await json('/api/vision/industrial/s7/simulator/start','POST')).status,200);
    const params={connection:'simulator',area:'db',dbNumber:1,byteOffset:10,dataType:'uint16'};
    const write=await json('/api/vision/industrial/run','POST',{operation:'s7_write',params:{...params,value:321}});assert.equal(write.status,200,JSON.stringify(write));
    const read=await json('/api/vision/industrial/run','POST',{operation:'s7_read',params});assert.equal(read.body.result.value,321);assert.equal(read.body.result.simulated,true);
    const s7Project={version:1,id:'s7-http',name:'S7 HTTP',steps:[{id:'s7',operation:'s7_read',params},{id:'value',operation:'variables',params:{scope:'flow',name:'s7Value',value:{$ref:'results.s7.value'}}}]};
    const start=await json('/api/vision/runtime/jobs','POST',{project:s7Project});assert.equal(start.status,202,JSON.stringify(start));let current=start.body;
    for(let i=0;i<150&&current.state==='running';i++){await delay(50);current=(await json('/api/vision/runtime/jobs/'+current.id)).body;}
    assert.equal(current.state,'completed',JSON.stringify(current));assert.equal(current.variables.flow.s7Value,321);
    assert.equal((await json('/api/vision/project','PUT',s7Project)).status,200);assert.equal((await json('/api/vision/project')).body.steps[0].operation,'s7_read');
    assert.equal((await json('/api/vision/industrial/run','POST',{operation:'s7_write',params:{...params,area:'pe',value:1}})).status,400);
    flows.push({id:'s7-http',type:'http in',z:'test-flow',url:'/test-s7',method:'post',upload:false,wires:[['s7-write']]},{id:'s7-write',type:'machine-s7_write',z:'test-flow',params:JSON.stringify({...params,value:456}),wires:[['s7-read']]},{id:'s7-read',type:'machine-s7_read',z:'test-flow',params:JSON.stringify(params),wires:[['s7-out']]},{id:'s7-out',type:'http response',z:'test-flow',statusCode:'200',headers:{'content-type':'application/json'},wires:[]});
    console.log('PASS: S7 HTTP read/write, typed variables, persistence and read-only input rejection');
  }
  if(process.env.TEST_OPCUA==='true'){
    assert.equal((await json('/api/vision/industrial/opcua/simulator/start','POST')).status,200);
    const params={connection:'simulator',nodeId:'ns=2;s=SIEANS.Count'};
    const write=await json('/api/vision/industrial/run','POST',{operation:'opcua_write',params:{...params,dataType:'UInt32',value:123}});assert.equal(write.status,200,JSON.stringify(write));
    const browse=await json('/api/vision/industrial/run','POST',{operation:'opcua_browse',params:{...params,nodeId:'ns=2;s=SIEANS'}});assert.equal(browse.body.result.count,6);
    const read=await json('/api/vision/industrial/run','POST',{operation:'opcua_read',params});assert.equal(read.body.result.value,123);assert.equal(read.body.result.quality,'good');
    const uaProject={version:1,id:'opcua-http',name:'OPC UA HTTP',steps:[{id:'ua',operation:'opcua_read',params},{id:'value',operation:'variables',params:{scope:'flow',name:'uaValue',value:{$ref:'results.ua.value'}}}]};
    const start=await json('/api/vision/runtime/jobs','POST',{project:uaProject});assert.equal(start.status,202,JSON.stringify(start));let current=start.body;
    for(let i=0;i<150&&current.state==='running';i++){await delay(50);current=(await json('/api/vision/runtime/jobs/'+current.id)).body;}
    assert.equal(current.state,'completed',JSON.stringify(current));assert.equal(current.variables.flow.uaValue,123);
    assert.equal((await json('/api/vision/project','PUT',uaProject)).status,200);assert.equal((await json('/api/vision/project')).body.steps[0].operation,'opcua_read');
    flows.push({id:'ua-http',type:'http in',z:'test-flow',url:'/test-ua',method:'post',upload:false,wires:[['ua-write']]},{id:'ua-write',type:'machine-opcua_write',z:'test-flow',params:JSON.stringify({...params,dataType:'UInt32',value:456}),wires:[['ua-read']]},{id:'ua-read',type:'machine-opcua_read',z:'test-flow',params:JSON.stringify(params),wires:[['ua-out']]},{id:'ua-out',type:'http response',z:'test-flow',statusCode:'200',headers:{'content-type':'application/json'},wires:[]});
    console.log('PASS: OPC UA HTTP browser/read/write, quality, variable binding and project persistence');
  }
  if(process.env.TEST_3D==='true')flows.push(
    {id:'cloud-http',type:'http in',z:'test-flow',url:'/test-cloud',method:'post',upload:false,wires:[['cloud-node']]},
    {id:'cloud-node',type:'machine-cloud_measure',z:'test-flow',params:'{}',wires:[['cloud-out'],[]]},
    {id:'cloud-out',type:'http response',z:'test-flow',statusCode:'200',headers:{'content-type':'application/json'},wires:[]},
    {id:'global-http',type:'http in',z:'test-flow',url:'/test-global',method:'post',upload:false,wires:[['global-node']]},
    {id:'global-node',type:'machine-cloud_register',z:'test-flow',params:JSON.stringify(globalDemo.steps[0].params),wires:[['cloud-out'],[]]},
    {id:'global-reject-http',type:'http in',z:'test-flow',url:'/test-global-reject',method:'post',upload:false,wires:[['global-reject-node']]},
    {id:'global-reject-node',type:'machine-cloud_register',z:'test-flow',params:JSON.stringify({...globalDemo.steps[0].params,maxRmsError:.01}),wires:[['cloud-out'],[]]}
  );
  if(process.env.TEST_CAMERAS==='true'){
    const params={driver:'simulator',deviceId:'synthetic-parts'};
    const devices=await json('/api/vision/cameras/run','POST',{operation:'camera_list',params});assert.equal(devices.status,200);assert.equal(devices.body.result.items.length,1);
    const captured=await json('/api/vision/cameras/run','POST',{operation:'camera_capture',params});assert.equal(captured.status,200);assert.equal(captured.body.result.width,640);
    assert.equal((await json('/api/vision/cameras/run','POST',{operation:'camera_capture',params:{...params,width:99999}})).status,400);
    const cameraProject={version:1,name:'Camera HTTP',steps:[{id:'camera',operation:'camera_capture',params},{id:'detect',operation:'geometry',params:{feature:'contours',minArea:50}}]};
    const accepted=await json('/api/vision/runtime/jobs','POST',{project:cameraProject});assert.equal(accepted.status,202);let job=accepted.body;
    for(let i=0;i<150&&job.state==='running';i++){await delay(50);job=(await json('/api/vision/runtime/jobs/'+job.id)).body;}
    assert.equal(job.state,'completed',JSON.stringify(job));assert.equal(job.results[1].output.result.count,3);
    assert.equal((await json('/api/vision/project','PUT',cameraProject)).status,200);assert.equal((await json('/api/vision/project')).body.steps[0].operation,'camera_capture');
    flows.push({id:'camera-http',type:'http in',z:'test-flow',url:'/test-camera',method:'post',upload:false,wires:[['camera-node']]},{id:'camera-node',type:'machine-camera_capture',z:'test-flow',params:JSON.stringify(params),wires:[['camera-detect']]},{id:'camera-detect',type:'machine-geometry',z:'test-flow',params:JSON.stringify({feature:'contours',minArea:50}),wires:[['camera-out'],[]]},{id:'camera-out',type:'http response',z:'test-flow',statusCode:'200',headers:{'content-type':'application/json'},wires:[]});
    console.log('PASS: camera HTTP enumerate/capture, runtime image acquisition and project persistence');
  }
  if(process.env.TEST_DEPTH==='true'){
    const params={driver:'rgbd_simulator',deviceId:'synthetic-rgbd',pointStride:1,minDepth:.9,maxDepth:1.1};
    const captured=await json('/api/vision/cameras/run','POST',{operation:'camera_capture',params});
    assert.equal(captured.status,200,JSON.stringify(captured.body));assert.equal(captured.body.depth.format,'png16');assert.equal(captured.body.depth.scaleMeters,.001);assert.equal(captured.body.cloud.unit,'mm');assert.equal(captured.body.cloud.points.length,3071);
    const crop={method:'crop',minimum:[-1000,-1000,970],maximum:[1000,1000,980]};
    const depthProject={version:1,id:'depth-http',name:'RGB-D HTTP',steps:[{id:'camera',operation:'camera_capture',params},{id:'crop',operation:'cloud_filter',params:crop},{id:'measure',operation:'cloud_measure',params:{}},{id:'save',operation:'variables',params:{scope:'flow',name:'topWidth',value:{$ref:'results.measure.sizeX'}}}]};
    const start=await json('/api/vision/runtime/jobs','POST',{project:depthProject});assert.equal(start.status,202,JSON.stringify(start));let current=start.body;
    for(let i=0;i<200&&current.state==='running';i++){await delay(50);current=(await json('/api/vision/runtime/jobs/'+current.id)).body;}
    assert.equal(current.state,'completed',current.error);assert.equal(current.results[1].output.cloud.points.length,200);assert(Math.abs(current.variables.flow.topWidth-185.25)<1e-6);assert.equal(current.results[0].output.depth.width,64);
    assert.equal((await json('/api/vision/project','PUT',depthProject)).status,200);assert.equal((await json('/api/vision/project')).body.steps[0].params.driver,'rgbd_simulator');
    flows.push({id:'depth-http',type:'http in',z:'test-flow',url:'/test-depth',method:'post',upload:false,wires:[['depth-camera']]},
      {id:'depth-camera',type:'machine-camera_capture',z:'test-flow',params:JSON.stringify(params),wires:[['depth-crop']]},
      {id:'depth-crop',type:'machine-cloud_filter',z:'test-flow',params:JSON.stringify(crop),wires:[['depth-measure'],[]]},
      {id:'depth-measure',type:'machine-cloud_measure',z:'test-flow',params:'{}',wires:[['depth-inspect'],[]]},
      {id:'depth-inspect',type:'function',z:'test-flow',func:'msg.payload={...msg.payload,depthFormat:msg.depth.format,depthWidth:msg.depth.width,depthScale:msg.depth.scaleMeters,unit:msg.cloud.unit};return msg;',outputs:1,wires:[['depth-out']]},
      {id:'depth-out',type:'http response',z:'test-flow',statusCode:'200',headers:{'content-type':'application/json'},wires:[]});
    console.log('PASS: RGB-D HTTP capture, raw depth, calibrated 3D processing, variable binding and project persistence');
  }
  const bridgeMetadata=await json('/editor/machine/operators');assert.equal(bridgeMetadata.status,200);assert(bridgeMetadata.body.plugins.some(p=>p.id==='sieans-planar'&&p.enabled));
  const bridgeIds=['bridge-calibrate','bridge-measure','bridge-brightness','bridge-normals','bridge-caliper','bridge-sphere-fit','bridge-sphere-inspect','bridge-cylinder-fit','bridge-cylinder-inspect'];
  const bridgeNode=(id,pluginId,operatorId,args,wires,bindings={})=>({id,z:'test-flow',type:'machine-operator',pluginId,pluginVersion:'1.0.0',operatorId,arguments:JSON.stringify(args),parameterBindings:JSON.stringify(bindings),validConfig:true,wires:[wires,[]]});
  flows.push(
    {id:'bridge-sphere-http',type:'http in',z:'test-flow',url:'/test-operator-sphere',method:'post',upload:false,wires:[['bridge-sphere-fit']]},
    bridgeNode('bridge-sphere-fit','sieans-sphere','fit',{detailMode:'outside'},['bridge-sphere-inspect']),
    bridgeNode('bridge-sphere-inspect','sieans-sphere','inspect',{detailMode:'outside'},['bridge-out'],{sphere:'payload.sphere'}),
    {id:'bridge-cylinder-http',type:'http in',z:'test-flow',url:'/test-operator-cylinder',method:'post',upload:false,wires:[['bridge-cylinder-fit']]},
    bridgeNode('bridge-cylinder-fit','sieans-cylinder','fit',{detailMode:'outside'},['bridge-cylinder-inspect']),
    bridgeNode('bridge-cylinder-inspect','sieans-cylinder','inspect',{detailMode:'outside'},['bridge-out'],{cylinder:'payload.cylinder'}),
    {id:'bridge-caliper-http',type:'http in',z:'test-flow',url:'/test-operator-caliper',method:'post',upload:false,wires:[['bridge-caliper']]},
    bridgeNode('bridge-caliper','sieans-caliper','edge-width',{scanAngle:28,unitsPerPixel:.1,unit:'mm',minimumWidth:8,maximumWidth:8.1},['bridge-caliper-inspect']),
    {id:'bridge-caliper-inspect',type:'function',z:'test-flow',func:'msg.payload={...msg.payload,image:msg.image,annotatedImage:msg.vision.annotatedImage};return msg;',outputs:1,wires:[['bridge-out']]},
    {id:'bridge-http',type:'http in',z:'test-flow',url:'/test-operator-plane',method:'post',upload:false,wires:[['bridge-calibrate']]},
    bridgeNode('bridge-calibrate','sieans-planar','calibrate',{},['bridge-measure']),
    bridgeNode('bridge-measure','sieans-planar','measure',{points:[{x:100,y:100},{x:500,y:100}]},['bridge-out'],{calibration:'payload.calibration'}),
    {id:'bridge-image-http',type:'http in',z:'test-flow',url:'/test-operator-image',method:'post',upload:false,wires:[['bridge-brightness']]},
    bridgeNode('bridge-brightness','sieans-inspection','brightness',{minimumMean:0,maximumMean:255},['bridge-out']),
    {id:'bridge-cloud-http',type:'http in',z:'test-flow',url:'/test-operator-cloud',method:'post',upload:false,wires:[['bridge-normals']]},
    bridgeNode('bridge-normals','sieans-normals','inspect',{},['bridge-out']),
    {id:'bridge-catch',type:'catch',z:'test-flow',scope:bridgeIds,uncaught:false,wires:[['bridge-error']]},
    {id:'bridge-error',type:'function',z:'test-flow',func:'msg.statusCode=422;msg.payload={error:msg.error.message};return msg;',outputs:1,wires:[['bridge-out']]},
    {id:'bridge-out',type:'http response',z:'test-flow',statusCode:'',headers:{'content-type':'application/json'},wires:[]}
  );
  // Node-RED distinguishes executable nodes from config nodes by x/y presence.
  flows.filter(node=>node.z).forEach((node,index)=>{node.x=150+(index%4)*200;node.y=80+Math.floor(index/4)*100;});
  const deployLogOffset=logs.length;
  const deploy=await fetch(url+'/editor/flows',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(flows)});
  assert.equal(deploy.status,204,logs);
  // The deploy HTTP acknowledgement precedes asynchronous node startup.
  for(let i=0;i<100&&!logs.slice(deployLogOffset).includes('Started flows');i++)await delay(50);
  assert(logs.slice(deployLogOffset).includes('Started flows'),'Deployed nodes did not start: '+logs.slice(deployLogOffset));
  assert(!logs.slice(deployLogOffset).includes('Circular config node dependency'),'Invalid test deployment: '+logs.slice(deployLogOffset));
  const nodeResult=await json('/test-vision','POST',{image});
  assert.equal(nodeResult.status,200);
  assert.equal(nodeResult.body.count,2,JSON.stringify(nodeResult.body));
  const bridgePlane=await json('/test-operator-plane','POST',{});assert.equal(bridgePlane.status,200,JSON.stringify(bridgePlane));assert(Math.abs(bridgePlane.body.length-100)<1e-6);
  const sphereCloud=JSON.parse(fs.readFileSync(path.join(root,'public/vision/samples/sphere-defects.json')));
  const bridgeSphere=await json('/test-operator-sphere','POST',{cloud:sphereCloud});assert.equal(bridgeSphere.status,200,JSON.stringify(bridgeSphere));assert.equal(bridgeSphere.body.passed,false);assert.equal(bridgeSphere.body.outsideCount,2);assert(Math.abs(bridgeSphere.body.maximumDistance-.5)<1e-8);assert(Math.abs(bridgeSphere.body.minimumDistance+.3)<1e-8);
  const cylinderCloud=JSON.parse(fs.readFileSync(path.join(root,'public/vision/samples/cylinder-defects.json')));
  const bridgeCylinder=await json('/test-operator-cylinder','POST',{cloud:cylinderCloud});assert.equal(bridgeCylinder.status,200,JSON.stringify(bridgeCylinder));assert.equal(bridgeCylinder.body.passed,false);assert.equal(bridgeCylinder.body.outsideCount,2);assert(Math.abs(bridgeCylinder.body.maximumDistance-.5)<1e-8);assert(Math.abs(bridgeCylinder.body.minimumDistance+.3)<1e-8);
  const caliperInput='data:image/png;base64,'+fs.readFileSync(path.join(root,'public/vision/samples/caliper-width-pass.png')).toString('base64');
  const bridgeCaliper=await json('/test-operator-caliper','POST',{image:caliperInput});assert.equal(bridgeCaliper.status,200,JSON.stringify(bridgeCaliper));assert.equal(bridgeCaliper.body.passed,true);assert(Math.abs(bridgeCaliper.body.meanWidth-8.04)<.015);assert.equal(bridgeCaliper.body.image,caliperInput);assert.notEqual(bridgeCaliper.body.annotatedImage,caliperInput);
  const bridgeInput='data:image/png;base64,'+fs.readFileSync(path.join(root,'public/vision/samples/parts.png')).toString('base64');
  const bridgeImage=await json('/test-operator-image','POST',{image:bridgeInput});assert.equal(bridgeImage.status,200,JSON.stringify(bridgeImage));assert.equal(bridgeImage.body.passed,true);assert.equal(bridgeImage.body.pixelCount,294000);
  const bridgeCloud=await json('/test-operator-cloud','POST',{cloud:JSON.parse(fs.readFileSync(path.join(root,'public/vision/samples/cloud-slope.json')))});assert.equal(bridgeCloud.status,200,JSON.stringify(bridgeCloud));assert.equal(bridgeCloud.body.validCount,121);assert(Math.abs(bridgeCloud.body.meanSlopeDegrees-30)<1e-8);
  assert.equal((await json('/test-operator-cloud','POST',{cloud:{unit:'bad',points:[[0,0,0]]}})).status,422);
  await json('/api/vision/plugins/sieans-planar','PUT',{enabled:false});const disabledBridge=await json('/test-operator-plane','POST',{});assert.equal(disabledBridge.status,422);assert.match(disabledBridge.body.error,/停用/);await json('/api/vision/plugins/sieans-planar','PUT',{enabled:true});
  console.log('PASS: Node-RED generic plugin discovery, planar binding chain, real 2D/3D operators and Catch errors/disable state');
  if(process.env.TEST_INDUSTRIAL==='true'){
    const result=await json('/test-io','POST',{});assert.equal(result.body.value,321,JSON.stringify(result));
    const triggered=await json('/test-wait','POST',{});assert.equal(triggered.body.triggered,true,JSON.stringify(triggered));assert.equal(triggered.body.value,321);
    console.log('PASS: Modbus wait HTTP, project persistence, runtime variable binding and Node-RED trigger node');
    await json('/api/vision/industrial/simulator/stop','POST');assert.equal((await json('/api/vision/industrial/simulator')).body.running,false);
    console.log('PASS: real Node-RED Modbus protocol plugin and simulator shutdown');
  }
  if(process.env.TEST_OPCUA==='true'){
    const result=await json('/test-ua','POST',{});assert.equal(result.status,200);assert.equal(result.body.value,456,JSON.stringify(result));
    await json('/api/vision/industrial/opcua/simulator/stop','POST');assert.equal((await json('/api/vision/industrial/opcua/simulator')).body.running,false);
    console.log('PASS: real Node-RED OPC UA write/read nodes and simulator shutdown');
  }
  if(process.env.TEST_3D==='true'){
    const cloud=JSON.parse(fs.readFileSync(path.join(root,'public/vision/samples/cloud-box.json')));
    const result=await json('/test-cloud','POST',{cloud});assert.equal(result.status,200);assert.equal(result.body.sizeX,20);
    console.log('PASS: real Node-RED 3D measurement plugin flow');
    const registration=await json('/test-global','POST',{cloud:globalCloud});assert.equal(registration.status,200);assert.equal(registration.body.found,true);assert.equal(registration.body.transformation.length,4);
    const rejected=await json('/test-global-reject','POST',{cloud:globalCloud});assert.equal(rejected.status,200);assert.equal(rejected.body.found,false);assert.equal(Object.hasOwn(rejected.body,'transformation'),false);
    console.log('PASS: real Node-RED global registration pass/reject flows');
  }
  if(process.env.TEST_CAMERAS==='true'){const out=await json('/test-camera','POST',{});assert.equal(out.status,200);assert.equal(out.body.count,3,JSON.stringify(out));console.log('PASS: Node-RED camera to real geometry detection');}
  if(process.env.TEST_DEPTH==='true'){
    const out=await json('/test-depth','POST',{});assert.equal(out.status,200);assert(Math.abs(out.body.sizeX-185.25)<1e-6,JSON.stringify(out.body));assert(Math.abs(out.body.sizeY-87.75)<1e-6);assert.equal(out.body.depthFormat,'png16');assert.equal(out.body.depthWidth,64);assert.equal(out.body.depthScale,.001);assert.equal(out.body.unit,'mm');
    console.log('PASS: real Node-RED RGB-D camera to crop/measurement; raw depth retained across operators');
  }
  if(process.env.TEST_S7==='true'){
    const out=await json('/test-s7','POST',{});assert.equal(out.status,200,JSON.stringify(out));assert.equal(out.body.value,456);
    await json('/api/vision/industrial/s7/simulator/stop','POST');assert.equal((await json('/api/vision/industrial/s7/simulator')).body.running,false);
    console.log('PASS: real Node-RED S7 write/read chain and simulator shutdown');
  }
  console.log('PASS: HTTP algorithm API, invalid input, project persistence, validation, real Node-RED ZXing flow');
}
main().catch(error=>{console.error(error,logs);process.exitCode=1;}).finally(async()=>{
  if(server&&server.exitCode===null){const exited=once(server,'exit');server.send({type:'sieans-shutdown'});await boundedExit(exited,15000);if(server.exitCode===null){server.kill();await boundedExit(exited,5000);}assert.notEqual(server.exitCode,null,'owned integration server must stop');}
  console.log('Test data: '+dataDir);
});
