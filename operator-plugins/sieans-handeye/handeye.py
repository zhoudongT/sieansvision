"""Eye-in-hand calibration: B_T_G @ G_T_C @ C_T_target is constant."""
import base64
import io
import math
import cv2
import numpy as np


def number(v,label,low=-1e9,high=1e9,integer=False):
    if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or not low<=v<=high or integer and int(v)!=v:raise ValueError(label+'类型或范围无效')
    return int(v) if integer else float(v)


def name(v):
    if not isinstance(v,str) or not 1<=len(v)<=120 or v.strip()!=v or any(ord(c)<32 for c in v):raise ValueError('坐标系名称无效')
    return v


def units(v):
    if v not in ('mm','m'):raise ValueError('长度单位仅支持 mm 或 m')
    return v


def factor(source,target):return {'mm':.001,'m':1.}[units(source)]/{'mm':.001,'m':1.}[units(target)]


def transform(r,t):
    out=np.eye(4);out[:3,:3]=r;out[:3,3]=np.asarray(t).reshape(3);return out


def inverse(t):return transform(t[:3,:3].T,-t[:3,:3].T@t[:3,3])


def angle(r):return float(np.degrees(np.linalg.norm(cv2.Rodrigues(r)[0])))


def rotation(v,kind):
    if kind=='rodrigues-rad':
        values=np.array([number(x,'旋转向量 (rad)',-2*math.pi,2*math.pi) for x in v]);return cv2.Rodrigues(values)[0]
    if kind!='euler-zyx-deg':raise ValueError('不支持该机器人旋转约定')
    x,y,z=np.radians([number(a,'欧拉角 (°)',-360,360) for a in v])
    rx=np.array([[1,0,0],[0,np.cos(x),-np.sin(x)],[0,np.sin(x),np.cos(x)]])
    ry=np.array([[np.cos(y),0,np.sin(y)],[0,1,0],[-np.sin(y),0,np.cos(y)]])
    rz=np.array([[np.cos(z),-np.sin(z),0],[np.sin(z),np.cos(z),0],[0,0,1]])
    return rz@ry@rx


def proper_rotation(value):
    if not isinstance(value,list) or len(value)!=3 or any(not isinstance(row,list) or len(row)!=3 for row in value):raise ValueError('旋转矩阵必须为 3×3')
    r=np.array([[number(v,'旋转系数',-1.000001,1.000001) for v in row] for row in value])
    if not np.allclose(r.T@r,np.eye(3),atol=1e-7,rtol=0) or abs(np.linalg.det(r)-1)>1e-7:raise ValueError('旋转矩阵不是有效刚体旋转')
    return r


def vector(value):
    if not isinstance(value,list) or len(value)!=3:raise ValueError('平移必须为三维数值')
    return np.array([number(v,'平移') for v in value])


def read_poses(rows,robot_unit,camera_unit,robot_rotation,minimum):
    keys=[prefix+part for prefix in ('robot','camera') for part in ('X','Y','Z','Rx','Ry','Rz')]
    if not isinstance(rows,list) or not minimum<=len(rows)<=100:raise ValueError('采样姿态表需要 '+str(minimum)+'–100 行')
    robots=[];cameras=[]
    for row in rows:
        if not isinstance(row,dict) or set(row)!=set(keys):raise ValueError('采样姿态表必须包含机器人与相机的十二列')
        values=[number(row[k],k) for k in keys]
        if values[8]<=0:raise ValueError('标定板原点必须位于相机正 Z 前方，检查标定板到相机的方向')
        robots.append(transform(rotation(values[3:6],robot_rotation),values[:3]))
        cameras.append(transform(rotation(values[9:12],'rodrigues-rad'),np.array(values[6:9])*factor(camera_unit,robot_unit)))
    return robots,cameras


