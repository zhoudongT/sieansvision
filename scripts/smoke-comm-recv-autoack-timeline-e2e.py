#!/usr/bin/env python3
"""Comm recvEvents ↔ LocalBus soft auto-ack / grouped reply timeline — no field TCP."""
from __future__ import annotations
import ast
import os
import subprocess
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
    for rel in ('desktop/comm_manager.py', 'lib/comm-bus.cjs'):
        src = (ROOT / rel).read_text(encoding='utf-8')
        if rel.endswith('.py'):
            ast.parse(src)
        ok(f'ast/parse {rel}')

    cm_src = (ROOT / 'desktop/comm_manager.py').read_text(encoding='utf-8')
    for needle in (
        'commRecvAutoAckTimeline', 'commRecvAutoAckMeta', 'commRecvAutoAckBtn',
        'commRecvAutoAckClear', 'commRecvAutoAckPayload',
        '_soft_recv_auto_ack_timeline', '_format_grouped_ack_timeline',
    ):
        (ok if needle in cm_src else bad)(
            f'comm_manager has {needle}' if needle in cm_src else f'missing {needle}'
        )

    bus = (ROOT / 'lib/comm-bus.cjs').read_text(encoding='utf-8')
    for needle in ('softAutoAckFromRecvEvents', 'formatGroupedReplyTimeline', 'autoAck-reply'):
        (ok if needle in bus else bad)(
            f'comm-bus has {needle}' if needle in bus else f'missing {needle}'
        )

    js = r'''
const bus = require('./lib/comm-bus.cjs');
bus.reset();
const proj = {
  commManager: {
    devices: [
      {name:'LocalLoop', protocol:'Local Bus'},
      {name:'PLC-A', protocol:'TCP Client'},
    ],
    recvEvents: [
      {device:'LocalLoop', variable:'flow.lastRecv'},
      {device:'PLC-A', variable:'global.plcRecv'},
    ],
    response: {enabled:true, timeoutMs:3000, ack:'ACK_OK'},
  }
};
const r = bus.softAutoAckFromRecvEvents(proj, 'RESULT ok=1', {forceAck:true, ack:'ACK_OK'});
if (!r || r.devices.length !== 2) throw new Error('devices '+JSON.stringify(r&&r.devices));
if (!r.ackEnabled) throw new Error('ackEnabled');
if (!r.grouped.includes('LocalLoop') || !r.grouped.includes('ACK')) throw new Error('grouped '+r.grouped);
const g2 = bus.formatGroupedReplyTimeline();
if (!g2.includes('auto-ack') && !g2.includes('ACK')) throw new Error('fmt '+g2);
console.log('ENGINE_OK', r.devices.join(','), r.entries.length);
'''
    r = subprocess.run(['node', '-e', js], cwd=str(ROOT), capture_output=True, text=True)
    if r.returncode == 0 and 'ENGINE_OK' in r.stdout:
        ok(f'engine softAutoAck · {r.stdout.strip()}')
    else:
        bad(f'engine failed rc={r.returncode} out={r.stdout!r} err={r.stderr!r}')

    from PySide6.QtWidgets import QApplication, QPlainTextEdit, QPushButton, QLabel, QLineEdit
    app = QApplication.instance() or QApplication([])
    from desktop.comm_manager import CommManagerDialog

    class Doc:
        def __init__(self):
            self.project = {
                'name': 'autoack-smoke',
                'steps': [], 'edges': [],
                'variables': {'global': {}, 'flow': {}},
                'commManager': {
                    'devices': [
                        {'name': 'LocalLoop', 'protocol': 'Local Bus', 'host': '', 'port': 0, 'enabled': True},
                        {'name': 'PLC-A', 'protocol': 'TCP Client', 'host': '127.0.0.1', 'port': 9000, 'enabled': True},
                        {'name': 'VisionHost', 'protocol': 'Local Bus', 'host': '', 'port': 0, 'enabled': True},
                    ],
                    'recvEvents': [
                        {'name': '收PLC', 'device': 'PLC-A', 'variable': 'flow.plcMsg', 'topic': ''},
                        {'name': '收Vision', 'device': 'VisionHost', 'variable': 'flow.visMsg', 'topic': ''},
                        {'name': '收Loop', 'device': 'LocalLoop', 'variable': 'flow.loopMsg', 'topic': ''},
                    ],
                    'sendEvents': [],
                    'heartbeat': {'enabled': False, 'intervalMs': 5000, 'payload': 'HB'},
                    'response': {'enabled': True, 'timeoutMs': 3000, 'ack': 'ACK_OK'},
                    'messageTemplates': [],
                },
            }
            self._commits = []
        def commit(self, p):
            self.project = p
            self._commits.append(p)

    doc = Doc()
    dlg = CommManagerDialog(doc)
    ok('CommManagerDialog constructed')
    assert dlg.findChild(QPlainTextEdit, 'commRecvAutoAckTimeline') is not None
    assert dlg.findChild(QPushButton, 'commRecvAutoAckBtn') is not None
    assert dlg.findChild(QLineEdit, 'commRecvAutoAckPayload') is not None
    ok('auto-ack widgets present')

    # Ensure response enabled + ack
    try:
        dlg.resp_enabled.setChecked(True)
    except Exception:
        pass
    dlg.resp_ack.setText('ACK_OK')
    dlg.ack_demo_payload.setText('RESULT ok=1 score=0.95')

    result = dlg._soft_recv_auto_ack_timeline()
    assert result and result.get('devices'), result
    assert len(result['devices']) >= 2, result
    timeline = dlg.ack_reply_timeline.toPlainText()
    assert 'auto-ack' in timeline or 'TX→ack' in timeline or 'ACK' in timeline, timeline
    assert 'PLC-A' in timeline or 'LocalLoop' in timeline, timeline
    ok(f'auto-ack timeline · devices={result["devices"]} · ack={result["ack"]}')
    meta = dlg.ack_reply_meta.text()
    assert '软收' in meta or 'LocalBus' in meta, meta
    ok(f'auto-ack meta · {meta}')

    # Grouped view has ▶ device headers
    assert '▶' in timeline, timeline
    ok('grouped reply headers present')

    dlg._clear_recv_auto_ack_timeline()
    assert '空' in dlg.ack_reply_timeline.toPlainText() or not dlg._ack_reply_lines
    ok('auto-ack timeline cleared')

    print(f'\n=== {pass_n} passed, {fail_n} failed ===')
    return 0 if fail_n == 0 else 1

if __name__ == '__main__':
    rc = main()
    import os as _os
    _os._exit(rc)
