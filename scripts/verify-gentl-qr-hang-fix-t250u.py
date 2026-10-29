#!/usr/bin/env python3
"""t250u e2e: multi-click 「运行」must not freeze UI + continuous ≥60s (sieans_native GenTL/QR).

After c9854f6 single-run still hung when Allen clicked 运行 many times (busy released
before heavy finished UI + sync filmstrip JPEG decode). This script:
  1) Rapid-fires run_once N times (click storm) while measuring Qt heartbeat gaps
  2) Runs continuous ≥60s with max_gap < 2.0s
  3) Requires sieans_native acquire evidence + ≥1 QR hit

Exit 0 only when pass_multi AND pass_cont AND pass_native AND pass_qr.
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
from PySide6.QtWidgets import QApplication
import cv2

os.environ.setdefault('SIEANS_GENTL_CTI',
                      '/opt/MVS/lib/64/MvProducerU3V.cti:/opt/MVS/lib/64/MvProducerGEV.cti')
os.environ.setdefault('LD_LIBRARY_PATH',
                      '/opt/MVS/lib/64' + (os.pathsep + os.environ['LD_LIBRARY_PATH']
                                          if os.environ.get('LD_LIBRARY_PATH') else ''))
os.environ.setdefault('MVCAM_COMMON_RUNENV', '/opt/MVS/lib')
os.environ.setdefault('SIEANS_NATIVE', 'auto')
os.environ.setdefault('SIEANS_NATIVE_GENTL_ACQUIRE', 'auto')

DATA = ROOT / 'data' / 'native-desktop-t250u'
DATA.mkdir(parents=True, exist_ok=True)
ART = ROOT / 'artifacts' / 't250u'
ART.mkdir(parents=True, exist_ok=True)
PROJECT = str(ROOT / 'projects' / 'open-and-run-gentl-qr.sieans')

MULTI_CLICKS = 15
CONT_DURATION_S = 65.0
ENGINE_WAIT_S = 45.0
MAX_GAP_S = 2.0
MIN_HEARTBEATS_CONT = 400


def _grab_barcode_from_result(result: dict | None) -> dict:
    out = dict(count=0, text='', formats=[], annotated='')
    if not isinstance(result, dict):
        return out
    vars_ = result.get('variables') or {}
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
        payload = op_out.get('result') if isinstance(op_out.get('result'), dict) else op_out
        if op_out.get('annotatedImage') and (
                'count' in payload or 'items' in payload or not out['annotated']):
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
    return out


def _rss_mb() -> float:
    try:
        for line in Path('/proc/self/status').read_text().splitlines():
            if line.startswith('VmRSS:'):
                return int(line.split()[1]) / 1024.0
    except Exception:
        pass
    return -1.0


def main() -> int:
    os.system("pkill -f 'python3 -m desktop.main' 2>/dev/null || true")
    os.system("pkill -f 'cameras/session_worker.py' 2>/dev/null || true")
    try:
        Path('/tmp/sieans-gentl-acquire-backend.txt').unlink(missing_ok=True)
    except Exception:
        pass
    time.sleep(1.0)

    app = QApplication(sys.argv[:1])
    app.setOrganizationName('SIEANS')
    app.setApplicationName('SIEANS Vision t250u e2e')

    from desktop.mainwindow import MainWindow

    win = MainWindow(ROOT, DATA, project=PROJECT)
    win._maybe_open_and_run = lambda *a, **k: None
    win.resize(1400, 900)
    win.show()
    win.raise_()
    win.activateWindow()

    state = {
        'warm_at': None,
        'heartbeats': [],
        'multi_hbs': [],
        'cycles': 0,
        'multi_cycles': 0,
        'multi_accepted': 0,
        'multi_ignored_busy': 0,
        'qr_hits': 0,
        'last_barcode': {},
        'errors': [],
        'phase': 'wait_engine',
        'done': False,
        'rss_start': _rss_mb(),
        'rss_after_multi': -1.0,
        'rss_end': -1.0,
        'click_times': [],
    }

    _orig_finished = win.finished

    def _finished_wrap(result, release=True):
        try:
            state['cycles'] += 1
            if state['phase'] in ('multi', 'multi_settle'):
                state['multi_cycles'] += 1
            bc = _grab_barcode_from_result(result if isinstance(result, dict) else {})
            if bc.get('count', 0) > 0 or (bc.get('text') or '').strip():
                state['qr_hits'] += 1
                state['last_barcode'] = {k: v for k, v in bc.items() if k != 'annotated'}
                if bc.get('annotated') and not state.get('last_annotated'):
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
        now = time.monotonic()
        state['heartbeats'].append(now)
        if state['phase'] in ('multi', 'multi_settle'):
            state['multi_hbs'].append(now)

    hb = QTimer()
    hb.setInterval(100)
    hb.timeout.connect(heartbeat)
    hb.start()

    def _gap_stats(hbs):
        gaps = [hbs[i] - hbs[i - 1] for i in range(1, len(hbs))] if len(hbs) > 2 else [999]
        return {
            'n': len(hbs),
            'span_s': round((hbs[-1] - hbs[0]), 2) if len(hbs) > 2 else 0,
            'max_gap_s': round(max(gaps), 3) if gaps else 999,
        }

    def finalize():
        if state['done']:
            return
        state['done'] = True
        try:
            win.stop_run()
        except Exception:
            pass
        QTimer.singleShot(600, after_stop)
        QTimer.singleShot(20000, lambda: app.quit())

    def after_stop():
        state['rss_end'] = _rss_mb()
        try:
            pix = win.grab()
            pix.save(str(ART / 'app-end.png'))
        except Exception as exc:
            state['errors'].append(f'grab: {exc}')

        multi = _gap_stats(state['multi_hbs'])
        cont_hbs = [t for t in state['heartbeats'] if state.get('cont_at') and t >= state['cont_at']]
        cont = _gap_stats(cont_hbs)
        bc = state['last_barcode'] or {}
        pass_multi = (
            state['multi_accepted'] >= MULTI_CLICKS
            and state['multi_cycles'] >= max(3, MULTI_CLICKS // 3)
            and multi['max_gap_s'] < MAX_GAP_S
            and multi['span_s'] >= 2.0
        )
        # Allow some ignored clicks (busy guard working) as long as storm completed
        if state['multi_accepted'] + state['multi_ignored_busy'] >= MULTI_CLICKS:
            if state['multi_cycles'] >= max(3, MULTI_CLICKS // 4) and multi['max_gap_s'] < MAX_GAP_S:
                pass_multi = True
        pass_cont = (
            cont['span_s'] >= 55.0
            and cont['max_gap_s'] < MAX_GAP_S
            and cont['n'] >= MIN_HEARTBEATS_CONT
            and state['cycles'] >= state['multi_cycles'] + 10
        )
        pass_qr = bool(state['qr_hits'] >= 1 or bc.get('count', 0) >= 1 or (bc.get('text') or '').strip())
        backend_txt = ''
        bp = Path('/tmp/sieans-gentl-acquire-backend.txt')
        if bp.exists():
            backend_txt = bp.read_text(encoding='utf-8').strip()
        pass_native = 'sieans_native' in backend_txt
        rss_delta = (state['rss_end'] - state['rss_start']) if state['rss_start'] > 0 else -1
        # Hard fail if RSS grew by >1.5GB during the e2e (prior hang ~4GB)
        if rss_delta > 1500:
            state['errors'].append(f'rss growth {rss_delta:.0f}MB')
            pass_multi = False

        summary = {
            'pass_multi': pass_multi,
            'pass_cont': pass_cont,
            'pass_qr': pass_qr,
            'pass_native': pass_native,
            'pass': pass_multi and pass_cont and pass_qr and pass_native,
            'multi_clicks': MULTI_CLICKS,
            'multi_accepted': state['multi_accepted'],
            'multi_ignored_busy': state['multi_ignored_busy'],
            'multi_cycles': state['multi_cycles'],
            'multi_heartbeat': multi,
            'cont_heartbeat': cont,
            'cycles_total': state['cycles'],
            'qr_hits': state['qr_hits'],
            'barcode': bc,
            'rss_mb': {
                'start': round(state['rss_start'], 1),
                'after_multi': round(state['rss_after_multi'], 1),
                'end': round(state['rss_end'], 1),
                'delta': round(rss_delta, 1) if rss_delta >= 0 else -1,
            },
            'acquire_backend': backend_txt[:500],
            'errors': state['errors'][:12],
            'fix_tag': 't250u-multi-click',
            'zone': 'Asia/Shanghai',
        }
        (ART / 'summary.json').write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        state['summary'] = summary
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        QTimer.singleShot(200, app.quit)

    def fire_click():
        """One rapid 「运行」attempt — mirrors toolbar click under busy/finishing guard."""
        if state['done'] or state['phase'] != 'multi':
            return
        if state['multi_accepted'] + state['multi_ignored_busy'] >= MULTI_CLICKS:
            return
        busy = bool(getattr(win, 'busy', False) or getattr(win, '_finishing', False))
        if busy:
            state['multi_ignored_busy'] += 1
            state['click_times'].append(('ignored', time.monotonic()))
            return
        try:
            state['multi_accepted'] += 1
            state['click_times'].append(('accepted', time.monotonic()))
            if hasattr(win, 'run_once'):
                win.run_once()
            else:
                win.continuous = False
                win.run()
        except Exception as exc:
            state['errors'].append(f'click: {exc}')

    def on_tick():
        if state['done']:
            return
        now = time.monotonic()
        if state['phase'] == 'wait_engine':
            if not win.engine_ready:
                if now - t0 > ENGINE_WAIT_S:
                    state['errors'].append('engine_ready timeout')
                    finalize()
                return
            steps = (getattr(win, 'document', None) and win.document.project or {}).get('steps') or []
            if not steps:
                if now - t0 > ENGINE_WAIT_S:
                    state['errors'].append('project steps empty')
                    finalize()
                return
            state['phase'] = 'multi'
            state['warm_at'] = time.monotonic()
            state['multi_at'] = time.monotonic()
            win.log(f't250u e2e: multi-click storm x{MULTI_CLICKS}')
            # Fire first burst immediately, then every 30ms (faster than run can finish)
            fire_click()
            return

        if state['phase'] == 'multi':
            # Keep clicking rapidly until we have MULTI_CLICKS attempts
            attempts = state['multi_accepted'] + state['multi_ignored_busy']
            if attempts < MULTI_CLICKS:
                fire_click()
                return
            # Wait until in-flight finishes drain (busy/_finishing clear) or timeout
            if getattr(win, 'busy', False) or getattr(win, '_finishing', False):
                if now - state['multi_at'] > 90.0:
                    state['errors'].append('multi-click drain timeout 90s')
                    finalize()
                return
            if state['multi_cycles'] < 1:
                if now - state['multi_at'] > 60.0:
                    state['errors'].append('multi-click zero cycles')
                    finalize()
                return
            state['phase'] = 'multi_settle'
            state['settle_at'] = now
            state['rss_after_multi'] = _rss_mb()
            win.log(f"t250u e2e: multi done accepted={state['multi_accepted']} "
                    f"ignored={state['multi_ignored_busy']} cycles={state['multi_cycles']}")
            return

        if state['phase'] == 'multi_settle':
            if now - state['settle_at'] < 2.0:
                return
            state['phase'] = 'cont'
            try:
                win.run_continuous()
                state['cont_at'] = time.monotonic()
                win.log('t250u e2e: continuous started')
            except Exception as exc:
                state['errors'].append(f'run_continuous: {exc}')
                finalize()
            return

        if state['phase'] == 'cont':
            bc = _grab_barcode_from_result(getattr(win, 'last_result', None))
            if bc.get('count', 0) > 0 or bc.get('text'):
                state['last_barcode'] = {k: v for k, v in bc.items() if k != 'annotated'}
                if state['qr_hits'] == 0:
                    state['qr_hits'] = 1
            elapsed = now - state.get('cont_at', now)
            if elapsed >= CONT_DURATION_S:
                finalize()

    t0 = time.monotonic()
    tick = QTimer()
    tick.setInterval(30)  # aggressive multi-click cadence
    tick.timeout.connect(on_tick)
    tick.start()

    QTimer.singleShot(int((ENGINE_WAIT_S + CONT_DURATION_S + 120) * 1000), lambda: (
        state['errors'].append('absolute timeout'), finalize()))

    app.exec()
    summary = state.get('summary') or {'pass': False, 'errors': state['errors'] + ['no summary']}
    return 0 if summary.get('pass') else 2


if __name__ == '__main__':
    raise SystemExit(main())
