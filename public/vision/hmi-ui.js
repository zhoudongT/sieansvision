'use strict';
const hmiTypes={text:'文本标题',value:'数值显示',lamp:'状态指示灯',image:'图像窗口',cloud:'3D 点云窗口',table:'数据表格',button:'操作按钮',input:'变量输入',alarm:'报警列表',trend:'趋势曲线'};
let hmiDraft=null,hmiSelection='',hmiState={variables:{},results:[],status:{state:'idle'}},hmiProjectId='',hmiFetching=false,hmiTimer=null,hmiError='',hmiEpoch=0;
const hmiViews=new Map();
function hmiReleaseSurface(id){for(const view of hmiViews.get(id)||[])view.cloudViewer?.destroy();hmiViews.delete(id);}
function hmiDataView(value){const view=resultValueView(value),details=view.matches('details')?view:view.querySelector('details');if(details)details.open=true;return view;}
function hmiBinding(source='flow',path='value',nodeId=''){return {source,path,...(nodeId?{nodeId}:{})};}
function hmiDefault(type,index=0){
 const c={id:'hmi-'+uid(),type,label:hmiTypes[type],x:0,y:Math.min(index*2,(hmiDraft?.rows||10)-2),w:['image','cloud','table','alarm','trend'].includes(type)?6:3,h:['image','cloud','table','alarm','trend'].includes(type)?4:2,color:'#1095bd',fontSize:24};
 if(type==='text')c.w=6;
 if(['value','lamp','table','input','alarm','trend'].includes(type))c.binding=hmiBinding('flow',type==='input'?'setpoint':type==='lamp'?'passed':'count');
 if(type==='image')c.binding=project.steps.length?hmiBinding('result','',project.steps.at(-1).id):hmiBinding('source','');
 if(type==='cloud'){c.binding=hmiBinding('result','',project.steps.at(-1)?.id||'missing');c.maxPoints=12000;c.pointSize=2;c.initialView='iso';}
 if(['value','trend'].includes(type)){c.precision=2;c.unit='';}
 if(type==='trend')c.capacity=120;
 if(type==='alarm'){c.comparison='gte';c.threshold=10;c.hysteresis=0;c.stableSamples=1;c.severity='warning';}
 if(type==='button'){c.action='run';c.label='运行检测';}
 if(type==='input'){c.dataType='number';c.minimum=-1000000;c.maximum=1000000;}
 return c;
}
function hmiSetStatus(){
 const s=hmiState.status||{},labels={idle:'等待运行',running:'运行中',completed:'上次运行完成',failed:'上次运行失败',cancelled:'上次运行已停止'};
 renderDataMessage($('hmi-state'),hmiError||((s.archive?.state==='writing'?'正在保存运行历史':labels[s.state]||'等待运行')+(s.startedAt?' · '+new Date(s.startedAt).toLocaleTimeString('zh-CN',{hour12:false}):'')+(s.error?' · '+s.error:'')+(s.archive?.state==='failed'?' · '+s.archive.error:'')+((s.monitorWarning||hmiState.monitor?.error)?' · '+(s.monitorWarning||hmiState.monitor.error):'')));
 $('hmi-state').className=hmiError||s.state==='failed'||s.archive?.state==='failed'||s.monitorWarning||hmiState.monitor?.error?'error':'';
}
function hmiSetGeometry(card,c,layout){card.style.left=(c.x/12*100)+'%';card.style.top=(c.y*layout.rowHeight)+'px';card.style.width=(c.w/12*100)+'%';card.style.height=(c.h*layout.rowHeight)+'px';}
function hmiRenderSurface(host,layout,editing){
 hmiReleaseSurface(host.id);
 host.replaceChildren();host.style.height=(layout.rows*layout.rowHeight)+'px';host.style.setProperty('--hmi-row',layout.rowHeight+'px');host.classList.toggle('editing',editing);const views=[];
 for(const c of layout.components){
  const card=formEl('section',undefined,'hmi-card'+(editing&&c.id===hmiSelection?' selected':''));card.dataset.componentId=c.id;card.dataset.type=c.type;card.setAttribute('aria-label','画面组件 '+c.label);hmiSetGeometry(card,c,layout);
  const panel=formEl('div',undefined,'hmi-card-inner'),heading=formEl('div',c.label,'hmi-widget-label'),content=formEl('div',undefined,'hmi-widget-content');panel.style.setProperty('--hmi-accent',c.color);content.style.fontSize=c.fontSize+'px';panel.append(heading,content);card.append(panel);host.append(card);
  if(editing){heading.title='拖动移动组件';heading.style.cursor='move';heading.onpointerdown=e=>hmiDrag(e,c,card,host,layout);card.onclick=()=>{if(hmiSelection!==c.id){hmiSelection=c.id;hmiSelectCards();hmiProperties();}};}
  const view={c,card,content,editing,signature:null};
  if(c.type==='cloud')view.cloudViewer=CloudViewer.create(content,{maxPoints:c.maxPoints,pointSize:c.pointSize,initialView:c.initialView,interactive:!editing});
  if(c.type==='trend'&&!editing){const pause=formEl('button','暂停显示');pause.setAttribute('aria-label','暂停趋势显示 '+c.label);pause.onclick=event=>{event.stopPropagation();view.paused=!view.paused;pause.textContent=view.paused?'继续显示':'暂停显示';pause.setAttribute('aria-label',(view.paused?'继续趋势显示 ':'暂停趋势显示 ')+c.label);if(!view.paused){view.monitorSignature=null;hmiMonitorUpdate(view);}};heading.append(pause);}
  if(c.type==='button'){
   const button=formEl('button',c.label,'hmi-action '+c.action);button.setAttribute('aria-label','画面操作 '+c.label);button.disabled=editing;button.onclick=safe(async()=>{if(editing)return;if(c.action==='navigate'){hmiNavigatePage(c.targetPageId);return;}if(c.action==='run'){await executeRuntime(false);}else if(typeof operatorStopRuntime==='function'){await operatorStopRuntime();}else if(running){$('stop').click();}else if(hmiState.status?.id){await api('runtime/jobs/'+hmiState.status.id+'/cancel',{method:'POST'});}await hmiRefresh();});content.append(button);view.button=button;
  }else if(c.type==='input'){
   const field=c.dataType==='boolean'?formSelect([['true','是'],['false','否']],'false','画面输入 '+c.label):formEl('input');if(c.dataType!=='boolean'){field.type=c.dataType==='number'?'number':'text';field.setAttribute('aria-label','画面输入 '+c.label);if(c.dataType==='number'){field.min=c.minimum;field.max=c.maximum;field.step='any';field.required=true;}}
   const discard=formEl('button','放弃未写入值');discard.setAttribute('aria-label','放弃未写入值 '+c.label);discard.disabled=editing;discard.onclick=()=>{view.pending=false;field.value=String(HmiLayout.read(c.binding,hmiState)??'');hmiUpdateWidgets();};const button=formEl('button','写入'),note=formEl('small','暂无当前值');button.setAttribute('aria-label','写入 '+c.label);field.disabled=editing;button.disabled=editing;field.oninput=field.onchange=()=>{view.pending=true;view.discard.disabled=view.editing||view.saving;note.textContent='待写入；点击写入后生效';};button.onclick=safe(()=>hmiWrite(c,field,note,view));content.append(field,button,discard,note);view.discard=discard;view.field=field;view.button=button;view.note=note;
  }
  views.push(view);
 }
 hmiViews.set(host.id,views);hmiUpdateWidgets();
}
function hmiSelectCards(){for(const el of $('hmi-design-canvas').querySelectorAll('.hmi-card'))el.classList.toggle('selected',el.dataset.componentId===hmiSelection);}
function hmiDrag(event,c,card,host,layout){
 if(event.button!==0)return;event.preventDefault();hmiSelection=c.id;hmiSelectCards();hmiProperties();
 const start={px:event.clientX,py:event.clientY,x:c.x,y:c.y},unit=host.getBoundingClientRect().width/12,handle=event.currentTarget;handle.setPointerCapture(event.pointerId);
 handle.onpointermove=e=>{const next=HmiLayout.move(c,start.x+(e.clientX-start.px)/unit,start.y+(e.clientY-start.py)/layout.rowHeight,layout);c.x=next.x;c.y=next.y;hmiSetGeometry(card,c,layout);};
 const end=()=>{handle.onpointermove=null;handle.onpointerup=null;handle.onpointercancel=null;hmiProperties();hmiComponentList();};handle.onpointerup=end;handle.onpointercancel=end;
}
function hmiUpdateWidgets(){
 const busy=running||continuousState.busy||hmiState.status?.state==='running';
 for(const views of hmiViews.values())for(const v of views){const {c,content}=v;const value=hmiError?undefined:HmiLayout.read(c.binding,hmiState);
  if(c.type==='button'){v.button.disabled=v.editing||(c.action==='navigate'?false:c.action==='run'?busy:!busy);continue;}
  if(c.type==='input'){
   v.discard.disabled=v.editing||v.saving||!v.pending;const structured=!v.pending&&((value!==null&&typeof value==='object')||DataPresentation.structuredParts(value)!==null);
   v.field.hidden=v.button.hidden=structured;
   if(structured){
    if(!v.structured){v.structured=formEl('div');content.append(v.structured);}v.structured.hidden=false;
    const signature=JSON.stringify(value);if(signature!==v.signature){v.signature=signature;v.structured.replaceChildren(hmiDataView(value));}
    v.note.textContent=typeof operatorWriteInput==='function'?'当前值为结构化数据，请联系管理员调整画面输入绑定。':'当前值为结构化数据，请在变量管理中按字段编辑。';continue;
   }
   if(v.structured)v.structured.hidden=true;
   v.button.disabled=v.editing||busy||v.saving||!!hmiError;v.field.disabled=v.editing||busy||v.saving;if(document.activeElement!==v.field&&!v.saving&&!v.pending&&value!==undefined&&typeof value===c.dataType)v.field.value=String(value);if(!v.saving)v.note.textContent=(value===undefined?'暂无当前值':'当前值：'+resultText(value))+(v.pending?' · 待写入':'');continue;
  }
  if(['alarm','trend'].includes(c.type)){hmiMonitorUpdate(v);continue;}
  if(c.type==='text'){content.textContent=c.label;continue;}
  if(c.type==='cloud'){
   const row=hmiState.results?.find(r=>r.id===c.binding.nodeId&&!r.error&&!r.skipped),signature=[hmiState.status?.id||'',row?.id||'',!!row?.output?.cloud,hmiError].join(':');
   if(v.signature!==signature){v.signature=signature;v.cloudViewer.setCloud(hmiError?null:row?.output?.cloud??null);}continue;
  }
  if(c.type==='image'){
   const row=hmiState.results?.find(r=>r.id===c.binding.nodeId&&!r.error&&!r.skipped);const data=hmiError?'':c.binding.source==='source'?source:row?.output?.annotatedImage||'';
   if(data===v.signature)continue;v.signature=data;content.replaceChildren();if(/^data:image\/(png|jpeg|webp);base64,/.test(data)){const image=formEl('img');image.src=data;image.alt=c.label;content.append(image);}else content.append(formEl('span','等待图像','hmi-empty'));continue;
  }
  const signature=JSON.stringify(value)??'undefined';if(v.signature===signature)continue;v.signature=signature;content.replaceChildren();
  if(c.type==='lamp'){const known=typeof value==='boolean';content.append(formEl('i',undefined,'hmi-lamp '+(known?(value?'on':'off'):'unknown')),formEl('strong',known?(value?'通过':'未通过'):'未知'));}
  else if(c.type==='value'){
   if((value!==null&&typeof value==='object')||DataPresentation.structuredParts(value)!==null){content.append(hmiDataView(value));continue;}
   const formatted=typeof value==='number'?value.toFixed(c.precision):resultText(value);content.append(formEl('strong',formatted,'hmi-number'),formEl('small',c.unit));
  }
  else if(c.type==='table'){
   if(value===undefined){content.append(formEl('span','暂无数据','hmi-empty'));continue;}
   const parsed=structuredText(value),display=parsed??value;
   if(parsed!==null)content.append(formEl('small','结构化文本 · 表格预览','muted'));
   const rows=Array.isArray(display)?display:[display],table=formEl('table',undefined,'form-table');
   const keys=[...new Set(rows.slice(0,100).flatMap(r=>r&&typeof r==='object'&&!Array.isArray(r)?Object.keys(r):['value']))].slice(0,20),head=formEl('tr');for(const k of keys)head.append(formEl('th',DataPresentation.recordFieldLabel(rows,k,resultLabel(k))));table.append(head);
   for(const row of rows.slice(0,100)){const tr=formEl('tr');for(const key of keys){const cell=formEl('td');cell.append(resultValueView(row&&typeof row==='object'&&!Array.isArray(row)?row[key]:row));tr.append(cell);}table.append(tr);}content.append(table);if(rows.length>100)content.append(formEl('small','显示前 100 行'));
  }
 }
 hmiSetStatus();monitorDialogUpdate();hmiPagesUpdateAlarmBadges();
}
async function hmiWrite(c,field,note,view){
 if(running||continuousState.busy||hmiState.status?.state==='running')throw Error('运行中不可写入设定值');
 if(!field.checkValidity()){field.reportValidity();return;}
 const value=c.dataType==='number'?Number(field.value):c.dataType==='boolean'?field.value==='true':field.value;
 // Validate the configuration as well as the form before writing one top-level variable.
 HmiLayout.normalize({...HmiLayout.empty(),rows:40,components:[c]});
 if(c.dataType==='number'&&(!Number.isFinite(value)||value<c.minimum||value>c.maximum))throw Error('设定值超出范围');
 if(typeof operatorWriteInput==='function'){
  view.saving=true;view.button.disabled=true;view.discard.disabled=true;
  try{hmiState.variables=await operatorWriteInput(c,value,hmiState.variables.revision);view.pending=false;status(c.label+' 已写入');}
  finally{view.saving=false;await hmiRefresh();}return;
 }
 const snapshot=structuredClone(hmiState.variables),b=c.binding;
 if(!Number.isInteger(snapshot.revision))throw Error('请等待变量读取完成');
 const target=b.source==='module'?snapshot.modules[b.nodeId]:snapshot[b.source];if(!target)throw Error('绑定模块不存在');target[b.path]=value;
 view.saving=true;view.button.disabled=true;view.discard.disabled=true;
 try{const updated=await api('runtime/variables',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({project:currentProject(),values:snapshot,revision:snapshot.revision})});hmiState.variables=updated;view.pending=false;status(c.label+' 已写入'+(updated.monitorWarning?'；'+updated.monitorWarning:''),updated.monitorWarning?'error':'success');}
 finally{view.saving=false;await hmiRefresh();}
}
async function hmiRefresh(){
 if(hmiFetching||running)return;if(!$('hmi-editor').open&&!document.body.classList.contains('custom-hmi')&&!$('monitor-dialog')?.open)return;
 if(hmiProjectId!==project.id){hmiProjectId=project.id;hmiState={variables:{},results:[],status:{state:'idle'}};}
 const id=project.id,epoch=hmiEpoch;hmiFetching=true;
 try{const fresh=await api('runtime/view',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({project,since:hmiState.version})});if(id!==project.id||epoch!==hmiEpoch)return;hmiState={...fresh,results:fresh.results??hmiState.results};hmiError='';}
 catch(error){if(id===project.id&&epoch===hmiEpoch)hmiError='数据读取失败：'+error.message;}
 finally{hmiFetching=false;hmiUpdateWidgets();}
}
function hmiBeginRun(){hmiEpoch++;hmiProjectId=project.id;hmiState={variables:hmiState.variables,monitor:hmiState.monitor,results:[],status:{state:'running',startedAt:Date.now()}};hmiError='';hmiUpdateWidgets();}
function hmiAcceptJob(job){hmiState={...hmiState,version:[job.id,job.state,job.archive?.state||'',job.cursor,job.activeStep||''].join(':'),results,variables:job.variables||hmiState.variables,monitor:job.monitor||hmiState.monitor,status:{...hmiState.status,id:job.id,state:job.state,archive:job.archive,error:job.error,elapsedMs:job.elapsedMs,activeStep:job.activeStep,monitorWarning:job.monitorWarning||''}};hmiUpdateWidgets();}
function hmiSyncMode(){
 if(hmiProjectId!==project.id){hmiProjectId=project.id;hmiState={variables:{},results:[],status:{state:'idle'}};hmiError='';}
 const show=document.body.classList.contains('runtime')&&!!project.hmi&&(project.hmi.version===2||HmiLayout.allComponents(project.hmi).length>0);document.body.classList.toggle('custom-hmi',show);
 if(show){hmiRuntimePagesRender();hmiRefresh();}else hmiReleaseSurface('hmi-runtime-canvas');
}
function hmiComponentList(){
 const holder=$('hmi-component-list');holder.replaceChildren();
 for(const c of hmiDraft.components){const button=formEl('button',c.label+' · '+hmiTypes[c.type]);button.classList.toggle('active',c.id===hmiSelection);button.onclick=()=>{hmiSelection=c.id;hmiSelectCards();hmiProperties();hmiComponentList();};holder.append(button);}
}
function hmiProperties(){
 const holder=$('hmi-properties');holder.replaceChildren();const c=hmiDraft.components.find(c=>c.id===hmiSelection);
 if(!c){holder.append(formEl('p','从左侧添加组件，或点击画面中的组件。'));return;}
 const rebuild=()=>{hmiRenderSurface($('hmi-design-canvas'),hmiDraft,true);hmiComponentList();};
 const field=(label,value,type,change,options={})=>{
  const row=formEl('label',label,'hmi-property');let input;
  if(Array.isArray(type))input=formSelect(type,value,label);else{input=formEl('input');input.type=type;input.value=value??'';input.setAttribute('aria-label',label);if(type==='number'){input.step='1';input.required=true;}for(const [k,v] of Object.entries(options))input[k]=v;}
  const commit=()=>{if(!input.checkValidity()){input.reportValidity();return;}change(input.type==='number'?Number(input.value):input.value);rebuild();};input.onchange=commit;if(['number','text','color'].includes(input.type))input.oninput=()=>{if(input.checkValidity())commit();};row.append(input);holder.append(row);return input;
 };
 holder.append(formEl('h3',hmiTypes[c.type]));field('组件标题',c.label,'text',v=>c.label=v,{maxLength:200});
 for(const [key,label,max] of [['x','列位置（从 0 开始）',12-c.w],['y','行位置（从 0 开始）',hmiDraft.rows-c.h],['w','宽度（列）',12-c.x],['h','高度（行）',hmiDraft.rows-c.y]])field(label,c[key],'number',v=>c[key]=v,{min:['w','h'].includes(key)?1:0,max});
 field('主题颜色',c.color,'color',v=>c.color=v);field('字号',c.fontSize,'number',v=>c.fontSize=v,{min:12,max:64});
 if(['value','trend'].includes(c.type)){field('小数位数',c.precision,'number',v=>c.precision=v,{min:0,max:6});field('单位',c.unit,'text',v=>c.unit=v,{maxLength:20});}
 if(c.type==='cloud'){field('最多预览点数（不影响计算）',c.maxPoints,'number',v=>c.maxPoints=v,{min:100,max:30000});field('显示点大小',c.pointSize,'number',v=>c.pointSize=v,{min:1,max:6});field('初始视角',c.initialView,[['iso','等轴'],['top','俯视'],['front','正视']],v=>c.initialView=v);}
 if(c.type==='button'){field('按钮动作',c.action,[['run','运行整个流程'],['stop','停止当前流程'],['navigate','跳转页面']],v=>{c.action=v;if(v==='navigate')c.targetPageId=hmiDocument.pages[0].id;else delete c.targetPageId;hmiProperties();});if(c.action==='navigate')field('跳转目标页面',c.targetPageId,hmiDocument.pages.map(p=>[p.id,p.title]),v=>c.targetPageId=v);}
 if(c.type==='input'){
  field('输入数据类型',c.dataType,[['number','数值'],['string','文本'],['boolean','开关']],v=>{c.dataType=v;if(v==='number'){c.minimum=-1000000;c.maximum=1000000;}hmiProperties();});
  if(c.dataType==='number'){field('允许最小值',c.minimum,'number',v=>c.minimum=v,{step:'any'});field('允许最大值',c.maximum,'number',v=>c.maximum=v,{step:'any'});}
 }
 hmiMonitorProperties(c,field);
 if(c.binding){
  const choices=c.type==='cloud'?[['result','模块输出点云']]:c.type==='image'?[['source','本页输入图像'],['result','模块输出图像']]:[['flow','流程变量'],['global','全局变量'],['module','模块变量'],...c.type==='input'?[]:[['result','模块结果'],['status','运行状态']]];
  field('数据来源',c.binding.source,choices,v=>{c.binding=hmiBinding(v,v==='status'?'state':['image','cloud'].includes(c.type)?'':'value',['module','result'].includes(v)?project.steps[0]?.id||'missing':'');hmiProperties();});
  if(['module','result'].includes(c.binding.source)){const nodes=project.steps.map(s=>[s.id,flowName(s.id)]);if(!nodes.some(([id])=>id===c.binding.nodeId))nodes.unshift([c.binding.nodeId||'missing','未找到模块']);field('绑定模块',c.binding.nodeId,nodes,v=>c.binding.nodeId=v);}
  if(!['image','cloud'].includes(c.type))field('变量名或结果字段',c.binding.path,'text',v=>c.binding.path=v,{maxLength:200});
 }
 const duplicate=formEl('button','复制组件');duplicate.onclick=safe(()=>{if(hmiDraft.components.length>=50)throw Error('最多 50 个组件');hmiPagesCheckAddition(c.type);const copy=structuredClone(c);copy.id='hmi-'+uid();copy.label+=' 副本';copy.y=Math.min(hmiDraft.rows-copy.h,copy.y+1);hmiDraft.components.push(copy);hmiSelection=copy.id;rebuild();hmiProperties();});
 const remove=formEl('button','删除组件');remove.onclick=()=>{hmiDraft.components=hmiDraft.components.filter(v=>v.id!==c.id);hmiSelection='';rebuild();hmiProperties();};holder.append(duplicate,remove);if(hmiDocument.pages.length>1){const move=formSelect(hmiDocument.pages.map(p=>[p.id,p.title]),hmiEditorPageId,'组件目标页面'),button=formEl('button','移动组件到页面');button.onclick=safe(()=>hmiPagesMoveComponent(c,move.value));holder.append(move,button);}
}
function hmiPreset(){
 hmiDraft=HmiLayout.empty();hmiDraft.title=project.name+' · 运行监控';const last=project.steps.at(-1)?.id;
 const make=(type,label,x,y,w,h,extra={})=>({...hmiDefault(type),label,x,y,w,h,...extra});
 hmiDraft.components=[make('text','SIEANS · 视觉检测',0,0,8,1),make('button','运行检测',8,0,2,1),make('button','停止检测',10,0,2,1,{action:'stop'}),make('image','检测图像',0,1,8,6),make('value','检测数量',8,1,4,2,{precision:0,binding:last?hmiBinding('result','count',last):hmiBinding('flow','count')}),make('lamp','检测判定',8,3,4,2,{binding:last?hmiBinding('result','passed',last):hmiBinding('flow','passed')}),make('value','运行耗时',8,5,4,2,{precision:0,unit:'ms',binding:hmiBinding('status','elapsedMs')}),make('table','结果明细',0,7,12,3,{binding:last?hmiBinding('result','',last):hmiBinding('flow','')})];
 hmiPagesReplaceDraft(hmiDraft);hmiSelection=hmiDraft.components[0].id;hmiRenderEditor();
}
function hmiRenderEditor(){
 hmiPagesRenderEditor();
 $('hmi-page-title').value=hmiDraft.title;$('hmi-rows').value=hmiDraft.rows;$('hmi-row-height').value=hmiDraft.rowHeight;hmiRenderSurface($('hmi-design-canvas'),hmiDraft,true);hmiProperties();hmiComponentList();
}
function initHmiUI(){
 initHmiPages();
 for(const [type,label] of Object.entries(hmiTypes)){const button=formEl('button','＋ '+label);button.onclick=safe(()=>{if(hmiDraft.components.length>=50)throw Error('最多 50 个组件');hmiPagesCheckAddition(type);const c=hmiDefault(type,hmiDraft.components.length);c.y=Math.min(c.y,hmiDraft.rows-c.h);hmiDraft.components.push(c);hmiSelection=c.id;hmiRenderEditor();});$('hmi-palette').append(button);}
 $('hmi-open').onclick=safe(()=>{if(running)return;applyParams();hmiPagesOpen(project.hmi||HmiLayout.empty());hmiSelection=hmiDraft.components[0]?.id||'';$('hmi-editor').showModal();hmiRenderEditor();hmiRefresh();});
 $('hmi-template').onclick=()=>hmiPreset();
 $('hmi-page-title').oninput=()=>{hmiDraft.title=$('hmi-page-title').value;hmiPagesRenderEditor();};
 for(const [id,key] of [['hmi-rows','rows'],['hmi-row-height','rowHeight']])$(id).onchange=safe(()=>{const next={...hmiDraft,[key]:Number($(id).value)};HmiLayout.normalizePage(next);Object.assign(hmiDraft,next);hmiRenderEditor();});
 $('hmi-apply').onclick=safe(()=>{const invalid=$('hmi-editor').querySelector('input:invalid');if(invalid){invalid.reportValidity();throw Error('请修正画面属性中的无效输入');}hmiPagesCommitCurrent();project.hmi=HmiLayout.normalize(hmiDocument);dirty(false);$('hmi-editor').close();hmiReleaseSurface('hmi-design-canvas');hmiSyncMode();status('运行画面已应用，请保存工程以保留','success');});
 $('hmi-cancel').onclick=()=>{$('hmi-editor').close();hmiReleaseSurface('hmi-design-canvas');};
 $('hmi-editor').addEventListener('close',()=>hmiReleaseSurface('hmi-design-canvas'));
 hmiTimer=setInterval(()=>hmiRefresh(),1000);hmiSyncMode();
}
