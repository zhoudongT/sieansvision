'use strict';
const {setTimeout:wait}=require('node:timers/promises');
function evalOne(p){
  const comparison=p.comparison||'eq',left=p.left,right=p.right;
  const scalar=v=>v===null||['string','boolean','number'].includes(typeof v)&&(!(typeof v==='number')||Number.isFinite(v));
  let passed;
  if(['is_true','is_false'].includes(comparison)){
    if(typeof left!=='boolean'){
      // soft coerce common cases for design-time tables
      if(left===1||left==='1'||left==='true'||left==='True')passed=comparison==='is_true';
      else if(left===0||left==='0'||left==='false'||left==='False'||left===''||left==null)passed=comparison==='is_false';
      else throw Error('开关判断需要布尔值，请检查输入类型');
    }else passed=comparison==='is_true'?left:!left;
  }else if(['eq','ne'].includes(comparison)){
    if(!scalar(left)||!scalar(right))throw Error('相等判断只支持数值、文本、开关和空值');
    passed=comparison==='eq'?left===right:left!==right;
  }else if(['gt','gte','lt','lte'].includes(comparison)){
    const L=typeof left==='number'?left:Number(left),R=typeof right==='number'?right:Number(right);
    if(!Number.isFinite(L)||!Number.isFinite(R))throw Error('大小比较要求两侧均为有限数值');
    passed=({gt:L>R,gte:L>=R,lt:L<R,lte:L<=R})[comparison];
  }else if(comparison==='contains'){
    if(typeof left!=='string'||typeof right!=='string')throw Error('包含判断要求两侧均为文本');
    passed=left.includes(right);
  }else throw Error('未知判断方式');
  return {comparison,left,...(!['is_true','is_false'].includes(comparison)?{right}:{}),passed};
}
function condition(p){
  if(Array.isArray(p.rules)&&p.rules.length){
    const logic=p.logic||'and';
    const results=p.rules.map(r=>evalOne(r));
    const passed=logic==='or'?results.some(r=>r.passed):results.every(r=>r.passed);
    return {logic,rules:results,comparison:p.comparison||results[0]?.comparison,left:p.left,right:p.right,passed};
  }
  return evalOne(p);
}
function branch(p){
  const paths=Array.isArray(p.paths)?p.paths:[];
  const defaultId=p.defaultPathId||'default';
  for(const path of paths){
    if(!path||path.id===defaultId)continue;
    try{
      const result=evalOne({left:path.left,comparison:path.comparison||'eq',right:path.right});
      if(result.passed)return {pathId:path.id,pathName:path.name||path.id,passed:true,matched:result};
    }catch(_){/* skip unmatched / bad row */}
  }
  const fallback=paths.find(x=>x&&(x.id===defaultId||x.name==='默认'))||paths[paths.length-1]||{id:defaultId,name:'默认'};
  return {pathId:fallback.id||defaultId,pathName:fallback.name||'默认',passed:true,default:true};
}
function poseCorrect(p,input){
  const source=p.fixtureSource||'auto';
  let fixtureX=Number(p.baseX)||0,fixtureY=Number(p.baseY)||0,fixtureAngle=Number(p.baseAngle)||0;
  // auto/bind: caller may have resolved base* from upstream into params already
  return {
    fixtureSource:source,
    fixtureX,fixtureY,fixtureAngle,
    followRoi:p.followRoi!==false,
    outputCoord:p.outputCoord||'fixture',
    matrix:[1,0,fixtureX,0,1,fixtureY,0,0,1],
    status:'ok',
  };
}
async function delay(p,signal){
  const milliseconds=p.milliseconds??100;
  if(!Number.isInteger(milliseconds)||milliseconds<0||milliseconds>30000)throw Error('延时必须为 0–30000 的整数毫秒');
  await wait(milliseconds,undefined,{signal});return {milliseconds};
}
module.exports={condition,delay,branch,poseCorrect};
