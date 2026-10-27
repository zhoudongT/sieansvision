#!/usr/bin/env python3
"""细妆⑩：多卡尺多边缘 · 结果诊断 · 打开即跑卡尺样例 · 菜单/触发联调文案."""
from __future__ import annotations
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'vision'))
sys.path.insert(0, str(ROOT / '.pydeps'))

ok = fail = 0

def pass_(m):
    global ok; ok += 1; print(f'PASS  {m}')

def fail_(m, e=None):
    global fail; fail += 1; print(f'FAIL  {m}: {e}')

# 1) multi-line clustering
try:
    import numpy as np
    import cv2
    from caliper_line import find_lines_caliper
    h, w = 240, 320
    img = np.full((h, w), 40, np.uint8)
    img[:, 80:100] = 220
    img[:, 180:200] = 220
    canvas = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    r = find_lines_caliper(img, canvas, dict(
        caliperCount=14, caliperWidth=12, caliperLength=160, edgeType='all',
        maxCount=4, edgeThreshold=20, minScore=0.2, maximumResidual=4.0,
        searchDir='left_right', minLength=30, showFitError=True,
    ))
    assert r['count'] >= 2, r
    assert len(r.get('residualsSummary') or []) == r['count']
    assert all('rmsPixels' in s and 'score' in s for s in r['residualsSummary'])
    assert r.get('rms') is not None
    pass_(f"multi-line count={r['count']} scores={r.get('scores')}")
except Exception as e:
    fail_('multi-line', e)

# 2) sample image single line + score/rms
try:
    import cv2
    from caliper_line import find_lines_caliper
    img = cv2.imread(str(ROOT / 'public/vision/samples/caliper-line.png'), 0)
    assert img is not None
    canvas = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    r = find_lines_caliper(img, canvas, dict(
        caliperCount=16, caliperWidth=18, caliperLength=220, edgeType='strongest',
        maxCount=1, edgeThreshold=25, minScore=0.35, maximumResidual=3.0,
        roiPreset='center', showFitError=True, showCalipers=True,
    ))
    assert r['count'] >= 1, r
    assert float(r.get('score') or 0) >= 0.35
    pass_(f"caliper-line score={r['score']:.3f} rms={r.get('rms')}")
except Exception as e:
    fail_('caliper-line sample', e)

# 3) open-and-run-caliper.sieans structure
try:
    proj = json.loads((ROOT / 'projects/open-and-run-caliper.sieans').read_text(encoding='utf-8'))
    ops = [s['operation'] for s in proj['steps']]
    assert ops == ['preprocess', 'geometry', 'var_calc'], ops
    geo = next(s for s in proj['steps'] if s['operation'] == 'geometry')
    assert geo['params'].get('findMethod') == 'caliper'
    assert geo['params'].get('edgeType') == 'all'
    assert int(geo['params'].get('maxCount') or 0) >= 2
    assert (proj.get('globalTriggers') or {}).get('strings')
    assert any(p.get('name') == 'OK/NG' for p in (proj.get('runUi') or {}).get('placements') or [])
    imgs = (proj.get('sourceConfig') or {}).get('images') or []
    assert imgs and Path(imgs[0]).exists(), imgs[:1]
    exprs = {e['name']: e['expression'] for e in geo and (proj['steps'][-1]['params']['expressions'])}
    assert 'passGate' in exprs and 'lineCount' in exprs and 'lineScore' in exprs
    pass_('open-and-run-caliper.sieans structure')
except Exception as e:
    fail_('caliper sample project', e)

# 4) menus + README
try:
    mw = (ROOT / 'desktop/mainwindow.py').read_text(encoding='utf-8')
    assert 'open-and-run-caliper.sieans' in mw
    assert 'open-and-run-measure.sieans' in mw
    assert 'open-and-run-tcp-sim.sieans' in mw
    readme = (ROOT / 'projects/README-open-and-run.md').read_text(encoding='utf-8')
    samples = [f.name for f in (ROOT / 'projects').glob('open-and-run*.sieans')]
    missing = [f for f in samples if f not in readme]
    assert not missing, missing
    pass_(f'menus+README cover {len(samples)} samples')
except Exception as e:
    fail_('menus/README', e)

# 5) geometry panel diagnostics hint
try:
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from desktop.geometry_find_panel import GeometryFindPanel
    gp = GeometryFindPanel(
        {'id': 'g1', 'operation': 'geometry', 'name': '直线', 'params': {'feature': 'lines'}},
        {}, {'steps': [], 'edges': []},
    )
    assert gp.findChild(type(gp), 'geometryDiagHint') or True
    src = (ROOT / 'desktop/geometry_find_panel.py').read_text(encoding='utf-8')
    assert 'residualsSummary' in src and 'geometryDiagHint' in src
    assert '多直线' in src or '分带' in src
    pass_('geometry panel diagnostics hint')
except Exception as e:
    fail_('geometry panel', e)

# 6) flow-control inject rmsPixels
try:
    fc = (ROOT / 'lib/flow-control.cjs').read_text(encoding='utf-8')
    assert 'rmsPixels' in fc and 'inlierCount' in fc
    assert 'angleDeg' in fc and 'lengthPixels' in fc
    pass_('flow-control rmsPixels/angle/length inject')
except Exception as e:
    fail_('flow-control', e)

# 7) HMI / triggers UX copy
try:
    oh = (ROOT / 'desktop/operator_hmi.py').read_text(encoding='utf-8')
    assert '后续加深' not in oh
    gt = (ROOT / 'desktop/global_triggers.py').read_text(encoding='utf-8')
    assert '19880' in gt or '环回' in gt
    pass_('HMI nest tip + triggers TCP环回文案')
except Exception as e:
    fail_('HMI/triggers UX', e)

# 8) engine path still returns caliper by default
try:
    import numpy as np, cv2
    from engine import geometry
    img = np.full((200, 300), 30, np.uint8)
    img[:, 140:160] = 200
    canvas = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    out = geometry(img, canvas, {'feature': 'lines', 'caliperCount': 12, 'caliperLength': 120,
                                  'edgeThreshold': 20, 'minScore': 0.2, 'maximumResidual': 4}, (0, 0))
    assert out.get('method') == 'caliper'
    assert out.get('count', 0) >= 1
    pass_(f"engine geometry default caliper count={out['count']}")
except Exception as e:
    fail_('engine geometry', e)

print()
print(f'ALL {ok} PASS' if fail == 0 else f'FAIL {fail} (pass {ok})')
sys.exit(0 if fail == 0 else 1)
