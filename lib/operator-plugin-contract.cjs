'use strict';
// Declarative, host-owned schemas. No vendor runtime or binary ABI is involved.
const {object}=require('./variable-store.cjs');
const KEY=/^[A-Za-z_][A-Za-z0-9_]{0,63}$/;
const reserved=new Set(['__proto__','constructor','prototype']);
const types=new Set(['number','integer','string','boolean','array','object']);
function check(ok,message){if(!ok)throw Error(message);}
function text(v,n=200){return typeof v==='string'&&v.length>0&&v.length<=n;}
function value(v,f,label){
  const valid=f.type==='integer'?Number.isSafeInteger(v):f.type==='number'?typeof v==='number'&&Number.isFinite(v):f.type==='array'?Array.isArray(v):f.type==='object'?v!==null&&typeof v==='object'&&!Array.isArray(v):typeof v===f.type;
  check(valid,label+' 的类型必须为 '+f.type);
  if(typeof v==='number'){check(f.minimum===undefined||v>=f.minimum,label+' 低于最小值');check(f.maximum===undefined||v<=f.maximum,label+' 超过最大值');}
  if(f.choices)check(f.choices.some(c=>c.value===v),label+' 不在可选值内');
  if(f.columns||f.items){
    check(v.length>=(f.minimumRows??0)&&v.length<=(f.maximumRows??1000),label+' 行数超出允许范围');
    for(const [index,row] of v.entries()){
      if(f.items)value(row,f.items,label+' 第 '+(index+1)+' 项');
      else record(row,f.columns,label+' 第 '+(index+1)+' 行',true);
    }
  }
  if(f.properties)record(v,f.properties,label);
  object({value:v},label);return v;
}
function record(v,fields,label,allRequired=false){
  check(v&&typeof v==='object'&&!Array.isArray(v),label+' 必须为记录');
  const keys=new Set(fields.map(f=>f.key));
  for(const key of Object.keys(v))check(keys.has(key),label+' 包含未声明字段：'+key);
  for(const f of fields){
    if(!Object.hasOwn(v,f.key)){check(!allRequired&&!f.required,label+' 缺少字段：'+f.label);continue;}
    value(v[f.key],f,label+' · '+f.label);
  }
}
function fields(list,label,inputs,depth=0,budget={count:0}){
  check(depth<=6,'插件字段定义嵌套最多 6 层');
  check(Array.isArray(list)&&list.length<=100,label+' 最多 100 项');const names=new Set();
  for(const f of list){
    check(++budget.count<=500,'单个契约最多 500 个字段');
    check(f&&KEY.test(f.key)&&!reserved.has(f.key)&&!names.has(f.key),label+' 名称无效或重复');names.add(f.key);
    check(text(f.label)&&types.has(f.type),label+' 标签或类型无效');
    check(f.required===undefined||typeof f.required==='boolean',label+' required 必须是开关');
    for(const [k,max] of [['description',2000],['group',100],['unit',40]])if(f[k]!==undefined)check(text(f[k],max),label+' '+k+' 无效');
    for(const k of ['minimum','maximum'])if(f[k]!==undefined)check(['number','integer'].includes(f.type)&&Number.isFinite(f[k]),label+' 数值范围无效');
    check(f.minimum===undefined||f.maximum===undefined||f.minimum<=f.maximum,label+' 数值范围颠倒');
    if(f.choices!==undefined){
      check(['string','number','integer','boolean'].includes(f.type)&&Array.isArray(f.choices)&&f.choices.length>0&&f.choices.length<=100,label+' 选项无效');
      for(const c of f.choices){check(c&&text(c.label),label+' 选项标签无效');value(c.value,{...f,choices:undefined},label);}
    }
    if(f.columns!==undefined){
      check(f.type==='array'&&Array.isArray(f.columns)&&f.columns.length>0&&f.columns.length<=12&&f.items===undefined,label+' 表格列配置无效');
      check(f.columns.every(c=>c&&!['array','object'].includes(c.type)&&c.columns===undefined),label+' 表格列必须为基础类型');
      fields(f.columns,label+' 表格列',inputs,depth+1,budget);
    }
    if(f.properties!==undefined){check(f.type==='object'&&Array.isArray(f.properties)&&f.properties.length>0,label+' 结构字段配置无效');fields(f.properties,label+' 结构字段',inputs,depth+1,budget);}
    if(f.items!==undefined){check(f.type==='array'&&f.items&&typeof f.items==='object'&&!Array.isArray(f.items)&&f.items.key===undefined,label+' 数组项配置无效');fields([{...f.items,key:'item',label:f.items.label||'数组项'}],label+' 数组项',inputs,depth+1,budget);}
    if(f.columns||f.items){
      for(const key of ['minimumRows','maximumRows'])if(f[key]!==undefined)check(Number.isInteger(f[key])&&f[key]>=0&&f[key]<=1000,label+' 表格行数范围无效');
      check((f.minimumRows??0)<=(f.maximumRows??1000),label+' 表格行数范围颠倒');
    }else check(f.minimumRows===undefined&&f.maximumRows===undefined,label+' 行数限制需要表格列或数组项');
    if(inputs&&Object.hasOwn(f,'default'))value(f.default,f,f.label+' 默认值');
  }
}
function prepare(data,definitions,label){
  const values=object(data??{},label),known=new Set(definitions.map(f=>f.key));
  for(const key of Object.keys(values))check(known.has(key),'未知'+label+'：'+key);
  for(const f of definitions){
    if(!Object.hasOwn(values,f.key)&&Object.hasOwn(f,'default'))values[f.key]=structuredClone(f.default);
    if(!Object.hasOwn(values,f.key)){check(!f.required,'缺少'+label+'：'+f.label);continue;}
    values[f.key]=defaults(values[f.key],f);value(values[f.key],f,f.label);
  }
  return values;
}
function defaults(v,f){
  if(f.properties&&v&&typeof v==='object'&&!Array.isArray(v)){
    for(const child of f.properties){
      if(!Object.hasOwn(v,child.key)&&Object.hasOwn(child,'default'))v[child.key]=structuredClone(child.default);
      if(Object.hasOwn(v,child.key))v[child.key]=defaults(v[child.key],child);
    }
  }
  if(f.items&&Array.isArray(v))return v.map(item=>defaults(item,f.items));
  return v;
}
module.exports={check,text,fields,value,prepare};
