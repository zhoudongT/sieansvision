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

function distortCorrect(p,input){
  const mode=p.mode||'file';
  return {
    status:p.enabled===false?'disabled':'ok',
    mode,
    calibPath:p.calibPath||'',
    coeffs:{fx:+p.fx||0,fy:+p.fy||0,cx:+p.cx||0,cy:+p.cy||0,k1:+p.k1||0,k2:+p.k2||0,p1:+p.p1||0,p2:+p.p2||0,k3:+p.k3||0,alpha:+p.alpha||0},
    note:'design-time shell; image passthrough',
  };
}
function ninePoint(p){
  const points=(Array.isArray(p.points)?p.points:[]).filter(r=>r&&r.enabled!==false);
  const used=points.filter(r=>{
    const a=Math.abs(+r.pixelX||0)+Math.abs(+r.pixelY||0)+Math.abs(+r.worldX||0)+Math.abs(+r.worldY||0);
    return a>0;
  });
  let transform=[1,0,0,0,1,0,0,0,1],rms=null;
  if(used.length>=3){
    // crude centroid-based translation + average scale (not a full SVD affine)
    const cx=used.reduce((s,r)=>s+(+r.pixelX||0),0)/used.length;
    const cy=used.reduce((s,r)=>s+(+r.pixelY||0),0)/used.length;
    const wx=used.reduce((s,r)=>s+(+r.worldX||0),0)/used.length;
    const wy=used.reduce((s,r)=>s+(+r.worldY||0),0)/used.length;
    transform=[1,0,wx-cx,0,1,wy-cy,0,0,1];
    let err=0;
    for(const r of used){
      const px=(+r.pixelX||0)+transform[2],py=(+r.pixelY||0)+transform[5];
      err+=Math.hypot(px-(+r.worldX||0),py-(+r.worldY||0));
    }
    rms=err/used.length;
  }
  return {coordSystem:p.coordSystem||'',unit:p.unit||'mm',method:p.method||'affine',usedPoints:used.length,transform,rms,status:used.length>=3?'ok':'need_points'};
}
function safeEvalExpr(expr,env){
  if(typeof expr!=='string')return {ok:false,error:'表达式须为文本'};
  const src=expr.trim();
  if(!src)return {ok:true,value:0};
  if(src.length>200)return {ok:false,error:'表达式过长'};
  if(!/^[\d\s+\-*/()._<>=!a-zA-Z]+$/.test(src))return {ok:false,error:'含非法字符'};
  // disallow keywords
  if(/\b(constructor|__proto__|prototype|Function|eval|window|global|process|require)\b/.test(src))return {ok:false,error:'非法标识符'};
  const names=Object.keys(env).filter(k=>/^[A-Za-z_][A-Za-z0-9_]*$/.test(k));
  try{
    // eslint-disable-next-line no-new-func
    const fn=new Function(...names,`"use strict"; return (${src});`);
    const value=fn(...names.map(n=>env[n]));
    if(typeof value==='number'&&!Number.isFinite(value))return {ok:false,error:'非有限数值'};
    return {ok:true,value};
  }catch(e){return {ok:false,error:String(e&&e.message||e)};}
}
function varCalc(p,context){
  const scope=p.scope||'flow';
  const target=scope==='module'?context.module:context[scope];
  if(!target||typeof target!=='object')throw Error('变量作用域无效');
  const env={...context.global,...context.flow,...context.module};
  const values={},errors=[];
  for(const row of (Array.isArray(p.expressions)?p.expressions:[])){
    if(!row||typeof row.name!=='string'||!/^[A-Za-z_][A-Za-z0-9_]{0,63}$/.test(row.name)){errors.push({name:row&&row.name,error:'变量名无效'});continue;}
    if(row.initOnRun&&target[row.name]===undefined)target[row.name]=row.initial??0;
    const base={...env,...target};
    const r=safeEvalExpr(String(row.expression??'0'),base);
    if(!r.ok){errors.push({name:row.name,error:r.error});continue;}
    let v=r.value;
    if(row.outType==='boolean')v=Boolean(v);
    else if(row.outType==='string')v=String(v);
    else if(typeof v==='boolean')v=v?1:0;
    target[row.name]=v;values[row.name]=v;env[row.name]=v;
  }
  return {scope,values,errors,status:errors.length?'partial':'ok'};
}
function elapsedStats(p,results,steps){
  const startId=p.startStepId||'',endId=p.endStepId||'';
  const order=[];
  if(startId==='source')order.push('source');
  for(const s of steps||[])order.push(s.id);
  let i0=order.indexOf(startId),i1=order.indexOf(endId);
  if(i0<0||i1<0)return {elapsedMs:0,startStepId:startId,endStepId:endId,breakdown:[],status:'missing_bounds'};
  if(i1<i0){const t=i0;i0=i1;i1=t;}
  const slice=order.slice(i0,i1+1);
  const byId=new Map();
  for(const r of results||[]){
    if(r&&r.id!=null)byId.set(r.id,r);
  }
  const breakdown=[];let total=0;
  for(const id of slice){
    if(id==='source')continue;
    const rec=byId.get(id);
    const ms=Number(rec?.output?.elapsedMs??rec?.elapsedMs??0)||0;
    breakdown.push({id,elapsedMs:ms});
    total+=ms;
  }
  return {elapsedMs:total,startStepId:startId,endStepId:endId,breakdown,status:'ok'};
}
function receiveData(p){
  return {device:p.device||'',channel:p.channel||'',payload:'',bytes:0,status:'stub',note:'通信后端未连接时返回空载荷'};
}
function sendData(p,message){
  const text=message==null?String(p.message||''):String(message);
  const body=p.appendCrLf?text+'\r\n':text;
  return {device:p.device||'',channel:p.channel||'',sent:body,bytes:Buffer.byteLength(body,'utf8'),status:'stub'};
}
function formatData(p,context){
  const tpl=String(p.template??'{0}');
  const raw=String(p.args||'');
  const parts=raw?raw.split(',').map(s=>s.trim()):[];
  const env={...context.global,...context.flow,...context.module};
  const values=parts.map(tok=>{
    if(Object.prototype.hasOwnProperty.call(env,tok))return env[tok];
    const n=Number(tok);return Number.isFinite(n)?n:tok;
  });
  let out=tpl;
  values.forEach((v,i)=>{out=out.split('{'+i+'}').join(String(v));});
  out=out.replace(/\{([A-Za-z_][A-Za-z0-9_]*)\}/g,(_,name)=>Object.prototype.hasOwnProperty.call(env,name)?String(env[name]):'');
  const scope=p.scope||'flow';
  const target=scope==='module'?context.module:context[scope];
  const name=p.targetVar||'formatted';
  if(target&&/^[A-Za-z_][A-Za-z0-9_]{0,63}$/.test(name))target[name]=out;
  return {formatted:out,targetVar:name,scope,status:'ok'};
}
function protocolParse(p,context){
  const scope=p.sourceScope||'flow';
  const bag=scope==='module'?context.module:context[scope];
  const raw=bag?bag[p.sourceVar||'recvData']:'';
  const text=raw==null?'':String(raw);
  const protocol=p.protocol||'delimited';
  const fieldNames=String(p.fields||'').split(',').map(s=>s.trim()).filter(Boolean);
  let fields={};
  if(protocol==='json'){
    try{fields=typeof raw==='object'&&raw?raw:JSON.parse(text||'{}');}catch(e){return {fields:{},status:'error',error:String(e.message||e)};}
  }else if(protocol==='regex'&&p.pattern){
    try{
      const m=text.match(new RegExp(p.pattern));
      if(m)fieldNames.forEach((n,i)=>{fields[n]=m[i+1]??m[0];});
    }catch(e){return {fields:{},status:'error',error:String(e.message||e)};}
  }else{
    const parts=text.split(p.delimiter||',');
    fieldNames.forEach((n,i)=>{fields[n]=parts[i]??'';});
  }
  if(context.flow)Object.assign(context.flow,fields);
  return {fields,protocol,status:'ok'};
}
function textSave(p,context){
  const fs=require('node:fs');
  const path=require('node:path');
  const file=String(p.path||'');
  if(!file)return {status:'missing_path'};
  let body=String(p.content||'');
  if(p.sourceVar){
    const v=context.flow?.[p.sourceVar]??context.global?.[p.sourceVar]??context.module?.[p.sourceVar];
    if(v!=null)body=String(v);
  }
  if(p.newline!==false&&body&&!body.endsWith('\n'))body+='\n';
  try{
    fs.mkdirSync(path.dirname(file),{recursive:true});
    if(p.append!==false)fs.appendFileSync(file,body,{encoding:p.encoding||'utf8'});
    else fs.writeFileSync(file,body,{encoding:p.encoding||'utf8'});
    return {path:file,bytes:Buffer.byteLength(body,p.encoding||'utf8'),status:'ok'};
  }catch(e){return {path:file,status:'error',error:String(e.message||e)};}
}
function outputImage(p){
  return {path:p.path||'',format:p.format||'png',status:'stub',note:'图像落盘由宿主保存管线处理；设计态已记录路径'};
}


