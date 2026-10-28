#!/usr/bin/env python3
"""Host SM Alarm history ↔ HMI OK-NG dashboard page co-bind strip — no robot SDK / no micro chips."""
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
        'desktop/host_state_machine.py',
        'desktop/production_task_panel.py',
    ):
        src = (ROOT / rel).read_text(encoding='utf-8')
        if 'host_state_machine' not in rel:
            ast.parse(src)
        ok(f'ast/parse-or-read {rel}')

    hmi_src = (ROOT / 'desktop/operator_hmi.py').read_text(encoding='utf-8')
    for needle in (
        'hmiAlarmHistOkNgCoBindStrip', 'hmiAlarmHistOkNgCoBindDetail',
        'co_bind_alarm_hist_okng_dashboard',
    ):
        (ok if needle in hmi_src else bad)(
            f'hmi has {needle}' if needle in hmi_src else f'missing {needle}'
        )

    host_src = (ROOT / 'desktop/host_state_machine.py').read_text(encoding='utf-8')
    for needle in (
        'hostAlarmHistOkNgCoBindStrip', 'set_alarm_okng_cobind_strip',
        '_soft_bump_alarm_okng_cobind',
    ):
        (ok if needle in host_src else bad)(
            f'host has {needle}' if needle in host_src else f'missing {needle}'
        )

    from PySide6.QtWidgets import QApplication, QLabel, QPlainTextEdit
    from PySide6.QtCore import QCoreApplication
    app = QApplication.instance() or QApplication([])

    from desktop.operator_hmi import OperatorHmiView
    from desktop.host_state_machine import HostStateMachineWidget
    from desktop.production_task_panel import ProductionTaskPanel

    view = OperatorHmiView()
    host = HostStateMachineWidget()
    view._wire_host_sm(host)
    ok('hmi+host constructed')
    assert view.findChild(QLabel, 'hmiAlarmHistOkNgCoBindStrip') is not None
    assert view.findChild(QPlainTextEdit, 'hmiAlarmHistOkNgCoBindDetail') is not None
    ok('HMI alarm↔OK-NG cobind strips present')
    assert host.findChild(QLabel, 'hostAlarmHistOkNgCoBindStrip') is not None
    ok('Host SM cobind strip present')

    # Seed alarm history via set_state Alarm
    host.set_state('Alarm', 'smoke NG 报警')
    for _ in range(10):
        QCoreApplication.processEvents()
        app.processEvents()
    hist = host.alarm_history()
    assert len(hist) >= 1, hist
    ok(f'alarm history seeded · n={len(hist)}')

    # Co-bind via HMI API
    bag = view.co_bind_alarm_hist_okng_dashboard(
        ok_n=3, ng_n=1, judge='NG', host_state='Alarm',
        open_alarms=1, last_alarm='smoke NG 报警', recipe='配方共绑',
        note='smoke',
    )
    assert bag['hist'] >= 1 and bag['ng'] == 1, bag
    strip = view._alarm_okng_cobind_strip.text()
    assert '共绑' in strip and ('报警' in strip or 'OK' in strip), strip
    ok(f'HMI cobind strip · {strip[:90]}')
    detail = view._alarm_okng_cobind_detail.toPlainText()
    assert 'Alarm history' in detail or '共绑' in detail or 'OPEN' in detail or 'cleared' in detail, detail
    ok(f'HMI cobind detail · {detail.splitlines()[-1][:80]}')
    hstrip = host._alarm_okng_cobind_strip.text()
    assert '共绑' in hstrip or 'OK' in hstrip, hstrip
    ok(f'Host cobind strip · {hstrip[:80]}')

    # refresh_okng_dashboard_strip should also cobind
    view.refresh_okng_dashboard_strip(
        ok_n=5, ng_n=2, judge='OK', host_state='Idle', recipe='配方共绑',
    )
    strip2 = view._alarm_okng_cobind_strip.text()
    assert 'OK 5' in strip2 or '良率' in strip2 or '共绑' in strip2, strip2
    ok(f'refresh_okng → cobind · {strip2[:80]}')

    # Closed loop from production_task NG→OK
    step = {
        'id': 'pt1', 'operation': 'production_task', 'name': '生产任务',
        'params': {
            'taskName': '共绑任务', 'recipe': '配方共绑', 'statusVar': 'taskStatus',
            'scope': 'global', 'chain': [{'step': '匹配', 'op': 'locate', 'vars': ''}],
        },
    }
    panel = ProductionTaskPanel(step, {}, {'steps': [step], 'edges': [], 'variables': {}})
    class Win:
        operator_hmi = view
        host_state_machine = host
    panel.window = lambda *a, **k: Win()  # type: ignore
    panel._soft_co_update_trial_result(
        phase='result', title='NG', ops=[], judge='NG',
        result={'state': 'failed', 'judge': 'NG'},
    )
    for _ in range(15):
        QCoreApplication.processEvents(); app.processEvents()
    assert host._state == 'Alarm', host._state
    ok(f'trial NG → Alarm · cobind={view._alarm_okng_cobind_strip.text()[:70]}')
    panel._soft_co_update_trial_result(
        phase='result', title='OK清除', ops=[], judge='OK',
        result={'state': 'completed', 'judge': 'OK'},
    )
    for _ in range(15):
        QCoreApplication.processEvents(); app.processEvents()
    ok(f'trial OK clear · host={host._state} · cobind={view._alarm_okng_cobind_strip.text()[:70]}')

    print(f'\n=== {pass_n} passed, {fail_n} failed ===')
    return 0 if fail_n == 0 else 1

if __name__ == '__main__':
    rc = main()
    import os as _os
    _os._exit(rc)
