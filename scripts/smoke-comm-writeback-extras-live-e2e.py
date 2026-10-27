#!/usr/bin/env python3
"""细妆⑰：Comm VALUE/MEAS → globals writeback deepen (module parse + listener + simulate).
No field HW / no robot SDK / no push.
"""
from __future__ import annotations
import os, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); os.chdir(ROOT)
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

fails = []
def ok(n, c, d=''):
    if c: print(f'PASS  {n}')
    else: fails.append(n); print(f'FAIL  {n}  {d}')

def main():
    from PySide6.QtWidgets import QApplication, QMessageBox
    app = QApplication.instance() or QApplication(sys.argv)
    # Non-blocking message boxes in smoke
    QMessageBox.information = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)

    from desktop.comm_manager import (
        parse_protocol_writeback_extras, write_project_variable,
        ensure_comm_manager,
    )
    from desktop import comm_manager as cm_mod
    from desktop.comm_listener import CommRecvListener
    from desktop.model import Document

    # --- parser ---
    ok('VALUE single', parse_protocol_writeback_extras('VALUE score=0.91') == [('score', '0.91')])
    ok('VALUE multi', parse_protocol_writeback_extras('VALUE a=1 b=2') == [('a', '1'), ('b', '2')])
    ok('VALUE comma', parse_protocol_writeback_extras('VALUE a=1,b=2') == [('a', '1'), ('b', '2')])
    meas = dict(parse_protocol_writeback_extras('MEAS {"ok":1,"x":3.5,"y":4,"angle":9,"foo":7}'))
    ok('MEAS measOk', meas.get('measOk') == 1, meas)
    ok('MEAS measX', meas.get('measX') == 3.5, meas)
    ok('MEAS measAngle', meas.get('measAngle') == 9, meas)
    ok('MEAS leftover', meas.get('meas_foo') == 7, meas)
    j = dict(parse_protocol_writeback_extras('{"n":1,"s":"hi"}'))
    ok('JSON flatten', j.get('json_n') == 1 and j.get('json_s') == 'hi', j)

    # --- simulate writeback with extras ---
    doc = Document()
    p = doc.project
    ensure_comm_manager(p)
    cm = p['commManager']
    cm['recvEvents'] = [
        dict(device='LocalLoop', message='VALUE score=0.88', variable='flow.acceptScore', enabled=True),
        dict(device='LocalLoop', message='MEAS {"ok":1,"x":11,"y":22}', variable='flow.measRaw', enabled=True),
    ]
    doc.commit(p)

    table = cm_mod._EventTable(var_role='write')
    table.bind_document(doc)
    table.set_rows(cm['recvEvents'], ['LocalLoop'])
    table._simulate_writeback()
    vars_ = doc.project.get('variables') or {}
    ok('sim acceptScore', str(vars_.get('acceptScore', '')).startswith('VALUE'), vars_.get('acceptScore'))
    ok('sim score sibling', vars_.get('score') == '0.88', vars_)
    ok('sim measRaw', str(vars_.get('measRaw', '')).startswith('MEAS'), vars_.get('measRaw'))
    ok('sim measOk', vars_.get('measOk') == 1, vars_)
    ok('sim measX', vars_.get('measX') == 11, vars_)
    ok('sim measY', vars_.get('measY') == 22, vars_)

    # --- listener live path ---
    class FakeHost:
        def __init__(self, document):
            self.document = document
            self.dialogs = {}
            self.logs = []
        def log(self, m): self.logs.append(m)
        def fire_string_trigger(self, text, reason=''): return False

    p2 = doc.project
    p2['variables'] = {}
    p2['commManager']['recvEvents'] = [
        dict(device='SimDev', message='', variable='flow.lineIn', enabled=True),
    ]
    doc.commit(p2)
    host = FakeHost(doc)
    listener = CommRecvListener(host)
    listener.reload(doc.project)
    listener._recv_events = [dict(device='SimDev', variable='flow.lineIn')]
    listener._on_received('SimDev', 'MEAS {"ok":0,"x":1.5,"y":2.5,"score":0.4}')
    v = doc.project.get('variables') or {}
    ok('live lineIn raw', str(v.get('lineIn', '')).startswith('MEAS'), v.get('lineIn'))
    ok('live measOk', v.get('measOk') == 0, v)
    ok('live measX', v.get('measX') == 1.5, v)
    ok('live measScore', v.get('measScore') == 0.4, v)

    # VALUE on live path
    p2['variables'] = {}
    doc.commit(p2)
    listener._on_received('SimDev', 'VALUE gate=1 pass=true')
    v = doc.project.get('variables') or {}
    ok('live VALUE gate', v.get('gate') == '1', v)
    ok('live VALUE pass', v.get('pass') == 'true', v)

    src_cl = open('desktop/comm_listener.py', encoding='utf-8').read()
    src_cm = open('desktop/comm_manager.py', encoding='utf-8').read()
    ok('listener imports parse', 'parse_protocol_writeback_extras' in src_cl)
    ok('module def present', 'def parse_protocol_writeback_extras(' in src_cm)
    ok('wrapper thin', 'Thin wrapper' in src_cm)

    print('----')
    if fails:
        print(f'{len(fails)} FAIL'); sys.exit(1)
    print('ALL PASS'); sys.exit(0)

if __name__ == '__main__':
    main()
