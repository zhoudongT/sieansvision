#!/usr/bin/env python3
"""wave146 UI: nine-point / var-gate denser result chrome (九N✓门✓) — budget soft closeout."""
from __future__ import annotations
import os, sys, json
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
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)

    from desktop.nine_point_var_gate_chrome import (
        chrome_badge_nine, chrome_badge_gate,
        soft_demo_nine_point_result, soft_demo_var_gate_result,
        summarize_nine_point, summarize_var_gate,
        build_residual_rows, format_residual_cells,
        build_gate_rows, format_gate_cells,
        build_nine_point_overlays, transform_matrix_rows,
        density_summary_rows_nine, density_summary_rows_gate,
        chrome_map_from_film_cache, okng_map_from_film_cache,
        strip_summary_from_film_cache,
        RESIDUAL_COLUMNS, GATE_COLUMNS, TRANSFORM_COLUMNS,
    )

    ok('badge 九9✓', chrome_badge_nine(True, 'OK', count=9) == '九9✓')
    ok('badge 九0✗', chrome_badge_nine(False, 'NG', count=0) == '九0✗')
    ok('badge 九·', chrome_badge_nine(None, '', count=None) == '九·')
    ok('badge 门✓', chrome_badge_gate(True, 'OK') == '门✓')
    ok('badge 门✗', chrome_badge_gate(False, 'NG') == '门✗')
    ok('RESIDUAL_COLUMNS 9', len(RESIDUAL_COLUMNS) == 9, RESIDUAL_COLUMNS)
    ok('GATE_COLUMNS 4', len(GATE_COLUMNS) == 4, GATE_COLUMNS)
    ok('TRANSFORM_COLUMNS 4', len(TRANSFORM_COLUMNS) == 4)

    params = {
        'rmsGate': 0.5, 'judgeMinPoints': 9, 'judgeEnable': True,
        'showOverlay': True, 'showResiduals': True, 'showPoints': True,
        'showTransform': True, 'resultVar': 'calibTransform',
        'points': soft_demo_nine_point_result(ok=True)['points'],
    }
    demo = soft_demo_nine_point_result(ok=True, n=9)
    summ = summarize_nine_point(demo, params=params)
    ok('chrome 九9✓', summ.get('chrome') == '九9✓', summ.get('chrome'))
    ok('judgeOk True', summ.get('judgeOk') is True, summ.get('judgeOk'))
    rows = summ.get('rows') or build_residual_rows(demo, params=params)
    ok('residual rows 9', len(rows) == 9, len(rows))
    cells = format_residual_cells(rows[0] if rows else {})
    ok('format_residual_cells', len(cells) == len(RESIDUAL_COLUMNS), cells)
    tm = transform_matrix_rows(demo.get('transform') or summ.get('transform'))
    ok('transform 3 rows', len(tm) == 3, tm)
    dens = density_summary_rows_nine(summ)
    ok('density_summary_rows_nine', len(dens) >= 4, dens)

    demo_ng = soft_demo_nine_point_result(ok=False, n=9)
    summ_ng = summarize_nine_point(demo_ng, params=params)
    ok('chrome NG has ✗', '✗' in str(summ_ng.get('chrome') or ''), summ_ng.get('chrome'))

    ov = build_nine_point_overlays(demo, params)
    kinds = {o.get('type') for o in ov}
    ok('overlays denser', len(ov) >= 9, len(ov))
    ok('overlay kinds', bool(kinds & {'cross', 'label', 'line', 'point', 'circle', 'text'}), kinds)

    gdemo = soft_demo_var_gate_result(ok=True, gate_name='passGate')
    gsum = summarize_var_gate(gdemo, params={'gateVar': 'passGate'}, gate_name='passGate')
    ok('gate chrome 门✓', gsum.get('chrome') == '门✓', gsum.get('chrome'))
    grows = gsum.get('rows') or build_gate_rows(gdemo, params={'gateVar': 'passGate'})
    ok('gate rows', len(grows) >= 1, grows)
    ok('format_gate_cells', len(format_gate_cells(grows[0] if grows else {})) == 4)
    ok('density_gate', len(density_summary_rows_gate(gsum)) >= 2)

    gng = summarize_var_gate(soft_demo_var_gate_result(ok=False), params={'gateVar': 'passGate'})
    ok('gate NG ✗', '✗' in str(gng.get('chrome') or ''), gng.get('chrome'))

    steps = [
        {'id': 'n1', 'operation': 'nine_point', 'name': '九点标定·铬', 'params': params},
        {'id': 'v1', 'operation': 'var_calc', 'name': '残差门限·门✓',
         'params': {'gateVar': 'passGate', 'expressions': [
             {'name': 'passGate', 'expression': '1', 'outType': 'number'}]}},
    ]
    cache = {
        '/tmp/nine.png': {
            'results': [
                {'id': 'n1', 'operation': 'nine_point', 'name': '九点标定·铬',
                 'output': {'result': demo}},
                {'id': 'v1', 'operation': 'var_calc', 'name': '残差门限·门✓',
                 'output': {'result': gdemo}},
            ],
        }
    }
    cmap = chrome_map_from_film_cache(cache, project_steps=steps)
    ok('chrome_map 九/门', any(('九' in str(v) or '门' in str(v)) for v in cmap.values()), cmap)
    omap = okng_map_from_film_cache(cache, project_steps=steps)
    ok('okng_map OK', 'OK' in list(omap.values()), omap)
    strip = strip_summary_from_film_cache(cache, current_path='/tmp/nine.png', project_steps=steps)
    ok('strip_summary', ('九' in strip or '门' in strip or '点' in strip), strip)

    from desktop.nine_point_panel import NinePointPanel, normalize_nine_point_params
    from desktop.var_calc_panel import VarCalcPanel, normalize_var_calc_params

    nparams = normalize_nine_point_params(params)
    npanel = NinePointPanel(
        {'id': 'n1', 'operation': 'nine_point', 'name': '九点标定·铬', 'params': nparams},
        {}, {})
    ok('NinePointPanel builds', npanel is not None)
    ok('nine chrome badge widget', getattr(npanel, '_chrome_lab', None) is not None)
    ok('residual table', getattr(npanel, '_residual_table', None) is not None)
    npanel._soft_demo_nine_density()
    ok('soft demo nine badge', '九' in str(npanel._chrome_lab.text()), npanel._chrome_lab.text())

    vparams = normalize_var_calc_params({
        'scope': 'flow', 'gateVar': 'passGate',
        'expressions': [
            {'name': 'passGate', 'expression': '1', 'outType': 'number', 'initial': 0, 'initOnRun': True},
        ],
    })
    vpanel = VarCalcPanel(
        {'id': 'v1', 'operation': 'var_calc', 'name': '残差门限·门✓', 'params': vparams},
        {}, {})
    ok('VarCalcPanel builds', vpanel is not None)
    ok('gate chrome badge', getattr(vpanel, '_chrome_lab', None) is not None)
    ok('gate table', getattr(vpanel, '_gate_table', None) is not None)
    vpanel._soft_demo_gate_density()
    ok('soft demo gate badge', '门' in str(vpanel._chrome_lab.text()), vpanel._chrome_lab.text())

    # filmstrip APIs present
    from desktop.widgets.filmstrip import FilmstripBar as Filmstrip
    ok('Filmstrip set_frame_nine_chrome', hasattr(Filmstrip, 'set_frame_nine_chrome'))
    ok('Filmstrip push_nine_summary', hasattr(Filmstrip, 'push_nine_summary'))

    # overlay density dispatch
    from desktop import display_overlay_density as dod
    src = Path('desktop/display_overlay_density.py').read_text()
    ok('overlay density imports nine chrome', 'build_nine_point_overlays' in src)

    # sample seed
    sample = json.loads((ROOT / 'projects/open-and-run-ninepoint.sieans').read_text())
    ops = [s.get('operation') for s in sample.get('steps') or []]
    ok('sample has nine_point+var_calc', 'nine_point' in ops and 'var_calc' in ops, ops)
    nstep = next(s for s in sample['steps'] if s['operation'] == 'nine_point')
    ok('sample rmsGate', float(nstep['params'].get('rmsGate', 0)) == 0.5)
    ok('sample 9 points', len(nstep['params'].get('points') or []) == 9)
    vstep = next(s for s in sample['steps'] if s['operation'] == 'var_calc')
    ok('sample gateVar', vstep['params'].get('gateVar') == 'passGate')
    ok('sample hostWatch', bool(sample.get('hostWatch')))

    # mainwindow hooks
    mw = (ROOT / 'desktop/mainwindow.py').read_text()
    ok('mw sync nine', '_sync_filmstrip_nine_chrome' in mw)
    ok('mw sync barcode kept', mw.count('_sync_filmstrip_barcode_chrome()') >= 2)
    ok('mw push_nine', 'push_nine_summary' in mw)
    ok('mw menu label', '九点/门限密度铬' in mw)

    print(f'\n{len(passes)} PASS / {len(fails)} FAIL')
    if fails:
        print('FAILED:', fails)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
