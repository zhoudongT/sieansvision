#!/usr/bin/env python3
"""画布点选绑定 measure_geom：collect/hit_test + ImageView/panel/mainwindow wires."""
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
    from desktop.geom_canvas_pick import collect_pickables, hit_test, overlay_specs_for_pickables

    last = {
        'results': [
            {
                'id': 's1', 'name': '找线1',
                'output': {'result': {
                    'lines': [
                        {'x1': 10, 'y1': 10, 'x2': 100, 'y2': 10},
                        {'x1': 10, 'y1': 10, 'x2': 10, 'y2': 80},
                    ],
                    'matches': [{'x': 50, 'y': 40}],
                }},
            },
            {
                'id': 's2', 'name': '交点',
                'output': {'result': {'intersectX': 10, 'intersectY': 10}},
            },
        ]
    }
    proj = {'steps': [
        {'id': 's1', 'name': '找线1', 'operation': 'geometry'},
        {'id': 's2', 'name': '交点', 'operation': 'line_intersect'},
    ]}
    lines = collect_pickables(last, proj, kind='line')
    assert len(lines) >= 2, lines
    ok(f'collect lines={len(lines)} field0={lines[0].get("field")}')
    pts = collect_pickables(last, proj, kind='point')
    assert len(pts) >= 1, pts
    ok(f'collect points={len(pts)}')

    hit = hit_test(lines, 55, 12, kind='line', tol=14)
    assert hit and hit.get('field'), hit
    ok(f'hit_test line → {hit.get("field")} dist={hit.get("hitDist"):.2f}')

    specs = overlay_specs_for_pickables(lines + pts)
    assert any(s.get('type') == 'line' for s in specs)
    ok(f'overlay specs={len(specs)}')

    iv = (ROOT / 'desktop/image_view.py').read_text(encoding='utf-8')
    for n in ('geom_picked', 'set_geom_pick_mode', '_geom_pick'):
        (ok if n in iv else bad)(f'image_view has {n}' if n in iv else f'image_view missing {n}')

    mg = (ROOT / 'desktop/measure_geom_panel.py').read_text(encoding='utf-8')
    for n in ('画布点选', 'begin_geom_canvas_pick', 'measureGeomCanvasPickBtn'):
        (ok if n in mg else bad)(f'measure_geom_panel has {n}' if n in mg else f'panel missing {n}')

    mw = (ROOT / 'desktop/mainwindow.py').read_text(encoding='utf-8')
    (ok if 'def begin_geom_canvas_pick' in mw else bad)('mainwindow begin_geom_canvas_pick')

    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from desktop.image_view import ImageView
    v = ImageView()
    assert hasattr(v, 'set_geom_pick_mode')
    v.set_geom_pick_mode(True, kind='line', pickables=lines)
    assert v.geom_pick_active()
    v.set_geom_pick_mode(False)
    assert not v.geom_pick_active()
    ok('ImageView pick mode toggle')

    print(f"\n{'FAIL' if fail_n else 'PASS'} {pass_n} ok / {fail_n} fail")
    return 1 if fail_n else 0

if __name__ == '__main__':
    raise SystemExit(main())
