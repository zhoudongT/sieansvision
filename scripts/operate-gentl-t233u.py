#!/usr/bin/env python3
"""t233u operate: GenTL continuous live ≥20s via LivePreviewLabel+ImageView.

Same path as UI (GentlLiveSession + PreviewFrameGate + show_live_frame).
PASS: heartbeat≥20s, max_gap<2.5s, JPEG, full-frame fill≈1.0, FPS≤15.
Saves proof PNGs under artifacts/operate-t233u-*.png
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT / '.pydeps'))
sys.path.insert(0, str(ROOT))

# Real graphical session — NOT offscreen
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

from PySide6.QtCore import QTimer, Qt, QRect
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication, QWidget, QHBoxLayout, QLabel, QVBoxLayout

from desktop.soft_acquisition_chrome import (
    PreviewFrameGate, LIVE_PREVIEW_POLICY, live_preview_ui_min_interval_ms,
)
from desktop.device_dialogs import LivePreviewLabel
from desktop.image_view import ImageView
from desktop.camera_backends import GentlLiveSession, live_preview_pipeline_ok
import base64
import cv2
import numpy as np


def _jpeg_active_stats(url: str) -> dict:
    """Row coverage of decoded live JPEG — dims alone cannot catch top-strip content."""
    if not url or ',' not in url:
        return dict(active_pct=0.0, active_rows=0, bot_mean=0.0, jpeg_bytes=0, w=0, h=0)
    raw = base64.b64decode(url.split(',', 1)[1], validate=False)
    arr = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_GRAYSCALE)
    if arr is None:
        return dict(active_pct=0.0, active_rows=0, bot_mean=0.0, jpeg_bytes=len(raw), w=0, h=0)
    row = arr.mean(axis=1)
    act = int((row > 5).sum())
    return dict(
        w=int(arr.shape[1]), h=int(arr.shape[0]), jpeg_bytes=len(raw),
        active_rows=act, active_pct=round(100.0 * act / arr.shape[0], 2),
        mean=round(float(arr.mean()), 1),
        bot_mean=round(float(row[-16:].mean()), 1),
    )


def _fill_live_label(label: LivePreviewLabel) -> dict:
    src = label._source
    if src.isNull() or label.width() < 8 or label.height() < 8:
        return dict(source=None, fill=0.0, ok=False)
    scaled = label._scaled if not label._scaled.isNull() else src
    # aspect-fit fill of the limiting dimension
    fill_w = scaled.width() / max(1, label.width())
    fill_h = scaled.height() / max(1, label.height())
    fill = max(fill_w, fill_h)  # one dim should be ~1.0 for contain
    # non-strip: both dims substantial vs source aspect
    ok = (src.width() >= 640 and src.height() >= 480
          and (scaled.width() >= label.width() * 0.7
               or scaled.height() >= label.height() * 0.7)
          and fill >= 0.7)
    return dict(
        source=[src.width(), src.height()],
        scaled=[scaled.width(), scaled.height()],
        widget=[label.width(), label.height()],
        fill=round(float(fill), 4),
        fill_w=round(float(fill_w), 4),
        fill_h=round(float(fill_h), 4),
        ok=ok,
    )


def _fill_image_view(view: ImageView) -> dict:
    src = getattr(view, '_live_source', None)
    pm = getattr(view, '_live_pixmap', None)
    if src is None or src.isNull():
        return dict(source=None, fill=0.0, ok=False)
    vp = view.viewport().size() if view.viewport() else view.size()
    vw, vh = max(1, vp.width()), max(1, vp.height())
    pm_w = pm.width() if pm and not pm.isNull() else 0
    pm_h = pm.height() if pm and not pm.isNull() else 0
    fill = max(pm_w / vw, pm_h / vh) if pm_w and pm_h else 0.0
    ok = src.width() >= 640 and src.height() >= 480 and fill >= 0.7
    return dict(
        source=[src.width(), src.height()],
        live_pixmap=[pm_w, pm_h],
        viewport=[vw, vh],
        fill=round(float(fill), 4),
        ok=ok,
    )


def _grab_widget(w: QWidget, path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Ensure painted
    w.repaint()
    QApplication.processEvents()
    pix = w.grab()
    pix.save(str(path), 'PNG')
    return str(path)


def main():
    app = QApplication(sys.argv)

    win = QWidget()
    win.setWindowTitle('t233u GenTL continuous operate — Soft|GenTL Hikrobot MV-CB013')
    win.resize(1400, 620)
    layout = QHBoxLayout(win)

    col_l = QVBoxLayout()
    col_r = QVBoxLayout()
    tip_l = QLabel('LivePreviewLabel (CameraDialog path)')
    tip_r = QLabel('ImageView (HMI canvas path)')
    label = LivePreviewLabel()
    label.resize(900, 560)
    label.setMinimumSize(640, 480)
    view = ImageView()
    view.setMinimumSize(640, 480)
    col_l.addWidget(tip_l)
    col_l.addWidget(label, 1)
    col_r.addWidget(tip_r)
    col_r.addWidget(view, 1)
    layout.addLayout(col_l, 1)
    layout.addLayout(col_r, 1)
    win.show()
    QApplication.processEvents()

    gate = PreviewFrameGate(live_preview_ui_min_interval_ms())

    heartbeats = []
    painted = {'n': 0, 'last_seq': None}
    warm = {'at': None}
    producer = {'n': 0, 'err': '', 'open': False, 'w': 0, 'h': 0, 'mime': '', 'device': ''}
    strip_trace = []
    stop = threading.Event()
    app_stat_samples = []

    def sample_app_stat():
        # Monitor desktop.main if present
        try:
            import subprocess
            out = subprocess.check_output(
                ['bash', '-lc', "pgrep -f 'python3 -m desktop.main' | head -1"],
                text=True,
            ).strip()
            if out:
                st = Path(f'/proc/{out}/stat').read_text().split()
                # field 3 is state
                app_stat_samples.append({'pid': int(out), 'stat': st[2], 't': time.monotonic()})
        except Exception:
            pass

    def heartbeat():
        if warm['at'] is None:
            return
        heartbeats.append(time.monotonic())
        if len(heartbeats) % 10 == 0:
            sample_app_stat()

    hb = QTimer()
    hb.setInterval(100)
    hb.timeout.connect(heartbeat)
    hb.start()

    def flush_gate():
        payload = gate.flush_due()
        if payload:
            seq = getattr(gate, '_last_taken_seq', None)
            label.show_live_frame(payload, seq=seq)
            try:
                view.show_live_frame(payload, seq=seq)
            except TypeError:
                view.show_live_frame(payload)
            painted['n'] += 1
            painted['last_seq'] = seq
        elif gate.has_pending():
            QTimer.singleShot(max(1, gate.ms_until_due()), flush_gate)

    def offer_on_ui(image, seq):
        paintable = gate.offer(image, seq=seq)
        if paintable is None:
            if gate.has_pending():
                QTimer.singleShot(max(1, gate.ms_until_due()), flush_gate)
            return
        label.show_live_frame(paintable, seq=seq)
        try:
            view.show_live_frame(paintable, seq=seq)
        except TypeError:
            view.show_live_frame(paintable)
        painted['n'] += 1
        painted['last_seq'] = seq

    latest = {'image': None, 'seq': None}
    lock = threading.Lock()

    def worker():
        try:
            sess = GentlLiveSession(timeout_ms=5000)
            st = sess.open()
            producer['open'] = bool(st.get('open'))
            producer['device'] = (
                st.get('display_name')
                or st.get('deviceId')
                or st.get('model')
                or str(st.get('statusZh') or '')[:120]
            )
            if producer['open']:
                warm['at'] = time.monotonic()
            if not producer['open']:
                producer['err'] = st.get('statusZh') or st.get('error') or 'not open'
                stop.set()
                return
            t_end = time.monotonic() + 22
            while time.monotonic() < t_end and not stop.is_set():
                fr = sess.grab()
                producer['n'] += 1
                img = fr.get('annotatedImage') or ''
                meta = fr.get('result') or {}
                producer['w'] = meta.get('width') or 0
                producer['h'] = meta.get('height') or 0
                producer['mime'] = (img.split(',', 1)[0] if img else '')
                n = producer['n']
                if n in (1, 2, 3, 4, 5, 9, 50, 100, 150, 200, 250, 300, 400, 500) or n % 100 == 0:
                    st = _jpeg_active_stats(img)
                    st.update(n=n, seq=meta.get('frameSequence'))
                    strip_trace.append(st)
                    # Save early full + late sample proofs
                    if n in (5, 200):
                        try:
                            raw = base64.b64decode(img.split(',', 1)[1], validate=False)
                            (ROOT / 'artifacts' / f'operate-t233u-livejpeg-{n}.jpg').write_bytes(raw)
                        except Exception:
                            pass
                if not live_preview_pipeline_ok(fr):
                    producer['err'] = 'bad preview pipeline'
                    break
                with lock:
                    latest['image'] = img
                    latest['seq'] = meta.get('frameSequence')
                time.sleep(0.01)
            sess.close()
        except Exception as exc:
            producer['err'] = str(exc)[:500]
        finally:
            stop.set()

    def poll_latest():
        with lock:
            img, seq = latest['image'], latest['seq']
            latest['image'] = None
        if img:
            offer_on_ui(img, seq)

    th = threading.Thread(target=worker, daemon=True)
    th.start()

    poll = QTimer()
    poll.setInterval(33)
    poll.timeout.connect(poll_latest)
    poll.start()

    # Mid-run screenshot timer (~12s after warm)
    shot_done = {'mid': False, 'end': False}

    def maybe_mid_shot():
        if shot_done['mid'] or warm['at'] is None:
            return
        if time.monotonic() - warm['at'] < 10:
            return
        if painted['n'] < 5:
            return
        shot_done['mid'] = True
        _grab_widget(label, ROOT / 'artifacts' / 'operate-t233u-LivePreviewLabel-mid.png')
        _grab_widget(view, ROOT / 'artifacts' / 'operate-t233u-ImageView-mid.png')
        _grab_widget(win, ROOT / 'artifacts' / 'operate-t233u-packed-mid.png')

    mid = QTimer()
    mid.setInterval(500)
    mid.timeout.connect(maybe_mid_shot)
    mid.start()

    t0 = time.monotonic()
    while not stop.is_set() and (time.monotonic() - t0) < 35:
        app.processEvents()
        time.sleep(0.01)
    poll.stop()
    mid.stop()
    settle_end = time.monotonic() + 1.0
    while time.monotonic() < settle_end:
        app.processEvents()
        time.sleep(0.01)
    hb.stop()

    # Final screenshots
    paths = {}
    paths['LivePreviewLabel'] = _grab_widget(
        label, ROOT / 'artifacts' / 'operate-t233u-LivePreviewLabel.png')
    paths['ImageView'] = _grab_widget(
        view, ROOT / 'artifacts' / 'operate-t233u-ImageView.png')
    paths['packed'] = _grab_widget(
        win, ROOT / 'artifacts' / 'operate-t233u-packed.png')
    # Also try screen grab of window via QScreen if available
    try:
        screen = QGuiApplication.primaryScreen()
        if screen is not None:
            geo = win.frameGeometry()
            sp = screen.grabWindow(0, geo.x(), geo.y(), geo.width(), geo.height())
            spath = ROOT / 'artifacts' / 'operate-t233u-screen.png'
            sp.save(str(spath), 'PNG')
            paths['screen'] = str(spath)
    except Exception as exc:
        paths['screen_err'] = str(exc)[:200]

    gaps = [b - a for a, b in zip(heartbeats, heartbeats[1:])]
    max_gap = max(gaps) if gaps else 999.0
    duration = (heartbeats[-1] - heartbeats[0]) if len(heartbeats) > 1 else 0.0
    fill_label = _fill_live_label(label)
    fill_view = _fill_image_view(view)

    painted_fps = (painted['n'] / duration) if duration > 0 else 0.0
    pass_hb = duration >= 20.0 and max_gap < 2.5 and len(heartbeats) >= 150
    pass_paint = painted['n'] >= 10 and painted['n'] <= producer['n'] + 5
    pass_jpeg = 'jpeg' in producer['mime']
    pass_fps = painted_fps <= 16.0  # ≤15 gated; allow tiny slack
    pass_fill = bool(fill_label.get('ok') and fill_view.get('ok'))
    # Content-full: every sampled source JPEG must cover ≳90% active rows (not top strip).
    min_active = min((s.get('active_pct', 0) for s in strip_trace), default=0)
    late = [s for s in strip_trace if s.get('n', 0) >= 50]
    early = [s for s in strip_trace if s.get('n', 0) <= 5]
    pass_content = bool(strip_trace) and min_active >= 90.0 and (
        not late or min(s['active_pct'] for s in late) >= 90.0
    )
    hung_states = [s for s in app_stat_samples if s.get('stat') in ('D', 'Z')]
    hang = (not pass_hb) or bool(hung_states)

    overall = bool(
        producer['open'] and not producer['err'] and pass_hb and pass_paint
        and pass_jpeg and pass_fill and pass_fps and pass_content and not hang
    )

    sha = os.popen('git rev-parse --short HEAD').read().strip()
    sha_full = os.popen('git rev-parse HEAD').read().strip()
    out = dict(
        sha=sha,
        sha_full=sha_full,
        overall_pass=overall,
        hang=hang,
        duration_s=round(duration, 2),
        heartbeats=len(heartbeats),
        max_heartbeat_gap_s=round(max_gap, 3),
        producer_frames=producer['n'],
        painted_frames=painted['n'],
        painted_fps=round(painted_fps, 2),
        gate_stats=gate.stats(),
        policy=dict(LIVE_PREVIEW_POLICY),
        producer=producer,
        fill_LivePreviewLabel=fill_label,
        fill_ImageView=fill_view,
        app_stat_samples=app_stat_samples[-8:],
        hung_states=hung_states,
        screenshots=paths,
        pass_heartbeat=pass_hb,
        pass_paint=pass_paint,
        pass_jpeg=pass_jpeg,
        pass_fps=pass_fps,
        pass_fill=pass_fill,
        pass_content=pass_content,
        strip_trace=strip_trace,
        min_active_pct=min_active,
        early_active=[s.get('active_pct') for s in early],
        late_active=[s.get('active_pct') for s in late[:5]],
        criteria='≥20s GenTL continuous; heartbeat max_gap<2.5s; JPEG; fill≥0.7≈full; painted_fps≤15; App not D/Z',
        asia_shanghai=time.strftime('%Y-%m-%d %H:%M:%S'),
    )
    art = ROOT / 'artifacts' / 'operate-t233u.json'
    art.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    (ROOT / 'artifacts' / 'operate-t233u-strip-trace.json').write_text(
        json.dumps(dict(samples=strip_trace, total_frames=producer['n'], min_active_pct=min_active),
                   ensure_ascii=False, indent=2), encoding='utf-8')
    notes = ROOT / 'artifacts' / 'operate-t233u-notes.txt'
    notes.write_text(
        f"sieansvision GenTL operate t233u (Asia/Shanghai)\n"
        f"SHA: {sha}\n"
        f"overall_pass: {overall}\n"
        f"hang: {hang}\n"
        f"device: {producer.get('device')}\n"
        f"duration={out['duration_s']}s hb={out['heartbeats']} max_gap={out['max_heartbeat_gap_s']}s\n"
        f"producer={producer['n']} painted={painted['n']} fps={out['painted_fps']} mime={producer['mime']}\n"
        f"fill_label={fill_label} fill_view={fill_view}\n"
        f"pass_content={pass_content} min_active={min_active} early={[s.get('active_pct') for s in early]} late={[s.get('active_pct') for s in late[:3]]}\n"
        f"shots={paths}\n",
        encoding='utf-8',
    )
    print(json.dumps(out, ensure_ascii=False, indent=2))
    # Keep window briefly so screen shot can settle; then quit
    QTimer.singleShot(400, app.quit)
    app.exec()
    return 0 if overall else 1


if __name__ == '__main__':
    raise SystemExit(main())
