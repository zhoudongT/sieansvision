"""Bounded rotated/scaled template search with polygon NMS and pose contracts."""
import hashlib
import math
import cv2
import numpy as np

MAX_VARIANTS=256
MAX_CELLS=30_000_000
MAX_CANDIDATES=4096


def number(p,key,default,low,high,integer=False):
    value=p.get(key,default)
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not low<=value<=high or integer and int(value)!=value:raise ValueError('模板定位参数类型或范围无效：'+key)
    return int(value) if integer else float(value)


def pixel_digest(image):return hashlib.sha256(image.tobytes()).hexdigest()


def variant(template,angle,scale):
    h,w=template.shape;corners=np.array([[-.5,-.5],[w-.5,-.5],[w-.5,h-.5],[-.5,h-.5]],np.float64)
    matrix=cv2.getRotationMatrix2D(((w-1)/2,(h-1)/2),angle,scale)
    transformed=corners@matrix[:,:2].T+matrix[:,2];low=transformed.min(axis=0);extent=transformed.max(axis=0)-low
    size=tuple(np.ceil(extent-1e-9).astype(int));matrix[:,2]+=-.5-low
    return matrix,size,corners


def overlap(a,b):
    if np.any(np.minimum(a.max(axis=0),b.max(axis=0))<=np.maximum(a.min(axis=0),b.min(axis=0))):return 0.
    intersection,_=cv2.intersectConvexConvex(a.astype(np.float32),b.astype(np.float32));union=abs(cv2.contourArea(a.astype(np.float32)))+abs(cv2.contourArea(b.astype(np.float32)))-intersection
    return max(0.,min(1.,float(intersection/union))) if union>0 else 0.


