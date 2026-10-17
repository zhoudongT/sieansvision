'use strict';
let continuousState={state:'idle',busy:false},continuousPolling=false,continuousStarting=false,continuousUiLock=false,continuousVersion='',continuousViewProject='',continuousError='',continuousEpoch=0;
const continuousLabels={idle:'未启动',running:'正在检测',waiting:'等待下一轮',stopping:'正在停止',stopped:'已停止',completed:'指定轮次已完成',failed:'异常停机',interrupted:'服务重启后已中断'};
function continuousRender(){
 const s=continuousState,busy=s.busy||continuousStarting,label=continuousStarting?'正在启动':continuousLabels[s.state]||s.state;
 $('continuous-banner').hidden=(!s.id||(!s.busy&&s.projectId!==project.id))&&!continuousError;
 renderDataMessage($('continuous-summary'),continuousError||((s.projectName||'连续检测')+' · '+label+' · 已完成 '+(s.completedCycles||0)+' / '+(s.maxCycles||'不限')+' 轮'+(s.error?' · '+s.error:'')));
 $('continuous-summary').className=continuousError||['failed','interrupted'].includes(s.state)?'error':'';
 $('continuous-start').disabled=busy||localExecuting||!project.steps.length;
 $('continuous-stop').disabled=!s.busy;$('continuous-banner-stop').disabled=!s.busy;
 $('continuous-interval').disabled=busy;$('continuous-count').disabled=busy;
 $('continuous-load').disabled=!s.hasProject||localExecuting;
 $('continuous-current-project').textContent=s.busy?'正在运行工程：'+s.projectName:'下次启动工程：'+project.name;
 const rows=[['运行状态',label],['运行工程',s.projectName||'—'],['设定执行次数',s.maxCycles===undefined?'—':s.maxCycles||'不限（直到停止）'],['开始轮次',s.startedCycles||0],['执行成功轮次',s.completedCycles||0],['执行失败轮次',s.failedCycles||0],['取消轮次',s.cancelledCycles||0],['轮次间隔',s.intervalMs? s.intervalMs+' ms':'—'],['上一轮耗时',s.lastElapsedMs===undefined?'—':s.lastElapsedMs+' ms'],['下轮计划时间',s.nextAt?new Date(s.nextAt).toLocaleTimeString('zh-CN',{hour12:false}):'—'],['启动时间',s.startedAt?new Date(s.startedAt).toLocaleString('zh-CN'):'—'],['停止原因',s.error||'—']];
 const holder=$('continuous-details');holder.replaceChildren();for(const [name,value] of rows){const row=formEl('tr');const cell=formEl('td');cell.append(resultValueView(value));row.append(formEl('th',name),cell);holder.append(row);}
}
function continuousApplyLock(){
 if(localExecuting)return;
 const busy=continuousState.busy||continuousStarting||mqttTriggerState.busy||mqttTriggerStarting,changed=continuousUiLock!==busy;
 if(busy||continuousUiLock){running=busy;setBusy(busy);}
 continuousUiLock=busy;if(changed){renderPipeline();hmiUpdateWidgets();}
}
async function continuousView(session=continuousState){
 if(localExecuting||session.projectId!==project.id)return;
 const id=project.id,epoch=continuousEpoch;if(continuousViewProject!==id){continuousViewProject=id;continuousVersion='';}
 const fresh=await api('runtime/view',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({project,since:continuousVersion})});
 if(id!==project.id||localExecuting||epoch!==continuousEpoch)return;
 const changed=fresh.version!==continuousVersion;continuousVersion=fresh.version;
 if(fresh.results&&changed){
   framePreviews.clear();results=fresh.results.map(item=>({...item,name:flowName(item.id)}));results.forEach(rememberFrame);
   activeStepId=fresh.status.activeStep||'';renderResults();renderPipeline();refreshInputPreview();
   if(results.at(-1)?.output?.cloud){$('cloud-data').value='result';setImageView('cloud');}
   else if(results.some(r=>r.output?.annotatedImage)&&document.querySelector('.views').dataset.view!=='split')setImageView('output');
   $('run-timing').textContent='本轮耗时 '+(fresh.status.elapsedMs||0)+' ms';
 }
 hmiProjectId=id;hmiState={...fresh,results:fresh.results??hmiState.results};hmiError='';hmiUpdateWidgets();
}
async function continuousRefresh(){
 if(continuousPolling||continuousStarting)return;continuousPolling=true;const epoch=continuousEpoch;
 try{
   const before=continuousState,fresh=await api('runtime/continuous');if(epoch!==continuousEpoch)return;continuousState=fresh;continuousError='';
   if(fresh.busy&&fresh.id!==before.id){$('continuous-interval').value=String(fresh.intervalMs);$('continuous-count').value=String(fresh.maxCycles);}
   continuousApplyLock();continuousRender();
   if(!localExecuting&&(continuousState.busy||before.busy||$('continuous-dialog').open))await continuousView();
   if(before.busy&&!continuousState.busy)status('连续检测：'+continuousLabels[continuousState.state]+'，执行成功 '+continuousState.completedCycles+' 轮'+(continuousState.error?'；'+continuousState.error:''),continuousState.state==='failed'?'error':'success');
 }catch(error){if(epoch!==continuousEpoch)return;continuousError='连续检测状态读取失败：'+error.message;continuousRender();if(continuousState.busy&&continuousState.projectId===project.id){hmiError=continuousError;hmiUpdateWidgets();}}
 finally{continuousPolling=false;}
}
async function continuousStart(){
 if(continuousStarting||continuousState.busy||running)return;
 applyParams();const interval=$('continuous-interval'),count=$('continuous-count');
 for(const input of [interval,count])if(!input.checkValidity()){input.reportValidity();return;}
 const request={project:currentProject(),image:source||'',cloud:sourceCloud,depth:sourceDepth,allowScripts:$('script-trust').checked,intervalMs:Number(interval.value),maxCycles:Number(count.value)};
 continuousEpoch++;continuousStarting=true;continuousApplyLock();continuousRender();
 try{continuousState=await api('runtime/continuous',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(request)});continuousVersion='';hmiBeginRun();status('服务器已启动连续检测；关闭浏览器不会停止');}
 finally{continuousStarting=false;continuousApplyLock();continuousRender();await continuousRefresh();}
}
async function continuousStop(){
 if(!continuousState.busy)return;
 continuousEpoch++;
 continuousState=await api('runtime/continuous/'+encodeURIComponent(continuousState.id)+'/stop',{method:'POST'});
 continuousRender();status('连续检测停止已请求；等待本轮取消后释放运行平台');await continuousRefresh();
}
function initContinuousUI(){
 const open=safe(async()=>{continuousRender();$('continuous-dialog').showModal();await continuousRefresh();});
 $('continuous-open').onclick=open;$('continuous-details-open').onclick=open;
 $('continuous-start').onclick=safe(continuousStart);$('continuous-stop').onclick=safe(continuousStop);$('continuous-banner-stop').onclick=safe(continuousStop);
 $('continuous-load').onclick=safe(async()=>{if(localExecuting)return;const data=await api('runtime/continuous/project');if(!data.project)throw Error('运行工程快照已过期，请打开已保存的工程');useProject(data.project);source='';sourceCloud=null;sourceDepth=null;originalImage=null;continuousVersion='';$('demo-banner').hidden=true;demoBackup=null;$('saved-state').textContent='服务器运行工程快照';continuousApplyLock();await continuousView();continuousRender();});
 continuousRender();continuousRefresh();setInterval(continuousRefresh,750);
}
