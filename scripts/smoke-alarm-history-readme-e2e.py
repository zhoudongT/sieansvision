#!/usr/bin/env python3
"""Alarm history panel + README gallery completeness. No robot SDK."""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

pass_n = fail_n = 0

def ok(m):
    global pass_n
    pass_n += 1
    print('PASS:', m)

def bad(m):
    global fail_n
    fail_n += 1
    print('FAIL:', m)

def main():
    readme = (ROOT / 'projects/README-open-and-run.md').read_text(encoding='utf-8')
    samples = sorted(p.name for p in (ROOT / 'projects').glob('open-and-run*.sieans'))
    missing = [s for s in samples if s not in readme]
    if not missing:
        ok(f'README lists {len(samples)} samples')
    else:
        bad(f'README missing {missing}')
    if 'open-and-run-locate.sieans' in readme and 'passGate' in readme:
        ok('README locate how-to mentions passGate')
    else:
        bad('README locate how-to weak')
    if 'open-and-run-measure.sieans' in readme:
        ok('README has measure sample')
    else:
        bad('README missing measure')

    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from desktop.host_state_machine import HostStateMachineWidget
    w = HostStateMachineWidget(compact=True)
    # Tab present
    names = [w.tabs.tabText(i) for i in range(w.tabs.count())]
    if '报警历史' in names:
        ok(f'alarm history tab in {names}')
    else:
        bad(f'no 报警历史 tab: {names}')
    assert hasattr(w, '_alarm_list')
    w.set_state('Alarm', 'smoke-A')
    hist = w.alarm_history()
    if len(hist) >= 1 and hist[-1]['reason'] == 'smoke-A':
        ok(f'history recorded n={len(hist)} reason={hist[-1]["reason"]}')
    else:
        bad(f'history not recorded: {hist}')
    w._clear_alarm()
    hist2 = w.alarm_history()
    if hist2 and hist2[-1].get('cleared') is True:
        ok('clear marks last entry cleared')
    else:
        bad(f'clear did not mark: {hist2}')
    w.set_state('Alarm', 'smoke-B')
    w.clear_alarm_history()
    if w.alarm_history() == []:
        ok('clear_alarm_history emptied')
    else:
        bad(f'history not empty: {w.alarm_history()}')
    # list widget object name
    if w._alarm_list.objectName() == 'hostAlarmHistoryList':
        ok('hostAlarmHistoryList objectName')
    else:
        bad('objectName mismatch')

    print('ALL PASS' if fail_n == 0 else f'FAIL {fail_n}')
    return 0 if fail_n == 0 else 1

if __name__ == '__main__':
    raise SystemExit(main())
