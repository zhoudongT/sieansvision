#!/usr/bin/env python3
"""wave156: TCP deepen + camera soft controls + whole-UI adaptability smoke.

Covers:
  • TCP: len4 framing, keep-alive flag, reconnect option, session pool, transcript filter, persist
  • Camera: soft exposure/gain/trigger, picker labels, last-device persist, reconnect flags
  • UI: MainWindow resize 1280×720 / 1600×900 / 1920×1080 — critical widgets non-zero geometry

No Halcon / robot / cloud. No :18280. Soft/loopback only.
PASS/FAIL counters; exit 1 on any FAIL.
"""
from __future__ import annotations
import ast
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / '.pydeps'))
os.chdir(ROOT)
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

fails, passes = [], []


def ok(name, cond, detail=''):
    if cond:
        passes.append(name)
        print(f'PASS  {name}')
    else:
        fails.append(name)
        print(f'FAIL  {name}  {detail}')


def main():
    # ---------- TCP deepen ----------
    from desktop import tcp_realtime as rt

    ok('framings include len4', rt.FRAMING_LEN4 in rt.FRAMINGS and 'lf' in rt.FRAMINGS)
    ok('normalize framing', rt.normalize_framing('LEN4') == 'len4')
    ok('framing label', 'Len4' in rt.framing_label('len4') or '长度' in rt.framing_label('len4'))

    # LF loopback still works
    r = rt.loopback_e2e(host='127.0.0.1', port=0, payload='PING', ack='OK', framing='lf')
    ok('lf loopback', r.get('ok') is True, r)
    ok('lf framing echo', r.get('framing') == 'lf', r)

    # Len4 loopback
    r4 = rt.loopback_e2e(host='127.0.0.1', port=0, payload='LEN4-HI', ack='ACK4', framing='len4')
    ok('len4 loopback', r4.get('ok') is True, r4)
    ok('len4 reply', r4.get('reply') == 'ACK4', r4)
    ok('len4 framing', r4.get('framing') == 'len4', r4)

    # Session pool longer-lived
    rt.session_pool_clear()
    pooled = rt.pooled_loopback_session(host='127.0.0.1', port=0, framing='lf', ack='OK')
    ok('pool start', pooled.get('ok') is True, pooled)
    ok('pool size>=1', rt.session_pool_size() >= 1, rt.session_pool_size())
    key = pooled.get('key')
    port = int(pooled.get('port') or 0)
    cli = rt.RealTcpSession(host='127.0.0.1', port=port, role=rt.ROLE_CLIENT, framing='lf')
    ex = cli.send('POOL', wait_reply=True, timeout_s=2.0)
    ok('pool exchange', ex.get('ok') and ex.get('reply') == 'OK', ex)
    reused = rt.pooled_loopback_session(host='127.0.0.1', port=0, framing='lf')
    ok('pool reuse', reused.get('reused') is True, reused)
    rt.session_pool_drop(key)
    cli.stop()
    ok('pool dropped', rt.session_pool_get(key) is None)

    # Keep-alive + reconnect flags on status
    srv = rt.RealTcpSession(host='127.0.0.1', port=0, role=rt.ROLE_SERVER, keep_alive=True, framing='lf')
    st = srv.start()
    ok('keepalive status', st.get('keepAlive') is True and st.get('status') == 'listening', st)
    c2 = rt.RealTcpSession(
        host='127.0.0.1', port=int(st['port']), role=rt.ROLE_CLIENT,
        keep_alive=True, reconnect=True, reconnect_max=2, reconnect_ms=100,
    )
    st2 = c2.start()
    ok('client connected keepalive', st2.get('status') == 'connected' and st2.get('reconnect') is True, st2)
    c2.stop(); srv.stop()

    # Transcript filter
    lines = [
        '[12:00:00.001] TX path=tcp-real 127.0.0.1:1 │ hello',
        '[12:00:00.002] RX path=tcp-real 127.0.0.1:1 │ OK',
        '[12:00:00.003] SYS path=tcp-real 127.0.0.1:1 │ CLOSE',
        '[12:00:00.004] ERR path=tcp-real 127.0.0.1:1 │ boom',
    ]
    only_tx = rt.filter_transcript(lines, directions=['TX'])
    ok('filter TX', len(only_tx) == 1 and 'TX' in only_tx[0], only_tx)
    ok('filter contains', len(rt.filter_transcript(lines, text_contains='boom')) == 1)

    # Persist host/port
    proj = {}
    saved = rt.save_tcp_persist(proj, host='127.0.0.1', port=19955, framing='len4', keepAlive=True)
    loaded = rt.load_tcp_persist(proj)
    ok('persist save', saved.get('framing') == 'len4' and proj['commManager']['tcpReal']['port'] == 19955)
    ok('persist load', loaded.get('host') == '127.0.0.1' and loaded.get('framing') == 'len4')

    # CommManager UI contract
    src = (ROOT / 'desktop/comm_manager.py').read_text(encoding='utf-8')
    ok('UI framing', 'commTcpRealFraming' in src)
    ok('UI keepalive', 'commTcpRealKeepAlive' in src)
    ok('UI filter', 'commTcpRealFilter' in src)
    ok('UI persist btn', 'commTcpRealPersist' in src)
    ok('UI tcp scroll', 'commTcpScroll' in src)

    # ---------- Camera deepen ----------
    from desktop.camera_backends import (
        soft_controls_defaults, clamp_exposure_us, clamp_gain_db, normalize_trigger,
        format_device_picker_label, save_last_device, load_last_device, pick_last_or_first,
        soft_controls_roundtrip, UvcLiveSession, SoftBackend, TRIGGER_MODES,
        apply_soft_controls_to_bgr, _soft_synthetic_bgr, live_preview_pipeline_ok,
    )
    ok('trigger modes', set(TRIGGER_MODES) >= {'freerun', 'software', 'line0'})
    ok('clamp exposure', clamp_exposure_us(50) == 100 and clamp_exposure_us(99999999) == 10_000_000)
    ok('clamp gain', clamp_gain_db(-1) == 0.0 and clamp_gain_db(100) == 48.0)
    ok('norm trigger', normalize_trigger('SOFTWARE') == 'software')
    dflt = soft_controls_defaults()
    ok('soft defaults', dflt.get('exposureUs') == 10000 and dflt.get('trigger') == 'freerun')

    lab = format_device_picker_label(
        {'name': 'CamA', 'model': 'X1', 'deviceId': 'dev-1', 'index': 0}, kind='uvc',
    )
    ok('picker label rich', 'CamA' in lab and 'uvc' in lab.lower() or '[uvc]' in lab, lab)

    save_last_device(kind='soft', device_id='synthetic-parts', label='Soft')
    last = load_last_device()
    ok('last device save', last.get('deviceId') == 'synthetic-parts' and last.get('kind') == 'soft', last)
    devices = SoftBackend().enumerate_local()
    picked = pick_last_or_first(devices, kind='soft')
    ok('pick last soft', picked is not None and picked.get('deviceId') == 'synthetic-parts', picked)

    rt_ctrl = soft_controls_roundtrip(exposure_us=8000, gain_db=3.0)
    ok('soft controls roundtrip', rt_ctrl.get('ok') and rt_ctrl.get('pipeline'), rt_ctrl)
    ok('soft controls echo', rt_ctrl.get('exposureUs') == 8000 and float(rt_ctrl.get('gainDb') or 0) == 3.0, rt_ctrl)

    img = apply_soft_controls_to_bgr(_soft_synthetic_bgr(seq=1), exposure_us=20000, gain_db=6.0, seq=1)
    ok('soft bgr apply', img is not None and getattr(img, 'shape', None) is not None)

    with UvcLiveSession(soft_fallback=True, exposure_us=5000, gain_db=2.0, auto_reconnect=True) as sess:
        st = sess.status()
        ok('uvc soft reconnect flag', st.get('reconnectResilient') is True and st.get('autoReconnect') is True, st)
        f = sess.grab()
        ok('uvc soft grab ctrl', f['result'].get('exposureUs') == 5000, f['result'])

    cam_src = (ROOT / 'desktop/camera_manager.py').read_text(encoding='utf-8')
    ok('cam UI exposure', 'cameraExposureUs' in cam_src)
    ok('cam UI gain', 'cameraGainDb' in cam_src)
    ok('cam UI trigger', 'cameraTriggerMode' in cam_src)
    ok('cam min size', 'setMinimumSize(640, 420)' in cam_src)

    # ---------- Whole-UI adaptability ----------
    from PySide6.QtWidgets import (
        QApplication, QToolBar, QSplitter, QPushButton, QScrollArea, QComboBox, QSpinBox,
    )
    app = QApplication.instance() or QApplication([])

    from desktop.mainwindow import MainWindow
    win = MainWindow(ROOT, ROOT / 'data/native-desktop', start_engine=False, project=None)
    win.show()
    app.processEvents()

    sizes = [(1280, 720), (1600, 900), (1920, 1080), (1280, 1024)]

    def geom_ok(w, label, min_w=1, min_h=1):
        if w is None:
            ok(f'{label} present', False, 'None')
            return False
        g = w.geometry()
        good = g.width() >= min_w and g.height() >= min_h
        ok(f'{label} geom', good, f'{g.width()}x{g.height()}')
        return good

    for w, h in sizes:
        win.resize(w, h)
        if hasattr(win, 'apply_responsive_layout'):
            win.apply_responsive_layout(w, h)
        app.processEvents()
        time.sleep(0.02)
        app.processEvents()
        tag = f'{w}x{h}'
        ok(f'resize {tag}', win.width() >= w - 40 and win.height() >= h - 40, f'{win.width()}x{win.height()}')
        toolbars = win.findChildren(QToolBar)
        ok(f'{tag} toolbar', len(toolbars) >= 1 and all(t.height() > 0 or not t.isVisible() for t in toolbars[:1]), len(toolbars))
        splits = win.findChildren(QSplitter)
        ok(f'{tag} splitters', len(splits) >= 1)
        # no zero-geometry for critical panes when visible
        for sp in splits:
            for i in range(sp.count()):
                child = sp.widget(i)
                if child is None or not child.isVisible():
                    continue
                g = child.geometry()
                # collapsed panes may be width 0 intentionally in run mode — only flag if both 0
                if g.width() == 0 and g.height() == 0:
                    ok(f'{tag} splitter child non-zero', False, child.objectName() or type(child).__name__)
                    break
        else:
            ok(f'{tag} splitter children ok', True)
        flow = getattr(win, '_flow_pane', None)
        img = getattr(win, '_image_pane', None)
        if flow is not None and flow.isVisible():
            geom_ok(flow, f'{tag} flow', 40, 40)
        else:
            ok(f'{tag} flow (hidden ok)', True)
        if img is not None and img.isVisible():
            geom_ok(img, f'{tag} image', 40, 40)
        else:
            ok(f'{tag} image (hidden ok)', True)
        geom_ok(getattr(win, 'results', None), f'{tag} results', 10, 10)
        # run-mode operator HMI
        try:
            if hasattr(win, 'set_app_mode'):
                win.set_app_mode('run')
            app.processEvents()
            hmi = win.operator_hmi
            ok(f'{tag} hmi present', hmi is not None)
            from desktop.image_view import ImageView
            ivs = hmi.findChildren(ImageView) if hmi else []
            if ivs:
                # may be hidden offscreen — check minimumSizeHint / sizePolicy instead of mapped geom
                v = ivs[0]
                ok(f'{tag} hmi preview minH', v.minimumHeight() >= 100, v.minimumHeight())
            else:
                ok(f'{tag} hmi preview', len(getattr(hmi, '_image_views', []) or []) >= 1)
            btns = hmi.findChildren(QPushButton) if hmi else []
            ok(f'{tag} hmi run btns', len(btns) >= 1, len(btns))
            if hasattr(win, 'set_app_mode'):
                win.set_app_mode('design')
            app.processEvents()
        except Exception as exc:
            ok(f'{tag} run-mode', False, str(exc))

    # Comm manager dialog
    try:
        from desktop.comm_manager import CommManagerDialog, default_comm_manager

        class Doc:
            project = {'commManager': default_comm_manager()}

        dlg = CommManagerDialog(Doc())
        dlg.show()
        app.processEvents()
        for w, h in ((900, 560), (1100, 700)):
            dlg.resize(w, h)
            app.processEvents()
            scrolls = [s for s in dlg.findChildren(QScrollArea) if s.objectName() == 'commTcpScroll']
            ok(f'comm {w}x{h} tcp scroll', len(scrolls) == 1)
            framing = None
            for cb in dlg.findChildren(QComboBox):
                if cb.objectName() == 'commTcpRealFraming':
                    framing = cb
                    break
            ok(f'comm {w}x{h} framing combo', framing is not None and framing.count() >= 4,
               framing.count() if framing else 0)
            # exercise filter + persist
            if hasattr(dlg, 'tcp_real_filter'):
                dlg.tcp_real_filter.setCurrentIndex(1)
                dlg._tcp_real_append_transcript(['[00:00:00.000] TX path=tcp-real │ hi', '[00:00:00.001] RX path=tcp-real │ OK'])
                app.processEvents()
                ok(f'comm {w}x{h} filter applied', 'TX' in dlg.tcp_real_transcript.toPlainText())
            if hasattr(dlg, '_tcp_real_persist_to_project'):
                dlg._tcp_real_persist_to_project()
                ok(f'comm {w}x{h} persist', isinstance((Doc.project.get('commManager') or {}).get('tcpReal'), dict))
        # UI loopback with len4
        if hasattr(dlg, 'tcp_real_framing'):
            li = dlg.tcp_real_framing.findData('len4')
            if li >= 0:
                dlg.tcp_real_framing.setCurrentIndex(li)
            dlg.tcp_transport.setCurrentIndex(dlg.tcp_transport.findData('tcp'))
            ui_r = dlg._tcp_real_loopback()
            ok('UI len4 loopback', ui_r.get('ok') is True and ui_r.get('framing') == 'len4', ui_r)
        dlg.close()
    except Exception as exc:
        ok('comm dialog', False, str(exc))

    # Camera manager dialog
    try:
        from unittest.mock import MagicMock
        from desktop.camera_manager import CameraManagerDialog

        class _Be:
            is_ready = False
            result = MagicMock()
            error = MagicMock()
            ready = MagicMock()

        cdlg = CameraManagerDialog(_Be(), parent=None)
        cdlg.show()
        app.processEvents()
        for w, h in ((640, 420), (860, 560), (1100, 700)):
            cdlg.resize(w, h)
            app.processEvents()
            ok(f'camdlg {w}x{h}', cdlg.width() >= w - 40 and cdlg.height() >= h - 40,
               f'{cdlg.width()}x{cdlg.height()}')
            exp = next((sp for sp in cdlg.findChildren(QSpinBox) if sp.objectName() == 'cameraExposureUs'), None)
            ok(f'camdlg {w}x{h} exposure', exp is not None)
        # soft enumerate polish
        try:
            cdlg.backend_kind.setCurrentIndex(cdlg.backend_kind.findData('soft'))
            cdlg._refresh_devices()
            app.processEvents()
            ok('cam soft enumerate', cdlg.camera_pick.count() >= 2, cdlg.camera_pick.count())
        except Exception as exc:
            ok('cam soft enumerate', False, str(exc))
        cdlg.close()
    except Exception as exc:
        ok('camera dialog', False, str(exc))

    # Source contracts
    mw = (ROOT / 'desktop/mainwindow.py').read_text(encoding='utf-8')
    ok('mw responsive helper', 'apply_responsive_layout' in mw)
    ok('mw min 1024', 'setMinimumSize(1024,640)' in mw or 'setMinimumSize(1024, 640)' in mw)

    # Syntax of touched modules
    for rel in (
        'desktop/tcp_realtime.py', 'desktop/comm_manager.py',
        'desktop/camera_backends.py', 'desktop/camera_manager.py',
        'desktop/mainwindow.py', 'desktop/operator_hmi.py',
    ):
        try:
            ast.parse((ROOT / rel).read_text(encoding='utf-8'))
            ok(f'syntax {rel}', True)
        except SyntaxError as e:
            ok(f'syntax {rel}', False, str(e))

    try:
        win.hide()
        win.deleteLater()
        app.processEvents()
    except Exception:
        pass
    print()
    print(f'PASS={len(passes)} FAIL={len(fails)}')
    if fails:
        print('Failed:', *fails, sep='\n  - ')
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