def locate(image,canvas,p,offset,reference):
    if reference is None:raise ValueError('目标定位需要模板图，可上传或从原图框选模板')
    template=cv2.cvtColor(reference,cv2.COLOR_BGR2GRAY);gray=cv2.cvtColor(image,cv2.COLOR_BGR2GRAY)
    if min(template.shape)<4 or template.size>1_000_000 or gray.size>4_000_000:raise ValueError('模板需至少 4×4 且不超过 100 万像素；搜索 ROI 不超过 400 万像素')
    if template.std()<1:raise ValueError('模板缺少纹理，无法可靠定位')
    start=number(p,'angleStart',0,-180,180);end=number(p,'angleEnd',0,-180,180);step=number(p,'angleStep',10,1,180)
    minimum=number(p,'minScore',.85,0,1);maximum=number(p,'maxMatches',1,1,50,True);iou=number(p,'overlapThreshold',.3,.01,.9)
    if end<start:raise ValueError('angleEnd 必须大于等于 angleStart')
    scales=p.get('scales',[1])
    if not isinstance(scales,list) or not 1<=len(scales)<=8:raise ValueError('搜索比例必须为 1–8 行数值')
    scales=[number({'scale':v},'scale',1,.1,5) for v in scales]
    scales=list(dict.fromkeys(scales));angles=list(np.arange(start,end+.00001,step))
    if len(angles)*len(scales)>MAX_VARIANTS:raise ValueError('旋转与缩放组合超过 256，请缩小搜索范围或增大角度步长')
    origin=p.get('origin',[0,0])
    if not isinstance(origin,list) or len(origin)!=2 or any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or abs(v)>1e9 for v in origin):raise ValueError('坐标原点必须是两个有限数值')
    # Prepare all sizes and reject excessive work before any expensive matching.
    variants=[];cells=0
    for scale in scales:
        for angle in angles:
            matrix,size,corners=variant(template,float(angle),scale);w,h=size
            if min(size)<4 or w>gray.shape[1] or h>gray.shape[0]:continue
            cells+=(gray.shape[1]-w+1)*(gray.shape[0]-h+1)
            if cells>MAX_CELLS:raise ValueError('模板搜索量超过 3000 万位置组合，请缩小 ROI 或角度/比例范围')
            variants.append((float(angle),scale,matrix,size,corners))
    if not variants:raise ValueError('所有旋转/比例的模板均比搜索区域大或过小')
    candidates=[];best_score=0.;candidate_limited=False;per_variant=min(256,max(32,4*(maximum+1)))
    # A separately tracked best score is diagnostic only. Below threshold, no
    # pose or position is returned for downstream measurement.
    for angle,scale,matrix,size,corners in variants:
        rotated=cv2.warpAffine(template,matrix,size,flags=cv2.INTER_LINEAR)
        mask=cv2.warpAffine(np.full_like(template,255),matrix,size,flags=cv2.INTER_NEAREST)
        if np.count_nonzero(mask)<16:continue
        errors=cv2.matchTemplate(gray,rotated,cv2.TM_SQDIFF_NORMED,mask=mask)
        scores=np.where(np.isfinite(errors),np.clip(1-errors,0,1),-1).astype(np.float32)
        best_score=max(best_score,float(scores.max()))
        peaks=(scores>=minimum)&(scores==cv2.dilate(scores,np.ones((3,3),np.uint8)))
        indices=np.flatnonzero(peaks)
        if len(indices)>per_variant:
            candidate_limited=True
            # Stable top ordering avoids selecting arbitrary plateau pixels.
            values=scores.ravel()[indices];order=np.lexsort((indices,-values))[:per_variant];indices=indices[order]
        for index in indices:
            y,x=divmod(int(index),scores.shape[1]);transform=matrix.copy();transform[:,2]+=np.array([x,y])+offset
            points=corners@transform[:,:2].T+transform[:,2]
            candidates.append(dict(score=float(scores[y,x]),angleDeg=angle,scale=scale,points=points,matrix=transform))
        if len(candidates)>MAX_CANDIDATES:raise ValueError('模板候选超过 4096，请提高匹配阈值或缩小搜索范围')
    candidates.sort(key=lambda c:(-c['score'],c['angleDeg'],c['scale'],c['matrix'][1,2],c['matrix'][0,2]))
    selected=[];more=False
    for candidate in candidates:
        if any(overlap(candidate['points'],other['points'])>iou for other in selected):continue
        if len(selected)==maximum:more=True;break
        selected.append(candidate)
    source_hash=pixel_digest(canvas);template_hash=pixel_digest(reference);height,width=canvas.shape[:2];th,tw=template.shape
    items=[]
    for index,candidate in enumerate(selected):
        points=candidate['points'];center=points.mean(axis=0);matrix=candidate['matrix'];inverse=cv2.invertAffineTransform(matrix)
        pose=dict(format='sieans-pose2d-v1',sourceWidth=width,sourceHeight=height,templateWidth=tw,templateHeight=th,sourcePixelSha256=source_hash,templatePixelSha256=template_hash,matrix=matrix.tolist(),inverse=inverse.tolist(),angleDeg=candidate['angleDeg'],scale=candidate['scale'])
        item=dict(index=index+1,score=candidate['score'],centerX=float(center[0]),centerY=float(center[1]),angleDeg=candidate['angleDeg'],scale=candidate['scale'],center=center.tolist(),polygon=points.tolist(),offsetPixels=(center-np.array(origin)).tolist(),pose=pose)
        items.append(item);cv2.polylines(canvas,[np.round(points).astype(np.int32)],True,(0,210,80),2,cv2.LINE_AA);cv2.putText(canvas,str(index+1),(round(center[0]),round(center[1])),cv2.FONT_HERSHEY_SIMPLEX,.6,(0,210,80),2,cv2.LINE_AA)
    limited=more or candidate_limited
    result=dict(found=bool(items),count=len(items),items=items,bestScore=best_score,limitReached=limited,candidateLimitReached=candidate_limited,unique=bool(len(items)==1 and not limited),searchedVariants=len(variants),score=items[0]['score'] if items else best_score,note='OpenCV 正角为逆时针；结果按分数降序。对称模板不能可靠区分方向；位置和角度为离散搜索值。')
    if items:
        result.update({key:items[0][key] for key in ['angleDeg','scale','center','centerX','centerY','polygon','offsetPixels','pose']})
    result['diagnostic']='匹配完成；结果可能因上限而截断' if limited else '已找到唯一目标' if result['unique'] else '已找到多个目标，请按明细选择' if items else '没有达到分数阈值的目标'
    return result
