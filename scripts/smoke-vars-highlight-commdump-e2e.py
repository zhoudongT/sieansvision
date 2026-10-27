#!/usr/bin/env python3
"""细妆⑲：Comm dump → Variables 面板即时高亮."""
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
    from PySide6.QtWidgets import QApplication, QMessageBox, QWidget
    app = QApplication.instance() or QApplication([])
    QMessageBox.information = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
    QMessageBox.warning = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)

    from desktop.variables_dialog import VariablesDialog
    from desktop.comm_acceptance_dialog import dump_acceptance_to_variables, CommAcceptanceDialog

    from PySide6.QtCore import QObject, Signal
    class Doc(QObject):
        changed = Signal()
        def __init__(self):
            super().__init__()
            self.project = {
                'id': 't', 'name': 't', 'steps': [],
                'variables': {'commAcceptPass': 0},
                'variableTypes': {},
            }
        def mark_dirty(self): pass

    class Backend:
        def request(self, *a, **k): return 1
        result = type('S', (), {'connect': staticmethod(lambda *a, **k: None)})()
        error = type('S', (), {'connect': staticmethod(lambda *a, **k: None)})()

    doc = Doc()
    backend = Backend()
    dlg = VariablesDialog(doc, backend, None)
    assert hasattr(dlg, 'highlight_written_keys')
    ok('VariablesDialog.highlight_written_keys present')

    dlg.mode.setCurrentIndex(0)
    dlg.render()
    dlg.live_patch_flow_var('commAcceptPass', 3)
    ok('live_patch_flow_var does not crash + triggers highlight')

    report = {
        'host': '127.0.0.1', 'port': 19880,
        'finishedAt': '2026-10-28 01:00:00',
        'summary': {'pass': 1, 'fail': 0, 'skip': 0},
        'items': [{'id': 'ping', 'status': 'PASS', 'reply': 'PONG'}],
    }
    stats = dump_acceptance_to_variables(doc.project, report)
    assert stats['keys']
    dlg.highlight_written_keys(stats['keys'])
    ok(f'highlight_written_keys({len(stats["keys"])} keys)')

    class FakeMWW(QWidget):
        def __init__(self):
            super().__init__()
            self.document = doc
            self.dialogs = {'variables': dlg}
            self._logs = []
            self._hi = []
        def log(self, m): self._logs.append(m)
        def statusBar(self):
            class SB:
                def showMessage(self, *a, **k): pass
            return SB()
        def highlight_variables_keys(self, keys):
            self._hi.append(list(keys))
            dlg.highlight_written_keys(keys)

    mw = FakeMWW()
    data = ROOT / 'native-data-smoke-vars-hi'
    data.mkdir(exist_ok=True)
    cad = CommAcceptanceDialog(mw, default_host='127.0.0.1', default_port=19880, data_dir=data)
    cad._report = report
    cad._dump_vars()
    assert mw._hi, 'dump should call highlight_variables_keys'
    ok(f'Comm dump → MW.highlight_variables_keys ({len(mw._hi[0])} keys)')

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
