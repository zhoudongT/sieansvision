#!/usr/bin/env python3
"""production_task ▶试跑 → HMI page-chrome + OK-NG dashboard co-update — no robot SDK."""
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
        'desktop/production_task_panel.py',
        'desktop/operator_hmi.py',
    ):
        ast.parse((ROOT / rel).read_text(encoding='utf-8'))
        ok(f'ast/parse {rel}')

    prod = (ROOT / 'desktop/production_task_panel.py').read_text(encoding='utf-8')
    for needle in (
        'productionTaskTrialResultStrip', 'productionTaskTrialResultMeta',
        '_soft_co_update_trial_result', 'trial→result', 'okNgDashboard',
    ):
        (ok if needle in prod else bad)(
            f'panel has {needle}' if needle in prod else f'missing {needle}'
        )

    hmi = (ROOT / 'desktop/operator_hmi.py').read_text(encoding='utf-8')
    for needle in (
        'hmiTrialResultStrip', 'apply_trial_result_co_update',
    ):
        (ok if needle in hmi else bad)(
            f'hmi has {needle}' if needle in hmi else f'missing {needle}'
        )

    from PySide6.QtWidgets import QApplication, QPlainTextEdit, QLabel
    app = QApplication.instance() or QApplication([])
    from desktop.production_task_panel import ProductionTaskPanel
    from desktop.operator_hmi import OperatorHmiView

    step = {
        'id': 'pt1', 'operation': 'production_task', 'name': '生产任务',
        'params': {
            'taskName': '对位贴合任务1',
            'recipe': '配方A',
            'statusVar': 'taskStatus',
            'scope': 'global',
            'autoStart': False,
            'note': '',
            'chain': [
                {'step': '读取图像', 'op': '图像源', 'vars': ''},
                {'step': '模板匹配', 'op': 'locate', 'vars': ''},
                {'step': '发送上位机', 'op': 'send_data / format_data', 'vars': 'MoveX'},
            ],
        },
    }
    project = {'steps': [step], 'edges': [], 'variables': {}}
    panel = ProductionTaskPanel(step, {}, project)
    ok('ProductionTaskPanel constructed')

    assert isinstance(panel._prod_trial_result_strip, QPlainTextEdit)
    assert panel._prod_trial_result_strip.objectName() == 'productionTaskTrialResultStrip'
    ok('trial→result strip present')

    view = OperatorHmiView()
    assert view.findChild(QLabel, 'hmiTrialResultStrip') is not None
    ok('HMI trial result strip present')

    # Wire panel.window → fake host with operator_hmi
    class Host:
        operator_hmi = view
    # ProductionTaskPanel.window() returns Qt window; call co-update directly
    snap_t = panel._soft_co_update_trial_result(
        phase='trial', title='建议链并试跑',
        ops=[{'operation': 'locate', 'name': '模板匹配'}],
    )
    assert snap_t['hostState'] == 'Running', snap_t
    assert snap_t['okng'] in ('试跑中', '—') or snap_t.get('trial'), snap_t
    txt = panel._prod_trial_result_strip.toPlainText()
    assert 'TRIAL' in txt or 'trial' in txt.lower() or 'PHASE' in txt.upper() or '试跑' in txt, txt
    ok(f'trial phase strip · {txt.splitlines()[-1][:80]}')

    # Direct HMI co-update trial
    view.apply_trial_result_co_update(phase='trial', snapshot=snap_t)
    tr = view._trial_result_strip.text()
    assert 'TRIAL' in tr or '试跑' in tr, tr
    ok(f'HMI trial strip · {tr}')
    assert 'Running' in view._page_chrome_banner.text() or '试跑' in view._page_chrome_banner.text(), view._page_chrome_banner.text()
    ok(f'HMI page chrome trial · {view._page_chrome_banner.text()[:60]}')

    # Result phase co-update
    snap_r = panel._soft_co_update_trial_result(
        phase='result', title='试跑回填', ops=[{'operation': 'locate'}],
        judge='OK', result={'state': 'completed', 'judge': 'OK', 'elapsedMs': 12},
    )
    assert snap_r['okng'] == 'OK', snap_r
    assert snap_r['hostState'] == 'Idle', snap_r
    ok(f'result snap okng={snap_r["okng"]} host={snap_r["hostState"]}')

    view.apply_trial_result_co_update(
        phase='result', snapshot=snap_r, judge='OK',
        result={'state': 'completed', 'elapsedMs': 12},
    )
    tr2 = view._trial_result_strip.text()
    assert 'RESULT' in tr2 or 'OK' in tr2, tr2
    ok(f'HMI result strip · {tr2}')
    dash = view._okng_dashboard_strip.text()
    assert 'OK' in dash or '看板' in dash, dash
    ok(f'OK-NG dashboard co-updated · {dash[:80]}')

    # project softOkNg bumped
    soft = project.get('softOkNg') or {}
    assert int(soft.get('ok') or 0) >= 1, soft
    ok(f'project.softOkNg bumped · {soft}')

    print(f'\n=== {pass_n} passed, {fail_n} failed ===')
    return 0 if fail_n == 0 else 1

if __name__ == '__main__':
    rc = main()
    import os as _os
    _os._exit(rc)
