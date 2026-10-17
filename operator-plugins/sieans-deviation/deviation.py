"""Unsigned sampled-cloud deviation, with explicit reverse coverage checks."""
import numpy as np
import open3d as o3d


def run(ctx):
    p, cloud = ctx['params'], ctx['cloud']
    points = np.asarray(cloud['points'], dtype=float)
    reference = np.asarray([[row[k] for k in ('x', 'y', 'z')] for row in p['referencePoints']], dtype=float)
    for name, values, limit in [('输入点云', points, 20000), ('参考点云', reference, 1000)]:
        if values.ndim != 2 or values.shape[1] != 3 or not 1 <= len(values) <= limit or not np.isfinite(values).all():
            raise ValueError(name+'为空、含无效坐标或超过点数上限')
    if cloud['unit'] != p['referenceUnit']:
        raise ValueError('参考点云与输入点云单位不一致；请先转换单位')
    if p['colorize'] and len(points) > 10000:
        raise ValueError('着色输出最多 10000 点；请关闭着色或先下采样')
    def make(values):
        result = o3d.geometry.PointCloud()
        result.points = o3d.utility.Vector3dVector(values)
        return result
    source, target = make(points), make(reference)
    forward = np.asarray(source.compute_point_cloud_distance(target))
    reverse = np.asarray(target.compute_point_cloud_distance(source)) if p['bidirectional'] else np.empty(0)
    distances = np.concatenate((forward, reverse))
    if not np.isfinite(distances).all():
        raise ValueError('点云距离计算溢出；请检查坐标范围')
    # Absolute tolerance follows coordinates, so normal floating point roundoff is not a defect.
    eps = 32*np.finfo(float).eps*max(1., float(np.max(np.abs(points))), float(np.max(np.abs(reference))))
    bad_forward, bad_reverse = forward > p['maximumDistance']+eps, reverse > p['maximumDistance']+eps
    count = int(np.count_nonzero(bad_forward)+np.count_nonzero(bad_reverse))
    percent = count*100/len(distances)
    maximum = float(np.max(distances))
    items = []
    for label, values, offsets, mask in [('输入→参考', points, forward, bad_forward), ('参考→输入', reference, reverse, bad_reverse)]:
        for index in np.flatnonzero(mask):
            if len(items) >= 500:
                break
            items.append(dict(direction=label, pointIndex=int(index), x=float(values[index, 0]), y=float(values[index, 1]), z=float(values[index, 2]), distance=float(offsets[index])))
    result = dict(pointCount=len(points), referenceCount=len(reference), evaluatedCount=len(distances),
                  outsideCount=count, outsidePercent=percent, forwardOutsideCount=int(np.count_nonzero(bad_forward)),
                  reverseOutsideCount=int(np.count_nonzero(bad_reverse)), maximumDistance=maximum,
                  meanDistance=float(np.sum(distances/len(distances))), rmsDistance=maximum*float(np.sqrt(np.mean((distances/maximum)**2))) if maximum else 0.,
                  unit=cloud['unit'], passed=percent <= p['maximumOutsidePercent'], items=items, detailsTruncated=count > 500)
    response = dict(result=result)
    if p['colorize']:
        response['cloud'] = dict(cloud, colors=np.where(bad_forward[:, None], [[1., .15, .1]], [[.1, .75, .4]]).tolist())
    return response
