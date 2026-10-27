#!/usr/bin/env python3
"""细妆81：再预览闪标时长可配 · 步进夹紧预览后闪标 · 短史闪标时长可配 · 策略复制原长写入悬停 toast · 档差闪标档写入 tip/status."""
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
        'def repreview_count_badge_flash_ms',
        'def set_repreview_count_badge_flash_ms',
        'repreviewCountBadgeFlashMs',
        'def flash_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound_volume_mute_badge_bar_wheel_step_badge',
        "'flashed': flashed",
        'def batch_remove_undo_toast_history_badge_flash_ms',
        'def set_batch_remove_undo_toast_history_badge_flash_ms',
        'batchRemoveUndoToastHistoryBadgeFlashMs',
        "f'可复制：菜单「复制悬停说明」/「复制原长」→toast'",
        "'toast': toast",
        "f'闪标档：{int(flash_ms)}ms'",
        "'status': status",
    ]
    try:
        for m in markers:
            assert m in hsm_src, m
        ok('wave113 APIs present')
    except Exception as e:
        bad(f'wave113 APIs present: {e}')
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

    # --- 1 repreview flash_ms ---
    try:
        host.set_repreview_count_badge_flash_ms(600, persist=True)
        assert int(host.repreview_count_badge_flash_ms()) == 600
        host._last_ab_trial_fallback_import_conflict_preview_layout_default_slot_shortcut_rollback_ignore = {
            'index': 0, 'repreview_conflict_n': 2, 'repreview': {'conflict_n': 2}}
        host.refresh_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_default_slot_shortcut_history_rollback_conflicts_repreview_count_badge(2)
        menu = host.show_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_default_slot_shortcut_history_rollback_conflicts_repreview_count_badge_context_menu()
        assert menu.get('ok') and 'flash_ms' in (menu.get('actions') or []), menu
        presets = menu.get('flash_ms_presets') or []
        assert '300' in presets and '600' in presets and '1200' in presets and '1800' in presets, presets
        assert int(menu.get('flash_ms') if menu.get('flash_ms') is not None else -1) == 600, menu
        setr = host.set_repreview_count_badge_flash_ms(300, persist=True)
        assert setr.get('ok') and int(setr.get('ms') if setr.get('ms') is not None else -1) == 300, setr
        fr = host.flash_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_default_slot_shortcut_history_rollback_conflicts_repreview_count_badge()
        assert fr.get('ok') and fr.get('flashed') and int(fr.get('ms') if fr.get('ms') is not None else -1) == 300, fr
        host.set_repreview_count_badge_flash_ms(600, persist=True)
        ok(f'1 repreview flash_ms presets={presets} used_ms={fr.get("ms")}')
    except Exception as e:
        bad(f'1 repreview flash_ms: {e}')

    # --- 2 wheel flash after clamp ---
    try:
        host.set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound_volume_mute_badge_bar_wheel_step(10, persist=True)
        host.refresh_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound_volume_mute_badge_bar_wheel_step_badge(10)
        prev = host.preview_clamp_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound_volume_mute_badge_bar_wheel_step_badge()
        assert prev.get('ok') and prev.get('preview') and prev.get('flashed'), prev
        fr = host.flash_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound_volume_mute_badge_bar_wheel_step_badge(ms=200)
        assert fr.get('ok') and fr.get('flashed'), fr
        ok(f'2 wheel flash prev_flashed={prev.get("flashed")} fr={fr.get("flashed")}')
    except Exception as e:
        bad(f'2 wheel flash: {e}')

    # --- 3 hist flash_ms ---
    try:
        host.set_batch_remove_undo_toast_history_badge_flash_ms(600, persist=True)
        assert int(host.batch_remove_undo_toast_history_badge_flash_ms()) == 600
        host.remember_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy_overlap_batch_remove_undo_toast(
            {'toast': '撤销批量移除 · 1', 'restored': ['a'], 'restored_n': 1})
        host.refresh_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy_overlap_batch_remove_undo_toast_history_badge()
        menu = host.show_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy_overlap_batch_remove_undo_toast_history_badge_context_menu()
        assert menu.get('ok') and 'flash_ms' in (menu.get('actions') or []), menu
        presets = menu.get('flash_ms_presets') or []
        assert '300' in presets and '1800' in presets, presets
        setr = host.set_batch_remove_undo_toast_history_badge_flash_ms(1200, persist=True)
        assert setr.get('ok') and int(setr.get('ms') if setr.get('ms') is not None else -1) == 1200, setr
        fr = host.flash_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy_overlap_batch_remove_undo_toast_history_badge()
        assert fr.get('ok') and fr.get('flashed') and int(fr.get('ms') if fr.get('ms') is not None else -1) == 1200, fr
        host.set_batch_remove_undo_toast_history_badge_flash_ms(600, persist=True)
        ok(f'3 hist flash_ms presets={presets} used_ms={fr.get("ms")}')
    except Exception as e:
        bad(f'3 hist flash_ms: {e}')

    # --- 4 strategy copy orig toast ---
    try:
        host.set_strategy_badge_hover_tip_max_len(400, persist=True)
        tip = host.tip_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover()
        assert '→toast' in tip or '复制原长」→toast' in tip, tip
        cp = host.copy_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover_tip_orig_len()
        assert cp.get('ok') and cp.get('copied') and cp.get('toast'), cp
        assert '已复制' in str(cp.get('toast') or '') and '原长' in str(cp.get('toast') or ''), cp
        hover_toast = getattr(host, '_last_dst_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_hover_toast', None)
        assert hover_toast == cp.get('toast'), hover_toast
        host.set_strategy_badge_hover_tip_max_len(96, persist=True)
        ok(f'4 copy_orig toast={cp.get("toast")}')
    except Exception as e:
        bad(f'4 copy_orig toast: {e}')

    # --- 5 jump flash_ms tip/status ---
    try:
        host.set_jump_delta_badge_flash_ms(1200, persist=True)
        host.refresh_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_freq_import_merge_undo_stack_preview_bar_jump_delta_badge(delta=3, from_idx=0, to_idx=3)
        tip = host.tip_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_freq_import_merge_undo_stack_preview_bar_jump_delta_badge_hover()
        assert '闪标档：1200ms' in tip, tip
        last = getattr(host, '_last_cycle_key_suggest_history_filter_presets_reorder_badge_freq_import_merge_undo_stack_preview_bar_jump_delta_badge', None) or {}
        assert int(last.get('flash_ms') if last.get('flash_ms') is not None else -1) == 1200, last
        assert last.get('status') == '闪标档：1200ms', last
        status = getattr(host, '_last_cycle_key_suggest_history_filter_presets_reorder_badge_freq_import_merge_undo_stack_preview_bar_jump_delta_badge_status', None)
        assert status == '闪标档：1200ms', status
        host.set_jump_delta_badge_flash_ms(600, persist=True)
        ok(f'5 jump tip/status flash_ms=1200 tip_has={("闪标档：1200ms" in tip)} status={status}')
    except Exception as e:
        bad(f'5 jump tip/status: {e}')

    print(f'\nRESULT: {pass_n} passed, {fail_n} failed')
    return 0 if fail_n == 0 else 1

if __name__ == '__main__':
    raise SystemExit(main())
