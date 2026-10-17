'use strict';
// Structured values stay structured in memory; controls never serialize them for editing.
const formTypes={number:'数值',string:'文本',boolean:'开关',array:'数组',object:'结构体',null:'空值',reference:'变量 / 结果绑定'};
const formDefaults={number:0,string:'',boolean:false,array:[],object:{},null:null,reference:{$ref:'flow.'}};
const fieldNames={value:'赋值内容',values:'批量写入值',roi:'检测区域',arguments:'脚本输入参数',minimum:'最小坐标',maximum:'最大坐标',initialTransform:'初始变换矩阵',calibration:'平面标定',points:'坐标点',distance:'实际距离',unit:'单位',origin:'坐标原点',scales:'搜索比例',classes:'类别筛选',cannyLow:'边缘低阈值',cannyHigh:'边缘高阈值',minRadius:'最小半径',maxRadius:'最大半径',minDistance:'圆心最小间距',votes:'检测票数',minLength:'最短直线',maxGap:'最大断点间距'};
function formEl(tag,text,cls){const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e;}
function formSelect(options,value,label){const e=formEl('select');e.setAttribute('aria-label',label);for(const [key,text] of options)e.append(new Option(text,key));e.value=value;return e;}
function formType(v){return v===null?'null':Array.isArray(v)?'array':typeof v==='object'?(Object.keys(v).length===1&&typeof v.$ref==='string'?'reference':'object'):typeof v;}
function structuredText(value){
 if(typeof value!=='string'||value.length>1000000||!/^\s*[\[{]/.test(value))return null;
 try{const parsed=JSON.parse(value);return parsed&&typeof parsed==='object'?parsed:null;}catch{return null;}
}
// Preserve text contracts and surrounding protocol/log text while editing data as fields.
function structuredTextEditor(value,change,label,depth=0){
 const parts=DataPresentation.structuredParts(value);if(!parts||depth>=20)return null;
 const box=formEl('div',undefined,'structured-text-editor');box.append(formEl('small','结构化文本 · 按字段编辑，保存后仍为文本','muted'));
 const save=()=>change(DataPresentation.joinParts(parts));
 parts.forEach((part,index)=>{
  if(part.kind==='data'){
   const holder=formEl('div');box.append(holder);
   collectionEditor(holder,part.value,next=>{part.value=next;delete part.raw;save();},{label:label+' 数据 '+(index+1),refs:false,depth:depth+1});
  }else if(part.value.trim()){
   const row=formEl('label', '说明文字','structured-text-label'),input=formEl('input');input.value=part.value;input.setAttribute('aria-label',label+' 说明文字 '+(index+1));input.oninput=()=>{part.value=input.value;save();};row.append(input);box.append(row);
  }
 });return box;
}
function validFormName(input,names=[]){const name=input.value.trim();const error=!name?'请输入名称':['__proto__','constructor','prototype'].includes(name)?'名称不可使用保留字':names.includes(name)?'名称已存在':'';input.setCustomValidity(error);if(error){input.reportValidity();return null;}return name;}
const bindingResultFields=new Map();
function collectBindingFields(values){
 const fields=[];
 const walk=(value,prefix='',depth=0)=>{
  if(depth>20)return;
  for(const [key,item] of Object.entries(value||{})){
   if(fields.length>=500)return;
   if(!key||key.includes('.')||['__proto__','prototype','constructor'].includes(key))continue;
   const path=prefix?prefix+'.'+key:key;
   fields.push([path,formTypes[formType(item)]||'值']);
   if(item&&typeof item==='object')walk(item,path,depth+1);
  }
 };
 walk(values);return fields;
}
function rememberBindingFields(items){for(const item of items)if(!item.error&&!item.skipped&&item.output?.result)bindingResultFields.set(item.id,collectBindingFields(item.output.result));}
function bindingFields(scope,nodeId){
 const step=selectedStep(),snapshot=variableSnapshot?.projectId===project.id?variableSnapshot:null;
 if(scope==='results'){const result=results.find(r=>r.id===nodeId&&!r.error&&!r.skipped);return result?.output?.result?collectBindingFields(result.output.result):(bindingResultFields.get(nodeId)||[]);}
 const values=scope==='global'?(snapshot?.global||{}):scope==='module'?{...step?.variables,...snapshot?.modules?.[step?.id]}:{...project.variables,...snapshot?.flow};
 return collectBindingFields(values);
}
function referenceEditor(value,change,label){
 const box=formEl('div',undefined,'reference-fields');const parts=value.$ref.split('.'),scope=parts.shift();let node=scope==='results'?parts.shift():'';
 const source=formSelect([['flow','流程变量'],['global','全局变量'],['module','当前模块变量'],['results','上游模块结果']],scope,label+'来源');
 const parents=new Set();const walk=id=>{for(const edge of project.edges.filter(e=>e.to===id))if(!parents.has(edge.from)){parents.add(edge.from);walk(edge.from);}};if(selectedStep())walk(selectedStep().id);
 const nodes=project.steps.filter(s=>parents.has(s.id)).map(s=>[s.id,flowName(s.id)]);if(node&&!nodes.some(([id])=>id===node))nodes.push([node,'未连接的模块（请检查连线）']);
 const module=formSelect([['','请选择上游模块'],...nodes],node,label+'上游模块');module.hidden=scope!=='results';module.required=scope==='results';
 const path=formEl('input');path.value=parts.join('.');path.placeholder='变量名或字段路径';path.required=true;path.pattern='[^.]+(?:\\.[^.]+)*';path.setAttribute('aria-label',label+'字段');
 const known=formSelect([['','选择已定义字段…']],'',label+'可选字段'),notice=formEl('small',undefined,'binding-notice');
 const refresh=formEl('button','刷新变量列表');refresh.type='button';
 const updateChoices=()=>{const fields=bindingFields(source.value,module.value);known.replaceChildren(new Option('选择已定义字段…',''),...fields.map(([key,type])=>new Option(key+' · '+type,key)));known.value=fields.some(([key])=>key===path.value)?path.value:'';known.disabled=!fields.length;notice.textContent=source.value==='results'?'列出最近运行的上游字段名，值在执行时读取。未列出的字段可填写名称。':'列出工程初始定义及已读取的运行变量；也可填写嵌套字段路径。';refresh.hidden=source.value==='results';};
 const save=()=>{module.hidden=source.value!=='results';module.required=source.value==='results';change({$ref:source.value+'.'+(source.value==='results'?module.value+'.':'')+path.value.trim()});};
 source.onchange=()=>{save();updateChoices();};module.onchange=()=>{save();updateChoices();};path.oninput=()=>{save();known.value=path.value;};known.onchange=()=>{if(known.value){path.value=known.value;save();}};
 refresh.onclick=safe(async()=>{refresh.disabled=true;const projectId=project.id;try{const snapshot=await api('runtime/variables/read',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({project:currentProject()})});if(project.id!==projectId||!box.isConnected)return;variableSnapshot={...snapshot,projectId};updateChoices();}finally{refresh.disabled=false;}});
 updateChoices();box.append(source,module,known,path,refresh,notice);return box;
}
function valueEditor(value,change,{label='值',refs=true,depth=0,typeCell=null}={}){
 const box=formEl('div',undefined,'value-editor');const detected=formType(value),type=!refs&&detected==='reference'?'object':detected,types=Object.entries(formTypes).filter(([k])=>refs||k!=='reference');
 const select=formSelect(types,type,label+'类型');const control=formEl('div',undefined,'value-control');
 if(typeCell){typeCell.replaceChildren(select);box.classList.add('value-only');box.append(control);}else box.append(select,control);
 select.onchange=()=>{const next=structuredClone(formDefaults[select.value]);change(next);box.replaceWith(valueEditor(next,change,{label,refs,depth,typeCell}));};
 if(type==='reference')control.append(referenceEditor(value,change,label));
 else if(type==='object'||type==='array'){
   const details=formEl('details'),summary=formEl('summary',(type==='array'?'数组':'结构体')+' · '+Object.keys(value).length+' 项');details.append(summary);const holder=formEl('div');details.append(holder);let built=false;details.ontoggle=()=>{if(details.open&&!built){built=true;collectionEditor(holder,value,next=>{summary.textContent=(type==='array'?'数组':'结构体')+' · '+Object.keys(next).length+' 项';change(next);},{label,refs,depth:depth+1});}};control.append(details);
 }else if(type==='null')control.append(formEl('span','未设置','muted'));
 else if(type==='boolean'){const input=formSelect([['true','是'],['false','否']],String(value),label);input.onchange=()=>change(input.value==='true');control.append(input);}
 else if(type==='string'&&depth<20&&DataPresentation.structuredParts(value)!==null){
   control.append(structuredTextEditor(value,change,label,depth));
 }
 else {const input=formEl('input');input.type=type==='number'?'number':'text';if(type==='number'){input.step='any';input.required=true;}input.value=value;input.setAttribute('aria-label',label);input.oninput=()=>{if(input.checkValidity()&&(type!=='number'||Number.isFinite(Number(input.value))))change(type==='number'?Number(input.value):input.value);};control.append(input);}
 return box;
}
function collectionEditor(holder,value,change,{label='字段',refs=true,depth=0}={}){
 holder.replaceChildren();if(depth>20){holder.append(formEl('p','嵌套层级超过编辑上限'));return;}
 const array=Array.isArray(value),table=formEl('table',undefined,'form-table definition-table'),head=formEl('tr');for(const text of [array?'序号':'名称','数据类型','值 / 绑定','操作'])head.append(formEl('th',text));table.append(head);
 const keys=Object.keys(value);let visible=0;const more=formEl('button','显示更多');more.type='button';
 const renderMore=()=>{for(const key of keys.slice(visible,visible+50)){
   let current=key;const row=formEl('tr'),nameCell=formEl('td'),typeCell=formEl('td'),valueCell=formEl('td'),actions=formEl('td');
   if(array){const axes=({'检测区域':['X','Y','宽度','高度'],'坐标原点':['X','Y'],'最小坐标':['X','Y','Z'],'最大坐标':['X','Y','Z']})[label];nameCell.textContent=axes?.[Number(key)]||String(Number(key)+1);}else{const name=formEl('input');name.value=key;name.setAttribute('aria-label',label+'名称');name.oninput=()=>{const next=validFormName(name,Object.keys(value).filter(k=>k!==current));if(next){const old=value[current];delete value[current];value[next]=old;current=next;change(value);}};nameCell.append(name);}
   valueCell.append(valueEditor(value[key],next=>{value[current]=next;change(value);},{label:label+' '+key,refs,depth,typeCell}));
   const remove=formEl('button','删除');remove.type='button';remove.onclick=()=>{if(array)value.splice(Number(current),1);else delete value[current];change(value);collectionEditor(holder,value,change,{label,refs,depth});};actions.append(remove);row.append(nameCell,typeCell,valueCell,actions);table.append(row);
 }visible+=50;more.hidden=visible>=keys.length;};more.onclick=renderMore;renderMore();holder.append(table,more);
 const add=formEl('button',array?'添加元素':depth===0&&label.includes('变量')?'新增变量':depth===0&&label==='脚本输入'?'添加输入参数':'添加字段');add.type='button';add.onclick=()=>{if(array)value.push(0);else{let n=1;while(Object.hasOwn(value,'field'+n))n++;value['field'+n]='';}change(value);collectionEditor(holder,value,change,{label,refs,depth});};holder.append(add);
}
const extraParams={preprocess:{cannyLow:50,cannyHigh:150,invert:false},locate:{scales:[1],origin:[0,0]},geometry:{minRadius:0,maxRadius:100,minDistance:20,votes:30,minLength:50,maxGap:10,cannyLow:50,cannyHigh:150},measure:{calibration:{points:[[0,0],[100,0]],distance:10},unit:'mm',points:[[0,0],[100,0]],origin:[0,0],minRadius:5,maxRadius:200,minDistance:30,votes:30,cannyHigh:150},yolo:{classes:[0]},cloud_filter:{minimum:[0,0,0],maximum:[100,100,100]},cloud_register:{initialTransform:[[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]]}};
Object.assign(fieldNames,{invert:'反色提取深色目标',threshold:'二值阈值',kernel:'卷积核大小',templateRoi:'模板区域',outputBindings:'输出变量绑定'});
extraParams.condition={left:0,right:0};Object.assign(fieldNames,{left:'输入值',right:'比较值'});
extraParams.yolo_segment={classes:[0]};
function functionalFieldVisible(step,key){
 const p=step.params,op=step.operation,method=p.method||'grayscale',feature=p.feature||'contours';
 if(op==='yolo_segment'&&key==='overlayAlpha')return typeof p.output==='object'||(p.output||'overlay')==='overlay';
 if(op==='cloud_register'&&typeof p.method!=='object'){
  if(key==='initialTransform')return (p.method||'icp')==='icp';
  if(['voxelSize','ransacIterations','ransacConfidence','minFitness','minTargetFitness','maxRmsError'].includes(key))return p.method==='global';
 }
 if(op==='condition'&&key==='right')return !['is_true','is_false'].includes(p.comparison);
 if(op==='cloud_filter'&&key!=='method'&&typeof p.method!=='object'&&['voxelSize','neighbors','stdRatio','radius','minPoints','minimum','maximum'].includes(key))return ({voxel:['voxelSize'],crop:['minimum','maximum'],statistical:['neighbors','stdRatio'],radius:['radius','minPoints']}[p.method||'voxel']||[]).includes(key);
 // A bound selector is resolved at runtime, so retain all potentially relevant fields.
 if(typeof method==='object'||typeof feature==='object')return true;
 if(op==='preprocess'){
   if(['cannyLow','cannyHigh'].includes(key))return method==='canny';
   if(['threshold','invert'].includes(key))return method==='threshold';
   if(key==='kernel')return ['blur','open','close','erode','dilate'].includes(method);
 }
 if(op==='geometry'||op==='measure'){
   if(['threshold','minArea','invert'].includes(key))return feature==='contours';
   if(['minRadius','maxRadius','minDistance'].includes(key))return feature==='circles';
   if(['minLength','maxGap'].includes(key))return feature==='lines';
   if(key==='votes')return ['circles','lines'].includes(feature);
   if(key==='cannyLow')return ['lines','edges'].includes(feature);
   if(key==='cannyHigh')return ['lines','edges','circles'].includes(feature);
 }
 return true;
}
// Match the engine's defaults without inserting unused settings into the project.
function functionalDefaults(step){
 const feature=step.params.feature||'contours';
 if(step.operation==='preprocess'){
  const method=step.params.method||'grayscale';
  if(method==='canny')return {cannyLow:50,cannyHigh:150};
  if(method==='threshold')return {threshold:127};
  if(['blur','open','close','erode','dilate'].includes(method))return {kernel:method==='blur'?5:3};
 }
 if(['geometry','measure'].includes(step.operation)){
  if(feature==='circles')return {minRadius:5,maxRadius:200,minDistance:30,votes:30,cannyHigh:150};
  if(feature==='lines')return {cannyLow:50,cannyHigh:150,votes:40,minLength:40,maxGap:10};
  if(feature==='edges')return {cannyLow:50,cannyHigh:150};
 }
 return {};
}
function numericParameterEditor(key,value,change){
 const label=fieldNames[key]||key;
 if(typeof value!=='number')return valueEditor(value,change,{label});
 const box=formEl('div',undefined,'numeric-parameter'),input=formEl('input'),bind=formEl('button','绑定变量或结果');
 const bounds={cannyLow:[0,255],cannyHigh:[0,255],minRadius:[0,10000],maxRadius:[0,10000],minDistance:[1,10000],votes:[1,10000],minLength:[1,10000],maxGap:[0,1000]}[key];
 input.type='number';input.required=true;input.step=['minRadius','maxRadius','votes'].includes(key)?'1':'any';input.value=value;input.setAttribute('aria-label',label);
 if(bounds){input.min=bounds[0];input.max=bounds[1];}
 input.oninput=()=>{if(input.checkValidity()&&Number.isFinite(Number(input.value)))change(Number(input.value));};
 bind.type='button';bind.onclick=()=>{const next={$ref:'flow.'};change(next);box.replaceWith(valueEditor(next,change,{label}));};
 box.append(input,bind);return box;
}
// Known geometric parameters keep their numeric shape while the stored format stays unchanged.
function functionalValueEditor(key,value,change){
 if(key==='calibration'&&value&&typeof value==='object'&&!Array.isArray(value)&&formType(value)!=='reference'){
  const box=formEl('div',undefined,'functional-value');
  for(const [field,item] of Object.entries(value)){
   box.append(formEl('label',field==='points'?'标定点 (px)':field==='distance'?'两点实际距离':fieldNames[field]||field,'section-caption'));
   box.append(field==='points'?functionalValueEditor('points',item,next=>{value[field]=next;change(value);}):valueEditor(item,next=>{value[field]=next;change(value);},{label:fieldNames[field]||field}));
  }return box;
 }
 const shapes={roi:{columns:['X (px)','Y (px)','宽度 (px)','高度 (px)'],rows:1,min:[0,0,1,1]},templateRoi:{columns:['X (px)','Y (px)','宽度 (px)','高度 (px)'],rows:1,min:[0,0,1,1]},origin:{columns:['X','Y'],rows:1},minimum:{columns:['X','Y','Z'],rows:1},maximum:{columns:['X','Y','Z'],rows:1},points:{columns:['X (px)','Y (px)'],rows:2},initialTransform:{columns:['X','Y','Z','平移'],rows:4}};
 const shape=shapes[key],label=fieldNames[key]||key;
 if(!shape||formType(value)==='reference')return valueEditor(value,change,{label});
 const vector=shape.rows===1,values=vector?[value]:value;
 const valid=Array.isArray(values)&&values.length===shape.rows&&values.every(row=>Array.isArray(row)&&row.length===shape.columns.length&&row.every(n=>typeof n==='number'&&Number.isFinite(n)));
 // Imported custom bindings remain editable rather than silently discarding their contents.
 if(!valid)return valueEditor(value,change,{label});
 const box=formEl('div',undefined,'functional-value'),table=formEl('table',undefined,'form-table coordinate-table'),head=formEl('tr');
 table.setAttribute('aria-label',label+'表格');head.append(formEl('th',vector?'参数':'序号'));for(const title of shape.columns)head.append(formEl('th',title));table.append(head);
 values.forEach((valuesRow,index)=>{const row=formEl('tr');row.append(formEl('th',vector?label:key==='points'?(index===0?'起点':'终点'):String(index+1)));
  valuesRow.forEach((number,column)=>{const cell=formEl('td'),input=formEl('input');input.type='number';input.step=key==='roi'||key==='templateRoi'?'1':'any';input.required=true;input.value=number;if(shape.min)input.min=shape.min[column];input.setAttribute('aria-label',label+' '+(index+1)+' '+shape.columns[column]);input.oninput=()=>{if(input.checkValidity()&&Number.isFinite(Number(input.value))){values[index][column]=Number(input.value);change(vector?values[0]:values);}};cell.append(input);row.append(cell);});table.append(row);
 });
 const bind=formEl('button','绑定变量或结果');bind.type='button';bind.onclick=()=>{const next={$ref:'flow.'};change(next);box.replaceWith(valueEditor(next,change,{label}));};box.append(table,bind);return box;
}
function renderStructuredParams(){
 const holder=$('structured-params');holder.replaceChildren();const step=selectedStep();if(!step)return;
 const handled=new Set(catalog[step.operation].fields.map(f=>f[0]));for(const k of ['code','targetCloud','arguments','outputBindings'])handled.add(k);
 const options={...extraParams[step.operation],...(!step.operation.startsWith('cloud_')?{roi:[0,0,100,100]}:{})};
 if(['condition','branch_merge','delay','variables','script','modbus_read','modbus_write','modbus_wait','s7_read','s7_write','mqtt_publish','mqtt_receive','tcp_exchange','udp_exchange','serial_exchange','opcua_read','opcua_write','opcua_browse','opcua_wait','camera_capture'].includes(step.operation))delete options.roi;
 for(const key of Object.keys(options))if((!functionalFieldVisible(step,key)||!socketFieldVisible(step,key)||!serialFieldVisible(step,key)))delete options[key];
 if(step.operation==='mqtt_publish'||step.operation==='variables'||step.operation==='opcua_write'||step.operation==='s7_write'||(step.operation==='modbus_write'&&!Object.hasOwn(step.params,'values')))options.value=0;
 if((isSocketStep(step)||isSerialStep(step))&&socketFieldVisible(step,'value')&&serialFieldVisible(step,'value'))options.value=step.params.encoding==='bytes'?[]:step.params.encoding==='structured'?{}:'';
 const defaults=functionalDefaults(step);
 const keys=[...new Set([...Object.keys(defaults),...Object.keys(step.params)])].filter(k=>!handled.has(k)&&functionalFieldVisible(step,k)&&socketFieldVisible(step,k)&&serialFieldVisible(step,k));
 for(const key of keys){
  const section=formEl('section',undefined,'parameter-value'),label=(step.operation==='mqtt_publish'||isSocketStep(step)||isSerialStep(step))&&key==='value'?'发送内容':fieldNames[key]||key;
  section.append(formEl('label',label,'section-caption'));const automatic=Object.hasOwn(defaults,key),value=Object.hasOwn(step.params,key)?step.params[key]:defaults[key];
  const remove=formEl('button',automatic?'恢复默认值':'移除此设置');remove.type='button';remove.disabled=automatic&&!Object.hasOwn(step.params,key);
  const update=v=>{step.params[key]=v;remove.disabled=false;dirty();};
  section.append((step.operation==='mqtt_publish'||isSocketStep(step)||isSerialStep(step))&&key==='value'?mqttValueEditor(value,update,step.params.encoding||'text'):automatic?numericParameterEditor(key,value,update):functionalValueEditor(key,value,update));
  remove.onclick=()=>{delete step.params[key];dirty();renderParams();};section.append(remove);holder.append(section);
 }
 const choices=Object.keys(options).filter(k=>!Object.hasOwn(step.params,k)&&!Object.hasOwn(defaults,k));if(choices.length){const select=formSelect(choices.map(k=>[k,fieldNames[k]||k]),choices[0],'可选设置');const add=formEl('button','添加设置');add.onclick=()=>{step.params[select.value]=structuredClone(options[select.value]);dirty();renderParams();};const row=formEl('div',undefined,'form-actions');row.append(select,add);holder.append(row);}
 if(step.operation==='script')renderScriptForms(step);
}
function renderDataMessage(holder,value){
 // Device errors and script exceptions can also contain serialized records.
 // Retain their full content while using the same table presentation as results.
 holder.replaceChildren(resultValueView(value));
}
function resultValueView(value,depth=0,labelFor=resultLabel){
 // A script may return serialized data as text. Present a table without changing its stored type.
 const parsed=depth<20?structuredText(value):null;
 if(parsed!==null){const box=formEl('div'),view=resultValueView(parsed,depth+1,labelFor);if(depth===0&&view.tagName==='DETAILS')view.open=true;box.append(formEl('small','结构化文本 · 表格预览','muted'),view);return box;}
 const parts=depth<20?DataPresentation.structuredParts(value):null;
 if(parts){const box=formEl('div',undefined,'structured-text-result');for(const part of parts){if(part.kind==='data'){const view=resultValueView(part.value,depth+1,labelFor);if(view.tagName==='DETAILS')view.open=true;box.append(view);}else if(part.value.trim())box.append(formEl('span',part.value,'script-log-text'));}return box;}
 if(value===null||typeof value!=='object')return formEl('span',resultText(value));
 if(depth>=20)return formEl('span','嵌套层级超过显示上限');
 const array=Array.isArray(value),entries=Object.entries(value),records=array&&value.length>0&&value.every(v=>v&&typeof v==='object'&&!Array.isArray(v));
 const matrix=array&&value.length>0&&value.every(v=>Array.isArray(v)&&v.length===value[0].length&&v.length>0&&v.length<=16&&v.every(n=>typeof n==='number'));
 const recordColumns=records?[...new Set(value.flatMap(v=>Object.keys(v)))]:[];
 const columns=records&&recordColumns.length<=20?recordColumns:matrix?value[0].map((_,i)=>'列 '+(i+1)):null;
 const details=formEl('details');details.open=depth===0;details.append(formEl('summary',(records?'记录表':matrix?'数值矩阵':array?'数组':'字段表')+' · '+entries.length+(array?' 行':' 项')));
 let built=false;details.ontoggle=()=>{if(!details.open||built)return;built=true;const wrap=formEl('div',undefined,'structured-result-scroll'),table=formEl('table',undefined,'form-table structured-result-table'),head=formEl('tr');
 head.append(formEl('th',array?'序号':'字段'));for(const title of columns||['值'])head.append(formEl('th',records?labelFor(title):title));table.append(head);let cursor=0;const more=formEl('button','显示更多');more.type='button';
 const append=()=>{for(const [key,item] of entries.slice(cursor,cursor+50)){const row=formEl('tr');row.append(formEl('td',array?Number(key)+1:labelFor(key)));for(const v of columns?(records?columns.map(c=>item[c]):item):[item]){const cell=formEl('td');cell.append(resultValueView(v,depth+1,labelFor));row.append(cell);}table.append(row);}cursor+=50;more.hidden=cursor>=entries.length;};more.onclick=append;append();wrap.append(table);details.append(wrap,more);};return details;
}
function scriptLogView(logs,labelFor=resultLabel){
 const box=formEl('div',undefined,'script-log-table'),table=formEl('table',undefined,'form-table'),head=formEl('tr');
 table.setAttribute('aria-label','脚本日志明细');for(const label of ['序号','内容类型','日志内容'])head.append(formEl('th',label));table.append(head);
 const entries=DataPresentation.logParts(logs),more=formEl('button','显示更多日志');more.type='button';let cursor=0;
 const append=()=>{for(const [index,entry] of entries.slice(cursor,cursor+50).entries()){
  const row=formEl('tr'),cell=formEl('td');cell.append(entry.kind==='data'?resultValueView(entry.value,0,labelFor):formEl('span',entry.value,'script-log-text'));
  row.append(formEl('td',cursor+index+1),formEl('td',entry.kind==='data'?'结构化数据':'文本'),cell);table.append(row);
 }cursor+=50;more.hidden=cursor>=entries.length;};more.onclick=append;append();box.append(table,more);return box;
}
function renderScriptForms(step){
 renderScriptVariables(step);
 if(!$('script-result-preview')){
  const section=formEl('details',undefined,'script-section');section.open=true;section.append(formEl('summary','脚本全部返回字段'));
  section.append(formEl('p','展示最近一次执行返回的全部结果，包含未绑定变量的字段。数组、结构体可逐层展开。','muted'));
  const preview=formEl('div');preview.id='script-result-preview';section.append(preview);$('script-tools').insertBefore(section,$('script-code').closest('details'));
 }
 const args=$('script-arguments');collectionEditor(args,structuredClone(step.params.arguments||{}),v=>{step.params.arguments=v;dirty();},{label:'脚本输入'});
 renderOutputBindings(step,$('script-outputs'));
}
function renderScriptVariables(step){
 let holder=$('script-variables');
 if(!holder){
  const section=formEl('details',undefined,'script-section');section.open=true;section.append(formEl('summary','脚本可用变量'));
  holder=formEl('div');holder.id='script-variables';section.append(holder);$('script-tools').prepend(section);
 }
 renderAvailableVariables(step,holder,true);
}
function renderModuleVariables(){
 const step=selectedStep();let section=$('module-variables-section');
 if(!section){
  section=formEl('details',undefined,'script-section module-variable-section');section.id='module-variables-section';section.open=true;
  section.append(formEl('summary','可用变量 · 定义与当前值'));
  const holder=formEl('div');holder.id='module-variables';section.append(holder);
  $('structured-params').after(section);
 }
 section.hidden=!step||step.operation==='script';
 if(step&&step.operation!=='script')renderAvailableVariables(step,$('module-variables'),false);
}
function refreshAvailableVariables(){
 const step=selectedStep();if(!step)return;
 if(step.operation==='script')renderScriptVariables(step);else renderModuleVariables();
}
function renderAvailableVariables(step,holder,script){
 holder.replaceChildren();
 const snapshot=variableSnapshot?.projectId===project.id?variableSnapshot:null;
 const scopes=[
  {id:'global',label:'全局',initial:{},values:snapshot?.global,types:snapshot?.globalTypes||{}},
  {id:'flow',label:'流程',initial:project.variables||{},values:snapshot?.flow,types:project.variableTypes||{}},
  {id:'module',label:'当前模块',initial:step.variables||{},values:snapshot?.modules?.[step.id],types:step.variableTypes||{}}
 ];
 const toolbar=formEl('div',undefined,'form-actions'),search=formEl('input'),refresh=formEl('button','读取变量值'),manage=formEl('button','管理变量定义');
 search.type='search';search.placeholder='搜索变量名';search.setAttribute('aria-label',script?'搜索脚本可用变量':'搜索模块可用变量');refresh.type=manage.type='button';
 const scopeFilter=formSelect([['','全部作用域'],['global','全局变量'],['flow','流程变量'],['module','当前模块变量']],'',script?'脚本变量作用域':'模块变量作用域');
 refresh.onclick=safe(async()=>{
  refresh.disabled=true;const projectId=project.id;
  try{const value=await api('runtime/variables/read',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({project:currentProject()})});
   if(project.id!==projectId)return;variableSnapshot={...value,projectId};if(selectedStep()?.id===step.id)refreshAvailableVariables();
  }finally{refresh.disabled=running;}
 });
 manage.onclick=()=>$('variables-open').click();toolbar.append(search,scopeFilter,refresh,manage);holder.append(toolbar);
 holder.append(formEl('p','列出全局、流程及当前模块变量。最近读取值为快照，执行时重新取值。'+(script?'添加为输入后，可在输入参数表中修改名称和绑定。':'通过参数旁的“绑定变量或结果”使用变量；其他模块的定义在变量管理中查看。'),'muted'));
 const wrap=formEl('div',undefined,'script-variable-scroll'),table=formEl('table',undefined,'form-table script-variable-table'),head=formEl('tr'),body=formEl('tbody');
 table.setAttribute('aria-label',script?'脚本可用变量定义与值':'模块可用变量定义与值');for(const text of ['作用域','变量名','固定类型','工程初始值','最近读取值',...(script?['操作']:[])])head.append(formEl('th',text));table.append(head,body);wrap.append(table);holder.append(wrap);
 const more=formEl('button','显示更多变量');more.type='button';holder.append(more);let limit=50;
 const entries=scopes.flatMap(scope=>[...new Set([...Object.keys(scope.initial),...Object.keys(scope.values||{}),...Object.keys(scope.types)])].map(name=>({scope,name})));
 const draw=()=>{
  body.replaceChildren();const rows=entries.filter(({scope,name})=>(!scopeFilter.value||scopeFilter.value===scope.id)&&name.toLocaleLowerCase().includes(search.value.trim().toLocaleLowerCase()));
  for(const {scope,name} of rows.slice(0,limit)){
   const row=formEl('tr'),initial=formEl('td'),current=formEl('td'),action=formEl('td'),add=formEl('button','添加为输入');add.type='button';add.disabled=running;
   initial.append(Object.hasOwn(scope.initial,name)?resultValueView(scope.initial[name]):formEl('span',scope.id==='global'?'全局持久值':'未定义','muted'));
   current.append(scope.values&&Object.hasOwn(scope.values,name)?resultValueView(scope.values[name]):formEl('span',snapshot?'尚无当前值':'尚未读取','muted'));
   add.setAttribute('aria-label',scope.label+'变量 '+name+' 添加为脚本输入');
   add.onclick=()=>{
    if(running||selectedStep()?.id!==step.id)return;
    const args=step.params.arguments||(step.params.arguments={});let key=name,index=2;while(Object.hasOwn(args,key))key=name+'_'+index++;
    args[key]={$ref:scope.id+'.'+name};dirty();renderScriptForms(step);status('已添加脚本输入 '+key+'，执行时读取'+scope.label+'变量 '+name);
   };
   row.append(formEl('td',scope.label),formEl('th',name),formEl('td',VariableTypes.labels[scope.types[name]]||'动态'),initial,current);if(script){action.append(add);row.append(action);}body.append(row);
  }
  more.hidden=rows.length<=limit;
  if(!rows.length){const row=formEl('tr'),cell=formEl('td',entries.length?'没有匹配的变量':'尚无变量定义，可点击“管理变量定义”添加；全局变量需先读取。','muted');cell.colSpan=script?6:5;row.append(cell);body.append(row);}
 };
 search.oninput=scopeFilter.onchange=()=>{limit=50;draw();};more.onclick=()=>{limit+=50;draw();};draw();
}
function refreshScriptResult(){
 const holder=$('script-result-preview'),step=selectedStep();if(!holder||step?.operation!=='script')return;
 const item=results.find(r=>r.id===step.id);
 if(holder.previewStep===step.id&&holder.previewResult===item)return;
 holder.previewStep=step.id;holder.previewResult=item;holder.replaceChildren();
 if(!item||item.error||item.skipped){holder.append(formEl('p',!item?'尚未运行':item.error?'模块执行失败，请查看运行日志':'模块已跳过','muted'));return;}
 const entries=Object.entries(item.output?.result||{});
 if(!entries.length){holder.append(formEl('p','脚本未返回结果字段','muted'));return;}
 holder.append(resultValueView(entries.map(([field,value])=>({field,type:formTypes[formType(value)]||'未知',value})),0,key=>({field:'结果字段',type:'实际类型',value:'返回值'})[key]||key));
}
function renderOutputBindings(step,holder){
 const prefix=step.operation==='plugin'?'插件':'脚本';holder.replaceChildren();const rows=step.params.outputBindings||[];const table=formEl('table',undefined,'form-table'),head=formEl('tr');for(const t of ['结果字段','写入范围','变量名','实际类型','最近输出值','操作'])head.append(formEl('th',t));table.append(head);
 rows.forEach((binding,index)=>{const row=formEl('tr'),field=step.operation==='plugin'?formSelect((pluginInfo(step).op?.outputs||[]).map(f=>[f.key,f.label]),binding.field,'插件输出字段'):formEl('input'),name=formEl('input');if(step.operation==='plugin'&&binding.field&&!Array.from(field.options).some(o=>o.value===binding.field))field.append(new Option(binding.field+'（嵌套或未声明）',binding.field));field.value=binding.field;name.value=binding.name;field.required=true;name.required=true;name.pattern='[A-Za-z_][A-Za-z0-9_]{0,63}';field.setAttribute('aria-label',prefix+'输出字段');name.setAttribute('aria-label',prefix+'输出变量名');const scope=formSelect([['flow','流程'],['global','全局'],['module','当前模块']],binding.scope,prefix+'输出范围');const save=()=>{rows[index]={field:field.value.trim(),scope:scope.value,name:name.value.trim()};step.params.outputBindings=rows;row.dataset.outputField=field.value.trim();refreshOutputBindingValues();dirty();};field.oninput=save;field.onchange=save;name.oninput=save;scope.onchange=save;const remove=formEl('button','删除');remove.onclick=()=>{rows.splice(index,1);step.params.outputBindings=rows;dirty();renderOutputBindings(step,holder);};for(const e of [field,scope,name]){const cell=formEl('td');cell.append(e);row.append(cell);}row.dataset.outputField=binding.field;row.dataset.outputStep=step.id;const actualType=formEl('td',undefined,'binding-actual-type'),actualValue=formEl('td',undefined,'binding-actual-value'),action=formEl('td');action.append(remove);row.append(actualType,actualValue,action);table.append(row);});
 const add=formEl('button','添加输出绑定');add.onclick=()=>{const defaultField=step.operation==='plugin'?(pluginInfo(step).op?.outputs.find(f=>f.key==='passed')?.key||pluginInfo(step).op?.outputs[0]?.key||''):'passed';rows.push({field:defaultField,scope:'flow',name:defaultField});step.params.outputBindings=rows;dirty();renderOutputBindings(step,holder);};const scroll=formEl('div',undefined,'output-binding-scroll');table.classList.add('output-binding-table');table.setAttribute('aria-label',prefix+'输出绑定及最近值');scroll.append(table);holder.append(scroll,add);refreshOutputBindingValues();
 const fields=results.find(r=>r.id===step.id&&!r.error&&!r.skipped)?.output?.result;
 const knownFields=fields?collectBindingFields(fields):(bindingResultFields.get(step.id)||[]);
 const fieldList=formEl('datalist');fieldList.id=holder.id+'-known-fields';for(const [name,type] of knownFields)fieldList.append(new Option(name+' · '+type,name));holder.append(fieldList);
 Array.from(table.querySelectorAll('tr')).slice(1).forEach((row,index)=>{
  const field=row.cells[0].querySelector('input'),scope=row.cells[1].querySelector('select'),name=row.cells[2].querySelector('input');if(field)field.setAttribute('list',fieldList.id);
  const list=formEl('datalist');list.id=holder.id+'-variables-'+index;name.setAttribute('list',list.id);holder.append(list);
  const update=()=>{list.replaceChildren(...bindingFields(scope.value).filter(([key])=>!key.includes('.')).map(([key,type])=>new Option(key+' · '+type,key)));};scope.addEventListener('change',update);update();
 });
 holder.append(formEl('p','最近输出值来自本次页面运行结果，并不代表变量已提交。变量当前保存值请查看变量管理。结果字段及变量名可选择已有项，也可填写新名称。','muted'));
}

// Refresh only preview cells so polling never replaces an in-progress binding edit.
function refreshOutputBindingValues(){
 refreshScriptResult();
 for(const row of document.querySelectorAll('[data-output-field][data-output-step]')){
  const result=results.find(item=>item.id===row.dataset.outputStep),field=row.dataset.outputField;
  if(row.previewResult===result&&row.previewField===field&&row.previewInitialized)continue;
  row.previewResult=result;row.previewField=field;row.previewInitialized=true;
  const type=row.querySelector('.binding-actual-type'),cell=row.querySelector('.binding-actual-value');
  const resolved=result&&!result.error&&!result.skipped?DataPresentation.fieldValue(result.output?.result,field):{found:false};
  type.textContent=resolved.found?(formTypes[formType(resolved.value)]||'未知'):'—';cell.replaceChildren();
  if(resolved.found)cell.append(resultValueView(resolved.value));
  else cell.append(formEl('span',!result?'尚未运行':result.error?'模块执行失败':result.skipped?'模块已跳过':'结果中没有该字段','muted'));
 }
}
