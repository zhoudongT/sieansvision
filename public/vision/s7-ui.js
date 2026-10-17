'use strict';
const s7Defaults={connection:'simulator',host:'127.0.0.1',port:102,rack:0,slot:1,area:'db',dbNumber:1,byteOffset:0,bitOffset:0,dataType:'uint16',timeoutMs:3000};
const s7Fields=[['connection','连接方式',['simulator','plc']],['host','设备 IP / 主机名','text'],['port','TCP 端口',1,65535],['rack','机架号',0,7],['slot','槽号',0,31],['area','数据区域',['db','mk','pe','pa']],['dbNumber','数据块编号',1,65535],['byteOffset','字节偏移（从 0 开始）',0,2097151],['dataType','数据类型',['bool','uint8','int8','uint16','int16','uint32','int32','float32','float64']],['bitOffset','位偏移',0,7],['timeoutMs','事务超时 (ms)',100,10000,100]];
const s7Catalog={
 s7_read:{name:'S7 读取',tag:'西门子 · DB / M / I / Q',glyph:'S7',defaults:{...s7Defaults,count:1},fields:[...s7Fields,['count','读取值数量',1,200]],description:'通过经典 S7 协议读取 PLC 或本机模拟设备。数值采用西门子大端布局；BOOL 访问单个位。',hint:'单次最多 200 字节。DB1.DBW10：DB 编号 1、字节偏移 10、类型 uint16。1200/1500 需具备 PUT/GET 访问和非优化数据块；不自动改变 PLC 配置。'},
 s7_write:{name:'S7 写入',tag:'西门子 · 检测结果输出',glyph:'S7',defaults:{...s7Defaults,byteOffset:10,value:0},fields:s7Fields,description:'向 DB、M 或 Q 写入数值、数组或单个位。输入区 I 只读；BOOL 直接使用位写入，不覆盖相邻位。',hint:'写入不自动重试。应答丢失时状态可能未知，需读回确认；流程失败不会回滚设备写入。单次最多 200 字节；BOOL 值选择开关类型。'}
};
function s7ParamDefault(step,key){return step.operation.startsWith('s7_')?(key==='connection'?'plc':s7Catalog[step.operation]?.defaults[key]):undefined;}
function s7FieldVisible(step,key){
 if(!step.operation.startsWith('s7_'))return true;
 if(['host','port','rack','slot'].includes(key))return step.params.connection!=='simulator';
 if(key==='dbNumber')return typeof step.params.area==='object'||(step.params.area||'db')==='db';
 if(key==='bitOffset')return typeof step.params.dataType==='object'||step.params.dataType==='bool';
 if(key==='count')return step.params.dataType!=='bool';
 return true;
}
function showS7Simulator(value){if(value.unavailable){$('s7-simulator-status').textContent='S7 服务暂不可用；新安装模块需要重启服务器。';$('s7-simulator-start').disabled=true;$('s7-simulator-stop').disabled=true;return;}$('s7-simulator-status').textContent=value.running?`本机 S7 模拟设备运行中 · ${value.host}:${value.port}`:'本机 S7 模拟设备未启动';$('s7-simulator-start').disabled=value.running;$('s7-simulator-stop').disabled=!value.running||running;}
function initS7UI(){
 $('s7-simulator-start').onclick=safe(async()=>{if(running)return;showS7Simulator(await api('industrial/s7/simulator/start',{method:'POST'}));});
 $('s7-simulator-stop').onclick=safe(async()=>{if(running)return;showS7Simulator(await api('industrial/s7/simulator/stop',{method:'POST'}));});
}
