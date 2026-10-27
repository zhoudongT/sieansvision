#!/usr/bin/env python3
"""细妆⑯：胶片缩略悬停 → 多帧几何对比叠层."""
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
    from desktop.geom_canvas_pick import (
        overlay_specs_for_multiframe, pickables_from_cached_result,
        summarize_pickables, collect_pickables,
    )

    a = {'results': [{'id': 'c1', 'name': '找线', 'operation': 'geometry',
                      'output': {'result': {'lines': [{'x1': 0, 'y1': 0, 'x2': 10, 'y2': 0}]}}}],
         '_filmPath': '/tmp/a.png'}
    b = {'results': [{'id': 'c1', 'name': '找线', 'operation': 'geometry',
                      'output': {'result': {'lines': [{'x1': 2, 'y1': 2, 'x2': 12, 'y2': 2}],
                                            'matches': [{'x': 5, 'y': 5}]}}}],
         '_filmPath': '/tmp/b.png'}
    proj = {'steps': [{'id': 'c1', 'name': '找线', 'operation': 'geometry'}]}
    pa = pickables_from_cached_result(a, proj)
    pb = pickables_from_cached_result(b, proj)
    assert pa and pb
    ok(f'pickables a={len(pa)} b={len(pb)}')

    frames = [
        {'path': '/tmp/a.png', 'pickables': pa},
        {'path': '/tmp/b.png', 'pickables': pb},
    ]
    specs = overlay_specs_for_multiframe(frames, highlight_path='/tmp/b.png')
    assert specs, specs
    colors = {s.get('color') for s in specs}
    assert len(colors) >= 2, colors
    assert any(s.get('text') and 'b.png' in str(s.get('text')) for s in specs if s.get('type') == 'label'), specs[:4]
    ok(f'multiframe specs={len(specs)} colors={colors}')

    tip = summarize_pickables(pb)
    assert '线' in tip or '点' in tip
    ok(f'summarize={tip}')

    fs = (ROOT / 'desktop/widgets/filmstrip.py').read_text(encoding='utf-8')
    for n in ('thumbHovered', '_emit_hover', '_on_thumb_entered', 'eventFilter'):
        (ok if n in fs else bad)(f'filmstrip has {n}' if n in fs else f'missing {n}')

    mw = (ROOT / 'desktop/mainwindow.py').read_text(encoding='utf-8')
    for n in ('_on_filmstrip_thumb_hover', '_show_filmstrip_compare_overlays',
              'overlay_specs_for_multiframe', 'thumbHovered'):
        (ok if n in mw else bad)(f'mainwindow has {n}' if n in mw else f'missing {n}')

    iv = (ROOT / 'desktop/image_view.py').read_text(encoding='utf-8')
    (ok if "spec.get('width')" in iv or 'spec.get("width")' in iv else bad)('image_view width support')

    print(f"\n{'FAIL' if fail_n else 'PASS'} {pass_n} ok / {fail_n} fail")
    return 1 if fail_n else 0

if __name__ == '__main__':
    sys.exit(main())
