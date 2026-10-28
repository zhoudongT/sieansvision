#!/usr/bin/env python3
"""Recipe chrome lock ↔ production_task statusVar writeback closed-loop page — no robot SDK."""
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
        'desktop/host_state_machine.py',
    ):
        src = (ROOT / rel).read_text(encoding='utf-8')
        if rel != 'desktop/host_state_machine.py':
            ast.parse(src)
        ok(f'ast/parse-or-read {rel}')

    rs = (ROOT / 'desktop/recipe_switch_dialog.py').read_text(encoding='utf-8')
    for needle in (
        'recipeChromeLockStatusVarLoopStrip', 'recipeChromeLockStatusVarLoopBtn',
        'soft_chrome_lock_statusvar_writeback_loop',
    ):
        (ok if needle in rs else bad)(f'recipe has {needle}' if needle in rs else f'missing {needle}')

    prod = (ROOT / 'desktop/production_task_panel.py').read_text(encoding='utf-8')
    for needle in (
        'productionTaskChromeLockStatusVarLoopStrip',
        'soft_chrome_lock_statusvar_writeback_loop',
    ):
        (ok if needle in prod else bad)(f'panel has {needle}' if needle in prod else f'missing {needle}')

    hmi_src = (ROOT / 'desktop/operator_hmi.py').read_text(encoding='utf-8')
    for needle in (
        'hmiChromeLockStatusVarLoopStrip', 'apply_chrome_lock_statusvar_writeback_loop',
    ):
        (ok if needle in hmi_src else bad)(f'hmi has {needle}' if needle in hmi_src else f'missing {needle}')

    host_src = (ROOT / 'desktop/host_state_machine.py').read_text(encoding='utf-8')
    for needle in (
        'hostChromeLockStatusVarLoopStrip', 'set_chrome_lock_statusvar_loop_strip',
    ):
        (ok if needle in host_src else bad)(f'host has {needle}' if needle in host_src else f'missing {needle}')

    from PySide6.QtWidgets import QApplication, QWidget
    app = QApplication.instance() or QApplication([])

    from desktop.recipe_switch_dialog import RecipeSwitchDialog
    from desktop.production_task_panel import ProductionTaskPanel
    from desktop.operator_hmi import OperatorHmiView
    from desktop.host_state_machine import HostStateMachineWidget

    class Doc:
        def __init__(self, project):
            self.project = project
        def mark_dirty(self):
            pass

    project = {
        'name': 'chrome-lock-statusvar-smoke',
        'activeRecipeName': '配方锁环A',
        'activeRecipeVariant': 'V1',
        'steps': [{
            'id': 'pt1', 'operation': 'production_task',
            'params': {
                'taskName': '产线任务1', 'recipe': '配方锁环A',
                'statusVar': 'taskStatus', 'scope': 'global',
                'autoStart': False,
                'chain': [
                    {'step': '读图', 'op': '图像源'},
                    {'step': '判定', 'op': 'judge'},
                ],
            },
        }],
        'variables': {'global': {'taskStatus': 'ready'}, 'flow': {}},
        'recipes': [],
    }
    doc = Doc(project)

    class HostWin(QWidget):
        def __init__(self):
            super().__init__()
            self.operator_hmi = None
            self.host_state_machine = None
            self.host_sm = None
            self.document = doc
            self._smoke_panel = None

        def findChildren(self, typ, *a, **k):
            try:
                if typ is ProductionTaskPanel or (
                    isinstance(typ, type) and issubclass(ProductionTaskPanel, typ)
                ):
                    if self._smoke_panel is not None:
                        return [self._smoke_panel]
            except Exception:
                pass
            return list(super().findChildren(typ, *a, **k) or [])

    win = HostWin()
    host = HostStateMachineWidget(parent=win)
    hmi = OperatorHmiView(parent=win)
    win.host_state_machine = host
    win.host_sm = host
    win.operator_hmi = hmi
    try:
        hmi._host_sm = host
    except Exception:
        pass

    step = project['steps'][0]
    panel = ProductionTaskPanel(step, {'name': 'production_task'}, project, parent=win)
    panel.setObjectName('smokeProdPanel')
    win._smoke_panel = panel
    panel.show()

    # RecipeSwitchDialog(document, root, parent=None)
    dlg = RecipeSwitchDialog(doc, str(ROOT), win)

    bag = dlg.soft_chrome_lock_statusvar_writeback_loop(
        demo=True, recipe='配方锁环A', variant='V1', enter_run=True,
    )
    phases = bag.get('phases') or []
    wb = bag.get('writeback') or {}
    if len(phases) == 2 and phases[0].get('locked') and not phases[1].get('locked'):
        ok(f'demo phases lock→unlock: {[p.get("status") for p in phases]}')
    else:
        bad(f'phases unexpected: {phases}')

    if wb.get('global.taskStatus') in ('ready', 'running', 'switching'):
        ok(f'statusVar writeback={wb.get("global.taskStatus")} keys={list(wb)[:5]}')
    else:
        # may use last phase running
        if any(str(v) in ('ready', 'running', 'switching') for v in wb.values()):
            ok(f'statusVar writeback values ok: {wb}')
        else:
            bad(f'writeback missing status: {wb}')

    gbag = (project.get('variables') or {}).get('global') or {}
    if gbag.get('taskStatus') in ('ready', 'running', 'switching'):
        ok(f'project variables.global.taskStatus={gbag.get("taskStatus")}')
    else:
        bad(f'project var not written: {gbag}')

    strip = getattr(dlg, '_chrome_lock_statusvar_loop', None)
    txt = strip.toPlainText() if strip is not None else ''
    if 'statusVar' in txt or 'chrome lock' in txt.lower() or '页铬锁' in txt:
        ok('recipe loop strip filled')
    else:
        bad(f'recipe strip empty: {txt[:120]!r}')

    hmi_lab = getattr(hmi, '_chrome_lock_statusvar_loop_strip', None)
    if hmi_lab is not None and ('statusVar' in hmi_lab.text() or '页铬锁' in hmi_lab.text()):
        ok(f'hmi loop strip: {hmi_lab.text()[:90]}')
    else:
        bad(f'hmi loop strip missing: {getattr(hmi_lab, "text", lambda: None)()!r}')

    # Direct panel path
    pbag = panel.soft_chrome_lock_statusvar_writeback_loop(
        locked=True, recipe='配方锁环A', status='switching', note='smoke-lock',
    )
    if pbag.get('status') == 'switching' and pbag.get('locked'):
        ok(f'panel lock writeback status=switching')
    else:
        bad(f'panel lock unexpected: {pbag}')
    pbag2 = panel.soft_chrome_lock_statusvar_writeback_loop(
        locked=False, recipe='配方锁环A', status='running', host_state='Running', note='smoke-unlock',
    )
    if pbag2.get('status') == 'running' and not pbag2.get('locked'):
        ok(f'panel unlock writeback status=running')
    else:
        bad(f'panel unlock unexpected: {pbag2}')

    print(f'\nRESULT {pass_n} pass / {fail_n} fail')
    return 0 if fail_n == 0 else 1

if __name__ == '__main__':
    sys.exit(main())
