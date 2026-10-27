#!/usr/bin/env python3
"""细妆59：pin筛选预设右键/快捷 · 冲突检测一键跳过/清橙 · DST快捷可改绑 · A/B布局导出导入 · jitter撤栈旁标快捷."""
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
        QApplication, QMessageBox, QFileDialog, QColorDialog, QInputDialog, QMenu,
    )
    from PySide6.QtCore import QSettings, Qt
    from PySide6.QtGui import QColor, QDesktopServices
    app = QApplication.instance() or QApplication([])
    QMessageBox.information = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
    QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)
    QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: ('', ''))
    QFileDialog.getOpenFileName = staticmethod(lambda *a, **k: ('', ''))
    QColorDialog.getColor = staticmethod(lambda *a, **k: QColor('#ccddee'))
    QInputDialog.getInt = staticmethod(lambda *a, **k: (4500, True))
    QInputDialog.getText = staticmethod(lambda *a, **k: ('Ctrl+Alt+Shift+U', True))
    QDesktopServices.openUrl = staticmethod(lambda *a, **k: True)
    def _no_exec(self, *a, **k):
        self.setProperty('smokeMenuNoExec', True)
        return None
    QMenu.exec = _no_exec  # type: ignore

    from desktop.host_state_machine import HostStateMachineWidget
    hsm_src = Path(ROOT / 'desktop' / 'host_state_machine.py').read_text(encoding='utf-8')

    for marker in [
        'def show_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_context_menu',
        'isCycleKeySuggestHistoryFilterPresetContextMenu',
        'isCycleKeySuggestHistoryFilterPresetShortcut',
        'def clear_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflicts_badge',
        'confirmTrialUndoImportConflictStrategyShortcutConflictAcked',
        'isUndoEyedropperHistoryOrderShortcutFixConfirmTrialUndoImportConflictStrategyLabMenuSkipConflict',
        'def show_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcuts_rebind_dialog',
        'isDstClearUndoTtlPresetCustomsReorderUndoDepthLabMenuRebind',
        'def export_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout',
        'isAbMirrorChannelPresetImportConflictPreviewLayoutExport',
        'def _on_jitter_reorder_undo_hotkey',
        'isJitterSeedRedoClearUndoTtlPresetCustomsReorderUndoDepthLab',
        'isJitterSeedRedoClearUndoTtlPresetCustomsReorderUndoShortcut',
    ]:
        assert marker in hsm_src, marker
    ok('wave91 APIs present')

    s = QSettings('SieansVision', 'HostStateMachineSmoke91')
    try:
        s.setValue('host/mergeDiffFailHistDropPulsePreviewLoopGapJitterSeedRedoClearUndoTtlPresetCustoms', '[]')
        s.setValue('host/toastCurvePngDatetimeTzCityDstCalendarYearRangeRecentApplyAllUndoClearUndoTtlPresetCustoms', '[]')
        s.setValue('host/mergeDiffFailHistDropSnapGuideRecentMaxPinAvoidCompareBarUndoSwatchConflictPreviewCycleKeySuggestHistoryFilterPresets', '[]')
        s.setValue('host/stalePruneUndoEyedropperHistoryOrderShortcutFixConfirmTrialUndoImportConflictStrategyShortcutConflictsAcked', False)
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
    host._jitter_reorder_redo_lab_menu_no_exec = True
    host._dst_reorder_depth_lab_menu_no_exec = True
    host._ics_strategy_shortcut_rebind_no_dialog = True
    host._cycle_key_suggest_history_filter_presets_export_no_dialog = True
    host._cycle_key_suggest_history_filter_presets_import_no_dialog = True
    host._cycle_key_suggest_history_filter_presets_reorder_no_dialog = True
    host._jitter_reorder_redo_shortcut_rebind_no_dialog = True
    host._ics_strategy_shortcut_conflict_quiet = True
    host._cycle_key_suggest_history_filter_presets_menu_no_exec = True
    host._dst_reorder_shortcuts_rebind_no_dialog = True
    host._ab_trial_fallback_import_conflict_preview_layout_export_no_dialog = True
    host._ab_trial_fallback_import_conflict_preview_layout_import_no_dialog = True
    app.processEvents()

    # --- 1. filter presets context/shortcut ---
    try:
        host.clear_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets(persist=True)
        for q in ('X', 'Y'):
            host.set_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query(q, persist=True)
        sk = host.merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_shortcut()
        assert 'P' in sk or 'Ctrl' in sk, sk
        host.set_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_shortcut(
            'Ctrl+Alt+Shift+P', persist=False, rebind=True)
        sk2 = host.merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_shortcut()
        assert 'Shift' in sk2 and 'P' in sk2, sk2
        shown = host.show_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_context_menu(persist=True)
        assert shown is True
        smoke = host._last_cycle_key_suggest_history_filter_presets_menu_smoke
        assert smoke and 'reorder' in smoke.get('actions', []), smoke
        assert smoke.get('presets')[:2] == ['Y', 'X'] or 'Y' in smoke.get('presets', []), smoke
        ok_hot = host._on_cycle_key_suggest_history_filter_presets_hotkey()
        assert ok_hot is True
        host.set_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_shortcut(
            'Ctrl+Alt+P', persist=False, rebind=True)
        ok('1 filter presets context/shortcut')
    except Exception as e:
        bad(f'1 filter presets context/shortcut: {e}')

    # --- 2. conflict skip / clear orange ---
    try:
        host.resume_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflicts_badge(persist=False)
        # force a conflicting key so tip has conflict
        host.set_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut(
            'Ctrl+S', persist=False, rebind=True)
        cf = host.format_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflicts()
        assert cf and 'Ctrl+S' in cf, cf
        assert host.stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflicts_acked() is False
        host.refresh_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_lab()
        lab = getattr(host, '_last_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_lab', None)
        if lab is not None:
            tip = str(lab.toolTip() or '')
            assert '⚠' in tip or 'Ctrl+S' in tip, tip
            ss = str(lab.styleSheet() or '')
            assert '#e6a23c' in ss, ss
        host.clear_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflicts_badge(persist=False)
        assert host.stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflicts_acked() is True
        if lab is not None:
            tip2 = str(lab.toolTip() or '')
            assert '已跳过' in tip2, tip2
            ss2 = str(lab.styleSheet() or '')
            assert '#e6a23c' not in ss2 and '#7ec8e3' in ss2, ss2
        host.resume_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflicts_badge(persist=False)
        host.set_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut(
            'Ctrl+Alt+I', persist=False, rebind=True)
        ok('2 conflict skip/clear orange')
    except Exception as e:
        bad(f'2 conflict skip/clear orange: {e}')

    # --- 3. DST rebind ---
    try:
        host._dst_reorder_shortcuts_rebind_smoke = ('Ctrl+Alt+Shift+U', 'Ctrl+Alt+Shift+D')
        out = host.show_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcuts_rebind_dialog()
        assert isinstance(out, tuple) and len(out) == 2, out
        assert 'Shift' in out[0] and 'U' in out[0], out
        assert 'Shift' in out[1] and 'D' in out[1], out
        # menu smoke includes rebind
        lab_u = getattr(host, '_last_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab', None)
        if lab_u is not None:
            from PySide6.QtGui import QMouseEvent
            from PySide6.QtCore import QEvent, QPoint
            ev = QMouseEvent(
                QEvent.Type.MouseButtonPress, QPoint(2, 2), QPoint(2, 2), QPoint(2, 2),
                Qt.MouseButton.RightButton, Qt.MouseButton.RightButton, Qt.KeyboardModifier.NoModifier)
            try:
                lab_u.mousePressEvent(ev)
            except Exception:
                pass
            smoke = getattr(host, '_last_dst_reorder_undo_lab_menu_smoke', None)
            if smoke:
                assert 'rebind' in (smoke.get('actions') or []), smoke
        tip_u = str(lab_u.toolTip() if lab_u is not None else '')
        host._refresh_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_depth_ui()
        lab_u = getattr(host, '_last_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab', None)
        if lab_u is not None:
            assert '改绑' in str(lab_u.toolTip() or '') or 'Ctrl' in str(lab_u.toolTip() or '')
        host.set_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcuts(
            'Ctrl+Alt+U', 'Ctrl+Alt+D', persist=False, rebind=True)
        ok('3 DST shortcuts rebind')
    except Exception as e:
        bad(f'3 DST shortcuts rebind: {e}')

    # --- 4. AB layout export/import ---
    try:
        host.set_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout({
            'columns': ['status', 'incoming'],
            'dialog_w': 480,
            'filter': 'new',
            'sort': 'incoming',
            'reverse': True,
        }, persist=True)
        with tempfile.TemporaryDirectory() as td:
            p = str(Path(td) / 'lay.json')
            host._ab_trial_fallback_import_conflict_preview_layout_export_smoke_path = p
            outp = host.export_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout()
            assert outp == p and Path(p).is_file(), outp
            data = json.loads(Path(p).read_text(encoding='utf-8'))
            assert data.get('filter') == 'new' and data.get('dialog_w') == 480, data
            # change then import back
            host.set_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout({
                'columns': ['flow'], 'filter': 'all', 'dialog_w': 300,
            }, persist=True)
            host._ab_trial_fallback_import_conflict_preview_layout_import_smoke_path = p
            imp = host.import_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout(persist=True)
            assert imp.get('filter') == 'new' and imp.get('dialog_w') == 480, imp
        assert 'isAbMirrorChannelPresetImportConflictPreviewLayoutExport' in hsm_src
        ok('4 AB layout export/import')
    except Exception as e:
        bad(f'4 AB layout export/import: {e}')

    # --- 5. jitter undo shortcut + lab ---
    try:
        from PySide6.QtWidgets import QWidget
        _keep = getattr(host, '_smoke_wave91_keep_widgets', None)
        if _keep is None:
            _keep = []
            host._smoke_wave91_keep_widgets = _keep
        _pw = QWidget(host)
        _keep.append(_pw)
        try:
            host._make_undo_color_scale_eyedropper_history_row(_pw, which='hi')
        except Exception:
            pass
        uk = host.merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_shortcut()
        assert 'K' in uk or 'Ctrl' in uk, uk
        host.set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_shortcut(
            'Ctrl+Alt+Shift+K', persist=False, rebind=True)
        uk2 = host.merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_shortcut()
        assert 'Shift' in uk2 and 'K' in uk2, uk2
        lab = getattr(host, '_last_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab', None)
        assert lab is not None, 'undo depth lab missing'
        tip = str(lab.toolTip() or '')
        assert '撤栈' in tip and ('Ctrl' in tip or 'K' in tip), tip
        # seed reorder so undo does something
        try:
            cur = host.list_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs()
            if len(cur) < 2:
                for name, ms in (('j1', 1000), ('j2', 2000)):
                    try:
                        host.add_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_custom(name, ms, persist=False)
                    except Exception:
                        pass
                cur = host.list_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs()
            if cur:
                host.reorder_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs(
                    list(reversed(cur)), persist=False)
        except Exception:
            pass
        ok_u = host._on_jitter_reorder_undo_hotkey()
        assert isinstance(ok_u, bool)
        host.set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_shortcut(
            'Ctrl+Alt+K', persist=False, rebind=True)
        # detect includes jitter撤
        cf_k = host.detect_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflicts('Ctrl+Alt+K')
        assert any('jitter撤' in str(c.get('reason', '')) for c in cf_k), cf_k
        ok('5 jitter undo shortcut/lab')
    except Exception as e:
        bad(f'5 jitter undo shortcut/lab: {e}')

    print(f'\nRESULT: {pass_n} passed, {fail_n} failed')
    host.close()
    return 0 if fail_n == 0 else 1

if __name__ == '__main__':
    raise SystemExit(main())
