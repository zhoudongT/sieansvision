#!/usr/bin/env python3
"""测量链绑定深挖 + 缺陷/OCR 结果面板 + 配方差分详情."""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
pass_n = fail_n = 0

def ok(m):
    global pass_n; pass_n += 1; print('PASS:', m)
def bad(m):
    global fail_n; fail_n += 1; print('FAIL:', m)

def main():
    from desktop.measure_geom_panel import (
        MeasureGeomPanel, normalize_measure_geom_params,
    )
    from desktop.recognize_panels import (
        DefectsPanel, OcrPanel, _norm_defects, _norm_ocr,
    )
    from desktop import recipe_library as rl
    from desktop.property_float import PropertyFloat
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])

    # --- measure normalize + panel ---
    for op, prefix in (
        ('point_distance', 'pointDist'),
        ('line_intersect', 'intersectPt'),
        ('point_line_distance', 'pointLineDist'),
    ):
        p = normalize_measure_geom_params(op, {})
        if p.get('resultVar') != prefix or not p.get('writeFlowVars', False):
            bad(f'{op} resultVar/writeFlowVars {p.get("resultVar")}')
        else:
            ok(f'{op} resultVar={prefix} writeFlowVars')
        if 'judgeEnable' not in p or 'judgeMin' not in p:
            bad(f'{op} missing judge fields')
        else:
            ok(f'{op} judge fields')

    step = {
        'id': 'm1', 'name': '点距', 'operation': 'point_distance',
        'params': normalize_measure_geom_params('point_distance', {
            'mode': 'manual', 'x1': 0, 'y1': 0, 'x2': 30, 'y2': 40,
            'judgeEnable': True, 'judgeMin': 40, 'judgeMax': 60,
            'resultVar': 'pdLive',
        }),
    }
    proj = {'steps': [step], 'variables': {'flow': {}}}
    panel = MeasureGeomPanel(step, {}, proj)
    names = {w.objectName() for w in panel.findChildren(type(panel)) if w.objectName()}
    # also search all QWidget children
    from PySide6.QtWidgets import QWidget, QLabel, QPushButton
    onames = {w.objectName() for w in panel.findChildren(QWidget) if w.objectName()}
    for need in ('measureGeomResultVar', 'measureGeomLiveBind', 'measureGeomLiveRefreshBtn'):
        (ok if need in onames else bad)(f'measure panel {need}' if need in onames else f'missing {need}')
    # trigger live refresh
    panel._refresh_live_bind()
    live = panel.findChild(QLabel, 'measureGeomLiveBind')
    assert live is not None
    ok(f'measure live text={live.text()[:60]}')

    # --- defects / ocr panels ---
    dstep = {'id': 'd1', 'name': '缺陷', 'operation': 'defects', 'params': _norm_defects({})}
    dpanel = DefectsPanel(dstep, {}, proj)
    donames = {w.objectName() for w in dpanel.findChildren(QWidget) if w.objectName()}
    for need in ('defectsResultVar', 'defectsLiveBind', 'defectsLiveRefreshBtn'):
        (ok if need in donames else bad)(f'defects {need}' if need in donames else f'missing {need}')
    dpanel._refresh_live()
    ok('defects live refresh')

    ostep = {'id': 'o1', 'name': 'OCR', 'operation': 'ocr', 'params': _norm_ocr({'judgeEnable': True, 'expectedText': 'OK'})}
    opanel = OcrPanel(ostep, {}, proj)
    oonames = {w.objectName() for w in opanel.findChildren(QWidget) if w.objectName()}
    for need in ('ocrResultVar', 'ocrLiveBind', 'ocrLiveRefreshBtn', 'ocrExpectedText', 'ocrTextPreview'):
        (ok if need in oonames else bad)(f'ocr {need}' if need in oonames else f'missing {need}')
    opanel._refresh_live()
    ok('ocr live refresh')

    # property_float routing source checks
    pf_src = (ROOT / 'desktop/property_float.py').read_text(encoding='utf-8')
    for n in ('DefectsPanel', 'OcrPanel', '_norm_defects', '_norm_ocr'):
        (ok if n in pf_src else bad)(f'property_float wires {n}' if n in pf_src else f'pf missing {n}')

    # engine source: judgeOk on defects/ocr
    eng = (ROOT / 'vision/engine.py').read_text(encoding='utf-8')
    for n in ("'judgeOk'", 'judgeStatus', 'showOverlay', 'judgeMaxRatio', 'expectedText'):
        (ok if n in eng else bad)(f'engine has {n}' if n in eng else f'engine missing {n}')

    # engine defects unit (synthetic images)
    import numpy as np
    import cv2
    from vision import engine as engmod
    img = np.zeros((64, 64, 3), dtype=np.uint8)
    ref = img.copy()
    # paint a bright blob on img only
    cv2.rectangle(img, (20, 20), (40, 40), (255, 255, 255), -1)
    canvas = img.copy()
    res = engmod.defects(img, canvas, {
        'threshold': 10, 'minArea': 10, 'judgeEnable': True,
        'judgeMaxCount': 0, 'judgeMaxRatio': 0.001,
        'showOverlay': True, 'showBoxes': True, 'showLabels': True,
    }, (0, 0), ref)
    if res.get('count', 0) < 1:
        bad(f'defects count={res.get("count")}')
    else:
        ok(f'defects count={res["count"]} ratio={res["defectRatio"]:.4f}')
    if res.get('judgeOk') is not False:
        bad(f'defects should NG judgeOk={res.get("judgeOk")}')
    else:
        ok(f'defects judgeStatus={res.get("judgeStatus")}')

    # recipe diff detail
    proj2 = {
        'name': 't',
        'steps': [
            {'id': 'a', 'name': '缺陷', 'operation': 'defects', 'params': {'threshold': 10}},
            {'id': 'b', 'name': 'OCR', 'operation': 'ocr', 'params': {'minConfidence': 0.5}},
        ],
        'variables': {'flow': {'pdLive': 0}},
    }
    rl.capture_recipe(proj2, 'R1', variant='V1')
    proj2['steps'][0]['params']['threshold'] = 40
    proj2['variables']['flow']['pdLive'] = 50
    rl.capture_recipe(proj2, 'R2', variant='V2')
    recs = [r for r in rl.ensure_recipes(proj2) if r.get('name') == 'R1']
    diff = rl.diff_recipe(proj2, recs[0]['id'])
    detail = rl.format_diff_detail(diff)
    assert isinstance(detail, list) and detail
    ok(f'diff detail rows={len(detail)} first={detail[0].get("text","")[:50]}')

    from desktop.recipe_switch_dialog import RecipeSwitchDialog
    class Doc:
        def __init__(self, project):
            self.project = project
        def commit(self, p):
            self.project = p
    dlg = RecipeSwitchDialog(Doc(proj2), ROOT, None)
    assert hasattr(dlg, '_diff_list')
    # select first recipe
    if dlg._recipe_list.count():
        dlg._recipe_list.setCurrentRow(0)
    dlg._refresh_diff_chip()
    ok(f'diff list count={dlg._diff_list.count()} chip={dlg._diff_chip.text()[:60]}')

    # flow-control source checks
    fc = (ROOT / 'lib/flow-control.cjs').read_text(encoding='utf-8')
    for n in ('_applyMeasureJudge', '_writeMeasureFlowVars', 'resultVar',
              'judgeOk', 'defectRatio', '_text', 'footX'):
        (ok if n in fc else bad)(f'flow-control has {n}' if n in fc else f'fc missing {n}')

    print(f"\n{'FAIL' if fail_n else 'PASS'} {pass_n} ok / {fail_n} fail")
    return 1 if fail_n else 0

if __name__ == '__main__':
    sys.exit(main())
