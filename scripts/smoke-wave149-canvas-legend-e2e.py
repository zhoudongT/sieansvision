#!/usr/bin/env python3
"""wave149: on-canvas annotate/display legend chrome — presence / toggle / bind."""
from __future__ import annotations
import os, sys, ast
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
    # --- pure helpers ---
    from desktop.canvas_legend_chrome import (
        PALETTE, LEGEND_DEFS, default_legend_entries, entries_from_overlay_specs,
        legend_summary, legend_toggle_state, html_legend_block,
    )
    ok('palette has ok/ng/roi', all(k in PALETTE for k in ('ok', 'ng', 'roi')))
    ok('LEGEND_DEFS ≥6', len(LEGEND_DEFS) >= 6, len(LEGEND_DEFS))
    defs = default_legend_entries()
    ok('default entries ≥5', len(defs) >= 5, len(defs))
    keys = {e['key'] for e in defs}
    ok('default has ok+ng+roi', {'ok', 'ng', 'roi'} <= keys, keys)

    specs = [
        dict(type='line', x1=0, y1=0, x2=10, y2=0, color='#00d250'),
        dict(type='rect', x=1, y=1, w=8, h=8, color='#e8a838'),
        dict(type='point', x=5, y=5, color='#66cfff'),
        dict(type='circle', x=20, y=20, r=4, color='#00bcd4'),
        dict(type='label', x=2, y=2, text='d=1.2', color='#9ad'),
        dict(type='polygon', points=[[0, 0], [1, 0], [1, 1]], color='#7c4dff'),
    ]
    bound = entries_from_overlay_specs(specs, judge_ok=True)
    bkeys = {e['key'] for e in bound}
    ok('bind activates measure', 'measure' in bkeys, bkeys)
    ok('bind activates roi', 'roi' in bkeys, bkeys)
    ok('bind activates point', 'point' in bkeys, bkeys)
    ok('bind activates find', 'find' in bkeys, bkeys)
    ok('bind activates match', 'match' in bkeys, bkeys)
    ok('bind activates label', 'label' in bkeys, bkeys)
    ok('bind keeps ok/ng', {'ok', 'ng'} <= bkeys, bkeys)
    summ = legend_summary(bound)
    ok('summary 图例', str(summ.get('summary', '')).startswith('图例'), summ)
    html = html_legend_block(bound)
    ok('html has 图例 title', '图例' in html and '●' in html, html[:80])
    tog = legend_toggle_state(True)
    ok('toggle open label', tog.get('label') == '图例·开' and tog.get('visible') is True, tog)
    tog2 = legend_toggle_state(False)
    ok('toggle closed label', tog2.get('label') == '图例·关', tog2)

    empty_bound = entries_from_overlay_specs([], judge_ok=None)
    ok('empty specs still has defaults', len(empty_bound) >= 3, empty_bound)

    # --- ImageView chrome ---
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)

    from desktop.image_view import ImageView
    view = ImageView()
    view.resize(640, 480)
    view.show()
    app.processEvents()

    ok('ImageView has legend API', all(hasattr(view, m) for m in (
        'bind_legend_from_specs', 'set_canvas_legend', 'set_legend_visible',
        'toggle_legend', 'legend_visible', 'clear_canvas_legend',
        '_ensure_legend_chrome',
    )))

    entries = view.bind_legend_from_specs(specs, judge_ok=True)
    app.processEvents()
    ok('bind returns entries', len(entries) >= 4, len(entries))
    ok('legend_visible default True', view.legend_visible() is True)
    frame = view._ensure_legend_chrome()
    ok('legend frame exists', frame is not None)
    ok('legend frame visible after bind', frame.isVisible(), frame.isVisible())
    ok('legend label has 图例', '图例' in (view._legend_label.text() or ''), view._legend_label.text()[:60])
    stored = view.canvas_legend_entries()
    ok('canvas_legend_entries stored', len(stored) == len(entries), len(stored))

    view.set_legend_visible(False)
    app.processEvents()
    ok('toggle hide', view.legend_visible() is False and not frame.isVisible())
    vis = view.toggle_legend()
    app.processEvents()
    ok('toggle show', vis is True and frame.isVisible())

    view.clear_canvas_legend()
    app.processEvents()
    ok('clear hides when empty', not frame.isVisible() and view.canvas_legend_entries() == [])

    # rebind + set_geom_overlays path (display)
    view.bind_legend_from_specs(specs)
    view.set_geom_overlays(specs)
    app.processEvents()
    ok('overlays + legend coexist', len(getattr(view, '_geom_items', []) or []) >= 1
       and frame.isVisible())

    # showOverlay-style visibility
    view.set_legend_visible(False)
    ok('display-like hide', not view.legend_visible())
    view.set_legend_visible(True)
    view.bind_legend_from_specs(getattr(view, '_last_overlay_specs', None) or specs)
    app.processEvents()
    ok('display-like rebind show', view.legend_visible() and frame.isVisible())

    # source wiring
    mw = (ROOT / 'desktop/mainwindow.py').read_text(encoding='utf-8')
    ok('mainwindow binds legend', 'bind_legend_from_specs' in mw)
    ok('mainwindow showOverlay legend', 'set_legend_visible' in mw and 'showOverlay' in mw)
    iv = (ROOT / 'desktop/image_view.py').read_text(encoding='utf-8')
    ok('image_view canvasLegendChrome', 'canvasLegendChrome' in iv)
    ok('image_view wave149', 'wave149' in iv)
    cl = (ROOT / 'desktop/canvas_legend_chrome.py').read_text(encoding='utf-8')
    ok('legend module wave149', 'wave149' in cl or 'On-canvas' in cl)
    for rel in ('desktop/canvas_legend_chrome.py', 'desktop/image_view.py', 'desktop/mainwindow.py'):
        ast.parse((ROOT / rel).read_text(encoding='utf-8'))
        ok(f'AST {Path(rel).name}', True)

    docs = (ROOT / 'docs/open-and-run-samples.md').read_text(encoding='utf-8')
    ok('docs mentions 图例/legend wave149', 'wave149' in docs or '图例' in docs, 'need docs one-liner')

    print(f'\n{len(passes)} PASS / {len(fails)} FAIL')
    if fails:
        print('FAILED:', ', '.join(fails))
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
