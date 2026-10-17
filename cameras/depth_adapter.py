"""RGB-D acquisition and calibrated point-cloud packaging. Distances are explicit."""
import base64
import math
import time
from datetime import datetime, timezone
import cv2
import numpy as np

MAX_DEPTH_PIXELS = 4_000_000
MAX_POINTS = 200_000


def sdk():
    try:
        import pyrealsense2 as rs
        return rs
    except ImportError as error:
        raise ValueError('RealSense SDK 未安装：请安装 cameras/requirements-depth.txt') from error


def png(image):
    ok, encoded = cv2.imencode('.png', image)
    if not ok or encoded.size > 12_000_000:
        raise ValueError('深度图编码失败或超过 12 MB')
    return 'data:image/png;base64,' + base64.b64encode(encoded).decode('ascii')


def intrinsics(value):
    return dict(width=value.width, height=value.height, fx=value.fx, fy=value.fy,
                cx=value.ppx, cy=value.ppy, model=str(value.model), coefficients=list(value.coeffs))


def devices(rs=None):
    rs = rs or sdk()
    context = rs.context()
    rows = []
    for device in context.query_devices():
        def info(key):
            return device.get_info(key) if device.supports(key) else ''
        if not any(s.is_depth_sensor() for s in device.query_sensors()):
            continue
        serial = info(rs.camera_info.serial_number)
        if not serial:
            continue
        rows.append(dict(driver='realsense', deviceId=serial, name=info(rs.camera_info.name),
                         serial=serial, model=info(rs.camera_info.product_line),
                         firmware=info(rs.camera_info.firmware_version), transport=info(rs.camera_info.usb_type_descriptor)))
    return rows


def profiles(device, rs):
    rows = []
    seen = set()
    for sensor in device.query_sensors():
        for profile in sensor.get_stream_profiles():
            if not profile.is_video_stream_profile() or profile.stream_type() not in (rs.stream.depth, rs.stream.color):
                continue
            video = profile.as_video_stream_profile()
            key = (str(video.stream_type()), video.width(), video.height(), video.fps(), str(video.format()))
            if key in seen:
                continue
            seen.add(key)
            rows.append(dict(stream=key[0], width=key[1], height=key[2], fps=key[3], format=key[4]))
    return rows


def pack(raw, scale, vertices_m, p, calibration, frame_name, color=None, texcoords=None, timestamp=None):
    """Do not infer depth scale or align a color raster by resizing it."""
    if raw.dtype != np.uint16 or raw.ndim != 2 or not 0 < raw.size <= MAX_DEPTH_PIXELS:
        raise ValueError('深度输入必须是 16 位单通道图像，最多 400 万像素')
    if not isinstance(scale, (int, float)) or not math.isfinite(scale) or not 0 < scale <= 1:
        raise ValueError('深度设备的米/原始值比例无效')
    h, w = raw.shape
    if vertices_m.shape != (h*w, 3):
        raise ValueError('标定点云和深度图尺寸不一致')
    stride = p.get('pointStride', 4)
    if (math.ceil(h / stride) * math.ceil(w / stride)) > MAX_POINTS:
        raise ValueError('采样网格超过 20 万点，请增大点云采样步长')
    low, high = p.get('minDepth', .1), p.get('maxDepth', 5.)
    meters = raw.astype(np.float64) * scale
    valid = (raw > 0) & (meters >= low) & (meters <= high)
    indices = np.arange(raw.size).reshape(h, w)[::stride, ::stride].ravel()
    mask = valid.ravel()[indices] & np.isfinite(vertices_m[indices]).all(axis=1) & (vertices_m[indices,2] > 0)
    indices = indices[mask]
    if not len(indices):
        raise ValueError('深度帧没有有效采样点；检查距离范围、遮挡、设备或曝光')
    points = vertices_m[indices].astype(np.float64) * 1000
    if np.max(np.abs(points)) > 1e9:
        raise ValueError('点云坐标超出允许范围')
    timestamp = timestamp or datetime.now(timezone.utc).isoformat()
    cloud = dict(points=points.tolist(), unit='mm', frame=frame_name, timestamp=timestamp,
                 intrinsics=calibration['depth'])
    if 'depthToColor' in calibration:
        cloud['extrinsics'] = calibration['depthToColor']
    mapped = 0
    if color is not None and texcoords is not None:
        if color.dtype != np.uint8 or color.ndim != 3 or color.shape[2] != 3 or texcoords.shape != (raw.size,2):
            raise ValueError('彩色图或深度到彩色坐标映射无效')
        ch, cw = color.shape[:2]
        uv = texcoords[indices]
        good = np.isfinite(uv).all(axis=1) & (uv >= 0).all(axis=1) & (uv < 1).all(axis=1)
        pixels = np.zeros_like(uv, dtype=np.int64)
        pixels[good] = np.floor(uv[good] * (cw,ch) + .5).astype(np.int64)
        good &= (pixels[:,0] < cw) & (pixels[:,1] < ch)
        colors = np.full((len(indices),3), .5, np.float64)
        colors[good] = color[pixels[good,1],pixels[good,0],::-1] / 255.
        cloud['colors'] = colors.tolist()
        mapped = int(good.sum())
    # Fixed display interval; raw uint16 data is retained separately without clipping.
    normalized = np.clip((meters-low)/(high-low)*255,0,255).astype(np.uint8)
    preview = cv2.applyColorMap(normalized, cv2.COLORMAP_TURBO)
    preview[~valid] = 0
    depth = dict(format='png16', image=png(raw), preview=png(preview), width=w, height=h,
                 scaleMeters=scale, intrinsics=calibration['depth'], frame=frame_name, timestamp=timestamp,
                 minMeters=low, maxMeters=high, invalidValue=0)
    stats = dict(depthWidth=w, depthHeight=h, depthScaleMeters=scale, validDepthPixels=int((raw>0).sum()),
                 inRangePixels=int(valid.sum()), invalidDepthPixels=int((raw==0).sum()), pointCount=len(indices),
                 pointStride=stride, mappedColorPoints=mapped, unit='mm', frame=frame_name, calibration=calibration,
                 minDepthMeters=float(meters[valid].min()), maxDepthMeters=float(meters[valid].max()),
                 depthPreviewRangeMeters=[low,high], colorAligned=False)
    return depth, cloud, stats, preview


