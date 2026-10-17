'use strict';
let computeInfo=null;
function computeLabel(id){const device=computeInfo?.devices.find(d=>d.id===id);return id==='auto'?'自动选择（优先 GPU）':id==='cpu'?'CPU':device?id+' · '+device.name:id+' · 尚未确认可用';}
function computeChoices(options,step,key){if(key!=='device'||!['yolo','yolo_segment'].includes(step.operation))return options;return [...new Set(['cpu','auto',...(computeInfo?.devices||[]).map(d=>d.id),...options,...(typeof step.params.device==='string'?[step.params.device]:[])])];}
function renderComputeParamTools(step){const button=$('compute-parameter-open');if(button)button.hidden=!['yolo','yolo_segment'].includes(step?.operation);}
async function refreshCompute(){
 const info=await api('compute?refresh=1');computeInfo=info;
 const holder=$('compute-details');holder.replaceChildren();
 trainingTable(holder,[['PyTorch 版本',info.torchVersion],['CUDA 运行库',info.cudaVersion||'未安装 CUDA 版本'],['状态',info.reason]]);
 const devices=formEl('table',undefined,'form-table'),head=formEl('tr');for(const name of ['设备编号','名称','显存 (MB)','计算能力'])head.append(formEl('th',name));devices.append(head);
 for(const d of info.devices){const row=formEl('tr');for(const value of [d.id,d.name,d.memoryMB??'—',d.capability??'—'])row.append(formEl('td',value));devices.append(row);}holder.append(devices);
 const select=$('training-device'),chosen=select.value||'cpu';select.replaceChildren(...['cpu','auto',...info.devices.filter(d=>d.id!=='cpu').map(d=>d.id)].map(id=>new Option(computeLabel(id),id)));if(!Array.from(select.options).some(o=>o.value===chosen))select.append(new Option(computeLabel(chosen),chosen));select.value=chosen;
 if(['yolo','yolo_segment'].includes(selectedStep()?.operation)&&!running)renderParams();
}
function initComputeUI(){
 const dialog=formEl('dialog');dialog.id='compute-dialog';dialog.setAttribute('aria-label','计算设备状态');dialog.innerHTML='<header class="training-heading"><h2>计算设备状态</h2><button id="compute-refresh">重新检测</button><button id="compute-close" aria-label="关闭计算设备">×</button></header><p>默认使用 CPU。“自动选择”优先使用可用 GPU；指定 CUDA 显卡不可用时会报错。显存不足或推理引擎设备不匹配会停止任务，不会静默改用 CPU。</p><div id="compute-details"></div><p id="compute-message" role="status"></p>';document.body.append(dialog);
 const open=()=>{dialog.showModal();refreshCompute().catch(error=>renderDataMessage($('compute-message'),error.message));};
 const train=formEl('button','计算设备');train.id='training-compute-open';train.onclick=open;$('training-refresh').before(train);
 const parameter=formEl('button','查看计算设备');parameter.id='compute-parameter-open';parameter.hidden=true;parameter.onclick=open;$('form-fields').before(parameter);
 $('compute-refresh').onclick=safe(async()=>{try{await refreshCompute();$('compute-message').textContent='检测完成';}catch(error){renderDataMessage($('compute-message'),error.message);}});$('compute-close').onclick=()=>dialog.close();
 const label=formEl('label','计算设备'),select=formEl('select');select.id='training-device';select.setAttribute('aria-label','训练计算设备');for(const id of ['cpu','auto','cuda:0'])select.append(new Option(computeLabel(id),id));label.append(select);$('training-config').prepend(label);
 refreshCompute().catch(error=>renderDataMessage($('compute-message'),error.message));
}
