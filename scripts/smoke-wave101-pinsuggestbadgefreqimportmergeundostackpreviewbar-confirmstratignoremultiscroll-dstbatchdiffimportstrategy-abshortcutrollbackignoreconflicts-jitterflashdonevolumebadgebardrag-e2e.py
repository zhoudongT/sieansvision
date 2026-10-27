#!/usr/bin/env python3
"""细妆69：频率撤销栈档位预览条 · 忽略高亮多选滚入 · DST diff导入策略合并/覆盖 · A/B回滚冲突一键忽略 · jitter旁标拖拽调音."""
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
        'def ensure_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_freq_import_merge_undo_stack_preview_bar',
        'def refresh_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_freq_import_merge_undo_stack_preview_bar',
        'def highlight_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy_overlap_rows',
        'def scroll_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy_overlap_highlight_keys_into_view',
        'def toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy',
        'def set_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy',
        'def ignore_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_default_slot_shortcut_history_rollback_conflicts',
        'def bind_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound_volume_mute_badge_bar_drag',
        'def drag_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound_volume_mute_badge_bar_to',
        '档位预览条',
        '多选高亮滚入',
        '导入策略·合并',
        '导入策略·覆盖',
        '一键忽略冲突',
        '旁标拖拽调音',
    ]
    try:
        for m in markers:
            assert m in hsm_src, m
        ok('wave101 APIs present')
    except Exception as e:
        bad(f'wave101 APIs present: {e}')
        print(f'\nRESULT: {pass_n} passed, {fail_n} failed')
        return 1

    import os
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    from PySide6.QtWidgets import QApplication, QLabel
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

    # --- 1 stack preview bar ---
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
            bar = host.refresh_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_freq_import_merge_undo_stack_preview_bar(focus=0)
            assert isinstance(bar, dict) and int(bar.get('depth') or 0) >= 2, bar
            assert isinstance(bar.get('chips'), list) and len(bar.get('chips') or []) >= 1, bar
        ok(f'1 stack preview bar depth={bar.get("depth")}')
    except Exception as e:
        bad(f'1 stack preview bar: {e}')

    # --- 2 multi scroll highlight ---
    try:
        keys = ['Ctrl+A', 'Ctrl+B', 'Ctrl+C']
        out = host.highlight_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy_overlap_rows(keys)
        assert isinstance(out, dict), out
        assert list(out.get('keys') or []) == keys, out
        scr = host.scroll_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy_overlap_highlight_keys_into_view()
        assert isinstance(scr, dict), scr
        ok(f'2 multi scroll n={len(out.get("keys") or [])}')
    except Exception as e:
        bad(f'2 multi scroll: {e}')

    # --- 3 DST import strategy ---
    try:
        s1 = host.set_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy('merge', persist=True)
        assert s1 == 'merge', s1
        s2 = host.set_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy('overwrite', persist=True)
        assert s2 == 'overwrite', s2
        cur = host.toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy()
        assert cur == 'overwrite', cur
        with tempfile.TemporaryDirectory() as td:
            path = str(Path(td) / 'diff.json')
            Path(path).write_text(json.dumps({
                'kind': 'dst_batch_diff', 'which': 'undo',
                'added': ['Ctrl+Shift+W101'], 'cleared': [],
                'batch': {'which': 'undo'},
            }, ensure_ascii=False), encoding='utf-8')
            host._dst_reorder_shortcut_conflict_history_batch_diff_import_smoke_path = path
            host.set_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy('merge', persist=True)
            imp = host.import_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff(
                path, apply=True, persist=False, strategy='merge')
            assert imp.get('ok') is True and imp.get('strategy') == 'merge', imp
            imp2 = host.import_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff(
                path, apply=True, persist=False, strategy='overwrite')
            assert imp2.get('ok') is True and imp2.get('strategy') == 'overwrite', imp2
        host.set_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_import_strategy('merge', persist=True)
        ok(f'3 import strategy merge/overwrite applied={imp.get("applied")}/{imp2.get("applied")}')
    except Exception as e:
        bad(f'3 import strategy: {e}')

    # --- 4 ignore rollback conflicts ---
    try:
        host.remember_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_default_slot_shortcut_history(
            'Ctrl+Shift+Z', persist=False)
        prev = host.preview_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_default_slot_shortcut_history_rollback_conflicts(0)
        assert isinstance(prev, dict), prev
        ign = host.ignore_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_default_slot_shortcut_history_rollback_conflicts(0, persist=True)
        assert isinstance(ign, dict) and ign.get('ok') is True, ign
        assert 'ignored' in ign and 'ignored_n' in ign, ign
        ok(f'4 ignore conflicts ignored_n={ign.get("ignored_n")} key={ign.get("key")}')
    except Exception as e:
        bad(f'4 ignore conflicts: {e}')

    # --- 5 volume badge drag ---
    try:
        bind = host.bind_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound_volume_mute_badge_bar_drag()
        assert bind.get('ok') is True or bind.get('bound') is True, bind
        drag = host.drag_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound_volume_mute_badge_bar_to(37, persist=True)
        assert drag.get('ok') is True and int(drag.get('pct') or -1) == 37, drag
        host.drag_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound_volume_mute_badge_bar_to(70, persist=True)
        ok(f'5 volume drag pct={drag.get("pct")}')
    except Exception as e:
        bad(f'5 volume drag: {e}')

    print(f'\nRESULT: {pass_n} passed, {fail_n} failed')
    return 0 if fail_n == 0 else 1

if __name__ == '__main__':
    raise SystemExit(main())
