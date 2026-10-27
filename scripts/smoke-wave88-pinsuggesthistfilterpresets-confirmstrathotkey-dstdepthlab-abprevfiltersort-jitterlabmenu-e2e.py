#!/usr/bin/env python3
"""细妆56：pin建议历史筛选最近查询预设 · 冲突策略旁标快捷键 · DST撤重做旁标 · A/B预览列筛/排序 · jitter旁标右键菜单."""
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
        QApplication, QMessageBox, QFileDialog, QColorDialog, QInputDialog, QLabel, QMenu,
    )
    from PySide6.QtCore import QSettings, Qt, QPoint
    from PySide6.QtGui import QColor, QDesktopServices, QKeySequence
    app = QApplication.instance() or QApplication([])
    QMessageBox.information = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
    QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)
    QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: ('', ''))
    QFileDialog.getOpenFileName = staticmethod(lambda *a, **k: ('', ''))
    QColorDialog.getColor = staticmethod(lambda *a, **k: QColor('#ccddee'))
    QInputDialog.getInt = staticmethod(lambda *a, **k: (4500, True))
    QInputDialog.getText = staticmethod(lambda *a, **k: ('Alt', True))
    QDesktopServices.openUrl = staticmethod(lambda *a, **k: True)
    def _no_exec(self, *a, **k):
        self.setProperty('smokeMenuNoExec', True)
        return None
    QMenu.exec = _no_exec  # type: ignore

    from desktop.host_state_machine import HostStateMachineWidget
    hsm_src = Path(ROOT / 'desktop' / 'host_state_machine.py').read_text(encoding='utf-8')

    for marker in [
        'def list_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets',
        'isCycleKeySuggestHistoryFilterPresetMenu',
        'def _on_confirm_trial_undo_import_conflict_strategy_hotkey',
        'isUndoEyedropperHistoryOrderShortcutFixConfirmTrialUndoImportConflictStrategyShortcut',
        'isDstClearUndoTtlPresetCustomsReorderUndoDepthLab',
        'isDstClearUndoTtlPresetCustomsReorderRedoDepthLab',
        'def filter_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_rows',
        'def sort_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_rows',
        'isJitterSeedRedoClearUndoTtlPresetCustomsReorderRedoDepthLabMenu',
    ]:
        assert marker in hsm_src, marker
    ok('wave88 APIs present')

    s = QSettings('SieansVision', 'HostStateMachineSmoke88')
    try:
        s.setValue('host/mergeDiffFailHistDropPulsePreviewLoopGapJitterSeedRedoClearUndoTtlPresetCustoms', '[]')
        s.setValue('host/toastCurvePngDatetimeTzCityDstCalendarYearRangeRecentApplyAllUndoClearUndoTtlPresetCustoms', '[]')
        s.setValue('host/mergeDiffFailHistDropSnapGuideRecentMaxPinAvoidCompareBarUndoSwatchConflictPreviewCycleKeySuggestHistoryFilterPresets', '[]')
        s.sync()
    except Exception:
        pass

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
    host._confirm_trial_undo_ics_lab_menu_no_exec = True
    host._jitter_reorder_redo_lab_menu_no_exec = True
    app.processEvents()

    # --- 1. filter recent query presets ---
    host.clear_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets(persist=False)
    host.set_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query('Alt', persist=False)
    host.set_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query('Ctrl', persist=False)
    host.set_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query('Shift', persist=False)
    presets = host.list_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets()
    assert presets[:3] == ['Shift', 'Ctrl', 'Alt'], presets
    # re-apply Alt → move to front
    host.apply_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_preset('Alt', persist=False)
    presets2 = host.list_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets()
    assert presets2[0] == 'Alt', presets2
    assert host.merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query() == 'Alt'
    nclear = host.clear_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets(persist=False)
    assert nclear >= 1
    assert host.list_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets() == []
    assert 'isCycleKeySuggestHistoryFilterPreset' in hsm_src
    assert '最近查询' in hsm_src
    ok('pin建议历史筛选最近查询预设')

    # --- 2. ICS hotkey ---
    host.set_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy('ask', persist=False)
    nxt = host._on_confirm_trial_undo_import_conflict_strategy_hotkey()
    assert nxt == 'replace', nxt  # ask -> replace
    nxt2 = host._on_confirm_trial_undo_import_conflict_strategy_hotkey()
    assert nxt2 == 'merge', nxt2
    assert 'Ctrl+Alt+I' in hsm_src
    # ensure chrome installs shortcut when row built
    try:
        host._make_undo_color_scale_eyedropper_history_row(host, which='hi')
    except Exception:
        pass
    app.processEvents()
    sc = getattr(host, '_ics_strategy_shortcut', None)
    assert sc is not None, 'ICS shortcut missing'
    assert 'isUndoEyedropperHistoryOrderShortcutFixConfirmTrialUndoImportConflictStrategyShortcut' in hsm_src
    ok('冲突策略旁标快捷键')

    # --- 3. DST undo/redo chrome ---
    host._toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs = []
    host._toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_undo = []
    host._toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_redo = []
    host.add_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_custom(1000, '一秒', persist=False)
    host.add_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_custom(2000, '两秒', persist=False)
    host.add_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_custom(3000, '三秒', persist=False)
    host.reorder_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs(
        [3000, 1000, 2000], persist=False)
    host.undo_reorder_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs(persist=False)
    depths = host._refresh_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_depth_ui()
    assert depths.get('redo', 0) >= 1, depths
    lab_dud = lab_drd = None
    for w in host.findChildren(QLabel):
        if w.objectName() == 'hostDstClearUndoTtlPresetCustomsReorderUndoDepthLab':
            lab_dud = w
        if w.objectName() == 'hostDstClearUndoTtlPresetCustomsReorderRedoDepthLab':
            lab_drd = w
    assert lab_dud is not None and lab_drd is not None, (lab_dud, lab_drd)
    assert lab_drd.text() != '', lab_drd.text()
    assert 'isDstClearUndoTtlPresetCustomsReorderUndoDepthLab' in hsm_src
    assert 'isDstClearUndoTtlPresetCustomsReorderRedoDepthLab' in hsm_src
    ok('DST撤重做旁标')

    # --- 4. AB preview filter/sort ---
    rows = [
        {'flow': 'team', 'status': 'conflict', 'current': 'local', 'incoming': 'clipboard'},
        {'flow': 'remote', 'status': 'same', 'current': 'file', 'incoming': 'file'},
        {'flow': 'disk', 'status': 'new', 'current': '', 'incoming': 'disk'},
    ]
    only_c = host.filter_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_rows(rows, status='conflict')
    assert len(only_c) == 1 and only_c[0]['flow'] == 'team', only_c
    sorted_r = host.sort_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_rows(rows, key='status')
    assert [r['status'] for r in sorted_r] == sorted([r['status'] for r in rows]), sorted_r
    sorted_rev = host.sort_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_rows(rows, key='flow', reverse=True)
    assert sorted_rev[0]['flow'] == 'team' or sorted_rev[0]['flow'] >= sorted_rev[-1]['flow'], sorted_rev
    assert 'isAbMirrorChannelPresetImportConflictPreviewFilter' in hsm_src
    assert 'isAbMirrorChannelPresetImportConflictPreviewSort' in hsm_src
    ok('A/B预览列筛/排序')

    # --- 5. jitter lab right-click menu ---
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
    host._refresh_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_redo_depth_ui()
    lab_jrd = None
    for w in host.findChildren(QLabel):
        if w.objectName() == 'hostJitterSeedRedoClearUndoTtlPresetCustomsReorderRedoDepthLab':
            lab_jrd = w
            break
    assert lab_jrd is not None
    host._jitter_reorder_redo_lab_menu_no_exec = True
    class _ER:
        def button(self):
            return Qt.MouseButton.RightButton
        def pos(self):
            return QPoint(1, 1)
    lab_jrd.mousePressEvent(_ER())
    smoke_m = getattr(host, '_last_jitter_reorder_redo_lab_menu_smoke', None) or {}
    assert smoke_m.get('via') == 'right_click_menu', smoke_m
    assert 'clear_redo' in (smoke_m.get('actions') or []), smoke_m
    assert 'isJitterSeedRedoClearUndoTtlPresetCustomsReorderRedoDepthLabMenu' in hsm_src
    assert '右击菜单' in (lab_jrd.toolTip() or '') or '右击菜单' in hsm_src
    try:
        s.setValue('host/mergeDiffFailHistDropPulsePreviewLoopGapJitterSeedRedoClearUndoTtlPresetCustoms', '[]')
        s.setValue('host/toastCurvePngDatetimeTzCityDstCalendarYearRangeRecentApplyAllUndoClearUndoTtlPresetCustoms', '[]')
        s.sync()
    except Exception:
        pass
    ok('jitter旁标右键菜单')

    print(f'\nwave88: {pass_n} PASS / {fail_n} FAIL', flush=True)
    return 0 if fail_n == 0 else 1

if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as e:
        import traceback
        traceback.print_exc()
        print('FAIL: unhandled', e, flush=True)
        raise SystemExit(2)
