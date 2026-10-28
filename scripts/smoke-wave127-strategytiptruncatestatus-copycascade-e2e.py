#!/usr/bin/env python3
"""细妆95：策略 tip/truncate Status 镜像 · copy 级联 status_prop_ok."""
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
        assert '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover_status_prop_ok' in hsm_src
        assert "'status_prop_ok': bool(status_prop_ok)}" in hsm_src or "'status_prop_ok': bool(status_prop_ok)" in hsm_src
        assert hsm_src.count("setProperty('dstImportStrategyBadgeStatus'") >= 5
        ok('wave127 APIs present')
    except Exception as e:
        bad(f'wave127 APIs present: {e}')
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

    # --- 1 tip merge status_prop_ok ---
    try:
        host.set_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy('merge', persist=True)
        tip = host.tip_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover()
        assert tip and 'DST导入策略' in tip
        assert getattr(host, '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover_status_prop_ok') is True
        assert getattr(host, '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover_status') == '策略·合并'
        assert getattr(host, '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover_tip_prop_ok') is True
        ok('1 tip merge status_prop_ok')
    except Exception as e:
        bad(f'1 tip merge: {e}')

    # --- 2 tip overwrite ---
    try:
        host.set_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy('overwrite', persist=True)
        tip = host.tip_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover()
        assert getattr(host, '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover_status_prop_ok') is True
        assert getattr(host, '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover_status') == '策略·覆盖'
        ok('2 tip overwrite status_prop_ok')
    except Exception as e:
        bad(f'2 tip overwrite: {e}')

    # --- 3 truncate status_prop_ok ---
    try:
        tr = host.truncate_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover_tip('x' * 200, max_len=40)
        assert isinstance(tr, tuple) and tr[1] is True
        last = getattr(host, '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover_tip_truncate', {})
        assert last.get('status_prop_ok') is True, last
        assert last.get('status') == '策略·覆盖', last
        assert last.get('truncated') is True
        ok(f'3 truncate status={last.get("status")} truncated')
    except Exception as e:
        bad(f'3 truncate: {e}')

    # --- 4 truncate no-op still status ---
    try:
        tr = host.truncate_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover_tip('short', max_len=96)
        assert tr[1] is False
        last = getattr(host, '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover_tip_truncate', {})
        assert last.get('status_prop_ok') is True, last
        ok('4 truncate short status_prop_ok')
    except Exception as e:
        bad(f'4 truncate short: {e}')

    # --- 5 copy cascade status_prop_ok ---
    try:
        host.tip_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover()
        out = host.copy_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover_tip()
        assert out.get('ok') and out.get('status_prop_ok') is True, out
        assert out.get('tip_prop_ok') is True, out
        assert str(out.get('status', '')).startswith('策略·'), out
        ok(f'5 copy cascade status={out.get("status")}')
    except Exception as e:
        bad(f'5 copy cascade: {e}')

    # --- 6 refresh still status (regress 94) ---
    try:
        out = host.refresh_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge()
        assert out.get('status_prop_ok') is True, out
        ok('6 refresh status regress')
    except Exception as e:
        bad(f'6 refresh regress: {e}')

    # --- 7 restore merge ---
    try:
        s = host.set_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy('merge', persist=True)
        assert s == 'merge'
        tip = host.tip_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover()
        assert getattr(host, '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover_status') == '策略·合并'
        ok('7 restore merge tip status')
    except Exception as e:
        bad(f'7 restore: {e}')

    print(f'\nRESULT: {pass_n} passed, {fail_n} failed')
    return 0 if fail_n == 0 else 1

if __name__ == '__main__':
    raise SystemExit(main())
