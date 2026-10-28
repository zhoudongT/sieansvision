#!/usr/bin/env python3
"""wave141 UI: contour/blob chrome + color-region panel + unified overlay density."""
from __future__ import annotations
import os, sys, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / '.pydeps'))
os.chdir(ROOT)
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

fails = []

def ok(n, c, d=''):
    if c:
        print(f'PASS  {n}')
    else:
        fails.append(n)
        print(f'FAIL  {n}  {d}')


def main():
    from PySide6.QtWidgets import QApplication, QPushButton, QLabel, QTableWidget, QTabWidget
    app = QApplication.instance() or QApplication(sys.argv)

    from desktop.geom_find_chrome import (
        feature_tag, soft_demo_geom_items, build_geom_find_rows,
        summarize_geom_find_result, build_contour_blob_overlays,
    )
    ok('tag contours', feature_tag('contours') == 'B')
    items = soft_demo_geom_items('contours', n=3)
    rows = build_geom_find_rows(items, 'contours')
    ok('contour rows n', len(rows) == 3)
    ok('contour peri/center', bool(rows and rows[0].get('perimeter') and rows[0].get('centerX') is not None), rows[:1])
    summ = summarize_geom_find_result({'feature': 'contours', 'items': items, 'judgeOk': True})
    ok('contour chrome', str(summ.get('chrome') or '').startswith('B') and '✓' in str(summ.get('chrome') or ''), summ)
    ovs = build_contour_blob_overlays(items, feature='contours')
    kinds = {o.get('type') for o in ovs}
    ok('contour overlays poly+cross', 'polygon' in kinds and 'cross' in kinds, kinds)

    from desktop.region_color_chrome import (
        operator_tag, soft_demo_region_items, summarize_region_result,
        build_region_overlays, chrome_map_from_film_cache,
    )
    ok('region tags', operator_tag('color') == '色' and operator_tag('blobs') == '斑')
    ritems = soft_demo_region_items('color', n=2)
    rsum = summarize_region_result({
        'count': 2,
        'areaPixels': sum(i['areaPixels'] for i in ritems),
        'coveragePercent': 12.5,
        'largestArea': ritems[0]['areaPixels'],
        'items': ritems,
        'passed': True,
    }, params={'operatorId': 'color'})
    ok('region chrome 色2✓', rsum.get('chrome') == '色2✓', rsum)
    rov = build_region_overlays(ritems, show_ellipse=True)
    rk = {o.get('type') for o in rov}
    ok('region overlays', 'rect' in rk and 'cross' in rk and 'ellipse' in rk, rk)

    film = {
        '/tmp/a.png': {
            'results': [{
                'id': 'p1', 'operation': 'plugin', 'name': 'HSV',
                'output': {'result': {
                    'count': 2, 'areaPixels': 16800, 'coveragePercent': 10,
                    'largestArea': 12000, 'items': ritems, 'passed': True,
                }},
            }],
        }
    }
    steps = [{'id': 'p1', 'operation': 'plugin',
              'params': {'pluginId': 'sieans-regions', 'operatorId': 'color'}}]
    cm = chrome_map_from_film_cache(film, project_steps=steps)
    ok('film region chrome', str(cm.get('/tmp/a.png') or '').startswith('色'), cm)

    from desktop.display_overlay_density import build_unified_overlays, summarize_overlay_density
    records = [
        {'id': 'g1', 'operation': 'geometry',
         'output': {'result': {'feature': 'contours', 'items': items}}},
        {'id': 'p1', 'operation': 'plugin',
         'output': {'result': {
             'count': 2, 'areaPixels': 16800, 'coveragePercent': 10,
             'largestArea': 12000, 'items': ritems, 'passed': True,
         }}},
        {'id': 'm1', 'operation': 'locate',
         'output': {'result': {'matches': [
             {'index': 1, 'score': 0.95, 'centerX': 50, 'centerY': 60,
              'width': 40, 'height': 30},
         ]}}},
    ]
    project = {'steps': [
        {'id': 'g1', 'operation': 'geometry',
         'params': {'feature': 'contours', 'showOverlay': True}},
        {'id': 'p1', 'operation': 'plugin',
         'params': {'pluginId': 'sieans-regions', 'operatorId': 'color',
                    'arguments': {'showOverlay': True}}},
        {'id': 'm1', 'operation': 'locate',
         'params': {'showMatchBox': True, 'showCross': True, 'showScore': True}},
    ]}
    specs = build_unified_overlays(records, project)
    sd = summarize_overlay_density(specs)
    ok('unified overlays', sd['total'] >= 6 and bool(sd['byType']), sd)

    proj = json.loads((ROOT / 'projects/open-and-run-contour-color.sieans').read_text(encoding='utf-8'))
    ops = [s['operation'] for s in proj['steps']]
    ok('project ops', ops == ['preprocess', 'geometry', 'plugin', 'var_calc'], ops)
    geo = next(s for s in proj['steps'] if s['operation'] == 'geometry')
    ok('project contours', geo['params'].get('feature') == 'contours')
    plug = next(s for s in proj['steps'] if s['operation'] == 'plugin')
    ok('project sieans-regions', plug['params'].get('pluginId') == 'sieans-regions')

    from desktop.region_color_panel import RegionColorPanel, normalize_region_color_params
    np = normalize_region_color_params({'pluginId': 'sieans-regions', 'operatorId': 'color'})
    ok('normalize hue/cross', np['arguments'].get('hueMin') == 170 and np['arguments'].get('showCross') is True, np['arguments'])

    step = {
        'id': 'rc1', 'operation': 'plugin', 'name': 'HSV色彩区域',
        'params': np,
    }
    panel = RegionColorPanel(step, None, project)
    ok('panel tabs', isinstance(panel.tabs, QTabWidget) and panel.tabs.count() >= 3)
    panel._soft_demo_region_density()
    ok('panel soft demo table', panel._region_table.rowCount() >= 1, panel._region_table.rowCount())
    ok('panel summary label', '色' in panel._region_summary.text() or '区域' in panel._region_summary.text(),
       panel._region_summary.text())
    ok('panel soft demo btn', panel.findChild(QPushButton, 'regionColorSoftDemoBtn') is not None)
    ok('panel result table obj', panel.findChild(QTableWidget, 'regionColorResultTable') is not None)

    eng = (ROOT / 'vision/engine.py').read_text(encoding='utf-8')
    ok('engine circularity', "'circularity': circ" in eng or 'circularity' in eng)

    iv = (ROOT / 'desktop/image_view.py').read_text(encoding='utf-8')
    for kind in ('polygon', 'cross', 'ellipse', 'circle'):
        ok(f'image_view {kind}', f"kind == '{kind}'" in iv)

    mw = (ROOT / 'desktop/mainwindow.py').read_text(encoding='utf-8')
    ok('mw overlay density', '_apply_find_overlay_density' in mw)
    ok('mw region ingest', '_ingest_region_color_panel_from_result' in mw)
    ok('mw menu sample', 'open-and-run-contour-color.sieans' in mw)

    pf = (ROOT / 'desktop/property_float.py').read_text(encoding='utf-8')
    ok('property_float RegionColorPanel', 'RegionColorPanel' in pf)

    print(f'\nwave141 UI {len(fails)} fail / {pass_n_total()} checks')
    return 1 if fails else 0


def pass_n_total():
    # recount from prints is awkward; use fails only for exit
    return 'see above'


if __name__ == '__main__':
    # recount passes roughly
    rc = main()
    if fails:
        print('FAILED:', ', '.join(fails))
    sys.exit(rc)
