#!/usr/bin/env python3
"""细妆78：档差旁标右键夹紧预览 · 短史徽章拖移 · 策略截断当前档写入 tip · 再预览悬停夹紧边界 · 步进旁标拖移."""
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
        'def preview_clamp_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_freq_import_merge_undo_stack_preview_bar_jump_delta_badge',
        '夹紧预览',
        'clamp_preview',
        'def bind_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy_overlap_batch_remove_undo_toast_history_badge_drag',
        'icsBatchRemoveUndoToastHistoryBadgePos',
        '截断档：',
        'def tip_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_default_slot_shortcut_history_rollback_conflicts_repreview_count_badge_hover',
        '边界：拖移夹紧到父客户区（越界归零）',
        'def bind_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound_volume_mute_badge_bar_wheel_step_badge_drag',
        'jitterFlashDoneSoundVolumeMuteBadgeBarWheelStepBadgePos',
    ]
    try:
        for m in markers:
            assert m in hsm_src, m
        ok('wave110 APIs present')
    except Exception as e:
        bad(f'wave110 APIs present: {e}')
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

    # --- 1 jump-delta RMB clamp preview ---
    try:
        host.refresh_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_freq_import_merge_undo_stack_preview_bar_jump_delta_badge(delta=3, from_idx=0, to_idx=3)
        menu = host.show_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_freq_import_merge_undo_stack_preview_bar_jump_delta_badge_context_menu()
        assert menu.get('ok') and 'clamp_preview' in (menu.get('actions') or []), menu
        prev = host.preview_clamp_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_freq_import_merge_undo_stack_preview_bar_jump_delta_badge()
        assert prev.get('ok') and prev.get('preview'), prev
        assert '夹紧预览' in str(prev.get('toast') or ''), prev
        assert 'max_x' in prev and 'clamped_x' in prev, prev
        ok(f'1 jump clamp_preview actions={menu.get("actions")} toast={prev.get("toast")}')
    except Exception as e:
        bad(f'1 jump clamp_preview: {e}')

    # --- 2 hist badge drag ---
    try:
        host.remember_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy_overlap_batch_remove_undo_toast(
            {'toast': '撤销批量移除 · 1', 'restored': ['a'], 'restored_n': 1})
        ref = host.refresh_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy_overlap_batch_remove_undo_toast_history_badge()
        assert ref.get('ok'), ref
        bind = host.bind_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy_overlap_batch_remove_undo_toast_history_badge_drag()
        assert bind.get('ok') and bind.get('bound'), bind
        mv = host.move_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy_overlap_batch_remove_undo_toast_history_badge_to(24, 180, persist=False)
        assert mv.get('ok') and int(mv.get('x') if mv.get('x') is not None else -1) == 24, mv
        assert int(mv.get('y') if mv.get('y') is not None else -1) == 180, mv
        badge = host.ensure_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy_overlap_batch_remove_undo_toast_history_badge()
        assert badge is not None and int(badge.x()) == 24 and int(badge.y()) == 180, (badge.x() if badge else None, badge.y() if badge else None)
        ok(f'2 hist drag bound={bind.get("bound")} move=({mv.get("x")},{mv.get("y")})')
    except Exception as e:
        bad(f'2 hist drag: {e}')

    # --- 3 strategy tip shows current max_len ---
    try:
        host.set_strategy_badge_hover_tip_max_len(96, persist=True)
        tip_fn = None
        # find tip builder via refresh path
        tip = host.tip_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover()
        assert '截断档：' in tip, tip
        assert '96' in tip, tip
        shown = getattr(host, '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover_tip_max_len_shown', None)
        assert int(shown if shown is not None else -1) == 96, shown
        host.set_strategy_badge_hover_tip_max_len(48, persist=True)
        tip2 = host.tip_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover()
        assert '截断档：48' in tip2 or '截断档：48字' in tip2, tip2
        host.set_strategy_badge_hover_tip_max_len(96, persist=True)
        ok(f'3 strategy tip max_len line tip_has96=True tip2_has48=True shown={shown}')
    except Exception as e:
        bad(f'3 strategy tip max_len: {e}')

    # --- 4 repreview hover clamp tip ---
    try:
        host._last_ab_trial_fallback_import_conflict_preview_layout_default_slot_shortcut_rollback_ignore = {
            'index': 0, 'repreview_conflict_n': 2, 'repreview': {'conflict_n': 2}}
        tip = host.tip_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_default_slot_shortcut_history_rollback_conflicts_repreview_count_badge_hover(2)
        assert '夹紧' in tip and '父客户区' in tip, tip
        assert '2' in tip, tip
        host.refresh_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_default_slot_shortcut_history_rollback_conflicts_repreview_count_badge(2)
        badge = host.ensure_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_default_slot_shortcut_history_rollback_conflicts_repreview_count_badge()
        bt = str(badge.toolTip() or '') if badge is not None else ''
        assert '夹紧' in bt and '父客户区' in bt, bt
        ok(f'4 repreview hover tip_len={len(tip)} badge_tip_has_clamp=True')
    except Exception as e:
        bad(f'4 repreview hover: {e}')

    # --- 5 wheel-step badge drag ---
    try:
        host.set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound_volume_mute_badge_bar_wheel_step(10, persist=True)
        host.refresh_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound_volume_mute_badge_bar_wheel_step_badge(10)
        bind = host.bind_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound_volume_mute_badge_bar_wheel_step_badge_drag()
        assert bind.get('ok') and bind.get('bound'), bind
        mv = host.move_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound_volume_mute_badge_bar_wheel_step_badge_to(30, 190, persist=False)
        assert mv.get('ok') and int(mv.get('x') if mv.get('x') is not None else -1) == 30, mv
        assert int(mv.get('y') if mv.get('y') is not None else -1) == 190, mv
        badge = host.ensure_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound_volume_mute_badge_bar_wheel_step_badge()
        assert badge is not None and int(badge.x()) == 30 and int(badge.y()) == 190
        ok(f'5 wheel drag bound={bind.get("bound")} move=({mv.get("x")},{mv.get("y")})')
    except Exception as e:
        bad(f'5 wheel drag: {e}')

    print(f'\nRESULT: {pass_n} passed, {fail_n} failed')
    return 0 if fail_n == 0 else 1

if __name__ == '__main__':
    raise SystemExit(main())
