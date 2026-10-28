#!/usr/bin/env python3
"""t236: CameraDialog continuous live must paint full non-black frames after abort/reopen.

Root cause: _abort_camera_actions / close popped camera/capture pending without clearing
_live_pending; reopen showed「连续采集中」but _live_tick returned forever → solid black.
"""
from __future__ import annotations

import base64
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT / '.pydeps'))
sys.path.insert(0, str(ROOT))

os.environ.setdefault('DISPLAY', ':0')
os.environ.setdefault('WAYLAND_DISPLAY', 'wayland-0')
os.environ.setdefault('XDG_RUNTIME_DIR', '/run/user/1000')
os.environ.setdefault('QT_QPA_PLATFORM', 'wayland')
os.environ.setdefault(
    'SIEANS_GENTL_CTI',
    '/opt/MVS/lib/64/MvProducerU3V.cti:/opt/MVS/lib/64/MvProducerGEV.cti',
)
os.environ.setdefault('MVCAM_COMMON_RUNENV', '/opt/MVS/lib')
os.environ['LD_LIBRARY_PATH'] = '/opt/MVS/lib/64:' + os.environ.get('LD_LIBRARY_PATH', '')

import cv2
import numpy as np
from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QApplication

from desktop.backend import Backend
from desktop.device_dialogs import CameraDialog


DEVICE = os.environ.get('SIEANS_LIVE_DEVICE', 'MV-CB013')
OUT = ROOT / 'artifacts'
OUT.mkdir(parents=True, exist_ok=True)


def _jpeg_stats(url: str) -> dict:
    if not url or ',' not in url:
        return dict(active_pct=0.0, mean=0.0, w=0, h=0, jpeg_bytes=0)
    raw = base64.b64decode(url.split(',', 1)[1], validate=False)
    arr = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_GRAYSCALE)
    if arr is None:
        return dict(active_pct=0.0, mean=0.0, w=0, h=0, jpeg_bytes=len(raw))
    row = arr.mean(axis=1)
    act = int((row > 5).sum())
    return dict(
        w=int(arr.shape[1]), h=int(arr.shape[0]), jpeg_bytes=len(raw),
        active_rows=act, active_pct=round(100.0 * act / arr.shape[0], 2),
        mean=round(float(arr.mean()), 1),
        bot_mean=round(float(row[-16:].mean()), 1),
    )


def _label_fill(label) -> dict:
    src = label._source
    if src.isNull() or label.width() < 8 or label.height() < 8:
        return dict(source=None, fill=0.0, ok=False, null=True)
    scaled = label._scaled if not label._scaled.isNull() else src
    fill_w = scaled.width() / max(1, label.width())
    fill_h = scaled.height() / max(1, label.height())
    fill = max(fill_w, fill_h)
    ok = (
        src.width() >= 640 and src.height() >= 480
        and (scaled.width() >= label.width() * 0.7 or scaled.height() >= label.height() * 0.7)
        and fill >= 0.7
    )
    return dict(
        source=[src.width(), src.height()],
        scaled=[scaled.width(), scaled.height()],
        widget=[label.width(), label.height()],
        fill=round(float(fill), 4),
        ok=ok,
        null=False,
    )


