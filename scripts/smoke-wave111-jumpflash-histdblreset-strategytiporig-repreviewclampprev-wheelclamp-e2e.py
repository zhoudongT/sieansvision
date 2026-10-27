#!/usr/bin/env python3
"""细妆79：档差夹紧预览后闪标 · 短史徽章双击复位 · 策略 tip 截断示原长 · 再预览右键夹紧预览 · 步进拖移夹紧边界."""
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
        'def flash_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_freq_import_merge_undo_stack_preview_bar_jump_delta_badge',
        "'flashed': flashed",
        'def dblclick_reset_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy_overlap_batch_remove_undo_toast_history_badge',
        '双击已复位短史徽章',
        '原长：',
        'def preview_clamp_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_default_slot_shortcut_history_rollback_conflicts_repreview_count_badge',
        'isAbRollbackRepreviewCountBadgeMenuClampPreview',
        'def clamp_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound_volume_mute_badge_bar_wheel_step_badge_pos',
        '边界：拖移夹紧到父客户区',
    ]
    try:
        for m in markers:
            assert m in hsm_src, m
        ok('wave111 APIs present')
    except Exception as e:
        bad(f'wave111 APIs present: {e}')
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

    # --- 1 jump clamp-preview flash ---
    try:
        host.refresh_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_freq_import_merge_undo_stack_preview_bar_jump_delta_badge(delta=3, from_idx=0, to_idx=3)
        prev = host.preview_clamp_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_freq_import_merge_undo_stack_preview_bar_jump_delta_badge()
        assert prev.get('ok') and prev.get('preview') and prev.get('flashed'), prev
        fr = host.flash_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_freq_import_merge_undo_stack_preview_bar_jump_delta_badge(ms=200)
        assert fr.get('ok') and fr.get('flashed'), fr
        badge = host.ensure_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_freq_import_merge_undo_stack_preview_bar_jump_delta_badge()
        ss = str(badge.styleSheet() or '') if badge is not None else ''
        assert 'e6a23c' in ss or 'border:2px' in ss or fr.get('flashed'), ss
        ok(f'1 jump flash flashed={prev.get("flashed")} fr={fr.get("flashed")}')
    except Exception as e:
        bad(f'1 jump flash: {e}')

    # --- 2 hist dblclick reset ---
    try:
        host.remember_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy_overlap_batch_remove_undo_toast(
            {'toast': '撤销批量移除 · 1', 'restored': ['a'], 'restored_n': 1})
        host.refresh_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy_overlap_batch_remove_undo_toast_history_badge()
        host.move_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy_overlap_batch_remove_undo_toast_history_badge_to(40, 200, persist=False)
        bind = host.bind_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy_overlap_batch_remove_undo_toast_history_badge_dblclick_reset()
        assert bind.get('ok') and bind.get('bound'), bind
        dbl = host.dblclick_reset_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy_overlap_batch_remove_undo_toast_history_badge()
        assert dbl.get('ok') and dbl.get('reset') and dbl.get('via') == 'dblclick', dbl
        assert int(dbl.get('x') if dbl.get('x') is not None else -1) == 8, dbl
        assert int(dbl.get('y') if dbl.get('y') is not None else -1) == 172, dbl
        assert '双击' in str(dbl.get('toast') or ''), dbl
        badge = host.ensure_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy_overlap_batch_remove_undo_toast_history_badge()
        assert badge is not None and int(badge.x()) == 8 and int(badge.y()) == 172
        ok(f'2 hist dblreset via={dbl.get("via")} pos=({dbl.get("x")},{dbl.get("y")})')
    except Exception as e:
        bad(f'2 hist dblreset: {e}')

    # --- 3 strategy tip orig_len when truncated ---
    try:
        host.set_strategy_badge_hover_tip_max_len(48, persist=True)
        tip = host.tip_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover()
        truncated = bool(getattr(host, '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover_tip_truncated', False))
        assert truncated, tip
        assert '原长：' in tip, tip
        orig = getattr(host, '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover_tip_orig_len', None)
        assert int(orig if orig is not None else -1) > 48, orig
        host.set_strategy_badge_hover_tip_max_len(400, persist=True)
        tip2 = host.tip_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover()
        truncated2 = bool(getattr(host, '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover_tip_truncated', True))
        assert not truncated2, tip2
        assert '原长：' not in tip2, tip2
        host.set_strategy_badge_hover_tip_max_len(96, persist=True)
        ok(f'3 tip orig_len truncated={truncated} orig={orig} untrunc_no_orig=True')
    except Exception as e:
        bad(f'3 strategy tip orig: {e}')

    # --- 4 repreview RMB clamp preview ---
    try:
        host._last_ab_trial_fallback_import_conflict_preview_layout_default_slot_shortcut_rollback_ignore = {
            'index': 0, 'repreview_conflict_n': 2, 'repreview': {'conflict_n': 2}}
        host.refresh_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_default_slot_shortcut_history_rollback_conflicts_repreview_count_badge(2)
        menu = host.show_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_default_slot_shortcut_history_rollback_conflicts_repreview_count_badge_context_menu()
        assert menu.get('ok') and 'clamp_preview' in (menu.get('actions') or []), menu
        prev = host.preview_clamp_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_default_slot_shortcut_history_rollback_conflicts_repreview_count_badge()
        assert prev.get('ok') and prev.get('preview'), prev
        assert '夹紧预览' in str(prev.get('toast') or ''), prev
        ok(f'4 repreview clamp_preview actions={menu.get("actions")} toast={prev.get("toast")}')
    except Exception as e:
        bad(f'4 repreview clamp_preview: {e}')

    # --- 5 wheel drag clamp ---
    try:
        host.set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound_volume_mute_badge_bar_wheel_step(10, persist=True)
        host.refresh_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound_volume_mute_badge_bar_wheel_step_badge(10)
        tip = host.tip_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound_volume_mute_badge_bar_wheel_step_badge_hover(10)
        assert '夹紧' in tip and '父客户区' in tip, tip
        cx, cy = host.clamp_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound_volume_mute_badge_bar_wheel_step_badge_pos(-10, -20)
        assert cx >= 0 and cy >= 0, (cx, cy)
        mv = host.move_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound_volume_mute_badge_bar_wheel_step_badge_to(-5, -8, persist=False)
        assert mv.get('ok') and int(mv.get('x') if mv.get('x') is not None else -1) >= 0 and int(mv.get('y') if mv.get('y') is not None else -1) >= 0, mv
        cx2, cy2 = host.clamp_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound_volume_mute_badge_bar_wheel_step_badge_pos(99999, 99999)
        pw = int(host.width() or 0); ph = int(host.height() or 0)
        if pw > 0 and ph > 0:
            assert cx2 <= pw and cy2 <= ph, (cx2, cy2, pw, ph)
        ok(f'5 wheel clamp neg=({cx},{cy}) move=({mv.get("x")},{mv.get("y")}) huge=({cx2},{cy2}) tip_has_clamp=True')
    except Exception as e:
        bad(f'5 wheel clamp: {e}')

    print(f'\nRESULT: {pass_n} passed, {fail_n} failed')
    return 0 if fail_n == 0 else 1

if __name__ == '__main__':
    raise SystemExit(main())
