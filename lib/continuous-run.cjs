'use strict';
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const ACTIVE=new Set(['running','waiting','stopping']);
class ContinuousRun{
  constructor(runtime,directory){
    this.runtime=runtime;this.file=path.join(directory,'continuous-run.json');this.owner=Symbol('continuous');this.request=null;this.project=null;this.promise=null;this.wake=null;this.stopRequested=false;
    this.state={state:'idle',completedCycles:0,startedCycles:0,failedCycles:0,cancelledCycles:0};
    if(fs.existsSync(this.file)){
      const saved=JSON.parse(fs.readFileSync(this.file,'utf8'));
      if(!saved||saved.version!==1||typeof saved.state!=='string')throw Error('连续检测记录格式无效');
      this.state=saved;
      if(ACTIVE.has(saved.state)){this.state={...saved,state:'interrupted',endedAt:Date.now(),nextAt:null,error:'服务重启中断了连续检测；请检查设备状态后重新启动'};this.persist();}
    }
  }
  get busy(){return ACTIVE.has(this.state.state);}
  status(){return {...structuredClone(this.state),busy:this.busy,hasProject:!!this.project};}
  persist(){fs.mkdirSync(path.dirname(this.file),{recursive:true});fs.writeFileSync(this.file+'.tmp',JSON.stringify({version:1,...this.state}));fs.renameSync(this.file+'.tmp',this.file);}
  start(body,operatorContext=null){
    if(this.busy||this.runtime.busy)throw Error('运行平台正在执行其他任务，请先停止');
    const intervalMs=body.intervalMs??1000,maxCycles=body.maxCycles??0;
    if(!Number.isInteger(intervalMs)||intervalMs<100||intervalMs>3600000)throw Error('轮次间隔必须为 100–3600000 毫秒');
    if(!Number.isInteger(maxCycles)||maxCycles<0||maxCycles>1000000)throw Error('执行次数必须为 0–1000000，0 表示直到停止');
    if(body.target!==undefined)throw Error('连续检测只支持完整流程');
    const prepared=this.runtime.prepare(body);
    if(!prepared.steps.length)throw Error('连续检测需要至少一个流程模块');
    // Capture a private project/input snapshot. Edits and browser lifetime cannot change a running session.
    const request={project:prepared.project,...prepared.input,allowScripts:body.allowScripts===true};
    this.runtime.reserve(this.owner);this.stopRequested=false;
    this.request=structuredClone(request);this.project=structuredClone(prepared.project);
    this.state={id:crypto.randomUUID(),projectId:prepared.project.id,projectName:prepared.project.name,state:'running',intervalMs,maxCycles,startedAt:Date.now(),endedAt:null,nextAt:null,startedCycles:0,completedCycles:0,failedCycles:0,cancelledCycles:0,lastJobId:null,lastElapsedMs:0,error:null};
    if(operatorContext){this.state.operatorPublicationVersion=operatorContext.publicationVersion;this.state.startedBy=operatorContext.startedBy;}
    try{this.persist();}catch(error){this.state.state='failed';this.state.error='连续检测记录保存失败：'+error.message;this.runtime.release(this.owner);this.request=null;throw Error(this.state.error);}
    // Defer first execution until after the session and promise are visible to callers.
    this.promise=Promise.resolve().then(()=>this.execute());return this.status();
  }
  stop(id){
    if(!id||id!==this.state.id)throw Error('连续检测会话已变化，请刷新后停止');
    if(!this.busy)return this.status();
    this.stopRequested=true;this.state.state='stopping';this.state.nextAt=null;
    if(this.runtime.active&&this.runtime.active.id===this.state.lastJobId)this.runtime.cancel(this.state.lastJobId);
    this.wake?.();return this.status();
  }
  wait(ms){return new Promise(resolve=>{const timer=setTimeout(done,ms);const self=this;function done(){clearTimeout(timer);if(self.wake===done)self.wake=null;resolve();}this.wake=done;if(this.stopRequested)done();});}
  async execute(){
    try{
      while(!this.stopRequested){
        this.state.state='running';this.state.nextAt=null;
        const accepted=this.runtime.start(this.request,this.owner),job=this.runtime.jobs.get(accepted.id);
        this.state.lastJobId=accepted.id;this.state.startedCycles++;await job.promise;
        this.state.lastElapsedMs=job.endedAt-job.startedAt;
        if(job.state==='completed')this.state.completedCycles++;
        else if(job.state==='cancelled'){this.state.cancelledCycles++;this.stopRequested=true;}
        else{this.state.failedCycles++;throw Error(job.error||'本轮执行失败');}
        if(job.archive?.state==='failed')throw Error(job.archive.error+'；连续检测已停止，已提交变量保留');
        if(job.monitorWarning)throw Error(job.monitorWarning+'；连续检测已停止，已提交变量保留');
        if(this.stopRequested)break;
        if(this.state.maxCycles&&this.state.completedCycles>=this.state.maxCycles){this.state.state='completed';return;}
        this.state.state='waiting';this.state.nextAt=Date.now()+this.state.intervalMs;this.persist();
        await this.wait(this.state.intervalMs);
      }
      this.state.state='stopped';
    }catch(error){
      // Failed persistence or execution never leaves another cycle scheduled.
      this.state.state='failed';this.state.error=error.message;
      if(this.runtime.active&&this.runtime.active.id===this.state.lastJobId){this.runtime.cancel(this.state.lastJobId);await this.runtime.jobs.get(this.state.lastJobId).promise;}
    }finally{
      this.state.endedAt=Date.now();this.state.nextAt=null;this.request=null;this.wake=null;
      this.runtime.release(this.owner);
      try{this.persist();}catch(error){this.state.state='failed';this.state.error='连续检测记录保存失败：'+error.message;}
    }
  }
}
module.exports={ContinuousRun};
