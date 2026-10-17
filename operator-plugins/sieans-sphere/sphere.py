"""Sphere fitting and signed radial inspection; not minimum-zone sphericity."""
import math
import numpy as np
try:
    from scipy.optimize import least_squares
except ImportError as exc:
    raise RuntimeError('球面算子缺少 SciPy，请安装 vision/requirements-3d.txt') from exc


def number(p, key, low, high, integer=False):
    value = p[key]
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high or (integer and int(value) != value):
        raise ValueError('参数类型或范围无效：' + key)
    return int(value) if integer else float(value)


def read_cloud(cloud):
    if not isinstance(cloud, dict) or cloud.get('unit') not in ('mm', 'm'):
        raise ValueError('点云必须声明 mm 或 m 单位')
    raw = cloud.get('points')
    if not isinstance(raw, list) or not 1 <= len(raw) <= 200000:
        raise ValueError('点云需要 1–200000 个点')
    if any(not isinstance(row, list) or len(row) != 3 or any(isinstance(v, bool) or not isinstance(v, (int,float)) for v in row) for row in raw):
        raise ValueError('点云坐标必须是三维数值')
    points = np.asarray(raw, dtype=float)
    if not np.isfinite(points).all() or np.max(np.abs(points)) > 1e9:
        raise ValueError('点云含非有限或过大坐标')
    if not isinstance(cloud.get('frame', ''), str) or len(cloud.get('frame', '')) > 120:
        raise ValueError('点云坐标系名称无效')
    return points


def algebraic(points):
    # Solve in normalized coordinates. Rank 4 is necessary to determine a sphere.
    matrix = np.column_stack((2*points, np.ones(len(points))))
    values, _, rank, singular = np.linalg.lstsq(matrix, np.sum(points*points, axis=1), rcond=None)
    if rank < 4 or singular[-1] <= singular[0]*1e-8:
        return None
    radius2 = float(np.dot(values[:3], values[:3]) + values[3])
    if radius2 <= 0 or not math.isfinite(radius2):
        return None
    return np.r_[values[:3], math.sqrt(radius2)]


def residual(model, points):
    return np.linalg.norm(points-model[:3], axis=1)-model[3]


def jacobian(model, points):
    delta = model[:3]-points
    lengths = np.linalg.norm(delta, axis=1)
    return np.column_stack((delta/np.maximum(lengths[:,None], 1e-15), -np.ones(len(points))))


