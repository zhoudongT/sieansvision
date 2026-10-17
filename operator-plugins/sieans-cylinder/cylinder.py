"""Free-axis cylinder fitting and signed radial inspection (infinite lateral surface)."""
import math
import numpy as np
try:
    from scipy.optimize import least_squares
except ImportError as exc:
    raise RuntimeError('圆柱算子缺少 SciPy，请安装 vision/requirements-3d.txt') from exc


def number(p, key, low, high, integer=False):
    v = p[key]
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or not low <= v <= high or (integer and int(v) != v):
        raise ValueError('参数类型或范围无效：' + key)
    return int(v) if integer else float(v)


def vector(v, name):
    if not isinstance(v, list) or len(v) != 3 or any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) or abs(x)>1e9 for x in v):
        raise ValueError(name + '必须是三个有限数值')
    return np.asarray(v, dtype=float)


def read_cloud(cloud):
    if not isinstance(cloud, dict) or cloud.get('unit') not in ('mm', 'm'):
        raise ValueError('点云必须声明 mm 或 m 单位')
    rows = cloud.get('points')
    if not isinstance(rows, list) or not 1 <= len(rows) <= 200000:
        raise ValueError('点云需要 1–200000 个点')
    if any(not isinstance(row, list) or len(row)!=3 or any(isinstance(v, bool) or not isinstance(v,(int,float)) for v in row) for row in rows):
        raise ValueError('点云坐标必须是三维数值')
    points = np.asarray(rows, dtype=float)
    if not np.isfinite(points).all() or np.max(np.abs(points))>1e9:
        raise ValueError('点云含非有限或过大坐标')
    if not isinstance(cloud.get('frame',''), str) or len(cloud.get('frame',''))>120:
        raise ValueError('点云坐标系名称无效')
    return points


def basis(direction):
    direction = direction/np.linalg.norm(direction)
    ref = np.eye(3)[np.argmin(np.abs(direction))]
    u = np.cross(direction, ref);u /= np.linalg.norm(u)
    return direction, u, np.cross(direction, u)


def unpack(parameters, axes):
    # Five identifiable parameters: two axis tilts, two perpendicular offsets, radius.
    # Rotate the starting basis with the axis; no redundant translation along the axis.
    d0,u0,v0 = axes
    direction = d0 + parameters[0]*u0 + parameters[1]*v0
    direction /= np.linalg.norm(direction)
    k = np.cross(d0,direction);c = float(np.dot(d0,direction))
    rotate = lambda w: w+np.cross(k,w)+np.cross(k,np.cross(k,w))/(1+c)
    u,v = rotate(u0),rotate(v0)
    return parameters[2]*u+parameters[3]*v, direction, parameters[4]


def distances(points, anchor, direction, radius):
    delta = points-anchor
    axial = delta@direction
    radial = delta-axial[:,None]*direction
    return np.linalg.norm(radial,axis=1)-radius, axial, radial


def residual(parameters, points, axes):
    return distances(points,*unpack(parameters,axes))[0]


def circle_initial(points, axes, lower, upper):
    xy = np.column_stack((points@axes[1],points@axes[2]))
    a = np.column_stack((2*xy,np.ones(len(xy))))
    values,_,rank,_ = np.linalg.lstsq(a,np.sum(xy*xy,axis=1),rcond=None)
    if rank<3:return None
    radius2 = float(np.dot(values[:2],values[:2])+values[2])
    if not math.isfinite(radius2) or radius2<=0:return None
    # An initialization outside the radius range may converge to a valid bounded fit.
    radius = np.clip(math.sqrt(radius2),lower+(upper-lower)*1e-8,upper-(upper-lower)*1e-8)
    return np.r_[0.,0.,values[:2],radius]


def coverage(points, anchor, direction, radius):
    _,axial,radial = distances(points,anchor,direction,radius)
    _,u,v = basis(direction)
    angles = np.sort(np.mod(np.arctan2(radial@v,radial@u),2*np.pi))
    gaps = np.diff(np.r_[angles,angles[0]+2*np.pi])
    return float(np.rad2deg(2*np.pi-gaps.max())), float(np.ptp(axial))


