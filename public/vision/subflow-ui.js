'use strict';
let subflowWorkspace=null;
function subflowProjectForSave(){
 const current=currentProject();if(!subflowWorkspace)return current;
 const next=clone(subflowWorkspace.root),definition=clone(current);delete definition.subflows;definition.id=subflowWorkspace.id;
 next.subflows=next.subflows.map(d=>d.id===definition.id?definition:d);const valid=FlowGraph.normalize(next);subflowWorkspace.root=clone(valid);return valid;
}
function subflowProjectForExecution(value){if(!subflowWorkspace)return value;const next=clone(value),definition=clone(value);delete definition.subflows;definition.id=subflowWorkspace.id;next.subflows=next.subflows.map(d=>d.id===definition.id?definition:d);return next;}
function subflowWorkspaceCheck(value){if(subflowWorkspace&&value.id!=='edit-'+subflowWorkspace.id.slice(0,75))throw Error('请先返回主流程，再打开其他工程或演示');return value;}
function subflowWorkspaceControls(busy=running){
 if(!$('subflows-open'))return;$('subflows-open').disabled=busy||!!subflowWorkspace;
 document.querySelectorAll('#subflow-manager input,#subflow-manager button').forEach(el=>el.disabled=busy||el.dataset.used==='true');
 $('subflow-return').disabled=busy;$('subflow-output').disabled=busy;
 if(subflowWorkspace)for(const id of ['sample','load-project','import-project','return-demo','hmi-open','continuous-open'])$(id).disabled=true;
}
function subflowWorkspaceRender(){
 if(!$('subflow-workspace'))return;$('subflow-workspace').hidden=!subflowWorkspace;if(!subflowWorkspace)return;
 $('subflow-editing-name').textContent='正在编辑子流程：'+project.name+' · 修改随主工程保存';const output=$('subflow-output');output.replaceChildren(new Option('请选择输出节点',''),...project.steps.map((s,i)=>new Option((i+1)+' · '+stepDefinition(s).name,s.id)));if(!project.steps.some(s=>s.id===project.outputNode))project.outputNode=project.steps.at(-1)?.id||null;output.value=project.outputNode||'';subflowWorkspaceControls();
}
function renderSubflowParams(step){
 const holder=$('structured-params');holder.replaceChildren();
 const label=formEl('label','子流程定义','field'),choices=(project.subflows||[]).filter(d=>d.id!==subflowWorkspace?.id),select=formSelect([['','请选择子流程'],...choices.map(d=>[d.id,d.name])],step.params.subflowId||'','调用子流程定义');select.onchange=()=>{step.params.subflowId=select.value;dirty();};label.append(select);holder.append(label);
 const choice=(key,name,options,fallback)=>{const row=formEl('label',name,'field'),input=formSelect(options,step.params[key]??fallback,name);input.onchange=()=>{step.params[key]=input.value;dirty();renderParams();};row.append(input);holder.append(row);};
 choice('stateMode','调用间变量状态',[['reset','每次调用重置'],['preserve','保留该调用点上次状态']],'reset');
 if(step.operation==='loop'){
  choice('mode','循环方式',[['count','固定次数'],['until','满足条件后停止']],'count');
  const row=formEl('div');row.append(formEl('label','循环次数 / 最大轮数（1–100）','section-caption'));
  const bound=formType(step.params.iterations)==='reference',sourceType=formSelect([['fixed','固定数值'],['binding','变量 / 结果绑定']],bound?'binding':'fixed','循环次数来源');sourceType.onchange=()=>{step.params.iterations=sourceType.value==='binding'?{$ref:'flow.'}:1;dirty();renderParams();};row.append(sourceType);
  if(bound)row.append(referenceEditor(step.params.iterations,next=>{step.params.iterations=next;dirty();},'循环次数'));else{const count=formEl('input');count.type='number';count.min=1;count.max=100;count.step=1;count.required=true;count.value=typeof(step.params.iterations??1)==='number'?(step.params.iterations??1):'';count.setAttribute('aria-label','循环次数');count.oninput=()=>{if(count.checkValidity()){step.params.iterations=Number(count.value);dirty();}};row.append(count);}holder.append(row);
  choice('frameMode','每轮输入数据',[['previous','上一轮输出'],['original','本次调用的原始输入']],'previous');
  if(step.params.mode==='until'){
   const field=formEl('label','输出中的停止字段','field'),input=formEl('input');input.value=step.params.stopField??'passed';input.setAttribute('aria-label','循环停止结果字段');input.onchange=()=>{step.params.stopField=input.value.trim();dirty();};field.append(input);holder.append(field);
   const stop=formEl('label','字段达到此开关值时停止','field'),value=formSelect([['true','是'],['false','否']],String(step.params.stopValue??true),'循环停止开关值');value.onchange=()=>{step.params.stopValue=value.value==='true';dirty();};stop.append(value);holder.append(stop);
  }
 }
 holder.append(formEl('label','输入变量（写入子流程局部作用域）','section-caption'));const args=formEl('div');holder.append(args);collectionEditor(args,step.params.arguments??{},next=>{step.params.arguments=next;dirty();},{label:'子流程输入变量'});
 holder.append(formEl('p','在“子流程管理”中编辑节点和输出。子流程内 flow._iteration / flow._iterations 为轮次及上限；主流程使用本节点结果 value、variables、iterations 和 trace 查看结果。','muted'));
}
function initSubflowUI(){
 const button=formEl('button','子流程管理');button.id='subflows-open';$('help').before(button);
 const banner=formEl('section');banner.id='subflow-workspace';banner.hidden=true;banner.innerHTML='<strong id="subflow-editing-name"></strong><label>输出节点<select id="subflow-output" aria-label="子流程输出节点"></select></label><button id="subflow-return">返回主流程</button>';document.querySelector('main').before(banner);
 $('subflow-output').onchange=()=>{project.outputNode=$('subflow-output').value||null;dirty();};
 $('subflow-return').onclick=safe(async()=>{
  if(running||!subflowWorkspace)return;const saved=subflowWorkspace,next=subflowProjectForSave();subflowWorkspace=null;useProject(next);selected=Math.min(saved.selected,project.steps.length-1);if(saved.source)await loadImage(saved.source);else{source='';originalImage=null;ctx.clearRect(0,0,canvas.width,canvas.height);$('empty-image').hidden=false;}sourceCloud=saved.cloud;sourceDepth=saved.depth||null;results=[];renderPipeline();renderParams();renderResults();subflowWorkspaceRender();setBusy(false);dirty();status('已返回主流程；请保存工程以持久保存子流程定义','success');
 });
 const dialog=formEl('dialog');dialog.id='subflow-manager';dialog.setAttribute('aria-label','子流程管理');dialog.innerHTML='<header><h2>子流程管理</h2><button id="subflow-manager-close" aria-label="关闭子流程管理">×</button></header><p>每个定义可多处调用。进入编辑后使用原有拖拽画布和参数表单；选择输出节点，返回主流程后保存。调用点的局部变量相互独立，全局变量随整轮主流程提交。</p><label>新定义名称<input id="subflow-new-name" aria-label="新子流程名称" maxlength="80"></label><button id="subflow-new">新建子流程</button><div id="subflow-definitions"></div><p id="subflow-manager-message" role="status"></p>';document.body.append(dialog);
 const draw=()=>{const holder=$('subflow-definitions');holder.replaceChildren();const table=formEl('table',undefined,'form-table'),head=formEl('tr');for(const text of ['名称','节点数','输出节点','操作'])head.append(formEl('th',text));table.append(head);
  for(const definition of project.subflows||[]){const row=formEl('tr'),name=formEl('input');name.value=definition.name;name.maxLength=80;name.setAttribute('aria-label','子流程 '+definition.name+' 名称');name.onchange=()=>{if(!name.value.trim()){name.value=definition.name;return;}definition.name=name.value.trim();dirty();};const cell=formEl('td');cell.append(name);const actions=formEl('td'),edit=formEl('button','编辑流程'),remove=formEl('button','删除定义');edit.setAttribute('aria-label','编辑子流程 '+definition.name);
   edit.onclick=safe(()=>{applyParams();const snapshot=clone(project);subflowWorkspace={root:snapshot,id:definition.id,selected,source,cloud:clone(sourceCloud),depth:clone(sourceDepth)};const working=clone(definition);working.id='edit-'+definition.id.slice(0,75);working.subflows=clone(snapshot.subflows);dialog.close();useProject(working);subflowWorkspaceRender();setBusy(false);status('子流程编辑：拖入算子并连线，选择输出节点，然后返回主流程');});
   const used=[...project.steps,...(project.subflows||[]).flatMap(d=>d.steps)].some(s=>['loop','subflow'].includes(s.operation)&&s.params.subflowId===definition.id);remove.disabled=used;remove.dataset.used=String(used);remove.title=used?'已有调用，先移除或修改调用节点':'';remove.onclick=()=>{project.subflows=project.subflows.filter(d=>d.id!==definition.id);dirty();draw();};actions.append(edit,remove);row.append(cell,formEl('td',definition.steps.length),formEl('td',definition.steps.find(s=>s.id===definition.outputNode)?.operation||'待选择'),actions);table.append(row);
  }holder.append(table);
 };
 button.onclick=safe(()=>{if(subflowWorkspace)throw Error('请先返回主流程');applyParams();draw();dialog.showModal();});$('subflow-manager-close').onclick=()=>{dialog.close();renderParams();};
 $('subflow-new').onclick=safe(()=>{const name=$('subflow-new-name').value.trim();if(!name)throw Error('请填写子流程名称');if((project.subflows||[]).length>=20)throw Error('最多 20 个子流程定义');project.subflows??=[];project.subflows.push({version:2,id:'sub-'+uid(),name,steps:[],edges:[],variables:{},outputNode:null});$('subflow-new-name').value='';dirty();draw();});
}
