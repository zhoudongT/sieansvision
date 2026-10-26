'use strict';
let cameraSessionState={state:'idle'},cameraSessionPending=false,cameraSessionFormLoaded=false,cameraSessionFormId=null,cameraSessionRead=0;
function cameraSessionParams(){
 const base=cameraDeviceParams(),step=selectedStep();
 if(step?.operation==='camera_capture'&&step.params.driver===base.driver&&step.params.deviceId===base.deviceId&&step.params.providerId===base.providerId)return structuredClone(step.params);
 return base;
}
function renderCameraSession(){
 const s=cameraSessionState,active=s.active,labels={idle:'未连接',opening:'正在打开设备',running:'持续采集中',reconnecting:'正在重连',stopping:'正在释放设备',stopped:'已停止',failed:'采集失败',interrupted:'服务中断，需手动重连'};
 $('camera-session-status').textContent=(labels[s.state]||s.state)+(s.error?' · '+s.error:'');
 $('camera-session-start').disabled=!!(active||running||cameraSessionPending||!cameraSelection);
 $('camera-session-reopen').disabled=!!(active||running||cameraSessionPending||!s.config);
 $('camera-session-stop').disabled=!!(!active||running||cameraSessionPending);
 $('camera-session-add').disabled=!!(s.state!=='running'||running||cameraSessionPending);
 $('camera-session-preview').disabled=!!(s.state!=='running'||running||cameraSessionPending);
 $('camera-session-apply').disabled=!!(s.state!=='running'||running||cameraSessionPending||selectedStep()?.operation!=='camera_capture');
 for(const id of ['camera-session-interval','camera-session-retries','camera-session-reconnect','camera-session-autostart'])$(id).disabled=!!(active||cameraSessionPending);
 const table=$('camera-session-statistics');table.replaceChildren();
 const rows=[['会话编号',s.id||'—'],['设备驱动',s.config?.params.driver||'—'],['设备标识',s.config?.params.deviceId||'—'],['接收帧数',s.received||0],['流程/预览取帧次数',s.consumed||0],['缓存覆盖未取帧数',s.overwritten||0],['重复使用缓存帧次数',s.reused||0],['重连次数',s.reconnects||0],['缓存帧龄 (ms)',s.frameAgeMs??'—'],['缓存容量','1 帧；新帧覆盖旧帧']];
 for(const [key,value]of rows){const row=formEl('tr');row.append(formEl('th',key),formEl('td',value));table.append(row);}
 if(!cameraSessionFormLoaded||s.active&&s.id!==cameraSessionFormId){for(const [id,key,fallback]of [['camera-session-interval','intervalMs',100],['camera-session-retries','reconnectAttempts',0],['camera-session-reconnect','reconnectMs',1000]])$(id).value=s.config?.[key]??fallback;$('camera-session-autostart').checked=s.config?.autoStart??true;cameraSessionFormLoaded=true;cameraSessionFormId=s.id;}
}
async function refreshCameraSession(){const request=++cameraSessionRead;try{const s=await api('cameras/session');if(request!==cameraSessionRead)return;cameraSessionState=s;renderCameraSession();}catch(error){if(request===cameraSessionRead)$('camera-session-status').textContent=error.message;}}
async function cameraSessionAction(action){if(cameraSessionPending||running)return;cameraSessionPending=true;renderCameraSession();let failure;try{await action();}catch(error){failure=error.message;status(error.message,'error');}finally{cameraSessionPending=false;await refreshCameraSession();if(failure)$('camera-session-status').textContent=failure;}}
function cameraSessionConfig(params){
 const config={params,autoStart:$('camera-session-autostart').checked};for(const [id,key]of [['camera-session-interval','intervalMs'],['camera-session-retries','reconnectAttempts'],['camera-session-reconnect','reconnectMs']]){const input=$(id),value=Number(input.value);if(input.value===''||!Number.isInteger(value)||value<Number(input.min)||value>Number(input.max)){input.reportValidity();throw Error('请修正连续采集表单：'+input.getAttribute('aria-label'));}config[key]=value;}return config;
}
function initCameraSessionUI(){
 const panel=formEl('section',undefined,'camera-session-panel');panel.append(formEl('h3','连续连接与帧缓存'));
 panel.append(formEl('p','连接后一直保持采集，停止流程或关闭网页不释放相机；退出采集服务时释放。勾选随服务启动后，下次启动自动连接。仅自由采集；故障重连次数可配置。新帧覆盖旧帧，不用于每帧无损记录。','form-notice'));
 const fields=formEl('div',undefined,'camera-selectors');
 for(const [id,label,min,max,value]of [['camera-session-interval','最短采集间隔 (ms)',50,60000,100],['camera-session-retries','本次会话重连总次数',0,5,0],['camera-session-reconnect','重连等待 (ms)',200,60000,1000]]){
  const row=formEl('label',label),input=formEl('input');input.id=id;input.type='number';input.min=min;input.max=max;input.step=1;input.value=value;input.required=true;input.setAttribute('aria-label',label);row.append(input);fields.append(row);
 }
 const autoRow=formEl('label','随采集服务启动自动连接'),autoInput=formEl('input');autoInput.id='camera-session-autostart';autoInput.type='checkbox';autoInput.checked=true;autoRow.append(autoInput);fields.append(autoRow);
 panel.append(fields);const actions=formEl('div',undefined,'camera-actions');
 for(const [id,label]of [['camera-session-start','打开所选相机并持续采集'],['camera-session-reopen','按上次配置重新连接'],['camera-session-stop','停止并释放设备'],['camera-session-preview','预览最新缓存帧'],['camera-session-apply','应用到所选采集节点'],['camera-session-add','添加连续取帧节点']]){const button=formEl('button',label);button.id=id;button.type='button';actions.append(button);}panel.append(actions);
 const state=formEl('p');state.id='camera-session-status';state.setAttribute('role','status');const table=formEl('table',undefined,'form-table');table.id='camera-session-statistics';panel.append(state,table);$('camera-dialog').append(panel);
 $('camera-session-start').onclick=()=>cameraSessionAction(async()=>{cameraSessionState=await api('cameras/session',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(cameraSessionConfig(cameraSessionParams()))});});
 $('camera-session-reopen').onclick=()=>cameraSessionAction(async()=>{cameraSessionState=await api('cameras/session',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(cameraSessionConfig(cameraSessionState.config.params))});});
 $('camera-session-stop').onclick=()=>cameraSessionAction(async()=>{cameraSessionState=await api('cameras/session/'+cameraSessionState.id+'/stop',{method:'POST'});});
 $('camera-session-preview').onclick=()=>cameraSessionAction(async()=>{const out=await cameraRequest('camera_capture',{driver:'session',sessionId:cameraSessionState.id,framePolicy:'latest',maxAgeMs:5000,timeoutMs:5000});cameraPreview=out;$('camera-preview').src=out.annotatedImage;$('camera-preview').hidden=false;cameraRows($('camera-properties'),Object.entries(out.result).map(([name,value])=>({name,value})),[['name','采集字段'],['value','值']]);});
 const useConnection=add=>{if(running||cameraSessionState.state!=='running')return;if(add)addStep('camera_capture');if(selectedStep()?.operation!=='camera_capture')return;selectedStep().params={driver:'session',sessionId:cameraSessionState.bindingId,framePolicy:'next',maxAgeMs:1000,timeoutMs:5000};dirty();renderParams();$('camera-dialog').close();};
 $('camera-session-add').onclick=safe(()=>useConnection(true));
 $('camera-session-apply').onclick=safe(()=>useConnection(false));
 refreshCameraSession();setInterval(()=>{if($('camera-dialog').open&&!cameraSessionPending)refreshCameraSession();},1000);
}
async function prepareCameraSessionDemo(steps,params){
 let s=await api('cameras/session');
 if(s.active&&(s.config?.params.driver!==params.driver||s.config?.params.deviceId!==params.deviceId))throw Error('已有其他设备的连续会话，请先在相机管理中停止，再运行此演示');
 if(!s.active)s=await api('cameras/session',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({params,intervalMs:100,reconnectAttempts:0})});
 for(let attempt=0;attempt<150&&s.state!=='running';attempt++){
  if(['failed','stopped','interrupted'].includes(s.state))throw Error(s.error||'连续相机未运行');
  await new Promise(resolve=>setTimeout(resolve,100));s=await api('cameras/session');
 }
 if(s.state!=='running')throw Error('连续相机打开超时，请在相机管理中检查状态');
 cameraSessionState=s;for(const step of steps)if(step.operation==='camera_capture'&&step.params.driver==='session')step.params.sessionId=s.id;
}
