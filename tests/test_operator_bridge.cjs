const {test}=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path');
const {OperatorPlugins}=require('../lib/operator-plugins.cjs');
const {createOperatorBridge}=require('../lib/operator-bridge.cjs');
const temp=()=>fs.mkdtempSync(path.join(os.tmpdir(),'sieans-bridge-'));
function fixture(code){const root=temp(),folder=path.join(root,'operator-plugins','bridge-test');fs.mkdirSync(folder,{recursive:true});fs.writeFileSync(path.join(folder,'operator-plugin.json'),JSON.stringify({apiVersion:1,id:'bridge-test',name:'测试',version:'1.0.0',license:'MIT',description:'测试用插件',operators:[{id:'test',name:'测试',description:'测试',input:'none',entry:'main.py',timeoutMs:5000,parameters:[],outputs:[{key:'value',label:'值',type:'number',required:true}]}]}));fs.writeFileSync(path.join(folder,'main.py'),code);return new OperatorPlugins(root);}
const config={pluginId:'bridge-test',pluginVersion:'1.0.0',operatorId:'test'};
function nodeHarness(service){let Node,permission,route;const RED={settings:{machineOperators:service},auth:{needsPermission(p){permission=p;return function(){};}},httpAdmin:{get(...args){route=args;}},nodes:{createNode(node){node.handlers={};node.on=(event,fn)=>node.handlers[event]=fn;node.status=()=>{};},registerType(name,constructor){assert.equal(name,'machine-operator');Node=constructor;}}};require('../plugins/node-red-contrib-machine/nodes/operator.js')(RED);return {create:options=>new Node({...config,arguments:'{}',parameterBindings:'{}',...options}),permission,route};}
async function input(node,msg){const sent=[];let error;await node.handlers.input(msg,data=>sent.push(data),e=>error=e);return {sent,error};}

test('bridge executes actual image and cloud plugins and validates version/input contracts',async()=>{
 const plugins=new OperatorPlugins(temp()),bridge=createOperatorBridge(plugins),base={pluginId:'sieans-inspection',pluginVersion:'1.0.0'};
 const image='data:image/png;base64,'+fs.readFileSync(path.join(__dirname,'../public/vision/samples/parts.png')).toString('base64');
 const bright=await bridge.run({...base,operatorId:'brightness',image});assert.equal(bright.result.pixelCount,294000);assert.equal(bright.annotatedImage,image);
 const cloud={unit:'mm',points:[[0,0,0],[2,4,6]]};const center=await bridge.run({...base,operatorId:'centroid',cloud,arguments:{targetX:1,targetY:2,targetZ:3,tolerance:0}});assert.equal(center.result.passed,true);assert.deepEqual(center.cloud,cloud);
 await assert.rejects(bridge.run({...base,operatorId:'centroid',cloud:{unit:'bad',points:[[0,0,0]]}}),/单位/);
 await assert.rejects(bridge.run({...base,operatorId:'brightness'}),/输入图像/);
 await assert.rejects(bridge.run({...base,pluginVersion:'2.0.0',operatorId:'brightness',image}),/版本/);
 plugins.setEnabled(base.pluginId,false);await assert.rejects(bridge.run({...base,operatorId:'brightness',image}),/停用/);
});
test('bridge preserves scoped message variables, applies replacements and clears stale channels',async()=>{
 const plugins=fixture('def run(ctx):\n    ctx["vars"]["flow"]["count"]+=1\n    return dict(result=dict(value=ctx["vars"]["flow"]["count"]),variables={"flow":ctx["vars"]["flow"]},cloud=None,image="")');
 const bridge=createOperatorBridge(plugins),vars={global:{name:'keep'},flow:{count:2},module:{ok:true}};
 const output=await bridge.run({...config,variables:vars,image:'image',cloud:{unit:'mm',points:[[1,2,3]]}});assert.equal(output.result.value,3);assert.equal(vars.flow.count,2);assert.equal(output.variables.flow.count,3);assert.equal(output.variables.global.name,'keep');assert.equal(output.cloud,null);assert.equal(output.annotatedImage,'');
 await assert.rejects(bridge.run({...config,variables:{unknown:{}}}),/未知/);
});
test('malformed plugin frame/variable output fails before a Node-RED message is published',async()=>{
 for(const suffix of ['cloud={"unit":"bad","points":[[0,0,0]]}','variables={"invalid":{}}','image=123','annotatedImage=123']){
  const bridge=createOperatorBridge(fixture('def run(ctx):\n    return dict(result=dict(value=1),'+suffix+')'));
  const node=nodeHarness(bridge).create();const result=await input(node,{});assert(result.error);assert.equal(result.sent.length,0);
 }
});
test('plugin active counts block enable changes and bound concurrency; cancellation releases slots',async()=>{
 const plugins=fixture('import time\ndef run(ctx):\n    time.sleep(3)\n    return dict(result=dict(value=1))'),controllers=Array.from({length:4},()=>new AbortController());
 const pending=controllers.map(c=>plugins.run(config,{}, {signal:c.signal}));const settled=Promise.allSettled(pending);
 assert.equal(plugins.activeCount,4);assert.throws(()=>plugins.setEnabled('bridge-test',false),/正在执行/);
 await assert.rejects(plugins.run(config,{}),/并发/);
 controllers.forEach(c=>c.abort());assert((await settled).every(r=>r.status==='rejected'));assert.equal(plugins.activeCount,0);plugins.setEnabled('bridge-test',false);
});
test('Node-RED resolves message bindings last, pins plugin identity and routes frame/results',async()=>{
 let request;const harness=nodeHarness({list:()=>[],async run(r){request=r;return {result:{count:2},annotatedImage:'output',cloud:null,depth:null,variables:{global:{},flow:{n:2},module:{}},elapsedMs:10};}});
 assert.equal(harness.permission,'flows.read');assert.equal(harness.route[0],'/machine/operators');
 const node=harness.create({arguments:'{"n":1}',parameterBindings:'{"n":"payload.count"}'});
 const result=await input(node,{payload:{count:3,image:'source'},operatorArgs:{n:2},pluginId:'injected'});
 assert.equal(request.arguments.n,3);assert.equal(request.image,'source');assert.equal(request.pluginId,'bridge-test');assert.equal(result.error,undefined);assert.equal(result.sent.length,1);assert.equal(result.sent[0][0].payload.count,2);assert.equal(result.sent[0][1].payload,'output');assert.equal(result.sent[0][0].operatorVariables.flow.n,2);
});
test('unsafe or missing message paths fail without calling the plugin',async()=>{
 let calls=0;const harness=nodeHarness({run(){calls++;}});
 for(const field of ['payload.__proto__.x','payload.constructor','missing','payload..n']){const result=await input(harness.create({parameterBindings:JSON.stringify({n:field})}),{payload:{n:1}});assert(result.error);}
 assert.equal(calls,0);
});
test('busy nodes reject overlap and redeployment cancels work without output',async()=>{
 let signal,reject;const harness=nodeHarness({run(_r,options){signal=options.signal;return new Promise((_resolve,r)=>{reject=r;signal.addEventListener('abort',()=>r(Error('取消')));});}}),node=harness.create();
 const first=input(node,{});const second=await input(node,{});assert.match(second.error.message,/上一条消息/);node.handlers.close();assert.equal(signal.aborted,true);const done=await first;assert.equal(done.sent.length,0);assert.equal(done.error,undefined);
});
