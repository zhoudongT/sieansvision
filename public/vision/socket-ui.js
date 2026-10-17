'use strict';
const socketLabels={device:'外部网络设备',exchange:'发送并等待应答',send:'仅发送',receive:'仅接收',raw:'原始字节',lf:'换行 LF',crlf:'回车换行 CRLF',nul:'零字节结束',length16be:'2 字节长度 · 大端',length16le:'2 字节长度 · 小端',length32be:'4 字节长度 · 大端',length32le:'4 字节长度 · 小端',fixed:'固定字节数',eof:'对端结束发送'};
const socketFields=[['connection','通信设备',['simulator','device']],['mode','通信方式',['exchange','send','receive']],['host','远端 IP / 主机名','text'],['port','远端端口',1,65535],['encoding','消息内容格式',['text','structured','bytes']],['timeoutMs','操作总超时 (ms)',100,60000,100],['maxBytes','接收字节上限',1,65536]];
const socketDefaults={connection:'simulator',mode:'exchange',host:'127.0.0.1',port:9000,encoding:'text',timeoutMs:3000,maxBytes:65536,value:'SIEANS 检测完成'};
const socketCatalog={
 tcp_exchange:{name:'TCP 报文通信',tag:'请求应答 · 报文分帧',glyph:'⇄',defaults:{...socketDefaults,txFraming:'crlf',rxFraming:'crlf',responseBytes:8},fields:[...socketFields,['txFraming','发送分帧方式',['raw','lf','crlf','nul','length16be','length16le','length32be','length32le']],['rxFraming','接收完成条件',['lf','crlf','nul','length16be','length16le','length32be','length32le','fixed','eof']],['responseBytes','应答字节数',1,65536]],description:'连接设备 TCP 服务，发送报文或等待一帧数据。自动拼接分段到达的数据，按所选规则识别完整报文。',hint:'每次执行创建并关闭连接；仅接收仍主动连接远端服务。长度前缀不计自身，结果移除前缀/结束符；定长按字节数。仅返回首帧，已收到的尾随字节计数显示在结果中。无自动重试，发送完成不代表设备已执行。'},
 udp_exchange:{name:'UDP 报文通信',tag:'单个数据报 · 对端筛选',glyph:'⇄',defaults:{...socketDefaults,localAddress:'',localPort:0},fields:[...socketFields,['localAddress','本地 IP（空白自动选择）','text'],['localPort','本地 UDP 端口（0 自动）',0,65535]],description:'发送一个 UDP 数据报，或接收来自指定设备的一条数据报。仅接收模式需要填写本地端口，其他模式可自动分配。',hint:'仅接收所配置远端 IP 和端口的数据；发送上限 65507 字节。UDP 不保证送达、顺序或不重复；请求应答建议在内容中携带事务编号。此节点不自动重试，不支持广播/组播。'}
};
function isSocketStep(step){return !!socketCatalog[step.operation];}
function socketParamDefault(step,key){return isSocketStep(step)?socketCatalog[step.operation].defaults[key]:undefined;}
function socketFieldVisible(step,key){
 if(!isSocketStep(step))return true;const p=step.params,mode=p.mode??'exchange';
 if(['host','port','localAddress','localPort'].includes(key)&&p.connection==='simulator')return false;
 if(['value','txFraming'].includes(key)&&mode==='receive')return false;
 if(['maxBytes','rxFraming','responseBytes'].includes(key)&&mode==='send')return false;
 if(key==='responseBytes'&&typeof p.rxFraming!=='object'&&(p.rxFraming??'crlf')!=='fixed')return false;
 return true;
}
function showSocketSimulator(value){
 $('socket-simulator-status').textContent=value.unavailable?'TCP/UDP 服务尚未加载，需要新版服务器。':value.running?`本机回显设备运行中 · TCP ${value.tcpPort} / UDP ${value.udpPort} · 收到 ${value.receivedBytes} 字节`:'本机 TCP/UDP 回显设备未启动';
 $('socket-simulator-start').disabled=!!value.unavailable||value.running;$('socket-simulator-stop').disabled=!!value.unavailable||!value.running||running;
}
function initSocketUI(){
 $('socket-simulator-start').onclick=safe(async()=>showSocketSimulator(await api('industrial/socket/simulator/start',{method:'POST'})));
 $('socket-simulator-stop').onclick=safe(async()=>{if(!running)showSocketSimulator(await api('industrial/socket/simulator/stop',{method:'POST'}));});
}
