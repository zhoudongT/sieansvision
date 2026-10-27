#!/usr/bin/env python3
"""细妆㊺：pin色标点击切冲突色预览 · 吸史候选悬停试键tip · DST全应用/全清 · A/B试算源记忆持久 · jitter撤清深度旁标/超时丢快照."""
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
        QApplication, QMessageBox, QFileDialog, QColorDialog, QInputDialog, QPushButton,
    )
    from PySide6.QtCore import QSettings, Qt, QTimer
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
        'cycle_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview',
        'set_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_mode',
        'trial_tip_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate',
        'apply_all_selected_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent',
        'clear_selected_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent',
        'select_all_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent',
        'load_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_trial',
        'persist_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_trial',
        'discard_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo',
        'set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_ms',
        '_refresh_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_depth_ui',
    ):
        assert hasattr(HostStateMachineWidget, name), name
    ok('wave77 APIs present')

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
    s.setValue('host/stalePruneUndoColorScaleAbMirrorChannelPresetImportConflictSourceTrial', '')
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
    s.setValue('host/mergeDiffFailHistDropPulsePreviewLoopGapJitterSeedRedoClearUndoTtlMs', 8000)
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
    host._eyedropper_history_order_shortcut_fix_menu_no_exec = True

    # --- 1. pin swatch conflict color preview cycle ---
    host._merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo = []
    host.set_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_mode('auto')
    assert host.merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_mode() == 'auto'
    host.set_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_keys(
        'Ctrl+C', 'Ctrl+V', persist=True, warn=False)
    host.apply_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar()
    r0 = host.render_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch()
    assert r0['conflict_preview_mode'] == 'auto'
    c1 = host.cycle_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview()
    assert c1['conflict_preview_mode'] == 'conflict'
    assert c1['swatch_current'] == '#e6a23c' and c1['swatch_restore'] == '#e6a23c'
    c2 = host.cycle_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview()
    assert c2['conflict_preview_mode'] == 'clean'
    assert c2['swatch_current'] == '#3ecf8e'
    c3 = host.cycle_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview()
    assert c3['conflict_preview_mode'] == 'swap'
    c4 = host.cycle_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview()
    assert c4['conflict_preview_mode'] == 'auto'
    host.set_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_mode('auto')
    host.undo_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar()
    host.reset_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_keys()
    ok('pin 色标点击切冲突色预览')

    # --- 2. hist candidate hover trial tip ---
    host.set_stale_prune_undo_eyedropper_history_order_shortcuts(
        'Ctrl+C', 'Ctrl+V', persist=True, rebind=True, warn=False)
    cands = host.list_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidates()
    assert cands
    tip = host.trial_tip_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate(
        cands[0]['undo'], cands[0]['redo'], index=0)
    assert '试键' in tip
    assert cands[0]['undo'] in tip and cands[0]['redo'] in tip
    assert '干净' in tip
    trial = host._last_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_trial
    assert trial['clean'] is True
    # keys unchanged by tip
    assert host.stale_prune_undo_eyedropper_history_order_undo_shortcut() == 'Ctrl+C'
    host.reset_stale_prune_undo_eyedropper_history_order_shortcuts()
    ok('吸史候选悬停试键 tip')

    # --- 3. DST 全应用/全清 ---
    host._toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent = []
    s.setValue('host/toastCurvePngDatetimeTzDstYearRangeRecent', [])
    s.sync()
    host.set_toast_curve_png_datetime_tz_city_dst_calendar_year_range(2001, 2028)
    host.set_toast_curve_png_datetime_tz_city_dst_calendar_year_range(2010, 2020)
    host.set_toast_curve_png_datetime_tz_city_dst_calendar_year_range(1995, 2015)
    rows = host.list_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent()
    assert len(rows) >= 3
    sel_all = host.select_all_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent()
    assert len(sel_all) == len(rows)
    host.set_selected_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent([0, 2])
    # apply all → last of selected (index 2 range) wins
    target = rows[2]
    got = host.apply_all_selected_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent()
    assert got == target or host.toast_curve_png_datetime_tz_city_dst_calendar_year_range() == target
    host.set_selected_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent([0, 1])
    cleared = host.clear_selected_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent()
    assert cleared == []
    assert host.selected_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent() == []
    # memory intact
    assert len(host.list_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent()) >= 3
    # menu smoke
    host._dst_year_range_recent_menu_smoke = {'action': 'select_all', 'indices': []}
    host.show_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_menu()
    assert len(host.selected_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent()) >= 3
    host._dst_year_range_recent_menu_smoke = {'action': 'clear_sel', 'indices': []}
    host.show_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_menu()
    assert host.selected_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent() == []
    host.set_toast_curve_png_datetime_tz_city_dst_calendar_year_range(1990, 2035)
    ok('DST 多选全应用/全清')

    # --- 4. A/B trial persist ---
    s.setValue('host/stalePruneUndoColorScaleAbMirrorChannelPresetImportConflictSourceTrial', '')
    s.sync()
    host._stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_trial = None
    assert host.load_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_trial() == ''
    t = host.trial_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_explain('team')
    assert t['trial_source'] == 'team'
    assert s.value('host/stalePruneUndoColorScaleAbMirrorChannelPresetImportConflictSourceTrial') == 'team'
    host._stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_trial = None
    assert host.load_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_trial() == 'team'
    host.persist_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_trial('local')
    assert s.value('host/stalePruneUndoColorScaleAbMirrorChannelPresetImportConflictSourceTrial') == 'local'
    host.trial_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_explain('')
    assert s.value('host/stalePruneUndoColorScaleAbMirrorChannelPresetImportConflictSourceTrial') == ''
    ok('A/B 试算源记忆+持久')

    # --- 5. jitter clear-undo depth + TTL discard ---
    host.set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_ms(50, persist=False)
    assert host.merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_ms() == 50
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
    cleared = host.clear_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo()
    assert cleared == d
    assert len(host._merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo) == d
    depth_ui = host._refresh_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_depth_ui()
    assert depth_ui == d
    # wait TTL
    t0 = getattr(host, '_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_timer', None)
    assert t0 is not None and t0.isActive()
    # process events until discarded
    for _ in range(40):
        app.processEvents()
        if not host._merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo:
            break
        QTimer.singleShot(20, lambda: None)
        app.processEvents()
        import time; time.sleep(0.02)
    assert host._merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo == []
    disc = host._last_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_discarded
    assert disc.get('reason') == 'ttl' and disc.get('discarded') == d
    assert host._refresh_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_depth_ui() == 0
    # manual discard path
    host._merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo = [1, 2]
    host.clear_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo()
    assert host.discard_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo(reason='manual') == 2
    assert host._merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo == []
    host.set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_ms(8000, persist=False)
    ok('jitter 撤清深度旁标/超时丢快照')

    print(f'wave77 DONE pass={pass_n} fail={fail_n}')
    return 0 if fail_n == 0 else 1

if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as e:
        bad(f'exception · {e}')
        import traceback; traceback.print_exc()
        print(f'wave77 DONE pass={pass_n} fail={fail_n}')
        raise SystemExit(1)
