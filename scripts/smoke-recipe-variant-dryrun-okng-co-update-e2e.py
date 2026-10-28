#!/usr/bin/env python3
"""Recipe variant apply → production_task chain dry-run → OK-NG dashboard page co-update — no robot SDK."""
from __future__ import annotations
import ast
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / '.pydeps'))
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('SIEANS_SMOKE', '1')

pass_n = fail_n = 0

def ok(m):
    global pass_n; pass_n += 1; print('PASS:', m)

def bad(m):
    global fail_n; fail_n += 1; print('FAIL:', m)

def main():
    for rel in (
        'desktop/recipe_switch_dialog.py',
        'desktop/production_task_panel.py',
        'desktop/operator_hmi.py',
    ):
        ast.parse((ROOT / rel).read_text(encoding='utf-8'))
        ok(f'ast/parse {rel}')

    rs = (ROOT / 'desktop/recipe_switch_dialog.py').read_text(encoding='utf-8')
    for needle in (
        'recipeVariantDryRunOkNgStrip', 'recipeVariantDryRunOkNgBtn',
        'soft_apply_variant_chain_dryrun_page',
    ):
        (ok if needle in rs else bad)(f'recipe has {needle}' if needle in rs else f'missing {needle}')

    prod = (ROOT / 'desktop/production_task_panel.py').read_text(encoding='utf-8')
    for needle in (
        'productionTaskVariantDryRunOkNgStrip', 'soft_apply_variant_chain_dryrun_okng',
    ):
        (ok if needle in prod else bad)(f'panel has {needle}' if needle in prod else f'missing {needle}')

    hmi_src = (ROOT / 'desktop/operator_hmi.py').read_text(encoding='utf-8')
    for needle in (
        'hmiVariantDryRunOkNgCoUpdateStrip', 'apply_variant_dryrun_okng_co_update',
    ):
        (ok if needle in hmi_src else bad)(f'hmi has {needle}' if needle in hmi_src else f'missing {needle}')

    from PySide6.QtWidgets import QApplication, QPlainTextEdit, QLabel, QWidget, QPushButton
    from PySide6.QtCore import QCoreApplication
    app = QApplication.instance() or QApplication([])

    from desktop.production_task_panel import ProductionTaskPanel
    from desktop.operator_hmi import OperatorHmiView
    from desktop.recipe_switch_dialog import RecipeSwitchDialog

    step = {
        'id': 'pt1', 'operation': 'production_task', 'name': '生产任务',
        'params': {
            'taskName': 'dryrun任务', 'recipe': '配方A', 'statusVar': 'lineStatus',
            'scope': 'global',
            'chain': [
                {'step': '旧步', 'op': 'image_source', 'vars': ''},
            ],
        },
    }
    project = {
        'name': 'variant-dryrun-smoke',
        'steps': [step], 'edges': [],
        'variables': {'global': {}, 'flow': {}},
        'recipes': [
            {
                'id': 'r1', 'name': '配方A', 'variant': 'A型',
                'modules': [
                    {'operation': 'image_source', 'name': '图像源', 'params': {}},
                    {'operation': 'locate', 'name': '模板匹配', 'params': {}},
                    {'operation': 'send_data', 'name': '发送', 'params': {}},
                ],
            },
            {
                'id': 'r2', 'name': '配方B', 'variant': 'B型',
                'modules': [
                    {'operation': 'ocr', 'name': 'OCR', 'params': {}},
                    {'operation': 'format_data', 'name': '格式化', 'params': {}},
                ],
            },
        ],
        'activeRecipeVariant': '',
    }
    panel = ProductionTaskPanel(step, {}, project)
    view = OperatorHmiView()
    ok('panel+hmi constructed')
    assert panel.findChild(QPlainTextEdit, 'productionTaskVariantDryRunOkNgStrip') is not None
    assert view.findChild(QLabel, 'hmiVariantDryRunOkNgCoUpdateStrip') is not None
    ok('dry-run OK-NG strips present')

    class Win(QWidget):
        def __init__(self):
            super().__init__()
            self.operator_hmi = view
        def findChildren(self, typ, *a, **k):
            try:
                from desktop.production_task_panel import ProductionTaskPanel as PTP
                if typ is PTP or (isinstance(typ, type) and issubclass(PTP, typ)):
                    return [panel]
            except Exception:
                pass
            return list(super().findChildren(typ, *a, **k) or [])

    panel.window = lambda *a, **k: Win()  # type: ignore
    prev_chain = list(panel.params.get('chain') or [])

    bag = panel.soft_apply_variant_chain_dryrun_okng(
        recipe='配方A', variant='A型',
        modules=project['recipes'][0]['modules'],
        note='smoke dry-run', dry_run=True, judge='OK',
    )
    assert bag['dryRun'] is True and bag['chainSteps'] == 3, bag
    assert bag['ok'] == 1 and bag['judge'] == 'OK', bag
    assert panel.params.get('chain') == prev_chain, (panel.params.get('chain'), prev_chain)
    ok(f'panel dry-run OK · steps={bag["chainSteps"]} restored_chain={len(prev_chain)}')
    txt = panel._prod_variant_dryrun_okng.toPlainText()
    assert 'dry-run' in txt and ('模板匹配' in txt or 'locate' in txt or 'chain' in txt.lower()), txt
    ok(f'panel dry-run strip · {txt.splitlines()[0][:80]}')
    htxt = view._variant_dryrun_okng_strip.text()
    assert '配方A' in htxt and ('OK' in htxt or 'dry-run' in htxt or '看板' in htxt or '变体' in htxt), htxt
    ok(f'HMI dry-run co-update · {htxt[:90]}')
    dash = view._okng_dashboard_strip.text()
    assert 'OK' in dash or '看板' in dash or '良' in dash, dash
    ok(f'OK-NG dashboard co-updated · {dash[:80]}')

    class Doc:
        def __init__(self):
            self.project = project
            self._commits = []
        def commit(self, p):
            self.project = p
            self._commits.append(p)

    doc = Doc()
    host_win = Win()
    dlg = RecipeSwitchDialog(doc, str(ROOT), host_win)
    assert dlg.findChild(QPlainTextEdit, 'recipeVariantDryRunOkNgStrip') is not None
    assert dlg.findChild(QPushButton, 'recipeVariantDryRunOkNgBtn') is not None
    ok('recipe dialog dry-run widgets present')
    out = dlg.soft_apply_variant_chain_dryrun_page(project['recipes'][1], dry_run=True, judge='OK')
    assert out['variant'] == 'B型' and out['dryRun'] is True, out
    rtxt = dlg._variant_dryrun_okng.toPlainText()
    assert '配方B' in rtxt or 'B型' in rtxt or 'dry-run' in rtxt, rtxt
    ok(f'recipe dialog dry-run · steps={out["steps"]} · {rtxt.splitlines()[-1][:70]}')

    bag2 = panel.soft_apply_variant_chain_dryrun_okng(
        recipe='配方B', variant='B型', modules=project['recipes'][1]['modules'],
        note='smoke NG', dry_run=True, judge='NG',
    )
    assert bag2['ng'] == 1 and bag2['judge'] == 'NG', bag2
    ok(f'NG dry-run · host={bag2["hostState"]} · hmi={view._variant_dryrun_okng_strip.text()[:70]}')

    print(f'\n=== {pass_n} passed, {fail_n} failed ===')
    return 0 if fail_n == 0 else 1

if __name__ == '__main__':
    rc = main()
    import os as _os
    _os._exit(rc)
