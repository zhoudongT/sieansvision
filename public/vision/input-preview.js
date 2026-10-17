'use strict';
// Last completed image-producing nodes are retained for ROI editing after parameter edits.
// These previews never overwrite the uploaded source or participate in server execution.
const framePreviews=new Map();
let inputPreviewImage=null,inputPreviewData='',inputPreviewEpoch=0;
function rememberFrame(item){const step=project.steps.find(s=>s.id===item.id),image=item.output?.image??item.output?.annotatedImage;if(step?.operation==='yolo_segment'){if(item.output?.result?.output==='mask'&&typeof item.output.maskImage==='string')framePreviews.set(item.id,item.output.maskImage);else framePreviews.delete(item.id);}else if(step&&['camera_capture','preprocess','script','plugin','branch_merge','subflow','loop'].includes(step.operation)&&typeof image==='string')framePreviews.set(item.id,image);}
function inputPreviewForStep(){
 const step=selectedStep();let id=['camera_capture','branch_merge'].includes(step?.operation)?step.id:step?.imageFrom;const visited=new Set();
 while(id&&id!=='source'&&!visited.has(id)){
  visited.add(id);if(results.find(r=>r.id===id)?.skipped)return {data:'',label:'上游分支已跳过'};if(framePreviews.has(id))return {data:framePreviews.get(id),label:flowName(id)+' · 上次运行图像'};
  const upstream=project.steps.find(s=>s.id===id);if(upstream?.operation==='camera_capture')return {data:'',label:'相机尚未采集'};if(upstream?.operation==='branch_merge')return {data:'',label:'运行分支汇合后显示实际输入'};id=upstream?.imageFrom;
 }
 return {data:source||'',label:'图像源1.输出图像'};
}
function imageSizeStatus(){const out=$('output-image'),view=document.querySelector('.views').dataset.view;const image=view==='output'&&!out.hidden&&out.complete?out:inputPreviewImage;$('image-size').textContent=image?.naturalWidth?`${image.naturalWidth} × ${image.naturalHeight}`:'暂无可显示图像';}
function refreshInputPreview(){
 const next=inputPreviewForStep();$('input-image-label').textContent=next.label;
 if(next.data===inputPreviewData){paintSource();imageSizeStatus();return;}
 inputPreviewData=next.data;inputPreviewImage=null;const epoch=++inputPreviewEpoch;paintSource();$('empty-image').hidden=false;imageSizeStatus();
 if(!next.data)return;
 const image=new Image();image.onload=()=>{if(epoch!==inputPreviewEpoch)return;inputPreviewImage=image;canvas.width=image.naturalWidth;canvas.height=image.naturalHeight;$('empty-image').hidden=true;paintSource();imageSizeStatus();};image.onerror=()=>{if(epoch===inputPreviewEpoch)status('输入预览无法解码，请重新采集或执行','error');};image.src=next.data;
}
