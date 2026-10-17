(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.MonitorChart=api;})(typeof globalThis!=='undefined'?globalThis:this,function(){
 'use strict';
 function plot(samples,width=520,height=180){
  const valid=samples.filter(s=>s.quality==='good'&&typeof s.value==='number'&&Number.isFinite(s.value)&&Number.isFinite(s.time));
  if(!valid.length)return {paths:[],validCount:0};
  const rawLow=Math.min(...valid.map(s=>s.value)),rawHigh=Math.max(...valid.map(s=>s.value)),scale=Math.max(1,Math.abs(rawLow),Math.abs(rawHigh));let low=rawLow/scale,high=rawHigh/scale;const padding=low===high?Math.max(1/scale,Math.abs(low)*.05):(high-low)*.1;low-=padding;high+=padding;
  const times=samples.filter(s=>Number.isFinite(s.time)).map(s=>s.time),start=Math.min(...times),end=Math.max(...times),paths=[],dots=[];let current=[],first=null;const finish=()=>{if(current.length){paths.push(current.join(' '));if(current.length===1)dots.push(first);}current=[];};
  samples.forEach((sample,i)=>{
   if(sample.quality!=='good'||typeof sample.value!=='number'||!Number.isFinite(sample.value)||!Number.isFinite(sample.time)){finish();return;}
   const x=52+(end===start?(samples.length<2?.5:i/(samples.length-1)):(sample.time-start)/(end-start))*(width-68),y=12+(high-sample.value/scale)/(high-low)*(height-42);
   if(!current.length)first={x,y};current.push((current.length?'L':'M')+x.toFixed(2)+','+y.toFixed(2));
  });finish();const finite=v=>Math.max(-Number.MAX_VALUE,Math.min(Number.MAX_VALUE,v*scale));return {paths,dots,validCount:valid.length,low:finite(low),high:finite(high),middle:finite((low+high)/2),start,end};
 }
 return {plot};
});