def fit_cylinder(points, p):
    threshold=number(p,'inlierThreshold',1e-9,1e9)
    lower_radius=number(p,'minimumRadius',1e-9,1e9)
    upper_radius=number(p,'maximumRadius',1e-9,1e9)
    maximum_points=number(p,'maximumFitPoints',12,10000,True)
    seed=number(p,'seed',0,2147483647,True)
    maximum_condition=number(p,'maximumCondition',2,1e6)
    minimum_coverage=number(p,'minimumAngularCoverage',10,350)
    minimum_span=number(p,'minimumAxialSpanRatio',.01,100)
    minimum_ratio=number(p,'minimumInlierRatio',.01,1)
    maximum_rms=number(p,'maximumRms',0,1e9)
    minimum_diameter=number(p,'minimumDiameter',0,2e9)
    maximum_diameter=number(p,'maximumDiameter',0,2e9)
    if p['method'] not in ('robust','all') or lower_radius>=upper_radius or minimum_diameter>maximum_diameter:
        raise ValueError('拟合方式、搜索半径或直径公差无效')
    unique=np.unique(points,axis=0)
    result=dict(found=False,passed=False,pointCount=len(points),uniquePointCount=len(unique),
                sampleCount=min(maximum_points,len(unique)),items=[],detailsTruncated=False)
    fail=lambda message:(dict(result,diagnostic=message),None)
    if len(unique)<12:return fail('至少需要 12 个独立坐标点')
    origin=np.median(unique,axis=0)
    scale=float(np.median(np.linalg.norm(unique-origin,axis=1)))
    if scale<=1e-12:return fail('点云尺度过小，不能稳定拟合')
    rng=np.random.default_rng(seed)
    indices=np.sort(rng.choice(len(unique),maximum_points,replace=False)) if len(unique)>maximum_points else np.arange(len(unique))
    sample=(unique[indices]-origin)/scale
    _,spread,directions=np.linalg.svd(sample-sample.mean(axis=0),full_matrices=False)
    if spread[-1]<=spread[0]*1e-8:return fail('点云共面、共线或重合，不能确定圆柱轴线')
    low,high=lower_radius/scale,upper_radius/scale
    limit=threshold/scale
    epsilon=64*np.finfo(float).eps*max(1.,float(np.max(np.abs(points))),scale)/scale
    bounds=([-2.,-2.,-np.inf,-np.inf,low],[2.,2.,np.inf,np.inf,high])
    best=None;best_score=(-1,float('-inf'))
    # All three PCA axes are seeds, not a fixed-axis assumption. Each can tilt in 2D.
    for direction in directions:
        axes=basis(direction)
        initial=circle_initial(sample,axes,low,high)
        if initial is None:continue
        solved=least_squares(residual,initial,args=(sample,axes),bounds=bounds,method='trf',
            loss='soft_l1' if p['method']=='robust' else 'linear',f_scale=max(limit,1e-9),
            ftol=1e-9,xtol=1e-9,gtol=1e-9,max_nfev=180)
        if not solved.success or not np.isfinite(solved.x).all():continue
        mask=np.abs(residual(solved.x,sample,axes))<=limit+epsilon if p['method']=='robust' else np.ones(len(sample),bool)
        converged=False
        for _ in range(8):
            if int(mask.sum())<12:break
            solved=least_squares(residual,solved.x,args=(sample[mask],axes),bounds=bounds,
                ftol=1e-10,xtol=1e-10,gtol=1e-10,max_nfev=120)
            if not solved.success or not np.isfinite(solved.x).all():break
            errors=residual(solved.x,sample,axes)
            new_mask=np.abs(errors)<=limit+epsilon if p['method']=='robust' else mask
            if np.array_equal(mask,new_mask):converged=True;break
            mask=new_mask
        if not converged:continue
        inliers=np.abs(errors)<=limit+epsilon
        n=int(inliers.sum())
        if n<12:continue
        quality=(n,-float(np.mean(errors[inliers]**2)))
        if quality>best_score:best=(solved,axes,mask);best_score=quality
    if best is None:return fail('未找到稳定圆柱；请裁剪目标、调整半径或内点阈值')
    solved,axes,mask=best
    anchor,direction,radius=unpack(solved.x,axes)
    singular=np.linalg.svd(solved.jac,compute_uv=False)
    if singular[-1]<=singular[0]*1e-12:return fail('圆柱拟合退化，请增加周向与轴向覆盖')
    condition=float(singular[0]/singular[-1]);result['conditionNumber']=condition
    if condition>maximum_condition:return fail('圆柱拟合病态，请增加周向与轴向覆盖')
    if np.any(np.abs(solved.x[:2])>1.99999):return fail('轴线优化达到方向搜索边界，请裁剪目标后重试')
    anchor=anchor*scale+origin;radius=float(radius*scale)
    # Axis sign is arbitrary; orient its largest-magnitude component positively.
    if direction[np.argmax(np.abs(direction))]<0:direction=-direction
    unique_errors,_,_=distances(unique,anchor,direction,radius)
    unique_mask=np.abs(unique_errors)<=threshold+epsilon*scale
    count=int(unique_mask.sum())
    if count<12:return fail('全点云验证的有效圆柱点不足')
    angular,span=coverage(unique[unique_mask],anchor,direction,radius)
    result.update(angularCoverageDeg=angular,sampledAxialSpan=span,axialSpanRatio=span/radius)
    if angular+1e-7<minimum_coverage or span/radius+1e-9<minimum_span:
        return fail('圆柱周向或轴向覆盖不足，不能输出可靠轴线与直径')
    # Report the point on the fitted axis nearest the centroid of unique inliers.
    anchor=anchor+np.dot(unique[unique_mask].mean(axis=0)-anchor,direction)*direction
    if np.max(np.abs(anchor))>1e9:return fail('圆柱轴点超出支持坐标范围')
    errors,axial,_=distances(points,anchor,direction,radius)
    outside=np.abs(errors)>threshold+epsilon*scale
    rms=float(np.sqrt(np.mean(unique_errors[unique_mask]**2)));ratio=count/len(unique);diameter=2*radius
    passed=ratio>=minimum_ratio and rms<=maximum_rms+epsilon*scale and minimum_diameter-epsilon*scale<=diameter<=maximum_diameter+epsilon*scale
    result.update(found=True,passed=bool(passed),axisPoint=anchor.tolist(),axisDirection=direction.tolist(),radius=radius,
                  diameter=diameter,uniqueInlierCount=count,inlierRatio=ratio,outsideCount=int(outside.sum()),rmsDistance=rms,
                  diagnostic='圆柱测量通过' if passed else '内点比例、拟合误差或直径公差不满足要求')
    return result,(anchor,direction,radius,errors,axial,outside)


