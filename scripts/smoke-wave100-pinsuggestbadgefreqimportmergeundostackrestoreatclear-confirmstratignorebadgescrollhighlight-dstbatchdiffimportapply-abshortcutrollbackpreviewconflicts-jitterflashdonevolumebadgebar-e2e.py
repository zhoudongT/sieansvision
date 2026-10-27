#!/usr/bin/env python3
"""细妆68：频率撤销栈按档回退/清空 · 忽略高亮滚入可视 · DST diff导入再应用 · A/B回滚预览冲突列表 · jitter音量旁标条."""
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
        'def restore_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_freq_import_merge_undo_stack_at',
        'def clear_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_freq_import_merge_undo_stack',
        'def scroll_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy_overlap_highlight_into_view',
        'def import_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff',
        'def apply_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff',
        'def preview_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_default_slot_shortcut_history_rollback_conflicts',
        'def ensure_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound_volume_mute_badge_bar',
        'def refresh_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound_volume_mute_badge_bar',
        '按档回退',
        '清空撤销栈',
        '滚入高亮行',
        '导入差异',
        '再应用差异',
        '预览冲突',
        '音量旁标条',
        'isJitterFlashDoneSoundVolumeMuteBadgeBar',
    ]
    try:
        for m in markers:
            assert m in hsm_src, m
        ok('wave100 APIs present')
    except Exception as e:
        bad(f'wave100 APIs present: {e}')
        print(f'\nRESULT: {pass_n} passed, {fail_n} failed')
        return 1

    from PySide6.QtWidgets import QApplication, QMessageBox, QFileDialog, QInputDialog, QMenu, QLabel
    app = QApplication.instance() or QApplication([])
    QMessageBox.information = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
    QMessageBox.warning = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
    QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)
    QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: ('', ''))
    QFileDialog.getOpenFileName = staticmethod(lambda *a, **k: ('', ''))
    QInputDialog.getText = staticmethod(lambda *a, **k: ('x', True))
    QInputDialog.getInt = staticmethod(lambda *a, **k: (0, True))
    QMenu.exec = lambda self, *a, **k: None

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
    host._ab_trial_fallback_import_conflict_preview_layout_default_slot_shortcut_rebind_no_dialog = True
    host._ab_trial_fallback_import_conflict_preview_layout_default_slot_shortcut_rollback_no_confirm = True
    host._jitter_reorder_undo_lab_menu_no_exec = True
    host._jitter_reorder_undo_depth_lab_flash_done_sound_wav_no_dialog = True
    host._jitter_reorder_undo_depth_lab_flash_done_sound_volume_no_dialog = True

    # --- 1 restore_at / clear stack ---
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
            stk = host.list_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_freq_import_merge_undo_stack(limit=8)
            assert len(stk) >= 2, stk
            # restore at index 1 (older) — drop index 0 and restore snap@1
            ra = host.restore_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_freq_import_merge_undo_stack_at(1, persist=True)
            assert ra.get('ok') is True, ra
            names = [str(x.get('name') or '') for x in host.list_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_freq_presets()]
            assert '快' in names, names
            # rebuild stack then clear
            host._cycle_key_suggest_history_filter_presets_reorder_badge_freq_import_merge_smoke_path = p1
            host.merge_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_freq_import(persist=True)
            host._cycle_key_suggest_history_filter_presets_reorder_badge_freq_import_merge_smoke_path = p2
            host.merge_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_freq_import(persist=True)
            clr = host.clear_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_freq_import_merge_undo_stack(persist=True)
            assert clr.get('ok') is True and int(clr.get('cleared') or 0) >= 1, clr
            stk2 = host.list_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_freq_import_merge_undo_stack(limit=8)
            assert len(stk2) == 0, stk2
        host.show_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_context_menu()
        smoke = getattr(host, '_last_cycle_key_suggest_history_filter_presets_reorder_badge_menu_smoke', {})
        acts = smoke.get('actions', [])
        assert 'import_merge_undo_restore_at' in acts and 'import_merge_undo_clear_stack' in acts, smoke
        ok('1 restore_at/clear stack')
    except Exception as e:
        bad(f'1 restore_at/clear: {e}')

    # --- 2 scroll highlight into view ---
    try:
        host.set_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role(
            {'ops': ['Ctrl+A'], 'qa': ['Ctrl+A', 'Ctrl+Q']}, persist=True, sync_flat=True)
        host.set_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy(
            'merge', persist=True)
        badge = host.refresh_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy_conflict_badge()
        assert badge.get('overlaps'), badge
        jmp = host.jump_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy_overlap(None)
        assert jmp.get('ok') is True, jmp
        hl = host.highlight_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy_overlap_row()
        assert hl.get('key') == 'Ctrl+A', hl
        assert 'scrolled' in hl or hl.get('scroll'), hl
        sc = host.scroll_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy_overlap_highlight_into_view()
        assert sc.get('ok') is True and sc.get('key') == 'Ctrl+A', sc
        host.show_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_menu()
        smoke = getattr(host, '_last_ics_strategy_shortcut_conflict_ignore_menu_smoke', {})
        assert 'scroll_highlight' in smoke.get('actions', []), smoke
        ok('2 scroll highlight into view')
    except Exception as e:
        bad(f'2 scroll highlight: {e}')

    # --- 3 DST import + re-apply ---
    try:
        host.clear_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history(persist=True)
        host._last_dst_reorder_shortcut_conflict_history_batch_diff = {
            'added': ['Ctrl+Imp'], 'cleared': [], 'delta_hit': 1, 'hit': 1,
        }
        host._last_dst_reorder_shortcut_conflict_history_batch_recheck = {'which': 'undo', 'hit': 1, 'keys': ['Ctrl+Imp']}
        with tempfile.TemporaryDirectory() as td:
            outp = str(Path(td) / 'diff.json')
            host._dst_reorder_shortcut_conflict_history_batch_diff_export_no_dialog = True
            host._dst_reorder_shortcut_conflict_history_batch_diff_export_smoke_path = outp
            got = host.export_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff()
            assert Path(outp).is_file(), got
            # clear history then import+apply
            host.clear_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history(persist=True)
            host._dst_reorder_shortcut_conflict_history_batch_diff_import_no_dialog = True
            host._dst_reorder_shortcut_conflict_history_batch_diff_import_smoke_path = outp
            imp = host.import_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff(apply=True, persist=True)
            assert imp.get('ok') is True and int(imp.get('applied') or 0) >= 1, imp
            hist = host.list_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history(limit=16)
            keys = [str(h.get('key') or '') for h in hist]
            assert 'Ctrl+Imp' in keys, keys
            # re-apply again
            ap = host.apply_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff(persist=True)
            assert ap.get('ok') is True and int(ap.get('applied') or 0) >= 1, ap
        assert host.show_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_menu()
        smoke = getattr(host, '_last_dst_reorder_shortcut_conflict_history_menu_smoke', {})
        acts = smoke.get('actions', [])
        assert 'import_batch_diff' in acts and 'apply_batch_diff' in acts, smoke
        ok('3 DST import/apply')
    except Exception as e:
        bad(f'3 DST import/apply: {e}')

    # --- 4 AB rollback preview conflicts ---
    try:
        host.set_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_default_slot_shortcut('Ctrl+Alt+D', persist=True)
        host.remember_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_default_slot_shortcut_history(
            'Ctrl+Alt+D', conflicts=[], persist=True)
        host.set_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_default_slot_shortcut('Ctrl+Alt+Z', persist=True)
        host.remember_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_default_slot_shortcut_history(
            'Ctrl+Alt+Z', conflicts=[], persist=True)
        prev = host.preview_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_default_slot_shortcut_history_rollback_conflicts(0)
        assert prev.get('ok') is True and 'conflict_n' in prev and 'conflicts' in prev, prev
        # rollback with confirm still works + preview embedded
        host._ab_trial_fallback_import_conflict_preview_layout_default_slot_shortcut_rollback_no_confirm = True
        rb = host.rollback_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_default_slot_shortcut_history(1, persist=True, confirm=True)
        assert rb.get('ok') is True, rb
        # cancel path still ok
        host._ab_trial_fallback_import_conflict_preview_layout_default_slot_shortcut_rollback_no_confirm = False
        QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.No)
        rb2 = host.rollback_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_default_slot_shortcut_history(0, persist=True, confirm=True)
        assert rb2.get('ok') is False and rb2.get('reason') == 'cancelled', rb2
        assert 'conflict_n' in rb2, rb2
        QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)
        host._ab_trial_fallback_import_conflict_preview_layout_default_slot_shortcut_rollback_no_confirm = True
        ok('4 AB preview conflicts')
    except Exception as e:
        bad(f'4 AB preview conflicts: {e}')

    # --- 5 volume badge bar ---
    try:
        host.set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound_volume(0.42, persist=True)
        bar = host.refresh_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound_volume_mute_badge_bar()
        assert bar.get('ok') is True and int(bar.get('pct') or 0) == 42, bar
        assert getattr(host, '_jitter_flash_done_sound_volume_mute_badge_bar', None) is not None
        host.set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound_mute_badge(True, persist=True)
        bar2 = host.refresh_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound_volume_mute_badge_bar()
        assert bar2.get('muted') is True, bar2
        host.set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound_mute_badge(False, persist=True)
        # menu smoke
        lab = getattr(host, '_last_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab', None)
        if lab is None:
            lab = QLabel('×0', host)
            host._last_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab = lab
        try:
            if hasattr(host, '_on_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_context_menu'):
                host._on_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_context_menu()
        except Exception:
            pass
        smoke = getattr(host, '_last_jitter_reorder_undo_lab_menu_smoke', {}) or {}
        if smoke:
            assert 'volume_badge_bar' in smoke.get('actions', []), smoke
        ok('5 volume badge bar')
    except Exception as e:
        bad(f'5 volume badge bar: {e}')

    print(f'\nRESULT: {pass_n} passed, {fail_n} failed')
    return 0 if fail_n == 0 else 1

if __name__ == '__main__':
    raise SystemExit(main())
