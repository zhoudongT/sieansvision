"""Camera acquisition operator chrome — soft + real UVC/GenTL path (wave150–153).

Industrial-dark density for ImageSource / camera session / Soft·UVC·GenTL picker.
wave153: real camera path start — UVC VideoCapture persistent session + GenTL shell.
No Halcon/CLR, robot vendor SDK, cloud, or TCP productization.
No Comm/Host cobind cascades, no spark/blink/chip micro-prop.
"""
from __future__ import annotations

from typing import Any

SOFT_DRIVERS = frozenset({'simulator', 'rgbd_simulator', 'file', 'local'})
REAL_DRIVERS = frozenset({'uvc', 'gentl'})
CAMERA_CAPTURE_OPS = ('camera_capture',)

OPERATOR_TAG = '采'
OPERATOR_LABEL = '采集'

# Industrial dark palette (align canvas_legend / annotate).
PALETTE = {
    'ok': '#00d250',
    'ng': '#ff5252',
    'warn': '#ffb400',
    'info': '#42a5f5',
    'soft': '#66cfff',
    'uvc': '#4fc3f7',
    'gentl': '#ab47bc',
    'idle': '#9aa3b2',
    'running': '#00d250',
    'session': '#7c4dff',
    'preview': '#e8a838',
    'bg': '#1e2430',
    'fg': '#d7dde8',
    'muted': '#8b93a7',
}

SESSION_COLUMNS = ['项', '值']

# Live preview policy — anti-flicker + continuous timing polish (wave152).
# Frame pacing: timer interval for pull ticks; uiMinIntervalMs throttles paints;
# dropOldFrame coalesces to latest so UI never paints a stale backlog.
LIVE_PREVIEW_POLICY = dict(
    intervalMs=50,
    managerIntervalMs=120,
    uiMinIntervalMs=33,  # ~30 Hz UI ceiling; drop-old coalesces faster producers
    dropOldFrame=True,
    framePolicy='latest',
    antiFlicker='in_place_pixmap',
    refitOnShow=True,
    note='同尺寸帧原地 setPixmap；UI 节流+丢旧帧；禁止每 tick scene.clear+fitInView',
)


def is_soft_driver(driver: str | None) -> bool:
    d = str(driver or '').strip().lower()
    return d in SOFT_DRIVERS or d in ('', 'synthetic')


def backend_kind_bit(kind: str | None = None, *, soft: bool | None = None, driver: str | None = None) -> str:
    """Short badge infix: 软 / UVC / GTL / ''."""
    k = str(kind or '').strip().lower()
    if not k and driver:
        try:
            from desktop.camera_backends import kind_of_driver
            k = kind_of_driver(driver)
        except Exception:
            k = 'soft' if soft else ''
    if soft is True and not k:
        k = 'soft'
    return {'soft': '软', 'uvc': 'UVC', 'gentl': 'GTL'}.get(k, '软' if soft else '')


def chrome_badge(
    judge_ok=None,
    status=None,
    *,
    soft: bool | None = None,
    frame_seq: int | None = None,
    ready: bool | None = None,
    backend_kind: str | None = None,
    driver: str | None = None,
) -> str:
    """Compact badge: 采软✓ / 采UVC12✓ / 采GTL· / 采✗."""
    mark = '·'
    if ready is True or judge_ok is True or str(status or '').upper() in (
        'OK', 'PASS', 'RUNNING', 'READY',
    ):
        mark = '✓'
    elif ready is False or judge_ok is False or str(status or '').upper() in (
        'NG', 'FAIL', 'ERROR', 'STOPPED',
    ):
        mark = '✗'
    bit = backend_kind_bit(backend_kind, soft=soft, driver=driver)
    if frame_seq is not None and int(frame_seq) >= 0:
        return f'{OPERATOR_TAG}{bit}{int(frame_seq)}{mark}'
    return f'{OPERATOR_TAG}{bit}{mark}'


def soft_capture_ready_reason(params: dict | None = None) -> str:
    """Empty → soft camera_capture ready to acquire+run; else Chinese reason."""
    p = params or {}
    driver = str(p.get('driver') or '').strip() or 'simulator'
    if not is_soft_driver(driver) and driver not in ('session',):
        return f'非软驱动（{driver}）— 本铬仅覆盖模拟/文件源'
    device = str(p.get('deviceId') or p.get('cameraId') or '').strip()
    if driver in ('simulator', 'rgbd_simulator') and not device:
        # Defaults used by demos — still warn lightly but treat as soft-fillable.
        return '未填设备标识（模拟默认 synthetic-parts / synthetic-rgbd）'
    return ''


