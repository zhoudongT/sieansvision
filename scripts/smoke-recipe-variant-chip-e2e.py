#!/usr/bin/env python3
"""细妆⑮：配方变体快切 chip — toolbar + production_task."""
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
    from desktop import recipe_library as rl
    proj = {
        'name': 't',
        'steps': [
            {'id': 'a', 'name': '卡尺', 'operation': 'geometry',
             'params': {'caliperCount': 5}},
            {'id': 'b', 'name': '生产任务1', 'operation': 'production_task',
             'params': {'taskName': 'T', 'recipe': ''}},
        ],
        'variables': {'flow': {}},
    }
    rl.capture_recipe(proj, 'A-全', variant='A型')
    # mutate then capture B
    proj['steps'][0]['params']['caliperCount'] = 12
    rl.capture_recipe(proj, 'B-全', variant='B型')
    assert 'A型' in rl.list_variants(proj) and 'B型' in rl.list_variants(proj)
    ok(f'variants={rl.list_variants(proj)}')

    # simulate quick-switch to A
    proj['steps'][0]['params']['caliperCount'] = 99
    recs = rl.recipes_for_variant(proj, 'A型')
    stats = rl.apply_recipe(proj, recs[0]['id'])
    assert proj['steps'][0]['params']['caliperCount'] == 5
    assert proj.get('activeRecipeVariant') == 'A型'
    ok(f'quick-switch A applied={stats["applied"]} count=5')

    mw = (ROOT / 'desktop/mainwindow.py').read_text(encoding='utf-8')
    for n in ('recipeVariantChip', 'refresh_variant_chip', 'apply_variant_quick', '_on_variant_chip'):
        (ok if n in mw else bad)(f'mainwindow has {n}' if n in mw else f'missing {n}')

    pt = (ROOT / 'desktop/production_task_panel.py').read_text(encoding='utf-8')
    for n in ('productionTaskVariantChip', '_apply_variant_chip', '_fill_variant_chip', '套用变体'):
        (ok if n in pt else bad)(f'production_task has {n}' if n in pt else f'missing {n}')

    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from desktop.production_task_panel import ProductionTaskPanel
    step = {'id': 'b', 'name': '生产任务1', 'operation': 'production_task',
            'params': {'taskName': 'T', 'recipe': ''}}
    panel = ProductionTaskPanel(step, {}, proj)
    assert hasattr(panel, '_variant_chip')
    assert panel._variant_chip.count() >= 2  # placeholder + variants
    ok(f'panel variant chip count={panel._variant_chip.count()}')
    # apply B via panel
    i = panel._variant_chip.findData('B型')
    assert i >= 0
    panel._variant_chip.setCurrentIndex(i)
    panel._apply_variant_chip()
    assert proj['steps'][0]['params']['caliperCount'] == 12
    ok('panel apply B型 → caliperCount=12')

    print(f"\n{'FAIL' if fail_n else 'PASS'} {pass_n} ok / {fail_n} fail")
    return 1 if fail_n else 0

if __name__ == '__main__':
    sys.exit(main())
