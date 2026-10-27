#!/usr/bin/env python3
"""细妆64：pin频率预设改名/另存 · 忽略名单导入分组JSON/角色合并策略 · DST冲突历史点选复检/按which筛 · A/B默认槽快捷改绑/启动开关 · jitter闪完toast文案可配/仅末次提示."""
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
        'def rename_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_freq_preset',
        'def save_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_freq_preset_as',
        'def stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy',
        'def import_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role',
        'def toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_which_filter',
        'def recheck_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_entry',
        'def stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_default_slot_autoload_enabled',
        'def show_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_default_slot_shortcut_rebind_dialog',
        'def merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_toast_text',
        'def merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_toast_last_only',
        'isCycleKeySuggestHistoryFilterPresetsReorderBadgeMenuFreqRename',
        'isAbMirrorChannelPresetImportConflictPreviewLayoutSlotsDialogRebindDefault',
        'isJitterSeedRedoClearUndoTtlPresetCustomsReorderUndoDepthLabMenuFlashToastText',
        'isDstClearUndoTtlPresetCustomsReorderShortcutConflictHistoryMenuRecheck',
    ]
    try:
        for m in markers:
            assert m in hsm_src, m
        ok('wave96 APIs present')
    except Exception as e:
        bad(f'wave96 APIs present: {e}')
        print(f'\nRESULT: {pass_n} passed, {fail_n} failed')
        return 1

    from PySide6.QtWidgets import QApplication, QMessageBox, QFileDialog, QInputDialog, QMenu, QLabel
    from PySide6.QtCore import QTimer
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
    host._jitter_reorder_undo_depth_lab_flash_toast_text_no_dialog = True

    # --- 1 badge freq rename / save_as ---
    try:
        host.set_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_freq_presets(
            [{'name': '快', 'ms': 400}, {'name': '标准', 'ms': 900}], persist=True)
        renamed = host.rename_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_freq_preset(
            '快', '极速', persist=True)
        names = [str(p.get('name') or '') for p in renamed]
        assert '极速' in names and '快' not in names, names
        saved = host.save_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_freq_preset_as(
            '自定义650', ms=650, persist=True)
        names2 = [str(p.get('name') or '') for p in saved]
        assert '自定义650' in names2, names2
        host.show_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_context_menu()
        smoke = getattr(host, '_last_cycle_key_suggest_history_filter_presets_reorder_badge_menu_smoke', {})
        assert 'rename' in smoke.get('actions', []) and 'save_as' in smoke.get('actions', []), smoke
        ok('1 badge freq rename/save_as')
    except Exception as e:
        bad(f'1 badge rename/save_as: {e}')

    # --- 2 ignore import_by_role + merge strategy ---
    try:
        host.set_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy(
            'prefer_incoming', persist=True)
        assert host.stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy() == 'prefer_incoming'
        host.set_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role(
            {'ops': ['Ctrl+A'], 'qa': ['Ctrl+Q']}, persist=True, sync_flat=True)
        with tempfile.TemporaryDirectory() as td:
            p = str(Path(td) / 'in_byrole.json')
            Path(p).write_text(json.dumps({
                'by_role': {'ops': ['Ctrl+A', 'Ctrl+Z'], 'dev': ['Ctrl+D']},
                'strategy': 'merge',
            }, ensure_ascii=False), encoding='utf-8')
            host._ics_strategy_shortcut_conflict_ignore_by_role_import_no_dialog = True
            host._ics_strategy_shortcut_conflict_ignore_by_role_import_smoke_path = p
            out = host.import_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role()
            assert isinstance(out, dict), out
            by = out.get('by_role') or out
            # prefer_incoming / merge should include new keys
            assert 'dev' in by or 'dev' in str(out), out
        host.show_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_menu()
        smoke = getattr(host, '_last_ics_strategy_shortcut_conflict_ignore_menu_smoke', {})
        assert 'import_by_role' in smoke.get('actions', []) and 'merge_strategy' in smoke.get('actions', []), smoke
        ok('2 ignore import_by_role/merge_strategy')
    except Exception as e:
        bad(f'2 ignore import/strategy: {e}')

    # --- 3 DST history recheck / which filter ---
    try:
        host.clear_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history(persist=True)
        host.remember_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history(
            [{'key': 'Ctrl+Z', 'reason': 'u'}], which='undo', persist=True)
        host.remember_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history(
            [{'key': 'Ctrl+Y', 'reason': 'r'}], which='redo', persist=True)
        host.set_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_which_filter('undo', persist=True)
        filt = host.list_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_filtered(which='undo')
        assert all(str(h.get('which') or '') == 'undo' for h in filt), filt
        re = host.recheck_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_entry(
            {'key': 'Ctrl+Z', 'which': 'undo'}, persist=True)
        assert isinstance(re, list)
        assert host.show_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_menu()
        smoke = getattr(host, '_last_dst_reorder_shortcut_conflict_history_menu_smoke', {})
        assert 'recheck' in smoke.get('actions', []) and 'which_filter' in smoke.get('actions', []), smoke
        assert smoke.get('which_filter') == 'undo', smoke
        ok('3 DST history recheck/which')
    except Exception as e:
        bad(f'3 DST recheck/which: {e}')

    # --- 4 AB rebind / autoload toggle ---
    try:
        host.set_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_default_slot_autoload_enabled(False, persist=True)
        assert host.stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_default_slot_autoload_enabled() is False
        host._ab_trial_fallback_import_conflict_preview_layout_default_slot_autoloaded = False
        skipped = host.autoload_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_default_slot(force=False, persist=False)
        assert skipped.get('skipped') is True or skipped.get('enabled') is False, skipped
        host.set_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_default_slot_autoload_enabled(True, persist=True)
        host._ab_trial_fallback_import_conflict_preview_layout_default_slot_shortcut_rebind_smoke = 'Ctrl+Alt+J'
        out = host.show_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_default_slot_shortcut_rebind_dialog()
        assert 'Ctrl+Alt+J' in str(out) or out, out
        host.show_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_slots_dialog()
        smoke = getattr(host, '_last_ab_trial_fallback_import_conflict_preview_layout_slots_dialog_smoke', {})
        assert 'rebind_default' in smoke.get('actions', []) and 'autoload_toggle' in smoke.get('actions', []), smoke
        ok('4 AB rebind/autoload toggle')
    except Exception as e:
        bad(f'4 AB rebind/autoload: {e}')

    # --- 5 jitter flash toast text / last_only ---
    try:
        host.set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_toast_text(
            '完成闪×{times}', persist=True)
        assert '完成闪' in host.merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_toast_text()
        host.set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_toast_last_only(True, persist=True)
        assert host.merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_toast_last_only() is True
        host.set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_count(2, persist=True)
        host.set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_toast(True, persist=True)
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
        assert getattr(host, '_last_jitter_reorder_undo_depth_lab_flash', False) or isinstance(done, dict)
        if isinstance(done, dict):
            assert done.get('last_only') is True
            assert '完成闪' in str(done.get('toast_text') or '')
        host._jitter_reorder_undo_depth_lab_flash_toast_text_smoke = '末次·{times}'
        host.show_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_toast_text_dialog()
        assert '末次' in host.merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_toast_text()
        assert 'isJitterSeedRedoClearUndoTtlPresetCustomsReorderUndoDepthLabMenuFlashToastLastOnly' in hsm_src
        ok('5 jitter flash toast text/last_only')
    except Exception as e:
        bad(f'5 jitter toast text/last_only: {e}')

    print(f'\nRESULT: {pass_n} passed, {fail_n} failed')
    return 0 if fail_n == 0 else 1

if __name__ == '__main__':
    raise SystemExit(main())
