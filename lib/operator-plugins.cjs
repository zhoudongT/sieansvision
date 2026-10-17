'use strict';
// Trusted server-installed Python operators. Discovery never executes plugin code.
const fs=require('node:fs'),path=require('node:path');
const scripts=require('./script-runner.cjs');
const {object}=require('./variable-store.cjs');
const ID=/^[a-z][a-z0-9-]{0,63}$/,KEY=/^[A-Za-z_][A-Za-z0-9_]{0,63}$/;
const reserved=new Set(['__proto__','constructor','prototype']);
const types=new Set(['number','integer','string','boolean','array','object']);
function check(ok,message){if(!ok)throw Error(message);}
function text(v,n=200){return typeof v==='string'&&v.length>0&&v.length<=n;}
function value(v,f,label){
  const valid=f.type==='integer'?Number.isSafeInteger(v):f.type==='number'?typeof v==='number'&&Number.isFinite(v):f.type==='array'?Array.isArray(v):f.type==='object'?v!==null&&typeof v==='object'&&!Array.isArray(v):typeof v===f.type;
  check(valid,label+' 的类型必须为 '+f.type);
  if(typeof v==='number'){check(f.minimum===undefined||v>=f.minimum,label+' 低于最小值');check(f.maximum===undefined||v<=f.maximum,label+' 超过最大值');}
  if(f.choices)check(f.choices.some(c=>c.value===v),label+' 不在可选值内');
  if(f.columns){
    check(v.length>=(f.minimumRows??0)&&v.length<=(f.maximumRows??1000),label+' 行数超出允许范围');
    const keys=new Set(f.columns.map(c=>c.key));
    for(const [index,row] of v.entries()){
      check(row&&typeof row==='object'&&!Array.isArray(row),label+' 第 '+(index+1)+' 行必须为记录');
      for(const key of Object.keys(row))check(keys.has(key),label+' 包含未声明列：'+key);
      for(const column of f.columns){check(Object.hasOwn(row,column.key),label+' 缺少列：'+column.label);value(row[column.key],column,label+' 第 '+(index+1)+' 行 '+column.label);}
    }
  }
  object({value:v},label);
  return v;
}
function fields(list,label,inputs){
  check(Array.isArray(list)&&list.length<=100,label+' 最多 100 项');const names=new Set();
  for(const f of list){
    check(f&&KEY.test(f.key)&&!reserved.has(f.key)&&!names.has(f.key),label+' 名称无效或重复');names.add(f.key);
    check(text(f.label)&&types.has(f.type),label+' 标签或类型无效');
    check(f.required===undefined||typeof f.required==='boolean',label+' required 必须是开关');
    for(const k of ['minimum','maximum'])if(f[k]!==undefined)check(['number','integer'].includes(f.type)&&Number.isFinite(f[k]),label+' 数值范围无效');
    check(f.minimum===undefined||f.maximum===undefined||f.minimum<=f.maximum,label+' 数值范围颠倒');
    if(f.choices!==undefined){check(['string','number','integer','boolean'].includes(f.type)&&Array.isArray(f.choices)&&f.choices.length>0&&f.choices.length<=100,label+' 选项无效');for(const c of f.choices){check(c&&text(c.label),label+' 选项标签无效');value(c.value,{...f,choices:undefined},label);}}
    if(f.columns!==undefined){
      check(inputs&&f.type==='array'&&Array.isArray(f.columns)&&f.columns.length>0&&f.columns.length<=12,label+' 表格列配置无效');
      check(f.columns.every(c=>c&&!['array','object'].includes(c.type)&&c.columns===undefined),label+' 表格列必须为基础类型');
      fields(f.columns,label+' 表格列',true);
      for(const key of ['minimumRows','maximumRows'])if(f[key]!==undefined)check(Number.isInteger(f[key])&&f[key]>=0&&f[key]<=1000,label+' 表格行数范围无效');
      check((f.minimumRows??0)<=(f.maximumRows??1000),label+' 表格行数范围颠倒');
    }else check(f.minimumRows===undefined&&f.maximumRows===undefined,label+' 行数限制需要表格列');
    if(inputs&&Object.hasOwn(f,'default'))value(f.default,f,f.label+' 默认值');
  }
}
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
    const {p,op}=this.get(params),args=structuredClone(params.arguments||{});object(args,'插件参数');
    const known=new Set(op.parameters.map(f=>f.key));for(const k of Object.keys(args))check(known.has(k),'未知插件参数：'+k);
    for(const f of op.parameters){if(!Object.hasOwn(args,f.key)&&Object.hasOwn(f,'default'))args[f.key]=structuredClone(f.default);if(!Object.hasOwn(args,f.key)){check(!f.required,'缺少插件参数：'+f.label);continue;}value(args[f.key],f,f.label);}
    if(op.input!=='none')check(context[op.input],'插件需要输入'+({image:'图像',cloud:'点云',depth:'深度图'})[op.input]);
    check(this.activeCount<4,'算子插件并发已达 4 个，请降低输入频率');this.activeCount++;
    try{
    const response=await scripts.run(p.code.get(op.id),{...context,params:args},{timeoutMs:op.timeoutMs,signal});
    const result=object(response.data.result??{},'插件结果'),knownOut=new Set(op.outputs.map(f=>f.key));
    for(const key of Object.keys(result))check(knownOut.has(key),'插件返回未声明结果：'+key);
    for(const f of op.outputs){if(!Object.hasOwn(result,f.key)){check(!f.required,'插件缺少结果：'+f.label);continue;}value(result[f.key],f,f.label);}
    return response;
    }finally{this.activeCount--;}
  }
}
module.exports={OperatorPlugins,readPackage};