def _grab_mean(label) -> dict:
    label.repaint()
    QApplication.processEvents()
    pix = label.grab()
    path = OUT / 'verify-t236-LivePreviewLabel.png'
    pix.save(str(path), 'PNG')
    img = pix.toImage().convertToFormat(pix.toImage().Format.Format_RGB32)
    w, h = img.width(), img.height()
    if w < 8 or h < 8:
        return dict(path=str(path), mean=0.0, w=w, h=h)
    # sample luminance
    total = 0
    n = 0
    step = max(1, min(w, h) // 64)
    for y in range(0, h, step):
        for x in range(0, w, step):
            c = img.pixelColor(x, y)
            total += (c.red() + c.green() + c.blue()) / 3.0
            n += 1
    return dict(path=str(path), mean=round(total / max(1, n), 1), w=w, h=h)


def main():
    app = QApplication(sys.argv)
    backend = Backend()
    backend.start(ROOT, ROOT / 'data' / 'native-desktop')

    ready = {'ok': False}

    def on_ready():
        ready['ok'] = True

    backend.ready.connect(on_ready)
    # wait engine
    t0 = time.monotonic()
    while not ready['ok'] and time.monotonic() - t0 < 20:
        app.processEvents()
        time.sleep(0.05)
    if not ready['ok']:
        print(json.dumps(dict(ok=False, err='engine not ready'), ensure_ascii=False))
        return 2

    dlg = CameraDialog(backend)
    dlg.show()
    dlg.resize(1120, 790)
    app.processEvents()

    # Select GenTL
    idx = dlg.driver.findData('gentl')
    if idx >= 0:
        dlg.driver.setCurrentIndex(idx)
    app.processEvents()

    # Wait for GenTL providers (showEvent requests them)
    t_prov = time.monotonic()
    while dlg.provider.count() == 0 and time.monotonic() - t_prov < 10:
        app.processEvents()
        time.sleep(0.05)
    if dlg.provider.count() == 0:
        # Force request
        got = {'v': None}
        def _p(v):
            got['v'] = v
            dlg._providers(v)
        dlg._request('camera/providers', callback=_p, kind='status')
        t_prov = time.monotonic()
        while got['v'] is None and time.monotonic() - t_prov < 10:
            app.processEvents()
            time.sleep(0.05)

    # Prefer U3V CTI
    for i in range(dlg.provider.count()):
        text = str(dlg.provider.itemText(i))
        data = dlg.provider.itemData(i)
        if 'U3V' in text or (data and 'U3V' in str(data)):
            dlg.provider.setCurrentIndex(i)
            break
    if dlg.provider.count() and dlg.provider.currentIndex() < 0:
        dlg.provider.setCurrentIndex(0)

    device_id = None
    provider_id = dlg.provider.currentData()
    sess_file = ROOT / 'data' / 'native-desktop' / 'camera-session.json'
    if sess_file.exists():
        try:
            prev = json.loads(sess_file.read_text())
            params0 = (((prev.get('session') or {}).get('config') or {}).get('params') or {})
            device_id = params0.get('deviceId')
            if params0.get('providerId'):
                provider_id = params0.get('providerId')
                pi = dlg.provider.findData(provider_id)
                if pi >= 0:
                    dlg.provider.setCurrentIndex(pi)
        except Exception:
            pass
    if not device_id:
        device_id = 'Hikrobot MV-CB013-A0UM-C (K13917662)'
    dlg.device_id.setText(device_id)

    started = {'ok': False, 'err': None}

    def after_start(state):
        try:
            dlg._session(state)
            started['ok'] = (dlg.state.get('state') == 'running')
            if not started['ok']:
                started['err'] = str(state)
        except Exception as exc:
            started['err'] = str(exc)

    params = dlg.params()
    params['driver'] = 'gentl'
    params['deviceId'] = dlg.device_id.text()
    params['trigger'] = 'freerun'
    params['timeoutMs'] = 5000
    params['sessionPersist'] = True
    params['keepConnectionOpen'] = True
    params['continuousLive'] = True
    params['backendKind'] = 'gentl'
    params['providerId'] = provider_id or dlg.provider.currentData() or ''
    if not params['providerId']:
        print(json.dumps(dict(ok=False, err='no GenTL providerId', providers=dlg.provider.count()), ensure_ascii=False))
        backend.shutdown()
        return 4

    dlg._request('camera/session/start', dlg._config(params), after_start)

    t0 = time.monotonic()
    while not started['ok'] and time.monotonic() - t0 < 25:
        app.processEvents()
        time.sleep(0.05)
    if not started['ok']:
        # try status — maybe already running from prior
        st_box = {'s': None}

        def got(s):
            st_box['s'] = s
            dlg._session(s)

        dlg._request('camera/session/status', {}, got, kind='status')
        t1 = time.monotonic()
        while st_box['s'] is None and time.monotonic() - t1 < 5:
            app.processEvents()
            time.sleep(0.05)
        if dlg.state.get('state') != 'running':
            print(json.dumps(dict(ok=False, err='session start failed', detail=started['err'], state=dlg.state), ensure_ascii=False))
            backend.shutdown()
            return 3

    # Phase A: paint a few seconds
    phase_a_end = time.monotonic() + 4.0
    while time.monotonic() < phase_a_end:
        app.processEvents()
        time.sleep(0.02)

    painted_before_abort = not dlg.preview._source.isNull()
    fill_before = _label_fill(dlg.preview)

    # Phase B: simulate the bug path — abort while live capture may be pending
    dlg._live_pending = True  # force stuck as pre-fix would leave
    # Also abort any real pending capture (like Close/Cancel)
    dlg._abort_camera_actions('sim-abort')
    assert dlg._live_pending is False, 'abort must clear _live_pending'

    # Simulate hide/show reopen: stop timer (hideEvent), then _session restart
    dlg.live_timer.stop()
    # Force _session running branch to restart timer
    st = dict(dlg.state)
    st['state'] = 'running'
    # Make live_timer inactive path run
    dlg._session(st)
    assert dlg.live_timer.isActive(), 'live timer should restart'
    assert dlg._live_pending is False, 'restart must clear _live_pending'

    # Phase C: ≥15s continuous after reopen
    samples = []
    t_start = time.monotonic()
    next_sample = t_start + 2.0
    hang_gaps = []
    last_hb = time.monotonic()
    last_ui_n = getattr(dlg, '_ui_heartbeat_n', 0)
    while time.monotonic() - t_start < 15.0:
        app.processEvents()
        now = time.monotonic()
        ui_n = getattr(dlg, '_ui_heartbeat_n', 0)
        if ui_n != last_ui_n:
            hang_gaps.append(now - last_hb)
            last_hb = now
            last_ui_n = ui_n
        if now >= next_sample:
            fr = dlg.frame if isinstance(dlg.frame, dict) else {}
            img = fr.get('annotatedImage') or ''
            samples.append(dict(
                t=round(now - t_start, 2),
                fill=_label_fill(dlg.preview),
                jpeg=_jpeg_stats(img),
                live_pending=bool(dlg._live_pending),
                ui_hb=ui_n,
                src_null=bool(dlg.preview._source.isNull()),
            ))
            next_sample = now + 2.0
        time.sleep(0.02)

    grab = _grab_mean(dlg.preview)
    fill_after = _label_fill(dlg.preview)
    last_jpeg = samples[-1]['jpeg'] if samples else {}
    max_gap = max(hang_gaps) if hang_gaps else 99.0
    hb_n = getattr(dlg, '_ui_heartbeat_n', 0)

    # Stop session cleanly
    if dlg.state.get('id'):
        dlg._request('camera/session/stop', {'id': dlg.state.get('id')}, lambda *_: None)
        t2 = time.monotonic()
        while time.monotonic() - t2 < 3:
            app.processEvents()
            time.sleep(0.05)

    pass_paint = (
        fill_after.get('ok')
        and not fill_after.get('null')
        and float(last_jpeg.get('active_pct') or 0) >= 95.0
        and float(last_jpeg.get('mean') or 0) > 10.0
        and float(grab.get('mean') or 0) > 10.0
    )
    pass_hang = hb_n >= 10 and max_gap < 2.5
    pass_abort = painted_before_abort  # we had frames before simulated stuck
    # After fix, even if before_abort failed due to slow start, after must pass
    overall = bool(pass_paint and pass_hang)

    report = dict(
        ok=overall,
        sha=os.popen('git rev-parse --short HEAD').read().strip(),
        pass_paint=pass_paint,
        pass_hang=pass_hang,
        pass_abort_clears=True,
        painted_before_abort=painted_before_abort,
        fill_before=fill_before,
        fill_after=fill_after,
        grab=grab,
        last_jpeg=last_jpeg,
        samples=samples,
        ui_heartbeat=hb_n,
        max_gap_s=round(max_gap, 3),
        device=dlg.device_id.text(),
        session_id=dlg.state.get('id'),
        message=dlg.message.text(),
    )
    (OUT / 'verify-t236-camdialog-black.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8'
    )
    print(json.dumps(report, ensure_ascii=False))
    dlg.close()
    backend.shutdown()
    # give engine a moment
    t3 = time.monotonic()
    while time.monotonic() - t3 < 1.5:
        app.processEvents()
        time.sleep(0.05)
    return 0 if overall else 1


if __name__ == '__main__':
    raise SystemExit(main())
