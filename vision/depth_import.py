"""Strict PNG16 optical-axis depth import; no SDK or Open3D dependency."""
import base64
import math
import struct
import time
import cv2
import numpy as np


def number(p, key, low, high, integer=False):
    v = p.get(key)
    if isinstance(v, bool) or not isinstance(v, (float, int)) or not math.isfinite(v) or not low <= v <= high or integer and int(v) != v:
        raise ValueError('深度导入参数无效：'+key)
    return int(v) if integer else float(v)


def png(image):
    ok, encoded = cv2.imencode('.png', image)
    if not ok or encoded.size > 12000000:
        raise ValueError('深度预览编码失败或超过 12 MB')
    return 'data:image/png;base64,'+base64.b64encode(encoded).decode('ascii')


def run(request):
    started = time.perf_counter()
    p = request.get('params')
    if not isinstance(p, dict) or p.get('projection') != 'rectified-z':
        raise ValueError('仅支持已校正针孔相机的光轴 Z 深度，请确认深度定义')
    fx, fy = [number(p, k, .000001, 1e9) for k in ('fx', 'fy')]
    cx, cy = [number(p, k, -1e6, 1e6) for k in ('cx', 'cy')]
    scale = number(p, 'scaleMeters', 1e-9, 1)
    low, high = [number(p, k, 0, 1000) for k in ('minDepth', 'maxDepth')]
    stride = number(p, 'pointStride', 1, 1024, True)
    invalid = number(p, 'invalidValue', 0, 65535, True)
    frame = p.get('frame')
    if not isinstance(frame, str) or not 1 <= len(frame) <= 120 or any(ord(c) < 32 for c in frame):
        raise ValueError('深度坐标系名称无效')
    if low >= high:
        raise ValueError('最近深度必须小于最远深度')
    value = request.get('content')
    if not isinstance(value, str) or len(value) > 16000050 or not value.startswith('data:image/png;base64,'):
        raise ValueError('请选择原始 16 位单通道 PNG，文件上限 12 MB')
    try:
        encoded = base64.b64decode(value[22:], validate=True)
    except ValueError:
        raise ValueError('深度 PNG 编码无效') from None
    if len(encoded) < 33 or len(encoded) > 12000000 or encoded[:8] != b'\x89PNG\r\n\x1a\n' or encoded[8:16] != b'\x00\x00\x00\rIHDR':
        raise ValueError('深度 PNG 文件头无效')
    w, h = struct.unpack('>II', encoded[16:24])
    if not w or not h or w*h > 4000000 or w > 32768 or h > 32768:
        raise ValueError('深度图最多 400 万像素，单边最多 32768')
    if encoded[24:26] != b'\x10\x00':
        raise ValueError('深度 PNG 必须是原始 16 位灰度，不能使用 8 位、彩色或伪彩图')
    if math.ceil(w/stride)*math.ceil(h/stride) > 200000:
        raise ValueError('采样网格超过 20 万点，请增大采样步长')
    raw = cv2.imdecode(np.frombuffer(encoded, np.uint8), cv2.IMREAD_UNCHANGED)
    if raw is None or raw.dtype != np.uint16 or raw.shape != (h, w):
        raise ValueError('深度 PNG 解码失败或尺寸/位深不一致')
    meters = raw.astype(np.float64)*scale
    valid = (raw != 0) & (raw != invalid)
    in_range = valid & (meters >= low) & (meters <= high)
    v, u = np.mgrid[0:h:stride, 0:w:stride]
    keep = in_range[v, u]
    v, u = v[keep], u[keep]
    z = meters[v, u]
    if len(z) == 0:
        raise ValueError('没有范围内有效采样点，请检查深度比例、距离范围和无效值')
    points = np.column_stack(((u-cx)*z/fx, (v-cy)*z/fy, z))*1000
    if not np.isfinite(points).all() or np.abs(points).max() > 1e9:
        raise ValueError('投影点云坐标超限，请检查内参与深度比例')
    intr = dict(width=w, height=h, fx=fx, fy=fy, cx=cx, cy=cy, model='none', coefficients=[0, 0, 0, 0, 0])
    normalized = np.clip((meters-low)/(high-low)*255, 0, 255).astype(np.uint8)
    preview = cv2.applyColorMap(normalized, cv2.COLORMAP_TURBO)
    preview[~in_range] = 0
    # Keep the exact original file bytes; preview and sampling never change raw depth.
    depth = dict(format='png16', image=value, preview=png(preview), width=w, height=h, scaleMeters=scale,
                 intrinsics=intr, frame=frame, minMeters=low, maxMeters=high, invalidValue=invalid,
                 projection='rectified-z', source='file')
    cloud = dict(points=points.tolist(), unit='mm', frame=frame, intrinsics=intr, source='depth-png16', pointStride=stride)
    stats = dict(depthWidth=w, depthHeight=h, depthScaleMeters=scale, pointStride=stride, pointCount=len(z),
                 validDepthPixels=int(valid.sum()), invalidDepthPixels=int((~valid).sum()), inRangePixels=int(in_range.sum()),
                 sampledInvalidPixels=int(keep.size-keep.sum()), minDepthMeters=float(z.min()), maxDepthMeters=float(z.max()),
                 unit='mm', frame=frame, projection='rectified-z')
    return dict(operation='depth_import', result=stats, cloud=cloud, depth=depth, annotatedImage=depth['preview'], elapsedMs=round((time.perf_counter()-started)*1000, 3))
