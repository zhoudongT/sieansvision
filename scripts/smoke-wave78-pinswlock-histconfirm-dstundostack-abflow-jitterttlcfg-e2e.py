#!/usr/bin/env python3
"""细妆㊻：pin冲突色预览快捷键/右键锁定 · 吸史悬停tip进试键确认 · DST全应用撤销栈 · A/B试算源按流程记忆 · jitter TTL可配/旁标快照列表."""
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
        'toggle_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_lock',
        'set_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_locked',
        'show_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_menu',
        '_ensure_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_shortcut',
        'merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key',
        'confirm_trial_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate',
        'undo_apply_all_selected_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent',
        'load_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_trial_by_flow',
        'persist_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_trial_by_flow',
        'current_flow_key_for_ab_trial',
        'prompt_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_ms',
        'list_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_snapshots',
        'show_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_snapshot_menu',
    ):
        assert hasattr(HostStateMachineWidget, name), name
    ok('wave78 APIs present')

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
    s.setValue('host/stalePruneUndoColorScaleAbMirrorChannelPresetImportConflictSourceTrialByFlow', '{}')
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
    s.setValue('host/mergeDiffFailHistDropSnapGuideRecentMaxPinAvoidCompareBarUndoSwatchConflictPreviewCycleKey', 'Ctrl+Shift+P')
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
    app.processEvents()

    # --- 1. pin conflict preview shortcut / lock menu ---
    assert host.merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key() == 'Ctrl+Shift+P'
    assert host._ensure_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_shortcut() is True
    sc = getattr(host, '_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_shortcut', None)
    assert sc is not None
    host.set_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_mode('auto')
    host.set_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_locked(False)
    bar = host.cycle_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview()
    assert bar.get('conflict_preview_mode') == 'conflict'
    # lock: click cycle blocked
    host.set_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_locked(True)
    assert host.merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_locked() is True
    bar2 = host.cycle_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview()
    assert bar2.get('conflict_preview_locked') is True
    assert host.merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_mode() == 'conflict'
    # force (shortcut path) still cycles
    bar3 = host.cycle_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview(force=True)
    assert bar3.get('conflict_preview_mode') == 'clean'
    # menu lock/unlock/mode
    host._swatch_conflict_preview_menu_smoke = {'action': 'unlock'}
    assert host.show_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_menu() == 'unlock'
    assert host.merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_locked() is False
    host._swatch_conflict_preview_menu_smoke = {'action': 'lock'}
    host.show_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_menu()
    assert host.merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_locked() is True
    host._swatch_conflict_preview_menu_smoke = {'action': 'swap'}
    assert host.show_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_menu() == 'swap'
    assert host.merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_mode() == 'swap'
    host.toggle_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_lock()
    assert host.merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_locked() is False
    host.set_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_mode('auto')
    ok('pin 冲突色预览快捷键/右键锁定')

    # --- 2. hist hover tip → confirm trial ---
    host.set_stale_prune_undo_eyedropper_history_order_shortcuts(
        'Ctrl+Shift+Z', 'Ctrl+Shift+Y', persist=False, rebind=True, warn=False)
    cands = host.list_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidates()
    assert cands, 'need candidates'
    row = cands[0]
    tip = host.trial_tip_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate(
        row['undo'], row['redo'], index=0)
    assert '试键' in tip
    trial = host._last_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_trial
    assert trial.get('undo') == row['undo'] and trial.get('redo') == row['redo']
    conf = host.confirm_trial_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate(persist=False)
    assert conf.get('applied') is True
    assert host.stale_prune_undo_eyedropper_history_order_undo_shortcut() == row['undo']
    assert host.stale_prune_undo_eyedropper_history_order_redo_shortcut() == row['redo']
    # menu smoke confirm
    if len(cands) > 1:
        row2 = cands[1]
        host.trial_tip_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate(
            row2['undo'], row2['redo'], index=1)
        host._eyedropper_history_order_shortcut_fix_menu_smoke_confirm_trial = True
        host._eyedropper_history_order_shortcut_fix_menu_smoke_index = None
        n = host.show_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_menu()
        assert n == 1
        assert host.stale_prune_undo_eyedropper_history_order_undo_shortcut() == row2['undo']
        host._eyedropper_history_order_shortcut_fix_menu_smoke_confirm_trial = False
    # no trial → not applied
    host._last_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_trial = {}
    conf2 = host.confirm_trial_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate(persist=False)
    assert conf2.get('applied') is False
    ok('吸史悬停 tip 进试键确认')

    # --- 3. DST apply_all undo stack ---
    host.set_toast_curve_png_datetime_tz_city_dst_calendar_year_range(1990, 2035)
    host._toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent = [
        (2000, 2010), (2011, 2020), (2021, 2030),
    ]
    host._toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo = []
    host.set_selected_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent([0, 1, 2])
    last = host.apply_all_selected_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent(persist=False)
    assert last == (2021, 2030)
    stack = host._toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo
    assert len(stack) == 1
    assert stack[0]['before'] == (1990, 2035)
    assert len(stack[0]['applied']) == 3
    restored = host.undo_apply_all_selected_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent(persist=False)
    assert restored == (1990, 2035)
    assert host._toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo == []
    und = host._last_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undone
    assert und.get('undone') is True
    # menu smoke
    host.set_selected_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent([0, 2])
    host._dst_year_range_recent_menu_smoke = {'action': 'apply_all', 'indices': [0, 2]}
    host.show_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_menu()
    assert len(host._toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo) >= 1
    host._dst_year_range_recent_menu_smoke = {'action': 'undo_apply_all', 'indices': []}
    host.show_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_menu()
    assert host.toast_curve_png_datetime_tz_city_dst_calendar_year_range()[0] == 1990
    ok('DST 全应用后撤销栈')

    # --- 4. A/B trial source by flow ---
    s.setValue('host/stalePruneUndoColorScaleAbMirrorChannelPresetImportConflictSourceTrialByFlow', '{}')
    s.setValue('host/stalePruneUndoColorScaleAbMirrorChannelPresetImportConflictSourceTrial', '')
    s.sync()
    host._stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_trial = None
    host._stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_trial_by_flow = None
    host._toast_curve_png_project_source_name = 'flow_alpha'
    fk = host.current_flow_key_for_ab_trial()
    assert fk == 'flow_alpha'
    host.persist_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_trial_by_flow('team', flow='flow_alpha')
    host.persist_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_trial_by_flow('local', flow='flow_beta')
    mp = host.load_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_trial_map()
    assert mp.get('flow_alpha') == 'team'
    assert mp.get('flow_beta') == 'local'
    host._toast_curve_png_project_source_name = 'flow_alpha'
    assert host.load_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_trial_by_flow() == 'team'
    host._toast_curve_png_project_source_name = 'flow_beta'
    assert host.load_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_trial_by_flow() == 'local'
    # trial() also writes by-flow
    host._toast_curve_png_project_source_name = 'flow_gamma'
    t = host.trial_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_explain('clipboard')
    assert t['trial_source'] == 'clipboard'
    assert host.load_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_trial_by_flow('flow_gamma') == 'clipboard'
    # clear
    host.trial_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_explain('')
    host._toast_curve_png_project_source_name = ''
    ok('A/B 试算源按流程记忆')

    # --- 5. jitter TTL configurable + snapshot list ---
    host.set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_ms(8000, persist=False)
    host._jitter_clear_undo_ttl_smoke = 1234
    got = host.prompt_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_ms(persist=False)
    assert got == 1234
    assert host.merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_ms() == 1234
    # build clear-undo snapshot
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
    snaps = host.list_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_snapshots()
    assert len(snaps) == d
    assert snaps[0].get('label')
    host._jitter_clear_undo_snapshot_menu_smoke = {'action': 'ttl'}
    host._jitter_clear_undo_ttl_smoke = 4321
    n = host.show_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_snapshot_menu()
    assert host.merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_ms() == 4321
    host._jitter_clear_undo_snapshot_menu_smoke = {'action': 'undo_clear'}
    restored_n = host.show_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_snapshot_menu()
    assert restored_n == d
    assert len(host._merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo) == d
    assert host._merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo == []
    # discard path
    host.clear_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo()
    assert len(host._merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo) == d
    host._jitter_clear_undo_snapshot_menu_smoke = {'action': 'discard'}
    host.show_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_snapshot_menu()
    assert host._merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo == []
    host.set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_ms(8000, persist=False)
    ok('jitter TTL 可配 / 旁标快照列表')

    print(f'wave78 DONE pass={pass_n} fail={fail_n}')
    return 0 if fail_n == 0 else 1

if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as e:
        bad(f'exception · {e}')
        import traceback; traceback.print_exc()
        print(f'wave78 DONE pass={pass_n} fail={fail_n}')
        raise SystemExit(1)
