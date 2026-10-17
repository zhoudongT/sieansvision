"""Local YOLOv8/11 instance masks with bounded contours and full-image coordinates."""
import base64
from pathlib import Path
import cv2
import numpy as np


def number(p,key,default,low,high,integer=False):
    value=p.get(key,default)
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not np.isfinite(value) or not low<=value<=high or (integer and int(value)!=value):
        raise ValueError(f'{key} 必须为 {low}–{high} 范围内的'+('整数' if integer else '数值'))
    return int(value) if integer else float(value)


def mask_record(mask,offset,epsilon):
    """Area/centroid from pixels; contour approximation is only for display/export."""
    area=int(np.count_nonzero(mask))
    if not area:return None
    x,y,w,h=cv2.boundingRect(mask)
    moments=cv2.moments(mask,binaryImage=True)
    contours,hierarchy=cv2.findContours(mask,cv2.RETR_TREE,cv2.CHAIN_APPROX_SIMPLE)
    outlines=[]
    for index,contour in enumerate(contours):
        parent=int(hierarchy[0,index,3]); ancestor=parent; depth=0
        while ancestor>=0:
            depth+=1;ancestor=int(hierarchy[0,ancestor,3])
        points=cv2.approxPolyDP(contour,epsilon,True).reshape(-1,2)+np.asarray(offset)
        outlines.append(dict(points=points.tolist(),isHole=bool(depth%2),parent=parent))
    return dict(areaPixels=area,center=[moments['m10']/area+offset[0],moments['m01']/area+offset[1]],
                maskBbox=[x+offset[0],y+offset[1],w,h],contours=outlines)


def segment(image,canvas,p,offset,model_dir,cache):
    name=p.get('model','yolo11n-seg.pt')
    if not isinstance(name,str) or Path(name).name!=name or not name.endswith('.pt'):
        raise ValueError('分割 model 必须是模型目录内的可信 .pt 文件名')
    path=(model_dir/name).resolve()
    if path.parent!=model_dir.resolve() or not path.is_file():
        raise ValueError('分割模型未安装或不在模型目录内；不会自动下载模型')
    confidence=number(p,'confidence',.25,0,1); iou=number(p,'iou',.45,0,1)
    size=number(p,'imageSize',640,32,1280,True)
    if size%32:raise ValueError('imageSize 必须为 32 的整数倍')
    maximum=number(p,'maxDetections',50,1,100,True)
    if maximum*size*size>32_768_000:raise ValueError('掩膜预算超限，请减小推理尺寸或最大目标数')
    minimum=number(p,'minArea',1,1,16_000_000,True)
    epsilon=number(p,'contourTolerance',.5,0,10)
    mode=p.get('output','overlay')
    if mode not in ('overlay','mask'):raise ValueError('output 必须为 overlay 或 mask')
    alpha=number(p,'overlayAlpha',.35,0,1) if mode=='overlay' else .35
    classes=p.get('classes')
    if classes is not None and (not isinstance(classes,list) or len(classes)>1000 or any(isinstance(v,bool) or not isinstance(v,int) or v<0 for v in classes)):
        raise ValueError('classes 必须是非负整数类别编号数组')
    from ultralytics import YOLO,settings
    from compute_device import select_device,predict
    selection=select_device(p.get('device','cpu'))
    from ultralytics.utils.ops import scale_masks
    settings.update({'sync':False})
    key=('segment',str(path),path.stat().st_mtime_ns,path.stat().st_size,selection['device'])
    if key not in cache:
        cache.clear()
        cache[key]=YOLO(str(path),task='segment')
    model=cache[key]
    if model.task!='segment':raise ValueError('此节点需要实例分割模型，请选择 YOLOv8/YOLO11 的分割权重')
    prediction=predict(model,image,selection,conf=confidence,iou=iou,imgsz=size,classes=classes,
                             max_det=maximum,retina_masks=False,verbose=False)
    boxes=prediction.boxes; masks=prediction.masks
    raw_count=len(boxes) if boxes is not None else 0
    if raw_count and (masks is None or len(masks.data)!=raw_count):
        raise ValueError('模型未返回与目标一一对应的实例掩膜')
    union=np.zeros(image.shape[:2],np.uint8); items=[]; total_points=0; discarded=0
    colors=[(220,145,20),(70,185,90),(40,110,230),(210,100,175),(180,180,30)]
    region=canvas[offset[1]:offset[1]+image.shape[0],offset[0]:offset[0]+image.shape[1]]
    for index in range(raw_count):
        # Resize one binary mask at a time; never allocate N full-resolution masks.
        mask=(scale_masks(masks.data[index:index+1,None],image.shape[:2],mode='nearest')[0,0].cpu().numpy()>.5).astype(np.uint8)*255
        area=int(np.count_nonzero(mask))
        if area<minimum:discarded+=1;continue
        record=mask_record(mask,offset,epsilon)
        total_points+=sum(len(c['points']) for c in record['contours'])
        if total_points>50000:raise ValueError('轮廓超过 50000 点，请增加轮廓简化容差或减少目标数')
        box=boxes[index]; category=int(box.cls[0]);score=float(box.conf[0]);label=str(prediction.names[category])
        x1,y1,x2,y2=box.xyxy[0].cpu().tolist()
        record.update(instance=len(items)+1,classId=category,label=label,confidence=score,bbox=[x1+offset[0],y1+offset[1],x2-x1,y2-y1])
        items.append(record);union|=mask
        if mode=='overlay':
            color=colors[index%len(colors)]; selected=mask>0
            region[selected]=np.round(region[selected]*(1-alpha)+np.array(color)*alpha).astype(np.uint8)
            contours,_=cv2.findContours(mask,cv2.RETR_LIST,cv2.CHAIN_APPROX_SIMPLE)
            cv2.drawContours(region,contours,-1,color,1)
            cv2.putText(canvas,f'{label} {score:.2f}',(round(x1)+offset[0],max(16,round(y1)+offset[1]-4)),cv2.FONT_HERSHEY_SIMPLEX,.5,color,1)
    full_mask=np.zeros(canvas.shape[:2],np.uint8)
    full_mask[offset[1]:offset[1]+union.shape[0],offset[0]:offset[0]+union.shape[1]]=union
    if mode=='mask':canvas[:]=cv2.cvtColor(full_mask,cv2.COLOR_GRAY2BGR)
    _,encoded=cv2.imencode('.png',full_mask)
    result=dict(model=name,task='segment',**selection,count=len(items),rawCount=raw_count,filteredCount=discarded,
                maxDetections=maximum,limitReached=raw_count>=maximum,output=mode,items=items,
                unionAreaPixels=int(np.count_nonzero(union)),summedAreaPixels=sum(item['areaPixels'] for item in items),
                maskWidth=canvas.shape[1],maskHeight=canvas.shape[0],contourTolerance=epsilon,
                note='面积按还原到原图的二值掩膜像素统计，保留空洞；轮廓用于展示，可有简化误差。目标重叠时面积和不等于并集面积。通用预训练类别不代表工业缺陷能力。')
    return result,'data:image/png;base64,'+base64.b64encode(encoded).decode()
