'use strict';
let sourceCloud=null,resultCloud=null,cloudYaw=-.65,cloudPitch=.65,cloudZoom=1,cloudPan=[0,0];
const cloudBoundsCache=new WeakMap();
const cloudCatalog={
  cloud_filter:{name:'点云滤波',tag:'3D · 裁剪 / 降采样 / 去噪',glyph:'▦',defaults:{method:'voxel',voxelSize:1},description:'处理点云并传给下游。所有距离参数使用输入点云的单位。',fields:[['method','处理方式',['voxel','crop','statistical','radius']],['voxelSize','体素边长',.000001,1000000,.1],['neighbors','统计邻域点数',2,200],['stdRatio','标准差倍数',.01,100,.1],['radius','邻域半径',.000001,1000000,.1],['minPoints','最少邻域点数',1,1000]],hint:'裁剪时通过最小坐标、最大坐标表设置三轴边界。voxel：体素降采样；statistical：统计去噪；radius：半径去噪。'},
  cloud_plane:{name:'3D 平面分割',tag:'Open3D · RANSAC',glyph:'▱',defaults:{distanceThreshold:.5,iterations:500,output:'inliers'},description:'拟合主平面，输出法向、平面方程与残差，可提取平面内点或移除背景平面。',fields:[['distanceThreshold','距离阈值',.000001,1000000,.1],['iterations','迭代次数',10,10000],['output','输出点云',['inliers','outliers','all']]],hint:'inliers：平面内点；outliers：平面外点；all：保留全部。方程 ax+by+cz+d=0；法向最大绝对分量朝正方向。'},
  cloud_cluster:{name:'3D 目标聚类',tag:'DBSCAN · 数量 / 尺寸',glyph:'◈',defaults:{eps:3,minPoints:8},description:'按空间密度分组，输出每个目标的点数与轴对齐尺寸，不推断物体类别。',fields:[['eps','邻域半径',.000001,1000000,.1],['minPoints','最小邻域点数',2,1000]],hint:'最多 3 万点、100 个聚类，请先滤波。不同聚类着不同颜色，灰色为噪声。'},
  cloud_measure:{name:'3D 尺寸测量',tag:'X / Y / Z · 包围盒',glyph:'↗',defaults:{},description:'测量当前坐标系下的轴对齐包围盒，输出三轴尺寸、中心和边界。',fields:[],hint:'坐标系旋转会影响尺寸。boundingBoxVolume 仅为包围盒体积，不等于实际物体体积。'},
  cloud_height:{name:'高度与体积估计',tag:'3D · 基准高度 / 表面网格',glyph:'▤',defaults:{baselineZ:0,cellSize:1},description:'相对水平基准 Z 测高度，按 XY 网格最高表面估计体积。适合单值高度表面。',fields:[['baselineZ','基准 Z',-1000000000,1000000000,.1],['cellSize','网格边长',.000001,1000000,.1]],hint:'缺失格不补齐，负高度归零；每个已观测网格计一个完整单元。遮挡、边缘和网格大小会影响估计，不是封闭实体真实体积。'},
  cloud_register:{name:'3D 点云配准',tag:'全局定位 · ICP 精配准',glyph:'⌖',defaults:{method:'icp',maxDistance:5,iterations:50},description:'将输入点云对齐参考坐标系。初始姿态未知时使用全局定位；已接近参考姿态时使用局部 ICP。',fields:[['method','配准方式',['icp','global']],['voxelSize','特征体素边长',.000001,1000000,'any'],['ransacIterations','粗配准最大尝试次数',100,100000],['ransacConfidence','粗配准停止概率',.9,.999999,'any'],['maxDistance','最大对应距离',.000001,1000000,'any'],['iterations','精配准迭代次数',1,500],['minFitness','输入最低覆盖比例',0,1,'any'],['minTargetFitness','参考最低覆盖比例',0,1,'any'],['maxRmsError','最大均方根误差',.000001,1000000,'any']],hint:'先上传同单位的参考点云。全局定位使用 FPFH 特征和 RANSAC，再进行精配准；质量不达标保留原点云、返回未找到。后接条件判断的“是否找到”字段，可阻止下游测量。覆盖率和停止概率均不是识别置信度；对称件可能有多解。'}
};
function cloudParamDefault(step,key){
 if(step.operation!=='cloud_register')return undefined;
 return {method:'icp',maxDistance:5,iterations:50,voxelSize:1,ransacIterations:25000,ransacConfidence:.999,minFitness:.7,minTargetFitness:.3,maxRmsError:typeof step.params.maxDistance==='number'?step.params.maxDistance/2:2.5}[key];
}
function cloudRefreshDefaults(step,key){
 if(step.operation==='cloud_register'&&key==='maxDistance'&&!Object.hasOwn(step.params,'maxRmsError')){
  const input=$('form-fields').querySelector('input[aria-label="最大均方根误差"]');
  if(input)input.value=cloudParamDefault(step,'maxRmsError');
 }
}
function cloudFields(){
  const step=selectedStep();$('cloud-reference-tools').hidden=step?.operation!=='cloud_register';
  $('quick-sample').textContent=step?.operation.startsWith('cloud_')?'仅载入当前算子的示例点云':'仅载入当前算子的示例图';
  $('cloud-reference-status').textContent=step?.params.targetCloud?`${step.params.targetCloud.points.length} 点 · ${step.params.targetCloud.unit}`:'尚未设置参考点云';
}
async function demoCloud(name){
  const response=await fetch('samples/'+name);if(!response.ok)throw Error('点云演示素材不存在');
  return (await api('run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({operation:'cloud_import',name,content:await readFile(await response.blob()),unit:'mm'})})).cloud;
}
async function readCloudFile(file){
  if(!file)throw Error('请选择点云文件');
  return (await api('run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({operation:'cloud_import',name:file.name,content:await readFile(file),unit:$('cloud-unit').value})})).cloud;
}
function setSourceCloud(value,depth=null){sourceCloud=value;sourceDepth=depth;resultCloud=null;results=[];renderResults();renderPipeline();setImageView('cloud');cloudReset();}
function cloudReset(view='iso'){cloudYaw=view==='top'?0:-.65;cloudPitch=view==='top'?Math.PI/2:.65;cloudZoom=1;cloudPan=[0,0];drawCloud();}
function selectedCloud(){return $('cloud-data').value==='input'?sourceCloud:resultCloud||sourceCloud;}
function drawCloud(){
  const canvas=$('cloud-canvas');if(!canvas||document.querySelector('.views').dataset.view!=='cloud')return;
  const rect=canvas.getBoundingClientRect();if(rect.width<1||rect.height<1)return;
  const dpr=Math.min(devicePixelRatio||1,2);canvas.width=Math.round(rect.width*dpr);canvas.height=Math.round(rect.height*dpr);
  const g=canvas.getContext('2d');g.scale(dpr,dpr);const w=rect.width,h=rect.height;
  g.fillStyle='#edf4f9';g.fillRect(0,0,w,h);g.strokeStyle='#dce8f0';g.lineWidth=1;
  for(let x=0;x<w;x+=28){g.beginPath();g.moveTo(x,0);g.lineTo(x,h);g.stroke();}
  for(let y=0;y<h;y+=28){g.beginPath();g.moveTo(0,y);g.lineTo(w,y);g.stroke();}
  const cloud=selectedCloud();$('cloud-empty').hidden=!!cloud;
  if(!cloud){$('cloud-stats').textContent='尚未载入点云';$('cloud-dimensions').textContent='';return;}
  if(!cloudBoundsCache.has(cloud)){const low=[Infinity,Infinity,Infinity],high=[-Infinity,-Infinity,-Infinity];for(const point of cloud.points)for(let k=0;k<3;k++){low[k]=Math.min(low[k],point[k]);high[k]=Math.max(high[k],point[k]);}cloudBoundsCache.set(cloud,{low,high});}
  const {low,high}=cloudBoundsCache.get(cloud);
  const center=low.map((n,k)=>(n+high[k])/2),span=Math.max(...low.map((n,k)=>high[k]-n),.000001);
  const cy=Math.cos(cloudYaw),sy=Math.sin(cloudYaw),cp=Math.cos(cloudPitch),sp=Math.sin(cloudPitch);
  const size=low.map((n,k)=>high[k]-n),projectedWidth=Math.abs(cy)*size[0]+Math.abs(sy)*size[1],projectedHeight=Math.abs(sp*sy)*size[0]+Math.abs(sp*cy)*size[1]+Math.abs(cp)*size[2];
  const scale=.78*Math.min(w/Math.max(projectedWidth,span*.05),h/Math.max(projectedHeight,span*.05))*cloudZoom;
  const project=p=>{const x=p[0]-center[0],y=p[1]-center[1],z=p[2]-center[2],rx=x*cy-y*sy,ry=x*sy+y*cy;return [w/2+cloudPan[0]+rx*scale,h/2+cloudPan[1]-(z*cp+ry*sp)*scale,ry*cp-z*sp];};
  // Display sampling only; all accepted points remain in the calculation payload.
  const stride=Math.max(1,Math.ceil(cloud.points.length/12000)),display=[];
  for(let i=0;i<cloud.points.length;i+=stride){const p=cloud.points[i],q=project(p),t=(p[2]-low[2])/(high[2]-low[2]||1);const rgb=cloud.colors?.[i];display.push({q,color:rgb?`rgb(${rgb.map(v=>Math.round(v*255)).join(',')})`:`hsl(${202-160*t} 70% ${40+8*t}%)`});}
  display.sort((a,b)=>b.q[2]-a.q[2]);for(const {q,color}of display){g.fillStyle=color;g.fillRect(q[0]-1.4,q[1]-1.4,2.8,2.8);}
  // Axis-aligned bounds, with dimensional labels in source coordinates.
  const corners=Array.from({length:8},(_,i)=>[i&1?high[0]:low[0],i&2?high[1]:low[1],i&4?high[2]:low[2]]);
  g.strokeStyle='#54799388';g.setLineDash([3,4]);for(let i=0;i<8;i++)for(let axis=0;axis<3;axis++){const j=i^(1<<axis);if(j<i)continue;const a=project(corners[i]),b=project(corners[j]);g.beginPath();g.moveTo(a[0],a[1]);g.lineTo(b[0],b[1]);g.stroke();}g.setLineDash([]);
  g.font='11px sans-serif';const origin=project(low);
  for(const [axis,color]of [[0,'#c64f59'],[1,'#219b77'],[2,'#1292c1']]){const end=[...low];end[axis]+=span*.3;const q=project(end);g.strokeStyle=color;g.beginPath();g.moveTo(origin[0],origin[1]);g.lineTo(q[0],q[1]);g.stroke();g.fillStyle=color;g.fillText('XYZ'[axis],q[0]+4,q[1]-4);}
  $('cloud-stats').textContent=`${cloud.points.length.toLocaleString()} 点 · ${cloud.unit} · ${cloud.frame||'sensor'}${stride>1?' · 预览 '+display.length.toLocaleString()+' 点（计算保留全部）':''}`;
  $('cloud-dimensions').textContent=low.map((v,k)=>'XYZ'[k]+' '+Number((high[k]-v).toFixed(3))).join(' / ')+' '+cloud.unit;
}
function initCloudUI(){
  initDepthImportUI();
  $('open-cloud').onclick=()=>{if(!running)$('cloud-dialog').showModal();};
  $('cloud-file').onchange=safe(async e=>{const file=e.target.files[0];if(!file)return;const button=$('cloud-file');button.disabled=true;try{const value=await readCloudFile(file);if(running)throw Error('执行期间不可替换点云');setSourceCloud(value);$('cloud-dialog').close();status(`已载入 ${file.name} · ${value.points.length} 点 · ${value.unit}`,'success');}finally{button.disabled=false;e.target.value='';}});
  $('cloud-clear').onclick=()=>{if(running)return;setSourceCloud(null);$('cloud-dialog').close();status('输入点云已清除');};
  $('cloud-reference-file').onchange=safe(async e=>{const step=selectedStep();if(!step||step.operation!=='cloud_register'||running)return;const value=await readCloudFile(e.target.files[0]);if(running||step!==selectedStep())throw Error('所选模块已变化，请重新上传参考点云');applyParams();step.params.targetCloud=value;dirty();renderParams();e.target.value='';});
  $('cloud-data').onchange=()=>{cloudReset();};$('cloud-reset').onclick=()=>cloudReset();$('cloud-top').onclick=()=>cloudReset('top');
  let drag=null;const canvas=$('cloud-canvas');canvas.onpointerdown=e=>{if(e.button!==0)return;drag={x:e.clientX,y:e.clientY,pan:e.shiftKey,yaw:cloudYaw,pitch:cloudPitch,offset:[...cloudPan]};canvas.setPointerCapture(e.pointerId);};
  canvas.onpointermove=e=>{if(!drag)return;const dx=e.clientX-drag.x,dy=e.clientY-drag.y;if(drag.pan)cloudPan=[drag.offset[0]+dx,drag.offset[1]+dy];else{cloudYaw=drag.yaw+dx*.008;cloudPitch=Math.max(-Math.PI/2,Math.min(Math.PI/2,drag.pitch+dy*.008));}drawCloud();};
  canvas.onpointerup=canvas.onpointercancel=()=>drag=null;
  canvas.addEventListener('wheel',e=>{e.preventDefault();cloudZoom=Math.max(.15,Math.min(20,cloudZoom*Math.exp(-e.deltaY*.001)));drawCloud();},{passive:false});
  canvas.onkeydown=e=>{if(['ArrowLeft','ArrowRight','ArrowUp','ArrowDown','+','-','Home'].includes(e.key)){e.preventDefault();if(e.key==='Home')return cloudReset();if(e.key==='ArrowLeft')cloudYaw-=.1;if(e.key==='ArrowRight')cloudYaw+=.1;if(e.key==='ArrowUp')cloudPitch=Math.min(Math.PI/2,cloudPitch+.1);if(e.key==='ArrowDown')cloudPitch=Math.max(-Math.PI/2,cloudPitch-.1);if(e.key==='+')cloudZoom=Math.min(20,cloudZoom*1.1);if(e.key==='-')cloudZoom=Math.max(.15,cloudZoom/1.1);drawCloud();}};
  new ResizeObserver(()=>requestAnimationFrame(drawCloud)).observe(canvas);
}
