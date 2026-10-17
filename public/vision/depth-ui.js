'use strict';
let sourceDepth=null,depthImporting=false;
async function depthFileContent(file){const value=await readFile(file);if(typeof value!=='string'||!/^data:[^,]*;base64,/.test(value))throw Error('深度文件读取格式无效');return 'data:image/png;base64,'+value.slice(value.indexOf(',')+1);}
function depthImportParams(){
 const number=id=>{const input=$('depth-import-'+id);if(!input.checkValidity()||input.value.trim()==='')throw Error('请填写有效的深度参数：'+input.getAttribute('aria-label'));return Number(input.value);};
 if(!$('depth-import-confirm').checked)throw Error('请确认文件是已校正针孔相机的光轴 Z 深度');
 return {projection:'rectified-z',fx:number('fx'),fy:number('fy'),cx:number('cx'),cy:number('cy'),scaleMeters:number('scale')/1000,minDepth:number('min')/1000,maxDepth:number('max')/1000,pointStride:number('stride'),invalidValue:number('invalid'),frame:$('depth-import-frame').value.trim()};
}
function setSourceDepthFrame(value){
 source='';originalImage=null;framePreviews.clear();inputPreviewEpoch++;inputPreviewData='';inputPreviewImage=null;
 ctx.clearRect(0,0,canvas.width,canvas.height);$('empty-image').hidden=false;$('image-size').textContent='未载入彩色图像';
 setSourceCloud(value.cloud,value.depth);setImageView('depth');renderDepthPreview();refreshInputPreview();
}
async function demoDepth(name,params){
 const response=await fetch('samples/'+name);if(!response.ok)throw Error('深度演示文件不存在');
 return api('run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({operation:'depth_import',name,content:await depthFileContent(await response.blob()),params})});
}
function initDepthImportUI(){
 $('depth-import-form').onsubmit=safe(async event=>{
  event.preventDefault();if(running||depthImporting)return;
  const file=$('depth-import-file').files[0];if(!file)throw Error('请选择原始 16 位 PNG 深度文件');
  if(file.size>12000000||!file.name.toLowerCase().endsWith('.png'))throw Error('请选择不超过 12 MB 的 PNG 深度文件');
  const params=depthImportParams(),before={project,source,cloud:sourceCloud,depth:sourceDepth};
  depthImporting=true;$('depth-import-fields').disabled=true;setBusy(true);
  try{
   const result=await api('run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({operation:'depth_import',name:file.name,content:await depthFileContent(file),params})});
   if(running||project!==before.project||source!==before.source||sourceCloud!==before.cloud||sourceDepth!==before.depth)throw Error('工程或输入已变化，请重新导入深度文件');
   setSourceDepthFrame(result);$('cloud-dialog').close();status(`已导入 ${file.name} · ${result.depth.width} × ${result.depth.height} · ${result.cloud.points.length} 点 · mm`,'success');
  }finally{depthImporting=false;$('depth-import-fields').disabled=running;setBusy(running);}
 });
}
function resultDepth(){
 let id=displayedResultId;const visited=new Set();
 while(id&&id!=='source'&&!visited.has(id)){
  visited.add(id);const row=results.find(r=>r.id===id),step=project.steps.find(s=>s.id===id);
  if(row?.error||row?.skipped)return null;
  if(row?.output&&Object.hasOwn(row.output,'depth'))return row.output.depth;
  if(step?.operation==='camera_capture')return null;
  id=row?.inputFrom||step?.imageFrom;
 }
 return sourceDepth;
}
function renderDepthPreview(){
 const depth=resultDepth(),image=$('depth-image');image.hidden=!depth;$('depth-empty').hidden=!!depth;
 if(!depth){image.removeAttribute('src');$('depth-summary').textContent='导入原始 16 位 PNG 深度文件，或选择深度采集结果';return;}
 image.src=depth.preview;
 $('depth-summary').textContent=`${depth.width} × ${depth.height} · 原始 16 位 · 1 原始值 = ${Number((depth.scaleMeters*1000).toPrecision(7))} mm · 色标 ${depth.minMeters}–${depth.maxMeters} m · 黑色为无效/范围外`;
}
