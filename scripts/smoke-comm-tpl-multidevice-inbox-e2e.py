#!/usr/bin/env python3
"""Comm messageTemplates multi-device LocalBus inbox soft timeline — no field TCP."""
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
        'commMessageTemplateDeviceList', 'commMessageTemplateInboxTimeline',
        'commMessageTemplateInboxMeta', 'commMessageTemplateFanoutBtn',
        'commMessageTemplateInboxClear', '_tpl_soft_fanout_timeline',
        '_tpl_refresh_device_list', 'multi-device LocalBus',
    ):
        (ok if needle in cm_src else bad)(
            f'comm_manager has {needle}' if needle in cm_src else f'missing {needle}'
        )

    bus = (ROOT / 'lib/comm-bus.cjs').read_text(encoding='utf-8')
    for needle in ('softFanoutTimeline', 'formatMultiDeviceInboxTimeline'):
        (ok if needle in bus else bad)(
            f'comm-bus has {needle}' if needle in bus else f'missing {needle}'
        )

    js = r'''
const bus = require('./lib/comm-bus.cjs');
bus.reset();
const r = bus.softFanoutTimeline(
  ['LocalLoop', 'PLC-A', 'VisionHost'],
  'RESULT ok=1 score=0.92',
  {template: 'OK/NG 行报文', channel: 'default'}
);
if (!r || r.devices.length !== 3) throw new Error('devices '+JSON.stringify(r));
if (!r.timeline.includes('LocalLoop') || !r.timeline.includes('PLC-A')) throw new Error('timeline '+r.timeline);
if (r.entries.length !== 3) throw new Error('entries '+r.entries.length);
const text = bus.formatMultiDeviceInboxTimeline();
if (!text.includes('multi-device') || !text.includes('VisionHost')) throw new Error('fmt '+text);
const lines = bus.getTranscript();
if (lines.length < 6) throw new Error('transcript short '+lines.length);
console.log('ENGINE_OK', r.devices.join(','), r.entries.length, lines.length);
'''
    r = subprocess.run(['node', '-e', js], cwd=str(ROOT), capture_output=True, text=True)
    if r.returncode == 0 and 'ENGINE_OK' in r.stdout:
        ok(f'engine softFanoutTimeline · {r.stdout.strip()}')
    else:
        bad(f'engine failed rc={r.returncode} out={r.stdout!r} err={r.stderr!r}')

    from PySide6.QtWidgets import QApplication, QPlainTextEdit, QListWidget, QPushButton, QLabel
    app = QApplication.instance() or QApplication([])
    from desktop.comm_manager import CommManagerDialog

    class Doc:
        def __init__(self):
            self.project = {
                'name': 'tpl-inbox-smoke',
                'steps': [],
                'edges': [],
                'variables': {
                    'global': {
                        'measureCount': 3,
                        'defectCount': 1,
                        'poseX': 10,
                        'poseY': 20,
                    },
                },
                'commManager': {
                    'devices': [
                        {'name': 'LocalLoop', 'protocol': 'Local Bus', 'host': '', 'port': 0, 'enabled': True},
                        {'name': 'PLC-A', 'protocol': 'TCP Client', 'host': '127.0.0.1', 'port': 9000, 'enabled': True},
                        {'name': 'VisionHost', 'protocol': 'Local Bus', 'host': '', 'port': 0, 'enabled': True},
                    ],
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
    ok('CommManagerDialog constructed')
    assert dlg.findChild(QListWidget, 'commMessageTemplateDeviceList') is not None
    assert dlg.findChild(QPlainTextEdit, 'commMessageTemplateInboxTimeline') is not None
    assert dlg.findChild(QPushButton, 'commMessageTemplateFanoutBtn') is not None
    ok('template fanout widgets present')

    try:
        dlg._tpl_refresh_device_list()
    except Exception as e:
        bad(f'refresh device list: {e}')
    else:
        ok(f'device list rows={dlg.tpl_device_list.count()}')

    # Select all devices for multi-device soft fan-out
    for i in range(dlg.tpl_device_list.count()):
        it = dlg.tpl_device_list.item(i)
        if it is not None:
            it.setSelected(True)
    assert dlg.tpl_device_list.count() >= 2, 'need multi-device list'
    ok(f'selected devices={ [it.text() for it in dlg.tpl_device_list.selectedItems()] }')

    # Ensure a template is selected / body filled
    if dlg.tpl_list.count() == 0:
        from desktop.comm_manager import builtin_message_templates
        dlg._tpl_load_from_project(builtin_message_templates())
    if dlg.tpl_list.count():
        dlg.tpl_list.setCurrentRow(0)
        dlg._tpl_load_form(0)
    dlg._tpl_refresh_preview()
    result = dlg._tpl_soft_fanout_timeline()
    assert result and result.get('devices'), result
    timeline = dlg.tpl_inbox_timeline.toPlainText()
    assert 'LocalBus' in timeline or 'TX→inbox' in timeline or 'multi-device' in timeline, timeline
    ok(f'fanout timeline · devices={result["devices"]} · bytes={result["bytes"]}')
    meta = dlg.tpl_inbox_meta.text()
    assert '软投递' in meta or 'LocalBus' in meta, meta
    ok(f'inbox meta · {meta}')

    dlg._tpl_clear_inbox_timeline()
    assert '空' in dlg.tpl_inbox_timeline.toPlainText() or not dlg._tpl_inbox_lines
    ok('inbox timeline cleared')

    print(f'\n=== {pass_n} passed, {fail_n} failed ===')
    return 0 if fail_n == 0 else 1

if __name__ == '__main__':
    rc = main()
    # Qt offscreen teardown can SIGSEGV after green asserts
    import os as _os
    _os._exit(rc)
