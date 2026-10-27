#!/usr/bin/env python3
"""细妆92：夹紧预览 tip_prop_ok · 右键菜单 status_prop_ok 镜像."""
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
        assert hsm_src.count("'tip_prop_ok': bool(tip_prop_ok)") >= 8
        assert hsm_src.count("'status_prop_ok': bool(status_prop_ok)") >= 8
        assert "setProperty('repreviewCountBadgeStatus', status)" in hsm_src
        ok('wave124 APIs present')
    except Exception as e:
        bad(f'wave124 APIs present: {e}')
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

    # --- 1 clamp repreview tip_prop_ok ---
    try:
        host.ensure_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_default_slot_shortcut_history_rollback_conflicts_repreview_count_badge()
        host._last_ab_trial_fallback_import_conflict_preview_layout_default_slot_shortcut_rollback_ignore = {
            'index': 0, 'repreview_conflict_n': 2, 'repreview': {'conflict_n': 2}}
        out = host.preview_clamp_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_default_slot_shortcut_history_rollback_conflicts_repreview_count_badge()
        assert out.get('ok') and out.get('status_prop_ok') is True, out
        assert out.get('tip_prop_ok') is True, out
        assert str(out.get('tip_prop')) == str(out.get('tip')), out
        ok(f'1 clamp repreview tip_prop_ok={out.get("tip_prop_ok")} status={out.get("status_prop_ok")}')
    except Exception as e:
        bad(f'1 clamp repreview: {e}')

    # --- 2 clamp jump tip_prop_ok ---
    try:
        host.ensure_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_freq_import_merge_undo_stack_preview_bar_jump_delta_badge()
        out = host.preview_clamp_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_freq_import_merge_undo_stack_preview_bar_jump_delta_badge()
        assert out.get('ok') and out.get('tip_prop_ok') is True and out.get('status_prop_ok') is True, out
        ok(f'2 clamp jump tip_prop_ok={out.get("tip_prop_ok")}')
    except Exception as e:
        bad(f'2 clamp jump: {e}')

    # --- 3 clamp wheel tip_prop_ok ---
    try:
        host.ensure_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound_volume_mute_badge_bar_wheel_step_badge()
        out = host.preview_clamp_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound_volume_mute_badge_bar_wheel_step_badge()
        assert out.get('ok') and out.get('tip_prop_ok') is True and out.get('status_prop_ok') is True, out
        ok(f'3 clamp wheel tip_prop_ok={out.get("tip_prop_ok")}')
    except Exception as e:
        bad(f'3 clamp wheel: {e}')

    # --- 4-7 menu status_prop_ok ---
    try:
        host.ensure_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_default_slot_shortcut_history_rollback_conflicts_repreview_count_badge()
        menu = host.show_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_default_slot_shortcut_history_rollback_conflicts_repreview_count_badge_context_menu()
        assert menu.get('status_prop_ok') is True and menu.get('tip_prop_ok') is True, menu
        ok(f'4 repreview menu status_prop_ok={menu.get("status_prop_ok")} status={menu.get("status")}')
    except Exception as e:
        bad(f'4 repreview menu status: {e}')

    try:
        host.ensure_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy_overlap_batch_remove_undo_toast_history_badge()
        host.remember_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy_overlap_batch_remove_undo_toast(
            {'toast': '撤销批量移除 · 1', 'restored': ['a'], 'restored_n': 1})
        menu = host.show_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy_overlap_batch_remove_undo_toast_history_badge_context_menu()
        assert menu.get('status_prop_ok') is True and menu.get('tip_prop_ok') is True, menu
        ok(f'5 hist menu status_prop_ok={menu.get("status_prop_ok")}')
    except Exception as e:
        bad(f'5 hist menu status: {e}')

    try:
        host.ensure_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_freq_import_merge_undo_stack_preview_bar_jump_delta_badge()
        menu = host.show_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_freq_import_merge_undo_stack_preview_bar_jump_delta_badge_context_menu()
        assert menu.get('status_prop_ok') is True and menu.get('tip_prop_ok') is True, menu
        ok(f'6 jump menu status_prop_ok={menu.get("status_prop_ok")}')
    except Exception as e:
        bad(f'6 jump menu status: {e}')

    try:
        host.ensure_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound_volume_mute_badge_bar_wheel_step_badge()
        menu = host.show_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound_volume_mute_badge_bar_wheel_step_badge_context_menu()
        assert menu.get('status_prop_ok') is True and menu.get('tip_prop_ok') is True and menu.get('flash_ms_prop_ok') is True, menu
        ok(f'7 wheel menu status_prop_ok={menu.get("status_prop_ok")}')
    except Exception as e:
        bad(f'7 wheel menu status: {e}')

    print(f'\nRESULT: {pass_n} passed, {fail_n} failed')
    return 0 if fail_n == 0 else 1

if __name__ == '__main__':
    raise SystemExit(main())
