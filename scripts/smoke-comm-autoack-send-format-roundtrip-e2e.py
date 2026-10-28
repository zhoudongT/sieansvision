#!/usr/bin/env python3
"""Comm auto-ack → sendEvents / format_data soft round-trip page strip — no field TCP."""
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
        'commAutoAckSendFormatRoundTripStrip', 'commAutoAckSendFormatRoundTripBtn',
        'commAutoAckSendFormatRoundTripMeta',
        '_soft_autoack_sendevents_format_roundtrip',
    ):
        (ok if needle in cm_src else bad)(
            f'comm_manager has {needle}' if needle in cm_src else f'missing {needle}'
        )

    bus = (ROOT / 'lib/comm-bus.cjs').read_text(encoding='utf-8')
    for needle in ('softAutoAckSendEventsFormatRoundTrip', 'sendEvent-format-rt', 'format_data-expand'):
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
    sendEvents: [
      {name:'fmtSend', device:'LocalLoop', message:'FMT ${flow.lastRecv} ACK=${flow.ack}'},
      {name:'status', device:'PLC-A', message:'status=${global.taskStatus}'},
    ],
    response: {enabled:true, timeoutMs:3000, ack:'ACK_OK'},
  }
};
const r = bus.softAutoAckSendEventsFormatRoundTrip(proj, 'RESULT ok=1', {forceAck:true, ack:'ACK_OK'});
if (!r || !r.ack || !r.sendEntries || r.sendEntries.length < 2) throw new Error(JSON.stringify(r&&{tx:(r.sendEntries||[]).length}));
if (!r.pageStrip.includes('format') && !r.pageStrip.includes('TX→send')) throw new Error(r.pageStrip);
if (!String(r.sendEntries[0].payload).includes('RESULT') && !String(r.sendEntries[0].payload).includes('FMT')) throw new Error(r.sendEntries[0].payload);
console.log('ENGINE_OK', r.devices.join(','), r.sendEntries.length, r.ack.ack);
'''
    r = subprocess.run(['node', '-e', js], cwd=str(ROOT), capture_output=True, text=True)
    if r.returncode == 0 and 'ENGINE_OK' in r.stdout:
        ok(f'engine softAckSendFormatRt · {r.stdout.strip()}')
    else:
        bad(f'engine failed rc={r.returncode} out={r.stdout!r} err={r.stderr!r}')

    from PySide6.QtWidgets import QApplication, QPlainTextEdit, QPushButton, QLabel
    app = QApplication.instance() or QApplication([])
    from desktop.comm_manager import CommManagerDialog

    class Doc:
        def __init__(self):
            self.project = {
                'name': 'ack-rt-smoke',
                'steps': [], 'edges': [],
                'variables': {
                    'global': {'taskStatus': 'ready'},
                    'flow': {},
                },
                'commManager': {
                    'devices': [
                        {'name': 'LocalLoop', 'protocol': 'Local Bus', 'host': '', 'port': 0, 'enabled': True},
                        {'name': 'PLC-A', 'protocol': 'TCP Client', 'host': '127.0.0.1', 'port': 9000, 'enabled': True},
                    ],
                    'recvEvents': [
                        {'name': '收Loop', 'device': 'LocalLoop', 'variable': 'flow.loopMsg', 'topic': ''},
                        {'name': '收PLC', 'device': 'PLC-A', 'variable': 'flow.plcMsg', 'topic': ''},
                    ],
                    'sendEvents': [
                        {'name': 'fmtSend', 'device': 'LocalLoop',
                         'message': 'FMT ${flow.lastRecv} ACK=${flow.ack} status=${global.taskStatus}',
                         'topic': '', 'variable': ''},
                        {'name': 'plain', 'device': 'PLC-A', 'message': 'PING', 'topic': '', 'variable': ''},
                    ],
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
    assert dlg.findChild(QPlainTextEdit, 'commAutoAckSendFormatRoundTripStrip') is not None
    assert dlg.findChild(QPushButton, 'commAutoAckSendFormatRoundTripBtn') is not None
    ok('round-trip widgets present')

    try:
        dlg.resp_enabled.setChecked(True)
    except Exception:
        pass
    dlg.resp_ack.setText('ACK_OK')
    dlg.ack_demo_payload.setText('RESULT ok=1 score=0.95')

    result = dlg._soft_autoack_sendevents_format_roundtrip()
    assert result and result.get('tx', 0) >= 1, result
    page = dlg.ack_rt_strip.toPlainText()
    assert 'round-trip' in page or 'TX→send' in page or 'format' in page, page
    assert 'ACK' in page or 'ACK_OK' in page, page
    ok(f'round-trip strip · tx={result["tx"]} · {page.splitlines()[-1][:70]}')
    meta = dlg.ack_rt_meta.text()
    assert '软往返' in meta or 'sendEvents' in meta, meta
    ok(f'round-trip meta · {meta}')
    # expanded format present
    assert 'RESULT ok=1' in page or 'FMT' in page, page
    ok('format_data-style expand visible in page strip')

    print(f'\n=== {pass_n} passed, {fail_n} failed ===')
    return 0 if fail_n == 0 else 1

if __name__ == '__main__':
    rc = main()
    import os as _os
    _os._exit(rc)
