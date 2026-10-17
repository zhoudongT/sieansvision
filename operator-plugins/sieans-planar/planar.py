"""Planar homography calibration and metric measurements, using OpenCV.

Calibration is specific to the plane, camera pose and image pixel coordinates.
It does not compensate lens distortion or infer out-of-plane dimensions.
"""
import base64
import math
import cv2
import numpy as np


def records(rows, keys, minimum, maximum, label):
    if not isinstance(rows,list) or not minimum<=len(rows)<=maximum:
        raise ValueError(f'{label}需要 {minimum}–{maximum} 个点')
    data=[]
    for row in rows:
        if not isinstance(row,dict) or set(row)!=set(keys):
            raise ValueError(label+'的点位列不完整或包含未知列')
        point=[row[k] for k in keys]
        if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or abs(v)>1e7 for v in point):
            raise ValueError(label+'坐标必须为绝对值不超过 1000 万的有限数值')
        data.append(point)
    return np.asarray(data,dtype=np.float64)


def spread(points,label):
    centered=points-points.mean(axis=0)
    singular=np.linalg.svd(centered,compute_uv=False)
    if singular[0]<1e-8 or singular[-1]/singular[0]<1e-5:
        raise ValueError(label+'共线或分布过窄，不能确定平面透视变换')
    if len(np.unique(points,axis=0))!=len(points):
        raise ValueError(label+'存在重复点，请检查对应关系')


def matrix(value):
    try: h=np.asarray(value,dtype=np.float64)
    except (TypeError,ValueError): raise ValueError('标定矩阵格式无效') from None
    if h.shape!=(3,3) or not np.isfinite(h).all() or np.max(np.abs(h))==0:
        raise ValueError('标定矩阵必须为有限的 3×3 矩阵')
    h=h/np.max(np.abs(h))
    if np.linalg.cond(h)>1e12: raise ValueError('标定矩阵奇异或数值不稳定')
    return h


def project(points,h):
    homogeneous=np.column_stack([points,np.ones(len(points))])@h.T
    divisor=homogeneous[:,2]
    scale=np.linalg.norm(h[2])*np.linalg.norm(np.column_stack([points,np.ones(len(points))]),axis=1)
    if np.any(np.abs(divisor)<=1e-12*np.maximum(scale,1e-12)):
        raise ValueError('测量点靠近透视无穷线，无法可靠换算')
    mapped=homogeneous[:,:2]/divisor[:,None]
    if not np.isfinite(mapped).all(): raise ValueError('坐标换算结果无效')
    return mapped,divisor


def image_from(ctx):
    if not ctx.get('image'): return None
    image=cv2.imdecode(np.frombuffer(base64.b64decode(ctx['image'].split(',',1)[-1]),np.uint8),cv2.IMREAD_COLOR)
    if image is None: raise ValueError('无法解码输入图像')
    return image


def image_bounds(points,image):
    if image is not None and np.any((points<0)|(points>=np.array([image.shape[1],image.shape[0]]))):
        raise ValueError('点位超出输入图像，请使用原始图像坐标')


def hull_of(points):
    return cv2.convexHull(points.astype(np.float32)).reshape(-1,2).astype(np.float64)


def annotate(image,points,labels,accepted=None,closed=False,connect=False):
    if image is None: return {}
    output=image.copy()
    if connect: cv2.polylines(output,[np.rint(points).astype(np.int32)],closed,(230,170,0),2,cv2.LINE_AA)
    for i,(point,label) in enumerate(zip(points,labels)):
        position=tuple(np.rint(point).astype(int))
        color=(60,190,50) if accepted is None or accepted[i] else (40,40,230)
        cv2.circle(output,position,5,color,2,cv2.LINE_AA)
        cv2.putText(output,str(label),(position[0]+8,position[1]-8),cv2.FONT_HERSHEY_SIMPLEX,.48,color,1,cv2.LINE_AA)
    ok,data=cv2.imencode('.png',output)
    if not ok: raise ValueError('无法生成标记图像')
    return dict(image='data:image/png;base64,'+base64.b64encode(data).decode())


