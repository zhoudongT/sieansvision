#!/usr/bin/env python3
"""真机 Comm 验收壳：checklist dry-run against tcp_device_sim (no field HW)."""
from __future__ import annotations
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
    from desktop import tcp_device_sim as tds
    from desktop.comm_acceptance_dialog import CHECKLIST, _tcp_exchange, CommAcceptanceDialog
    assert len(CHECKLIST) >= 7
    ok(f'checklist items={len(CHECKLIST)}')

    try:
        tds.stop()
    except Exception:
        pass
    st = tds.start()
    port = int(st.get('tcpPort') or 19880)
    ok(f'sim up tcp={port}')

    reply = _tcp_exchange('127.0.0.1', port, 'PING')
    assert reply.upper() == 'PONG', reply
    ok('exchange PING')

    # run predicates offline
    for cid, title, cmd, pred in CHECKLIST:
        if cid == 'run_echo':
            continue
        r = _tcp_exchange('127.0.0.1', port, cmd)
        if not pred(r):
            bad(f'{cid} pred fail reply={r[:80]!r}')
        else:
            ok(f'{cid} PASS ({r[:40]!r}…)' if len(r) > 40 else f'{cid} PASS ({r!r})')

    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    dlg = CommAcceptanceDialog(default_host='127.0.0.1', default_port=port)
    dlg.chk_sim.setChecked(False)  # already up
    # run sync-ish: start thread and wait
    dlg._start()
    for _ in range(100):
        app.processEvents()
        if dlg._report is not None:
            break
        time.sleep(0.05)
    if dlg._runner and dlg._runner.isRunning():
        dlg._runner.wait(5000)
        app.processEvents()
    rep = dlg._report
    if not rep:
        bad('no report after dry-run')
    else:
        s = rep.get('summary') or {}
        ok(f"dialog dry-run pass={s.get('pass')} fail={s.get('fail')} skip={s.get('skip')}")
        if s.get('fail', 1) > 1:
            bad(f"too many fails: {rep.get('items')}")
    csv = dlg.report_csv()
    assert 'status' in csv and 'PING' in csv.upper() or 'ping' in csv
    ok('report_csv non-empty')

    mw = (ROOT / 'desktop/mainwindow.py').read_text(encoding='utf-8')
    if 'open_comm_acceptance' in mw and '真机 Comm 验收壳' in mw:
        ok('mainwindow menu wired')
    else:
        bad('mainwindow missing acceptance menu')

    print(f"\n{'FAIL' if fail_n else 'PASS'} {pass_n} ok / {fail_n} fail")
    return 1 if fail_n else 0

if __name__ == '__main__':
    raise SystemExit(main())
