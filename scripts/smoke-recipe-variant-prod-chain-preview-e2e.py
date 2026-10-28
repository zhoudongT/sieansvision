#!/usr/bin/env python3
"""Recipe variant list ↔ production_task chain soft preview page chrome — no robot SDK / no chips."""
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
        'recipeVariantChainPreviewStrip', 'recipeVariantChainPreviewMeta',
        'soft_preview_variant_prod_chain_page',
    ):
        (ok if needle in rs else bad)(
            f'recipe has {needle}' if needle in rs else f'missing {needle}'
        )

    prod = (ROOT / 'desktop/production_task_panel.py').read_text(encoding='utf-8')
    for needle in (
        'productionTaskVariantChainPreviewStrip', 'productionTaskVariantChainPreviewMeta',
        'soft_preview_variant_prod_chain',
    ):
        (ok if needle in prod else bad)(
            f'panel has {needle}' if needle in prod else f'missing {needle}'
        )

    hmi_src = (ROOT / 'desktop/operator_hmi.py').read_text(encoding='utf-8')
    for needle in ('hmiVariantChainPreviewStrip', 'apply_variant_chain_preview_chrome'):
        (ok if needle in hmi_src else bad)(
            f'hmi has {needle}' if needle in hmi_src else f'missing {needle}'
        )

    from PySide6.QtWidgets import QApplication, QPlainTextEdit, QLabel, QWidget
    from PySide6.QtCore import QCoreApplication, Qt
    app = QApplication.instance() or QApplication([])

    from desktop.production_task_panel import ProductionTaskPanel
    from desktop.operator_hmi import OperatorHmiView
    from desktop.recipe_switch_dialog import RecipeSwitchDialog

    step = {
        'id': 'pt1', 'operation': 'production_task', 'name': '生产任务',
        'params': {
            'taskName': '变体链预览任务',
            'recipe': '配方A',
            'statusVar': 'lineStatus',
            'scope': 'global',
            'chain': [
                {'step': '读取图像', 'op': '图像源', 'vars': ''},
                {'step': '模板匹配', 'op': 'locate', 'vars': ''},
                {'step': '发送', 'op': 'send_data', 'vars': ''},
            ],
        },
    }
    project = {
        'name': 'variant-chain-smoke',
        'steps': [step, {'id': 's1', 'operation': 'image_source', 'name': '图像源', 'params': {}}],
        'edges': [],
        'variables': {'global': {}, 'flow': {}},
        'recipes': [
            {
                'id': 'r1', 'name': '配方A', 'variant': 'A型',
                'modules': [
                    {'operation': 'image_source', 'name': '图像源', 'params': {'path': 'a.png'}},
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
    assert panel.findChild(QPlainTextEdit, 'productionTaskVariantChainPreviewStrip') is not None
    assert view.findChild(QLabel, 'hmiVariantChainPreviewStrip') is not None
    ok('variant chain preview strips present')

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

    snap = panel.soft_preview_variant_prod_chain(
        recipe='配方A', variant='A型',
        modules=project['recipes'][0]['modules'], note='smoke预览',
    )
    assert snap['variant'] == 'A型' and snap['chainSteps'] == 3, snap
    txt = panel._prod_variant_chain_preview.toPlainText()
    assert '模板匹配' in txt or 'locate' in txt or 'soft preview' in txt, txt
    ok(f'panel chain preview · {txt.splitlines()[0][:80]}')
    htxt = view._variant_chain_preview_strip.text()
    assert '配方A' in htxt and ('A型' in htxt or '链' in htxt), htxt
    ok(f'HMI chain preview · {htxt[:80]}')

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
    assert dlg.findChild(QPlainTextEdit, 'recipeVariantChainPreviewStrip') is not None
    ok('recipe dialog preview strip present')
    # Select first recipe
    if dlg._recipe_list.count() >= 1:
        dlg._recipe_list.setCurrentRow(0)
        for _ in range(10):
            QCoreApplication.processEvents(); app.processEvents()
    bag = dlg.soft_preview_variant_prod_chain_page(project['recipes'][0])
    assert bag['variant'] == 'A型' and len(bag['steps']) >= 2, bag
    rtxt = dlg._variant_chain_preview.toPlainText()
    assert 'soft preview' in rtxt or '配方A' in rtxt or 'locate' in rtxt or '模板匹配' in rtxt, rtxt
    ok(f'recipe dialog preview · {rtxt.splitlines()[1][:80] if len(rtxt.splitlines())>1 else rtxt[:80]}')
    # B variant
    bag2 = dlg.soft_preview_variant_prod_chain_page(project['recipes'][1])
    assert bag2['variant'] == 'B型', bag2
    assert any('ocr' in str(s.get('op') or '').lower() or 'OCR' in str(s.get('step') or '') for s in bag2['steps']), bag2
    ok(f'B型 preview steps · {[s.get("op") for s in bag2["steps"]]}')

    print(f'\n=== {pass_n} passed, {fail_n} failed ===')
    return 0 if fail_n == 0 else 1

if __name__ == '__main__':
    rc = main()
    import os as _os
    _os._exit(rc)