def calibrate(ctx,p,image):
    values=records(p['points'],['pixelX','pixelY','worldX','worldY'],4,500,'标定')
    pixels,world=values[:,:2],values[:,2:]
    image_bounds(pixels,image)
    spread(pixels,'图像标定点');spread(world,'实际标定点')
    method=p['method']
    if method not in ('all','ransac'): raise ValueError('标定方法无效')
    unit=p['unit']
    if unit not in ('mm','cm','m'): raise ValueError('标定单位无效')
    # Destination coordinates are pixels, so RANSAC's threshold is in pixels.
    forward,mask=cv2.findHomography(world,pixels,0 if method=='all' else cv2.RANSAC,
                                   p['inlierThreshold'],maxIters=5000,confidence=.999)
    if forward is None or mask is None: raise ValueError('未找到有效的平面透视变换')
    forward=matrix(forward)
    predicted,_=project(world,forward)
    errors=np.linalg.norm(predicted-pixels,axis=1)
    inliers=np.ones(len(values),dtype=bool) if method=='all' else mask.ravel().astype(bool)&(errors<=p['inlierThreshold'])
    if inliers.sum()<4 or inliers.mean()<p['minimumInlierRatio']:
        raise ValueError('有效标定点不足，请检查图像点与实际点的对应关系')
    spread(pixels[inliers],'有效图像标定点');spread(world[inliers],'有效实际标定点')
    rms=float(np.sqrt(np.mean(errors[inliers]**2)))
    if rms>p['maximumRmsError']: raise ValueError(f'标定拟合误差 {rms:.4f} px 超出设定上限')
    inverse=matrix(np.linalg.inv(forward))
    hull=hull_of(pixels[inliers])
    _,denominator=project(hull,inverse)
    if np.min(denominator)*np.max(denominator)<=0: raise ValueError('标定有效区域跨越透视无穷线')
    calibration=dict(model='sieans-plane-homography-v1',matrix=inverse.tolist(),unit=unit,pixelHull=hull.tolist(),
                     imageWidth=int(image.shape[1]) if image is not None else 0,imageHeight=int(image.shape[0]) if image is not None else 0,
                     rmsErrorPixels=rms,inlierCount=int(inliers.sum()))
    result=dict(calibration=calibration,unit=unit,pointCount=len(values),inlierCount=int(inliers.sum()),
                rejectedCount=int((~inliers).sum()),rmsErrorPixels=rms,maximumErrorPixels=float(np.max(errors[inliers])),
                accepted=True,items=[dict(index=i+1,pixelX=float(pixels[i,0]),pixelY=float(pixels[i,1]),worldX=float(world[i,0]),worldY=float(world[i,1]),errorPixels=float(errors[i]),inlier=bool(inliers[i])) for i in range(len(values))])
    return dict(result=result,**annotate(image,pixels,range(1,len(pixels)+1),inliers))


def measure(ctx,p,image):
    calibration=p['calibration']
    if not isinstance(calibration,dict) or calibration.get('model')!='sieans-plane-homography-v1' or calibration.get('unit') not in ('mm','cm','m'):
        raise ValueError('请选择平面透视标定算子的完整标定结果')
    h=matrix(calibration.get('matrix'))
    hull=np.asarray(calibration.get('pixelHull'),dtype=np.float64)
    if hull.ndim!=2 or hull.shape[1]!=2 or not 3<=len(hull)<=500 or not np.isfinite(hull).all():
        raise ValueError('标定有效区域无效')
    spread(hull,'标定有效区域')
    hull=hull_of(hull)
    points=records(p['points'],['x','y'],2,500,'测量')
    image_bounds(points,image)
    if image is not None:
        width,height=calibration.get('imageWidth'),calibration.get('imageHeight')
        if (width or height) and (width!=image.shape[1] or height!=image.shape[0]):
            raise ValueError('图像尺寸与标定不一致，请重新标定，不能直接缩放或裁剪后沿用')
    inside=np.array([cv2.pointPolygonTest(hull.astype(np.float32),tuple(point),False)>=0 for point in points])
    if not p['allowExtrapolation'] and not inside.all(): raise ValueError('测量点超出标定有效区域；如需外推，请显式允许并验证精度')
    converted,denominator=project(points,h)
    if np.min(denominator)*np.max(denominator)<=0: raise ValueError('测量线段跨越透视无穷线')
    closed=p['closed']
    if closed and len(points)<3: raise ValueError('闭合测量需要至少 3 个点')
    segments=[]
    for i in range(len(points) if closed else len(points)-1):
        end=(i+1)%len(points)
        vector=converted[end]-converted[i]
        segments.append(dict(index=i+1,startPoint=i+1,endPoint=end+1,startX=float(converted[i,0]),startY=float(converted[i,1]),
                             endX=float(converted[end,0]),endY=float(converted[end,1]),segmentLength=float(np.linalg.norm(vector)),
                             angleDegrees=float(np.degrees(np.arctan2(vector[1],vector[0])))))
    result=dict(unit=calibration['unit'],pointCount=len(points),segmentCount=len(segments),length=sum(s['segmentLength'] for s in segments),
                extrapolated=bool(not inside.all()),items=segments,
                points=[dict(index=i+1,pixelX=float(points[i,0]),pixelY=float(points[i,1]),worldX=float(converted[i,0]),worldY=float(converted[i,1]),insideCalibration=bool(inside[i])) for i in range(len(points))])
    return dict(result=result,**annotate(image,points,range(1,len(points)+1),connect=True,closed=closed))


def run(ctx):
    p=ctx['params'];image=image_from(ctx)
    if p['task']=='calibrate': return calibrate(ctx,p,image)
    if p['task']=='measure': return measure(ctx,p,image)
    raise ValueError('未知平面测量操作')
