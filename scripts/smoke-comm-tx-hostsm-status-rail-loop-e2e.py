#!/usr/bin/env python3
"""Comm sendEvents result-out → Host SM / HMI status rail closed-loop page chrome — no field TCP."""
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
        'desktop/comm_manager.py',
        'desktop/operator_hmi.py',
        'desktop/production_task_panel.py',
        'desktop/host_state_machine.py',
    ):
        src = (ROOT / rel).read_text(encoding='utf-8')
        if rel != 'desktop/host_state_machine.py':
            ast.parse(src)
        ok(f'ast/parse-or-read {rel}')

    cm = (ROOT / 'desktop/comm_manager.py').read_text(encoding='utf-8')
    for needle in (
        'commSendEventsHostSmStatusRailLoopStrip', '_soft_close_loop_host_sm_status_rail',
        'statusRailLoop',
    ):
        (ok if needle in cm else bad)(f'comm has {needle}' if needle in cm else f'missing {needle}')

    hmi_src = (ROOT / 'desktop/operator_hmi.py').read_text(encoding='utf-8')
    for needle in (
        'hmiCommTxStatusRailClosedLoopStrip', 'apply_comm_tx_status_rail_closed_loop',
    ):
        (ok if needle in hmi_src else bad)(f'hmi has {needle}' if needle in hmi_src else f'missing {needle}')

    host_src = (ROOT / 'desktop/host_state_machine.py').read_text(encoding='utf-8')
    for needle in (
        'hostCommTxStatusRailLoopStrip', 'set_comm_tx_status_rail_loop_strip',
    ):
        (ok if needle in host_src else bad)(f'host has {needle}' if needle in host_src else f'missing {needle}')

    prod = (ROOT / 'desktop/production_task_panel.py').read_text(encoding='utf-8')
    for needle in (
        'productionTaskCommTxStatusRailLoopStrip', 'statusRailLoop',
    ):
        (ok if needle in prod else bad)(f'panel has {needle}' if needle in prod else f'missing {needle}')

    from PySide6.QtWidgets import QApplication, QPlainTextEdit, QLabel
    from PySide6.QtCore import QCoreApplication
    app = QApplication.instance() or QApplication([])

    from desktop.comm_manager import CommManagerDialog
    from desktop.operator_hmi import OperatorHmiView
    from desktop.host_state_machine import HostStateMachineWidget
    from desktop.production_task_panel import ProductionTaskPanel

    project = {
        'name': 'tx-rail-loop-smoke',
        'steps': [], 'edges': [],
        'variables': {'global': {'taskStatus': 'ready'}, 'flow': {}},
        'commManager': {
            'devices': [{'name': 'LocalLoop', 'protocol': 'Local Bus', 'enabled': True}],
            'recvEvents': [],
            'sendEvents': [
                {'name': 'fmt', 'device': 'LocalLoop',
                 'message': 'RESULT okng=${flow.okng} recipe=${flow.recipe}'},
            ],
            'heartbeat': {'enabled': False},
            'response': {'enabled': True, 'ack': 'ACK_OK'},
            'messageTemplates': [],
        },
    }

    class Doc:
        def __init__(self):
            self.project = project
            self._commits = []
        def commit(self, p):
            self.project = p
            self._commits.append(p)

    view = OperatorHmiView()
    host = HostStateMachineWidget()
    view._wire_host_sm(host)
    doc = Doc()
    dlg = CommManagerDialog(doc)
    ok('widgets constructed')
    assert dlg.findChild(QPlainTextEdit, 'commSendEventsHostSmStatusRailLoopStrip') is not None
    assert view.findChild(QLabel, 'hmiCommTxStatusRailClosedLoopStrip') is not None
    assert host.findChild(QLabel, 'hostCommTxStatusRailLoopStrip') is not None
    ok('closed-loop strips present')

    class Win:
        def __init__(self):
            self.operator_hmi = view
            self.host_state_machine = host
            self.document = doc
            self.comm_manager = dlg
        def parent(self):
            return None
        def findChildren(self, typ, *a, **k):
            try:
                from desktop.comm_manager import CommManagerDialog as CMD
                if typ is CMD or (isinstance(typ, type) and issubclass(CMD, typ)):
                    return [dlg]
            except Exception:
                pass
            return []

    win = Win()
    dlg.parent = lambda: win  # type: ignore

    bag = dlg.soft_result_okng_send_tx(judge='OK', recipe='配方轨', status_var='global.taskStatus')
    assert bag.get('tx', 0) >= 1, bag
    loop = bag.get('statusRailLoop') or {}
    assert loop.get('hostState') == 'Idle' or loop.get('railStatus') == 'ready', loop
    ok(f'OK TX loop · host={loop.get("hostState")} rail={loop.get("railStatus")} tx={bag["tx"]}')
    page = dlg.tx_status_rail_loop_strip.toPlainText()
    assert '闭环' in page or 'status rail' in page.lower() or '状态轨' in page, page
    ok(f'comm loop strip · {page.splitlines()[-1][:80]}')
    htxt = view._comm_tx_status_rail_loop_strip.text()
    assert '出站' in htxt or '闭环' in htxt or 'OK' in htxt, htxt
    ok(f'HMI status-rail loop · {htxt[:80]}')
    host_txt = host._comm_tx_status_rail_loop_strip.text()
    assert '出站' in host_txt or '闭环' in host_txt or 'OK' in host_txt or 'TX' in host_txt, host_txt
    ok(f'Host status-rail loop · {host_txt[:80]}')

    step = {
        'id': 'pt1', 'operation': 'production_task', 'name': '生产任务',
        'params': {
            'taskName': '出站闭环', 'recipe': '配方轨', 'statusVar': 'taskStatus',
            'scope': 'global',
            'chain': [{'step': '发送', 'op': 'send_data', 'vars': ''}],
        },
    }
    project['steps'] = [step]
    panel = ProductionTaskPanel(step, {}, project)
    panel.window = lambda *a, **k: win  # type: ignore
    snap = panel._soft_co_update_trial_result(
        phase='result', title='NG出站', ops=[], judge='NG',
        result={'state': 'failed', 'judge': 'NG'},
    )
    for _ in range(10):
        QCoreApplication.processEvents(); app.processEvents()
    assert snap.get('okng') == 'NG', snap
    ploop = panel._prod_tx_status_rail_loop.toPlainText()
    assert 'Alarm' in ploop or 'alarm' in ploop.lower() or 'NG' in ploop or '闭环' in ploop, ploop
    ok(f'panel NG→status-rail · {ploop.splitlines()[-1][:80]}')
    assert host._state == 'Alarm' or 'Alarm' in view._comm_tx_status_rail_loop_strip.text() or 'NG' in view._comm_tx_status_rail_loop_strip.text(), host._state
    ok(f'NG closed host={host._state}')

    print(f'\n=== {pass_n} passed, {fail_n} failed ===')
    return 0 if fail_n == 0 else 1

if __name__ == '__main__':
    rc = main()
    import os as _os
    _os._exit(rc)
