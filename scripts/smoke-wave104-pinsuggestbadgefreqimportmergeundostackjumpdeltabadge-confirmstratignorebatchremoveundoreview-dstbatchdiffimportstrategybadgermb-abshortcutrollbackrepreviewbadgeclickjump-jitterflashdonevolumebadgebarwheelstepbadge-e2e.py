#!/usr/bin/env python3
"""细妆72：跳档档差旁标持久 · 撤销批量移除toast可回看 · 策略徽章右键菜单 · 再预览角标点击跳冲突 · 滚轮步进旁标显示."""
from __future__ import annotations
import sys
import json
import tempfile
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
        'def ensure_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_freq_import_merge_undo_stack_preview_bar_jump_delta_badge',
        'def refresh_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_freq_import_merge_undo_stack_preview_bar_jump_delta_badge',
        '档差旁标',
        'def remember_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy_overlap_batch_remove_undo_toast',
        'def review_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy_overlap_batch_remove_undo_toast',
        '回看撤销批量移除',
        'def show_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_context_menu',
        'def bind_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_context_menu',
        '徽章右键菜单',
        'def jump_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_default_slot_shortcut_history_rollback_conflicts_repreview_count_badge_to_conflict',
        'def bind_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_default_slot_shortcut_history_rollback_conflicts_repreview_count_badge_click_jump',
        '跳冲突',
        'def ensure_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound_volume_mute_badge_bar_wheel_step_badge',
        'def refresh_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound_volume_mute_badge_bar_wheel_step_badge',
        '步进旁标',
        '步进·',
    ]
    try:
        for m in markers:
            assert m in hsm_src, m
        ok('wave104 APIs present')
    except Exception as e:
        bad(f'wave104 APIs present: {e}')
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
    host._dst_reorder_shortcut_conflict_history_batch_diff_import_no_dialog = True
    host._ab_trial_fallback_import_conflict_preview_layout_slots_dialog_no_exec = True
    host._ab_trial_fallback_import_conflict_preview_layout_default_slot_shortcut_rebind_no_dialog = True
    host._ab_trial_fallback_import_conflict_preview_layout_default_slot_shortcut_rollback_no_confirm = True
    host._jitter_reorder_undo_lab_menu_no_exec = True
    host._jitter_reorder_undo_depth_lab_flash_done_sound_wav_no_dialog = True
    host._jitter_reorder_undo_depth_lab_flash_done_sound_volume_no_dialog = True

    # --- 1 jump delta badge ---
    try:
        host._cycle_key_suggest_history_filter_presets_reorder_badge_freq_import_merge_undo_stack = []
        host._cycle_key_suggest_history_filter_presets_reorder_badge_freq_import_merge_undo_snap = None
        host.set_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_freq_presets(
            [{'name': '快', 'ms': 400}], persist=True)
        host.set_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_freq_ms(400, persist=True)
        host.set_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_freq_import_merge_strategy(
            'prefer_incoming', persist=True)
        with tempfile.TemporaryDirectory() as td:
            p1 = str(Path(td) / 'freq1.json')
            Path(p1).write_text(json.dumps({'presets': [{'name': '快', 'ms': 350}, {'name': '慢', 'ms': 1500}], 'freq_ms': 700}, ensure_ascii=False), encoding='utf-8')
            p2 = str(Path(td) / 'freq2.json')
            Path(p2).write_text(json.dumps({'presets': [{'name': '中', 'ms': 900}], 'freq_ms': 900}, ensure_ascii=False), encoding='utf-8')
            host._cycle_key_suggest_history_filter_presets_reorder_badge_freq_import_merge_no_dialog = True
            host._cycle_key_suggest_history_filter_presets_reorder_badge_freq_import_merge_smoke_path = p1
            assert host.merge_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_freq_import(persist=True).get('undo_ready')
            host._cycle_key_suggest_history_filter_presets_reorder_badge_freq_import_merge_smoke_path = p2
            assert host.merge_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_freq_import(persist=True).get('undo_ready')
            host.refresh_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_freq_import_merge_undo_stack_preview_bar(focus=0)
            jmp = host.jump_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_freq_import_merge_undo_stack_preview_bar_to(1, persist=True)
            assert jmp.get('ok') is True, jmp
            badge = host.refresh_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_freq_import_merge_undo_stack_preview_bar_jump_delta_badge()
            assert badge.get('ok') and '档差' in str(badge.get('text') or ''), badge
            assert int(badge.get('delta') or 0) == int(jmp.get('delta') or 0), (badge, jmp)
            last = getattr(host, '_last_cycle_key_suggest_history_filter_presets_reorder_badge_freq_import_merge_undo_stack_preview_bar_jump_delta_badge', None) or {}
            assert last.get('ok') is True, last
        ok(f'1 jump delta badge text={badge.get("text")} delta={badge.get("delta")}')
    except Exception as e:
        bad(f'1 jump delta badge: {e}')

    # --- 2 undo toast review ---
    try:
        keys = ['Ctrl+Alt+21', 'Ctrl+Alt+22']
        for k in keys:
            host.add_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore(k, persist=False)
        host.highlight_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy_overlap_rows(keys)
        br = host.batch_remove_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy_overlap_highlight_keys(persist=True)
        assert br.get('ok') and int(br.get('removed_n') or 0) >= 2, br
        undo = host.undo_batch_remove_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy_overlap_highlight_keys(persist=True)
        assert undo.get('ok') and int(undo.get('restored_n') or 0) >= 2, undo
        hist = host.list_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy_overlap_batch_remove_undo_toast_history(limit=4)
        assert isinstance(hist, list) and len(hist) >= 1, hist
        rev = host.review_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy_overlap_batch_remove_undo_toast(-1)
        assert rev.get('ok') is True and int(rev.get('restored_n') or 0) >= 2, rev
        ok(f'2 undo toast review n={rev.get("restored_n")} hist={len(hist)}')
    except Exception as e:
        bad(f'2 undo toast review: {e}')

    # --- 3 strategy badge RMB ---
    try:
        host.set_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy('merge', persist=True)
        bind = host.bind_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_context_menu()
        assert bind.get('ok') or bind.get('bound'), bind
        menu = host.show_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_context_menu()
        assert menu.get('ok') is True, menu
        assert 'merge' in (menu.get('actions') or []) and 'toggle' in (menu.get('actions') or []), menu
        ok(f'3 badge RMB strategy={menu.get("strategy")} actions={menu.get("actions")}')
    except Exception as e:
        bad(f'3 badge RMB: {e}')

    # --- 4 repreview badge click jump ---
    try:
        host.remember_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_default_slot_shortcut_history(
            'Ctrl+Shift+W', persist=False)
        ign = host.ignore_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_default_slot_shortcut_history_rollback_conflicts(0, persist=True)
        assert ign.get('ok') is True, ign
        bind = host.bind_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_default_slot_shortcut_history_rollback_conflicts_repreview_count_badge_click_jump()
        assert bind.get('ok') or bind.get('bound'), bind
        jmp = host.jump_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_default_slot_shortcut_history_rollback_conflicts_repreview_count_badge_to_conflict()
        assert jmp.get('ok') is True and 'conflict_n' in jmp, jmp
        assert '跳冲突' in str(jmp.get('toast') or ''), jmp
        ok(f'4 repreview click jump n={jmp.get("conflict_n")} first={jmp.get("first")}')
    except Exception as e:
        bad(f'4 repreview click jump: {e}')

    # --- 5 wheel step badge ---
    try:
        host.set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound_volume_mute_badge_bar_wheel_step(10, persist=True)
        badge = host.refresh_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound_volume_mute_badge_bar_wheel_step_badge()
        assert badge.get('ok') and badge.get('step') == 10 and '步进·10%' in str(badge.get('text') or ''), badge
        host.set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound_volume_mute_badge_bar_wheel_step(5, persist=True)
        last = getattr(host, '_last_jitter_flash_done_sound_volume_mute_badge_bar_wheel_step_badge', None) or {}
        assert last.get('step') == 5 and '步进·5%' in str(last.get('text') or ''), last
        ok(f'5 wheel step badge {badge.get("text")}->{last.get("text")}')
    except Exception as e:
        bad(f'5 wheel step badge: {e}')

    print(f'\nRESULT: {pass_n} passed, {fail_n} failed')
    return 0 if fail_n == 0 else 1

if __name__ == '__main__':
    raise SystemExit(main())
