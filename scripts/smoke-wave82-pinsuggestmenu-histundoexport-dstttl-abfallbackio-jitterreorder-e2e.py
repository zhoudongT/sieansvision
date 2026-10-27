#!/usr/bin/env python3
"""细妆㊿：pin建议键候选菜单多选 · 试键撤栈导出/清空可撤 · DST撤清TTL · A/B回退记忆清/导出 · jitter自定义拖拽排序."""
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
    from PySide6.QtCore import QSettings, QTimer
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
        'show_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_menu',
        'merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_selected',
        'export_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo',
        'clear_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo',
        'undo_clear_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo',
        'toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_ms',
        'set_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_ms',
        'prompt_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_ms',
        'discard_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_snap',
        'clear_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_trial_fallback',
        'export_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_trial_fallback',
        'reorder_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs',
        'show_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_dialog',
    ):
        assert hasattr(HostStateMachineWidget, name), name
    ok('wave82 APIs present')

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
    s.setValue('host/toastCurvePngDatetimeTzDstYearRangeRecentApplyAllUndoClearUndoTtlMs', 8000)
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
    host._swatch_conflict_preview_cycle_key_suggest_menu_no_exec = True
    host._dst_clear_undo_ttl_no_dialog = True
    host._jitter_ttl_preset_customs_reorder_no_dialog = True
    app.processEvents()

    # --- 1. pin suggest menu multi-select ---
    host.set_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key(
        'Ctrl+C', persist=False)
    suggests = host.suggest_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key('Ctrl+C')
    cleans = [x for x in suggests if x.get('clean')]
    assert cleans, suggests
    pick_keys = [str(c.get('key')) for c in cleans[:2]]
    host._swatch_conflict_preview_cycle_key_suggest_menu_smoke = {
        'keys': pick_keys, 'apply': True,
    }
    mout = host.show_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_menu(
        persist=False, key='Ctrl+C')
    assert mout.get('selected') == pick_keys, mout
    assert mout.get('applied') == pick_keys[0], mout
    sel = host.merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_selected()
    assert sel == pick_keys, sel
    # resolve via menu
    host.set_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key(
        'Ctrl+C', persist=False)
    host._swatch_conflict_preview_cycle_key_suggest_menu_smoke = {
        'keys': pick_keys, 'apply': True,
    }
    host._swatch_conflict_preview_cycle_key_resolve_smoke = {'action': 'menu'}
    resolved = host.prompt_resolve_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_conflicts(
        'Ctrl+C', persist=False)
    assert resolved.get('via') == 'menu', resolved
    assert resolved.get('resolved') is True
    assert resolved.get('selected') == pick_keys
    host.set_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key(
        'Ctrl+Shift+P', persist=False)
    ok('pin建议键候选菜单多选')

    # --- 2. confirm undo export / clear undoable ---
    lab = QLabel('')
    host._last_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_depth_lab = lab
    host._stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo = []
    host._stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_clear_snap = []
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
    text = host.export_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo(
        to_clipboard=True)
    payload = json.loads(text)
    assert payload.get('kind') == 'sieans.confirm_trial_undo_stack'
    assert payload.get('depth') == depth
    assert len(payload.get('entries') or []) == depth
    # menu smoke export
    host._confirm_trial_undo_menu_smoke = {'action': 'export'}
    host.show_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_menu()
    # clear + undo_clear
    nclear = host.clear_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo(toast=True)
    assert nclear == depth
    assert host.stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_depth() == 0
    restored = host.undo_clear_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo(toast=True)
    assert restored == depth
    assert host.stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_depth() == depth
    # menu clear + undo_clear
    host._confirm_trial_undo_menu_smoke = {'action': 'clear'}
    host.show_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_menu()
    assert host.stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_depth() == 0
    host._confirm_trial_undo_menu_smoke = {'action': 'undo_clear'}
    host.show_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_menu()
    assert host.stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_depth() == depth
    ok('试键撤栈导出/清空可撤')

    # --- 3. DST clear TTL ---
    host.set_toast_curve_png_datetime_tz_city_dst_calendar_year_range(1990, 2035)
    host._toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent = [
        (2000, 2010), (2011, 2020),
    ]
    host._toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo = []
    host._toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_snap = []
    ttl0 = host.toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_ms()
    assert ttl0 == 8000
    ttl1 = host.set_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_ms(
        1500, persist=False)
    assert ttl1 == 1500
    host._dst_clear_undo_ttl_smoke = 2500
    ttl2 = host.prompt_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_ms(
        persist=False)
    assert ttl2 == 2500
    host.set_selected_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent([0, 1])
    host.apply_all_selected_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent(persist=False)
    d0 = host.toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_depth()
    assert d0 >= 1
    nclear = host.clear_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo(toast=True)
    assert nclear >= 1
    assert host.toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_depth() == nclear
    # timer should be scheduled
    t = getattr(host, '_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_timer', None)
    assert t is not None and t.isActive()
    # discard via TTL path
    nd = host.discard_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_snap(
        reason='ttl', toast=True)
    assert nd == nclear
    assert host.toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_depth() == 0
    assert not t.isActive()
    # clear again then undo_clear stops timer
    host.apply_all_selected_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent(persist=False)
    nclear2 = host.clear_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo(toast=False)
    assert nclear2 >= 1
    assert t.isActive()
    restored2 = host.undo_clear_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo(toast=False)
    assert restored2 == nclear2
    assert not t.isActive()
    # ttl=0 → no schedule
    host.set_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_ms(
        0, persist=False)
    host.clear_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo(toast=False)
    assert not t.isActive()
    host.set_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_ms(
        8000, persist=False)
    ok('DST撤清TTL')

    # --- 4. A/B fallback clear / export ---
    s.setValue('host/stalePruneUndoColorScaleAbMirrorChannelPresetImportConflictSourceTrialFallbackByFlow', '{}')
    s.sync()
    host._stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_trial_fallback_by_flow = None
    host.remember_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_trial_fallback(
        'flow_a', 'team', reason='smoke')
    host.remember_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_trial_fallback(
        'flow_b', 'local', reason='smoke')
    exp = host.export_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_trial_fallback(
        to_clipboard=True)
    ep = json.loads(exp)
    assert ep.get('kind') == 'sieans.ab_trial_fallback_memory'
    assert ep.get('count') == 2
    assert 'flow_a' in ep.get('by_flow', {})
    clr1 = host.clear_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_trial_fallback(
        'flow_a', persist=False)
    assert clr1.get('cleared') == 1
    assert clr1.get('whole') is False
    assert host.recall_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_trial_fallback(
        'flow_a').get('found') is False
    assert host.recall_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_trial_fallback(
        'flow_b').get('found') is True
    clr_all = host.clear_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_trial_fallback(
        None, persist=False)
    assert clr_all.get('whole') is True
    assert clr_all.get('cleared') >= 1
    assert host.recall_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_trial_fallback(
        'flow_b').get('found') is False
    ok('A/B回退记忆清/导出')

    # --- 5. jitter customs drag reorder ---
    host._merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs = None
    host.add_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_custom(
        4500, '4.5秒', persist=False)
    host.add_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_custom(
        9999, '烟测', persist=False)
    host.add_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_custom(
        3000, '三秒', persist=False)
    before = host.list_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs()
    ms_order = [int(c.get('ms')) for c in before]
    assert ms_order[:3] == [4500, 9999, 3000] or set(ms_order) == {4500, 9999, 3000}
    reordered = host.reorder_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs(
        [3000, 9999, 4500], persist=False)
    assert [int(c.get('ms')) for c in reordered] == [3000, 9999, 4500]
    # dialog smoke (reverse)
    host._jitter_ttl_preset_customs_reorder_smoke = [9999, 4500, 3000]
    outd = host.show_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_dialog(
        persist=False)
    assert [int(c.get('ms')) for c in outd] == [9999, 4500, 3000]
    # menu smoke ttl_reorder
    host._jitter_clear_undo_snapshot_menu_smoke = {'action': 'ttl_reorder'}
    host._jitter_ttl_preset_customs_reorder_smoke = [4500, 3000, 9999]
    host.show_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_snapshot_menu()
    left = host.list_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs()
    assert [int(c.get('ms')) for c in left] == [4500, 3000, 9999]
    ok('jitter自定义拖拽排序')

    print(f'wave82 DONE pass={pass_n} fail={fail_n}')
    return 0 if fail_n == 0 else 1

if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as e:
        bad(f'exception · {e}')
        import traceback; traceback.print_exc()
        print(f'wave82 DONE pass={pass_n} fail={fail_n}')
        raise SystemExit(1)
