#!/usr/bin/env python3
"""Host SM liaison timeline ↔ Comm sendEvents ack/response page co-bind — no field TCP."""
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
        'desktop/host_state_machine.py',
    ):
        src = (ROOT / rel).read_text(encoding='utf-8')
        if rel != 'desktop/host_state_machine.py':
            ast.parse(src)
        ok(f'ast/parse-or-read {rel}')

    cm = (ROOT / 'desktop/comm_manager.py').read_text(encoding='utf-8')
    for needle in (
        'commLiaisonSendAckResponseCoBindStrip', 'commLiaisonSendAckResponseCoBindBtn',
        'soft_co_bind_liaison_send_ack_response',
    ):
        (ok if needle in cm else bad)(f'comm has {needle}' if needle in cm else f'missing {needle}')

    hmi_src = (ROOT / 'desktop/operator_hmi.py').read_text(encoding='utf-8')
    for needle in (
        'hmiLiaisonSendAckResponseCoBindStrip', 'co_bind_liaison_send_ack_response',
    ):
        (ok if needle in hmi_src else bad)(f'hmi has {needle}' if needle in hmi_src else f'missing {needle}')

    host_src = (ROOT / 'desktop/host_state_machine.py').read_text(encoding='utf-8')
    for needle in (
        'hostLiaisonSendAckResponseCoBindStrip', 'co_bind_liaison_send_ack_response',
        'set_liaison_send_ack_cobind_strip',
    ):
        (ok if needle in host_src else bad)(f'host has {needle}' if needle in host_src else f'missing {needle}')

    from PySide6.QtWidgets import QApplication, QWidget
    app = QApplication.instance() or QApplication([])

    from desktop.comm_manager import CommManagerDialog
    from desktop.operator_hmi import OperatorHmiView
    from desktop.host_state_machine import HostStateMachineWidget

    class Doc:
        def __init__(self, project):
            self.project = project
        def mark_dirty(self):
            pass

    project = {
        'name': 'liaison-ack-cobind-smoke',
        'steps': [], 'edges': [],
        'variables': {'global': {'taskStatus': 'ready'}, 'flow': {}},
        'commManager': {
            'devices': [{'name': 'LocalLoop', 'protocol': 'Local Bus', 'enabled': True}],
            'recvEvents': [],
            'sendEvents': [
                {'name': 'ackResp', 'device': 'LocalLoop',
                 'message': 'ACK okng=${flow.okng} ack=${flow.ack} recipe=${flow.recipe}'},
            ],
            'response': {'enabled': True, 'timeoutMs': 3000, 'ack': 'ACK_OK'},
            'heartbeat': {'enabled': False},
        },
    }
    doc = Doc(project)

    class HostWin(QWidget):
        def __init__(self):
            super().__init__()
            self.operator_hmi = None
            self.host_state_machine = None
            self.host_sm = None

    win = HostWin()
    host = HostStateMachineWidget(parent=win)
    hmi = OperatorHmiView(parent=win)
    win.host_state_machine = host
    win.host_sm = host
    win.operator_hmi = hmi
    try:
        hmi._host_sm = host
    except Exception:
        pass

    dlg = CommManagerDialog(doc, parent=win)
    # Ensure response widgets
    if hasattr(dlg, 'resp_ack'):
        dlg.resp_ack.setText('ACK_OK')
    if hasattr(dlg, 'resp_enabled'):
        dlg.resp_enabled.setChecked(True)

    bag = dlg.soft_co_bind_liaison_send_ack_response(
        judge='OK', recipe='配方联调A', status_var='global.taskStatus',
    )
    if bag.get('tx', 0) >= 1 and bag.get('ack') == 'ACK_OK':
        ok(f"soft cobind OK tx={bag.get('tx')} ack={bag.get('ack')} host={bag.get('hostState')}")
    else:
        bad(f'cobind OK bag unexpected: {bag}')

    strip = getattr(dlg, 'liaison_ack_cobind_strip', None)
    txt = strip.toPlainText() if strip is not None else ''
    if 'liaison timeline' in txt.lower() or '联调' in txt or 'ack/response' in txt.lower() or 'sendEvents' in txt:
        ok('comm page strip filled')
    else:
        bad(f'comm strip empty/unexpected: {txt[:120]!r}')

    host_lab = getattr(host, '_liaison_send_ack_cobind_strip', None)
    if host_lab is not None and ('应答' in host_lab.text() or '联调' in host_lab.text() or 'ACK' in host_lab.text()):
        ok(f'host strip: {host_lab.text()[:80]}')
    else:
        bad(f'host strip missing/empty: {getattr(host_lab, "text", lambda: None)()!r}')

    hmi_lab = getattr(hmi, '_liaison_send_ack_cobind_strip', None)
    if hmi_lab is not None and ('应答' in hmi_lab.text() or '联调' in hmi_lab.text() or 'ACK' in hmi_lab.text()):
        ok(f'hmi strip: {hmi_lab.text()[:80]}')
    else:
        bad(f'hmi strip missing: {getattr(hmi_lab, "text", lambda: None)()!r}')

    # NG path
    bag2 = dlg.soft_co_bind_liaison_send_ack_response(judge='NG', recipe='配方联调A', ack='ACK_NG')
    if bag2.get('hostState') == 'Alarm' and bag2.get('okng') == 'NG':
        ok(f"NG cobind host=Alarm liaison={bag2.get('liaison')}")
    else:
        bad(f'NG cobind unexpected: {bag2}')

    # Liaison events landed
    try:
        evs = list(host.liaison_events() or [])
    except Exception:
        evs = list(getattr(host, '_liaison_events', []) or [])
    codes = [str(e.get('code') or '') for e in evs]
    if any('ACK_' in c for c in codes):
        ok(f'liaison events have ACK codes: {codes[-4:]}')
    else:
        bad(f'no ACK liaison codes: {codes[-6:]}')

    print(f'\nRESULT {pass_n} pass / {fail_n} fail')
    return 0 if fail_n == 0 else 1

if __name__ == '__main__':
    sys.exit(main())
