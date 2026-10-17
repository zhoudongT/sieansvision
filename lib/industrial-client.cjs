'use strict';
const {spawn}=require('node:child_process');
const fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'..'),active=new Map();
const simulator=require('./modbus-simulator.cjs');
const opcuaSimulator=require('./opcua-simulator.cjs');
const s7Simulator=require('./s7-simulator.cjs');
const mqttClient=require('./mqtt-client.cjs');
const socketClient=require('./socket-client.cjs');
const serialClient=require('./serial-client.cjs');
const operations=new Set(['modbus_read','modbus_write','modbus_wait','opcua_read','opcua_write','opcua_browse','opcua_wait','s7_read','s7_write','mqtt_publish','mqtt_receive','tcp_exchange','udp_exchange','serial_exchange']);
async function run(request,{signal}={}){
 if(!request||(!operations.has(request.operation)&&request.operation!=='serial_ports')||!request.params||typeof request.params!=='object'||Array.isArray(request.params))throw Error('工业通信请求格式无效');
 if(signal?.aborted)throw Error('通信已取消');
 if(['tcp_exchange','udp_exchange'].includes(request.operation))return socketClient.run(request,{signal});
 if(request.operation.startsWith('mqtt_'))return mqttClient.run(request,{signal});
 const serial=request.operation==='serial_exchange';
 const prepared=serial?serialClient.prepare(request.params):null;
 if(serial){const {sentValue,...params}=prepared;request={...request,params};}
 const opcua=request.operation.startsWith('opcua_'),s7=request.operation.startsWith('s7_');
 const simulated=serial?prepared.simulated:opcua||s7?request.params.connection==='simulator':request.params.transport==='simulator';
 if(simulated&&!serial){
  if(opcua){const endpoint=await opcuaSimulator.start();request={...request,params:{...request.params,endpoint:endpoint.endpoint,security:'None',username:'',passwordEnv:'',namespaceUri:request.params.namespaceUri||(/^ns=[1-9][0-9]*;/.test(request.params.nodeId||'')?endpoint.namespaceUri:'')}};}
  else if(s7){const endpoint=await s7Simulator.start();request={...request,params:{...request.params,host:endpoint.host,port:endpoint.port,rack:0,slot:1}};}
  else {const endpoint=await simulator.start();request={...request,params:{...request.params,transport:'tcp',host:endpoint.host,port:endpoint.port,deviceId:1}};}
 }
 const p=request.params,timeout=p.timeoutMs??(opcua||s7?3000:1500);
 const waiting=['modbus_wait','opcua_wait'].includes(request.operation),waitTimeout=p.waitTimeoutMs??10000;
 if(waiting&&(!Number.isInteger(waitTimeout)||waitTimeout<100||waitTimeout>600000))throw Error('等待超时必须为 100–600000 ms');
 if(!Number.isInteger(timeout)||timeout<100||timeout>10000)return Promise.reject(Error('通信超时必须为 100–10000 ms'));
 if(Buffer.byteLength(JSON.stringify(request))>100000)return Promise.reject(Error('工业通信参数超过 100 KB'));
 if(signal?.aborted)return Promise.reject(Error('通信已取消'));
 let opcuaKey='';if(opcua){try{const url=new URL(p.endpoint);opcuaKey=url.hostname.toLowerCase()+':'+url.port;}catch{throw Error('OPC UA 端点地址无效');}}
 const key=opcua?'opcua:'+opcuaKey:s7?'s7:'+String(p.host||'127.0.0.1').toLowerCase()+':'+(p.port??102):(serial||p.transport==='rtu')?serialClient.portKey(p.serialPort):'tcp:'+String(p.host||'127.0.0.1').toLowerCase()+':'+(p.port??502);
 if(active.has(key))return Promise.reject(Error('此通信端点正在使用，请串联操作后重试'));
 if(active.size>=8)return Promise.reject(Error('工业通信并发任务已达上限 8'));
 const local=path.join(root,'.venv',process.platform==='win32'?'Scripts/python.exe':'bin/python');
 const python=process.env.VISION_PYTHON||(fs.existsSync(local)?local:'python3');
 return new Promise((resolve,reject)=>{
  const child=spawn(python,['-X','utf8','-u',path.join(root,'industrial/worker.py')],{cwd:root,windowsHide:true});
  active.set(key,child);let output='',bytes=0,errors='',settled=false;
  const caution=(request.operation.endsWith('_write')||(serial&&prepared.mode!=='receive'))?'；外部写入状态可能未知，不能回滚，未自动重试':'';
  const finish=(error,data)=>{if(settled)return;settled=true;clearTimeout(timer);signal?.removeEventListener('abort',cancel);if(error){child.kill();reject(error);}else resolve(data);};
  const cancel=()=>finish(Error('通信已取消'+caution));
  const timer=setTimeout(()=>finish(Error('工业通信进程超时'+caution)),waiting?waitTimeout+timeout*2+2500:serial?timeout+1500:s7?timeout+1000:timeout*2+2500);
  signal?.addEventListener('abort',cancel,{once:true});
  child.stdout.on('data',data=>{bytes+=data.length;if(bytes>1_000_000)return finish(Error('通信输出超过 1 MB'));output+=data.toString('utf8');});
  child.stderr.on('data',data=>{errors=(errors+data.toString('utf8')).slice(-2000);});
  child.on('error',error=>finish(Error('通信进程启动失败：'+error.message)));
  child.stdin.on('error',error=>finish(error));
  child.on('close',code=>{
    if(active.get(key)===child)active.delete(key);
    if(settled)return;
    try{if(code!==0)throw Error('通信进程异常退出：'+errors+caution);const response=JSON.parse(output);if(!response.ok)throw Error(response.error);if(response.data.result)response.data.result.simulated=simulated;finish(null,serial?serialClient.output(response.data,prepared):response.data);}catch(error){finish(error);}
  });
  child.stdin.end(JSON.stringify(request));
 });
}
async function stop(){for(const child of active.values())child.kill();await simulator.stop();await opcuaSimulator.stop();await s7Simulator.stop();await mqttClient.stop();await socketClient.stop();}
module.exports={run,stop,operations,activeCount:()=>active.size};
