#!/usr/bin/env python3
"""细妆⑱：Comm 验收 → 变量一键落盘（汇总 + VALUE/MEAS extras）."""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
pass_n = fail_n = 0

def ok(m):
    global pass_n; pass_n += 1; print('PASS:', m)
def bad(m):
    global fail_n; fail_n += 1; print('FAIL:', m)

def main():
    from PySide6.QtWidgets import QApplication, QWidget
    app = QApplication.instance() or QApplication([])

    from desktop.comm_acceptance_dialog import (
        CommAcceptanceDialog, dump_acceptance_to_variables,
    )
    from desktop.comm_manager import read_project_variable

    report = {
        'host': '127.0.0.1',
        'port': 19880,
        'finishedAt': '2026-10-28 01:00:00',
        'summary': {'pass': 2, 'fail': 1, 'skip': 0},
        'items': [
            {'id': 'ping', 'status': 'PASS', 'reply': 'PONG', 'detail': ''},
            {'id': 'get', 'status': 'PASS', 'reply': 'VALUE score=0.91 accept_probe=1', 'detail': ''},
            {'id': 'meas', 'status': 'FAIL',
             'reply': 'MEAS {"ok":0,"x":1.2,"y":3.4,"pass":0}', 'detail': 'pred fail'},
        ],
    }
    project = {'variables': {}, 'name': 't'}
    stats = dump_acceptance_to_variables(project, report)
    assert stats['written'] >= 7, stats
    assert read_project_variable(project, 'flow.commAcceptPass') == 2
    assert read_project_variable(project, 'flow.commAcceptFail') == 1
    assert read_project_variable(project, 'flow.commAcceptOverall') == 'FAIL'
    assert read_project_variable(project, 'flow.commAccept_ping') == 'PASS'
    assert read_project_variable(project, 'flow.commAccept_get') == 'PASS'
    # extras from VALUE
    score = read_project_variable(project, 'flow.commAccept_get_score')
    assert str(score) == '0.91', score
    # extras from MEAS
    mx = read_project_variable(project, 'flow.commAccept_meas_measX')
    assert str(mx) in ('1.2', '1.20') or float(mx) == 1.2, mx
    ok(f'dump written={stats["written"]} extras={stats["extras"]} keys={len(stats["keys"])}')

    # Dialog button present
    class FakeDoc:
        project = {'variables': {}, 'name': 'host'}
        def mark_dirty(self): pass
        changed = type('S', (), {'emit': staticmethod(lambda: None)})()
    class FakeMW(QWidget):
        def __init__(self):
            super().__init__()
            self.document = FakeDoc()
            self._logs = []
        def log(self, m): self._logs.append(m)
        def statusBar(self):
            class SB:
                def showMessage(self, *a, **k): pass
            return SB()

    mw = FakeMW()
    data = ROOT / 'native-data-smoke-comm-vars'
    data.mkdir(exist_ok=True)
    dlg = CommAcceptanceDialog(mw, default_host='127.0.0.1', default_port=19880, data_dir=data)
    assert hasattr(dlg, 'btn_dump_vars')
    assert hasattr(dlg, '_dump_vars')
    dlg._report = report
    # stub modal boxes so headless doesn't hang
    from PySide6.QtWidgets import QMessageBox
    QMessageBox.information = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
    QMessageBox.warning = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
    dlg._dump_vars()
    assert read_project_variable(mw.document.project, 'flow.commAcceptPass') == 2
    ok('dialog 一键写入变量 → project.variables')

    print(f'\nRESULT pass={pass_n} fail={fail_n}')
    return 0 if fail_n == 0 else 1

if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as e:
        bad(f'crash: {e}')
        import traceback; traceback.print_exc()
        print(f'\nRESULT pass={pass_n} fail={fail_n}')
        raise SystemExit(1)
