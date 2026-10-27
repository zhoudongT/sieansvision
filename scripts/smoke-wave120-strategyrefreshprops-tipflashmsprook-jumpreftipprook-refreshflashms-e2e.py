#!/usr/bin/env python3
"""细妆88：策略 refresh out 属性同步 · 再预览/短史/步进 tip flash_ms_prop_ok · 档差 refresh tip_prop_ok · FlashMs refresh 往返."""
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
        assert "strategy_prop_ok': bool(strategy_prop_ok)" in hsm_src
        assert 'repreview_flash_ms_prop_ok' in hsm_src or '_rollback_repreview_flash_ms_prop_ok' in hsm_src
        assert "'tip_prop_ok': bool(tip_prop_ok)" in hsm_src
        assert hsm_src.count("'flash_ms_prop_ok': bool(flash_ms_prop_ok)") >= 8
        ok('wave120 APIs present')
    except Exception as e:
        bad(f'wave120 APIs present: {e}')
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
    host._ics_strategy_shortcut_conflict_ignore_menu_no_exec = True
    host._ics_strategy_shortcut_conflict_quiet = True
    host._dst_reorder_shortcut_conflict_quiet = True
    host._dst_reorder_shortcut_conflict_history_menu_no_exec = True
    host._ab_trial_fallback_import_conflict_preview_layout_slots_dialog_no_exec = True
    host._jitter_reorder_undo_lab_menu_no_exec = True

    # --- 1 strategy refresh out prop sync ---
    try:
        host.set_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy('overwrite', persist=True)
        host.copy_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover_tip_orig_len()
        host.set_strategy_badge_hover_tip_max_len(160, persist=True)
        ref = host.refresh_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge()
        assert ref.get('ok') is True, ref
        assert ref.get('strategy') == 'overwrite', ref
        assert ref.get('strategy_prop_ok') is True, ref
        assert ref.get('strategy_prop') == 'overwrite', ref
        assert ref.get('tip_max_len_prop_ok') is True, ref
        assert int(ref.get('tip_max_len_prop') if ref.get('tip_max_len_prop') is not None else -1) == 160, ref
        assert ref.get('last_toast_brief_prop_ok') is True, ref
        host.set_strategy_badge_hover_tip_max_len(96, persist=True)
        host.set_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy('merge', persist=True)
        ok(f'1 strategy refresh props strategy_prop_ok={ref.get("strategy_prop_ok")} tip_ml={ref.get("tip_max_len_prop")}')
    except Exception as e:
        bad(f'1 strategy refresh props: {e}')

    # --- 2 repreview/hist/wheel tip flash_ms_prop_ok ---
    try:
        host._last_ab_trial_fallback_import_conflict_preview_layout_default_slot_shortcut_rollback_ignore = {
            'index': 0, 'repreview_conflict_n': 2, 'repreview': {'conflict_n': 2}}
        host.set_repreview_count_badge_flash_ms(1800, persist=True)
        tip = host.tip_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_default_slot_shortcut_history_rollback_conflicts_repreview_count_badge_hover()
        assert '闪标档：1800ms' in tip, tip
        ok_r = getattr(host, '_last_ab_trial_fallback_import_conflict_preview_layout_default_slot_shortcut_rollback_repreview_flash_ms_prop_ok', None)
        assert ok_r is True, ok_r

        host.remember_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy_overlap_batch_remove_undo_toast(
            {'toast': '撤销批量移除 · 1', 'restored': ['a'], 'restored_n': 1})
        host.set_batch_remove_undo_toast_history_badge_flash_ms(1200, persist=True)
        tip = host.tip_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy_overlap_batch_remove_undo_toast_history_badge_hover()
        assert '闪标档：1200ms' in tip, tip
        ok_h = getattr(host, '_last_ics_strategy_shortcut_conflict_ignore_by_role_merge_strategy_overlap_batch_remove_undo_toast_hist_badge_flash_ms_prop_ok', None)
        assert ok_h is True, ok_h

        host.set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound_volume_mute_badge_bar_wheel_step(10, persist=True)
        host.set_wheel_step_badge_flash_ms(300, persist=True)
        tip = host.tip_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound_volume_mute_badge_bar_wheel_step_badge_hover()
        assert '闪标档：300ms' in tip, tip
        ok_w = getattr(host, '_last_jitter_flash_done_sound_volume_mute_badge_bar_wheel_step_badge_flash_ms_prop_ok', None)
        assert ok_w is True, ok_w

        host.set_repreview_count_badge_flash_ms(600, persist=True)
        host.set_batch_remove_undo_toast_history_badge_flash_ms(600, persist=True)
        host.set_wheel_step_badge_flash_ms(600, persist=True)
        ok(f'2 tip flash_ms_prop_ok r/h/w={ok_r}/{ok_h}/{ok_w}')
    except Exception as e:
        bad(f'2 tip flash_ms_prop_ok: {e}')

    # --- 3 jump refresh tip_prop_ok ---
    try:
        host.set_jump_delta_badge_flash_ms(1800, persist=True)
        ref = host.refresh_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_freq_import_merge_undo_stack_preview_bar_jump_delta_badge(delta=2, from_idx=0, to_idx=2)
        assert ref.get('ok') and ref.get('status_prop_ok') is True, ref
        assert ref.get('tip_prop_ok') is True, ref
        assert ref.get('flash_ms_prop_ok') is True, ref
        assert int(ref.get('flash_ms_prop') if ref.get('flash_ms_prop') is not None else -1) == 1800, ref
        host.set_jump_delta_badge_flash_ms(600, persist=True)
        ok(f'3 jump refresh tip_prop_ok={ref.get("tip_prop_ok")} flash_ms_prop_ok={ref.get("flash_ms_prop_ok")}')
    except Exception as e:
        bad(f'3 jump refresh tip_prop_ok: {e}')

    # --- 4 refresh FlashMs round-trip ---
    try:
        host.set_repreview_count_badge_flash_ms(1200, persist=True)
        ref = host.refresh_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_default_slot_shortcut_history_rollback_conflicts_repreview_count_badge(2)
        assert ref.get('flash_ms_prop_ok') is True, ref
        assert int(ref.get('flash_ms_prop') if ref.get('flash_ms_prop') is not None else -1) == 1200, ref

        host.set_batch_remove_undo_toast_history_badge_flash_ms(1800, persist=True)
        refh = host.refresh_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy_overlap_batch_remove_undo_toast_history_badge()
        assert refh.get('flash_ms_prop_ok') is True, refh
        assert int(refh.get('flash_ms_prop') if refh.get('flash_ms_prop') is not None else -1) == 1800, refh

        host.set_wheel_step_badge_flash_ms(300, persist=True)
        refw = host.refresh_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound_volume_mute_badge_bar_wheel_step_badge(10)
        assert refw.get('flash_ms_prop_ok') is True, refw
        assert int(refw.get('flash_ms_prop') if refw.get('flash_ms_prop') is not None else -1) == 300, refw

        host.set_repreview_count_badge_flash_ms(600, persist=True)
        host.set_batch_remove_undo_toast_history_badge_flash_ms(600, persist=True)
        host.set_wheel_step_badge_flash_ms(600, persist=True)
        ok(f'4 refresh FlashMs round-trip r/h/w flash_ms_prop_ok')
    except Exception as e:
        bad(f'4 refresh FlashMs: {e}')

    # --- 5 combined sanity ---
    try:
        menu = host.show_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_context_menu()
        assert menu.get('strategy_prop_ok') is True, menu
        setr = host.set_jump_delta_badge_flash_ms(1200, persist=True)
        assert setr.get('tip_prop_ok') is True and setr.get('flash_ms_prop_ok') is True, setr
        host.set_jump_delta_badge_flash_ms(600, persist=True)
        ok('5 combined menu+jump set still green')
    except Exception as e:
        bad(f'5 combined: {e}')

    print(f'\nRESULT: {pass_n} passed, {fail_n} failed')
    return 0 if fail_n == 0 else 1

if __name__ == '__main__':
    raise SystemExit(main())
