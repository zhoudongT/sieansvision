#!/usr/bin/env python3
"""细妆㊼：pin预览锁定态色标角标/快捷改键 · 吸史试键确认可撤销 · DST撤销栈深度旁标 · A/B流程切换自动载源 · jitter快照单项恢复/TTL预设档."""
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
        'prompt_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key',
        '_refresh_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_lock_badge',
        'undo_confirm_trial_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate',
        'toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_depth',
        '_refresh_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_depth_ui',
        'autoload_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_trial_for_flow',
        'switch_ab_trial_flow',
        'restore_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_snapshot',
        'list_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_presets',
        'apply_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset',
    ):
        assert hasattr(HostStateMachineWidget, name), name
    ok('wave79 APIs present')

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
    host._swatch_conflict_preview_cycle_key_no_dialog = True
    app.processEvents()

    # --- 1. pin lock badge + rebind cycle key ---
    from PySide6.QtWidgets import QLabel
    badge = QLabel('')
    host._last_snap_guide_recent_max_pin_avoid_compare_bar_undo_swatch_lock_badge = badge
    host.set_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_locked(False)
    host._refresh_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_lock_badge()
    assert badge.text() == ''
    host.set_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_locked(True)
    # lock setter refreshes swatch UI which calls badge refresh
    host._refresh_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_lock_badge()
    assert badge.text() == '🔒'
    assert badge.property('snapGuideRecentMaxPinAvoidCompareBarUndoSwatchConflictPreviewLocked') is True
    # rebind via prompt smoke
    host._swatch_conflict_preview_cycle_key_smoke = 'Ctrl+Alt+P'
    out_key = host.prompt_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key(persist=False)
    assert out_key == 'Ctrl+Alt+P'
    assert host.merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key() == 'Ctrl+Alt+P'
    # menu rebind smoke
    host._swatch_conflict_preview_cycle_key_smoke = 'Ctrl+Shift+P'
    host._swatch_conflict_preview_menu_smoke = {'action': 'rebind'}
    assert host.show_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_menu() == 'Ctrl+Shift+P'
    host.set_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_locked(False)
    ok('pin 预览锁定态色标角标 / 快捷改键')

    # --- 2. hist confirm trial undoable ---
    host.set_stale_prune_undo_eyedropper_history_order_shortcuts(
        'Ctrl+Shift+Z', 'Ctrl+Shift+Y', persist=False, rebind=True, warn=False)
    host._stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo = []
    cands = host.list_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidates()
    assert cands, 'need candidates'
    row = cands[0]
    host.trial_tip_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate(
        row['undo'], row['redo'], index=0)
    conf = host.confirm_trial_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate(persist=False)
    assert conf.get('applied') is True
    assert conf.get('undo_depth', 0) >= 1
    assert host.stale_prune_undo_eyedropper_history_order_undo_shortcut() == row['undo']
    und = host.undo_confirm_trial_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate(persist=False)
    assert und.get('undone') is True
    assert und.get('undo') == 'Ctrl+Shift+Z'
    assert host.stale_prune_undo_eyedropper_history_order_undo_shortcut() == 'Ctrl+Shift+Z'
    # menu smoke undo confirm
    host.trial_tip_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate(
        row['undo'], row['redo'], index=0)
    host.confirm_trial_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate(persist=False)
    host._eyedropper_history_order_shortcut_fix_menu_smoke_undo_confirm_trial = True
    host._eyedropper_history_order_shortcut_fix_menu_smoke_confirm_trial = False
    host._eyedropper_history_order_shortcut_fix_menu_smoke_index = None
    n = host.show_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_menu()
    assert n == 1
    assert host.stale_prune_undo_eyedropper_history_order_undo_shortcut() == 'Ctrl+Shift+Z'
    host._eyedropper_history_order_shortcut_fix_menu_smoke_undo_confirm_trial = False
    # empty stack
    host._stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo = []
    und2 = host.undo_confirm_trial_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate(persist=False)
    assert und2.get('undone') is False
    ok('吸史试键确认可撤销')

    # --- 3. DST undo depth badge ---
    host.set_toast_curve_png_datetime_tz_city_dst_calendar_year_range(1990, 2035)
    host._toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent = [
        (2000, 2010), (2011, 2020), (2021, 2030),
    ]
    host._toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo = []
    assert host.toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_depth() == 0
    from PySide6.QtWidgets import QLabel as _QLabel
    lab = _QLabel('')
    host._last_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_depth_lab = lab
    host._refresh_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_depth_ui(0)
    assert lab.text() == ''
    host.set_selected_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent([0, 1, 2])
    host.apply_all_selected_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent(persist=False)
    assert host.toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_depth() == 1
    assert lab.text() == '1'
    assert lab.property('toastCurvePngDatetimeTzDstYearRangeRecentApplyAllUndoDepth') == 1
    host.undo_apply_all_selected_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent(persist=False)
    assert host.toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_depth() == 0
    assert lab.text() == ''
    # second apply → depth 1 again, click lab undoes
    host.set_selected_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent([0])
    host.apply_all_selected_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent(persist=False)
    assert lab.text() == '1'
    ok('DST 撤销栈深度旁标')

    # --- 4. A/B autoload on flow switch ---
    s.setValue('host/stalePruneUndoColorScaleAbMirrorChannelPresetImportConflictSourceTrialByFlow', '{}')
    s.setValue('host/stalePruneUndoColorScaleAbMirrorChannelPresetImportConflictSourceTrial', '')
    s.sync()
    host._stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_trial = None
    host._stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_trial_by_flow = None
    host._last_ab_trial_autoload_flow = ''
    host.persist_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_trial_by_flow('team', flow='flow_a')
    host.persist_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_trial_by_flow('local', flow='flow_b')
    out = host.switch_ab_trial_flow('flow_a')
    assert out.get('flow') == 'flow_a'
    assert out.get('source') == 'team'
    assert out.get('switched') is True
    assert host._stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_trial == 'team'
    out2 = host.autoload_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_trial_for_flow('flow_b')
    assert out2.get('source') == 'local'
    assert out2.get('switched') is True
    # set project name triggers autoload
    host.set_toast_curve_png_project_name('flow_a', persist=False)
    assert host._stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_trial == 'team'
    auto = host._last_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_trial_autoloaded
    assert auto.get('flow') == 'flow_a'
    host.set_toast_curve_png_project_name('default', persist=False)
    ok('A/B 流程切换自动载源')

    # --- 5. jitter single restore + TTL presets ---
    presets = host.list_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_presets()
    assert len(presets) >= 5
    assert any(p.get('ms') == 0 for p in presets)
    assert any(p.get('ms') == 8000 for p in presets)
    got = host.apply_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset(3000, persist=False)
    assert got == 3000
    assert host.merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_ms() == 3000
    # menu ttl_preset smoke
    host._jitter_clear_undo_snapshot_menu_smoke = {'action': 'ttl_preset', 'ms': 15000}
    host.show_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_snapshot_menu()
    assert host.merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_ms() == 15000
    # build snapshot + restore one
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
    host.clear_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo()
    snaps = host.list_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_snapshots()
    assert len(snaps) == d
    seed0 = snaps[0].get('seed')
    r = host.restore_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_snapshot(0)
    assert r.get('restored') is True
    assert r.get('seed') == seed0
    assert r.get('snapshot_left') == d - 1
    assert len(host._merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo) == 1
    assert host._merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo[-1] == seed0
    # menu restore smoke
    left = len(host._merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo)
    assert left >= 1
    host._jitter_clear_undo_snapshot_menu_smoke = {'action': 'restore', 'index': 0}
    assert host.show_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_snapshot_menu() == 1
    assert len(host._merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo) == 2
    assert len(host._merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo) == left - 1
    # bad index
    bad_r = host.restore_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_snapshot(99)
    assert bad_r.get('restored') is False
    host.set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_ms(8000, persist=False)
    ok('jitter 快照单项恢复 / TTL 预设档')

    print(f'wave79 DONE pass={pass_n} fail={fail_n}')
    return 0 if fail_n == 0 else 1

if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as e:
        bad(f'exception · {e}')
        import traceback; traceback.print_exc()
        print(f'wave79 DONE pass={pass_n} fail={fail_n}')
        raise SystemExit(1)
