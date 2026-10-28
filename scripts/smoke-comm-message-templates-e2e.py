#!/usr/bin/env python3
"""Comm 消息模板 tab + ${} expand demo — no field TCP device / no robot SDK."""
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
    cm_path = ROOT / 'desktop/comm_manager.py'
    src = cm_path.read_text(encoding='utf-8')
    ast.parse(src); ok('comm_manager ast')
    for needle in (
        'DEFAULT_MESSAGE_TEMPLATES',
        'commMessageTemplateList',
        'commMessageTemplatePreview',
        'preview_expand_template',
        'messageTemplates=self._tpl_collect',
        'udpProtocolPreset',
        '消息模板',
    ):
        (ok if needle in src else bad)(f'has {needle}' if needle in src else f'missing {needle}')

    from desktop.comm_manager import (
        DEFAULT_MESSAGE_TEMPLATES, merge_message_templates,
        preview_expand_template, expand_payload_placeholders,
        builtin_message_templates, CommManagerDialog,
    )
    assert len(DEFAULT_MESSAGE_TEMPLATES) >= 6
    ok(f'builtin templates={len(DEFAULT_MESSAGE_TEMPLATES)}')

    merged = merge_message_templates([
        {'id': 'result-line', 'name': '覆盖行', 'body': 'X=${flow.passGate}', 'protocol': 'line'},
        {'id': 'custom-a', 'name': '自定义A', 'body': 'A=${flow.matchScore}', 'protocol': 'line'},
    ])
    by_id = {t['id']: t for t in merged}
    assert by_id['result-line']['name'] == '覆盖行'
    assert 'custom-a' in by_id
    ok('merge_message_templates override+custom')

    expanded = preview_expand_template(
        {'variables': {}},
        'RESULT ok=${flow.passGate} score=${flow.matchScore}',
        demo_vars={'passGate': 1, 'matchScore': 0.91},
    )
    assert expanded == 'RESULT ok=1 score=0.91', expanded
    ok(f'preview_expand demo → {expanded}')

    expanded2 = expand_payload_placeholders(
        {'variables': {'passGate': 0, 'matchScore': 0.5}},
        'ok=${flow.passGate};s=${matchScore}',
    )
    assert 'ok=0' in expanded2 and 's=0.5' in expanded2, expanded2
    ok(f'expand real vars → {expanded2}')

    from PySide6.QtWidgets import QApplication, QListWidget, QPlainTextEdit, QPushButton
    app = QApplication.instance() or QApplication([])

    class Doc:
        def __init__(self):
            self.project = {
                'variables': {
                    'passGate': 1,
                    'matchScore': 0.88,
                    'matchCount': 2,
                    'measureCount': 3,
                    'defectCount': 1,
                    'poseX': 10,
                    'poseY': 20,
                },
                'commManager': {
                    'devices': [{'name': 'LocalLoop', 'protocol': 'Local Bus', 'host': '', 'port': 0, 'enabled': True}],
                    'recvEvents': [],
                    'sendEvents': [],
                    'heartbeat': {'enabled': False, 'intervalMs': 5000, 'payload': 'HB'},
                    'response': {'enabled': False, 'timeoutMs': 3000, 'ack': 'OK'},
                    'messageTemplates': [],
                },
            }
            self._commits = []
        def commit(self, p):
            self.project = p
            self._commits.append(p)

    doc = Doc()
    dlg = CommManagerDialog(doc)
    # find 消息模板 tab
    tabs = dlg.tabs
    titles = [tabs.tabText(i) for i in range(tabs.count())]
    if '消息模板' in titles:
        ok(f'tabs include 消息模板 @ {titles.index("消息模板")}')
        tabs.setCurrentIndex(titles.index('消息模板'))
    else:
        bad(f'no 消息模板 tab in {titles}')

    lst = dlg.findChild(QListWidget, 'commMessageTemplateList')
    assert lst is not None and lst.count() >= 6
    ok(f'template list count={lst.count()}')

    prev = dlg.findChild(QPlainTextEdit, 'commMessageTemplatePreview')
    assert prev is not None
    dlg._tpl_refresh_preview()
    text = prev.toPlainText()
    assert text, 'empty preview'
    ok(f'preview non-empty len={len(text)}')

    # apply to send event
    before = len(dlg.send_table.rows())
    dlg._tpl_apply_to_send_event()
    after = len(dlg.send_table.rows())
    assert after == before + 1
    ok(f'apply→sendEvents {before}→{after}')

    # apply to tcp
    dlg._tpl_apply_to_test('tcp')
    assert dlg.tcp_payload.text()
    ok(f'tcp payload filled={dlg.tcp_payload.text()[:40]}…')

    # UDP preset object
    assert hasattr(dlg, 'udp_preset')
    dlg.udp_preset.setCurrentIndex(1)  # PING
    dlg._udp_preset_apply()
    assert dlg.udp_payload.text() == 'PING'
    ok('udp preset → PING')

    # persist via accept_save path (_tpl_collect)
    collected = dlg._tpl_collect()
    assert isinstance(collected, list) and len(collected) >= 6
    ok(f'_tpl_collect n={len(collected)}')

    # sample project has messageTemplates
    sample = ROOT / 'projects/open-and-run-locate-measure-defect.sieans'
    import json
    proj = json.loads(sample.read_text(encoding='utf-8'))
    mt = (proj.get('commManager') or {}).get('messageTemplates') or []
    assert mt, 'sample missing messageTemplates'
    ok(f'sample messageTemplates={len(mt)}')

    print(f'\n{pass_n} PASS / {fail_n} FAIL')
    sys.exit(1 if fail_n else 0)

if __name__ == '__main__':
    main()
