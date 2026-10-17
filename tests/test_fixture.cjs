'use strict';
const {test,after}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),os=require('node:os');
const {Runtime}=require('../lib/runtime.cjs'),{OperatorPlugins}=require('../lib/operator-plugins.cjs'),vision=require('../lib/vision-client.cjs'),{createOperatorBridge}=require('../lib/operator-bridge.cjs');
const graph=require('../public/vision/flow-graph.js'),hmi=require('../public/vision/hmi-layout.js'),samples=path.join(__dirname,'../public/vision/samples'),demos=JSON.parse(fs.readFileSync(path.join(samples,'demos-fixture.json')));
after(()=>vision.stop());
const imageOf=name=>'data:image/png;base64,'+fs.readFileSync(path.join(samples,name)).toString('base64');
function project(demo){
 const steps=structuredClone(demo.steps).map((s,i)=>({...s,id:'f'+i,reference:s.reference?imageOf(s.reference):undefined}));
 for(const b of demo.bindings||[])steps[b.step].params[b.param]={$ref:'results.f'+b.source+'.'+b.field};
 const layout=structuredClone(demo.hmi);for(const b of demo.hmiBindings)layout.components[b.component].binding.nodeId='f'+b.step;
 const p={version:1,id:demo.id,name:demo.name,steps,hmi:layout};if(demo.connections){p.version=2;p.edges=demo.connections.map(([from,to,when],i)=>({id:'link'+i,from:from<0?'source':steps[from].id,to:steps[to].id,...(when?{when}:{})}));}return graph.normalize(p);
}
function make(){const dir=fs.mkdtempSync(path.join(os.tmpdir(),'sieans-fixture-'));return new Runtime(dir,vision,new OperatorPlugins(dir));}
async function execute(runtime,p,image){const job=runtime.start({project:p,image});await runtime.jobs.get(job.id).promise;return runtime.poll(job.id);}
test('five fixture demos execute multi-match, rectified inspection and unique-target guarded branches',async()=>{
 for(const demo of demos){const runtime=make(),p=project(demo),image=imageOf(demo.image),job=await execute(runtime,p,image);assert.equal(job.state,'completed',job.error);
  const first=job.results[0].output.result,last=job.results.at(-1).output.result;
  if(demo.id==='fixture-multiple'){assert.equal(first.count,3);assert.equal(first.unique,false);assert.equal(first.items.length,3);}
  if(demo.id==='fixture-rotated'){assert.equal(first.unique,true);assert.equal(last.count,2);assert.equal(last.passed,true);assert.equal(hmi.read(p.hmi.components[1].binding,job).length,2);}
  if(demo.id==='fixture-inspect'){
   assert.equal(job.results[2].output.result.width,56);assert.equal(job.results[2].output.result.height,40);assert.equal(job.variables.flow.holeCount,2);assert.equal(last.passed,true);
   assert.equal(job.results[2].output.image,job.results[2].output.annotatedImage);assert.notEqual(job.results[2].output.image,image);assert.equal(job.results[3].output.annotatedImage,job.results[2].output.image);
  }
  if(demo.id==='fixture-blank'){assert.equal(first.found,false);assert.equal(first.pose,undefined);assert.equal(first.center,undefined);}
  if(demo.id==='fixture-guard'){
   assert.equal(job.results.filter(r=>r.skipped).length,3);
   const rotated=await execute(runtime,p,imageOf('fixture-rotated.png'));assert.equal(rotated.state,'completed',rotated.error);assert.equal(rotated.variables.flow.holeCount,2);assert(rotated.results.every(r=>!r.skipped));
   const multiple=await execute(runtime,p,imageOf('fixture-multiple.png'));assert.equal(multiple.state,'completed',multiple.error);assert.equal(multiple.results.filter(r=>r.skipped).length,3);assert.equal(hmi.read(p.hmi.components[1].binding,multiple),undefined);
  }
 }
});
test('pose stored in all scopes, stale frame refused and earlier staged variables rolled back',async()=>{
 const runtime=make(),p=project(demos[1]);p.steps[2].params.outputBindings=[{field:'passed',scope:'global',name:'fixtureOK'},{field:'count',scope:'module',name:'pointCount'}];
 const first=await execute(runtime,p,imageOf(demos[1].image));assert.equal(first.state,'completed',first.error);assert.equal(first.variables.global.fixtureOK,true);assert.equal(first.variables.modules.f2.pointCount,2);const pose=structuredClone(first.variables.flow.partPose);
 const stale=graph.normalize({version:1,id:p.id,name:'过期位姿拒绝',steps:[{id:'stage',operation:'variables',params:{scope:'flow',name:'uncommitted',value:3}},{...p.steps[2],id:'stale'}]});
 const failed=await execute(runtime,stale,imageOf('fixture-blank.png'));assert.equal(failed.state,'failed');assert.match(failed.error,/同一帧/);assert.equal(runtime.snapshot(p).flow.uncommitted,undefined);assert.deepEqual(runtime.snapshot(p).flow.partPose,pose);
 const noPose=project(demos[1]);noPose.id=p.id;const absent=await execute(runtime,noPose,imageOf('fixture-blank.png'));assert.equal(absent.state,'failed');assert.match(absent.error,/字段不存在|无法解析|不存在/);assert.deepEqual(runtime.snapshot(p).flow.partPose,pose);
});
test('Node-RED operator bridge consumes built-in location pose and emits corrected frame for detection',async()=>{
 const runtime=make(),bridge=createOperatorBridge(runtime.plugins),demo=demos[2],p=project(demo),image=imageOf(demo.image);
 const location=await vision.run({operation:'locate',image,reference:p.steps[0].reference,params:p.steps[0].params});assert.equal(location.result.unique,true);
 const corrected=await bridge.run({...p.steps[2].params,image,arguments:{pose:location.result.pose,cropX:12,cropY:12,cropWidth:56,cropHeight:40}});
 const holes=await bridge.run({...p.steps[3].params,image:corrected.image});assert.equal(holes.result.count,2);assert.equal(corrected.result.rectified,true);
});
test('Node-RED template node routes target table, source image and no-match status',async()=>{
 const registry=new Map();const RED={settings:{machineVision:vision},nodes:{registerType:(name,ctor)=>registry.set(name,ctor),createNode(node){node.handlers={};node.states=[];node.on=(event,handler)=>node.handlers[event]=handler;node.status=state=>node.states.push(state);}}};require('../plugins/node-red-contrib-machine/nodes/vision.js')(RED);
 const node=new (registry.get('machine-locate'))({params:JSON.stringify(demos[0].steps[0].params),reference:imageOf('fixture-template.png')});
 const input=async image=>{let sent,error;await node.handlers.input({image},message=>sent=message,e=>error=e);if(error)throw error;return sent;};
 const image=imageOf('fixture-multiple.png'),messages=await input(image);assert.equal(messages[0].payload.count,3);assert.equal(messages[0].image,image);assert.equal(messages[1].payload,messages[0].vision.annotatedImage);
 const absent=await input(imageOf('fixture-blank.png'));assert.equal(absent[0].payload.pose,undefined);assert.equal(node.states.at(-1).fill,'yellow');assert.equal(node.states.at(-1).text,'未检出目标');
});
