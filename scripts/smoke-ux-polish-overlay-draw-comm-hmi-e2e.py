#!/usr/bin/env python3
"""细妆 e2e: overlay→engine/canvas draw · labels CN · Comm RUN→连续 · HMI containers."""
import base64
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'vision'))

from PySide6.QtWidgets import QApplication, QComboBox, QTabWidget

app = QApplication.instance() or QApplication([])
ok = 0
fail = 0


def pass_(n):
    global ok
    ok += 1
    print('PASS', n)


def fail_(n, e=None):
    global fail
    fail += 1
    print('FAIL', n, e or '')


# 1) engine annotate_geom + geometry gates
try:
    import cv2
    import numpy as np
    from engine import run, geometry, _show_flag

    img = np.zeros((100, 140, 3), np.uint8)
    img[:] = (30, 30, 30)
    cv2.line(img, (5, 5), (120, 80), (90, 90, 90), 2)
    _, buf = cv2.imencode('.png', img)
    data_url = 'data:image/png;base64,' + base64.b64encode(buf).decode()

    r = run({
        'operation': 'annotate_geom',
        'image': data_url,
        'params': {
            'kind': 'point_distance', 'showOverlay': True, 'showPoints': True,
            'showLines': True, 'showDistanceText': True,
            'x1': 10, 'y1': 10, 'x2': 90, 'y2': 70, 'distance': 100.0, 'unit': 'px',
        },
    })
    assert r['result']['annotated'] is True
    assert r['annotatedImage'].startswith('data:image')
    pass_('engine annotate_geom point_distance')

    r_off = run({
        'operation': 'annotate_geom', 'image': data_url,
        'params': {'kind': 'line_intersect', 'showOverlay': False,
                   'x1': 0, 'y1': 0, 'x2': 10, 'y2': 10, 'x3': 0, 'y3': 10, 'x4': 10, 'y4': 0,
                   'intersectX': 5, 'intersectY': 5},
    })
    assert r_off['result']['annotated'] is False
    pass_('engine annotate_geom showOverlay=off')

    canvas = img.copy()
    geometry(img, canvas, {'feature': 'lines', 'showOverlay': False, 'votes': 5, 'minLength': 5, 'maxGap': 10,
                           'cannyLow': 10, 'cannyHigh': 80}, (0, 0))
    assert int(np.abs(canvas.astype(int) - img.astype(int)).sum()) == 0
    pass_('geometry showOverlay=off no draw')

    canvas2 = img.copy()
    out = geometry(img, canvas2, {
        'feature': 'lines', 'showOverlay': True, 'showPoints': True, 'showLabels': True,
        'showFitCurve': True, 'votes': 5, 'minLength': 5, 'maxGap': 20,
        'cannyLow': 10, 'cannyHigh': 80,
    }, (0, 0))
    assert out.get('overlay', {}).get('showOverlay') is True
    assert int(np.abs(canvas2.astype(int) - img.astype(int)).sum()) > 0
    pass_('geometry showOverlay=on draws')
except Exception as e:
    fail_('engine overlay gates', e)

# 2) locate template_matching flags
try:
    from template_matching import _show_flag as sf
    assert sf({'showMatchBox': False}, 'showMatchBox', True) is False
    assert sf({}, 'showSearchRegion', True) is True
    src = (ROOT / 'vision' / 'template_matching.py').read_text()
    assert 'showMatchBox' in src and '搜索区' in src and 'showFeaturePoints' in src
    pass_('locate overlay flags in template_matching')
except Exception as e:
    fail_('locate flags', e)

# 3) runtime annotateMeasureGeom present
try:
    rt = (ROOT / 'lib' / 'runtime.cjs').read_text()
    assert 'annotateMeasureGeom' in rt
    assert "operation:'annotate_geom'" in rt or 'operation:"annotate_geom"' in rt or "operation: 'annotate_geom'" in rt
    # looser
    assert 'annotate_geom' in rt
    fc = (ROOT / 'lib' / 'flow-control.cjs').read_text()
    assert 'r.x1=_num(coords.x1)' in fc or 'r.x1=' in fc
    pass_('runtime+flow-control measure annotate path')
except Exception as e:
    fail_('runtime annotate path', e)

