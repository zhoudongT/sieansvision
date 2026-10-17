"""Orbbec SDK v2 single-frame adapter. SDK coordinates retain their reported scale."""
import math
import os
import time
import tempfile
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
import cv2
import numpy as np
try:
    from . import depth_adapter as depth
except ImportError:
    import depth_adapter as depth

SDK_VERSION = '2.1.2'
COLOR_FORMATS = ('RGB', 'BGR', 'MJPG', 'YUYV', 'UYVY', 'NV12', 'NV21')


def sdk():
    try:
        from importlib.metadata import version
        if version('pyorbbecsdk2') != SDK_VERSION:
            raise ValueError('Orbbec SDK 版本不匹配；请安装 cameras/requirements-orbbec.txt')
        import pyorbbecsdk as ob
        return ob
    except ImportError as error:
        raise ValueError('Orbbec SDK 未安装：请安装 cameras/requirements-orbbec.txt') from error


def context(ob, network=False):
    logs=Path(os.environ.get('MACHINE_DATA_DIR') or Path(__file__).resolve().parents[1]/'data')/'camera-sdk-logs'/'orbbec'
    logs.mkdir(parents=True,exist_ok=True)
    ob.Context.set_logger_to_file(ob.OBLogLevel.ERROR,str(logs))
    ob.Context.set_logger_to_console(ob.OBLogLevel.ERROR)
    # The packaged XML enables network enumeration. Disable it before Context
    # starts discovery, then enable only when explicitly requested by the form.
    config=ET.parse(Path(ob.__file__).parent/'OrbbecSDKConfig.xml')
    enumeration=config.find('./Device/EnumerateNetDevice')
    if enumeration is None:raise ValueError('Orbbec SDK 配置缺少网络发现设置')
    enumeration.text='false'
    with tempfile.NamedTemporaryFile(dir=logs,suffix='.xml',delete=False) as output:
        config.write(output,encoding='utf-8',xml_declaration=True);config_path=output.name
    try:ctx=ob.Context(config_path)
    finally:Path(config_path).unlink(missing_ok=True)
    ctx.enable_net_device_enumeration(network)
    return ctx


def device_rows(items):
    # DeviceList metadata does not open a device or begin streaming.
    rows=[]
    for i in range(items.get_count()):
        serial=items.get_device_serial_number_by_index(i)
        if not serial:continue
        rows.append(dict(driver='orbbec',deviceId=serial,serial=serial,
                         name=items.get_device_name_by_index(i),model=items.get_device_name_by_index(i),
                         vendor='Orbbec',transport=items.get_device_connection_type_by_index(i),
                         uid=items.get_device_uid_by_index(i)))
    return rows


def devices(p, ob=None):
    ob=ob or sdk();ctx=context(ob,p.get('discoverNetwork',False))
    return device_rows(ctx.query_devices())


def profile_rows(pipe,ob):
    rows=[]
    for sensor,label in [(ob.OBSensorType.DEPTH_SENSOR,'深度'),(ob.OBSensorType.COLOR_SENSOR,'彩色')]:
        try:profiles=pipe.get_stream_profile_list(sensor)
        except ob.OBError:
            if label=='深度':raise
            continue
        for i in range(len(profiles)):
            profile=profiles[i].as_video_stream_profile()
            rows.append(dict(stream=label,width=profile.get_width(),height=profile.get_height(),
                             fps=profile.get_fps(),format=profile.get_format().name))
    return rows


def intrinsics(profile):
    intr=profile.get_intrinsic();dist=profile.get_distortion()
    values=dict(width=int(intr.width),height=int(intr.height),fx=float(intr.fx),fy=float(intr.fy),cx=float(intr.cx),cy=float(intr.cy),
                model=dist.model.name,coefficients=[float(getattr(dist,k)) for k in ('k1','k2','p1','p2','k3','k4','k5','k6')],
                coefficientOrder=['k1','k2','p1','p2','k3','k4','k5','k6'])
    if values['width']!=profile.get_width() or values['height']!=profile.get_height() or not all(math.isfinite(values[k]) for k in ('fx','fy','cx','cy')) or min(values['fx'],values['fy'])<=0 or not all(map(math.isfinite,values['coefficients'])):
        raise ValueError('Orbbec 内参与实际流配置不一致或无效')
    return values


