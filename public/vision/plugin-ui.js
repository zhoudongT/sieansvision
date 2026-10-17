'use strict';
let installedPlugins=[],pluginReloadSupported=false;
function pluginOptions(){return installedPlugins.filter(p=>p.enabled).flatMap(p=>p.operators.map(op=>({plugin:p,op,key:p.id+'/'+op.id})));}
function pluginInfo(step){const p=installedPlugins.find(p=>p.id===step?.params?.pluginId);return {plugin:p,op:p?.operators.find(o=>o.id===step?.params?.operatorId)};}
function stepDefinition(step){if(step?.operation!=='plugin')return catalog[step?.operation];const info=pluginInfo(step);return {...catalog.plugin,name:info.op?.name||'未找到的算子插件',description:info.op?.description||'请在插件管理中检查安装状态与工程固定版本。'};}
function pluginDefaults(key){const option=pluginOptions().find(o=>o.key===key)||pluginOptions()[0];if(!option)throw Error('没有可用算子插件，请检查插件管理');return {pluginId:option.plugin.id,pluginVersion:option.plugin.version,operatorId:option.op.id,arguments:Object.fromEntries(option.op.parameters.filter(f=>Object.hasOwn(f,'default')).map(f=>[f.key,structuredClone(f.default)])),outputBindings:[]};}
function renderPluginLibrary(query){
 const options=pluginOptions().filter(o=>(o.op.name+' '+o.plugin.name+' '+o.key).toLowerCase().includes(query));if(!options.length)return 0;
 const group=formEl('details',undefined,'operator-group');group.open=Boolean(query);const title=formEl('summary','算子插件');title.append(formEl('span',String(options.length)));group.append(title);
 for(const option of options){const button=formEl('button',undefined,'operator');button.append(formEl('span','▧','glyph'),formEl('span',option.op.name));button.title='添加 '+option.op.name;button.disabled=running;enablePointerDrag(button,{operation:'plugin',pluginKey:option.key});button.onclick=safe(()=>addStep('plugin',undefined,option.key));group.append(button);}
 $('operators').append(group);return options.length;
}
function renderPluginParams(step){
 const holder=$('structured-params');holder.replaceChildren();const info=pluginInfo(step),key=step.params.pluginId+'/'+step.params.operatorId;
 const options=pluginOptions().map(o=>[o.key,o.op.name+' · '+o.plugin.name]);if(!options.some(([id])=>id===key))options.unshift([key,'当前插件不可用']);
 const choose=formSelect(options,key,'插件算子');choose.onchange=()=>{step.params=pluginDefaults(choose.value);dirty();renderPipeline();renderParams();};holder.append(formEl('label','选择算子','section-caption'),choose);
 holder.append(formEl('p','工程固定版本：'+(step.params.pluginVersion||'未设置')+' · 已安装：'+(info.plugin?.version||'未安装'),'muted'));
 if(!info.plugin?.enabled||!info.op||step.params.pluginVersion!==info.plugin.version){holder.append(formEl('p','插件停用、缺失或版本不匹配。请恢复工程所需插件，或使用已安装版本并重新配置参数。','form-notice'));if(info.plugin?.enabled&&info.op){const reset=formEl('button','采用已安装版本并重置参数');reset.onclick=()=>{step.params=pluginDefaults(key);dirty();renderPipeline();renderParams();};holder.append(reset);}return;}
 const table=formEl('table',undefined,'form-table plugin-parameters');const head=formEl('tr');for(const name of ['参数','值 / 绑定'])head.append(formEl('th',name));table.append(head);
 step.params.arguments??={};
 for(const f of info.op.parameters){
   const row=formEl('tr'),cell=formEl('td');row.append(formEl('td',f.label));let v=step.params.arguments[f.key];if(v===undefined&&Object.hasOwn(f,'default'))v=structuredClone(f.default);
   const isRef=formType(v)==='reference';
   if(isRef){cell.append(referenceEditor(v,next=>{step.params.arguments[f.key]=next;dirty();},f.label));}
   else if(f.type==='string'&&!f.choices&&DataPresentation.structuredParts(v)){cell.append(structuredTextEditor(v,next=>{step.params.arguments[f.key]=next;dirty();},f.label));}
   else if(f.columns){const tableHolder=formEl('div',undefined,'record-parameter');renderRecordParameter(tableHolder,f,v||[],next=>{step.params.arguments[f.key]=next;dirty();});cell.append(tableHolder);}
   else if(['array','object'].includes(f.type)){cell.append(valueEditor(v??(f.type==='array'?[]:{}),next=>{step.params.arguments[f.key]=next;dirty();},{label:f.label}));}
   else {
     let input;if(f.choices){input=formSelect(f.choices.map((c,i)=>[String(i),c.label]),String(f.choices.findIndex(c=>c.value===v)),f.label);input.onchange=()=>{step.params.arguments[f.key]=f.choices[Number(input.value)].value;dirty();};}
     else if(f.type==='boolean'){input=formSelect([['true','是'],['false','否']],String(v??false),f.label);input.onchange=()=>{step.params.arguments[f.key]=input.value==='true';dirty();};}
     else {input=formEl('input');input.type=['number','integer'].includes(f.type)?'number':'text';input.value=v??'';input.required=!!f.required;input.setAttribute('aria-label',f.label);if(input.type==='number'){input.step=f.type==='integer'?'1':'any';if(f.minimum!==undefined)input.min=f.minimum;if(f.maximum!==undefined)input.max=f.maximum;}input.oninput=()=>{if(!input.checkValidity())return;if(input.value===''&&!f.required)delete step.params.arguments[f.key];else step.params.arguments[f.key]=input.type==='number'?Number(input.value):input.value;dirty();};}
     cell.append(input);
   }
   const bind=formEl('button',isRef?'使用固定值':'绑定变量或结果');bind.onclick=()=>{step.params.arguments[f.key]=isRef?structuredClone(f.default??({number:0,integer:0,string:'',boolean:false,array:[],object:{}}[f.type])):{$ref:'flow.'};dirty();renderParams();};cell.append(bind);row.append(cell);table.append(row);
 }
 holder.append(formEl('h3','输入参数'),table);
 const outputs=formEl('div');outputs.id='plugin-outputs';holder.append(formEl('h3','输出变量绑定'),outputs);renderOutputBindings(step,outputs);
 const outputTable=formEl('table',undefined,'form-table');const h=formEl('tr');for(const t of ['结果字段','含义','类型'])h.append(formEl('th',t));outputTable.append(h);
 for(const f of info.op.outputs){const r=formEl('tr');r.append(formEl('td',f.key),formEl('td',f.label),formEl('td',formTypes[f.type]||'整数'));outputTable.append(r);}
 holder.append(formEl('h3','算子输出说明'),outputTable);
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
  const actions=formEl('td'),remove=formEl('button','删除');remove.type='button';remove.onclick=()=>{values.splice(index,1);change(values);renderRecordParameter(holder,field,values,change);};actions.append(remove);row.append(actions);table.append(row);
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
