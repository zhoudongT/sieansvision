"""Pluggable camera acquisition backends — Soft / UVC / GenTL shell (wave153).

Real path start toward industrial desktop use:
  • soft  — file/sim (no hardware); always available
  • uvc   — OpenCV VideoCapture persistent session (enumerate + open once)
  • gentl — GenTL/GigE producer shell; honest unsupported when no CTI loaded

No Halcon/CLR, robot vendor SDK, cloud, or TCP productization here.
GenTL does not fake frames — status is unsupported/not_loaded when producer missing.
"""
from __future__ import annotations

import platform
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


class CameraBackend:
    """Minimal pluggable backend surface shared by Soft / UVC / GenTL shell."""

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
            requiresHardware=self.kind != BACKEND_SOFT,
            pluggable=True,
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
        """Params for camera/session/start — freerun persistent session."""
        params: dict[str, Any] = {
            'driver': self.driver,
            'deviceId': device_id,
            'timeoutMs': int(extra.get('timeoutMs', 5000)),
            'trigger': 'freerun',
            'sessionPersist': True,
            'keepConnectionOpen': True,
            'openClosePerGrab': False,
            'backendKind': self.kind,
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
            zh = 'UVC / OpenCV VideoCapture 可用（持久会话·跨帧保持连接）'
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
    """GenTL / GigE shell — pluggable later without rewriting UI.

    Honest unsupported/not_loaded when no producer CTI or harvesters.
    Never yields synthetic frames labeled as GenTL.
    """

    kind = BACKEND_GENTL
    driver = 'gentl'

    def availability(self) -> dict[str, Any]:
        providers: list[dict[str, Any]] = []
        harv = False
        try:
            # Prefer cameras.adapter when on PYTHONPATH (desktop / session).
            from cameras.adapter import providers as _providers  # type: ignore
            providers = list(_providers() or [])
        except Exception:
            try:
                import os
                from pathlib import Path
                import hashlib
                for raw in os.environ.get('SIEANS_GENTL_CTI', '').split(os.pathsep):
                    if not raw.strip():
                        continue
                    path = Path(raw.strip()).expanduser().resolve()
                    key = hashlib.sha256(os.path.normcase(str(path)).encode()).hexdigest()[:20]
                    providers.append(dict(
                        id=key, name=path.name, path=str(path),
                        available=path.is_file() and path.suffix.lower() == '.cti',
                    ))
            except Exception:
                providers = []
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
            status, zh = 'not_loaded', 'GenTL 未加载：未装 harvesters，且未配置可用 CTI（SIEANS_GENTL_CTI）'
        elif not harv:
            status, zh = 'not_loaded', 'GenTL 未加载：harvesters 未安装（CTI 已配置亦无法打开 Producer）'
        elif not available_cti:
            status, zh = 'unsupported', 'GenTL Producer 未配置或不存在 — 设置 SIEANS_GENTL_CTI 后重启'
        else:
            status, zh = 'ready', f'GenTL Producer 可用（{len(available_cti)} 个 CTI）'
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
            note='无 Producer 时不伪造 GenTL 帧；UI 保持可插拔壳',
        )

    def enumerate_local(self) -> list[dict[str, Any]]:
        # Device list requires live Producer — shell returns empty when not ready.
        avail = self.availability()
        if not avail.get('available'):
            return []
        # Prefer RPC path in UI; local enumerate left empty to avoid opening CTI twice.
        return []


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
