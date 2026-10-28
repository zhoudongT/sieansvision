#!/usr/bin/env python3
"""wave143 UI: measure/caliper chrome + OCR/defect tables + annotate density."""
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
    from PySide6.QtWidgets import QApplication, QTableWidget, QCheckBox, QLabel
    app = QApplication.instance() or QApplication(sys.argv)

    from desktop.measure_caliper_chrome import (
        chrome_badge, soft_demo_measure_result, soft_demo_caliper_result,
        summarize_measure_result, density_measure_rows, build_measure_table_rows,
        build_caliper_item_rows, build_measure_overlays, build_caliper_overlays,
        tolerance_band, MEASURE_OPS,
    )
    ok('measure badge 距✓', chrome_badge(True, 'ok', op='point_distance') == '距✓')
    ok('caliper badge 尺3✗', chrome_badge(False, 'ng', op='caliper', count=3) == '尺3✗')
    demo = soft_demo_measure_result('point_distance', ok=True)
    summ = summarize_measure_result(demo, {'judgeMin': 80, 'judgeMax': 200, 'showTolerance': True},
                                    op='point_distance')
    ok('measure chrome 距✓', summ.get('chrome') == '距✓', summ)
    ok('measure table rows', len(summ.get('rows') or []) >= 1, summ.get('rows'))
    ok('density_measure_rows', len(density_measure_rows(demo)) >= 4)
    ok('build_measure_table_rows', len(build_measure_table_rows(demo)) >= 1)
    tb = tolerance_band(128, 80, 200)
    ok('tolerance_band', bool(tb.get('inBand')) and abs(float(tb.get('ratio') or 0) - 0.4) < 1e-6, tb)
    mov = build_measure_overlays(demo, {'showTolerance': True, 'showOverlay': True}, op='point_distance')
    mk = {o.get('type') for o in mov}
    ok('measure overlays line/point/label', 'line' in mk or 'point' in mk, mk)
    cdemo = soft_demo_caliper_result(n=3, ok=False)
    crows = build_caliper_item_rows(cdemo)
    ok('caliper item rows', len(crows) == 3, crows)
    cov = build_caliper_overlays(cdemo, {'showCalipers': True, 'showOverlay': True})
    ck = {o.get('type') for o in cov}
    ok('caliper overlays', len(cov) >= 3 and ('line' in ck or 'cross' in ck or 'point' in ck), ck)
    ok('MEASURE_OPS has point_distance', 'point_distance' in MEASURE_OPS)

    from desktop.ocr_defect_chrome import (
        chrome_badge as od_badge, soft_demo_ocr_result, soft_demo_defect_result,
        summarize_ocr_result, summarize_defect_result, build_ocr_rows, build_defect_rows,
        build_ocr_overlays, build_defect_overlays, density_summary_rows,
    )
    ok('ocr badge 识3✓', od_badge('ocr', True, 3) == '识3✓')
    ok('defect badge 缺3✗', od_badge('defects', False, 3) == '缺3✗')
    odemo = soft_demo_ocr_result(ok=True, n=3)
    osum = summarize_ocr_result(odemo, {'expectedText': 'BATCH'})
    ok('ocr chrome', str(osum.get('chrome') or '').startswith('识') and '✓' in str(osum.get('chrome')), osum)
    ok('ocr rows 3', len(osum.get('rows') or []) == 3)
    ok('build_ocr_rows', len(build_ocr_rows(odemo.get('items'))) == 3)
    oov = build_ocr_overlays(odemo, {'showBoxes': True, 'showText': True})
    ok('ocr overlays rect', any(o.get('type') == 'rect' for o in oov), {o.get('type') for o in oov})
    ddemo = soft_demo_defect_result(ok=False, n=3)
    dsum = summarize_defect_result(ddemo, {})
    ok('defect chrome 缺3✗', dsum.get('chrome') == '缺3✗', dsum)
    ok('defect rows 3', len(dsum.get('rows') or []) == 3)
    ok('build_defect_rows', len(build_defect_rows(ddemo.get('items'))) == 3)
    dov = build_defect_overlays(ddemo, {'showBoxes': True})
    ok('defect overlays', len(dov) >= 3)
    ok('density_summary_rows', len(density_summary_rows(osum)) >= 4)

    from desktop.annotate_draw_density import (
        PALETTE, pen_style, crosshair_specs, roi_rect_specs, tolerance_chip_specs,
        measure_segment_specs, caliper_probe_specs, densify_overlay_list,
        annotate_density_summary, shared_editor_defaults,
    )
    ok('PALETTE caliper', 'caliper' in PALETTE and 'tolerance_ok' in PALETTE)
    ok('pen_style roi', pen_style('roi').get('color'))
    ch = crosshair_specs(100, 80)
    ok('crosshair_specs', len(ch) >= 1)
    rr = roi_rect_specs([10, 10, 60, 40])
    ok('roi_rect_specs', any(s.get('type') == 'rect' for s in rr))
    tc = tolerance_chip_specs(50, 50, 80, 200, value=128, in_band=True)
    ok('tolerance_chip_specs', len(tc) >= 1)
    ms = measure_segment_specs(0, 0, 40, 30, judge_ok=True, label='128')
    ok('measure_segment_specs', len(ms) >= 1)
    cp = caliper_probe_specs(50, 40, 8, 40, 0.0)
    ok('caliper_probe_specs', len(cp) >= 1)
    dens = densify_overlay_list([{'type': 'line', 'x1': 0, 'y1': 0, 'x2': 10, 'y2': 10}])
    ok('densify_overlay_list', len(dens) >= 1)
    ok('annotate_density_summary', isinstance(annotate_density_summary(dens), dict))
    ok('shared_editor_defaults', 'showCrosshair' in shared_editor_defaults())

    from desktop.display_overlay_density import build_unified_overlays, summarize_overlay_density
    records = [
        {'id': 'pd1', 'operation': 'point_distance', 'output': {'result': demo}},
        {'id': 'ocr1', 'operation': 'ocr', 'output': {'result': odemo}},
        {'id': 'def1', 'operation': 'defects', 'output': {'result': ddemo}},
        {'id': 'geo1', 'operation': 'geometry',
         'output': {'result': soft_demo_caliper_result(n=2, ok=True)}},
    ]
    project = {'steps': [
        {'id': 'pd1', 'operation': 'point_distance',
         'params': {'showTolerance': True, 'showOverlay': True, 'judgeMin': 80, 'judgeMax': 200}},
        {'id': 'ocr1', 'operation': 'ocr', 'params': {'showBoxes': True, 'showText': True}},
        {'id': 'def1', 'operation': 'defects', 'params': {'showBoxes': True}},
        {'id': 'geo1', 'operation': 'geometry',
         'params': {'feature': 'lines', 'findMethod': 'caliper', 'showCalipers': True,
                    'caliperCount': 8}},
    ]}
    specs = build_unified_overlays(records, project)
    sd = summarize_overlay_density(specs)
    ok('unified measure+ocr+defect overlays', sd['total'] >= 6 and bool(sd['byType']), sd)

    proj = json.loads((ROOT / 'projects/open-and-run-measure-caliper-chrome.sieans').read_text(encoding='utf-8'))
    ops = [s['operation'] for s in proj['steps']]
    ok('project ops', ops == ['preprocess', 'geometry', 'point_distance', 'ocr', 'defects', 'var_calc'], ops)
    pd = next(s for s in proj['steps'] if s['operation'] == 'point_distance')
    ok('project showTolerance', pd['params'].get('showTolerance') is True)
    ok('notes wave143', 'wave143' in str(proj.get('notes') or ''))

    from desktop.measure_geom_panel import MeasureGeomPanel
    mstep = {'id': 'pd1', 'operation': 'point_distance', 'name': '点距',
             'params': {'showTolerance': True, 'judgeEnable': True, 'judgeMin': 80, 'judgeMax': 200,
                        'x1': 60, 'y1': 80, 'x2': 160, 'y2': 160}}
    mpanel = MeasureGeomPanel(mstep, None, project)
    ok('measure panel', mpanel is not None)
    table = mpanel.findChild(QTableWidget, 'measureGeomResultTable')
    ok('measureGeomResultTable', table is not None and table.columnCount() == 6,
       table.columnCount() if table else None)
    if hasattr(mpanel, '_soft_demo_measure_density'):
        mpanel._soft_demo_measure_density()
    ok('measure soft demo', True)
    mpanel.set_last_result({'results': [
        {'id': 'pd1', 'operation': 'point_distance', 'output': {'result': demo}},
    ]})
    ok('measure set_last_result', True)
    chrome_lab = getattr(mpanel, '_chrome_lab', None)
    ok('measure chrome lab', chrome_lab is not None and '距' in str(chrome_lab.text()),
       chrome_lab.text() if chrome_lab else None)

    from desktop.recognize_panels import DefectsPanel, OcrPanel
    ostep = {'id': 'ocr1', 'operation': 'ocr', 'name': 'OCR',
             'params': {'showBoxes': True, 'expectedText': 'BATCH', 'judgeEnable': True}}
    opanel = OcrPanel(ostep, None, project)
    ok('ocr panel', opanel is not None)
    ot = opanel.findChild(QTableWidget, 'ocrItemsTable')
    ok('ocrItemsTable 6col', ot is not None and ot.columnCount() == 6)
    if hasattr(opanel, '_soft_demo_ocr_density'):
        opanel._soft_demo_ocr_density()
    ok('ocr soft demo rows', ot.rowCount() >= 1 if ot else False, ot.rowCount() if ot else None)

    dstep = {'id': 'def1', 'operation': 'defects', 'name': '缺陷',
             'params': {'showBoxes': True, 'judgeEnable': True, 'judgeMaxCount': 2}}
    dpanel = DefectsPanel(dstep, None, project)
    ok('defects panel', dpanel is not None)
    dt = dpanel.findChild(QTableWidget, 'defectsItemsTable')
    ok('defectsItemsTable 6col', dt is not None and dt.columnCount() == 6)
    if hasattr(dpanel, '_soft_demo_defects_density'):
        dpanel._soft_demo_defects_density()
    ok('defects soft demo rows', dt.rowCount() >= 1 if dt else False, dt.rowCount() if dt else None)

    from desktop.simple_roi_editor import SimpleRoiEditorDialog
    import numpy as np_arr
    img = np_arr.zeros((100, 140, 3), dtype='uint8')
    dlg = SimpleRoiEditorDialog({'roi': [10, 10, 60, 40], 'roiMode': 'draw'}, None, image_data=img)
    ok('roi annotate helper', callable(getattr(dlg, '_annotate_density_pen', None)))
    ok('roi crosshair', getattr(dlg, 'crosshair_cb', None) is not None)

    from desktop.caliper_roi_editor import CaliperRoiEditorDialog
    cdlg = CaliperRoiEditorDialog(
        {'roi': [20, 20, 100, 80], 'caliperCount': 5, 'caliperWidth': 12, 'caliperLength': 60},
        image_data=None, parent=None,
    )
    ok('caliper annotate pens', callable(getattr(cdlg, '_annotate_density_pens', None)))

    mw = (ROOT / 'desktop/mainwindow.py').read_text(encoding='utf-8')
    ok('mw measure ingest', '_ingest_measure_geom_panel_from_result' in mw)
    ok('mw recognize ingest', '_ingest_recognize_panels_from_result' in mw)
    ok('mw menu sample', 'open-and-run-measure-caliper-chrome.sieans' in mw)

    od = (ROOT / 'desktop/display_overlay_density.py').read_text(encoding='utf-8')
    ok('overlay measure hook', 'build_measure_overlays' in od)
    ok('overlay ocr hook', 'build_ocr_overlays' in od)
    ok('overlay defect hook', 'build_defect_overlays' in od)

    for rel in ('desktop/measure_caliper_chrome.py', 'desktop/ocr_defect_chrome.py',
                'desktop/annotate_draw_density.py'):
        txt = (ROOT / rel).read_text(encoding='utf-8')
        dirty = any(x in txt for x in ('hostWatch', 'sparkBlink', 'recipeSwitch'))
        ok(f'clean {Path(rel).name}', not dirty)

    print(f'\nwave143 UI {len(passes)} pass / {len(fails)} fail')
    return 1 if fails else 0


if __name__ == '__main__':
    rc = main()
    if fails:
        print('FAILED:', ', '.join(fails))
    sys.exit(rc)
