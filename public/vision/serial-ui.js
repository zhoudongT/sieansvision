'use strict';
const serialLabels={none:'无流控',rtscts:'RTS / CTS 硬件流控',xonxoff:'XON / XOFF 软件流控',dsrdtr:'DSR / DTR 硬件流控',M:'固定 1（Mark）',S:'固定 0（Space）'};
const serialCatalog={serial_exchange:{name:'串口报文通信',tag:'扫码枪 · 测量仪 · 自定义报文',glyph:'⇄',defaults:{connection:'simulator',mode:'exchange',serialPort:'',baudrate:115200,dataBits:8,parity:'N',stopbits:1,flowControl:'none',rts:true,dtr:true,clearInput:false,encoding:'text',responseEncoding:'text',timeoutMs:3000,maxBytes:65536,txFraming:'crlf',rxFraming:'crlf',responseBytes:8,value:'SIEANS-SERIAL-00042'},fields:[['connection','串口连接',['simulator','device']],['mode','通信方式',['exchange','send','receive']],['serialPort','服务器串口路径','text'],['baudrate','波特率',300,4000000],['dataBits','数据位',5,8],['parity','校验位',['N','E','O','M','S']],['stopbits','停止位',1,2,.5],['flowControl','流量控制',['none','rtscts','xonxoff','dsrdtr']],['rts','打开时 RTS 状态','boolean'],['dtr','打开时 DTR 状态','boolean'],['encoding','发送内容格式',['text','structured','bytes']],['responseEncoding','接收内容格式',['text','structured','bytes']],['timeoutMs','通信超时 (ms)',100,10000,100],['maxBytes','接收字节上限',1,65536],['clearInput','发送前丢弃已有接收数据','boolean'],['txFraming','发送分帧方式',['raw','lf','crlf','nul','length16be','length16le','length32be','length32le']],['rxFraming','接收完成条件',['lf','crlf','nul','length16be','length16le','length32be','length32le','fixed']],['responseBytes','应答字节数',1,65536]],description:'通过服务器上的串口与设备收发一帧报文。支持文本、结构化字段和字节表，以及结束符、长度头和定长分帧。回环模拟使用 pySerial 软件回环，不访问真实端口。',hint:'在工业通信面板刷新串口表，可选择到本模块。每次执行打开/关闭端口，与 Modbus RTU 互斥；打开端口可能改变 RTS/DTR。默认不丢弃已有输入。回环模式固定 115200、8N1、无流控，报文含头部最多 4096 字节。仅发送不表示设备已执行；无自动重试。'}};
function isSerialStep(step){return step.operation==='serial_exchange';}
function serialParamDefault(step,key){return isSerialStep(step)?key==='responseEncoding'?(step.params.encoding??'text'):serialCatalog.serial_exchange.defaults[key]:undefined;}
function serialFieldVisible(step,key){
 if(!isSerialStep(step))return true;const p=step.params,mode=p.mode??'exchange';
 if(p.connection==='simulator'&&['serialPort','baudrate','dataBits','parity','stopbits','flowControl','rts','dtr'].includes(key))return false;
 if((key==='rts'&&p.flowControl==='rtscts')||(key==='dtr'&&p.flowControl==='dsrdtr'))return false;
 if(mode==='receive'&&['value','encoding','txFraming','clearInput'].includes(key))return false;
 if(mode==='send'&&['maxBytes','responseEncoding','rxFraming','responseBytes'].includes(key))return false;
 if(key==='responseBytes'&&typeof p.rxFraming!=='object'&&(p.rxFraming??'crlf')!=='fixed')return false;
 return true;
}
