"""Pluggable camera acquisition backends — Soft / UVC / GenTL live (wave153–154).

wave153: Soft / UVC / GenTL pluggable shell + persistent session contract.
wave154: UVC real grab + continuous live; GenTL producer load/enumerate/open/grab
wave156: soft exposure/gain/trigger · multi-device picker polish · last-device persist · reconnect
wave157: GenTL LiveSession auto_reconnect + sessionPersist status parity with UVC
         into the same PreviewFrameGate / show_live_frame path.

Real path toward industrial desktop use:
  • soft  — file/sim (no hardware); always available
  • uvc   — OpenCV VideoCapture persistent session (open once, grab many)
  • gentl — GenTL/GigE producer; Hikrobot CTI auto-discover; honest empty devices

No Halcon/CLR, robot vendor SDK, cloud, or TCP productization here.
GenTL does not fake frames — empty device list when producer loaded but no camera.
"""
from __future__ import annotations

import base64
import hashlib
import math
import os
import platform
import time
from pathlib import Path
from typing import Any, Callable

# Operator-facing kinds (stable ids used by camera_manager / image_source / chrome).
BACKEND_SOFT = 'soft'
BACKEND_UVC = 'uvc'
BACKEND_GENTL = 'gentl'

BACKEND_KINDS = (BACKEND_SOFT, BACKEND_UVC, BACKEND_GENTL)

BACKEND_LABELS = {
    BACKEND_SOFT: '软模拟 Soft',
    BACKEND_UVC: 'USB UVC',
    BACKEND_GENTL: 'GenTL / GigE',
}

# Map UI kind → cameras/adapter driver id used by session + capture RPC.
KIND_TO_DRIVER = {
    BACKEND_SOFT: 'simulator',
    BACKEND_UVC: 'uvc',
    BACKEND_GENTL: 'gentl',
}

DRIVER_TO_KIND = {
    'simulator': BACKEND_SOFT,
    'rgbd_simulator': BACKEND_SOFT,
    'file': BACKEND_SOFT,
    'local': BACKEND_SOFT,
    'uvc': BACKEND_UVC,
    'gentl': BACKEND_GENTL,
    'session': BACKEND_UVC,  # live session is real-path; refined by nested driver
}

# Persistent session contract (do not open/close VideoCapture every grab).
SESSION_PERSIST = dict(
    keepConnectionOpen=True,
    openClosePerGrab=False,
    reuseAcrossFrames=True,
    softFallbackWhenNoDevice=True,
    note='连续会话保持打开；单帧抓取走 session 缓存，不每帧开关设备',
)

# Well-known Hikrobot / MVS CTI locations (Linux + Windows) for auto-discover.
_DEFAULT_CTI_CANDIDATES = (
    '/opt/MVS/lib/64/MvProducerU3V.cti',
    '/opt/MVS/lib/64/MvProducerGEV.cti',
    '/opt/MVS/lib/32/MvProducerU3V.cti',
    '/opt/MVS/lib/32/MvProducerGEV.cti',
    r'C:\Program Files (x86)\Common Files\MVS\Runtime\Win64_x64\MvProducerU3V.cti',
    r'C:\Program Files (x86)\Common Files\MVS\Runtime\Win64_x64\MvProducerGEV.cti',
)


def kind_of_driver(driver: str | None, *, nested: dict | None = None) -> str:
    """Resolve Soft/UVC/GenTL kind from driver (+ optional nested session params)."""
    d = str(driver or '').strip().lower()
    if d == 'session' and isinstance(nested, dict):
        inner = nested.get('params') if isinstance(nested.get('params'), dict) else nested
        if isinstance(inner, dict):
            inner_d = str(inner.get('driver') or '').strip().lower()
            if inner_d in DRIVER_TO_KIND:
                return DRIVER_TO_KIND[inner_d]
    return DRIVER_TO_KIND.get(d, BACKEND_SOFT if not d else BACKEND_UVC)


def driver_for_kind(kind: str | None) -> str:
    k = str(kind or BACKEND_SOFT).strip().lower()
    return KIND_TO_DRIVER.get(k, 'simulator')


def label_for_kind(kind: str | None) -> str:
    k = str(kind or '').strip().lower()
    return BACKEND_LABELS.get(k, str(kind or '—'))


def session_persist_flags() -> dict[str, Any]:
    return dict(SESSION_PERSIST)


def _provider_from_path(path: Path) -> dict[str, Any]:
    key = hashlib.sha256(os.path.normcase(str(path)).encode()).hexdigest()[:20]
    return dict(
        id=key,
        name=path.name,
        path=str(path),
        available=path.is_file() and path.suffix.lower() == '.cti',
        discovered=True,
    )


def discover_gentl_ctis(*, include_env: bool = True) -> list[dict[str, Any]]:
    """List GenTL CTI providers from SIEANS_GENTL_CTI and well-known Hikrobot paths.

    Env wins order; auto-discover fills gaps when env empty or files missing.
    Never downloads SDK; missing paths marked available=False.
    """
    seen: set[str] = set()
    out: list[dict[str, Any]] = []

    def add(raw: str, *, discovered: bool = False) -> None:
        if not raw or not str(raw).strip():
            return
        path = Path(str(raw).strip()).expanduser()
        try:
            path = path.resolve()
        except Exception:
            pass
        key = os.path.normcase(str(path))
        if key in seen:
            return
        seen.add(key)
        row = _provider_from_path(path)
        row['discovered'] = discovered
        out.append(row)

    if include_env:
        for raw in os.environ.get('SIEANS_GENTL_CTI', '').split(os.pathsep):
            add(raw, discovered=False)
    # Auto-discover when env empty OR as supplement of known-good Hikrobot CTIs.
    if not any(p.get('available') for p in out):
        for cand in _DEFAULT_CTI_CANDIDATES:
            add(cand, discovered=True)
    return out


