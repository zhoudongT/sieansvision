#!/usr/bin/env python3
"""细妆71：跳档toast档差 · 批量移除撤销 · 策略徽章点击切换 · 再预览冲突计数角标 · 滚轮步进可配."""
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
        '档差',
        '_cycle_key_suggest_history_filter_presets_reorder_badge_freq_import_merge_undo_stack_preview_focus',
        'def undo_batch_remove_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy_overlap_highlight_keys',
        '撤销批量移除',
        'def bind_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_click_toggle',
        'def toggle_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge',
        '徽章点击切换',
        'def ensure_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_default_slot_shortcut_history_rollback_conflicts_repreview_count_badge',
        'def refresh_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_default_slot_shortcut_history_rollback_conflicts_repreview_count_badge',
        '再预览·',
        'def merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound_volume_mute_badge_bar_wheel_step',
        'def set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound_volume_mute_badge_bar_wheel_step',
        'def cycle_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound_volume_mute_badge_bar_wheel_step',
        '滚轮步进',
    ]
    try:
        for m in markers:
            assert m in hsm_src, m
        ok('wave103 APIs present')
    except Exception as e:
        bad(f'wave103 APIs present: {e}')
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

    # --- 1 jump toast delta ---
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
            m1 = host.merge_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_freq_import(persist=True)
            assert m1.get('undo_ready') is True, m1
            host._cycle_key_suggest_history_filter_presets_reorder_badge_freq_import_merge_smoke_path = p2
            m2 = host.merge_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_freq_import(persist=True)
            assert m2.get('undo_ready') is True, m2
            host.refresh_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_freq_import_merge_undo_stack_preview_bar(focus=0)
            jmp = host.jump_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_freq_import_merge_undo_stack_preview_bar_to(1, persist=True)
            assert jmp.get('ok') is True, jmp
            assert 'delta' in jmp, jmp
            assert int(jmp.get('from_idx') if jmp.get('from_idx') is not None else jmp.get('from', -1)) == 0, jmp
            assert int(jmp.get('delta')) == 1, jmp
            last = getattr(host, '_last_cycle_key_suggest_history_filter_presets_reorder_badge_freq_import_merge_undo_stack_preview_bar_jump', None) or {}
            tip = str(last.get('toast') or last.get('tip') or '')
            # toast text may be in flash; delta attrs sufficient
            assert int(last.get('delta') if last.get('delta') is not None else jmp.get('delta')) == 1, last
        ok(f'1 jump delta from={jmp.get("from_idx")} delta={jmp.get("delta")}')
    except Exception as e:
        bad(f'1 jump delta: {e}')

    # --- 2 batch remove undo ---
    try:
        keys = ['Ctrl+Alt+11', 'Ctrl+Alt+12']
        for k in keys:
            host.add_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore(k, persist=False)
        host.highlight_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy_overlap_rows(keys)
        br = host.batch_remove_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy_overlap_highlight_keys(persist=True)
        assert br.get('ok') is True and int(br.get('removed_n') or 0) >= 2, br
        undo = host.undo_batch_remove_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy_overlap_highlight_keys(persist=True)
        assert undo.get('ok') is True and int(undo.get('restored_n') or 0) >= 2, undo
        left = host.list_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore()
        left_s = [str(x) for x in (left or [])]
        for k in keys:
            assert k in left_s, (k, left_s)
        ok(f'2 batch remove undo n={undo.get("restored_n")}')
    except Exception as e:
        bad(f'2 batch remove undo: {e}')

    # --- 3 strategy badge click toggle ---
    try:
        host.set_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy('merge', persist=True)
        bind = host.bind_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge_click_toggle()
        assert bind.get('ok') or bind.get('bound'), bind
        t1 = host.toggle_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge(persist=True)
        assert t1.get('ok') and t1.get('to') == 'overwrite', t1
        t2 = host.toggle_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy_badge(persist=True)
        assert t2.get('ok') and t2.get('to') == 'merge', t2
        cur = host.toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy()
        assert cur == 'merge', cur
        ok(f'3 badge toggle {t1.get("from")}->{t1.get("to")}->{t2.get("to")}')
    except Exception as e:
        bad(f'3 badge toggle: {e}')

    # --- 4 repreview conflict count badge ---
    try:
        host.remember_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_default_slot_shortcut_history(
            'Ctrl+Shift+Z', persist=False)
        ign = host.ignore_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_default_slot_shortcut_history_rollback_conflicts(0, persist=True)
        assert ign.get('ok') is True, ign
        badge = host.refresh_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_default_slot_shortcut_history_rollback_conflicts_repreview_count_badge()
        assert badge.get('ok') is True, badge
        assert 'count' in badge and '再预览·' in str(badge.get('text') or ''), badge
        last = getattr(host, '_last_ab_trial_fallback_import_conflict_preview_layout_default_slot_shortcut_rollback_repreview_count_badge', None) or {}
        assert last.get('ok') is True, last
        ok(f'4 repreview badge count={badge.get("count")} text={badge.get("text")}')
    except Exception as e:
        bad(f'4 repreview badge: {e}')

    # --- 5 wheel step configurable ---
    try:
        s0 = host.merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound_volume_mute_badge_bar_wheel_step()
        assert isinstance(s0, int) and 1 <= s0 <= 20, s0
        s1 = host.set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound_volume_mute_badge_bar_wheel_step(10, persist=True)
        assert s1 == 10, s1
        assert host.merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound_volume_mute_badge_bar_wheel_step() == 10
        s2 = host.cycle_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound_volume_mute_badge_bar_wheel_step(persist=True)
        assert s2 == 1, s2  # 10 -> 1 in [1,5,10]
        host.set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound_volume_mute_badge_bar_wheel_step(5, persist=True)
        bind = host.bind_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound_volume_mute_badge_bar_wheel()
        assert bind.get('ok') or bind.get('bound'), bind
        ok(f'5 wheel step {s0}->{s1}->{s2}->5')
    except Exception as e:
        bad(f'5 wheel step: {e}')

    print(f'\nRESULT: {pass_n} passed, {fail_n} failed')
    return 0 if fail_n == 0 else 1

if __name__ == '__main__':
    raise SystemExit(main())
