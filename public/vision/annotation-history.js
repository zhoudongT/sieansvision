'use strict';
function annotationHistoryControls(){if($('annotation-history-open'))$('annotation-history-open').disabled=annotationSession?.busy||!annotationSession?.frame;document.querySelectorAll('#annotation-history-dialog button').forEach(button=>button.disabled=annotationSession?.busy||button.dataset.invalid==='true');}
function initAnnotationHistory(){
 const open=formEl('button','标注历史');open.id='annotation-history-open';$('annotation-reload').after(open);
 const dialog=formEl('dialog');dialog.id='annotation-history-dialog';dialog.setAttribute('aria-label','标注历史版本');dialog.innerHTML='<header class="annotation-header"><h2>标注历史版本</h2><button id="annotation-history-close" aria-label="关闭标注历史">×</button></header><p>每次覆盖保存前保留旧版本。载入历史只修改当前编辑内容，可撤销；确认后点击“保存标注”才写入文件，当前已保存版本也会备份。</p><p id="annotation-history-image"></p><div id="annotation-history-entries"></div><p id="annotation-history-status" role="status"></p>';document.body.append(dialog);
 $('annotation-history-close').onclick=()=>{if(!annotationSession.busy)dialog.close();};dialog.addEventListener('cancel',event=>{event.preventDefault();$('annotation-history-close').click();});
 open.onclick=()=>annotationAction(async()=>{
  annotationGuard();const s=annotationSession;if(!s.frame)throw Error('请先选择图片');$('annotation-history-image').textContent=s.frame.name;$('annotation-history-status').textContent='正在读取历史…';$('annotation-history-entries').replaceChildren();dialog.showModal();
  try{
   const base={name:s.frame.name,split:s.frame.split,revision:s.frame.revision},response=await annotationApi('history',base),table=formEl('table',undefined,'form-table'),head=formEl('tr');for(const name of ['版本时间','目标数量','状态','操作'])head.append(formEl('th',name));table.append(head);
   for(const entry of response.entries){const row=formEl('tr'),cell=formEl('td'),load=formEl('button','载入到编辑器');load.dataset.invalid=String(!entry.valid);load.disabled=!entry.valid;load.setAttribute('aria-label','载入历史版本 '+(response.entries.indexOf(entry)+1));load.onclick=()=>annotationAction(async()=>{
    try{annotationGuard();const restored=await annotationApi('history_load',{...base,historyId:entry.id});annotationChange();s.records=structuredClone(restored.records);s.selected=s.records.length?0:-1;s.draft=[];annotationAssistReset();annotationRenderRecords();annotationDraw();dialog.close();renderDataMessage($('annotation-status'),'历史版本已载入，尚未保存；可调整或撤销，确认后保存标注。');}catch(error){renderDataMessage($('annotation-history-status'),error.message);}
   });cell.append(load);row.append(formEl('td',new Date(entry.createdAt).toLocaleString()),formEl('td',entry.objects??'—'),formEl('td',entry.valid?(entry.objects?'可载入':'背景标注'):entry.error),cell);table.append(row);}
   $('annotation-history-entries').append(table);$('annotation-history-status').textContent=response.entries.length?(response.limitReached?'仅显示最近 200 个版本，其他备份仍保留在服务器。':'共 '+response.entries.length+' 个历史版本。'):'暂无历史版本；首次保存后再次修改并保存，会保留覆盖前的版本。';
  }catch(error){renderDataMessage($('annotation-history-status'),error.message);}
 });
}
