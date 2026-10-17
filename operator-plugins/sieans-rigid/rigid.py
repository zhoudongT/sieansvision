"""Known-correspondence rigid calibration. No ICP, scale estimation or reflection."""
import math
import numpy as np


def number(value, label, low, high, integer=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high or integer and int(value) != value:
        raise ValueError(label+'类型或范围无效')
    return int(value) if integer else float(value)


def frame_name(value):
    if not isinstance(value, str) or not 1 <= len(value) <= 120 or value.strip() != value or any(ord(c)<32 for c in value):
        raise ValueError('坐标系名称必须为 1–120 字符，不能有首尾空白或控制字符')
    return value


def unit(value):
    if value not in ('mm', 'm'):
        raise ValueError('坐标单位只支持 mm 或 m')
    return value


def scale(source, target):
    return {'mm':.001,'m':1.}[unit(source)] / {'mm':.001,'m':1.}[unit(target)]


def records(rows, keys, minimum=1):
    if not isinstance(rows, list) or not minimum <= len(rows) <= 500:
        raise ValueError('点位表需要 '+str(minimum)+'–500 行')
    values=[]
    for row in rows:
        if not isinstance(row, dict) or set(row) != set(keys):
            raise ValueError('点位表包含缺失或未知列')
        values.append([number(row[key],key,-1e9,1e9) for key in keys])
    return np.asarray(values,dtype=np.float64)


def spread(points):
    if len(np.unique(points,axis=0)) != len(points):
        raise ValueError('对应点不能有重复位置')
    centered=points-points.mean(axis=0)
    singular=np.linalg.svd(centered,compute_uv=False)
    if singular[0]<1e-9 or singular[1] < singular[0]*1e-5:
        raise ValueError('对应点共线、分布过窄或尺度过小，不能确定三维刚体变换')
    return centered


def fit(source,target):
    a,b=spread(source),spread(target)
    u,_,vt=np.linalg.svd(a.T@b)
    sign=np.eye(3);sign[-1,-1]=1 if np.linalg.det(vt.T@u.T)>0 else -1
    rotation=vt.T@sign@u.T
    translation=target.mean(axis=0)-rotation@source.mean(axis=0)
    return rotation,translation


def mapped(points,rotation,translation,factor=1.):
    result=(points*factor)@rotation.T+translation
    if not np.isfinite(result).all() or np.max(np.abs(result))>1e9:
        raise ValueError('转换坐标非有限或超过 10 亿，检查单位和标定结果')
    return result


def model(value,inverse=False):
    keys={'model','version','sourceFrame','targetFrame','sourceUnit','targetUnit','rotation','translation'}
    if not isinstance(value,dict) or set(value)!=keys or value.get('model')!='sieans-rigid-v1' or type(value.get('version')) is not int or value['version']!=1:
        raise ValueError('需要完整的三维刚体标定结果')
    src,dst=frame_name(value['sourceFrame']),frame_name(value['targetFrame'])
    if src==dst:raise ValueError('源和目标坐标系名称必须不同')
    source_unit,target_unit=unit(value['sourceUnit']),unit(value['targetUnit'])
    rotation=value['rotation'];translation=value['translation']
    if not isinstance(rotation,list) or len(rotation)!=3 or any(not isinstance(row,list) or len(row)!=3 for row in rotation) or not isinstance(translation,list) or len(translation)!=3:
        raise ValueError('旋转应为 3×3、平移应为三维数值')
    r=np.array([[number(v,'旋转系数',-1.000001,1.000001) for v in row] for row in rotation])
    t=np.array([number(v,'平移系数',-1e9,1e9) for v in translation])
    if not np.allclose(r.T@r,np.eye(3),atol=1e-7,rtol=0) or abs(np.linalg.det(r)-1)>1e-7:
        raise ValueError('旋转矩阵不是正交且行列式为 +1 的刚体旋转')
    factor=scale(source_unit,target_unit)
    if type(inverse) is not bool:raise ValueError('反向转换开关必须为布尔值')
    if inverse:
        r,t=r.T,-r.T@t/factor
        return r,t,1/factor,dst,src,target_unit,source_unit
    return r,t,factor,src,dst,source_unit,target_unit


def pairs(rows):
    data=records(rows,['sourceX','sourceY','sourceZ','targetX','targetY','targetZ'],3)
    return data[:,:3],data[:,3:]


def calibrate(p):
    source,target=pairs(p['pairs'])
    src,dst=frame_name(p['sourceFrame']),frame_name(p['targetFrame'])
    if src==dst:raise ValueError('源和目标坐标系名称必须不同')
    source_unit,target_unit=unit(p['sourceUnit']),unit(p['targetUnit'])
    source=source*scale(source_unit,target_unit)
    spread(source);spread(target)
    threshold=number(p['inlierThreshold'],'内点距离阈值',1e-9,1e9)
    minimum_ratio=number(p['minimumInlierRatio'],'最低内点比例',.1,1)
    maximum_rms=number(p['maximumRms'],'最大均方根误差',0,1e9)
    maximum_error=number(p['maximumError'],'最大单点误差',0,1e9)
    iterations=number(p['iterations'],'抽样次数',10,2000,True)
    seed=number(p['seed'],'随机种子',0,2147483647,True)
    if p['method']=='all':
        inliers=np.ones(len(source),dtype=bool)
    elif p['method']=='ransac':
        rng=np.random.default_rng(seed);best=None
        for _ in range(iterations):
            indices=rng.choice(len(source),3,replace=False)
            try:r,t=fit(source[indices],target[indices])
            except ValueError:continue
            errors=np.linalg.norm(source@r.T+t-target,axis=1)
            mask=errors<=threshold
            if mask.sum()<3:continue
            score=(int(mask.sum()),-float(np.sum(errors[mask]**2)))
            if best is None or score>best[0]:best=(score,mask)
        if best is None:raise ValueError('未找到有效对应点模型')
        inliers=best[1]
        for _ in range(10):
            if inliers.sum()<3:raise ValueError('标定内点不足')
            r,t=fit(source[inliers],target[inliers]);errors=np.linalg.norm(source@r.T+t-target,axis=1)
            revised=errors<=threshold
            if np.array_equal(revised,inliers):break
            inliers=revised
        else:raise ValueError('内点集合不稳定，请检查对应点或距离阈值')
    else:raise ValueError('未知拟合方式')
    if inliers.sum()<3 or inliers.mean()<minimum_ratio:raise ValueError('标定内点数量或比例不足')
    r,t=fit(source[inliers],target[inliers]);errors=np.linalg.norm(source@r.T+t-target,axis=1)
    rms=float(np.sqrt(np.mean(errors[inliers]**2)));maximum=float(np.max(errors[inliers]))
    if rms>maximum_rms or maximum>maximum_error:raise ValueError('标定残差超限，请检查对应关系、单位或非刚性变化')
    calibration=dict(model='sieans-rigid-v1',version=1,sourceFrame=src,targetFrame=dst,sourceUnit=source_unit,targetUnit=target_unit,rotation=r.tolist(),translation=t.tolist())
    model(calibration)
    return dict(result=dict(calibration=calibration,inlierCount=int(inliers.sum()),rejectedCount=int((~inliers).sum()),rmsError=rms,maximumError=maximum,unit=target_unit,
        items=[dict(index=i+1,error=float(errors[i]),inlier=bool(inliers[i])) for i in range(len(source))],
        note='误差仅衡量拟合内点；需用独立点验证。仅旋转和平移，不估计比例、反射或手眼关系。'))


def convert_points(p):
    r,t,factor,src,dst,su,tu=model(p['calibration'],p['inverse'])
    points=records(p['points'],['x','y','z'])
    converted=mapped(points,r,t,factor)
    return dict(result=dict(sourceFrame=src,targetFrame=dst,sourceUnit=su,targetUnit=tu,pointCount=len(points),
        items=[dict(index=i+1,sourceX=float(v[0]),sourceY=float(v[1]),sourceZ=float(v[2]),targetX=float(converted[i,0]),targetY=float(converted[i,1]),targetZ=float(converted[i,2])) for i,v in enumerate(points)]))


def check(p):
    r,t,factor,src,dst,su,tu=model(p['calibration'],p['inverse'])
    source,target=pairs(p['pairs']);converted=mapped(source,r,t,factor)
    errors=np.linalg.norm(converted-target,axis=1)
    maximum_rms=number(p['maximumRms'],'最大均方根误差',0,1e9);maximum_error=number(p['maximumError'],'最大单点误差',0,1e9)
    rms=float(np.sqrt(np.mean(errors**2)));maximum=float(np.max(errors))
    return dict(result=dict(passed=rms<=maximum_rms and maximum<=maximum_error,rmsError=rms,maximumError=maximum,unit=tu,pointCount=len(source),
        items=[dict(index=i+1,error=float(errors[i]),passed=bool(errors[i]<=maximum_error),targetX=float(converted[i,0]),targetY=float(converted[i,1]),targetZ=float(converted[i,2])) for i in range(len(source))]))


def convert_cloud(ctx,p):
    r,t,factor,src,dst,su,tu=model(p['calibration'],p['inverse']);cloud=ctx.get('cloud')
    if not isinstance(cloud,dict) or cloud.get('unit')!=su or cloud.get('frame')!=src:raise ValueError('输入点云单位或坐标系与标定方向不一致')
    raw=cloud.get('points')
    if not isinstance(raw,list) or not 1<=len(raw)<=200000 or any(not isinstance(row,list) or len(row)!=3 for row in raw):raise ValueError('点云需要 1–200000 个三维点')
    points=np.array([[number(v,'点云坐标',-1e9,1e9) for v in row] for row in raw])
    converted=mapped(points,r,t,factor)
    # Intrinsics, camera extrinsics and raw-depth pixel mappings no longer apply
    # in the destination frame. Carry only explicitly supported metadata.
    output=dict(points=converted.tolist(),unit=tu,frame=dst)
    if 'timestamp' in cloud:output['timestamp']=cloud['timestamp']
    if 'colors' in cloud:
        colors=cloud['colors']
        if not isinstance(colors,list) or len(colors)!=len(raw) or any(not isinstance(row,list) or len(row)!=3 for row in colors):raise ValueError('点云颜色数量或形状不一致')
        output['colors']=[[number(v,'颜色',0,1) for v in row] for row in colors]
    if 'normals' in cloud:
        normals=cloud['normals']
        if not isinstance(normals,list) or len(normals)!=len(raw) or any(not isinstance(row,list) or len(row)!=3 for row in normals):raise ValueError('法向数量或形状不一致')
        normals=np.array([[number(v,'法向',-1e9,1e9) for v in row] for row in normals])
        output['normals']=(normals@r.T).tolist()
    return dict(cloud=output,image='',depth=None,result=dict(sourceFrame=src,targetFrame=dst,sourceUnit=su,targetUnit=tu,pointCount=len(points),
        minimum=converted.min(axis=0).tolist(),maximum=converted.max(axis=0).tolist(),note='点云已转换坐标系，旧图像/深度及投影内外参已清除。颜色保留，法向仅旋转。'))


def run(ctx):
    p=ctx['params'];task=p['task']
    if task=='calibrate':return calibrate(p)
    if task=='points':return convert_points(p)
    if task=='check':return check(p)
    if task=='cloud':return convert_cloud(ctx,p)
    raise ValueError('未知三维坐标操作')