def _encode_bgr_png_data_url(image) -> str:
    """BGR/gray ndarray → data:image/jpeg;base64,… for PreviewFrameGate / show_live_frame.

    Kept name for callers; JPEG keeps continuous-live UI responsive (PNG decode hung Qt).
    """
    import cv2
    import numpy as np
    if image is None:
        raise ValueError('empty image')
    arr = image
    if getattr(arr, 'ndim', 0) == 2:
        arr = cv2.cvtColor(arr, cv2.COLOR_GRAY2BGR)
    if arr.dtype != np.uint8:
        arr = arr.astype(np.uint8)
    ok, encoded = cv2.imencode('.jpg', arr, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
    if not ok:
        raise ValueError('JPEG encode failed')
    return 'data:image/jpeg;base64,' + base64.b64encode(encoded.tobytes()).decode('ascii')


def _soft_synthetic_bgr(width: int = 640, height: int = 400, seq: int = 0):
    """CI-safe soft frame (no hardware)."""
    import cv2
    import numpy as np
    w, h = max(16, int(width)), max(16, int(height))
    image = np.zeros((h, w, 3), np.uint8)
    cv2.rectangle(image, (w // 10, h // 8), (w * 4 // 10, h * 4 // 10), (255, 255, 255), -1)
    cv2.circle(image, (w * 7 // 10, h // 4), max(2, min(w, h) // 9), (255, 255, 255), -1)
    # Moving tick so continuous live proves frame advance without hardware.
    x = (seq * 17) % max(1, w - 20) + 10
    cv2.line(image, (x, h * 3 // 4), (min(w - 10, x + 40), h * 3 // 4), (200, 200, 255), max(1, h // 80))
    return image



# ----- wave156 soft acquisition controls + last-device persist -----
TRIGGER_MODES = ('freerun', 'software', 'line0')
DEFAULT_EXPOSURE_US = 10000
DEFAULT_GAIN_DB = 0.0

_LAST_DEVICE_PATH = Path(__file__).resolve().parents[1] / 'data' / 'camera-last-device.json'


def soft_controls_defaults() -> dict[str, Any]:
    return dict(
        exposureUs=DEFAULT_EXPOSURE_US,
        gainDb=DEFAULT_GAIN_DB,
        trigger='freerun',
        triggerModes=list(TRIGGER_MODES),
        softSimulated=True,
    )


def clamp_exposure_us(v) -> int:
    try:
        n = int(float(v))
    except (TypeError, ValueError):
        n = DEFAULT_EXPOSURE_US
    return max(100, min(10_000_000, n))


def clamp_gain_db(v) -> float:
    try:
        n = float(v)
    except (TypeError, ValueError):
        n = DEFAULT_GAIN_DB
    return max(0.0, min(48.0, n))


def normalize_trigger(v) -> str:
    s = str(v or 'freerun').lower().strip()
    return s if s in TRIGGER_MODES else 'freerun'


def apply_soft_controls_to_bgr(image, *, exposure_us: int = DEFAULT_EXPOSURE_US, gain_db: float = 0.0, seq: int = 0):
    """Simulate exposure/gain on a BGR frame (Soft + UVC soft-fallback)."""
    import cv2
    import numpy as np
    if image is None:
        return image
    img = image.copy()
    # exposure: map 100..1e6 us → brightness scale ~0.35..1.8
    exp = clamp_exposure_us(exposure_us)
    scale = 0.35 + min(1.45, (exp / 10000.0) * 0.65)
    g = clamp_gain_db(gain_db)
    scale *= (1.0 + g / 24.0)
    out = np.clip(img.astype(np.float32) * scale, 0, 255).astype(np.uint8)
    # stamp tiny HUD so live preview proves control took effect
    label = f'exp={exp}us gain={g:.1f}dB #{seq}'
    cv2.putText(out, label, (8, max(16, out.shape[0] - 8)), cv2.FONT_HERSHEY_SIMPLEX,
                max(0.35, min(out.shape[0], out.shape[1]) / 900.0), (40, 220, 40), 1, cv2.LINE_AA)
    return out


def apply_uvc_soft_controls(cap, *, exposure_us: int | None = None, gain_db: float | None = None) -> dict[str, Any]:
    """Best-effort CAP_PROP_EXPOSURE / CAP_PROP_GAIN when backend allows; never raise."""
    applied = dict(exposure=False, gain=False, notes=[])
    if cap is None:
        return applied
    try:
        import cv2
    except Exception as exc:
        applied['notes'].append(str(exc))
        return applied
    if exposure_us is not None:
        exp = clamp_exposure_us(exposure_us)
        try:
            # Many UVC cams want auto-exposure off first; value units vary — soft best-effort.
            if hasattr(cv2, 'CAP_PROP_AUTO_EXPOSURE'):
                cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)  # manual on some backends
            ok = bool(cap.set(cv2.CAP_PROP_EXPOSURE, float(exp) / 1000.0))
            applied['exposure'] = ok
            if not ok:
                applied['notes'].append('CAP_PROP_EXPOSURE rejected')
        except Exception as exc:
            applied['notes'].append(f'exposure: {exc}')
    if gain_db is not None:
        g = clamp_gain_db(gain_db)
        try:
            ok = bool(cap.set(cv2.CAP_PROP_GAIN, float(g)))
            applied['gain'] = ok
            if not ok:
                applied['notes'].append('CAP_PROP_GAIN rejected')
        except Exception as exc:
            applied['notes'].append(f'gain: {exc}')
    return applied


def format_device_picker_label(device: dict | None, *, kind: str = '') -> str:
    """Rich multi-device picker label: name · model · id · kind."""
    d = device if isinstance(device, dict) else {}
    name = d.get('name') or d.get('display_name') or d.get('deviceId') or '?'
    bits = [str(name)]
    model = d.get('model') or d.get('serial') or ''
    if model and str(model) not in bits[0]:
        bits.append(str(model))
    did = d.get('deviceId') or ''
    if did and str(did) not in bits[0]:
        bits.append(str(did)[:24])
    k = kind or d.get('backendKind') or d.get('driver') or ''
    if k:
        bits.append(f'[{k}]')
    idx = d.get('index')
    if idx is not None and str(idx) not in bits[0]:
        bits.append(f'#{idx}')
    return ' · '.join(bits)


def load_last_device() -> dict[str, Any]:
    try:
        import json
        if _LAST_DEVICE_PATH.is_file():
            data = json.loads(_LAST_DEVICE_PATH.read_text(encoding='utf-8'))
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {}


def save_last_device(*, kind: str, device_id: str, label: str = '', extra: dict | None = None) -> dict[str, Any]:
    import json
    row = dict(
        kind=str(kind or ''),
        deviceId=str(device_id or ''),
        label=str(label or ''),
        savedAt=time.strftime('%Y-%m-%dT%H:%M:%S%z'),
    )
    if isinstance(extra, dict):
        row.update({k: v for k, v in extra.items() if k not in row})
    try:
        _LAST_DEVICE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _LAST_DEVICE_PATH.write_text(json.dumps(row, ensure_ascii=False, indent=2), encoding='utf-8')
    except Exception:
        pass
    return row


def pick_last_or_first(devices: list[dict], *, kind: str = '') -> dict | None:
    """Prefer persisted last device when still present; else first."""
    items = list(devices or [])
    if not items:
        return None
    last = load_last_device()
    want = str(last.get('deviceId') or '')
    if want and (not kind or last.get('kind') == kind):
        match = next((d for d in items if str(d.get('deviceId') or '') == want), None)
        if match is not None:
            return match
    return items[0]


class CameraBackend:
    """Minimal pluggable backend surface shared by Soft / UVC / GenTL."""

    kind: str = BACKEND_SOFT
    driver: str = 'simulator'

    def label(self) -> str:
        return label_for_kind(self.kind)

    def capabilities(self) -> dict[str, Any]:
        return dict(
            kind=self.kind,
            driver=self.driver,
            label=self.label(),
            enumerate=True,
            persistentSession=True,
            sessionPersist=session_persist_flags(),
            livePreview=True,
            continuousLive=True,
            requiresHardware=self.kind != BACKEND_SOFT,
            pluggable=True,
            previewPath='PreviewFrameGate+show_live_frame',
            softControls=soft_controls_defaults(),
            exposureGain=True,
            triggerModes=list(TRIGGER_MODES),
            reconnectResilient=True,
        )

    def availability(self) -> dict[str, Any]:
        """Honest status — never invent devices or fake GenTL frames."""
        raise NotImplementedError

    def enumerate_local(self) -> list[dict[str, Any]]:
        """Best-effort local enumerate (no RPC). Soft always returns sim device."""
        raise NotImplementedError

    def list_rpc_params(self, *, provider_id: str = '') -> dict[str, Any]:
        """Params for camera/list RPC."""
        body: dict[str, Any] = {'driver': self.driver}
        if self.kind == BACKEND_GENTL and provider_id:
            body['providerId'] = provider_id
        return body

    def connect_params(self, device_id: str, *, provider_id: str = '', **extra) -> dict[str, Any]:
        """Params for camera/session/start — freerun persistent session + soft controls."""
        params: dict[str, Any] = {
            'driver': self.driver,
            'deviceId': device_id,
            'timeoutMs': int(extra.get('timeoutMs', 5000)),
            'trigger': normalize_trigger(extra.get('trigger', 'freerun')),
            'exposureUs': clamp_exposure_us(extra.get('exposureUs', DEFAULT_EXPOSURE_US)),
            'gainDb': clamp_gain_db(extra.get('gainDb', DEFAULT_GAIN_DB)),
            'sessionPersist': True,
            'keepConnectionOpen': True,
            'openClosePerGrab': False,
            'backendKind': self.kind,
            'continuousLive': True,
            'reconnectResilient': True,
        }
        if self.kind == BACKEND_GENTL:
            params['providerId'] = provider_id or ''
        if self.kind == BACKEND_UVC:
            # Warmup once at open; subsequent frames reuse VideoCapture.
            params.setdefault('warmupFrames', int(extra.get('warmupFrames', 3)))
        if self.kind == BACKEND_SOFT and not device_id:
            params['deviceId'] = 'synthetic-parts'
        params.update({k: v for k, v in extra.items() if k not in params and v is not None})
        return params


class SoftBackend(CameraBackend):
    kind = BACKEND_SOFT
    driver = 'simulator'

    def availability(self) -> dict[str, Any]:
        return dict(
            kind=self.kind,
            available=True,
            status='ready',
            statusZh='软模拟就绪（无需硬件）',
            requiresHardware=False,
            sessionPersist=session_persist_flags(),
            continuousLive=True,
        )

    def enumerate_local(self) -> list[dict[str, Any]]:
        return [dict(
            deviceId='synthetic-parts',
            name='合成零件相机（模拟）',
            driver='simulator',
            serial='SIM-CAMERA-001',
            backendKind=BACKEND_SOFT,
        )]


class UvcBackend(CameraBackend):
    kind = BACKEND_UVC
    driver = 'uvc'

    def availability(self) -> dict[str, Any]:
        sysname = platform.system()
        supported = sysname in ('Windows', 'Linux')
        opencv = False
        enum_mod = False
        try:
            import cv2  # noqa: F401
            opencv = True
        except Exception:
            opencv = False
        try:
            from cv2_enumerate_cameras import enumerate_cameras  # noqa: F401
            enum_mod = True
        except Exception:
            enum_mod = False
        ok = supported and opencv and enum_mod
        if not supported:
            zh = f'UVC 当前仅适配 Windows DirectShow / Linux V4L2（本机 {sysname}）'
            status = 'unsupported'
        elif not opencv:
            zh = 'OpenCV 未装，无法打开 UVC VideoCapture'
            status = 'not_loaded'
        elif not enum_mod:
            zh = 'cv2-enumerate-cameras 未装，无法枚举 UVC'
            status = 'not_loaded'
        else:
            zh = 'UVC / OpenCV VideoCapture 可用（持久会话·连续 live·跨帧保持连接）'
            status = 'ready'
        return dict(
            kind=self.kind,
            available=ok,
            status=status,
            statusZh=zh,
            requiresHardware=True,
            opencv=opencv,
            enumerateModule=enum_mod,
            platform=sysname,
            sessionPersist=session_persist_flags(),
            captureApi='VideoCapture',
            openClosePerGrab=False,
            continuousLive=True,
            softFallbackWhenNoDevice=True,
        )

    def enumerate_local(self) -> list[dict[str, Any]]:
        avail = self.availability()
        if not avail.get('available'):
            return []
        try:
            import cv2
            from cv2_enumerate_cameras import enumerate_cameras
            backend = cv2.CAP_DSHOW if platform.system() == 'Windows' else cv2.CAP_V4L2
            rows = []
            for c in enumerate_cameras(backend):
                if not getattr(c, 'path', None):
                    continue
                rows.append(dict(
                    deviceId=c.path,
                    name=c.name,
                    index=c.index,
                    backend=c.backend,
                    vendorId=getattr(c, 'vid', None),
                    productId=getattr(c, 'pid', None),
                    driver='uvc',
                    backendKind=BACKEND_UVC,
                ))
            return rows
        except Exception:
            return []


class GentlBackend(CameraBackend):
    """GenTL / GigE — load producer, enumerate, open/grab into live preview path.

    Honest unsupported/not_loaded when no producer CTI or harvesters.
    Never yields synthetic frames labeled as GenTL.
    Empty device list is OK when producer loaded but no camera attached.
    """

    kind = BACKEND_GENTL
    driver = 'gentl'

    def availability(self) -> dict[str, Any]:
        providers = discover_gentl_ctis(include_env=True)
        # Prefer cameras.adapter.providers when on PYTHONPATH (matches engine).
        try:
            from cameras.adapter import providers as _providers  # type: ignore
            adapted = list(_providers() or [])
            if adapted:
                # Merge: adapter env list first; keep discovered extras if env empty.
                by_id = {p.get('id'): p for p in providers}
                for p in adapted:
                    by_id[p.get('id')] = {**by_id.get(p.get('id'), {}), **p}
                providers = list(by_id.values()) or adapted
        except Exception:
            pass
        harv = False
        try:
            from importlib.metadata import version, PackageNotFoundError
            try:
                version('harvesters')
                harv = True
            except PackageNotFoundError:
                harv = False
        except Exception:
            harv = False
        available_cti = [p for p in providers if p.get('available')]
        if not harv and not available_cti:
            status, zh = 'not_loaded', 'GenTL 未加载：未装 harvesters，且未配置可用 CTI（SIEANS_GENTL_CTI / 自动发现）'
        elif not harv:
            status, zh = 'not_loaded', 'GenTL 未加载：harvesters 未安装（CTI 已配置亦无法打开 Producer）'
        elif not available_cti:
            status, zh = 'unsupported', 'GenTL Producer 未配置或不存在 — 设置 SIEANS_GENTL_CTI 或安装 MVS 后重启'
        else:
            status, zh = 'ready', f'GenTL Producer 可用（{len(available_cti)} 个 CTI）· 可枚举/开流'
        return dict(
            kind=self.kind,
            available=status == 'ready',
            status=status,
            statusZh=zh,
            requiresHardware=True,
            harvesters=harv,
            providers=[{k: v for k, v in p.items() if k != 'path'} for p in providers],
            availableProviderCount=len(available_cti),
            sessionPersist=session_persist_flags(),
            fakeFrames=False,
            continuousLive=True,
            note='无 Producer 时不伪造 GenTL 帧；Producer 在但无相机 → 空设备列表',
        )

    def enumerate_local(self) -> list[dict[str, Any]]:
        """Load producer + enumerate devices. Empty list if ready but no camera (honest)."""
        avail = self.availability()
        if not avail.get('available'):
            return []
        try:
            return gentl_enumerate_devices()
        except Exception:
            return []


# ---------------------------------------------------------------------------
# wave154: persistent live grab sessions (open once → grab many → PNG for preview)
# ---------------------------------------------------------------------------


class UvcLiveSession:
    """OpenCV VideoCapture held open across frames (continuous live).

    Soft-fallback: when no device / open fails and soft_fallback=True, yields
    synthetic frames labeled soft (never claim UVC).
    """

    def __init__(
        self,
        device_id: str | None = None,
        *,
        warmup_frames: int = 2,
        soft_fallback: bool = True,
        width: int = 0,
        height: int = 0,
        exposure_us: int = DEFAULT_EXPOSURE_US,
        gain_db: float = DEFAULT_GAIN_DB,
        trigger: str = 'freerun',
        auto_reconnect: bool = True,
        reconnect_max: int = 2,
    ):
        self.device_id = device_id or ''
        self.warmup_frames = max(0, int(warmup_frames))
        self.soft_fallback = bool(soft_fallback)
        self.width = int(width or 0)
        self.height = int(height or 0)
        self.exposure_us = clamp_exposure_us(exposure_us)
        self.gain_db = clamp_gain_db(gain_db)
        self.trigger = normalize_trigger(trigger)
        self.auto_reconnect = bool(auto_reconnect)
        self.reconnect_max = max(0, int(reconnect_max))
        self._cap = None
        self._device: dict[str, Any] | None = None
        self._soft = False
        self._seq = 0
        self._opened = False
        self._reconnect_count = 0
        self._controls_applied: dict[str, Any] = {}
        self.backend_kind = BACKEND_UVC

    @property
    def is_open(self) -> bool:
        return bool(self._opened)

    @property
    def is_soft(self) -> bool:
        return bool(self._soft)

    def open(self) -> dict[str, Any]:
        if self._opened:
            return self.status()
        devices = UvcBackend().enumerate_local()
        match = None
        if self.device_id:
            match = next((d for d in devices if d.get('deviceId') == self.device_id), None)
            if match is None and self.device_id.isdigit():
                match = next((d for d in devices if str(d.get('index')) == self.device_id), None)
        if match is None and devices:
            match = devices[0]
            self.device_id = match.get('deviceId') or self.device_id
        if match is None:
            if not self.soft_fallback:
                raise RuntimeError('no UVC device and soft_fallback=False')
            self._soft = True
            self._opened = True
            self.backend_kind = BACKEND_SOFT
            return self.status()
        try:
            import cv2
            cap = cv2.VideoCapture(int(match['index']), match['backend'])
            if not cap.isOpened():
                raise RuntimeError('VideoCapture open failed')
            if self.width > 0:
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            if self.height > 0:
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            image = None
            for _ in range(self.warmup_frames + 1):
                ok, image = cap.read()
                if not ok or image is None:
                    raise RuntimeError('UVC warmup read failed')
            self._cap = cap
            self._device = match
            self._soft = False
            self._opened = True
            self.backend_kind = BACKEND_UVC
            # stash last warmup as seq0 buffer
            self._last = image
            self._controls_applied = apply_uvc_soft_controls(
                cap, exposure_us=self.exposure_us, gain_db=self.gain_db,
            )
            try:
                save_last_device(
                    kind=BACKEND_UVC,
                    device_id=self.device_id or match.get('deviceId') or '',
                    label=format_device_picker_label(match, kind=BACKEND_UVC),
                    extra=dict(trigger=self.trigger, exposureUs=self.exposure_us, gainDb=self.gain_db),
                )
            except Exception:
                pass
            return self.status()
        except Exception:
            if self._cap is not None:
                try:
                    self._cap.release()
                except Exception:
                    pass
                self._cap = None
            if not self.soft_fallback:
                raise
            self._soft = True
            self._opened = True
            self.backend_kind = BACKEND_SOFT
            return self.status()

    def status(self) -> dict[str, Any]:
        return dict(
            open=self._opened,
            soft=self._soft,
            backendKind=self.backend_kind,
            deviceId=self.device_id or (self._device or {}).get('deviceId') or ('synthetic-parts' if self._soft else ''),
            device=self._device,
            keepConnectionOpen=True,
            openClosePerGrab=False,
            frameSequence=self._seq,
            captureApi='VideoCapture' if not self._soft else 'soft',
            exposureUs=self.exposure_us,
            gainDb=self.gain_db,
            trigger=self.trigger,
            autoReconnect=self.auto_reconnect,
            reconnectCount=self._reconnect_count,
            controlsApplied=dict(self._controls_applied or {}),
            reconnectResilient=True,
        )

    def grab(self) -> dict[str, Any]:
        """Return one preview frame dict: {annotatedImage, result, backendKind}."""
        if not self._opened:
            self.open()
        started = time.monotonic()
        if self._soft:
            img = _soft_synthetic_bgr(seq=self._seq)
            img = apply_soft_controls_to_bgr(
                img, exposure_us=self.exposure_us, gain_db=self.gain_db, seq=self._seq,
            )
            url = _encode_bgr_png_data_url(img)
            self._seq += 1
            return dict(
                annotatedImage=url,
                soft=True,
                backendKind=BACKEND_SOFT,
                result=dict(
                    width=img.shape[1], height=img.shape[0],
                    pixelFormat='BGR8', driver='simulator',
                    frameSequence=self._seq - 1,
                    simulated=True, softFallback=True,
                    keepConnectionOpen=True, openClosePerGrab=False,
                    exposureUs=self.exposure_us, gainDb=self.gain_db, trigger=self.trigger,
                    elapsedMs=round((time.monotonic() - started) * 1000, 2),
                ),
            )
        import cv2
        # Prefer fresh read; fall back to last warmup buffer once; then reconnect.
        ok, image = (False, None)
        try:
            ok, image = self._cap.read()
        except Exception:
            ok, image = False, None
        if (not ok or image is None) and getattr(self, '_last', None) is not None:
            image = self._last
            self._last = None
            ok = image is not None
        if not ok or image is None:
            if self.auto_reconnect and self._reconnect_once():
                try:
                    ok, image = self._cap.read()
                except Exception:
                    ok, image = False, None
            if not ok or image is None:
                raise RuntimeError('UVC grab failed')
        url = _encode_bgr_png_data_url(image)
        self._seq += 1
        return dict(
            annotatedImage=url,
            soft=False,
            backendKind=BACKEND_UVC,
            result=dict(
                width=int(image.shape[1]), height=int(image.shape[0]),
                pixelFormat='BGR8', driver='uvc',
                frameSequence=self._seq - 1,
                device=self._device,
                simulated=False,
                keepConnectionOpen=True, openClosePerGrab=False,
                exposureUs=self.exposure_us, gainDb=self.gain_db, trigger=self.trigger,
                reconnectCount=self._reconnect_count,
                elapsedMs=round((time.monotonic() - started) * 1000, 2),
            ),
        )

    def set_soft_controls(self, *, exposure_us=None, gain_db=None, trigger=None) -> dict[str, Any]:
        if exposure_us is not None:
            self.exposure_us = clamp_exposure_us(exposure_us)
        if gain_db is not None:
            self.gain_db = clamp_gain_db(gain_db)
        if trigger is not None:
            self.trigger = normalize_trigger(trigger)
        if self._cap is not None and not self._soft:
            self._controls_applied = apply_uvc_soft_controls(
                self._cap, exposure_us=self.exposure_us, gain_db=self.gain_db,
            )
        return self.status()

    def _reconnect_once(self) -> bool:
        if self._reconnect_count >= self.reconnect_max:
            return False
        self._reconnect_count += 1
        try:
            if self._cap is not None:
                try:
                    self._cap.release()
                except Exception:
                    pass
            self._cap = None
            self._opened = False
            self.open()
            return bool(self._opened and not self._soft and self._cap is not None)
        except Exception:
            return False

    def grab_many(self, n: int = 3) -> list[dict[str, Any]]:
        return [self.grab() for _ in range(max(1, int(n)))]

    def close(self) -> None:
        if self._cap is not None:
            try:
                self._cap.release()
            except Exception:
                pass
        self._cap = None
        self._opened = False

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, *exc):
        self.close()
        return False


def gentl_load_producer(provider_id: str | None = None) -> dict[str, Any]:
    """Exercise GenTL producer load API. Returns status; does not fake devices."""
    providers = discover_gentl_ctis(include_env=True)
    available = [p for p in providers if p.get('available')]
    if not available:
        return dict(
            loaded=False,
            status='unsupported',
            statusZh='无可用 CTI',
            providers=[],
            fakeFrames=False,
        )
    try:
        from importlib.metadata import version
        version('harvesters')
    except Exception:
        return dict(
            loaded=False,
            status='not_loaded',
            statusZh='harvesters 未安装',
            providers=[{k: v for k, v in p.items() if k != 'path'} for p in available],
            fakeFrames=False,
        )
    pick = None
    if provider_id:
        pick = next((p for p in available if p.get('id') == provider_id), None)
    if pick is None:
        pick = available[0]
    # Prefer cameras.adapter.harvester when importable (shares Hikrobot compat hooks).
    try:
        from cameras.adapter import harvester as _harvester  # type: ignore
        h = _harvester(pick['id'])
        try:
            n_ifaces = len(getattr(h, 'device_info_list', []) or [])
        finally:
            try:
                h.reset()
            except Exception:
                pass
        return dict(
            loaded=True,
            status='ready',
            statusZh=f"已加载 Producer {pick.get('name')}",
            providerId=pick.get('id'),
            providerName=pick.get('name'),
            deviceInfoCount=n_ifaces,
            fakeFrames=False,
        )
    except Exception as exc:
        # Fallback: open Harvester directly on CTI path.
        try:
            from harvesters.core import Harvester
            h = Harvester()
            cti_path = pick.get('path')
            if not cti_path:
                # recover path from discover list
                full = next((p for p in discover_gentl_ctis() if p.get('id') == pick.get('id')), None)
                cti_path = (full or {}).get('path')
            if not cti_path:
                raise RuntimeError('CTI path missing')
            h.add_file(str(cti_path))
            h.update()
            n = len(h.device_info_list or [])
            h.reset()
            return dict(
                loaded=True,
                status='ready',
                statusZh=f"已加载 Producer {pick.get('name')}",
                providerId=pick.get('id'),
                providerName=pick.get('name'),
                deviceInfoCount=n,
                fakeFrames=False,
                note=str(exc)[:200],
            )
        except Exception as exc2:
            return dict(
                loaded=False,
                status='error',
                statusZh=f'Producer 打开失败：{exc2}',
                providerId=pick.get('id'),
                providerName=pick.get('name'),
                fakeFrames=False,
                error=str(exc2)[:500],
            )


def gentl_enumerate_devices(provider_id: str | None = None) -> list[dict[str, Any]]:
    """Enumerate GenTL devices via loaded producer. Empty = honest no-camera."""
    providers = discover_gentl_ctis(include_env=True)
    available = [p for p in providers if p.get('available')]
    if not available:
        return []
    pick = None
    if provider_id:
        pick = next((p for p in available if p.get('id') == provider_id), None)
    if pick is None:
        pick = available[0]
    try:
        from cameras.adapter import gentl_session, gentl_devices  # type: ignore
        with gentl_session(pick['id']) as h:
            rows = gentl_devices(h)
            for r in rows:
                r.setdefault('backendKind', BACKEND_GENTL)
                r.setdefault('providerId', pick['id'])
            return rows
    except Exception:
        # Direct harvesters path
        try:
            from harvesters.core import Harvester
            full = next((p for p in discover_gentl_ctis() if p.get('id') == pick.get('id')), pick)
            path = full.get('path')
            if not path:
                return []
            h = Harvester()
            h.add_file(str(path))
            h.update()
            rows = []
            for info in h.device_info_list or []:
                def get(key, default=''):
                    try:
                        return getattr(info, key, default) or default
                    except Exception:
                        return default
                did = f"{get('vendor')} {get('model')} ({get('serial_number')})".strip()
                rows.append(dict(
                    deviceId=did or get('display_name') or str(info),
                    name=get('display_name') or get('model') or did,
                    vendor=get('vendor'),
                    model=get('model'),
                    serial=get('serial_number'),
                    transport=get('tl_type'),
                    driver='gentl',
                    backendKind=BACKEND_GENTL,
                    providerId=pick['id'],
                ))
            h.reset()
            return rows
        except Exception:
            return []


class GentlLiveSession:
    """GenTL open once → grab many via cameras.adapter acquire_gentl_frames.

    When producer present but no device: open() succeeds as empty; grab() raises
    honest error (no fake GenTL frames). Smoke can use mocks separately.

    wave157: auto_reconnect / reconnectResilient parity with UvcLiveSession so
    transient USB/GenTL drops recover without tearing down the desktop session.
    """

    def __init__(
        self,
        device_id: str | None = None,
        *,
        provider_id: str | None = None,
        timeout_ms: int = 8000,
        auto_reconnect: bool = True,
        reconnect_max: int = 2,
    ):
        self.device_id = device_id or ''
        self.provider_id = provider_id or ''
        self.timeout_ms = int(timeout_ms)
        self.auto_reconnect = bool(auto_reconnect)
        self.reconnect_max = max(0, int(reconnect_max))
        self._reconnect_count = 0
        self._gen = None
        self._opened = False
        self._seq = 0
        self._device: dict[str, Any] | None = None
        self.backend_kind = BACKEND_GENTL

    @property
    def is_open(self) -> bool:
        return bool(self._opened)

    def open(self) -> dict[str, Any]:
        if self._opened:
            return self.status()
        load = gentl_load_producer(self.provider_id or None)
        if not load.get('loaded'):
            raise RuntimeError(load.get('statusZh') or 'GenTL producer not loaded')
        self.provider_id = load.get('providerId') or self.provider_id
        devices = gentl_enumerate_devices(self.provider_id)
        if not devices:
            # Honest empty — session marked open=False for grab, but load/enum exercised.
            self._opened = False
            self._empty = True
            return dict(
                open=False,
                emptyDevice=True,
                backendKind=BACKEND_GENTL,
                providerId=self.provider_id,
                devices=[],
                fakeFrames=False,
                statusZh='Producer 已加载但未发现相机',
                load=load,
            )
        match = None
        if self.device_id:
            match = next((d for d in devices if d.get('deviceId') == self.device_id), None)
        if match is None:
            match = devices[0]
            self.device_id = match.get('deviceId') or ''
        self._device = match
        # Start frame generator (keeps IA open across grabs).
        from cameras.adapter import acquire_gentl_frames, config  # type: ignore
        p = config({
            'driver': 'gentl',
            'providerId': self.provider_id,
            'deviceId': self.device_id,
            'timeoutMs': self.timeout_ms,
            'trigger': 'freerun',
        })
        self._gen = acquire_gentl_frames(p)
        self._opened = True
        self._empty = False
        return self.status()

    def status(self) -> dict[str, Any]:
        return dict(
            open=self._opened,
            emptyDevice=bool(getattr(self, '_empty', False)),
            backendKind=BACKEND_GENTL,
            providerId=self.provider_id,
            deviceId=self.device_id,
            device=self._device,
            keepConnectionOpen=True,
            openClosePerGrab=False,
            sessionPersist=True,
            reconnectResilient=True,
            autoReconnect=self.auto_reconnect,
            reconnectCount=self._reconnect_count,
            reconnectMax=self.reconnect_max,
            frameSequence=self._seq,
            fakeFrames=False,
        )

    def grab(self) -> dict[str, Any]:
        if getattr(self, '_empty', False) and not self._opened:
            raise RuntimeError('GenTL producer loaded but no camera — no fake frames')
        if not self._opened:
            st = self.open()
            if st.get('emptyDevice'):
                raise RuntimeError('GenTL producer loaded but no camera — no fake frames')
        try:
            return self._grab_once()
        except Exception as exc:
            if self.auto_reconnect and self._reconnect_once():
                try:
                    frame = self._grab_once()
                    frame.setdefault('result', {})
                    if isinstance(frame['result'], dict):
                        frame['result']['reconnected'] = True
                        frame['result']['reconnectCount'] = self._reconnect_count
                    return frame
                except Exception as exc2:
                    raise RuntimeError(
                        f'GenTL grab failed after reconnect: {exc2}'
                    ) from exc2
            raise

    def _grab_once(self) -> dict[str, Any]:
        started = time.monotonic()
        from cameras.adapter import pack_frame, config  # type: ignore
        if self._gen is None:
            raise RuntimeError('GenTL session generator not open')
        raw = next(self._gen)
        p = config({
            'driver': 'gentl',
            'providerId': self.provider_id,
            'deviceId': self.device_id,
            'timeoutMs': self.timeout_ms,
            'trigger': 'freerun',
        })
        packed = pack_frame(raw, p, started)
        self._seq += 1
        result = dict(packed.get('result') or {})
        result['frameSequence'] = self._seq - 1
        result['keepConnectionOpen'] = True
        result['openClosePerGrab'] = False
        result['backendKind'] = BACKEND_GENTL
        result['reconnectCount'] = self._reconnect_count
        return dict(
            annotatedImage=packed.get('annotatedImage') or '',
            soft=False,
            backendKind=BACKEND_GENTL,
            result=result,
            cloud=packed.get('cloud'),
            depth=packed.get('depth'),
        )

    def _reconnect_once(self) -> bool:
        if self._reconnect_count >= self.reconnect_max:
            return False
        self._reconnect_count += 1
        try:
            self.close()
            st = self.open()
            return bool(self._opened and not st.get('emptyDevice'))
        except Exception:
            return False

    def grab_many(self, n: int = 2) -> list[dict[str, Any]]:
        return [self.grab() for _ in range(max(1, int(n)))]

    def close(self) -> None:
        if self._gen is not None:
            try:
                self._gen.close()
            except Exception:
                pass
        self._gen = None
        self._opened = False

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, *exc):
        self.close()
        return False


def soft_live_frames(n: int = 3) -> list[dict[str, Any]]:
    """CI-safe continuous soft frames through the same PNG preview contract."""
    sess = UvcLiveSession(device_id='', soft_fallback=True)
    # Force soft path even if UVC exists (explicit soft helper).
    sess._soft = True
    sess._opened = True
    sess.backend_kind = BACKEND_SOFT
    try:
        return sess.grab_many(n)
    finally:
        sess.close()


def live_preview_pipeline_ok(frame: dict | None) -> bool:
    """True when frame can feed PreviewFrameGate / show_live_frame."""
    if not isinstance(frame, dict):
        return False
    img = frame.get('annotatedImage') or frame.get('image') or ''
    return isinstance(img, str) and img.startswith('data:image/') and len(img) > 32


_REGISTRY: dict[str, Callable[[], CameraBackend]] = {
    BACKEND_SOFT: SoftBackend,
    BACKEND_UVC: UvcBackend,
    BACKEND_GENTL: GentlBackend,
}


def get_backend(kind: str | None) -> CameraBackend:
    k = str(kind or BACKEND_SOFT).strip().lower()
    factory = _REGISTRY.get(k) or SoftBackend
    return factory()


def all_backends() -> list[CameraBackend]:
    return [factory() for factory in _REGISTRY.values()]


def backend_status_table() -> list[dict[str, Any]]:
    rows = []
    for b in all_backends():
        avail = b.availability()
        rows.append(dict(
            kind=b.kind,
            label=b.label(),
            driver=b.driver,
            status=avail.get('status'),
            statusZh=avail.get('statusZh'),
            available=bool(avail.get('available')),
            sessionPersist=session_persist_flags(),
            continuousLive=True,
            capabilities=b.capabilities(),
        ))
    return rows


def picker_choices() -> list[tuple[str, str]]:
    """(label, kind) for Soft vs UVC vs GenTL combo."""
    return [(BACKEND_LABELS[k], k) for k in BACKEND_KINDS]


def soft_fallback_devices() -> list[dict[str, Any]]:
    """CI-safe soft devices when no physical camera present."""
    return SoftBackend().enumerate_local()


def assert_uvc_session_persist_contract(flags: dict | None = None) -> list[str]:
    """Return list of failed contract checks (empty = PASS)."""
    f = flags if isinstance(flags, dict) else session_persist_flags()
    fails = []
    if f.get('keepConnectionOpen') is not True:
        fails.append('keepConnectionOpen must be True')
    if f.get('openClosePerGrab') is not False:
        fails.append('openClosePerGrab must be False')
    if f.get('reuseAcrossFrames') is not True:
        fails.append('reuseAcrossFrames must be True')
    return fails



def soft_controls_roundtrip(exposure_us: int = 8000, gain_db: float = 3.0) -> dict[str, Any]:
    """CI-safe: soft session applies exposure/gain; frame result echoes controls."""
    with UvcLiveSession(device_id='', soft_fallback=True, exposure_us=exposure_us, gain_db=gain_db) as sess:
        st = sess.status()
        frame = sess.grab()
        return dict(
            ok=True,
            status=st,
            exposureUs=frame['result'].get('exposureUs'),
            gainDb=frame['result'].get('gainDb'),
            trigger=frame['result'].get('trigger'),
            pipeline=live_preview_pipeline_ok(frame),
            soft=sess.is_soft,
        )
