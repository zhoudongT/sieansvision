'use strict';
let mqttTriggerState={state:'idle',busy:false},mqttTriggerStarting=false,mqttTriggerPolling=false,mqttTriggerFormLoaded=false;
const mqttTriggerLabels={idle:'未启动',connecting:'正在连接',subscribed:'正在订阅',reconnecting:'断线重连中',stopping:'正在停止',stopped:'已停止',failed:'异常停机',interrupted:'服务重启后已中断'};
const mqttTriggerNames={simulator:'本机模拟消息服务器',broker:'指定消息服务器',plain:'普通 TCP',tls:'TLS 加密',text:'UTF-8 文本',structured:'结构化字段',bytes:'字节数组',stop:'停止事件会话',dropOldest:'丢弃最早等待消息',dropNewest:'丢弃新消息'};
function mqttTriggerRender(){
 const s=mqttTriggerState,busy=s.busy||mqttTriggerStarting,label=mqttTriggerLabels[s.state]||s.state;
 $('mqtt-trigger-banner').hidden=!s.id||(!s.busy&&s.projectId!==project.id);$('mqtt-trigger-summary').textContent=(s.projectName||'MQTT 事件触发')+' · '+label+' · 成功 '+(s.completed||0)+' · 排队 '+(s.queued||0)+(s.error?' · '+s.error:'');
 $('mqtt-trigger-test').disabled=s.state!=='subscribed'||s.config?.connection?.connection!=='simulator';$('mqtt-trigger-start').disabled=busy||running||!project.steps.length;$('mqtt-trigger-stop').disabled=!s.busy;$('mqtt-trigger-banner-stop').disabled=!s.busy;$('mqtt-trigger-load').disabled=!s.hasProject||localExecuting;
 for(const field of $('mqtt-trigger-fields').querySelectorAll('input,select'))field.disabled=busy;
 const rows={'运行工程':s.projectName||'—','连接状态':label,'正在执行流程':s.executing?'是':'否','接收消息':s.received||0,'成功执行':s.completed||0,'失败执行':s.failed||0,'等待消息':s.queued||0,'丢弃消息':s.dropped||0,'过期消息':s.expired||0,'重复消息':s.duplicates||0,'无效消息':s.invalid||0,'重连次数':s.reconnects||0,'最近主题':s.lastMessage?.topic||'—','最近接收时间':s.lastMessage?new Date(s.lastMessage.receivedAt).toLocaleString('zh-CN'):'—','连接或消息提示':s.connectionError||'—','停止原因':s.error||'—'};
 const table=$('mqtt-trigger-details');table.replaceChildren();for(const [label,value] of Object.entries(rows)){const row=formEl('tr');row.append(formEl('th',label),formEl('td',String(value)));table.append(row);}
}
function mqttTriggerForm(config){
 const holder=$('mqtt-trigger-fields');holder.replaceChildren();const connection={...mqttDefaults,acceptRetained:false,...config?.connection};
 const fields=[...mqttFields,['acceptRetained','接收保留消息（重连后可能重新收到）','boolean'],['variable','接收消息写入流程变量','text'],['keyField','消息内容去重字段（可选，如 requestId）','text'],['capacity','等待队列容量',1,100],['maxAgeMs','等待消息有效期 (ms)',100,3600000],['reconnectMs','断线重连间隔 (ms)',200,60000],['overflow','队列满时的处理',['stop','dropOldest','dropNewest']]];
 const defaults={variable:'mqttEvent',keyField:'',capacity:20,maxAgeMs:30000,reconnectMs:1000,overflow:'stop',...config};
 const refresh=()=>{const params={};for(const [key] of mqttFields)params[key]=$('event-'+key).value;for(const label of holder.querySelectorAll('[data-mqtt-field]')){const key=label.dataset.mqttField;label.hidden=!mqttFieldVisible({operation:'mqtt_receive',params},key);}};
 for(const [key,label,type,max] of fields){const wrap=formEl('label',key==='timeoutMs'?'连接与订阅应答超时 (ms)':label);wrap.dataset.mqttField=key;let input;
  const value=mqttFields.some(([name])=>name===key)||key==='acceptRetained'?connection[key]:defaults[key];
  if(Array.isArray(type)){input=formEl('select');input.replaceChildren(...type.map(v=>new Option(mqttTriggerNames[v]||String(v),v)));input.value=value??type[0];}
  else {input=formEl('input');input.type=type==='boolean'?'checkbox':typeof type==='number'?'number':'text';if(input.type==='checkbox')input.checked=!!value;else input.value=value??'';if(typeof type==='number'){input.min=type;input.max=max;input.required=true;}}
  input.id='event-'+key;input.setAttribute('aria-label','事件触发 '+label);if(key==='variable'){input.required=true;input.pattern='[A-Za-z_][A-Za-z0-9_]{0,63}';}input.onchange=refresh;wrap.append(input);holder.append(wrap);
 }refresh();
}
async function mqttTriggerRefresh(){
 if(mqttTriggerPolling||mqttTriggerStarting)return;mqttTriggerPolling=true;const epoch=continuousEpoch;
 try{const before=mqttTriggerState,s=await api('runtime/mqtt-trigger');if(epoch!==continuousEpoch)return;mqttTriggerState=s;
  if(s.config&&(!mqttTriggerFormLoaded||(s.busy&&s.id!==before.id))){mqttTriggerForm(s.config);mqttTriggerFormLoaded=true;}
  continuousApplyLock();mqttTriggerRender();
  if(!localExecuting&&(s.busy||before.busy||$('mqtt-trigger-dialog').open))await continuousView(s);
 }catch(error){$('mqtt-trigger-summary').textContent='MQTT 事件状态读取失败：'+error.message;}
 finally{mqttTriggerPolling=false;}
}
async function mqttTriggerStart(){
 if(running||mqttTriggerStarting)return;applyParams();for(const field of $('mqtt-trigger-fields').querySelectorAll('input:not([type=checkbox])'))if(!field.checkValidity()){field.reportValidity();return;}
 const number=key=>Number($('event-'+key).value),connection={};for(const [key,,type] of mqttFields)connection[key]=typeof type==='number'?number(key):$('event-'+key).value;
 connection.acceptRetained=$('event-acceptRetained').checked;
 const request={project:currentProject(),image:source||'',cloud:sourceCloud,depth:sourceDepth,allowScripts:$('script-trust').checked,connection,variable:$('event-variable').value,keyField:$('event-keyField').value,capacity:number('capacity'),maxAgeMs:number('maxAgeMs'),reconnectMs:number('reconnectMs'),overflow:$('event-overflow').value};
 continuousEpoch++;mqttTriggerStarting=true;continuousApplyLock();mqttTriggerRender();
 try{mqttTriggerState=await api('runtime/mqtt-trigger',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(request)});continuousVersion='';hmiBeginRun();status('服务器已启动 MQTT 事件订阅；关闭浏览器不会停止');}
 finally{mqttTriggerStarting=false;continuousApplyLock();mqttTriggerRender();await mqttTriggerRefresh();}
}
async function mqttTriggerStop(){if(!mqttTriggerState.busy)return;continuousEpoch++;mqttTriggerState=await api('runtime/mqtt-trigger/'+encodeURIComponent(mqttTriggerState.id)+'/stop',{method:'POST'});mqttTriggerRender();status('事件触发停止已请求；未执行消息将丢弃，当前流程取消');await mqttTriggerRefresh();}
function initMqttTriggerUI(){
 const button=formEl('button','事件触发');button.id='mqtt-trigger-open';button.onclick=safe(async()=>{mqttTriggerRender();$('mqtt-trigger-dialog').showModal();await mqttTriggerRefresh();});$('continuous-open').after(button);
 const banner=formEl('div');banner.id='mqtt-trigger-banner';banner.hidden=true;banner.setAttribute('role','region');banner.setAttribute('aria-label','MQTT 事件触发状态');banner.innerHTML='<span id="mqtt-trigger-summary"></span><button id="mqtt-trigger-banner-stop">停止事件触发</button>';$('continuous-banner').after(banner);
 const dialog=formEl('dialog');dialog.id='mqtt-trigger-dialog';dialog.innerHTML='<form method="dialog"><button class="dialog-close" aria-label="关闭事件触发">×</button></form><h2>MQTT 事件触发</h2><p>服务器长期订阅消息，每条有效消息按队列执行一次当前工程快照。消息的主题、内容、接收时间等写入指定流程变量；绑定示例：流程变量 mqttEvent.value。流程失败时停止，已发出的设备动作不会回滚。</p><div id="mqtt-trigger-fields"></div><div class="continuous-actions"><button id="mqtt-trigger-start">启动事件订阅</button><button id="mqtt-trigger-stop">停止订阅</button><button id="mqtt-trigger-test">发送模拟测试消息</button><button id="mqtt-trigger-load">载入运行工程快照</button></div><table class="form-table" aria-label="事件会话统计"><tbody id="mqtt-trigger-details"></tbody></table>';document.body.append(dialog);
 $('mqtt-trigger-test').onclick=safe(async()=>{await api('runtime/mqtt-trigger/test-message',{method:'POST'});status('本机模拟消息已发送；等待服务器执行事件流程');await mqttTriggerRefresh();});
 mqttTriggerForm();$('mqtt-trigger-start').onclick=safe(mqttTriggerStart);$('mqtt-trigger-stop').onclick=safe(mqttTriggerStop);$('mqtt-trigger-banner-stop').onclick=safe(mqttTriggerStop);
 $('mqtt-trigger-load').onclick=safe(async()=>{const data=await api('runtime/mqtt-trigger/project');if(!data.project)throw Error('事件工程快照已过期，请打开保存的工程');useProject(data.project);source='';sourceCloud=null;sourceDepth=null;originalImage=null;continuousVersion='';continuousApplyLock();await continuousView(mqttTriggerState);status('已载入服务器事件工程快照');});
 mqttTriggerRender();mqttTriggerRefresh();setInterval(mqttTriggerRefresh,750);
}
