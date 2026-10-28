#!/usr/bin/env python3
"""细妆94：策略 refresh/set/ensure status_prop_ok · tip_max_len 级联 Status."""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

pass_n = fail_n = 0

def ok(m):
    global pass_n; pass_n += 1; print('PASS:', m, flush=True)

def bad(m):
    global fail_n; fail_n += 1; print('FAIL:', m, flush=True)

def main() -> int:
    hsm_src = (ROOT / 'desktop' / 'host_state_machine.py').read_text(encoding='utf-8')
    try:
        assert hsm_src.count("setProperty('dstImportStrategyBadgeStatus'") >= 3
        assert '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_set' in hsm_src
        assert '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_status_prop_ok' in hsm_src
        ok('wave126 APIs present')
    except Exception as e:
        bad(f'wave126 APIs present: {e}')
        print(f'\nRESULT: {pass_n} passed, {fail_n} failed')
        return 1

    import os
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from desktop.host_state_machine import HostStateMachineWidget
    host = HostStateMachineWidget(compact=True)
    host.show()
    app.processEvents()

    host._dst_reorder_shortcut_conflict_quiet = True
    host._dst_reorder_shortcut_conflict_history_menu_no_exec = True

    # --- 1 ensure inits Status ---
    try:
        # force fresh badge
        host._dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge = None
        badge = host.ensure_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge()
        assert badge is not None
        sp = badge.property('dstImportStrategyBadgeStatus')
        assert str(sp) == '策略·合并', sp
        ok(f'1 ensure Status init={sp}')
    except Exception as e:
        bad(f'1 ensure Status: {e}')

    # --- 2 refresh status_prop_ok merge ---
    try:
        host.set_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy('merge', persist=True)
        out = host.refresh_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge()
        assert out.get('status_prop_ok') is True, out
        assert out.get('status') == '策略·合并', out
        assert out.get('strategy_prop_ok') is True, out
        ok(f'2 refresh merge status={out.get("status")} ok={out.get("status_prop_ok")}')
    except Exception as e:
        bad(f'2 refresh merge: {e}')

    # --- 3 set overwrite: str return + stash status_prop_ok ---
    try:
        s = host.set_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy('overwrite', persist=True)
        assert s == 'overwrite', s
        last = getattr(host, '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_set', {})
        assert last.get('status_prop_ok') is True, last
        assert last.get('status') == '策略·覆盖', last
        assert last.get('strategy') == 'overwrite', last
        ok(f'3 set overwrite str+stash status={last.get("status")}')
    except Exception as e:
        bad(f'3 set overwrite: {e}')

    # --- 4 refresh overwrite ---
    try:
        out = host.refresh_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge()
        assert out.get('status_prop_ok') is True and out.get('status') == '策略·覆盖', out
        ok(f'4 refresh overwrite status_prop_ok')
    except Exception as e:
        bad(f'4 refresh overwrite: {e}')

    # --- 5 tip_max_len cascade status_prop_ok ---
    try:
        out = host.set_strategy_badge_hover_tip_max_len(80, persist=True)
        assert out.get('status_prop_ok') is True, out
        assert str(out.get('status', '')).startswith('策略·'), out
        ok(f'5 tip_max_len cascade status={out.get("status")}')
    except Exception as e:
        bad(f'5 tip_max_len cascade: {e}')

    # --- 6 menu still status_prop_ok (regress 93) ---
    try:
        menu = host.show_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_context_menu()
        assert menu.get('status_prop_ok') is True and menu.get('tip_prop_ok') is True, menu
        ok(f'6 menu status+tip regress status={menu.get("status")}')
    except Exception as e:
        bad(f'6 menu regress: {e}')

    # --- 7 restore merge ---
    try:
        s = host.set_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy('merge', persist=True)
        assert s == 'merge'
        last = getattr(host, '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_set', {})
        assert last.get('status_prop_ok') is True and last.get('status') == '策略·合并', last
        ok('7 restore merge stash ok')
    except Exception as e:
        bad(f'7 restore: {e}')

    print(f'\nRESULT: {pass_n} passed, {fail_n} failed')
    return 0 if fail_n == 0 else 1

if __name__ == '__main__':
    raise SystemExit(main())
