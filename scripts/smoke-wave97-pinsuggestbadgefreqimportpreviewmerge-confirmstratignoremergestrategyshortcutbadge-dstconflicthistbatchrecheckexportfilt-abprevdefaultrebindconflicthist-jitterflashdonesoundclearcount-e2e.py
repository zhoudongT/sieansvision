#!/usr/bin/env python3
"""细妆65：pin频率预设导入冲突预览/一键合并 · 忽略名单合并策略快捷/冲突旁标 · DST复检批量/导出筛选 · A/B默认槽改绑冲突检测/最近快捷史 · jitter闪完音效/旁标闪完计数清零."""
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
        'def preview_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_freq_import_conflicts',
        'def merge_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_freq_import',
        'def cycle_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy',
        'def refresh_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy_conflict_badge',
        'def recheck_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch',
        'def export_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_filtered',
        'def detect_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_default_slot_shortcut_conflicts',
        'def list_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_default_slot_shortcut_history',
        'def merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound',
        'def merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_clear_count',
        'isCycleKeySuggestHistoryFilterPresetsReorderBadgeMenuFreqImportPreview',
        'isUndoEyedropperIgnoreByRoleMergeStrategyConflictBadge',
        'isDstClearUndoTtlPresetCustomsReorderShortcutConflictHistoryMenuBatchRecheck',
        'isJitterSeedRedoClearUndoTtlPresetCustomsReorderUndoDepthLabMenuFlashDoneSound',
    ]
    try:
        for m in markers:
            assert m in hsm_src, m
        ok('wave97 APIs present')
    except Exception as e:
        bad(f'wave97 APIs present: {e}')
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

    # --- 1 badge freq import preview / one-click merge ---
    try:
        host.set_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_freq_presets(
            [{'name': '快', 'ms': 400}, {'name': '标准', 'ms': 900}], persist=True)
        with tempfile.TemporaryDirectory() as td:
            p = str(Path(td) / 'freq_in.json')
            Path(p).write_text(json.dumps({
                'presets': [{'name': '快', 'ms': 350}, {'name': '慢', 'ms': 1500}],
                'freq_ms': 700,
            }, ensure_ascii=False), encoding='utf-8')
            host._cycle_key_suggest_history_filter_presets_reorder_badge_freq_import_preview_no_dialog = True
            host._cycle_key_suggest_history_filter_presets_reorder_badge_freq_import_preview_smoke_path = p
            prev = host.preview_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_freq_import_conflicts()
            assert int(prev.get('conflict_count') or 0) >= 1, prev
            host._cycle_key_suggest_history_filter_presets_reorder_badge_freq_import_merge_no_dialog = True
            host._cycle_key_suggest_history_filter_presets_reorder_badge_freq_import_merge_smoke_path = p
            merged = host.merge_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_freq_import(
                strategy='prefer_incoming', persist=True)
            names = [str(x.get('name') or '') for x in (merged.get('presets') or [])]
            assert '慢' in names and '快' in names, names
            by = {str(x.get('name')): x for x in (merged.get('presets') or [])}
            assert int(by['快'].get('ms') or 0) == 350, by['快']
        host.show_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_context_menu()
        smoke = getattr(host, '_last_cycle_key_suggest_history_filter_presets_reorder_badge_menu_smoke', {})
        assert 'import_preview' in smoke.get('actions', []) and 'import_merge' in smoke.get('actions', []), smoke
        ok('1 badge freq import preview/merge')
    except Exception as e:
        bad(f'1 badge import preview/merge: {e}')

    # --- 2 ignore merge-strategy shortcut / conflict badge ---
    try:
        host.set_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy_shortcut(
            'Ctrl+Alt+M', persist=True)
        assert 'Ctrl+Alt+M' in host.stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy_shortcut()
        host.set_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy(
            'merge', persist=True)
        host.set_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role(
            {'ops': ['Ctrl+A'], 'qa': ['Ctrl+A', 'Ctrl+Q']}, persist=True, sync_flat=True)
        nxt = host.cycle_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy(persist=True)
        assert nxt in ('replace', 'prefer_incoming', 'prefer_existing', 'merge'), nxt
        badge = host.refresh_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy_conflict_badge()
        assert isinstance(badge, dict) and 'conflicted' in badge and 'overlaps' in badge, badge
        assert badge.get('overlaps'), badge
        host.show_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_menu()
        smoke = getattr(host, '_last_ics_strategy_shortcut_conflict_ignore_menu_smoke', {})
        assert 'strategy_shortcut' in smoke.get('actions', []) and 'strategy_badge' in smoke.get('actions', []), smoke
        ok('2 ignore merge-strategy shortcut/badge')
    except Exception as e:
        bad(f'2 ignore strategy shortcut/badge: {e}')

    # --- 3 DST batch recheck / export filtered ---
    try:
        host.clear_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history(persist=True)
        host.remember_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history(
            [{'key': 'Ctrl+Z', 'reason': 'u'}], which='undo', persist=True)
        host.remember_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history(
            [{'key': 'Ctrl+Y', 'reason': 'r'}], which='redo', persist=True)
        host.set_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_which_filter('undo', persist=True)
        batch = host.recheck_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_batch(
            which='undo', persist=True)
        assert int(batch.get('checked') or 0) >= 1, batch
        with tempfile.TemporaryDirectory() as td:
            p = str(Path(td) / 'dst_filt.json')
            host._dst_reorder_shortcut_conflict_history_filtered_export_no_dialog = True
            host._dst_reorder_shortcut_conflict_history_filtered_export_smoke_path = p
            outp = host.export_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_filtered(
                which='undo')
            assert outp == p and Path(p).is_file(), outp
            data = json.loads(Path(p).read_text(encoding='utf-8'))
            assert data.get('which_filter') == 'undo', data
        assert host.show_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history_menu()
        smoke = getattr(host, '_last_dst_reorder_shortcut_conflict_history_menu_smoke', {})
        assert 'batch_recheck' in smoke.get('actions', []) and 'export_filtered' in smoke.get('actions', []), smoke
        ok('3 DST batch recheck/export filtered')
    except Exception as e:
        bad(f'3 DST batch/export: {e}')

    # --- 4 AB rebind conflict detect / shortcut history ---
    try:
        host.set_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role_merge_strategy_shortcut(
            'Ctrl+Alt+J', persist=True)
        host._ab_trial_fallback_import_conflict_preview_layout_default_slot_shortcut_rebind_smoke = 'Ctrl+Alt+J'
        out = host.show_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_default_slot_shortcut_rebind_dialog()
        assert 'Ctrl+Alt+J' in str(out) or out, out
        conf = host.detect_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_default_slot_shortcut_conflicts('Ctrl+Alt+J')
        assert isinstance(conf, list) and any(c.get('role') == 'merge_strategy' for c in conf), conf
        hist = host.list_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_default_slot_shortcut_history(limit=8)
        assert isinstance(hist, list) and hist and 'Ctrl+Alt+J' in str(hist[0].get('key') or ''), hist
        host.show_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_slots_dialog()
        smoke = getattr(host, '_last_ab_trial_fallback_import_conflict_preview_layout_slots_dialog_smoke', {})
        assert 'shortcut_history' in smoke.get('actions', []), smoke
        ok('4 AB rebind conflict/history')
    except Exception as e:
        bad(f'4 AB rebind conflict/history: {e}')

    # --- 5 jitter flash-done sound / clear count ---
    try:
        host.set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound(True, persist=True)
        assert host.merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_sound() is True
        host.set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_clear_count(True, persist=True)
        assert host.merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_done_clear_count() is True
        host.set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_count(3, persist=True)
        host.set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_toast(True, persist=True)
        host.set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_toast_last_only(True, persist=True)
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
        assert done.get('sound') is True, done
        assert done.get('clear_count') is True, done
        assert getattr(host, '_last_jitter_reorder_undo_depth_lab_flash_done_beeped', False) is True
        cnt = host.merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab_flash_count()
        assert int(cnt) == 1, cnt
        assert 'isJitterSeedRedoClearUndoTtlPresetCustomsReorderUndoDepthLabMenuFlashDoneClearCount' in hsm_src
        ok('5 jitter flash-done sound/clear count')
    except Exception as e:
        bad(f'5 jitter flash-done sound/clear: {e}')

    print(f'\nRESULT: {pass_n} passed, {fail_n} failed')
    return 0 if fail_n == 0 else 1

if __name__ == '__main__':
    raise SystemExit(main())
