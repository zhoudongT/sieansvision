#!/usr/bin/env python3
"""产线配方 / 换型：snapshot apply + library discover + dialog wires."""
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
             'params': {'caliperCount': 10, 'feature': 'lines'}},
            {'id': 'b', 'name': '生产任务1', 'operation': 'production_task',
             'params': {'taskName': 'T', 'recipe': ''}},
        ],
        'variables': {'global': {'x': 1}},
    }
    e1 = rl.capture_recipe(proj, '型号A', '线体1')
    assert e1['name'] == '型号A'
    assert proj['activeRecipeId'] == e1['id']
    assert proj['steps'][1]['params']['recipe'] == '型号A'
    ok(f'capture recipe id={e1["id"][:8]}…')

    # mutate then apply
    proj['steps'][0]['params']['caliperCount'] = 99
    e2 = rl.capture_recipe(proj, '型号B')
    # switch back to A
    stats = rl.apply_recipe(proj, e1['id'])
    assert stats['applied'] >= 1
    assert proj['steps'][0]['params']['caliperCount'] == 10
    assert proj['steps'][1]['params']['recipe'] == '型号A'
    ok(f'apply 型号A → caliperCount=10 applied={stats["applied"]}')

    srcs = rl.discover_library_sources(ROOT)
    assert any('caliper' in s['name'] for s in srcs), srcs[:3]
    ok(f'library sources {len(srcs)} (has caliper)')

    # dialog import + headless construct
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    class Doc:
        def __init__(self, p): self.project = p
        def commit(self, p): self.project = p
    from desktop.recipe_switch_dialog import RecipeSwitchDialog
    dlg = RecipeSwitchDialog(Doc(deepcopy(proj)), ROOT)
    assert dlg._recipe_list.count() >= 2
    ok(f'dialog lists {dlg._recipe_list.count()} recipes')
    assert dlg._lib_list.count() >= 1
    ok(f'dialog library {dlg._lib_list.count()}')

    mw = (ROOT / 'desktop/mainwindow.py').read_text(encoding='utf-8')
    if 'open_recipe_switch' in mw and '产线配方 / 换型' in mw:
        ok('mainwindow menu wired')
    else:
        bad('mainwindow missing recipe menu')

    print(f"\n{'FAIL' if fail_n else 'PASS'} {pass_n} ok / {fail_n} fail")
    return 1 if fail_n else 0

if __name__ == '__main__':
    raise SystemExit(main())
