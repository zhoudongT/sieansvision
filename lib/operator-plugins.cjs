'use strict';
// Trusted server-installed Python operators. Discovery never executes plugin code.
const fs=require('node:fs'),path=require('node:path');
const scripts=require('./script-runner.cjs');
const {object}=require('./variable-store.cjs');
const ID=/^[a-z][a-z0-9-]{0,63}$/;
const reserved=new Set(['__proto__','constructor','prototype']);
const {check,text,fields,value,prepare}=require('./operator-plugin-contract.cjs');
function readPackage(folder){
  const real=fs.realpathSync(folder),manifestFile=path.join(real,'operator-plugin.json');
  check(!fs.lstatSync(manifestFile).isSymbolicLink()&&fs.statSync(manifestFile).size<=128000,'插件清单必须是 128 KB 内的普通文件');
  const m=JSON.parse(fs.readFileSync(manifestFile,'utf8'));object(m,'插件清单');
  check(m.apiVersion===1,'不兼容的插件接口版本，仅支持 1');
  check(ID.test(m.id)&&!reserved.has(m.id)&&text(m.name)&&/^\d+\.\d+\.\d+$/.test(m.version),'插件名称、标识或版本无效');
  check(text(m.description,2000)&&text(m.license),'插件必须说明用途及许可证');
  check(Array.isArray(m.operators)&&m.operators.length>0&&m.operators.length<=50,'每个插件需要 1–50 个算子');
  const ids=new Set(),code=new Map();
  for(const op of m.operators){
    check(op&&ID.test(op.id)&&!ids.has(op.id)&&text(op.name)&&text(op.description,2000),'算子名称或标识无效/重复');ids.add(op.id);
    check(['none','image','cloud','depth'].includes(op.input),'算子输入类型无效');
    check(typeof op.entry==='string'&&/^[A-Za-z0-9_-]+\.py$/.test(op.entry),'入口必须是插件目录中的 Python 文件名');
    const file=path.join(real,op.entry);check(!fs.lstatSync(file).isSymbolicLink()&&fs.statSync(file).isFile()&&fs.statSync(file).size<=100000,'插件入口必须是 100 KB 内的普通文件');
    fields(op.parameters,'输入参数',true);fields(op.outputs,'结果字段',false);
    if(op.inputs!==undefined)fields(op.inputs,'模块输入',true);
    if(op.category!==undefined)check(text(op.category,100),'算子分类无效');
    check(Number.isInteger(op.timeoutMs)&&op.timeoutMs>=100&&op.timeoutMs<=30000,'插件超时范围为 100–30000 ms');
    code.set(op.id,fs.readFileSync(file,'utf8'));
  }
  return {manifest:m,code};
}
class OperatorPlugins{
  constructor(directory,{bundled=path.join(__dirname,'..','operator-plugins')}={}){
    this.activeCount=0;this.directory=directory;this.roots=[bundled,path.join(directory,'operator-plugins')];this.stateFile=path.join(directory,'operator-plugin-state.json');this.reload();
  }
  reload(){
    check(!this.activeCount,'算子插件正在执行，暂不可重新扫描');
    const state=fs.existsSync(this.stateFile)?JSON.parse(fs.readFileSync(this.stateFile,'utf8')):{};object(state,'插件启用设置');
    this.records=[];this.registry=new Map();const seen=new Set();
    for(const root of this.roots){if(!fs.existsSync(root))continue;for(const item of fs.readdirSync(root,{withFileTypes:true}).sort((a,b)=>a.name.localeCompare(b.name))){
      if(!item.isDirectory()||item.isSymbolicLink())continue;
      try{
        const loaded=readPackage(path.join(root,item.name)),m=loaded.manifest;
        if(seen.has(m.id)){this.registry.delete(m.id);for(const record of this.records.filter(r=>r.id===m.id)){record.enabled=false;record.status='加载失败';record.error='插件 ID 重复：'+m.id;}throw Error('插件 ID 重复：'+m.id);}
        seen.add(m.id);
        const enabled=state[m.id]!==false;this.registry.set(m.id,{...loaded,enabled});this.records.push({...m,enabled,status:enabled?'已加载':'已停用'});
      }catch(error){this.records.push({id:item.name,name:item.name,version:'—',enabled:false,status:'加载失败',error:error.message,operators:[]});}
    }}
  }
  list(){return structuredClone(this.records);}
  setEnabled(id,enabled){
    check(this.activeCount===0,'算子插件正在执行，暂不可修改启用状态');
    check(this.registry.has(id)&&typeof enabled==='boolean','插件或启用状态无效');
    const state=fs.existsSync(this.stateFile)?JSON.parse(fs.readFileSync(this.stateFile,'utf8')):{};state[id]=enabled;
    fs.mkdirSync(this.directory,{recursive:true});fs.writeFileSync(this.stateFile+'.tmp',JSON.stringify(state));fs.renameSync(this.stateFile+'.tmp',this.stateFile);
    this.registry.get(id).enabled=enabled;for(const record of this.records.filter(r=>r.id===id&&!r.error)){record.enabled=enabled;record.status=enabled?'已加载':'已停用';}return this.list();
  }
  get(params){
    const p=this.registry.get(params.pluginId);check(p&&p.enabled,'插件未安装或已停用：'+String(params.pluginId));
    check(params.pluginVersion===p.manifest.version,'插件版本不匹配：工程 '+params.pluginVersion+'，已安装 '+p.manifest.version);
    const op=p.manifest.operators.find(o=>o.id===params.operatorId);check(op,'插件中不存在该算子');return {p,op};
  }
  async run(params,context,{signal}={}){
    const {p,op}=this.get(params),args=prepare(params.arguments,op.parameters,'插件参数'),inputs=prepare(params.inputs,op.inputs||[],'插件输入');
    if(op.input!=='none')check(context[op.input],'插件需要输入'+({image:'图像',cloud:'点云',depth:'深度图'})[op.input]);
    check(this.activeCount<4,'算子插件并发已达 4 个，请降低输入频率');this.activeCount++;
    try{
    const response=await scripts.run(p.code.get(op.id),{...context,params:args,inputs},{timeoutMs:op.timeoutMs,signal});
    const result=object(response.data.result??{},'插件结果'),knownOut=new Set(op.outputs.map(f=>f.key));
    for(const key of Object.keys(result))check(knownOut.has(key),'插件返回未声明结果：'+key);
    for(const f of op.outputs){if(!Object.hasOwn(result,f.key)){check(!f.required,'插件缺少结果：'+f.label);continue;}value(result[f.key],f,f.label);}
    return response;
    }finally{this.activeCount--;}
  }
}
module.exports={OperatorPlugins,readPackage};
