"""Single-frame camera adapters. Native SDK work runs in a disposable process."""
import base64
import hashlib
import math
import os
import platform
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np
try:
    from . import depth_adapter as rgbd
    from . import orbbec_adapter as orbbec
    from . import gentl3d
    from .gentl_compat import hikrobot_transport
except ImportError:
    import depth_adapter as rgbd
    import orbbec_adapter as orbbec
    import gentl3d
    from gentl_compat import hikrobot_transport

MAX_PIXELS = 16_000_000
FEATURES = ('DeviceVendorName', 'DeviceModelName', 'DeviceSerialNumber', 'Width', 'Height',
            'OffsetX', 'OffsetY', 'PixelFormat', 'ExposureAuto', 'ExposureTime', 'GainAuto',
            'Gain', 'AcquisitionMode', 'TriggerSelector', 'TriggerMode', 'TriggerSource',
            'ComponentSelector', 'ComponentEnable', 'GenDCStreamingMode', 'Scan3dOutputMode',
            'Scan3dCoordinateSystem', 'Scan3dDistanceUnit', 'Scan3dCoordinateSystemReference',
            'Scan3dCoordinateSelector', 'Scan3dCoordinateScale', 'Scan3dCoordinateOffset',
            'Scan3dInvalidDataFlag', 'Scan3dInvalidDataValue')


