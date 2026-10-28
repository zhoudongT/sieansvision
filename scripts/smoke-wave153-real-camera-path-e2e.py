#!/usr/bin/env python3
"""wave153: real camera path start — Soft/UVC/GenTL pluggable backends + persist + UI wiring."""
from __future__ import annotations
import os, sys, ast, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / '.pydeps'))
os.chdir(ROOT)
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

fails, passes = [], []


def ok(n, c, d=''):
    if c:
        passes.append(n)
        print(f'PASS  {n}')
    else:
        fails.append(n)
        print(f'FAIL  {n}  {d}')


def main():
    from desktop.camera_backends import (
        BACKEND_KINDS, BACKEND_SOFT, BACKEND_UVC, BACKEND_GENTL,
        SoftBackend, UvcBackend, GentlBackend, get_backend, all_backends,
        backend_status_table, picker_choices, session_persist_flags,
        assert_uvc_session_persist_contract, kind_of_driver, driver_for_kind,
        soft_fallback_devices, SESSION_PERSIST,
    )

    ok('kinds Soft/UVC/GenTL', BACKEND_KINDS == (BACKEND_SOFT, BACKEND_UVC, BACKEND_GENTL))
    ok('picker 3 choices', len(picker_choices()) == 3)
    ok('driver soft→simulator', driver_for_kind('soft') == 'simulator')
    ok('driver uvc', driver_for_kind('uvc') == 'uvc')
    ok('driver gentl', driver_for_kind('gentl') == 'gentl')
    ok('kind_of uvc', kind_of_driver('uvc') == 'uvc')
    ok('kind_of gentl', kind_of_driver('gentl') == 'gentl')
    ok('kind_of simulator', kind_of_driver('simulator') == 'soft')
    ok('kind_of session nested uvc', kind_of_driver('session', nested={'params': {'driver': 'uvc'}}) == 'uvc')

    flags = session_persist_flags()
    ok('persist keepConnectionOpen', flags.get('keepConnectionOpen') is True)
    ok('persist openClosePerGrab False', flags.get('openClosePerGrab') is False)
    ok('persist reuseAcrossFrames', flags.get('reuseAcrossFrames') is True)
    ok('assert contract empty fails', assert_uvc_session_persist_contract(flags) == [])
    ok('assert contract catches bad', len(assert_uvc_session_persist_contract({'keepConnectionOpen': False, 'openClosePerGrab': True, 'reuseAcrossFrames': True})) >= 2)

    soft = SoftBackend()
    soft_av = soft.availability()
    ok('soft available', soft_av.get('available') is True)
    ok('soft status ready', soft_av.get('status') == 'ready')
    soft_devs = soft.enumerate_local()
    ok('soft enumerate ≥1', len(soft_devs) >= 1, soft_devs)
    ok('soft fallback same', len(soft_fallback_devices()) >= 1)
    soft_params = soft.connect_params('')
    ok('soft connect deviceId', soft_params.get('deviceId') == 'synthetic-parts')
    ok('soft connect persist', soft_params.get('keepConnectionOpen') is True and soft_params.get('openClosePerGrab') is False)
    ok('soft backendKind', soft_params.get('backendKind') == 'soft')

    uvc = UvcBackend()
    uvc_av = uvc.availability()
    ok('uvc has status', uvc_av.get('status') in ('ready', 'not_loaded', 'unsupported'), uvc_av)
    ok('uvc captureApi VideoCapture', uvc_av.get('captureApi') == 'VideoCapture' or not uvc_av.get('available'))
    ok('uvc openClosePerGrab False flag', uvc_av.get('openClosePerGrab') is False or 'sessionPersist' in uvc_av)
    ok('uvc sessionPersist contract', assert_uvc_session_persist_contract(uvc_av.get('sessionPersist')) == [])
    # Enumerate API path (may be empty without camera — still must not crash)
    try:
        uvc_devs = uvc.enumerate_local()
        ok('uvc enumerate API no crash', isinstance(uvc_devs, list), type(uvc_devs))
        if not uvc_devs:
            # soft-fallback path used by camera_manager when no hardware
            fb = soft_fallback_devices()
            ok('no-camera soft-fallback', len(fb) >= 1, fb)
        else:
            ok('uvc devices present', len(uvc_devs) >= 1, uvc_devs[:1])
            ok('uvc device has deviceId', bool(uvc_devs[0].get('deviceId')))
            ok('uvc device backendKind', uvc_devs[0].get('backendKind') == 'uvc')
    except Exception as exc:
        ok('uvc enumerate API no crash', False, str(exc))

    uvc_params = uvc.connect_params(uvc_devs[0]['deviceId'] if uvc_devs else '0')
    ok('uvc connect keepConnectionOpen', uvc_params.get('keepConnectionOpen') is True)
    ok('uvc connect openClosePerGrab False', uvc_params.get('openClosePerGrab') is False)
    ok('uvc connect sessionPersist', uvc_params.get('sessionPersist') is True)
    ok('uvc connect backendKind', uvc_params.get('backendKind') == 'uvc')
    ok('uvc warmupFrames', int(uvc_params.get('warmupFrames') or 0) >= 1)

    gentl = GentlBackend()
    g_av = gentl.availability()
    ok('gentl status honest', g_av.get('status') in ('ready', 'not_loaded', 'unsupported'), g_av)
    ok('gentl fakeFrames False', g_av.get('fakeFrames') is False)
    if not g_av.get('available'):
        ok('gentl unavailable → empty enumerate', gentl.enumerate_local() == [])
        ok('gentl statusZh present', bool(g_av.get('statusZh')), g_av)
    else:
        ok('gentl available path', True)

    table = backend_status_table()
    ok('status table 3', len(table) == 3, table)
    kinds = {r['kind'] for r in table}
    ok('table has all kinds', kinds == set(BACKEND_KINDS), kinds)
    ok('all_backends 3', len(all_backends()) == 3)
    ok('get_backend uvc', get_backend('uvc').kind == 'uvc')

    # Chrome badges for Soft/UVC/GenTL
    from desktop.soft_acquisition_chrome import (
        chrome_badge, backend_kind_bit, summarize_session, session_stat_rows,
        html_session_strip, fixed_bar_camera_text, REAL_DRIVERS, PreviewFrameGate,
    )
    ok('REAL_DRIVERS has uvc+gentl', REAL_DRIVERS == frozenset({'uvc', 'gentl'}))
    ok('bit soft', backend_kind_bit('soft') == '软')
    ok('bit uvc', backend_kind_bit('uvc') == 'UVC')
    ok('bit gentl', backend_kind_bit('gentl') == 'GTL')
    ok('badge soft', chrome_badge(soft=True, ready=True) == '采软✓')
    ok('badge uvc', 'UVC' in chrome_badge(backend_kind='uvc', ready=True, frame_seq=3))
    ok('badge gentl', 'GTL' in chrome_badge(backend_kind='gentl', ready=False))

    sess_uvc = summarize_session({
        'state': 'running', 'id': 's-uvc', 'received': 5,
        'config': {'params': {'driver': 'uvc', 'deviceId': '/dev/video0'}},
    })
    ok('session backendKind uvc', sess_uvc.get('backendKind') == 'uvc', sess_uvc)
    ok('session not soft', sess_uvc.get('soft') is False)
    ok('session badge UVC', 'UVC' in str(sess_uvc.get('badge')), sess_uvc.get('badge'))
    rows = session_stat_rows(sess_uvc)
    labels = [r[0] for r in rows]
    ok('stat has 后端种类', '后端种类' in labels, labels)
    html = html_session_strip(sess_uvc)
    ok('html mentions UVC or 采集', 'UVC' in html or '采集' in html, html[:160])
    ok('fixed bar uvc', 'UVC' in fixed_bar_camera_text(sess_uvc) or '采' in fixed_bar_camera_text(sess_uvc))

    sess_g = summarize_session({
        'state': 'idle',
        'config': {'params': {'driver': 'gentl', 'deviceId': 'cam1'}},
    })
    ok('session backendKind gentl', sess_g.get('backendKind') == 'gentl', sess_g)

    # PreviewFrameGate still works for real path producers
    gate = PreviewFrameGate(min_interval_ms=20)
    ok('gate first', gate.offer('f0', seq=0, now_ms=1000.0) == 'f0')
    ok('gate throttle', gate.offer('f1', seq=1, now_ms=1005.0) is None)

    # AST wiring
    for rel, needles in (
        ('desktop/camera_backends.py', ('BACKEND_UVC', 'SESSION_PERSIST', 'GentlBackend', 'fakeFrames', 'VideoCapture')),
        ('desktop/camera_manager.py', ('backend_kind', 'cameraBackendKind', '_current_kind', 'wave153', 'connect_params')),
        ('desktop/image_source.py', ('acquisitionBackend', 'imageSourceAcqBackend', '_on_acq_backend', 'wave153')),
        ('desktop/soft_acquisition_chrome.py', ('backend_kind_bit', 'REAL_DRIVERS', 'backendKind', 'UVC')),
        ('desktop/device_dialogs.py', ('wave153', 'keepConnectionOpen', 'backendKind')),
        ('docs/open-and-run-samples.md', ('wave153', 'camera_backends')),
        ('docs/camera-acquisition.md', ('wave153', 'VideoCapture', 'not_loaded')),
    ):
        text = (ROOT / rel).read_text(encoding='utf-8')
        ok(f'AST {rel}', isinstance(ast.parse(text), ast.AST) if rel.endswith('.py') else True)
        for n in needles:
            ok(f'{Path(rel).name} has {n}', n in text)

    # Qt dialog: Soft/UVC/GenTL combo present; soft enumerate without hardware
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from unittest.mock import MagicMock
    from desktop.camera_manager import CameraManagerDialog

    b = MagicMock()
    b.is_ready = False
    b.result = MagicMock()
    b.error = MagicMock()
    b.ready = MagicMock()
    b.request = MagicMock(return_value='rid')
    dlg = CameraManagerDialog(b, None)
    ok('dlg has backend_kind', hasattr(dlg, 'backend_kind'))
    kinds_ui = [dlg.backend_kind.itemData(i) for i in range(dlg.backend_kind.count())]
    ok('dlg kinds Soft/UVC/GenTL', set(kinds_ui) == {'soft', 'uvc', 'gentl'}, kinds_ui)
    # Soft path without engine
    dlg.backend_kind.setCurrentIndex(dlg.backend_kind.findData('soft'))
    dlg._refresh_devices()
    soft_ids = [dlg.camera_pick.itemData(i) for i in range(dlg.camera_pick.count())]
    ok('dlg soft lists synthetic', 'synthetic-parts' in soft_ids, soft_ids)
    # UVC with no engine → soft fallback or real list (no crash)
    dlg.backend_kind.setCurrentIndex(dlg.backend_kind.findData('uvc'))
    dlg._refresh_devices()
    ok('dlg uvc refresh no crash', dlg.camera_pick.count() >= 1)
    # GenTL honest when not loaded
    dlg.backend_kind.setCurrentIndex(dlg.backend_kind.findData('gentl'))
    dlg._refresh_backend_status()
    status_txt = dlg.backend_status.text()
    ok('dlg gentl status shown', '[' in status_txt and status_txt != '—', status_txt)
    params = dlg._params()
    ok('dlg params backendKind', params.get('backendKind') in ('soft', 'uvc', 'gentl'), params)
    ok('dlg params persist', params.get('keepConnectionOpen') is True and params.get('openClosePerGrab') is False, params)

    from desktop.image_source import ImageSourceForm
    form = ImageSourceForm({'mode': 'camera', 'acquisitionBackend': 'uvc'})
    ok('image_source has acq_backend', hasattr(form, 'acq_backend'))
    ok('image_source default uvc', form.acq_backend.currentData() == 'uvc', form.acq_backend.currentData())

    # unittest camera manager still importable
    from tests.test_camera_manager_dialog import CameraManagerDialogTests
    ok('legacy tests importable', CameraManagerDialogTests is not None)

    print(f'\n=== wave153 summary: {len(passes)} PASS / {len(fails)} FAIL ===')
    if fails:
        print('FAILED:', fails)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
