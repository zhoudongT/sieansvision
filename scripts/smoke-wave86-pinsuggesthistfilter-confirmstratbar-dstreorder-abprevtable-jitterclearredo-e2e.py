#!/usr/bin/env python3
"""细妆54：pin建议历史按键过滤/搜索 · 导入冲突策略默认+持久指示条 · DST自定义拖拽排序 · A/B回退冲突预览表 · jitter重做深度/清redo UI."""
from __future__ import annotations
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
pass_n = fail_n = 0

def ok(m):
    global pass_n; pass_n += 1; print('PASS:', m, flush=True)
def bad(m):
    global fail_n; fail_n += 1; print('FAIL:', m, flush=True)

def main():
    from PySide6.QtWidgets import (
        QApplication, QMessageBox, QFileDialog, QColorDialog, QInputDialog, QLabel,
    )
    from PySide6.QtCore import QSettings
    from PySide6.QtGui import QColor, QDesktopServices
    app = QApplication.instance() or QApplication([])
    QMessageBox.information = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
    QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)
    QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: ('', ''))
    QFileDialog.getOpenFileName = staticmethod(lambda *a, **k: ('', ''))
    QColorDialog.getColor = staticmethod(lambda *a, **k: QColor('#ccddee'))
    QInputDialog.getInt = staticmethod(lambda *a, **k: (4500, True))
    QInputDialog.getText = staticmethod(lambda *a, **k: ('Alt', True))
    QDesktopServices.openUrl = staticmethod(lambda *a, **k: True)

    from desktop.host_state_machine import HostStateMachineWidget
    hsm_src = (ROOT / 'desktop' / 'host_state_machine.py').read_text(encoding='utf-8')
    for name in (
        'filter_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history',
        'set_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query',
        'merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query',
        'refresh_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_lab',
        'reorder_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs',
        'show_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_dialog',
        'preview_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_trial_fallback',
        'show_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_dialog',
        'clear_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_redo',
    ):
        assert hasattr(HostStateMachineWidget, name), name
    for marker in (
        'isCycleKeySuggestHistoryFilter',
        'isUndoEyedropperHistoryOrderShortcutFixConfirmTrialUndoImportConflictStrategyLab',
        'isDstClearUndoTtlPresetCustomsReorder',
        'isAbMirrorChannelPresetImportConflictPreviewTable',
        'isJitterSeedRedoClearUndoTtlPresetCustomsReorderClearRedo',
        '策略默认·持久',
    ):
        assert marker in hsm_src, marker
    ok('wave86 APIs present')

    s = QSettings('SIEANS', 'VisionDesktop')
    s.setValue('host/alarmFilmCsvDirs', [])
    s.setValue('host/sevPinArcSeizeRecentColors', [])
    s.setValue('host/toastHistCapTipAnim', True)
    s.setValue('host/toastHistCapTipAnimEasing', 'OutCubic')
    s.setValue('host/stalePruneUndoColorScale', 'traffic')
    s.setValue('host/stalePruneUndoColorScaleCompare', 'cool')
    s.setValue('host/stalePruneUndoColorScaleAbLock', False)
    s.setValue('host/toastCurvePngStationName', 'station1')
    s.setValue('host/toastCurvePngDatetimeFormat', '%Y-%m-%d_%H-%M-%S')
    s.setValue('host/toastCurvePngDatetimeTzOffsetHours', 0)
    s.setValue('host/toastCurvePngDatetimeTzCity', 'local')
    s.setValue('host/toastCurvePngDatetimeTzDstYearLo', 1990)
    s.setValue('host/toastCurvePngDatetimeTzDstYearHi', 2035)
    s.setValue('host/toastCurvePngDatetimeTzDstYearRangeRecent', [])
    s.setValue('host/toastCurvePngDatetimeTzDstYearRangeRecentApplyAllUndoClearUndoTtlMs', 8000)
    s.setValue('host/toastCurvePngDatetimeTzCityDstCalendarYearRangeRecentApplyAllUndoClearUndoTtlPresetCustoms', '[]')
    s.setValue('host/sevPinSoloDeleteUndoMs', 4000)
    s.setValue('host/mergeDiffFailHistDropPulsePreviewLoopGapJitterSeedRedoClearUndoTtlPresetCustoms', '[]')
    s.setValue('host/toastCurvePngDatetimeTzCityDstCalendarYearRangeRecentApplyAllUndoClearUndoTtlPresetCustoms', '[]')
    s.setValue('host/mergeDiffFailHistDropSnapGuideRecentMaxPinAvoidCompareBarUndoSwatchConflictPreviewCycleKeySuggestHistoryFilter', '')
    s.sync()
    host = HostStateMachineWidget(compact=True)
    host.show()
    host._toast_hist_cap_keep_exit_tip_quiet = True
    host._toast_hist_cap_tip_anim_easing_quiet = True
    host._toast_hist_cap_tip_anim_curve_quiet = True
    host._toast_hist_cap_tip_anim_curve_no_exec = True
    host._toast_hist_cap_tip_anim_curve_png_no_dialog = True
    host._toast_curve_png_recent_exports_menu_no_exec = True
    host._toast_curve_png_name_template_dialog_no_dialog = True
    host._toast_curve_png_datetime_custom_no_dialog = True
    host._stale_prune_undo_custom_rgb_no_dialog = True
    host._stale_prune_undo_custom_hex_no_dialog = True
    host._stale_prune_undo_eyedropper_no_dialog = True
    host._stale_prune_undo_custom_preview_no_exec = True
    host._path_copy_badge_fail_hist_clear_no_confirm = True
    host._path_copy_badge_fail_hist_undo_bar_menu_no_exec = True
    host._merge_diff_fail_hist_no_exec = True
    host._stale_prune_undo_step_menu_no_exec = True
    host._snap_guide_custom_color_no_dialog = True
    host._snap_guide_recent_swatch_context_no_exec = True
    host._eyedropper_history_order_shortcut_fix_menu_no_exec = True
    host._dst_year_range_recent_menu_no_exec = True
    host._dst_year_range_no_dialog = True
    host._jitter_seed_redo_clear_no_confirm = True
    host._swatch_conflict_preview_menu_no_exec = True
    host._jitter_clear_undo_ttl_no_dialog = True
    host._jitter_clear_undo_snapshot_menu_no_exec = True
    host._swatch_conflict_preview_cycle_key_no_dialog = True
    host._jitter_ttl_preset_custom_no_dialog = True
    host._swatch_conflict_preview_cycle_key_resolve_no_dialog = True
    host._confirm_trial_undo_menu_no_exec = True
    host._jitter_ttl_preset_custom_edit_no_dialog = True
    host._swatch_conflict_preview_cycle_key_suggest_menu_no_exec = True
    host._dst_clear_undo_ttl_no_dialog = True
    host._jitter_ttl_preset_customs_reorder_no_dialog = True
    host._dst_clear_undo_ttl_preset_menu_no_exec = True
    host._dst_ttl_preset_custom_no_dialog = True
    host._dst_ttl_preset_custom_edit_no_dialog = True
    host._dst_ttl_preset_customs_reorder_no_dialog = True
    host._ab_trial_fallback_import_conflict_preview_no_dialog = True
    app.processEvents()

    # --- 1. pin suggest history filter/search ---
    host.clear_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history()
    host.set_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query('', persist=False)
    host.set_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_selected(
        ['Alt+1', 'Alt+2'], persist=False, remember=True)
    host.set_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_selected(
        ['Ctrl+C'], persist=False, remember=True)
    host.set_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_selected(
        ['Alt+9'], persist=False, remember=True)
    filt = host.filter_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history('alt')
    assert len(filt) >= 2, filt
    assert all('alt' in ' '.join([str(r.get('label') or '').lower()] + [str(k).lower() for k in (r.get('keys') or [])]) for r in filt), filt
    host.set_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query('Ctrl', persist=False)
    assert host.merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query() == 'Ctrl'
    host._swatch_conflict_preview_cycle_key_suggest_menu_smoke = {'action': 'filter_history', 'query': 'Alt', 'persist': False}
    mout = host.show_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_menu(
        persist=False, key='Ctrl+C')
    assert mout.get('via') == 'filter_history', mout
    assert mout.get('count', 0) >= 1, mout
    assert 'isCycleKeySuggestHistoryFilter' in hsm_src
    ok('pin建议历史按键过滤/搜索')

    # --- 2. conflict strategy default + indicator bar ---
    lab = QLabel('')
    host._last_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_lab = lab
    host.set_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy('ask', persist=False)
    assert lab.text() == '询', lab.text()
    host.set_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy('merge', persist=False)
    assert lab.text() == '并', lab.text()
    v = host.refresh_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_lab('skip')
    assert v == 'skip' and lab.text() == '跳'
    assert '导入冲突 ·' in hsm_src and '· 默认' in hsm_src
    assert '策略默认·持久' in hsm_src
    assert 'isUndoEyedropperHistoryOrderShortcutFixConfirmTrialUndoImportConflictStrategyLab' in hsm_src
    ok('导入冲突策略默认+持久指示条')

    # --- 3. DST customs drag reorder ---
    host._toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs = []
    host.add_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_custom(1000, '一秒', persist=False)
    host.add_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_custom(2000, '两秒', persist=False)
    host.add_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_custom(3000, '三秒', persist=False)
    customs = host.list_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs()
    assert len(customs) == 3, customs
    reordered = host.reorder_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs(
        [3000, 1000, 2000], persist=False)
    assert [c['ms'] for c in reordered] == [3000, 1000, 2000], reordered
    host._dst_clear_undo_ttl_preset_menu_smoke = {'action': 'reorder_customs', 'order': [2000, 3000, 1000]}
    n = host.show_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_menu(persist=False)
    # menu smoke may return via other path; call dialog directly too
    host._dst_ttl_preset_customs_reorder_no_dialog = True
    host._dst_ttl_preset_customs_reorder_smoke = [2000, 3000, 1000]
    out = host.show_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_dialog(persist=False)
    assert [c['ms'] for c in out] == [2000, 3000, 1000], out
    assert 'isDstClearUndoTtlPresetCustomsReorder' in hsm_src
    ok('DST自定义拖拽排序')

    # --- 4. A/B conflict preview table ---
    host.persist_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_trial_fallback_map(
        {'team': 'local', 'remote': 'file'})
    payload = json.dumps({
        'kind': 'sieans.ab_trial_fallback_memory',
        'by_flow': {'team': 'clipboard', 'remote': 'file', 'disk': 'disk'},
    }, ensure_ascii=False)
    prev = host.preview_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_trial_fallback(
        payload, from_clipboard=False)
    assert prev.get('count') == 3, prev
    statuses = {r['flow']: r['status'] for r in prev['rows']}
    assert statuses.get('team') == 'conflict', statuses
    assert statuses.get('remote') == 'same', statuses
    assert statuses.get('disk') == 'new', statuses
    assert len(prev.get('conflicts') or []) == 1
    host._ab_trial_fallback_import_conflict_preview_no_dialog = True
    host._ab_trial_fallback_import_conflict_preview_smoke = {'strategy': 'replace'}
    choice = host.show_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_dialog(
        payload, from_clipboard=False)
    assert choice == 'replace', choice
    assert 'isAbMirrorChannelPresetImportConflictPreviewTable' in hsm_src
    ok('A/B回退冲突预览表')

    # --- 5. jitter redo depth / clear redo UI ---
    host._merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs = [
        {'ms': 500, 'label': 'a', 'custom': True},
        {'ms': 1500, 'label': 'b', 'custom': True},
    ]
    host._merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo = []
    host._merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_redo = []
    host.reorder_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs(
        [1500, 500], persist=False, record_undo=True)
    host.undo_reorder_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs(persist=False)
    rd = host.merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_redo_depth()
    assert rd >= 1, rd
    cleared = host.clear_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_redo()
    assert cleared >= 1
    assert host.merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_redo_depth() == 0
    try:
        s.setValue('host/mergeDiffFailHistDropPulsePreviewLoopGapJitterSeedRedoClearUndoTtlPresetCustoms', '[]')
        s.sync()
    except Exception:
        pass
    assert 'isJitterSeedRedoClearUndoTtlPresetCustomsReorderClearRedo' in hsm_src
    assert '清重做栈' in hsm_src
    ok('jitter重做深度指示/清redo UI')

    print(f'\nwave86: {pass_n} PASS / {fail_n} FAIL', flush=True)
    return 0 if fail_n == 0 else 1

if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as e:
        bad(f'exception: {e}')
        import traceback; traceback.print_exc()
        raise SystemExit(1)
