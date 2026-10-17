const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path');
const {Runtime}=require('../lib/runtime.cjs');
const graph=require('../public/vision/flow-graph.js');
const {resolve}=require('../lib/variable-store.cjs');
const script=require('../lib/script-runner.cjs');
const variableTypes=require('../public/vision/variable-types.js');
const dir=()=>fs.mkdtempSync(path.join(os.tmpdir(),'sieans-runtime-'));
const node=(id,operation,params={})=>({id,operation,params});
const project=(id,steps)=>graph.normalize({version:1,id,name:id,steps});
async function run(runtime,p,options={}){const started=runtime.start({project:p,image:'',...options});await runtime.jobs.get(started.id).promise;return runtime.poll(started.id);}

test('fixed variable types reject coercion, unsafe integers, wrong array elements and malformed definitions',()=>{
  for(const [type,good,bad] of [['number',1.5,'1.5'],['integer',3,3.1],['string','3',3],['boolean',true,1],['array',[1,'a'],{}],['object',{a:1},[]],['null',null,0],['number[]',[1,2.5],[1,'2']],['integer[]',[1,2],[1,2.5]],['string[]',['a'],[1]],['boolean[]',[true],[0]]]){
    variableTypes.assert({v:good},{v:type});assert.throws(()=>variableTypes.assert({v:bad},{v:type}),/类型不匹配/);
  }
  assert.throws(()=>variableTypes.assert({v:Infinity},{v:'number'}),/类型/);
  assert.throws(()=>variableTypes.assert({v:Number.MAX_SAFE_INTEGER+1},{v:'integer'}),/类型/);
  assert.throws(()=>variableTypes.assert({},{v:'number'}),/不能删除/);
  for(const definitions of [[],null,{v:'int'},JSON.parse('{"__proto__":"number"}'),{v:['number']}])assert.throws(()=>variableTypes.definitions(definitions));
});

test('flow/module type definitions survive graph operations and validate initial values',()=>{
  const p=project('types',[{...node('a','variables',{scope:'module',name:'ok',value:true}),variables:{ok:false},variableTypes:{ok:'boolean'}}]);
  p.variables={count:0};p.variableTypes={count:'integer'};
  assert.deepEqual(graph.layout(graph.normalize(p)).variableTypes,{count:'integer'});
  assert.deepEqual(graph.normalize(p).steps[0].variableTypes,{ok:'boolean'});
  for(const value of ['0',null,.5]){const bad=structuredClone(p);bad.variables.count=value;assert.throws(()=>graph.normalize(bad),/流程初始变量.count/);}
});

test('type mismatch stops before downstream execution and rolls back all earlier mutations',async()=>{
  let calls=0;const runtime=new Runtime(dir(),{run:async()=>{calls++;return {result:{},elapsedMs:0};}});
  const p=project('typed-stop',[node('one','variables',{scope:'global',name:'changed',value:1}),node('bad','variables',{scope:'flow',name:'count',value:'3'}),node('downstream','geometry')]);
  p.variables={count:0};p.variableTypes={count:'integer'};
  const result=await run(runtime,p,{image:'image'});assert.equal(result.state,'failed');assert.match(result.error,/flow.count 类型不匹配/);
  assert.equal(calls,0);assert.equal(result.results.at(-1).id,'bad');assert.deepEqual(runtime.snapshot(p).global,{});assert.equal(runtime.snapshot(p).flow.count,0);
  p.steps[1].params.value=3;assert.equal((await run(runtime,p,{image:'image'})).state,'completed');assert.equal(calls,1);
});

test('persisted values conflicting with a new contract fail preflight and remain repairable',async()=>{
  const runtime=new Runtime(dir(),{}),p=project('migration',[node('set','variables',{name:'count',value:'old'})]);
  await run(runtime,p);p.variables={count:0};p.variableTypes={count:'integer'};
  assert.throws(()=>runtime.start({project:p}),/flow.count 类型不匹配/);assert.equal(runtime.active,null);
  let state=runtime.snapshot(p);assert.equal(state.flow.count,'old');delete state.flow.count;
  state=runtime.update(p,state,state.revision);assert.equal(state.flow.count,0);
  p.steps[0].params.value=4;assert.equal((await run(runtime,p)).variables.flow.count,4);
});

