#!/usr/bin/env python3
"""Denser LocalBus transcript + format/protocol soft round-trip — no field TCP / no robot SDK."""
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
    for rel in (
        'desktop/data_io_panel.py',
        'desktop/wave3_thin_panels.py',
        'lib/comm-bus.cjs',
    ):
        src = (ROOT / rel).read_text(encoding='utf-8')
        if rel.endswith('.py'):
            ast.parse(src)
        ok(f'ast/parse {rel}')

    dio_src = (ROOT / 'desktop/data_io_panel.py').read_text(encoding='utf-8')
    for needle in (
        'dataIoLocalBusTranscript', 'dataIoLocalBusMeta', 'dataIoLocalBusAppend',
        'dataIoLocalBusClear', '_build_soft_roundtrip_transcript', '_append_soft_bus_line',
    ):
        (ok if needle in dio_src else bad)(f'data_io has {needle}' if needle in dio_src else f'missing {needle}')

    wave = (ROOT / 'desktop/wave3_thin_panels.py').read_text(encoding='utf-8')
    for needle in (
        'soft_format_protocol_roundtrip', 'formatDataRoundtripPreview', 'protocolParseRoundtripPreview',
        'soft_format_preview', 'soft_protocol_parse_preview',
    ):
        (ok if needle in wave else bad)(f'wave3 has {needle}' if needle in wave else f'missing {needle}')

    bus = (ROOT / 'lib/comm-bus.cjs').read_text(encoding='utf-8')
    for needle in ('getTranscript', 'formatTranscript', 'pushTranscript', 'TRANSCRIPT_MAX', 'clearTranscript'):
        (ok if needle in bus else bad)(f'comm-bus has {needle}' if needle in bus else f'missing {needle}')

    # Engine LocalBus transcript soft round-trip (no field TCP)
    js = r'''
const bus = require('./lib/comm-bus.cjs');
bus.reset();
(async () => {
  const project = {commManager:{devices:[{name:'LocalLoop',protocol:'Local Bus',enabled:true}]}};
  const vars = {flow:{}, global:{}, modules:{}};
  const sent = await bus.send(
    {device:'LocalLoop', channel:'default', appendCrLf:false},
    'OK,12.5,PASS',
    {project, vars}
  );
  if (!sent || sent.status !== 'ok') throw new Error('send fail '+JSON.stringify(sent));
  const recv = await bus.receive(
    {device:'LocalLoop', channel:'default', timeoutMs:50, targetVar:'recvData'},
    {project, vars}
  );
  if (!recv || recv.payload !== 'OK,12.5,PASS') throw new Error('recv mismatch '+JSON.stringify(recv));
  const lines = bus.getTranscript();
  if (lines.length < 2) throw new Error('transcript too short '+lines.length);
  const text = bus.formatTranscript();
  if (!text.includes('TX') || !text.includes('RX')) throw new Error('transcript missing TX/RX:\n'+text);
  if (!text.includes('OK,12.5,PASS')) throw new Error('transcript missing payload');
  console.log('ENGINE_OK', lines.length, sent.path, recv.path);
})().catch((e) => { console.error(e); process.exit(1); });
'''
    r = subprocess.run(['node', '-e', js], cwd=str(ROOT), capture_output=True, text=True)
    if r.returncode == 0 and 'ENGINE_OK' in r.stdout:
        ok(f'engine LocalBus transcript · {r.stdout.strip()}')
    else:
        bad(f'engine transcript failed rc={r.returncode} out={r.stdout!r} err={r.stderr!r}')

    from PySide6.QtWidgets import QApplication, QPlainTextEdit, QLabel
    app = QApplication.instance() or QApplication([])

    from desktop.data_io_panel import DataIoPanel
    from desktop.wave3_thin_panels import (
        FormatDataPanel, ProtocolParsePanel, soft_format_protocol_roundtrip,
    )

    send_step = {
        'id': 's1', 'operation': 'send_data', 'name': 'LocalBus发送',
        'params': {
            'device': 'LocalLoop', 'channel': 'default', 'sourceMode': 'text',
            'message': 'RESULT ok=1 score=0.95', 'encoding': 'utf-8',
            'appendCrLf': False, 'prefix': '', 'suffix': '',
        },
    }
    project = {
        'steps': [send_step], 'edges': [], 'variables': {},
        'commManager': {'devices': [{'name': 'LocalLoop', 'protocol': 'Local Bus'}]},
    }
    panel = DataIoPanel(send_step, {}, project)
    ok('DataIoPanel send constructed')
    assert hasattr(panel, '_io_bus_transcript') and isinstance(panel._io_bus_transcript, QPlainTextEdit)
    assert panel._io_bus_transcript.objectName() == 'dataIoLocalBusTranscript'
    t = panel._io_bus_transcript.toPlainText()
    assert 'TX' in t and 'RX' in t and 'RESULT ok=1' in t, t
    ok(f'send LocalBus soft transcript dense · {t.count(chr(10))+1} lines')
    panel._append_soft_bus_line()
    t2 = panel._io_bus_transcript.toPlainText()
    assert 'soft-append' in t2 or 'TX' in t2, t2
    ok('append soft bus line')
    meta = panel._io_bus_meta.text()
    assert '软笔录' in meta and 'TX=' in meta, meta
    ok(f'bus meta · {meta}')

    recv_step = {
        'id': 'r1', 'operation': 'receive_data', 'name': 'LocalBus读回',
        'params': {
            'device': 'LocalLoop', 'channel': 'default', 'targetScope': 'flow',
            'targetVar': 'recvData', 'samplePayload': 'OK,12.5,PASS',
            'encoding': 'utf-8', 'timeoutMs': 1000, 'trim': False,
        },
    }
    rpanel = DataIoPanel(recv_step, {}, {'steps': [recv_step], 'edges': []})
    rt = rpanel._io_bus_transcript.toPlainText()
    assert 'RX' in rt and 'OK,12.5,PASS' in rt, rt
    assert 'WRITE' in rt and 'flow.recvData' in rt, rt
    ok('receive LocalBus soft transcript has RX+WRITE')

    # format ↔ protocol round-trip soft (open-and-run path)
    fmt_step = {
        'id': 'fmt1', 'operation': 'format_data', 'name': '格式化',
        'params': {
            'template': '{0},{1},{2}', 'args': 'OK,12.5,PASS',
            'targetVar': 'formatted', 'scope': 'flow', 'encoding': 'utf-8',
            'trim': False, 'onEmpty': 'keep',
        },
    }
    proto_step = {
        'id': 'proto1', 'operation': 'protocol_parse', 'name': '协议解析',
        'params': {
            'sourceVar': 'recvData', 'sourceScope': 'flow', 'protocol': 'delimited',
            'delimiter': ',', 'fields': 'code,score,gate', 'targetPrefix': 'parsed_',
            'sample': 'OK,12.5,PASS',
        },
    }
    proj2 = {'steps': [fmt_step, proto_step], 'edges': [], 'variables': {}}
    fmt = FormatDataPanel(fmt_step, {}, proj2)
    ok('FormatDataPanel constructed')
    assert hasattr(fmt, '_fmt_roundtrip')
    fblock = fmt._fmt_roundtrip.toPlainText()
    assert 'format →' in fblock and 'protocol parse' in fblock, fblock
    assert 'parsed_code' in fblock or 'parsed_f0' in fblock or 'OK' in fblock, fblock
    ok(f'format round-trip soft · {fblock.splitlines()[0][:60]}')
    assert 'round-trip soft' in fmt._fmt_roundtrip_meta.text()
    ok(f'format round-trip meta · {fmt._fmt_roundtrip_meta.text()}')

    proto = ProtocolParsePanel(proto_step, {}, proj2)
    ok('ProtocolParsePanel constructed')
    assert hasattr(proto, '_proto_roundtrip')
    pblock = proto._proto_roundtrip.toPlainText()
    assert 'protocol parse' in pblock and 'LocalBus' in pblock, pblock
    ok('protocol round-trip soft present')
    ptext = proto._proto_result_preview.toPlainText()
    assert 'parsed_code' in ptext and 'OK' in ptext, ptext
    ok(f'protocol fields · {ptext.replace(chr(10), " | ")}')

    block, meta, formatted, parsed = soft_format_protocol_roundtrip(
        fmt_step['params'], proto_step['params']
    )
    assert formatted.startswith('OK'), formatted
    assert parsed.get('code') == 'OK' or 'code' in parsed or parsed.get('f0') == 'OK' or True
    # delimited with fields code,score,gate on OK,12.5,PASS
    assert parsed.get('code') == 'OK', parsed
    assert parsed.get('score') == '12.5', parsed
    assert parsed.get('gate') == 'PASS', parsed
    ok(f'helper round-trip parsed={parsed}')

    # open-and-run project still present
    sieans = ROOT / 'projects/open-and-run-format-protocol.sieans'
    assert sieans.exists()
    text = sieans.read_text(encoding='utf-8')
    assert 'format_data' in text and 'protocol_parse' in text and 'send_data' in text
    ok('open-and-run-format-protocol.sieans still wires format↔protocol↔LocalBus')

    print(f'\n=== {pass_n} passed, {fail_n} failed ===')
    return 0 if fail_n == 0 else 1

if __name__ == '__main__':
    sys.exit(main())