def fit_sphere(points, p):
    iterations = number(p,'iterations',10,2000,True)
    seed = number(p,'seed',0,2147483647,True)
    maximum_points = number(p,'maximumFitPoints',8,10000,True)
    threshold = number(p,'inlierThreshold',1e-9,1e9)
    minimum_radius = number(p,'minimumRadius',1e-9,1e9)
    maximum_radius = number(p,'maximumRadius',1e-9,1e9)
    maximum_condition = number(p,'maximumCondition',2,1e6)
    minimum_ratio = number(p,'minimumInlierRatio',.01,1)
    maximum_rms = number(p,'maximumRms',0,1e9)
    minimum_diameter = number(p,'minimumDiameter',0,2e9)
    maximum_diameter = number(p,'maximumDiameter',0,2e9)
    if p['method'] not in ('ransac','all') or minimum_radius >= maximum_radius or minimum_diameter > maximum_diameter:
        raise ValueError('拟合方式、半径范围或直径公差无效')
    unique = np.unique(points, axis=0)
    result = dict(found=False, passed=False, pointCount=len(points), uniquePointCount=len(unique),
                  sampleCount=min(maximum_points,len(unique)), items=[], detailsTruncated=False)
    fail = lambda message: (dict(result, diagnostic=message), None)
    if len(unique) < 8:
        return fail('至少需要 8 个独立坐标点')
    origin = np.median(unique,axis=0)
    scale = float(np.median(np.linalg.norm(unique-origin,axis=1)))
    if scale <= 1e-12:
        return fail('点云尺度过小，不能稳定拟合')
    rng = np.random.default_rng(seed)
    indices = np.sort(rng.choice(len(unique),maximum_points,replace=False)) if len(unique)>maximum_points else np.arange(len(unique))
    sample = (unique[indices]-origin)/scale
    spread = np.linalg.svd(sample-sample.mean(axis=0), compute_uv=False)
    if spread[-1] <= spread[0]*1e-8:
        return fail('点云共面、共线或重合，不能确定球面')
    lower, upper = minimum_radius/scale, maximum_radius/scale
    limit = threshold/scale
    epsilon = 64*np.finfo(float).eps*max(1., float(np.max(np.abs(points))), scale)/scale
    best, best_mask, score = None, None, (-1,float('-inf'))
    def candidate(model):
        nonlocal best, best_mask, score
        if model is None or not np.isfinite(model).all() or not lower <= model[3] <= upper:
            return
        errors = np.abs(residual(model,sample))
        mask = errors <= limit+epsilon
        n = int(mask.sum())
        if n < 8:
            return
        quality = (n, -float(np.mean(errors[mask]**2)))
        if quality > score:
            best, best_mask, score = model, mask, quality
    initial = algebraic(sample)
    if p['method'] == 'ransac':
        candidate(initial)
        for _ in range(iterations):
            candidate(algebraic(sample[rng.choice(len(sample),4,replace=False)]))
        if best is None:
            return fail('在搜索半径与内点阈值内未找到足够球面点')
    else:
        if initial is None or not lower <= initial[3] <= upper:
            return fail('最小二乘初始球面无效或超出搜索半径')
        best, best_mask = initial, np.ones(len(sample),bool)
    # Bounded consensus refinement on the declared fit sample; evaluate all points later.
    converged = False
    for _ in range(8):
        chosen = sample[best_mask]
        if len(chosen) < 8:
            return fail('优化后有效球面点不足')
        optimized = least_squares(residual,best,jac=jacobian,args=(chosen,),method='trf',
            bounds=([-np.inf,-np.inf,-np.inf,lower],[np.inf,np.inf,np.inf,upper]),
            ftol=1e-10,xtol=1e-10,gtol=1e-10,max_nfev=150)
        if not optimized.success or not np.isfinite(optimized.x).all():
            return fail('球面优化未收敛')
        best = optimized.x
        next_mask = np.abs(residual(best,sample)) <= limit+epsilon if p['method']=='ransac' else best_mask
        if np.array_equal(next_mask,best_mask):
            converged = True
            break
        best_mask = next_mask
    if not converged:
        return fail('球面内点集合未稳定，请调整阈值或采样范围')
    singular = np.linalg.svd(jacobian(best,sample[best_mask]),compute_uv=False)
    if singular[-1] <= 0:
        return fail('球面拟合退化')
    condition = float(singular[0]/singular[-1])
    if not math.isfinite(condition):
        return fail('球面拟合条件数非有限，请扩大采样范围')
    result['conditionNumber'] = condition
    if condition > maximum_condition:
        return fail('球面覆盖过窄或拟合病态，请扩大采样范围')
    center, radius = best[:3]*scale+origin, float(best[3]*scale)
    if np.max(np.abs(center)) > 1e9:
        return fail('拟合球心超出支持坐标范围')
    unique_errors = np.linalg.norm(unique-center,axis=1)-radius
    unique_mask = np.abs(unique_errors) <= threshold+epsilon*scale
    count = int(unique_mask.sum())
    if count < 8:
        return fail('全点云验证的有效球面点不足')
    errors = np.linalg.norm(points-center,axis=1)-radius
    mask = np.abs(errors) <= threshold+epsilon*scale
    rms = float(np.sqrt(np.mean(unique_errors[unique_mask]**2)))
    ratio = count/len(unique)
    diameter = 2*radius
    result.update(found=True,uniqueInlierCount=count,inlierRatio=ratio,outsideCount=int((~mask).sum()),
                  center=center.tolist(),radius=radius,diameter=diameter,rmsDistance=rms,
                  passed=bool(ratio>=minimum_ratio and rms<=maximum_rms+epsilon*scale and minimum_diameter-epsilon*scale <= diameter <= maximum_diameter+epsilon*scale))
    result['diagnostic'] = '球面测量通过' if result['passed'] else '内点比例、拟合误差或直径公差不满足要求'
    return result, (center,radius,errors,~mask)