def motion_check(robots,cameras):
    # Relative axes expressed in a common reference frame must span at least
    # two directions. One-axis rotations cannot constrain the full transform.
    for poses in (robots,cameras):
        vectors=[]
        for i in range(1,len(poses)):
            rv=cv2.Rodrigues(poses[i][:3,:3]@poses[0][:3,:3].T)[0].ravel()
            if np.linalg.norm(rv)>=math.radians(5):vectors.append(rv)
        if len(vectors)<2:raise ValueError('旋转激励不足：需绕不同轴改变姿态，不能只平移')
        s=np.linalg.svd(np.asarray(vectors),compute_uv=False)
        if s[1]/s[0]<.05:raise ValueError('采样旋转轴近似平行，不能可靠求解手眼关系')
    for poses in (robots,cameras):
        signatures=np.array([pose[:3,:].ravel() for pose in poses])
        if len(np.unique(np.round(signatures,10),axis=0))!=len(poses):raise ValueError('存在重复采样姿态')


def average(transforms):
    u,_,vt=np.linalg.svd(sum(t[:3,:3] for t in transforms));d=np.eye(3);d[-1,-1]=np.linalg.det(u@vt)
    return transform(u@d@vt,np.mean([t[:3,3] for t in transforms],axis=0))


def park(robots,cameras):
    # AX=XB. Log(Ra)=Rx Log(Rb) gives an orthogonal Procrustes
    # problem; translation follows from (Ra-I)tx=Rx*tb-ta.
    pairs=[];left=[];right=[]
    for i in range(len(robots)):
        for j in range(i+1,len(robots)):
            a=inverse(robots[j])@robots[i];b=cameras[j]@inverse(cameras[i])
            va=cv2.Rodrigues(a[:3,:3])[0].ravel();vb=cv2.Rodrigues(b[:3,:3])[0].ravel()
            # Near-pi logarithms have an unstable axis sign; exclude them.
            if max(np.linalg.norm(va),np.linalg.norm(vb))>math.radians(175):continue
            left.append(va);right.append(vb);pairs.append((a,b))
    if len(pairs)<3:raise ValueError('可用相对运动不足')
    u,s,vt=np.linalg.svd(np.asarray(left).T@np.asarray(right))
    if s[0]<=1e-12 or s[1]/s[0]<1e-3:raise ValueError('旋转求解病态，请增加多轴姿态变化')
    correction=np.eye(3);correction[-1,-1]=np.linalg.det(u@vt);r=u@correction@vt
    a=np.vstack([pa[:3,:3]-np.eye(3) for pa,pb in pairs]);b=np.concatenate([r@pb[:3,3]-pa[:3,3] for pa,pb in pairs])
    t,_,rank,singular=np.linalg.lstsq(a,b,rcond=None)
    if rank<3 or singular[-1]/singular[0]<1e-3:raise ValueError('平移求解病态，请增加多轴姿态变化')
    return r,t


def errors(robots,cameras,x,reference):
    rows=[]
    for index,(g,c) in enumerate(zip(robots,cameras)):
        board=g@x@c
        rows.append(dict(index=index+1,translationError=float(np.linalg.norm(board[:3,3]-reference[:3,3])),angleErrorDegrees=angle(board[:3,:3]@reference[:3,:3].T)))
    return rows


def quality(rows,p,length_unit):
    rms=math.sqrt(sum(v['translationError']**2 for v in rows)/len(rows));maximum=max(v['translationError'] for v in rows);angular=max(v['angleErrorDegrees'] for v in rows)
    limit=number(p['maximumTranslationRms'],'最大平移 RMS (mm)',0,1e9)*factor('mm',length_unit);point_limit=number(p['maximumTranslationError'],'最大单次平移误差 (mm)',0,1e9)*factor('mm',length_unit);angle_limit=number(p['maximumAngleError'],'最大角度误差',0,180)
    return rms<=limit and maximum<=point_limit and angular<=angle_limit,rms,maximum,angular