def soft_capture_ready(params: dict | None = None) -> bool:
    why = soft_capture_ready_reason(params)
    # Missing deviceId on simulator is soft-fillable → still "ready enough" for open-and-run
    # if driver is soft; only hard-block non-soft.
    p = params or {}
    driver = str(p.get('driver') or '').strip() or 'simulator'
    if not is_soft_driver(driver) and driver not in ('session',):
        return False
    return True if why.startswith('未填') or not why else not bool(why)


def soft_source_ready_reason(source_config: dict | None = None) -> str:
    """ImageSource / sourceConfig soft open-and-run readiness."""
    cfg = source_config or {}
    mode = str(cfg.get('mode') or 'local').strip().lower()
    if mode == 'local':
        images = cfg.get('images') or []
        if not images:
            return '本地图像列表为空（请挂样张或切软相机）'
        return ''
    if mode in ('camera', 'sdk'):
        cam = cfg.get('cameraId') or (cfg.get('cameraParams') or {}).get('deviceId')
        if not cam:
            return '未关联相机（软路径请用模拟驱动或本地胶片）'
        return ''
    return ''


def default_soft_device_id(driver: str | None = None) -> str:
    d = str(driver or 'simulator').strip().lower()
    if d == 'rgbd_simulator':
        return 'synthetic-rgbd'
    if d in ('simulator', 'file', 'local', ''):
        return 'synthetic-parts'
    return ''


def normalize_soft_capture_params(params: dict | None = None) -> dict:
    """Fill soft defaults for open-and-run (simulator freerun). Does not touch GenTL."""
    p = dict(params or {})
    driver = str(p.get('driver') or 'simulator').strip() or 'simulator'
    if not is_soft_driver(driver):
        return p
    p['driver'] = driver
    if not str(p.get('deviceId') or '').strip():
        p['deviceId'] = default_soft_device_id(driver)
    p.setdefault('trigger', 'freerun')
    p.setdefault('timeoutMs', 5000)
    if driver == 'simulator':
        p.setdefault('dataMode', 'image')
    return p


def summarize_session(state: dict | None = None, *, params: dict | None = None) -> dict[str, Any]:
    """Dense session summary for operator chrome / fixed bar / dialog strip."""
    st = state if isinstance(state, dict) else {}
    cfg = params if isinstance(params, dict) else (st.get('config') or {}).get('params') or {}
    if not isinstance(cfg, dict):
        cfg = {}
    # Nested config forms from camera/session/status
    nested = st.get('config') if isinstance(st.get('config'), dict) else {}
    if not cfg and isinstance(nested.get('params'), dict):
        cfg = nested['params']
    driver = str(cfg.get('driver') or st.get('driver') or '').strip()
    device = str(cfg.get('deviceId') or st.get('deviceId') or '').strip()
    running = str(st.get('state') or '').lower() in ('running', 'connected', 'open')
    soft = is_soft_driver(driver) if driver else True
    try:
        from desktop.camera_backends import kind_of_driver
        backend_kind = kind_of_driver(driver, nested=nested if isinstance(nested, dict) else cfg)
    except Exception:
        backend_kind = 'soft' if soft else ('uvc' if driver == 'uvc' else ('gentl' if driver == 'gentl' else ''))
    if soft:
        backend_kind = 'soft'
    seq = st.get('received')
    if seq is None:
        seq = st.get('frameSequence')
    try:
        seq_i = int(seq) if seq is not None else None
    except (TypeError, ValueError):
        seq_i = None
    age = st.get('frameAgeMs')
    try:
        age_i = int(age) if age is not None else None
    except (TypeError, ValueError):
        age_i = None
    badge = chrome_badge(
        soft=soft,
        frame_seq=seq_i,
        ready=running or soft_capture_ready(cfg),
        status='RUNNING' if running else (st.get('state') or 'idle'),
        backend_kind=backend_kind,
        driver=driver,
    )
    state_zh = {
        'running': '持续采集中',
        'idle': '未连接',
        'stopped': '已停止',
        'error': '故障',
        'connecting': '连接中',
    }.get(str(st.get('state') or 'idle').lower(), str(st.get('state') or '未连接'))
    kind_zh = {'soft': '软模拟', 'uvc': 'USB UVC', 'gentl': 'GenTL'}.get(backend_kind, driver)
    line = ' · '.join(
        x for x in (
            badge,
            kind_zh if (soft or driver or backend_kind) else None,
            device or None,
            state_zh,
            f'帧#{seq_i}' if seq_i is not None else None,
            f'龄{age_i}ms' if age_i is not None else None,
        ) if x
    )
    return dict(
        badge=badge,
        soft=soft,
        backendKind=backend_kind,
        driver=driver or ('simulator' if soft else ''),
        deviceId=device,
        state=str(st.get('state') or 'idle'),
        stateZh=state_zh,
        frameSequence=seq_i,
        frameAgeMs=age_i,
        sessionId=st.get('id') or st.get('sessionId'),
        received=st.get('received'),
        consumed=st.get('consumed'),
        overwritten=st.get('overwritten'),
        reused=st.get('reused'),
        summary=line,
        ready=bool(running or soft_capture_ready(cfg)),
        livePolicy=dict(LIVE_PREVIEW_POLICY),
    )


