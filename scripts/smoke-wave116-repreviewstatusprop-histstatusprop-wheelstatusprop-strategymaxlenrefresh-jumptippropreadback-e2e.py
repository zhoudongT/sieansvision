#!/usr/bin/env python3
"""细妆84：再预览/短史/步进旁标属性同步 status/flash_ms · 策略截断档改后刷新 tip · 档差 tip 写入 status 属性读回校验."""
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
        "repreviewCountBadgeStatus",
        "batchRemoveUndoToastHistoryBadgeStatus",
        "wheelStepBadgeStatus",
        "jump_delta_badge_status_prop_ok",
        "wave108/116: set configurable truncate length",
    ]
    try:
        for m in markers:
            assert m in hsm_src, m
        ok('wave116 APIs present')
    except Exception as e:
        bad(f'wave116 APIs present: {e}')
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

    # --- 1 repreview status/flash_ms property ---
    try:
        host._last_ab_trial_fallback_import_conflict_preview_layout_default_slot_shortcut_rollback_ignore = {
            'index': 0, 'repreview_conflict_n': 2, 'repreview': {'conflict_n': 2}}
        host.ensure_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_default_slot_shortcut_history_rollback_conflicts_repreview_count_badge()
        setr = host.set_repreview_count_badge_flash_ms(1800, persist=True)
        assert setr.get('ok') and setr.get('status') == '闪标档：1800ms', setr
        badge = getattr(host, '_ab_trial_fallback_import_conflict_preview_layout_default_slot_shortcut_rollback_repreview_count_badge', None)
        assert badge is not None
        assert badge.property('repreviewCountBadgeStatus') == '闪标档：1800ms', badge.property('repreviewCountBadgeStatus')
        assert int(badge.property('repreviewCountBadgeFlashMs') if badge.property('repreviewCountBadgeFlashMs') is not None else -1) == 1800
        ref = host.refresh_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_default_slot_shortcut_history_rollback_conflicts_repreview_count_badge(2)
        assert ref.get('ok') and ref.get('status') == '闪标档：1800ms', ref
        assert int(ref.get('flash_ms') if ref.get('flash_ms') is not None else -1) == 1800, ref
        assert badge.property('repreviewCountBadgeStatus') == '闪标档：1800ms'
        host.set_repreview_count_badge_flash_ms(600, persist=True)
        ok(f'1 repreview status prop flash={badge.property("repreviewCountBadgeFlashMs")}')
    except Exception as e:
        bad(f'1 repreview status prop: {e}')

    # --- 2 hist status/flash_ms property ---
    try:
        host.remember_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy_overlap_batch_remove_undo_toast(
            {'toast': '撤销批量移除 · 1', 'restored': ['a'], 'restored_n': 1})
        host.ensure_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy_overlap_batch_remove_undo_toast_history_badge()
        setr = host.set_batch_remove_undo_toast_history_badge_flash_ms(1200, persist=True)
        assert setr.get('ok') and setr.get('status') == '闪标档：1200ms', setr
        badge = getattr(host, '_ics_strategy_shortcut_conflict_ignore_by_role_merge_strategy_overlap_batch_remove_undo_toast_hist_badge', None)
        assert badge is not None
        assert badge.property('batchRemoveUndoToastHistoryBadgeStatus') == '闪标档：1200ms', badge.property('batchRemoveUndoToastHistoryBadgeStatus')
        assert int(badge.property('batchRemoveUndoToastHistoryBadgeFlashMs') if badge.property('batchRemoveUndoToastHistoryBadgeFlashMs') is not None else -1) == 1200
        ref = host.refresh_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy_overlap_batch_remove_undo_toast_history_badge()
        assert ref.get('ok') and ref.get('status') == '闪标档：1200ms', ref
        assert badge.property('batchRemoveUndoToastHistoryBadgeStatus') == '闪标档：1200ms'
        host.set_batch_remove_undo_toast_history_badge_flash_ms(600, persist=True)
        ok(f'2 hist status prop flash={badge.property("batchRemoveUndoToastHistoryBadgeFlashMs")}')
    except Exception as e:
        bad(f'2 hist status prop: {e}')

    # --- 3 wheel status/flash_ms property ---
    try:
        host.set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound_volume_mute_badge_bar_wheel_step(10, persist=True)
        host.ensure_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound_volume_mute_badge_bar_wheel_step_badge()
        setr = host.set_wheel_step_badge_flash_ms(300, persist=True)
        assert setr.get('ok') and setr.get('status') == '闪标档：300ms', setr
        badge = getattr(host, '_jitter_flash_done_sound_volume_mute_badge_bar_wheel_step_badge', None)
        assert badge is not None
        assert badge.property('wheelStepBadgeStatus') == '闪标档：300ms', badge.property('wheelStepBadgeStatus')
        assert int(badge.property('wheelStepBadgeFlashMs') if badge.property('wheelStepBadgeFlashMs') is not None else -1) == 300
        ref = host.refresh_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound_volume_mute_badge_bar_wheel_step_badge(10)
        assert ref.get('ok') and ref.get('status') == '闪标档：300ms', ref
        assert badge.property('wheelStepBadgeStatus') == '闪标档：300ms'
        host.set_wheel_step_badge_flash_ms(600, persist=True)
        ok(f'3 wheel status prop flash={badge.property("wheelStepBadgeFlashMs")}')
    except Exception as e:
        bad(f'3 wheel status prop: {e}')

    # --- 4 strategy max_len change refreshes tip/ToolTip ---
    try:
        host.ensure_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge()
        setr = host.set_strategy_badge_hover_tip_max_len(64, persist=True)
        assert setr.get('ok') and setr.get('tip_refreshed'), setr
        assert int(setr.get('max_len') if setr.get('max_len') is not None else -1) == 64, setr
        tip = str(setr.get('tip') or '')
        assert '截断档：64字' in tip, tip
        badge = getattr(host, '_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge', None)
        assert badge is not None and '截断档：64字' in str(badge.toolTip() or ''), badge.toolTip() if badge else None
        host.set_strategy_badge_hover_tip_max_len(96, persist=True)
        ok(f'4 strategy max_len refresh tip_refreshed={setr.get("tip_refreshed")} max_len={setr.get("max_len")}')
    except Exception as e:
        bad(f'4 strategy max_len refresh: {e}')

    # --- 5 jump tip writes status property + readback ---
    try:
        host.refresh_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_freq_import_merge_undo_stack_preview_bar_jump_delta_badge(delta=3, from_idx=0, to_idx=3)
        host.set_jump_delta_badge_flash_ms(1800, persist=True)
        tip = host.tip_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_freq_import_merge_undo_stack_preview_bar_jump_delta_badge_hover()
        assert '闪标档：1800ms' in tip, tip
        ok_flag = getattr(host, '_last_cycle_key_suggest_history_filter_presets_reorder_badge_freq_import_merge_undo_stack_preview_bar_jump_delta_badge_status_prop_ok', None)
        prop = getattr(host, '_last_cycle_key_suggest_history_filter_presets_reorder_badge_freq_import_merge_undo_stack_preview_bar_jump_delta_badge_status_prop', None)
        assert ok_flag is True, ok_flag
        assert prop == '闪标档：1800ms', prop
        badge = getattr(host, '_cycle_key_suggest_history_filter_presets_reorder_badge_freq_import_merge_undo_stack_preview_bar_jump_delta_badge', None)
        assert badge is not None and badge.property('jumpDeltaBadgeStatus') == '闪标档：1800ms'
        assert int(badge.property('jumpDeltaBadgeFlashMs') if badge.property('jumpDeltaBadgeFlashMs') is not None else -1) == 1800
        host.set_jump_delta_badge_flash_ms(600, persist=True)
        ok(f'5 jump tip status prop readback ok={ok_flag} prop={prop}')
    except Exception as e:
        bad(f'5 jump tip status prop readback: {e}')

    print(f'\nRESULT: {pass_n} passed, {fail_n} failed')
    return 0 if fail_n == 0 else 1

if __name__ == '__main__':
    raise SystemExit(main())
