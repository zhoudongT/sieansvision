#!/usr/bin/env python3
"""细妆⑳：Variables commAccept 簇滚动 · Alarm清除恢复 · 变体试跑 · 试跑回填."""
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
    from PySide6.QtWidgets import QApplication, QMessageBox, QWidget, QCheckBox
    from PySide6.QtCore import QObject, Signal
    app = QApplication.instance() or QApplication([])
    QMessageBox.information = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
    QMessageBox.warning = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)

    # --- Variables commAccept cluster scroll ---
    from desktop.variables_dialog import VariablesDialog
    class Doc(QObject):
        changed = Signal()
        def __init__(self):
            super().__init__()
            self.project = {
                'id': 't', 'name': 't', 'steps': [],
                'variables': {
                    'other': 1,
                    'commAcceptPass': 2,
                    'commAcceptFail': 0,
                    'commAcceptOverall': 'PASS',
                    'zzz': 9,
                },
                'variableTypes': {},
            }
        def mark_dirty(self): pass
    class Backend:
        def request(self, *a, **k): return 1
        result = type('S', (), {'connect': staticmethod(lambda *a, **k: None)})()
        error = type('S', (), {'connect': staticmethod(lambda *a, **k: None)})()
    dlg = VariablesDialog(Doc(), Backend(), None)
    dlg.mode.setCurrentIndex(0)
    # seed runtime draft so render shows flow vars
    dlg.runtime_draft = {
        'flow': dict(dlg.document.project['variables']),
        'global': {},
        'modules': {},
        'globalTypes': {},
    }
    dlg.snapshot = dict(dlg.runtime_draft)
    dlg.render()
    keys = [f'flow.{k}' for k in ('other', 'commAcceptPass', 'commAcceptFail', 'commAcceptOverall', 'zzz')]
    dlg.highlight_written_keys(keys, duration_ms=800)
    msg = dlg.message.text()
    assert 'commAccept' in msg, msg
    ok(f'highlight scrolls to commAccept cluster: {msg}')

    # --- Alarm clear restore pulse ---
    from desktop.operator_hmi import OperatorHmiView
    from desktop.run_ui_designer import default_host_run_ui
    hmi = OperatorHmiView()
    proj = {
        'name': 'alarm-pulse',
        'runUi': default_host_run_ui(),
        'steps': [], 'recipes': [],
    }
    fb = proj['runUi'].setdefault('fixedBars', {})
    fb.update(top=True, bottom=True, left=True, right=True,
              showRunStatus=True, showOkNg=True)
    hmi.reload_layout(proj)
    assert hasattr(hmi, '_pulse_alarm_cleared')
    hmi._paint_machine_chrome('Alarm')
    assert hmi._alarm_was_on is True
    ok('Alarm paints _alarm_was_on')
    hmi._paint_machine_chrome('Idle')
    assert hmi._alarm_was_on is False
    # fixed top should briefly show 清除 tip (or already settling)
    tip = hmi._fix_top.text() if hmi._fix_top else ''
    assert ('清除' in tip) or (not hmi._live_host_alarm), tip
    ok(f'Alarm→Idle restore tip/edge: {tip[:60]}')

    # --- trial backfill ---
    hmi.set_recipe_chrome('测量链', 'A型')
    hmi.set_trial_backfill_pending(True)
    assert hmi._pending_trial_backfill
    # fake a stats panel history
    class FakePanel:
        def ok_history(self): return [True]
        def ok_count(self): return 1
        def ng_count(self): return 0
        def elapsed_history(self): return [42.0]
        def gate_key(self): return None
        def set_gate_key(self, *a, **k): pass
        def set_host_state_mirror(self, *a, **k): pass
    hmi._stats_panels = [FakePanel()]
    assert hmi.backfill_after_trial({'state': 'completed', 'elapsedMs': 42}) is True
    assert hmi._pending_trial_backfill is False
    tip = hmi._recipe_badge.toolTip() if hmi._recipe_badge else ''
    assert '试跑回填' in tip and 'OK' in tip, tip
    ok(f'trial backfill tip: {tip}')

    # --- variant trialOnce signature ---
    import inspect
    from desktop.mainwindow import MainWindow
    sig = inspect.signature(MainWindow.apply_variant_quick)
    assert 'trial_once' in sig.parameters
    ok('apply_variant_quick(trial_once=) present')

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
