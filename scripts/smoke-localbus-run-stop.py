#!/usr/bin/env python3
"""Headless E2E: LocalBus inject RUN → command chain → STOP via CommRecvListener.

Uses project.globalTriggers.strings schema (dialog + commands[]).
No robot SDK. Offscreen Qt. Exit 0 on PASS.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtCore import QObject, QTimer, QEventLoop
from PySide6.QtWidgets import QApplication


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)

    from desktop.comm_listener import CommRecvListener
    from desktop.global_triggers import collect_string_commands, ACTION_TO_COMMAND, COMMAND_TYPES

    events = []

    class FakeDoc:
        def __init__(self, project):
            self.project = project

        def commit(self, p):
            self.project = p

    class Host(QObject):
        def __init__(self):
            super().__init__()
            self.logs = []
            self.continuous = False
            self._pending_trigger_cmds = []
            self._dispatching_triggers = False
            self.document = FakeDoc({
                'name': 'smoke-localbus',
                'steps': [],
                'variables': {},
                'commManager': {
                    'devices': [
                        {'name': 'LocalLoop', 'protocol': 'Local Bus', 'enabled': True},
                    ],
                    'recvEvents': [
                        {'device': 'LocalLoop', 'variable': 'flow.lastCmd'},
                    ],
                    'heartbeat': {'enabled': False},
                    'response': {'enabled': False},
                },
                'globalTriggers': {
                    'events': [],
                    'strings': [
                        {
                            'enabled': True,
                            'event': 'RUN',
                            'match': 'RUN',
                            'partial': False,
                            'commandType': '执行·单次',
                            'config': '',
                            'commands': [
                                {'type': '状态·清除报警', 'config': 'after-run'},
                            ],
                        },
                        {
                            'enabled': True,
                            'event': 'STOP',
                            'match': 'STOP',
                            'partial': False,
                            'commandType': '执行·停止',
                            'config': '',
                        },
                    ],
                },
            })

        def log(self, m):
            self.logs.append(str(m))

        def run_once(self):
            events.append('执行·单次')
            pending = list(self._pending_trigger_cmds)
            self._pending_trigger_cmds = []
            if pending:
                QTimer.singleShot(0, lambda: self._dispatch_global_triggers(pending, reason='链式触发'))

        def run_continuous(self):
            events.append('执行·连续')
            self.continuous = True

        def stop_run(self):
            events.append('执行·停止')
            self.continuous = False

        def fire_string_trigger(self, text, reason='外部字符串'):
            payload = '' if text is None else str(text)
            cmds = collect_string_commands(self.document.project, payload)
            if not cmds:
                self.logs.append(f'NO_MATCH:{payload}')
                return False
            self.logs.append(f'MATCH:{payload}×{len(cmds)}')
            self._dispatch_global_triggers(cmds, reason=reason)
            return True

        def _dispatch_global_triggers(self, commands, reason=''):
            if self._dispatching_triggers:
                return
            self._dispatching_triggers = True
            try:
                self._run_hmi_commands(commands)
            finally:
                self._dispatching_triggers = False

        def _run_hmi_commands(self, commands):
            cmds = list(commands or [])
            for i, cmd in enumerate(cmds):
                raw = (cmd or {}).get('type') or ''
                ctype = ACTION_TO_COMMAND.get(raw) or raw
                if ctype not in COMMAND_TYPES and raw in COMMAND_TYPES:
                    ctype = raw
                if ctype in ('执行·单次', '执行'):
                    self._pending_trigger_cmds = list(cmds[i + 1:])
                    self.run_once()
                    return
                if ctype == '执行·连续':
                    self._pending_trigger_cmds = []
                    self.run_continuous()
                    return
                if ctype == '执行·停止':
                    self._pending_trigger_cmds = []
                    self.stop_run()
                    continue
                if ctype == '状态·清除报警':
                    events.append('状态·清除报警')
                    continue
                events.append(ctype or raw)

    host = Host()
    run_cmds = collect_string_commands(host.document.project, 'RUN')
    stop_cmds = collect_string_commands(host.document.project, 'STOP')
    print('RUN cmds', [(c.get('type'), c.get('config')) for c in run_cmds])
    print('STOP cmds', [(c.get('type'), c.get('config')) for c in stop_cmds])
    if not run_cmds or not stop_cmds:
        print('FAIL: triggers not collected')
        return 2
    # Expect chain: 执行·单次 then 状态·清除报警
    types = [c.get('type') for c in run_cmds]
    if '执行·单次' not in types or '状态·清除报警' not in types:
        print('FAIL: RUN chain incomplete', types)
        return 2

    lis = CommRecvListener(host=host)
    lis.reload(host.document.project)

    lis.push_local('LocalLoop', 'RUN')
    loop = QEventLoop()
    QTimer.singleShot(250, loop.quit)
    loop.exec()

    lis.push_local('LocalLoop', 'STOP')
    loop = QEventLoop()
    QTimer.singleShot(250, loop.quit)
    loop.exec()

    lis.stop()

    print('events', events)
    print('vars', host.document.project.get('variables'))
    print('logs', host.logs[-10:])

    if '执行·单次' not in events:
        print('FAIL: missing 执行·单次')
        return 1
    if '状态·清除报警' not in events:
        print('FAIL: missing chained 状态·清除报警')
        return 1
    if '执行·停止' not in events:
        print('FAIL: missing 执行·停止')
        return 1
    if host.document.project.get('variables', {}).get('lastCmd') != 'STOP':
        print('FAIL: lastCmd not STOP', host.document.project.get('variables'))
        return 1
    # Order: RUN path before STOP
    i_run = events.index('执行·单次')
    i_chain = events.index('状态·清除报警')
    i_stop = events.index('执行·停止')
    if not (i_run < i_chain < i_stop):
        print('FAIL: order', events)
        return 1
    print('PASS smoke-localbus-run-stop')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
