#!/usr/bin/env python3
"""细妆55：pin建议历史筛选高亮/多字段 · 冲突策略指示条右键菜单 · DST自定义排序撤/重做栈 · A/B冲突预览表复制/导出 · jitter重做旁标 chrome."""
from __future__ import annotations
import json
import sys
import tempfile
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
        QApplication, QMessageBox, QFileDialog, QColorDialog, QInputDialog, QLabel, QMenu,
    )
    from PySide6.QtCore import QSettings, Qt, QPoint
    from PySide6.QtGui import QColor, QDesktopServices
    app = QApplication.instance() or QApplication([])
    QMessageBox.information = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
    QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)
    QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: ('', ''))
    QFileDialog.getOpenFileName = staticmethod(lambda *a, **k: ('', ''))
    QColorDialog.getColor = staticmethod(lambda *a, **k: QColor('#ccddee'))
    QInputDialog.getInt = staticmethod(lambda *a, **k: (4500, True))
    QInputDialog.getText = staticmethod(lambda *a, **k: ('Alt', True))
    QDesktopServices.openUrl = staticmethod(lambda *a, **k: True)
    _orig_exec = QMenu.exec
    def _no_exec(self, *a, **k):
        self.setProperty('smokeMenuNoExec', True)
        return None
    QMenu.exec = _no_exec  # type: ignore

    from desktop.host_state_machine import HostStateMachineWidget
    hsm_src = Path(ROOT / 'desktop' / 'host_state_machine.py').read_text(encoding='utf-8')

    for marker in [
        'def highlight_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history',
        'isUndoEyedropperHistoryOrderShortcutFixConfirmTrialUndoImportConflictStrategyLabMenu',
        'def undo_reorder_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs',
        'def redo_reorder_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs',
        'def copy_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_table',
        'def export_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_table',
        'isJitterSeedRedoClearUndoTtlPresetCustomsReorderRedoDepthLab',
    ]:
        assert marker in hsm_src, marker
    ok('wave87 APIs present')

    s = QSettings('SieansVision', 'HostStateMachineSmoke87')
    try:
        s.setValue('host/mergeDiffFailHistDropPulsePreviewLoopGapJitterSeedRedoClearUndoTtlPresetCustoms', '[]')
        s.setValue('host/toastCurvePngDatetimeTzCityDstCalendarYearRangeRecentApplyAllUndoClearUndoTtlPresetCustoms', '[]')
        s.sync()
    except Exception:
        pass

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
    host._dst_ttl_preset_customs_reorder_no_dialog = True
    host._ab_trial_fallback_import_conflict_preview_no_dialog = True
    host._confirm_trial_undo_ics_lab_menu_no_exec = True
    app.processEvents()

    # --- 1. pin suggest history filter highlight / multi-field ---
    host.clear_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history()
    host.set_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query('', persist=False)
    host.set_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_selected(
        ['Alt+1', 'Alt+2'], persist=False, remember=True)
    host.set_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_selected(
        ['Ctrl+C'], persist=False, remember=True)
    host.set_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_selected(
        ['Alt+9'], persist=False, remember=True)
    # inject ISO ts for multi-field (remember() stores unix int)
    rows = host.list_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history()
    for r in rows:
        if isinstance(r, dict):
            r['ts'] = '2026-10-28T05:00:00'
    host._merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history = list(rows)

    filt = host.filter_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history('alt')
    assert len(filt) >= 2, filt
    assert any(isinstance(r.get('_matches'), list) and r.get('_matches') for r in filt), filt
    assert any(isinstance(r.get('_highlight'), dict) for r in filt), filt
    hl = host.highlight_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history(filt[0], 'alt')
    assert isinstance(hl, str) and len(hl) > 0, hl
    assert '「' in hl or 'keys' in hl or 'label' in hl, hl
    filt_ts = host.filter_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history('2026')
    assert len(filt_ts) >= 1, filt_ts
    assert any('ts' in (r.get('_matches') or []) for r in filt_ts), filt_ts
    assert 'isCycleKeySuggestHistoryHighlight' in hsm_src
    assert '多字段' in hsm_src
    ok('pin建议历史筛选高亮/多字段')

    # --- 2. ICS right-click menu ---
    lab = QLabel('')
    host._last_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_lab = lab
    host.set_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy('ask', persist=False)
    assert lab.text() == '询', lab.text()
    # build real chrome row for right-click handler
    try:
        host._make_undo_color_scale_eyedropper_history_row(host, which='hi')
    except Exception:
        pass
    app.processEvents()
    real = None
    for w in host.findChildren(QLabel):
        if w.objectName() == 'hostUndoEyedropperHistoryOrderShortcutFixConfirmTrialUndoImportConflictStrategyLab':
            real = w
            break
    if real is None:
        real = getattr(host, '_last_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_lab', None)
    assert real is not None, 'ICS chrome lab missing'
    assert '右击菜单' in (real.toolTip() or '') or 'isUndoEyedropperHistoryOrderShortcutFixConfirmTrialUndoImportConflictStrategyLabMenu' in hsm_src
    class _ER:
        def button(self):
            return Qt.MouseButton.RightButton
        def pos(self):
            return QPoint(1, 1)
    host._confirm_trial_undo_ics_lab_menu_no_exec = True
    try:
        real.mousePressEvent(_ER())
    except Exception as e:
        raise AssertionError(f'right click failed: {e}')
    smoke_m = getattr(host, '_last_confirm_trial_undo_ics_lab_menu_smoke', None) or {}
    assert smoke_m.get('via') == 'right_click_menu', smoke_m
    assert 'merge' in (smoke_m.get('choices') or []), smoke_m
    assert 'isUndoEyedropperHistoryOrderShortcutFixConfirmTrialUndoImportConflictStrategyLabMenu' in hsm_src
    assert 'isUndoEyedropperHistoryOrderShortcutFixConfirmTrialUndoImportConflictStrategyLabMenuItem' in hsm_src
    # left click cycles
    before = host.stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy()
    class _EL:
        def button(self):
            return Qt.MouseButton.LeftButton
        def pos(self):
            return QPoint(1, 1)
    real.mousePressEvent(_EL())
    after = host.stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy()
    assert after != before, (before, after)
    ok('冲突策略指示条右键菜单')

    # --- 3. DST undo/redo stack ---
    host._toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs = []
    host._toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_undo = []
    host._toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_redo = []
    host.add_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_custom(1000, '一秒', persist=False)
    host.add_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_custom(2000, '两秒', persist=False)
    host.add_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_custom(3000, '三秒', persist=False)
    reordered = host.reorder_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs(
        [3000, 1000, 2000], persist=False)
    assert [c['ms'] for c in reordered] == [3000, 1000, 2000], reordered
    assert host.toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_undo_depth() >= 1
    u = host.undo_reorder_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs(persist=False)
    assert u.get('undone'), u
    ms2 = [c['ms'] for c in host.list_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs()]
    assert ms2 == [1000, 2000, 3000], ms2
    assert host.toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_redo_depth() >= 1
    r = host.redo_reorder_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs(persist=False)
    assert r.get('redone'), r
    ms3 = [c['ms'] for c in host.list_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs()]
    assert ms3 == [3000, 1000, 2000], ms3
    # re-undo to refill redo stack, then clear
    host.undo_reorder_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs(persist=False)
    assert host.toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_redo_depth() >= 1
    cleared = host.clear_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_redo()
    assert cleared >= 1
    assert host.toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_redo_depth() == 0
    assert 'isDstClearUndoTtlPresetCustomsReorderUndo' in hsm_src
    assert 'isDstClearUndoTtlPresetCustomsReorderRedo' in hsm_src
    assert 'isDstClearUndoTtlPresetCustomsReorderClearRedo' in hsm_src
    ok('DST自定义排序撤/重做栈')

    # --- 4. A/B conflict preview copy/export ---
    host.persist_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_source_trial_fallback_map(
        {'team': 'local', 'remote': 'file'})
    payload = json.dumps({
        'kind': 'sieans.ab_trial_fallback_memory',
        'by_flow': {'team': 'clipboard', 'remote': 'file', 'disk': 'disk'},
    }, ensure_ascii=False)
    body = host.format_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_table(
        payload, from_clipboard=False)
    assert 'status' in body and 'flow' in body, body[:200]
    assert body.count('\n') >= 3, body
    copied = host.copy_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_table(
        payload, from_clipboard=False)
    assert copied.get('chars', 0) > 0, copied
    with tempfile.TemporaryDirectory() as td:
        path = str(Path(td) / 'ab_prev.tsv')
        host._ab_trial_fallback_import_conflict_preview_no_dialog = True
        host._ab_trial_fallback_import_conflict_preview_export_smoke = {'path': path}
        exported = host.export_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_table(
            path, payload, from_clipboard=False)
        assert exported.get('exported'), exported
        assert Path(path).exists() and Path(path).stat().st_size > 0
        assert Path(path).read_text(encoding='utf-8').startswith('status')
    assert 'isAbMirrorChannelPresetImportConflictPreviewCopy' in hsm_src
    assert 'isAbMirrorChannelPresetImportConflictPreviewExport' in hsm_src
    ok('A/B冲突预览表复制/导出')

    # --- 5. jitter redo chrome ---
    host._merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs = [
        {'ms': 500, 'label': 'a', 'custom': True},
        {'ms': 1500, 'label': 'b', 'custom': True},
    ]
    host._merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo = []
    host._merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_redo = []
    host.reorder_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs(
        [1500, 500], persist=False, record_undo=True)
    host.undo_reorder_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs(persist=False)
    rd = host.merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_redo_depth()
    assert rd >= 1, rd
    d = host._refresh_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_redo_depth_ui()
    assert d >= 1, d
    lab_jrd = None
    for w in host.findChildren(QLabel):
        if w.objectName() == 'hostJitterSeedRedoClearUndoTtlPresetCustomsReorderRedoDepthLab':
            lab_jrd = w
            break
    assert lab_jrd is not None, 'jitter redo depth lab missing'
    assert lab_jrd.property('isJitterSeedRedoClearUndoTtlPresetCustomsReorderRedoDepthLab') in (True, 'true', 1)
    # refresh should update text
    host._refresh_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_redo_depth_ui(rd)
    assert lab_jrd.text() == str(rd), lab_jrd.text()
    cleared = host.clear_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_redo()
    assert cleared >= 1
    assert host.merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_redo_depth() == 0
    assert lab_jrd.text() == '', lab_jrd.text()
    try:
        s.setValue('host/mergeDiffFailHistDropPulsePreviewLoopGapJitterSeedRedoClearUndoTtlPresetCustoms', '[]')
        s.setValue('host/toastCurvePngDatetimeTzCityDstCalendarYearRangeRecentApplyAllUndoClearUndoTtlPresetCustoms', '[]')
        s.sync()
    except Exception:
        pass
    assert '点击重做 · 右击清栈' in hsm_src
    ok('jitter重做旁标 chrome')

    print(f'\nwave87: {pass_n} PASS / {fail_n} FAIL', flush=True)
    return 0 if fail_n == 0 else 1

if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as e:
        import traceback
        traceback.print_exc()
        print('FAIL: unhandled', e, flush=True)
        raise SystemExit(2)
