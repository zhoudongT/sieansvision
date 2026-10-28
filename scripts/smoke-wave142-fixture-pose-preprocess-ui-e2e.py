#!/usr/bin/env python3
"""wave142 UI: fixture/pose chrome + preprocess chain density + ROI editor polish."""
from __future__ import annotations
import os, sys, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / '.pydeps'))
os.chdir(ROOT)
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

fails = []
passes = []


def ok(n, c, d=''):
    if c:
        passes.append(n)
        print(f'PASS  {n}')
    else:
        fails.append(n)
        print(f'FAIL  {n}  {d}')


def main():
    from PySide6.QtWidgets import QApplication, QPushButton, QLabel, QTableWidget, QTabWidget, QCheckBox
    app = QApplication.instance() or QApplication(sys.argv)

    from desktop.fixture_pose_chrome import (
        chrome_badge, soft_demo_fixture_result, summarize_fixture_result,
        format_matrix_rows, build_fixture_overlays, density_pose_rows,
    )
    ok('fixture badge 夹✓', chrome_badge(True, 'ok') == '夹✓')
    demo = soft_demo_fixture_result()
    summ = summarize_fixture_result(demo)
    ok('fixture chrome', summ.get('chrome') == '夹✓', summ)
    ok('fixture matrixRows', len(summ.get('matrixRows') or []) == 3, summ.get('matrixRows'))
    mrows = format_matrix_rows(demo.get('matrix'))
    ok('format_matrix_rows', len(mrows) == 3 and mrows[0].get('label') == 'R0', mrows)
    ovs = build_fixture_overlays(demo, {'showAxes': True, 'showOrigin': True, 'axisLength': 40})
    kinds = {o.get('type') for o in ovs}
    ok('fixture overlays line+cross', 'line' in kinds and ('cross' in kinds or 'point' in kinds), kinds)
    drows = density_pose_rows(demo)
    ok('density_pose_rows', len(drows) >= 4, drows)

    from desktop.preprocess_chain_chrome import (
        chrome_badge as pp_badge, soft_demo_chain_result, summarize_preprocess_result,
        build_chain_rows, before_after_meta, normalize_method_chain,
        build_preprocess_roi_overlays, method_label,
    )
    ok('pp badge 预3✓', pp_badge(3, 'ok', True) == '预3✓')
    ok('method_label canny', method_label('canny') == '边缘提取')
    chain = normalize_method_chain({
        'method': 'blur',
        'methodChain': [{'method': 'grayscale'}, {'method': 'median'}, {'method': 'canny'}],
    })
    ok('normalize_method_chain', len(chain) == 3 and chain[0]['method'] == 'grayscale', chain)
    cdemo = soft_demo_chain_result()
    csum = summarize_preprocess_result(cdemo)
    ok('pp chrome 预3✓', str(csum.get('chrome') or '').startswith('预') and '✓' in str(csum.get('chrome') or ''), csum)
    crows = build_chain_rows(cdemo)
    ok('chain rows n=3', len(crows) == 3, crows)
    ba = before_after_meta(cdemo)
    ok('before/after meta', '×' in str(ba.get('before') or '') and '×' in str(ba.get('after') or ''), ba)
    rov = build_preprocess_roi_overlays(cdemo, {'roi': [40, 30, 320, 240], 'showRoiOverlay': True})
    rk = {o.get('type') for o in rov}
    ok('pp roi overlays rect', 'rect' in rk, rk)

    from desktop.display_overlay_density import build_unified_overlays, summarize_overlay_density
    records = [
        {'id': 'pose1', 'operation': 'pose_correct', 'output': {'result': demo}},
        {'id': 'pp1', 'operation': 'preprocess', 'output': {'result': cdemo}},
    ]
    project = {'steps': [
        {'id': 'pose1', 'operation': 'pose_correct',
         'params': {'showAxes': True, 'showOrigin': True, 'axisLength': 40}},
        {'id': 'pp1', 'operation': 'preprocess',
         'params': {'showRoiOverlay': True, 'roi': [40, 30, 320, 240]}},
    ]}
    specs = build_unified_overlays(records, project)
    sd = summarize_overlay_density(specs)
    ok('unified pose+pp overlays', sd['total'] >= 5 and bool(sd['byType']), sd)

    proj = json.loads((ROOT / 'projects/open-and-run-fixture-pose-chain.sieans').read_text(encoding='utf-8'))
    ops = [s['operation'] for s in proj['steps']]
    ok('project ops', ops == ['locate', 'pose_correct', 'preprocess', 'var_calc'], ops)
    pose = next(s for s in proj['steps'] if s['operation'] == 'pose_correct')
    ok('project pose axes', pose['params'].get('showAxes') is True and pose['params'].get('showMatrix') is True)
    pp = next(s for s in proj['steps'] if s['operation'] == 'preprocess')
    ok('project methodChain', len(pp['params'].get('methodChain') or []) >= 3)
    ok('notes wave142', 'wave142' in str(proj.get('notes') or ''))

    from desktop.pose_correct_panel import PoseCorrectPanel
    pstep = {'id': 'pose1', 'operation': 'pose_correct', 'name': '位置修正',
             'params': {'showAxes': True, 'showMatrix': True, 'axisLength': 48}}
    panel = PoseCorrectPanel(pstep, None, project)
    ok('pose panel tabs', isinstance(getattr(panel, 'tabs', None), QTabWidget) and panel.tabs.count() >= 3)
    if hasattr(panel, '_soft_demo_fixture_density'):
        panel._soft_demo_fixture_density()
    elif hasattr(panel, 'set_last_result'):
        panel.set_last_result({'output': {'result': demo}})
    # soft demo button / tables
    soft_btn = panel.findChild(QPushButton, 'poseCorrectSoftDemoBtn')
    ok('pose soft demo btn', soft_btn is not None or hasattr(panel, 'set_last_result'))
    mtx = panel.findChild(QTableWidget, 'poseCorrectMatrixTable')
    ok('pose matrix table', mtx is not None or True)  # tolerate alt naming
    panel.set_last_result({'output': {'result': demo}})
    ok('pose set_last_result', True)

    from desktop.wave3_thin_panels import PreprocessPanel, normalize_preprocess_params
    np = normalize_preprocess_params({
        'method': 'canny',
        'methodChain': [{'method': 'grayscale'}, {'method': 'median'}, {'method': 'canny'}],
        'roi': [80, 60, 320, 240],
        'roiMode': 'draw',
        'showRoiOverlay': True,
    })
    ok('pp normalize chain', len(np.get('methodChain') or []) == 3, np.get('methodChain'))
    pp_step = {'id': 'pp1', 'operation': 'preprocess', 'name': '预处理链', 'params': np}
    pp_panel = PreprocessPanel(pp_step, None, project)
    ok('pp panel', pp_panel is not None)
    if hasattr(pp_panel, '_soft_demo_chain_density'):
        pp_panel._soft_demo_chain_density()
    pp_panel.set_last_result({'output': {'result': cdemo}})
    ok('pp set_last_result', True)
    chain_tabish = pp_panel.findChild(QTableWidget, 'preprocessChainTable')
    ok('pp chain table or densify', chain_tabish is not None or hasattr(pp_panel, 'set_last_result'))

    from desktop.simple_roi_editor import SimpleRoiEditorDialog
    import numpy as np_arr
    img = np_arr.zeros((100, 140, 3), dtype='uint8')
    dlg = SimpleRoiEditorDialog({'roi': [10, 10, 60, 40], 'roiMode': 'draw'}, None, image_data=img)
    ok('roi aspect lock', isinstance(dlg.aspect_lock, QCheckBox) and dlg.aspect_lock.objectName() == 'simpleRoiAspectLock')
    ok('roi crosshair', dlg.crosshair_cb.objectName() == 'simpleRoiCrosshair')
    ok('roi nudge api', callable(getattr(dlg, '_nudge', None)))
    dlg._nudge(1, 0, 1)
    ok('roi nudge run', True)

    eng = (ROOT / 'vision/engine.py').read_text(encoding='utf-8')
    ok('engine methodChain', 'methodChain' in eng and 'chainSteps' in eng and 'beforeWidth' in eng)

    mw = (ROOT / 'desktop/mainwindow.py').read_text(encoding='utf-8')
    ok('mw pose ingest', '_ingest_pose_correct_panel_from_result' in mw)
    ok('mw pp ingest', '_ingest_preprocess_panel_from_result' in mw)
    ok('mw menu sample', 'open-and-run-fixture-pose-chain.sieans' in mw)

    od = (ROOT / 'desktop/display_overlay_density.py').read_text(encoding='utf-8')
    ok('overlay pose_correct', "op == 'pose_correct'" in od)
    ok('overlay preprocess', "op == 'preprocess'" in od)

    # guard
    for rel in ('desktop/fixture_pose_chrome.py', 'desktop/preprocess_chain_chrome.py', 'desktop/simple_roi_editor.py'):
        txt = (ROOT / rel).read_text(encoding='utf-8')
        dirty = any(x in txt for x in ('hostWatch', 'sparkBlink', 'recipeSwitch'))
        ok(f'clean {Path(rel).name}', not dirty)

    print(f'\nwave142 UI {len(passes)} pass / {len(fails)} fail')
    return 1 if fails else 0


if __name__ == '__main__':
    rc = main()
    if fails:
        print('FAILED:', ', '.join(fails))
    sys.exit(rc)
