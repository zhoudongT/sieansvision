#!/usr/bin/env python3
"""细妆52：pin建议多选持久/历史 · 试键撤栈导入冲突策略 · DST TTL自定义档 · A/B回退记忆按流程导出 · jitter排序多级撤栈."""
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
    QInputDialog.getInt = staticmethod(lambda *a, **k: (4500, True))
    QInputDialog.getText = staticmethod(lambda *a, **k: ('烟测档', True))
    QDesktopServices.openUrl = staticmethod(lambda *a, **k: True)

    from desktop.host_state_machine import HostStateMachineWidget
    for name in (
        'persist_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_selected',
        'remember_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history',
        'list_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history',
        'stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy',
        'set_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy',
        'list_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs',
        'add_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_custom',
        'export_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_trial_fallback_for_flow',
        'merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth',
        'undo_reorder_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs',
    ):
        assert hasattr(HostStateMachineWidget, name), name
    ok('wave84 APIs present')

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
    s.setValue('host/mergeDiffFailHistDropSnapGuideRecentMaxPinAvoidCompareBarUndoSwatchConflictPreviewCycleKeySuggestSelected', '[]')
    s.setValue('host/mergeDiffFailHistDropSnapGuideRecentMaxPinAvoidCompareBarUndoSwatchConflictPreviewCycleKeySuggestHistory', '[]')
    s.setValue('host/stalePruneUndoEyedropperHistoryOrderShortcutConflictFixCandidateConfirmUndoImportConflict', 'replace')
    s.setValue('host/toastCurvePngDatetimeTzCityDstCalendarYearRangeRecentApplyAllUndoClearUndoTtlPresetCustoms', '[]')
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
    host._dst_ttl_preset_custom_no_dialog = True
    app.processEvents()

    # --- 1. pin suggest persist + history ---
    host.clear_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history()
    host.set_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key(
        'Ctrl+C', persist=False)
    out = host.apply_all_clean_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggests(
        key='Ctrl+C', persist=False)
    sel = list(out.get('selected') or [])
    assert sel, out
    hist = host.list_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history()
    assert hist and hist[0].get('keys') == sel, hist
    # set another selection → history grows / dedup
    host.set_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_selected(
        ['Alt+1', 'Alt+2'], persist=False, remember=True)
    hist2 = host.list_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history()
    assert hist2[0].get('keys') == ['Alt+1', 'Alt+2'], hist2
    assert len(hist2) >= 2
    # menu smoke history / restore
    host._swatch_conflict_preview_cycle_key_suggest_menu_smoke = {'action': 'history'}
    mout = host.show_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_menu(
        persist=False, key='Ctrl+C')
    assert mout.get('via') == 'history' and mout.get('history'), mout
    host._swatch_conflict_preview_cycle_key_suggest_menu_smoke = {'action': 'restore_history', 'index': 1, 'apply': False}
    mout2 = host.show_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_menu(
        persist=False, key='Ctrl+C')
    assert mout2.get('via') == 'restore_history'
    assert mout2.get('selected') == sel or mout2.get('selected') == hist2[1].get('keys'), mout2
    host._swatch_conflict_preview_cycle_key_suggest_menu_smoke = {'action': 'clear_history'}
    mout3 = host.show_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_menu(
        persist=False, key='Ctrl+C')
    assert mout3.get('via') == 'clear_history'
    assert host.list_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history() == []
    host.set_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key(
        'Ctrl+Shift+P', persist=False)
    ok('pin建议多选持久/历史')

    # --- 2. confirm import conflict strategy ---
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
    # skip strategy
    host.set_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy(
        'skip', persist=False)
    assert host.stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy() == 'skip'
    skip_out = host.import_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo(
        text, from_clipboard=False, conflict='skip')
    assert skip_out.get('reason') == 'conflict_skip'
    assert skip_out.get('imported') == 0
    assert host.stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_depth() == depth
    # merge strategy
    before = depth
    merge_out = host.import_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo(
        text, from_clipboard=False, conflict='merge')
    assert merge_out.get('ok') is True and merge_out.get('strategy') == 'merge'
    assert host.stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_depth() >= before
    # replace
    rep = host.import_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo(
        text, from_clipboard=False, conflict='replace')
    assert rep.get('ok') is True and rep.get('strategy') == 'replace'
    assert host.stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_depth() == depth
    # ask → smoke skip
    host._confirm_trial_undo_import_conflict_smoke = 'skip'
    ask = host.import_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo(
        text, from_clipboard=False, conflict='ask')
    assert ask.get('reason') == 'conflict_skip'
    host._confirm_trial_undo_import_conflict_smoke = None
    # menu smoke with conflict kw
    host.clear_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo(toast=False)
    host._confirm_trial_undo_menu_smoke = {
        'action': 'import', 'text': text, 'clipboard': False, 'conflict': 'replace'}
    host.show_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_menu()
    assert host.stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_depth() == depth
    host.set_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy(
        'replace', persist=False)
    ok('试键撤栈导入冲突策略')

    # --- 3. DST TTL customs ---
    host._toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs = None
    customs0 = host.list_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs()
    assert customs0 == []
    host.add_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_custom(
        4500, '4.5秒', persist=False)
    presets = host.list_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_presets()
    assert any(int(p.get('ms')) == 4500 and p.get('custom') for p in presets), presets
    host._dst_clear_undo_ttl_preset_menu_smoke = {'action': 'add_custom', 'ms': 9999, 'label': '烟测'}
    n = host.show_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_menu(
        persist=False)
    customs = host.list_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs()
    assert any(int(c.get('ms')) == 9999 for c in customs), customs
    host._dst_clear_undo_ttl_preset_menu_smoke = {'action': 'delete_custom', 'ms': 9999}
    host.show_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_menu(
        persist=False)
    customs2 = host.list_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs()
    assert not any(int(c.get('ms')) == 9999 for c in customs2)
    host.apply_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset(
        4500, persist=False)
    assert host.toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_ms() == 4500
    host.apply_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset(
        8000, persist=False)
    ok('DST TTL自定义档')

    # --- 4. A/B fallback export by flow ---
    s.setValue('host/stalePruneUndoColorScaleAbMirrorChannelPresetImportConflictSourceTrialFallbackByFlow', '{}')
    s.sync()
    host._stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_trial_fallback_by_flow = None
    host.remember_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_trial_fallback(
        'flow_a', 'team', reason='a')
    host.remember_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_trial_fallback(
        'flow_b', 'local', reason='b')
    full = host.export_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_trial_fallback(
        to_clipboard=False)
    full_p = json.loads(full)
    assert full_p.get('count') == 2 and 'flow_a' in full_p.get('by_flow') and 'flow_b' in full_p.get('by_flow')
    sub = host.export_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_trial_fallback(
        ['flow_a'], to_clipboard=False)
    sub_p = json.loads(sub)
    assert sub_p.get('subset') is True
    assert sub_p.get('count') == 1
    assert list(sub_p.get('by_flow').keys()) == ['flow_a']
    one = host.export_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_trial_fallback_for_flow(
        'flow_b', to_clipboard=False)
    one_p = json.loads(one)
    assert one_p.get('count') == 1 and 'flow_b' in one_p.get('by_flow')
    ok('A/B回退记忆按流程导出子集')

    # --- 5. jitter reorder multi-stack ---
    host._merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs = None
    host.clear_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo()
    host.add_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_custom(
        4500, '4.5秒', persist=False)
    host.add_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_custom(
        9999, '烟测', persist=False)
    host.add_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_custom(
        3000, '三秒', persist=False)
    before = [int(c.get('ms')) for c in host.list_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs()]
    host.reorder_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs(
        [3000, 9999, 4500], persist=False)
    host.reorder_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs(
        [9999, 3000, 4500], persist=False)
    host.reorder_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs(
        [4500, 3000, 9999], persist=False)
    depth_u = host.merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth()
    assert depth_u == 3, depth_u
    mid = [int(c.get('ms')) for c in host.list_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs()]
    assert mid == [4500, 3000, 9999]
    u1 = host.undo_reorder_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs(
        persist=False)
    assert u1.get('undone') is True and u1.get('depth') == 2
    assert [int(c.get('ms')) for c in host.list_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs()] == [9999, 3000, 4500]
    u2 = host.undo_reorder_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs(
        persist=False, steps=2)
    assert u2.get('undone') is True and u2.get('steps') == 2
    assert [int(c.get('ms')) for c in host.list_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs()] == before
    assert host.merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth() == 0
    u3 = host.undo_reorder_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs(
        persist=False)
    assert u3.get('undone') is False
    ok('jitter排序多级撤栈')

    print(f'wave84 DONE pass={pass_n} fail={fail_n}')
    return 0 if fail_n == 0 else 1

if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as e:
        bad(f'exception · {e}')
        import traceback; traceback.print_exc()
        print(f'wave84 DONE pass={pass_n} fail={fail_n}')
        raise SystemExit(1)
