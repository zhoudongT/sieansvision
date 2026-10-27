#!/usr/bin/env python3
"""HMI 结果表「模块」列跟末次步骤名（非硬编码「流程」）."""
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
    if "_last_module_name" in oh and "跟末次步骤名" in oh: ok('HMI tracks _last_module_name')
    else: bad('missing _last_module_name')
    if "('模块', '流程', '—')" in oh: bad('still hardcodes 模块=流程')
    else: ok('no hardcoded 模块=流程 row')
    if 'mod_name = getattr(self, \'_last_module_name\'' in oh or 'mod_name = getattr(self, "_last_module_name"' in oh:
        ok('refresh uses mod_name')
    else: bad('refresh not using mod_name')
    mw = (ROOT / 'desktop/mainwindow.py').read_text(encoding='utf-8')
    if 'named_recs' in mw and 'hmi_result' in mw: ok('finished enriches names for HMI')
    else: bad('finished missing named_recs')

    # Headless apply
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from desktop.operator_hmi import OperatorHmiView
    v = OperatorHmiView()
    assert getattr(v, '_last_module_name', None) == '流程'
    fake = {
        'state': 'completed',
        'elapsedMs': 12,
        'variables': {'flow': {'passGate': 1}},
        'results': [
            {'id': 'a', 'name': '卡尺直线查找', 'output': {'result': {'status': 'ok', 'count': 3}}},
            {'id': 'b', 'name': '交点·垂距门限·OK/NG', 'output': {'result': {'status': 'ok'}}},
        ],
    }
    v.set_runtime(fake, image='', annotated='')
    if v._last_module_name == '交点·垂距门限·OK/NG':
        ok(f'last module → {v._last_module_name}')
    else:
        bad(f'last module got {v._last_module_name!r}')
    print(f"\n{'FAIL' if fail_n else 'PASS'} {pass_n} ok / {fail_n} fail")
    return 1 if fail_n else 0

if __name__ == '__main__':
    raise SystemExit(main())
