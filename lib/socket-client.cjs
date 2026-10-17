'use strict';
const net=require('node:net'),dgram=require('node:dgram'),dns=require('node:dns/promises');
const codec=require('./message-codec.cjs'),simulator=require('./socket-simulator.cjs');
const active=new Map(),MAX=65536;
const delimiters={lf:Buffer.from([10]),crlf:Buffer.from([13,10]),nul:Buffer.from([0])};
const prefixes={length16be:[2,'readUInt16BE','writeUInt16BE'],length16le:[2,'readUInt16LE','writeUInt16LE'],length32be:[4,'readUInt32BE','writeUInt32BE'],length32le:[4,'readUInt32LE','writeUInt32LE']};
function requireThat(ok,message){if(!ok)throw Error(message);}
function integer(v,min,max,label){requireThat(Number.isInteger(v)&&v>=min&&v<=max,label+'必须为 '+min+'–'+max+' 的整数');return v;}
function choice(v,values,label){requireThat(values.includes(v),label+'无效');return v;}
function host(v){requireThat(typeof v==='string'&&v.length>0&&v.length<=253&&!/[\s\x00-\x1f\x7f/?#@]/.test(v)&&v.isWellFormed(),'远端主机名或 IP 无效');return v;}
// Resolve only settings used by the chosen mode. Hidden bindings left by a mode switch
// must not require a missing variable or accidentally send data in receive-only mode.
function activeParams(operation,p,resolve=v=>v){
 const out={},take=key=>{if(Object.hasOwn(p,key))out[key]=p[key];};
 for(const key of ['connection','mode'])if(Object.hasOwn(p,key))out[key]=resolve(p[key]);
 for(const key of ['encoding','timeoutMs'])take(key);
 const udp=operation==='udp_exchange',mode=out.mode??'exchange';
 if(out.connection!=='simulator'){take('host');take('port');if(udp){take('localPort');take('localAddress');}}
 if(mode!=='receive'){take('value');if(!udp)take('txFraming');}
 if(mode!=='send'){take('maxBytes');if(!udp){if(Object.hasOwn(p,'rxFraming'))out.rxFraming=resolve(p.rxFraming);if(out.rxFraming==='fixed')take('responseBytes');}}
 return out;
}
function config(operation,p){
 requireThat(['tcp_exchange','udp_exchange'].includes(operation),'网络通信操作无效');requireThat(p&&typeof p==='object'&&!Array.isArray(p),'网络通信参数无效');
 p=activeParams(operation,p);
 const c={udp:operation==='udp_exchange',mode:choice(p.mode??'exchange',['exchange','send','receive'],'通信方式'),simulated:choice(p.connection??'device',['simulator','device'],'连接方式')==='simulator',encoding:choice(p.encoding??'text',['text','structured','bytes'],'消息格式'),timeoutMs:integer(p.timeoutMs??3000,100,60000,'总超时'),maxBytes:integer(p.maxBytes??65536,1,MAX,'接收字节上限')};
 c.send=c.mode!=='receive';c.receive=c.mode!=='send';
 if(c.simulated)requireThat(c.mode!=='receive','回显模拟器需要先发送，请选择请求应答或仅发送');
 else {c.host=host(p.host??'127.0.0.1');c.port=integer(p.port??9000,1,65535,'远端端口');}
 c.localPort=c.udp&&!c.simulated?integer(p.localPort??0,c.mode==='receive'?1:0,65535,'本地 UDP 端口'):0;
 c.localAddress=c.udp&&!c.simulated?(p.localAddress??''):'';
 requireThat(typeof c.localAddress==='string'&&(!c.localAddress||net.isIP(c.localAddress)),'本地地址必须是 IP 或留空');
 if(c.send){c.payload=codec.encode(Object.hasOwn(p,'value')?p.value:'',c.encoding);requireThat(c.payload.length<=(c.udp?65507:MAX),c.udp?'UDP 报文超过 65507 字节':'发送数据超过 64 KiB');}
 if(!c.udp){
  c.txFraming=c.send?choice(p.txFraming??'crlf',['raw',...Object.keys(delimiters),...Object.keys(prefixes)],'发送分帧方式'):'raw';
  c.rxFraming=c.receive?choice(p.rxFraming??'crlf',[...Object.keys(delimiters),...Object.keys(prefixes),'fixed','eof'],'接收分帧方式'):'eof';
  if(c.rxFraming==='fixed')c.responseBytes=integer(p.responseBytes??1,1,c.maxBytes,'定长报文字节数');
  if(c.send)c.wire=framePayload(c.payload,c.txFraming);
 }
 return c;
}
function framePayload(payload,framing){
 if(delimiters[framing]){requireThat(payload.indexOf(delimiters[framing])===-1,'发送内容包含所选结束符，请改用长度前缀或字节协议');return Buffer.concat([payload,delimiters[framing]]);}
 if(prefixes[framing]){const [length,,write]=prefixes[framing];requireThat(length!==2||payload.length<=65535,'两字节长度前缀最大支持 65535 字节');const header=Buffer.alloc(length);header[write](payload.length);return Buffer.concat([header,payload]);}
 return payload;
}
// Accumulate bytes, not decoded text: delimiters, headers and UTF-8 characters may span chunks.
function parser(c){
 let buffer=Buffer.alloc(0),done=false;
 return (chunk,ended=false)=>{
  if(done)throw Error('报文已经结束');buffer=Buffer.concat([buffer,chunk]);
  let offset=0,length=null,wireLength=null;
  if(delimiters[c.rxFraming]){const delimiter=delimiters[c.rxFraming],at=buffer.indexOf(delimiter);if(at>=0){length=at;wireLength=at+delimiter.length;}else requireThat(buffer.length<=c.maxBytes+delimiter.length-1,'接收数据超过字节上限');}
  else if(prefixes[c.rxFraming]){const [size,read]=prefixes[c.rxFraming];if(buffer.length>=size){offset=size;length=buffer[read]();requireThat(length<=c.maxBytes,'长度前缀超过接收字节上限');wireLength=size+length;}}
  else if(c.rxFraming==='fixed'){length=c.responseBytes;wireLength=length;}
  else {requireThat(buffer.length<=c.maxBytes,'接收数据超过字节上限');if(ended){length=buffer.length;wireLength=length;}}
  if(length!==null)requireThat(length<=c.maxBytes,'接收数据超过字节上限');
  if(wireLength!==null&&buffer.length>=wireLength){done=true;return {payload:buffer.subarray(offset,offset+length),trailingBytes:buffer.length-wireLength};}
  requireThat(!ended,'对端关闭连接，但未收到完整报文');return null;
 };
}
async function run(request,{signal}={}){
 const started=Date.now();if(signal?.aborted)throw Error('网络通信已取消');const c=config(request.operation,request.params);
 const key=(c.udp?'udp:':'tcp:')+(c.simulated?'simulator':c.host.toLowerCase()+':'+c.port)+(c.udp?':'+c.localAddress+':'+c.localPort:'');
 requireThat(!active.has(key),'此网络通信端点正在使用，请串联执行');requireThat(active.size<8,'网络通信并发任务已达上限 8');
 const controller=new AbortController(),abort=()=>controller.abort();signal?.addEventListener('abort',abort,{once:true});
 let done;active.set(key,{abort,done:new Promise(r=>done=r)});
 let socket,sent=false,timer,cancel,settled=false;
 try{
  return await new Promise((resolve,reject)=>{
   const finish=(error,result)=>{
    if(settled)return;settled=true;clearTimeout(timer);controller.signal.removeEventListener('abort',cancel);
    const complete=()=>error?reject(Error(error.message+(sent?'；数据可能已经发出，不能回滚，未自动重试':''))):resolve({result,elapsedMs:Date.now()-started});
    if(socket){if(c.udp){try{socket.close(complete);}catch{complete();}}else if(socket.destroyed)complete();else {socket.once('close',complete);socket.destroy();}}else complete();
   };
   cancel=()=>finish(Error('网络通信已取消'));controller.signal.addEventListener('abort',cancel,{once:true});timer=setTimeout(()=>finish(Error('网络通信总超时')),c.timeoutMs);
   const result=(payload,trailingBytes=0)=>{
    try{const value=codec.decode(payload,c.encoding);finish(null,{protocol:c.udp?'UDP':'TCP',mode:c.mode,encoding:c.encoding,host:c.host,port:c.port,localPort:c.udp?socket.address().port:socket.localPort,simulated:c.simulated,delivery:c.receive?'received':'sent',acknowledged:false,value,byteLength:payload.length,sentBytes:c.send?(c.udp?c.payload.length:c.wire.length):0,trailingBytes,timestamp:new Date().toISOString()});}catch(error){finish(error);}
   };
   (async()=>{
    if(c.simulated){const endpoint=await simulator.start();c.host=endpoint.host;c.port=c.udp?endpoint.udpPort:endpoint.tcpPort;}
    if(settled)return;
    const peer=await dns.lookup(c.host);if(settled)return;
    if(c.localAddress)requireThat(net.isIP(c.localAddress)===peer.family,'本地与远端 IP 地址族不一致');
    if(c.udp){
     socket=dgram.createSocket(peer.family===6?'udp6':'udp4');socket.on('error',error=>finish(Error('UDP 通信失败：'+error.message)));
     socket.on('message',(payload,info)=>{if(settled||!c.receive||info.address!==peer.address||info.port!==c.port)return;if(payload.length>c.maxBytes)return finish(Error('UDP 报文超过接收字节上限'));result(payload);});
     socket.bind(c.localPort,c.localAddress||undefined,()=>{
      if(settled)return;
      socket.connect(c.port,peer.address,error=>{if(settled)return;if(error)return finish(error);if(!c.send)return;try{sent=true;socket.send(c.payload,error=>{if(settled)return;if(error)finish(error);else if(!c.receive)result(c.payload);});}catch(error){finish(error);}});
     });
    }else {
     const consume=parser(c);socket=new net.Socket();socket.setNoDelay(true);
     socket.on('error',error=>finish(Error('TCP 通信失败：'+error.message)));
     socket.on('close',()=>{if(!settled)finish(Error('TCP 连接在报文完成前关闭'));});
     const receive=(chunk,end)=>{if(settled||!c.receive)return;try{const frame=consume(chunk,end);if(frame)result(frame.payload,frame.trailingBytes);}catch(error){finish(error);}};
     socket.on('data',chunk=>receive(chunk,false));socket.on('end',()=>receive(Buffer.alloc(0),true));
     socket.connect({host:peer.address,port:c.port},()=>{
      if(settled||!c.send)return;sent=true;
      const written=error=>{if(settled)return;if(error)finish(error);else if(!c.receive)result(c.payload);};
      if(c.rxFraming==='eof')socket.end(c.wire,written);else socket.write(c.wire,written);
     });
    }
   })().catch(finish);
   if(controller.signal.aborted)cancel();
  });
 }finally{signal?.removeEventListener('abort',abort);active.delete(key);done();}
}
async function stop(){const tasks=[...active.values()];tasks.forEach(t=>t.abort());await Promise.allSettled(tasks.map(t=>t.done));await simulator.stop();}
module.exports={config,activeParams,framePayload,parser,run,stop,activeCount:()=>active.size};
