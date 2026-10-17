'use strict';
const mqttDefaults={connection:'simulator',host:'127.0.0.1',port:1883,security:'plain',topic:'sieans/inspection',encoding:'structured',qos:1,timeoutMs:5000,clientId:''};
const mqttFields=[['connection','消息服务器',['simulator','broker']],['host','服务器 IP / 主机名','text'],['port','MQTT 端口',1,65535],['security','连接安全',['plain','tls']],['username','用户名（可选）','text'],['passwordEnv','密码环境变量名','text'],['caFile','CA 证书路径（可选）','text'],['clientCertificate','客户端证书路径（可选）','text'],['privateKey','客户端私钥路径','text'],['keyPasswordEnv','私钥密码环境变量名','text'],['clientId','客户端标识（空白自动生成）','text'],['topic','消息主题','text'],['encoding','消息内容格式',['structured','text','bytes']],['qos','QoS 等级',0,2],['timeoutMs','操作总超时 (ms)',100,60000,100]];
const mqttCatalog={
 mqtt_publish:{name:'MQTT 发布',tag:'检测结果 · 消息输出',glyph:'MQ',defaults:{...mqttDefaults,retain:true,value:{count:0,passed:false}},fields:[...mqttFields,['retain','服务器保留最后一条消息','boolean']],description:'将文本、结构化数据或字节数组发布到消息服务器。发送内容通过表格编辑或绑定变量和上游结果。',hint:'QoS 0 仅表示已发送；QoS 1/2 表示服务器协议应答，不代表下游设备已执行。发布不自动重试；流程失败或停止不能回滚已发布消息。保留消息为空文本/空字节数组时清除该主题保留值。'},
 mqtt_receive:{name:'MQTT 接收',tag:'限时接收 · 主题筛选',glyph:'MQ',defaults:{...mqttDefaults,acceptRetained:true},fields:[...mqttFields,['acceptRetained','允许读取服务器保留消息','boolean']],description:'订阅主题，在限定时间内接收一条消息后结束。实际主题、内容、QoS 和保留标记以结果表显示，内容可写入三级变量。',hint:'支持 + 单层与 # 多层通配符。关闭保留消息后只接收新消息。每次执行建立新连接，不自动重连；持续订阅与事件触发另行配置。'}
};
function mqttParamDefault(step,key){return step.operation.startsWith('mqtt_')?(key==='connection'?'broker':key==='encoding'?'text':mqttCatalog[step.operation]?.defaults[key]):undefined;}
function mqttValueEditor(value,change,encoding){
 const box=formEl('div'),notice=formEl('p',undefined,'form-notice');
 const update=next=>{const bound=formType(next)==='reference',valid=bound||(encoding==='text'?typeof next==='string':encoding==='bytes'?Array.isArray(next):true);notice.className=valid?'form-notice':'form-notice error';notice.textContent=encoding==='text'?'发送 UTF-8 文本；请选择文本类型或绑定文本变量。':encoding==='bytes'?'发送字节数组；每个元素为 0–255 的整数。':'发送数值、文本、开关、数组或结构体；通过字段表定义内容。';};
 update(value);box.append(notice,valueEditor(value,next=>{change(next);update(next);},{label:'发送内容'}));return box;
}
function mqttFieldVisible(step,key){
 if(!step.operation.startsWith('mqtt_'))return true;
 const mode=step.params.connection,security=step.params.security||'plain';
 if(['host','port','security','username','passwordEnv','caFile','clientCertificate','privateKey','keyPasswordEnv'].includes(key)&&mode==='simulator')return false;
 if(['caFile','clientCertificate','privateKey','keyPasswordEnv'].includes(key))return typeof security==='object'||security==='tls';
 return true;
}
function showMqttSimulator(value){
 $('mqtt-simulator-status').textContent=value.unavailable?'MQTT 服务尚未加载，需要服务器使用新版代码。':value.running?`本机 MQTT 服务器运行中 · ${value.host}:${value.port} · 保留主题 ${value.retainedTopics}`:'本机 MQTT 服务器未启动';
 $('mqtt-simulator-start').disabled=!!value.unavailable||value.running;$('mqtt-simulator-stop').disabled=!!value.unavailable||!value.running||running;
}
function initMqttUI(){
 $('mqtt-simulator-start').onclick=safe(async()=>{showMqttSimulator(await api('industrial/mqtt/simulator/start',{method:'POST'}));});
 $('mqtt-simulator-stop').onclick=safe(async()=>{if(running)return;showMqttSimulator(await api('industrial/mqtt/simulator/stop',{method:'POST'}));status('MQTT 模拟服务器已停止，保留消息已清空');});
}
