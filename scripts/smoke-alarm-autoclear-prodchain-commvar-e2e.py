#!/usr/bin/env python3
"""Headless E2E (t191/t192 CONTINUE):
1) Alarm auto-clear policy: off / on_ok / timeout
2) production_task chain → format+send expand + seed params (P0 p40)
3) Comm recv live-patches open Variables dialog (P1)
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

from PySide6.QtWidgets import QApplication, QWidget, QLabel
from PySide6.QtCore import QTimer

fails = []


def ok(name, cond, detail=''):
    if cond:
        print(f'PASS  {name}')
    else:
        fails.append(name)
        print(f'FAIL  {name}  {detail}')


def main():
    app = QApplication.instance() or QApplication(sys.argv)
    from desktop.host_state_machine import (
        HostStateMachineWidget, ALARM_CLEAR_OFF, ALARM_CLEAR_ON_OK,
        ALARM_CLEAR_TIMEOUT, ALARM_CLEAR_POLICIES,
    )
    from desktop.production_task_panel import (
        DEFAULT_CHAIN, chain_to_operations, seed_chain_step_params,
    )
    from desktop.comm_listener import CommRecvListener
    from desktop.comm_manager import write_project_variable, ensure_comm_manager
    from desktop.model import Document
    from desktop.mainwindow import MainWindow

    src_sm = open('desktop/host_state_machine.py', encoding='utf-8').read()
    src_cl = open('desktop/comm_listener.py', encoding='utf-8').read()
    src_mw = open('desktop/mainwindow.py', encoding='utf-8').read()

    ok('policies defined', set(ALARM_CLEAR_POLICIES) == {ALARM_CLEAR_OFF, ALARM_CLEAR_ON_OK, ALARM_CLEAR_TIMEOUT})
    ok('sm has set_alarm_auto_clear', hasattr(HostStateMachineWidget, 'set_alarm_auto_clear'))
    ok('sm has holds_alarm_on_ok', hasattr(HostStateMachineWidget, 'holds_alarm_on_ok'))
    ok('mw respects holds_alarm', 'holds_alarm_on_ok' in src_mw)
    ok('mw seeds chain', 'seed_chain_step_params' in src_mw)
    ok('comm live_patch recv', 'live_patch_flow_var' in src_cl and 'def _on_received' in src_cl)

    # ===== Alarm auto-clear =====
    sm = HostStateMachineWidget(compact=True)
    cmds = []
    sm.triggerCommands.connect(lambda c: cmds.extend(c))

    # Default on_ok
    ok('default policy on_ok', sm.alarm_auto_clear == ALARM_CLEAR_ON_OK, sm.alarm_auto_clear)
    ok('policy combo present', hasattr(sm, '_alarm_policy_combo'))

    sm.set_state('Alarm', 'test')
    ok('in Alarm', sm.state == 'Alarm')
    cmds.clear()
    sm.sync_from_runtime({'state': 'completed', 'elapsedMs': 1})
    ok('on_ok clears to Idle', sm.state == 'Idle', sm.state)
    ok('on_ok emits 状态·清除报警', any(c.get('type') == '状态·清除报警' for c in cmds), cmds)

    # Policy off: stay Alarm after OK
    sm.set_alarm_auto_clear(ALARM_CLEAR_OFF)
    ok('policy off', sm.alarm_auto_clear == ALARM_CLEAR_OFF)
    sm.set_state('Alarm', 'hold')
    ok('holds_alarm_on_ok True', sm.holds_alarm_on_ok())
    sm.sync_from_runtime({'state': 'completed'})
    ok('off stays Alarm', sm.state == 'Alarm', sm.state)

    # Timeout policy
    sm.set_alarm_auto_clear(ALARM_CLEAR_TIMEOUT, timeout_sec=1)
    ok('policy timeout', sm.alarm_auto_clear == ALARM_CLEAR_TIMEOUT)
    ok('timeout sec 1', sm._alarm_timeout_sec == 1)
    sm.set_state('Idle', 'reset')
    cmds.clear()
    sm.set_state('Alarm', 'tick')
    ok('timer armed', sm._alarm_timer.isActive())
    # Process timeout via direct callback (avoid waiting full second flaky)
    # Use short wait with QTimer
    sm._alarm_timeout_sec = 1
    # Force fire
    sm._on_alarm_timeout()
    ok('timeout cleared Idle', sm.state == 'Idle', sm.state)
    ok('timeout emits clear', any(c.get('type') == '状态·清除报警' for c in cmds), cmds)

    # Settings round-trip
    sm.set_alarm_auto_clear(ALARM_CLEAR_ON_OK, timeout_sec=12)
    sm2 = HostStateMachineWidget(compact=True)
    ok('settings loaded policy', sm2.alarm_auto_clear == ALARM_CLEAR_ON_OK, sm2.alarm_auto_clear)
    ok('settings loaded sec', sm2._alarm_timeout_sec == 12, sm2._alarm_timeout_sec)

    # ===== production chain P0 =====
    ops = chain_to_operations(DEFAULT_CHAIN)
    ops_keys = [o['operation'] for o in ops]
    ok('chain has locate', 'locate' in ops_keys)
    ok('chain has var_calc×2', ops_keys.count('var_calc') >= 2, ops_keys)
    ok('chain expands format', 'format_data' in ops_keys, ops_keys)
    ok('chain expands send', 'send_data' in ops_keys, ops_keys)
    ok('format before send', ops_keys.index('format_data') < ops_keys.index('send_data'))
    ok('display in chain', 'display' in ops_keys)

    dx = seed_chain_step_params('var_calc', '偏差', 'dx, dy')
    ok('seed dx formula', any(e['name']=='dx' and 'target_X_M' in e['expression'] for e in dx['expressions']), dx)
    mv = seed_chain_step_params('var_calc', '最终移动量', 'MoveX, MoveY')
    ok('seed MoveX', any(e['name']=='MoveX' for e in mv['expressions']), mv)
    fmt = seed_chain_step_params('format_data', '格式化', '')
    ok('seed format template', 'MoveX=' in (fmt.get('template') or ''), fmt)
    send = seed_chain_step_params('send_data', '发送', '', project={})
    ok('seed send LocalLoop', send.get('device') == 'LocalLoop', send)
    ok('seed send var formatted', send.get('sourceVar') == 'formatted' and send.get('sourceMode') == 'variable', send)

    # ===== Comm recv live patch =====
    class Host(QWidget):
        def __init__(self):
            super().__init__()
            self.document = Document()
            ensure_comm_manager(self.document.project)
            self.dialogs = {}
            self.logs = []
        def log(self, m):
            self.logs.append(m)
        def fire_string_trigger(self, text, reason=''):
            return False

    class FakeDlg:
        def __init__(self):
            self.patches = []
            self._vis = True
        def isVisible(self):
            return self._vis
        def live_patch_flow_var(self, name, value):
            self.patches.append(('flow', name, value))

    host = Host()
    # Configure recv event
    cm = host.document.project['commManager']
    cm['recvEvents'] = [dict(name='e1', device='LocalLoop', variable='flow.recvDemo', message='')]
    dlg = FakeDlg()
    host.dialogs['variables'] = dlg
    listener = CommRecvListener(host)
    listener.reload(host.document.project)
    listener._on_received('LocalLoop', 'HELLO_OK')
    ok('recv wrote variable', host.document.project.get('variables', {}).get('recvDemo') == 'HELLO_OK'
       or any('recvDemo' in str(x) for x in host.logs), host.document.project.get('variables'))
    ok('recv live_patched dialog', any(p[1] == 'recvDemo' and p[2] == 'HELLO_OK' for p in dlg.patches), dlg.patches)

    # write_project_variable helper sanity
    scope, name = write_project_variable(host.document.project, 'flow.x', 1)
    ok('write_project_variable', scope == 'flow' and name == 'x')

    if fails:
        print(f'\nFAILED {len(fails)}: {fails}')
        return 1
    print('\nALL PASS')
    return 0


if __name__ == '__main__':
    sys.exit(main())
