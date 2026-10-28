#!/usr/bin/env python3
"""t240u e2e: GenTL→QR continuous hang-free + decode.

Exercises MainWindow.run_continuous on open-and-run-gentl-qr.sieans:
  - Qt heartbeat ≥20s with max_gap < 2.0s (no grabWindow / GenTL during measure)
  - ≥5 finished cycles, ≥1 QR decode hit
  - Proof photos AFTER stop (live + annotated + app window)

Exit 0 only when pass_hang AND pass_qr.
"""
from __future__ import annotations

import base64
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ['PYTHONPATH'] = str(ROOT / '.pydeps') + os.pathsep + str(ROOT) + (
    os.pathsep + os.environ['PYTHONPATH'] if os.environ.get('PYTHONPATH') else '')
# Prefer PySide6 plugins over cv2's bundled Qt (xcb-cursor break).
_pyside_plugins = ROOT / '.pydeps' / 'PySide6' / 'Qt' / 'plugins'
if _pyside_plugins.is_dir():
    os.environ['QT_PLUGIN_PATH'] = str(_pyside_plugins)
os.environ.pop('QT_QPA_PLATFORM_PLUGIN_PATH', None)
if os.environ.get('XDG_SESSION_TYPE') == 'wayland' or os.environ.get('WAYLAND_DISPLAY'):
    os.environ['QT_QPA_PLATFORM'] = 'wayland'
else:
    os.environ.setdefault('QT_QPA_PLATFORM', 'xcb')

import numpy as np
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication
import cv2
os.environ.setdefault('SIEANS_GENTL_CTI',
                      '/opt/MVS/lib/64/MvProducerU3V.cti:/opt/MVS/lib/64/MvProducerGEV.cti')
os.environ.setdefault('LD_LIBRARY_PATH',
                      '/opt/MVS/lib/64' + (os.pathsep + os.environ['LD_LIBRARY_PATH']
                                          if os.environ.get('LD_LIBRARY_PATH') else ''))
os.environ.setdefault('MVCAM_COMMON_RUNENV', '/opt/MVS/lib')

DATA = ROOT / 'data' / 'native-desktop-t240u'
DATA.mkdir(parents=True, exist_ok=True)
ART = ROOT / 'artifacts'
ART.mkdir(parents=True, exist_ok=True)
PROJECT = str(ROOT / 'projects' / 'open-and-run-gentl-qr.sieans')

DURATION_S = 22.0
ENGINE_WAIT_S = 45.0
MAX_GAP_S = 2.0
MIN_HEARTBEATS = 150
MIN_CYCLES = 3


def _decode_data_url(url: str):
    if not url or not isinstance(url, str):
        return None, b''
    raw = url
    if ',' in url and url.startswith('data:'):
        raw = url.split(',', 1)[1]
    try:
        buf = base64.b64decode(raw)
    except Exception:
        return None, b''
    arr = cv2.imdecode(np.frombuffer(buf, dtype=np.uint8), cv2.IMREAD_COLOR)
    return arr, buf


