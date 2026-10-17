'use strict';
const modbusFields=[['transport','连接方式',['simulator','tcp','rtu']],['host','设备 IP / 主机名','text'],['port','TCP 端口',1,65535],['serialPort','串口路径','text'],['baudrate','波特率',300,4000000],['parity','校验位',['N','E','O']],['stopbits','停止位',1,2],['deviceId','设备站号',0,255],['area','数据区域',['holding','input','coils','discrete']],['address','起始地址（从 0 开始）',0,65535],['dataType','数据类型',['uint16','int16','uint32','int32','float32','float64']],['byteOrder','字节序',['big','little']],['wordOrder','字序',['big','little']],['timeoutMs','超时 (ms)',100,10000,100]];
const industrialCatalog={
 modbus_wait:{name:'等待 PLC 信号',tag:'Modbus · 条件 / 边沿触发',glyph:'↯',defaults:{transport:'simulator',area:'holding',address:0,dataType:'uint16',byteOrder:'big',wordOrder:'big',timeoutMs:1500,deviceId:1,host:'127.0.0.1',port:502,serialPort:'',baudrate:19200,parity:'N',stopbits:1,comparison:'eq',expectedValue:123,triggerMode:'level',pollIntervalMs:100,stableMs:0,waitTimeoutMs:10000,onTimeout:'error'},description:'使用一个连接轮询单个 PLC 值，满足条件后执行下游。边沿模式每次启动重新建立基线；等待中可停止。',fields:[...modbusFields,['comparison','信号条件',['eq','ne','gt','gte','lt','lte','is_true','is_false']],['expectedValue','比较值',-1e15,1e15,.01],['triggerMode','触发方式',['level','rising','falling']],['pollIntervalMs','采样间隔 (ms)',20,10000],['stableMs','连续采样稳定时间 (ms)',0,60000],['waitTimeoutMs','等待超时 (ms)',100,600000],['onTimeout','超时处理',['error','continue']]],hint:'轮询可能漏掉两次采样之间的短脉冲。稳定时间只验证连续采样结果。超时继续时，应使用条件节点检查 triggered 再决定是否检测；通信错误始终停止。读取后间隔指定时间再采样；超时含连接与读取，正在进行的通信结束后返回，不接受超时后信号。'},
 modbus_read:{name:'Modbus 读取',tag:'TCP / RTU · 寄存器 / 线圈',glyph:'R',defaults:{transport:'simulator',area:'holding',address:0,count:1,dataType:'uint16',byteOrder:'big',wordOrder:'big',timeoutMs:1500,deviceId:1,host:'127.0.0.1',port:502,serialPort:'',baudrate:19200,parity:'N',stopbits:1},description:'读取真实 Modbus TCP/RTU 设备，或本机模拟设备。count 是数据值个数，32 位/64 位占多个寄存器。',fields:[...modbusFields,['count','读取值数量',1,2000]],hint:'使用协议零起始地址，不能把手册 40001 直接当地址 0。原始寄存器在 registers；解码结果在 values / value，可绑定三级变量。当前每次操作建立并关闭连接。'},
 modbus_write:{name:'Modbus 写入',tag:'TCP / RTU · 检测结果输出',glyph:'W',defaults:{transport:'simulator',area:'holding',address:10,dataType:'uint16',byteOrder:'big',wordOrder:'big',value:0,timeoutMs:1500,deviceId:1,host:'127.0.0.1',port:502,serialPort:'',baudrate:19200,parity:'N',stopbits:1},description:'写入线圈或保持寄存器。可输入数值/数组，或绑定检测结果与变量。外部设备写入不随流程失败回滚。',fields:modbusFields,hint:'不自动重试写入。通信中断时设备可能已收到请求，应读取状态确认；设备应答仅表示协议确认，不代表物理动作已完成。线圈使用 true / false。'}
};
function industrialParamDefault(step,key){return step.operation.startsWith('modbus_')?(key==='transport'?'tcp':industrialCatalog[step.operation].defaults[key]):undefined;}
function industrialFieldVisible(step,key){
 if(!step.operation.startsWith('modbus_'))return true;
 const transport=step.params.transport||'tcp',bits=['coils','discrete'].includes(step.params.area);
 if(step.operation==='modbus_wait'&&key==='expectedValue')return typeof step.params.comparison==='object'||!['is_true','is_false'].includes(step.params.comparison);
 if(typeof transport==='object')return true;
 if(['host','port'].includes(key))return transport==='tcp';
 if(['serialPort','baudrate','parity','stopbits'].includes(key))return transport==='rtu';
 if(key==='deviceId'&&transport==='simulator')return false;
 if(['dataType','byteOrder','wordOrder'].includes(key)&&bits)return false;
 return true;
}
function industrialFields() {}
function showSimulator(value){
 $('simulator-status').textContent=value.running?`本机模拟设备运行中 · ${value.host}:${value.port} · 站号 1`:'本机模拟设备未启动';
 $('simulator-start').disabled=value.running;$('simulator-stop').disabled=!value.running||running;
}
async function readSerialPorts(){
 const result=await api('industrial/ports');const list=$('serial-ports');list.replaceChildren();
 if(!result.ports.length){list.textContent='服务器未发现串口设备；可使用软件回环演示。';return;}
 const table=formEl('table',undefined,'form-table'),head=formEl('tr');for(const title of ['串口','描述','硬件标识','操作'])head.append(formEl('th',title));table.append(head);
 for(const port of result.ports){const row=formEl('tr');for(const value of [port.device,port.description,port.hwid])row.append(formEl('td',value));const cell=formEl('td'),select=formEl('button','用于所选模块');const step=selectedStep();select.disabled=running||!step||!['serial_exchange','modbus_read','modbus_write','modbus_wait'].includes(step.operation);select.onclick=()=>{const target=selectedStep();if(running||!target)return;target.params.serialPort=port.device;if(isSerialStep(target))target.params.connection='device';else if(target.operation.startsWith('modbus_'))target.params.transport='rtu';else return;dirty();renderParams();$('communications-dialog').close();status('已选择 '+port.device+'，请核对波特率及串口格式');};cell.append(select);row.append(cell);table.append(row);}list.append(table);
}
function initIndustrialUI(){
 $('communications-open').onclick=safe(async()=>{showSimulator(await api('industrial/simulator'));showS7Simulator(await api('industrial/s7/simulator').catch(()=>({unavailable:true})));showOpcuaSimulator(await api('industrial/opcua/simulator'));showMqttSimulator(await api('industrial/mqtt/simulator').catch(()=>({unavailable:true})));showSocketSimulator(await api('industrial/socket/simulator').catch(()=>({unavailable:true})));$('communications-dialog').showModal();});
 $('simulator-start').onclick=safe(async()=>{if(running)return;showSimulator(await api('industrial/simulator/start',{method:'POST'}));status('Modbus 模拟设备已启动，仅监听服务器本机','success');});
 $('simulator-stop').onclick=safe(async()=>{if(running)return;showSimulator(await api('industrial/simulator/stop',{method:'POST'}));status('模拟设备已停止；下次启动恢复初始寄存器');});
 $('serial-refresh').onclick=safe(readSerialPorts);
}
