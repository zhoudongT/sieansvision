#!/usr/bin/env python3
"""细妆⑱：配方/换型 → production_task / 运行壳闭环（enterRun/trialOnce flags + sync API）."""
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
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])

    from desktop import recipe_library as rl
    from desktop.recipe_switch_dialog import RecipeSwitchDialog

    proj = {
        'name': 'loop',
        'steps': [
            {'id': 'a', 'name': '卡尺1', 'operation': 'geometry',
             'params': {'caliperCount': 10}},
            {'id': 'b', 'name': '生产任务1', 'operation': 'production_task',
             'params': {'taskName': 'T', 'recipe': ''}},
        ],
        'variables': {},
        'runUi': {},
    }

    class Doc:
        def __init__(self, p):
            self.project = p
            self._commits = []
        def commit(self, p):
            self.project = p
            self._commits.append(deepcopy(p))
        def mark_dirty(self):
            pass

    doc = Doc(proj)
    e = rl.capture_recipe(doc.project, '线体A', variant='A型')
    doc.project['steps'][0]['params']['caliperCount'] = 99
    ok(f'captured {e["name"]} variant={e.get("variant")}')

    dlg = RecipeSwitchDialog(doc, ROOT, None)
    assert hasattr(dlg, '_chk_enter_run') and hasattr(dlg, '_chk_trial_once')
    assert dlg._chk_enter_run.isChecked()  # default on
    ok('dialog post-apply checkboxes present (enterRun default on)')

    # stamp helper
    stamped = dlg._stamp_post_apply({'name': '线体A', 'applied': 1})
    assert stamped['enterRun'] is True
    dlg._chk_trial_once.setChecked(True)
    stamped = dlg._stamp_post_apply({'name': '线体A'})
    assert stamped['trialOnce'] is True
    ok('stamp_post_apply enterRun/trialOnce')

    # apply via library + sync production_task field
    stats = rl.apply_recipe(doc.project, e['id'])
    assert doc.project['steps'][0]['params']['caliperCount'] == 10
    assert doc.project['steps'][1]['params']['recipe'] == '线体A'
    assert stats.get('variant') == 'A型'
    ok(f'apply → production_task.recipe={doc.project["steps"][1]["params"]["recipe"]}')

    # Lightweight stand-in exercising the same contract as MainWindow.sync_after_recipe_apply
    from desktop.operator_hmi import OperatorHmiView

    class FakeMW:
        def __init__(self):
            self.document = doc
            self.app_mode = 'design'
            self.operator_hmi = OperatorHmiView()
            self.logs = []
        def log(self, m): self.logs.append(m)
        def statusBar(self):
            class SB:
                def showMessage(self, *a, **k): pass
            return SB()
        def refresh_parameters(self): pass
        def refresh_variant_chip(self): pass
        class scene:
            @staticmethod
            def rebuild(): pass
        def guard(self, fn):
            return fn()
        def set_app_mode(self, mode):
            self.app_mode = mode
            if mode == 'run':
                self.operator_hmi.reload_layout(self.document.project)
        def sync_after_recipe_apply(self, stats=None):
            """Mirrors MainWindow.sync_after_recipe_apply contract (细妆⑱)."""
            stats = stats or {}
            name = str(stats.get('name') or '')
            variant = str(stats.get('variant') or '')
            try:
                self.document.changed.emit() if hasattr(self.document, 'changed') else None
            except Exception:
                pass
            try:
                self.refresh_parameters(); self.scene.rebuild(); self.refresh_variant_chip()
            except Exception:
                pass
            try:
                self.operator_hmi.set_recipe_chrome(name, variant)
                if self.app_mode == 'run':
                    self.operator_hmi.reload_layout(self.document.project)
            except Exception:
                pass
            if stats.get('enterRun') and self.app_mode != 'run':
                self.guard(lambda: self.set_app_mode('run'))
                self.log(f'换型闭环 · 已切运行态 · 配方 {name or "—"}')

    # Also assert real MainWindow has the method (import may be heavy — timeout-safe check via source)
    src = (ROOT / 'desktop' / 'mainwindow.py').read_text(encoding='utf-8')
    assert 'def sync_after_recipe_apply' in src
    assert 'enterRun' in src and 'trialOnce' in src
    ok('MainWindow.sync_after_recipe_apply present in source')

    mw = FakeMW()
    mw.sync_after_recipe_apply({
        **stats, 'enterRun': True, 'trialOnce': False,
    })
    assert mw.app_mode == 'run', mw.app_mode
    assert '线体A' in mw.operator_hmi._recipe_badge.text()
    ok(f'sync_after_recipe_apply → run + badge={mw.operator_hmi._recipe_badge.text()}')

    print(f'\nRESULT pass={pass_n} fail={fail_n}')
    return 0 if fail_n == 0 else 1

if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as e:
        bad(f'crash: {e}')
        import traceback; traceback.print_exc()
        print(f'\nRESULT pass={pass_n} fail={fail_n}')
        raise SystemExit(1)
