"""Signed distances to a defined or least-squares plane, not minimum-zone flatness."""
import math
import numpy as np


def run(ctx):
    p, cloud = ctx['params'], ctx['cloud']
    points = np.asarray(cloud['points'], dtype=float)
    if len(points) == 0:
        raise ValueError('点云为空')
    if p['lowerDistance'] > p['upperDistance']:
        raise ValueError('偏差下限不能大于上限')
    if p['colorize'] and len(points) > 10000:
        raise ValueError('着色输出最多 10000 点；请关闭着色以检测全部点，或先下采样')
    if p['planeMode'] == 'fit':
        if len(points) < 3:
            raise ValueError('拟合平面至少需要 3 个不共线点')
        center = np.mean(points, axis=0)
        _, singular, vectors = np.linalg.svd(points-center, full_matrices=False)
        if singular[1] <= max(singular[0]*1e-10, 1e-12):
            raise ValueError('点云共线或重合，不能确定拟合平面')
        normal = vectors[-1]
        # Deterministic sign: the largest normal component is positive.
        if normal[int(np.argmax(np.abs(normal)))] < 0:
            normal = -normal
        offset = -float(normal @ center)
    else:
        normal = np.array([p['normalX'], p['normalY'], p['normalZ']], dtype=float)
        length = math.hypot(*normal)
        if length < 1e-12:
            raise ValueError('基准平面法向量不能为零')
        normal /= length
        offset = p['planeOffset']/length
    distances = points @ normal + offset
    # Only roundoff-sized tolerance; physical tolerances remain user-controlled.
    epsilon = 32*np.finfo(float).eps*max(1, float(np.max(np.abs(points))), abs(offset))
    outside = (distances < p['lowerDistance']-epsilon) | (distances > p['upperDistance']+epsilon)
    indices = np.flatnonzero(outside)
    ratio = len(indices)*100/len(points)
    items = [dict(pointIndex=int(i), x=float(points[i, 0]), y=float(points[i, 1]), z=float(points[i, 2]), distance=float(distances[i])) for i in indices[:500]]
    result = dict(pointCount=len(points), outsideCount=len(indices), outsidePercent=ratio,
                  minimumDistance=float(np.min(distances)), maximumDistance=float(np.max(distances)),
                  peakToValley=float(np.ptp(distances)), rmsDistance=float(np.sqrt(np.mean(distances**2))),
                  plane=[*normal.tolist(), offset], unit=cloud['unit'], items=items,
                  detailsTruncated=len(indices)>500, passed=ratio <= p['maximumOutsidePercent'])
    response = dict(result=result)
    if p['colorize']:
        response['cloud'] = dict(cloud, colors=np.where(outside[:, None], [[1., .15, .1]], [[.1, .75, .4]]).tolist())
    return response
