'use strict';
const fs=require('node:fs');
const path=require('node:path');
const types=require('../public/vision/variable-types.js');
const forbidden=new Set(['__proto__','prototype','constructor']);
function validate(value,depth=0){
  if(depth>20)throw Error('变量嵌套超过 20 层');
  if(value===null||typeof value==='string'||typeof value==='boolean')return;
  if(typeof value==='number'&&Number.isFinite(value))return;
  if(Array.isArray(value)){for(const item of value)validate(item,depth+1);return;}
  if(value&&typeof value==='object'){for(const [key,item] of Object.entries(value)){if(forbidden.has(key))throw Error('变量名称不可使用 '+key);validate(item,depth+1);}return;}
  throw Error('变量必须是有效 JSON 值');
}
function object(value,label){if(!value||typeof value!=='object'||Array.isArray(value))throw Error(label+' 必须是对象');validate(value);if(Buffer.byteLength(JSON.stringify(value))>1_000_000)throw Error(label+' 超过 1 MB');return structuredClone(value);}
const defaults=(stored,initial)=>({...structuredClone(initial||{}),...structuredClone(stored||{})});
class VariableStore{
  constructor(directory){this.file=path.join(directory,'runtime-variables.json');this.state=fs.existsSync(this.file)?JSON.parse(fs.readFileSync(this.file,'utf8')):{revision:0,global:{},projects:{}};object(this.state,'变量存储');this.state.globalTypes=types.definitions(this.state.globalTypes);types.assert(this.state.global,this.state.globalTypes,'全局变量');}
  snapshot(project){const saved=this.state.projects[project.id]||{};const modules={};for(const step of project.steps)modules[step.id]=defaults(saved.modules?.[step.id],step.variables);return {revision:this.state.revision,global:structuredClone(this.state.global),globalTypes:structuredClone(this.state.globalTypes),flow:defaults(saved.flow,project.variables),modules};}
  assertTypes(project,state,globalTypes=this.state.globalTypes){
    types.assert(state.global,globalTypes,'global');types.assert(state.flow,project.variableTypes,'flow');
    for(const step of project.steps)types.assert(state.modules[step.id]||{},step.variableTypes,'module['+step.id+']');
  }
  commit(project,state,revision,globalTypes=this.state.globalTypes){
    if(revision!==this.state.revision)throw Error('变量已被其他操作更新，请重新读取');
    const next=structuredClone(this.state);next.global=object(state.global,'全局变量');next.globalTypes=types.definitions(globalTypes);this.assertTypes(project,state,next.globalTypes);next.projects[project.id]={flow:object(state.flow,'流程变量'),modules:object(state.modules,'模块变量')};next.revision++;
    if(Buffer.byteLength(JSON.stringify(next))>8_000_000)throw Error('变量持久化总量超过 8 MB');
    fs.mkdirSync(path.dirname(this.file),{recursive:true});fs.writeFileSync(this.file+'.tmp',JSON.stringify(next,null,2));fs.renameSync(this.file+'.tmp',this.file);this.state=next;return next.revision;
  }
}
function lookup(context,reference){
  if(typeof reference!=='string'||reference.length>300)throw Error('变量引用格式无效');const keys=reference.split('.');
  if(!['global','flow','module','results'].includes(keys[0])||keys.length<2)throw Error('引用须以 global、flow、module 或 results 开头');
  let value=context;for(const key of keys){if(!key||forbidden.has(key)||value===null||typeof value!=='object'||!Object.hasOwn(value,key))throw Error('引用不存在：'+reference);value=value[key];}return structuredClone(value);
}
function resolve(value,context){validate(value);const walk=v=>{if(Array.isArray(v))return v.map(walk);if(v&&typeof v==='object'){if(Object.keys(v).length===1&&Object.hasOwn(v,'$ref'))return lookup(context,v.$ref);return Object.fromEntries(Object.entries(v).map(([key,item])=>[key,walk(item)]));}return v;};return walk(value);}
module.exports={VariableStore,validate,object,resolve};
