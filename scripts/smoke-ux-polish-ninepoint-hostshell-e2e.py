#!/usr/bin/env python3
"""Structural 细妆 smoke: ninepoint verify tab, script bang, default host shell, alarm export, fixed-bar live."""
import ast, json, sys
from pathlib import Path
root = Path(__file__).resolve().parents[1]
pass_n = fail_n = 0

def ok(m):
    global pass_n; pass_n += 1; print('PASS:', m)
def bad(m):
    global fail_n; fail_n += 1; print('FAIL:', m)

# ninepoint verify tab
src = (root / 'desktop/nine_point_panel.py').read_text()
ast.parse(src)
if "_verify_tab" in src and "验证示意" in src:
    ok('ninepoint 验证示意 tab')
else:
    bad('ninepoint 验证示意 tab missing')

# script bang
cs = (root / 'desktop/config_status.py').read_text()
if "op == 'script'" in cs:
    ok('script N4 bang')
else:
    bad('script N4 bang missing')

# default-platform host shell
dp = json.loads((root / 'projects/default-platform.sieans').read_text())
names = [p['name'] for p in (dp.get('runUi') or {}).get('placements') or []]
if '上位机状态机' in names and '图像' in names:
    ok(f'default-platform placements={names}')
else:
    bad(f'default-platform placements={names}')

# alarm export
hsm = (root / 'desktop/host_state_machine.py').read_text()
for n in ('export_alarm_history_clipboard', 'export_alarm_history_file', 'hostAlarmHistoryCopyBtn'):
    (ok if n in hsm else bad)(f'alarm {n}')

# fixed bar live
oh = (root / 'desktop/operator_hmi.py').read_text()
ast.parse(oh)
if 'def update_fixed_bar_live' in oh and '_live_run_status' in oh:
    ok('fixed-bar live chrome')
else:
    bad('fixed-bar live chrome missing')

# samples exist
for f in ('open-and-run-ninepoint.sieans', 'open-and-run-comm-multiproto.sieans'):
    (ok if (root / 'projects' / f).is_file() else bad)(f'sample {f}')

# inject rms
fc = (root / 'lib/flow-control.cjs').read_text()
if 'bag.rms' in fc and 'usedPoints' in fc:
    ok('flow-control inject rms/count')
else:
    bad('flow-control inject missing')

print('---')
print(f'{pass_n} PASS / {fail_n} FAIL')
sys.exit(1 if fail_n else 0)
