#!/usr/bin/env python3
"""wave147 UI: OCR/defect denser result chrome (识N✓缺N✓) — budget soft closeout wave."""
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

    from desktop.ocr_defect_chrome import (
        chrome_badge, soft_demo_ocr_result, soft_demo_defect_result,
        summarize_ocr_result, summarize_defect_result,
        build_ocr_rows, build_defect_rows,
        format_ocr_cells, format_defect_cells,
        OCR_COLUMNS, DEFECT_COLUMNS,
        build_ocr_overlays, build_defect_overlays,
        overlay_flags, overlay_flags_ocr, overlay_flags_defect,
        chrome_map_from_film_cache, okng_map_from_film_cache,
        strip_summary_from_film_cache, density_summary_rows,
        OCR_OPS, DEFECT_OPS,
    )

    ok('badge 识3✓', chrome_badge('ocr', True, 3, 'OK') == '识3✓')
    ok('badge 识0✗', chrome_badge('ocr', False, 0, 'NG') == '识0✗')
    ok('badge 识·', chrome_badge('ocr', None, None, '') == '识·')
    ok('badge 缺2✗', chrome_badge('defects', False, 2, 'NG') == '缺2✗')
    ok('badge 缺0✓', chrome_badge('defects', True, 0, 'OK') == '缺0✓')
    ok('OCR_COLUMNS 8', len(OCR_COLUMNS) == 8, OCR_COLUMNS)
    ok('DEFECT_COLUMNS 8', len(DEFECT_COLUMNS) == 8, DEFECT_COLUMNS)
    ok('cols OCR 文本/判定', '文本' in OCR_COLUMNS and '判定' in OCR_COLUMNS)
    ok('cols defect 面积/判定', '面积' in DEFECT_COLUMNS and '判定' in DEFECT_COLUMNS)
    ok('OCR_OPS', 'ocr' in OCR_OPS)
    ok('DEFECT_OPS', 'defects' in DEFECT_OPS)

    params_o = {
        'judgeEnable': True, 'expectedText': 'BATCH', 'judgeMinConfidence': 0.5,
        'showOverlay': True, 'showBoxes': True, 'showText': True,
        'showConf': True, 'showIndex': True, 'showRoi': True,
        'roi': [20, 40, 400, 120],
    }
    demo = soft_demo_ocr_result(ok=True, n=3)
    summ = summarize_ocr_result(demo, params_o)
    ok('chrome 识3✓', summ.get('chrome') == '识3✓', summ.get('chrome'))
    ok('ocr rows 3', len(summ.get('rows') or []) == 3)
    ok('ocr judgeOk True', summ.get('judgeOk') is True, summ.get('judgeOk'))
    cells = format_ocr_cells((summ.get('rows') or [{}])[0])
    ok('format_ocr_cells 8', len(cells) == 8, cells)
    ok('ocr top text BATCH', 'BATCH' in str(cells[1]), cells)

    demo_ng = soft_demo_ocr_result(ok=False, n=3)
    summ_ng = summarize_ocr_result(demo_ng, params_o)
    ok('ocr chrome NG has ✗', '✗' in str(summ_ng.get('chrome') or ''), summ_ng.get('chrome'))

    rows = build_ocr_rows(demo.get('items'), params=params_o)
    ok('build_ocr_rows 3', len(rows) == 3)

    ov = build_ocr_overlays(demo, params_o)
    kinds = {o.get('type') for o in ov}
    ok('ocr overlays denser', len(ov) >= 3, len(ov))
    ok('ocr overlay kinds', bool(kinds & {'rect', 'label', 'cross'}), kinds)
    ok('ocr has ROI overlay', any(o.get('text') == 'ROI' or (o.get('type') == 'rect' and o.get('color') == '#ffb400') for o in ov), ov[:2])
    flags = overlay_flags_ocr(params_o)
    ok('overlay_flags_ocr', len(flags) >= 3, flags)
    dens = density_summary_rows(summ)
    ok('density_summary_rows ocr', len(dens) >= 4 and any(r.get('key') == '徽标' for r in dens), dens)

    params_d = {
        'judgeEnable': True, 'judgeMaxCount': 0, 'minArea': 20,
        'showOverlay': True, 'showBoxes': True, 'showLabels': True,
        'showArea': True, 'showIndex': True, 'showRoi': True,
        'method': 'absdiff',
    }
    ddemo = soft_demo_defect_result(ok=True, n=0)
    dsum = summarize_defect_result(ddemo, params_d)
    ok('defect chrome 缺0✓', dsum.get('chrome') == '缺0✓', dsum.get('chrome'))
    ok('defect judgeOk True', dsum.get('judgeOk') is True)

    ddemo_ng = soft_demo_defect_result(ok=False, n=3)
    dsum_ng = summarize_defect_result(ddemo_ng, params_d)
    ok('defect chrome has ✗', '✗' in str(dsum_ng.get('chrome') or ''), dsum_ng.get('chrome'))
    ok('defect rows 3', len(dsum_ng.get('rows') or []) == 3)
    dcells = format_defect_cells((dsum_ng.get('rows') or [{}])[0])
    ok('format_defect_cells 8', len(dcells) == 8, dcells)
    dov = build_defect_overlays(ddemo_ng, params_d)
    ok('defect overlays denser', len(dov) >= 3, len(dov))
    dflags = overlay_flags_defect(params_d)
    ok('overlay_flags_defect', len(dflags) >= 3, dflags)
    ddens = density_summary_rows(dsum_ng)
    ok('density_summary_rows defect', any(r.get('key') == '缺陷数' for r in ddens), ddens)

    # film cache maps
    steps = [
        {'id': 's1', 'operation': 'ocr', 'name': 'OCR工业表·铬', 'params': params_o},
        {'id': 's2', 'operation': 'defects', 'name': '缺陷工业表·铬', 'params': params_d},
    ]
    cache = {
        '/tmp/text.png': {
            'results': [
                {'id': 's1', 'operation': 'ocr', 'name': 'OCR工业表·铬',
                 'output': {'result': demo}},
                {'id': 's2', 'operation': 'defects', 'name': '缺陷工业表·铬',
                 'output': {'result': ddemo}},
            ],
        }
    }
    cmap = chrome_map_from_film_cache(cache, project_steps=steps)
    ok('chrome_map has 识/缺', any(('识' in str(v) or '缺' in str(v)) for v in cmap.values()), cmap)
    omap = okng_map_from_film_cache(cache, project_steps=steps)
    ok('okng_map OK', 'OK' in omap.values(), omap)
    strip = strip_summary_from_film_cache(cache, current_path='/tmp/text.png', project_steps=steps)
    ok('strip_summary OCR/缺陷', 'OCR' in strip or '识' in strip or '缺' in strip, strip)

    # Panels soft demo
    from desktop.recognize_panels import OcrPanel, DefectsPanel, _norm_ocr

    ostep = {'id': 's1', 'operation': 'ocr', 'name': 'OCR工业表·铬', 'params': dict(params_o)}
    try:
        from desktop.recognize_panels import _norm_ocr as _no
        ostep['params'] = _no(ostep['params'])
    except Exception:
        pass
    opanel = OcrPanel(ostep, {}, {})
    ok('OcrPanel builds', opanel is not None)
    opanel._soft_demo_ocr_density()
    ok('ocr chrome badge', getattr(opanel, '_chrome_lab', None) is not None and '识' in opanel._chrome_lab.text(),
       getattr(getattr(opanel, '_chrome_lab', None), 'text', lambda: '')())
    ok('ocr items table rows>=1', opanel._ocr_items_table.rowCount() >= 1, opanel._ocr_items_table.rowCount())
    ok('ocr items cols 8', opanel._ocr_items_table.columnCount() == 8, opanel._ocr_items_table.columnCount())
    ok('ocr density rows>=1', opanel._density_table.rowCount() >= 1, opanel._density_table.rowCount())

    dstep = {'id': 's2', 'operation': 'defects', 'name': '缺陷工业表·铬', 'params': dict(params_d)}
    dpanel = DefectsPanel(dstep, {}, {})
    ok('DefectsPanel builds', dpanel is not None)
    dpanel._soft_demo_defects_density()
    ok('defect chrome badge', getattr(dpanel, '_chrome_lab', None) is not None and '缺' in dpanel._chrome_lab.text(),
       getattr(getattr(dpanel, '_chrome_lab', None), 'text', lambda: '')())
    ok('defect items table', dpanel._defects_items_table.columnCount() == 8, dpanel._defects_items_table.columnCount())

    # sample JSON
    sample = json.loads((ROOT / 'projects/open-and-run-ocr-defect-chrome.sieans').read_text(encoding='utf-8'))
    ok('sample name 密度铬', 'OCR' in sample.get('name', '') and '铬' in sample.get('name', ''), sample.get('name'))
    ok('sample hostWatch', bool(sample.get('hostWatch')), sample.get('hostWatch'))
    ops = [s.get('operation') for s in (sample.get('steps') or [])]
    ok('sample has ocr+defects+var_calc', ops == ['ocr', 'defects', 'var_calc'], ops)

    # filmstrip API
    from PySide6.QtWidgets import QWidget, QVBoxLayout
    from desktop.widgets.filmstrip import FilmstripBar
    host = QWidget()
    lay = QVBoxLayout(host)
    bar = FilmstripBar()
    lay.addWidget(bar)
    host.show()
    ok('set_frame_ocr_chrome', hasattr(bar, 'set_frame_ocr_chrome'))
    ok('push_ocr_summary', hasattr(bar, 'push_ocr_summary'))
    bar.set_frame_ocr_chrome({'/tmp/a.png': '识3✓缺0✓'}, {'/tmp/a.png': 'OK'})
    ok('frame ocr chrome stored', getattr(bar, '_frame_ocr_chrome', {}).get('/tmp/a.png') == '识3✓缺0✓')
    bar.push_ocr_summary('OCR/缺陷 · 测试 识3✓')
    strip_txt = bar.ocr_strip.text() if bar.ocr_strip else ''
    ok('ocr_strip visible', bar.ocr_strip.isVisible() and ('识' in strip_txt or 'OCR' in strip_txt), strip_txt)

    # overlay density wiring still imports
    from desktop.display_overlay_density import build_unified_overlays
    specs = build_unified_overlays(
        [{'id': 's1', 'operation': 'ocr', 'output': {'result': demo}},
         {'id': 's2', 'operation': 'defects', 'output': {'result': ddemo_ng}}],
        {'steps': steps},
    )
    ok('unified overlays include ocr/defect', len(specs) >= 2, len(specs))

    print(f'\nRESULT {len(passes)}/{len(passes)+len(fails)} (fail={len(fails)})')
    return 0 if not fails else 1


if __name__ == '__main__':
    sys.exit(main())
