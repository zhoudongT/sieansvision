#!/usr/bin/env python3
"""细妆⑯：配方变体 / 换型前 params delta chip 预览."""
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
             'params': {'caliperCount': 5, 'roi': [0, 0, 10, 10]}},
            {'id': 'b', 'name': '变量', 'operation': 'var_calc',
             'params': {'expressions': [{'name': 'x', 'expression': '1'}]}},
        ],
        'variables': {'flow': {'x': 1}},
    }
    rl.capture_recipe(proj, 'A-全', variant='A型')
    proj['steps'][0]['params']['caliperCount'] = 12
    proj['variables']['flow']['x'] = 99
    rl.capture_recipe(proj, 'B-全', variant='B型')

    # live is B state; diff against A should show deltas
    recs = rl.recipes_for_variant(proj, 'A型')
    diff = rl.diff_recipe(proj, recs[0]['id'])
    assert diff['summary']['stepsChanged'] >= 1, diff
    chip = rl.format_diff_chip(diff)
    assert '模块' in chip or 'Δ' in chip or '变量' in chip, chip
    ok(f'diff A vs live chip={chip}')

    # identical → 无变化
    stats = rl.apply_recipe(proj, recs[0]['id'])
    diff2 = rl.diff_recipe(proj, recs[0]['id'])
    assert diff2['summary']['stepsChanged'] == 0
    ok(f'after apply identical chip={rl.format_diff_chip(diff2)}')

    src = (ROOT / 'desktop/recipe_switch_dialog.py').read_text(encoding='utf-8')
    for n in ('recipeDiffChip', '_refresh_diff_chip', '差分预览', 'diff_recipe'):
        (ok if n in src else bad)(f'dialog has {n}' if n in src else f'missing {n}')

    mw = (ROOT / 'desktop/mainwindow.py').read_text(encoding='utf-8')
    (ok if '变体差分预览' in mw or 'format_diff_chip' in mw else bad)('mainwindow variant diff log')

    lib = (ROOT / 'desktop/recipe_library.py').read_text(encoding='utf-8')
    for n in ('def diff_recipe', 'def format_diff_chip', 'stepDeltas', 'varDeltas'):
        (ok if n in lib else bad)(f'library has {n}' if n in lib else f'missing {n}')

    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    # minimal document stub
    class Doc:
        def __init__(self, project):
            self.project = project
        def commit(self, p):
            self.project = p
        changed = type('S', (), {'emit': staticmethod(lambda *a, **k: None)})()
    from desktop.recipe_switch_dialog import RecipeSwitchDialog
    dlg = RecipeSwitchDialog(Doc(proj), ROOT, None)
    assert hasattr(dlg, '_diff_chip')
    dlg._refresh_diff_chip()
    ok(f'dialog chip text={dlg._diff_chip.text()[:80]}')

    print(f"\n{'FAIL' if fail_n else 'PASS'} {pass_n} ok / {fail_n} fail")
    return 1 if fail_n else 0

if __name__ == '__main__':
    sys.exit(main())
