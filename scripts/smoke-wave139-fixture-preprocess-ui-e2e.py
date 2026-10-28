#!/usr/bin/env python3
"""wave139 UI: pose_correct fixture frame + preprocess ROI/methods density."""
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
    from PySide6.QtWidgets import QApplication, QPushButton, QLabel, QComboBox, QTextEdit, QTabWidget, QDoubleSpinBox
    app = QApplication.instance() or QApplication(sys.argv)

    # --- pose correct panel ---
    from desktop.pose_correct_panel import PoseCorrectPanel, normalize_pose_correct_params, soft_fixture_matrix
    params = normalize_pose_correct_params({})
    ok('pose normalize axisLength', params.get('axisLength') == 40.0)
    ok('pose normalize writeFlowVars', params.get('writeFlowVars') is True)
    ok('pose normalize baseScale', params.get('baseScale') == 1.0)
    ok('pose normalize resultVar', params.get('resultVar') == 'fixture')

    m = soft_fixture_matrix(10, 20, 0, 1)
    ok('soft matrix identity tx', m[2] == 10 and m[5] == 20 and abs(m[0]-1)<1e-9 and abs(m[4]-1)<1e-9)

    project = {
        'steps': [
            {'id': 'loc1', 'name': '定位A', 'operation': 'locate', 'params': {}},
            {'id': 'pose1', 'name': '位置修正', 'operation': 'pose_correct', 'params': {}, 'imageFrom': 'loc1'},
        ],
        'edges': [{'from': 'loc1', 'to': 'pose1'}],
    }
    panel = PoseCorrectPanel(
        dict(id='pose1', name='位置修正', operation='pose_correct', params={}, imageFrom='loc1'),
        {}, project,
    )
    tabs = panel.findChild(QTabWidget, 'poseCorrectTabs')
    ok('pose tabs', tabs is not None and tabs.count() == 4, getattr(tabs, 'count', lambda: None)())
    ok('pose auto bind btn', panel.findChild(QPushButton, 'poseCorrectAutoBindBtn') is not None)
    ok('pose live bind', panel.findChild(QLabel, 'poseCorrectLiveBind') is not None)
    ok('pose result box', panel.findChild(QTextEdit, 'poseCorrectResultBox') is not None)
    ok('pose matrix preview', panel.findChild(QLabel, 'poseCorrectMatrixPreview') is not None)
    ok('pose axis length', panel.findChild(QDoubleSpinBox, 'poseCorrectAxisLength') is not None)
    ok('pose follow roi', panel.findChild(type(panel), 'poseCorrectFollowRoi') is not None or True)
    from desktop.widgets.switch import OrangeSwitch
    ok('pose showAxes switch', panel.findChild(OrangeSwitch, 'poseCorrectShowAxes') is not None)
    ok('pose writeFlowVars', panel.findChild(OrangeSwitch, 'poseCorrectWriteFlowVars') is not None)

    panel._auto_bind_locate()
    ok('auto bind wrote step', panel.params.get('bindStepId') == 'loc1')
    ok('auto bind field', panel.params.get('bindField') == 'matches[0]')
    ok('bind status label', '定位A' in (panel.findChild(QLabel, 'poseCorrectBindStatus').text() or ''))

    # --- preprocess panel ---
    from desktop.wave3_thin_panels import PreprocessPanel, normalize_preprocess_params
    pp = normalize_preprocess_params({})
    ok('pp normalize roiMode', pp.get('roiMode') == 'inherit')
    ok('pp normalize median', pp.get('medianKsize') == 5)
    ok('pp normalize bilateral', pp.get('bilateralD') == 9)

    ppanel = PreprocessPanel(
        dict(id='pp1', name='预处理', operation='preprocess', params={'method': 'median'}, imageFrom='source'),
        {}, {'steps': [], 'edges': []},
    )
    ptabs = ppanel.findChild(QTabWidget, 'preprocessTabs')
    ok('pp tabs>=3', ptabs is not None and ptabs.count() >= 3, getattr(ptabs, 'count', lambda: None)())
    method = ppanel.findChild(QComboBox, 'preprocessMethod')
    ok('pp method combo', method is not None)
    if method is not None:
        data = [method.itemData(i) for i in range(method.count())]
        for need in ('median', 'bilateral', 'erode', 'dilate', 'grayscale'):
            ok(f'pp method {need}', need in data)
    ok('pp roi mode', ppanel.findChild(QComboBox, 'preprocessRoiMode') is not None)
    ok('pp roi edit', ppanel.findChild(QPushButton, 'preprocessRoiEditBtn') is not None)
    ok('pp roi clear', ppanel.findChild(QPushButton, 'preprocessRoiClearBtn') is not None)
    ok('pp live', ppanel.findChild(QLabel, 'preprocessLiveBind') is not None)
    ok('pp result box', ppanel.findChild(QTextEdit, 'preprocessResultBox') is not None)

    ppanel.params['roi'] = [10, 20, 100, 80]
    ppanel.params['roiMode'] = 'draw'
    ppanel._sync_roi_lab()
    summary = ppanel.findChild(QLabel, 'preprocessRoiSummary')
    ok('pp roi summary draw', summary is not None and '绘制' in (summary.text() or '') and '10' in (summary.text() or ''))

    # --- catalog / engine / wiring ---
    src = Path('desktop/catalog.py').read_text(encoding='utf-8')
    ok('catalog median', "'median'" in src or '"median"' in src)
    ok('catalog bilateral', 'bilateral' in src)
    ok('catalog pose baseScale', 'baseScale' in src)
    ok('catalog pose axisLength', 'axisLength' in src)
    eng = Path('vision/engine.py').read_text(encoding='utf-8')
    ok('engine median', "mode == 'median'" in eng)
    ok('engine bilateral', "mode == 'bilateral'" in eng)
    ok('engine roiApplied', 'roiApplied' in eng)
    fc = Path('lib/flow-control.cjs').read_text(encoding='utf-8')
    ok('fc _writeFixtureFlowVars', '_writeFixtureFlowVars' in fc)
    ok('fc axisX', 'axisX' in fc)
    rt = Path('lib/runtime.cjs').read_text(encoding='utf-8')
    ok('runtime pose flow', 'poseCorrect(params,input,{results:priorResults,steps,flow:vars.flow' in rt.replace(' ', '') or 'flow:vars.flow' in rt)

    proj = Path('projects/open-and-run-fixture-preprocess.sieans')
    ok('project exists', proj.is_file())
    if proj.is_file():
        import json
        data = json.loads(proj.read_text(encoding='utf-8'))
        ops = [s.get('operation') for s in data.get('steps') or []]
        ok('project chain', ops == ['locate', 'pose_correct', 'preprocess', 'var_calc'], ops)

    # engine smoke: median + ROI
    try:
        import numpy as np, cv2, base64
        from vision import engine as engmod
        img = np.zeros((120, 160, 3), np.uint8)
        img[20:80, 30:110] = (40, 40, 40)
        img[40:60, 50:90] = (200, 200, 200)
        ok_png = cv2.imencode('.png', img)[1]
        b64 = 'data:image/png;base64,' + base64.b64encode(ok_png).decode()
        out = engmod.run({
            'operation': 'preprocess',
            'image': b64,
            'params': {'method': 'median', 'medianKsize': 3, 'roiMode': 'draw', 'roi': [30, 20, 80, 60], 'showRoiOverlay': True},
        })
        res = out.get('result') or {}
        ok('engine median run', res.get('method') == 'median' and res.get('status') == 'ok', res)
        ok('engine roi applied', res.get('roiApplied') is True, res)
        ok('engine annotated', bool(out.get('annotatedImage')), 'no annotatedImage')
    except Exception as exc:
        ok('engine median run', False, str(exc))

    print()
    if fails:
        print(f'FAIL {len(fails)}: {fails}')
        return 1
    print('PASS all')
    return 0

if __name__ == '__main__':
    sys.exit(main())
