#!/usr/bin/env python3
"""production_task result OK/NG → Comm sendEvents soft TX page strip — LocalBus only; no field TCP."""
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
        'desktop/production_task_panel.py',
        'desktop/comm_manager.py',
        'lib/comm-bus.cjs',
    ):
        src = (ROOT / rel).read_text(encoding='utf-8')
        if rel.endswith('.py'):
            ast.parse(src)
        ok(f'ast/parse {rel}')

    prod = (ROOT / 'desktop/production_task_panel.py').read_text(encoding='utf-8')
    for needle in (
        'productionTaskResultOkNgCommTxStrip', 'productionTaskResultOkNgCommTxMeta',
        '_soft_result_okng_comm_send_tx',
    ):
        (ok if needle in prod else bad)(
            f'panel has {needle}' if needle in prod else f'missing {needle}'
        )

    cm_src = (ROOT / 'desktop/comm_manager.py').read_text(encoding='utf-8')
    for needle in (
        'commResultOkNgSendTxStrip', 'commResultOkNgSendTxBtn',
        'commResultOkNgSendTxMeta', 'soft_result_okng_send_tx',
    ):
        (ok if needle in cm_src else bad)(
            f'comm has {needle}' if needle in cm_src else f'missing {needle}'
        )

    bus = (ROOT / 'lib/comm-bus.cjs').read_text(encoding='utf-8')
    for needle in ('softResultOkNgSendEventsTx', 'result-okng-send', 'TX→result'):
        (ok if needle in bus else bad)(
            f'bus has {needle}' if needle in bus else f'missing {needle}'
        )

    js = r'''
const bus = require('./lib/comm-bus.cjs');
bus.reset();
const proj = {
  commManager: {
    devices: [{name:'LocalLoop', protocol:'Local Bus'}],
    sendEvents: [
      {name:'fmt', device:'LocalLoop', message:'RESULT okng=${flow.okng} ok=${flow.resultOk} recipe=${flow.recipe}'},
      {name:'st', device:'LocalLoop', message:'status=${flow.taskStatus}'},
    ],
  }
};
const r = bus.softResultOkNgSendEventsTx(proj, 'OK', {recipe:'配方TX', taskStatus:'ready'});
if (!r || !r.sendEntries || r.sendEntries.length < 2) throw new Error(JSON.stringify(r));
if (r.resultOk !== 1) throw new Error('resultOk');
if (!String(r.sendEntries[0].payload).includes('OK')) throw new Error(r.sendEntries[0].payload);
if (!r.pageStrip.includes('sendEvents soft TX')) throw new Error(r.pageStrip);
const ng = bus.softResultOkNgSendEventsTx(proj, 'NG', {recipe:'配方TX'});
if (ng.resultOk !== 0 || ng.resultNg !== 1) throw new Error(JSON.stringify(ng));
console.log('ENGINE_OK', r.devices.join(','), r.sendEntries.length, ng.okng);
'''
    r = subprocess.run(['node', '-e', js], cwd=str(ROOT), capture_output=True, text=True)
    if r.returncode == 0 and 'ENGINE_OK' in r.stdout:
        ok(f'engine softResultOkNgTx · {r.stdout.strip()}')
    else:
        bad(f'engine failed rc={r.returncode} out={r.stdout!r} err={r.stderr!r}')

    from PySide6.QtWidgets import QApplication, QPlainTextEdit, QPushButton, QLabel
    app = QApplication.instance() or QApplication([])

    from desktop.production_task_panel import ProductionTaskPanel
    from desktop.comm_manager import CommManagerDialog

    step = {
        'id': 'pt1', 'operation': 'production_task', 'name': '生产任务',
        'params': {
            'taskName': '结果出站任务',
            'recipe': '配方TX',
            'statusVar': 'taskStatus',
            'scope': 'global',
            'autoStart': False,
            'chain': [
                {'step': '读取图像', 'op': '图像源', 'vars': ''},
                {'step': '模板匹配', 'op': 'locate', 'vars': ''},
                {'step': '发送上位机', 'op': 'send_data / format_data', 'vars': ''},
            ],
        },
    }
    project = {
        'name': 'okng-tx-smoke',
        'steps': [step], 'edges': [],
        'variables': {'global': {'taskStatus': 'ready'}, 'flow': {}},
        'commManager': {
            'devices': [
                {'name': 'LocalLoop', 'protocol': 'Local Bus', 'host': '', 'port': 0, 'enabled': True},
            ],
            'recvEvents': [],
            'sendEvents': [
                {'name': 'fmt', 'device': 'LocalLoop',
                 'message': 'RESULT okng=${flow.okng} ok=${flow.resultOk} recipe=${flow.recipe}',
                 'topic': '', 'variable': ''},
                {'name': 'st', 'device': 'LocalLoop', 'message': 'status=${flow.taskStatus}',
                 'topic': '', 'variable': ''},
            ],
            'heartbeat': {'enabled': False, 'intervalMs': 5000, 'payload': 'HB'},
            'response': {'enabled': True, 'timeoutMs': 3000, 'ack': 'ACK_OK'},
            'messageTemplates': [],
        },
    }
    panel = ProductionTaskPanel(step, {}, project)
    ok('ProductionTaskPanel constructed')
    assert panel.findChild(QPlainTextEdit, 'productionTaskResultOkNgCommTxStrip') is not None
    ok('panel result→Comm TX strip present')

    class Doc:
        def __init__(self):
            self.project = project
            self._commits = []
        def commit(self, p):
            self.project = p
            self._commits.append(p)

    doc = Doc()
    dlg = CommManagerDialog(doc)
    ok('CommManagerDialog constructed')
    assert dlg.findChild(QPlainTextEdit, 'commResultOkNgSendTxStrip') is not None
    assert dlg.findChild(QPushButton, 'commResultOkNgSendTxBtn') is not None
    ok('comm result OK/NG TX widgets present')

    class Win:
        operator_hmi = None
        host_state_machine = None
        comm_manager = dlg
        document = doc
    panel.window = lambda *a, **k: Win()  # type: ignore

    # OK path via trial→result co-update
    snap = panel._soft_co_update_trial_result(
        phase='result', title='试跑OK出站', ops=[{'operation': 'locate'}],
        judge='OK', result={'state': 'completed', 'judge': 'OK'},
    )
    assert snap['okng'] == 'OK', snap
    strip = panel._prod_result_comm_tx_strip.toPlainText()
    assert 'sendEvents soft TX' in strip or 'TX→result' in strip or 'okng=OK' in strip, strip
    assert 'OK' in strip, strip
    ok(f'panel OK TX strip · {strip.splitlines()[-1][:80]}')
    meta = panel._prod_result_comm_tx_meta.text()
    assert '闭环出站' in meta or 'TX=' in meta, meta
    ok(f'panel TX meta · {meta[:80]}')

    # NG path via Comm dialog API
    bag = dlg.soft_result_okng_send_tx(judge='NG', recipe='配方TX', status_var='global.taskStatus')
    assert bag and bag.get('tx', 0) >= 1, bag
    assert bag.get('resultOk') == 0, bag
    page = dlg.result_okng_tx_strip.toPlainText()
    assert 'NG' in page and ('TX→result' in page or 'soft TX' in page), page
    ok(f'comm NG TX strip · tx={bag["tx"]} · {page.splitlines()[-1][:70]}')
    cmeta = dlg.result_okng_tx_meta.text()
    assert 'sendEvents' in cmeta or '闭环出站' in cmeta, cmeta
    ok(f'comm TX meta · {cmeta[:80]}')

    print(f'\n=== {pass_n} passed, {fail_n} failed ===')
    return 0 if fail_n == 0 else 1

if __name__ == '__main__':
    rc = main()
    import os as _os
    _os._exit(rc)
