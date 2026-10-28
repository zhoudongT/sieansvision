#!/usr/bin/env python3
"""wave138 UI: measure_geom new ops · csharp shell · vars/trigger result chrome."""
from __future__ import annotations
import os, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); os.chdir(ROOT)
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

fails = []
def ok(n, c, d=''):
    if c: print(f'PASS  {n}')
    else: fails.append(n); print(f'FAIL  {n}  {d}')

def main():
    from PySide6.QtWidgets import QApplication, QPushButton, QLabel, QPlainTextEdit, QTextEdit
    app = QApplication.instance() or QApplication(sys.argv)

    # --- measure geom new ops ---
    from desktop.measure_geom_panel import MeasureGeomPanel, MEASURE_GEOM_OPS, OP_META
    ok('ops include line_angle', 'line_angle' in MEASURE_GEOM_OPS)
    ok('ops include point_circle', 'point_circle_distance' in MEASURE_GEOM_OPS)
    ok('ops include circle_circle', 'circle_circle_distance' in MEASURE_GEOM_OPS)
    ok('OP_META keys', set(OP_META) == set(MEASURE_GEOM_OPS))

    for op, expect_slots in (
        ('line_angle', ('直线1', '直线2')),
        ('point_circle_distance', ('点', '圆')),
        ('circle_circle_distance', ('圆1', '圆2')),
    ):
        p = MeasureGeomPanel(dict(id='m1', name=op, operation=op, params={}), {}, {'steps': []})
        slots = p._bind_slots()
        ok(f'{op} slots', len(slots) == 2 and slots[0][0] == expect_slots[0] and slots[1][0] == expect_slots[1], slots)
        ok(f'{op} live lab', p.findChild(QLabel, 'measureGeomLiveBind') is not None)

    # --- csharp shell ---
    from desktop.csharp_script_panel import CsharpScriptPanel, normalize_csharp_params
    params = normalize_csharp_params({'language': 'python'})
    ok('csharp normalize writeOutputVars', params.get('writeOutputVars') is True)
    ok('csharp normalize injectGlobals', params.get('injectGlobals') is True)
    panel = CsharpScriptPanel(
        dict(id='cs1', name='脚本', operation='csharp_script', params={'language': 'python'}),
        {}, {'steps': []},
    )
    ok('csharp status chip', panel.findChild(QLabel, 'csharpScriptStatusChip') is not None)
    ok('csharp editor', panel.findChild(QPlainTextEdit, 'csharpScriptEditor') is not None)
    ok('csharp live', panel.findChild(QLabel, 'csharpScriptLiveBind') is not None)
    ok('csharp result box', panel.findChild(QTextEdit, 'csharpScriptResultBox') is not None)
    ok('csharp inject preview', panel.findChild(QTextEdit, 'csharpScriptInjectPreview') is not None)
    ok('csharp writeOutput checkbox', panel.findChild(type(panel.findChildren(type(app))[0]) if False else __import__('PySide6.QtWidgets', fromlist=['QCheckBox']).QCheckBox, 'csharpScriptWriteOutputVars') is not None)

    from PySide6.QtWidgets import QCheckBox
    ok('writeOutputVars cb', panel.findChild(QCheckBox, 'csharpScriptWriteOutputVars') is not None)
    ok('injectGlobals cb', panel.findChild(QCheckBox, 'csharpScriptInjectGlobals') is not None)

    # switch lang → highlighter
    ok('has highlighter', hasattr(panel, '_highlighter'))
    panel._set_param('language', 'csharp')
    ok('chrome csharp unsupported', 'unsupported' in (panel._status_chip.text() or ''))

    # --- catalog / property float wiring ---
    src = Path('desktop/catalog.py').read_text(encoding='utf-8')
    for op in ('line_angle', 'point_circle_distance', 'circle_circle_distance'):
        ok(f'catalog has {op}', f"definitions['{op}']" in src or f'definitions["{op}"]' in src)
    ok('catalog csharp writeOutputVars default', 'writeOutputVars=True' in src)

    pf = Path('desktop/property_float.py').read_text(encoding='utf-8')
    ok('property_float new ops', 'line_angle' in pf and 'circle_circle_distance' in pf)
    cfg = Path('desktop/config_status.py').read_text(encoding='utf-8')
    ok('config_status circle keys', 'circle1From' in cfg)
    fg = Path('public/vision/flow-graph.js').read_text(encoding='utf-8')
    ok('flow-graph new ops', 'line_angle' in fg and 'circle_circle_distance' in fg)
    mw = Path('desktop/mainwindow.py').read_text(encoding='utf-8')
    ok('mainwindow overlays', "op == 'line_angle'" in mw and "op == 'circle_circle_distance'" in mw)

    # --- variables dialog chrome ---
    from desktop.variables_dialog import VariablesDialog
    from PySide6.QtCore import QObject, Signal
    class _Doc(QObject):
        changed = Signal()
        def __init__(self):
            super().__init__()
            self.project = {
                'id': 'wave138', 'name': 'wave138', 'steps': [],
                'variables': {'lineAngle_angleDeg': 90, 'script_out0': 1},
                'variableTypes': {}, 'variableNotes': {},
            }
        def mark_dirty(self): pass
    class _Backend:
        def request(self, *a, **k): return 1
        result = type('S', (), {'connect': staticmethod(lambda *a, **k: None)})()
        error = type('S', (), {'connect': staticmethod(lambda *a, **k: None)})()
    try:
        dlg = VariablesDialog(_Doc(), _Backend())
        ok('vars result chrome', dlg.findChild(QLabel, 'varsResultChrome') is not None)
        keys = [dlg.watch_preset.itemData(i) for i in range(dlg.watch_preset.count())]
        ok('vars preset geometry', 'geometry' in keys, keys)
        ok('vars preset script', 'script' in keys, keys)
        # seed runtime_draft so chrome sees flow keys
        dlg.runtime_draft = {'flow': {'lineAngle_angleDeg': 90, 'script_out0': 1}, 'global': {}, 'revision': 1}
        dlg._refresh_result_chrome()
        txt = dlg.result_chrome.text()
        ok('vars chrome mentions geom/script', ('几何' in txt) or ('脚本' in txt) or ('flow' in txt), txt)
        dlg.close()
    except Exception as e:
        ok('vars dialog', False, str(e))

    from desktop.host_var_watch import classify_watch_key
    ok('classify geometry', classify_watch_key('lineAngle_angleDeg') in ('geometry', 'measure'))
    ok('classify script', classify_watch_key('script_out0') == 'script')

    # --- global triggers chrome ---
    from desktop.global_triggers import GlobalTriggersDialog
    class _Doc2:
        project = {'globalTriggers': {'events': [], 'strings': [{'pattern': 'RUN', 'enabled': True, 'commands': [{'type': 'run_once'}]}]}}
        def subscribe(self, *a, **k): pass
    try:
        td = GlobalTriggersDialog(_Doc2())
        ok('triggers result chrome', td.findChild(QLabel, 'triggersResultChrome') is not None)
        td.test_input.setText('xx RUN yy')
        td._test_match()
        ok('triggers match chrome', '命中' in (td.result_chrome.text() or ''), td.result_chrome.text())
        td.close()
    except Exception as e:
        ok('triggers dialog', False, str(e))

    # --- var_calc result box ---
    from desktop.var_calc_panel import VarCalcPanel
    vp = VarCalcPanel(dict(id='vc1', name='变量计算', operation='var_calc', params={}), {}, {})
    ok('var_calc result box', vp.findChild(QTextEdit, 'varCalcResultBox') is not None)

    print(f'\nRESULT: {len(fails)} failed, {0 if fails else "all"} ok')
    if fails:
        print('FAILED:', fails)
        return 1
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
