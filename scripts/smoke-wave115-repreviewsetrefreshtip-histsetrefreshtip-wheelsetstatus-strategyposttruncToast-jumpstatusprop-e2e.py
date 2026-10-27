#!/usr/bin/env python3
"""细妆83：再预览/短史改闪标档后刷新 tip · 步进 tip/status 同步闪标档 · 策略截断后仍见上次 toast · 档差 status 旁标属性同步."""
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
        "tip_refreshed': tip_refreshed, 'tip': tip, 'status': status}",
        'def set_repreview_count_badge_flash_ms',
        'def set_batch_remove_undo_toast_history_badge_flash_ms',
        'def set_wheel_step_badge_flash_ms',
        "jumpDeltaBadgeStatus",
        '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover_toast_brief',
        '_last_jitter_flash_done_sound_volume_mute_badge_bar_wheel_step_badge_status',
    ]
    try:
        for m in markers:
            assert m in hsm_src, m
        ok('wave115 APIs present')
    except Exception as e:
        bad(f'wave115 APIs present: {e}')
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

    # --- 1 repreview set flash_ms refreshes tip ---
    try:
        host._last_ab_trial_fallback_import_conflict_preview_layout_default_slot_shortcut_rollback_ignore = {
            'index': 0, 'repreview_conflict_n': 2, 'repreview': {'conflict_n': 2}}
        host.ensure_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_default_slot_shortcut_history_rollback_conflicts_repreview_count_badge()
        setr = host.set_repreview_count_badge_flash_ms(1800, persist=True)
        assert setr.get('ok') and setr.get('tip_refreshed'), setr
        assert '闪标档：1800ms' in str(setr.get('tip') or ''), setr
        assert setr.get('status') == '闪标档：1800ms', setr
        tip = host.tip_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_default_slot_shortcut_history_rollback_conflicts_repreview_count_badge_hover()
        assert '闪标档：1800ms' in tip, tip
        badge = getattr(host, '_ab_trial_fallback_import_conflict_preview_layout_default_slot_shortcut_rollback_repreview_count_badge', None)
        assert badge is not None and '闪标档：1800ms' in str(badge.toolTip() or ''), badge.toolTip() if badge else None
        host.set_repreview_count_badge_flash_ms(600, persist=True)
        ok(f'1 repreview set refresh tip_refreshed={setr.get("tip_refreshed")} status={setr.get("status")}')
    except Exception as e:
        bad(f'1 repreview set refresh tip: {e}')

    # --- 2 hist set flash_ms refreshes tip ---
    try:
        host.remember_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy_overlap_batch_remove_undo_toast(
            {'toast': '撤销批量移除 · 1', 'restored': ['a'], 'restored_n': 1})
        host.ensure_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy_overlap_batch_remove_undo_toast_history_badge()
        setr = host.set_batch_remove_undo_toast_history_badge_flash_ms(1200, persist=True)
        assert setr.get('ok') and setr.get('tip_refreshed'), setr
        assert '闪标档：1200ms' in str(setr.get('tip') or ''), setr
        assert setr.get('status') == '闪标档：1200ms', setr
        badge = getattr(host, '_ics_strategy_shortcut_conflict_ignore_by_role_merge_strategy_overlap_batch_remove_undo_toast_hist_badge', None)
        assert badge is not None and '闪标档：1200ms' in str(badge.toolTip() or ''), badge.toolTip() if badge else None
        host.set_batch_remove_undo_toast_history_badge_flash_ms(600, persist=True)
        ok(f'2 hist set refresh tip_refreshed={setr.get("tip_refreshed")} status={setr.get("status")}')
    except Exception as e:
        bad(f'2 hist set refresh tip: {e}')

    # --- 3 wheel tip/status sync flash_ms ---
    try:
        host.set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound_volume_mute_badge_bar_wheel_step(10, persist=True)
        host.ensure_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound_volume_mute_badge_bar_wheel_step_badge()
        setr = host.set_wheel_step_badge_flash_ms(300, persist=True)
        assert setr.get('ok') and setr.get('tip_refreshed'), setr
        assert '闪标档：300ms' in str(setr.get('tip') or ''), setr
        assert setr.get('status') == '闪标档：300ms', setr
        status = getattr(host, '_last_jitter_flash_done_sound_volume_mute_badge_bar_wheel_step_badge_status', None)
        assert status == '闪标档：300ms', status
        ref = host.refresh_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound_volume_mute_badge_bar_wheel_step_badge(10)
        assert ref.get('ok') and int(ref.get('flash_ms') if ref.get('flash_ms') is not None else -1) == 300, ref
        assert ref.get('status') == '闪标档：300ms', ref
        assert '闪标档：300ms' in str(ref.get('tip') or ''), ref
        badge = getattr(host, '_jitter_flash_done_sound_volume_mute_badge_bar_wheel_step_badge', None)
        assert badge is not None and '闪标档：300ms' in str(badge.toolTip() or ''), badge.toolTip() if badge else None
        host.set_wheel_step_badge_flash_ms(600, persist=True)
        ok(f'3 wheel tip/status sync flash_ms={ref.get("flash_ms")} status={ref.get("status")}')
    except Exception as e:
        bad(f'3 wheel tip/status sync: {e}')

    # --- 4 strategy tip truncated still shows last toast summary ---
    try:
        host.set_strategy_badge_hover_tip_max_len(400, persist=True)
        cp = host.copy_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover_tip_orig_len()
        assert cp.get('ok') and cp.get('toast'), cp
        # force severe truncate so body is cut; last toast must still appear after
        host.set_strategy_badge_hover_tip_max_len(48, persist=True)
        tip = host.tip_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover()
        assert '上次 toast：' in tip, tip
        brief = getattr(host, '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover_toast_brief', None)
        assert brief and brief != '无', brief
        assert f'上次 toast：{brief}' in tip, tip
        truncated = getattr(host, '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover_tip_truncated', None)
        assert truncated is True, truncated
        host.set_strategy_badge_hover_tip_max_len(96, persist=True)
        ok(f'4 strategy post-trunc toast brief={brief!r} truncated={truncated}')
    except Exception as e:
        bad(f'4 strategy post-trunc toast: {e}')

    # --- 5 jump status property sync ---
    try:
        ref = host.refresh_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_freq_import_merge_undo_stack_preview_bar_jump_delta_badge(delta=2, from_idx=0, to_idx=2)
        assert ref.get('ok') and ref.get('status') == '闪标档：600ms', ref
        badge = getattr(host, '_cycle_key_suggest_history_filter_presets_reorder_badge_freq_import_merge_undo_stack_preview_bar_jump_delta_badge', None)
        assert badge is not None, 'no jump badge'
        assert badge.property('jumpDeltaBadgeStatus') == '闪标档：600ms', badge.property('jumpDeltaBadgeStatus')
        assert int(badge.property('jumpDeltaBadgeFlashMs') if badge.property('jumpDeltaBadgeFlashMs') is not None else -1) == 600, badge.property('jumpDeltaBadgeFlashMs')
        setr = host.set_jump_delta_badge_flash_ms(1800, persist=True)
        assert setr.get('ok') and setr.get('tip_refreshed'), setr
        assert badge.property('jumpDeltaBadgeStatus') == '闪标档：1800ms', badge.property('jumpDeltaBadgeStatus')
        assert int(badge.property('jumpDeltaBadgeFlashMs') if badge.property('jumpDeltaBadgeFlashMs') is not None else -1) == 1800, badge.property('jumpDeltaBadgeFlashMs')
        host.set_jump_delta_badge_flash_ms(600, persist=True)
        ok(f'5 jump status prop sync status={badge.property("jumpDeltaBadgeStatus")} flash={badge.property("jumpDeltaBadgeFlashMs")}')
    except Exception as e:
        bad(f'5 jump status prop: {e}')

    print(f'\nRESULT: {pass_n} passed, {fail_n} failed')
    return 0 if fail_n == 0 else 1

if __name__ == '__main__':
    raise SystemExit(main())