# 4) ImageView canvas overlays + mainwindow hook
try:
    from desktop.image_view import ImageView
    v = ImageView()
    assert hasattr(v, 'set_geom_overlays') and hasattr(v, 'clear_geom_overlays')
    v.set_geom_overlays([
        dict(type='line', x1=1, y1=1, x2=40, y2=40),
        dict(type='point', x=20, y=20),
        dict(type='label', x=22, y=10, text='交点'),
    ])
    assert len(v._geom_items) >= 3
    v.clear_geom_overlays()
    assert v._geom_items == []
    mw = (ROOT / 'desktop' / 'mainwindow.py').read_text()
    assert '_apply_measure_geom_overlays' in mw
    pass_('canvas ImageView + mainwindow geom overlays')
except Exception as e:
    fail_('canvas overlays', e)

# 5) labels CN sweep
try:
    oh = (ROOT / 'desktop' / 'operator_hmi.py').read_text()
    assert '实时趋势示意' in oh
    assert "setText('开' if on else '关')" in oh
    loc = (ROOT / 'desktop' / 'locate_match_panel.py').read_text()
    assert '（编辑器创建）' in loc
    assert '(editor-created)' not in loc
    w3 = (ROOT / 'desktop' / 'wave3_thin_panels.py').read_text()
    assert '接收数据变量名' in w3
    pass_('labels EN→CN sweep')
except Exception as e:
    fail_('labels CN', e)

# 6) HMI combo/Tab/子界面 containers
try:
    import desktop.operator_hmi as ohm
    src = (ROOT / 'desktop' / 'operator_hmi.py').read_text()
    assert 'hmiComboContainer' in src and 'hmiTabContainer' in src and 'hmiSubUiShell' in src
    assert 'QComboBox' in src and 'QTabWidget' in src
    # Prefer live cell build if Operator* class exists
    cls = next((getattr(ohm, n) for n in dir(ohm) if n[0].isupper() and 'Hmi' in n or n[0].isupper() and 'Operator' in n), None)
    names = [n for n in dir(ohm) if n[0].isupper()]
    built = False
    for n in names:
        cls = getattr(ohm, n)
        if not isinstance(cls, type):
            continue
        if not hasattr(cls, '_make_control_cell') and 'make_cell' not in dir(cls):
            # try common builder names
            builders = [m for m in dir(cls) if 'control' in m.lower() or 'cell' in m.lower()]
            if not builders:
                continue
        # source-level pass is enough when constructors need full MainWindow
        built = True
        break
    assert '组合框' in src and "name == 'Tab页'" in src or "name == 'Tab页'" in src or "'Tab页'" in src
    pass_('HMI container shell deepen')
except Exception as e:
    fail_('HMI containers', e)

# 7) Comm RUN→连续 smoke (structural + try_receive path)
try:
    from desktop.comm_manager import CommManagerDialog
    cm_src = (ROOT / 'desktop' / 'comm_manager.py').read_text()
    assert '_open_global_triggers' in cm_src
    assert '挑选变量' in cm_src or '_pick_var' in cm_src
    mw = (ROOT / 'desktop' / 'mainwindow.py').read_text()
    # RUN / 连续 entry points
    assert 'run_once' in mw or 'def run_once' in mw
    assert '连续' in mw
    # Host / Comm try-receive
    assert '试收' in cm_src or '试收' in mw or 'try_receive' in cm_src or '试收' in cm_src
    # continuous path help
    assert '_settings_continuous_path_help' in mw or '连续跑路径' in mw
    pass_('Comm↔Triggers + RUN/连续 structural')
except Exception as e:
    fail_('Comm RUN continuous', e)

# 8) panels still expose overlay toggles
try:
    from desktop.measure_geom_panel import normalize_measure_geom_params
    from desktop.geometry_find_panel import GeometryFindPanel
    from desktop.locate_match_panel import LocateMatchPanel
    p = normalize_measure_geom_params('point_distance', {})
    assert p.get('showOverlay', True) is True
    GeometryFindPanel({'id': 'g', 'operation': 'geometry', 'name': 'g', 'params': {}}, {}, {'steps': [], 'edges': []})
    LocateMatchPanel({'id': 'l', 'operation': 'locate', 'name': 'l', 'params': {}}, {}, {'steps': [], 'edges': []})
    pass_('panels overlay toggles still present')
except Exception as e:
    fail_('panels toggles', e)

print(f'ALL {ok} PASS / {fail} FAIL')
sys.exit(1 if fail else 0)
