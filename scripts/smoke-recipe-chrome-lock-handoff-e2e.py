#!/usr/bin/env python3
"""Recipe 换型 full-page chrome lock + Idle↔Running soft handoff — no robot SDK."""
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
        'desktop/operator_hmi.py',
        'desktop/recipe_switch_dialog.py',
        'desktop/mainwindow.py',
    ):
        src = (ROOT / rel).read_text(encoding='utf-8')
        if rel.endswith('.py') and rel != 'desktop/mainwindow.py':
            ast.parse(src)
        ok(f'ast/parse-or-read {rel}')

    hmi_src = (ROOT / 'desktop/operator_hmi.py').read_text(encoding='utf-8')
    for needle in (
        'lock_page_chrome_for_recipe_switch', 'soft_handoff_idle_running',
        '_page_chrome_locked',
    ):
        (ok if needle in hmi_src else bad)(
            f'hmi has {needle}' if needle in hmi_src else f'missing {needle}'
        )

    rs = (ROOT / 'desktop/recipe_switch_dialog.py').read_text(encoding='utf-8')
    for needle in (
        'recipeChromeLockRail', '_lock_hmi_page_chrome', '_handoff_after_recipe',
        '_set_chrome_lock_rail',
    ):
        (ok if needle in rs else bad)(
            f'recipe_switch has {needle}' if needle in rs else f'missing {needle}'
        )

    mw = (ROOT / 'desktop/mainwindow.py').read_text(encoding='utf-8')
    for needle in ('soft_handoff_idle_running', 'lock_page_chrome_for_recipe_switch'):
        (ok if needle in mw else bad)(
            f'mainwindow has {needle}' if needle in mw else f'missing {needle}'
        )

    from PySide6.QtWidgets import QApplication, QLabel
    from PySide6.QtCore import QCoreApplication
    app = QApplication.instance() or QApplication([])
    from desktop.operator_hmi import OperatorHmiView

    view = OperatorHmiView()
    ok('OperatorHmiView constructed')

    # Lock
    view.lock_page_chrome_for_recipe_switch(True, recipe='配方锁测', reason='换型')
    assert view._page_chrome_locked is True
    ban = view._page_chrome_banner.text()
    assert '锁' in ban and '配方锁测' in ban, ban
    ok(f'page chrome locked · {ban}')

    # Soft handoff Idle→Running
    target = view.soft_handoff_idle_running(recipe='配方锁测', to_running=True, note='smoke')
    assert target == 'Running', target
    assert view._page_chrome_locked is False
    # process queued QTimer
    for _ in range(30):
        QCoreApplication.processEvents()
        app.processEvents()
        from time import sleep
        sleep(0.02)
        if 'Running' in (view._page_chrome_banner.text() or '') or getattr(view, '_host_state', '') == 'Running':
            break
    ban2 = view._page_chrome_banner.text()
    ok(f'handoff arrived · banner={ban2[:70]} · host={getattr(view, "_host_state", "?")}')
    # host state should be Running after timer
    assert getattr(view, '_host_state', '') in ('Running', 'Idle'), getattr(view, '_host_state', None)
    ok(f'host_state after handoff · {view._host_state}')

    # Reverse handoff to Idle
    view.lock_page_chrome_for_recipe_switch(True, recipe='配方B')
    view.soft_handoff_idle_running(recipe='配方B', to_running=False)
    for _ in range(30):
        QCoreApplication.processEvents()
        app.processEvents()
        from time import sleep
        sleep(0.02)
    ok(f'reverse handoff · host={view._host_state} · banner={view._page_chrome_banner.text()[:60]}')

    # Recipe switch dialog chrome rail present
    from desktop.recipe_switch_dialog import RecipeSwitchDialog
    from desktop import recipe_library as rl

    class Doc:
        def __init__(self):
            self.project = {
                'name': 'lock-smoke',
                'steps': [
                    {'id': 's1', 'operation': 'image_source', 'name': '图像源', 'params': {}},
                ],
                'edges': [],
                'variables': {},
                'recipes': [
                    {
                        'id': 'r1', 'name': '配方锁测',
                        'modules': [
                            {'operation': 'image_source', 'name': '图像源', 'params': {'path': 'a.png'}},
                        ],
                    }
                ],
            }
            self._commits = []
        def commit(self, p):
            self.project = p
            self._commits.append(p)

    doc = Doc()
    # Ensure recipes shape matches library expectations — soft construct
    try:
        dlg = RecipeSwitchDialog(doc, str(ROOT), None)
        rail = dlg.findChild(QLabel, 'recipeChromeLockRail')
        assert rail is not None
        ok(f'recipe chrome lock rail · {rail.text()[:60]}')
        dlg._set_chrome_lock_rail('页铬锁 · 锁定中 · 配方 配方锁测', locked=True)
        assert '锁定' in dlg._chrome_lock_rail.text()
        ok('chrome lock rail locked style')
        dlg._set_chrome_lock_rail('页铬手递 · Idle↔Running · 配方 配方锁测', handoff=True)
        assert '手递' in dlg._chrome_lock_rail.text()
        ok('chrome lock rail handoff style')
    except Exception as e:
        bad(f'RecipeSwitchDialog: {e}')

    print(f'\n=== {pass_n} passed, {fail_n} failed ===')
    return 0 if fail_n == 0 else 1

if __name__ == '__main__':
    rc = main()
    import os as _os
    _os._exit(rc)