def inspect_cylinder(points,cloud,p):
    model=p['cylinder']
    if not isinstance(model,dict) or model.get('model')!='sieans-cylinder-v1':
        raise ValueError('基准圆柱模型无效，请绑定拟合结果或填写模型字段表')
    if model.get('unit')!=cloud['unit'] or model.get('frame','')!=cloud.get('frame',''):
        raise ValueError('基准圆柱与输入点云的单位或坐标系不一致')
    anchor=vector(model.get('axisPoint'),'轴点');direction=vector(model.get('axisDirection'),'轴向')
    norm=float(np.linalg.norm(direction))
    if abs(norm-1)>1e-6:raise ValueError('基准圆柱轴向必须是单位向量')
    direction/=norm
    radius=number(model,'radius',1e-9,1e9)
    lower=number(p,'lowerDistance',-1e9,1e9);upper=number(p,'upperDistance',-1e9,1e9)
    maximum_outside=number(p,'maximumOutsidePercent',0,100)
    if lower>upper:raise ValueError('圆柱偏差下限不能大于上限')
    errors,axial,_=distances(points,anchor,direction,radius)
    epsilon=64*np.finfo(float).eps*max(1.,float(np.max(np.abs(points))),float(np.max(np.abs(anchor))),radius)
    outside=(errors<lower-epsilon)|(errors>upper+epsilon)
    count=int(outside.sum());percent=count*100/len(points)
    return dict(found=True,passed=bool(percent<=maximum_outside),pointCount=len(points),axisPoint=anchor.tolist(),
                axisDirection=direction.tolist(),radius=radius,diameter=radius*2,outsideCount=count,outsidePercent=percent,
                minimumDistance=float(errors.min()),maximumDistance=float(errors.max()),peakToValley=float(np.ptp(errors)),
                rmsDistance=float(np.sqrt(np.mean(errors**2))),sampledAxialSpan=float(np.ptp(axial)),
                diagnostic='圆柱侧面偏差通过' if percent<=maximum_outside else '圆柱侧面超差点比例超过限制'),(anchor,direction,radius,errors,axial,outside)


def run(ctx):
    p,cloud=ctx['params'],ctx['cloud'];points=read_cloud(cloud)
    if type(p['colorize']) is not bool or p['detailMode'] not in ('all','outside'):raise ValueError('显示参数无效')
    if p['colorize'] and len(points)>10000:raise ValueError('着色最多输出 10000 点，请关闭着色或先下采样')
    if p['task']=='fit':result,measurement=fit_cylinder(points,p)
    elif p['task']=='inspect':result,measurement=inspect_cylinder(points,cloud,p)
    else:raise ValueError('未知圆柱功能')
    result['unit']=cloud['unit'];response=dict(result=result)
    if measurement is not None:
        anchor,direction,radius,errors,axial,outside=measurement
        result['cylinder']=dict(model='sieans-cylinder-v1',axisPoint=anchor.tolist(),axisDirection=direction.tolist(),radius=radius,unit=cloud['unit'],frame=cloud.get('frame',''))
        indices=np.arange(len(points)) if p['detailMode']=='all' else np.flatnonzero(outside)
        result['items']=[dict(pointIndex=int(i),x=float(points[i,0]),y=float(points[i,1]),z=float(points[i,2]),axialPosition=float(axial[i]),distance=float(errors[i]),outside=bool(outside[i])) for i in indices[:500]]
        result['detailsTruncated']=len(indices)>500
        colors=np.where(outside[:,None],[[1.,.15,.1]],[[.1,.75,.4]])
    else:colors=np.tile([.6,.6,.6],(len(points),1))
    if p['colorize']:response['cloud']=dict(cloud,colors=colors.tolist())
    return response
