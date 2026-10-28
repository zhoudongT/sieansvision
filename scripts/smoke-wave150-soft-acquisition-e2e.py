#!/usr/bin/env python3
"""wave150: soft camera / acquisition open-and-run chrome — presence / ready / catalog."""
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
    from desktop.soft_acquisition_chrome import (
        PALETTE, LIVE_PREVIEW_POLICY, SOFT_DRIVERS,
        chrome_badge, is_soft_driver, soft_capture_ready, soft_capture_ready_reason,
        normalize_soft_capture_params, default_soft_device_id,
        summarize_session, session_stat_rows, html_session_strip,
        source_chrome_strip, project_soft_acquisition_summary,
        capture_result_chrome, live_preview_interval_ms, fixed_bar_camera_text,
    )

    ok('palette has soft+ok', all(k in PALETTE for k in ('soft', 'ok', 'ng')))
    ok('SOFT_DRIVERS has simulator', 'simulator' in SOFT_DRIVERS)
    ok('live policy antiFlicker', LIVE_PREVIEW_POLICY.get('antiFlicker') == 'in_place_pixmap')
    ok('live interval 50', live_preview_interval_ms() == 50)
    ok('manager interval 120', live_preview_interval_ms(manager=True) == 120)

    ok('is_soft simulator', is_soft_driver('simulator'))
    ok('not soft gentl', not is_soft_driver('gentl'))
    ok('default device synthetic-parts', default_soft_device_id('simulator') == 'synthetic-parts')
    ok('default rgbd', default_soft_device_id('rgbd_simulator') == 'synthetic-rgbd')

    bare = normalize_soft_capture_params({'driver': 'simulator'})
    ok('normalize fills deviceId', bare.get('deviceId') == 'synthetic-parts', bare)
    ok('normalize freerun', bare.get('trigger') == 'freerun')
    ok('soft ready True', soft_capture_ready(bare) is True)
    # reason may warn about empty device before normalize
    why = soft_capture_ready_reason({'driver': 'simulator'})
    ok('missing device reason', '设备标识' in why or why == '', why)

    badge = chrome_badge(soft=True, ready=True, frame_seq=3)
    ok('badge 采软3✓', badge == '采软3✓', badge)
    badge2 = chrome_badge(soft=True, ready=False)
    ok('badge 采软✗ or ·', badge2.startswith('采软'), badge2)

    sess = summarize_session({
        'state': 'running', 'id': 'sess-1', 'received': 12, 'consumed': 4,
        'overwritten': 1, 'reused': 0, 'frameAgeMs': 40,
        'config': {'params': {'driver': 'simulator', 'deviceId': 'synthetic-parts'}},
    })
    ok('session soft True', sess.get('soft') is True)
    ok('session badge has 采', '采' in str(sess.get('badge')), sess.get('badge'))
    ok('session summary non-empty', len(str(sess.get('summary') or '')) > 8, sess.get('summary'))
    rows = session_stat_rows(sess)
    ok('stat rows ≥8', len(rows) >= 8, len(rows))
    html = html_session_strip(sess)
    ok('html strip dark bg', '#1e2430' in html and '采' in html, html[:120])

    src = source_chrome_strip({'mode': 'local', 'images': ['public/vision/samples/parts.png']})
    ok('source local ready', src.get('ready') is True, src)
    src_empty = source_chrome_strip({'mode': 'local', 'images': []})
    ok('source empty not ready', src_empty.get('ready') is False)

    sample_path = ROOT / 'projects/open-and-run-soft-camera.sieans'
    ok('sample file exists', sample_path.is_file(), str(sample_path))
    proj = json.loads(sample_path.read_text(encoding='utf-8'))
    summ = project_soft_acquisition_summary(proj)
    ok('project soft steps ≥1', len(summ.get('softSteps') or []) >= 1, summ)
    ok('project ready', summ.get('ready') is True, summ)
    cap = next(s for s in proj['steps'] if s.get('operation') == 'camera_capture')
    ok('sample driver simulator', (cap.get('params') or {}).get('driver') == 'simulator')
    ok('sample deviceId set', bool((cap.get('params') or {}).get('deviceId')))

    cres = capture_result_chrome(
        {'width': 640, 'height': 400, 'frameSequence': 2, 'driver': 'simulator'},
        params=cap.get('params'),
    )
    ok('capture result soft', cres.get('soft') is True)
    ok('capture result size', cres.get('size') == '640×400', cres.get('size'))
    ok('fixed bar text soft', '软' in fixed_bar_camera_text(sess, bind='软模拟采集'), fixed_bar_camera_text(sess))

    # catalog parity
    from desktop.open_and_run_catalog import OPEN_AND_RUN_ENTRIES, expected_sample_files
    rels = [r for _, r in OPEN_AND_RUN_ENTRIES]
    ok('catalog lists soft-camera', 'projects/open-and-run-soft-camera.sieans' in rels, rels[-3:])
    ok('expected_sample includes soft-camera',
       'projects/open-and-run-soft-camera.sieans' in expected_sample_files())
    for rel in expected_sample_files():
        if 'soft-camera' in rel:
            ok('soft-camera file on disk', (ROOT / rel).is_file())

    # AST wiring
    for rel, needles in (
        ('desktop/image_source.py', ('soft_acquisition_chrome', '_refresh_acq_chrome', '_acq_chrome')),
        ('desktop/device_dialogs.py', ('soft_acquisition_chrome', 'summarize_session', 'wave150')),
        ('desktop/camera_manager.py', ('soft_acquisition_chrome', 'chrome_badge')),
        ('desktop/mainwindow.py', ('soft_acquisition_chrome', 'normalize_soft_capture_params', 'fixed_bar_camera_text')),
    ):
        src_txt = (ROOT / rel).read_text(encoding='utf-8')
        ok(f'AST {rel} parse', isinstance(ast.parse(src_txt), ast.AST))
        for n in needles:
            ok(f'{Path(rel).name} has {n}', n in src_txt)

    docs = (ROOT / 'docs/open-and-run-samples.md').read_text(encoding='utf-8')
    ok('docs mention wave150', 'wave150' in docs and 'soft-camera' in docs)
    readme = (ROOT / 'projects/README-open-and-run.md').read_text(encoding='utf-8')
    ok('readme lists soft-camera', 'open-and-run-soft-camera.sieans' in readme)

    # Qt ImageSource chrome strip
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    from desktop.image_source import ImageSourceForm
    form = ImageSourceForm({'mode': 'local', 'images': ['public/vision/samples/parts.png']})
    form.show()
    app.processEvents()
    ok('ImageSource has _acq_chrome', hasattr(form, '_acq_chrome'))
    ok('ImageSource has refresh API', hasattr(form, '_refresh_acq_chrome'))
    txt = form._acq_chrome.text() if form._acq_chrome is not None else ''
    ok('acq chrome html non-empty', len(txt) > 10 and ('采' in txt or '#' in txt), txt[:80])
    form._refresh_acq_chrome({'state': 'running', 'received': 5,
                              'config': {'params': {'driver': 'simulator', 'deviceId': 'synthetic-parts'}}})
    app.processEvents()
    txt2 = form._acq_chrome.text() or ''
    ok('acq chrome refreshes session', '采' in txt2, txt2[:100])

    # Preview anti-flicker still present
    from desktop.device_dialogs import _Preview
    ok('Preview docstring anti-clear', 'scene.clear' in (_Preview.__doc__ or ''))

    print()
    print(f'PASS {len(passes)}  FAIL {len(fails)}')
    if fails:
        print('Failed:', *fails, sep='\n  ')
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
