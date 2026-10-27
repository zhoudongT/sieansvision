#!/usr/bin/env python3
"""细妆⑮：Comm 验收定时复测 + last-vs-now 差分."""
from __future__ import annotations
import json
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
    from desktop.comm_acceptance_dialog import CommAcceptanceDialog

    prev = {'finishedAt': 'a', 'summary': {'pass': 3, 'fail': 1, 'skip': 0},
            'items': [
                {'id': 'ping', 'title': 'PING', 'status': 'PASS', 'detail': ''},
                {'id': 'echo', 'title': 'ECHO', 'status': 'FAIL', 'detail': 'x'},
            ]}
    now = {'finishedAt': 'b', 'summary': {'pass': 4, 'fail': 0, 'skip': 0},
           'items': [
               {'id': 'ping', 'title': 'PING', 'status': 'PASS', 'detail': ''},
               {'id': 'echo', 'title': 'ECHO', 'status': 'PASS', 'detail': 'ok'},
               {'id': 'new', 'title': 'NEW', 'status': 'PASS', 'detail': ''},
           ]}
    d = CommAcceptanceDialog.diff_reports(prev, now)
    assert len(d['changed']) == 2, d
    ids = {c['id'] for c in d['changed']}
    assert ids == {'echo', 'new'}, ids
    ok(f'diff_reports changed={ids}')

    same = CommAcceptanceDialog.diff_reports(now, now)
    assert len(same['changed']) == 0
    ok('diff identical → 0 changed')

    src = (ROOT / 'desktop/comm_acceptance_dialog.py').read_text(encoding='utf-8')
    for n in ('commAcceptScheduleChk', 'commAcceptDiffBtn', '_on_schedule_fire',
              '_compare_last_vs_now', 'diff_reports', 'QTimer'):
        (ok if n in src else bad)(f'src has {n}' if n in src else f'missing {n}')

    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    data = ROOT / 'native-data-smoke-comm-diff'
    data.mkdir(exist_ok=True)
    dlg = CommAcceptanceDialog(default_host='127.0.0.1', default_port=19880, data_dir=data)
    assert hasattr(dlg, 'chk_schedule') and hasattr(dlg, 'diff_banner')
    assert hasattr(dlg, '_schedule_timer')
    ok('dialog schedule/diff widgets')

    # seed disk prev, set memory now, compare
    path = dlg.last_report_path()
    path.write_text(json.dumps(prev, ensure_ascii=False), encoding='utf-8')
    dlg._report = now
    dlg._compare_last_vs_now()
    assert '变更' in dlg.diff_banner.text() or '差分' in dlg.diff_banner.text()
    ok(f'diff_banner={dlg.diff_banner.text()[:80]}')

    # schedule toggle does not crash
    dlg.schedule_spin.setValue(1)
    dlg.chk_schedule.setChecked(True)
    assert dlg._schedule_timer.isActive()
    ok('schedule timer active')
    dlg.chk_schedule.setChecked(False)
    assert not dlg._schedule_timer.isActive()
    ok('schedule timer stopped')

    print(f"\n{'FAIL' if fail_n else 'PASS'} {pass_n} ok / {fail_n} fail")
    return 1 if fail_n else 0

if __name__ == '__main__':
    sys.exit(main())
