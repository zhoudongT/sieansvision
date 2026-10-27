#!/usr/bin/env python3
"""细妆⑮：HMI 门限列 passGate 序列 spark."""
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
    for n in ('_gate_hist', 'gate_spark_text', '_refresh_gate_spark', 'hmiGateSpark'):
        (ok if n in oh else bad)(f'has {n}' if n in oh else f'missing {n}')

    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from desktop.operator_hmi import OperatorHmiView
    v = OperatorHmiView()
    layout = {
        'split': '4',
        'pages': [{'name': 'P1', 'controls': [
            {'type': '结果表', 'binding': ''},
            {'type': '生产统计', 'binding': ''},
        ]}],
        'fixedBars': {'gateKey': 'passGate'},
    }
    try:
        v.reload_layout({'runUi': layout, 'name': 't'})
    except Exception as e:
        print('reload_layout note:', e)
    v._fixed_bars_cache = {'gateKey': 'passGate'}

    # seed a history row so update can write gate
    v._result_history = [{'ts': 't', 'seq': 1, 'module': 'm', 'elapsedMs': '1',
                          'judge': 'OK', 'ok': '1', 'ng': '0', 'gate': '—', 'note': '—'}]
    for val in (1, 1, 0, 1, 0):
        v.update_gate_column_live({'flow': {'passGate': val}})
    gh = v.gate_hist()
    assert len(gh) == 5, gh
    assert gh[0] is False and gh[1] is True  # newest first
    ok(f'gate_hist={gh}')

    spark = v.gate_spark_text()
    assert '▇' in spark and '▁' in spark
    ok(f'spark={spark}')

    labs = getattr(v, '_gate_spark_labs', []) or []
    if labs:
        txt = labs[0].text()
        (ok if '门限' in txt else bad)(f'spark lab={txt[:60]}')
    else:
        # layout may not have created 结果表; force refresh after ensuring lab
        from PySide6.QtWidgets import QLabel
        lab = QLabel()
        v._gate_spark_labs = [lab]
        v._refresh_gate_spark()
        (ok if '门限' in lab.text() else bad)(f'forced spark lab={lab.text()[:60]}')

    v.clear_result_history()
    assert v.gate_hist() == []
    ok('clear_result_history clears gate_hist')

    print(f"\n{'FAIL' if fail_n else 'PASS'} {pass_n} ok / {fail_n} fail")
    return 1 if fail_n else 0

if __name__ == '__main__':
    sys.exit(main())
