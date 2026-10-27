#!/usr/bin/env python3
"""细妆77：档差旁标悬停夹紧提示 · 短史徽章右键清短史 · 策略截断长度右键设档 · 再预览角标拖移夹紧 · 步进旁标双击复位."""
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
        'def tip_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_freq_import_merge_undo_stack_preview_bar_jump_delta_badge_hover',
        '边界：拖移夹紧到父客户区',
        'def show_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy_overlap_batch_remove_undo_toast_history_badge_context_menu',
        '清短史',
        '截断长度',
        'tip_max_len',
        'def clamp_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_default_slot_shortcut_history_rollback_conflicts_repreview_count_badge_pos',
        'def dblclick_reset_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound_volume_mute_badge_bar_wheel_step',
        '双击已复位步进',
    ]
    try:
        for m in markers:
            assert m in hsm_src, m
        ok('wave109 APIs present')
    except Exception as e:
        bad(f'wave109 APIs present: {e}')
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

    # --- 1 jump-delta hover clamp hint ---
    try:
        host.refresh_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_freq_import_merge_undo_stack_preview_bar_jump_delta_badge(delta=3, from_idx=0, to_idx=3)
        tip = host.tip_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_freq_import_merge_undo_stack_preview_bar_jump_delta_badge_hover(delta=3, from_idx=0, to_idx=3)
        assert '夹紧' in tip and '父客户区' in tip, tip
        assert '档差' in tip or '跳档' in tip, tip
        badge = host.ensure_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_freq_import_merge_undo_stack_preview_bar_jump_delta_badge()
        bt = str(badge.toolTip() or '') if badge is not None else ''
        assert '夹紧' in bt, bt
        ok(f'1 jump hover clamp tip_len={len(tip)} badge_tip_has_clamp=True')
    except Exception as e:
        bad(f'1 jump hover: {e}')

    # --- 2 hist badge RMB clear ---
    try:
        host.remember_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy_overlap_batch_remove_undo_toast(
            {'toast': '撤销批量移除 · 1', 'restored': ['a'], 'restored_n': 1})
        ref = host.refresh_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy_overlap_batch_remove_undo_toast_history_badge()
        assert ref.get('ok'), ref
        bind = host.bind_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy_overlap_batch_remove_undo_toast_history_badge_context_menu()
        assert bind.get('ok') and bind.get('bound'), bind
        menu = host.show_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy_overlap_batch_remove_undo_toast_history_badge_context_menu()
        assert menu.get('ok') and 'clear' in (menu.get('actions') or []), menu
        clr = host.clear_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy_overlap_batch_remove_undo_toast_history()
        assert clr.get('ok') and clr.get('cleared'), clr
        ok(f'2 hist RMB clear actions={menu.get("actions")} cleared={clr.get("cleared")}')
    except Exception as e:
        bad(f'2 hist RMB: {e}')

    # --- 3 strategy tip max_len menu ---
    try:
        host.set_strategy_badge_hover_tip_max_len(96, persist=True)
        menu = host.show_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_context_menu()
        assert menu.get('ok') and 'tip_max_len' in (menu.get('actions') or []), menu
        presets = menu.get('tip_max_len_presets') or []
        assert '48' in presets and '96' in presets and '160' in presets and '240' in presets, presets
        assert int(menu.get('tip_max_len') if menu.get('tip_max_len') is not None else -1) == 96, menu
        setr = host.set_strategy_badge_hover_tip_max_len(48, persist=True)
        assert setr.get('ok') and int(setr.get('max_len') if setr.get('max_len') is not None else -1) == 48, setr
        menu2 = host.show_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_context_menu()
        assert int(menu2.get('tip_max_len') if menu2.get('tip_max_len') is not None else -1) == 48, menu2
        host.set_strategy_badge_hover_tip_max_len(96, persist=True)
        ok(f'3 tip_max_len menu presets={presets} cur48={menu2.get("tip_max_len")}')
    except Exception as e:
        bad(f'3 tip_max_len menu: {e}')

    # --- 4 repreview clamp ---
    try:
        host._last_ab_trial_fallback_import_conflict_preview_layout_default_slot_shortcut_rollback_ignore = {
            'index': 0, 'repreview_conflict_n': 2, 'repreview': {'conflict_n': 2}}
        host.refresh_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_default_slot_shortcut_history_rollback_conflicts_repreview_count_badge(2)
        badge = host.ensure_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_default_slot_shortcut_history_rollback_conflicts_repreview_count_badge()
        assert badge is not None
        cx, cy = host.clamp_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_default_slot_shortcut_history_rollback_conflicts_repreview_count_badge_pos(-10, -20, badge)
        assert cx >= 0 and cy >= 0, (cx, cy)
        mv = host.move_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_default_slot_shortcut_history_rollback_conflicts_repreview_count_badge_to(-5, -8, persist=False)
        assert mv.get('ok') and int(mv.get('x') if mv.get('x') is not None else -1) >= 0 and int(mv.get('y') if mv.get('y') is not None else -1) >= 0, mv
        cx2, cy2 = host.clamp_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_default_slot_shortcut_history_rollback_conflicts_repreview_count_badge_pos(99999, 99999, badge)
        pw = int(host.width() or 0); ph = int(host.height() or 0)
        if pw > 0 and ph > 0:
            assert cx2 <= pw and cy2 <= ph, (cx2, cy2, pw, ph)
        ok(f'4 repreview clamp neg=({cx},{cy}) move=({mv.get("x")},{mv.get("y")}) huge=({cx2},{cy2})')
    except Exception as e:
        bad(f'4 repreview clamp: {e}')

    # --- 5 wheel dblclick reset ---
    try:
        host.set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound_volume_mute_badge_bar_wheel_step(10, persist=True)
        assert int(host.merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound_volume_mute_badge_bar_wheel_step()) == 10
        host.refresh_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound_volume_mute_badge_bar_wheel_step_badge(10)
        bind = host.bind_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound_volume_mute_badge_bar_wheel_step_badge_dblclick_reset()
        assert bind.get('ok') and bind.get('bound'), bind
        dbl = host.dblclick_reset_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound_volume_mute_badge_bar_wheel_step()
        assert dbl.get('ok') and dbl.get('reset') and dbl.get('via') == 'dblclick', dbl
        assert int(dbl.get('step') if dbl.get('step') is not None else -1) == 5, dbl
        assert '双击' in str(dbl.get('toast') or ''), dbl
        ok(f'5 wheel dblreset step={dbl.get("step")} via={dbl.get("via")} toast={dbl.get("toast")}')
    except Exception as e:
        bad(f'5 wheel dblreset: {e}')

    print(f'\nRESULT: {pass_n} passed, {fail_n} failed')
    return 0 if fail_n == 0 else 1

if __name__ == '__main__':
    raise SystemExit(main())
