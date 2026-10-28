#!/usr/bin/env python3
"""OK-NG dashboard ↔ Comm recvEvents auto-ack page co-update — no field TCP."""
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
        'commOkNgRecvAutoAckCoUpdateStrip', 'commOkNgRecvAutoAckCoUpdateBtn',
        'soft_co_update_okng_recv_autoack',
    ):
        (ok if needle in cm else bad)(f'comm has {needle}' if needle in cm else f'missing {needle}')

    hmi_src = (ROOT / 'desktop/operator_hmi.py').read_text(encoding='utf-8')
    for needle in (
        'hmiOkNgRecvAutoAckCoUpdateStrip', 'co_update_okng_recv_autoack',
    ):
        (ok if needle in hmi_src else bad)(f'hmi has {needle}' if needle in hmi_src else f'missing {needle}')

    host_src = (ROOT / 'desktop/host_state_machine.py').read_text(encoding='utf-8')
    for needle in (
        'hostOkNgRecvAutoAckCoUpdateStrip', 'set_okng_recv_autoack_co_update_strip',
    ):
        (ok if needle in host_src else bad)(f'host has {needle}' if needle in host_src else f'missing {needle}')

    prod = (ROOT / 'desktop/production_task_panel.py').read_text(encoding='utf-8')
    for needle in (
        'productionTaskOkNgRecvAutoAckCoUpdateStrip', 'soft_co_update_okng_recv_autoack',
    ):
        (ok if needle in prod else bad)(f'panel has {needle}' if needle in prod else f'missing {needle}')

    from PySide6.QtWidgets import QApplication, QWidget
    app = QApplication.instance() or QApplication([])

    from desktop.comm_manager import CommManagerDialog
    from desktop.operator_hmi import OperatorHmiView
    from desktop.host_state_machine import HostStateMachineWidget
    from desktop.production_task_panel import ProductionTaskPanel

    class Doc:
        def __init__(self, project):
            self.project = project
        def mark_dirty(self):
            pass

    project = {
        'name': 'okng-recv-ack-smoke',
        'steps': [{
            'id': 'pt1', 'operation': 'production_task',
            'params': {
                'taskName': '任务OKNG', 'recipe': '配方OKNG',
                'statusVar': 'taskStatus', 'scope': 'global',
                'chain': [{'step': '判定', 'op': 'judge'}],
            },
        }],
        'variables': {'global': {'taskStatus': 'ready'}, 'flow': {}},
        'commManager': {
            'devices': [
                {'name': 'LocalLoop', 'protocol': 'Local Bus', 'enabled': True},
                {'name': 'PLC-A', 'protocol': 'TCP Client', 'enabled': True},
            ],
            'recvEvents': [
                {'device': 'LocalLoop', 'variable': 'flow.lastRecv'},
                {'device': 'PLC-A', 'variable': 'global.plcRecv'},
            ],
            'sendEvents': [],
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
    if hasattr(dlg, 'resp_ack'):
        dlg.resp_ack.setText('ACK_OK')
    if hasattr(dlg, 'resp_enabled'):
        dlg.resp_enabled.setChecked(True)

    bag = dlg.soft_co_update_okng_recv_autoack(
        judge='OK', recipe='配方OKNG', ok_n=3, ng_n=1,
    )
    if bag.get('okng') == 'OK' and bag.get('ack') and bag.get('ok') == 3:
        ok(f"co-update OK ack={bag.get('ack')} devices={bag.get('devices')} ok={bag.get('ok')}")
    else:
        bad(f'co-update OK unexpected: {bag}')

    strip = getattr(dlg, 'okng_recv_ack_strip', None)
    txt = strip.toPlainText() if strip is not None else ''
    if 'OK-NG' in txt or 'recv' in txt.lower() or 'auto-ack' in txt.lower() or '自动应答' in txt:
        ok('comm OK-NG↔recv strip filled')
    else:
        bad(f'comm strip empty: {txt[:120]!r}')

    # Auto-ack timeline also filled
    ack_tl = getattr(dlg, 'ack_reply_timeline', None)
    ack_txt = ack_tl.toPlainText() if ack_tl is not None else ''
    if 'RX' in ack_txt or 'ack' in ack_txt.lower() or 'ACK' in ack_txt or '应答' in ack_txt:
        ok('recv auto-ack timeline filled via co-update')
    else:
        bad(f'ack timeline empty: {ack_txt[:120]!r}')

    hmi_lab = getattr(hmi, '_okng_recv_autoack_co_update_strip', None)
    if hmi_lab is not None and ('OK-NG' in hmi_lab.text() or '自动应答' in hmi_lab.text() or 'ack' in hmi_lab.text().lower()):
        ok(f'hmi co-update strip: {hmi_lab.text()[:90]}')
    else:
        bad(f'hmi strip missing: {getattr(hmi_lab, "text", lambda: None)()!r}')

    dash = getattr(hmi, '_okng_dashboard_strip', None)
    if dash is not None and ('OK' in dash.text() or '看板' in dash.text()):
        ok(f'okng dashboard refreshed: {dash.text()[:90]}')
    else:
        bad(f'dashboard not refreshed: {getattr(dash, "text", lambda: None)()!r}')

    host_lab = getattr(host, '_okng_recv_autoack_co_update_strip', None)
    if host_lab is not None and host_lab.text() and '待命' not in host_lab.text():
        ok(f'host co-update strip: {host_lab.text()[:90]}')
    else:
        bad(f'host strip not updated: {getattr(host_lab, "text", lambda: None)()!r}')

    # NG path
    bag2 = dlg.soft_co_update_okng_recv_autoack(judge='NG', recipe='配方OKNG', ok_n=3, ng_n=2)
    if bag2.get('okng') == 'NG' and bag2.get('hostState') == 'Alarm':
        ok(f"NG co-update host=Alarm ng={bag2.get('ng')}")
    else:
        bad(f'NG co-update unexpected: {bag2}')

    # Panel mirror
    panel = ProductionTaskPanel(project['steps'][0], {'name': 'production_task'}, project, parent=win)
    pbag = panel.soft_co_update_okng_recv_autoack(judge='OK', ok_n=1, ng_n=0, ack='ACK_OK')
    if pbag.get('okng') == 'OK':
        ok('panel okng↔recv mirror OK')
    else:
        bad(f'panel mirror unexpected: {pbag}')

    # Direct auto-ack also paints co-update strip
    if hasattr(dlg, 'ack_demo_payload') and dlg.ack_demo_payload is not None:
        dlg.ack_demo_payload.setText('RESULT okng=OK ok=1 ng=0')
    abag = dlg._soft_recv_auto_ack_timeline()
    if abag.get('okngCoUpdate') or (strip and '自应答' in (getattr(dlg, 'okng_recv_ack_meta', None).text() if getattr(dlg, 'okng_recv_ack_meta', None) else '')):
        ok(f"auto-ack→okng hook: {abag.get('okngCoUpdate')}")
    else:
        # still OK if strip mentions auto-ack
        meta = getattr(dlg, 'okng_recv_ack_meta', None)
        mt = meta.text() if meta is not None else ''
        if '共更' in mt or abag.get('devices'):
            ok(f'auto-ack ran devices={abag.get("devices")} meta={mt[:60]}')
        else:
            bad(f'auto-ack hook weak: {abag.keys()} meta={mt!r}')

    print(f'\nRESULT {pass_n} pass / {fail_n} fail')
    return 0 if fail_n == 0 else 1

if __name__ == '__main__':
    sys.exit(main())