def acquire_frames(p, inspect=False, rs=None):
    rs = rs or sdk()
    context = rs.context()
    found = [d for d in context.query_devices() if d.supports(rs.camera_info.serial_number)
             and d.get_info(rs.camera_info.serial_number) == p.get('deviceId')]
    if len(found) != 1:
        raise ValueError('所选 RealSense 设备不存在或序列号不唯一，请重新枚举')
    device = found[0]
    info = dict(deviceId=p['deviceId'], serial=p['deviceId'], name=device.get_info(rs.camera_info.name), driver='realsense')
    if inspect:
        yield dict(device=info, items=[dict(name='可用流配置', value=profiles(device,rs), writable=False),
                                      dict(name='深度比例（米/原始值）',value=device.first_depth_sensor().get_depth_scale(),writable=False)])
        return
    pipe = rs.pipeline(context)
    cfg = rs.config()
    cfg.enable_device(p['deviceId'])
    w,h,fps = p.get('width',640),p.get('height',480),p.get('fps',30)
    cfg.enable_stream(rs.stream.depth,w,h,rs.format.z16,fps)
    has_color = p.get('enableColor',True)
    if has_color:
        cfg.enable_stream(rs.stream.color,p.get('colorWidth',640),p.get('colorHeight',480),rs.format.bgr8,fps)
    started = False
    deadline = time.monotonic() + p['timeoutMs']/1000
    try:
        pipe.start(cfg)
        started = True
        for _ in range(p.get('warmupFrames',5)+1):
            remaining = int((deadline-time.monotonic())*1000)
            if remaining <= 0:
                raise TimeoutError('RealSense 预热/采集超过总时限')
            frames = pipe.wait_for_frames(remaining)
        while True:
            received_at = datetime.now(timezone.utc).isoformat()
            depth_frame = frames.get_depth_frame()
            color_frame = frames.get_color_frame() if has_color else None
            if not depth_frame or (has_color and not color_frame):
                raise ValueError('RealSense 未返回请求的深度/彩色帧')
            depth_profile = depth_frame.profile.as_video_stream_profile()
            if (depth_profile.width(),depth_profile.height(),depth_profile.fps(),depth_profile.format()) != (w,h,fps,rs.format.z16):
                raise ValueError('RealSense 实际深度流配置与请求不一致')
            raw = np.asanyarray(depth_frame.get_data()).copy()
            if raw.size > MAX_DEPTH_PIXELS:
                raise ValueError('深度帧超过 400 万像素')
            scale = depth_frame.get_units()
            calibration = dict(depth=intrinsics(depth_profile.get_intrinsics()))
            color = None
            pc = rs.pointcloud()
            if has_color:
                cp = color_frame.profile.as_video_stream_profile()
                if (cp.width(),cp.height(),cp.fps(),cp.format()) != (p.get('colorWidth',640),p.get('colorHeight',480),fps,rs.format.bgr8):
                    raise ValueError('RealSense 实际彩色流配置与请求不一致')
                color = np.asanyarray(color_frame.get_data()).copy()
                calibration['color'] = intrinsics(cp.get_intrinsics())
                extrinsic = depth_profile.get_extrinsics_to(cp)
                calibration['depthToColor'] = dict(rotation=np.asarray(extrinsic.rotation).reshape(3,3,order='F').tolist(),
                                                   translation=list(extrinsic.translation), unit='m',
                                                   fromFrame='depth-optical', toFrame='color-optical')
                pc.map_to(color_frame)
            points = pc.calculate(depth_frame)
            vertices = np.asanyarray(points.get_vertices()).view(np.float32).reshape(-1,3).copy()
            texture = np.asanyarray(points.get_texture_coordinates()).view(np.float32).reshape(-1,2).copy() if has_color else None
            depth,cloud,stats,preview = pack(raw,scale,vertices,p,calibration,'realsense-depth:'+p['deviceId'][:80],color,texture,received_at)
            meta = dict(device=info, timestamp=received_at, pixelFormat='BGR8', sourceBits=8 if has_color else 16, outputBits=8, depthBits=16,
                        imageKind='color' if has_color else 'depth-preview', applied=[], **stats,
                        depthFrameNumber=str(depth_frame.get_frame_number()), depthDeviceTimeMs=depth_frame.get_timestamp(),
                        depthClockDomain=str(depth_frame.get_frame_timestamp_domain()))
            if has_color:
                meta.update(colorFrameNumber=str(color_frame.get_frame_number()),colorDeviceTimeMs=color_frame.get_timestamp(),
                            colorClockDomain=str(color_frame.get_frame_timestamp_domain()))
            yield color if has_color else preview, meta, depth, cloud
            frames = pipe.wait_for_frames(p['timeoutMs'])
    finally:
        if started:
            pipe.stop()