function _num(v, d=0){const n=Number(v);return Number.isFinite(n)?n:d;}
function _lineIntersectManual(p){
  const x1=_num(p.x1),y1=_num(p.y1),x2=_num(p.x2),y2=_num(p.y2);
  const x3=_num(p.x3),y3=_num(p.y3),x4=_num(p.x4),y4=_num(p.y4);
  const den=(x1-x2)*(y3-y4)-(y1-y2)*(x3-x4);
  if(Math.abs(den)<1e-12)return {intersectX:null,intersectY:null,parallel:true,status:'parallel'};
  const t=((x1-x3)*(y3-y4)-(y1-y3)*(x3-x4))/den;
  const ix=x1+t*(x2-x1),iy=y1+t*(y2-y1);
  return {intersectX:ix,intersectY:iy,parallel:false,status:'ok',t};
}
function _pickPoint(obj){
  if(!obj||typeof obj!=='object')return null;
  if(Array.isArray(obj)&&obj.length>=2)return {x:_num(obj[0]),y:_num(obj[1])};
  if('x' in obj&&'y' in obj)return {x:_num(obj.x),y:_num(obj.y)};
  if(Array.isArray(obj.center)&&obj.center.length>=2)return {x:_num(obj.center[0]),y:_num(obj.center[1])};
  if(obj.center&&typeof obj.center==='object'&&'x' in obj.center)return {x:_num(obj.center.x),y:_num(obj.center.y)};
  if('centerX' in obj)return {x:_num(obj.centerX),y:_num(obj.centerY)};
  if(Array.isArray(obj.start)&&Array.isArray(obj.end)){
    return {x:(_num(obj.start[0])+_num(obj.end[0]))/2,y:(_num(obj.start[1])+_num(obj.end[1]))/2};
  }
  return null;
}
function _pickLine(obj){
  if(!obj||typeof obj!=='object')return null;
  if(Array.isArray(obj.start)&&Array.isArray(obj.end)&&obj.start.length>=2&&obj.end.length>=2){
    return {x1:_num(obj.start[0]),y1:_num(obj.start[1]),x2:_num(obj.end[0]),y2:_num(obj.end[1])};
  }
  if('x1' in obj&&'y1' in obj&&'x2' in obj&&'y2' in obj)return {x1:_num(obj.x1),y1:_num(obj.y1),x2:_num(obj.x2),y2:_num(obj.y2)};
  return null;
}
function _resolvePath(bag, field){
  if(!bag||typeof bag!=='object')return null;
  const path=String(field||'').trim();
  if(!path)return bag;
  // support result.items[0] / lines[0] / matches[0] / items[0]
  let cur=bag;
  const parts=path.replace(/\[(\d+)\]/g,'.$1').split('.').filter(Boolean);
  for(const part of parts){
    if(cur==null)return null;
    if(part==='lines'||part==='circles'||part==='rects'||part==='matches'||part==='items'){
      const arr=cur[part]||cur.items||cur.result?.[part]||cur.result?.items;
      cur=arr;continue;
    }
    if(/^\d+$/.test(part)){cur=Array.isArray(cur)?cur[Number(part)]:null;continue;}
    cur=cur[part];
  }
  return cur;
}
function _fromResults(results, stepId, field){
  if(!stepId||!results)return null;
  const rec=results[stepId]||results.get?.(stepId);
  const out=rec?.result??rec?.output?.result??rec;
  return _resolvePath(out, field);
}
function lineIntersect(p, context){
  const scale=_num(p.scale,1)||1;
  if((p.mode||'bind')==='manual'){
    const r=_lineIntersectManual(p);
    if(r.intersectX!=null){r.intersectX*=scale;r.intersectY*=scale;}
    r.unit=p.unit||'px';return r;
  }
  const l1=_pickLine(_fromResults(context.results,p.line1From,p.line1Field))||_pickLine(_resolvePath(context.results?.[p.line1From],p.line1Field));
  const l2=_pickLine(_fromResults(context.results,p.line2From,p.line2Field));
  if(!l1||!l2){
    // fallback manual coords if bind missing
    return {..._lineIntersectManual(p),status:'fallback_manual',note:'上游直线未解析，使用手动坐标'};
  }
  const r=_lineIntersectManual({x1:l1.x1,y1:l1.y1,x2:l1.x2,y2:l1.y2,x3:l2.x1,y3:l2.y1,x4:l2.x2,y4:l2.y2});
  if(r.intersectX!=null){r.intersectX*=scale;r.intersectY*=scale;}
  r.unit=p.unit||'px';return r;
}
function pointDistance(p, context){
  const scale=_num(p.scale,1)||1;
  let a,b;
  if((p.mode||'bind')==='manual'){
    a={x:_num(p.x1),y:_num(p.y1)};b={x:_num(p.x2),y:_num(p.y2)};
  }else{
    a=_pickPoint(_fromResults(context.results,p.point1From,p.point1Field));
    b=_pickPoint(_fromResults(context.results,p.point2From,p.point2Field));
    if(!a||!b){a={x:_num(p.x1),y:_num(p.y1)};b={x:_num(p.x2),y:_num(p.y2)};}
  }
  const dx=(b.x-a.x),dy=(b.y-a.y);
  const distance=Math.hypot(dx,dy)*scale;
  return {distance,dx:dx*scale,dy:dy*scale,unit:p.unit||'px',x1:a.x,y1:a.y,x2:b.x,y2:b.y,status:'ok'};
}
function pointLineDistance(p, context){
  const scale=_num(p.scale,1)||1;
  let pt,ln;
  if((p.mode||'bind')==='manual'){
    pt={x:_num(p.px),y:_num(p.py)};ln={x1:_num(p.x1),y1:_num(p.y1),x2:_num(p.x2),y2:_num(p.y2)};
  }else{
    pt=_pickPoint(_fromResults(context.results,p.pointFrom,p.pointField));
    ln=_pickLine(_fromResults(context.results,p.lineFrom,p.lineField));
    if(!pt||!ln){pt={x:_num(p.px),y:_num(p.py)};ln={x1:_num(p.x1),y1:_num(p.y1),x2:_num(p.x2),y2:_num(p.y2)};}
  }
  const {x1,y1,x2,y2}=ln;const dx=x2-x1,dy=y2-y1;
  const len2=dx*dx+dy*dy;
  if(len2<1e-18)return {distance:0,footX:x1,footY:y1,status:'degenerate'};
  const t=((pt.x-x1)*dx+(pt.y-y1)*dy)/len2;
  const fx=x1+t*dx,fy=y1+t*dy;
  const distance=Math.hypot(pt.x-fx,pt.y-fy)*scale;
  return {distance,footX:fx,footY:fy,t,unit:p.unit||'px',status:'ok'};
}
function csharpScript(p){
  const lang=p.language||'csharp';
  const code=String(p.code||'');
  return {
    language:lang,
    entry:p.entry||'Script.Run',
    bytes:Buffer.byteLength(code,'utf8'),
    timeoutMs:p.timeoutMs??5000,
    references:p.references||'',
    status:lang==='csharp'?'unsupported':'stub',
    note:lang==='csharp'?'本机无 CLR；设计态已保存脚本。真实执行请用 script 算子。':'Python 示意壳；请改用 script 算子执行。',
  };
}

module.exports={condition,delay,branch,poseCorrect,distortCorrect,ninePoint,varCalc,elapsedStats,receiveData,sendData,formatData,protocolParse,textSave,outputImage,lineIntersect,pointDistance,pointLineDistance,csharpScript};
