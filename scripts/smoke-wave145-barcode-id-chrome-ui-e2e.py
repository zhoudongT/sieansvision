#!/usr/bin/env python3
"""wave145 UI: barcode/ID denser result chrome + BarcodePanel soft demo."""
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
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)

    from desktop.barcode_id_chrome import (
        chrome_badge, soft_demo_barcode_result, soft_demo_barcodes,
        summarize_barcode, build_barcode_rows, format_row_cells,
        BARCODE_COLUMNS, build_barcode_overlays, overlay_flags,
        chrome_map_from_film_cache, okng_map_from_film_cache,
        strip_summary_from_film_cache, extract_barcode_items,
        density_summary_rows,
    )
    ok('badge 码2✓', chrome_badge(True, 'OK', count=2) == '码2✓')
    ok('badge 码0✗', chrome_badge(False, 'NG', count=0) == '码0✗')
    ok('badge 码·', chrome_badge(None, '', count=None) == '码·')
    ok('BARCODE_COLUMNS 8', len(BARCODE_COLUMNS) == 8, BARCODE_COLUMNS)
    ok('cols has 文本/码制/判定', '文本' in BARCODE_COLUMNS and '码制' in BARCODE_COLUMNS and '判定' in BARCODE_COLUMNS)

    demo = soft_demo_barcode_result(n=2, ok=True)
    items = extract_barcode_items(demo)
    ok('soft demo 2 items', len(items) == 2, len(items))
    params = {
        'judgeEnable': True, 'expectedText': 'MACHINE-QR-2026',
        'judgeMinCount': 1, 'showOverlay': True, 'showBoxes': True,
        'showText': True, 'showFormat': True, 'showIndex': True,
    }
    summ = summarize_barcode(demo, params=params)
    ok('chrome 码2✓', summ.get('chrome') == '码2✓', summ.get('chrome'))
    ok('rows 2', len(summ.get('rows') or []) == 2)
    ok('judgeOk True', summ.get('judgeOk') is True, summ.get('judgeOk'))
    cells = format_row_cells((summ.get('rows') or [{}])[0])
    ok('format_row_cells 8', len(cells) == 8, cells)
    ok('top text MACHINE', 'MACHINE' in str(cells[1]), cells)

    demo_ng = soft_demo_barcode_result(n=2, ok=False)
    summ_ng = summarize_barcode(demo_ng, params=params)
    ok('chrome NG has ✗', '✗' in str(summ_ng.get('chrome') or ''), summ_ng.get('chrome'))

    rows = build_barcode_rows(soft_demo_barcodes(3, ok=True), params=params)
    ok('build_barcode_rows 3', len(rows) == 3)

    ov = build_barcode_overlays(demo, params)
    kinds = {o.get('type') for o in ov}
    ok('overlays denser', len(ov) >= 2, len(ov))
    ok('overlay kinds polygon/label', 'polygon' in kinds and ('label' in kinds or 'cross' in kinds), kinds)
    flags = overlay_flags(params)
    ok('overlay_flags non-empty', len(flags) >= 2, flags)
    dens = density_summary_rows(summ)
    ok('density_summary_rows', len(dens) >= 4, dens)

    # film cache maps
    steps = [{'id': 's1', 'operation': 'barcode', 'name': '多码识别·铬', 'params': params}]
    cache = {
        '/tmp/codes.png': {
            'results': [{
                'id': 's1', 'operation': 'barcode', 'name': '多码识别·铬',
                'output': {'result': demo},
            }],
        }
    }
    cmap = chrome_map_from_film_cache(cache, project_steps=steps)
    ok('chrome_map has 码', any('码' in str(v) for v in cmap.values()), cmap)
    omap = okng_map_from_film_cache(cache, project_steps=steps)
    ok('okng_map OK', list(omap.values()) == ['OK'] or 'OK' in omap.values(), omap)
    strip = strip_summary_from_film_cache(cache, current_path='/tmp/codes.png', project_steps=steps)
    ok('strip_summary', '条码' in strip or '码' in strip, strip)

    # BarcodePanel soft demo
    from desktop.recognize_panels import BarcodePanel, _norm_barcode
    step = {
        'id': 's1', 'operation': 'barcode', 'name': '多码识别·铬',
        'params': _norm_barcode(params),
    }
    panel = BarcodePanel(step, {}, {})
    ok('BarcodePanel builds', panel is not None)
    panel._soft_demo_barcode_density()
    chrome_lab = panel.findChild(type(panel._chrome_lab), 'barcodeChromeBadge') if hasattr(panel, '_chrome_lab') else panel._chrome_lab
    ok('chrome badge widget', chrome_lab is not None and '码' in chrome_lab.text(), getattr(chrome_lab, 'text', lambda: '')())
    table = panel._items_table
    ok('items table rows>=1', table.rowCount() >= 1, table.rowCount())
    dens_t = panel._density_table
    ok('density table rows>=1', dens_t.rowCount() >= 1, dens_t.rowCount())

    # sample JSON load
    sample = json.loads((ROOT / 'projects/open-and-run-barcode.sieans').read_text(encoding='utf-8'))
    ok('sample name 密度铬', '条码' in sample.get('name', '') and '铬' in sample.get('name', ''), sample.get('name'))
    ok('sample hostWatch', bool(sample.get('hostWatch')), sample.get('hostWatch'))
    ok('sample 2 steps', len(sample.get('steps') or []) == 2, len(sample.get('steps') or []))

    # filmstrip API exists
    from PySide6.QtWidgets import QWidget, QVBoxLayout
    from desktop.widgets.filmstrip import FilmstripBar
    host = QWidget()
    lay = QVBoxLayout(host)
    bar = FilmstripBar()
    lay.addWidget(bar)
    host.show()
    ok('set_frame_barcode_chrome', hasattr(bar, 'set_frame_barcode_chrome'))
    ok('push_barcode_summary', hasattr(bar, 'push_barcode_summary'))
    bar.set_frame_barcode_chrome({'/tmp/a.png': '码2✓'}, {'/tmp/a.png': 'OK'})
    ok('frame barcode chrome stored', getattr(bar, '_frame_barcode_chrome', {}).get('/tmp/a.png') == '码2✓')
    bar.push_barcode_summary('条码/ID · 测试 码2✓')
    strip_txt = bar.barcode_strip.text() if bar.barcode_strip else ''
    ok('barcode_strip visible', bar.barcode_strip.isVisible() and '码' in strip_txt, strip_txt)

    print(f'\nRESULT {len(passes)}/{len(passes)+len(fails)} (fail={len(fails)})')
    return 0 if not fails else 1


if __name__ == '__main__':
    sys.exit(main())
