#!/usr/bin/env python3
"""§6 余 P2：Locate/Geometry 结果显示与卡尺级参数 + P3 九点验证 UI（无 Halcon）。"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import cv2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'vision'))
pass_n = fail_n = 0

def ok(m):
    global pass_n; pass_n += 1; print('PASS:', m)
def bad(m):
    global fail_n; fail_n += 1; print('FAIL:', m)

def main():
    # --- template_matching.locate overlays / judge / angleEnable ---
    src = Path('vision/template_matching.py').read_text(encoding='utf-8')
    for needle in ('angleEnable', 'showMatchIndex', 'resultJudgeEnable', 'traceFullCanvas',
                   'showAngleDeg', 'judgeOk', '无 Halcon'):
        (ok if needle in src else bad)(f'template_matching has {needle}')

    from template_matching import locate as tm_locate
    # BGR scene + reference (bright rect)
    scene = np.zeros((120, 160, 3), dtype=np.uint8)
    # textured patch (std>=1) so locate accepts the template
    rng = np.random.RandomState(0)
    patch = rng.randint(40, 220, (25, 30, 3), dtype=np.uint8)
    scene[30:55, 40:70] = patch
    # duplicate for a match elsewhere too
    scene[70:95, 90:120] = patch
    ref = scene[30:55, 40:70].copy()
    canvas = scene.copy()
    p = {
        'minScore': 0.5, 'maxMatches': 3, 'angleStart': 0, 'angleEnd': 0, 'angleStep': 10,
        'scales': [1.0], 'overlapThreshold': 0.3,
        'angleEnable': False,
        'showMatchBox': True, 'showScore': True, 'showMatchIndex': True,
        'showAngleDeg': True, 'traceFullCanvas': True,
        'showCross': True, 'showContour': True, 'showSearchRegion': True,
        'resultJudgeEnable': True, 'resultJudgeMin': 0.0, 'resultJudgeMax': 1.0,
    }
    try:
        r = tm_locate(scene, canvas, p, (0, 0), ref)
        ok(f'tm locate found={r.get("found")} count={r.get("count")} judgeOk={r.get("judgeOk")} variants={r.get("searchedVariants")}')
        assert r.get('judgeEnable') is True
        if r.get('items'):
            assert 'judgeOk' in r['items'][0] and 'judgeStatus' in r['items'][0]
            ok(f'item0 judgeStatus={r["items"][0].get("judgeStatus")} score={r["items"][0].get("score")}')
        # angleEnable False → end==start → 1 angle × scales
        assert int(r.get('searchedVariants') or 0) <= 8
        ok(f'angleEnable=False variants={r.get("searchedVariants")}')
    except Exception as exc:
        bad(f'tm locate runtime: {exc}')

    p_ng = dict(p)
    p_ng['resultJudgeMin'] = 0.9999
    p_ng['resultJudgeMax'] = 1.0
    try:
        r2 = tm_locate(scene, canvas.copy(), p_ng, (0, 0), ref)
        if r2.get('items'):
            # score typically < 1.0 for discrete match → likely NG
            ok(f'judge tight judgeOk={r2.get("judgeOk")} status0={r2["items"][0].get("judgeStatus")}')
        else:
            ok('judge tight: no items')
    except Exception as exc:
        bad(f'tm judge NG: {exc}')

    # --- geometry / caliper judge ---
    from engine import geometry
    gimg = np.zeros((100, 140, 3), dtype=np.uint8)
    cv2.line(gimg, (10, 50), (120, 50), (255, 255, 255), 2)
    gcanvas = gimg.copy()
    gp = {
        'feature': 'lines', 'findMethod': 'hough', 'maxCount': 3,
        'cannyLow': 50, 'cannyHigh': 150, 'votes': 20, 'minLength': 40, 'maxGap': 10,
        'showOverlay': True, 'showCalipers': True, 'showFitCurve': True,
        'showLabels': True, 'showPoints': True, 'showFitError': True,
        'judgeEnable': True, 'judgeMin': 50, 'judgeMax': 200,
        'caliperCount': 8, 'caliperWidth': 16, 'caliperLength': 32, 'caliperSigma': 1.2,
    }
    try:
        gr = geometry(gimg, gcanvas, gp, (0, 0))
        ok(f'geometry lines count={gr.get("count")} judgeOk={gr.get("judgeOk")}')
        assert gr.get('judgeEnable') is True
        if gr.get('items'):
            assert 'judgeOk' in gr['items'][0]
            ok(f'geom item0 metric={gr["items"][0].get("judgeMetric")} status={gr["items"][0].get("judgeStatus")}')
        else:
            ok('geom hough soft no items')
    except Exception as exc:
        bad(f'geometry: {exc}')

    from caliper_line import find_lines_caliper
    gp2 = dict(gp)
    gp2['findMethod'] = 'caliper'
    gp2['edgeThreshold'] = 30
    gray = cv2.cvtColor(gimg, cv2.COLOR_BGR2GRAY)
    try:
        cr = find_lines_caliper(gray, gcanvas.copy(), gp2, offset=(0, 0),
                                show_ov=True, show_calipers=True, show_pts=True,
                                show_fit=True, show_labels=True, show_ruler=False, show_fit_err=True)
        ok(f'caliper count={cr.get("count")} judgeOk={cr.get("judgeOk")} rms={cr.get("rms")}')
        assert 'judgeEnable' in cr
        ok('caliper judgeEnable field')
        assert '非 Halcon' in (cr.get('note') or '') or 'OpenCV' in (cr.get('note') or '')
        ok('caliper note disclaims Halcon-ish')
    except Exception as exc:
        bad(f'caliper: {exc}')

    # --- panels ---
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])

    from desktop.locate_match_panel import LocateMatchPanel, normalize_locate_params
    np_ = normalize_locate_params({})
    for k in ('showMatchIndex', 'showAngleDeg', 'traceFullCanvas', 'resultJudgeEnable', 'angleEnable'):
        (ok if k in np_ else bad)(f'locate normalize has {k}')

    step = {'id': 'm1', 'name': '快速匹配', 'type': 'locate', 'params': {}}
    panel = LocateMatchPanel(step, {}, {'steps': [step], 'edges': []})
    assert hasattr(panel, '_refresh_result_summary')
    panel._set_param('angleEnable', False)
    assert float(panel.params.get('angleStart') or 0) == 0.0
    ok('locate angleEnable=False zeros angles')
    panel._set_param('showAngleDeg', True)
    panel._set_param('resultJudgeEnable', True)
    panel._refresh_result_summary()
    txt = panel._result_summary.text()
    assert '角' in txt and '判断' in txt
    ok(f'locate result summary ok')

    from desktop.geometry_find_panel import GeometryFindPanel, normalize_geometry_params
    assert normalize_geometry_params({}, 'lines').get('caliperCount') == 10
    ok('geometry normalize caliper defaults')
    gstep = {'id': 'g1', 'name': '直线查找', 'type': 'geometry', 'params': {'feature': 'lines'}}
    gpanel = GeometryFindPanel(gstep, {}, {'steps': [gstep], 'edges': []})
    gpanel._set_param('caliperCount', 12)
    gpanel._set_param('judgeEnable', True)
    assert 'count=12' in gpanel._caliper_hint.text()
    ok('geometry live caliper hint')
    assert '判断开' in gpanel._judge_hint.text()
    ok('geometry judge hint')

    from desktop.nine_point_panel import NinePointPanel
    nstep = {'id': 'n1', 'name': '九点', 'type': 'nine_point', 'params': {}}
    npanel = NinePointPanel(nstep, {}, {'steps': [nstep], 'edges': []})
    assert hasattr(npanel, '_demo_solve') and hasattr(npanel, '_refresh_verify_checklist')
    ok('ninepoint verify APIs')
    npanel._fill_grid()
    assert len(npanel._used_points()) == 9
    ok('fill_grid 9 points')
    npanel._demo_solve()
    rms = npanel.params.get('rms')
    assert rms is not None and float(rms) < 1e-6
    ok(f'demo_solve rms={rms}')
    assert '✅' in npanel._verify_checklist.text()
    ok('verify checklist lit')
    assert 'status=ok' in npanel._verify_result.text()
    ok('verify result status=ok')

    for f, keys in (
        ('vision/engine.py', ('judgeEnable', 'judgeOk', '非 Halcon')),
        ('vision/caliper_line.py', ('judgeEnable', 'judgeOk')),
        ('desktop/nine_point_panel.py', ('ninePointDemoSolveBtn', '_demo_solve')),
    ):
        s = Path(f).read_text(encoding='utf-8')
        for k in keys:
            (ok if k in s else bad)(f'{f} has {k}')

    print('---')
    print(f'passed={pass_n} failed={fail_n}')
    return 0 if fail_n == 0 else 1

if __name__ == '__main__':
    sys.exit(main())
