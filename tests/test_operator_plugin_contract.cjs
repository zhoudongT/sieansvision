'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),os=require('node:os'),path=require('node:path');
const {OperatorPlugins,readPackage}=require('../lib/operator-plugins.cjs');
const {Runtime}=require('../lib/runtime.cjs'),graph=require('../public/vision/flow-graph.js');
const {fields}=require('../lib/operator-plugin-contract.cjs');
const point={key:'origin',label:'基准点',type:'object',required:true,properties:[{key:'x',label:'X',type:'number',required:true,unit:'mm'},{key:'y',label:'Y',type:'number',required:true,default:0}]};
function fixture(t,code){
 const directory=fs.mkdtempSync(path.join(os.tmpdir(),'plugin-contract-'));t.after(()=>fs.rmSync(directory,{recursive:true,force:true}));
 const folder=path.join(directory,'operator-plugins','typed');fs.mkdirSync(folder,{recursive:true});
 const manifest={apiVersion:1,id:'typed',name:'具名输入测试',version:'1.0.0',description:'隔离的契约验收',license:'MIT',operators:[{id:'offset',name:'点偏移',description:'组合参数和具名输入',category:'几何测量',input:'none',entry:'main.py',timeoutMs:2000,inputs:[point,{key:'samples',label:'采样值',type:'array',required:true,minimumRows:1,maximumRows:3,items:{type:'number',minimum:0}}],parameters:[{key:'gain',label:'倍率',type:'number',default:2,group:'计算',description:'采样值倍率',minimum:0}],outputs:[{...point,key:'point',label:'结果点'},{key:'samples',label:'采样结果',type:'array',required:true,items:{type:'number'}},{key:'rows',label:'记录',type:'array',columns:[{key:'value',label:'值',type:'integer'}],required:true}]}]};
 const save=()=>fs.writeFileSync(path.join(folder,'operator-plugin.json'),JSON.stringify(manifest));save();
 fs.writeFileSync(path.join(folder,'main.py'),code||'def run(ctx):\n    p = ctx["inputs"]["origin"]\n    return dict(result=dict(point=dict(x=p["x"]+ctx["params"]["gain"]*sum(ctx["inputs"]["samples"]),y=p["y"]),samples=ctx["inputs"]["samples"],rows=[dict(value=1)]))');
 return {directory,folder,manifest,save,registry:()=>new OperatorPlugins(directory,{bundled:path.join(directory,'empty')})};
}
const params=(inputs,extra={})=>({pluginId:'typed',pluginVersion:'1.0.0',operatorId:'offset',inputs,arguments:{},...extra});
test('named inputs reach Python separately from parameters, clone input values, and fill nested defaults',async t=>{
 const f=fixture(t),inputs={origin:{x:10},samples:[1,2]},registry=f.registry();const response=await registry.run(params(inputs),{});
 assert.deepEqual(response.data.result,{point:{x:16,y:0},samples:[1,2],rows:[{value:1}]});assert.deepEqual(inputs,{origin:{x:10},samples:[1,2]});
 const list=registry.list();assert.equal(list[0].operators[0].inputs[0].properties[0].unit,'mm');
});
test('named input and nested schema errors are rejected before spawning the Python entry',async t=>{
 const f=fixture(t,'raise RuntimeError("ENTRY_EXECUTED")'),registry=f.registry();
 for(const inputs of [undefined,{origin:{x:1},samples:[]},{origin:{x:1},samples:[-1]},{origin:{x:1},samples:[1,2,3,4]},{origin:{x:'1'},samples:[1]},{origin:{x:1,z:2},samples:[1]},{origin:{},samples:[1]},{origin:{x:1},samples:[1],typo:3}]){
  await assert.rejects(registry.run(params(inputs),{}),error=>{assert.doesNotMatch(error.message,/ENTRY_EXECUTED/);return true;});assert.equal(registry.activeCount,0);
 }
});
test('nested result fields and declared output tables reject wrong types, missing and extra fields',async t=>{
 for(const result of [{point:{x:1,y:'bad'},samples:[1],rows:[{value:1}]},{point:{x:1},samples:[1],rows:[{value:1}]},{point:{x:1,y:2,z:3},samples:[1],rows:[{value:1}]},{point:{x:1,y:2},samples:['bad'],rows:[{value:1}]},{point:{x:1,y:2},samples:[1],rows:[{value:1.5}]}]){
  const f=fixture(t,'import json\ndef run(ctx):\n    return dict(result=json.loads('+JSON.stringify(JSON.stringify(result))+'))');
  await assert.rejects(f.registry().run(params({origin:{x:1},samples:[1]}),{}));
 }
});
test('declarative schema rejects mismatched container types, unknown shapes, invalid choices and excessive nesting',t=>{
 const f=fixture(t),op=f.manifest.operators[0];
 for(const mutate of [o=>o.inputs[0].type='number',o=>o.inputs[0].properties[0].key='constructor',o=>o.inputs[1].items.key='x',o=>o.inputs[1].columns=[{key:'x',label:'X',type:'number'}],o=>o.parameters[0].choices=[{value:'wrong',label:'类型错误'}],o=>o.parameters[0].group='',o=>o.outputs[2].columns[0].type='object']){
  const copy=structuredClone(op);mutate(copy);f.manifest.operators=[copy];f.save();assert.throws(()=>readPackage(f.folder));
 }
 let nested={key:'end',label:'结尾',type:'number'};for(let i=0;i<8;i++)nested={key:'level',label:'层',type:'object',properties:[nested]};assert.throws(()=>fields([nested],'测试',true),/最多 6 层/);
});
test('upstream named-input bindings and nested output bindings run in the normal transactional runtime',async t=>{
 const f=fixture(t),runtime=new Runtime(f.directory,{},f.registry());
 const project=graph.normalize({version:1,id:'typed-project',name:'具名输入回归',steps:[{id:'start',operation:'variables',params:{scope:'flow',name:'x',value:4}},{id:'typed',operation:'plugin',params:params({origin:{x:{$ref:'results.start.value'}},samples:[1,2]},{outputBindings:[{field:'point.x',scope:'flow',name:'answer'}]})}]});
 const job=runtime.start({project});await runtime.jobs.get(job.id).promise;const result=runtime.poll(job.id);assert.equal(result.state,'completed',result.error);assert.equal(result.variables.flow.answer,10);
 const failed=structuredClone(project);failed.steps[1].params.inputs.samples=[-1];const next=runtime.start({project:failed});await runtime.jobs.get(next.id).promise;assert.equal(runtime.poll(next.id).state,'failed');assert.equal(runtime.snapshot(project).flow.answer,10);
});
