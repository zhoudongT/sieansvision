'use strict';
const mqtt=require('mqtt'),fs=require('node:fs'),crypto=require('node:crypto');
const simulator=require('./mqtt-simulator.cjs');
const active=new Map();
function reserve(c,task){
 requireThat(active.size<8,'MQTT 并发任务已达上限 8');
 const key=(c.simulated?'simulator':c.options.protocol+':'+c.options.host.toLowerCase()+':'+c.options.port)+'|'+c.clientId;
 requireThat(!active.has(key),'此 MQTT 客户端标识正在使用，请使用不同标识或串联执行');active.set(key,task);
 return ()=>{if(active.get(key)===task)active.delete(key);};
}
function requireThat(ok,message){if(!ok)throw Error(message);}
function text(value,label,max=1024,empty=false){requireThat(typeof value==='string'&&(empty||value.length>0)&&Buffer.byteLength(value)<=max&&!/[\u0000-\u001f\u007f]/.test(value)&&value.isWellFormed(),label+'无效');return value;}
function integer(value,min,max,label){requireThat(Number.isInteger(value)&&value>=min&&value<=max,label+'必须为 '+min+'–'+max+' 的整数');return value;}
function boolean(value,label){requireThat(typeof value==='boolean',label+'必须为开关值');return value;}
function topic(value,receive){text(value,'MQTT 主题',1024);const levels=value.split('/');requireThat(levels.length<=64,'主题层级最多 64 层');
 requireThat(!value.startsWith('$share/'),'当前不支持共享订阅');
 if(!receive)requireThat(!/[+#]/.test(value),'发布主题不能包含通配符');
 else levels.forEach((part,index)=>requireThat((!part.includes('+')||part==='+')&&(!part.includes('#')||(part==='#'&&index===levels.length-1)),'订阅通配符 + 必须独占层级，# 必须位于最后一层'));
 return value;
}
const {encode,decode}=require('./message-codec.cjs');
function secret(name,label){if(!name)return undefined;text(name,label,128);requireThat(/^[A-Za-z_][A-Za-z0-9_]*$/.test(name),label+'名称无效');requireThat(process.env[name]!==undefined,label+'未设置');return process.env[name];}
function certificate(file,label){text(file,label,2048);try{const stat=fs.statSync(file);requireThat(stat.isFile()&&stat.size<=1024*1024,label+'须为不超过 1 MiB 的文件');return fs.readFileSync(file);}catch{throw Error(label+'无法读取，请检查服务器文件路径');}}
function config(operation,p){
 requireThat(['mqtt_publish','mqtt_receive'].includes(operation),'MQTT 操作无效');requireThat(p&&typeof p==='object'&&!Array.isArray(p),'MQTT 参数无效');
 const receive=operation==='mqtt_receive',connection=p.connection??'broker',encoding=p.encoding??'text',security=p.security??'plain';
 requireThat(['simulator','broker'].includes(connection),'MQTT 连接方式无效');requireThat(['text','structured','bytes'].includes(encoding),'MQTT 消息格式无效');requireThat(['plain','tls'].includes(security),'MQTT 安全模式无效');
 const c={receive,simulated:connection==='simulator',encoding,topic:topic(p.topic??'sieans/inspection',receive),qos:integer(p.qos??1,0,2,'QoS'),timeoutMs:integer(p.timeoutMs??5000,100,60000,'MQTT 超时'),retain:boolean(p.retain??false,'保留消息'),acceptRetained:boolean(p.acceptRetained??true,'接收保留消息')};
 c.clientId=p.clientId?text(p.clientId,'客户端标识',128):'sv-'+crypto.randomBytes(10).toString('hex');
 if(!receive)c.payload=encode(Object.hasOwn(p,'value')?p.value:'',encoding);
 c.options={protocolVersion:4,clientId:c.clientId,clean:true,protocol:'mqtt',reconnectPeriod:0,reconnectOnConnackError:false,resubscribe:false,queueQoSZero:false,connectTimeout:c.timeoutMs,keepalive:15,manualConnect:true};
 if(!c.simulated){
  c.options.host=text(p.host??'127.0.0.1','服务器主机名',253);requireThat(!/[\s/?#@]/.test(c.options.host),'服务器主机名不能包含 URL 或空白');c.options.port=integer(p.port??(security==='tls'?8883:1883),1,65535,'MQTT 端口');
  if(p.username)c.options.username=text(p.username,'用户名',256);const password=secret(p.passwordEnv,'MQTT 密码环境变量');if(password!==undefined){requireThat(!!c.options.username,'设置密码时必须填写用户名');c.options.password=password;}
  if(security==='tls'){
   c.options.protocol='mqtts';c.options.rejectUnauthorized=true;
   if(p.caFile)c.options.ca=certificate(p.caFile,'CA 证书');
   requireThat(!!p.clientCertificate===!!p.privateKey,'客户端证书和私钥必须成对设置');
   if(p.clientCertificate){c.options.cert=certificate(p.clientCertificate,'客户端证书');c.options.key=certificate(p.privateKey,'客户端私钥');const passphrase=secret(p.keyPasswordEnv,'私钥密码环境变量');if(passphrase!==undefined)c.options.passphrase=passphrase;}
  }
 }
 return c;
}
async function run(request,{signal}={}){
 const started=Date.now();if(signal?.aborted)throw Error('MQTT 已取消');const c=config(request.operation,request.params);
 requireThat(active.size<8,'MQTT 并发任务已达上限 8');
 // Reserve before starting the asynchronous simulator, so pending starts count toward the limit.
 const key=(c.simulated?'simulator':c.options.protocol+':'+c.options.host.toLowerCase()+':'+c.options.port)+'|'+c.clientId;
 requireThat(!active.has(key),'此 MQTT 客户端标识正在使用，请使用不同标识或串联执行');
 const controller=new AbortController(),cancel=()=>controller.abort();signal?.addEventListener('abort',cancel,{once:true});
 let finishTask;const task={cancel,done:new Promise(r=>finishTask=r)};active.set(key,task);
 try{
  if(c.simulated){const endpoint=await simulator.start();Object.assign(c.options,{host:endpoint.host,port:endpoint.port});}
  if(controller.signal.aborted)throw Error('MQTT 已取消');
  const remaining=c.timeoutMs-(Date.now()-started);requireThat(remaining>0,'MQTT 操作超时');c.options.connectTimeout=remaining;
  return await new Promise((resolve,reject)=>{
   let client,settled=false,sent=false,timer,received=null,subscribed=false;
   const finish=(error,result)=>{
    if(settled)return;settled=true;clearTimeout(timer);controller.signal.removeEventListener('abort',onAbort);
    let completed=false,cleanupTimer;
    const complete=()=>{if(completed)return;completed=true;clearTimeout(cleanupTimer);if(error)reject(Error(error.message+(sent?'；消息可能已被服务器接收，不能回滚，未自动重试':'')));else resolve({result,elapsedMs:Date.now()-started});};
    if(client){try{cleanupTimer=setTimeout(()=>{if(client.stream&&!client.stream.destroyed){client.stream.once('close',complete);client.stream.destroy();}else complete();},500);client.end(!!error,{},complete);}catch{complete();}}else complete();
   };
   const onAbort=()=>finish(Error('MQTT 已取消'));
   const base=()=>({protocol:'MQTT 3.1.1',action:c.receive?'receive':'publish',topic:c.topic,encoding:c.encoding,qos:c.qos,clientId:c.clientId,simulated:c.simulated,timestamp:new Date().toISOString()});
   const accept=()=>{if(!received||!subscribed||settled)return;const {name,payload,packet}=received;try{const value=decode(payload,c.encoding);finish(null,{...base(),topic:name,qos:packet.qos,retained:!!packet.retain,duplicate:!!packet.dup,value,byteLength:payload.length,delivery:'received'});}catch(error){finish(error);}};
   controller.signal.addEventListener('abort',onAbort,{once:true});timer=setTimeout(()=>finish(Error('MQTT 操作超时')),remaining);
   try{
    client=mqtt.connect(c.options);
    client.on('error',error=>finish(Error('MQTT 连接或通信失败：'+error.message)));
    client.on('close',()=>{if(!settled)finish(Error('MQTT 连接在操作完成前关闭'));});
    client.on('message',(name,payload,packet)=>{if(settled||!c.receive||(!c.acceptRetained&&packet.retain)||received)return;received={name,payload,packet};setImmediate(accept);});
    client.on('connect',()=>{
     if(settled)return;
     if(c.receive)client.subscribe(c.topic,{qos:c.qos},(error,granted)=>{if(error)return finish(error);if(!granted?.length||granted[0].qos===128)return finish(Error('MQTT 服务器拒绝订阅'));subscribed=true;accept();});
     else {sent=true;client.publish(c.topic,c.payload,{qos:c.qos,retain:c.retain},error=>{if(error)return finish(error);finish(null,{...base(),byteLength:c.payload.length,retained:c.retain,acknowledged:c.qos>0,delivery:c.qos>0?'broker_acknowledged':'sent',value:decode(c.payload,c.encoding)});});}
    });
    client.connect();if(controller.signal.aborted)onAbort();
   }catch(error){finish(error);}
  });
 }finally{signal?.removeEventListener('abort',cancel);active.delete(key);finishTask();}
}
async function stop(){const tasks=[...active.values()];tasks.forEach(t=>t.cancel());await Promise.allSettled(tasks.map(t=>t.done));await simulator.stop();}
module.exports={run,stop,config,encode,decode,reserve,activeCount:()=>active.size};
