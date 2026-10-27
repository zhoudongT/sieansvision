#!/usr/bin/env python3
"""细妆76：档差旁标拖移边界夹紧 · 短史徽章点击开菜单 · 策略截断可配置长度 · 再预览角标双击复位 · 步进旁标悬停含已复位状态."""
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
        'def clamp_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_freq_import_merge_undo_stack_preview_bar_jump_delta_badge_pos',
        'import_merge_undo_preview_bar_jump_delta_badge_clamp',
        'def ensure_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy_overlap_batch_remove_undo_toast_history_badge',
        'def bind_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy_overlap_batch_remove_undo_toast_history_badge_click_menu',
        '点击打开短史菜单',
        'def strategy_badge_hover_tip_max_len',
        'def set_strategy_badge_hover_tip_max_len',
        'dstImportStrategyBadgeHoverTipMaxLen',
        'def dblclick_reset_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_default_slot_shortcut_history_rollback_conflicts_repreview_count_badge',
        '双击已复位再预览角标',
        "状态：{status}",
        '已复位',
    ]
    try:
        for m in markers:
            assert m in hsm_src, m
        ok('wave108 APIs present')
    except Exception as e:
        bad(f'wave108 APIs present: {e}')
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
    host._ics_strategy_shortcut_conflict_ignore_by_role_merge_strategy_overlap_batch_remove_undo_toast_hist_menu_no_exec = True

    # --- 1 jump-delta clamp ---
    try:
        host.refresh_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_freq_import_merge_undo_stack_preview_bar_jump_delta_badge(delta=3, from_idx=0, to_idx=3)
        badge = host.ensure_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_freq_import_merge_undo_stack_preview_bar_jump_delta_badge()
        assert badge is not None
        # negative → clamped to >=0
        cx, cy = host.clamp_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_freq_import_merge_undo_stack_preview_bar_jump_delta_badge_pos(-10, -20, badge)
        assert cx >= 0 and cy >= 0, (cx, cy)
        # move_to also clamps
        mv = host.move_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_freq_import_merge_undo_stack_preview_bar_jump_delta_badge_to(-5, -8, persist=False)
        assert mv.get('ok') and int(mv.get('x') if mv.get('x') is not None else -1) >= 0 and int(mv.get('y') if mv.get('y') is not None else -1) >= 0, mv
        # huge coords: if parent sized, should clamp under parent; else still >=0
        cx2, cy2 = host.clamp_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_freq_import_merge_undo_stack_preview_bar_jump_delta_badge_pos(99999, 99999, badge)
        assert cx2 >= 0 and cy2 >= 0, (cx2, cy2)
        pw = int(host.width() or 0)
        ph = int(host.height() or 0)
        if pw > 0 and ph > 0:
            assert cx2 <= pw and cy2 <= ph, (cx2, cy2, pw, ph)
        ok(f'1 clamp neg=({cx},{cy}) move=({mv.get("x")},{mv.get("y")}) huge=({cx2},{cy2}) parent={pw}x{ph}')
    except Exception as e:
        bad(f'1 clamp: {e}')

    # --- 2 hist badge click opens menu ---
    try:
        host.remember_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy_overlap_batch_remove_undo_toast(
            {'toast': '撤销批量移除 · 1', 'restored': ['a'], 'restored_n': 1})
        ref = host.refresh_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy_overlap_batch_remove_undo_toast_history_badge()
        assert ref.get('ok') and ref.get('click_opens_menu') is True, ref
        assert int(ref.get('count') if ref.get('count') is not None else -1) >= 1, ref
        badge = host.ensure_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy_overlap_batch_remove_undo_toast_history_badge()
        assert badge is not None and '短史' in str(badge.text() or ''), badge.text() if badge else None
        bind = host.bind_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy_overlap_batch_remove_undo_toast_history_badge_click_menu()
        assert bind.get('ok') and bind.get('bound'), bind
        # invoke menu via API (quiet)
        host._ics_strategy_shortcut_conflict_ignore_by_role_merge_strategy_overlap_batch_remove_undo_toast_hist_menu_no_exec = True
        menu = host.show_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy_overlap_batch_remove_undo_toast_history_menu()
        assert menu.get('ok'), menu
        tip = str(badge.toolTip() or '')
        assert '点击' in tip or '短史' in tip, tip
        ok(f'2 hist click bound={bind.get("bound")} shown={ref.get("shown")} menu_ok={menu.get("ok")} tip_has_click={"点击" in tip}')
    except Exception as e:
        bad(f'2 hist badge click: {e}')

    # --- 3 strategy tip max_len configurable ---
    try:
        cur = host.strategy_badge_hover_tip_max_len()
        assert isinstance(cur, int) and 16 <= cur <= 400, cur
        setr = host.set_strategy_badge_hover_tip_max_len(48, persist=True)
        assert setr.get('ok') and int(setr.get('max_len') if setr.get('max_len') is not None else -1) == 48, setr
        assert host.strategy_badge_hover_tip_max_len() == 48
        # truncate with default (configured) max_len
        long_tip = '甲' * 200
        trunc, flag = host.truncate_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover_tip(long_tip)
        assert flag is True and len(trunc) == 48 and trunc.endswith('…'), (len(trunc), trunc[-5:], flag)
        # override explicit
        trunc2, flag2 = host.truncate_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover_tip(long_tip, max_len=32)
        assert flag2 is True and len(trunc2) == 32, (len(trunc2), flag2)
        tip = host.tip_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover('merge')
        assert isinstance(tip, str) and len(tip) <= 48, (len(tip), tip)
        # restore default
        host.set_strategy_badge_hover_tip_max_len(96, persist=True)
        ok(f'3 tip max_len set=48 trunc={len(trunc)} tip_len={len(tip)} override32={len(trunc2)}')
    except Exception as e:
        bad(f'3 tip max_len: {e}')

    # --- 4 repreview dblclick reset ---
    try:
        host._last_ab_trial_fallback_import_conflict_preview_layout_default_slot_shortcut_rollback_ignore = {
            'index': 0, 'repreview_conflict_n': 2, 'repreview': {'conflict_n': 2}}
        ref = host.refresh_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_default_slot_shortcut_history_rollback_conflicts_repreview_count_badge(2)
        assert ref.get('ok') and int(ref.get('count') if ref.get('count') is not None else -1) == 2, ref
        mv = host.move_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_default_slot_shortcut_history_rollback_conflicts_repreview_count_badge_to(40, 160, persist=True)
        assert mv.get('ok') and int(mv.get('x') if mv.get('x') is not None else -1) == 40, mv
        bind = host.bind_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_default_slot_shortcut_history_rollback_conflicts_repreview_count_badge_dblclick_clear()
        assert bind.get('ok') and bind.get('bound'), bind
        dbl = host.dblclick_reset_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_default_slot_shortcut_history_rollback_conflicts_repreview_count_badge()
        assert dbl.get('ok') and dbl.get('reset') and dbl.get('via') == 'dblclick', dbl
        assert int(dbl.get('x') if dbl.get('x') is not None else -1) == 8 and int(dbl.get('y') if dbl.get('y') is not None else -1) == 120, dbl
        ok(f'4 repreview dblreset x={dbl.get("x")} y={dbl.get("y")} via={dbl.get("via")} cleared={dbl.get("cleared")}')
    except Exception as e:
        bad(f'4 repreview dblreset: {e}')

    # --- 5 wheel tip 已复位 status ---
    try:
        host.set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound_volume_mute_badge_bar_wheel_step(10, persist=True)
        tip10 = host.tip_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound_volume_mute_badge_bar_wheel_step_badge_hover(10)
        assert '状态：' in tip10 and '自定义' in tip10, tip10
        rst = host.reset_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound_volume_mute_badge_bar_wheel_step(persist=True)
        assert rst.get('ok') and rst.get('reset') and rst.get('status') == '已复位', rst
        assert rst.get('tip_has_reset_status') is True, rst
        tip5 = host.tip_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound_volume_mute_badge_bar_wheel_step_badge_hover(5)
        assert '状态：已复位' in tip5, tip5
        st = getattr(host, '_last_jitter_flash_done_sound_volume_mute_badge_bar_wheel_step_badge_hover_status', None)
        assert st == '已复位', st
        ok(f'5 wheel status tip5_has=已复位 tip10_custom={"自定义" in tip10} rst_status={rst.get("status")}')
    except Exception as e:
        bad(f'5 wheel status: {e}')

    print(f'\nRESULT: {pass_n} passed, {fail_n} failed')
    return 0 if fail_n == 0 else 1

if __name__ == '__main__':
    raise SystemExit(main())
