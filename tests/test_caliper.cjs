'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),vm=require('node:vm');
const {Runtime}=require('../lib/runtime.cjs'),{OperatorPlugins}=require('../lib/operator-plugins.cjs');
const {createOperatorBridge}=require('../lib/operator-bridge.cjs');
const graph=require('../public/vision/flow-graph.js');
const samples=path.join(__dirname,'../public/vision/samples');
const demos=JSON.parse(fs.readFileSync(path.join(samples,'demos-caliper.json')));
const imageOf=demo=>'data:image/png;base64,'+fs.readFileSync(path.join(samples,demo.image)).toString('base64');
async function execute(runtime,project,image){const job=runtime.start({project,image});await runtime.jobs.get(job.id).promise;return runtime.poll(job.id);}

test('caliper demos execute real Python, preserve source frames and bind variables',async()=>{
 for(const demo of demos){
  const dir=fs.mkdtempSync(path.join(os.tmpdir(),'sieans-caliper-')),runtime=new Runtime(dir,{},new OperatorPlugins(dir));
  const p=graph.normalize({version:1,id:demo.id,name:demo.name,variables:{minimumRatio:.8},steps:[
   {...demo.steps[0],id:'caliper',params:{...demo.steps[0].params,arguments:{...demo.steps[0].params.arguments,minimumValidRatio:{$ref:'flow.minimumRatio'}},outputBindings:[...demo.steps[0].params.outputBindings,...['global','module'].map(scope=>({scope,name:'caliperOK',field:'passed'}))]}},
   {id:'downstream',operation:'plugin',params:{pluginId:'sieans-inspection',pluginVersion:'1.0.0',operatorId:'brightness',arguments:{}}}
  ]});
  const image=imageOf(demo),job=await execute(runtime,p,image);assert.equal(job.state,'completed',job.error);
  const out=job.results[0].output,passed=['caliper-line','caliper-width-pass'].includes(demo.id);
  assert.equal(out.result.passed,passed);assert.equal(job.variables.global.caliperOK,passed);assert.equal(job.variables.modules.caliper.caliperOK,passed);
  assert.equal(out.image,image);assert.notEqual(out.annotatedImage,image);assert.equal(job.results[1].output.annotatedImage,image);
  if(demo.id==='caliper-line')assert.equal(out.result.inlierCount,13);
  if(demo.id.startsWith('caliper-width'))assert(Math.abs(job.variables.flow.measuredWidth-(passed?8.04:8.6))<.015);
  if(demo.id==='caliper-no-edge'){assert.equal(out.result.found,false);assert.equal(out.result.line,undefined);}
 }
});
test('Node-RED bridge separates caliper display from original data image',async()=>{
 const plugins=new OperatorPlugins(fs.mkdtempSync(path.join(os.tmpdir(),'sieans-caliper-'))),bridge=createOperatorBridge(plugins),demo=demos[1],image=imageOf(demo);
 const result=await bridge.run({...demo.steps[0].params,image});assert.equal(result.image,image);assert.notEqual(result.annotatedImage,image);assert.equal(result.result.passed,true);
 const next=await bridge.run({pluginId:'sieans-inspection',pluginVersion:'1.0.0',operatorId:'brightness',image:result.image});assert.equal(next.image,image);
});
test('input preview selects processing image, including an explicit cleared channel',()=>{
 const context=vm.createContext({project:{steps:[{id:'caliper',operation:'plugin'}]}});
 vm.runInContext(fs.readFileSync(path.join(__dirname,'../public/vision/input-preview.js'),'utf8'),context);
 context.item={id:'caliper',output:{image:'original',annotatedImage:'overlay'}};vm.runInContext('rememberFrame(item)',context);
 assert.equal(vm.runInContext('framePreviews.get("caliper")',context),'original');
 context.item.output.image='';vm.runInContext('rememberFrame(item)',context);assert.equal(vm.runInContext('framePreviews.get("caliper")',context),'');
});
test('script image and display channels remain distinct; malformed display rolls variables back',async()=>{
 const directory=fs.mkdtempSync(path.join(os.tmpdir(),'sieans-caliper-')),runtime=new Runtime(directory,{});
 const project=graph.normalize({version:1,id:'script-display',name:'显示通道测试',steps:[
  {id:'script',operation:'script',params:{code:'def run(ctx):\n    return dict(result={},image="processed",annotatedImage="overlay")'}},
  {id:'next',operation:'script',params:{code:'def run(ctx):\n    return dict(result=dict(input=ctx["image"]))'}}
 ]});
 let job=runtime.start({project,allowScripts:true,image:'original'});await runtime.jobs.get(job.id).promise;job=runtime.poll(job.id);
 assert.equal(job.state,'completed',job.error);assert.equal(job.results[0].output.annotatedImage,'overlay');assert.equal(job.results[0].output.image,'processed');assert.equal(job.results[1].output.result.input,'processed');
 project.steps[0].params.code='def run(ctx):\n    return dict(result={},annotatedImage=123,variables=dict(flow=dict(shouldRollback=1)))';
 job=runtime.start({project,allowScripts:true});await runtime.jobs.get(job.id).promise;job=runtime.poll(job.id);
 assert.equal(job.state,'failed');assert.match(job.error,/显示图像/);assert.equal(runtime.snapshot(project).flow.shouldRollback,undefined);
});
