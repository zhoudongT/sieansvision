#!/usr/bin/env python3
"""细妆90：再预览/短史/步进 set_flash_ms tip_prop · 右键菜单 flash_ms_prop_ok."""
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
        assert "setProperty('repreviewCountBadgeHoverTip', tip)" in hsm_src
        assert "setProperty('batchRemoveUndoToastHistoryBadgeHoverTip', tip)" in hsm_src
        assert "setProperty('wheelStepBadgeHoverTip', tip)" in hsm_src
        assert hsm_src.count("'flash_ms_prop_ok': bool(flash_ms_prop_ok)") >= 6
        ok('wave122 APIs present')
    except Exception as e:
        bad(f'wave122 APIs present: {e}')
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
    host._ab_trial_fallback_import_conflict_preview_layout_quiet = True
    host._jitter_reorder_undo_lab_menu_no_exec = True
    host._jitter_reorder_undo_depth_lab_flash_done_quiet = True

    # --- 1 set_repreview flash tip_prop_ok ---
    try:
        host.ensure_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_default_slot_shortcut_history_rollback_conflicts_repreview_count_badge()
        host._last_ab_trial_fallback_import_conflict_preview_layout_default_slot_shortcut_rollback_ignore = {
            'index': 0, 'repreview_conflict_n': 2, 'repreview': {'conflict_n': 2}}
        out = host.set_repreview_count_badge_flash_ms(1200, persist=True)
        assert out.get('ok') and out.get('tip_prop_ok') is True, out
        assert out.get('flash_ms_prop_ok') is True, out
        assert str(out.get('tip_prop')) == str(out.get('tip')), out
        host.set_repreview_count_badge_flash_ms(600, persist=True)
        ok(f'1 set_repreview tip_prop_ok={out.get("tip_prop_ok")} flash={out.get("flash_ms_prop_ok")}')
    except Exception as e:
        bad(f'1 set_repreview tip_prop: {e}')

    # --- 2 set_hist flash tip_prop_ok ---
    try:
        host.ensure_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy_overlap_batch_remove_undo_toast_history_badge()
        host.remember_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy_overlap_batch_remove_undo_toast(
            {'toast': '撤销批量移除 · 1', 'restored': ['a'], 'restored_n': 1})
        out = host.set_batch_remove_undo_toast_history_badge_flash_ms(1200, persist=True)
        assert out.get('ok') and out.get('tip_prop_ok') is True, out
        assert out.get('flash_ms_prop_ok') is True, out
        host.set_batch_remove_undo_toast_history_badge_flash_ms(600, persist=True)
        ok(f'2 set_hist tip_prop_ok={out.get("tip_prop_ok")}')
    except Exception as e:
        bad(f'2 set_hist tip_prop: {e}')

    # --- 3 set_wheel flash tip_prop_ok ---
    try:
        host.ensure_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound_volume_mute_badge_bar_wheel_step_badge()
        out = host.set_wheel_step_badge_flash_ms(1200, persist=True)
        assert out.get('ok') and out.get('tip_prop_ok') is True, out
        assert out.get('flash_ms_prop_ok') is True, out
        host.set_wheel_step_badge_flash_ms(600, persist=True)
        ok(f'3 set_wheel tip_prop_ok={out.get("tip_prop_ok")}')
    except Exception as e:
        bad(f'3 set_wheel tip_prop: {e}')

    # --- 4 repreview menu flash_ms_prop_ok ---
    try:
        host.ensure_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_default_slot_shortcut_history_rollback_conflicts_repreview_count_badge()
        menu = host.show_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_default_slot_shortcut_history_rollback_conflicts_repreview_count_badge_context_menu()
        assert menu.get('ok') and menu.get('shown') is False, menu
        assert menu.get('flash_ms_prop_ok') is True, menu
        ok(f'4 repreview menu flash_ms_prop_ok={menu.get("flash_ms_prop_ok")} ms={menu.get("flash_ms")}')
    except Exception as e:
        bad(f'4 repreview menu: {e}')

    # --- 5 hist menu flash_ms_prop_ok ---
    try:
        host.ensure_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy_overlap_batch_remove_undo_toast_history_badge()
        menu = host.show_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy_overlap_batch_remove_undo_toast_history_badge_context_menu()
        assert menu.get('ok') and menu.get('shown') is False, menu
        assert menu.get('flash_ms_prop_ok') is True, menu
        ok(f'5 hist menu flash_ms_prop_ok={menu.get("flash_ms_prop_ok")}')
    except Exception as e:
        bad(f'5 hist menu: {e}')

    # --- 6 wheel menu flash_ms_prop_ok ---
    try:
        host.ensure_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound_volume_mute_badge_bar_wheel_step_badge()
        menu = host.show_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound_volume_mute_badge_bar_wheel_step_badge_context_menu()
        assert menu.get('ok') and menu.get('shown') is False, menu
        assert menu.get('flash_ms_prop_ok') is True, menu
        ok(f'6 wheel menu flash_ms_prop_ok={menu.get("flash_ms_prop_ok")}')
    except Exception as e:
        bad(f'6 wheel menu: {e}')

    print(f'\nRESULT: {pass_n} passed, {fail_n} failed')
    return 0 if fail_n == 0 else 1

if __name__ == '__main__':
    raise SystemExit(main())
