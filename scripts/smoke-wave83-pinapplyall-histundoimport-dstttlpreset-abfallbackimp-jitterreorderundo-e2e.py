#!/usr/bin/env python3
"""细妆51：pin建议批量应用全选干净键 · 试键撤栈JSON导入 · DST TTL预设档 · A/B回退记忆导入 · jitter排序可撤."""
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
        'apply_all_clean_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggests',
        'import_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo',
        'list_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_presets',
        'apply_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset',
        'show_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_menu',
        'import_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_trial_fallback',
        'undo_reorder_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs',
    ):
        assert hasattr(HostStateMachineWidget, name), name
    ok('wave83 APIs present')

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
    host._dst_clear_undo_ttl_preset_menu_no_exec = True
    app.processEvents()

    # --- 1. pin apply_all_clean ---
    host.set_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key(
        'Ctrl+C', persist=False)
    suggests = host.suggest_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key('Ctrl+C')
    cleans = [x for x in suggests if x.get('clean')]
    assert cleans, suggests
    out = host.apply_all_clean_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggests(
        key='Ctrl+C', persist=False)
    assert out.get('clean_count') == len(cleans) or out.get('clean_count') >= 1, out
    assert out.get('applied') == out.get('selected')[0]
    assert host.merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_selected() == out.get('selected')
    # menu smoke
    host.set_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key(
        'Ctrl+C', persist=False)
    host._swatch_conflict_preview_cycle_key_suggest_menu_smoke = {'action': 'apply_all_clean'}
    mout = host.show_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_menu(
        persist=False, key='Ctrl+C')
    assert mout.get('via') == 'apply_all_clean' or mout.get('applied'), mout
    # resolve via apply_all_clean
    host.set_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key(
        'Ctrl+C', persist=False)
    host._swatch_conflict_preview_cycle_key_resolve_smoke = {'action': 'apply_all_clean'}
    resolved = host.prompt_resolve_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_conflicts(
        'Ctrl+C', persist=False)
    assert resolved.get('via') == 'apply_all_clean', resolved
    assert resolved.get('resolved') is True
    host.set_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key(
        'Ctrl+Shift+P', persist=False)
    ok('pin建议批量应用全选干净键')

    # --- 2. confirm undo JSON import ---
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
    assert depth >= 2
    text = host.export_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo(
        to_clipboard=False)
    # clear then import replace
    host.clear_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo(toast=False)
    assert host.stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_depth() == 0
    imp = host.import_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo(
        text, merge=False, from_clipboard=False)
    assert imp.get('ok') is True
    assert imp.get('imported') == depth
    assert host.stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_depth() == depth
    # menu smoke import
    host.clear_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo(toast=False)
    host._confirm_trial_undo_menu_smoke = {'action': 'import', 'text': text, 'clipboard': False}
    n = host.show_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_menu()
    assert host.stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_depth() == depth
    # merge adds
    before = host.stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_depth()
    imp2 = host.import_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo(
        text, merge=True, from_clipboard=False)
    assert imp2.get('ok') is True
    assert host.stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_depth() >= before
    ok('试键撤栈JSON导入')

    # --- 3. DST TTL presets ---
    presets = host.list_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_presets()
    assert any(int(p.get('ms')) == 0 for p in presets)
    assert any(int(p.get('ms')) == 8000 for p in presets)
    assert len(presets) >= 6
    applied = host.apply_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset(
        3000, persist=False)
    assert applied == 3000
    assert host.toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_ms() == 3000
    host._dst_clear_undo_ttl_preset_menu_smoke = {'action': 'apply', 'ms': 15000}
    n = host.show_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_menu(
        persist=False)
    assert host.toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_ms() == 15000
    host.apply_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset(
        8000, persist=False)
    ok('DST TTL预设档')

    # --- 4. A/B fallback import ---
    s.setValue('host/stalePruneUndoColorScaleAbMirrorChannelPresetImportConflictSourceTrialFallbackByFlow', '{}')
    s.sync()
    host._stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_trial_fallback_by_flow = None
    host.remember_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_trial_fallback(
        'flow_x', 'team', reason='seed')
    exp = host.export_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_trial_fallback(
        to_clipboard=False)
    host.clear_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_trial_fallback(
        None, persist=False)
    assert host.recall_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_trial_fallback(
        'flow_x').get('found') is False
    # import replace
    imp = host.import_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_trial_fallback(
        exp, merge=False, from_clipboard=False, persist=False)
    assert imp.get('ok') is True
    assert imp.get('imported') >= 1
    assert host.recall_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_trial_fallback(
        'flow_x').get('source') == 'team'
    # merge new
    extra = json.dumps({
        'kind': 'sieans.ab_trial_fallback_memory',
        'by_flow': {'flow_y': {'source': 'local', 'reason': 'imp'}},
    }, ensure_ascii=False)
    imp2 = host.import_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_trial_fallback(
        extra, merge=True, from_clipboard=False, persist=False)
    assert imp2.get('ok') is True
    assert host.recall_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_trial_fallback(
        'flow_y').get('source') == 'local'
    assert host.recall_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_trial_fallback(
        'flow_x').get('found') is True
    ok('A/B回退记忆导入')

    # --- 5. jitter reorder undo ---
    host._merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs = None
    host.add_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_custom(
        4500, '4.5秒', persist=False)
    host.add_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_custom(
        9999, '烟测', persist=False)
    host.add_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_custom(
        3000, '三秒', persist=False)
    before = [int(c.get('ms')) for c in host.list_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs()]
    host.reorder_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs(
        [3000, 9999, 4500], persist=False)
    mid = [int(c.get('ms')) for c in host.list_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs()]
    assert mid == [3000, 9999, 4500]
    und = host.undo_reorder_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs(
        persist=False)
    assert und.get('undone') is True
    after = [int(c.get('ms')) for c in host.list_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs()]
    assert after == before
    # second undo empty
    und2 = host.undo_reorder_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs(
        persist=False)
    assert und2.get('undone') is False
    # menu smoke: reorder then undo
    host._jitter_ttl_preset_customs_reorder_smoke = [9999, 4500, 3000]
    host._jitter_clear_undo_snapshot_menu_smoke = {'action': 'ttl_reorder'}
    host.show_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_snapshot_menu()
    assert [int(c.get('ms')) for c in host.list_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs()] == [9999, 4500, 3000]
    host._jitter_clear_undo_snapshot_menu_smoke = {'action': 'ttl_reorder_undo'}
    host.show_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_snapshot_menu()
    assert [int(c.get('ms')) for c in host.list_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs()] == before
    ok('jitter排序可撤')

    print(f'wave83 DONE pass={pass_n} fail={fail_n}')
    return 0 if fail_n == 0 else 1

if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as e:
        bad(f'exception · {e}')
        import traceback; traceback.print_exc()
        print(f'wave83 DONE pass={pass_n} fail={fail_n}')
        raise SystemExit(1)
