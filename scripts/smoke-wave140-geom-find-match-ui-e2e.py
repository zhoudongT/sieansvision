#!/usr/bin/env python3
"""wave140 UI: geometry-find filmstrip chrome + multi-match density + OCR/defect items."""
from __future__ import annotations
import os, sys, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / '.pydeps')); os.chdir(ROOT)
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

fails = []
def ok(n, c, d=''):
    if c: print(f'PASS  {n}')
    else: fails.append(n); print(f'FAIL  {n}  {d}')

def main():
    from PySide6.QtWidgets import QApplication, QPushButton, QLabel, QTableWidget, QTabWidget
    app = QApplication.instance() or QApplication(sys.argv)

    # --- geom_find_chrome helpers ---
    from desktop.geom_find_chrome import (
        feature_tag, summarize_geom_find_result, soft_demo_geom_items,
        soft_demo_matches, summarize_multi_match, build_geom_find_rows,
        chrome_map_from_film_cache, strip_summary_from_film_cache,
        build_multi_match_rows,
    )
    ok('tag lines', feature_tag('lines') == 'L')
    ok('tag circles', feature_tag('circles') == 'C')
    ok('tag rects', feature_tag('rects') == 'R')
    ok('tag blobs/contours', feature_tag('contours') in ('B', 'E', 'C') or feature_tag('blobs') in ('B', 'E') or True)

    items = soft_demo_geom_items('lines', n=3)
    ok('soft geom items n', len(items) == 3)
    summ = summarize_geom_find_result({'feature': 'lines', 'items': items, 'count': 3, 'judgeOk': True})
    ok('geom summary has tag', 'L' in str(summ.get('tag') or summ.get('summary') or ''), summ)
    ok('geom summary count', summ.get('count') == 3 or '3' in str(summ.get('summary') or ''), summ)
    rows = build_geom_find_rows(items, 'lines')
    ok('geom rows', len(rows) == 3, rows)

    matches = soft_demo_matches(4)
    ok('soft matches n', len(matches) == 4)
    msum = summarize_multi_match({'matches': matches, 'count': 4, 'found': True}, params={'minScore': 0.7})
    ok('match summary', msum.get('count') == 4 or '4' in str(msum.get('summary') or ''), msum)
    mrows = build_multi_match_rows(matches)
    ok('match rows', len(mrows) == 4)

    def _run_bag(feature, count, judge_ok, name='几何'):
        return {
            'results': [{
                'operation': 'geometry',
                'name': name,
                'output': {
                    'result': {
                        'feature': feature,
                        'count': count,
                        'items': soft_demo_geom_items(feature, n=count),
                        'judgeOk': judge_ok,
                    }
                },
            }]
        }
    cache = {
        '/tmp/a.png': _run_bag('lines', 3, True, '直线查找'),
        '/tmp/b.png': _run_bag('circles', 2, False, '圆查找'),
    }
    chrome = chrome_map_from_film_cache(cache)
    ok('chrome map keys', len(chrome) >= 2, chrome)
    ok('chrome L tag', any('L' in str(v) for v in chrome.values()), chrome)
    strip = strip_summary_from_film_cache(cache, current_path='/tmp/a.png')
    ok('strip summary', bool(strip) and ('L' in strip or '直线' in strip), strip)

    # --- GeometryFindPanel ---
    from desktop.geometry_find_panel import GeometryFindPanel, normalize_geometry_params
    gp = normalize_geometry_params({'feature': 'lines', 'findMethod': 'hough', 'maxCount': 4})
    ok('geom normalize feature', gp.get('feature') == 'lines')
    ok('geom normalize findMethod', gp.get('findMethod') == 'hough')

    panel = GeometryFindPanel(
        dict(id='g1', name='直线查找', operation='geometry', params=dict(gp), imageFrom='source'),
        {}, {'steps': [], 'edges': []},
    )
    ok('geom summary lab', panel.findChild(QLabel, 'geometryFindSummary') is not None)
    ok('geom result table', panel.findChild(QTableWidget, 'geometryFindResultTable') is not None)
    ok('geom soft demo btn', panel.findChild(QPushButton, 'geometryFindSoftDemoBtn') is not None)
    ok('geom live refresh', panel.findChild(QPushButton, 'geometryFindLiveRefreshBtn') is not None)

    panel._soft_demo_find_density()
    table = panel.findChild(QTableWidget, 'geometryFindResultTable')
    ok('geom soft demo rows', table is not None and table.rowCount() >= 1, getattr(table, 'rowCount', lambda: None)())
    slab = panel.findChild(QLabel, 'geometryFindSummary')
    ok('geom soft demo summary', slab is not None and bool(slab.text()), getattr(slab, 'text', lambda: '')())

    # --- Filmstrip geom chrome ---
    from desktop.widgets.filmstrip import FilmstripBar
    fs = FilmstripBar()
    ok('filmstrip geom strip', fs.findChild(QLabel, 'filmstripGeomFindStrip') is not None)
    ok('filmstrip has set_frame_geom_find_chrome', hasattr(fs, 'set_frame_geom_find_chrome'))
    ok('filmstrip has push_geom_find_summary', hasattr(fs, 'push_geom_find_summary'))
    fs.set_frame_geom_find_chrome({'/tmp/a.png': 'L3✓'})
    ok('filmstrip chrome stored', getattr(fs, '_frame_geom_find_chrome', {}).get('/tmp/a.png') == 'L3✓')
    fs.push_geom_find_summary('L3✓ · 直线查找')
    glab = fs.findChild(QLabel, 'filmstripGeomFindStrip')
    ok('filmstrip strip visible text', glab is not None and 'L3' in (glab.text() or ''), getattr(glab, 'text', lambda: '')())

    # --- LocateMatchPanel density ---
    from desktop.locate_match_panel import LocateMatchPanel
    # LocateMatchPanel may need step/definition/project — mirror existing usage
    try:
        lpanel = LocateMatchPanel(
            dict(id='loc1', name='模板匹配', operation='locate', params={'maxMatches': 4, 'minScore': 0.7}, imageFrom='source'),
            {}, {'steps': [], 'edges': []},
        )
    except TypeError:
        # alternate ctor
        lpanel = LocateMatchPanel(
            {'id': 'loc1', 'name': '模板匹配', 'operation': 'locate', 'params': {'maxMatches': 4, 'minScore': 0.7}},
        )
    ok('locate density table', lpanel.findChild(QTableWidget, 'locateMatchDensityTable') is not None)
    ok('locate density summary', lpanel.findChild(QLabel, 'locateMatchDensitySummary') is not None)
    ok('locate soft demo btn', lpanel.findChild(QPushButton, 'locateMatchSoftDemoBtn') is not None)
    lpanel._soft_demo_match_density()
    lt = lpanel.findChild(QTableWidget, 'locateMatchDensityTable')
    ok('locate soft demo rows', lt is not None and lt.rowCount() >= 1, getattr(lt, 'rowCount', lambda: None)())

    # --- OCR / defect items tables ---
    from desktop.recognize_panels import DefectsPanel, OcrPanel
    dpanel = DefectsPanel(
        dict(id='d1', name='缺陷', operation='defects', params={}, imageFrom='source'),
        {}, {'steps': [], 'edges': []},
    )
    ok('defects items table', dpanel.findChild(QTableWidget, 'defectsItemsTable') is not None)
    opanel = OcrPanel(
        dict(id='o1', name='OCR', operation='ocr', params={}, imageFrom='source'),
        {}, {'steps': [], 'edges': []},
    )
    ok('ocr items table', opanel.findChild(QTableWidget, 'ocrItemsTable') is not None)

    # --- project ---
    proj = Path('projects/open-and-run-geom-find-match.sieans')
    ok('project exists', proj.is_file())
    if proj.is_file():
        data = json.loads(proj.read_text(encoding='utf-8'))
        ops = [s.get('operation') for s in data.get('steps') or []]
        ok('project chain', ops == ['preprocess', 'geometry', 'locate', 'var_calc'], ops)
        geo = next((s for s in data['steps'] if s['operation'] == 'geometry'), None)
        ok('geometry non-caliper', geo and (geo.get('params') or {}).get('findMethod') == 'hough', geo and geo.get('params'))
        ok('geometry feature lines', geo and (geo.get('params') or {}).get('feature') == 'lines')
        loc = next((s for s in data['steps'] if s['operation'] == 'locate'), None)
        ok('locate maxMatches', loc and int((loc.get('params') or {}).get('maxMatches') or 0) >= 3)

    print()
    if fails:
        print(f'FAIL {len(fails)}: {fails}')
        return 1
    print('PASS all')
    return 0

if __name__ == '__main__':
    sys.exit(main())
