"""Bounded point-cloud operators. Coordinates and thresholds use the declared unit."""
import base64
import copy
import json
import math
import re
from pathlib import Path
import tempfile
import time

import numpy as np

MAX_POINTS = 200_000
OPERATIONS = {'cloud_filter', 'cloud_plane', 'cloud_cluster', 'cloud_measure', 'cloud_height', 'cloud_register'}


def number(params, key, default, low, high):
    value = params.get(key, default)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f'{key} 必须在 {low} 到 {high} 之间')
    return float(value)


def vector(value, size, name):
    if not isinstance(value, list) or len(value) != size:
        raise ValueError(f'{name} 必须包含 {size} 个数值')
    if any(isinstance(x, bool) or not isinstance(x, (int, float)) for x in value):
        raise ValueError(f'{name} 必须为数值')
    array = np.asarray(value, dtype=float)
    if not np.isfinite(array).all():
        raise ValueError(f'{name} 包含非有限数值')
    return array


def validate(cloud):
    if not isinstance(cloud, dict) or cloud.get('unit') not in ('mm', 'm'):
        raise ValueError('点云必须声明单位 mm 或 m')
    points = cloud.get('points')
    if not isinstance(points, list) or not 1 <= len(points) <= MAX_POINTS:
        raise ValueError(f'点云必须包含 1 到 {MAX_POINTS} 个点')
    try:
        array = np.asarray(points)
        if array.dtype.kind not in 'fi' or array.shape != (len(points), 3):
            raise ValueError()
        array = array.astype(float)
    except (TypeError, ValueError):
        raise ValueError('点云 points 必须为 N×3 数值数组') from None
    if not np.isfinite(array).all() or np.abs(array).max() > 1e9:
        raise ValueError('点云包含无效坐标或坐标超过 1e9')
    if 'colors' in cloud:
        colors = np.asarray(cloud['colors'])
        if colors.shape != array.shape or colors.dtype.kind not in 'fi' or not np.isfinite(colors).all() or np.any((colors < 0) | (colors > 1)):
            raise ValueError('colors 必须与 points 等长，每项 RGB 在 0 到 1 之间')
    if not isinstance(cloud.get('frame', 'sensor'), str) or len(cloud.get('frame', 'sensor')) > 120:
        raise ValueError('点云坐标系名称无效')
    return array


def make_cloud(points, original, colors=None):
    if len(points) == 0:
        raise ValueError('处理后点云为空，请调整筛选参数')
    if len(points) > MAX_POINTS:
        raise ValueError('点云超过 20 万点，请先缩小数据文件')
    value = {key: copy.deepcopy(original[key]) for key in ('unit', 'frame', 'timestamp', 'intrinsics', 'extrinsics') if key in original}
    value.setdefault('frame', 'sensor')
    value['points'] = np.asarray(points).tolist()
    if colors is not None and len(colors) == len(points):
        value['colors'] = np.asarray(colors).tolist()
    validate(value)
    return value


def depth_cloud(data):
    """Pinhole projection. depthScale = raw depth values per declared length unit."""
    depth = np.asarray(data.get('depth'))
    if depth.ndim != 2 or not depth.size or depth.size > MAX_POINTS or depth.dtype.kind not in 'fi':
        raise ValueError('depth 必须为数值二维数组，最多 20 万像素')
    if not np.isfinite(depth).all() or np.any(depth < 0):
        raise ValueError('depth 包含非有限或负深度；无效深度使用 0')
    intrinsics = data.get('intrinsics', {})
    if not isinstance(intrinsics, dict):
        raise ValueError('缺少深度相机内参')
    fx = number(intrinsics, 'fx', 0, 1e-9, 1e9)
    fy = number(intrinsics, 'fy', 0, 1e-9, 1e9)
    cx = number(intrinsics, 'cx', 0, -1e6, 1e6)
    cy = number(intrinsics, 'cy', 0, -1e6, 1e6)
    scale = number(data, 'depthScale', 1, 1e-9, 1e9)
    v, u = np.nonzero(depth > 0)
    z = depth[v, u] / scale
    points = np.column_stack(((u-cx)*z/fx, (v-cy)*z/fy, z))
    return make_cloud(points, data)


