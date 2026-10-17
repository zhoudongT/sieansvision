'use strict';
let annotationSession=null;
const annotationNS='http://www.w3.org/2000/svg';
function annotationSvg(tag,attrs){const el=document.createElementNS(annotationNS,tag);for(const [k,v] of Object.entries(attrs))el.setAttribute(k,String(v));return el;}
function annotationGuard(){if(annotationSession?.dirty||annotationSession?.draft.length)throw Error('当前图片有未保存的修改。请先保存，或点击“放弃当前修改”。');}
function annotationChange(){const s=annotationSession;s.undo.push(structuredClone(s.records));if(s.undo.length>30)s.undo.shift();s.dirty=true;}
function annotationApi(action,body={}){return api('training/datasets/'+encodeURIComponent(annotationSession.dataset.id)+'/annotations/'+action,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});}
async function annotationAction(action){if(annotationSession?.busy)return;annotationSession.busy=true;annotationRenderControls();try{await action();}catch(error){renderDataMessage($('annotation-status'),error.message);}finally{annotationSession.busy=false;annotationRenderControls();}}
function annotationRenderControls(){const s=annotationSession;if(!s)return;const loaded=!!s.frame;for(const id of ['annotation-upload','annotation-reload','annotation-save','annotation-background','annotation-undo','annotation-discard','annotation-finish','annotation-cancel-draw'])$(id).disabled=s.busy;
 $('annotation-save').disabled=s.busy||!loaded||!s.records.length||!!s.draft.length;$('annotation-background').disabled=s.busy||!loaded||!!s.records.length||!!s.draft.length;
 $('annotation-undo').disabled=s.busy||!s.undo.length;$('annotation-finish').disabled=s.busy||s.draft.length<3;$('annotation-cancel-draw').disabled=s.busy||!s.draft.length;
 document.querySelectorAll('#annotation-records input,#annotation-records select,#annotation-records button,#annotation-files button,#annotation-split,#annotation-tool,#annotation-class').forEach(el=>el.disabled=s.busy);
 annotationAssistControls();annotationHistoryControls();
 $('annotation-state').textContent=!loaded?'请选择图片':(s.dirty?'有未保存修改 · ':s.frame.hasLabel?'已保存 · ':'未标注 · ')+s.frame.name+' · '+s.frame.width+' × '+s.frame.height+' · '+s.records.length+' 个目标';
}
function annotationDraw(){
 const s=annotationSession,svg=$('annotation-svg');svg.replaceChildren();if(!s?.frame)return;
 const w=s.frame.width,h=s.frame.height,r=Math.max(w,h)/130,line=Math.max(w,h)/500;
 svg.setAttribute('viewBox',`0 0 ${w} ${h}`);svg.append(annotationSvg('image',{href:s.frame.image,x:0,y:0,width:w,height:h,'pointer-events':'none'}));
 const draw=(record,index,draft=false)=>{
  const points=record.box?AnnotationGeometry.corners(record.box):record.points,selected=index===s.selected&&!draft,color=draft?'#f3b54a':selected?'#009ec6':'#34bc8c';
  const shape=annotationSvg(record.box?'polygon':draft?'polyline':'polygon',{points:points.map(([x,y])=>`${x*w},${y*h}`).join(' '),fill:draft?'none':color+'22',stroke:color,'stroke-width':line*(selected?2:1),'data-target':index});svg.append(shape);
  if(!draft){const text=annotationSvg('text',{x:points[0][0]*w,y:Math.max(r*2,points[0][1]*h-r),fill:color,'font-size':r*2,'pointer-events':'none'});text.textContent=(index+1)+' · '+s.dataset.names[record.classId];svg.append(text);}
  if(selected||draft)points.forEach(([x,y],vertex)=>svg.append(annotationSvg('circle',{cx:x*w,cy:y*h,r,fill:'#fff',stroke:color,'stroke-width':line,'data-target':index,'data-vertex':vertex,role:'button',tabindex:0,'aria-label':draft?'绘制顶点 '+(vertex+1):'目标 '+(index+1)+' 顶点 '+(vertex+1)})));
 };
 s.records.forEach((record,i)=>draw(record,i));if(s.draft.length)draw({points:s.draft},-1,true);if(s.sketch)draw({box:AnnotationGeometry.box(s.sketch[0],s.sketch[1])},-1,true);
 annotationRenderControls();
}
function annotationRenderRecords(){
 const s=annotationSession,holder=$('annotation-records');holder.replaceChildren();const table=formEl('table',undefined,'form-table'),head=formEl('tr');for(const t of ['目标','类别','操作'])head.append(formEl('th',t));table.append(head);
 s.records.forEach((record,i)=>{const row=formEl('tr'),pick=formEl('button',String(i+1)),cell=formEl('td'),actions=formEl('td'),remove=formEl('button','删除');pick.setAttribute('aria-label','选择标注目标 '+(i+1));pick.onclick=()=>{s.selected=i;annotationRenderRecords();annotationDraw();};const name=formSelect(s.dataset.names.map((n,c)=>[String(c),n]),String(record.classId),'标注目标 '+(i+1)+' 类别');name.onchange=()=>{annotationChange();record.classId=Number(name.value);annotationDraw();};cell.append(name);remove.onclick=()=>{annotationChange();s.records.splice(i,1);s.selected=Math.min(i,s.records.length-1);annotationRenderRecords();annotationDraw();};actions.append(remove);const number=formEl('td');number.append(pick);row.append(number,cell,actions);table.append(row);});holder.append(table);
 const record=s.records[s.selected];if(!record||!s.frame)return;
 holder.append(formEl('h4','所选目标 · 像素坐标'));
 const coordinate=(title,value,maximum,change)=>{const label=formEl('label',title),input=formEl('input');input.type='number';input.step='any';input.required=true;input.min=0;input.max=maximum;input.value=Number(value.toFixed(3));input.setAttribute('aria-label',title);input.onchange=()=>{if(!input.reportValidity())return;annotationChange();change(Number(input.value));annotationDraw();};label.append(input);return label;};
 if(record.box){const [x,y,w,h]=record.box,fw=s.frame.width,fh=s.frame.height;for(const [title,value,max,index,scale] of [['中心 X',x*fw,fw,0,fw],['中心 Y',y*fh,fh,1,fh],['宽度',w*fw,fw,2,fw],['高度',h*fh,fh,3,fh]])holder.append(coordinate(title,value,max,n=>record.box[index]=n/scale));}
 else{
  const points=formEl('table',undefined,'form-table annotation-point-table'),header=formEl('tr');for(const t of ['点','X','Y'])header.append(formEl('th',t));points.append(header);
  record.points.forEach((point,i)=>{const row=formEl('tr');row.append(formEl('td',i+1));for(const [axis,max] of [[0,s.frame.width],[1,s.frame.height]]){const cell=formEl('td');cell.append(coordinate('顶点 '+(i+1)+' '+(axis?'Y':'X'),point[axis]*max,max,n=>point[axis]=n/max));row.append(cell);}points.append(row);});holder.append(points);
 }
}
async function annotationList(){
 const s=annotationSession,result=await annotationApi('list');s.items=result.items;
 const holder=$('annotation-files');holder.replaceChildren();const table=formEl('table',undefined,'form-table'),head=formEl('tr');for(const t of ['图片','状态'])head.append(formEl('th',t));table.append(head);
 const visible=s.items.filter(i=>i.split===s.split);let cursor=0;const more=formEl('button','显示更多图片');more.type='button';const append=()=>{for(const item of visible.slice(cursor,cursor+50)){
  const row=formEl('tr'),cell=formEl('td'),button=formEl('button',item.name);button.title=item.name;button.onclick=()=>annotationAction(async()=>{annotationGuard();await annotationLoad(item);});cell.append(button);row.append(cell,formEl('td',item.hasLabel?'已保存':'待标注'));table.append(row);
 }cursor+=50;more.hidden=cursor>=visible.length;};more.onclick=append;append();holder.append(table,more);$('annotation-file-count').textContent=visible.length+' 张图片';
}
async function annotationLoad(item){annotationAssistReset();const s=annotationSession,frame=await annotationApi('load',item);s.frame=frame;s.records=structuredClone(frame.records);s.original=structuredClone(frame.records);s.selected=s.records.length?0:-1;s.undo=[];s.dirty=false;s.draft=[];s.sketch=null;annotationRenderRecords();annotationDraw();renderDataMessage($('annotation-status'),frame.hasLabel?'标注已载入，可选择目标编辑':'图片尚未标注，请绘制目标或明确保存为背景');}
function annotationPoint(event){const svg=$('annotation-svg'),point=svg.createSVGPoint();point.x=event.clientX;point.y=event.clientY;const p=point.matrixTransform(svg.getScreenCTM().inverse()),s=annotationSession;return [AnnotationGeometry.clamp(p.x/s.frame.width),AnnotationGeometry.clamp(p.y/s.frame.height)];}
function initAnnotationUI(){
 const dialog=formEl('dialog');dialog.id='annotation-dialog';dialog.setAttribute('aria-label','数据集图像标注');
 dialog.innerHTML='<header class="annotation-header"><div><h2>图像标注</h2><span id="annotation-dataset-name"></span></div><button id="annotation-close" aria-label="关闭图像标注">×</button></header><div class="annotation-toolbar"><label>图片划分<select id="annotation-split" aria-label="标注图片划分"><option value="train">训练集</option><option value="val">验证集</option></select></label><label>当前类别<select id="annotation-class" aria-label="绘制目标类别"></select></label><select id="annotation-tool" aria-label="标注工具"><option value="draw">绘制目标</option><option value="select">选择 / 移动 / 调整顶点</option></select><label class="button">导入图片<input id="annotation-upload" type="file" accept="image/png,image/jpeg,image/bmp" multiple hidden></label><button id="annotation-reload">刷新列表</button><button id="annotation-finish">完成轮廓</button><button id="annotation-cancel-draw">取消绘制</button><button id="annotation-undo">撤销</button></div><p id="annotation-instruction" class="muted"></p><div class="annotation-body"><aside><h3>图片 <small id="annotation-file-count"></small></h3><div id="annotation-files"></div></aside><section class="annotation-stage"><svg id="annotation-svg" tabindex="0" role="img" aria-label="标注画布"></svg></section><aside><h3>目标与坐标</h3><div id="annotation-records"></div></aside></div><footer class="annotation-footer"><span id="annotation-state">请选择图片</span><button id="annotation-discard">放弃当前修改</button><button id="annotation-background">保存为背景</button><button id="annotation-save" class="primary">保存标注</button></footer><p id="annotation-status" role="status"></p>';
 document.body.append(dialog);initAnnotationAssist();initAnnotationHistory();
 const open=formEl('button','图片导入与标注');open.id='training-annotate';$('training-check').before(open);
 open.onclick=safe(async()=>{const dataset=trainingState?.datasets.find(d=>d.id===$('training-dataset').value);if(!dataset)throw Error('请先创建或选择数据集');annotationSession={dataset,split:'train',items:[],frame:null,records:[],original:[],undo:[],selected:-1,draft:[],sketch:null,dirty:false,busy:false};annotationAssistReset();$('annotation-dataset-name').textContent=dataset.id+' · '+(dataset.task==='segment'?'实例分割':'目标检测');$('annotation-class').replaceChildren(...dataset.names.map((n,i)=>new Option(n,String(i))));$('annotation-split').value='train';$('annotation-tool').value='draw';$('annotation-finish').hidden=dataset.task!=='segment';$('annotation-instruction').textContent=dataset.task==='segment'?'逐点点击描绘轮廓，点击“完成轮廓”闭合。选择工具可移动目标、拖动顶点；右侧表格可精确输入像素坐标。Enter 完成、Esc 取消绘制。':'在图片上拖动绘制矩形框。选择工具可移动框、拖动角点；右侧表格可精确输入像素坐标。';annotationRenderRecords();annotationDraw();annotationRenderControls();dialog.showModal();await annotationAction(annotationList);});
 $('annotation-close').onclick=()=>annotationAction(async()=>{annotationGuard();dialog.close();});dialog.addEventListener('cancel',event=>{event.preventDefault();$('annotation-close').click();});
 $('annotation-split').onchange=()=>annotationAction(async()=>{const s=annotationSession,next=$('annotation-split').value;try{annotationGuard();s.split=next;annotationAssistReset();s.frame=null;s.records=[];s.selected=-1;s.draft=[];annotationRenderRecords();annotationDraw();await annotationList();}catch(error){$('annotation-split').value=s.split;throw error;}});
 $('annotation-reload').onclick=()=>annotationAction(async()=>{annotationGuard();await annotationList();});
 $('annotation-discard').onclick=()=>{const s=annotationSession;gesture=null;s.records=structuredClone(s.original);s.draft=[];s.sketch=null;s.undo=[];s.dirty=false;s.selected=s.records.length?0:-1;annotationRenderRecords();annotationDraw();};
 $('annotation-undo').onclick=()=>{const s=annotationSession;if(!s.undo.length)return;s.records=s.undo.pop();s.selected=Math.min(s.selected,s.records.length-1);s.draft=[];s.dirty=true;annotationRenderRecords();annotationDraw();};
 $('annotation-cancel-draw').onclick=()=>{gesture=null;annotationSession.draft=[];annotationSession.sketch=null;annotationDraw();};
 $('annotation-finish').onclick=()=>annotationAction(async()=>{const s=annotationSession;if(!AnnotationGeometry.polygonValid(s.draft))throw Error('轮廓需至少 3 点，不能自相交、重复顶点或面积为零');annotationChange();s.records.push({classId:Number($('annotation-class').value),points:structuredClone(s.draft)});s.selected=s.records.length-1;s.draft=[];annotationRenderRecords();annotationDraw();});
 const save=()=>annotationAction(async()=>{const s=annotationSession;if(!s.frame||s.draft.length)throw Error('请先完成或取消当前绘制');if(s.dataset.task==='segment'&&s.records.some(r=>!AnnotationGeometry.polygonValid(r.points)))throw Error('轮廓不能自相交、重复顶点或面积为零，请调整坐标后保存');const result=await annotationApi('save',{name:s.frame.name,split:s.frame.split,revision:s.frame.revision,records:s.records});s.frame.revision=result.revision;s.frame.hasLabel=true;s.original=structuredClone(s.records);s.dirty=false;await annotationList();renderDataMessage($('annotation-status'),s.records.length?'标注已保存，可继续标注下一张':'已明确保存为无目标背景图');});$('annotation-save').onclick=save;$('annotation-background').onclick=save;
 $('annotation-upload').onchange=()=>annotationAction(async()=>{annotationGuard();const input=$('annotation-upload'),files=Array.from(input.files||[]);input.value='';if(files.length>100)throw Error('一次最多导入 100 张图片');let count=0;const errors=[];for(const file of files){try{if(file.size>12000000)throw Error('超过 12 MB');await annotationApi('upload',{split:annotationSession.split,name:file.name,image:await readFile(file)});count++;}catch(error){errors.push(file.name+'：'+error.message);}}await annotationList();renderDataMessage($('annotation-status'),'已导入 '+count+' 张'+(errors.length?'；失败：'+errors.join('；'):''));});
 const svg=$('annotation-svg');let gesture=null;
 svg.onpointerdown=event=>{
  const s=annotationSession;if(!s.frame||s.busy||event.button!==0)return;svg.focus();const point=annotationPoint(event);
  if($('annotation-tool').value==='draw'){
   if(s.dataset.task==='segment'){if(s.draft.length>=500)return;s.draft.push(point);annotationDraw();return;}
   s.sketch=[point,point];gesture={type:'draw',start:point};
  }else{
   const target=event.target.closest('[data-target]'),index=Number(target?.getAttribute('data-target'));if(!target||index<0||!s.records[index])return;s.selected=index;
   gesture={type:'edit',start:point,record:structuredClone(s.records[index]),before:structuredClone(s.records),index,vertex:target.hasAttribute('data-vertex')?Number(target.getAttribute('data-vertex')):null};annotationRenderRecords();
  }svg.setPointerCapture(event.pointerId);annotationDraw();event.preventDefault();
 };
 svg.onpointermove=event=>{if(!gesture)return;const s=annotationSession,point=annotationPoint(event);if(gesture.type==='draw')s.sketch=[gesture.start,point];else{const g=gesture,r=structuredClone(g.record);if(g.vertex===null)s.records[g.index]=AnnotationGeometry.move(r,point[0]-g.start[0],point[1]-g.start[1]);else if(r.box){const opposite=AnnotationGeometry.corners(r.box)[(g.vertex+2)%4];r.box=AnnotationGeometry.box(opposite,point);s.records[g.index]=r;}else{r.points[g.vertex]=point;s.records[g.index]=r;}}annotationDraw();};
 svg.onpointerup=event=>{if(!gesture)return;const s=annotationSession,g=gesture;gesture=null;
  if(g.type==='draw'){const b=AnnotationGeometry.box(g.start,annotationPoint(event));if(b[2]*s.frame.width>=1&&b[3]*s.frame.height>=1){annotationChange();s.records.push({classId:Number($('annotation-class').value),box:b});s.selected=s.records.length-1;}s.sketch=null;}
  else if(JSON.stringify(s.records)!==JSON.stringify(g.before)){s.undo.push(g.before);if(s.undo.length>30)s.undo.shift();s.dirty=true;}
  annotationRenderRecords();annotationDraw();
 };
 svg.onpointercancel=()=>{if(gesture?.before)annotationSession.records=gesture.before;gesture=null;annotationSession.sketch=null;annotationRenderRecords();annotationDraw();};
 svg.onkeydown=event=>{if(event.key==='Escape'){$('annotation-cancel-draw').click();event.preventDefault();event.stopPropagation();}else if(event.key==='Enter'&&annotationSession.draft.length){$('annotation-finish').click();event.preventDefault();}};
}
