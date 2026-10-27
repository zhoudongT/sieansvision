#!/usr/bin/env python3
"""细妆⑰：生产链路 / 报警历史 UX deepen（Host SM spark·severity·prod strip · Stats UPH/CSV/host mirror）.
No robot SDK / no push / no field HW.
"""
from __future__ import annotations
import os, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); os.chdir(ROOT)
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

fails = []
def ok(n, c, d=''):
    if c: print(f'PASS  {n}')
    else: fails.append(n); print(f'FAIL  {n}  {d}')

def main():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)

    from desktop.host_state_machine import HostStateMachineWidget, STATE_ZH
    from desktop.operator_hmi import ProductionStatsPanel, OperatorHmiView

    sm = HostStateMachineWidget(compact=True)
    ok('prod strip present', hasattr(sm, '_prod_strip'))
    ok('alarm spark present', hasattr(sm, '_alarm_spark'))
    ok('status filter present', hasattr(sm, '_alarm_status_filter'))
    ok('set_production_snapshot', callable(getattr(sm, 'set_production_snapshot', None)))

    sm.set_production_snapshot(12, 3, host_state='Running')
    txt = sm._prod_strip.text()
    ok('prod strip OK/NG', 'OK 12' in txt and 'NG 3' in txt, txt)
    ok('prod strip yield', '良率' in txt and '80' in txt, txt)
    ok('prod strip state', '运行中' in txt, txt)

    sm.set_state('Alarm', '检测失败 fail')
    hist = sm.alarm_history()
    ok('alarm recorded', len(hist) >= 1)
    e = hist[-1]
    ok('severity error', e.get('severity') == 'error', e)
    ok('cleared_at empty', not e.get('cleared_at'))
    ok('spark uncleared', '▇' in (sm._alarm_spark.text() or ''), sm._alarm_spark.text())

    sm._clear_alarm()
    e2 = sm.alarm_history()[-1]
    ok('cleared flag', e2.get('cleared') is True)
    ok('cleared_at set', bool(e2.get('cleared_at')), e2)
    ok('spark cleared bar', '▁' in (sm._alarm_spark.text() or ''), sm._alarm_spark.text())

    csv = sm.alarm_history_csv()
    ok('csv header severity', 'severity' in csv.splitlines()[0] and 'cleared_at' in csv.splitlines()[0], csv.splitlines()[0])

    # status filter open/cleared
    sm.set_state('Alarm', 'NG 超时')
    sm._alarm_status_filter.setCurrentIndex(sm._alarm_status_filter.findData('open'))
    sm._refresh_alarm_history_ui()
    ok('filter open shows', sm._alarm_list.count() >= 1)
    sm._alarm_status_filter.setCurrentIndex(sm._alarm_status_filter.findData('cleared'))
    sm._refresh_alarm_history_ui()
    # at least the previously cleared one
    ok('filter cleared shows', sm._alarm_list.count() >= 1)

    # ProductionStatsPanel deepen
    panel = ProductionStatsPanel()
    ok('host state lab', hasattr(panel, '_host_state_lab'))
    ok('ok spark lab', hasattr(panel, '_ok_spark_lab'))
    ok('uph lab', hasattr(panel, '_uph_lab'))
    ok('export_history_file', callable(getattr(panel, 'export_history_file', None)))
    ok('history_csv', callable(getattr(panel, 'history_csv', None)))
    panel.record(True, 50, 'ok1')
    panel.record(False, 80, 'ng1')
    panel.record(True, 60, 'ok2')
    ok('uph text', 'UPH' in panel._uph_lab.text() and '节拍' in panel._uph_lab.text(), panel._uph_lab.text())
    ok('ok spark has bars', '▇' in panel._ok_spark_lab.text() or '▁' in panel._ok_spark_lab.text(), panel._ok_spark_lab.text())
    panel.set_host_state_mirror('Running', '运行中')
    ok('host mirror Running', '运行中' in panel._host_state_lab.text(), panel._host_state_lab.text())
    panel.set_host_state_mirror('Alarm', '报警')
    ok('host mirror Alarm', '报警' in panel._host_state_lab.text())
    hcsv = panel.history_csv()
    ok('stats csv header', 'timestamp' in hcsv.splitlines()[0], hcsv.splitlines()[0])

    # OperatorHmiView wiring presence
    src = open('desktop/operator_hmi.py', encoding='utf-8').read()
    ok('push_production_snapshot', 'def push_production_snapshot' in src)
    ok('chrome feeds snapshot', 'set_production_snapshot' in src and 'set_host_state_mirror' in src)

    print('----')
    if fails:
        print(f'{len(fails)} FAIL'); sys.exit(1)
    print('ALL PASS'); sys.exit(0)

if __name__ == '__main__':
    main()