def session_stat_rows(summary: dict | None = None) -> list[list[str]]:
    s = summary or {}
    rows = [
        ['徽标', str(s.get('badge') or '采·')],
        ['路径', {'soft': '软模拟', 'uvc': 'USB UVC', 'gentl': 'GenTL'}.get(str(s.get('backendKind') or ''), '软模拟' if s.get('soft') else str(s.get('driver') or '—'))],
        ['后端种类', str(s.get('backendKind') or ('soft' if s.get('soft') else '—'))],
        ['驱动', str(s.get('driver') or '—')],
        ['设备', str(s.get('deviceId') or '—')],
        ['状态', str(s.get('stateZh') or s.get('state') or '—')],
        ['会话', str(s.get('sessionId') or '—')],
        ['接收帧', str(s.get('received') if s.get('received') is not None else '—')],
        ['取帧次数', str(s.get('consumed') if s.get('consumed') is not None else '—')],
        ['覆盖未取', str(s.get('overwritten') if s.get('overwritten') is not None else '—')],
        ['重复缓存', str(s.get('reused') if s.get('reused') is not None else '—')],
        ['帧龄 ms', str(s.get('frameAgeMs') if s.get('frameAgeMs') is not None else '—')],
        ['预览策略', str((s.get('livePolicy') or LIVE_PREVIEW_POLICY).get('antiFlicker') or '—')],
        ['帧策略', str((s.get('livePolicy') or LIVE_PREVIEW_POLICY).get('framePolicy') or 'latest')],
        ['丢旧帧', '是' if (s.get('livePolicy') or LIVE_PREVIEW_POLICY).get('dropOldFrame', True) else '否'],
        ['UI节流 ms', str((s.get('livePolicy') or LIVE_PREVIEW_POLICY).get('uiMinIntervalMs') or '—')],
    ]
    return rows


def html_session_strip(summary: dict | None = None) -> str:
    """Compact industrial-dark HTML strip for ImageSource / dialog chrome."""
    s = summary or summarize_session({})
    badge = s.get('badge') or '采·'
    color = PALETTE['ok'] if s.get('ready') else PALETTE['idle']
    kind = str(s.get('backendKind') or ('soft' if s.get('soft') else ''))
    bit = backend_kind_bit(kind, soft=s.get('soft'), driver=s.get('driver'))
    kind_color = PALETTE.get(kind) or PALETTE['soft']
    body = (
        f"<span style='color:{color};font-weight:600'>{badge}</span> "
        f"<span style='color:{kind_color}'>{bit or ''}采集</span> · "
        f"<span style='color:{PALETTE['fg']}'>{s.get('stateZh') or '未连接'}</span>"
    )
    if s.get('deviceId'):
        body += f" · <span style='color:{PALETTE['muted']}'>{s.get('deviceId')}</span>"
    if s.get('frameSequence') is not None:
        body += f" · <span style='color:{PALETTE['preview']}'>#{s.get('frameSequence')}</span>"
    note = LIVE_PREVIEW_POLICY.get('note') or ''
    return (
        f"<div style='background:{PALETTE['bg']};color:{PALETTE['fg']};"
        f"padding:6px 8px;border-radius:4px;font-size:12px;line-height:1.45'>"
        f"{body}<div style='color:{PALETTE['muted']};margin-top:2px'>{note}</div></div>"
    )


