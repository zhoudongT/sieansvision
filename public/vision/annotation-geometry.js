(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.AnnotationGeometry=api;})(typeof globalThis!=='undefined'?globalThis:this,function(){
 'use strict';
 const clamp=v=>Math.max(0,Math.min(1,v));
 function box(a,b){return [(a[0]+b[0])/2,(a[1]+b[1])/2,Math.abs(a[0]-b[0]),Math.abs(a[1]-b[1])];}
 function corners(b){const [x,y,w,h]=b;return [[x-w/2,y-h/2],[x+w/2,y-h/2],[x+w/2,y+h/2],[x-w/2,y+h/2]];}
 function move(record,dx,dy){const p=record.box?corners(record.box):record.points;dx=Math.max(-Math.min(...p.map(v=>v[0])),Math.min(1-Math.max(...p.map(v=>v[0])),dx));dy=Math.max(-Math.min(...p.map(v=>v[1])),Math.min(1-Math.max(...p.map(v=>v[1])),dy));return record.box?{...record,box:[record.box[0]+dx,record.box[1]+dy,...record.box.slice(2)]}:{...record,points:p.map(([x,y])=>[x+dx,y+dy])};}
 function polygonValid(points){
  if(points.length<3||points.length>500||points.some(p=>p.length!==2||p.some(v=>!Number.isFinite(v)||v<0||v>1)))return false;
  const cross=(a,b,c)=>(b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]);
  const on=(a,b,p)=>Math.abs(cross(a,b,p))<1e-10&&p[0]>=Math.min(a[0],b[0])-1e-10&&p[0]<=Math.max(a[0],b[0])+1e-10&&p[1]>=Math.min(a[1],b[1])-1e-10&&p[1]<=Math.max(a[1],b[1])+1e-10;
  let area=0;
  for(let i=0;i<points.length;i++){
   const a=points[i],b=points[(i+1)%points.length];if(Math.hypot(a[0]-b[0],a[1]-b[1])<1e-10)return false;area+=a[0]*b[1]-b[0]*a[1];
   for(let j=i+1;j<points.length;j++){
    if(j===i+1||(i===0&&j===points.length-1))continue;const c=points[j],d=points[(j+1)%points.length];
    if((cross(a,b,c)*cross(a,b,d)<0&&cross(c,d,a)*cross(c,d,b)<0)||on(a,b,c)||on(a,b,d)||on(c,d,a)||on(c,d,b))return false;
   }
  }return Math.abs(area)>2e-8;
 }
 return {clamp,box,corners,move,polygonValid};
});