test('global type contracts persist across projects and cannot be bypassed by an omitted type map',async()=>{
  const folder=dir(),runtime=new Runtime(folder,{}),p=project('globals',[]);
  let state=runtime.snapshot(p);state.global.counter=2;state.globalTypes.counter='integer';state=runtime.update(p,state,state.revision);
  const other=project('other',[node('bad','variables',{scope:'global',name:'counter',value:false})]);
  const failed=await run(new Runtime(folder,{}),other);assert.equal(failed.state,'failed');assert.match(failed.error,/global.counter 类型不匹配/);
  const changed=structuredClone(state);delete changed.globalTypes;changed.global.counter='wrong';assert.throws(()=>runtime.update(p,changed,state.revision),/类型不匹配/);
  delete changed.global.counter;assert.throws(()=>runtime.update(p,changed,state.revision),/不能删除/);
  state.global.counter=3;const updated=runtime.update(p,state,state.revision);
  assert.throws(()=>runtime.update(p,state,state.revision),/其他操作/);
  updated.globalTypes={};updated.global.counter='deliberately dynamic';runtime.update(p,updated,updated.revision);
  assert.deepEqual(new Runtime(folder,{}).snapshot(other).globalTypes,{});
});

test('Python replacements, plugin output bindings and module mutations honor contracts',async()=>{
  for(const code of ['def run(ctx):\n    return {"variables":{"flow":{"count":"bad"}}}', 'def run(ctx):\n    return {"variables":{"flow":{}}}', 'def run(ctx):\n    return {"variables":{"module":{"ok":1}}}']){
    const runtime=new Runtime(dir(),{}),p=project('script-types',[{...node('py','script',{code}),variables:{ok:false},variableTypes:{ok:'boolean'}}]);p.variables={count:0};p.variableTypes={count:'integer'};
    const failed=await run(runtime,p,{allowScripts:true});assert.equal(failed.state,'failed');assert.equal(runtime.snapshot(p).revision,0);
  }
  const plugins={get(){return {};},async run(){return {data:{result:{count:'bad'}},elapsedMs:0};}};
  const runtime=new Runtime(dir(),{},plugins),p=project('plugin-types',[node('plug','plugin',{outputBindings:[{field:'count',scope:'flow',name:'count'}]})]);p.variables={count:0};p.variableTypes={count:'integer'};
  const failed=await run(runtime,p);assert.equal(failed.state,'failed');assert.match(failed.error,/flow.count/);
});

test('manual and HMI-style updates validate all scopes atomically without coercion',()=>{
  const runtime=new Runtime(dir(),{}),p=project('manual-types',[{...node('m','variables',{scope:'module',name:'labels',value:['A']}),variables:{labels:[]},variableTypes:{labels:'string[]'}}]);p.variables={count:0};p.variableTypes={count:'integer'};
  for(const change of [s=>s.flow.count='3',s=>s.modules.m.labels=[1],s=>{s.globalTypes={flag:'boolean'};s.global.flag=0;}]){
    const state=runtime.snapshot(p);change(state);assert.throws(()=>runtime.update(p,state,state.revision),/类型不匹配/);assert.equal(runtime.snapshot(p).revision,0);
  }
  const state=runtime.snapshot(p);state.modules.m.labels=['A','B'];state.flow.count=7;
  assert.deepEqual(runtime.update(p,state,state.revision).modules.m.labels,['A','B']);
});

