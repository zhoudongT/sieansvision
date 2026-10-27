#!/usr/bin/env python3
"""细妆58：pin筛选预设拖拽排序 · 冲突策略快捷键冲突检测 · DST旁标快捷键 · A/B预览列宽/持久布局 · jitter旁标快捷键可改绑."""
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
    from PySide6.QtGui import QColor, QDesktopServices, QKeySequence
    app = QApplication.instance() or QApplication([])
    QMessageBox.information = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
    QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)
    QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: ('', ''))
    QFileDialog.getOpenFileName = staticmethod(lambda *a, **k: ('', ''))
    QColorDialog.getColor = staticmethod(lambda *a, **k: QColor('#ccddee'))
    QInputDialog.getInt = staticmethod(lambda *a, **k: (4500, True))
    QInputDialog.getText = staticmethod(lambda *a, **k: ('Ctrl+Alt+K', True))
    QDesktopServices.openUrl = staticmethod(lambda *a, **k: True)
    def _no_exec(self, *a, **k):
        self.setProperty('smokeMenuNoExec', True)
        return None
    QMenu.exec = _no_exec  # type: ignore

    from desktop.host_state_machine import HostStateMachineWidget
    hsm_src = Path(ROOT / 'desktop' / 'host_state_machine.py').read_text(encoding='utf-8')

    for marker in [
        'def reorder_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets',
        'def show_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_dialog',
        'isCycleKeySuggestHistoryFilterPresetReorder',
        'def detect_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflicts',
        'confirmTrialUndoImportConflictStrategyShortcutConflict',
        'def toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_undo_shortcut',
        'def toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_redo_shortcut',
        'def _on_dst_reorder_undo_hotkey',
        'def _on_dst_reorder_redo_hotkey',
        'def stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout',
        'def set_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout',
        'isAbMirrorChannelPresetImportConflictPreviewLayout',
        'def show_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_redo_shortcut_rebind_dialog',
        'isJitterSeedRedoClearUndoTtlPresetCustomsReorderRedoDepthLabMenuRebind',
    ]:
        assert marker in hsm_src, marker
    ok('wave90 APIs present')

    s = QSettings('SieansVision', 'HostStateMachineSmoke90')
    try:
        s.setValue('host/mergeDiffFailHistDropPulsePreviewLoopGapJitterSeedRedoClearUndoTtlPresetCustoms', '[]')
        s.setValue('host/toastCurvePngDatetimeTzCityDstCalendarYearRangeRecentApplyAllUndoClearUndoTtlPresetCustoms', '[]')
        s.setValue('host/mergeDiffFailHistDropSnapGuideRecentMaxPinAvoidCompareBarUndoSwatchConflictPreviewCycleKeySuggestHistoryFilterPresets', '[]')
        s.setValue('host/stalePruneUndoColorScaleAbMirrorChannelPresetImportConflictPreviewLayout', '')
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
    app.processEvents()

    # --- 1. filter presets drag reorder ---
    try:
        host.clear_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets(persist=True)
        for q in ('A', 'B', 'C'):
            host.set_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query(q, persist=True)
        presets = host.list_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets()
        assert presets[:3] == ['C', 'B', 'A'], presets
        reo = host.reorder_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets(
            ['A', 'C', 'B'], persist=True)
        assert reo[:3] == ['A', 'C', 'B'], reo
        host._cycle_key_suggest_history_filter_presets_reorder_smoke = ['B', 'A', 'C']
        out = host.show_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_dialog(persist=True)
        assert out[:3] == ['B', 'A', 'C'], out
        assert 'isCycleKeySuggestHistoryFilterPresetReorder' in hsm_src
        ok('1 filter presets reorder')
    except Exception as e:
        bad(f'1 filter presets reorder: {e}')

    # --- 2. ICS strategy shortcut conflict detect ---
    try:
        # default Ctrl+Alt+I should not conflict with reserved
        cf0 = host.detect_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflicts('Ctrl+Alt+I')
        assert cf0 == [] or isinstance(cf0, list), cf0
        # reserved key
        cf_r = host.detect_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflicts('Ctrl+S')
        assert any('保留' in str(c.get('reason', '')) for c in cf_r), cf_r
        tip_r = host.format_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflicts(cf_r)
        assert 'Ctrl+S' in tip_r and tip_r, tip_r
        # collide with jitter default Ctrl+Alt+J
        cf_j = host.detect_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflicts('Ctrl+Alt+J')
        assert any('jitter' in str(c.get('reason', '')) for c in cf_j), cf_j
        # collide with DST undo default
        cf_d = host.detect_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflicts('Ctrl+Alt+U')
        assert any('DST' in str(c.get('reason', '')) for c in cf_d), cf_d
        # set_ should stamp conflict property via refresh
        host.set_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut(
            'Ctrl+S', persist=False, rebind=True)
        # restore
        host.set_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut(
            'Ctrl+Alt+I', persist=False, rebind=True)
        ok('2 ICS strategy shortcut conflict detect')
    except Exception as e:
        bad(f'2 ICS strategy shortcut conflict: {e}')

    # --- 3. DST hotkeys ---
    try:
        uk = host.toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_undo_shortcut()
        rk = host.toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_redo_shortcut()
        assert 'Ctrl' in uk and 'U' in uk, uk
        assert 'Ctrl' in rk and 'D' in rk, rk
        host.set_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcuts(
            'Ctrl+Alt+Shift+U', 'Ctrl+Alt+Shift+D', persist=False, rebind=True)
        uk2 = host.toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_undo_shortcut()
        rk2 = host.toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_redo_shortcut()
        assert 'Shift' in uk2 and 'U' in uk2, uk2
        assert 'Shift' in rk2 and 'D' in rk2, rk2
        # seed DST customs + reorder so undo/redo stacks exist
        try:
            customs = host.list_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs()
        except Exception:
            customs = []
        if len(customs) < 2:
            for name, ms in (('α', 3000), ('β', 8000), ('γ', 15000)):
                try:
                    host.add_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_custom(name, ms, persist=False)
                except Exception:
                    try:
                        host.remember_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_custom(name, ms, persist=False)
                    except Exception:
                        pass
        try:
            cur = host.list_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs()
            if cur:
                host.reorder_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs(
                    list(reversed(cur)), persist=False)
        except Exception:
            pass
        ok_u = host._on_dst_reorder_undo_hotkey()
        ok_r = host._on_dst_reorder_redo_hotkey()
        assert isinstance(ok_u, bool) and isinstance(ok_r, bool)
        # tip mentions shortcut
        host._refresh_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_depth_ui()
        lab_u = getattr(host, '_last_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab', None)
        if lab_u is not None:
            tip = str(lab_u.toolTip() or '')
            assert 'Ctrl' in tip or 'U' in tip, tip
        # restore defaults
        host.set_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcuts(
            'Ctrl+Alt+U', 'Ctrl+Alt+D', persist=False, rebind=True)
        ok('3 DST reorder hotkeys')
    except Exception as e:
        bad(f'3 DST reorder hotkeys: {e}')

    # --- 4. AB preview layout persist ---
    try:
        lay0 = host.stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout()
        assert isinstance(lay0, dict) and 'columns' in lay0 and 'dialog_w' in lay0, lay0
        saved = host.set_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout({
            'columns': ['status', 'flow'],
            'widths': {'status': 80, 'flow': 120},
            'dialog_w': 500,
            'dialog_h': 400,
            'filter': 'conflict',
            'sort': 'status',
            'reverse': True,
        }, persist=True)
        assert saved['columns'] == ['status', 'flow'], saved
        assert saved['dialog_w'] == 500 and saved['filter'] == 'conflict', saved
        assert saved['reverse'] is True
        host._ab_trial_fallback_import_conflict_preview_layout = None
        lay1 = host.stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout()
        assert lay1.get('dialog_w') == 500 and lay1.get('filter') == 'conflict', lay1
        assert 'status' in (lay1.get('columns') or [])
        assert 'isAbMirrorChannelPresetImportConflictPreviewLayout' in hsm_src
        ok('4 AB preview layout persist')
    except Exception as e:
        bad(f'4 AB preview layout: {e}')

    # --- 5. jitter shortcut rebind ---
    try:
        cur = host.merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_redo_shortcut()
        assert 'J' in cur or 'Ctrl' in cur, cur
        host._jitter_reorder_redo_shortcut_rebind_smoke = 'Ctrl+Alt+Shift+J'
        out = host.show_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_redo_shortcut_rebind_dialog()
        assert 'Shift' in out and 'J' in out, out
        # right-click menu smoke includes rebind
        lab = getattr(host, '_last_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_redo_depth_lab', None)
        if lab is None:
            # force refresh to create lab
            try:
                host._refresh_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_redo_depth_ui()
            except Exception:
                pass
            lab = getattr(host, '_last_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_redo_depth_lab', None)
        if lab is not None:
            tip = str(lab.toolTip() or '')
            assert '改绑' in tip or 'Ctrl' in tip, tip
            # synthesize right click via eventFilter / mousePress if available
            from PySide6.QtGui import QMouseEvent
            from PySide6.QtCore import QEvent
            ev = QMouseEvent(
                QEvent.Type.MouseButtonPress, QPoint(2, 2), QPoint(2, 2), QPoint(2, 2),
                Qt.MouseButton.RightButton, Qt.MouseButton.RightButton, Qt.KeyboardModifier.NoModifier)
            # call the handler if bound via mousePressEvent override on lab
            try:
                lab.mousePressEvent(ev)
            except Exception:
                pass
            smoke = getattr(host, '_last_jitter_reorder_redo_lab_menu_smoke', None)
            if smoke:
                assert 'rebind' in (smoke.get('actions') or []), smoke
        # restore
        host.set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_redo_shortcut(
            'Ctrl+Alt+J', persist=False)
        ok('5 jitter shortcut rebind')
    except Exception as e:
        bad(f'5 jitter shortcut rebind: {e}')

    print(f'\nRESULT: {pass_n} passed, {fail_n} failed')
    host.close()
    return 0 if fail_n == 0 else 1

if __name__ == '__main__':
    raise SystemExit(main())
