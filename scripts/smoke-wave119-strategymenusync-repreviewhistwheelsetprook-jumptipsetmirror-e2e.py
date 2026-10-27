#!/usr/bin/env python3
"""细妆87：策略菜单同步 out 属性 · 再预览/短史/步进 set status_prop_ok · 档差 tip/set 读回镜像."""
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
        assert 'strategy_prop_ok' in hsm_src
        assert "flash_ms_prop_ok': bool(flash_ms_prop_ok)" in hsm_src
        assert 'jumpDeltaBadgeHoverTip' in hsm_src
        assert hsm_src.count("'status_prop_ok': bool(status_prop_ok)") >= 7
        ok('wave119 APIs present')
    except Exception as e:
        bad(f'wave119 APIs present: {e}')
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

    # --- 1 strategy menu sync out props ---
    try:
        host.ensure_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge()
        host.set_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy('overwrite', persist=True)
        host.copy_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover_tip_orig_len()
        host.set_strategy_badge_hover_tip_max_len(160, persist=True)
        menu = host.show_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_context_menu()
        assert menu.get('ok') is True, menu
        assert menu.get('strategy') == 'overwrite', menu
        assert menu.get('strategy_prop_ok') is True, menu
        assert menu.get('strategy_prop') == 'overwrite', menu
        assert menu.get('tip_max_len_prop_ok') is True, menu
        assert int(menu.get('tip_max_len_prop') if menu.get('tip_max_len_prop') is not None else -1) == 160, menu
        assert menu.get('last_toast_brief_prop_ok') is True, menu
        host.set_strategy_badge_hover_tip_max_len(96, persist=True)
        host.set_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy('merge', persist=True)
        ok(f'1 strategy menu sync strategy_prop_ok={menu.get("strategy_prop_ok")} tip_ml={menu.get("tip_max_len_prop")}')
    except Exception as e:
        bad(f'1 strategy menu sync: {e}')

    # --- 2 repreview set status_prop_ok + flash_ms_prop_ok ---
    try:
        host._last_ab_trial_fallback_import_conflict_preview_layout_default_slot_shortcut_rollback_ignore = {
            'index': 0, 'repreview_conflict_n': 2, 'repreview': {'conflict_n': 2}}
        host.ensure_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_default_slot_shortcut_history_rollback_conflicts_repreview_count_badge()
        setr = host.set_repreview_count_badge_flash_ms(1800, persist=True)
        assert setr.get('ok') and setr.get('status_prop_ok') is True, setr
        assert setr.get('flash_ms_prop_ok') is True, setr
        assert setr.get('status_prop') == '闪标档：1800ms', setr
        assert int(setr.get('flash_ms_prop') if setr.get('flash_ms_prop') is not None else -1) == 1800, setr
        host.set_repreview_count_badge_flash_ms(600, persist=True)
        ok(f'2 repreview set status_prop_ok={setr.get("status_prop_ok")} flash_ms_prop_ok={setr.get("flash_ms_prop_ok")}')
    except Exception as e:
        bad(f'2 repreview set: {e}')

    # --- 3 hist set status_prop_ok + flash_ms_prop_ok ---
    try:
        host.remember_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy_overlap_batch_remove_undo_toast(
            {'toast': '撤销批量移除 · 1', 'restored': ['a'], 'restored_n': 1})
        host.ensure_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy_overlap_batch_remove_undo_toast_history_badge()
        setr = host.set_batch_remove_undo_toast_history_badge_flash_ms(1200, persist=True)
        assert setr.get('ok') and setr.get('status_prop_ok') is True, setr
        assert setr.get('flash_ms_prop_ok') is True, setr
        assert setr.get('status_prop') == '闪标档：1200ms', setr
        host.set_batch_remove_undo_toast_history_badge_flash_ms(600, persist=True)
        ok(f'3 hist set status_prop_ok={setr.get("status_prop_ok")} flash_ms_prop_ok={setr.get("flash_ms_prop_ok")}')
    except Exception as e:
        bad(f'3 hist set: {e}')

    # --- 4 wheel set status_prop_ok + flash_ms_prop_ok ---
    try:
        host.set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound_volume_mute_badge_bar_wheel_step(10, persist=True)
        host.ensure_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound_volume_mute_badge_bar_wheel_step_badge()
        setr = host.set_wheel_step_badge_flash_ms(300, persist=True)
        assert setr.get('ok') and setr.get('status_prop_ok') is True, setr
        assert setr.get('flash_ms_prop_ok') is True, setr
        assert setr.get('status_prop') == '闪标档：300ms', setr
        host.set_wheel_step_badge_flash_ms(600, persist=True)
        ok(f'4 wheel set status_prop_ok={setr.get("status_prop_ok")} flash_ms_prop_ok={setr.get("flash_ms_prop_ok")}')
    except Exception as e:
        bad(f'4 wheel set: {e}')

    # --- 5 jump tip/set readback mirror ---
    try:
        host.refresh_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_freq_import_merge_undo_stack_preview_bar_jump_delta_badge(delta=2, from_idx=0, to_idx=2)
        host.set_jump_delta_badge_flash_ms(1800, persist=True)
        tip = host.tip_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_freq_import_merge_undo_stack_preview_bar_jump_delta_badge_hover()
        assert '闪标档：1800ms' in tip, tip
        tip_ok = getattr(host, '_last_cycle_key_suggest_history_filter_presets_reorder_badge_freq_import_merge_undo_stack_preview_bar_jump_delta_badge_tip_prop_ok', None)
        fm_ok = getattr(host, '_last_cycle_key_suggest_history_filter_presets_reorder_badge_freq_import_merge_undo_stack_preview_bar_jump_delta_badge_flash_ms_prop_ok', None)
        st_ok = getattr(host, '_last_cycle_key_suggest_history_filter_presets_reorder_badge_freq_import_merge_undo_stack_preview_bar_jump_delta_badge_status_prop_ok', None)
        assert tip_ok is True, tip_ok
        assert fm_ok is True, fm_ok
        assert st_ok is True, st_ok
        setr = host.set_jump_delta_badge_flash_ms(1200, persist=True)
        assert setr.get('ok') and setr.get('status_prop_ok') is True, setr
        assert setr.get('tip_prop_ok') is True, setr
        assert setr.get('flash_ms_prop_ok') is True, setr
        assert int(setr.get('flash_ms_prop') if setr.get('flash_ms_prop') is not None else -1) == 1200, setr
        host.set_jump_delta_badge_flash_ms(600, persist=True)
        ok(f'5 jump tip/set mirror tip_ok={tip_ok} set tip/fm={setr.get("tip_prop_ok")}/{setr.get("flash_ms_prop_ok")}')
    except Exception as e:
        bad(f'5 jump tip/set mirror: {e}')

    # --- 6 more badge property round-trips (set outs persist attrs) ---
    try:
        setr = host.set_repreview_count_badge_flash_ms(300, persist=True)
        assert setr.get('flash_ms_prop_ok') is True and setr.get('status_prop_ok') is True, setr
        last = getattr(host, '_last_ab_trial_fallback_import_conflict_preview_layout_default_slot_shortcut_rollback_repreview_flash_ms_set', None)
        assert isinstance(last, dict) and last.get('flash_ms_prop_ok') is True, last
        seth = host.set_batch_remove_undo_toast_history_badge_flash_ms(1800, persist=True)
        assert seth.get('flash_ms_prop_ok') is True, seth
        setw = host.set_wheel_step_badge_flash_ms(1200, persist=True)
        assert setw.get('flash_ms_prop_ok') is True, setw
        host.set_repreview_count_badge_flash_ms(600, persist=True)
        host.set_batch_remove_undo_toast_history_badge_flash_ms(600, persist=True)
        host.set_wheel_step_badge_flash_ms(600, persist=True)
        ok(f'6 more round-trips repreview/hist/wheel flash_ms_prop_ok')
    except Exception as e:
        bad(f'6 more round-trips: {e}')

    print(f'\nRESULT: {pass_n} passed, {fail_n} failed')
    return 0 if fail_n == 0 else 1

if __name__ == '__main__':
    raise SystemExit(main())
