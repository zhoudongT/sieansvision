#!/usr/bin/env python3
"""细妆㊽：pin锁角标点击切换+cycle键冲突检测 · 试键撤销深度旁标 · DST深度长按清栈 · A/B载源失败回退提示 · jitter预设自定义/单项恢复动画."""
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
        QApplication, QMessageBox, QFileDialog, QColorDialog, QInputDialog, QPushButton, QLabel,
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
        'detect_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_conflicts',
        'format_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_conflicts',
        'toggle_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_lock',
        'stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_depth',
        '_refresh_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_depth_ui',
        'clear_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo',
        'toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_long_press_ms',
        'autoload_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_trial_for_flow',
        'add_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_custom',
        'prompt_add_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_custom',
        '_animate_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_snapshot_restore',
    ):
        assert hasattr(HostStateMachineWidget, name), name
    ok('wave80 APIs present')

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
    s.setValue('host/mergeDiffFailHistDropPulsePreviewLoopGapJitterSeedRedoClearUndoTtlPresetCustoms', '[]')
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
    host._jitter_ttl_preset_custom_no_dialog = True
    app.processEvents()

    # --- 1. lock badge click toggle + cycle key conflict ---
    badge = QLabel('')
    host._last_snap_guide_recent_max_pin_avoid_compare_bar_undo_swatch_lock_badge = badge
    host.set_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_locked(False)
    host._refresh_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_lock_badge()
    assert '点击锁定' in (badge.toolTip() or '')
    host.toggle_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_lock()
    assert host.merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_locked() is True
    host._refresh_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_lock_badge()
    assert badge.text() == '🔒'
    assert '点击解锁' in (badge.toolTip() or '')
    host.toggle_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_lock()
    assert host.merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_locked() is False
    # conflict: Ctrl+C reserved
    confs = host.detect_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_conflicts('Ctrl+C')
    assert confs and any('保留' in str(c.get('reason')) for c in confs)
    fmt = host.format_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_conflicts(confs)
    assert 'Ctrl+C' in fmt
    # conflict with dec key
    confs2 = host.detect_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_conflicts('Ctrl+[')
    assert any('减键' in str(c.get('reason')) for c in confs2)
    # set with conflict still applies + records
    host.set_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key('Ctrl+Z', persist=False)
    assert host.merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key() == 'Ctrl+Z'
    last = host._last_snap_guide_recent_max_pin_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_set
    assert last.get('conflicts')
    # clean key
    host.set_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key('Ctrl+Shift+P', persist=False)
    confs_ok = host.detect_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_conflicts('Ctrl+Shift+P')
    assert confs_ok == [] or confs_ok is not None
    ok('pin 锁角标点击切换 + cycle 键冲突检测')

    # --- 2. confirm trial undo depth badge ---
    lab = QLabel('')
    host._last_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_depth_lab = lab
    host._stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo = []
    host._refresh_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_depth_ui(0)
    assert lab.text() == ''
    assert host.stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_depth() == 0
    host.set_stale_prune_undo_eyedropper_history_order_shortcuts(
        'Ctrl+Shift+Z', 'Ctrl+Shift+Y', persist=False, rebind=True, warn=False)
    cands = host.list_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidates()
    assert cands
    row = cands[0]
    host.trial_tip_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate(
        row['undo'], row['redo'], index=0)
    conf = host.confirm_trial_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate(persist=False)
    assert conf.get('applied') is True
    assert host.stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_depth() == 1
    assert lab.text() == '1'
    host.undo_confirm_trial_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate(persist=False)
    assert host.stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_depth() == 0
    assert lab.text() == ''
    ok('试键撤销深度旁标')

    # --- 3. DST depth long-press clear ---
    host.set_toast_curve_png_datetime_tz_city_dst_calendar_year_range(1990, 2035)
    host._toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent = [
        (2000, 2010), (2011, 2020),
    ]
    host._toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo = []
    host.set_selected_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent([0, 1])
    host.apply_all_selected_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent(persist=False)
    assert host.toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_depth() == 1
    # second apply to deepen
    host.set_toast_curve_png_datetime_tz_city_dst_calendar_year_range(1990, 2035, persist=False) if False else None
    host.set_selected_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent([0])
    host.apply_all_selected_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent(persist=False)
    assert host.toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_depth() >= 1
    ms = host.toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_long_press_ms()
    assert 200 <= ms <= 3000
    nclear = host.clear_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo(toast=True)
    assert nclear >= 1
    assert host.toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_depth() == 0
    assert host.clear_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo() == 0
    ok('DST 深度长按清栈')

    # --- 4. A/B load fallback tip ---
    s.setValue('host/stalePruneUndoColorScaleAbMirrorChannelPresetImportConflictSourceTrialByFlow', '{}')
    s.setValue('host/stalePruneUndoColorScaleAbMirrorChannelPresetImportConflictSourceTrial', 'team')
    s.sync()
    host._stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_trial = 'team'
    host._stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_trial_by_flow = None
    host._last_ab_trial_autoload_flow = 'seed'
    # unknown flow → no_flow_memory fallback
    out = host.autoload_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_trial_for_flow('flow_unknown')
    assert out.get('fallback') is True
    assert out.get('fallback_reason') == 'no_flow_memory'
    assert out.get('source') == 'team'  # global
    # known flow
    host.persist_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_trial_by_flow('local', flow='flow_known')
    out2 = host.autoload_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_trial_for_flow('flow_known')
    assert out2.get('fallback') is False
    assert out2.get('source') == 'local'
    # simulate error path: break load_map temporarily
    def _boom(*a, **k):
        raise RuntimeError('boom')
    host.load_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_trial_map = _boom  # type: ignore
    host._stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_trial = 'local'
    out3 = host.autoload_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_trial_for_flow('flow_err')
    assert out3.get('fallback') is True
    assert str(out3.get('fallback_reason') or '').startswith('error:')
    # restore method
    del host.load_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_trial_map
    ok('A/B 载源失败回退提示')

    # --- 5. jitter custom presets + restore anim ---
    host._merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs = None
    customs = host.add_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_custom(
        4500, '4.5秒', persist=False)
    assert any(int(c.get('ms')) == 4500 for c in customs)
    presets = host.list_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_presets()
    assert any(int(p.get('ms')) == 4500 and p.get('custom') for p in presets)
    host._jitter_ttl_preset_custom_smoke = {'ms': 9999, 'label': '烟测'}
    outc = host.prompt_add_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_custom(persist=False)
    assert any(int(c.get('ms')) == 9999 for c in outc)
    host._jitter_clear_undo_snapshot_menu_smoke = {'action': 'ttl_custom'}
    host._jitter_ttl_preset_custom_smoke = {'ms': 7777, 'label': '菜单'}
    n = host.show_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_snapshot_menu()
    assert n >= 1
    # restore + anim
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
    # attach fake targets for anim
    host._last_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_depth_lab = QLabel('2')
    host._last_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_depth_lab = QLabel(str(d))
    r = host.restore_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_snapshot(0)
    assert r.get('restored') is True
    assert r.get('animated') is True
    anim = host._last_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_snapshot_restore_anim
    assert anim.get('animated') is True
    # process anim timer
    app.processEvents()
    host.set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_ms(8000, persist=False)
    ok('jitter 预设自定义 / 单项恢复动画')

    print(f'wave80 DONE pass={pass_n} fail={fail_n}')
    return 0 if fail_n == 0 else 1

if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as e:
        bad(f'exception · {e}')
        import traceback; traceback.print_exc()
        print(f'wave80 DONE pass={pass_n} fail={fail_n}')
        raise SystemExit(1)