def import_cloud(request):
    name = request.get('name', '')
    suffix = Path(name).suffix.lower()
    if suffix not in ('.ply', '.pcd', '.xyz', '.xyzn', '.xyzrgb', '.pts', '.json'):
        raise ValueError('支持 PLY / PCD / XYZ / XYZN / XYZRGB / PTS / JSON')
    content = request.get('content', '')
    if not isinstance(content, str) or len(content) > 17_000_000:
        raise ValueError('点云文件超过 12 MB')
    try:
        raw = base64.b64decode(content.split(',')[-1], validate=True)
    except Exception:
        raise ValueError('点云文件编码无效') from None
    if not raw or len(raw) > 12_000_000:
        raise ValueError('点云文件为空或超过 12 MB')
    if suffix == '.json':
        data = json.loads(raw.decode('utf-8-sig'))
        if isinstance(data, list):
            data = {'points': data}
        if not isinstance(data, dict):
            raise ValueError('点云 JSON 必须是对象或 XYZ 数组')
        data.setdefault('unit', request.get('unit', 'mm'))
        if 'depth' in data:
            return depth_cloud(data)
        points = validate(data)
        return make_cloud(points, data, data.get('colors'))
    import open3d as o3d
    o3d.utility.set_verbosity_level(o3d.utility.VerbosityLevel.Error)
    # Reject declared oversized binary clouds before the native reader allocates.
    if suffix in ('.pcd', '.ply'):
        header = raw[:65536]
        match = re.search(rb'(?im)^\s*(?:POINTS|element\s+vertex)\s+(\d+)\s*$', header)
        if not match or int(match.group(1)) > MAX_POINTS:
            raise ValueError('点云文件头缺少有效点数或超过 20 万点')
    # Generated names only; never interpret a client path as a server path.
    with tempfile.TemporaryDirectory(prefix='sieans-cloud-') as folder:
        path = Path(folder) / ('input'+suffix)
        path.write_bytes(raw)
        cloud = o3d.io.read_point_cloud(str(path), remove_nan_points=False, remove_infinite_points=False, print_progress=False)
    return make_cloud(np.asarray(cloud.points), {'unit': request.get('unit', 'mm')}, np.asarray(cloud.colors) if cloud.has_colors() else None)


def bounds(points):
    low, high = points.min(axis=0), points.max(axis=0)
    extent = high-low
    return {'minimum': low.tolist(), 'maximum': high.tolist(), 'center': ((low+high)/2).tolist(),
            'sizeX': float(extent[0]), 'sizeY': float(extent[1]), 'sizeZ': float(extent[2]), 'boundingBoxVolume': float(np.prod(extent))}


