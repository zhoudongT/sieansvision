#!/usr/bin/env python3
"""细妆53：pin建议历史子菜单 · 导入冲突策略菜单 · DST自定义编辑/删项 · A/B回退按流程导入/冲突 · jitter排序重做栈."""
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
    hsm_src = (ROOT / 'desktop' / 'host_state_machine.py').read_text(encoding='utf-8')
    for name in (
        'restore_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history',
        'set_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy',
        'edit_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_custom',
        'prompt_edit_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_custom',
        'stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_trial_fallback_import_conflict_strategy',
        'set_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_trial_fallback_import_conflict_strategy',
        'import_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_trial_fallback_for_flow',
        'redo_reorder_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs',
        'merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_redo_depth',
    ):
        assert hasattr(HostStateMachineWidget, name), name
    for marker in (
        'isCycleKeySuggestHistoryMenu',
        'isEyedropperHistoryOrderShortcutFixConfirmTrialUndoImportConflictMenu',
        'isDstClearUndoTtlPresetCustomEdit',
        'isDstClearUndoTtlPresetCustomDelete',
        'isJitterSeedRedoClearUndoTtlPresetCustomsReorderRedo',
    ):
        assert marker in hsm_src, marker
    ok('wave85 APIs present')

    s = QSettings('SIEANS', 'VisionDesktop')
    s.setValue('host/alarmFilmCsvDirs', [])
    s.setValue('host/sevPinArcSeizeRecentColors', [])
    s.setValue('host/toastHistCapTipAnim', True)
    s.setValue('host/toastHistCapTipAnimEasing', 'OutCubic')
    s.setValue('host/stalePruneUndoColorScale', 'traffic')
    s.setValue('host/stalePruneUndoColorScaleCompare', 'cool')
    s.setValue('host/stalePruneUndoColorScaleAbLock', False)
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
    host._dst_ttl_preset_custom_edit_no_dialog = True
    app.processEvents()

    # --- 1. pin suggest history submenu / restore ---
    host.clear_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history()
    host.set_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_selected(
        ['Alt+1', 'Alt+2'], persist=False, remember=True)
    host.set_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_selected(
        ['Ctrl+C'], persist=False, remember=True)
    hist = host.list_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history()
    assert len(hist) >= 2, hist
    out = host.restore_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history(
        1, persist=False, apply=False, remember=False)
    assert out.get('restored') is True
    assert out.get('selected') == hist[1].get('keys'), out
    host._swatch_conflict_preview_cycle_key_suggest_menu_smoke = {'action': 'restore_history', 'index': 0, 'apply': False}
    mout = host.show_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_menu(
        persist=False, key='Ctrl+C')
    assert mout.get('via') == 'restore_history'
    assert 'isCycleKeySuggestHistoryMenu' in hsm_src and '清空历史' in hsm_src
    ok('pin建议历史子菜单UI')

    # --- 2. confirm conflict strategy menu ---
    lab = QLabel('')
    host._last_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_depth_lab = lab
    host._stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo = []
    host._confirm_trial_undo_menu_smoke = {'action': 'set_conflict', 'strategy': 'ask', 'persist': False}
    v = host.show_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_menu()
    assert str(v) == 'ask'
    assert host.stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy() == 'ask'
    host._confirm_trial_undo_menu_smoke = {'action': 'set_conflict', 'strategy': 'skip', 'persist': False}
    v2 = host.show_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_menu()
    assert str(v2) == 'skip'
    host._confirm_trial_undo_menu_smoke = {'action': 'get_conflict'}
    g = host.show_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_menu()
    assert str(g) == 'skip'
    assert '导入冲突 ·' in hsm_src and 'isEyedropperHistoryOrderShortcutFixConfirmTrialUndoImportConflictMenu' in hsm_src
    host.set_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy(
        'replace', persist=False)
    ok('导入冲突策略菜单切换')

    # --- 3. DST custom edit/delete ---
    host._toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs = None
    host.add_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_custom(
        4500, '4.5秒', persist=False)
    host.add_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_custom(
        9999, '烟测', persist=False)
    host._dst_clear_undo_ttl_preset_menu_smoke = {
        'action': 'edit_custom', 'old_ms': 9999, 'ms': 9999, 'label': '改名烟测'}
    host.show_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_menu(
        persist=False)
    customs = host.list_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs()
    assert any(str(c.get('label')) == '改名烟测' for c in customs), customs
    host.edit_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_custom(
        4500, 4600, '4.6秒', persist=False)
    customs2 = host.list_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs()
    assert any(int(c.get('ms')) == 4600 and c.get('label') == '4.6秒' for c in customs2), customs2
    assert not any(int(c.get('ms')) == 4500 for c in customs2)
    host._dst_clear_undo_ttl_preset_menu_smoke = {'action': 'delete_custom', 'ms': 9999}
    host.show_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_menu(
        persist=False)
    customs3 = host.list_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs()
    assert not any(int(c.get('ms')) == 9999 for c in customs3)
    assert 'isDstClearUndoTtlPresetCustomEdit' in hsm_src
    ok('DST自定义编辑/删项UI')

    # --- 4. A/B fallback import by flow + conflict ---
    s.setValue('host/stalePruneUndoColorScaleAbMirrorChannelPresetImportConflictSourceTrialFallbackByFlow', '{}')
    s.sync()
    host._stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_trial_fallback_by_flow = None
    host.remember_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_trial_fallback(
        'flow_a', 'team', reason='a')
    host.remember_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_trial_fallback(
        'flow_b', 'local', reason='b')
    payload = {
        'kind': 'sieans.ab_trial_fallback_memory',
        'version': 1,
        'by_flow': {
            'flow_a': {'source': 'remote', 'reason': 'imp'},
            'flow_c': {'source': 'disk', 'reason': 'c'},
        },
    }
    text = json.dumps(payload, ensure_ascii=False)
    host.set_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_trial_fallback_import_conflict_strategy(
        'skip', persist=False)
    skip_out = host.import_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_trial_fallback(
        text, from_clipboard=False, persist=False, conflict='skip')
    assert skip_out.get('reason') == 'conflict_skip', skip_out
    mp = host.load_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_trial_fallback_map()
    assert mp['flow_a']['source'] == 'team'
    sub = host.import_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_trial_fallback(
        text, from_clipboard=False, persist=False, flows=['flow_c'], conflict='merge')
    assert sub.get('ok') is True and sub.get('imported') == 1, sub
    assert sub.get('subset') is True
    mp = host.load_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_trial_fallback_map()
    assert 'flow_c' in mp and mp['flow_a']['source'] == 'team'
    merge_out = host.import_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_trial_fallback(
        text, from_clipboard=False, persist=False, conflict='merge')
    assert merge_out.get('ok') is True and merge_out.get('strategy') == 'merge'
    mp = host.load_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_trial_fallback_map()
    assert mp['flow_a']['source'] == 'remote'
    one = host.import_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_trial_fallback_for_flow(
        'flow_a', text, from_clipboard=False, persist=False, conflict='merge')
    assert one.get('imported') == 1 and one.get('flows') == ['flow_a'], one
    host._ab_trial_fallback_import_conflict_smoke = 'skip'
    ask = host.import_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_trial_fallback(
        text, from_clipboard=False, persist=False, conflict='ask')
    assert ask.get('reason') == 'conflict_skip'
    host._ab_trial_fallback_import_conflict_smoke = None
    ok('A/B回退按流程导入/冲突')

    # --- 5. jitter reorder redo stack ---
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
    mid = [int(c.get('ms')) for c in host.list_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs()]
    assert mid == [9999, 3000, 4500]
    assert host.merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_redo_depth() == 0
    u1 = host.undo_reorder_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs(
        persist=False)
    assert u1.get('undone') is True
    assert [int(c.get('ms')) for c in host.list_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs()] == [3000, 9999, 4500]
    assert host.merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_redo_depth() == 1
    r1 = host.redo_reorder_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs(
        persist=False)
    assert r1.get('redone') is True, r1
    assert [int(c.get('ms')) for c in host.list_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs()] == [9999, 3000, 4500]
    assert host.merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_redo_depth() == 0
    host.undo_reorder_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs(persist=False)
    host.undo_reorder_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs(persist=False)
    assert [int(c.get('ms')) for c in host.list_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs()] == before
    assert host.merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_redo_depth() == 2
    host.redo_reorder_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs(
        persist=False, steps=2)
    assert [int(c.get('ms')) for c in host.list_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs()] == [9999, 3000, 4500]
    host.undo_reorder_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs(persist=False)
    assert host.merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_redo_depth() == 1
    host.reorder_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs(
        [4500, 3000, 9999], persist=False)
    assert host.merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_redo_depth() == 0
    host._jitter_clear_undo_snapshot_menu_smoke = {'action': 'ttl_reorder_undo'}
    # smoke path for redo
    host.undo_reorder_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs(persist=False)
    host._jitter_clear_undo_snapshot_menu_smoke = {'action': 'ttl_reorder_redo'}
    n = host.show_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_snapshot_menu()
    assert int(n) >= 1
    assert 'isJitterSeedRedoClearUndoTtlPresetCustomsReorderRedo' in hsm_src
    ok('jitter排序重做栈')

    print(f'wave85 DONE pass={pass_n} fail={fail_n}')
    return 0 if fail_n == 0 else 1

if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as e:
        bad(f'exception · {e}')
        import traceback; traceback.print_exc()
        print(f'wave85 DONE pass={pass_n} fail={fail_n}')
        raise SystemExit(1)
