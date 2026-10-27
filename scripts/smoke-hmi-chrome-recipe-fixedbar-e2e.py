#!/usr/bin/env python3
"""细妆⑱：运行模式 chrome 观感收束 — 配方徽章 / 固定栏 chip / StatusLamp NG blink."""
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
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])

    from desktop.operator_hmi import OperatorHmiView, StatusLamp
    from desktop.run_ui_designer import default_host_run_ui

    # StatusLamp NG blink API
    lamp = StatusLamp('判定')
    assert hasattr(lamp, 'set_state') and hasattr(lamp, '_blink_timer')
    lamp.set_state(True)
    assert not lamp._blink_timer.isActive()
    lamp.set_state(False)
    assert lamp._blink_timer.isActive(), 'NG should start blink'
    lamp.set_state(None)
    assert not lamp._blink_timer.isActive()
    ok('StatusLamp NG blink edge')

    hmi = OperatorHmiView()
    assert hasattr(hmi, 'set_recipe_chrome')
    assert hasattr(hmi, '_recipe_badge')
    assert hasattr(hmi, '_strip_recipe_lab')
    ok('HMI recipe badge + strip label present')

    proj = {
        'name': 'chrome-smoke',
        'runUi': default_host_run_ui(),
        'activeRecipeId': '',
        'recipes': [],
        'steps': [],
    }
    # enable all fixed bars + counters
    fb = proj['runUi'].setdefault('fixedBars', {})
    fb.update(top=True, bottom=True, left=True, right=True,
              showRunStatus=True, showOkNg=True, showCounters=True,
              gateKey='passGate', cameraBind='本机', commBind='TCP')
    hmi.reload_layout(proj)
    hmi.set_recipe_chrome('型号A', 'A型')
    assert '型号A' in hmi._recipe_badge.text()
    assert 'A型' in hmi._recipe_badge.text() or 'A型' in hmi._strip_recipe_lab.text()
    ok(f'recipe chrome → {hmi._recipe_badge.text()}')

    hmi.update_fixed_bar_live(run_status='运行中', okng='OK', counters='12/1')
    tip = hmi._fix_top.text()
    assert '配方' in tip or '型号A' in tip
    assert 'OK' in tip or '◆' in tip
    assert not hmi._fix_top.isHidden()
    ok(f'fixed top chip tip: {tip[:80]}…')

    hmi.update_fixed_bar_live(okng='NG')
    # lamps should be False
    lamps = hmi._status_lamps
    if lamps:
        assert lamps[0]._ok is False
        ok('OK/NG live drives StatusLamp → NG')
    else:
        ok('no status lamps in this layout (skip drive check)')

    # strip groups exist
    assert 'once' in hmi._strip_btns and 'clear' in hmi._strip_btns
    ok('default strip buttons grouped')

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
