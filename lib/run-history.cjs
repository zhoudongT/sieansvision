'use strict';
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const ID=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const terminal=new Set(['completed','failed','cancelled']);
class RunHistory{
  constructor(directory,{maxRecords=200,maxBytes=256*1024*1024,maxRecordBytes=50*1024*1024}={}){
    if(![maxRecords,maxBytes,maxRecordBytes].every(n=>Number.isSafeInteger(n)&&n>0))throw Error('历史保留限制必须是正整数');
    this.directory=path.join(directory,'run-history');this.maxRecords=maxRecords;this.maxBytes=maxBytes;this.maxRecordBytes=maxRecordBytes;this.records=[];this.warnings=[];this.pending=Promise.resolve();
    if(!fs.existsSync(this.directory))return;
    const entries=fs.readdirSync(this.directory),known=new Set();
    for(const name of entries.filter(n=>n.endsWith('.meta.json'))){
      const id=name.slice(0,-10);if(!ID.test(id))continue;
      try{const metaFile=this.file(id,'meta'),dataFile=this.file(id,'data');if(fs.statSync(metaFile).size>32000)throw Error('摘要过大');const meta=JSON.parse(fs.readFileSync(metaFile,'utf8'));
        this.validateSummary(meta,id);if(fs.statSync(dataFile).size!==meta.bytes)throw Error('记录长度不符');this.records.push(meta);known.add(id);
      }catch{this.warnings.push('部分历史摘要不可用，正在尝试恢复。');}
    }
    // A completed detail write may outlive a crash before its summary was written.
    for(const name of entries.filter(n=>n.endsWith('.data.json'))){const id=name.slice(0,-10);if(!ID.test(id)||known.has(id))continue;
      try{const file=this.file(id,'data');if(fs.statSync(file).size>this.maxRecordBytes)throw Error('记录过大');const content=fs.readFileSync(file,'utf8'),record=JSON.parse(content);if(record.version!==1||record.id!==id)throw Error('记录格式无效');const meta=this.summary(record,content);this.validateSummary(meta,id);fs.writeFileSync(this.file(id,'meta'),JSON.stringify(meta));this.records.push(meta);known.add(id);
      }catch{this.warnings.push('存在无法恢复的历史文件；已保留原文件。');}
    }
    this.records.sort((a,b)=>b.startedAt-a.startedAt||b.id.localeCompare(a.id));this.warnings=[...new Set(this.warnings)];
    while(this.records.length>this.maxRecords||this.records.reduce((sum,r)=>sum+r.bytes,0)>this.maxBytes){
      const oldest=this.records.at(-1);try{fs.unlinkSync(this.file(oldest.id,'data'));}catch(error){if(error.code!=='ENOENT'){this.warnings.push('历史清理失败；请检查存储目录权限与可用空间。');break;}}this.records.pop();
      try{fs.unlinkSync(this.file(oldest.id,'meta'));}catch(error){if(error.code!=='ENOENT'&&!this.warnings.includes('部分过期摘要无法清理。'))this.warnings.push('部分过期摘要无法清理。');}
    }
  }
  file(id,kind){if(typeof id!=='string'||!ID.test(id))throw Object.assign(Error('运行记录 ID 无效'),{status:400});return path.join(this.directory,id+'.'+kind+'.json');}
  validateSummary(meta,id){if(!meta||meta.id!==id||!terminal.has(meta.state)||typeof meta.projectId!=='string'||typeof meta.projectName!=='string'||!Number.isFinite(meta.startedAt)||!Number.isFinite(meta.endedAt)||!Number.isSafeInteger(meta.bytes)||meta.bytes<1||meta.bytes>this.maxRecordBytes||!(/^[a-f0-9]{64}$/).test(meta.sha256))throw Error('运行记录摘要无效');}
  summary(record,content){return {id:record.id,projectId:record.project.id,projectName:record.project.name,state:record.state,origin:record.origin,startedAt:record.startedAt,endedAt:record.endedAt,elapsedMs:record.endedAt-record.startedAt,
    stepCount:record.plannedStepIds.length,finishedSteps:record.results.filter(r=>!r.skipped&&!r.error).length,skippedSteps:record.results.filter(r=>r.skipped).length,
    inspectionFailures:record.results.filter(r=>r.output?.result?.passed===false).length,error:record.error||'',framesSaved:record.framesSaved,bytes:Buffer.byteLength(content),sha256:crypto.createHash('sha256').update(content).digest('hex')};}
  async store(record){
    this.file(record.id,'data');if(record.version!==1||!terminal.has(record.state))throw Error('只能归档已结束的作业');
    const content=JSON.stringify(record),meta=this.summary(record,content);if(meta.bytes>this.maxRecordBytes)throw Error('单次运行记录超过 '+Math.round(this.maxRecordBytes/1048576)+' MiB 上限');this.validateSummary(meta,record.id);
    if(meta.bytes>this.maxBytes)throw Error('单次运行记录超过历史存储容量');
    const task=this.pending.then(()=>this.write(content,meta));this.pending=task.catch(()=>{});return task;
  }
  async write(content,meta){
    if(this.records.some(r=>r.id===meta.id))throw Error('运行记录已存在，不可覆盖');
    await fs.promises.mkdir(this.directory,{recursive:true});
    for(const [kind,data] of [['data',content],['meta',JSON.stringify(meta)]]){const file=this.file(meta.id,kind);await fs.promises.writeFile(file+'.tmp',data);await fs.promises.rename(file+'.tmp',file);}
    this.records.unshift(meta);this.records.sort((a,b)=>b.startedAt-a.startedAt||b.id.localeCompare(a.id));
    while(this.records.length>this.maxRecords||this.records.reduce((sum,r)=>sum+r.bytes,0)>this.maxBytes){
      const oldest=this.records.at(-1);try{await fs.promises.unlink(this.file(oldest.id,'data'));}catch(error){if(error.code!=='ENOENT')throw Error('历史清理失败：'+error.message);}this.records.pop();
      try{await fs.promises.unlink(this.file(oldest.id,'meta'));}catch(error){if(error.code!=='ENOENT'&&!this.warnings.includes('部分过期摘要无法清理。'))this.warnings.push('部分过期摘要无法清理。');}
    }
    return meta;
  }
  list({projectId='',state='',before,after,offset=0,limit=20}={}){
    offset=Number(offset);limit=Number(limit);
    if(!Number.isInteger(offset)||offset<0||!Number.isInteger(limit)||limit<1||limit>100)throw Error('历史分页参数无效');
    if(state&&!terminal.has(state))throw Error('运行状态筛选无效');
    const from=after==null||after===''?-Infinity:Number(after),to=before==null||before===''?Infinity:Number(before);
    if((after!=null&&after!==''&&!Number.isFinite(from))||(before!=null&&before!==''&&!Number.isFinite(to))||from>to)throw Error('历史时间范围无效');
    if(typeof projectId!=='string'||projectId.length>80)throw Error('工程筛选无效');
    const selected=this.records.filter(r=>(!projectId||r.projectId===projectId)&&(!state||r.state===state)&&r.startedAt>=from&&r.startedAt<=to);
    return {items:structuredClone(selected.slice(offset,offset+limit)),total:selected.length,offset,limit,storedCount:this.records.length,storedBytes:this.records.reduce((sum,r)=>sum+r.bytes,0),maxRecords:this.maxRecords,maxBytes:this.maxBytes,warnings:[...this.warnings]};
  }
  async get(id){
    this.file(id,'data');const meta=this.records.find(r=>r.id===id);if(!meta)throw Object.assign(Error('运行记录不存在或已按保留策略清理'),{status:404});
    try{const file=this.file(id,'data'),stat=await fs.promises.stat(file);if(stat.size!==meta.bytes||stat.size>this.maxRecordBytes)throw Error('运行记录已损坏（长度不符）');
      const content=await fs.promises.readFile(file,'utf8');if(crypto.createHash('sha256').update(content).digest('hex')!==meta.sha256)throw Error('运行记录已损坏（校验不符）');return JSON.parse(content);
    }catch(error){throw Object.assign(Error(error.code==='ENOENT'?'运行记录文件已不存在，请刷新列表':error.message),{status:error.code==='ENOENT'?404:409});}
  }
}
function archiveRecord(job,project,steps,input,variables){
  const framesSaved=project.history?.includeFrames===true;
  const results=job.results.map(row=>{const copy={...row};if(row.output){copy.output={...row.output};if(!framesSaved)for(const key of ['image','annotatedImage','maskImage','cloud','depth'])delete copy.output[key];}return copy;});
  return {version:1,id:job.id,project:structuredClone(project),plannedStepIds:steps.map(s=>s.id),state:job.state,origin:job.origin,startedAt:job.startedAt,endedAt:job.endedAt,error:job.error||'',monitorWarning:job.monitorWarning||'',framesSaved,
    variablesCommitted:job.state==='completed',variables:structuredClone(variables),results,...(job.trigger?{trigger:structuredClone(job.trigger)}:{}),...(framesSaved?{input:structuredClone(input)}:{})};
}
module.exports={RunHistory,archiveRecord};
