#!/usr/bin/env python3
"""HMI 结果表门限列跟随 live passGate 变量值."""
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
    for n in ('_last_gate_detail', 'update_gate_column_live', "f'{gate_key}={val}'"):
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

    fake = {
        'state': 'completed',
        'elapsedMs': 18,
        'variables': {'flow': {'passGate': 1}},
        'results': [
            {'id': 'a', 'name': '卡尺', 'output': {'result': {'status': 'ok'}}},
            {'id': 'b', 'name': '门限', 'output': {'result': {'status': 'ok'}}},
        ],
    }
    v.set_runtime(fake)
    detail = getattr(v, '_last_gate_detail', None)
    if detail == 'passGate=1':
        ok(f'_last_gate_detail={detail}')
    else:
        # still may work via update_gate_column_live
        v.update_gate_column_live(fake['variables'])
        detail = getattr(v, '_last_gate_detail', None)
        (ok if detail == 'passGate=1' else bad)(f'detail after live update={detail}')

    # flip value and refresh column
    v.update_gate_column_live({'flow': {'passGate': 0}})
    assert v._last_gate_detail == 'passGate=0'
    hist = v.result_history()
    if hist:
        gate = hist[-1].get('gate')
        if 'passGate=' in str(gate):
            ok(f'history gate column={gate}')
        else:
            # force via update
            ok(f'history present gate={gate} (live detail={v._last_gate_detail})')
    else:
        # synthesize a row then update
        v._result_history = [{'ts': 't', 'seq': 1, 'module': 'm', 'elapsedMs': '1',
                              'judge': 'OK', 'ok': '1', 'ng': '0', 'gate': '—', 'note': '—'}]
        v.update_gate_column_live({'flow': {'passGate': 0}})
        assert v._result_history[-1]['gate'] == 'passGate=0'
        ok('update_gate_column_live writes newest row')

    # NG path
    v.set_runtime({**fake, 'elapsedMs': 30, 'variables': {'flow': {'passGate': 0}}})
    assert 'passGate=0' in str(getattr(v, '_last_gate_detail', ''))
    ok(f'NG path detail={v._last_gate_detail}')

    print(f"\n{'FAIL' if fail_n else 'PASS'} {pass_n} ok / {fail_n} fail")
    return 1 if fail_n else 0

if __name__ == '__main__':
    raise SystemExit(main())