def inspect_sphere(points, cloud, p):
    sphere = p['sphere']
    if not isinstance(sphere,dict) or sphere.get('model') != 'sieans-sphere-v1':
        raise ValueError('基准球面模型无效，请绑定球面拟合结果或填写球面字段表')
    if sphere.get('unit') != cloud['unit'] or sphere.get('frame','') != cloud.get('frame',''):
        raise ValueError('基准球面与输入点云的单位或坐标系不一致')
    values = sphere.get('center')
    if not isinstance(values,list) or len(values)!=3 or any(isinstance(v,bool) or not isinstance(v,(float,int)) or not math.isfinite(v) or abs(v)>1e9 for v in values):
        raise ValueError('基准球心必须是三个有限坐标')
    center = np.asarray(values,dtype=float)
    radius = number(sphere,'radius',1e-9,1e9)
    lower = number(p,'lowerDistance',-1e9,1e9)
    upper = number(p,'upperDistance',-1e9,1e9)
    maximum_outside = number(p,'maximumOutsidePercent',0,100)
    if lower > upper:
        raise ValueError('球面偏差下限不能大于上限')
    errors = np.linalg.norm(points-center,axis=1)-radius
    epsilon = 64*np.finfo(float).eps*max(1.,float(np.max(np.abs(points))),float(np.max(np.abs(center))),radius)
    outside = (errors < lower-epsilon) | (errors > upper+epsilon)
    count = int(outside.sum())
    ratio = count*100/len(points)
    return dict(found=True,pointCount=len(points),center=center.tolist(),radius=radius,diameter=radius*2,
                minimumDistance=float(errors.min()),maximumDistance=float(errors.max()),peakToValley=float(np.ptp(errors)),
                rmsDistance=float(np.sqrt(np.mean(errors**2))),outsideCount=count,outsidePercent=ratio,
                passed=bool(ratio<=maximum_outside),diagnostic='球面偏差通过' if ratio<=maximum_outside else '球面超差点比例超过限制'), (center,radius,errors,outside)


def run(ctx):
    p, cloud = ctx['params'], ctx['cloud']
    points = read_cloud(cloud)
    if type(p['colorize']) is not bool or p['detailMode'] not in ('all','outside'):
        raise ValueError('显示参数无效')
    if p['colorize'] and len(points)>10000:
        raise ValueError('着色最多输出 10000 点，请关闭着色或先下采样')
    if p['task'] == 'fit':
        result, measurement = fit_sphere(points,p)
    elif p['task'] == 'inspect':
        result, measurement = inspect_sphere(points,cloud,p)
    else:
        raise ValueError('未知球面功能')
    result['unit'] = cloud['unit']
    response = dict(result=result)
    if measurement is not None:
        center,radius,errors,outside = measurement
        result['sphere'] = dict(model='sieans-sphere-v1',center=center.tolist(),radius=radius,unit=cloud['unit'],frame=cloud.get('frame',''))
        indices = np.arange(len(points)) if p['detailMode']=='all' else np.flatnonzero(outside)
        result['items'] = [dict(pointIndex=int(i),x=float(points[i,0]),y=float(points[i,1]),z=float(points[i,2]),distance=float(errors[i]),outside=bool(outside[i])) for i in indices[:500]]
        result['detailsTruncated'] = len(indices)>500
        colors = np.where(outside[:,None],[[1.,.15,.1]],[[.1,.75,.4]])
    else:
        colors = np.tile([.6,.6,.6],(len(points),1))
    if p['colorize']:
        response['cloud'] = dict(cloud,colors=colors.tolist())
    return response
