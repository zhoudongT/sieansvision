#!/usr/bin/env python3
"""细妆82：步进闪标时长可配 · 再预览 tip 闪标档 · 短史 tip/status 闪标档 · 策略 tip 显示上次 toast · 档差改闪标档后刷新 tip."""
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
        'def wheel_step_badge_flash_ms',
        'def set_wheel_step_badge_flash_ms',
        'wheelStepBadgeFlashMs',
        "f'闪标档：{int(flash_ms)}ms'",
        'def tip_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy_overlap_batch_remove_undo_toast_history_badge_hover',
        '上次 toast：',
        'tip_refreshed',
    ]
    try:
        for m in markers:
            assert m in hsm_src, m
        ok('wave114 APIs present')
    except Exception as e:
        bad(f'wave114 APIs present: {e}')
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

    # --- 1 wheel flash_ms ---
    try:
        host.set_wheel_step_badge_flash_ms(600, persist=True)
        assert int(host.wheel_step_badge_flash_ms()) == 600
        host.set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound_volume_mute_badge_bar_wheel_step(10, persist=True)
        host.refresh_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound_volume_mute_badge_bar_wheel_step_badge(10)
        menu = host.show_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound_volume_mute_badge_bar_wheel_step_badge_context_menu()
        assert menu.get('ok') and 'flash_ms' in (menu.get('actions') or []), menu
        presets = menu.get('flash_ms_presets') or []
        assert '300' in presets and '1800' in presets, presets
        setr = host.set_wheel_step_badge_flash_ms(300, persist=True)
        assert setr.get('ok') and int(setr.get('ms') if setr.get('ms') is not None else -1) == 300, setr
        fr = host.flash_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound_volume_mute_badge_bar_wheel_step_badge()
        assert fr.get('ok') and fr.get('flashed') and int(fr.get('ms') if fr.get('ms') is not None else -1) == 300, fr
        tip = host.tip_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound_volume_mute_badge_bar_wheel_step_badge_hover()
        assert '闪标档：300ms' in tip, tip
        host.set_wheel_step_badge_flash_ms(600, persist=True)
        ok(f'1 wheel flash_ms presets={presets} used_ms={fr.get("ms")}')
    except Exception as e:
        bad(f'1 wheel flash_ms: {e}')

    # --- 2 repreview tip flash_ms ---
    try:
        host.set_repreview_count_badge_flash_ms(1200, persist=True)
        host._last_ab_trial_fallback_import_conflict_preview_layout_default_slot_shortcut_rollback_ignore = {
            'index': 0, 'repreview_conflict_n': 2, 'repreview': {'conflict_n': 2}}
        tip = host.tip_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_default_slot_shortcut_history_rollback_conflicts_repreview_count_badge_hover()
        assert '闪标档：1200ms' in tip, tip
        status = getattr(host, '_last_ab_trial_fallback_import_conflict_preview_layout_default_slot_shortcut_rollback_repreview_status', None)
        assert status == '闪标档：1200ms', status
        host.set_repreview_count_badge_flash_ms(600, persist=True)
        ok(f'2 repreview tip flash_ms status={status}')
    except Exception as e:
        bad(f'2 repreview tip: {e}')

    # --- 3 hist tip/status flash_ms ---
    try:
        host.set_batch_remove_undo_toast_history_badge_flash_ms(1800, persist=True)
        host.remember_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy_overlap_batch_remove_undo_toast(
            {'toast': '撤销批量移除 · 1', 'restored': ['a'], 'restored_n': 1})
        tip = host.tip_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy_overlap_batch_remove_undo_toast_history_badge_hover()
        assert '闪标档：1800ms' in tip, tip
        ref = host.refresh_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy_overlap_batch_remove_undo_toast_history_badge()
        assert ref.get('ok') and int(ref.get('flash_ms') if ref.get('flash_ms') is not None else -1) == 1800, ref
        assert ref.get('status') == '闪标档：1800ms', ref
        assert '闪标档：1800ms' in str(ref.get('tip') or ''), ref
        host.set_batch_remove_undo_toast_history_badge_flash_ms(600, persist=True)
        ok(f'3 hist tip/status flash_ms={ref.get("flash_ms")} status={ref.get("status")}')
    except Exception as e:
        bad(f'3 hist tip/status: {e}')

    # --- 4 strategy tip last toast ---
    try:
        host.set_strategy_badge_hover_tip_max_len(400, persist=True)
        tip0 = host.tip_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover()
        assert '上次 toast：无' in tip0, tip0
        cp = host.copy_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover_tip_orig_len()
        assert cp.get('ok') and cp.get('toast'), cp
        tip1 = host.tip_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover()
        assert f'上次 toast：{cp.get("toast")}' in tip1, tip1
        host.set_strategy_badge_hover_tip_max_len(96, persist=True)
        ok(f'4 last toast shown tip_has={cp.get("toast") in tip1}')
    except Exception as e:
        bad(f'4 strategy last toast: {e}')

    # --- 5 jump set flash_ms refreshes tip ---
    try:
        host.refresh_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_freq_import_merge_undo_stack_preview_bar_jump_delta_badge(delta=2, from_idx=0, to_idx=2)
        setr = host.set_jump_delta_badge_flash_ms(1800, persist=True)
        assert setr.get('ok') and setr.get('tip_refreshed'), setr
        assert '闪标档：1800ms' in str(setr.get('tip') or ''), setr
        assert setr.get('status') == '闪标档：1800ms', setr
        tip = host.tip_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_freq_import_merge_undo_stack_preview_bar_jump_delta_badge_hover()
        assert '闪标档：1800ms' in tip, tip
        badge = getattr(host, '_cycle_key_suggest_history_filter_presets_reorder_badge_freq_import_merge_undo_stack_preview_bar_jump_delta_badge', None)
        assert badge is not None and '闪标档：1800ms' in str(badge.toolTip() or ''), badge.toolTip() if badge else None
        host.set_jump_delta_badge_flash_ms(600, persist=True)
        ok(f'5 jump set refresh tip_refreshed={setr.get("tip_refreshed")} status={setr.get("status")}')
    except Exception as e:
        bad(f'5 jump set refresh tip: {e}')

    print(f'\nRESULT: {pass_n} passed, {fail_n} failed')
    return 0 if fail_n == 0 else 1

if __name__ == '__main__':
    raise SystemExit(main())