test('legacy stores and dynamic variables retain their original behavior',async()=>{
  const folder=dir();fs.writeFileSync(path.join(folder,'runtime-variables.json'),JSON.stringify({revision:4,global:{v:1},projects:{}}));
  const runtime=new Runtime(folder,{}),p=project('legacy-types',[node('set','variables',{scope:'global',name:'v',value:'text'})]);
  const job=await run(runtime,p);assert.equal(job.state,'completed');assert.equal(job.variables.global.v,'text');assert.deepEqual(job.variables.globalTypes,{});assert.equal(job.variables.revision,5);
});
test('three scopes isolate modules/flows, share globals and survive reload',async()=>{
  const folder=dir(),runtime=new Runtime(folder,{});
  const p=project('flow-one',[node('a','variables',{scope:'global',name:'total',mode:'increment',value:1}),node('b','variables',{scope:'flow',name:'count',value:7}),node('c','variables',{scope:'module',name:'local',value:3})]);
  let result=await run(runtime,p);assert.equal(result.state,'completed');assert.equal(result.variables.global.total,1);assert.equal(result.variables.flow.count,7);assert.equal(result.variables.modules.c.local,3);assert.deepEqual(result.variables.modules.a,{});
  const second=project('flow-two',[node('c','variables',{scope:'flow',name:'other',value:9})]);result=await run(runtime,second);assert.equal(result.variables.global.total,1);assert.equal(result.variables.flow.count,undefined);assert.deepEqual(result.variables.modules.c,{});
  const reloaded=new Runtime(folder,{});assert.equal(reloaded.snapshot(p).modules.c.local,3);assert.equal(reloaded.snapshot(p).flow.count,7);
});
test('typed parameter bindings read ancestor results and scoped values',async()=>{
  const runtime=new Runtime(dir(),{run:async request=>({result:{count:4,threshold:request.params.threshold},annotatedImage:request.image,elapsedMs:1})});
  const p=project('bindings',[node('a','variables',{scope:'flow',name:'threshold',value:125}),node('vision','geometry',{threshold:{$ref:'flow.threshold'}}),node('b','variables',{scope:'module',name:'count',value:{$ref:'results.vision.count'}})]);
  const result=await run(runtime,p,{image:'image'});assert.equal(result.state,'completed');assert.equal(result.results[1].output.result.threshold,125);assert.equal(result.variables.modules.b.count,4);
  assert.throws(()=>resolve({x:{$ref:'flow.missing'}},{flow:{}}),/不存在/);
  assert.throws(()=>resolve(JSON.parse('{"__proto__":{}}'),{}),/名称/);
});
test('failure rolls back earlier variable changes',async()=>{
  const runtime=new Runtime(dir(),{}),p=project('rollback',[node('a','variables',{scope:'global',name:'count',value:42}),node('b','variables',{scope:'flow',name:'bad',value:{$ref:'flow.missing'}})]);
  const result=await run(runtime,p);assert.equal(result.state,'failed');assert.deepEqual(runtime.snapshot(p).global,{});assert.equal(runtime.snapshot(p).revision,0);
});
test('server refuses overlapping executions and stale variable edits',async()=>{
  let release;const runtime=new Runtime(dir(),{run:()=>new Promise(r=>release=r)}),p=project('lock',[node('a','geometry')]);
  const started=runtime.start({project:p,image:'img'});assert.throws(()=>runtime.start({project:p,image:'img'}),/其他任务/);assert.throws(()=>runtime.update(p,{global:{},flow:{},modules:{}},0),/执行期间/);
  release({result:{},annotatedImage:'img',elapsedMs:1});await runtime.jobs.get(started.id).promise;
  assert.throws(()=>runtime.update(p,{global:{},flow:{},modules:{}},0),/其他操作/);
});
test('real Python script reads data, logs and writes scoped variables',async()=>{
  const runtime=new Runtime(dir(),{}),code='def run(ctx):\n    print("识别完成")\n    v=ctx["vars"]\n    v["flow"]["count"]=3\n    v["module"]["called"]=True\n    return {"result":{"passed":True},"variables":v}\n';
  const p=project('python',[node('py','script',{code,timeoutMs:3000})]);
  assert.throws(()=>runtime.start({project:p,image:''}),/可信/);
  const result=await run(runtime,p,{allowScripts:true});assert.equal(result.state,'completed',result.error);assert.equal(result.variables.flow.count,3);assert.equal(result.variables.modules.py.called,true);assert.match(result.results[0].output.logs,/识别完成/);
});
test('Python timeout and explicit cancel release runtime without committing variables',async()=>{
  await assert.rejects(script.run('while True: pass',{}, {timeoutMs:150}),/超时/);
  const runtime=new Runtime(dir(),{}),p=project('cancel',[node('set','variables',{scope:'global',name:'changed',value:true}),node('py','script',{code:'import time\ndef run(ctx):\n    time.sleep(10)\n    return {}',timeoutMs:20000})]);
  const started=runtime.start({project:p,image:'',allowScripts:true});runtime.cancel(started.id);await runtime.jobs.get(started.id).promise;
  assert.equal(runtime.poll(started.id).state,'cancelled');assert.deepEqual(runtime.snapshot(p).global,{});assert.equal(runtime.active,null);
});
test('script malformed output and non-finite values fail without corrupting store',async()=>{
  const runtime=new Runtime(dir(),{}),p=project('invalid',[node('py','script',{code:'def run(ctx):\n    return {"result":{"v":float("nan")}}',timeoutMs:3000})]);
  const result=await run(runtime,p,{allowScripts:true});assert.equal(result.state,'failed');assert.equal(runtime.snapshot(p).revision,0);
});
test('sibling result references cannot depend on accidental evaluation order',async()=>{
  const runtime=new Runtime(dir(),{});const p=graph.normalize({version:2,id:'siblings',name:'siblings',steps:[node('a','variables',{scope:'flow',name:'value',value:3}),node('b','variables',{scope:'flow',name:'bad',value:{$ref:'results.a.value'}})],edges:[{id:'e1',from:'source',to:'a'},{id:'e2',from:'source',to:'b'}]});
  const result=await run(runtime,p);assert.equal(result.state,'failed');assert.deepEqual(runtime.snapshot(p).flow,{});
});

