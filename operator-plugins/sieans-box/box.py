"""Convex-hull optimized oriented enclosure; never solid volume or robot pose."""
import math
import numpy as np


def number(p, key, low, high):
    v = p[key]
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or not low <= v <= high:
        raise ValueError('参数类型或范围无效：'+key)
    return float(v)


def run(ctx):
    try:
        import open3d as o3d
    except ImportError:
        raise ValueError('旋转包围盒需要 Open3D，请安装 vision/requirements-3d.txt') from None
    cloud = ctx.get('cloud')
    if not isinstance(cloud, dict) or cloud.get('unit') not in ('mm', 'm'):
        raise ValueError('点云必须声明 mm 或 m 单位')
    raw = cloud.get('points')
    if not isinstance(raw, list) or not 4 <= len(raw) <= 20000:
        raise ValueError('旋转包围盒需要 4–20000 个输入点；请显式裁剪或下采样')
    if any(not isinstance(row, list) or len(row) != 3 or any(isinstance(v, bool) or not isinstance(v, (int, float)) for v in row) for row in raw):
        raise ValueError('点云坐标必须为三维数值')
    points = np.asarray(raw, dtype=np.float64)
    if not np.isfinite(points).all() or np.abs(points).max() > 1e9:
        raise ValueError('点云包含无效或超限坐标')
    frame = cloud.get('frame', 'sensor')
    if not isinstance(frame, str) or len(frame) > 120:
        raise ValueError('点云坐标系无效')
    p = ctx['params']
    minimum_thickness = number(p, 'minimumThickness', 1e-9, 1e6)
    limits = [(number(p, 'minimum'+key, 0, 1e9), number(p, 'maximum'+key, 0, 1e9)) for key in ('Long', 'Middle', 'Short')]
    if any(low > high for low, high in limits):
        raise ValueError('尺寸公差下限不能大于上限')
    unique = np.unique(points, axis=0)
    if len(unique) < 4:
        raise ValueError('独立点不足，不能形成三维包围盒')
    origin = unique.mean(axis=0)
    scale = float(np.max(np.linalg.norm(unique-origin, axis=1)))
    if scale <= 0:
        raise ValueError('点云退化')
    normalized = (unique-origin)/scale
    singular = np.linalg.svd(normalized, compute_uv=False)
    if singular[-1] <= singular[0]*1e-8:
        raise ValueError('点云共面、共线或厚度病态，不能形成可靠三维包围盒')
    pc = o3d.geometry.PointCloud(o3d.utility.Vector3dVector(normalized))
    try:
        hull, _ = pc.compute_convex_hull(joggle_inputs=False)
    except RuntimeError:
        raise ValueError('三维凸包计算失败，请检查重复、共面或退化数据') from None
    if len(hull.triangles) > 2048:
        raise ValueError('凸包超过 2048 个三角面，请显式滤波或下采样，不返回截断尺寸')
    try:
        box = hull.get_minimal_oriented_bounding_box(robust=False)
    except RuntimeError:
        raise ValueError('旋转包围盒求解失败，不使用随机扰动补造厚度') from None
    rotation = np.asarray(box.R).copy()
    if not np.isfinite(rotation).all() or not np.allclose(rotation.T@rotation, np.eye(3), atol=1e-7) or abs(abs(np.linalg.det(rotation))-1) > 1e-7:
        raise ValueError('包围盒方向矩阵无效')
    # Open3D can return axes with small float precision drift. Restore an orthonormal
    # frame before using its transpose as an inverse; extrema are then recomputed.
    u, _, vt = np.linalg.svd(rotation)
    rotation = u@vt
    # Recompute extrema against every accepted point, never only a sampled subset.
    projected = (points-origin)@rotation
    extents = np.ptp(projected, axis=0)
    order = np.argsort(-extents, kind='stable')
    rotation = rotation[:, order]
    for axis in (0, 1):
        if rotation[np.argmax(np.abs(rotation[:, axis])), axis] < 0: rotation[:, axis] *= -1
    rotation[:, 2] = np.cross(rotation[:, 0], rotation[:, 1])
    projected = (points-origin)@rotation
    low, high = projected.min(axis=0), projected.max(axis=0)
    extents = high-low
    if extents[-1] < minimum_thickness:
        raise ValueError('测得厚度小于最小可靠厚度，不形成三维测量')
    center = origin+rotation@((low+high)/2)
    corners = []
    for i in range(8):
        point = origin+rotation@np.array([high[k] if i&(1 << k) else low[k] for k in range(3)])
        corners.append(dict(index=i+1, cornerX=float(point[0]), cornerY=float(point[1]), cornerZ=float(point[2]), unit=cloud['unit']))
    rows = [dict(dimension=label, measured=float(extents[i]), minimum=limits[i][0], maximum=limits[i][1], unit=cloud['unit'], passed=bool(limits[i][0] <= extents[i] <= limits[i][1])) for i, label in enumerate(('长边', '中边', '短边'))]
    aabb = np.ptp(points, axis=0)
    result = dict(found=True, passed=all(row['passed'] for row in rows), items=rows,
                  length=float(extents[0]), width=float(extents[1]), thickness=float(extents[2]),
                  boxCenterX=float(center[0]), boxCenterY=float(center[1]), boxCenterZ=float(center[2]),
                  boundingBoxVolume=float(np.prod(extents)), axisAlignedVolume=float(np.prod(aabb)),
                  axisAlignedDimensions=[dict(axis=axis, measured=float(aabb[i])) for i, axis in enumerate(('X', 'Y', 'Z'))],
                  axes=[dict(axis=label, directionX=float(rotation[0,i]), directionY=float(rotation[1,i]), directionZ=float(rotation[2,i])) for i, label in enumerate(('长边轴', '中边轴', '短边轴'))],
                  corners=corners, pointCount=len(points), uniquePointCount=len(unique), hullTriangles=len(hull.triangles),
                  nearEqualDimensions=bool(np.min(np.abs(np.diff(extents))) <= max(extents)*.001),
                  unit=cloud['unit'], frame=frame, method='convex-hull-optimized',
                  diagnostic='尺寸公差通过' if all(row['passed'] for row in rows) else '旋转包围盒尺寸超差')
    # Omit cloud: the platform preserves the original frame, colors and all metadata.
    return dict(result=result)