def fit(p):
    ru,cu=units(p['robotUnit']),units(p['cameraUnit']);rr=p['robotRotation']
    frames=[name(p[k]) for k in ['cameraFrame','toolFrame','baseFrame','boardFrame']]
    if len(set(frames))!=4:raise ValueError('相机、工具、基座与标定板坐标系名称必须不同')
    robots,cameras=read_poses(p['poses'],ru,cu,rr,6);motion_check(robots,cameras)
    if p['method']!='park':raise ValueError('当前支持 Park / SVD 手眼求解')
    r,t=park(robots,cameras)
    r=proper_rotation(np.asarray(r).tolist());t=vector(np.asarray(t).reshape(3).tolist());x=transform(r,t)
    reference=average([g@x@c for g,c in zip(robots,cameras)])
    rows=errors(robots,cameras,x,reference);passed,rms,maximum,angular=quality(rows,p,ru)
    if not passed:raise ValueError('固定标定板一致性超限；检查同步、变换方向、角度约定或标定板是否移动')
    calibration=dict(model='sieans-rigid-v1',version=1,sourceFrame=frames[0],targetFrame=frames[1],sourceUnit=cu,targetUnit=ru,rotation=r.tolist(),translation=t.tolist())
    record=dict(model='sieans-handeye-reference-v1',version=1,mode='eye-in-hand',robotUnit=ru,cameraUnit=cu,robotRotation=rr,cameraFrame=frames[0],toolFrame=frames[1],baseFrame=frames[2],boardFrame=frames[3],boardRotation=reference[:3,:3].tolist(),boardTranslation=reference[:3,3].tolist())
    return dict(result=dict(calibration=calibration,reference=record,sampleCount=len(rows),rmsTranslationError=rms,maximumTranslationError=maximum,maximumAngleErrorDegrees=angular,unit=ru,items=rows,note='假定相机刚性安装在工具上、标定板固定于基座；一致性残差不是现场定位精度。'))


def validate(p):
    ref=p['reference'];model=p['calibration']
    keys={'model','version','mode','robotUnit','cameraUnit','robotRotation','cameraFrame','toolFrame','baseFrame','boardFrame','boardRotation','boardTranslation'}
    if not isinstance(ref,dict) or set(ref)!=keys or ref['model']!='sieans-handeye-reference-v1' or type(ref['version']) is not int or ref['version']!=1 or ref['mode']!='eye-in-hand':raise ValueError('需要完整的手眼标定参考记录')
    frames=[name(ref[k]) for k in ['cameraFrame','toolFrame','baseFrame','boardFrame']]
    if len(set(frames))!=4:raise ValueError('参考坐标系名称不一致')
    ru,cu=units(ref['robotUnit']),units(ref['cameraUnit'])
    model_keys={'model','version','sourceFrame','targetFrame','sourceUnit','targetUnit','rotation','translation'}
    if not isinstance(model,dict) or set(model)!=model_keys or model['model']!='sieans-rigid-v1' or type(model['version']) is not int or model['version']!=1 or (model['sourceFrame'],model['targetFrame'],model['sourceUnit'],model['targetUnit'])!=(ref['cameraFrame'],ref['toolFrame'],cu,ru):raise ValueError('手眼模型与参考的方向、坐标系或单位不一致')
    x=transform(proper_rotation(model['rotation']),vector(model['translation']))
    reference=transform(proper_rotation(ref['boardRotation']),vector(ref['boardTranslation']))
    robots,cameras=read_poses(p['poses'],ru,cu,ref['robotRotation'],3)
    rows=errors(robots,cameras,x,reference);passed,rms,maximum,angular=quality(rows,p,ru)
    return dict(result=dict(passed=passed,sampleCount=len(rows),rmsTranslationError=rms,maximumTranslationError=maximum,maximumAngleErrorDegrees=angular,unit=ru,items=rows))


