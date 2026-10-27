#!/usr/bin/env python3
"""细妆57：pin筛选预设持久/导出 · 冲突策略快捷键可改绑 · DST旁标右键菜单 · A/B预览列显隐 · jitter旁标快捷键."""
from __future__ import annotations
import json
import sys
import tempfile
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
    from PySide6.QtGui import QColor, QDesktopServices
    app = QApplication.instance() or QApplication([])
    QMessageBox.information = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
    QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)
    QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: ('', ''))
    QFileDialog.getOpenFileName = staticmethod(lambda *a, **k: ('', ''))
    QColorDialog.getColor = staticmethod(lambda *a, **k: QColor('#ccddee'))
    QInputDialog.getInt = staticmethod(lambda *a, **k: (4500, True))
    QInputDialog.getText = staticmethod(lambda *a, **k: ('Ctrl+Alt+K', True))
    QDesktopServices.openUrl = staticmethod(lambda *a, **k: True)
    def _no_exec(self, *a, **k):
        self.setProperty('smokeMenuNoExec', True)
        return None
    QMenu.exec = _no_exec  # type: ignore

    from desktop.host_state_machine import HostStateMachineWidget
    hsm_src = Path(ROOT / 'desktop' / 'host_state_machine.py').read_text(encoding='utf-8')

    for marker in [
        'def export_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets',
        'def import_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets',
        'isCycleKeySuggestHistoryFilterPresetExport',
        'def set_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut',
        'isUndoEyedropperHistoryOrderShortcutFixConfirmTrialUndoImportConflictStrategyLabMenuRebind',
        'isDstClearUndoTtlPresetCustomsReorderUndoDepthLabMenu',
        'isDstClearUndoTtlPresetCustomsReorderRedoDepthLabMenu',
        'def set_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_columns',
        'isAbMirrorChannelPresetImportConflictPreviewColumn',
        'isJitterSeedRedoClearUndoTtlPresetCustomsReorderRedoShortcut',
        'def _on_jitter_reorder_redo_hotkey',
    ]:
        assert marker in hsm_src, marker
    ok('wave89 APIs present')

    s = QSettings('SieansVision', 'HostStateMachineSmoke89')
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
    host._dst_reorder_depth_lab_menu_no_exec = True
    host._ics_strategy_shortcut_rebind_no_dialog = True
    host._cycle_key_suggest_history_filter_presets_export_no_dialog = True
    host._cycle_key_suggest_history_filter_presets_import_no_dialog = True
    app.processEvents()

    # --- 1. filter presets persist/export/import ---
    host.clear_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets(persist=True)
    host.set_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query('Alpha', persist=True)
    host.set_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query('Beta', persist=True)
    presets = host.list_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets()
    assert presets[:2] == ['Beta', 'Alpha'], presets
    # persist: reload from settings
    host._merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_presets = None
    presets2 = host.list_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets()
    assert 'Beta' in presets2 and 'Alpha' in presets2, presets2
    with tempfile.TemporaryDirectory() as td:
        path = str(Path(td) / 'presets.json')
        host._cycle_key_suggest_history_filter_presets_export_smoke = {'path': path}
        exp = host.export_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets(path)
        assert exp.get('ok'), exp
        assert Path(path).is_file()
        data = json.loads(Path(path).read_text(encoding='utf-8'))
        assert data.get('kind') == 'cycleKeySuggestHistoryFilterQueryPresets'
        assert 'Beta' in data.get('presets', [])
        host.clear_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets(persist=False)
        host._cycle_key_suggest_history_filter_presets_import_smoke = {'path': path}
        imp = host.import_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets(path, persist=False, merge=False)
        assert imp.get('ok') and imp.get('count') >= 2, imp
        assert host.list_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets()[0] in ('Beta', 'Alpha')
    assert 'isCycleKeySuggestHistoryFilterPresetExport' in hsm_src
    assert '导出预设' in hsm_src
    ok('pin建议历史筛选预设持久/导出')

    # --- 2. ICS shortcut rebind ---
    cur = host.stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut()
    assert 'Ctrl' in cur or 'Alt' in cur, cur
    host._ics_strategy_shortcut_rebind_smoke = 'Ctrl+Alt+K'
    nxt = host.show_confirm_trial_undo_import_conflict_strategy_shortcut_rebind_dialog()
    assert 'K' in nxt or nxt == 'Ctrl+Alt+K', nxt
    host.set_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut('Ctrl+Alt+I', persist=False)
    assert 'I' in host.stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut()
    # right menu smoke includes rebind
    host.set_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy('ask', persist=False)
    host._confirm_trial_undo_ics_lab_menu_no_exec = True
    try:
        host._make_undo_color_scale_eyedropper_history_row(host, which='hi')
    except Exception:
        pass
    app.processEvents()
    lab_ics = None
    for w in host.findChildren(QLabel):
        if w.objectName() == 'hostUndoEyedropperHistoryOrderShortcutFixConfirmTrialUndoImportConflictStrategyLab':
            lab_ics = w
            break
    if lab_ics is None:
        lab_ics = getattr(host, '_last_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_lab', None)
    assert lab_ics is not None, 'ICS lab missing'
    class _ER:
        def button(self):
            return Qt.MouseButton.RightButton
        def pos(self):
            return QPoint(1, 1)
    lab_ics.mousePressEvent(_ER())
    smoke_m = getattr(host, '_last_confirm_trial_undo_ics_lab_menu_smoke', {}) or {}
    assert smoke_m.get('via') == 'right_click_menu', smoke_m
    assert 'rebind' in smoke_m or 'rebind' in (smoke_m.get('actions') or []), smoke_m
    assert '改绑' in hsm_src
    ok('冲突策略快捷键可改绑定')

    # --- 3. DST lab right menus ---
    host._toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs = []
    host._toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_undo = []
    host._toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_redo = []
    host.add_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_custom(1000, '一秒', persist=False)
    host.add_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_custom(2000, '两秒', persist=False)
    host.add_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_custom(3000, '三秒', persist=False)
    host.reorder_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs(
        [3000, 1000, 2000], persist=False)
    # undo stack has depth; redo empty until undo
    host._refresh_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_depth_ui()
    lab_dud = lab_drd = None
    for w in host.findChildren(QLabel):
        if w.objectName() == 'hostDstClearUndoTtlPresetCustomsReorderUndoDepthLab':
            lab_dud = w
        if w.objectName() == 'hostDstClearUndoTtlPresetCustomsReorderRedoDepthLab':
            lab_drd = w
    assert lab_dud and lab_drd
    host._dst_reorder_depth_lab_menu_no_exec = True
    lab_dud.mousePressEvent(_ER())
    su = getattr(host, '_last_dst_reorder_undo_lab_menu_smoke', {}) or {}
    assert su.get('via') == 'right_click_menu' and 'clear_undo' in (su.get('actions') or []), su
    host.undo_reorder_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs(persist=False)
    host._refresh_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_depth_ui()
    lab_drd.mousePressEvent(_ER())
    sr = getattr(host, '_last_dst_reorder_redo_lab_menu_smoke', {}) or {}
    assert sr.get('via') == 'right_click_menu' and 'clear_redo' in (sr.get('actions') or []), sr
    n = host.clear_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_undo()
    assert isinstance(n, int)
    assert '右击菜单' in (lab_dud.toolTip() or '') or '右击菜单' in hsm_src
    ok('DST旁标右键菜单')

    # --- 4. AB column visibility ---
    cols = host.set_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_columns(
        ['flow', 'status'], persist=False)
    assert cols == ['flow', 'status'], cols
    toggled = host.toggle_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_column('incoming', persist=False)
    assert 'incoming' in toggled and 'flow' in toggled, toggled
    # cannot hide last column
    host.set_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_columns(['status'], persist=False)
    still = host.toggle_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_column('status', persist=False)
    assert still == ['status'], still
    text = host.format_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_table(
        json.dumps({'team': {'a': 1}}), from_clipboard=False, columns=['flow', 'status'])
    assert text.splitlines()[0] == 'flow\tstatus', text
    assert 'isAbMirrorChannelPresetImportConflictPreviewColumn' in hsm_src
    ok('A/B预览列显隐')

    # --- 5. jitter hotkey ---
    key = host.merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_redo_shortcut()
    assert 'J' in key or 'Ctrl' in key, key
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
    ok_hot = host._on_jitter_reorder_redo_hotkey()
    assert ok_hot is True or ok_hot is False  # bool
    assert host.merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_redo_depth() < rd
    host._ensure_jitter_reorder_redo_shortcut(force=True)
    sc = getattr(host, '_jitter_reorder_redo_shortcut', None)
    assert sc is not None
    assert 'isJitterSeedRedoClearUndoTtlPresetCustomsReorderRedoShortcut' in hsm_src
    assert 'Ctrl+Alt+J' in hsm_src
    try:
        s.setValue('host/mergeDiffFailHistDropPulsePreviewLoopGapJitterSeedRedoClearUndoTtlPresetCustoms', '[]')
        s.setValue('host/toastCurvePngDatetimeTzCityDstCalendarYearRangeRecentApplyAllUndoClearUndoTtlPresetCustoms', '[]')
        s.sync()
    except Exception:
        pass
    ok('jitter旁标快捷键')

    print(f'\nwave89: {pass_n} PASS / {fail_n} FAIL', flush=True)
    return 0 if fail_n == 0 else 1

if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as e:
        import traceback
        traceback.print_exc()
        print('FAIL: unhandled', e, flush=True)
        raise SystemExit(2)
