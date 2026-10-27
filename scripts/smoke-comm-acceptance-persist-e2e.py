#!/usr/bin/env python3
"""Comm 验收报告落盘 + 载入上次结果."""
from __future__ import annotations
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
pass_n = fail_n = 0

def ok(m):
    global pass_n; pass_n += 1; print('PASS:', m)
def bad(m):
    global fail_n; fail_n += 1; print('FAIL:', m)

def main():
    data = ROOT / 'native-data-smoke-comm-persist'
    data.mkdir(exist_ok=True)

    from desktop import tcp_device_sim as tds
    from desktop.comm_acceptance_dialog import CommAcceptanceDialog
    try:
        tds.stop()
    except Exception:
        pass
    st = tds.start()
    port = int(st.get('tcpPort') or 19880)
    ok(f'sim tcp={port}')

    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    dlg = CommAcceptanceDialog(default_host='127.0.0.1', default_port=port, data_dir=data)
    assert hasattr(dlg, 'last_banner')
    assert hasattr(dlg, '_persist_report')
    ok('dialog persist API')

    dlg.chk_sim.setChecked(False)
    dlg._start()
    for _ in range(120):
        app.processEvents()
        if dlg._report is not None and not (dlg._runner and dlg._runner.isRunning()):
            break
        time.sleep(0.05)
    if dlg._runner and dlg._runner.isRunning():
        dlg._runner.wait(8000)
        app.processEvents()
    rep = dlg._report
    if not rep:
        bad('no report after run')
        print(f"\nFAIL {pass_n} ok / {fail_n} fail")
        return 1
    ok(f'run summary={rep.get("summary")}')

    path = dlg.last_report_path()
    assert path.is_file(), path
    disk = json.loads(path.read_text(encoding='utf-8'))
    assert disk.get('summary')
    ok(f'persisted {path.relative_to(ROOT)}')

    # new dialog should bootstrap banner from disk
    dlg2 = CommAcceptanceDialog(default_host='127.0.0.1', default_port=port, data_dir=data)
    assert 'PASS' in dlg2.last_banner.text() or '上次' in dlg2.last_banner.text()
    ok(f'bootstrap banner={dlg2.last_banner.text()[:60]}')
    dlg2._load_last_report()
    assert dlg2._report and dlg2._report.get('summary')
    ok('load last report into table')

    src = (ROOT / 'desktop/comm_acceptance_dialog.py').read_text(encoding='utf-8')
    for n in ('last-report.json', '_persist_report', 'commAcceptLoadLastBtn'):
        (ok if n in src else bad)(f'src has {n}' if n in src else f'missing {n}')

    mw = (ROOT / 'desktop/mainwindow.py').read_text(encoding='utf-8')
    (ok if 'data_dir=self.data' in mw else bad)('mainwindow passes data_dir')

    print(f"\n{'FAIL' if fail_n else 'PASS'} {pass_n} ok / {fail_n} fail")
    return 1 if fail_n else 0

if __name__ == '__main__':
    raise SystemExit(main())
