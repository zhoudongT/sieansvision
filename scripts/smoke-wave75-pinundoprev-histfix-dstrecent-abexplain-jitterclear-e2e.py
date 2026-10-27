#!/usr/bin/env python3
"""细妆㊸：pin对比条撤销预览tip · 吸史冲突一键改键 · DST范围最近记忆 · A/B按来源说明条 · jitter深度右键清栈."""
from __future__ import annotations
import sys, json
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
    from PySide6.QtGui import QColor, QDesktopServices, QMouseEvent
    from PySide6.QtCore import QPointF
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
        'preview_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo',
        'suggest_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix',
        'fix_stale_prune_undo_eyedropper_history_order_shortcut_conflicts',
        'list_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent',
        'remember_toast_curve_png_datetime_tz_city_dst_calendar_year_range',
        'apply_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent',
        'render_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_explain',
        'clear_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo',
    ):
        assert hasattr(HostStateMachineWidget, name), name
    ok('wave75 APIs present')

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

    # --- 1. pin compare-bar undo preview tip ---
    host._merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo = []
    empty = host.preview_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo()
    assert empty['available'] is False and empty['undo_depth'] == 0
    assert '无可撤销' in empty['tip']
    host.set_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_keys(
        'Ctrl+C', 'Ctrl+V', persist=True, warn=False)
    before = (
        host.merge_diff_fail_hist_drop_snap_guide_recent_max_pin_dec_key(),
        host.merge_diff_fail_hist_drop_snap_guide_recent_max_pin_inc_key(),
    )
    applied = host.apply_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar()
    assert applied['undo_depth'] >= 1
    prev = host.preview_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo()
    assert prev['available'] is True
    assert prev['restore'] == before
    assert '撤销预览' in prev['tip']
    assert before[0] in prev['tip']
    # UI tip carries preview
    for hx in ('#aa66ff', '#ff6688'):
        host.remember_merge_diff_fail_hist_drop_snap_guide_recent_color(hx)
    menu_g = host._build_merge_diff_fail_hist_drop_snap_guide_menu()
    bar_w = getattr(host, '_last_snap_guide_recent_max_pin_avoid_compare_bar', None)
    assert bar_w is not None
    tip = str(bar_w.toolTip() or '')
    assert '撤销预览' in tip or '右击撤销' in tip
    assert str(bar_w.property('snapGuideRecentMaxPinAvoidCompareBarUndoPreview') or '')
    host.undo_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar()
    host.reset_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_keys()
    ok('pin 对比条撤销预览 tip')

    # --- 2. hist conflict one-click rekey ---
    host.set_stale_prune_undo_eyedropper_history_order_shortcuts(
        'Ctrl+C', 'Ctrl+V', persist=True, rebind=True, warn=False)
    conf = host.detect_stale_prune_undo_eyedropper_history_order_shortcut_conflicts()
    assert conf
    sug = host.suggest_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix()
    assert sug['needed'] is True
    assert sug['changed'] is True
    assert sug['suggested_undo'] != 'Ctrl+C' or sug['suggested_redo'] != 'Ctrl+V'
    fixed = host.fix_stale_prune_undo_eyedropper_history_order_shortcut_conflicts()
    left = host.detect_stale_prune_undo_eyedropper_history_order_shortcut_conflicts(
        fixed[0], fixed[1])
    assert left == [], left
    assert fixed[0] != 'Ctrl+C' or fixed[1] != 'Ctrl+V'
    # no-conflict path
    sug2 = host.suggest_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix()
    assert sug2['needed'] is False
    host.reset_stale_prune_undo_eyedropper_history_order_shortcuts()
    ok('吸史冲突一键改键')

    # --- 3. DST year range recent memory ---
    host._toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent = []
    s.setValue('host/toastCurvePngDatetimeTzDstYearRangeRecent', [])
    s.sync()
    assert host.list_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent() == []
    host.set_toast_curve_png_datetime_tz_city_dst_calendar_year_range(2001, 2028)
    rows = host.list_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent()
    assert rows and rows[0] == (2001, 2028)
    host.set_toast_curve_png_datetime_tz_city_dst_calendar_year_range(2010, 2020)
    rows2 = host.list_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent()
    assert rows2[0] == (2010, 2020) and (2001, 2028) in rows2
    # apply recent index 1 → 2001,2028 moves to front
    got = host.apply_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent(1)
    assert got == (2001, 2028)
    assert host.toast_curve_png_datetime_tz_city_dst_calendar_year_range() == (2001, 2028)
    assert host.list_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent()[0] == (2001, 2028)
    # restore default
    host.set_toast_curve_png_datetime_tz_city_dst_calendar_year_range(1990, 2035)
    ok('DST 范围最近记忆')

    # --- 4. A/B source explain bar ---
    ex = host.render_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_explain('source')
    assert ex['active'] is True
    assert 'team' in ex['text'] and '改名' in ex['text']
    ex2 = host.render_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_explain(
        'source', source='clipboard')
    assert ex2['resolved'] == 'skip'
    assert 'clip' in ex2['text'].lower() or 'clipboard' in ex2['text'].lower() or '跳过' in ex2['text']
    ex3 = host.render_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_explain('overwrite')
    assert ex3['active'] is False and '覆盖' in ex3['text']
    host.set_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_strategy('source')
    host.set_stale_prune_undo_color_scale_ab_lock(True)
    host.set_stale_prune_undo_color_scale_ab_mirror(True)
    host.set_stale_prune_undo_color_scale_ab_mirror_dir('both')
    menu = host._build_undo_color_scale_hot_sync_menu()
    lab = getattr(host, '_last_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_explain_lab', None)
    assert lab is not None
    assert '按来源' in str(lab.text() or '')
    host.set_stale_prune_undo_color_scale_ab_lock(False)
    host.set_stale_prune_undo_color_scale_ab_mirror(False)
    host.set_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_strategy('overwrite')
    ok('A/B 按来源策略说明条')

    # --- 5. jitter depth right-click clear ---
    host.set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed(42)
    host._merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_history = []
    host._merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo = []
    host.reshuffle_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed()
    host.reshuffle_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed()
    host.undo_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_reshuffle()
    host.undo_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_reshuffle()
    d = len(host._merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo)
    assert d >= 2
    cleared = host.clear_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo()
    assert cleared == d
    assert host._merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo == []
    assert host._refresh_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_depth_ui() == 0
    # empty clear
    assert host.clear_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo() == 0
    ok('jitter 深度右键清栈')

    print(f'wave75 DONE pass={pass_n} fail={fail_n}')
    return 0 if fail_n == 0 else 1

if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as e:
        bad(f'exception · {e}')
        import traceback; traceback.print_exc()
        print(f'wave75 DONE pass={pass_n} fail={fail_n}')
        raise SystemExit(1)
