#!/usr/bin/env python3
"""Headless E2E (t191/t192 CONTINUE P0):
1) HMI HostStateMachine deepen: Idle/Run/Pause/Alarm/Stop chrome + soft pause/resume cmds
2) Comm heartbeat badge polish (♥payload pulse + settle)
3) Redo history dropdown (mirror undo)
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

from PySide6.QtWidgets import QApplication, QWidget, QLabel, QMenu

fails = []


def ok(name, cond, detail=''):
    if cond:
        print(f'PASS  {name}')
    else:
        fails.append(name)
        print(f'FAIL  {name}  {detail}')


def main():
    app = QApplication.instance() or QApplication(sys.argv)
    from desktop.model import Document
    from desktop.mainwindow import MainWindow
    from desktop.operator_hmi import OperatorHmiView
    from desktop.host_state_machine import (
        HostStateMachineWidget, STATES, STATE_ZH, STATE_COLOR,
    )

    src_mw = open('desktop/mainwindow.py', encoding='utf-8').read()
    src_hmi = open('desktop/operator_hmi.py', encoding='utf-8').read()
    src_sm = open('desktop/host_state_machine.py', encoding='utf-8').read()

    # ========== source markers ==========
    ok('STATES has 5', STATES == ('Idle', 'Running', 'Paused', 'Alarm', 'Stopped'))
    ok('STATE_ZH covers all', all(s in STATE_ZH for s in STATES))
    ok('STATE_COLOR covers all', all(s in STATE_COLOR for s in STATES))
    ok('sm sync_from_runtime keep_running', 'keep_running' in src_sm)
    ok('sm pause emits 执行·暂停', "type='执行·暂停'" in src_sm or '执行·暂停' in src_sm)
    ok('sm resume emits 执行·继续', "type='执行·继续'" in src_sm or '执行·继续' in src_sm)
    ok('sm NOT pause→停止', "type='执行·停止'" not in src_sm.split('def _auto_pause')[1].split('def _auto_resume')[0])
    ok('hmi has _paint_machine_chrome', hasattr(OperatorHmiView, '_paint_machine_chrome'))
    ok('hmi has set_host_machine_state', hasattr(OperatorHmiView, 'set_host_machine_state'))
    ok('hmi has set_keep_host_running', hasattr(OperatorHmiView, 'set_keep_host_running'))
    ok('hmi has _wire_host_sm', hasattr(OperatorHmiView, '_wire_host_sm'))
    ok('hmi state rail', '_state_rail' in src_hmi and 'hostStateRail' in src_hmi)
    ok('mw has _sync_host_sm_state', hasattr(MainWindow, '_sync_host_sm_state'))
    ok('mw has _set_keep_host_running', hasattr(MainWindow, '_set_keep_host_running'))
    ok('mw soft pause_continuous on 执行·暂停', 'pause_continuous()' in src_mw.split("if ctype == '执行·暂停'")[1].split('if ctype ==')[0])
    ok('mw resume on 执行·继续', 'resume_continuous()' in src_mw.split("if ctype == '执行·继续'")[1].split('if ctype ==')[0])
    ok('mw redo menu set', 'redo_action.setMenu(self._redo_history_menu)' in src_mw)
    ok('mw has _populate_redo_history_menu', hasattr(MainWindow, '_populate_redo_history_menu'))
    ok('mw has _redo_to_history_index', hasattr(MainWindow, '_redo_to_history_index'))
    ok('mw heartbeat ♥', '♥' in src_mw.split('def _on_comm_heartbeat_tick')[1].split('def _settle')[0])
    ok('mw settle hb badge', hasattr(MainWindow, '_settle_comm_hb_badge'))

    # ========== HostStateMachineWidget behavior ==========
    sm = HostStateMachineWidget(compact=True)
    ok('sm starts Idle', sm.state == 'Idle')
    cmds = []
    sm.triggerCommands.connect(lambda c: cmds.extend(c))
    states = []
    sm.stateChanged.connect(lambda s: states.append(s))

    sm.set_state('Running', 'test')
    ok('sm → Running', sm.state == 'Running' and states[-1] == 'Running')

    # keep_running: completed stays Running
    sm.sync_from_runtime({'state': 'completed', 'elapsedMs': 12}, keep_running=True)
    ok('keep_running stays Running', sm.state == 'Running')

    sm.sync_from_runtime({'state': 'completed', 'elapsedMs': 12}, keep_running=False)
    # already Running → stays Running per "keep_running or state==Running"
    ok('completed while Running stays Running', sm.state == 'Running')

    sm.set_state('Idle', 'reset')
    sm.sync_from_runtime({'state': 'completed'}, keep_running=False)
    ok('completed from Idle → Idle', sm.state == 'Idle')

    sm.sync_from_runtime({'state': 'failed', 'error': 'boom'})
    ok('failed → Alarm', sm.state == 'Alarm', sm.state)

    sm.set_state('Idle', 'clear')
    sm.sync_from_runtime({'state': 'cancelled'})
    ok('cancelled → Stopped', sm.state == 'Stopped', sm.state)

    sm.set_state('Running', 'go')
    cmds.clear()
    sm._auto_pause('自动')
    ok('auto_pause → Paused', sm.state == 'Paused')
    ok('auto_pause emits 执行·暂停', any(c.get('type') == '执行·暂停' for c in cmds), cmds)

    cmds.clear()
    sm._auto_resume('自动')
    ok('auto_resume → Running', sm.state == 'Running')
    ok('auto_resume emits 执行·继续', any(c.get('type') == '执行·继续' for c in cmds), cmds)

    cmds.clear()
    sm._auto_stop('自动')
    ok('auto_stop → Stopped', sm.state == 'Stopped')
    ok('auto_stop emits 执行·停止', any(c.get('type') == '执行·停止' for c in cmds), cmds)

    # ========== OperatorHmiView chrome ==========
    hmi = OperatorHmiView()
    ok('hmi has state rail labels', hasattr(hmi, '_state_rail_labels') and len(hmi._state_rail_labels) == 5)
    ok('hmi has _state_badge', hasattr(hmi, '_state_badge'))
    hmi._paint_machine_chrome('Running')
    ok('badge shows 运行中', hmi._state_badge.text() == STATE_ZH['Running'], hmi._state_badge.text())
    ok('host_state Running', hmi._host_state == 'Running')
    hmi.set_keep_host_running(True)
    ok('keep flag on', getattr(hmi, '_keep_host_running', False) is True)
    hmi.set_host_machine_state('Alarm', 'test')
    # without host_sm widget, paint only
    ok('chrome Alarm', hmi._host_state == 'Alarm', hmi._host_state)
    ok('badge 报警', hmi._state_badge.text() == '报警')

    # Embed SM via set_runtime keep path
    host = HostStateMachineWidget(compact=True)
    hmi._wire_host_sm(host)
    ok('wired _host_sm', hmi._host_sm is host)
    hmi.set_keep_host_running(True)
    host.set_state('Running', 'cont')
    hmi.set_runtime({'state': 'completed', 'elapsedMs': 5})
    ok('set_runtime keep stays Running', host.state == 'Running', host.state)
    ok('chrome mirrors Running', hmi._host_state == 'Running')

    # ========== Redo history menu ==========
    class Stub(QWidget):
        pass
    stub = Stub()
    stub.document = Document()
    # Build history with labels (commit no-ops if project unchanged)
    from copy import deepcopy
    for lab, name in [('A', '方案A'), ('B', '方案B'), ('C', '方案C')]:
        p = deepcopy(stub.document.project)
        p['name'] = name
        stub.document.commit(p, label=lab)
    ok('history len 4', len(stub.document.history) == 4, len(stub.document.history))
    ok('index at tip C', stub.document.index == 3, stub.document.index)
    # undo twice → land on A (index 1)
    stub.document.undo()
    stub.document.undo()
    ok('index after 2 undo', stub.document.index == 1, stub.document.index)
    stub._redo_history_menu = QMenu()
    stub._undo_history_menu_n = 12
    stub.log = lambda *a, **k: None
    stub._show_canvas_status_chip = lambda *a, **k: None
    stub._maybe_log_fold_cross = lambda *a, **k: None
    stub._refresh_undo_redo_labels = lambda: None
    MainWindow._populate_redo_history_menu(stub)
    acts = [a.text() for a in stub._redo_history_menu.actions()]
    ok('redo menu has entries', len(acts) >= 1 and '无可重做' not in acts[0], acts)
    ok('redo menu mentions B or C', any('B' in a or 'C' in a for a in acts), acts)
    # Jump redo to last
    last = len(stub.document.history) - 1
    MainWindow._redo_to_history_index(stub, last, tip_label='C')
    ok('redo jump to tip', stub.document.index == last, stub.document.index)

    # ========== Heartbeat badge polish (stub) ==========
    stub2 = Stub()
    stub2.comm_listen_badge = QLabel('监听·开')
    stub2._last_listen_badge = '监听·开'
    stub2._hb_tick_count = 0
    stub2._comm_listener = type('L', (), {'_heartbeat': {'enabled': True, 'intervalMs': 2000, 'payload': 'PING'}, '_last_hb_ms': 1})()
    stub2.dialogs = {}
    MainWindow._on_comm_heartbeat_tick(stub2, 'PING')
    txt = stub2.comm_listen_badge.text()
    ok('hb badge has ♥PING', '♥PING' in txt, txt)
    ok('hb tick count 1', stub2._hb_tick_count == 1)
    tip = stub2.comm_listen_badge.toolTip()
    ok('hb tip has 载荷', 'PING' in tip and '心跳' in tip, tip)
    MainWindow._settle_comm_hb_badge(stub2)
    ok('settle stylesheet green', '#5ecf8a' in (stub2.comm_listen_badge.styleSheet() or ''), stub2.comm_listen_badge.styleSheet())

    MainWindow._on_comm_listening_changed(stub2, False, '监听·关')
    ok('listen off resets tick', stub2._hb_tick_count == 0)
    ok('listen off text', stub2.comm_listen_badge.text() == '监听·关')

    if fails:
        print(f'\nFAILED {len(fails)}: {fails}')
        return 1
    print('\nALL PASS')
    return 0


if __name__ == '__main__':
    sys.exit(main())
