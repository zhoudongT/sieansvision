#!/usr/bin/env python3
"""Alarm hist export/filter ↔ OK-NG sequence page co-bind — no robot SDK / no micro chips."""
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
    ):
        src = (ROOT / rel).read_text(encoding='utf-8')
        if rel != 'desktop/host_state_machine.py':
            ast.parse(src)
        ok(f'ast/parse-or-read {rel}')

    hmi_src = (ROOT / 'desktop/operator_hmi.py').read_text(encoding='utf-8')
    for needle in (
        'hmiAlarmHistOkNgSeqCoBindStrip', 'hmiAlarmHistOkNgSeqCoBindDetail',
        'co_bind_alarm_hist_export_filter_okng_sequence',
    ):
        (ok if needle in hmi_src else bad)(f'hmi has {needle}' if needle in hmi_src else f'missing {needle}')

    host_src = (ROOT / 'desktop/host_state_machine.py').read_text(encoding='utf-8')
    for needle in (
        'hostAlarmHistOkNgSeqCoBindStrip', 'set_alarm_okng_seq_cobind_strip',
        '_soft_bump_alarm_hist_okng_seq_cobind',
    ):
        (ok if needle in host_src else bad)(f'host has {needle}' if needle in host_src else f'missing {needle}')

    from PySide6.QtWidgets import QApplication, QLabel, QPlainTextEdit
    from PySide6.QtCore import QCoreApplication
    app = QApplication.instance() or QApplication([])

    from desktop.operator_hmi import OperatorHmiView
    from desktop.host_state_machine import HostStateMachineWidget

    view = OperatorHmiView()
    host = HostStateMachineWidget()
    view._wire_host_sm(host)
    host._operator_hmi = view
    ok('hmi+host constructed')
    assert view.findChild(QLabel, 'hmiAlarmHistOkNgSeqCoBindStrip') is not None
    assert view.findChild(QPlainTextEdit, 'hmiAlarmHistOkNgSeqCoBindDetail') is not None
    assert host.findChild(QLabel, 'hostAlarmHistOkNgSeqCoBindStrip') is not None
    ok('alarm↔OK-NG seq cobind strips present')

    host.set_state('Alarm', 'smoke filter NG 报警A')
    host.set_state('Idle', 'clear soft')
    try:
        host._clear_alarm()
    except Exception:
        pass
    host.set_state('Alarm', 'smoke filter 联调B')
    for _ in range(12):
        QCoreApplication.processEvents(); app.processEvents()
    hist = host.alarm_history()
    assert len(hist) >= 1, hist
    ok(f'alarm history seeded · n={len(hist)}')

    host._alarm_filter.setText('联调')
    for _ in range(8):
        QCoreApplication.processEvents(); app.processEvents()
    hstrip = host._alarm_okng_seq_cobind_strip.text()
    assert '筛选' in hstrip or '序列' in hstrip or '共绑' in hstrip or '显示' in hstrip, hstrip
    ok(f'filter bump host seq · {hstrip[:90]}')
    vstrip = view._alarm_okng_seq_cobind_strip.text()
    assert '序列' in vstrip or '共绑' in vstrip or '筛选' in vstrip or '报警' in vstrip, vstrip
    ok(f'filter bump HMI seq · {vstrip[:90]}')

    host._alarm_filter.setText('')
    for _ in range(5):
        QCoreApplication.processEvents(); app.processEvents()
    host.set_production_snapshot(4, 1, host_state='Idle')
    host.export_alarm_history_clipboard()
    for _ in range(8):
        QCoreApplication.processEvents(); app.processEvents()
    hstrip2 = host._alarm_okng_seq_cobind_strip.text()
    assert '导出' in hstrip2 or 'clipboard' in hstrip2.lower() or '序列' in hstrip2, hstrip2
    ok(f'export clipboard cobind · {hstrip2[:90]}')
    detail = view._alarm_okng_seq_cobind_detail.toPlainText()
    assert (
        'export/filter' in detail.lower() or '共绑' in detail or 'OPEN' in detail
        or 'cleared' in detail or '筛选' in detail or '序列' in detail or '报警' in detail
    ), detail
    ok(f'HMI seq detail · {detail.splitlines()[0][:80]}')

    bag = view.co_bind_alarm_hist_export_filter_okng_sequence(
        hist=hist, filtered=hist[:1], filter_needle='smoke', filter_status='open',
        export_kind='api', export_n=1, ok_n=4, ng_n=1, judge='OK', host_state='Idle',
        seq='OON', note='smoke-api',
    )
    assert bag['shown'] == 1 and bag['ok'] == 4, bag
    assert 'OON' in view._alarm_okng_seq_cobind_strip.text() or '序列' in view._alarm_okng_seq_cobind_strip.text()
    ok(f'API cobind · shown={bag["shown"]} seq={bag["seq"]}')

    print(f'\n=== {pass_n} passed, {fail_n} failed ===')
    return 0 if fail_n == 0 else 1

if __name__ == '__main__':
    rc = main()
    import os as _os
    _os._exit(rc)
