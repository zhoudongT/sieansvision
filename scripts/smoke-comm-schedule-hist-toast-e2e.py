#!/usr/bin/env python3
"""细妆⑯：Comm 定时复测历史 spark + FAIL alert toast."""
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
    src = (ROOT / 'desktop/comm_acceptance_dialog.py').read_text(encoding='utf-8')
    for n in ('commAcceptScheduleSpark', '_schedule_hist', 'schedule_spark_text',
              '_fail_alert_toast', '_record_schedule_hist', 'FAIL 告警'):
        (ok if n in src else bad)(f'src has {n}' if n in src else f'missing {n}')

    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from desktop.comm_acceptance_dialog import CommAcceptanceDialog
    data = ROOT / 'native-data-smoke-comm-hist'
    data.mkdir(exist_ok=True)
    dlg = CommAcceptanceDialog(default_host='127.0.0.1', default_port=19880, data_dir=data)
    assert hasattr(dlg, 'schedule_spark') and hasattr(dlg, '_schedule_hist')
    ok('dialog spark widget')

    # record pass then fail
    dlg._record_schedule_hist({'summary': {'pass': 5, 'fail': 0, 'skip': 0},
                               'finishedAt': 't1', 'host': '127.0.0.1', 'port': 19880})
    dlg._record_schedule_hist({'summary': {'pass': 3, 'fail': 2, 'skip': 0},
                               'finishedAt': 't2', 'host': '127.0.0.1', 'port': 19880})
    gh = dlg._schedule_hist
    assert gh[0] is False and gh[1] is True, gh
    spark = dlg.schedule_spark_text()
    assert '▇' in spark and '▁' in spark, spark
    ok(f'spark={spark}')

    dlg._fail_alert_toast({'summary': {'fail': 2}, 'host': '127.0.0.1', 'port': 19880,
                           'finishedAt': 't2'})
    assert 'FAIL' in dlg.diff_banner.text() or '告警' in dlg.diff_banner.text()
    ok(f'toast banner={dlg.diff_banner.text()[:80]}')

    print(f"\n{'FAIL' if fail_n else 'PASS'} {pass_n} ok / {fail_n} fail")
    return 1 if fail_n else 0

if __name__ == '__main__':
    sys.exit(main())
