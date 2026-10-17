'use strict';
let hmiDocument=null,hmiEditorPageId='',hmiRuntimePageId='',hmiRuntimePageProject='',hmiRuntimeRenderedSignature='';
function hmiPagesOpen(value){hmiDocument=HmiLayout.document(value);hmiEditorPageId=hmiDocument.pages.some(p=>p.id===hmiRuntimePageId)?hmiRuntimePageId:hmiDocument.defaultPageId;hmiDraft=hmiDocument.pages.find(p=>p.id===hmiEditorPageId);}
function hmiPagesCommitCurrent(){
 const invalid=$('hmi-editor').querySelector('input:invalid');if(invalid){invalid.reportValidity();throw Error('请修正画面属性后再切页或应用');}
 Object.assign(hmiDraft,HmiLayout.normalizePage({...hmiDraft,title:$('hmi-page-title').value,rows:Number($('hmi-rows').value),rowHeight:Number($('hmi-row-height').value)}));
 if(!hmiDraft.title.trim())throw Error('页面标题不能为空');
}
function hmiPagesRenderEditor(){
 if(!hmiDocument||!$('hmi-edit-page'))return;
 const select=$('hmi-edit-page');select.replaceChildren(...hmiDocument.pages.map(p=>new Option(p.title+(p.id===hmiDocument.defaultPageId?' · 默认':''),p.id)));select.value=hmiEditorPageId;
 $('hmi-document-title').value=hmiDocument.title;const index=hmiDocument.pages.findIndex(p=>p.id===hmiEditorPageId);
 $('hmi-page-up').disabled=index===0;$('hmi-page-down').disabled=index===hmiDocument.pages.length-1;
 const used=hmiDocument.pages.filter(p=>p.id!==hmiEditorPageId).some(p=>p.components.some(c=>c.action==='navigate'&&c.targetPageId===hmiEditorPageId));$('hmi-page-delete').disabled=hmiDocument.pages.length===1||used;$('hmi-page-delete').title=used?'其他页面的跳转按钮仍引用此页':'';
 $('hmi-page-count').textContent=hmiDocument.pages.length+' / 20 页 · '+HmiLayout.allComponents(hmiDocument).length+' / 200 个组件';
}
function hmiPagesSelectEditor(id){hmiEditorPageId=id;hmiDraft=hmiDocument.pages.find(p=>p.id===id);hmiSelection=hmiDraft.components[0]?.id||'';hmiRenderEditor();}
function hmiPagesReplaceDraft(value){hmiDraft={id:hmiEditorPageId,...value};hmiDocument.pages[hmiDocument.pages.findIndex(p=>p.id===hmiEditorPageId)]=hmiDraft;}
function hmiPagesCheckAddition(type){if(HmiLayout.allComponents(hmiDocument).length>=200)throw Error('所有页面合计最多 200 个组件');if(['alarm','trend'].includes(type)&&HmiLayout.allComponents(hmiDocument).filter(c=>['alarm','trend'].includes(c.type)).length>=50)throw Error('整个工程最多 50 个报警与趋势组件');}
function hmiPagesMoveComponent(c,id){
 hmiPagesCommitCurrent();const target=hmiDocument.pages.find(p=>p.id===id);if(!target||target===hmiDraft)return;if(target.components.length>=50)throw Error('目标页面已有 50 个组件');if(c.h>target.rows)throw Error('组件高度超过目标页行数，请先调整尺寸');
 hmiDraft.components=hmiDraft.components.filter(v=>v.id!==c.id);target.components.push({...c,x:Math.min(c.x,12-c.w),y:Math.min(c.y,target.rows-c.h)});hmiPagesSelectEditor(target.id);hmiSelection=c.id;hmiSelectCards();hmiProperties();hmiComponentList();
}
function hmiRuntimePagesRender(){
 const layout=project.hmi,pages=HmiLayout.pages(layout);if(!pages.length)return;
 if(hmiRuntimePageProject!==project.id){hmiRuntimePageProject=project.id;let remembered='';try{remembered=sessionStorage.getItem('sieans.hmi.page.'+project.id)||'';}catch{}const requested=new URL(location.href).searchParams.get('page');hmiRuntimePageId=pages.some(p=>p.id===requested)?requested:remembered;}
 if(!pages.some(p=>p.id===hmiRuntimePageId))hmiRuntimePageId=layout.defaultPageId||pages[0].id;
 const page=pages.find(p=>p.id===hmiRuntimePageId),nav=$('hmi-page-tabs');nav.replaceChildren();nav.hidden=pages.length<2;
 for(const p of pages){const button=formEl('button',p.title);button.id='hmi-page-tab-'+p.id;button.type='button';button.setAttribute('role','tab');button.setAttribute('aria-label',p.title);button.setAttribute('aria-selected',String(p.id===page.id));button.setAttribute('aria-controls','hmi-runtime-canvas');const badge=formEl('small',undefined,'hmi-page-alarm-badge');badge.setAttribute('aria-hidden','true');button.append(badge);button.onclick=safe(()=>hmiNavigatePage(p.id));nav.append(button);}
 $('hmi-title').textContent=layout.version===2?layout.title+' · '+page.title:layout.title;hmiPagesUpdateAlarmBadges();const signature=JSON.stringify([project.id,page]);if(signature===hmiRuntimeRenderedSignature&&hmiViews.has('hmi-runtime-canvas'))return;hmiRuntimeRenderedSignature=signature;hmiRenderSurface($('hmi-runtime-canvas'),page,false);
 if(!page.components.length)$('hmi-runtime-canvas').append(formEl('p','当前页面暂无组件','hmi-empty'));
}
function hmiPagesUpdateAlarmBadges(){for(const page of HmiLayout.pages(project.hmi)){const button=document.getElementById('hmi-page-tab-'+page.id),badge=button?.querySelector('.hmi-page-alarm-badge');if(!badge)continue;const count=HmiLayout.alarmCount(page,hmiState.monitor);badge.hidden=!count;badge.textContent=String(count);button.setAttribute('aria-description',count?'活动或待确认报警 '+count+' 条':'无活动或待确认报警');}}
function hmiNavigatePage(id){
 if(!HmiLayout.pages(project.hmi).some(p=>p.id===id))throw Error('目标页面不存在');
 if(id===hmiRuntimePageId)return;
 if((hmiViews.get('hmi-runtime-canvas')||[]).some(v=>v.pending||v.saving))throw Error('当前页有未写入的变量，请先写入或点击“放弃未写入值”');
 hmiRuntimePageId=id;try{sessionStorage.setItem('sieans.hmi.page.'+project.id,id);}catch{}
 const url=new URL(location.href);url.searchParams.set('page',id);url.searchParams.set('mode','run');history.replaceState(null,'',url);hmiRuntimePagesRender();hmiRefresh();document.getElementById('hmi-page-tab-'+id)?.focus();
}
function initHmiPages(){
 const bar=formEl('div',undefined,'hmi-pages-editor');bar.innerHTML='<label>运行画面总标题<input id="hmi-document-title" aria-label="运行画面总标题" maxlength="100"></label><label>编辑页面<select id="hmi-edit-page" aria-label="编辑画面页面"></select></label><button id="hmi-page-new">新增页面</button><button id="hmi-page-copy">复制页面</button><button id="hmi-page-delete">删除页面</button><button id="hmi-page-up">页面前移</button><button id="hmi-page-down">页面后移</button><button id="hmi-page-default">设为默认页</button><small id="hmi-page-count"></small>';$('hmi-editor').querySelector('header').after(bar);
 const nav=formEl('nav');nav.id='hmi-page-tabs';nav.setAttribute('role','tablist');nav.setAttribute('aria-label','运行画面页面');$('hmi-runtime-canvas').before(nav);
 $('hmi-document-title').oninput=()=>hmiDocument.title=$('hmi-document-title').value;
 $('hmi-page-title').required=true;
 $('hmi-edit-page').onchange=safe(()=>{const next=$('hmi-edit-page').value;try{hmiPagesCommitCurrent();hmiPagesSelectEditor(next);}catch(error){$('hmi-edit-page').value=hmiEditorPageId;throw error;}});
 $('hmi-page-new').onclick=safe(()=>{hmiPagesCommitCurrent();if(hmiDocument.pages.length>=20)throw Error('最多 20 页');const next={id:'page-'+uid(),...HmiLayout.empty(),title:'新页面 '+(hmiDocument.pages.length+1)};hmiDocument.pages.push(next);hmiPagesSelectEditor(next.id);});
 $('hmi-page-copy').onclick=safe(()=>{hmiPagesCommitCurrent();const id='page-'+uid();hmiDocument=HmiLayout.copyPage(hmiDocument,hmiEditorPageId,id);hmiPagesSelectEditor(id);});
 $('hmi-page-delete').onclick=safe(()=>{hmiPagesCommitCurrent();hmiDocument=HmiLayout.removePage(hmiDocument,hmiEditorPageId);hmiPagesSelectEditor(hmiDocument.defaultPageId);});
 for(const [id,direction] of [['hmi-page-up',-1],['hmi-page-down',1]])$(id).onclick=safe(()=>{hmiPagesCommitCurrent();const index=hmiDocument.pages.findIndex(p=>p.id===hmiEditorPageId),next=index+direction;if(next<0||next>=hmiDocument.pages.length)return;[hmiDocument.pages[index],hmiDocument.pages[next]]=[hmiDocument.pages[next],hmiDocument.pages[index]];hmiPagesRenderEditor();});
 $('hmi-page-default').onclick=safe(()=>{hmiPagesCommitCurrent();hmiDocument.defaultPageId=hmiEditorPageId;hmiPagesRenderEditor();});
}
