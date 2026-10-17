"""Local PCA surface inspection with explicit unsupported-neighborhood reporting."""
import math
import numpy as np
import open3d as o3d


def run(ctx):
    p, cloud = ctx['params'], ctx['cloud']
    points = np.asarray(cloud['points'], dtype=float)
    if points.ndim != 2 or points.shape[1] != 3 or not np.isfinite(points).all() or not 3 <= len(points) <= 20000:
        raise ValueError('法向检测需要 3–20000 个有限三维点；大点云请先下采样')
    if p['minimumNeighbors'] > p['maximumNeighbors']:
        raise ValueError('最少邻居数不能超过最多邻居数')
    if p['colorize'] and len(points) > 10000:
        raise ValueError('着色输出最多 10000 点；请关闭着色或先下采样')
    reference = np.array([p['referenceX'], p['referenceY'], p['referenceZ']], dtype=float)
    scale = float(np.max(np.abs(reference)))
    if not math.isfinite(scale) or scale == 0:
        raise ValueError('参考方向不能为零')
    reference /= scale
    reference /= math.hypot(*reference)
    # Search unique coordinates so duplicate samples cannot manufacture support.
    unique, inverse = np.unique(points, axis=0, return_inverse=True)
    pc = o3d.geometry.PointCloud(o3d.utility.Vector3dVector(unique))
    tree = o3d.geometry.KDTreeFlann(pc)
    rows = []
    for point in unique:
        count, indices, _ = tree.search_hybrid_vector_3d(point, p['radius'], p['maximumNeighbors'])
        row = dict(valid=False, neighborCount=count, reason='邻域点数不足')
        if count >= p['minimumNeighbors']:
            neighbors = unique[np.asarray(indices)]
            centered = neighbors - np.mean(neighbors, axis=0)
            covariance = centered.T @ centered / count
            eigenvalues, vectors = np.linalg.eigh(covariance)
            eigenvalues = np.maximum(eigenvalues, 0)
            if eigenvalues[0] <= 64*np.finfo(float).eps*eigenvalues[2]:
                eigenvalues[0] = 0.
            # Reject collinear or isotropic neighborhoods instead of arbitrary normals.
            if eigenvalues[2] <= 0 or eigenvalues[1] <= eigenvalues[2] * 1e-8:
                row['reason'] = '邻域共线或重合'
            elif eigenvalues[1] - eigenvalues[0] <= eigenvalues[2] * 1e-6:
                row['reason'] = '邻域无法确定唯一法向'
            else:
                normal = vectors[:, 0]
                dot = float(normal @ reference)
                if dot < -1e-12 or (abs(dot) <= 1e-12 and normal[np.argmax(np.abs(normal))] < 0):
                    normal = -normal
                slope = math.degrees(math.atan2(float(np.linalg.norm(np.cross(normal, reference))), abs(float(normal @ reference))))
                residual = float(math.sqrt(eigenvalues[0]))
                outside = slope > p['maximumSlopeDegrees'] + 1e-8 or residual > p['maximumResidual'] + 1e-12
                row = dict(valid=True, neighborCount=count, reason='', normalX=float(normal[0]),
                           normalY=float(normal[1]), normalZ=float(normal[2]), slopeDegrees=slope,
                           localResidual=residual, surfaceVariation=float(eigenvalues[0]/sum(eigenvalues)), outside=outside)
        rows.append(row)
    per_point = [rows[i] for i in inverse]
    valid = [r for r in per_point if r['valid']]
    invalid_count = len(points) - len(valid)
    outside_count = sum(r['outside'] for r in valid)
    invalid_percent = invalid_count * 100 / len(points)
    outside_percent = outside_count * 100 / len(valid) if valid else 0.
    details = []
    # Put unusable and failed samples first so truncation does not hide them.
    order = sorted(range(len(points)), key=lambda i: (per_point[i]['valid'], not per_point[i].get('outside', False), i))
    for i in order[:500]:
        row = per_point[i]
        detail = dict(pointIndex=i, valid=row['valid'])
        if row['valid']:
            detail.update(slopeDegrees=row['slopeDegrees'], localResidual=row['localResidual'], outside=row['outside'])
        else:
            detail['reason'] = row['reason']
        detail.update(neighborCount=row['neighborCount'])
        if row['valid']:
            detail.update(normalX=row['normalX'], normalY=row['normalY'], normalZ=row['normalZ'], surfaceVariation=row['surfaceVariation'])
        detail.update(x=float(points[i, 0]), y=float(points[i, 1]), z=float(points[i, 2]))
        details.append(detail)
    result = dict(pointCount=len(points), uniquePointCount=len(unique), validCount=len(valid), invalidCount=invalid_count,
                  invalidPercent=invalid_percent, outsideCount=outside_count, outsidePercent=outside_percent,
                  hasValidNormals=bool(valid), unit=cloud['unit'], referenceDirection=reference.tolist(),
                  passed=bool(valid) and invalid_percent <= p['maximumInvalidPercent'] and outside_percent <= p['maximumOutsidePercent'],
                  items=details, detailsTruncated=len(points)>500)
    # No artificial zero measurements if every neighborhood is unsupported.
    if valid:
        result.update(meanSlopeDegrees=float(np.mean([r['slopeDegrees'] for r in valid])),
                      maxSlopeDegrees=max(r['slopeDegrees'] for r in valid),
                      maxLocalResidual=max(r['localResidual'] for r in valid))
    response = dict(result=result)
    if p['colorize']:
        colors = [[.6, .6, .6] if not r['valid'] else [1., .15, .1] if r['outside'] else [.1, .75, .4] for r in per_point]
        response['cloud'] = dict(cloud, colors=colors)
    return response
