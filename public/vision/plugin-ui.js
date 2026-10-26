'use strict';
let installedPlugins=[],pluginReloadSupported=false;
function pluginOptions(){return installedPlugins.filter(p=>p.enabled).flatMap(p=>p.operators.map(op=>({plugin:p,op,key:p.id+'/'+op.id})));}
function pluginInfo(step){const p=installedPlugins.find(p=>p.id===step?.params?.pluginId);return {plugin:p,op:p?.operators.find(o=>o.id===step?.params?.operatorId)};}
function stepDefinition(step){if(step?.operation!=='plugin')return catalog[step?.operation];const info=pluginInfo(step);return {...catalog.plugin,name:info.op?.name||'未找到的算子插件',description:info.op?.description||'请在插件管理中检查安装状态与工程固定版本。'};}
function pluginDefaults(key){const option=pluginOptions().find(o=>o.key===key)||pluginOptions()[0];if(!option)throw Error('没有可用算子插件，请检查插件管理');return {pluginId:option.plugin.id,pluginVersion:option.plugin.version,operatorId:option.op.id,arguments:Object.fromEntries(option.op.parameters.filter(f=>Object.hasOwn(f,'default')).map(f=>[f.key,structuredClone(f.default)])),inputs:Object.fromEntries((option.op.inputs||[]).filter(f=>Object.hasOwn(f,'default')).map(f=>[f.key,structuredClone(f.default)])),outputBindings:[]};}
function renderPluginLibrary(query){
 const options=pluginOptions().filter(o=>(o.op.name+' '+o.plugin.name+' '+o.key).toLowerCase().includes(query));if(!options.length)return 0;
 const group=formEl('details',undefined,'operator-group');group.open=Boolean(query);const title=formEl('summary','算子插件');title.append(formEl('span',String(options.length)));group.append(title);
 for(const option of options){const button=formEl('button',undefined,'operator');button.append(formEl('span','▧','glyph'),formEl('span',option.op.name));button.title='添加 '+option.op.name;button.disabled=running;enablePointerDrag(button,{operation:'plugin',pluginKey:option.key});button.onclick=safe(()=>addStep('plugin',undefined,option.key));group.append(button);}
 $('operators').append(group);return options.length;
}
const pluginParamTabs=new WeakMap();
function pluginFieldType(f){
 if(f.columns)return '记录表';
 if(f.items)return (formTypes[f.items.type]||'整数')+'数组';
 return formTypes[f.type]||'整数';
}
function pluginFixedValue(f){
 if(Object.hasOwn(f,'default'))return structuredClone(f.default);
 if(f.choices)return f.choices[0].value;
 if(f.properties)return Object.fromEntries(f.properties.filter(c=>c.required||Object.hasOwn(c,'default')).map(c=>[c.key,pluginFixedValue(c)]));
 return {number:0,integer:0,string:'',boolean:false,array:[],object:{}}[f.type];
}
function pluginFieldEditor(f,v,change,label=f.label){
 const box=formEl('div',undefined,'plugin-field-editor'),isRef=formType(v)==='reference';
 const save=next=>change(next);
 if(isRef)box.append(referenceEditor(v,save,label));
 else if(f.properties){
  const current=v&&typeof v==='object'&&!Array.isArray(v)?structuredClone(v):{};
  if(v!==undefined&&(!v||typeof v!=='object'||Array.isArray(v)))box.append(formEl('p','当前结构无效，请恢复默认值后编辑。','form-notice'));
  else pluginFieldRows(box,f.properties,current,next=>save(next),label+' · ');
 }else if(f.items){
  const values=Array.isArray(v)?structuredClone(v):[];
  if(v!==undefined&&!Array.isArray(v))box.append(formEl('p','当前数组无效，请恢复默认值后编辑。','form-notice'));
  else{
   const table=formEl('table',undefined,'form-table'),head=formEl('tr');head.append(formEl('th','序号'),formEl('th','值'),formEl('th','操作'));table.append(head);
   let cursor=0;const more=formEl('button','显示更多');more.type='button';
   const append=()=>{for(let index=cursor;index<Math.min(cursor+50,values.length);index++){
    const row=formEl('tr'),cell=formEl('td'),action=formEl('td'),remove=formEl('button','删除');remove.type='button';remove.disabled=values.length<=(f.minimumRows??0);
    cell.append(pluginFieldEditor({...f.items,required:true},values[index],next=>{values[index]=next;save(values);},label+' 第 '+(index+1)+' 项'));
    remove.onclick=()=>{values.splice(index,1);save(values);box.replaceWith(pluginFieldEditor(f,values,change,label));};action.append(remove);row.append(formEl('td',index+1),cell,action);table.append(row);
   }cursor+=50;more.hidden=cursor>=values.length;};more.onclick=append;append();
   const add=formEl('button','添加一项');add.type='button';add.disabled=values.length>=(f.maximumRows??1000);add.onclick=()=>{values.push(pluginFixedValue(f.items));save(values);box.replaceWith(pluginFieldEditor(f,values,change,label));};
   box.append(formEl('p',values.length+' 项 · 允许 '+(f.minimumRows??0)+'–'+(f.maximumRows??1000)+' 项','muted'),table,more,add);
  }
 }else if(f.columns){const tableHolder=formEl('div',undefined,'record-parameter');renderRecordParameter(tableHolder,f,v??[],save);box.append(tableHolder);}
 else if(['array','object'].includes(f.type))box.append(valueEditor(v??(f.type==='array'?[]:{}),save,{label}));
 else if(f.type==='string'&&!f.choices&&DataPresentation.structuredParts(v))box.append(structuredTextEditor(v,save,label));
 else{
  let input;
  if(f.choices||f.type==='boolean'){
   const choices=f.choices||[{value:true,label:'是'},{value:false,label:'否'}];
   input=formSelect([['','请选择…'],...choices.map((c,i)=>[String(i),c.label])],v===undefined?'':String(choices.findIndex(c=>c.value===v)),label);input.required=!!f.required;
   input.onchange=()=>save(input.value===''?undefined:choices[Number(input.value)].value);
  }else{
   input=formEl('input');input.type=['number','integer'].includes(f.type)?'number':'text';input.value=v??'';input.required=!!f.required;input.setAttribute('aria-label',label);
   if(input.type==='number'){input.step=f.type==='integer'?'1':'any';if(f.minimum!==undefined)input.min=f.minimum;if(f.maximum!==undefined)input.max=f.maximum;}
   input.oninput=()=>{if(!input.checkValidity())return;save(input.value===''&&!f.required?undefined:input.type==='number'?Number(input.value):input.value);};
  }
  box.append(input);
 }
 const bind=formEl('button',isRef?'使用固定值':'绑定变量或结果');bind.type='button';bind.setAttribute('aria-label',label+' '+bind.textContent);
 bind.onclick=()=>{const next=isRef?pluginFixedValue(f):{$ref:'flow.'};save(next);box.replaceWith(pluginFieldEditor(f,next,change,label));};box.append(bind);
 if(!isRef){const reset=formEl('button','恢复默认值');reset.type='button';reset.setAttribute('aria-label',label+' 恢复默认值');reset.onclick=()=>{const next=pluginFixedValue(f);save(next);box.replaceWith(pluginFieldEditor(f,next,change,label));};box.append(reset);}
 return box;
}
function pluginFieldRows(holder,fields,values,change,prefix=''){
 const groups=new Map();for(const f of fields){const group=f.group||'';if(!groups.has(group))groups.set(group,[]);groups.get(group).push(f);}
 for(const [group,items] of groups){
  if(group)holder.append(formEl('h4',group));const table=formEl('table',undefined,'form-table plugin-parameters'),head=formEl('tr');head.append(formEl('th','名称 / 类型'),formEl('th','值 / 绑定'));table.append(head);
  for(const f of items){
   const row=formEl('tr'),name=formEl('td'),cell=formEl('td');name.append(formEl('strong',f.label+(f.required?' *':'')),formEl('p',pluginFieldType(f)+(f.unit?' · '+f.unit:''),'muted'));if(f.description)name.append(formEl('small',f.description,'muted'));
   if(f.minimum!==undefined||f.maximum!==undefined)name.append(formEl('p','范围：'+(f.minimum??'不限')+' – '+(f.maximum??'不限'),'muted'));
   const v=Object.hasOwn(values,f.key)?values[f.key]:Object.hasOwn(f,'default')?structuredClone(f.default):undefined;
   cell.append(pluginFieldEditor(f,v,next=>{if(next===undefined)delete values[f.key];else values[f.key]=next;change(values);},prefix+f.label));row.append(name,cell);table.append(row);
  }holder.append(table);
 }
}
function renderPluginParams(step){
 const holder=$('structured-params');holder.replaceChildren();const info=pluginInfo(step),key=step.params.pluginId+'/'+step.params.operatorId;
 const options=pluginOptions().map(o=>[o.key,o.op.name+' · '+o.plugin.name]);if(!options.some(([id])=>id===key))options.unshift([key,'当前插件不可用']);
 const choose=formSelect(options,key,'插件算子');choose.onchange=()=>{step.params=pluginDefaults(choose.value);dirty();renderPipeline();renderParams();};holder.append(formEl('label','选择算子','section-caption'),choose);
 holder.append(formEl('p','工程固定版本：'+(step.params.pluginVersion||'未设置')+' · 已安装：'+(info.plugin?.version||'未安装'),'muted'));
 if(!info.plugin?.enabled||!info.op||step.params.pluginVersion!==info.plugin.version){holder.append(formEl('p','插件停用、缺失或版本不匹配。请恢复工程所需插件，或使用已安装版本并重新配置参数。','form-notice'));if(info.plugin?.enabled&&info.op){const reset=formEl('button','采用已安装版本并重置参数');reset.onclick=()=>{step.params=pluginDefaults(key);dirty();renderPipeline();renderParams();};holder.append(reset);}return;}
 holder.append(formEl('p',info.op.description,'muted'));
 const tabbar=formEl('div',undefined,'plugin-param-tabs'),panels=[],buttons=[],names=['输入','参数','输出'];tabbar.setAttribute('role','tablist');tabbar.setAttribute('aria-label','模块配置');tabbar.style.cssText='display:flex;gap:6px;margin:12px 0';
 const select=index=>{pluginParamTabs.set(step,index);panels.forEach((p,i)=>{p.hidden=i!==index;buttons[i].setAttribute('aria-selected',String(i===index));buttons[i].tabIndex=i===index?0:-1;buttons[i].style.fontWeight=i===index?'700':'400';});};
 names.forEach((name,index)=>{const button=formEl('button',name),panel=formEl('section');button.type='button';button.id='plugin-tab-'+index;button.setAttribute('role','tab');button.setAttribute('aria-controls','plugin-panel-'+index);panel.id='plugin-panel-'+index;panel.setAttribute('role','tabpanel');panel.setAttribute('aria-labelledby',button.id);button.onclick=()=>select(index);button.onkeydown=event=>{if(!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;event.preventDefault();const next=event.key==='Home'?0:event.key==='End'?2:(index+(event.key==='ArrowRight'?1:2))%3;select(next);buttons[next].focus();};panel.addEventListener('invalid',()=>select(index),true);buttons.push(button);panels.push(panel);tabbar.append(button);});holder.append(tabbar,...panels);
 panels[0].append(formEl('h3','模块输入'),formEl('p','数据通道：'+({none:'无必需图像 / 点云通道',image:'图像',cloud:'点云',depth:'深度图'}[info.op.input])+'。由流程中的输入连线传入。','muted'));
 step.params.inputs??={};step.params.arguments??={};
 if(info.op.inputs?.length)pluginFieldRows(panels[0],info.op.inputs,step.params.inputs,next=>{step.params.inputs=next;dirty();});else panels[0].append(formEl('p','此算子未声明额外命名输入。','muted'));
 panels[1].append(formEl('h3','模块参数'));pluginFieldRows(panels[1],info.op.parameters,step.params.arguments,next=>{step.params.arguments=next;dirty();});
 if(!info.op.parameters.length)panels[1].append(formEl('p','此算子无需配置参数。','muted'));
 const outputs=formEl('div');outputs.id='plugin-outputs';panels[2].append(formEl('h3','输出变量绑定'),outputs);renderOutputBindings(step,outputs);
 const table=formEl('table',undefined,'form-table'),head=formEl('tr');for(const name of ['结果字段','含义','类型','要求','操作'])head.append(formEl('th',name));table.append(head);
 const appendOutput=(f,path=f.key)=>{const row=formEl('tr'),action=formEl('td'),bind=formEl('button','添加绑定');bind.type='button';bind.setAttribute('aria-label','绑定输出 '+path);bind.onclick=()=>{const rows=step.params.outputBindings??=[];const target=f.key;let name=target,suffix=1;while(rows.some(r=>r.scope==='flow'&&r.name===name))name=target.slice(0,58)+'_'+suffix++;rows.push({field:path,scope:'flow',name});dirty();renderOutputBindings(step,outputs);};action.append(bind);row.append(formEl('td',path),formEl('td',f.label),formEl('td',pluginFieldType(f)),formEl('td',f.required?'必需':'可选'),action);table.append(row);if(f.properties)for(const child of f.properties)appendOutput(child,path+'.'+child.key);};
 for(const f of info.op.outputs)appendOutput(f);panels[2].append(formEl('h3','结果字段'),table);select(pluginParamTabs.get(step)??1);
}
async function loadOperatorPlugins(){const response=await api('plugins');installedPlugins=response.plugins;pluginReloadSupported=response.canReload===true;renderLibrary();renderPipeline();renderParams();}
function renderRecordParameter(holder,field,values,change){
 if(!Array.isArray(values)||values.some(row=>!row||typeof row!=='object'||Array.isArray(row)||Object.keys(row).some(key=>!field.columns.some(c=>c.key===key)))){
  const reset=formEl('button','恢复默认表格');reset.type='button';reset.onclick=()=>{const next=structuredClone(field.default||[]);change(next);renderRecordParameter(holder,field,next,change);};holder.replaceChildren(formEl('p','表格格式与算子定义不一致。请修正绑定来源，或恢复默认表格后编辑。','form-notice'),reset);return;
 }
 holder.replaceChildren();const table=formEl('table',undefined,'form-table record-table'),head=formEl('tr');
 head.append(formEl('th','序号'));for(const c of field.columns)head.append(formEl('th',c.label));head.append(formEl('th','操作'));table.append(head);
 let cursor=0;const more=formEl('button','显示更多');more.type='button';
 const append=()=>{for(let index=cursor;index<Math.min(cursor+50,values.length);index++){
  const row=formEl('tr');row.append(formEl('td',index+1));
  for(const c of field.columns){const cell=formEl('td');let input;
   const isReference=formType(values[index][c.key])==='reference',label=field.label+' 第 '+(index+1)+' 行 '+c.label;
   if(isReference){input=referenceEditor(values[index][c.key],next=>{values[index][c.key]=next;change(values);},label);}
   else if(c.type==='boolean'){input=formSelect([['true','是'],['false','否']],String(values[index][c.key]),field.label+' 第 '+(index+1)+' 行 '+c.label);input.onchange=()=>{values[index][c.key]=input.value==='true';change(values);};}
   else if(c.choices){input=formSelect(c.choices.map((o,i)=>[String(i),o.label]),String(c.choices.findIndex(o=>o.value===values[index][c.key])),field.label+' 第 '+(index+1)+' 行 '+c.label);input.onchange=()=>{values[index][c.key]=c.choices[Number(input.value)].value;change(values);};}
   else{input=formEl('input');input.type=['number','integer'].includes(c.type)?'number':'text';input.value=values[index][c.key]??'';input.required=true;input.setAttribute('aria-label',field.label+' 第 '+(index+1)+' 行 '+c.label);if(input.type==='number'){input.step=c.type==='integer'?'1':'any';if(c.minimum!==undefined)input.min=c.minimum;if(c.maximum!==undefined)input.max=c.maximum;}input.oninput=()=>{if(input.checkValidity()){values[index][c.key]=input.type==='number'?Number(input.value):input.value;change(values);}};}
   const bind=formEl('button',isReference?'使用固定值':'绑定变量或结果');bind.type='button';bind.setAttribute('aria-label',label+' '+(isReference?'使用固定值':'绑定变量或结果'));
   bind.onclick=()=>{values[index][c.key]=isReference?structuredClone(c.default??c.choices?.[0]?.value??({number:0,integer:0,string:'',boolean:false}[c.type])):{$ref:'flow.'};change(values);renderRecordParameter(holder,field,values,change);};
   cell.append(input,bind);row.append(cell);
  }
  const actions=formEl('td'),remove=formEl('button','删除');remove.type='button';remove.disabled=values.length<=(field.minimumRows??0);remove.onclick=()=>{values.splice(index,1);change(values);renderRecordParameter(holder,field,values,change);};actions.append(remove);row.append(actions);table.append(row);
 }cursor+=50;more.hidden=cursor>=values.length;};more.onclick=append;append();
 const add=formEl('button','添加一行');add.type='button';add.disabled=values.length>=(field.maximumRows??1000);add.onclick=()=>{values.push(Object.fromEntries(field.columns.map(c=>[c.key,structuredClone(c.default??c.choices?.[0]?.value??({number:0,integer:0,string:'',boolean:false}[c.type]))])));change(values);renderRecordParameter(holder,field,values,change);};
 holder.append(formEl('p',`${values.length} 行 · 允许 ${field.minimumRows??0}–${field.maximumRows??1000} 行`,'muted'),table,more,add);
}
function renderPluginManager(){
 const reloadButton=formEl('button','重新扫描插件');reloadButton.type='button';reloadButton.disabled=running;reloadButton.hidden=!pluginReloadSupported;
 reloadButton.onclick=safe(async()=>{if(running)return;reloadButton.disabled=true;try{const response=await api('plugins/reload',{method:'POST'});installedPlugins=response.plugins;renderLibrary();renderPipeline();renderParams();renderPluginManager();}finally{reloadButton.disabled=running;}});
 const holder=$('plugin-list');holder.replaceChildren(reloadButton);const table=formEl('table',undefined,'form-table');const head=formEl('tr');for(const text of ['插件','版本','算子','状态','操作'])head.append(formEl('th',text));table.append(head);
 for(const p of installedPlugins){const row=formEl('tr'),actions=formEl('td'),state=formEl('td');state.append(resultValueView(p.error||p.status));row.append(formEl('td',p.name),formEl('td',p.version),formEl('td',p.operators.map(o=>o.name).join('、')),state);if(!p.error){const button=formEl('button',p.enabled?'停用':'启用');button.disabled=running;button.onclick=safe(async()=>{if(running)return;installedPlugins=(await api('plugins/'+encodeURIComponent(p.id),{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({enabled:!p.enabled})})).plugins;renderPluginManager();renderLibrary();renderPipeline();renderParams();});actions.append(button);}row.append(actions);table.append(row);}
 holder.append(table);
}
function initPluginUI(){
 $('plugins-open').onclick=safe(async()=>{if(running)return;await loadOperatorPlugins();renderPluginManager();$('plugins-dialog').showModal();});
 return loadOperatorPlugins();
}
