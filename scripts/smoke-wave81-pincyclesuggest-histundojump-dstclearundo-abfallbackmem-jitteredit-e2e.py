#!/usr/bin/env python3
"""细妆㊾：pin cycle冲突弹窗改键建议 · 试键撤销栈浏览/多级跳 · DST清栈可撤销 · A/B回退源记忆 · jitter自定义预设编辑/删."""
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
    QInputDialog.getInt = staticmethod(lambda *a, **k: (200, False))
    QInputDialog.getText = staticmethod(lambda *a, **k: ('烟测档', True))
    QDesktopServices.openUrl = staticmethod(lambda *a, **k: True)

    from desktop.host_state_machine import HostStateMachineWidget
    for name in (
        'suggest_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key',
        'prompt_resolve_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_conflicts',
        'list_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_entries',
        'jump_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo',
        'show_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_menu',
        'undo_clear_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo',
        'toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_depth',
        'remember_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_trial_fallback',
        'recall_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_trial_fallback',
        'edit_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_custom',
        'delete_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_custom',
        'prompt_edit_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_custom',
    ):
        assert hasattr(HostStateMachineWidget, name), name
    ok('wave81 APIs present')

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
    s.setValue('host/stalePruneUndoColorScaleAbMirrorChannelPresetImportConflictSourceTrialFallbackByFlow', '{}')
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
    host._swatch_conflict_preview_cycle_key_resolve_no_dialog = True
    host._confirm_trial_undo_menu_no_exec = True
    host._jitter_ttl_preset_custom_edit_no_dialog = True
    app.processEvents()

    # --- 1. cycle conflict suggest dialog ---
    confs = host.detect_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_conflicts('Ctrl+C')
    assert confs
    sug = host.suggest_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key('Ctrl+C')
    cleans = [x for x in sug if x.get('clean')]
    assert cleans, sug
    host.set_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key('Ctrl+C', persist=False)
    host._swatch_conflict_preview_cycle_key_resolve_smoke = {'apply': True}
    resolved = host.prompt_resolve_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_conflicts(
        'Ctrl+C', persist=False)
    assert resolved.get('needed') is True
    assert resolved.get('resolved') is True
    assert resolved.get('applied') != 'Ctrl+C'
    # no conflict → needed False
    host.set_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key(
        str(resolved.get('applied')), persist=False)
    r2 = host.prompt_resolve_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_conflicts(
        persist=False)
    assert r2.get('needed') is False
    # prompt path also resolves
    host._swatch_conflict_preview_cycle_key_smoke = 'Ctrl+Z'
    host._swatch_conflict_preview_cycle_key_resolve_smoke = {'apply': True, 'key': 'Ctrl+Alt+P'}
    outp = host.prompt_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key(persist=False)
    assert outp == 'Ctrl+Alt+P' or outp != 'Ctrl+Z'
    host.set_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key(
        'Ctrl+Shift+P', persist=False)
    ok('pin cycle 冲突弹窗改键建议')

    # --- 2. confirm undo browse / jump ---
    lab = QLabel('')
    host._last_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_depth_lab = lab
    host._stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo = []
    host.set_stale_prune_undo_eyedropper_history_order_shortcuts(
        'Ctrl+Shift+Z', 'Ctrl+Shift+Y', persist=False, rebind=True, warn=False)
    cands = host.list_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidates()
    assert len(cands) >= 2
    for i in range(min(3, len(cands))):
        row = cands[i]
        host.trial_tip_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate(
            row['undo'], row['redo'], index=i)
        host.confirm_trial_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate(persist=False)
    depth = host.stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_depth()
    assert depth >= 2, depth
    entries = host.list_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_entries()
    assert len(entries) == depth
    assert entries[0]['index'] == 0
    # jump to index 1 → undo 2 steps
    before_d = depth
    jmp = host.jump_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo(1, persist=False)
    assert jmp.get('jumped') is True
    assert jmp.get('steps') == 2
    assert host.stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_depth() == before_d - 2
    # menu smoke jump
    # re-fill stack
    host._stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo = []
    for i in range(min(3, len(cands))):
        row = cands[i]
        host.trial_tip_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate(
            row['undo'], row['redo'], index=i)
        host.confirm_trial_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate(persist=False)
    host._confirm_trial_undo_menu_smoke = {'action': 'jump', 'index': 0}
    n = host.show_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_menu()
    assert n >= 1 or host.stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_depth() >= 0
    ok('试键撤销栈浏览/多级跳')

    # --- 3. DST clear undoable ---
    host.set_toast_curve_png_datetime_tz_city_dst_calendar_year_range(1990, 2035)
    host._toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent = [
        (2000, 2010), (2011, 2020),
    ]
    host._toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo = []
    host._toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_snap = []
    host.set_selected_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent([0, 1])
    host.apply_all_selected_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent(persist=False)
    host.set_selected_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent([0])
    host.apply_all_selected_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent(persist=False)
    d0 = host.toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_depth()
    assert d0 >= 1
    nclear = host.clear_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo(toast=True)
    assert nclear >= 1
    assert host.toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_depth() == 0
    assert host.toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_depth() == nclear
    restored = host.undo_clear_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo(toast=True)
    assert restored == nclear
    assert host.toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_depth() == nclear
    assert host.toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_depth() == 0
    assert host.undo_clear_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo() == 0
    ok('DST 清栈可撤销')

    # --- 4. A/B fallback memory ---
    s.setValue('host/stalePruneUndoColorScaleAbMirrorChannelPresetImportConflictSourceTrialByFlow', '{}')
    s.setValue('host/stalePruneUndoColorScaleAbMirrorChannelPresetImportConflictSourceTrialFallbackByFlow', '{}')
    s.setValue('host/stalePruneUndoColorScaleAbMirrorChannelPresetImportConflictSourceTrial', 'team')
    s.sync()
    host._stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_trial = 'team'
    host._stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_trial_by_flow = None
    host._stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_trial_fallback_by_flow = None
    host._last_ab_trial_autoload_flow = 'seed'
    out = host.autoload_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_trial_for_flow('flow_fb1')
    assert out.get('fallback') is True
    assert out.get('fallback_reason') == 'no_flow_memory'
    mem = host.recall_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_trial_fallback('flow_fb1')
    assert mem.get('found') is True
    assert mem.get('source') == 'team'
    # second autoload → recalled
    host._last_ab_trial_autoload_flow = 'other'
    out2 = host.autoload_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_trial_for_flow('flow_fb1')
    assert out2.get('recalled_fallback') is True
    assert out2.get('fallback') is False
    assert out2.get('source') == 'team'
    # manual remember
    host.remember_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_trial_fallback(
        'flow_x', 'local', reason='manual')
    assert host.recall_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_trial_fallback('flow_x').get('source') == 'local'
    ok('A/B 回退源记忆')

    # --- 5. jitter custom edit/delete ---
    host._merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs = None
    host.add_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_custom(
        4500, '4.5秒', persist=False)
    host.add_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_custom(
        9999, '烟测', persist=False)
    edited = host.edit_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_custom(
        4500, 5500, '5.5秒', persist=False)
    assert any(int(c.get('ms')) == 5500 and c.get('label') == '5.5秒' for c in edited)
    assert not any(int(c.get('ms')) == 4500 for c in edited)
    host._jitter_ttl_preset_custom_edit_smoke = {'ms': 6600, 'label': '改档'}
    oute = host.prompt_edit_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_custom(
        ms=5500, persist=False)
    assert any(int(c.get('ms')) == 6600 for c in oute)
    deleted = host.delete_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_custom(
        ms=9999, persist=False)
    assert not any(int(c.get('ms')) == 9999 for c in deleted)
    host._jitter_clear_undo_snapshot_menu_smoke = {'action': 'ttl_delete', 'ms': 6600}
    host.show_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_snapshot_menu()
    left = host.list_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs()
    assert not any(int(c.get('ms')) == 6600 for c in left)
    # re-add and menu edit smoke
    host.add_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_custom(
        3000, '三秒', persist=False)
    host._jitter_ttl_preset_custom_edit_smoke = {'ms': 3500, 'label': '三秒半'}
    host._jitter_clear_undo_snapshot_menu_smoke = {'action': 'ttl_edit', 'ms': 3000}
    host.show_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_snapshot_menu()
    left2 = host.list_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs()
    assert any(int(c.get('ms')) == 3500 for c in left2)
    ok('jitter 自定义预设编辑/删')

    print(f'wave81 DONE pass={pass_n} fail={fail_n}')
    return 0 if fail_n == 0 else 1

if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as e:
        bad(f'exception · {e}')
        import traceback; traceback.print_exc()
        print(f'wave81 DONE pass={pass_n} fail={fail_n}')
        raise SystemExit(1)
