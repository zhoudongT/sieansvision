'use strict';
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),mqtt=require('mqtt');
const transport=require('./mqtt-client.cjs'),simulator=require('./mqtt-simulator.cjs');
const ACTIVE=new Set(['connecting','subscribed','reconnecting','stopping']);
const forbidden=new Set(['__proto__','constructor','prototype']);
function integer(v,min,max,label){if(!Number.isInteger(v)||v<min||v>max)throw Error(label+'范围 '+min+'–'+max);return v;}
function settings(body){
 if(!body.connection||typeof body.connection!=='object'||Array.isArray(body.connection))throw Error('MQTT 连接参数无效');
 const c=transport.config('mqtt_receive',{acceptRetained:false,...body.connection});
 const p=body.connection,publicConnection={connection:c.simulated?'simulator':'broker',topic:c.topic,encoding:c.encoding,qos:c.qos,timeoutMs:c.timeoutMs,clientId:p.clientId||'',acceptRetained:c.acceptRetained};
 if(!c.simulated){Object.assign(publicConnection,{host:c.options.host,port:c.options.port,security:c.options.protocol==='mqtts'?'tls':'plain'});for(const key of ['username','passwordEnv',...(c.options.protocol==='mqtts'?['caFile','clientCertificate','privateKey','keyPasswordEnv']:[])])if(p[key])publicConnection[key]=p[key];}
 const variable=body.variable??'mqttEvent';if(typeof variable!=='string'||!/^[A-Za-z_][A-Za-z0-9_]{0,63}$/.test(variable)||forbidden.has(variable))throw Error('事件变量名称无效');
 const keyField=body.keyField??'';if(typeof keyField!=='string'||keyField.length>200||(keyField&&!keyField.split('.').every(k=>k&&!forbidden.has(k))))throw Error('去重字段路径无效');
 const overflow=body.overflow??'stop';if(!['stop','dropOldest','dropNewest'].includes(overflow))throw Error('队列溢出策略无效');
 return {c,publicConnection,variable,keyField,overflow,capacity:integer(body.capacity??20,1,100,'队列容量'),maxAgeMs:integer(body.maxAgeMs??30000,100,3600000,'消息有效期 (ms)'),reconnectMs:integer(body.reconnectMs??1000,200,60000,'重连间隔 (ms)')};
}
class MqttTrigger{
 constructor(runtime,directory){
  this.runtime=runtime;this.file=path.join(directory,'mqtt-trigger.json');this.owner=Symbol('mqtt-trigger');this.queue=[];this.bytes=0;this.seen=new Map();this.client=null;this.request=null;this.project=null;this.draining=null;this.finishPromise=null;
  this.state={state:'idle',received:0,completed:0,failed:0,dropped:0,expired:0,duplicates:0,invalid:0,reconnects:0,queued:0};
  if(fs.existsSync(this.file)){if(fs.statSync(this.file).size>1024*1024)throw Error('MQTT 触发记录过大');const saved=JSON.parse(fs.readFileSync(this.file,'utf8'));if(saved.version!==1||typeof saved.state!=='string')throw Error('MQTT 触发记录格式无效');this.state=saved;if(ACTIVE.has(saved.state)){this.state.state='interrupted';this.state.endedAt=Date.now();this.state.dropped+=(this.state.queued||0);this.state.queued=0;this.state.error='服务重启中断了事件订阅；未执行消息不重放，请检查设备后重新启动';this.persist();}}
 }
 get busy(){return ACTIVE.has(this.state.state);}
 status(){return {...structuredClone(this.state),busy:this.busy,executing:!!this.runtime.active&&this.runtime.active.id===this.state.lastJobId,hasProject:!!this.project};}
 persist(){fs.mkdirSync(path.dirname(this.file),{recursive:true});fs.writeFileSync(this.file+'.tmp',JSON.stringify({version:1,...this.state}));fs.renameSync(this.file+'.tmp',this.file);}
 record(){try{this.state.queued=this.queue.length;this.persist();}catch(error){this.fail('事件状态保存失败：'+error.message);}}
 start(body){
  if(this.busy||this.runtime.busy)throw Error('运行平台正在执行其他任务，请先停止');
  const cfg=settings(body),prepared=this.runtime.prepare(body);if(!prepared.steps.length)throw Error('事件触发需要完整流程');if(body.target!==undefined)throw Error('事件触发只支持完整流程');
  this.runtime.reserve(this.owner);this.cfg=cfg;this.queue=[];this.bytes=0;this.seen.clear();this.ready=false;this.stopping=false;this.finishPromise=null;this.draining=null;
  this.request=structuredClone({project:prepared.project,...prepared.input,allowScripts:body.allowScripts===true});this.project=structuredClone(prepared.project);
  this.state={state:'connecting',id:crypto.randomUUID(),projectId:prepared.project.id,projectName:prepared.project.name,startedAt:Date.now(),endedAt:null,received:0,completed:0,failed:0,dropped:0,expired:0,duplicates:0,invalid:0,reconnects:0,queued:0,lastJobId:null,lastMessage:null,error:'',connectionError:'',config:{connection:cfg.publicConnection,variable:cfg.variable,keyField:cfg.keyField,overflow:cfg.overflow,capacity:cfg.capacity,maxAgeMs:cfg.maxAgeMs,reconnectMs:cfg.reconnectMs}};
  let done;this.transportDone=new Promise(r=>done=r);this.transportFinished=done;
  try{this.releaseTransport=transport.reserve(cfg.c,{cancel:()=>this.stop(this.state.id),done:this.transportDone});this.persist();}
  catch(error){this.releaseTransport?.();this.releaseTransport=null;done();this.state.state='failed';this.runtime.release(this.owner);this.request=null;throw error;}
  this.connecting=this.connect().catch(error=>this.fail(error.message));return this.status();
 }
 async connect(){
  const c=this.cfg.c;if(c.simulated){const endpoint=await simulator.start();Object.assign(c.options,{host:endpoint.host,port:endpoint.port});}if(this.stopping)return;
  this.client=mqtt.connect({...c.options,reconnectPeriod:this.cfg.reconnectMs,reconnectOnConnackError:true,resubscribe:false});
  this.client.on('error',error=>{if(this.stopping)return;this.state.connectionError=String(error.message).slice(0,500);this.record();});
  this.client.on('close',()=>{clearTimeout(this.subscribeTimer);this.subscriptionEpoch=(this.subscriptionEpoch||0)+1;this.ready=false;if(!this.stopping){this.state.state='reconnecting';this.record();}});
  this.client.on('reconnect',()=>{if(!this.stopping){this.state.state='reconnecting';this.state.reconnects++;this.record();}});
  this.client.on('connect',()=>{
   if(this.stopping)return;this.ready=false;const epoch=this.subscriptionEpoch=(this.subscriptionEpoch||0)+1;
   this.subscribeTimer=setTimeout(()=>this.fail('MQTT 订阅应答超时'),c.timeoutMs);
   this.client.subscribe(c.topic,{qos:c.qos},(error,granted)=>{
    if(this.stopping||epoch!==this.subscriptionEpoch||!this.client.connected)return;clearTimeout(this.subscribeTimer);if(error||!granted?.length||granted.some(g=>g.qos===128)){this.fail('MQTT 订阅被拒绝：'+(error?.message||'无授权'));return;}
    this.ready=true;this.state.state='subscribed';this.state.connectionError='';this.record();this.drain();
   });
  });
  this.client.on('message',(topic,payload,packet)=>this.accept(topic,payload,packet));this.client.connect();
 }
 accept(topic,payload,packet){
  if(this.stopping||!this.busy)return;this.state.received++;
  if(packet.retain&&!this.cfg.c.acceptRetained){this.state.dropped++;this.record();return;}
  let message,key,size;try{
   const value=transport.decode(payload,this.cfg.c.encoding);
   message={id:crypto.randomUUID(),topic,value,qos:packet.qos,retained:!!packet.retain,duplicate:!!packet.dup,receivedAt:Date.now(),byteLength:payload.length};
   size=Buffer.byteLength(JSON.stringify(message));if(size>512*1024)throw Error('解码消息超过 512 KiB');
   if(this.cfg.keyField){let v=value;for(const field of this.cfg.keyField.split('.')){if(!v||typeof v!=='object'||!Object.hasOwn(v,field))throw Error('消息缺少去重字段');v=v[field];}if(!['string','number','boolean'].includes(typeof v)||typeof v==='string'&&v.length>200)throw Error('去重字段须为短文本、数值或开关');key=JSON.stringify([topic,v]);if(this.seen.has(key)){this.state.duplicates++;this.record();return;}}
  }catch(error){this.state.invalid++;this.state.connectionError='消息未执行：'+error.message;this.record();return;}
  if(this.queue.length>=this.cfg.capacity||this.bytes+size>4*1024*1024){
   if(this.cfg.overflow==='stop'){this.state.dropped++;this.fail('MQTT 消息队列已满，事件触发已停止；未执行消息不重放');return;}
   if(this.cfg.overflow==='dropNewest'){this.state.dropped++;this.record();return;}
   while(this.queue.length&&(this.queue.length>=this.cfg.capacity||this.bytes+size>4*1024*1024)){const old=this.queue.shift();this.bytes-=old.size;this.state.dropped++;}
  }
  if(key){this.seen.set(key,true);while(this.seen.size>1000)this.seen.delete(this.seen.keys().next().value);}
  this.queue.push({message,size});this.bytes+=size;this.state.lastMessage={id:message.id,topic,receivedAt:message.receivedAt,byteLength:message.byteLength};this.record();this.drain();
 }
 drain(){
  if(this.draining||this.stopping||!this.ready)return;
  const work=async()=>{
   while(this.queue.length&&!this.stopping){
    const entry=this.queue.shift();this.bytes-=entry.size;
    if(Date.now()-entry.message.receivedAt>this.cfg.maxAgeMs){this.state.expired++;this.record();continue;}
    this.record();if(this.stopping)break;
    try{
     const accepted=this.runtime.start(this.request,this.owner,{kind:'mqtt',variable:this.cfg.variable,message:entry.message}),job=this.runtime.jobs.get(accepted.id);this.state.lastJobId=job.id;this.record();await job.promise;
     if(job.state==='completed')this.state.completed++;else if(!this.stopping){this.state.failed++;throw Error(job.error||'事件流程未完成');}
     if(job.archive?.state==='failed'||job.monitorWarning)throw Error(job.archive?.error||job.monitorWarning);
     this.record();
    }catch(error){if(!this.stopping){this.state.failed=Math.max(1,this.state.failed);this.fail(error.message);}break;}
   }
  };
  this.draining=Promise.resolve().then(work).finally(()=>{this.draining=null;if(this.queue.length&&!this.stopping)this.drain();});
 }
 fail(message){if(this.stopping)return;this.finish('failed',message);}
 stop(id){if(id!==this.state.id)throw Error('MQTT 事件会话已变化，请刷新后停止');if(this.busy&&!this.stopping)this.finish('stopped','');return this.status();}
 finish(finalState,error){
  if(this.stopping)return this.finishPromise;this.stopping=true;this.ready=false;clearTimeout(this.subscribeTimer);this.state.state='stopping';this.state.error=String(error||'').slice(0,1000);this.state.dropped+=this.queue.length;this.queue=[];this.bytes=0;this.state.queued=0;
  if(this.runtime.active?.id===this.state.lastJobId)this.runtime.cancel(this.state.lastJobId);
  this.finishPromise=Promise.resolve().then(async()=>{
   await this.connecting;
   const client=this.client;if(client)await new Promise(resolve=>{let complete=false;const done=()=>{if(complete)return;complete=true;clearTimeout(timer);resolve();};const timer=setTimeout(()=>{client.stream?.destroy();done();},1000);try{client.end(true,{},done);}catch{done();}});
   await this.draining;this.client=null;this.request=null;this.releaseTransport?.();this.releaseTransport=null;this.transportFinished?.();this.runtime.release(this.owner);this.state.state=finalState;this.state.endedAt=Date.now();
   try{this.persist();}catch(e){this.state.state='failed';this.state.error='事件状态保存失败：'+e.message;}
  });return this.finishPromise;
 }
 async shutdown(){if(this.busy)this.stop(this.state.id);await this.finishPromise;}
}
module.exports={MqttTrigger,settings};
