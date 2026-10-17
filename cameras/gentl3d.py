"""SFNC calibrated Cartesian grids transported by Harvesters (not a vendor SDK)."""
import math
import hashlib
import json

import cv2
import numpy as np

FORMAT_DTYPES = {'Coord3D_ABC32f': np.dtype('<f4'), 'Coord3D_ABC32f_Planar': np.dtype('<f4'),
                 'Coord3D_ABC16': np.dtype('<u2'), 'Coord3D_ABC16_Planar': np.dtype('<u2')}
FORMATS = tuple(FORMAT_DTYPES)
MAX_PIXELS = 4_000_000
MAX_POINTS = 200_000


def read(node_map, name):
    from genicam.genapi import is_readable
    try:
        node = getattr(node_map, name)
        if not is_readable(node):
            raise ValueError('不可读')
        return node.value
    except Exception as exc:
        raise ValueError('3D 相机缺少可读参数 ' + name) from exc


def finite(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError('3D 相机参数 ' + name + ' 必须为有限数值')
    return float(value)


def check_integer_marker(fmt, value):
    if FORMAT_DTYPES[fmt].kind == 'u':
        limit = np.iinfo(FORMAT_DTYPES[fmt]).max
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= limit or int(value) != value:
            raise ValueError('整数 XYZ 的无效标记必须是 0 至 ' + str(limit) + ' 之间的整数')


def configure(node_map, params, applied, set_feature):
    # No user-set load, firmware changes or guessed camera calibration.
    from genicam.genapi import is_available
    try:
        node = getattr(node_map, 'GenDCStreamingMode')
    except Exception:
        node = None
    if node is not None and is_available(node):
        if read(node_map, 'GenDCStreamingMode') != 'Off':
            set_feature(node_map, 'GenDCStreamingMode', 'Off', applied)
    set_feature(node_map, 'ComponentSelector', 'Range', applied)
    if params.get('configure3d', True):
        for name, value in [('ComponentEnable', True), ('Scan3dOutputMode', 'CalibratedABC_Grid'),
                            ('PixelFormat', params.get('coordinateFormat', FORMATS[0]))]:
            # Fixed read-only values that already match are valid too.
            if read(node_map, name) != value:
                set_feature(node_map, name, value, applied)
    if read(node_map, 'ComponentEnable') is not True:
        raise ValueError('Range 分量未启用')
    if read(node_map, 'PixelFormat') not in FORMATS:
        raise ValueError('3D Range 需要支持的 Coord3D_ABC32f / ABC16 或其 Planar 格式')
    if read(node_map, 'Scan3dOutputMode') != 'CalibratedABC_Grid':
        raise ValueError('3D 采集仅接受 CalibratedABC_Grid 标定栅格')
    if read(node_map, 'Scan3dCoordinateSystem') != 'Cartesian':
        raise ValueError('3D 采集需要 Cartesian 笛卡尔坐标系')
    unit = read(node_map, 'Scan3dDistanceUnit')
    if unit not in ('Millimeter', 'Inch'):
        raise ValueError('不支持的 SFNC 距离单位：' + str(unit))
    reference = read(node_map, 'Scan3dCoordinateSystemReference')
    if reference not in ('Anchor', 'Transformed'):
        raise ValueError('不支持的 3D 坐标参考系：' + str(reference))
    old = read(node_map, 'Scan3dCoordinateSelector')
    axes = []
    try:
        for axis in ('CoordinateA', 'CoordinateB', 'CoordinateC'):
            set_feature(node_map, 'Scan3dCoordinateSelector', axis, applied)
            scale = finite(read(node_map, 'Scan3dCoordinateScale'), '比例')
            offset = finite(read(node_map, 'Scan3dCoordinateOffset'), '偏移')
            if scale == 0:
                raise ValueError('3D 坐标比例不能为 0')
            invalid = read(node_map, 'Scan3dInvalidDataFlag')
            if type(invalid) is not bool:
                raise ValueError('3D 无效值标志必须为开关')
            sentinel = read(node_map, 'Scan3dInvalidDataValue') if invalid else None
            if invalid and (isinstance(sentinel, bool) or not isinstance(sentinel, (int, float))):
                raise ValueError('3D 无效坐标标志值必须是数值')
            if invalid:
                check_integer_marker(read(node_map, 'PixelFormat'), sentinel)
            # NaN/Inf are excluded independently; metadata remains serializable.
            axes.append(dict(axis=axis, scale=scale, offset=offset, invalidEnabled=invalid,
                             invalidValue=sentinel if invalid and math.isfinite(sentinel) else None))
    finally:
        set_feature(node_map, 'Scan3dCoordinateSelector', old, applied)
    transform = {}
    if reference == 'Transformed':
        old_transform = read(node_map, 'Scan3dCoordinateTransformSelector')
        try:
            for key in ('RotationX','RotationY','RotationZ','TranslationX','TranslationY','TranslationZ'):
                set_feature(node_map,'Scan3dCoordinateTransformSelector',key,applied)
                transform[key]=finite(read(node_map,'Scan3dTransformValue'),key)
        finally:
            set_feature(node_map,'Scan3dCoordinateTransformSelector',old_transform,applied)
    return dict(unit=unit, millimetersPerUnit=1. if unit == 'Millimeter' else 25.4,
                reference=reference, axes=axes, transform=transform,pixelFormat=read(node_map, 'PixelFormat'))


def capture(components, params, calibration):
    if not components or len(components) > 64:
        raise ValueError('3D 帧分量数量无效')
    rows = [dict(index=i, pixelFormat=str(c.data_format), width=int(c.width), height=int(c.height))
            for i, c in enumerate(components)]
    chosen = params.get('rangeComponent', -1)
    if chosen == -1:
        matches = [i for i, c in enumerate(components) if str(c.data_format) in FORMATS]
        if len(matches) != 1:
            available='；'.join(str(r['index'])+' = '+r['pixelFormat'] for r in rows)
            raise ValueError('无法唯一识别 XYZ 分量，请在表单选择正确分量索引。收到：'+available)
        chosen = matches[0]
    if chosen >= len(components):
        raise ValueError('XYZ 分量索引超出本帧范围')
    component = components[chosen]
    fmt, w, h = str(component.data_format), int(component.width), int(component.height)
    if fmt not in FORMATS or fmt != calibration['pixelFormat']:
        raise ValueError('XYZ 分量格式与 Range 配置不一致')
    if min(w, h) < 1 or w * h > MAX_PIXELS:
        raise ValueError('3D 栅格最多 400 万点')
    data = component.data
    if data.dtype != FORMAT_DTYPES[fmt] or data.size != w*h*3:
        raise ValueError('XYZ 分量需要与格式及尺寸一致的 ' + FORMAT_DTYPES[fmt].name + ' 缓冲区')
    raw = (data.reshape(3, h, w).transpose(1, 2, 0) if fmt.endswith('_Planar') else data.reshape(h, w, 3)).copy()
    valid = np.isfinite(raw).all(axis=2)
    # SFNC invalid markers are per axis, in transmitted (unscaled) coordinates.
    for index, axis in enumerate(calibration['axes']):
        if axis['invalidEnabled']:
            check_integer_marker(fmt, axis['invalidValue'])
        if axis['invalidEnabled'] and axis['invalidValue'] is not None:
            valid &= raw[:, :, index] != axis['invalidValue']
    xyz = raw.astype(np.float64)
    for index, axis in enumerate(calibration['axes']):
        xyz[:, :, index] = (xyz[:, :, index]*axis['scale'] + axis['offset']) * calibration['millimetersPerUnit']
    if not np.isfinite(xyz[valid]).all() or (np.abs(xyz[valid]) > 1e9).any():
        raise ValueError('换算后的 3D 坐标超出允许范围')
    finite_count = int(valid.sum())
    used = {chosen}

    def optional_component(key, formats):
        index = params.get(key, -1)
        if index == -1:
            return None
        if index >= len(components) or index in used:
            raise ValueError('亮度、置信度和 XYZ 分量索引必须各不相同且存在')
        used.add(index)
        c = components[index]
        if str(c.data_format) not in formats or int(c.width) != w or int(c.height) != h:
            raise ValueError(key + ' 格式或栅格尺寸不匹配；需要与 XYZ 逐像素对应的分量')
        dtype = np.uint8 if str(c.data_format).endswith('8') else np.uint16
        if c.data.dtype != dtype or c.data.size != w*h:
            raise ValueError(key + ' 缓冲区类型或长度错误')
        return c.data.reshape(h,w).copy()

    confidence = optional_component('confidenceComponent', ('Confidence8','Confidence16','Mono8','Mono16'))
    if confidence is not None:
        threshold = params.get('confidenceThreshold', 1)
        if threshold > np.iinfo(confidence.dtype).max:
            raise ValueError('置信度阈值超过所选分量位深')
        valid &= confidence >= threshold
    intensity = optional_component('intensityComponent', ('Mono8','Mono16'))
    stride = params.get('pointStride',4)
    sampled = valid[::stride,::stride]
    count = int(sampled.sum())
    if not count:
        raise ValueError('3D 帧没有通过有效性与置信度筛选的采样点')
    if count > MAX_POINTS:
        raise ValueError('点云超过 20 万点，请增加点云采样步长')
    points = xyz[::stride,::stride][sampled]
    identity=dict(provider=params.get('providerId',''),device=params.get('deviceId',''),
                  reference=calibration['reference'],unit=calibration['unit'],transform=calibration.get('transform',{}))
    key = hashlib.sha256(json.dumps(identity,sort_keys=True,allow_nan=False).encode()).hexdigest()[:16]
    cloud = dict(unit='mm',frame='gentl-'+key+'-'+calibration['reference'].lower(),points=points.tolist())
    if intensity is not None:
        image = (intensity >> 8).astype(np.uint8) if intensity.dtype == np.uint16 else intensity
        grayscale = image[::stride,::stride][sampled].astype(np.float64)/255.
        cloud['colors'] = np.repeat(grayscale[:,None],3,axis=1).tolist()
        kind = 'aligned-intensity-preview'
        preview_range = None
    else:
        # A Z preview, never fabricated as a lossless raw depth image.
        z = xyz[:,:,2];low,high = float(z[valid].min()),float(z[valid].max())
        normalized = np.zeros((h,w),np.uint8)
        normalized[valid] = 128 if high==low else np.clip((z[valid]-low)/(high-low)*255,0,255).astype(np.uint8)
        image = cv2.applyColorMap(normalized,cv2.COLORMAP_TURBO);image[~valid]=0
        kind,preview_range = 'coordinate-z-preview', [low,high]
    info = dict(pixelFormat=fmt,sourceBits=data.dtype.itemsize*8,outputBits=8,imageKind=kind,pointCount=count,
                componentAlignment='user-confirmed' if len(used)>1 else 'not-used',
                validCoordinatePoints=finite_count,confidenceAcceptedPoints=int(valid.sum()),
                invalidCoordinatePoints=w*h-finite_count,rangeComponent=chosen,
                intensityComponent=params.get('intensityComponent',-1),confidenceComponent=params.get('confidenceComponent',-1),
                pointStride=stride,components=rows,calibration=calibration,zPreviewRangeMm=preview_range)
    return image,info,None,cloud