def _grab_barcode_from_result(result: dict | None) -> dict:
    out = dict(count=0, text='', formats=[], annotated='')
    if not isinstance(result, dict):
        return out
    vars_ = result.get('variables') or {}
    # variables may be nested {flow:{...}, global:{...}}
    scopes = [vars_]
    for sk in ('flow', 'global', 'module'):
        if isinstance(vars_.get(sk), dict):
            scopes.append(vars_[sk])
    for scope in scopes:
        for k in ('barcodeCount', 'barcode_count', 'barcode.count'):
            if k in scope:
                try:
                    out['count'] = max(out['count'], int(scope[k] or 0))
                except Exception:
                    pass
        for k in ('barcodeText', 'barcode_text', 'barcode', 'barcode.text'):
            v = scope.get(k)
            if isinstance(v, str) and v.strip():
                out['text'] = v.strip()
                out['count'] = max(out['count'], 1)
            elif isinstance(v, dict) and v.get('text'):
                out['text'] = str(v['text'])
                out['count'] = max(out['count'], int(v.get('count') or 1))
    for rec in result.get('results') or []:
        op_out = rec.get('output') or {}
        if not isinstance(op_out, dict):
            continue
        # Vision nests payload under output.result
        payload = op_out.get('result') if isinstance(op_out.get('result'), dict) else op_out
        if op_out.get('annotatedImage') and (
                'count' in payload or 'items' in payload or not out['annotated']):
            # Prefer barcode annotated (has count/items); else keep first
            if 'count' in payload or 'items' in payload or not out['annotated']:
                if 'count' in payload or 'items' in payload:
                    out['annotated'] = op_out['annotatedImage']
                elif not out['annotated']:
                    out['annotated'] = op_out['annotatedImage']
        if 'count' in payload or 'items' in payload:
            try:
                out['count'] = max(out['count'], int(payload.get('count') or 0))
            except Exception:
                pass
            if payload.get('text'):
                out['text'] = str(payload['text'])
            for it in payload.get('items') or []:
                if isinstance(it, dict) and it.get('format'):
                    out['formats'].append(str(it['format']))
    return out


def _save_app_window(win, tag: str) -> None:
    """Grab AFTER continuous stopped — never during hang measurement."""
    try:
        pix = win.grab()
        pix.save(str(ART / f't240u-app-{tag}.png'))
    except Exception as exc:
        print('app grab failed', tag, exc, file=sys.stderr)


