"""Radial image calipers, robust geometric circle fitting and nested-circle checks.

Image coordinates: +X right, +Y down; positive angles are clockwise.
Radial residuals and ideal-circle wall gaps are not certified roundness/GD&T.
"""
import base64
import hashlib
import math
import cv2
import numpy as np


def number(p,key,low,high,integer=False):
    v=p[key]
    if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or not low<=v<=high or integer and int(v)!=v:raise ValueError('参数类型或范围无效：'+key)
    return int(v) if integer else float(v)


def peaks(profile,positions,sigma,threshold):
    step=float(positions[1]-positions[0]);support=math.ceil(3*sigma/step)
    smooth=cv2.GaussianBlur(profile.reshape(1,-1),(2*support+1,1),sigma/step,borderType=cv2.BORDER_REPLICATE)[0]
    gradient=np.gradient(smooth,step);strength=np.abs(gradient);result=[]
    for i in range(support+2,len(profile)-support-2):
        if strength[i]<threshold or not (strength[i]>=strength[i-1] and strength[i]>strength[i+1]):continue
        denominator=strength[i-1]-2*strength[i]+strength[i+1]
        offset=0 if abs(denominator)<1e-12 else float(np.clip(.5*(strength[i-1]-strength[i+1])/denominator,-.5,.5))
        result.append(dict(radius=float(positions[i]+offset*step),gradient=float(gradient[i]),sign=1 if gradient[i]>0 else -1))
    return result


def algebraic(points):
    origin=points.mean(axis=0);scale=float(np.max(np.linalg.norm(points-origin,axis=1)))
    if scale<1:return None
    q=(points-origin)/scale;matrix=np.column_stack((2*q,np.ones(len(q))))
    solution,_,rank,singular=np.linalg.lstsq(matrix,np.sum(q*q,axis=1),rcond=None)
    radius_squared=float(solution[2]+solution[:2]@solution[:2])
    if rank<3 or singular[-1]<1e-6*singular[0] or radius_squared<=0:return None
    return np.r_[origin+solution[:2]*scale,math.sqrt(radius_squared)*scale]


def geometric(points,model):
    model=model.copy()
    for _ in range(30):
        delta=points-model[:2];distance=np.linalg.norm(delta,axis=1)
        if np.any(distance<1e-9):return None
        jacobian=np.column_stack((-delta/distance[:,None],-np.ones(len(points))))
        update,_,rank,singular=np.linalg.lstsq(jacobian,-(distance-model[2]),rcond=None)
        if rank<3 or singular[-1]<1e-4*singular[0]:return None
        model+=update
        if not np.all(np.isfinite(model)) or model[2]<=0:return None
        if np.linalg.norm(update)<1e-7:return model
    return None


def residuals(points,model):return np.linalg.norm(points-model[:2],axis=1)-model[2]


def fit_circle(points,threshold,low_radius,high_radius):
    """Deterministic RANSAC followed by monotone rejection and geometric refit."""
    if len(points)<6:return None
    rng=np.random.default_rng(2107);best=None;best_score=(-1,-math.inf)
    seeds=[points]+[points[rng.choice(len(points),3,replace=False)] for _ in range(256)]
    for seed in seeds:
        model=algebraic(seed)
        if model is None or not low_radius<=model[2]<=high_radius:continue
        errors=residuals(points,model);mask=np.abs(errors)<=threshold
        score=(int(mask.sum()),-float(np.sum(np.minimum(errors**2,threshold**2))))
        if score>best_score:best=model;best_score=score
    if best is None:return None
    mask=np.abs(residuals(points,best))<=threshold
    for _ in range(len(points)+1):
        if mask.sum()<6:return None
        best=geometric(points[mask],best)
        if best is None or not low_radius<=best[2]<=high_radius:return None
        errors=residuals(points,best);new_mask=mask&(np.abs(errors)<=threshold)
        if np.array_equal(mask,new_mask):return best,mask,errors
        mask=new_mask
    return None


