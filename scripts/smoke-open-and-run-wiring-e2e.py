#!/usr/bin/env python3
"""Offscreen: openAndRun helpers + relative path rebase + panel okVar."""
import os, sys, json, ast
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / '.pydeps'))

pass_n = fail_n = 0

def ok(m):
    global pass_n; pass_n += 1; print('PASS:', m)

def bad(m):
    global fail_n; fail_n += 1; print('FAIL:', m)

# 1) project relative images + openAndRun
proj = json.loads((ROOT / 'projects/default-platform.sieans').read_text(encoding='utf-8'))
imgs = (proj.get('sourceConfig') or {}).get('images') or []
if imgs and all(not Path(i).is_absolute() for i in imgs):
    ok('default-platform images relative')
else:
    bad(f'images not relative: {imgs}')
for i in imgs:
    if not (ROOT / i).is_file():
        bad(f'missing sample {i}')
    else:
        ok(f'sample exists {Path(i).name}')
meta = ((proj.get('runUi') or {}).get('meta') or {})
ok('openAndRun') if meta.get('openAndRun') else bad('openAndRun missing')

# 2) mainwindow helpers present
mw = (ROOT / 'desktop/mainwindow.py').read_text(encoding='utf-8')
for name in ('_rebase_source_images', '_maybe_open_and_run', 'openAndRun'):
    if name in mw:
        ok(f'mainwindow has {name}')
    else:
        bad(f'mainwindow missing {name}')
ast.parse(mw); ok('mainwindow ast')

# 3) panel okVar + flow-control deepen markers
w3 = (ROOT / 'desktop/wave3_thin_panels.py').read_text(encoding='utf-8')
ok('panel okVar') if "okVar" in w3 and 'passGate' in w3 else bad('panel okVar')
fc = (ROOT / 'lib/flow-control.cjs').read_text(encoding='utf-8')
for needle in ('skipped_ng', 'timestampPrefix', 'onEmpty', 'fixedWidths', 'filePrefix'):
    ok(f'flow-control {needle}') if needle in fc else bad(f'missing {needle}')

# 4) Qt: MainWindow rebase method callable shape
from PySide6.QtWidgets import QApplication
app = QApplication.instance() or QApplication([])
from desktop.mainwindow import MainWindow
win = MainWindow(ROOT, ROOT / 'data/native-desktop', start_engine=False, project=None)
fake = {
    'sourceConfig': {
        'mode': 'local',
        'images': [str(ROOT / 'public/vision/samples/circle-ring.png')],
        'currentIndex': 0,
    }
}
out = win._rebase_source_images(fake)
imgs2 = out['sourceConfig']['images']
if imgs2 and not Path(imgs2[0]).is_absolute():
    ok(f'rebase → {imgs2[0]}')
else:
    bad(f'rebase failed {imgs2}')
# openAndRun no-op without flag
win.document.project = {'runUi': {'meta': {}}}
win._maybe_open_and_run()
ok('openAndRun no-op without flag')
win.document.project = {
    'runUi': {'meta': {'openAndRun': True}},
    'sourceConfig': {'mode': 'local', 'images': ['public/vision/samples/circle-ring.png'], 'currentIndex': 0},
}
win._maybe_open_and_run()
if getattr(win, 'app_mode', '') == 'run':
    ok('openAndRun entered run mode')
else:
    bad(f'app_mode={getattr(win,"app_mode",None)}')

print(f'\n{pass_n} PASS / {fail_n} FAIL')
sys.exit(1 if fail_n else 0)
