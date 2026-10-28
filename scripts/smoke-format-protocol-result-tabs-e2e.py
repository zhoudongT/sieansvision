#!/usr/bin/env python3
"""FormatData / ProtocolParse result-tab deepen — design-time preview, no hardware."""
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
    path = ROOT / 'desktop/wave3_thin_panels.py'
    src = path.read_text(encoding='utf-8')
    ast.parse(src); ok('wave3_thin_panels ast')
    for needle in (
        'formatDataResultPreview',
        'formatDataResultMeta',
        'formatDataResultRefresh',
        '_refresh_format_result',
        'protocolParseResultPreview',
        'protocolParseResultMeta',
        'protocolParseResultRefresh',
        '_refresh_protocol_result',
    ):
        (ok if needle in src else bad)(f'has {needle}' if needle in src else f'missing {needle}')

    from PySide6.QtWidgets import QApplication, QPlainTextEdit, QLabel, QPushButton
    app = QApplication.instance() or QApplication([])

    from desktop.wave3_thin_panels import FormatDataPanel, ProtocolParsePanel

    fmt_step = {
        'id': 'fmt1', 'operation': 'format_data', 'name': '格式化',
        'params': {
            'template': 'OK={0};score={1}',
            'args': '1,0.95',
            'targetVar': 'formatted',
            'scope': 'flow',
            'encoding': 'utf-8',
            'trim': False,
            'onEmpty': 'keep',
        },
    }
    project = {'steps': [fmt_step], 'edges': [], 'variables': {}}
    fmt = FormatDataPanel(fmt_step, {}, project)
    ok('FormatDataPanel constructed')
    assert hasattr(fmt, '_fmt_result_preview') and isinstance(fmt._fmt_result_preview, QPlainTextEdit)
    assert hasattr(fmt, '_fmt_result_meta') and isinstance(fmt._fmt_result_meta, QLabel)
    text = fmt._fmt_result_preview.toPlainText()
    assert 'OK=1' in text and 'score=0.95' in text, text
    ok(f'format result preview → {text}')
    meta = fmt._fmt_result_meta.text()
    assert 'flow.formatted' in meta and 'utf-8' in meta, meta
    ok(f'format result meta → {meta}')

    fmt._set_param('template', 'PASS={0}')
    fmt._set_param('args', 'YES')
    fmt._refresh_format_result()
    text2 = fmt._fmt_result_preview.toPlainText()
    assert text2 == 'PASS=YES', text2
    ok(f'format live refresh → {text2}')

    proto_step = {
        'id': 'proto1', 'operation': 'protocol_parse', 'name': '协议解析',
        'params': {
            'sourceVar': 'recvData',
            'sourceScope': 'flow',
            'protocol': 'delimited',
            'delimiter': ',',
            'fields': 'code,score,gate',
            'targetPrefix': 'parsed_',
            'sample': 'A12,0.91,1',
            'pattern': '',
            'fixedWidths': '8,8,16',
        },
    }
    project2 = {'steps': [proto_step], 'edges': [], 'variables': {}}
    proto = ProtocolParsePanel(proto_step, {}, project2)
    ok('ProtocolParsePanel constructed')
    assert hasattr(proto, '_proto_result_preview')
    ptext = proto._proto_result_preview.toPlainText()
    assert 'parsed_code' in ptext and 'A12' in ptext, ptext
    assert 'parsed_score' in ptext and '0.91' in ptext, ptext
    assert 'parsed_gate' in ptext, ptext
    ok(f'protocol delimited preview → {ptext.replace(chr(10), " | ")}')
    pmeta = proto._proto_result_meta.text()
    assert 'flow.recvData' in pmeta and 'delimited' in pmeta, pmeta
    ok(f'protocol result meta → {pmeta}')

    proto._set_param('protocol', 'json')
    proto._set_param('sample', '{"code":"B","ok":1}')
    proto._refresh_protocol_result()
    jtext = proto._proto_result_preview.toPlainText()
    assert 'parsed_code' in jtext and 'B' in jtext, jtext
    assert 'parsed_ok' in jtext, jtext
    ok(f'protocol json preview → {jtext.replace(chr(10), " | ")}')

    proto._set_param('protocol', 'fixed')
    proto._set_param('fixedWidths', '3,4,2')
    proto._set_param('fields', 'a,b,c')
    proto._set_param('sample', 'ABCxxxxOK')
    proto._refresh_protocol_result()
    ftext = proto._proto_result_preview.toPlainText()
    assert 'parsed_a' in ftext and 'ABC' in ftext, ftext
    ok(f'protocol fixed preview → {ftext.replace(chr(10), " | ")}')

    # objectName smoke for UI hooks
    assert fmt._fmt_result_preview.objectName() == 'formatDataResultPreview'
    assert proto._proto_result_preview.objectName() == 'protocolParseResultPreview'
    ok('objectNames wired')

    print(f'\n=== {pass_n} passed, {fail_n} failed ===')
    return 0 if fail_n == 0 else 1

if __name__ == '__main__':
    sys.exit(main())
