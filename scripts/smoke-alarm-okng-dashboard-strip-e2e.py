#!/usr/bin/env python3
"""Alarm/OK-NG dashboard soft strip deepen — page-level; no robot SDK / no sev-chip cascade."""
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
        ast.parse((ROOT / rel).read_text(encoding='utf-8'))
        ok(f'ast/parse {rel}')

    hmi_src = (ROOT / 'desktop/operator_hmi.py').read_text(encoding='utf-8')
    for needle in (
        'hmiOkNgDashboardStrip', 'prodOkNgDashboardStrip',
        'refresh_okng_dashboard_strip',
    ):
        (ok if needle in hmi_src else bad)(
            f'hmi has {needle}' if needle in hmi_src else f'missing {needle}'
        )

    host_src = (ROOT / 'desktop/host_state_machine.py').read_text(encoding='utf-8')
    for needle in ('hostOkNgDashboardStrip', 'set_okng_dashboard_strip'):
        (ok if needle in host_src else bad)(
            f'host has {needle}' if needle in host_src else f'missing {needle}'
        )

    from PySide6.QtWidgets import QApplication, QLabel
    app = QApplication.instance() or QApplication([])
    from desktop.host_state_machine import HostStateMachineWidget
    from desktop.operator_hmi import ProductionStatsPanel, OperatorHmiView

    sm = HostStateMachineWidget(compact=True)
    assert hasattr(sm, '_okng_dashboard_strip')
    assert sm._okng_dashboard_strip.objectName() == 'hostOkNgDashboardStrip'
    ok('host okng dashboard strip present')

    sm.set_production_snapshot(12, 3, host_state='Running')
    prod = sm._prod_strip.text()
    dash = sm._okng_dashboard_strip.text()
    assert 'OK 12' in prod and 'NG 3' in prod, prod
    assert 'OK 12' in dash and 'NG 3' in dash and '良率' in dash, dash
    assert '报警开' in dash and '状态' in dash, dash
    ok(f'host dashboard deepen · {dash[:80]}')

    sm.set_state('Alarm', '检测失败 fail')
    sm.set_production_snapshot(12, 4, host_state='Alarm')
    dash2 = sm._okng_dashboard_strip.text()
    assert '报警开' in dash2, dash2
    ok(f'host dashboard alarm · {dash2[:80]}')

    panel = ProductionStatsPanel()
    assert panel.findChild(QLabel, 'prodOkNgDashboardStrip') is not None
    panel.record(True, elapsed_ms=12, detail='ok1')
    panel.record(True, elapsed_ms=10, detail='ok2')
    panel.record(False, elapsed_ms=15, detail='ng1')
    dashp = panel._okng_dash_lab.text()
    assert 'OK 2' in dashp and 'NG 1' in dashp and '序列' in dashp, dashp
    ok(f'stats dashboard strip · {dashp}')

    view = OperatorHmiView()
    assert view.findChild(QLabel, 'hmiOkNgDashboardStrip') is not None
    text = view.refresh_okng_dashboard_strip(
        ok_n=20, ng_n=5, judge='OK', open_alarms=1,
        host_state='Running', recipe='配方A', status_var='global.taskStatus',
        last_alarm='超时',
    )
    assert 'OK 20' in text and 'NG 5' in text and '配方A' in text, text
    assert '报警开 1' in text and '末警' in text, text
    shown = view._okng_dashboard_strip.text()
    assert 'OK 20' in shown, shown
    ok(f'HMI dashboard strip · {shown[:90]}')

    # ensure no new sev-chip cascade objectNames introduced this wave
    for banned in ('hostAlarmSevChip_wave_dash', 'hostWatchOkNgChip'):
        if banned in host_src:
            bad(f'unexpected micro-chip {banned}')
        else:
            ok(f'no micro-chip {banned}')

    print(f'\n=== {pass_n} passed, {fail_n} failed ===')
    return 0 if fail_n == 0 else 1

if __name__ == '__main__':
    rc = main()
    # Qt offscreen teardown can SIGSEGV after green asserts
    import os as _os
    _os._exit(rc)
