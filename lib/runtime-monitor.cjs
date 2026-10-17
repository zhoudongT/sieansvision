'use strict';
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),hmi=require('../public/vision/hmi-layout.js'),control=require('./flow-control.cjs');
const validId=id=>typeof id==='string'&&/^[A-Za-z0-9_-]{1,80}$/.test(id)&&!['__proto__','constructor','prototype'].includes(id);
class RuntimeMonitor{
 constructor(directory){
  this.file=path.join(directory,'runtime-monitor.json');this.state={version:1,revision:0,projects:{}};
  if(fs.existsSync(this.file)){
   if(fs.statSync(this.file).size>16*1024*1024)throw Error('监控记录超过 16 MB');
   const data=JSON.parse(fs.readFileSync(this.file,'utf8'));
   if(data.version!==1||!Number.isSafeInteger(data.revision)||!data.projects||typeof data.projects!=='object'||Array.isArray(data.projects))throw Error('监控记录格式无效');
   for(const [id,p] of Object.entries(data.projects))if(!validId(id)||!Array.isArray(p.events)||!p.widgets||typeof p.widgets!=='object')throw Error('监控工程记录无效');
   this.state=data;
  }
 }
 persist(next){
  const content=JSON.stringify(next);if(Buffer.byteLength(content)>16*1024*1024)throw Error('监控存储超过 16 MB，未写入本次采样');
  fs.mkdirSync(path.dirname(this.file),{recursive:true});const temporary=this.file+'.tmp';fs.writeFileSync(temporary,content);fs.renameSync(temporary,this.file);this.state=next;
 }
 batch(action){
  const initial=this.state,persist=this.persist;this.persist=next=>{this.state=next;};
  try{action();const next=this.state;this.state=initial;if(next!==initial)persist.call(this,next);}
  catch(error){this.state=initial;throw error;}
  finally{this.persist=persist;}
 }
 view(id){const project=this.state.projects[id];return {revision:this.state.revision,...(project?structuredClone(project):{widgets:{},events:[],discardedSamples:0,discardedEvents:0})};}
 observe(project,state,{kind='job',jobId='',time=Date.now()}={}){
  const configs=hmi.allComponents(project.hmi).filter(c=>['alarm','trend'].includes(c.type));
  if(!configs.length&&!this.state.projects[project.id])return;
  const next=structuredClone(this.state);next.revision++;
  const p=next.projects[project.id]??={widgets:{},events:[],discardedSamples:0,discardedEvents:0};p.updatedAt=time;
  const current=new Set(configs.map(c=>c.id));
  const retire=(id,reason)=>{const widget=p.widgets[id];if(widget?.activeId){const event=p.events.find(e=>e.id===widget.activeId);if(event&&!event.returnedAt){event.returnedAt=time;event.endReason=reason;}}if(widget?.samples)p.discardedSamples+=widget.samples.length;delete p.widgets[id];};
  for(const id of Object.keys(p.widgets))if(!current.has(id))retire(id,'组件已移除');
  for(const config of configs){
   const signature=JSON.stringify(Object.fromEntries(Object.entries(config).filter(([k])=>!['x','y','w','h','fontSize','color'].includes(k))));
   if(p.widgets[config.id]?.signature!==signature)retire(config.id,'监控配置已更改');
   const widget=p.widgets[config.id]??={type:config.type,label:config.label,signature,...(config.type==='trend'?{samples:[]}:{active:false,pending:0})};
   if(kind==='variables'&&['result','status'].includes(config.binding.source))continue;
   if(kind==='global'&&config.binding.source!=='global')continue;
   let value=hmi.read(config.binding,state),reason='';
   if(kind==='job'&&state.status.state!=='completed'&&config.binding.source!=='status'){value=undefined;reason='本轮未成功提交，保留数据缺口';}
   widget.lastAt=time;
   if(config.type==='trend'){
    const valid=typeof value==='number'&&Number.isFinite(value);widget.quality=valid?'good':'invalid';widget.reason=valid?'':reason||'绑定值不是有效数值';
    widget.samples.push({time,value:valid?value:null,quality:widget.quality,reason:widget.reason,jobId});
    if(widget.samples.length>config.capacity)p.discardedSamples+=widget.samples.splice(0,widget.samples.length-config.capacity).length;
   }else{
    let triggered;
    try{
     if(value===undefined)throw Error(reason||'绑定值缺失');
     triggered=control.condition({comparison:config.comparison,left:value,right:config.threshold}).passed;
     if(widget.active&&config.hysteresis>0){
      const threshold=config.threshold+(['lt','lte'].includes(config.comparison)?config.hysteresis:-config.hysteresis);
      triggered=control.condition({comparison:config.comparison,left:value,right:threshold}).passed;
     }
     widget.quality='good';widget.reason='';widget.value=typeof value==='string'?value.slice(0,500):value;
    }catch(error){widget.quality='invalid';widget.reason=String(error.message);widget.pending=0;continue;}
    if(triggered===widget.active){widget.pending=0;continue;}
    if(widget.pendingValue!==triggered){widget.pendingValue=triggered;widget.pending=0;}widget.pending++;
    if(widget.pending<config.stableSamples)continue;widget.pending=0;widget.active=triggered;
    if(triggered){const event={id:crypto.randomUUID(),componentId:config.id,label:config.label,severity:config.severity,startedAt:time,returnedAt:null,acknowledgedAt:null,value:widget.value,...(typeof value==='string'&&value.length>500?{valueTruncated:true}:{})};p.events.unshift(event);widget.activeId=event.id;}
    else{const event=p.events.find(e=>e.id===widget.activeId);if(event)event.returnedAt=time;widget.activeId=null;}
   }
  }
  while(p.events.length>200){let index=p.events.findLastIndex(e=>e.returnedAt);if(index<0)index=p.events.length-1;p.events.splice(index,1);p.discardedEvents++;}
  let total=Object.values(p.widgets).reduce((sum,w)=>sum+(w.samples?.length||0),0);
  while(total>5000){const widget=Object.values(p.widgets).filter(w=>w.samples?.length).sort((a,b)=>a.samples[0].time-b.samples[0].time)[0];widget.samples.shift();total--;p.discardedSamples++;}
  const ids=Object.keys(next.projects).sort((a,b)=>next.projects[a].updatedAt-next.projects[b].updatedAt);
  while(ids.length>20){const index=ids.findIndex(id=>id!==project.id&&!Object.values(next.projects[id].widgets).some(w=>w.active)&&!next.projects[id].events.some(e=>!e.returnedAt));if(index<0)throw Error('监控工程已达 20 个且旧工程仍有活动报警，无法安全淘汰');delete next.projects[ids.splice(index,1)[0]];}
  this.persist(next);
 }
 observeGlobals(global,originId,time=Date.now()){
  for(const [id,p] of Object.entries(this.state.projects)){
   if(id===originId)continue;
   const components=Object.entries(p.widgets).map(([id,w])=>({id,...JSON.parse(w.signature)}));
   if(components.some(c=>c.binding.source==='global'))this.observe({id,hmi:{components}},{variables:{global},status:{state:'completed'},results:[]},{kind:'global',time});
  }
 }
 acknowledge(projectId,id,comment=''){
  if(!validId(projectId)||typeof id!=='string'||! /^[0-9a-f-]{36}$/.test(id)||typeof comment!=='string'||comment.length>200)throw Error('报警确认参数无效');
  const next=structuredClone(this.state),event=next.projects[projectId]?.events.find(e=>e.id===id);if(!event)throw Error('报警记录不存在或已过保留期');
  if(event.acknowledgedAt)return this.view(projectId);
  event.acknowledgedAt=Date.now();event.comment=comment;next.revision++;this.persist(next);return this.view(projectId);
 }
}
module.exports={RuntimeMonitor};
