'use strict';
let runtimeJob=null,variableRevision=null,variableSnapshot=null,localExecuting=false;
async function executeRuntime(single=false){
  if(running)return;applyParams();if(!project.steps.length)throw Error('请先添加算子');
  const snapshot=FlowGraph.normalize(subflowProjectForExecution(currentProject())),target=single?selectedStep()?.id:undefined;const planned=FlowGraph.plan(snapshot,target);
  if(single&&!target)throw Error('请先选择算子');
  if(FlowGraph.expanded(snapshot,target).some(s=>s.operation==='script')&&!$('script-trust').checked)throw Error('请先勾选“运行可信脚本”；Python 使用服务器账户权限执行');
  framePreviews.clear();refreshInputPreview();localExecuting=true;running=true;cancelled=false;results=[];flowLink=null;flowEdge=null;setBusy(true);renderResults();renderPipeline();hmiBeginRun();status('流程正在执行…');const started=performance.now();
  try{
    let job=await api('runtime/jobs',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({project:snapshot,image:source||'',cloud:sourceCloud,depth:sourceDepth,target,allowScripts:$('script-trust').checked})});runtimeJob=job.id;let cursor=0;
    while(true){
      activeStepId=job.activeStep||'';
      for(const item of job.results){rememberFrame(item);results.push({...item,name:flowName(item.id)});status(flowName(item.id)+(item.error?'：'+item.error+(item.handled?'（已转入错误分支）':''):item.skipped?' 已跳过：'+item.reason:' 完成'),item.error?'error':'success');if(item.output?.logs)scriptLog(flowName(item.id),item.output.logs);}
      cursor=job.cursor;hmiAcceptJob(job);renderResults();renderPipeline();refreshInputPreview();
      if(results.at(-1)?.output?.cloud){$('cloud-data').value='result';setImageView('cloud');}else if(results.length&&document.querySelector('.views').dataset.view!=='split')setImageView('output');
      if(job.state!=='running'){
        const archiveError=job.archive?.state==='failed'?'；'+job.archive.error:'';
        if(job.state==='failed')throw Error((job.error||'流程执行失败')+archiveError);
        status((job.state==='cancelled'?(job.error?'已停止：'+job.error+'；变量变更未提交':'已停止，变量变更未提交'):'流程完成：执行 '+results.filter(r=>!r.skipped).length+' 个，跳过 '+results.filter(r=>r.skipped).length+' 个；已处理错误 '+results.filter(r=>r.handled).length+' 个；变量已保存')+archiveError,archiveError?'error':job.state==='completed'?'success':'');break;
      }
      if(cancelled)await api('runtime/jobs/'+runtimeJob+'/cancel',{method:'POST'});
      await new Promise(resolve=>setTimeout(resolve,150));job=await api('runtime/jobs/'+runtimeJob+'?after='+cursor);
    }
  }finally{localExecuting=false;running=false;runtimeJob=null;activeStepId='';setBusy(false);continuousApplyLock();renderPipeline();hmiUpdateWidgets();hmiRefresh();$('run-timing').textContent='总耗时 '+Math.round(performance.now()-started)+' ms';}
}
function runtimeFields(){
  const step=selectedStep();$('script-tools').hidden=step?.operation!=='script';
  if(step?.operation==='script')$('script-code').value=step.params.code||'';
  $('script-permission').hidden=![...project.steps,...(project.subflows||[]).flatMap(d=>d.steps)].some(s=>s.operation==='script');
}
let variableDraft=null,initialDraft=null,variableTypeDraft=null;
// Keep a variable's value and contract on the same row, including missing values.
function variableDefinitionEditor(holder,values,contracts,{title,editable,change}){
 holder.replaceChildren();
 const table=formEl('table',undefined,'form-table variable-definition-table'),head=formEl('tr');
 table.setAttribute('aria-label',title+'定义和值');
 for(const label of ['变量名称','值类型','固定类型','值','校验状态','操作'])head.append(formEl('th',label));table.append(head);
 const names=[...new Set([...Object.keys(values),...Object.keys(contracts)])];let cursor=0;
 const more=formEl('button','显示更多变量');more.type='button';
 const redraw=()=>variableDefinitionEditor(holder,values,contracts,{title,editable,change});
 const append=()=>{
  for(const key of names.slice(cursor,cursor+50)){
   const row=formEl('tr'),nameCell=formEl('td'),typeCell=formEl('td'),contractCell=formEl('td'),valueCell=formEl('td'),state=formEl('td'),actions=formEl('td');
   let current=key;
   const name=formEl('input');name.value=key;name.required=true;name.pattern='[A-Za-z_][A-Za-z0-9_]{0,63}';name.setAttribute('aria-label',title+' '+key+' 名称');
   name.disabled=!editable&&Object.hasOwn(contracts,key);
   name.oninput=()=>{
    const next=validFormName(name,[...new Set([...Object.keys(values),...Object.keys(contracts)])].filter(k=>k!==current));
    if(!next||!name.reportValidity())return;
    if(Object.hasOwn(values,current)){const value=values[current];delete values[current];values[next]=value;}
    if(Object.hasOwn(contracts,current)){const type=contracts[current];delete contracts[current];contracts[next]=type;}
    current=next;change(values);check();
   };
   nameCell.append(name);
   const fixed=formSelect([['','动态（不限制）'],...Object.entries(VariableTypes.labels)],contracts[key]||'',title+' '+key+' 固定类型');fixed.disabled=!editable;
   const check=()=>{const type=contracts[current],has=Object.hasOwn(values,current);state.textContent=!has?'缺少值':!type?'动态类型':VariableTypes.matches(values[current],type)?'符合类型':'类型不匹配';state.className=!has||(type&&!VariableTypes.matches(values[current],type))?'error':'';};
   fixed.onchange=()=>{if(fixed.value)contracts[current]=fixed.value;else delete contracts[current];change(values);check();};contractCell.append(fixed);
   if(Object.hasOwn(values,key))valueCell.append(valueEditor(values[key],next=>{values[current]=next;change(values);check();},{label:title+' '+key,refs:false,typeCell}));
   else{typeCell.textContent='—';const supply=formEl('button','补充值');supply.type='button';supply.onclick=()=>{const type=contracts[current];values[current]=type?.endsWith('[]')?[]:type==='integer'?0:structuredClone(formDefaults[type]??'');if(type==='null')values[current]=null;change(values);redraw();};valueCell.append(supply);}
   const remove=formEl('button','删除');remove.type='button';remove.disabled=!editable&&Object.hasOwn(contracts,key);remove.title=remove.disabled?'请先在工程初始定义中解除固定类型':'';
   remove.onclick=()=>{delete values[current];if(editable)delete contracts[current];change(values);redraw();};actions.append(remove);
   check();row.append(nameCell,typeCell,contractCell,valueCell,state,actions);table.append(row);
  }
  cursor+=50;more.hidden=cursor>=names.length;
 };
 more.onclick=append;append();
 const add=formEl('button','新增变量');add.type='button';add.onclick=()=>{let i=1;while(Object.hasOwn(values,'field'+i)||Object.hasOwn(contracts,'field'+i))i++;values['field'+i]='';change(values);redraw();};
 holder.append(table,more,add);
 if(!editable)holder.append(formEl('p','固定类型在“工程初始定义”中修改；当前页可修改值。','muted'));
}
function renderVariableOverview(){
 const holder=$('variable-sections');holder.replaceChildren();
 const controls=formEl('div',undefined,'variable-toolbar'),search=formEl('input');search.type='search';search.placeholder='搜索变量或模块名称';search.setAttribute('aria-label','搜索变量');
 const scopes=[{id:'global',label:'全局变量',values:variableSnapshot.global,initial:{},types:variableSnapshot.globalTypes||{}},
  {id:'flow',label:'流程变量',values:variableSnapshot.flow,initial:project.variables||{},types:project.variableTypes||{}},
  ...project.steps.map(step=>({id:'module:'+step.id,label:'模块 · '+flowName(step.id),values:variableSnapshot.modules[step.id]||{},initial:step.variables||{},types:step.variableTypes||{}}))];
 const filter=formSelect([['','全部作用域'],...scopes.map(s=>[s.id,s.label])],'','变量作用域筛选');controls.append(search,filter);holder.append(controls);
 const wrap=formEl('div',undefined,'variable-overview-scroll'),table=formEl('table',undefined,'form-table variable-overview'),head=formEl('thead'),row=formEl('tr'),body=formEl('tbody'),summary=formEl('p',undefined,'muted');table.setAttribute('aria-label','所有变量定义与当前值');
 for(const title of ['作用域 / 模块','变量名称','固定类型','工程初始值','运行当前值','校验状态','操作'])row.append(formEl('th',title));head.append(row);table.append(head,body);wrap.append(table);holder.append(summary,wrap);
 const more=formEl('button','显示更多变量');more.type='button';holder.append(more);let visible=50;
 const edit=(scope,mode)=>{ $('variable-mode').value=mode;renderVariableForms();Array.from(holder.querySelectorAll('.variable-scope-section')).find(el=>el.dataset.scope===scope.id)?.scrollIntoView({block:'start'}); };
 const draw=()=>{
  body.replaceChildren();const query=search.value.trim().toLocaleLowerCase();const entries=scopes.flatMap(scope=>[...new Set([...Object.keys(scope.initial),...Object.keys(scope.values),...Object.keys(scope.types)])].map(name=>({scope,name})));
  const matching=entries.filter(({scope,name})=>(!filter.value||scope.id===filter.value)&&(!query||(scope.label+' '+name).toLocaleLowerCase().includes(query)));
  for(const {scope,name} of matching.slice(0,visible)){
   const row=formEl('tr'),initial=formEl('td'),current=formEl('td'),actions=formEl('td'),has=Object.hasOwn(scope.values,name),type=scope.types[name];
   initial.append(Object.hasOwn(scope.initial,name)?resultValueView(scope.initial[name]):formEl('span',scope.id==='global'?'全局持久值':'未定义','muted'));
   current.append(has?resultValueView(scope.values[name]):formEl('span','尚无当前值','muted'));
   const state=type?(!has?'缺少当前值':VariableTypes.matches(scope.values[name],type)?'符合类型':'类型不匹配'):'动态类型';
   const status=formEl('td',state,type&&(!has||!VariableTypes.matches(scope.values[name],type))?'error':'');
   const change=formEl('button','编辑当前值');change.type='button';change.setAttribute('aria-label',scope.label+' '+name+' 编辑当前值');change.onclick=()=>edit(scope,'current');actions.append(change);
   if(scope.id!=='global'){const define=formEl('button','编辑定义');define.type='button';define.setAttribute('aria-label',scope.label+' '+name+' 编辑定义');define.onclick=()=>edit(scope,'initial');actions.append(define);}
   row.append(formEl('td',scope.label),formEl('th',name),formEl('td',VariableTypes.labels[type]||'动态'),initial,current,status,actions);body.append(row);
  }
  summary.textContent='共 '+entries.length+' 个变量 · 筛选 '+matching.length+' 个 · 显示 '+Math.min(visible,matching.length)+' 个；当前值为最近读取的快照。';more.hidden=visible>=matching.length;
  if(!matching.length){const row=formEl('tr'),cell=formEl('td',entries.length?'没有匹配的变量':'尚未定义变量。切换到“工程初始定义”或“运行当前值”添加。','muted');cell.colSpan=7;row.append(cell);body.append(row);}
 };
 search.oninput=filter.onchange=()=>{visible=50;draw();};more.onclick=()=>{visible+=50;draw();};draw();
}
function showVariables(snapshot){
  variableRevision=snapshot.revision;variableSnapshot={...snapshot,projectId:project.id};
  variableDraft=structuredClone({global:snapshot.global,flow:snapshot.flow,modules:snapshot.modules,globalTypes:snapshot.globalTypes||{}});
  initialDraft={flow:structuredClone(project.variables||{}),modules:Object.fromEntries(project.steps.map(step=>[step.id,structuredClone(step.variables||{})]))};
  variableTypeDraft={flow:structuredClone(project.variableTypes||{}),modules:Object.fromEntries(project.steps.map(step=>[step.id,structuredClone(step.variableTypes||{})]))};
  renderVariableForms();
  refreshAvailableVariables();
}
function renderVariableForms(){
  const overview=$('variable-mode').value==='overview';$('variables-save').hidden=overview;
  if(overview){$('variable-mode-hint').textContent='查看已应用的工程定义和最近读取的运行值；未提交的修改保留在编辑页。数组、结构体及结构化文本展开为表格；编辑按钮进入对应作用域。';if(variableDraft)renderVariableOverview();return;}
  const initial=$('variable-mode').value==='initial',draft=initial?initialDraft:variableDraft;
  if(!draft)return;
  $('variables-save').textContent=initial?'应用初始定义到工程':'写入当前值';
  $('variable-mode-hint').textContent=initial?'定义流程与模块的初始值及固定类型；无保存值时使用初始值。类型为“动态”时兼容原有行为。应用后请保存工程。全局类型在“运行当前值”中管理。':'查看和修改三级变量；数组和结构体逐项编辑。固定类型会阻止错误赋值，不自动转换文本/数字。流程与模块类型在“工程初始定义”中修改。删除当前值时恢复工程初始值；全局固定类型变量须先解除约束才能删除。';
  const holder=$('variable-sections');holder.replaceChildren();
  const section=(title,values,set,contracts,editable,scope)=>{
    const box=formEl('section',undefined,'variable-scope-section');box.dataset.scope=scope;box.append(formEl('h3',title));const editor=formEl('div');
    variableDefinitionEditor(editor,values,contracts,{title,editable,change:set});box.append(editor);holder.append(box);
  };
  if(!initial)section('全局变量',draft.global,v=>draft.global=v,draft.globalTypes,true,'global');
  section('流程变量',draft.flow,v=>draft.flow=v,initial?variableTypeDraft.flow:(project.variableTypes||{}),initial,'flow');
  for(const step of project.steps)section('模块变量 · '+flowName(step.id),draft.modules[step.id]||{},v=>draft.modules[step.id]=v,initial?variableTypeDraft.modules[step.id]:(step.variableTypes||{}),initial,'module:'+step.id);
}
function initRuntimeUI(){
  const codeSection=$('script-code').closest('details');codeSection.open=false;codeSection.classList.add('script-source');$('script-tools').append(codeSection);
  $('script-code').oninput=()=>{const step=selectedStep();if(step?.operation!=='script'||running)return;step.params.code=$('script-code').value;dirty();};
  $('script-code').onkeydown=e=>{if(e.key==='Tab'){e.preventDefault();const input=e.target,start=input.selectionStart,end=input.selectionEnd;input.setRangeText('    ',start,end,'end');input.dispatchEvent(new Event('input'));}};
  $('variables-open').onclick=safe(async()=>{if(running)return;applyParams();showVariables(await api('runtime/variables/read',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({project:currentProject()})}));$('variables-dialog').showModal();});
  $('variable-mode').onchange=renderVariableForms;
  $('variables-refresh').onclick=safe(async()=>{showVariables(await api('runtime/variables/read',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({project:currentProject()})}));status('已重新读取服务器变量，未提交的编辑已撤销','success');});
  $('variables-save').onclick=safe(async()=>{
    if(running||variableRevision===null)return;
    const invalid=$('variables-dialog').querySelector('input:invalid,select:invalid');if(invalid){invalid.reportValidity();throw Error('请修正变量表中的无效输入');}
    if($('variable-mode').value==='initial'){
      const candidate=structuredClone(project);candidate.variables=structuredClone(initialDraft.flow);candidate.variableTypes=structuredClone(variableTypeDraft.flow);
      for(const step of candidate.steps){step.variables=structuredClone(initialDraft.modules[step.id]||{});step.variableTypes=structuredClone(variableTypeDraft.modules[step.id]||{});}
      const normalized=FlowGraph.normalize(candidate);project.variables=normalized.variables;project.variableTypes=normalized.variableTypes;
      for(const step of project.steps){const definition=normalized.steps.find(s=>s.id===step.id);step.variables=definition.variables;step.variableTypes=definition.variableTypes;}
      dirty();refreshAvailableVariables();status('初始定义已应用，请保存工程以保留','success');return;
    }
    const saved=await api('runtime/variables',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({project:currentProject(),values:variableDraft,revision:variableRevision})});
    variableRevision=saved.revision;variableSnapshot={...saved,projectId:project.id};variableDraft=structuredClone({global:saved.global,flow:saved.flow,modules:saved.modules,globalTypes:saved.globalTypes||{}});renderVariableForms();refreshAvailableVariables();status('三级变量及全局类型已写入运行平台','success');
  });
}