def coverage(points,center):
    angles=np.sort(np.mod(np.arctan2(points[:,1]-center[1],points[:,0]-center[0]),2*math.pi))
    gaps=np.diff(np.r_[angles,angles[0]+2*math.pi])
    return float(math.degrees(2*math.pi-np.max(gaps)))


def circle_model(model):
    if not isinstance(model,dict) or model.get('format')!='sieans-circle-v1':raise ValueError('需要圆形卡尺输出的圆模型')
    for key in ['centerX','centerY']:number(model,key,0,32766)
    number(model,'radiusPixels',1,32766)
    for key in ['width','height']:number(model,key,1,32766,True)
    number(model,'unitsPerPixel',1e-6,10000)
    if model.get('unit') not in ('px','mm','cm','m') or model['unit']=='px' and model['unitsPerPixel']!=1:raise ValueError('圆模型单位或比例无效')
    if model['centerX']>=model['width'] or model['centerY']>=model['height']:raise ValueError('圆模型中心超出图像')
    digest=model.get('imageSha256')
    if not isinstance(digest,str) or len(digest)!=64 or any(c not in '0123456789abcdef' for c in digest):raise ValueError('圆模型缺少有效的原始图像摘要')
    return model


def display(image,passed):
    cv2.putText(image,'PASS' if passed else 'FAIL',(15,30),cv2.FONT_HERSHEY_SIMPLEX,.8,(60,200,60) if passed else (40,40,230),2,cv2.LINE_AA)
    encoded=cv2.imencode('.jpg',image,[cv2.IMWRITE_JPEG_QUALITY,85])[1]
    if len(encoded)>700000:raise ValueError('标记图过大，请缩小输入图像')
    return 'data:image/jpeg;base64,'+base64.b64encode(encoded).decode()


def nested(p,image_data=None):
    inner=circle_model(p['innerCircle']);outer=circle_model(p['outerCircle'])
    if any(inner[key]!=outer[key] for key in ['width','height','unit','unitsPerPixel','imageSha256']):raise ValueError('两个圆必须来自同一原始图像，并使用相同尺寸、单位和比例')
    if inner['radiusPixels']>=outer['radiusPixels']:raise ValueError('外圆半径必须大于内圆')
    maximum=number(p,'maximumCenterDistance',0,1e9);low=number(p,'minimumWall',0,1e9);high=number(p,'maximumWall',0,1e9)
    if low>high:raise ValueError('壁厚公差上下限颠倒')
    delta=np.array([inner['centerX']-outer['centerX'],inner['centerY']-outer['centerY']]);distance=float(np.linalg.norm(delta));scale=inner['unitsPerPixel'];gap=outer['radiusPixels']-inner['radiusPixels']
    contained=distance<gap
    result=dict(found=True,passed=False,nested=contained,unit=inner['unit'],unitsPerPixel=scale,centerDistancePixels=distance,centerDistance=distance*scale,offsetX=delta[0]*scale,offsetY=delta[1]*scale,items=[dict(role='内圆',centerX=inner['centerX'],centerY=inner['centerY'],radiusPixels=inner['radiusPixels']),dict(role='外圆',centerX=outer['centerX'],centerY=outer['centerY'],radiusPixels=outer['radiusPixels'])])
    if contained:
        result.update(minimumWall=(gap-distance)*scale,maximumWall=(gap+distance)*scale,nominalWall=gap*scale)
        result['passed']=bool(result['centerDistance']<=maximum and low<=result['minimumWall'] and result['maximumWall']<=high)
    result['diagnostic']='双圆检测通过' if result['passed'] else '内圆未完全位于外圆内' if not contained else '中心偏移或理想圆壁厚超差'
    output=dict(result=result)
    if image_data:
        raw=base64.b64decode(image_data.split(',',1)[-1],validate=True)
        if hashlib.sha256(raw).hexdigest()!=inner['imageSha256']:raise ValueError('双圆模型与当前输入图像不一致')
        image=cv2.imdecode(np.frombuffer(raw,np.uint8),cv2.IMREAD_COLOR)
        if image is None or image.shape[:2]!=(inner['height'],inner['width']):raise ValueError('双圆图像尺寸或编码无效')
        for circle,color in [(inner,(0,230,255)),(outer,(255,180,0))]:
            center=(round(circle['centerX']),round(circle['centerY']));cv2.circle(image,center,round(circle['radiusPixels']),color,2,cv2.LINE_AA);cv2.drawMarker(image,center,color,cv2.MARKER_CROSS,15,1,cv2.LINE_AA)
        cv2.line(image,(round(inner['centerX']),round(inner['centerY'])),(round(outer['centerX']),round(outer['centerY'])),(0,0,255),2,cv2.LINE_AA)
        output['annotatedImage']=display(image,result['passed'])
    return output