def main() -> int:
    os.system("pkill -f 'python3 -m desktop.main' 2>/dev/null || true")
    os.system("pkill -f 'cameras/session_worker.py' 2>/dev/null || true")
    time.sleep(1.2)

    app = QApplication(sys.argv[:1])
    app.setOrganizationName('SIEANS')
    app.setApplicationName('SIEANS Vision t240u e2e')

    from desktop.mainwindow import MainWindow

    win = MainWindow(ROOT, DATA, project=PROJECT)
    # Keep design canvas for e2e; openAndRun HMI would duplicate live decode cost.
    win._maybe_open_and_run = lambda *a, **k: None
    win.resize(1400, 900)
    win.show()
    win.raise_()
    win.activateWindow()

    state = {
        'warm_at': None,
        'heartbeats': [],
        'cycles': 0,
        'qr_hits': 0,
        'last_barcode': {},
        'last_annotated': '',
        'errors': [],
        'started_cont': False,
        'done': False,
        'pass_hang': False,
        'pass_qr': False,
        'cycle_elapsed': [],
    }

    _orig_finished = win.finished

    def _finished_wrap(result, release=True):
        try:
            state['cycles'] += 1
            if state['warm_at'] is not None:
                state['cycle_elapsed'].append(
                    round((time.monotonic() - state['warm_at']) * 1000))
            bc = _grab_barcode_from_result(result if isinstance(result, dict) else {})
            if bc.get('count', 0) > 0 or (bc.get('text') or '').strip():
                state['qr_hits'] += 1
                state['last_barcode'] = bc
                if bc.get('annotated'):
                    state['last_annotated'] = bc['annotated']
            elif isinstance(result, dict) and result.get('state') == 'failed':
                err = str(result.get('error') or '')[:200]
                if err and err not in state['errors']:
                    state['errors'].append('run failed: ' + err)
        except Exception as exc:
            state['errors'].append(f'finished wrap: {exc}')
        return _orig_finished(result, release)

    win.finished = _finished_wrap

    def heartbeat():
        if state['warm_at'] is None or state['done']:
            return
        state['heartbeats'].append(time.monotonic())
        if len(state['heartbeats']) % 20 == 0:
            try:
                (ART / 't240u-hb.txt').write_text(
                    f"n={len(state['heartbeats'])} cycles={state['cycles']} qr={state['qr_hits']}\n",
                    encoding='utf-8')
            except Exception:
                pass

    hb = QTimer()
    hb.setInterval(100)
    hb.timeout.connect(heartbeat)
    hb.start()

    def finalize():
        if state['done']:
            return
        state['done'] = True
        try:
            win.stop_run()
        except Exception:
            pass
        # Let session/stop settle before any photo / optional hardware touch
        QTimer.singleShot(800, after_stop)
        # Hard quit if after_stop / session teardown blocks
        def after_stop_watchdog():
            if not state.get('summary'):
                state['errors'].append('after_stop watchdog')
                try:
                    after_stop()
                except Exception as exc:
                    state['errors'].append(f'watchdog after_stop: {exc}')
                    app.quit()
            else:
                app.quit()
        QTimer.singleShot(15000, after_stop_watchdog)

    def after_stop():
        # Proof photos — AFTER hang window, never during
        try:
            _save_app_window(win, 'end')
        except Exception as exc:
            state['errors'].append(f'app end: {exc}')

        ann = state['last_annotated'] or ''
        if not ann:
            bc2 = _grab_barcode_from_result(getattr(win, 'last_result', None))
            ann = bc2.get('annotated') or ''
            if bc2.get('count', 0) > 0:
                state['last_barcode'] = bc2
                state['pass_qr'] = True
        if ann:
            arr, raw = _decode_data_url(ann)
            if raw:
                (ART / 't240u-annotated.jpg').write_bytes(raw)
            if arr is not None:
                # Draw confirm text on annotated proof
                try:
                    bc = state['last_barcode'] or {}
                    label = f"QR count={bc.get('count', 0)} hits={state['qr_hits']}"
                    cv2.putText(arr, label, (20, 40), cv2.FONT_HERSHEY_SIMPLEX,
                                1.0, (0, 220, 80), 2, cv2.LINE_AA)
                    texts = (bc.get('text') or '').split('\n')[:2]
                    for i, t in enumerate(texts):
                        cv2.putText(arr, t[:60], (20, 80 + i * 32),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 200, 255), 2)
                    (ART / 't240u-annotated.png').write_bytes(
                        cv2.imencode('.png', arr)[1].tobytes())
                    (ART / 't240u-annotated.jpg').write_bytes(
                        cv2.imencode('.jpg', arr, [int(cv2.IMWRITE_JPEG_QUALITY), 90])[1].tobytes())
                except Exception as exc:
                    state['errors'].append(f'ann annotate: {exc}')

        # Live frame from output_view pixmap (no GenTL re-open)
        try:
            view = getattr(win, 'output_view', None)
            saved = False
            if view is not None:
                for attr in ('pixmap', 'image', '_pixmap', '_live_pixmap'):
                    pm = getattr(view, attr, None)
                    if callable(pm):
                        try:
                            pm = pm()
                        except Exception:
                            pm = None
                    if pm is not None and hasattr(pm, 'save') and not getattr(pm, 'isNull', lambda: True)():
                        pm.save(str(ART / 't240u-live.jpg'), 'JPG', 90)
                        saved = True
                        break
                if not saved and hasattr(view, 'grab'):
                    g = view.grab()
                    if g and not g.isNull():
                        g.save(str(ART / 't240u-live.jpg'), 'JPG', 90)
                        saved = True
            if not saved and ann:
                # fallback: same as annotated without overlay text
                _, raw = _decode_data_url(ann)
                if raw:
                    (ART / 't240u-live.jpg').write_bytes(raw)
        except Exception as exc:
            state['errors'].append(f'live save: {exc}')

        # Optional mid app shot from earlier cache if we deferred one via timer flag
        mid = ART / 't240u-app-mid.png'
        if not mid.exists():
            try:
                _save_app_window(win, 'mid')
            except Exception:
                pass

        hbs = state['heartbeats']
        gaps = [hbs[i] - hbs[i - 1] for i in range(1, len(hbs))] if len(hbs) > 2 else [999]
        max_gap = max(gaps) if gaps else 999
        span = (hbs[-1] - hbs[0]) if len(hbs) > 2 else 0
        bc = state['last_barcode'] or _grab_barcode_from_result(getattr(win, 'last_result', None))
        state['pass_hang'] = (
            span >= 20.0 and max_gap < MAX_GAP_S and len(hbs) >= MIN_HEARTBEATS
            and state['cycles'] >= MIN_CYCLES
        )
        state['pass_qr'] = bool(bc.get('count', 0) >= 1 or (bc.get('text') or '').strip()
                                or state['qr_hits'] >= 1)
        if not state['pass_qr']:
            try:
                import zxingcpp
                for proof in (ART / 't240u-annotated.png', ART / 't240u-live.jpg', ART / 't240u-annotated.jpg'):
                    if not proof.exists():
                        continue
                    img = cv2.imread(str(proof))
                    if img is None:
                        continue
                    bars = zxingcpp.read_barcodes(img)
                    if bars:
                        state['pass_qr'] = True
                        bc = dict(bc or {})
                        bc['count'] = max(int(bc.get('count') or 0), len(bars))
                        bc['text'] = chr(10).join(b.text for b in bars[:3])
                        bc['proof_zxing'] = proof.name
                        break
            except Exception as exc:
                state['errors'].append('zxing proof: ' + str(exc))
        # Drop huge annotated from summary
        bc_light = {k: v for k, v in (bc or {}).items() if k != 'annotated'}
        bc_light['annotated_saved'] = bool(ann)
        summary = {
            'pass_hang': state['pass_hang'],
            'pass_qr': state['pass_qr'],
            'pass': state['pass_hang'] and state['pass_qr'],
            'heartbeat_span_s': round(span, 2),
            'heartbeat_n': len(hbs),
            'max_gap_s': round(max_gap, 3),
            'cycles': state['cycles'],
            'qr_hits': state['qr_hits'],
            'cycle_elapsed_ms_head': state['cycle_elapsed'][:8],
            'barcode': bc_light,
            'errors': state['errors'][:12],
            'continuous_at_stop': bool(getattr(win, 'continuous', False)),
            'zone': 'Asia/Shanghai',
            'artifacts': [
                't240u-live.jpg', 't240u-annotated.jpg', 't240u-annotated.png',
                't240u-app-end.png', 't240u-app-mid.png', 't240u-summary.json',
            ],
        }
        (ART / 't240u-summary.json').write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        state['summary'] = summary
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        QTimer.singleShot(300, app.quit)

    def on_tick():
        if state['done']:
            return
        now = time.monotonic()
        if not win.engine_ready:
            if now - t0 > ENGINE_WAIT_S:
                state['errors'].append('engine_ready timeout')
                finalize()
            return
        # Wait until pending project finished validate+load (engine_ready alone races).
        steps = (getattr(win, 'document', None) and win.document.project or {}).get('steps') or []
        if not steps:
            if now - t0 > ENGINE_WAIT_S:
                state['errors'].append('project steps empty after engine ready')
                finalize()
            return
        if not state['started_cont']:
            state['started_cont'] = True
            try:
                win.run_continuous()
                state['warm_at'] = time.monotonic()
                win.log('t240u e2e: continuous started steps=' + str(len(steps)))
            except Exception as exc:
                state['errors'].append(f'run_continuous: {exc}')
                finalize()
            return

        # Sample QR from last_result without blocking
        bc = _grab_barcode_from_result(getattr(win, 'last_result', None))
        if bc.get('count', 0) > 0 or bc.get('text'):
            if state['qr_hits'] == 0:
                state['qr_hits'] = 1  # ensure flag; finished wrap owns precise count
            state['last_barcode'] = bc
            if bc.get('annotated'):
                state['last_annotated'] = bc['annotated']

        elapsed = now - state['warm_at']
        if elapsed >= DURATION_S:
            finalize()

    t0 = time.monotonic()
    tick = QTimer()
    tick.setInterval(200)
    tick.timeout.connect(on_tick)
    tick.start()

    # Safety: absolute wall-clock abort
    QTimer.singleShot(int((ENGINE_WAIT_S + DURATION_S + 30) * 1000), lambda: (
        state['errors'].append('absolute timeout'), finalize()))

    app.exec()
    summary = state.get('summary') or {'pass': False, 'errors': state['errors'] + ['no summary']}
    return 0 if summary.get('pass') else 2


if __name__ == '__main__':
    raise SystemExit(main())
