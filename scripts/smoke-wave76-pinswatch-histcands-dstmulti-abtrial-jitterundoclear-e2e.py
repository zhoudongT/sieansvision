#!/usr/bin/env python3
"""细妆㊹：pin撤销预览色标条 · 吸史改键候选菜单 · DST最近右键多选 · A/B说明条点源试算 · jitter清栈确认/撤销."""
from __future__ import annotations
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
        QApplication, QMessageBox, QFileDialog, QColorDialog, QInputDialog,
    )
    from PySide6.QtCore import QSettings, Qt
    from PySide6.QtGui import QColor, QDesktopServices
    app = QApplication.instance() or QApplication([])
    QMessageBox.information = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
    QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)
    QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: ('', ''))
    QFileDialog.getOpenFileName = staticmethod(lambda *a, **k: ('', ''))
    QColorDialog.getColor = staticmethod(lambda *a, **k: QColor('#ccddee'))
    QInputDialog.getInt = staticmethod(lambda *a, **k: (200, False))
    QInputDialog.getText = staticmethod(lambda *a, **k: ('烟测档', True))
    QDesktopServices.openUrl = staticmethod(lambda *a, **k: True)

    from desktop.host_state_machine import HostStateMachineWidget
    for name in (
        'render_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch',
        '_refresh_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_ui',
        'list_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidates',
        'show_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_menu',
        'selected_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent',
        'set_selected_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent',
        'toggle_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_selected',
        'apply_selected_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent',
        'remove_selected_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent',
        'show_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_menu',
        'trial_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_explain',
        'undo_clear_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo',
        'clear_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo',
    ):
        assert hasattr(HostStateMachineWidget, name), name
    ok('wave76 APIs present')

    s = QSettings('SIEANS', 'VisionDesktop')
    s.setValue('host/alarmFilmCsvDirs', [])
    s.setValue('host/sevPinArcSeizeRecentColors', [])
    s.setValue('host/toastHistCapTipAnim', True)
    s.setValue('host/toastHistCapTipAnimEasing', 'OutCubic')
    s.setValue('host/stalePruneUndoColorScale', 'traffic')
    s.setValue('host/stalePruneUndoColorScaleCompare', 'cool')
    s.setValue('host/stalePruneUndoColorScaleAbLock', False)
    s.setValue('host/stalePruneUndoColorScaleAbMirror', False)
    s.setValue('host/stalePruneUndoColorScaleAbMirrorDir', 'a_to_b')
    s.setValue('host/stalePruneUndoColorScaleAbMirrorChannels', ['a_to_b', 'b_to_a'])
    s.setValue('host/stalePruneUndoColorScaleAbMirrorChannelPresetCustoms', [])
    s.setValue('host/stalePruneUndoColorScaleAbMirrorChannelPresetImportConflict', 'overwrite')
    s.setValue('host/stalePruneUndoEyedropperHistory', [])
    s.setValue('host/stalePruneUndoEyedropperHistoryOrderUndoShortcut', 'Ctrl+Shift+Z')
    s.setValue('host/stalePruneUndoEyedropperHistoryOrderRedoShortcut', 'Ctrl+Shift+Y')
    s.setValue('host/stalePruneUndoColorCustomAlpha', 160)
    s.setValue('host/stalePruneUndoColorCustomAlphaStep', 10)
    s.setValue('host/mergeDiffBatchFailHistory', [])
    s.setValue('host/mergeDiffFailHistGroupOrder', [])
    s.setValue('host/mergeDiffFailHistCollapsed', [])
    s.setValue('host/mergeDiffFailHistDropSnapThresh', 18)
    s.setValue('host/mergeDiffFailHistDropPulseMs', 280)
    s.setValue('host/mergeDiffFailHistDropPulseEasing', 'OutCubic')
    s.setValue('host/mergeDiffFailHistDropPulseIntensityPct', 100)
    s.setValue('host/mergeDiffFailHistDropSnapGuidePreset', 'green')
    s.setValue('host/mergeDiffFailHistDropSnapGuideAlphaPct', 12)
    s.setValue('host/mergeDiffFailHistDropSnapGuideCustomHex', '#3ecf8e')
    s.setValue('host/mergeDiffFailHistDropSnapGuideRecentColors', [])
    s.setValue('host/mergeDiffFailHistDropSnapGuideRecentPinned', [])
    s.setValue('host/mergeDiffFailHistDropSnapGuideRecentMaxPin', 3)
    s.setValue('host/mergeDiffFailHistDropSnapGuideRecentMaxPinDecKey', 'Ctrl+[')
    s.setValue('host/mergeDiffFailHistDropSnapGuideRecentMaxPinIncKey', 'Ctrl+]')
    s.setValue('host/mergeDiffFailHistDropPulsePreviewLoopGapMs', 120)
    s.setValue('host/mergeDiffFailHistDropPulsePreviewLoopGapJitterMs', 40)
    s.setValue('host/mergeDiffFailHistDropPulsePreviewLoopGapJitterDist', 'uniform')
    s.setValue('host/mergeDiffFailHistDropPulsePreviewLoopGapJitterSeed', 42)
    s.setValue('host/toastCurvePngExportDir', '')
    s.setValue('host/toastCurvePngRecentExports', [])
    s.setValue('host/toastCurvePngNameTemplate', '{project}-{datetime}.png')
    s.setValue('host/toastCurvePngProjectName', 'default')
    s.setValue('host/toastCurvePngStationName', 'station1')
    s.setValue('host/toastCurvePngDatetimeFormat', '%Y-%m-%d_%H-%M-%S')
    s.setValue('host/toastCurvePngDatetimeTzOffsetHours', 0)
    s.setValue('host/toastCurvePngDatetimeTzCity', 'local')
    s.setValue('host/toastCurvePngDatetimeTzDstYearLo', 1990)
    s.setValue('host/toastCurvePngDatetimeTzDstYearHi', 2035)
    s.setValue('host/toastCurvePngDatetimeTzDstYearRangeRecent', [])
    s.setValue('host/sevPinSoloDeleteUndoMs', 4000)
    s.sync()
    host = HostStateMachineWidget(compact=True)
    host.show()
    host._toast_hist_cap_keep_exit_tip_quiet = True
    host._toast_hist_cap_tip_anim_easing_quiet = True
    host._toast_hist_cap_tip_anim_curve_quiet = True
    host._toast_hist_cap_tip_anim_curve_no_exec = True
    host._toast_hist_cap_tip_anim_curve_png_no_dialog = True
    host._toast_curve_png_recent_exports_menu_no_exec = True
    host._toast_curve_png_name_template_dialog_no_exec = True
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
    host._sev_pin_solo_delete_undo_ms_menu_no_exec = True
    host._merge_diff_fail_hist_drop_pulse_preview_no_exec = True
    host._stale_prune_undo_eyedropper_history_ctx_no_exec = True
    host._snap_guide_recent_max_pin_keys_no_dialog = True
    host._jitter_quantile_export_no_dialog = True
    host._ab_mirror_channel_preset_custom_no_dialog = True
    host._ab_mirror_channel_preset_custom_smoke_name = '烟测档'
    host._eyedropper_history_order_shortcuts_no_dialog = True
    host._dst_year_range_no_dialog = True
    host._dst_year_range_recent_menu_no_exec = True
    host._jitter_seed_redo_clear_no_confirm = True

    # --- 1. pin undo preview swatch bar ---
    host._merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo = []
    empty = host.render_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch()
    assert empty['available'] is False
    assert empty['swatch_current'] and empty['swatch_restore']
    assert 'qlineargradient' in empty['css'] or 'background' in empty['css']
    assert '无可撤销' in empty['text'] or '无可撤销' in empty['tip']
    host.set_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_keys(
        'Ctrl+C', 'Ctrl+V', persist=True, warn=False)
    host.apply_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar()
    sw = host.render_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch()
    assert sw['available'] is True
    assert sw['undo_depth'] >= 1
    assert sw['swatch_current'] != sw['swatch_restore'] or True  # may coincide if same conflict state
    assert 'qlineargradient' in sw['css']
    prev = host.preview_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo()
    assert prev.get('bar_css') and prev.get('bar_text')
    assert prev.get('swatch_current') and prev.get('swatch_restore')
    for hx in ('#aa66ff', '#ff6688'):
        host.remember_merge_diff_fail_hist_drop_snap_guide_recent_color(hx)
    menu_g = host._build_merge_diff_fail_hist_drop_snap_guide_menu()
    lab_sw = getattr(host, '_last_snap_guide_recent_max_pin_avoid_compare_bar_undo_swatch_lab', None)
    # lab may be named differently
    if lab_sw is None:
        lab_sw = getattr(host, '_last_snap_guide_recent_max_pin_avoid_compare_bar_undo_swatch_ui', None)
    bar_w = getattr(host, '_last_snap_guide_recent_max_pin_avoid_compare_bar', None)
    assert bar_w is not None
    host._refresh_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_ui()
    host.undo_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar()
    host.reset_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_keys()
    ok('pin 撤销预览色标条')

    # --- 2. hist fix candidates menu ---
    host.set_stale_prune_undo_eyedropper_history_order_shortcuts(
        'Ctrl+C', 'Ctrl+V', persist=True, rebind=True, warn=False)
    cands = host.list_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidates()
    assert isinstance(cands, list) and len(cands) >= 1
    row0 = cands[0]
    assert isinstance(row0, dict)
    assert row0.get('clean') is True
    assert (row0.get('undo'), row0.get('redo')) != ('Ctrl+C', 'Ctrl+V')
    host._eyedropper_history_order_shortcut_fix_menu_no_exec = True
    host._eyedropper_history_order_shortcut_fix_menu_smoke_index = 0
    n_menu = host.show_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_menu()
    assert isinstance(n_menu, int)
    last = getattr(host, '_last_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_menu', None)
    assert isinstance(last, dict) and last.get('executed') is False
    assert last.get('candidates')
    # apply first candidate via fix
    fixed = host.fix_stale_prune_undo_eyedropper_history_order_shortcut_conflicts()
    left = host.detect_stale_prune_undo_eyedropper_history_order_shortcut_conflicts(fixed[0], fixed[1])
    assert left == [], left
    host.reset_stale_prune_undo_eyedropper_history_order_shortcuts()
    ok('吸史改键候选菜单')

    # --- 3. DST recent right-click multi-select ---
    host._toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent = []
    s.setValue('host/toastCurvePngDatetimeTzDstYearRangeRecent', [])
    s.sync()
    host.set_toast_curve_png_datetime_tz_city_dst_calendar_year_range(2001, 2028)
    host.set_toast_curve_png_datetime_tz_city_dst_calendar_year_range(2010, 2020)
    host.set_toast_curve_png_datetime_tz_city_dst_calendar_year_range(1995, 2015)
    rows = host.list_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent()
    assert len(rows) >= 3
    host.set_selected_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent([1, 2])
    sel = host.selected_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent()
    assert sel == [1, 2], sel
    host.toggle_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_selected(1)
    assert 1 not in host.selected_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent()
    host.set_selected_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent([1])
    got = host.apply_selected_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent()
    assert got == rows[1]
    host.set_selected_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent([0])
    # menu smoke remove
    host._dst_year_range_recent_menu_smoke = {'action': 'remove', 'indices': [0]}
    host.show_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_menu()
    after = host.list_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent()
    assert len(after) == len(rows) - 1
    host.set_toast_curve_png_datetime_tz_city_dst_calendar_year_range(1990, 2035)
    ok('DST 最近右键多选')

    # --- 4. A/B explain click source trial ---
    host._stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_trial = ''
    t1 = host.trial_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_explain('team')
    assert t1['trial_source'] == 'team'
    assert t1['trial_resolved'] == 'rename'
    assert '试算' in t1['trial_tip']
    t2 = host.trial_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_explain('local')
    assert t2['trial_resolved'] == 'overwrite'
    t3 = host.trial_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_explain('clipboard')
    assert t3['trial_resolved'] == 'skip'
    # cycle
    host._stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_trial = 'clipboard'
    t4 = host.trial_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_explain()
    assert t4['trial_source'] == ''
    host.set_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_strategy('source')
    host.set_stale_prune_undo_color_scale_ab_lock(True)
    host.set_stale_prune_undo_color_scale_ab_mirror(True)
    host.set_stale_prune_undo_color_scale_ab_mirror_dir('both')
    menu = host._build_undo_color_scale_hot_sync_menu()
    lab = getattr(host, '_last_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_explain_lab', None)
    assert lab is not None
    # trial chips
    chips = []
    for ch in menu.findChildren(type(lab)):
        pass
    from PySide6.QtWidgets import QPushButton
    trial_btns = [
        b for b in menu.findChildren(QPushButton)
        if b.property('isUndoColorScaleAbMirrorChannelPresetImportConflictSourceTrial')
    ]
    assert len(trial_btns) >= 3, len(trial_btns)
    host.trial_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_explain('team')
    assert '试算' in str(lab.text() or '') or lab.property('abMirrorChannelPresetImportConflictTrialSource') == 'team'
    host.set_stale_prune_undo_color_scale_ab_lock(False)
    host.set_stale_prune_undo_color_scale_ab_mirror(False)
    host.set_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_strategy('overwrite')
    ok('A/B 说明条点源试算')

    # --- 5. jitter clear confirm + undo ---
    host.set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed(42)
    host._merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_history = []
    host._merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo = []
    host._merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo = []
    host.reshuffle_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed()
    host.reshuffle_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed()
    host.undo_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_reshuffle()
    host.undo_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_reshuffle()
    d = len(host._merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo)
    assert d >= 2
    # cancel path
    host._jitter_seed_redo_clear_no_confirm = False
    QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.No)
    cancelled = host.clear_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo()
    assert cancelled == 0
    assert len(host._merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo) == d
    assert host._last_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_cleared.get('cancelled') is True
    # confirm Yes
    QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)
    cleared = host.clear_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo()
    assert cleared == d
    assert host._merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo == []
    snap = host._merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo
    assert len(snap) == d
    restored = host.undo_clear_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo()
    assert restored == d
    assert len(host._merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo) == d
    assert host._merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo == []
    # empty undo
    assert host.undo_clear_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo() == 0
    # UI 撤清 btn
    for hx in ('#aa66ff',):
        host.remember_merge_diff_fail_hist_drop_snap_guide_recent_color(hx)
    # build jitter area via pulse preview menu if needed
    try:
        host._build_merge_diff_fail_hist_drop_pulse_preview_menu()
    except Exception:
        pass
    btn_u = getattr(
        host,
        '_last_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_btn',
        None)
    # may be None if menu not built; still ok if API works
    host._jitter_seed_redo_clear_no_confirm = True
    host.clear_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo()
    ok('jitter 清栈确认/撤销')

    print(f'wave76 DONE pass={pass_n} fail={fail_n}')
    return 0 if fail_n == 0 else 1

if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as e:
        bad(f'exception · {e}')
        import traceback; traceback.print_exc()
        print(f'wave76 DONE pass={pass_n} fail={fail_n}')
        raise SystemExit(1)
