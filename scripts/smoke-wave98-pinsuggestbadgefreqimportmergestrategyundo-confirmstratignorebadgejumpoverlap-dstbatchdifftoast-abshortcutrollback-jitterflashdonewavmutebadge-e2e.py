#!/usr/bin/env python3
"""细妆66：频率预设导入合并策略记忆/撤销 · 忽略策略旁标点击跳重叠项 · DST批量复检差异diff toast · A/B快捷史回滚一键 · jitter闪完音效自定义wav/关声旁标."""
from __future__ import annotations
import sys
import json
import tempfile
import time
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
        'def merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_freq_import_merge_strategy',
        'def undo_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_freq_import_merge',
        'def jump_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy_overlap',
        'def show_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_toast',
        'def rollback_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_default_slot_shortcut_history',
        'def merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound_wav',
        'def merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound_mute_badge',
        'isCycleKeySuggestHistoryFilterPresetsReorderBadgeMenuFreqImportMergeUndo',
        'isUndoEyedropperHistoryOrderShortcutFixConfirmTrialUndoImportConflictStrategyIgnoreMenuJumpOverlap',
        'isDstClearUndoTtlPresetCustomsReorderShortcutConflictHistoryMenuBatchDiff',
        'isAbMirrorChannelPresetImportConflictPreviewLayoutSlotsDialogShortcutRollback',
        'isJitterSeedRedoClearUndoTtlPresetCustomsReorderUndoDepthLabMenuFlashDoneMuteBadge',
    ]
    try:
        for m in markers:
            assert m in hsm_src, m
        ok('wave98 APIs present')
    except Exception as e:
        bad(f'wave98 APIs present: {e}')
        print(f'\nRESULT: {pass_n} passed, {fail_n} failed')
        return 1

    from PySide6.QtWidgets import QApplication, QMessageBox, QFileDialog, QInputDialog, QMenu, QLabel
    app = QApplication.instance() or QApplication([])
    QMessageBox.information = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
    QMessageBox.warning = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
    QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: ('', ''))
    QFileDialog.getOpenFileName = staticmethod(lambda *a, **k: ('', ''))
    QInputDialog.getText = staticmethod(lambda *a, **k: ('x', True))
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
    host._jitter_reorder_undo_lab_menu_no_exec = True
    host._jitter_reorder_undo_depth_lab_flash_done_sound_wav_no_dialog = True

    # --- 1 merge strategy memory / undo ---
    try:
        host.set_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_freq_presets(
            [{'name': '快', 'ms': 400}, {'name': '标准', 'ms': 900}], persist=True)
        host.set_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_freq_ms(900, persist=True)
        host.set_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_freq_import_merge_strategy(
            'prefer_existing', persist=True)
        assert host.merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_freq_import_merge_strategy() == 'prefer_existing'
        with tempfile.TemporaryDirectory() as td:
            p = str(Path(td) / 'freq_in.json')
            Path(p).write_text(json.dumps({
                'presets': [{'name': '快', 'ms': 350}, {'name': '慢', 'ms': 1500}],
                'freq_ms': 700,
            }, ensure_ascii=False), encoding='utf-8')
            host._cycle_key_suggest_history_filter_presets_reorder_badge_freq_import_merge_no_dialog = True
            host._cycle_key_suggest_history_filter_presets_reorder_badge_freq_import_merge_smoke_path = p
            merged = host.merge_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_freq_import(persist=True)
            assert merged.get('strategy') == 'prefer_existing', merged
            by = {str(x.get('name')): x for x in (merged.get('presets') or [])}
            assert int(by['快'].get('ms') or 0) == 400, by['快']  # prefer_existing keeps
            assert '慢' in by
            assert merged.get('undo_ready') is True
            und = host.undo_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_freq_import_merge(persist=True)
            assert und.get('ok') is True, und
            names = [str(x.get('name') or '') for x in host.list_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_freq_presets()]
            assert '慢' not in names and '快' in names, names
        host.show_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_context_menu()
        smoke = getattr(host, '_last_cycle_key_suggest_history_filter_presets_reorder_badge_menu_smoke', {})
        assert 'import_merge_strategy' in smoke.get('actions', []) and 'import_merge_undo' in smoke.get('actions', []), smoke
        ok('1 badge freq merge strategy/undo')
    except Exception as e:
        bad(f'1 merge strategy/undo: {e}')

    # --- 2 badge jump overlap ---
    try:
        host.set_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role(
            {'ops': ['Ctrl+A'], 'qa': ['Ctrl+A', 'Ctrl+Q']}, persist=True, sync_flat=True)
        host.set_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy(
            'merge', persist=True)
        badge = host.refresh_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy_conflict_badge()
        assert badge.get('overlaps'), badge
        jmp = host.jump_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy_overlap(None)
        assert jmp.get('ok') is True and jmp.get('key') == 'Ctrl+A', jmp
        jmp2 = host._on_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy_badge_clicked()
        assert jmp2.get('ok') is True, jmp2
        host.show_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_menu()
        smoke = getattr(host, '_last_ics_strategy_shortcut_conflict_ignore_menu_smoke', {})
        assert 'jump_overlap' in smoke.get('actions', []), smoke
        ok('2 ignore badge jump overlap')
    except Exception as e:
        bad(f'2 badge jump: {e}')

    # --- 3 DST batch diff toast ---
    try:
        host.clear_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history(persist=True)
        host.remember_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history(
            [{'key': 'Ctrl+Z', 'reason': 'u'}], which='undo', persist=True)
        host._last_dst_reorder_shortcut_conflict_history_batch_recheck = None
        b1 = host.recheck_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch(
            which='undo', persist=True)
        assert 'diff' in b1, b1
        host.remember_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history(
            [{'key': 'Ctrl+X', 'reason': 'u2'}], which='undo', persist=True)
        b2 = host.recheck_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch(
            which='undo', persist=True)
        diff = b2.get('diff') or {}
        assert isinstance(diff.get('added'), list) and isinstance(diff.get('cleared'), list), diff
        shown = host.show_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch_diff_toast()
        assert shown.get('ok') is True, shown
        assert host.show_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_menu()
        smoke = getattr(host, '_last_dst_reorder_shortcut_conflict_history_menu_smoke', {})
        assert 'batch_diff' in smoke.get('actions', []), smoke
        ok('3 DST batch diff toast')
    except Exception as e:
        bad(f'3 DST batch diff: {e}')

    # --- 4 AB shortcut rollback ---
    try:
        host.set_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_default_slot_shortcut('Ctrl+Alt+D', persist=True)
        host.remember_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_default_slot_shortcut_history(
            'Ctrl+Alt+D', conflicts=[], persist=True)
        host.set_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_default_slot_shortcut('Ctrl+Alt+Z', persist=True)
        host.remember_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_default_slot_shortcut_history(
            'Ctrl+Alt+Z', conflicts=[], persist=True)
        # history[0] is latest Z; rollback index 1 should restore D (or index 0 re-applies Z)
        # After remember Z then D was earlier: list is [Z, D, ...]
        rb = host.rollback_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_default_slot_shortcut_history(1, persist=True)
        assert rb.get('ok') is True, rb
        assert 'Ctrl+Alt+D' in str(rb.get('key') or ''), rb
        assert 'Ctrl+Alt+D' in host.stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_default_slot_shortcut()
        host.show_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_slots_dialog()
        smoke = getattr(host, '_last_ab_trial_fallback_import_conflict_preview_layout_slots_dialog_smoke', {})
        assert 'shortcut_rollback' in smoke.get('actions', []), smoke
        ok('4 AB shortcut rollback')
    except Exception as e:
        bad(f'4 AB rollback: {e}')

    # --- 5 jitter wav / mute badge ---
    try:
        with tempfile.TemporaryDirectory() as td:
            wav = str(Path(td) / 'ding.wav')
            # minimal RIFF/WAVE header + silence (not needed to be valid for path store)
            Path(wav).write_bytes(b'RIFF' + (36).to_bytes(4,'little') + b'WAVEfmt ' + (16).to_bytes(4,'little')
                                  + (1).to_bytes(2,'little') + (1).to_bytes(2,'little') + (8000).to_bytes(4,'little')
                                  + (8000).to_bytes(4,'little') + (1).to_bytes(2,'little') + (8).to_bytes(2,'little')
                                  + b'data' + (0).to_bytes(4,'little'))
            host._jitter_reorder_undo_depth_lab_flash_done_sound_wav_smoke_path = wav
            got = host.pick_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound_wav()
            assert wav in got, got
        host.set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound_mute_badge(True, persist=True)
        assert host.merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound_mute_badge() is True
        play = host._play_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound()
        assert play.get('muted') is True and play.get('played') is False, play
        host.set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound_mute_badge(False, persist=True)
        host.set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound(True, persist=True)
        host.set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_toast(False, persist=True)
        host.set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_count(2, persist=True)
        lab = getattr(host, '_last_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab', None)
        if lab is None:
            lab = QLabel('×0', host)
            host._last_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab = lab
        assert host.flash_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab(ms=40)
        t0 = time.time()
        while time.time() - t0 < 1.5:
            app.processEvents()
            time.sleep(0.04)
        done = getattr(host, '_last_jitter_reorder_undo_depth_lab_flash_done', None)
        assert isinstance(done, dict), done
        assert done.get('sound') is True
        assert 'muted' in done and 'wav' in done
        badge = host.refresh_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound_mute_badge()
        assert 'muted' in badge
        ok('5 jitter wav/mute badge')
    except Exception as e:
        bad(f'5 jitter wav/mute: {e}')

    print(f'\nRESULT: {pass_n} passed, {fail_n} failed')
    return 0 if fail_n == 0 else 1

if __name__ == '__main__':
    raise SystemExit(main())
