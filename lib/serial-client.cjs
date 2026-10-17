'use strict';
const fs=require('node:fs'),path=require('node:path');
const {config:networkConfig}=require('./socket-client.cjs'),{decode}=require('./message-codec.cjs');
function requireThat(ok,message){if(!ok)throw Error(message);}
const serialKeys=['serialPort','baudrate','dataBits','parity','stopbits','flowControl','rts','dtr'];
function activeParams(p,resolve=v=>v){
 const out={},take=key=>{if(Object.hasOwn(p,key))out[key]=p[key];};
 for(const key of ['connection','mode'])if(Object.hasOwn(p,key))out[key]=resolve(p[key]);
 take('timeoutMs');if((out.mode??'exchange')!=='receive'||!Object.hasOwn(p,'responseEncoding'))take('encoding');
 if(out.connection!=='simulator'){
  if(Object.hasOwn(p,'flowControl'))out.flowControl=resolve(p.flowControl);
  for(const key of serialKeys){if(key==='flowControl'||(key==='rts'&&out.flowControl==='rtscts')||(key==='dtr'&&out.flowControl==='dsrdtr'))continue;take(key);}
 }
 if((out.mode??'exchange')!=='receive'){take('value');take('txFraming');take('clearInput');}
 if((out.mode??'exchange')!=='send'){take('responseEncoding');take('maxBytes');if(Object.hasOwn(p,'rxFraming'))out.rxFraming=resolve(p.rxFraming);if(out.rxFraming==='fixed')take('responseBytes');}
 return out;
}
function portKey(port){
 let key=String(port??'');
 if(process.platform==='win32'){key=key.replace(/^\\\\\.\\/,'').toUpperCase();if(/^COM0*[1-9]\d*$/.test(key))key='COM'+Number(key.slice(3));}
 else {try{key=fs.realpathSync(key);}catch{key=path.resolve(key);}}
 return 'serial:'+key;
}
function prepare(params){
 const p=activeParams(params),simulated=p.connection==='simulator';
 requireThat(['device','simulator'].includes(p.connection??'device'),'串口连接方式无效');
 requireThat(!simulated||(p.mode??'exchange')!=='receive','回环模拟需要先发送，请选择请求应答或仅发送');
 requireThat((p.rxFraming??'crlf')!=='eof','串口没有 EOF 报文边界，请设置结束符、长度头或固定字节数');
 const c=networkConfig('tcp_exchange',{...p,connection:'device',host:'127.0.0.1',port:1});
 requireThat(c.timeoutMs<=10000,'串口超时必须为 100–10000 ms');
 let serialPort=simulated?'loop://':p.serialPort;
 if(!simulated){
  requireThat(typeof serialPort==='string'&&serialPort.length>0&&serialPort.length<=1024&&!/[\x00-\x1f\x7f]/.test(serialPort),'串口路径无效');
  if(process.platform==='win32'){serialPort=serialPort.replace(/^\\\\\.\\/,'').toUpperCase();requireThat(/^COM[1-9]\d{0,4}$/.test(serialPort),'Windows 串口请填写 COM 编号，例如 COM3');}
  else requireThat(serialPort.startsWith('/dev/')&&!serialPort.includes('://'),'串口路径须位于 /dev/，例如 /dev/ttyUSB0');
 }
 const settings={baudrate:simulated?115200:p.baudrate??115200,dataBits:simulated?8:p.dataBits??8,parity:simulated?'N':p.parity??'N',stopbits:simulated?1:p.stopbits??1,flowControl:simulated?'none':p.flowControl??'none',rts:simulated?true:p.rts??true,dtr:simulated?true:p.dtr??true};
 requireThat(Number.isInteger(settings.baudrate)&&settings.baudrate>=300&&settings.baudrate<=4000000,'波特率须为 300–4000000 的整数');
 requireThat([5,6,7,8].includes(settings.dataBits),'数据位须为 5、6、7 或 8');requireThat(['N','E','O','M','S'].includes(settings.parity),'校验位无效');requireThat([1,1.5,2].includes(settings.stopbits),'停止位须为 1、1.5 或 2');
 requireThat(['none','rtscts','xonxoff','dsrdtr'].includes(settings.flowControl),'串口流控无效');requireThat(typeof settings.rts==='boolean'&&typeof settings.dtr==='boolean','RTS/DTR 须为开关值');
 const responseEncoding=c.receive?(p.responseEncoding??c.encoding):c.encoding;requireThat(['text','structured','bytes'].includes(responseEncoding),'接收内容格式无效');
 const clearInput=c.send?(p.clearInput??false):false;requireThat(typeof clearInput==='boolean','清空接收缓冲须为开关值');
 if(c.send){requireThat(c.wire.every(n=>n<2**settings.dataBits),'发送报文含超出所选数据位的字节，请使用 8 数据位');if(simulated)requireThat(c.wire.length<=4096,'回环模拟报文含头部最多 4096 字节，真实端口支持 64 KiB 内容');}
 return {serialPort,simulated,mode:c.mode,encoding:c.encoding,responseEncoding,timeoutMs:c.timeoutMs,maxBytes:c.maxBytes,txFraming:c.txFraming,rxFraming:c.rxFraming,responseBytes:c.responseBytes,clearInput,...settings,wireBase64:c.send?c.wire.toString('base64'):null,sentValue:c.send?decode(c.payload,c.encoding):undefined};
}
function output(data,prepared){
 const result=data.result;requireThat(result&&typeof result.payloadBase64==='string','串口适配器返回无效数据');
 const payload=Buffer.from(result.payloadBase64,'base64');delete result.payloadBase64;
 result.encoding=prepared.mode==='send'?prepared.encoding:prepared.responseEncoding;result.sentEncoding=prepared.mode!=='receive'?prepared.encoding:null;result.value=prepared.mode==='send'?prepared.sentValue:decode(payload,prepared.responseEncoding);result.byteLength=prepared.mode==='send'?Buffer.byteLength(require('./message-codec.cjs').encode(prepared.sentValue,prepared.encoding)):payload.length;
 return data;
}
module.exports={activeParams,portKey,prepare,output};