def raw_depth(frame,ob):
    w,h=frame.get_width(),frame.get_height()
    if frame.get_format()!=ob.OBFormat.Y16 or w<1 or h<1 or w*h>depth.MAX_DEPTH_PIXELS:
        raise ValueError('Orbbec 深度帧须为 Y16 且不超过 400 万像素')
    data=np.frombuffer(frame.get_data(),np.uint16)
    if data.size!=w*h:raise ValueError('Orbbec 深度缓冲区尺寸不一致')
    return data.reshape(h,w).copy()


def color_image(frame,ob):
    w,h=frame.get_width(),frame.get_height();fmt=frame.get_format().name
    if w<1 or h<1 or w*h>16_000_000:raise ValueError('Orbbec 彩色帧尺寸无效或过大')
    data=np.frombuffer(frame.get_data(),np.uint8)
    if fmt in ('RGB','BGR'):
        if data.size!=w*h*3:raise ValueError('Orbbec 彩色缓冲区长度不一致')
        image=data.reshape(h,w,3)
        image=cv2.cvtColor(image,cv2.COLOR_RGB2BGR) if fmt=='RGB' else image.copy()
    elif fmt=='MJPG':
        if data.size>12_000_000:raise ValueError('Orbbec 彩色压缩帧超过 12 MB')
        image=cv2.imdecode(data,cv2.IMREAD_COLOR)
    elif fmt in ('YUYV','UYVY'):
        if w%2 or data.size!=w*h*2:raise ValueError('Orbbec YUV422 缓冲区尺寸无效')
        image=cv2.cvtColor(data.reshape(h,w,2),cv2.COLOR_YUV2BGR_YUY2 if fmt=='YUYV' else cv2.COLOR_YUV2BGR_UYVY)
    elif fmt in ('NV12','NV21'):
        if w%2 or h%2 or data.size!=w*h*3//2:raise ValueError('Orbbec YUV420 缓冲区尺寸无效')
        image=cv2.cvtColor(data.reshape(h*3//2,w),cv2.COLOR_YUV2BGR_NV12 if fmt=='NV12' else cv2.COLOR_YUV2BGR_NV21)
    else:raise ValueError('不支持 Orbbec 彩色格式 '+fmt)
    if image is None or image.shape!=(h,w,3):raise ValueError('Orbbec 彩色帧解码尺寸不一致')
    return image


def process_frames(frames,p,ob=None):
    ob=ob or sdk();df=frames.get_depth_frame()
    if df is None:raise ValueError('Orbbec 帧组缺少深度帧')
    raw=raw_depth(df,ob);h,w=raw.shape
    stride=p.get('pointStride',4)
    if math.ceil(h/stride)*math.ceil(w/stride)>depth.MAX_POINTS:raise ValueError('采样网格超过 20 万点，请增大点云采样步长')
    scale=float(df.get_depth_scale())/1000.
    if not math.isfinite(scale) or not 0<scale<=1:raise ValueError('Orbbec 深度比例无效')
    dp=df.get_stream_profile().as_video_stream_profile();calibration={'depth':intrinsics(dp)}
    pc=ob.PointCloudFilter();pc.set_create_point_format(ob.OBFormat.POINT)
    point_frame=pc.process(df)
    if point_frame is None:raise ValueError('Orbbec SDK 未生成点云')
    point_frame=point_frame.as_points_frame();point_scale=float(point_frame.get_position_value_scale())/1000.
    if not math.isfinite(point_scale) or not 0<point_scale<=1:raise ValueError('Orbbec 点坐标比例无效')
    # PointCloudFilter returns float coordinates in units specified by the PointsFrame,
    # which need not be millimetres (e.g. depth scale 0.5 mm). Never assume unit scale.
    xyz=np.frombuffer(point_frame.get_data(),np.float32)
    if xyz.size!=raw.size*3 or (point_frame.get_width(),point_frame.get_height())!=(w,h):raise ValueError('Orbbec 点云与深度栅格不一致')
    vertices=xyz.reshape(-1,3).astype(np.float64)*point_scale
    color=None;texture=None;cf=None
    if p.get('enableColor',True):
        cf=frames.get_color_frame()
        if cf is None:raise ValueError('Orbbec 帧组缺少请求的彩色帧')
        cp=cf.get_stream_profile().as_video_stream_profile();calibration['color']=intrinsics(cp)
        extr=dp.get_extrinsic_to(cp)
        rotation=np.asarray(extr.rot,np.float64).reshape(3,3)
        translation=np.asarray(extr.transform,np.float64)/1000.
        if translation.shape!=(3,) or not np.isfinite(rotation).all() or not np.isfinite(translation).all():raise ValueError('Orbbec 深度到彩色外参无效')
        calibration['depthToColor']=dict(rotation=rotation.tolist(),translation=translation.tolist(),unit='m',fromFrame='depth-optical',toFrame='color-optical')
        # AlignFilter accepts RGB input reliably across the supported color encodings.
        # Use the SDK converter so stream calibration/extrinsics survive conversion.
        color_image(cf,ob)  # Validate declared dimensions/buffer before native conversion.
        align_frames=frames
        fmt=cf.get_format().name
        if fmt!='RGB':
            conversions={'BGR':'BGR_TO_RGB','MJPG':'MJPG_TO_RGB888','YUYV':'YUYV_TO_RGB888','UYVY':'UYVY_TO_RGB888','NV12':'NV12_TO_RGB888','NV21':'NV21_TO_RGB888'}
            converter=ob.FormatConvertFilter();converter.set_format_convert_format(getattr(ob.OBConvertFormat,conversions[fmt]))
            converted=converter.process(cf)
            if converted is None or converted.get_format()!=ob.OBFormat.RGB:raise ValueError('Orbbec SDK 彩色格式转换失败')
            align_frames=ob.Frame.create_frame_set();align_frames.push_frame(df);align_frames.push_frame(converted)
        # SDK C2D maps RGB into the depth optical grid; the native depth must remain unchanged.
        aligned=ob.AlignFilter(align_to_stream=ob.OBStreamType.DEPTH_STREAM).process(align_frames)
        if aligned is None:raise ValueError('Orbbec SDK 彩色到深度对齐失败')
        aligned=aligned.as_frame_set();ad=aligned.get_depth_frame();ac=aligned.get_color_frame()
        if ad is None or ac is None or not np.array_equal(raw_depth(ad,ob),raw) or not math.isclose(float(ad.get_depth_scale())/1000.,scale,rel_tol=1e-7):raise ValueError('Orbbec C2D 未保留原始深度')
        color=color_image(ac,ob)
        if color.shape[:2]!=(h,w):raise ValueError('Orbbec C2D 彩色栅格与深度不一致')
        y,x=np.indices((h,w));texture=np.stack((x/w,y/h),axis=-1).reshape(-1,2)
    received=datetime.now(timezone.utc).isoformat()
    raw_out,cloud,stats,preview=depth.pack(raw,scale,vertices,p,calibration,'orbbec-depth:'+p['deviceId'][:80],color,texture,received)
    stats['colorAligned']=color is not None
    stats['colorAlignment']='sdk-color-to-depth' if color is not None else 'none'
    if color is not None:
        stats['alignedColorSamples']=stats.pop('mappedColorPoints')
        stats['colorCoverageKnown']=False  # SDK blank alignment pixels have no separate validity mask.
    stats.update(depthFrameNumber=str(df.get_index()),depthDeviceTimeUs=str(df.get_timestamp_us()),depthSystemTimeUs=str(df.get_system_timestamp_us()),
                 depthClockDomain='device',sdkVersion=SDK_VERSION,pointPositionScaleMeters=point_scale)
    if cf is not None:stats.update(colorFrameNumber=str(cf.get_index()),colorDeviceTimeUs=str(cf.get_timestamp_us()),colorSystemTimeUs=str(cf.get_system_timestamp_us()))
    return color if color is not None else preview,stats,raw_out,cloud


def check_profile(profile,w,h,fps,fmt,label):
    if (profile.get_width(),profile.get_height(),profile.get_fps(),profile.get_format())!=(w,h,fps,fmt):raise ValueError('Orbbec '+label+'实际流配置与请求不一致')


def acquire_frames(p,inspect=False,ob=None):
    ob=ob or sdk();ctx=context(ob,p.get('discoverNetwork',False));items=ctx.query_devices()
    matches=[row for row in device_rows(items) if row['deviceId']==p.get('deviceId')]
    if len(matches)!=1:raise ValueError('所选 Orbbec 设备不存在或序列号不唯一，请重新枚举')
    device=items.get_device_by_serial_number(p['deviceId']);pipe=ob.Pipeline(device)
    info={**matches[0],'firmware':device.get_device_info().get_firmware_version()}
    if inspect:
        yield dict(device=info,items=[dict(name='可用流配置',value=profile_rows(pipe,ob),writable=False),dict(name='SDK 版本',value=SDK_VERSION,writable=False)])
        return
    cfg=ob.Config();w,h,fps=p.get('width',640),p.get('height',480),p.get('fps',30)
    dp=pipe.get_stream_profile_list(ob.OBSensorType.DEPTH_SENSOR).get_video_stream_profile(w,h,ob.OBFormat.Y16,fps)
    check_profile(dp,w,h,fps,ob.OBFormat.Y16,'深度');cfg.enable_stream(dp)
    cp=None
    if p.get('enableColor',True):
        fmt=getattr(ob.OBFormat,p.get('colorFormat','RGB'));cw,ch=p.get('colorWidth',640),p.get('colorHeight',480)
        cp=pipe.get_stream_profile_list(ob.OBSensorType.COLOR_SENSOR).get_video_stream_profile(cw,ch,fmt,fps)
        check_profile(cp,cw,ch,fps,fmt,'彩色');cfg.enable_stream(cp);pipe.enable_frame_sync()
    cfg.set_frame_aggregate_output_mode(ob.OBFrameAggregateOutputMode.FULL_FRAME_REQUIRE)
    started=False;deadline=time.monotonic()+p['timeoutMs']/1000
    try:
        pipe.start(cfg);started=True;received=0;frames=None
        while received<=p.get('warmupFrames',5):
            remaining=int((deadline-time.monotonic())*1000)
            if remaining<=0:raise TimeoutError('Orbbec 预热/采集超过总时限')
            frames=pipe.wait_for_frames(remaining)
            if frames is None or frames.get_depth_frame() is None or (cp is not None and frames.get_color_frame() is None):continue
            received+=1
        while True:
            check_profile(frames.get_depth_frame().get_stream_profile().as_video_stream_profile(),w,h,fps,ob.OBFormat.Y16,'深度')
            if cp is not None:check_profile(frames.get_color_frame().get_stream_profile().as_video_stream_profile(),cw,ch,fps,fmt,'彩色')
            image,stats,raw,cloud=process_frames(frames,p,ob)
            meta=dict(device=info,timestamp=raw['timestamp'],pixelFormat='BGR8',sourceBits=8 if cp is not None else 16,outputBits=8,depthBits=16,
                      imageKind='color-aligned-to-depth' if cp is not None else 'depth-preview',applied=[],**stats)
            yield image,meta,raw,cloud
            deadline=time.monotonic()+p['timeoutMs']/1000
            while True:
                remaining=int((deadline-time.monotonic())*1000)
                if remaining<=0:raise TimeoutError('Orbbec 连续采集超时')
                frames=pipe.wait_for_frames(remaining)
                if frames is not None and frames.get_depth_frame() is not None and (cp is None or frames.get_color_frame() is not None):break
    finally:
        if started:pipe.stop()


def acquire(p,inspect=False,ob=None):
    frames=acquire_frames(p,inspect,ob)
    try:
        return next(frames)
    finally:
        frames.close()
