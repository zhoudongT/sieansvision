(function(root,factory){
 'use strict';
 const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.DataPresentation=api;
})(typeof globalThis!=='undefined'?globalThis:this,function(){
 'use strict';
 // Recognize complete objects/arrays in plain, prefixed and multiline script logs.
 // Never execute log text, or change the value returned by the script.
 function logParts(input,preserve=false){
  const text=String(input??''),parts=[];let cursor=0,start=0;
  const plain=end=>{const raw=text.slice(start,end),value=preserve?raw:raw.trim();if(value)parts.push({kind:'text',value});};
  while(cursor<text.length){
   if(text[cursor]!=='{'&&text[cursor]!=='['){cursor++;continue;}
   const begin=cursor,stack=[];let quoted=false,escaped=false,complete=false;
   for(;cursor<text.length;cursor++){
    const c=text[cursor];
    if(quoted){if(escaped)escaped=false;else if(c==='\\')escaped=true;else if(c==='"')quoted=false;continue;}
    if(c==='"'){quoted=true;continue;}
    if(c==='{'||c==='[')stack.push(c);
    else if(c==='}'||c===']'){
     if(stack.pop()!==(c==='}'?'{':'['))break;
     if(!stack.length){complete=true;cursor++;break;}
    }
   }
   if(complete){
    try{const raw=text.slice(begin,cursor),value=JSON.parse(raw);plain(begin);parts.push({kind:'data',value,...(preserve?{raw}:{})});start=cursor;}catch{/* Ordinary bracketed text remains text. */}
   }else if(cursor===text.length)break;
   else cursor++;
  }
  plain(text.length);return parts;
 }
 function structuredParts(value){
  if(typeof value!=='string'||value.length>1000000||!/[\[{]/.test(value))return null;
  const parts=logParts(value,true);return parts.some(part=>part.kind==='data')?parts:null;
 }
 function joinParts(parts){return parts.map(part=>part.kind==='data'?(part.raw??JSON.stringify(part.value)):part.value).join('');}
 function messageSummary(value){
  const parts=structuredParts(value);
  return parts?parts.map(part=>part.kind==='data'?'〔结构化数据，详见运行日志〕':part.value).join(''):String(value??'');
 }
 function fieldValue(result,path){
  const keys=String(path??'').split('.');let value=result;
  for(const key of keys){
   if(!key||['__proto__','prototype','constructor'].includes(key)||value===null||typeof value!=='object'||!Object.hasOwn(value,key))return {found:false};
   value=value[key];
  }
  return {found:true,value};
 }
 function pluginRequirementError(steps,plugins){
  for(const step of steps||[]){
   if(step.operation!=='plugin')continue;
   const params=step.params||{},plugin=(plugins||[]).find(p=>p.id===params.pluginId);
   if(!plugin)return '服务尚未加载插件：'+String(params.pluginId||'未指定');
   if(!plugin.enabled||plugin.error)return '插件已停用或加载失败：'+plugin.name;
   if(plugin.version!==params.pluginVersion)return '插件版本不匹配：'+plugin.name+'（需要 '+String(params.pluginVersion)+'）';
   if(!plugin.operators?.some(op=>op.id===params.operatorId))return '插件缺少所需算子：'+String(params.operatorId);
  }
  return '';
 }
 function remapResultReferences(value,ids){
  if(Array.isArray(value))return value.map(item=>remapResultReferences(item,ids));
  if(!value||typeof value!=='object')return value;
  if(Object.keys(value).length===1&&typeof value.$ref==='string'){
   return {$ref:value.$ref.replace(/^results\.([A-Za-z0-9_-]+)(?=\.|$)/, (prefix,id)=>Object.hasOwn(ids,id)?'results.'+ids[id]:prefix)};
  }
  return Object.fromEntries(Object.entries(value).map(([key,item])=>[key,remapResultReferences(item,ids)]));
 }
 function recordFieldLabel(rows,key,fallback){
  const nearest=Array.isArray(rows)&&rows.some(row=>row&&['输入→参考','参考→输入'].includes(row.direction));
  if(nearest&&key==='distance')return '最近点距离';
  if(nearest&&key==='direction')return '比较方向';
  return fallback;
 }
 return {logParts,structuredParts,joinParts,fieldValue,messageSummary,pluginRequirementError,remapResultReferences,recordFieldLabel};
});