def board_pose(ctx,p):
    from PIL import Image
    raw=base64.b64decode(ctx['image'].split(',',1)[-1],validate=True)
    if len(raw)>12_000_000:raise ValueError('图像超过 12 MB')
    with Image.open(io.BytesIO(raw)) as header:
        if header.width*header.height>16_000_000:raise ValueError('图像超过 1600 万像素')
    image=cv2.imdecode(np.frombuffer(raw,np.uint8),cv2.IMREAD_COLOR)
    if image is None:raise ValueError('无法解码图像')
    h,w=image.shape[:2];intr=p['intrinsics']
    keys={'model','version','width','height','fx','fy','cx','cy','k1','k2','p1','p2','k3'}
    if not isinstance(intr,dict) or set(intr)!=keys or intr['model']!='pinhole-opencv5' or type(intr['version']) is not int or intr['version']!=1:raise ValueError('需要完整的针孔相机内参标定结果')
    if intr['width']!=w or intr['height']!=h:raise ValueError('图像尺寸与内参不一致')
    fx=number(intr['fx'],'fx',1e-6,w*100);fy=number(intr['fy'],'fy',1e-6,h*100)
    k=np.array([[fx,0,number(intr['cx'],'cx',0,w-1)],[0,fy,number(intr['cy'],'cy',0,h-1)],[0,0,1]])
    d=np.array([number(intr[key],key,-100,100) for key in ['k1','k2','p1','p2','k3']])
    cols=number(p['columns'],'内角点列',3,15,True);rows=number(p['rows'],'内角点行',3,15,True);square=number(p['squareSize'],'格边长',.001,10000);units(p['unit'])
    found,corners=cv2.findChessboardCornersSB(cv2.cvtColor(image,cv2.COLOR_BGR2GRAY),(cols,rows),cv2.CALIB_CB_NORMALIZE_IMAGE)
    if not found:raise ValueError('未找到完整棋盘格')
    if type(p['reverseCorners']) is not bool:raise ValueError('反转角点开关应为布尔值')
    if p['reverseCorners']:corners=corners[::-1].copy()
    obj=np.zeros((cols*rows,3),np.float64);obj[:,:2]=np.mgrid[0:cols,0:rows].T.reshape(-1,2)*square
    solutions=cv2.solvePnPGeneric(obj,corners,k,d,flags=cv2.SOLVEPNP_IPPE)
    candidates=[]
    for rv,tv in zip(solutions[1],solutions[2]):
        r=cv2.Rodrigues(rv)[0]
        if not np.all((obj@r.T+tv.reshape(3))[:,2]>1e-6):continue
        projected=cv2.projectPoints(obj,rv,tv,k,d)[0].reshape(-1,2)
        rms=float(np.sqrt(np.mean(np.sum((projected-corners.reshape(-1,2))**2,axis=1))))
        if not math.isfinite(rms):continue
        candidates.append((rms,rv,tv,r))
    candidates.sort(key=lambda item:item[0])
    if not candidates:raise ValueError('没有位于相机前方的有效棋盘位姿')
    gap=number(p['minimumAmbiguityGap'],'最小位姿误差差距',0,10)
    if len(candidates)>1 and candidates[1][0]-candidates[0][0]<gap and angle(candidates[0][3]@candidates[1][3].T)>3:raise ValueError('平面位姿存在歧义，请增加棋盘倾斜并重新采集')
    rms,rv,tv,r=candidates[0]
    if rms>number(p['maximumReprojectionError'],'最大重投影误差',.001,100):raise ValueError('棋盘位姿重投影误差超限')
    canvas=image.copy();cv2.drawChessboardCorners(canvas,(cols,rows),corners,True);cv2.drawFrameAxes(canvas,k,d,rv,tv,square*2,2)
    encoded=cv2.imencode('.jpg',canvas,[cv2.IMWRITE_JPEG_QUALITY,80])[1]
    if encoded.size>1_000_000:raise ValueError('标注图超过插件显示上限，请降低采集分辨率')
    pose=dict(zip(['x','y','z','rx','ry','rz'],map(float,np.r_[tv.ravel(),rv.ravel()])))
    origin=corners.reshape(-1,2)[0]
    return dict(annotatedImage='data:image/jpeg;base64,'+base64.b64encode(encoded).decode(),result=dict(pose=pose,unit=p['unit'],rotationConvention='rodrigues-rad',rmsPixels=rms,cornerCount=cols*rows,originX=float(origin[0]),originY=float(origin[1]),note='标定板到相机变换；rvec 为弧度轴角，不是欧拉角。普通棋盘无唯一原点，跨姿态须核对原点及轴向。'))


def run(ctx):
    p=ctx['params']
    if p['task']=='pose':return board_pose(ctx,p)
    if p['task']=='fit':return fit(p)
    if p['task']=='check':return validate(p)
    raise ValueError('未知手眼算子')
