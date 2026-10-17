'use strict';
const CLOUD_OPERATIONS=new Set(['cloud_filter','cloud_plane','cloud_cluster','cloud_measure','cloud_height','cloud_register']);
function cloud(value){
  if(!value||typeof value!=='object'||!['mm','m'].includes(value.unit))throw Error('点云必须声明单位 mm 或 m');
  if(!Array.isArray(value.points)||value.points.length<1||value.points.length>200000)throw Error('点云必须包含 1 到 200000 个点');
  const xyz=p=>Array.isArray(p)&&p.length===3&&p.every(n=>typeof n==='number'&&Number.isFinite(n)&&Math.abs(n)<=1e9);
  if(!value.points.every(xyz))throw Error('点云 points 必须为有限 N×3 数值数组');
  if(value.colors!==undefined&&(!Array.isArray(value.colors)||value.colors.length!==value.points.length||!value.colors.every(p=>xyz(p)&&p.every(n=>n>=0&&n<=1))))throw Error('点云 RGB 颜色必须在 0 到 1 之间并与点数量一致');
  if(value.frame!==undefined&&(typeof value.frame!=='string'||value.frame.length>120))throw Error('点云坐标系名称无效');
  if(Buffer.byteLength(JSON.stringify(value))>25_000_000)throw Error('点云数据超过 25 MB');
  return structuredClone(value);
}
function frame(request){
  const image=request.image??'';
  if(typeof image!=='string'||image.length>17_000_000)throw Error('输入图像格式无效');
  return {image,cloud:request.cloud==null?null:cloud(request.cloud),depth:request.depth==null?null:depth(request.depth)};
}
function depth(value){
  if(!value||value.format!=='png16'||!Number.isInteger(value.width)||!Number.isInteger(value.height)||value.width<1||value.height<1||value.width*value.height>4_000_000)throw Error('深度帧尺寸或格式无效');
  if(typeof value.scaleMeters!=='number'||!Number.isFinite(value.scaleMeters)||value.scaleMeters<=0||value.scaleMeters>1)throw Error('深度比例必须为有效的米/原始值');
  const intr=value.intrinsics;
  if(!intr||!['fx','fy','cx','cy'].every(k=>typeof intr[k]==='number'&&Number.isFinite(intr[k]))||intr.fx<=0||intr.fy<=0||intr.width!==value.width||intr.height!==value.height)throw Error('深度内参与图像尺寸不一致');
  if(typeof value.image!=='string'||value.image.length>16_000_050||!/^data:image\/png;base64,[A-Za-z0-9+/]+={0,2}$/.test(value.image))throw Error('深度图必须为 PNG 编码数据');
  const data=Buffer.from(value.image.slice(22),'base64');
  if(data.length<33||!data.subarray(0,8).equals(Buffer.from([137,80,78,71,13,10,26,10]))||data.toString('ascii',12,16)!=='IHDR'||data.readUInt32BE(16)!==value.width||data.readUInt32BE(20)!==value.height||data[24]!==16||data[25]!==0)throw Error('深度 PNG 头必须匹配尺寸及 16 位灰度格式');
  if(value.preview!==undefined&&(typeof value.preview!=='string'||value.preview.length>17_000_000||!value.preview.startsWith('data:image/png;base64,')))throw Error('深度预览图无效');
  if(typeof value.frame!=='string'||value.frame.length>120)throw Error('深度坐标系无效');
  if(!Number.isFinite(value.minMeters)||!Number.isFinite(value.maxMeters)||value.minMeters>=value.maxMeters)throw Error('深度预览范围无效');
  if(Buffer.byteLength(JSON.stringify(value))>25_000_000)throw Error('深度数据超过 25 MB');
  return structuredClone(value);
}
module.exports={cloud,depth,frame,CLOUD_OPERATIONS};