def run(request):
    started = time.perf_counter()
    operation = request.get('operation')
    if operation == 'cloud_import':
        cloud = import_cloud(request)
        result = {'pointCount': len(cloud['points']), 'unit': cloud['unit'], **bounds(np.asarray(cloud['points']))}
        return {'operation': operation, 'result': result, 'cloud': cloud, 'elapsedMs': round((time.perf_counter()-started)*1000, 1)}
    import open3d as o3d
    o3d.utility.set_verbosity_level(o3d.utility.VerbosityLevel.Error)
    original = request.get('cloud')
    points = validate(original)
    p = request.get('params', {})
    if not isinstance(p, dict):
        raise ValueError('params 必须为对象')
    pc = o3d.geometry.PointCloud(o3d.utility.Vector3dVector(points))
    if 'colors' in original:
        pc.colors = o3d.utility.Vector3dVector(original['colors'])
    result = {'unit': original['unit'], 'inputCount': len(points)}
    if operation == 'cloud_filter':
        method = p.get('method', 'voxel')
        if method == 'voxel':
            pc = pc.voxel_down_sample(number(p, 'voxelSize', 1, 1e-9, 1e6))
        elif method == 'crop':
            low = vector(p.get('minimum', [-100, -100, -100]), 3, 'minimum')
            high = vector(p.get('maximum', [100, 100, 100]), 3, 'maximum')
            if np.any(high <= low):
                raise ValueError('裁剪 maximum 必须大于 minimum')
            pc = pc.crop(o3d.geometry.AxisAlignedBoundingBox(low, high))
        elif method == 'statistical':
            neighbors = int(number(p, 'neighbors', 20, 2, 200))
            if len(points) <= neighbors:
                raise ValueError('点数量必须大于邻域点数')
            pc, _ = pc.remove_statistical_outlier(neighbors, number(p, 'stdRatio', 2, .01, 100))
        elif method == 'radius':
            pc, _ = pc.remove_radius_outlier(int(number(p, 'minPoints', 6, 1, 1000)), number(p, 'radius', 3, 1e-9, 1e6))
        else:
            raise ValueError('未知点云滤波方式')
        result['method'] = method
    elif operation == 'cloud_plane':
        if len(points) < 3:
            raise ValueError('平面拟合至少需要 3 个点')
        if np.linalg.matrix_rank(points-points.mean(axis=0)) < 2:
            raise ValueError('点云共线，不能拟合平面')
        o3d.utility.random.seed(42)
        model, indices = pc.segment_plane(number(p, 'distanceThreshold', .5, 1e-9, 1e6), 3, int(number(p, 'iterations', 500, 10, 10000)))
        model = np.asarray(model)
        if len(indices) < 3:
            raise ValueError('未找到有效平面')
        if model[np.argmax(np.abs(model[:3]))] < 0:
            model = -model
        distances = np.abs(points[indices] @ model[:3] + model[3])
        mode = p.get('output', 'inliers')
        if mode not in ('inliers', 'outliers', 'all'):
            raise ValueError('平面输出仅支持 inliers / outliers / all')
        if mode != 'all':
            pc = pc.select_by_index(indices, invert=mode == 'outliers')
        result.update(normal=model[:3].tolist(), plane=model.tolist(), inlierCount=len(indices), inlierRatio=len(indices)/len(points), rmsError=float(np.sqrt(np.mean(distances**2))), output=mode)
    elif operation == 'cloud_cluster':
        # DBSCAN neighborhoods can grow quadratically. Bound this expensive operator.
        if len(points) > 30_000:
            raise ValueError('聚类最多 3 万点，请先体素下采样')
        labels = np.asarray(pc.cluster_dbscan(number(p, 'eps', 3, 1e-9, 1e6), int(number(p, 'minPoints', 8, 2, 1000)), print_progress=False))
        ids = sorted(set(labels)-{-1})
        if len(ids) > 100:
            raise ValueError('聚类超过 100 个，请调整半径和最小点数')
        palette = np.asarray([[.02,.65,.88],[.95,.5,.18],[.25,.8,.5],[.7,.4,.95],[.95,.3,.45],[.85,.8,.25]])
        colors = np.tile([.5,.55,.6], (len(points),1))
        for index in ids:
            colors[labels == index] = palette[index % len(palette)]
        pc.colors = o3d.utility.Vector3dVector(colors)
        result.update(count=len(ids), noiseCount=int(np.sum(labels < 0)), items=[{'cluster': int(i), 'pointCount': int(np.sum(labels==i)), **bounds(points[labels==i])} for i in ids])
    elif operation == 'cloud_measure':
        result.update(bounds(points), note='坐标轴对齐包围盒尺寸；包围盒体积不等于物体实际体积')
    elif operation == 'cloud_height':
        baseline = number(p, 'baselineZ', 0, -1e9, 1e9)
        cell = number(p, 'cellSize', 1, 1e-6, 1e6)
        heights = points[:,2]-baseline
        # One topmost surface value per occupied XY cell; missing cells are NOT filled.
        cells = np.floor((points[:,:2]-points[:,:2].min(axis=0))/cell).astype(np.int64)
        _, inverse = np.unique(cells, axis=0, return_inverse=True)
        top = np.full(int(inverse.max())+1, -np.inf)
        np.maximum.at(top, inverse, heights)
        positive = np.maximum(top, 0)
        result.update(minHeight=float(heights.min()), maxHeight=float(heights.max()), meanHeight=float(heights.mean()), baselineZ=baseline,
                      cellSize=cell, occupiedCells=len(top), sampledArea=float(len(top)*cell**2), estimatedVolume=float(positive.sum()*cell**2),
                      volumeUnit=original['unit']+'³', note='沿 +Z 相对 baselineZ 的可见表面网格积分；每格取最高点、负高度归零、缺失格不补齐。仅适用于单值高度表面，非封闭物体真实体积。')
    elif operation == 'cloud_register':
        target = p.get('targetCloud')
        target_points = validate(target)
        if target['unit'] != original['unit']:
            raise ValueError('配准点云单位必须相同')
        if min(len(points),len(target_points)) < 3:
            raise ValueError('配准至少需要 3 个点')
        target_pc = o3d.geometry.PointCloud(o3d.utility.Vector3dVector(target_points))
        from global_registration import register, rigid
        method = p.get('method','icp')
        result.update(sourceFrame=original.get('frame','sensor'),targetFrame=target.get('frame','target'))
        if method == 'global':
            diagnostic, transform = register(points,target_points,p,o3d)
            result.update(diagnostic)
        elif method == 'icp':
            transform = np.asarray(p.get('initialTransform', np.eye(4).tolist()), dtype=float)
            if not rigid(transform):
                raise ValueError('initialTransform 必须为 4×4 刚体变换矩阵')
            registration = o3d.pipelines.registration.registration_icp(pc, target_pc, number(p, 'maxDistance', 5, 1e-9, 1e6), transform,
                o3d.pipelines.registration.TransformationEstimationPointToPoint(), o3d.pipelines.registration.ICPConvergenceCriteria(max_iteration=int(number(p, 'iterations', 50, 1, 500))))
            if registration.fitness == 0:
                raise ValueError('配准没有有效对应点，请检查初始位置和最大距离')
            transform = registration.transformation
            result.update(method='icp',fitness=registration.fitness, rmsError=registration.inlier_rmse, transformation=transform.tolist(), note='局部点到点 ICP；依赖初始姿态，fitness 不是检测置信度')
        else:
            raise ValueError('配准方式必须为 icp 或 global')
        if transform is not None:
            pc.transform(transform)
            # Camera intrinsics/extrinsics describe the old sensor frame, not this
            # newly registered coordinate system. Keep the original timestamp only.
            original = {k:v for k,v in original.items() if k not in ('intrinsics','extrinsics')}
            original = {**original, 'frame': target.get('frame', 'target')}
    else:
        raise ValueError('未知 3D 操作')
    cloud = make_cloud(np.asarray(pc.points), original, np.asarray(pc.colors) if pc.has_colors() else None)
    result['pointCount'] = len(cloud['points'])
    return {'operation': operation, 'result': result, 'cloud': cloud, 'elapsedMs': round((time.perf_counter()-started)*1000, 1)}