def source_chrome_strip(source_config: dict | None = None, *, session: dict | None = None) -> dict[str, Any]:
    """Operator settings chrome density for ImageSourceForm."""
    cfg = source_config or {}
    mode = str(cfg.get('mode') or 'local').strip().lower()
    why = soft_source_ready_reason(cfg)
    sess = summarize_session(session or {}, params=(cfg.get('cameraParams') or {}))
    if mode == 'local':
        n = len(cfg.get('images') or [])
        badge = chrome_badge(soft=True, ready=not bool(why), frame_seq=n if n else None)
        line = f'{badge} · 本地胶片 · {n} 张' + (f' · ⚠ {why}' if why else ' · 打开即跑就绪')
        ready = not bool(why)
    elif mode in ('camera', 'sdk'):
        badge = sess.get('badge') or chrome_badge(soft=True, ready=not bool(why))
        line = f'{badge} · {mode} · ' + (why or (sess.get('summary') or '待连接'))
        ready = not bool(why)
    else:
        badge = chrome_badge(soft=True, ready=False)
        line = f'{badge} · 未知模式 {mode}'
        ready = False
    return dict(
        badge=badge,
        mode=mode,
        ready=ready,
        reason=why,
        summary=line,
        html=html_session_strip(dict(sess, badge=badge, ready=ready, stateZh=line.split(' · ')[1] if ' · ' in line else line)),
        soft=True,
    )


def project_soft_acquisition_summary(project: dict | None = None) -> dict[str, Any]:
    """Scan project for soft camera_capture / sourceConfig open-and-run readiness."""
    proj = project or {}
    steps = proj.get('steps') or []
    soft_steps = []
    for s in steps:
        if not isinstance(s, dict):
            continue
        if s.get('operation') not in CAMERA_CAPTURE_OPS:
            continue
        params = normalize_soft_capture_params(s.get('params') or {})
        if not is_soft_driver(params.get('driver')):
            continue
        soft_steps.append(dict(
            id=s.get('id'),
            name=s.get('name') or '软采集',
            params=params,
            ready=soft_capture_ready(params),
            reason=soft_capture_ready_reason(params),
        ))
    src = source_chrome_strip(proj.get('sourceConfig') or {})
    ready = bool(soft_steps) and all(x.get('ready') for x in soft_steps)
    if not soft_steps and src.get('ready') and src.get('mode') == 'local':
        # Local filmstrip alone is also a soft open-and-run path
        ready = True
    badge = chrome_badge(soft=True, ready=ready, frame_seq=len(soft_steps) or None)
    return dict(
        badge=badge,
        softSteps=soft_steps,
        source=src,
        ready=ready,
        summary=f"{badge} · 软采集节点 {len(soft_steps)} · 源:{src.get('mode')}",
    )


def capture_result_chrome(result: dict | None = None, *, params: dict | None = None) -> dict[str, Any]:
    """Denser result chrome for a soft camera_capture run output."""
    bag = result if isinstance(result, dict) else {}
    for key in ('output', 'outputs', 'result', 'camera'):
        inner = bag.get(key)
        if isinstance(inner, dict) and (
            'width' in inner or 'frameSequence' in inner or 'driver' in inner
        ):
            bag = inner
            break
    p = params or {}
    driver = str(bag.get('driver') or p.get('driver') or 'simulator')
    soft = is_soft_driver(driver)
    w = bag.get('width')
    h = bag.get('height')
    seq = bag.get('frameSequence') or bag.get('sequence')
    try:
        seq_i = int(seq) if seq is not None else None
    except (TypeError, ValueError):
        seq_i = None
    ok = bag.get('ok')
    if ok is None:
        ok = bool(w and h) or soft
    badge = chrome_badge(judge_ok=ok, soft=soft, frame_seq=seq_i, ready=bool(ok))
    size = f'{w}×{h}' if w and h else '—'
    rows = [
        ['徽标', badge],
        ['驱动', driver],
        ['软路径', '是' if soft else '否'],
        ['尺寸', size],
        ['帧序号', str(seq_i if seq_i is not None else '—')],
        ['设备', str(bag.get('deviceId') or p.get('deviceId') or '—')],
        ['触发', str(bag.get('trigger') or p.get('trigger') or 'freerun')],
    ]
    return dict(
        badge=badge,
        soft=soft,
        driver=driver,
        size=size,
        frameSequence=seq_i,
        rows=rows,
        summary=f'{badge} · {driver} · {size}',
        ok=bool(ok),
    )