def simulated_devices():
    return [dict(deviceId='synthetic-rgbd',name='标定深度相机（模拟）',driver='rgbd_simulator',serial='SIM-RGBD-001',model='64 × 48 深度/彩色')]


def simulate(p, inspect=False):
    if p.get('deviceId','synthetic-rgbd') != 'synthetic-rgbd':
        raise ValueError('模拟深度设备不存在')
    if p.get('width',64) != 64 or p.get('height',48) != 48:
        raise ValueError('模拟深度设备的固定尺寸为 64 × 48')
    if inspect:
        return dict(device=simulated_devices()[0],items=[dict(name='深度尺寸',value=[64,48],writable=False),dict(name='深度比例（米/原始值）',value=.001,writable=False)])
    raw = np.full((48,64),1000,np.uint16)
    raw[19:29,22:42] = 975
    raw[0,0] = 0
    y,x = np.indices(raw.shape)
    z = raw.astype(np.float64)*.001
    vertices = np.stack(((x-31.5)*z/100,(y-23.5)*z/100,z),axis=-1).reshape(-1,3)
    color = np.full((48,64,3),40,np.uint8)
    color[19:29,22:42] = [40,220,40]
    uv = np.stack((x/64,y/48),axis=-1).reshape(-1,2)
    intr = dict(width=64,height=48,fx=100.,fy=100.,cx=31.5,cy=23.5,model='none',coefficients=[0.]*5)
    calibration = dict(depth=intr,color=dict(intr),depthToColor=dict(rotation=np.eye(3).tolist(),translation=[0.,0.,0.],unit='m',fromFrame='depth-optical',toFrame='color-optical'))
    depth,cloud,stats,preview = pack(raw,.001,vertices,{**p,'pointStride':p.get('pointStride',1)},calibration,'simulated-depth-optical',color,uv)
    stats['colorAligned'] = True
    return color,dict(device=simulated_devices()[0],timestamp=depth['timestamp'],pixelFormat='BGR8',sourceBits=8,outputBits=8,depthBits=16,imageKind='color',applied=[],**stats),depth,cloud


def acquire(p, inspect=False, rs=None):
    frames = acquire_frames(p, inspect, rs)
    try:
        return next(frames)
    finally:
        frames.close()