def run(ctx):
    p=ctx['params']
    if p['task']=='nested':return nested(p,ctx.get('image'))
    if p['task']!='caliper':raise ValueError('未知圆测量功能')
    center=np.array([number(p,'centerX',0,32766),number(p,'centerY',0,32766)])
    radius=number(p,'expectedRadius',8,16000);length=number(p,'searchLength',16,2048);width=number(p,'caliperWidth',1,51,True);count=number(p,'probeCount',12,360,True)
    start=number(p,'startAngle',-360,360);span=number(p,'arcSpan',60,360);minimum_coverage=number(p,'minimumCoverage',60,350)
    sigma=number(p,'sigma',.2,5);threshold=number(p,'minimumGradient',.1,255);ratio=number(p,'minimumValidRatio',.1,1)
    maximum_residual=number(p,'maximumResidual',.01,100);maximum_rms=number(p,'maximumRms',.001,100)
    scale=number(p,'unitsPerPixel',1e-6,10000);low=number(p,'minimumDiameter',0,1e9);high=number(p,'maximumDiameter',0,1e9)
    if p['polarity'] not in ('rising','falling','either') or p['selection'] not in ('strongest','inner','outer'):raise ValueError('边缘极性或选择方式无效')
    if p['unit'] not in ('px','mm','cm','m') or p['unit']=='px' and scale!=1:raise ValueError('单位或比例无效；像素单位比例必须为 1')
    if low>high or minimum_coverage>span:raise ValueError('直径范围或最小角度覆盖范围无效')
    if radius-length/2<1 or length<=2*(math.ceil(3*sigma)+3):raise ValueError('搜索环带过宽、过短或内半径小于 1 px')
    samples=math.ceil(length)+1
    if samples*width*count>2_000_000:raise ValueError('卡尺采样量超过 200 万')
    raw=base64.b64decode(ctx['image'].split(',',1)[-1],validate=True);image=cv2.imdecode(np.frombuffer(raw,np.uint8),cv2.IMREAD_COLOR)
    if image is None:raise ValueError('无法解码圆形卡尺图像')
    height,image_width=image.shape[:2]
    if max(height,image_width)>=32767:raise ValueError('图像单边必须小于 32767 像素')
    if center[0]>=image_width or center[1]>=height:raise ValueError('搜索中心超出图像')
    gray=cv2.cvtColor(image,cv2.COLOR_BGR2GRAY).astype(np.float32);radii=np.linspace(radius-length/2,radius+length/2,samples);offsets=np.arange(width)-(width-1)/2;rows=[]
    angles=np.linspace(start,start+span,count,endpoint=span!=360)
    for index,angle in enumerate(angles):
        radians=math.radians(angle);direction=np.array([math.cos(radians),math.sin(radians)]);tangent=np.array([-direction[1],direction[0]])
        xy=center+radii[None,:,None]*direction+offsets[:,None,None]*tangent
        row=dict(probe=index+1,angleDeg=float(angle),valid=False,inlier=False,reason='未找到满足极性的边缘');rows.append(row)
        inside=bool(np.all(xy[...,0]>=0) and np.all(xy[...,0]<=image_width-1) and np.all(xy[...,1]>=0) and np.all(xy[...,1]<=height-1))
        ends=np.round(center+np.array([radii[0],radii[-1]])[:,None]*direction).astype(int)
        cv2.line(image,tuple(ends[0]),tuple(ends[1]),(160,110,30) if inside else (40,40,220),1,cv2.LINE_AA)
        if not inside:row['reason']='采样区域超出图像';continue
        profile=cv2.remap(gray,xy[...,0].astype(np.float32),xy[...,1].astype(np.float32),cv2.INTER_LINEAR).mean(axis=0)
        candidates=[e for e in peaks(profile,radii,sigma,threshold) if p['polarity']=='either' or e['sign']==(1 if p['polarity']=='rising' else -1)]
        if not candidates:continue
        edge=candidates[0] if p['selection']=='inner' else candidates[-1] if p['selection']=='outer' else max(candidates,key=lambda e:abs(e['gradient']))
        point=center+edge['radius']*direction
        row.update(valid=True,reason='',edgeX=float(point[0]),edgeY=float(point[1]),gradient=edge['gradient'])
    valid=[r for r in rows if r['valid']];points=np.array([[r['edgeX'],r['edgeY']] for r in valid],dtype=float)
    fitted=fit_circle(points,maximum_residual,radii[0],radii[-1])
    result=dict(found=False,passed=False,probeCount=count,detectedCount=len(valid),missingCount=count-len(valid),inlierCount=0,validRatio=0.,unit=p['unit'],unitsPerPixel=scale,items=rows,diagnostic='有效边缘不足或无法稳定拟合圆')
    if fitted:
        model,mask,errors=fitted;angular=coverage(points[mask],model[:2]);result['coverageDeg']=angular
        if angular<minimum_coverage or not (0<=model[0]<image_width and 0<=model[1]<height):
            result['diagnostic']='有效角度覆盖不足或拟合圆心超出图像';fitted=None
        else:
            rms=float(np.sqrt(np.mean(errors[mask]**2)));diameter=float(model[2]*2*scale);inliers=int(mask.sum())
            circle=dict(format='sieans-circle-v1',width=image_width,height=height,imageSha256=hashlib.sha256(raw).hexdigest(),centerX=float(model[0]),centerY=float(model[1]),radiusPixels=float(model[2]),unit=p['unit'],unitsPerPixel=scale)
            result.update(found=True,passed=bool(inliers/count>=ratio and rms<=maximum_rms and low<=diameter<=high),circle=circle,centerX=circle['centerX'],centerY=circle['centerY'],radiusPixels=circle['radiusPixels'],diameterPixels=circle['radiusPixels']*2,diameter=diameter,rmsPixels=rms,maximumDeviationPixels=float(np.max(np.abs(errors[mask]))),radialRangePixels=float(np.ptp(errors[mask])),inlierCount=inliers,validRatio=inliers/count,rejectedCount=len(valid)-inliers)
            result['diagnostic']='圆测量通过' if result['passed'] else '有效比例、拟合误差或直径公差不满足要求'
            for row,keep,error in zip(valid,mask,errors):row.update(inlier=bool(keep),radialResidualPixels=float(error),reason='' if keep else '径向残差超限，未用于拟合')
            cv2.circle(image,(round(model[0]),round(model[1])),round(model[2]),(0,240,240),2,cv2.LINE_AA)
            cv2.drawMarker(image,(round(model[0]),round(model[1])),(0,240,240),cv2.MARKER_CROSS,15,1,cv2.LINE_AA)
    if not fitted:
        for row in valid:row['reason']=result['diagnostic']
    for row in valid:cv2.circle(image,(round(row['edgeX']),round(row['edgeY'])),2,(60,210,60) if row['inlier'] else (40,40,230),-1,cv2.LINE_AA)
    return dict(result=result,annotatedImage=display(image,result['passed']))
