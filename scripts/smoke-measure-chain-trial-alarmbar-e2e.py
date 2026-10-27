#!/usr/bin/env python3
"""细妆⑲：测量链一键换型→试跑入口 + Host SM Alarm↔固定栏色联动."""
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
    from PySide6.QtWidgets import QApplication, QMessageBox, QPushButton
    app = QApplication.instance() or QApplication([])
    QMessageBox.information = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
    QMessageBox.warning = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
    QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)

    from desktop.operator_hmi import OperatorHmiView
    from desktop.run_ui_designer import default_host_run_ui

    hmi = OperatorHmiView()
    proj = {'name': 'alarm-bar', 'runUi': default_host_run_ui(), 'steps': []}
    fb = proj['runUi'].setdefault('fixedBars', {})
    fb.update(top=True, bottom=True, left=True, right=True,
              showRunStatus=True, showOkNg=True)
    hmi.reload_layout(proj)
    hmi.update_fixed_bar_live(run_status='运行中', okng='OK')
    tip_ok = hmi._fix_top.text()
    assert '⚠' not in tip_ok
    ok(f'OK state tip (no alarm): {tip_ok[:60]}')

    hmi._paint_machine_chrome('Alarm')
    tip_al = hmi._fix_top.text()
    ss = hmi._fix_top.styleSheet()
    assert '⚠' in tip_al or '报警' in tip_al, tip_al
    assert '#e35d6a' in ss or '#3a1c1c' in ss, ss
    ok(f'Alarm paints fixed top: {tip_al[:70]}')

    hmi._paint_machine_chrome('Idle')
    assert getattr(hmi, '_live_host_alarm', None) is False
    ok('Idle clears alarm flag')

    from desktop.recipe_switch_dialog import RecipeSwitchDialog

    class Doc:
        def __init__(self):
            self.project = {
                'name': 'm', 'steps': [], 'variables': {}, 'recipes': [],
                'runUi': {},
            }
        def commit(self, p): self.project = p
        def mark_dirty(self): pass

    doc = Doc()
    dlg = RecipeSwitchDialog(doc, ROOT, None)
    assert hasattr(dlg, '_load_measure_chain_trial')
    assert hasattr(dlg, 'post_apply_flags')
    names = [b.objectName() for b in dlg.findChildren(QPushButton)]
    assert 'recipeMeasureChainTrialBtn' in names, names
    ok('recipe dialog has 测量链 · 换型→试跑 button')

    flags = dlg.post_apply_flags()
    assert 'enterRun' in flags and 'trialOnce' in flags
    ok(f'post_apply_flags → {flags}')

    src = (ROOT / 'desktop/mainwindow.py').read_text(encoding='utf-8')
    assert 'def open_measure_chain_trial' in src
    assert '一键「换型→试跑」·测量链' in src
    assert 'def highlight_variables_keys' in src
    ok('MainWindow open_measure_chain_trial + highlight_variables_keys + menu')

    assert (ROOT / 'projects/open-and-run-caliper-measure.sieans').is_file()
    assert (ROOT / 'projects/open-and-run-measure.sieans').is_file()
    ok('open-and-run measure chain templates present')

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
