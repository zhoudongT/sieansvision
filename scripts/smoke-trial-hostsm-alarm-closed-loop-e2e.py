#!/usr/bin/env python3
"""production_task trial→result → Host SM liaison / Alarm clear closed loop — page chrome; no robot SDK."""
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
        'desktop/host_state_machine.py',
    ):
        src = (ROOT / rel).read_text(encoding='utf-8')
        if rel.endswith('.py') and 'host_state_machine' not in rel:
            ast.parse(src)
        ok(f'ast/parse-or-read {rel}')

    prod = (ROOT / 'desktop/production_task_panel.py').read_text(encoding='utf-8')
    for needle in (
        'productionTaskHostSmClosedLoopStrip', 'productionTaskHostSmClosedLoopMeta',
        '_soft_host_sm_liaison_alarm_closed_loop', 'TRIAL_ALARM', 'ALARM_CLEAR',
    ):
        (ok if needle in prod else bad)(
            f'panel has {needle}' if needle in prod else f'missing {needle}'
        )

    hmi = (ROOT / 'desktop/operator_hmi.py').read_text(encoding='utf-8')
    for needle in (
        'hmiHostSmClosedLoopStrip', 'apply_host_sm_alarm_closed_loop',
    ):
        (ok if needle in hmi else bad)(
            f'hmi has {needle}' if needle in hmi else f'missing {needle}'
        )

    from PySide6.QtWidgets import QApplication, QPlainTextEdit, QLabel
    from PySide6.QtCore import QCoreApplication
    app = QApplication.instance() or QApplication([])

    from desktop.production_task_panel import ProductionTaskPanel
    from desktop.operator_hmi import OperatorHmiView
    from desktop.host_state_machine import HostStateMachineWidget

    step = {
        'id': 'pt1', 'operation': 'production_task', 'name': '生产任务',
        'params': {
            'taskName': '对位贴合任务1',
            'recipe': '配方闭环',
            'statusVar': 'taskStatus',
            'scope': 'global',
            'autoStart': False,
            'note': '',
            'chain': [
                {'step': '读取图像', 'op': '图像源', 'vars': ''},
                {'step': '模板匹配', 'op': 'locate', 'vars': ''},
            ],
        },
    }
    project = {'steps': [step], 'edges': [], 'variables': {}}
    panel = ProductionTaskPanel(step, {}, project)
    ok('ProductionTaskPanel constructed')
    assert panel.findChild(QPlainTextEdit, 'productionTaskHostSmClosedLoopStrip') is not None
    ok('Host SM closed-loop strip present')

    view = OperatorHmiView()
    host = HostStateMachineWidget()
    view._wire_host_sm(host)
    assert view.findChild(QLabel, 'hmiHostSmClosedLoopStrip') is not None
    ok('HMI Host SM closed-loop strip present')

    # Fake window() so panel finds hmi/host
    class Win:
        operator_hmi = view
        host_state_machine = host
    panel.window = lambda *a, **k: Win()  # type: ignore

    # NG path → Alarm + liaison
    snap_ng = panel._soft_co_update_trial_result(
        phase='result', title='试跑NG', ops=[{'operation': 'locate'}],
        judge='NG', result={'state': 'failed', 'judge': 'NG'},
    )
    assert snap_ng['okng'] == 'NG', snap_ng
    assert host._state == 'Alarm', host._state
    ok(f'NG → host Alarm · {host._state}')
    lia = [e.get('code') for e in host.liaison_events()]
    assert 'TRIAL_ALARM' in lia or any('ALARM' in str(c) for c in lia), lia
    ok(f'liaison has TRIAL_ALARM · {lia[-3:]}')
    strip = panel._prod_hostsm_loop_strip.toPlainText()
    assert 'TRIAL_ALARM' in strip or 'Alarm' in strip or 'NG' in strip, strip
    ok(f'panel closed-loop strip · {strip.splitlines()[-1][:80]}')
    hstrip = view._hostsm_closed_loop_strip.text()
    assert 'ALARM' in hstrip or '闭环' in hstrip, hstrip
    ok(f'HMI closed-loop strip · {hstrip[:80]}')

    # OK path → clear Alarm closed loop
    snap_ok = panel._soft_co_update_trial_result(
        phase='result', title='试跑OK清除', ops=[{'operation': 'locate'}],
        judge='OK', result={'state': 'completed', 'judge': 'OK'},
    )
    assert snap_ok['okng'] == 'OK', snap_ok
    for _ in range(20):
        QCoreApplication.processEvents()
        app.processEvents()
    assert host._state in ('Idle', 'Running'), host._state
    ok(f'OK → host cleared · {host._state}')
    lia2 = [e.get('code') for e in host.liaison_events()]
    assert 'ALARM_CLEAR' in lia2 or 'TRIAL_OK' in lia2, lia2
    ok(f'liaison clear/ok · {lia2[-4:]}')
    strip2 = panel._prod_hostsm_loop_strip.toPlainText()
    assert '闭环' in strip2 or 'Clear' in strip2 or 'OK' in strip2 or 'ALARM_CLEAR' in strip2, strip2
    ok(f'closed-loop OK strip · {strip2.splitlines()[-1][:80]}')
    meta = panel._prod_hostsm_loop_meta.text()
    assert '已清除' in meta or '空闲' in meta or 'OK' in meta, meta
    ok(f'closed-loop meta · {meta[:80]}')

    # Direct HMI API
    view.apply_host_sm_alarm_closed_loop(
        phase='result', judge='OK', snapshot=snap_ok,
        loop={'driven': True, 'liaison': ['ALARM_CLEAR'], 'cleared': True, 'host': 'Idle'},
    )
    assert 'CLOSED' in view._hostsm_closed_loop_strip.text() or '闭环' in view._hostsm_closed_loop_strip.text()
    ok(f'HMI apply closed-loop · {view._hostsm_closed_loop_strip.text()[:70]}')

    print(f'\n=== {pass_n} passed, {fail_n} failed ===')
    return 0 if fail_n == 0 else 1

if __name__ == '__main__':
    rc = main()
    import os as _os
    _os._exit(rc)
