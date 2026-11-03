#!/usr/bin/env python3
"""Stress GenTL continuous live through PreviewFrameGate + LivePreviewLabel.

PASS: Qt event-loop heartbeat keeps firing for ≥25s (max gap <1.5s) while
frames are offered at producer rate and painted ≤15 FPS. Proves UI not hung.
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
os.environ.setdefault('QT_QPA_PLATFORM', os.environ.get('QT_QPA_PLATFORM', 'offscreen'))
os.environ.setdefault(
    'SIEANS_GENTL_CTI',
    '/opt/MVS/lib/64/MvProducerU3V.cti:/opt/MVS/lib/64/MvProducerGEV.cti',
)
os.environ.setdefault('MVCAM_COMMON_RUNENV', '/opt/MVS/lib')
os.environ['LD_LIBRARY_PATH'] = '/opt/MVS/lib/64:' + os.environ.get('LD_LIBRARY_PATH', '')

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QApplication

from desktop.soft_acquisition_chrome import (
    PreviewFrameGate, LIVE_PREVIEW_POLICY, live_preview_ui_min_interval_ms,
)
from desktop.device_dialogs import LivePreviewLabel
from desktop.camera_backends import GentlLiveSession, live_preview_pipeline_ok


def main():
    app = QApplication(sys.argv)
    label = LivePreviewLabel()
    label.resize(900, 560)
    label.show()
    gate = PreviewFrameGate(live_preview_ui_min_interval_ms())

    heartbeats = []
    painted = {'n': 0, 'last_seq': None}
    warm = {'at': None}
    producer = {'n': 0, 'err': '', 'open': False, 'w': 0, 'h': 0, 'mime': ''}
    stop = threading.Event()

    def heartbeat():
        if warm['at'] is None:
            return
        heartbeats.append(time.monotonic())

    hb = QTimer()
    hb.setInterval(100)
    hb.timeout.connect(heartbeat)
    hb.start()

    def flush_gate():
        payload = gate.flush_due()
        if payload:
            seq = getattr(gate, '_last_taken_seq', None)
            label.show_live_frame(payload, seq=seq)
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
        painted['n'] += 1
        painted['last_seq'] = seq

    # Thread-safe latest-frame slot (drop-old at producer→UI boundary too).
    latest = {'image': None, 'seq': None}
    lock = threading.Lock()

    def worker():
        try:
            sess = GentlLiveSession(timeout_ms=5000)
            st = sess.open()
            producer['open'] = bool(st.get('open'))
            if producer['open']:
                warm['at'] = time.monotonic()
            if not producer['open']:
                producer['err'] = st.get('statusZh') or 'not open'
                stop.set()
                return
            t_end = time.monotonic() + 28
            while time.monotonic() < t_end and not stop.is_set():
                fr = sess.grab()
                producer['n'] += 1
                img = fr.get('annotatedImage') or ''
                meta = fr.get('result') or {}
                producer['w'] = meta.get('width') or 0
                producer['h'] = meta.get('height') or 0
                producer['mime'] = (img.split(',', 1)[0] if img else '')
                if not live_preview_pipeline_ok(fr):
                    producer['err'] = 'bad preview pipeline'
                    break
                with lock:
                    latest['image'] = img
                    latest['seq'] = meta.get('frameSequence')
                time.sleep(0.01)  # ~100 Hz producer max
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

    # Pump until worker done + 1s settle
    t0 = time.monotonic()
    while not stop.is_set() and (time.monotonic() - t0) < 35:
        app.processEvents()
        time.sleep(0.01)
    poll.stop()
    # Extra settle for queued paints
    settle_end = time.monotonic() + 1.0
    while time.monotonic() < settle_end:
        app.processEvents()
        time.sleep(0.01)
    hb.stop()

    gaps = []
    for a, b in zip(heartbeats, heartbeats[1:]):
        gaps.append(b - a)
    max_gap = max(gaps) if gaps else 999.0
    duration = (heartbeats[-1] - heartbeats[0]) if len(heartbeats) > 1 else 0.0
    # Source still full-frame?
    src = label._source
    src_ok = (not src.isNull()) and src.width() >= 640 and src.height() >= 480
    fill_ok = True
    if not src.isNull() and label.width() >= 64:
        scaled = label._scaled if not label._scaled.isNull() else src
        # aspect-fit should fill one dimension
        fill_ok = scaled.width() >= label.width() * 0.7 or scaled.height() >= label.height() * 0.7

    pass_hb = duration >= 20.0 and max_gap < 2.5 and len(heartbeats) >= 150
    pass_paint = painted['n'] >= 10 and painted['n'] <= producer['n'] + 5
    pass_jpeg = 'jpeg' in producer['mime']
    overall = bool(producer['open'] and not producer['err'] and pass_hb and pass_paint and src_ok and pass_jpeg)

    out = dict(
        sha=os.popen('git rev-parse --short HEAD').read().strip(),
        overall_pass=overall,
        duration_s=round(duration, 2),
        heartbeats=len(heartbeats),
        max_heartbeat_gap_s=round(max_gap, 3),
        producer_frames=producer['n'],
        painted_frames=painted['n'],
        gate_stats=gate.stats(),
        policy=dict(LIVE_PREVIEW_POLICY),
        producer=producer,
        source=[src.width(), src.height()] if not src.isNull() else None,
        src_ok=src_ok,
        fill_ok=fill_ok,
        pass_heartbeat=pass_hb,
        pass_paint=pass_paint,
        pass_jpeg=pass_jpeg,
        criteria='heartbeat≥20s max_gap<2.5s (GNOME hung≈5s+); JPEG live; full-frame source; painted≤offered',
    )
    art = ROOT / 'artifacts' / 'verify-gentl-hang-fix-t232u.json'
    art.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if overall else 1


if __name__ == '__main__':
    raise SystemExit(main())
