(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.HmiLayout=api;})(typeof globalThis!=='undefined'?globalThis:this,function(){
 'use strict';
 const types=['text','value','lamp','image','cloud','table','button','input','alarm','trend'];
 const forbidden=new Set(['__proto__','constructor','prototype']);
 function check(ok,message){if(!ok)throw Error(message);}
 function integer(v,min,max){return Number.isInteger(v)&&v>=min&&v<=max;}
 function plain(v){return v&&typeof v==='object'&&!Array.isArray(v);}
 function binding(b,type){
  check(plain(b)&&['flow','global','module','result','source','status'].includes(b.source),'画面数据来源无效');
  check(typeof b.path==='string'&&b.path.length<=200&&(!b.path||b.path.split('.').every(k=>k&&!forbidden.has(k))),'画面字段路径无效');
  if(['module','result'].includes(b.source))check(typeof b.nodeId==='string'&&b.nodeId.length>0&&b.nodeId.length<=80&&!forbidden.has(b.nodeId),'请选择绑定模块');
  if(type==='image')check(['result','source'].includes(b.source),'图像组件只能绑定输入或模块图像');
  if(type==='cloud')check(b.source==='result'&&b.path==='','点云组件只能绑定模块输出点云通道');
  if(type==='input')check(['flow','global','module'].includes(b.source)&&/^[A-Za-z_][A-Za-z0-9_]{0,63}$/.test(b.path)&&!forbidden.has(b.path),'输入框须绑定单个变量名称');
  return {source:b.source,path:b.path,...(['module','result'].includes(b.source)?{nodeId:b.nodeId}:{})};
 }
 function normalizePage(v,targets=null){
  check(plain(v)&&v.version===1&&typeof v.title==='string'&&v.title.length<=100,'运行画面格式或标题无效');
  check(integer(v.rows,4,40)&&integer(v.rowHeight,40,120),'画面行数范围 4–40，行高范围 40–120');
  check(Array.isArray(v.components)&&v.components.length<=50,'运行画面最多 50 个组件');
  const ids=new Set();
  const components=v.components.map(c=>{
   check(plain(c)&&typeof c.id==='string'&&/^[A-Za-z0-9_-]{1,80}$/.test(c.id)&&!forbidden.has(c.id)&&!ids.has(c.id),'画面组件 ID 无效或重复');ids.add(c.id);
   check(types.includes(c.type)&&typeof c.label==='string'&&c.label.length<=200,'画面组件类型或标题无效');
   check(integer(c.x,0,11)&&integer(c.y,0,v.rows-1)&&integer(c.w,1,12)&&integer(c.h,1,v.rows)&&c.x+c.w<=12&&c.y+c.h<=v.rows,'画面组件超出网格边界');
   check(/^#[a-fA-F0-9]{6}$/.test(c.color)&&integer(c.fontSize,12,64),'组件颜色或字号无效');
   const n={id:c.id,type:c.type,label:c.label,x:c.x,y:c.y,w:c.w,h:c.h,color:c.color,fontSize:c.fontSize};
   if(['value','lamp','image','cloud','table','input','alarm','trend'].includes(c.type))n.binding=binding(c.binding,c.type);
   if(c.type==='cloud'){check(integer(c.maxPoints,100,30000)&&integer(c.pointSize,1,6)&&['iso','top','front'].includes(c.initialView),'点云预览点数、点大小或初始视角无效');n.maxPoints=c.maxPoints;n.pointSize=c.pointSize;n.initialView=c.initialView;}
   if(['alarm','trend'].includes(c.type))check(c.binding.source!=='source','报警和趋势不能绑定图像源');
   if(['value','trend'].includes(c.type)){check(integer(c.precision,0,6)&&typeof c.unit==='string'&&c.unit.length<=20,'数值小数位或单位无效');n.precision=c.precision;n.unit=c.unit;}
   if(c.type==='trend'){check(integer(c.capacity,20,1000),'趋势保留样本数须为 20–1000');n.capacity=c.capacity;}
   if(c.type==='alarm'){
    check(['gt','gte','lt','lte','eq','ne','is_true','is_false'].includes(c.comparison),'报警判断方式无效');
    check(['info','warning','critical'].includes(c.severity)&&integer(c.stableSamples,1,100),'报警级别或稳定样本数无效');
    check(typeof c.hysteresis==='number'&&Number.isFinite(c.hysteresis)&&c.hysteresis>=0&&c.hysteresis<=1e12,'报警回差无效');
    if(!['is_true','is_false'].includes(c.comparison)){
     check(c.threshold===null||['number','string','boolean'].includes(typeof c.threshold)&&(!(typeof c.threshold==='number')||Number.isFinite(c.threshold)),'报警阈值需为有限数值、文本或开关');
     if(['gt','gte','lt','lte'].includes(c.comparison))check(typeof c.threshold==='number'&&Number.isFinite(c.threshold),'大小比较报警需要数值阈值');
     if(typeof c.threshold==='string')check(c.threshold.length<=200,'文本报警阈值不能超过 200 字');n.threshold=c.threshold;
    }
    check(c.hysteresis===0||['gt','gte','lt','lte'].includes(c.comparison),'回差仅适用于大小比较');
    n.comparison=c.comparison;n.severity=c.severity;n.stableSamples=c.stableSamples;n.hysteresis=c.hysteresis;
   }
   if(c.type==='button'){check(['run','stop','navigate'].includes(c.action),'画面按钮动作无效');n.action=c.action;if(c.action==='navigate'){check(typeof c.targetPageId==='string'&&/^[A-Za-z0-9_-]{1,80}$/.test(c.targetPageId)&&!forbidden.has(c.targetPageId),'请选择跳转页面');if(targets)check(targets.has(c.targetPageId),'页面跳转目标不存在');n.targetPageId=c.targetPageId;}}
   if(c.type==='input'){check(['number','string','boolean'].includes(c.dataType),'变量输入类型无效');n.dataType=c.dataType;if(c.dataType==='number'){for(const k of ['minimum','maximum']){check(typeof c[k]==='number'&&Number.isFinite(c[k]),'变量输入范围无效');n[k]=c[k];}check(c.minimum<=c.maximum,'变量输入范围颠倒');}}
   return n;
  });
  return {version:1,title:v.title,rows:v.rows,rowHeight:v.rowHeight,components};
 }
 function normalize(v){
  if(v?.version!==2)return normalizePage(v,new Set(['main']));
  check(plain(v)&&typeof v.title==='string'&&v.title.length<=100&&Array.isArray(v.pages)&&v.pages.length>=1&&v.pages.length<=20,'多页画面需要 1–20 页及有效标题');
  const ids=new Set();for(const p of v.pages){check(plain(p)&&typeof p.id==='string'&&/^[A-Za-z0-9_-]{1,80}$/.test(p.id)&&!forbidden.has(p.id)&&!ids.has(p.id),'画面页面编号无效或重复');ids.add(p.id);}
  check(typeof v.defaultPageId==='string'&&ids.has(v.defaultPageId),'默认页面不存在');
  const pages=v.pages.map(p=>({id:p.id,...normalizePage({...p,version:1},ids)})),components=pages.flatMap(p=>p.components),componentIds=new Set();
  check(components.length<=200,'多页画面合计最多 200 个组件');
  check(components.filter(c=>['alarm','trend'].includes(c.type)).length<=50,'整个工程的报警与趋势组件合计最多 50 个');
  for(const c of components){check(!componentIds.has(c.id),'跨页面组件编号重复');componentIds.add(c.id);}
  return {version:2,title:v.title,defaultPageId:v.defaultPageId,pages};
 }
 function pages(v){return !v?[]:v.version===2?v.pages:[{id:'main',...v}];}
 function allComponents(v){return pages(v).flatMap(p=>p.components||[]);}
 function alarmCount(page,monitor){const ids=new Set(page.components.filter(c=>c.type==='alarm').map(c=>c.id));return (monitor?.events||[]).filter(e=>ids.has(e.componentId)&&(!e.returnedAt||!e.acknowledgedAt)).length;}
 function document(v){const n=normalize(v);return JSON.parse(JSON.stringify(n.version===2?n:{version:2,title:n.title,defaultPageId:'main',pages:[{id:'main',...n}]}));}
 function copyPage(v,id,newId){const n=document(v),source=n.pages.find(p=>p.id===id);check(!!source,'要复制的页面不存在');const page=JSON.parse(JSON.stringify(source));page.id=newId;page.title=page.title.slice(0,94)+' 副本';const prefix='copy-'+newId.slice(-20);page.components.forEach((c,i)=>{c.id=prefix+'-'+i;if(c.action==='navigate'&&c.targetPageId===id)c.targetPageId=newId;});n.pages.push(page);return normalize(n);}
 function removePage(v,id){const n=document(v);check(n.pages.length>1,'至少保留一个运行页面');check(n.pages.some(p=>p.id===id),'页面不存在');check(!n.pages.filter(p=>p.id!==id).some(p=>p.components.some(c=>c.action==='navigate'&&c.targetPageId===id)),'其他页面仍有按钮跳转到此页，请先修改跳转目标');n.pages=n.pages.filter(p=>p.id!==id);if(n.defaultPageId===id)n.defaultPageId=n.pages[0].id;return normalize(n);}
 function read(b,state){
  if(!b)return undefined;
  let v=b.source==='module'?state.variables?.modules?.[b.nodeId]:b.source==='result'?state.results?.find(r=>r.id===b.nodeId&&!r.error&&!r.skipped)?.output?.result:b.source==='status'?state.status:state.variables?.[b.source];
  for(const part of b.path?b.path.split('.'):[]){if(forbidden.has(part)||v===null||typeof v!=='object'||!Object.hasOwn(v,part))return undefined;v=v[part];}
  return v;
 }
 function move(c,x,y,layout){return {...c,x:Math.min(12-c.w,Math.max(0,Math.round(x))),y:Math.min(layout.rows-c.h,Math.max(0,Math.round(y)))};}
 function empty(){return {version:1,title:'运行监控',rows:10,rowHeight:60,components:[]};}
 return {types,normalize,normalizePage,pages,allComponents,alarmCount,document,copyPage,removePage,read,move,empty};
});
