'use strict';
const {setTimeout:wait}=require('node:timers/promises');
function condition(p){
  const comparison=p.comparison||'eq',left=p.left,right=p.right;
  const scalar=v=>v===null||['string','boolean','number'].includes(typeof v)&&(!(typeof v==='number')||Number.isFinite(v));
  let passed;
  if(['is_true','is_false'].includes(comparison)){
    if(typeof left!=='boolean')throw Error('开关判断需要布尔值，请检查输入类型');
    passed=comparison==='is_true'?left:!left;
  }else if(['eq','ne'].includes(comparison)){
    if(!scalar(left)||!scalar(right))throw Error('相等判断只支持数值、文本、开关和空值');
    passed=comparison==='eq'?left===right:left!==right;
  }else if(['gt','gte','lt','lte'].includes(comparison)){
    if(typeof left!=='number'||typeof right!=='number'||!Number.isFinite(left)||!Number.isFinite(right))throw Error('大小比较要求两侧均为有限数值');
    passed=({gt:left>right,gte:left>=right,lt:left<right,lte:left<=right})[comparison];
  }else if(comparison==='contains'){
    if(typeof left!=='string'||typeof right!=='string')throw Error('包含判断要求两侧均为文本');
    passed=left.includes(right);
  }else throw Error('未知判断方式');
  return {comparison,left,...(!['is_true','is_false'].includes(comparison)?{right}:{}),passed};
}
async function delay(p,signal){
  const milliseconds=p.milliseconds??100;
  if(!Number.isInteger(milliseconds)||milliseconds<0||milliseconds>30000)throw Error('延时必须为 0–30000 的整数毫秒');
  await wait(milliseconds,undefined,{signal});return {milliseconds};
}
module.exports={condition,delay};
