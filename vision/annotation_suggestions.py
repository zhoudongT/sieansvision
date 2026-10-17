"""Read-only model proposals. Labels are written only by the existing explicit save."""
import math
from pathlib import Path
from annotations import image_path,read_image,revision
from training import parse_labels


def convert(items,task,width,height):
    proposals=[];rejected=[]
    for index,item in enumerate(items):
        try:
            if task=='detect':
                x,y,w,h=item['bbox']
                x1=max(0,min(width,x));y1=max(0,min(height,y))
                x2=max(0,min(width,x+w));y2=max(0,min(height,y+h))
                coords=[(x1+x2)/2/width,(y1+y2)/2/height,(x2-x1)/width,(y2-y1)/height]
                record=dict(box=coords)
            else:
                contours=item['contours']
                if len(contours)!=1 or contours[0]['isHole']:raise ValueError('存在空洞或分离轮廓，需人工绘制')
                points=[[max(0,min(1,x/width)),max(0,min(1,y/height))] for x,y in contours[0]['points']]
                if len(points)>500:raise ValueError('轮廓超过 500 点，需人工简化')
                coords=[v for p in points for v in p];record=dict(points=points)
            parse_labels('0 '+' '.join(str(v) for v in coords),task,['proposal'])
            confidence=float(item['confidence'])
            if not math.isfinite(confidence):raise ValueError('置信度无效')
            proposals.append(dict(label=str(item['label']),modelClassId=int(item['classId']),confidence=confidence,**record))
        except (ValueError,KeyError,TypeError) as error:
            rejected.append(dict(target=index+1,reason=str(error)))
    return dict(proposals=proposals,rejected=rejected)


def suggest(request):
    from ultralytics import YOLO,settings
    from compute_device import select_device,predict
    image,label=image_path(request['folder'],request['split'],request['name'])
    pixels=read_image(image)
    before=revision(image,label)
    if before!=request.get('revision'):raise ValueError('图片或标注已被其他页面修改，请重新载入后编辑')
    model_path=Path(request['modelPath'])
    if not model_path.is_file():raise ValueError('本地模型不存在')
    confidence=request.get('confidence',.25)
    if isinstance(confidence,bool) or not isinstance(confidence,(float,int)) or not math.isfinite(confidence) or not .01<=confidence<=1:raise ValueError('候选置信度须为 0.01–1')
    selection=select_device(request.get('device','cpu'))
    settings.update({'sync':False})
    model=YOLO(str(model_path))
    if model.task!=request['task']:raise ValueError('模型任务与数据集不一致，请选择对应的检测或分割模型')
    if request['task']=='segment':
        # Reuse the established original-resolution mask/contour contract, including holes.
        from yolo_segmentation import segment
        cache={('segment',str(model_path),model_path.stat().st_mtime_ns,model_path.stat().st_size,selection['device']):model}
        result,_=segment(pixels,pixels.copy(),dict(model=model_path.name,confidence=confidence,device=request.get('device','cpu'),imageSize=640,maxDetections=50,output='mask',contourTolerance=1),[0,0],model_path.parent,cache)
        items=result['items'];limited=result['limitReached']
    else:
        prediction=predict(model,pixels,selection,conf=confidence,imgsz=640,max_det=50,verbose=False)
        items=[]
        for box in prediction.boxes:
            x1,y1,x2,y2=box.xyxy[0].cpu().tolist();category=int(box.cls[0])
            items.append(dict(bbox=[x1,y1,x2-x1,y2-y1],classId=category,label=str(prediction.names[category]),confidence=float(box.conf[0])))
        limited=len(items)>=50
    if before!=revision(image,label):raise ValueError('图片或标注已被其他页面修改，请重新载入后编辑')
    return dict(**convert(items,request['task'],pixels.shape[1],pixels.shape[0]),**selection,revision=before,limitReached=limited,model=model_path.name)
