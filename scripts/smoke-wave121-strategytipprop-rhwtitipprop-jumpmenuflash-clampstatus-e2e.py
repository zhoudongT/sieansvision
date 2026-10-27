#!/usr/bin/env python3
"""细妆89：策略 tip/set/refresh tip_prop · 再预览/短史/步进 tip_prop 镜像 · 档差菜单 flash 同步 · 夹紧预览 status_prop_ok."""
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
        assert "dstImportStrategyBadgeHoverTip'" in hsm_src
        assert 'repreviewCountBadgeHoverTip' in hsm_src
        assert 'batchRemoveUndoToastHistoryBadgeHoverTip' in hsm_src
        assert 'wheelStepBadgeHoverTip' in hsm_src
        assert "'status_prop_ok': bool(status_prop_ok)" in hsm_src
        assert hsm_src.count('_clamp_preview') >= 3
        ok('wave121 APIs present')
    except Exception as e:
        bad(f'wave121 APIs present: {e}')
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

    # --- 1 strategy tip/set/refresh tip_prop_ok ---
    try:
        host.set_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy('overwrite', persist=True)
        host.copy_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover_tip_orig_len()
        tip = host.tip_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover()
        assert tip and 'DST' in tip, tip[:80]
        tip_ok = getattr(host, '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover_tip_prop_ok', None)
        assert tip_ok is True, tip_ok
        sot = host.set_strategy_badge_hover_tip_max_len(140, persist=True)
        assert sot.get('ok') and sot.get('tip_prop_ok') is True, sot
        assert sot.get('tip_prop') and str(sot.get('tip_prop')) == str(sot.get('tip')), sot
        ref = host.refresh_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge()
        assert ref.get('ok') and ref.get('tip_prop_ok') is True, ref
        host.set_strategy_badge_hover_tip_max_len(96, persist=True)
        host.set_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy('merge', persist=True)
        ok(f'1 strategy tip/set/refresh tip_prop_ok tip={tip_ok} set={sot.get("tip_prop_ok")} ref={ref.get("tip_prop_ok")}')
    except Exception as e:
        bad(f'1 strategy tip_prop: {e}')

    # --- 2 repreview/hist/wheel tip tip_prop_ok ---
    try:
        host._last_ab_trial_fallback_import_conflict_preview_layout_default_slot_shortcut_rollback_ignore = {
            'index': 0, 'repreview_conflict_n': 2, 'repreview': {'conflict_n': 2}}
        tip = host.tip_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_default_slot_shortcut_history_rollback_conflicts_repreview_count_badge_hover()
        assert tip, tip
        ok_r = getattr(host, '_last_ab_trial_fallback_import_conflict_preview_layout_default_slot_shortcut_rollback_repreview_tip_prop_ok', None)
        assert ok_r is True, ok_r

        host.remember_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy_overlap_batch_remove_undo_toast(
            {'toast': '撤销批量移除 · 1', 'restored': ['a'], 'restored_n': 1})
        tip = host.tip_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy_overlap_batch_remove_undo_toast_history_badge_hover()
        assert tip, tip
        ok_h = getattr(host, '_last_ics_strategy_shortcut_conflict_ignore_by_role_merge_strategy_overlap_batch_remove_undo_toast_hist_badge_tip_prop_ok', None)
        assert ok_h is True, ok_h

        host.set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound_volume_mute_badge_bar_wheel_step(10, persist=True)
        tip = host.tip_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound_volume_mute_badge_bar_wheel_step_badge_hover()
        assert tip, tip
        ok_w = getattr(host, '_last_jitter_flash_done_sound_volume_mute_badge_bar_wheel_step_badge_tip_prop_ok', None)
        assert ok_w is True, ok_w
        ok(f'2 tip tip_prop_ok r/h/w={ok_r}/{ok_h}/{ok_w}')
    except Exception as e:
        bad(f'2 tip tip_prop_ok: {e}')

    # --- 3 repreview/hist/wheel refresh tip_prop_ok ---
    try:
        host._last_ab_trial_fallback_import_conflict_preview_layout_default_slot_shortcut_rollback_ignore = {
            'index': 0, 'repreview_conflict_n': 3, 'repreview': {'conflict_n': 3}}
        ref = host.refresh_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_default_slot_shortcut_history_rollback_conflicts_repreview_count_badge(3)
        assert ref.get('ok') and ref.get('tip_prop_ok') is True, ref

        host.remember_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy_overlap_batch_remove_undo_toast(
            {'toast': '撤销批量移除 · 2', 'restored': ['b'], 'restored_n': 1})
        refh = host.refresh_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy_overlap_batch_remove_undo_toast_history_badge()
        assert refh.get('ok') and refh.get('tip_prop_ok') is True, refh

        host.set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound_volume_mute_badge_bar_wheel_step(15, persist=True)
        refw = host.refresh_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound_volume_mute_badge_bar_wheel_step_badge()
        assert refw.get('ok') and refw.get('tip_prop_ok') is True, refw
        ok(f'3 refresh tip_prop_ok r/h/w={ref.get("tip_prop_ok")}/{refh.get("tip_prop_ok")}/{refw.get("tip_prop_ok")}')
    except Exception as e:
        bad(f'3 refresh tip_prop_ok: {e}')

    # --- 4 jump menu flash_ms_prop sync ---
    try:
        host.set_jump_delta_badge_flash_ms(1200, persist=True)
        host.refresh_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_freq_import_merge_undo_stack_preview_bar_jump_delta_badge(delta=1, from_idx=0, to_idx=1)
        menu = host.show_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_freq_import_merge_undo_stack_preview_bar_jump_delta_badge_context_menu()
        assert menu.get('ok') is True, menu
        assert menu.get('shown') is False, menu
        assert int(menu.get('flash_ms') if menu.get('flash_ms') is not None else -1) == 1200, menu
        assert menu.get('flash_ms_prop_ok') is True, menu
        assert int(menu.get('flash_ms_prop') if menu.get('flash_ms_prop') is not None else -1) == 1200, menu
        host.set_jump_delta_badge_flash_ms(600, persist=True)
        ok(f'4 jump menu flash_ms_prop_ok={menu.get("flash_ms_prop_ok")} flash_ms={menu.get("flash_ms")}')
    except Exception as e:
        bad(f'4 jump menu flash: {e}')

    # --- 5 clamp-preview status_prop_ok ---
    try:
        c1 = host.preview_clamp_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_default_slot_shortcut_history_rollback_conflicts_repreview_count_badge()
        assert c1.get('ok') and c1.get('status_prop_ok') is True, c1
        assert c1.get('status') == '夹紧预览', c1
        c2 = host.preview_clamp_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_freq_import_merge_undo_stack_preview_bar_jump_delta_badge()
        assert c2.get('ok') and c2.get('status_prop_ok') is True, c2
        c3 = host.preview_clamp_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound_volume_mute_badge_bar_wheel_step_badge()
        assert c3.get('ok') and c3.get('status_prop_ok') is True, c3
        ok(f'5 clamp status_prop_ok r/j/w={c1.get("status_prop_ok")}/{c2.get("status_prop_ok")}/{c3.get("status_prop_ok")}')
    except Exception as e:
        bad(f'5 clamp status_prop_ok: {e}')

    # --- 6 regress: jump refresh tip_prop still ok ---
    try:
        host.set_jump_delta_badge_flash_ms(1800, persist=True)
        ref = host.refresh_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_freq_import_merge_undo_stack_preview_bar_jump_delta_badge(delta=2, from_idx=0, to_idx=2)
        assert ref.get('ok') and ref.get('tip_prop_ok') is True and ref.get('flash_ms_prop_ok') is True, ref
        host.set_jump_delta_badge_flash_ms(600, persist=True)
        ok(f'6 regress jump refresh tip/flash ok')
    except Exception as e:
        bad(f'6 regress jump: {e}')

    print(f'\nRESULT: {pass_n} passed, {fail_n} failed')
    return 0 if fail_n == 0 else 1

if __name__ == '__main__':
    raise SystemExit(main())
