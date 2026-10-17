'use strict';
let historyOffset=0,historyTotal=0,historyEpoch=0,historyRecord=null,historyProjectId='';
const historyStates={completed:'执行完成',failed:'执行失败',cancelled:'已取消'};
function historyTime(value){return new Date(value).toLocaleString('zh-CN',{hour12:false});}
function historyName(step){return step.name||(step.operation==='plugin'?step.params.operatorId+' · '+step.params.pluginId:catalog[step.operation]?.name||step.operation);}
function historyParameterLabel(step,key){
 const special={arguments:'输入参数',outputBindings:'输出变量绑定',timeoutMs:'执行超时 (ms)',targetCloud:'配准参考点云',pluginId:'插件标识',pluginVersion:'插件版本',operatorId:'算子标识'};
 return special[key]||catalog[step.operation]?.fields.find(field=>field[0]===key)?.[1]||fieldNames[key]||key;
}
function historyMessage(text,error=false){renderDataMessage($('history-message'),text);$('history-message').className=error?'error':'muted';}
function historyFields(holder,values){
 const table=formEl('table',undefined,'form-table history-fields'),head=formEl('tr');head.append(formEl('th','字段'),formEl('th','记录值'));table.append(head);
 for(const [key,value] of Object.entries(values)){const row=formEl('tr'),cell=formEl('td');cell.append(resultValueView(value,0,k=>resultLabel(k,false)));row.append(formEl('th',key),cell);table.append(row);}holder.append(table);
}
function historyFrame(holder,frame,label){
 const section=formEl('section');section.append(formEl('h4',label));
 if(/^data:image\/(png|jpeg|webp);base64,/.test(frame?.image||'')){const image=formEl('img');image.src=frame.image;image.alt=label;image.className='history-image';section.append(image);}
 const cloud=frame?.cloud,depth=frame?.depth;
 if(cloud)historyFields(section,{'点云坐标单位':cloud.unit,'点数':cloud.points?.length??0,'坐标预览（前 50 点）':cloud.points?.slice(0,50)||[]});
 if(depth)historyFields(section,{'深度图宽度':depth.width,'深度图高度':depth.height,'深度单位比例':depth.scaleMeters,'相机内参':depth.intrinsics});
 if(/^data:image\/png;base64,/.test(depth?.preview||'')){const image=formEl('img');image.src=depth.preview;image.alt=label+'深度距离预览';image.className='history-image';section.append(image,formEl('p',`深度色标 ${depth.minMeters}–${depth.maxMeters} m；黑色为无效或范围外。`,'muted'));}
 if(!frame?.image&&!cloud&&!depth)section.append(formEl('p','该数据帧没有图像、点云或深度数据。','muted'));
 holder.append(section);
}
function historyRenderStep(){
 const record=historyRecord;if(!record)return;
 const step=record.project.steps.find(s=>s.id===$('history-step').value),holder=$('history-step-details');holder.replaceChildren();if(!step)return;
 const row=record.results.find(r=>r.id===step.id),planned=record.plannedStepIds.includes(step.id);
 historyFields(holder,{'模块':historyName(step),'节点 ID':step.id,'执行状态':!planned?'不在本次执行范围':!row?'未执行':row.error?(row.handled?'失败 · 已转入错误分支':'执行失败'):row.skipped?'已跳过':'执行完成','原因':row?.error||row?.reason||'—','耗时 (ms)':row?.output?.elapsedMs??null});
 if(row?.output?.result){holder.append(formEl('h4','模块结果'));historyFields(holder,Object.fromEntries(Object.entries(row.output.result).map(([key,value])=>[resultLabel(key,false)+' ('+key+')',value])));}
 if(row?.output?.logs)holder.append(formEl('h4','脚本日志'),scriptLogView(row.output.logs,k=>resultLabel(k,false)));
 const params=formEl('details');params.append(formEl('summary','本次运行的参数与脚本'));
 const fields={};for(const [key,value] of Object.entries(step.params)){
  if(key==='code'){const code=formEl('pre',value,'history-code');params.append(formEl('h4','脚本代码（只读）'),code);}
  else if(key==='arguments'&&step.operation==='plugin'){
   const schema=pluginInfo(step).op?.parameters||[];
   fields[historyParameterLabel(step,key)]=Object.fromEntries(Object.entries(value||{}).map(([name,item])=>[(schema.find(field=>field.key===name)?.label||name)+' ('+name+')',item]));
  }else fields[historyParameterLabel(step,key)+' ('+key+')']=value;
 }
 historyFields(params,fields);holder.append(params);
 if(record.framesSaved&&row?.output)historyFrame(holder,{image:row.output.annotatedImage,cloud:row.output.cloud,depth:row.output.depth},'模块输出图像 / 数据帧');
}
async function historyShowRecord(id){
 const epoch=++historyEpoch;historyMessage('正在读取运行明细…');
 try{const record=await api('history/'+encodeURIComponent(id));if(epoch!==historyEpoch||!$('history-dialog').open)return;
  historyRecord=record;$('history-list-view').hidden=true;$('history-detail-view').hidden=false;
  $('history-record-title').textContent=record.project.name+' · '+historyTime(record.startedAt);
  const summary=$('history-record-summary');summary.replaceChildren();historyFields(summary,{'运行 ID':record.id,'运行状态':historyStates[record.state],'启动方式':record.origin==='mqtt'?'MQTT 事件触发':record.origin==='continuous'?'连续检测':'手动执行','总耗时 (ms)':record.endedAt-record.startedAt,'变量处理':record.variablesCommitted?'本轮变量已提交':'本轮变量未提交，显示结束时的已保存值','停止原因':record.error||'—','监控记录提示':record.monitorWarning||'无监控写入错误','已处理错误数量':record.results.filter(row=>row.handled).length,'采集与输出数据帧':record.framesSaved?'已按工程设置保留':'未保留（仅参数、结果、日志及变量）'});
  if(record.trigger)historyFields(summary,{'事件输入':record.trigger.message});
  const select=$('history-step');select.replaceChildren(...record.project.steps.map((s,i)=>new Option((i+1)+' · '+historyName(s),s.id)));
  const failed=record.results.find(r=>r.error);select.value=failed?.id||record.results.at(-1)?.id||record.project.steps[0]?.id||'';historyRenderStep();
  const variables=$('history-variables');variables.replaceChildren();historyFields(variables,{'全局变量':record.variables.global,'全局固定类型':record.variables.globalTypes||{},'流程变量':record.variables.flow,'流程固定类型':record.project.variableTypes||{}});
  for(const [index,step] of record.project.steps.entries()){const section=formEl('details');section.append(formEl('summary','模块变量 · '+(index+1)+' · '+historyName(step)));historyFields(section,{'节点 ID':step.id,'变量值':record.variables.modules[step.id]||{},'固定类型':step.variableTypes||{}});variables.append(section);}
  const input=$('history-input');input.replaceChildren();if(record.framesSaved)historyFrame(input,record.input,'本次输入数据帧');else input.append(formEl('p','此次未保留输入图像、深度和点云。','muted'));historyMessage('历史记录为只读，不会替换当前工程或写回变量。');
 }catch(error){if(epoch===historyEpoch)historyMessage(error.message,true);}
}
async function historyLoad(){
 const epoch=++historyEpoch;historyRecord=null;$('history-list-view').hidden=false;$('history-detail-view').hidden=true;historyMessage('正在查询运行历史…');
 const params=new URLSearchParams({offset:String(historyOffset),limit:'20',state:$('history-state').value});
 if($('history-project').value==='current')params.set('projectId',historyProjectId);
 for(const [id,key] of [['history-from','after'],['history-to','before']])if($(id).value){const time=new Date($(id).value).getTime();if(!Number.isFinite(time)){historyMessage('请选择有效的时间范围',true);return;}params.set(key,String(time));}
 $('history-refresh').disabled=true;$('history-prev').disabled=true;$('history-next').disabled=true;
 try{const data=await api('history?'+params);if(epoch!==historyEpoch||!$('history-dialog').open)return;historyTotal=data.total;
  if(historyOffset>=data.total&&historyOffset>0){historyOffset=Math.max(0,Math.floor((data.total-1)/20)*20);return historyLoad();}
  const body=$('history-rows');body.replaceChildren();
  for(const record of data.items){const row=formEl('tr'),action=formEl('td'),button=formEl('button','查看明细');button.setAttribute('aria-label','查看 '+historyTime(record.startedAt)+' '+record.projectName+' 明细');button.onclick=()=>historyShowRecord(record.id);action.append(button);
  for(const value of [historyTime(record.startedAt),record.projectName,historyStates[record.state],record.elapsedMs+' ms',record.finishedSteps+' / '+record.stepCount,record.inspectionFailures?record.inspectionFailures+' 个模块未通过':record.state!=='completed'?'未完成判定':'无未通过标记',record.framesSaved?'保留':'未保留'])row.append(formEl('td',value));row.append(action);body.append(row);
  }
  if(!data.items.length){const row=formEl('tr'),cell=formEl('td','当前筛选没有运行记录。');cell.colSpan=8;row.append(cell);body.append(row);}
  $('history-page').textContent=`共 ${data.total} 条 · 第 ${data.total?Math.floor(historyOffset/20)+1:0} / ${Math.ceil(data.total/20)} 页`;
  $('history-prev').disabled=historyOffset===0;$('history-next').disabled=historyOffset+20>=data.total;
  $('history-storage').textContent=`服务器保存 ${data.storedCount} 条，有效明细 ${(data.storedBytes/1048576).toFixed(1)} MiB；保留最近 ${data.maxRecords} 条，明细容量上限 ${Math.round(data.maxBytes/1048576)} MiB，超限先清理最旧记录。`;
  historyMessage(data.warnings.join(' ')||'“执行完成”不等于产品合格；未通过标记只统计模块顶层 passed 为否的结果。',data.warnings.length>0);
 }catch(error){if(epoch===historyEpoch){$('history-rows').replaceChildren();$('history-page').textContent='查询失败';historyMessage(error.message,true);}}
 finally{if(epoch===historyEpoch)$('history-refresh').disabled=false;}
}
function initHistoryUI(){
 $('history-open').onclick=()=>{historyProjectId=project.id;historyOffset=0;$('history-frame-project').textContent=project.name;$('history-frames').checked=project.history?.includeFrames===true;$('history-frames').disabled=running||continuousState.busy;$('history-dialog').showModal();historyLoad();};
 $('history-dialog').addEventListener('close',()=>{historyEpoch++;historyRecord=null;$('history-step-details').replaceChildren();$('history-input').replaceChildren();$('history-variables').replaceChildren();});
 $('history-refresh').onclick=()=>{historyOffset=0;historyLoad();};$('history-prev').onclick=()=>{historyOffset=Math.max(0,historyOffset-20);historyLoad();};$('history-next').onclick=()=>{if(historyOffset+20<historyTotal){historyOffset+=20;historyLoad();}};
 $('history-back').onclick=historyLoad;$('history-step').onchange=historyRenderStep;
 $('history-frames').onchange=safe(()=>{if(running||continuousState.busy){$('history-frames').checked=project.history?.includeFrames===true;throw Error('请在本次运行结束后修改归档设置');}project.history={includeFrames:$('history-frames').checked};dirty(false);historyMessage('归档设置已应用于后续运行；请保存工程以长期保留。');});
}
