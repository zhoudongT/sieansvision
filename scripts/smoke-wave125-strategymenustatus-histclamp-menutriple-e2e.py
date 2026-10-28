#!/usr/bin/env python3
"""细妆93：策略菜单 status_prop_ok · 短史夹紧 tip/status · 菜单 flash+tip+status 三联回归."""
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
        assert "setProperty('dstImportStrategyBadgeStatus', status)" in hsm_src
        assert 'preview_clamp_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy_overlap_batch_remove_undo_toast_history_badge' in hsm_src
        assert 'clamp_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy_overlap_batch_remove_undo_toast_history_badge_pos' in hsm_src
        assert "isUndoEyedropperBatchRemoveUndoToastHistoryBadgeMenuClampPreview" in hsm_src
        ok('wave125 APIs present')
    except Exception as e:
        bad(f'wave125 APIs present: {e}')
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

    host._cycle_key_suggest_history_filter_presets_reorder_badge_menu_no_exec = True
    host._cycle_key_suggest_history_filter_presets_reorder_badge_quiet = True
    host._ics_strategy_shortcut_conflict_ignore_menu_no_exec = True
    host._ics_strategy_shortcut_conflict_quiet = True
    host._dst_reorder_shortcut_conflict_quiet = True
    host._dst_reorder_shortcut_conflict_history_menu_no_exec = True
    host._ab_trial_fallback_import_conflict_preview_layout_slots_dialog_no_exec = True
    host._ab_trial_fallback_import_conflict_preview_layout_quiet = True
    host._jitter_reorder_undo_lab_menu_no_exec = True
    host._jitter_reorder_undo_depth_lab_flash_done_quiet = True

    # --- 1 strategy menu status_prop_ok ---
    try:
        host.ensure_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge()
        menu = host.show_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_context_menu()
        assert menu.get('status_prop_ok') is True, menu
        assert menu.get('tip_prop_ok') is True, menu
        assert str(menu.get('status', '')).startswith('策略·'), menu
        ok(f'1 strategy menu status_prop_ok status={menu.get("status")} tip_ok={menu.get("tip_prop_ok")}')
    except Exception as e:
        bad(f'1 strategy menu status: {e}')

    # --- 2 hist clamp tip/status ---
    try:
        host.ensure_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy_overlap_batch_remove_undo_toast_history_badge()
        host.remember_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy_overlap_batch_remove_undo_toast(
            {'toast': '撤销批量移除 · 1', 'restored': ['a'], 'restored_n': 1})
        out = host.preview_clamp_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy_overlap_batch_remove_undo_toast_history_badge()
        assert out.get('ok') and out.get('status_prop_ok') is True, out
        assert out.get('tip_prop_ok') is True, out
        assert out.get('status') == '夹紧预览', out
        ok(f'2 hist clamp tip_prop_ok={out.get("tip_prop_ok")} status_prop_ok={out.get("status_prop_ok")}')
    except Exception as e:
        bad(f'2 hist clamp: {e}')

    # --- 3 hist menu includes clamp_preview + triple ---
    try:
        menu = host.show_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy_overlap_batch_remove_undo_toast_history_badge_context_menu()
        assert 'clamp_preview' in (menu.get('actions') or []), menu
        assert menu.get('flash_ms_prop_ok') is True and menu.get('tip_prop_ok') is True and menu.get('status_prop_ok') is True, menu
        ok(f'3 hist menu clamp_preview + triple flash/tip/status')
    except Exception as e:
        bad(f'3 hist menu clamp: {e}')

    # --- 4-7 menu flash+tip+status triple regress ---
    try:
        host.ensure_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_default_slot_shortcut_history_rollback_conflicts_repreview_count_badge()
        menu = host.show_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_default_slot_shortcut_history_rollback_conflicts_repreview_count_badge_context_menu()
        assert menu.get('flash_ms_prop_ok') is True and menu.get('tip_prop_ok') is True and menu.get('status_prop_ok') is True, menu
        ok(f'4 repreview menu triple ok')
    except Exception as e:
        bad(f'4 repreview menu triple: {e}')

    try:
        host.ensure_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_freq_import_merge_undo_stack_preview_bar_jump_delta_badge()
        menu = host.show_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_freq_import_merge_undo_stack_preview_bar_jump_delta_badge_context_menu()
        assert menu.get('flash_ms_prop_ok') is True and menu.get('tip_prop_ok') is True and menu.get('status_prop_ok') is True, menu
        ok(f'5 jump menu triple ok')
    except Exception as e:
        bad(f'5 jump menu triple: {e}')

    try:
        host.ensure_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound_volume_mute_badge_bar_wheel_step_badge()
        menu = host.show_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound_volume_mute_badge_bar_wheel_step_badge_context_menu()
        assert menu.get('flash_ms_prop_ok') is True and menu.get('tip_prop_ok') is True and menu.get('status_prop_ok') is True, menu
        ok(f'6 wheel menu triple ok')
    except Exception as e:
        bad(f'6 wheel menu triple: {e}')

    try:
        # strategy also has tip+status (no flash_ms on strategy menu)
        menu = host.show_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_context_menu()
        assert menu.get('tip_prop_ok') is True and menu.get('status_prop_ok') is True and menu.get('strategy_prop_ok') is True, menu
        ok(f'7 strategy menu tip+status+strategy triple-ish ok')
    except Exception as e:
        bad(f'7 strategy tip+status: {e}')

    print(f'\nRESULT: {pass_n} passed, {fail_n} failed')
    return 0 if fail_n == 0 else 1

if __name__ == '__main__':
    raise SystemExit(main())
