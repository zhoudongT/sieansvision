'use strict';
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const graph=require('../public/vision/flow-graph.js'),hmi=require('../public/vision/hmi-layout.js');
const cloudPreview=require('../public/vision/cloud-viewer.js').preview;
const hash=value=>crypto.createHash('sha256').update(JSON.stringify(value)).digest('hex');
const problem=message=>{const e=Error(message);e.status=409;return e;};
function exact(body,keys){if(!body||typeof body!=='object'||Array.isArray(body)||Object.keys(body).some(k=>!keys.includes(k)))throw Error('请求包含未开放的操作字段');}
function continuousPolicy(value={enabled:false,intervalMs:1000,maxCycles:10}){exact(value,['enabled','intervalMs','maxCycles']);if(typeof value.enabled!=='boolean'||!Number.isInteger(value.intervalMs)||value.intervalMs<100||value.intervalMs>3600000||!Number.isInteger(value.maxCycles)||value.maxCycles<0||value.maxCycles>1000000)throw Error('连续检测发布设置无效：间隔 100–3600000 毫秒，次数 0–1000000');return {enabled:value.enabled,intervalMs:value.intervalMs,maxCycles:value.maxCycles};}
function publicationHash(p){return hash({project:p.project,allowScripts:p.allowScripts,...(p.format===2?{continuous:continuousPolicy(p.continuous)}:{})});}
function pick(target,pathText,value){const parts=pathText?pathText.split('.'):[];if(!parts.length)return structuredClone(value);let out=target;for(const part of parts.slice(0,-1)){if(['__proto__','constructor','prototype'].includes(part))throw Error('字段名称无效');out[part]??={};out=out[part];}if(['__proto__','constructor','prototype'].includes(parts.at(-1)))throw Error('字段名称无效');if(value!==undefined)out[parts.at(-1)]=structuredClone(value);return target;}
class OperatorRuntime{
 constructor(directory,runtime,continuous,mqtt){this.file=path.join(directory,'operator-publication.json');this.draft=path.join(directory,'vision-project.json');this.runtime=runtime;this.continuous=continuous;this.mqtt=mqtt;}
 draftState(){if(!fs.existsSync(this.draft))throw Error('请先保存服务器工程');const project=graph.normalize(JSON.parse(fs.readFileSync(this.draft,'utf8')));return {project,draftHash:hash(project),hasScripts:graph.expanded(project).some(s=>s.operation==='script')};}
 summary(){let draft=null;try{const d=this.draftState();draft={id:d.project.id,name:d.project.name,draftHash:d.draftHash,hasScripts:d.hasScripts};}catch(error){draft={error:error.message};}let p=null,publicationError='';try{p=this.load(false);}catch(error){publicationError=error.message;}return {draft,publicationError,publication:p?{id:p.project.id,name:p.project.name,version:p.version,publishedAt:p.publishedAt,publishedBy:p.publishedBy,allowScripts:p.allowScripts,continuous:p.format===2?continuousPolicy(p.continuous):continuousPolicy()}:null};}
 load(required=true){if(!fs.existsSync(this.file)){if(required)throw problem('尚未发布运行方案，请由管理员发布已保存工程');return null;}const p=JSON.parse(fs.readFileSync(this.file,'utf8'));if(![1,2].includes(p.format)||typeof p.allowScripts!=='boolean'||p.format===2&&!p.continuous)throw Error('运行方案发布记录无效');p.project=graph.normalize(p.project);if(p.version!==publicationHash(p))throw Error('运行方案完整性校验失败');return p;}
 publish(body,username){
  exact(body,['draftHash','allowScripts','continuous']);if(this.runtime.busy)throw problem('运行期间不可发布新方案，请先停止当前任务');const d=this.draftState();if(body.draftHash!==d.draftHash)throw problem('服务器工程已变化，请刷新并重新检查发布内容');if(typeof body.allowScripts!=='boolean'||d.hasScripts&&!body.allowScripts)throw Error('工程含 Python 脚本，需要管理员明确允许发布可信脚本');
  const policy=continuousPolicy(body.continuous);this.runtime.prepare({project:d.project,allowScripts:body.allowScripts});if(policy.enabled&&!d.project.steps.length)throw Error('连续检测需要至少一个流程模块');const p={format:2,project:d.project,allowScripts:body.allowScripts,continuous:policy,publishedAt:Date.now(),publishedBy:username};p.version=publicationHash(p);
  const temporary=this.file+'.'+crypto.randomUUID()+'.tmp';fs.writeFileSync(temporary,JSON.stringify(p)+'\n',{flag:'wx',mode:0o600});fs.renameSync(temporary,this.file);return this.summary();
 }
 current(version){const p=this.load();if(version!==p.version)throw problem('运行方案已更新，请刷新运行画面后重试');return p;}
 publicState(){
  const p=this.load(),state=this.runtime.view(p.project),components=hmi.allComponents(p.project.hmi),variables={global:{},flow:{},modules:{},revision:state.variables.revision},results=[];
  for(const c of components){const b=c.binding;if(!b)continue;
   if(['global','flow','module'].includes(b.source)){
    const scope=b.source==='module'?(variables.modules[b.nodeId]??={}):variables[b.source];let value;try{value=hmi.read(b,state);}catch{}
    if(!b.path&&value!==undefined){if(b.source==='module')variables.modules[b.nodeId]=structuredClone(value);else variables[b.source]=structuredClone(value);}else pick(scope,b.path,value);
   }
  }
  for(const row of state.results||[]){const refs=components.filter(c=>c.binding?.source==='result'&&c.binding.nodeId===row.id);if(!refs.length)continue;const out={id:row.id,...(row.error?{error:row.error}:{}),...(row.skipped?{skipped:true,reason:row.reason}:{}),output:{result:{},elapsedMs:row.output?.elapsedMs??0}};
   const cloudRefs=refs.filter(c=>c.type==='cloud');if(cloudRefs.length&&row.output?.cloud)out.output.cloud=cloudPreview(row.output.cloud,Math.max(...cloudRefs.map(c=>c.maxPoints)));
   for(const c of refs){if(c.type==='image')out.output.annotatedImage=row.output?.annotatedImage||'';else if(c.type!=='cloud'){const value=hmi.read(c.binding,state);if(value!==undefined)out.output.result=pick(out.output.result,c.binding.path,value);}}
   results.push(out);
  }
  const permitted=new Set(components.filter(c=>['alarm','trend'].includes(c.type)).map(c=>c.id));const monitor={...state.monitor,widgets:Object.fromEntries(Object.entries(state.monitor.widgets||{}).filter(([id])=>permitted.has(id))),events:(state.monitor.events||[]).filter(e=>permitted.has(e.componentId))};
  const session=this.continuous.state,owned=session?.operatorPublicationVersion===p.version;
  const continuous={busy:!!(this.continuous.busy||this.mqtt.busy),matchesPublication:!!owned,...(owned?Object.fromEntries(['id','state','intervalMs','maxCycles','startedAt','endedAt','nextAt','startedCycles','completedCycles','failedCycles','cancelledCycles','lastElapsedMs','lastJobId','startedBy'].map(key=>[key,session[key]])):{state:'idle'})};
  return {publication:{version:p.version,publishedAt:p.publishedAt,continuous:p.format===2?continuousPolicy(p.continuous):continuousPolicy()},project:{id:p.project.id,name:p.project.name,hmi:p.project.hmi||hmi.empty(),steps:p.project.steps.map(s=>({id:s.id,operation:s.operation,variables:{},params:{}}))},projectId:state.projectId,version:state.version,status:state.status,variables,results,monitor,continuous,busy:this.runtime.busy};
 }
 run(body){exact(body,['version','image','cloud']);const p=this.current(body.version),job=this.runtime.start({project:p.project,allowScripts:p.allowScripts,image:body.image??'',cloud:body.cloud??null});return {id:job.id,state:job.state};}
 async importCloud(body){
  exact(body,['version','name','content','unit']);this.current(body.version);
  if(typeof body.name!=='string'||body.name.length>255||body.name!==body.name.trim()||/[\/\\\x00-\x1f]/.test(body.name)||!/^.+\.(ply|pcd|xyz|xyzn|xyzrgb|pts)$/i.test(body.name)||!['mm','m'].includes(body.unit)||typeof body.content!=='string'||body.content.length>16000080||!/^data:[^,;]{0,100}(?:;[^,;]{0,100})?;base64,[A-Za-z0-9+/]+={0,2}$/.test(body.content))throw Error('请选择有效点云文件并明确原始单位 mm 或 m，文件上限 12 MB');
  const comma=body.content.indexOf(','),encoded=body.content.slice(comma+1);if(Buffer.from(encoded,'base64').length>12000000)throw Error('点云文件超过 12 MB');
  const owner=Symbol('operator-cloud-import');this.runtime.reserve(owner);this.importing=true;
  try{const result=await this.runtime.vision.run({operation:'cloud_import',name:body.name,content:body.content,unit:body.unit},{timeoutMs:15000});this.current(body.version);const cloud=require('./frame.cjs').cloud(result.cloud);if(cloud.unit!==body.unit)throw Error('导入点云的单位不一致');return {cloud};}finally{this.importing=false;this.runtime.release(owner);}
 }
 startContinuous(body,username){exact(body,['version','image','cloud']);const p=this.current(body.version),policy=p.format===2?continuousPolicy(p.continuous):continuousPolicy();if(!policy.enabled)throw problem('管理员未在此发布方案中开放连续检测');const session=this.continuous.start({project:p.project,allowScripts:p.allowScripts,image:body.image??'',cloud:body.cloud??null,intervalMs:policy.intervalMs,maxCycles:policy.maxCycles},{publicationVersion:p.version,startedBy:username});return {id:session.id,state:session.state};}
 stop(body){exact(body,[]);if(this.importing)throw problem('正在解析点云文件，请等待导入结束后操作');if(this.continuous.busy)this.continuous.stop(this.continuous.state.id);if(this.mqtt.busy)this.mqtt.stop(this.mqtt.state.id);if(this.runtime.active)this.runtime.cancel(this.runtime.active.id);return {stopping:this.runtime.busy};}
 write(body){
  exact(body,['version','componentId','value','revision']);const p=this.current(body.version);const c=hmi.allComponents(p.project.hmi).find(c=>c.id===body.componentId&&c.type==='input');if(!c)throw Error('该设定值未在已发布画面中开放');
  if(typeof body.value!==c.dataType||c.dataType==='number'&&(!Number.isFinite(body.value)||body.value<c.minimum||body.value>c.maximum)||c.dataType==='string'&&body.value.length>10000)throw Error('设定值类型或范围无效');
  const snapshot=this.runtime.snapshot(p.project),b=c.binding;if(snapshot.revision!==body.revision)throw problem('设定值已被其他客户端修改，请刷新');const target=b.source==='module'?snapshot.modules[b.nodeId]:snapshot[b.source];if(!target)throw Error('设定值绑定不存在');target[b.path]=body.value;this.runtime.update(p.project,snapshot,body.revision);return this.publicState().variables;
 }
 acknowledge(body){exact(body,['version','id','comment']);const p=this.current(body.version),event=this.runtime.monitor.view(p.project.id).events.find(e=>e.id===body.id);if(!event||!hmi.allComponents(p.project.hmi).some(c=>c.id===event.componentId&&c.type==='alarm'))throw Error('报警不属于已发布运行画面');this.runtime.monitor.acknowledge(p.project.id,body.id,body.comment??'');return this.publicState().monitor;}
}
module.exports={OperatorRuntime,hash,continuousPolicy};
