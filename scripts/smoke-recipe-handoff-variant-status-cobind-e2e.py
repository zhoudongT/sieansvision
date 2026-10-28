#!/usr/bin/env python3
"""Recipe lock handoff → production_task statusVar + variant page co-bind — no robot SDK / no micro chips."""
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
        '_co_bind_production_variant_status', 'status_var', 'activeRecipeVariant',
        'soft_handoff_idle_running',
    ):
        (ok if needle in rs else bad)(
            f'recipe_switch has {needle}' if needle in rs else f'missing {needle}'
        )

    prod = (ROOT / 'desktop/production_task_panel.py').read_text(encoding='utf-8')
    for needle in (
        'soft_co_bind_variant_status_page_chrome',
        'productionTaskVariantStatusCoBindStrip',
        'productionTaskVariantStatusCoBindMeta',
    ):
        (ok if needle in prod else bad)(
            f'panel has {needle}' if needle in prod else f'missing {needle}'
        )

    hmi_src = (ROOT / 'desktop/operator_hmi.py').read_text(encoding='utf-8')
    for needle in (
        'co_bind_variant_status_page_chrome', 'hmiVariantStatusCoBindStrip',
        '_pending_handoff_cobind',
    ):
        (ok if needle in hmi_src else bad)(
            f'hmi has {needle}' if needle in hmi_src else f'missing {needle}'
        )

    from PySide6.QtWidgets import QApplication, QPlainTextEdit, QLabel
    from PySide6.QtCore import QCoreApplication
    app = QApplication.instance() or QApplication([])

    from desktop.production_task_panel import ProductionTaskPanel
    from desktop.operator_hmi import OperatorHmiView
    from desktop.recipe_switch_dialog import RecipeSwitchDialog

    step = {
        'id': 'pt1', 'operation': 'production_task', 'name': '生产任务',
        'params': {
            'taskName': '换型共绑任务',
            'recipe': '配方A',
            'statusVar': 'lineStatus',
            'scope': 'global',
            'autoStart': False,
            'chain': [{'step': '读取图像', 'op': '图像源', 'vars': ''}],
        },
    }
    project = {
        'name': 'cobind-smoke',
        'steps': [step, {'id': 's1', 'operation': 'image_source', 'name': '图像源', 'params': {}}],
        'edges': [],
        'variables': {'global': {}, 'flow': {}},
        'recipes': [
            {
                'id': 'r1', 'name': '配方A', 'variant': 'A型',
                'modules': [
                    {'operation': 'image_source', 'name': '图像源', 'params': {'path': 'a.png'}},
                ],
            }
        ],
        'activeRecipeVariant': '',
    }
    panel = ProductionTaskPanel(step, {}, project)
    view = OperatorHmiView()
    ok('panel+hmi constructed')
    assert panel.findChild(QPlainTextEdit, 'productionTaskVariantStatusCoBindStrip') is not None
    assert view.findChild(QLabel, 'hmiVariantStatusCoBindStrip') is not None
    ok('variant/statusVar co-bind strips present')

    class Win:
        operator_hmi = view
        def findChildren(self, typ):
            return [panel]
    panel.window = lambda *a, **k: Win()  # type: ignore

    snap = panel.soft_co_bind_variant_status_page_chrome(
        recipe='配方A', variant='A型', status_var='lineStatus', scope='global',
        host_state='Running', note='换型手递',
    )
    assert snap['variant'] == 'A型', snap
    assert snap['statusVar'] == 'lineStatus', snap
    assert project.get('activeRecipeVariant') == 'A型', project
    txt = panel._prod_variant_status_strip.toPlainText()
    assert 'lineStatus' in txt and 'A型' in txt, txt
    ok(f'panel co-bind strip · {txt.splitlines()[0][:80]}')
    htxt = view._variant_status_cobind_strip.text()
    assert 'lineStatus' in htxt and ('A型' in htxt or '变体' in htxt), htxt
    ok(f'HMI co-bind strip · {htxt[:80]}')
    ban = view._page_chrome_banner.text()
    assert '配方A' in ban or 'lineStatus' in ban or '共绑' in ban or 'A型' in ban, ban
    ok(f'page chrome banner · {ban[:70]}')

    # soft_handoff with cobind kwargs
    view.lock_page_chrome_for_recipe_switch(True, recipe='配方A')
    view.soft_handoff_idle_running(
        recipe='配方A', to_running=True, note='smoke',
        variant='A型', status_var='lineStatus', scope='global',
    )
    for _ in range(30):
        QCoreApplication.processEvents()
        app.processEvents()
        from time import sleep
        sleep(0.02)
    ok(f'handoff cobind · host={getattr(view, "_host_state", "?")} · strip={view._variant_status_cobind_strip.text()[:60]}')

    # RecipeSwitchDialog handoff path
    class Doc:
        def __init__(self):
            self.project = project
            self._commits = []
        def commit(self, p):
            self.project = p
            self._commits.append(p)

    from PySide6.QtWidgets import QWidget
    class HostWin(QWidget):
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

    doc = Doc()
    try:
        host_win = HostWin()
        dlg = RecipeSwitchDialog(doc, str(ROOT), host_win)
        assert hasattr(dlg, '_co_bind_production_variant_status')
        dlg._handoff_after_recipe({
            'name': '配方A', 'variant': 'A型', 'enterRun': True, 'trialOnce': False,
            'applied': 1, 'skipped': 0,
        })
        rail = dlg._chrome_lock_rail.text()
        assert '共绑' in rail or 'lineStatus' in rail or '手递' in rail, rail
        ok(f'recipe handoff rail · {rail[:80]}')
        for _ in range(30):
            QCoreApplication.processEvents()
            app.processEvents()
            from time import sleep
            sleep(0.02)
        ok(f'after handoff variant={project.get("activeRecipeVariant")} · hmi={view._variant_status_cobind_strip.text()[:60]}')
    except Exception as e:
        bad(f'RecipeSwitchDialog handoff: {e}')

    print(f'\n=== {pass_n} passed, {fail_n} failed ===')
    return 0 if fail_n == 0 else 1

if __name__ == '__main__':
    rc = main()
    import os as _os
    _os._exit(rc)