def number(value, label, low, high, integer=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(label + ' 必须为有限数值')
    if not low <= value <= high or (integer and int(value) != value):
        raise ValueError(label + ' 超出允许范围')
    return int(value) if integer else float(value)


def config(params):
    if not isinstance(params, dict):
        raise ValueError('相机参数必须为字段集合')
    p = dict(params)
    if p.get('driver') not in ('simulator', 'uvc', 'gentl', 'realsense', 'orbbec', 'rgbd_simulator'):
        raise ValueError('请选择支持的 2D 或深度相机驱动')
    # Soft/UI session chrome from camera_backends.connect_params (wave154–156).
    # Accepted for 2D Soft/UVC/GenTL so camera/session/start is not rejected.
    session_ui = {
        'backendKind', 'keepConnectionOpen', 'openClosePerGrab',
        'exposureUs', 'gainDb', 'sessionPersist', 'continuousLive', 'reconnectResilient',
    }
    allowed = {'driver', 'deviceId', 'timeoutMs', 'trigger', 'width', 'height'} | session_ui | {
        'simulator': set(), 'uvc': {'fps', 'warmupFrames'},
        'gentl': {'providerId', 'exposureTime', 'gain', 'pixelFormat', 'triggerSource', 'dataMode',
                  'acquisitionFrameRate', 'previewBufferCount',
                  'configure3d','coordinateFormat','rangeComponent','intensityComponent','confidenceComponent',
                  'confidenceThreshold','pointStride','alignedComponents'},
        'realsense': {'fps','warmupFrames','enableColor','colorWidth','colorHeight','pointStride','minDepth','maxDepth'},
        'orbbec': {'fps','warmupFrames','enableColor','colorWidth','colorHeight','colorFormat','pointStride','minDepth','maxDepth','discoverNetwork'},
        'rgbd_simulator': {'pointStride','minDepth','maxDepth'},
    }[p['driver']]
    # Empty providerId is sent by the device-list UI for non-GenTL devices.
    if p.get('providerId') == '' and p['driver'] != 'gentl':
        del p['providerId']
    if set(p) - allowed:
        raise ValueError('当前驱动不支持参数：' + ', '.join(sorted(set(p) - allowed)))
    # Map soft µs/dB controls onto GenTL native names when only soft keys are present.
    if p['driver'] == 'gentl':
        if 'exposureTime' not in p and 'exposureUs' in p:
            p['exposureTime'] = p['exposureUs']
        if 'gain' not in p and 'gainDb' in p:
            p['gain'] = p['gainDb']
    p['timeoutMs'] = number(p.get('timeoutMs', 5000), '采集超时', 100, 30000, True)
    for name, bounds in {'width': (16, 8192), 'height': (16, 8192), 'fps': (1, 240),
                         'exposureTime': (1, 10_000_000), 'gain': (0, 1000)}.items():
        if name in p:
            p[name] = number(p[name], name, *bounds, name in ('width', 'height'))
    if p.get('width', 640) * p.get('height', 400) > MAX_PIXELS:
        raise ValueError('图像超过 1600 万像素')
    p['trigger'] = p.get('trigger', 'freerun')
    if p['trigger'] not in ('freerun', 'software', 'external'):
        raise ValueError('触发模式无效')
    if p['driver'] != 'gentl' and p['trigger'] != 'freerun':
        raise ValueError('软件或外部触发仅适用于 GenTL 相机')
    if p['driver'] == 'uvc' and any(k in p for k in ('exposureTime', 'gain', 'pixelFormat')):
        raise ValueError('UVC 曝光/增益/像素格式语义因驱动而异，本适配器不设置这些参数')
    for name in ('deviceId', 'providerId', 'pixelFormat', 'triggerSource'):
        if name in p and (not isinstance(p[name], str) or len(p[name]) > 2048 or '\x00' in p[name]):
            raise ValueError(name + ' 无效')
    if p['driver'] in ('realsense','orbbec','rgbd_simulator'):
        for name, default, low, high, integer in [('pointStride',1 if p['driver']=='rgbd_simulator' else 4,1,64,True),
                                                 ('minDepth',.1,.001,100,False),('maxDepth',5.,.002,100,False)]:
            p[name]=number(p.get(name,default),name,low,high,integer)
        if p['minDepth'] >= p['maxDepth']:
            raise ValueError('最大深度必须大于最小深度（米）')
        if p.get('width',640)*p.get('height',480)>rgbd.MAX_DEPTH_PIXELS:
            raise ValueError('深度帧最多 400 万像素')
    if p['driver'] in ('realsense','orbbec'):
        for name, default, low, high in [('warmupFrames',5,0,30),('fps',30,1,240),('colorWidth',640,16,4096),('colorHeight',480,16,4096)]:
            p[name]=number(p.get(name,default),name,low,high,True)
        if type(p.get('enableColor',True)) is not bool:
            raise ValueError('彩色流开关必须为布尔值')
        if p.get('enableColor',True) and p['colorWidth']*p['colorHeight']>MAX_PIXELS:
            raise ValueError('彩色帧超过 1600 万像素')
    if p['driver']=='orbbec':
        if type(p.get('discoverNetwork',False)) is not bool:raise ValueError('网络设备发现开关必须为布尔值')
        if p.get('colorFormat','RGB') not in orbbec.COLOR_FORMATS:raise ValueError('Orbbec 彩色格式不支持')
    if p['driver']=='gentl':
        if p.get('dataMode','image') not in ('image','pointcloud'):
            raise ValueError('GenTL 输出模式无效')
        if p.get('dataMode')=='pointcloud':
            if 'pixelFormat' in p:raise ValueError('3D 模式请通过 XYZ 像素格式配置 Range 分量')
            if type(p.get('configure3d',True)) is not bool:raise ValueError('配置 3D 输出开关必须为布尔值')
            if type(p.get('alignedComponents',False)) is not bool:raise ValueError('分量对齐确认必须为布尔值')
            if p.get('coordinateFormat',gentl3d.FORMATS[0]) not in gentl3d.FORMATS:raise ValueError('XYZ 像素格式不支持')
            for name,default,low,high in [('pointStride',4,1,64),('rangeComponent',-1,-1,63),
                                         ('intensityComponent',-1,-1,63),('confidenceComponent',-1,-1,63),
                                         ('confidenceThreshold',1,1,65535)]:
                p[name]=number(p.get(name,default),name,low,high,True)
            selected=[p[key] for key in ('rangeComponent','intensityComponent','confidenceComponent') if p[key]>=0]
            if len(selected)!=len(set(selected)):raise ValueError('3D 各分量索引不能重复')
            if any(p[key]>=0 for key in ('intensityComponent','confidenceComponent')) and not p.get('alignedComponents',False):
                raise ValueError('请确认所选亮度/置信度分量与 XYZ 栅格逐像素对应')
        # Continuous freerun at the device max (often ~90 FPS) with Harvesters'
        # default 3 buffers overruns when JPEG/UI consume slower → complete=True
        # frames that are only a top hairline of pixels (rest zeros). Default ≤10 FPS
        # so a 100 ms session_worker interval never lags the GenTL ring; callers /
        # session_worker may raise it explicitly when they pull faster.
        if 'acquisitionFrameRate' in p:
            p['acquisitionFrameRate'] = number(p['acquisitionFrameRate'], 'acquisitionFrameRate', 1, 240, False)
        else:
            p['acquisitionFrameRate'] = 10.0
        if 'previewBufferCount' in p:
            p['previewBufferCount'] = number(p['previewBufferCount'], 'previewBufferCount', 3, 64, True)
        else:
            p['previewBufferCount'] = 16
    return p


def providers():
    result = []
    for raw in os.environ.get('SIEANS_GENTL_CTI', '').split(os.pathsep):
        if not raw.strip():
            continue
        path = Path(raw.strip()).expanduser().resolve()
        key = hashlib.sha256(os.path.normcase(str(path)).encode()).hexdigest()[:20]
        if not any(x['id'] == key for x in result):
            result.append(dict(id=key, name=path.name, path=str(path), available=path.is_file() and path.suffix.lower() == '.cti'))
    return result


def harvester(provider_id):
    from harvesters.core import Harvester
    match = next((x for x in providers() if x['id'] == provider_id), None)
    if not match or not match['available']:
        raise ValueError('GenTL 驱动未配置或不存在；请在服务器设置 SIEANS_GENTL_CTI')
    h = Harvester()
    try:
        h.add_file(match['path'], check_existence=True, check_validity=True)
        h.update()
        return h
    except Exception:
        h.reset()
        raise


def uvc_devices():
    from cv2_enumerate_cameras import enumerate_cameras
    backend = cv2.CAP_DSHOW if platform.system() == 'Windows' else cv2.CAP_V4L2
    if platform.system() not in ('Windows', 'Linux'):
        raise ValueError('UVC 当前适配 Windows DirectShow 和 Linux V4L2')
    # Enumeration uses OS device metadata; it does not open a capture stream.
    return [dict(deviceId=c.path, name=c.name, index=c.index, backend=c.backend,
                 vendorId=c.vid, productId=c.pid, driver='uvc')
            for c in enumerate_cameras(backend) if c.path]


def gentl_devices(h):
    rows = []
    for d in h.device_info_list:
        def get(key):
            try:
                return str(getattr(d, key))
            except Exception:
                return ''
        rows.append(dict(deviceId=get('id_'), name=get('display_name'), vendor=get('vendor'),
                         model=get('model'), serial=get('serial_number'), transport=get('tl_type'), driver='gentl'))
    return rows


@contextmanager
def gentl_session(provider_id):
    match = next((item for item in providers() if item['id'] == provider_id), None)
    with hikrobot_transport(match['path'] if match and match['available'] else None):
        h = harvester(provider_id)
        try:
            yield h
        finally:
            h.reset()


def list_devices(p):
    if p['driver']=='orbbec':
        return orbbec.devices(p)
    if p['driver']=='realsense':
        return rgbd.devices()
    if p['driver']=='rgbd_simulator':
        return rgbd.simulated_devices()
    if p['driver'] == 'simulator':
        return [dict(deviceId='synthetic-parts', name='合成零件相机（模拟）', driver='simulator', serial='SIM-CAMERA-001')]
    if p['driver'] == 'uvc':
        return uvc_devices()
    with gentl_session(p.get('providerId')) as h:
        return gentl_devices(h)


def feature_rows(node_map):
    from genicam.genapi import is_readable, is_writable
    result = []
    for name in FEATURES:
        try:
            node = getattr(node_map, name)
            if not is_readable(node):
                continue
            value=node.value
            if isinstance(value,float) and not math.isfinite(value):value=str(value)
            row = dict(name=name, value=value, writable=is_writable(node))
            for attr, key in [('min', 'minimum'), ('max', 'maximum'), ('inc', 'increment'), ('symbolics', 'choices')]:
                try:
                    value = getattr(node, attr)
                    if isinstance(value, tuple):
                        value = list(value)
                    if not isinstance(value, float) or math.isfinite(value):
                        row[key] = value
                except Exception:
                    pass
            result.append(row)
        except Exception:
            continue
    return result


def set_feature(node_map, name, value, applied):
    from genicam.genapi import is_writable
    try:
        node = getattr(node_map, name)
        if not is_writable(node):
            raise ValueError('节点不可写')
        node.value = value
        actual = node.value
        applied.append(dict(name=name, requested=value, actual=actual))
        equal = math.isclose(actual, value, rel_tol=1e-5, abs_tol=1e-6) if isinstance(value, float) else actual == value
        if not equal:
            raise ValueError('设备回读值与请求不一致')
    except Exception as error:
        raise ValueError('相机参数 ' + name + ' 设置失败：' + str(error)) from error



def gentl_frame_looks_incomplete(image):
    """Detect classic USB/GenTL overrun: complete=True but only a top strip is live."""
    if image is None or not hasattr(image, 'shape') or image.size == 0:
        return True
    plane = image if image.ndim == 2 else image.mean(axis=2)
    h = int(plane.shape[0])
    if h < 64:
        return False
    band = max(8, h // 16)
    top = float(plane[:band].mean())
    bot = float(plane[-band:].mean())
    active = float((plane.mean(axis=1) > 5.0).mean())
    return bot < 1.5 and top > 5.0 and active < 0.35


def pixels(component):
    """Copy SDK memory before re-queueing. Output is explicit 8-bit gray/BGR."""
    w, h = int(component.width), int(component.height)
    if w < 1 or h < 1 or w * h > MAX_PIXELS:
        raise ValueError('相机图像尺寸无效或超过 1600 万像素')
    fmt = str(component.data_format)
    data = component.data
    bits = 8
    if fmt in ('Mono8', 'Mono10', 'Mono12', 'Mono16'):
        bits = int(fmt[4:])
        dtype = np.uint8 if bits == 8 else np.uint16
        if data.dtype != dtype or data.size != w * h:
            raise ValueError('灰度图缓冲区类型/长度与像素格式不一致')
        image = data.reshape(h, w).copy()
        if bits > 8:
            if image.max() > (1 << bits) - 1:
                raise ValueError('灰度值超出声明的位深')
            image = (image >> (bits - 8)).astype(np.uint8)
    elif fmt in ('RGB8', 'BGR8', 'RGBA8', 'BGRA8'):
        channels = 4 if 'A' in fmt else 3
        if data.dtype != np.uint8 or data.size != w * h * channels:
            raise ValueError('彩色图缓冲区类型/长度不一致')
        image = data.reshape(h, w, channels).copy()
        code = {'RGB8': cv2.COLOR_RGB2BGR, 'RGBA8': cv2.COLOR_RGBA2BGR, 'BGRA8': cv2.COLOR_BGRA2BGR}.get(fmt)
        if code is not None:
            image = cv2.cvtColor(image, code)
    elif fmt in ('BayerRG8', 'BayerBG8', 'BayerGR8', 'BayerGB8'):
        if data.dtype != np.uint8 or data.size != w * h or min(w, h) < 4:
            raise ValueError('Bayer 图缓冲区类型/尺寸不一致')
        code = {'BayerRG8': cv2.COLOR_BayerRGGB2BGR, 'BayerBG8': cv2.COLOR_BayerBGGR2BGR,
                'BayerGR8': cv2.COLOR_BayerGRBG2BGR, 'BayerGB8': cv2.COLOR_BayerGBRG2BGR}[fmt]
        image = cv2.cvtColor(data.reshape(h, w), code)
    else:
        raise ValueError('暂不支持像素格式 ' + fmt + '；请选 Mono8 / RGB8 / BGR8 / Bayer8 或非打包 Mono10/12/16')
    return image, dict(pixelFormat=fmt, sourceBits=bits, outputBits=8,
                       conversion='固定满量程右移到 8 位' if bits > 8 else '保持灰度或转 BGR8')


def prepare_trigger(node_map, trigger, applied):
    choices = node_map.TriggerSelector.symbolics
    # This USB model exposes only FrameBurstStart. Free-running acquisition
    # merely disables it; a burst must never be silently used as a frame trigger.
    burst_only = isinstance(choices, (tuple, list)) and tuple(choices) == ('FrameBurstStart',)
    if burst_only and trigger != 'freerun':
        raise ValueError('该相机仅提供帧突发触发；当前适配器支持自由采集，尚不支持该型号的软件/外部突发触发')
    set_feature(node_map, 'TriggerMode', 'Off', applied)
    if not burst_only:
        set_feature(node_map, 'TriggerSelector', 'FrameStart', applied)
        set_feature(node_map, 'TriggerMode', 'Off', applied)



def _gentl_cti_path(provider_id):
    match = next((item for item in providers() if item['id'] == provider_id), None)
    if match and match.get('available'):
        return match['path']
    # Fall back to env / default CTI list used by C++ split_cti.
    return os.environ.get('SIEANS_GENTL_CTI', '')


def _gentl_prefer_native(p, inspect=False):
    """Prefer C++ GenTLCapture for 2D freerun; keep harvesters for 3D/inspect/trigger."""
    if inspect or p.get('dataMode') == 'pointcloud':
        return False
    if p.get('trigger', 'freerun') != 'freerun':
        return False
    try:
        from vision import native_bridge
        return bool(native_bridge.gentl_acquire_preferred())
    except Exception as exc:
        # Soft: missing vision package when adapter runs as cameras/ cwd script.
        try:
            import sys
            root = str(Path(__file__).resolve().parents[1])
            if root not in sys.path:
                sys.path.insert(0, root)
            from vision import native_bridge
            return bool(native_bridge.gentl_acquire_preferred())
        except Exception as exc2:
            sys.stderr.write(f'[sieans] native GenTL prefer check failed: {exc2}\n')
            return False


def acquire_gentl_frames_native(p, inspect=False):
    """Continuous 2D freerun via sieans_native.GenTLCapture (Hikrobot MvCameraControl).

    Preserves hang mitigations: LatestImagesOnly (drop-old), acquisitionFrameRate
    cap, previewBufferCount, strip-frame skip, and session_worker paced encode.
    """
    if inspect:
        raise ValueError('native GenTL inspect 请走 harvesters 路径')
    if p.get('dataMode') == 'pointcloud':
        raise ValueError('native GenTL 暂不支持点云；请用 harvesters/gentl3d')
    import sys
    root = str(Path(__file__).resolve().parents[1])
    pydeps = str(Path(root) / '.pydeps')
    for path in (pydeps, root):
        if path not in sys.path:
            sys.path.insert(0, path)
    import sieans_native as native  # type: ignore
    if not native.gentl_available():
        raise RuntimeError('sieans_native GenTL unavailable')

    cti = _gentl_cti_path(p.get('providerId'))
    devices = list(native.GenTLCapture.enumerate(cti or ''))
    device_id = (p.get('deviceId') or '').strip()
    matches = []
    if not device_id:
        matches = list(devices)
    else:
        for d in devices:
            did = d.get('id') or ''
            serial = d.get('serial') or ''
            model = d.get('model') or ''
            vendor = d.get('vendor') or ''
            display = f'{vendor} {model} ({serial})'.strip()
            if device_id in (did, serial, display) or did == device_id:
                matches.append(d)
        if not matches:
            matches = [d for d in devices
                       if (d.get('serial') and d.get('serial') in device_id)
                       or (d.get('id') and device_id in d.get('id'))]
    if len(matches) != 1:
        raise ValueError('设备不存在或标识不唯一，请重新枚举并选择')
    dev = matches[0]
    device_row = dict(
        deviceId=dev.get('id') or device_id,
        name=dev.get('id') or dev.get('model') or '',
        vendor=dev.get('vendor') or '',
        model=dev.get('model') or '',
        serial=dev.get('serial') or '',
        transport='U3V' if 'U3V' in (dev.get('cti_path') or '') else 'GEV',
        driver='gentl',
    )
    applied = [dict(name='acquireBackend', actual='sieans_native')]
    cap = native.GenTLCapture()
    try:
        cap.open(dev.get('id') or device_id, dev.get('cti_path') or cti or '')
        if 'exposureTime' in p:
            try:
                cap.set_exposure_us(float(p['exposureTime']))
                applied.append(dict(name='ExposureTime', requested=p['exposureTime'], actual=p['exposureTime']))
            except Exception as err:
                applied.append(dict(name='ExposureTime', error=str(err)[:200]))
        if 'gain' in p:
            try:
                cap.set_gain_db(float(p['gain']))
                applied.append(dict(name='Gain', requested=p['gain'], actual=p['gain']))
            except Exception as err:
                applied.append(dict(name='Gain', error=str(err)[:200]))
        fps = float(p.get('acquisitionFrameRate', 10.0))
        bufs = int(p.get('previewBufferCount', 16))
        try:
            cap.configure_freerun(fps=fps, buffer_count=bufs)
            applied.append(dict(name='AcquisitionFrameRate', requested=fps, actual=fps))
            applied.append(dict(name='previewBufferCount', requested=bufs, actual=bufs))
            applied.append(dict(name='GrabStrategy', actual='LatestImagesOnly'))
        except Exception as err:
            applied.append(dict(name='configure_freerun', error=str(err)[:200]))
        cap.start()
        sys.stderr.write(
            f'[sieans] GenTL acquire backend=sieans_native device={device_row["deviceId"]} '
            f'fps={fps} buffers={bufs}\n'
        )
        sys.stderr.flush()
        try:
            marker = Path('/tmp/sieans-gentl-acquire-backend.txt')
            marker.write_text(
                f'backend=sieans_native\ndevice={device_row["deviceId"]}\nfps={fps}\n',
                encoding='utf-8',
            )
        except Exception:
            pass
        strip_skips = 0
        timeout_ms = int(p.get('timeoutMs', 5000))
        while True:
            frame = cap.grab(timeout_ms)
            received_at = datetime.now(timezone.utc).isoformat()
            image = frame['image']
            # numpy view from pybind — copy so FreeImageBuffer-equivalent is safe
            image = np.asarray(image).copy()
            if gentl_frame_looks_incomplete(image):
                strip_skips += 1
                if strip_skips > 30:
                    raise ValueError('相机连续返回不完整条带帧，请降低帧率或检查 USB 带宽')
                continue
            strip_skips = 0
            info = dict(
                device=device_row,
                applied=applied,
                timestamp=received_at,
                pixelFormat=frame.get('pixel_format') or 'Mono8',
                sourceBits=8,
                outputBits=8,
                conversion='sieans_native GenTLCapture',
                acquireBackend='sieans_native',
                frameId=int(frame.get('frame_id') or 0),
            )
            try:
                info['deviceTimestampNs'] = str(int(frame.get('timestamp_ns') or 0))
            except Exception:
                pass
            yield image, info
    finally:
        try:
            cap.close()
        except Exception:
            pass


def acquire_gentl_frames_harvesters(p, inspect=False):
    with gentl_session(p.get('providerId')) as h:
        matches = [d for d in gentl_devices(h) if d['deviceId'] == p.get('deviceId')]
        if len(matches) != 1:
            raise ValueError('设备不存在或标识不唯一，请重新枚举并选择')
        with h.create({'id_': p['deviceId']}) as ia:
            node_map = ia.remote_device.node_map
            if inspect:
                yield dict(device=matches[0], items=feature_rows(node_map))
                return
            applied = []
            is_3d = p.get('dataMode') == 'pointcloud'
            # Disable trigger before changing selector and acquisition settings.
            prepare_trigger(node_map, p['trigger'], applied)
            set_feature(node_map, 'AcquisitionMode', 'Continuous', applied)
            if is_3d:
                set_feature(node_map,'ComponentSelector','Range',applied)
            for key, name in [('width', 'Width'), ('height', 'Height'), ('pixelFormat', 'PixelFormat'),
                              ('exposureTime', 'ExposureTime'), ('gain', 'Gain')]:
                if key in p:
                    if key in ('exposureTime', 'gain'):
                        set_feature(node_map, 'ExposureAuto' if key == 'exposureTime' else 'GainAuto', 'Off', applied)
                    set_feature(node_map, name, p[key], applied)
            calibration = gentl3d.configure(node_map,p,applied,set_feature) if is_3d else None
            if p['trigger'] != 'freerun':
                source = 'Software' if p['trigger'] == 'software' else p.get('triggerSource', 'Line0')
                if p['trigger'] == 'external' and source not in ('Line0', 'Line1', 'Line2', 'Line3'):
                    raise ValueError('外部触发源必须为 Line0–Line3')
                set_feature(node_map, 'TriggerSource', source, applied)
                set_feature(node_map, 'TriggerMode', 'On', applied)
            # Cap device freerun so USB/GenTL buffers are not overwritten mid-frame
            # while the host encodes JPEG / session_worker paces pulls. Default 10 FPS
            # matches the 100 ms session interval; more buffers cover jitter.
            if p['trigger'] == 'freerun' and not is_3d:
                try:
                    from genicam.genapi import is_writable
                    if hasattr(node_map, 'AcquisitionFrameRateEnable') and is_writable(node_map.AcquisitionFrameRateEnable):
                        set_feature(node_map, 'AcquisitionFrameRateEnable', True, applied)
                    if hasattr(node_map, 'AcquisitionFrameRate') and is_writable(node_map.AcquisitionFrameRate):
                        set_feature(node_map, 'AcquisitionFrameRate', float(p.get('acquisitionFrameRate', 10.0)), applied)
                except Exception as rate_err:
                    # Non-fatal: still try more buffers below.
                    applied.append(dict(name='AcquisitionFrameRate', error=str(rate_err)[:200]))
                try:
                    want = int(p.get('previewBufferCount', 16))
                    if getattr(ia, 'num_buffers', 0) < want:
                        ia.num_buffers = want
                except Exception:
                    pass
            ia.start()
            try:
                strip_skips = 0
                while True:
                    if p['trigger'] == 'software':
                        node_map.TriggerSoftware.execute()
                    with ia.fetch(timeout=p['timeoutMs'] / 1000) as buffer:
                        received_at = datetime.now(timezone.utc).isoformat()
                        if not buffer.module.is_complete():
                            raise ValueError('相机返回不完整帧，未交给检测算子')
                        components = buffer.payload.components
                        if is_3d:
                            image,info,depth,cloud = gentl3d.capture(components,p,calibration)
                        elif len(components) != 1:
                            raise ValueError('多分量/3D 相机需要专用深度适配器，不能按单幅 2D 图像读取')
                        else:
                            image, info = pixels(components[0])
                            if gentl_frame_looks_incomplete(image):
                                strip_skips += 1
                                if strip_skips > 30:
                                    raise ValueError('相机连续返回不完整条带帧，请降低帧率或检查 USB 带宽')
                                continue
                            strip_skips = 0
                        try:
                            info['deviceTimestampNs'] = str(buffer.timestamp_ns)
                        except Exception:
                            pass
                    result = image, dict(device=matches[0], applied=applied, timestamp=received_at, **info)
                    yield (*result,depth,cloud) if is_3d else result
            finally:
                ia.stop()


def acquire_gentl_frames(p, inspect=False):
    """GenTL frame generator: prefer C++ GenTLCapture for 2D freerun.

    Falls back to harvesters for inspect / 3D / non-freerun / native missing.
    Env: SIEANS_NATIVE / SIEANS_NATIVE_GENTL_ACQUIRE (see vision.native_bridge).
    """
    prefer = _gentl_prefer_native(p, inspect=inspect)
    if prefer:
        try:
            yield from acquire_gentl_frames_native(p, inspect=inspect)
            return
        except Exception as exc:
            import sys
            force = False
            try:
                from vision import native_bridge
                force = native_bridge.native_mode() == 'force'
            except Exception:
                pass
            ov = (os.environ.get('SIEANS_NATIVE_GENTL_ACQUIRE') or '').strip().lower()
            if ov in ('1', 'true', 'on', 'yes', 'native', 'force', 'cpp'):
                force = True
            sys.stderr.write(
                f'[sieans] native GenTL acquire failed'
                f'{" (force)" if force else " → harvesters fallback"}: {exc}\n'
            )
            sys.stderr.flush()
            if force:
                raise
    yield from acquire_gentl_frames_harvesters(p, inspect=inspect)



def acquire_uvc_frames(p, inspect=False):
    matches = [d for d in uvc_devices() if d['deviceId'] == p.get('deviceId')]
    if len(matches) != 1:
        raise ValueError('USB 设备不存在或标识不唯一，请重新枚举并选择')
    device = matches[0]
    cap = cv2.VideoCapture(device['index'], device['backend'])
    try:
        if not cap.isOpened():
            raise ValueError('USB 相机无法打开，检查权限或设备占用')
        properties = [('width', cv2.CAP_PROP_FRAME_WIDTH), ('height', cv2.CAP_PROP_FRAME_HEIGHT), ('fps', cv2.CAP_PROP_FPS)]
        if inspect:
            rows = []
            for key, prop in properties:
                value = cap.get(prop)
                rows.append(dict(name=key, value=value if math.isfinite(value) else None, writable='依驱动支持'))
            yield dict(device=device, items=rows)
            return
        applied = []
        # Set size pair before readback: some drivers negotiate after both writes.
        for key, prop in properties:
            if key in p and not cap.set(prop, p[key]):
                raise ValueError('USB 驱动拒绝设置 ' + key)
        for key, prop in properties:
            if key in p:
                actual = cap.get(prop)
                applied.append(dict(name=key, requested=p[key], actual=actual))
                if not math.isfinite(actual) or not math.isclose(actual, p[key], rel_tol=.001, abs_tol=.01):
                    raise ValueError('USB 驱动回读 ' + key + ' 与请求不一致，请使用设备支持的参数')
        # Explicit warmup, bounded by outer process timeout even if native read blocks.
        image = None
        for _ in range(number(p.get('warmupFrames', 3), '预热帧数', 0, 30, True) + 1):
            ok, image = cap.read()
            if not ok or image is None:
                raise ValueError('USB 相机未返回有效图像')
        while True:
            yield image, dict(device=device, applied=applied, pixelFormat='BGR8', sourceBits=8, outputBits=8,
                               timestamp=datetime.now(timezone.utc).isoformat())
            ok, image = cap.read()
            if not ok or image is None:
                raise ValueError('USB 相机未返回有效图像')
    finally:
        cap.release()


def first_frame(generator):
    try:
        return next(generator)
    finally:
        generator.close()


def acquire_gentl(p, inspect=False):
    return first_frame(acquire_gentl_frames(p, inspect))


def acquire_uvc(p, inspect=False):
    return first_frame(acquire_uvc_frames(p, inspect))


def simulate(p, inspect=False):
    if p.get('deviceId', 'synthetic-parts') != 'synthetic-parts':
        raise ValueError('模拟设备不存在')
    device = list_devices(p)[0]
    if inspect:
        return dict(device=device, items=[dict(name='Width', value=640, writable=True), dict(name='Height', value=400, writable=True)])
    w, h = p.get('width', 640), p.get('height', 400)
    image = np.zeros((h, w, 3), np.uint8)
    cv2.rectangle(image, (w//10, h//8), (w*4//10, h*4//10), (255, 255, 255), -1)
    cv2.circle(image, (w*7//10, h//4), max(2, min(w, h)//9), (255, 255, 255), -1)
    cv2.line(image, (w//8, h*3//4), (w*7//8, h*3//4), (255, 255, 255), max(1, h//80))
    return image, dict(device=device, pixelFormat='BGR8', sourceBits=8, outputBits=8, applied=[])


def run(request):
    started = time.monotonic()
    operation = request.get('operation')
    if operation == 'camera_providers':
        from importlib.metadata import version, PackageNotFoundError
        def installed(name):
            try:
                return version(name)
            except PackageNotFoundError:
                return None
        return dict(result=dict(items=[{k: v for k, v in item.items() if k != 'path'} for item in providers()],
                                harvesters=installed('harvesters'), genicam=installed('genicam'), realsense=installed('pyrealsense2'), orbbec=installed('pyorbbecsdk2'), platform=platform.system()))
    p = config(request.get('params'))
    if operation == 'camera_list':
        return dict(result=dict(items=list_devices(p), simulated=p['driver'] in ('simulator','rgbd_simulator')))
    if operation not in ('camera_capture', 'camera_inspect'):
        raise ValueError('未知相机操作')
    result = {'simulator': simulate, 'uvc': acquire_uvc, 'gentl': acquire_gentl, 'realsense': rgbd.acquire, 'orbbec': orbbec.acquire, 'rgbd_simulator': rgbd.simulate}[p['driver']](p, operation == 'camera_inspect')
    if operation == 'camera_inspect':
        return dict(result={**result, 'simulated': p['driver'] in ('simulator','rgbd_simulator')})
    return pack_frame(result, p, started)


def pack_frame(result, p, started):
    image, info = result[:2]
    depth, cloud = result[2:] if len(result)==4 else (None,None)
    info.setdefault('timestamp', datetime.now(timezone.utc).isoformat())
    if image.dtype != np.uint8 or image.ndim not in (2, 3) or image.shape[0] * image.shape[1] > MAX_PIXELS:
        raise ValueError('相机帧必须为不超过 1600 万像素的 8 位图像')
    # Mono8/16→BGR so Qt QPixmap / 全局图像 always paint a visible full-frame RGB PNG
    # (grayscale PNG is valid but some preview paths showed a black 1:1 crop).
    if image.ndim == 2:
        image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    # JPEG for continuous live: Mono8→BGR PNG was ~2MB/frame and ~24ms QPixmap
    # decode on the Qt UI thread (GNOME「python3无响应」). JPEG ~0.2MB / ~7ms.
    ok, encoded = cv2.imencode('.jpg', image, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
    if not ok or encoded.size > 12_000_000:
        raise ValueError('相机帧编码失败或超过 12 MB')
    result_meta = dict(**info, driver=p['driver'], width=image.shape[1], height=image.shape[0],
                       timestampSource='host-receive', previewCodec='jpeg80',
                       simulated=p['driver'] in ('simulator','rgbd_simulator'), trigger=p['trigger'])
    if 'acquireBackend' not in result_meta:
        result_meta['acquireBackend'] = (
            (info.get('acquireBackend') if isinstance(info, dict) else None)
            or ('harvesters' if p['driver'] == 'gentl' else p['driver'])
        )
    return dict(annotatedImage='data:image/jpeg;base64,' + base64.b64encode(encoded).decode('ascii'), cloud=cloud, depth=depth,
                result=result_meta, elapsedMs=round((time.monotonic()-started)*1000, 2))


def capture_frames(params, encode_flag=None):
    """Yield packed frames. If encode_flag is a dict with on=False, drain only
    (no JPEG/base64) so idle freerun does not burn encode CPU (t245u)."""
    p = config(params)
    driver = p['driver']
    def _encode_on():
        return encode_flag is None or bool(encode_flag.get('on', True))
    if driver in ('simulator', 'rgbd_simulator'):
        method = simulate if driver == 'simulator' else rgbd.simulate
        while True:
            started = time.monotonic()
            if _encode_on():
                yield pack_frame(method(p), p, started)
            else:
                method(p)
                yield None
    else:
        method = {'uvc': acquire_uvc_frames, 'gentl': acquire_gentl_frames,
                  'realsense': rgbd.acquire_frames, 'orbbec': orbbec.acquire_frames}[driver]
        frames = method(p)
        try:
            while True:
                started = time.monotonic()
                raw = next(frames)
                if _encode_on():
                    yield pack_frame(raw, p, started)
                else:
                    yield None
        finally:
            frames.close()
