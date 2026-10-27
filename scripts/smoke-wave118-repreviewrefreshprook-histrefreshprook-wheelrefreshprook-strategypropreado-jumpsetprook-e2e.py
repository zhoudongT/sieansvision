#!/usr/bin/env python3
"""细妆86：再预览/短史/步进 refresh status_prop_ok · 策略 tip/set 读回校验 · 档差 set_flash_ms status_prop_ok."""
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
        "repreview_count_badge = dict(out)",
        "'status_prop_ok': bool(status_prop_ok)}",
        "tip_max_len_prop_ok",
        "last_toast_brief_prop_ok",
        "jump_delta_badge_flash_ms_set = dict(out)",
    ]
    try:
        # ensure key strings exist
        assert 'tip_max_len_prop_ok' in hsm_src
        assert 'last_toast_brief_prop_ok' in hsm_src
        assert hsm_src.count("'status_prop_ok': bool(status_prop_ok)") >= 4
        ok('wave118 APIs present')
    except Exception as e:
        bad(f'wave118 APIs present: {e}')
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

    # --- 1 repreview refresh status_prop_ok ---
    try:
        host._last_ab_trial_fallback_import_conflict_preview_layout_default_slot_shortcut_rollback_ignore = {
            'index': 0, 'repreview_conflict_n': 2, 'repreview': {'conflict_n': 2}}
        host.set_repreview_count_badge_flash_ms(1800, persist=True)
        ref = host.refresh_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_default_slot_shortcut_history_rollback_conflicts_repreview_count_badge(2)
        assert ref.get('ok') and ref.get('status_prop_ok') is True, ref
        assert ref.get('status_prop') == '闪标档：1800ms', ref
        assert int(ref.get('flash_ms') if ref.get('flash_ms') is not None else -1) == 1800, ref
        host.set_repreview_count_badge_flash_ms(600, persist=True)
        ok(f'1 repreview refresh status_prop_ok={ref.get("status_prop_ok")}')
    except Exception as e:
        bad(f'1 repreview refresh status_prop_ok: {e}')

    # --- 2 hist refresh status_prop_ok ---
    try:
        host.remember_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy_overlap_batch_remove_undo_toast(
            {'toast': '撤销批量移除 · 1', 'restored': ['a'], 'restored_n': 1})
        host.set_batch_remove_undo_toast_history_badge_flash_ms(1200, persist=True)
        ref = host.refresh_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy_overlap_batch_remove_undo_toast_history_badge()
        assert ref.get('ok') and ref.get('status_prop_ok') is True, ref
        assert ref.get('status_prop') == '闪标档：1200ms', ref
        host.set_batch_remove_undo_toast_history_badge_flash_ms(600, persist=True)
        ok(f'2 hist refresh status_prop_ok={ref.get("status_prop_ok")}')
    except Exception as e:
        bad(f'2 hist refresh status_prop_ok: {e}')

    # --- 3 wheel refresh status_prop_ok ---
    try:
        host.set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound_volume_mute_badge_bar_wheel_step(10, persist=True)
        host.set_wheel_step_badge_flash_ms(300, persist=True)
        ref = host.refresh_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound_volume_mute_badge_bar_wheel_step_badge(10)
        assert ref.get('ok') and ref.get('status_prop_ok') is True, ref
        assert ref.get('status_prop') == '闪标档：300ms', ref
        host.set_wheel_step_badge_flash_ms(600, persist=True)
        ok(f'3 wheel refresh status_prop_ok={ref.get("status_prop_ok")}')
    except Exception as e:
        bad(f'3 wheel refresh status_prop_ok: {e}')

    # --- 4 strategy tip/set readback ---
    try:
        host.ensure_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge()
        cp = host.copy_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover_tip_orig_len()
        assert cp.get('ok') and cp.get('toast'), cp
        setr = host.set_strategy_badge_hover_tip_max_len(72, persist=True)
        assert setr.get('ok') and setr.get('tip_max_len_prop_ok') is True, setr
        assert setr.get('last_toast_brief_prop_ok') is True, setr
        assert int(setr.get('tip_max_len_prop') if setr.get('tip_max_len_prop') is not None else -1) == 72, setr
        tip = host.tip_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover()
        assert '上次 toast：' in tip, tip
        ml_ok = getattr(host, '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover_tip_max_len_prop_ok', None)
        br_ok = getattr(host, '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover_toast_brief_prop_ok', None)
        assert ml_ok is True, ml_ok
        assert br_ok is True, br_ok
        host.set_strategy_badge_hover_tip_max_len(96, persist=True)
        ok(f'4 strategy tip/set readback set_ok={setr.get("tip_max_len_prop_ok")}/{setr.get("last_toast_brief_prop_ok")} tip_ok={ml_ok}/{br_ok}')
    except Exception as e:
        bad(f'4 strategy tip/set readback: {e}')

    # --- 5 jump set_flash_ms status_prop_ok ---
    try:
        host.refresh_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_freq_import_merge_undo_stack_preview_bar_jump_delta_badge(delta=2, from_idx=0, to_idx=2)
        setr = host.set_jump_delta_badge_flash_ms(1800, persist=True)
        assert setr.get('ok') and setr.get('tip_refreshed'), setr
        assert setr.get('status_prop_ok') is True, setr
        assert setr.get('status_prop') == '闪标档：1800ms', setr
        assert setr.get('status') == '闪标档：1800ms', setr
        host.set_jump_delta_badge_flash_ms(600, persist=True)
        ok(f'5 jump set status_prop_ok={setr.get("status_prop_ok")} prop={setr.get("status_prop")}')
    except Exception as e:
        bad(f'5 jump set status_prop_ok: {e}')

    print(f'\nRESULT: {pass_n} passed, {fail_n} failed')
    return 0 if fail_n == 0 else 1

if __name__ == '__main__':
    raise SystemExit(main())
