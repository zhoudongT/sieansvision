#!/usr/bin/env python3
"""细妆80：档差闪标时长可配 · 短史双击复位后闪标 · 策略原长可复制 · 再预览夹紧预览后闪标 · 步进右键夹紧预览."""
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
    markers = [
        'def jump_delta_badge_flash_ms',
        'def set_jump_delta_badge_flash_ms',
        '闪标时长',
        'jumpDeltaBadgeFlashMs',
        'def flash_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy_overlap_batch_remove_undo_toast_history_badge',
        "'flashed': flashed",
        'def copy_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover_tip_orig_len',
        '复制原长',
        'def flash_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_default_slot_shortcut_history_rollback_conflicts_repreview_count_badge',
        'def preview_clamp_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound_volume_mute_badge_bar_wheel_step_badge',
        'isJitterVolumeBadgeBarWheelStepBadgeMenuClampPreview',
    ]
    try:
        for m in markers:
            assert m in hsm_src, m
        ok('wave112 APIs present')
    except Exception as e:
        bad(f'wave112 APIs present: {e}')
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

    # --- 1 jump flash ms ---
    try:
        host.set_jump_delta_badge_flash_ms(600, persist=True)
        assert int(host.jump_delta_badge_flash_ms()) == 600
        host.refresh_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_freq_import_merge_undo_stack_preview_bar_jump_delta_badge(delta=3, from_idx=0, to_idx=3)
        menu = host.show_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_freq_import_merge_undo_stack_preview_bar_jump_delta_badge_context_menu()
        assert menu.get('ok') and 'flash_ms' in (menu.get('actions') or []), menu
        presets = menu.get('flash_ms_presets') or []
        assert '300' in presets and '600' in presets and '1200' in presets and '1800' in presets, presets
        assert int(menu.get('flash_ms') if menu.get('flash_ms') is not None else -1) == 600, menu
        setr = host.set_jump_delta_badge_flash_ms(300, persist=True)
        assert setr.get('ok') and int(setr.get('ms') if setr.get('ms') is not None else -1) == 300, setr
        fr = host.flash_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_freq_import_merge_undo_stack_preview_bar_jump_delta_badge()
        assert fr.get('ok') and fr.get('flashed') and int(fr.get('ms') if fr.get('ms') is not None else -1) == 300, fr
        host.set_jump_delta_badge_flash_ms(600, persist=True)
        ok(f'1 flash_ms presets={presets} used_ms={fr.get("ms")}')
    except Exception as e:
        bad(f'1 flash_ms: {e}')

    # --- 2 hist flash after dblreset ---
    try:
        host.remember_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy_overlap_batch_remove_undo_toast(
            {'toast': '撤销批量移除 · 1', 'restored': ['a'], 'restored_n': 1})
        host.refresh_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy_overlap_batch_remove_undo_toast_history_badge()
        host.move_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy_overlap_batch_remove_undo_toast_history_badge_to(40, 200, persist=False)
        dbl = host.dblclick_reset_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy_overlap_batch_remove_undo_toast_history_badge()
        assert dbl.get('ok') and dbl.get('reset') and dbl.get('flashed'), dbl
        fr = host.flash_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy_overlap_batch_remove_undo_toast_history_badge(ms=200)
        assert fr.get('ok') and fr.get('flashed'), fr
        ok(f'2 hist flash dbl_flashed={dbl.get("flashed")} fr={fr.get("flashed")}')
    except Exception as e:
        bad(f'2 hist flash: {e}')

    # --- 3 strategy copy orig_len ---
    try:
        host.set_strategy_badge_hover_tip_max_len(48, persist=True)
        menu = host.show_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_context_menu()
        assert menu.get('ok') and 'copy_orig_len' in (menu.get('actions') or []), menu
        cp = host.copy_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover_tip_orig_len()
        assert cp.get('ok') and cp.get('copied'), cp
        assert int(cp.get('orig_len') if cp.get('orig_len') is not None else -1) > 48, cp
        assert '原长：' in str(cp.get('text') or ''), cp
        host.set_strategy_badge_hover_tip_max_len(400, persist=True)
        tip_full = host.tip_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover()
        assert '复制原长' in tip_full, tip_full
        host.set_strategy_badge_hover_tip_max_len(48, persist=True)
        tip_trunc = host.tip_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover()
        assert '原长：' in tip_trunc, tip_trunc
        host.set_strategy_badge_hover_tip_max_len(96, persist=True)
        ok(f'3 copy_orig_len actions={menu.get("actions")} orig={cp.get("orig_len")} text={cp.get("text")}')
    except Exception as e:
        bad(f'3 copy_orig_len: {e}')

    # --- 4 repreview flash after clamp preview ---
    try:
        host._last_ab_trial_fallback_import_conflict_preview_layout_default_slot_shortcut_rollback_ignore = {
            'index': 0, 'repreview_conflict_n': 2, 'repreview': {'conflict_n': 2}}
        host.refresh_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_default_slot_shortcut_history_rollback_conflicts_repreview_count_badge(2)
        prev = host.preview_clamp_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_default_slot_shortcut_history_rollback_conflicts_repreview_count_badge()
        assert prev.get('ok') and prev.get('preview') and prev.get('flashed'), prev
        fr = host.flash_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_default_slot_shortcut_history_rollback_conflicts_repreview_count_badge(ms=200)
        assert fr.get('ok') and fr.get('flashed'), fr
        ok(f'4 repreview flash prev_flashed={prev.get("flashed")} fr={fr.get("flashed")}')
    except Exception as e:
        bad(f'4 repreview flash: {e}')

    # --- 5 wheel clamp preview ---
    try:
        host.set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound_volume_mute_badge_bar_wheel_step(10, persist=True)
        host.refresh_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound_volume_mute_badge_bar_wheel_step_badge(10)
        menu = host.show_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound_volume_mute_badge_bar_wheel_step_badge_context_menu()
        assert menu.get('ok') and 'clamp_preview' in (menu.get('actions') or []), menu
        prev = host.preview_clamp_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound_volume_mute_badge_bar_wheel_step_badge()
        assert prev.get('ok') and prev.get('preview'), prev
        assert '夹紧预览' in str(prev.get('toast') or ''), prev
        ok(f'5 wheel clamp_preview actions={menu.get("actions")} toast={prev.get("toast")}')
    except Exception as e:
        bad(f'5 wheel clamp_preview: {e}')

    print(f'\nRESULT: {pass_n} passed, {fail_n} failed')
    return 0 if fail_n == 0 else 1

if __name__ == '__main__':
    raise SystemExit(main())
