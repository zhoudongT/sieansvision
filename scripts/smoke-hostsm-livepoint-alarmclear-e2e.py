#!/usr/bin/env python3
"""Headless E2E (t191/t192 CONTINUE NEXT):
1) Host SM live Start/Pause/Resume/Stop quick bar drives SM + triggerCommands
2) Alarm clear UX: quick/tab/rail/strip → 状态·清除报警
3) OperatorHmi strip Pause/Resume/Clear enablement
Exit 0 on PASS. No robot SDK. No push.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtCore import Qt, QEvent, QPoint
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication

fails = []


def ok(name, cond, detail=''):
    if cond:
        print(f'PASS  {name}')
    else:
        fails.append(name)
        print(f'FAIL  {name}  {detail}')


def main():
    app = QApplication.instance() or QApplication(sys.argv)
    from desktop.host_state_machine import HostStateMachineWidget, STATE_ZH
    from desktop.operator_hmi import (
        OperatorHmiView, DEFAULT_PAUSE_COMMANDS, DEFAULT_RESUME_COMMANDS,
        DEFAULT_CLEAR_ALARM_COMMANDS,
    )
    from desktop.mainwindow import MainWindow
    from desktop.global_triggers import COMMAND_TYPES

    src_sm = open('desktop/host_state_machine.py', encoding='utf-8').read()
    src_hmi = open('desktop/operator_hmi.py', encoding='utf-8').read()
    src_mw = open('desktop/mainwindow.py', encoding='utf-8').read()

    ok('COMMAND_TYPES has 状态·清除报警', '状态·清除报警' in COMMAND_TYPES)
    ok('sm has _clear_alarm', hasattr(HostStateMachineWidget, '_clear_alarm'))
    ok('sm has _raise_alarm', hasattr(HostStateMachineWidget, '_raise_alarm'))
    ok('sm _clear_alarm emits 状态·清除报警', '状态·清除报警' in src_sm.split('def _clear_alarm')[1].split('def _auto_start')[0])
    ok('sm quick bar', '_q_start' in src_sm and 'hostSmQuickBar' in src_sm)
    ok('hmi DEFAULT_PAUSE', DEFAULT_PAUSE_COMMANDS[0]['type'] == '执行·暂停')
    ok('hmi DEFAULT_CLEAR', DEFAULT_CLEAR_ALARM_COMMANDS[0]['type'] == '状态·清除报警')
    ok('hmi strip clear', 'hmiClearAlarmBtn' in src_hmi)
    ok('hmi eventFilter alarm', 'hostAlarmRail' in src_hmi or 'Alarm' in src_hmi.split('def eventFilter')[1][:400])
    ok('mw clear logs', '状态·清除报警 → 空闲' in src_mw)
    ok('mw has _run_hmi_commands', hasattr(MainWindow, '_run_hmi_commands'))

    # ===== Host SM live controls =====
    sm = HostStateMachineWidget(compact=True)
    ok('compact opens auto tab', sm.tabs.currentIndex() == 1, sm.tabs.currentIndex())
    ok('quick bar widgets', all(hasattr(sm, a) for a in ('_q_start', '_q_pause', '_q_resume', '_q_stop', '_q_clear')))

    cmds = []
    sm.triggerCommands.connect(lambda c: cmds.extend(c))

    # Start
    ok('start enabled Idle', sm._q_start.isEnabled())
    ok('pause disabled Idle', not sm._q_pause.isEnabled())
    ok('clear disabled Idle', not sm._q_clear.isEnabled())
    cmds.clear()
    sm._q_start.click()
    ok('start → Running', sm.state == 'Running')
    ok('start emits 执行·连续', any(c.get('type') == '执行·连续' for c in cmds), cmds)
    ok('pause enabled Running', sm._q_pause.isEnabled())
    ok('stop enabled Running', sm._q_stop.isEnabled())

    # Pause
    cmds.clear()
    sm._q_pause.click()
    ok('pause → Paused', sm.state == 'Paused')
    ok('pause emits 执行·暂停', any(c.get('type') == '执行·暂停' for c in cmds), cmds)
    ok('resume enabled Paused', sm._q_resume.isEnabled())

    # Resume
    cmds.clear()
    sm._q_resume.click()
    ok('resume → Running', sm.state == 'Running')
    ok('resume emits 执行·继续', any(c.get('type') == '执行·继续' for c in cmds), cmds)

    # Stop
    cmds.clear()
    sm._q_stop.click()
    ok('stop → Stopped', sm.state == 'Stopped')
    ok('stop emits 执行·停止', any(c.get('type') == '执行·停止' for c in cmds), cmds)
    ok('start enabled Stopped', sm._q_start.isEnabled())

    # Alarm + clear
    cmds.clear()
    sm._raise_alarm()
    ok('raise → Alarm', sm.state == 'Alarm')
    ok('raise emits 状态·报警', any(c.get('type') == '状态·报警' for c in cmds), cmds)
    ok('clear enabled Alarm', sm._q_clear.isEnabled())
    ok('start blocked Alarm', not sm._q_start.isEnabled())
    # Start while Alarm should no-op
    before = list(cmds)
    sm._auto_start('正常生产')
    ok('start blocked stays Alarm', sm.state == 'Alarm')

    cmds.clear()
    sm._q_clear.click()
    ok('clear → Idle', sm.state == 'Idle')
    ok('clear emits 状态·清除报警', any(c.get('type') == '状态·清除报警' for c in cmds), cmds)
    ok('clear disabled after', not sm._q_clear.isEnabled())

    # Start while Paused → resume path
    sm.set_state('Paused', 'test')
    cmds.clear()
    sm._auto_start('正常生产')
    ok('start-from-Paused resumes', sm.state == 'Running')
    ok('start-from-Paused emits 继续', any(c.get('type') == '执行·继续' for c in cmds), cmds)

    # ===== OperatorHmi strip + rail =====
    hmi = OperatorHmiView()
    hmi_cmds = []
    hmi.triggerCommands.connect(lambda c: hmi_cmds.extend(c))
    ok('strip has pause/resume/clear', all(k in hmi._strip_btns for k in ('pause', 'resume', 'clear')))

    hmi._paint_machine_chrome('Running')
    ok('strip pause on Running', hmi._strip_btns['pause'].isEnabled())
    ok('strip clear off Running', not hmi._strip_btns['clear'].isEnabled())

    hmi._paint_machine_chrome('Paused')
    ok('strip resume on Paused', hmi._strip_btns['resume'].isEnabled())

    hmi._paint_machine_chrome('Alarm')
    ok('strip clear on Alarm', hmi._strip_btns['clear'].isEnabled())
    ok('badge 报警', hmi._state_badge.text() == STATE_ZH['Alarm'])

    hmi_cmds.clear()
    hmi._strip_btns['clear'].click()
    ok('strip clear emits 状态·清除报警',
       any(c.get('type') == '状态·清除报警' for c in hmi_cmds), hmi_cmds)

    # Alarm rail click via eventFilter
    hmi._paint_machine_chrome('Alarm')
    hmi_cmds.clear()
    lab = hmi._state_rail_labels['Alarm']
    press = QMouseEvent(
        QEvent.Type.MouseButtonPress, QPoint(5, 5), QPoint(5, 5), QPoint(5, 5),
        Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
    )
    # Use eventFilter directly
    handled = hmi.eventFilter(lab, press)
    ok('rail click handled', handled is True)
    ok('rail click emits clear',
       any(c.get('type') == '状态·清除报警' for c in hmi_cmds), hmi_cmds)

    # Wire host into HMI — clear via host also reaches triggerCommands
    host = HostStateMachineWidget(compact=True)
    hmi._wire_host_sm(host)
    hmi_cmds.clear()
    host._raise_alarm()
    # raise emits on host → wired to hmi.triggerCommands
    ok('wired raise reaches hmi', any(c.get('type') == '状态·报警' for c in hmi_cmds), hmi_cmds)
    hmi_cmds.clear()
    host._clear_alarm()
    ok('wired clear reaches hmi', any(c.get('type') == '状态·清除报警' for c in hmi_cmds), hmi_cmds)
    ok('chrome Idle after clear', hmi._host_state == 'Idle', hmi._host_state)

    # Live continuous path markers in MainWindow
    ok('mw pause_continuous on 执行·暂停', 'pause_continuous()' in src_mw.split("if ctype == '执行·暂停'")[1].split('if ctype ==')[0])
    ok('mw resume_continuous on 执行·继续', 'resume_continuous()' in src_mw.split("if ctype == '执行·继续'")[1].split('if ctype ==')[0])

    if fails:
        print(f'\nFAILED {len(fails)}: {fails}')
        return 1
    print('\nALL PASS')
    return 0


if __name__ == '__main__':
    sys.exit(main())