class PreviewFrameGate:
    """UI-side continuous-preview gate: throttle paints + drop/coalesce old frames.

    Producers (soft simulator / session cache) may outrun the ImageView paint path.
    offer() keeps only the latest pending payload when dropOldFrame is on; returns
    a paintable payload only when the UI min-interval has elapsed. flush_due() is
    for a short QTimer follow-up after a throttled offer.
    """

    __slots__ = (
        'min_interval_ms', 'drop_old',
        '_last_paint_ms', '_pending', '_pending_seq',
        '_offered', '_painted', '_dropped',
    )

    def __init__(self, min_interval_ms: int | None = None, *, drop_old: bool | None = None):
        pol = LIVE_PREVIEW_POLICY
        self.min_interval_ms = int(
            min_interval_ms if min_interval_ms is not None else pol.get('uiMinIntervalMs', 33)
        )
        self.drop_old = bool(pol.get('dropOldFrame', True) if drop_old is None else drop_old)
        self._last_paint_ms = 0.0
        self._pending = None
        self._pending_seq = None
        self._offered = 0
        self._painted = 0
        self._dropped = 0

    def reset(self) -> None:
        self._last_paint_ms = 0.0
        self._pending = None
        self._pending_seq = None
        self._offered = 0
        self._painted = 0
        self._dropped = 0

    def _now(self, now_ms: float | None) -> float:
        if now_ms is not None:
            return float(now_ms)
        import time
        return time.monotonic() * 1000.0

    def offer(self, payload, *, seq=None, now_ms: float | None = None):
        """Offer a frame for UI. Returns payload to paint now, or None if held/dropped."""
        if payload is None:
            return None
        now = self._now(now_ms)
        self._offered += 1
        if self.drop_old and self._pending is not None:
            self._dropped += 1
        self._pending = payload
        self._pending_seq = seq
        if self._last_paint_ms > 0 and (now - self._last_paint_ms) < self.min_interval_ms:
            return None
        return self.take(now_ms=now)

    def take(self, *, now_ms: float | None = None):
        """Force-take pending latest (caller paints). None if empty."""
        if self._pending is None:
            return None
        now = self._now(now_ms)
        payload = self._pending
        self._pending = None
        self._pending_seq = None
        self._last_paint_ms = now
        self._painted += 1
        return payload

    def flush_due(self, *, now_ms: float | None = None):
        """If a coalesced frame is waiting and interval elapsed, return it to paint."""
        if self._pending is None:
            return None
        now = self._now(now_ms)
        if self._last_paint_ms > 0 and (now - self._last_paint_ms) < self.min_interval_ms:
            return None
        return self.take(now_ms=now)

    def has_pending(self) -> bool:
        return self._pending is not None

    def ms_until_due(self, *, now_ms: float | None = None) -> int:
        if self._pending is None:
            return 0
        now = self._now(now_ms)
        remain = self.min_interval_ms - (now - self._last_paint_ms)
        return max(0, int(remain)) if self._last_paint_ms > 0 else 0

    def stats(self) -> dict[str, Any]:
        return dict(
            offered=self._offered,
            painted=self._painted,
            dropped=self._dropped,
            pending=self._pending is not None,
            pendingSeq=self._pending_seq,
            minIntervalMs=self.min_interval_ms,
            dropOldFrame=self.drop_old,
            framePolicy=LIVE_PREVIEW_POLICY.get('framePolicy', 'latest'),
        )


def live_preview_ui_min_interval_ms() -> int:
    return int(LIVE_PREVIEW_POLICY.get('uiMinIntervalMs') or 33)


def live_capture_frame_policy() -> str:
    return str(LIVE_PREVIEW_POLICY.get('framePolicy') or 'latest')


def live_preview_drop_old() -> bool:
    return bool(LIVE_PREVIEW_POLICY.get('dropOldFrame', True))


def live_preview_interval_ms(*, manager: bool = False) -> int:
    pol = LIVE_PREVIEW_POLICY
    return int(pol['managerIntervalMs'] if manager else pol['intervalMs'])


def fixed_bar_camera_text(summary: dict | None = None, *, bind: str | None = None) -> str:
    """Short fixed-bar cameraBind live text."""
    s = summary or {}
    kind = str(s.get('backendKind') or ('soft' if s.get('soft') else ''))
    base = (bind or '').strip() or ({'soft': '软采集', 'uvc': 'UVC采集', 'gentl': 'GenTL采集'}.get(kind, '采集'))
    hint = s.get('badge') or s.get('stateZh') or s.get('state') or '未连接'
    bit = backend_kind_bit(kind, soft=s.get('soft'), driver=s.get('driver'))
    if bit:
        return f'{base}({hint}·{bit})'[:28]
    return f'{base}({hint})'[:28]
