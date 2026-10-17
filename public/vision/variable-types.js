(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.VariableTypes=api;})(typeof globalThis!=='undefined'?globalThis:this,function(){
  'use strict';
  const labels={number:'数值',integer:'整数',string:'文本',boolean:'开关',array:'数组',object:'结构体',null:'空值','number[]':'数值数组','integer[]':'整数数组','string[]':'文本数组','boolean[]':'开关数组'};
  const forbidden=new Set(['__proto__','constructor','prototype']);
  function definitions(value={}){
    if(!value||typeof value!=='object'||Array.isArray(value)||Object.keys(value).length>1000)throw Error('变量类型定义必须是最多 1000 项的映射');
    for(const [name,type] of Object.entries(value)){
      if(!/^[A-Za-z_][A-Za-z0-9_]{0,63}$/.test(name)||forbidden.has(name))throw Error('固定类型变量名称无效：'+name);
      if(typeof type!=='string'||!Object.hasOwn(labels,type))throw Error('不支持的变量类型：'+String(type));
    }
    return {...value};
  }
  function matches(value,type){
    if(type.endsWith('[]'))return Array.isArray(value)&&value.every(item=>matches(item,type.slice(0,-2)));
    if(type==='integer')return Number.isSafeInteger(value);
    if(type==='number')return typeof value==='number'&&Number.isFinite(value);
    if(type==='null')return value===null;
    if(type==='array')return Array.isArray(value);
    if(type==='object')return !!value&&typeof value==='object'&&!Array.isArray(value);
    return typeof value===type;
  }
  function assert(values,types={},scope='变量'){
    for(const [name,type] of Object.entries(definitions(types))){
      if(!Object.hasOwn(values,name))throw Error(scope+'.'+name+' 已定义为 '+labels[type]+'，不能删除；请先修改类型定义');
      if(!matches(values[name],type))throw Error(scope+'.'+name+' 类型不匹配：要求 '+labels[type]+'，不自动转换输入值');
    }
  }
  return {labels,definitions,matches,assert};
});
