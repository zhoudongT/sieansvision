(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.CloudViewer=api;})(typeof globalThis!=='undefined'?globalThis:this,function(){
 'use strict';
 function validate(cloud){
  if(!cloud||!['mm','m'].includes(cloud.unit)||!Array.isArray(cloud.points)||!cloud.points.length||cloud.points.length>200000)throw Error('点云需要 mm/m 单位和 1–200000 个点');
  const xyz=p=>Array.isArray(p)&&p.length===3&&p.every(v=>typeof v==='number'&&Number.isFinite(v)&&Math.abs(v)<=1e9);
  if(!cloud.points.every(xyz))throw Error('点云坐标无效');
  if(cloud.colors!==undefined&&(!Array.isArray(cloud.colors)||cloud.colors.length!==cloud.points.length||!cloud.colors.every(c=>xyz(c)&&c.every(v=>v>=0&&v<=1))))throw Error('点云颜色需与点数对应且处于 0–1 范围');
  return cloud;
 }
 function preview(cloud,limit=12000){
  validate(cloud);if(!Number.isInteger(limit)||limit<100||limit>30000)throw Error('预览点数上限需为 100–30000');
  const stride=Math.max(1,Math.ceil(cloud.points.length/limit)),indices=[];const low=[Infinity,Infinity,Infinity],high=[-Infinity,-Infinity,-Infinity];
  for(let i=0;i<cloud.points.length;i++){const p=cloud.points[i];for(let k=0;k<3;k++){low[k]=Math.min(low[k],p[k]);high[k]=Math.max(high[k],p[k]);}if(i%stride===0)indices.push(i);}
  const bounds=cloud.bounds;const validBounds=Array.isArray(bounds)&&bounds.length===2&&bounds.every(p=>Array.isArray(p)&&p.length===3&&p.every(v=>Number.isFinite(v)&&Math.abs(v)<=1e9))&&bounds[0].every((v,i)=>v<=low[i]&&bounds[1][i]>=high[i]);
  return {unit:cloud.unit,frame:typeof cloud.frame==='string'?cloud.frame:'',points:indices.map(i=>cloud.points[i].slice()),...(cloud.colors?{colors:indices.map(i=>cloud.colors[i].slice())}:{}),sourcePointCount:Number.isInteger(cloud.sourcePointCount)&&cloud.sourcePointCount>=cloud.points.length&&cloud.sourcePointCount<=200000?cloud.sourcePointCount:cloud.points.length,bounds:validBounds?bounds.map(p=>p.slice()):[low,high]};
 }
 function orientation(view='iso'){return view==='top'?{yaw:0,pitch:Math.PI/2}:view==='front'?{yaw:0,pitch:0}:{yaw:-.65,pitch:.65};}
 function project(cloud,camera,width,height){
  if(!Number.isFinite(width)||!Number.isFinite(height)||width<=0||height<=0)return [];
  const [low,high]=cloud.bounds,center=low.map((v,i)=>(v+high[i])/2),size=low.map((v,i)=>high[i]-v),span=Math.max(...size,1e-12),cy=Math.cos(camera.yaw),sy=Math.sin(camera.yaw),cp=Math.cos(camera.pitch),sp=Math.sin(camera.pitch);
  const pw=Math.abs(cy)*size[0]+Math.abs(sy)*size[1],ph=Math.abs(sp*sy)*size[0]+Math.abs(sp*cy)*size[1]+Math.abs(cp)*size[2],scale=.78*Math.min(width/Math.max(pw,span*.05),height/Math.max(ph,span*.05))*camera.zoom;
  return cloud.points.map((point,i)=>{const [x,y,z]=point.map((v,k)=>v-center[k]),rx=x*cy-y*sy,ry=x*sy+y*cy;return {x:width/2+camera.pan[0]+rx*scale,y:height/2+camera.pan[1]-(z*cp+ry*sp)*scale,depth:ry*cp-z*sp,index:i};}).sort((a,b)=>b.depth-a.depth||a.index-b.index);
 }
 function create(host,options={}){
  const document=host.ownerDocument||globalThis.document;const shell=document.createElement('div'),bar=document.createElement('div'),canvas=document.createElement('canvas'),note=document.createElement('small');shell.className='cloud-widget';bar.className='cloud-widget-controls';canvas.className='cloud-widget-canvas';canvas.tabIndex=0;canvas.setAttribute('aria-label','点云预览；方向键旋转，加减键缩放，Home复位');canvas.setAttribute('role','img');note.setAttribute('role','status');shell.append(bar,canvas,note);host.append(shell);
  let cloud=null,error='',camera={...orientation(options.initialView),zoom:1,pan:[0,0]},pending=0,disposed=false,drag=null;
  const schedule=()=>{if(!disposed&&!pending)pending=requestAnimationFrame(draw);};
  function draw(){pending=0;if(disposed)return;const rect=canvas.getBoundingClientRect();if(rect.width<1||rect.height<1)return;const dpr=Math.min(globalThis.devicePixelRatio||1,2);canvas.width=Math.round(rect.width*dpr);canvas.height=Math.round(rect.height*dpr);const g=canvas.getContext('2d');if(!g)return;g.scale(dpr,dpr);g.fillStyle='#edf4f9';g.fillRect(0,0,rect.width,rect.height);
   if(!cloud){note.textContent=error||'等待模块点云';return;}
   const dots=project(cloud,camera,rect.width,rect.height);for(const dot of dots){if(dot.x<0||dot.y<0||dot.x>rect.width||dot.y>rect.height)continue;const color=cloud.colors?.[dot.index];g.fillStyle=color?'rgb('+color.map(v=>Math.round(v*255)).join(',')+')':'#1095bd';const size=options.pointSize||2;g.fillRect(dot.x-size/2,dot.y-size/2,size,size);}
   note.textContent=cloud.sourcePointCount+' 点 · 显示 '+cloud.points.length+' 点 · '+cloud.unit+(cloud.frame?' · '+cloud.frame:'')+' · 拖动旋转 / Shift 拖动平移';
  }
  const reset=view=>{camera={...orientation(view||options.initialView),zoom:1,pan:[0,0]};schedule();};
  for(const [title,view]of [['等轴','iso'],['俯视','top'],['正视','front']]){const button=document.createElement('button');button.type='button';button.textContent=title;button.setAttribute('aria-label','点云'+title);button.disabled=options.interactive===false;button.onclick=()=>reset(view);bar.append(button);}
  if(options.interactive!==false){
   canvas.onpointerdown=e=>{if(e.button!==0)return;drag={id:e.pointerId,x:e.clientX,y:e.clientY};canvas.setPointerCapture(e.pointerId);canvas.focus();};
   canvas.onpointermove=e=>{if(!drag||drag.id!==e.pointerId)return;const dx=e.clientX-drag.x,dy=e.clientY-drag.y;drag.x=e.clientX;drag.y=e.clientY;if(e.shiftKey){camera.pan[0]+=dx;camera.pan[1]+=dy;}else{camera.yaw+=dx*.01;camera.pitch=Math.max(-Math.PI/2,Math.min(Math.PI/2,camera.pitch+dy*.01));}schedule();};
   const end=e=>{if(drag?.id!==e.pointerId)return;drag=null;if(canvas.hasPointerCapture(e.pointerId))canvas.releasePointerCapture(e.pointerId);};canvas.onpointerup=end;canvas.onpointercancel=end;canvas.onlostpointercapture=()=>{drag=null;};
   canvas.onwheel=e=>{e.preventDefault();camera.zoom=Math.max(.1,Math.min(20,camera.zoom*Math.exp(-Math.max(-100,Math.min(100,e.deltaY))*.002)));schedule();};
   canvas.onkeydown=e=>{if(!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown','+','=','-','Home'].includes(e.key))return;e.preventDefault();if(e.key==='Home')return reset();if(e.key==='ArrowLeft')camera.yaw-=.1;if(e.key==='ArrowRight')camera.yaw+=.1;if(e.key==='ArrowUp')camera.pitch=Math.min(Math.PI/2,camera.pitch+.1);if(e.key==='ArrowDown')camera.pitch=Math.max(-Math.PI/2,camera.pitch-.1);if(['+','='].includes(e.key))camera.zoom=Math.min(20,camera.zoom*1.1);if(e.key==='-')camera.zoom=Math.max(.1,camera.zoom/1.1);schedule();};
  }
  const observer=typeof ResizeObserver==='function'?new ResizeObserver(schedule):null;observer?.observe(canvas);schedule();
  return {setCloud(value){if(disposed)return;try{cloud=value?preview(value,options.maxPoints||12000):null;error='';}catch(e){cloud=null;error=e.message;}schedule();},reset,destroy(){disposed=true;observer?.disconnect();if(pending)cancelAnimationFrame(pending);drag=null;cloud=null;shell.remove();},state:()=>({camera:structuredClone(camera),count:cloud?.points.length||0,disposed}),canvas};
 }
 return {validate,preview,orientation,project,create};
});
