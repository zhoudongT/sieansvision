#!/usr/bin/env python3
"""细妆75：档差旁标双击复位确认toast · 清短史后徽章刷新 · 策略悬停说明长度截断 · 再预览角标右键复位 · 步进旁标右键复位步进."""
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
        'def dblclick_reset_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_freq_import_merge_undo_stack_preview_bar_jump_delta_badge',
        '双击已复位档差旁标',
        'def refresh_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy_overlap_batch_remove_undo_toast_history_badge',
        'badge_refreshed',
        '撤销短史',
        'def truncate_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover_tip',
        'def reset_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_default_slot_shortcut_history_rollback_conflicts_repreview_count_badge_pos',
        '再预览角标已复位',
        'def reset_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound_volume_mute_badge_bar_wheel_step',
        '复位步进',
    ]
    try:
        for m in markers:
            assert m in hsm_src, m
        ok('wave107 APIs present')
    except Exception as e:
        bad(f'wave107 APIs present: {e}')
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

    # --- 1 jump delta dblclick reset toast ---
    try:
        host.refresh_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_freq_import_merge_undo_stack_preview_bar_jump_delta_badge(delta=3, from_idx=0, to_idx=3)
        mv = host.move_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_freq_import_merge_undo_stack_preview_bar_jump_delta_badge_to(50, 200, persist=True)
        assert mv.get('ok') and mv.get('x') == 50, mv
        dbl = host.dblclick_reset_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_freq_import_merge_undo_stack_preview_bar_jump_delta_badge()
        assert dbl.get('ok') and dbl.get('reset') and dbl.get('via') == 'dblclick', dbl
        assert dbl.get('x') == 8 and dbl.get('y') == 148, dbl
        assert '双击' in str(dbl.get('toast') or ''), dbl
        ok(f'1 dblclick reset x={dbl.get("x")} y={dbl.get("y")} toast={dbl.get("toast")}')
    except Exception as e:
        bad(f'1 dblclick reset: {e}')

    # --- 2 clear hist → badge refresh ---
    try:
        host.remember_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy_overlap_batch_remove_undo_toast(
            {'toast': '撤销批量移除 · 1', 'restored': ['a'], 'restored_n': 1})
        host.remember_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy_overlap_batch_remove_undo_toast(
            {'toast': '撤销批量移除 · 2', 'restored': ['b', 'c'], 'restored_n': 2})
        ref = host.refresh_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy_overlap_batch_remove_undo_toast_history_badge()
        assert ref.get('ok') and ref.get('refreshed') and int(ref.get('count') if ref.get('count') is not None else -1) == 2, ref
        assert '短史' in str(ref.get('tip') or ref.get('text') or ''), ref
        clr = host.clear_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy_overlap_batch_remove_undo_toast_history()
        assert clr.get('ok') and clr.get('cleared') and clr.get('badge_refreshed') is True, clr
        assert int(clr.get('count') if clr.get('count') is not None else -1) == 0, clr
        ref0 = host.refresh_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy_overlap_batch_remove_undo_toast_history_badge()
        assert int(ref0.get('count') if ref0.get('count') is not None else -1) == 0, ref0
        ok(f'2 hist badge was={clr.get("was")} refreshed={clr.get("badge_refreshed")} count0={ref0.get("count")}')
    except Exception as e:
        bad(f'2 hist badge: {e}')

    # --- 3 strategy hover tip truncate ---
    try:
        tip = host.tip_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover('merge')
        assert isinstance(tip, str) and len(tip) <= 96, (len(tip), tip)
        long_tip = '甲' * 200
        trunc, flag = host.truncate_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover_tip(long_tip, max_len=96)
        assert flag is True and len(trunc) == 96 and trunc.endswith('…'), (len(trunc), trunc[-5:], flag)
        short, flag2 = host.truncate_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover_tip('短', max_len=96)
        assert flag2 is False and short == '短', (short, flag2)
        ok(f'3 tip truncate len={len(tip)} long={len(trunc)} flag={flag}')
    except Exception as e:
        bad(f'3 tip truncate: {e}')

    # --- 4 repreview RMB reset ---
    try:
        host._last_ab_trial_fallback_import_conflict_preview_layout_default_slot_shortcut_rollback_ignore = {
            'index': 0, 'repreview_conflict_n': 2, 'repreview': {'conflict_n': 2}}
        ref = host.refresh_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_default_slot_shortcut_history_rollback_conflicts_repreview_count_badge(2)
        assert ref.get('ok') and int(ref.get('count') or 0) == 2, ref
        bind = host.bind_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_default_slot_shortcut_history_rollback_conflicts_repreview_count_badge_context_menu()
        assert bind.get('ok') and bind.get('bound'), bind
        mv = host.move_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_default_slot_shortcut_history_rollback_conflicts_repreview_count_badge_to(40, 160, persist=True)
        assert mv.get('ok') and mv.get('x') == 40, mv
        menu = host.show_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_default_slot_shortcut_history_rollback_conflicts_repreview_count_badge_context_menu()
        assert menu.get('ok') and 'reset' in (menu.get('actions') or []), menu
        rst = host.reset_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_default_slot_shortcut_history_rollback_conflicts_repreview_count_badge_pos(persist=True)
        assert rst.get('ok') and rst.get('reset') and rst.get('x') == 8 and rst.get('y') == 120, rst
        ok(f'4 repreview reset x={rst.get("x")} y={rst.get("y")} actions={menu.get("actions")}')
    except Exception as e:
        bad(f'4 repreview reset: {e}')

    # --- 5 wheel step reset ---
    try:
        host.set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound_volume_mute_badge_bar_wheel_step(10, persist=True)
        cur = host.merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound_volume_mute_badge_bar_wheel_step()
        assert int(cur) == 10, cur
        menu = host.show_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound_volume_mute_badge_bar_wheel_step_badge_context_menu()
        assert menu.get('ok') and 'reset' in (menu.get('actions') or []), menu
        rst = host.reset_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound_volume_mute_badge_bar_wheel_step(persist=True)
        assert rst.get('ok') and rst.get('reset') and int(rst.get('step') if rst.get('step') is not None else -1) == 5, rst
        tip = host.tip_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound_volume_mute_badge_bar_wheel_step_badge_hover(5)
        assert '复位步进' in tip, tip
        ok(f'5 wheel step reset step={rst.get("step")} actions={menu.get("actions")}')
    except Exception as e:
        bad(f'5 wheel step reset: {e}')

    print(f'\nRESULT: {pass_n} passed, {fail_n} failed')
    return 0 if fail_n == 0 else 1

if __name__ == '__main__':
    raise SystemExit(main())
