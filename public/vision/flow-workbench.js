'use strict';
const flowSelection=new Set(),flowHistory=new FlowEdit.History();
let flowClipboard=null,flowHistoryReady=false,flowRestoring=false,flowPasteOffset=40;
function flowEditingBusy(){return running||!!$('flow-layout')?.disabled;}
function flowEditReset(){flowHistory.reset(project);flowHistoryReady=true;flowSelection.clear();flowClipboard=null;flowEditButtons();}
function flowEditRecord(){if(flowHistoryReady&&!flowRestoring){flowHistory.record(project);flowEditButtons();}}
function flowSelectedIds(){return flowSelection.size?[...flowSelection]:selectedStep()?[selectedStep().id]:[];}
function flowEditButtons(){
  for(const [id,disabled] of [['undo',!flowHistory.canUndo],['redo',!flowHistory.canRedo],['copy',!flowSelectedIds().length],['paste',!flowClipboard],['delete',!flowSelectedIds().length]]){
    const button=$('flow-'+id);if(button)button.disabled=flowEditingBusy()||disabled;
  }
  document.querySelectorAll('#pipeline .step').forEach(el=>el.classList.toggle('multi-selected',flowSelection.has(el.dataset.nodeId)));
}
function flowUndo(redo=false){
  if(flowEditingBusy()||!(redo?flowHistory.canRedo:flowHistory.canUndo))return;
  flowRestoring=true;
  try{
    project=redo?flowHistory.redo():flowHistory.undo();selected=Math.min(selected,project.steps.length-1);flowSelection.clear();flowEdge=null;flowLink=null;
    framePreviews.clear();bindingResultFields.clear();$('project-name').value=project.name;dirty();renderPipeline();renderParams();
    status(redo?'已重做编辑':'已撤销编辑');
  }finally{flowRestoring=false;flowEditButtons();}
}
function flowCopy(){if(flowEditingBusy())return;applyParams();flowClipboard=FlowEdit.copy(project,flowSelectedIds());flowPasteOffset=40;flowEditButtons();status('已复制 '+flowClipboard.steps.length+' 个模块（含参数、内部连线和上游引用）');}
function flowPaste(){
  if(flowEditingBusy())return;applyParams();const pasted=FlowEdit.paste(project,flowClipboard,uid,flowPasteOffset);flowPasteOffset+=40;
  flowSelection.clear();pasted.ids.forEach(id=>flowSelection.add(id));selected=pasted.project.steps.findIndex(s=>s.id===pasted.ids[0]);
  flowCommit(pasted.project,'已粘贴模块；输出变量绑定沿用原配置，请按需修改');
}
function flowDelete(){
  if(flowEditingBusy())return;applyParams();
  if(flowEdge){flowCommit(FlowGraph.disconnect(project,flowEdge),'连线已删除');return;}
  const ids=flowSelectedIds();if(!ids.length)return;
  const next=FlowEdit.remove(project,ids);flowSelection.clear();selected=Math.min(selected,next.steps.length-1);flowCommit(next,'已删除 '+ids.length+' 个模块及关联连线');
}
function flowSelect(id,toggle=false){
  if(!toggle)flowSelection.clear();
  if(toggle&&flowSelection.has(id))flowSelection.delete(id);else flowSelection.add(id);
  selected=project.steps.findIndex(s=>s.id===(flowSelection.has(id)?id:[...flowSelection].at(-1)));flowEditButtons();
}
function flowRename(){
  const step=selectedStep();if(!step||flowEditingBusy())return;
  const dialog=$('flow-name-dialog'),input=$('flow-node-name');input.value=step.name||stepDefinition(step).name;
  dialog.dataset.nodeId=step.id;dialog.showModal();input.focus();input.select();
}
function flowContext(event){
  const node=event.target.closest('.step'),edge=event.target.closest('.flow-edge');
  if(!node&&!edge)return;event.preventDefault();if(flowEditingBusy())return;
  if(node){if(!flowSelection.has(node.dataset.nodeId))flowSelect(node.dataset.nodeId);selected=project.steps.findIndex(s=>s.id===node.dataset.nodeId);flowEdge=null;flowUpdateSelection();renderParams();}
  else{flowEdge=edge.dataset.edgeId;flowLink=null;flowUpdateSelection();}
  const menu=$('flow-context');menu.replaceChildren();
  const actions=node?[['配置模块',()=>openParameters()],['重命名',flowRename],['复制模块',flowCopy],['粘贴模块',flowPaste],['删除模块',flowDelete]]:
    [['在连线上插入模块',()=>status('已选择插入位置，请点击工具箱中的算子；Esc 取消')],['断开连线',flowDelete]];
  for(const [label,action]of actions){const b=document.createElement('button');b.textContent=label;b.setAttribute('role','menuitem');b.disabled=label==='粘贴模块'&&!flowClipboard;b.onclick=safe(()=>{menu.hidden=true;action();});menu.append(b);}
  menu.hidden=false;menu.style.left=Math.max(4,Math.min(event.clientX,innerWidth-200))+'px';menu.style.top=Math.max(4,Math.min(event.clientY,innerHeight-menu.offsetHeight-8))+'px';menu.querySelector('button')?.focus();
}
function flowWorkbenchInit(){
  const tools=document.querySelector('.flow-tools');
  const bar=document.createElement('div');bar.className='flow-edit-tools';bar.setAttribute('aria-label','流程编辑操作');
  for(const [id,label,title,action]of [['undo','撤销','Ctrl+Z',()=>flowUndo()],['redo','重做','Ctrl+Y',()=>flowUndo(true)],['copy','复制','Ctrl+C',flowCopy],['paste','粘贴','Ctrl+V',flowPaste],['delete','删除','Delete',flowDelete]]){
    const b=document.createElement('button');b.id='flow-'+id;b.textContent=label;b.title=label+' · '+title;b.onclick=safe(action);bar.append(b);
  }
  tools.after(bar);
  const menu=document.createElement('div');menu.id='flow-context';menu.className='flow-context';menu.hidden=true;menu.setAttribute('role','menu');document.body.append(menu);
  const dialog=document.createElement('dialog');dialog.id='flow-name-dialog';dialog.setAttribute('aria-label','重命名模块');
  const form=document.createElement('form'),label=document.createElement('label'),input=document.createElement('input'),save=document.createElement('button'),cancel=document.createElement('button');
  label.textContent='模块名称';input.id='flow-node-name';input.required=true;input.maxLength=80;input.setAttribute('aria-label','模块名称');label.append(input);
  save.textContent='保存名称';save.type='submit';cancel.type='button';cancel.textContent='取消';cancel.onclick=()=>dialog.close();form.append(label,save,cancel);dialog.append(form);document.body.append(dialog);
  form.onsubmit=safe(e=>{e.preventDefault();if(flowEditingBusy())return;const step=project.steps.find(s=>s.id===dialog.dataset.nodeId);if(!step)return;const name=input.value.trim();if(!name)throw Error('请输入模块名称');step.name=name;dirty();renderPipeline();renderParams();dialog.close();});
  document.querySelector('.flow-viewport').addEventListener('contextmenu',safe(flowContext));
  const viewport=document.querySelector('.flow-viewport');let selectionBox=null;
  viewport.addEventListener('pointerdown',e=>{
    if(flowEditingBusy()||!e.shiftKey||e.button!==0||e.target.closest('.step,.flow-source,.flow-edge'))return;
    e.preventDefault();const element=document.createElement('div');element.className='flow-selection-box';$('pipeline').append(element);
    selectionBox={start:flowPoint(e),element};viewport.setPointerCapture(e.pointerId);
  });
  viewport.addEventListener('pointermove',e=>{
    if(!selectionBox)return;const point=flowPoint(e),start=selectionBox.start;
    const rect={x:Math.min(start.x,point.x),y:Math.min(start.y,point.y),width:Math.abs(point.x-start.x),height:Math.abs(point.y-start.y)};selectionBox.rect=rect;
    Object.assign(selectionBox.element.style,{left:rect.x+'px',top:rect.y+'px',width:rect.width+'px',height:rect.height+'px'});
  });
  viewport.addEventListener('pointerup',()=>{
    if(!selectionBox)return;const rect=selectionBox.rect;selectionBox.element.remove();selectionBox=null;
    if(rect){flowSelection.clear();for(const step of project.steps)if(step.position.x<rect.x+rect.width&&step.position.x+200>rect.x&&step.position.y<rect.y+rect.height&&step.position.y+72>rect.y)flowSelection.add(step.id);selected=project.steps.findIndex(s=>flowSelection.has(s.id));flowEdge=null;flowEditButtons();renderParams();}
  });
  viewport.addEventListener('pointercancel',()=>{selectionBox?.element.remove();selectionBox=null;});
  document.addEventListener('pointerdown',e=>{if(!menu.contains(e.target))menu.hidden=true;});
  document.addEventListener('keydown',safe(e=>{
    if(e.defaultPrevented)return;
    if(e.key==='Escape')menu.hidden=true;
    if(flowEditingBusy()||e.target.closest('input,textarea,select,[contenteditable="true"]')||document.querySelector('dialog[open]'))return;
    const inFlow=e.target.closest('.flow-panel,.flow-context');if(!inFlow)return;
    const key=e.key.toLowerCase(),control=e.ctrlKey||e.metaKey;
    if(control&&['z','y','c','v','a'].includes(key)){
      e.preventDefault();
      if(key==='z')flowUndo(e.shiftKey);else if(key==='y')flowUndo(true);else if(key==='c')flowCopy();else if(key==='v')flowPaste();
      else{flowSelection.clear();project.steps.forEach(s=>flowSelection.add(s.id));flowEditButtons();}
    }else if(e.key==='Delete'&&!flowEdge){e.preventDefault();flowDelete();}else if(e.key==='F2'){e.preventDefault();flowRename();}
  }));
  flowEditReset();
}