test('script form inputs and output bindings preserve types across all scopes',async()=>{
  const runtime=new Runtime(dir(),{});
  const code='def run(ctx):\n    p=ctx["params"]\n    return {"result":{"inspection":{"count":p["threshold"]+1,"passed":True},"labels":["A","B"]}}';
  const p=project('script-form',[node('set','variables',{scope:'flow',name:'threshold',value:2}),node('py','script',{code,arguments:{threshold:{$ref:'flow.threshold'}},outputBindings:[{field:'inspection.count',scope:'flow',name:'count'},{field:'inspection.passed',scope:'module',name:'passed'},{field:'labels',scope:'global',name:'labels'}]})]);
  const result=await run(runtime,p,{allowScripts:true});assert.equal(result.state,'completed',result.error);assert.equal(result.variables.flow.count,3);assert.equal(result.variables.modules.py.passed,true);assert.deepEqual(result.variables.global.labels,['A','B']);
});

test('missing and duplicate script output bindings roll back all variable changes',async()=>{
  for(const bindings of [[{field:'missing',scope:'flow',name:'result'}],[{field:'count',scope:'flow',name:'result'},{field:'count',scope:'flow',name:'result'}]]){
    const runtime=new Runtime(dir(),{}),p=project('invalid-binding',[node('set','variables',{scope:'global',name:'changed',value:true}),node('py','script',{code:'def run(ctx):\n    return {"result":{"count":3}}',outputBindings:bindings})]);
    const result=await run(runtime,p,{allowScripts:true});assert.equal(result.state,'failed');assert.equal(runtime.snapshot(p).revision,0);assert.deepEqual(runtime.snapshot(p).global,{});
  }
});
