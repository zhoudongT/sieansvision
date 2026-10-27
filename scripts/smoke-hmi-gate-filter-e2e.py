#!/usr/bin/env python3
"""细妆⑯：HMI 门限 spark 点击 → 结果表按通/拒窗口筛选."""
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
    oh = (ROOT / 'desktop/operator_hmi.py').read_text(encoding='utf-8')
    for n in ('_cycle_gate_filter', '_gate_filter_mode', '_make_gate_spark_click_handler',
              'gatePass', '仅通', '仅拒'):
        (ok if n in oh else bad)(f'has {n}' if n in oh else f'missing {n}')

    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from desktop.operator_hmi import OperatorHmiView
    v = OperatorHmiView()
    layout = {
        'split': '4',
        'pages': [{'name': 'P1', 'controls': [
            {'type': '结果表', 'binding': ''},
        ]}],
        'fixedBars': {'gateKey': 'passGate'},
    }
    try:
        v.reload_layout({'runUi': layout, 'name': 't'})
    except Exception as e:
        print('reload note:', e)
    # ensure 结果表 cell exists even if layout path skipped (keep parent ref)
    cell_keep = None
    if not getattr(v, '_result_tables', None):
        try:
            cell_keep = v._build_control('结果表', {'binding': ''})
            cell_keep.setParent(v)  # keep C++ alive
        except Exception as e:
            print('build_control note:', e)

    v._result_history = [
        {'ts': 't1', 'seq': 1, 'module': 'm', 'elapsedMs': '1', 'judge': 'OK',
         'ok': '1', 'ng': '0', 'gate': 'passGate=1', 'note': '—', 'gatePass': True},
        {'ts': 't2', 'seq': 2, 'module': 'm', 'elapsedMs': '2', 'judge': 'NG',
         'ok': '1', 'ng': '1', 'gate': 'passGate=0', 'note': '—', 'gatePass': False},
        {'ts': 't3', 'seq': 3, 'module': 'm', 'elapsedMs': '1', 'judge': 'OK',
         'ok': '2', 'ng': '1', 'gate': 'passGate=1', 'note': '—', 'gatePass': True},
    ]
    v._gate_hist = [True, False, True]
    v._gate_filter_mode = 'all'
    v._refresh_result_tables_ui()
    tables = getattr(v, '_result_tables', []) or []
    if tables:
        assert tables[0].rowCount() == 3, tables[0].rowCount()
        ok(f'all filter rows={tables[0].rowCount()}')
    else:
        bad('no result tables')

    v._cycle_gate_filter()  # all → pass
    assert v._gate_filter_mode == 'pass'
    v._refresh_result_tables_ui()
    if tables:
        assert tables[0].rowCount() == 2, tables[0].rowCount()
        ok(f'pass filter rows={tables[0].rowCount()}')
    v._cycle_gate_filter()  # pass → fail
    assert v._gate_filter_mode == 'fail'
    v._refresh_result_tables_ui()
    if tables:
        assert tables[0].rowCount() == 1, tables[0].rowCount()
        ok(f'fail filter rows={tables[0].rowCount()}')
    v._cycle_gate_filter()  # fail → all
    assert v._gate_filter_mode == 'all'
    ok('cycle all→pass→fail→all')

    spark = v.gate_spark_text()
    v._refresh_gate_spark()
    labs = getattr(v, '_gate_spark_labs', []) or []
    if labs:
        assert '筛选' in labs[0].text()
        ok(f'spark lab={labs[0].text()[:70]}')
    else:
        ok('spark lab skipped (no layout lab)')

    print(f"\n{'FAIL' if fail_n else 'PASS'} {pass_n} ok / {fail_n} fail")
    return 1 if fail_n else 0

if __name__ == '__main__':
    sys.exit(main())
