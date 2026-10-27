#!/usr/bin/env python3
"""配方产品变体 / 变量子集 / 部分套用."""
from __future__ import annotations
import sys
from copy import deepcopy
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
            {'id': 'a', 'name': '卡尺1', 'operation': 'geometry',
             'params': {'caliperCount': 10}},
            {'id': 'c', 'name': '几何量测', 'operation': 'measure_geom',
             'params': {'op': 'line_intersect'}},
            {'id': 'b', 'name': '生产任务1', 'operation': 'production_task',
             'params': {'taskName': 'T', 'recipe': ''}},
        ],
        'variables': {'flow': {'passGate': 1, 'tol': 0.5, 'noise': 9}},
    }
    eA = rl.capture_recipe(proj, '型号A-全量', '全', variant='A型')
    assert eA.get('variant') == 'A型'
    ok(f'capture A型 full variant={eA["variant"]}')

    eSub = rl.capture_recipe(
        proj, '型号A-几何子集', '只几何', variant='A型',
        step_ops=['measure_geom'], var_keys=['passGate', 'tol'],
    )
    assert eSub.get('stepOps') == ['measure_geom']
    assert set(eSub.get('varKeys')) == {'passGate', 'tol'}
    snap_ops = {s['operation'] for s in eSub['snapshot']['steps']}
    assert snap_ops == {'measure_geom'}, snap_ops
    ok(f'capture subset ops={eSub["stepOps"]} vars={eSub["varKeys"]}')

    variants = rl.list_variants(proj)
    assert 'A型' in variants
    ok(f'list_variants={variants}')
    assert len(rl.recipes_for_variant(proj, 'A型')) >= 2
    ok('recipes_for_variant A型')

    # mutate then partial apply subset
    proj['steps'][1]['params']['op'] = 'point_distance'
    proj['variables']['flow']['passGate'] = 0
    proj['variables']['flow']['tol'] = 9.9
    proj['variables']['flow']['noise'] = 1
    proj['steps'][0]['params']['caliperCount'] = 99

    stats = rl.apply_recipe(proj, eSub['id'])  # uses recipe-stored subset
    assert stats.get('partial') or stats.get('applied') >= 1
    assert proj['steps'][1]['params']['op'] == 'line_intersect'
    assert proj['steps'][0]['params']['caliperCount'] == 99  # not in subset
    assert proj['variables']['flow']['passGate'] == 1
    assert proj['variables']['flow']['tol'] == 0.5
    assert proj['variables']['flow']['noise'] == 1  # not in varKeys
    assert proj.get('activeRecipeVariant') == 'A型'
    ok(f'partial apply via stored subset applied={stats["applied"]} vars={stats["varsApplied"]}')

    # explicit vars_only
    proj['variables']['flow']['passGate'] = 0
    st2 = rl.apply_recipe(proj, eA['id'], var_keys=['passGate'], vars_only=True)
    assert proj['variables']['flow']['passGate'] == 1
    assert st2['applied'] == 0 and st2['varsApplied'] >= 1
    ok(f'vars_only apply varsApplied={st2["varsApplied"]}')

    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    class Doc:
        def __init__(self, p): self.project = p
        def commit(self, p): self.project = p
    from desktop.recipe_switch_dialog import RecipeSwitchDialog
    dlg = RecipeSwitchDialog(Doc(deepcopy(proj)), ROOT)
    assert hasattr(dlg, '_variant_edit') and hasattr(dlg, '_partial_ops')
    assert dlg.findChild(type(dlg), 'recipePartialApplyBtn') or True
    from PySide6.QtWidgets import QPushButton
    btn = dlg.findChild(QPushButton, 'recipePartialApplyBtn')
    assert btn is not None
    ok('dialog partial-apply UI present')
    assert dlg._filter_variant.count() >= 2  # 全部 + A型
    ok(f'variant filter count={dlg._filter_variant.count()}')

    print(f"\n{'FAIL' if fail_n else 'PASS'} {pass_n} ok / {fail_n} fail")
    return 1 if fail_n else 0

if __name__ == '__main__':
    raise SystemExit(main())
