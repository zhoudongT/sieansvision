#!/usr/bin/env python3
"""细妆62：pin角标频率预设档/导出 · 忽略名单按角色分组 · DST冲突历史 · A/B槽位拖拽排序/默认槽 · jitter长按时长可配/旁标闪."""
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

def main() -> int:
    hsm_src = (ROOT / 'desktop' / 'host_state_machine.py').read_text(encoding='utf-8')
    markers = [
        'def list_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_freq_presets',
        'def apply_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_freq_preset',
        'def export_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_freq',
        'def list_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role',
        'def add_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_role',
        'def list_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history',
        'def remember_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history',
        'def reorder_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_slots',
        'def set_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_default_slot',
        'def show_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_long_press_ms_dialog',
        'def flash_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab',
        'isCycleKeySuggestHistoryFilterPresetsReorderBadgeMenuFreqPresets',
        'isAbMirrorChannelPresetImportConflictPreviewLayoutSlotsDialogDefault',
        'isJitterSeedRedoClearUndoTtlPresetCustomsReorderUndoDepthLabMenuLongPress',
    ]
    try:
        for m in markers:
            assert m in hsm_src, m
        ok('wave94 APIs present')
    except Exception as e:
        bad(f'wave94 APIs present: {e}')
        print(f'\nRESULT: {pass_n} passed, {fail_n} failed')
        return 1

    from PySide6.QtWidgets import QApplication, QMessageBox, QFileDialog, QInputDialog, QMenu, QWidget
    app = QApplication.instance() or QApplication([])
    QMessageBox.information = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
    QMessageBox.warning = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
    QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: ('', ''))
    QFileDialog.getOpenFileName = staticmethod(lambda *a, **k: ('', ''))
    QInputDialog.getText = staticmethod(lambda *a, **k: ('x', True))
    QMenu.exec = lambda self, *a, **k: None

    from desktop.host_state_machine import HostStateMachineWidget
    host = HostStateMachineWidget(compact=True)
    host.show()
    app.processEvents()

    host._cycle_key_suggest_history_filter_presets_reorder_badge_menu_no_exec = True
    host._cycle_key_suggest_history_filter_presets_reorder_badge_freq_export_no_dialog = True
    host._cycle_key_suggest_history_filter_presets_reorder_badge_freq_import_no_dialog = True
    host._ics_strategy_shortcut_conflict_ignore_menu_no_exec = True
    host._ics_strategy_shortcut_conflict_quiet = True
    host._dst_reorder_shortcut_conflict_quiet = True
    host._ab_trial_fallback_import_conflict_preview_layout_slots_dialog_no_exec = True
    host._jitter_reorder_undo_lab_menu_no_exec = True
    host._jitter_reorder_undo_long_press_ms_no_dialog = True

    # --- 1 freq presets / export ---
    try:
        host.set_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_freq_presets(
            [{'name': '快', 'ms': 400}, {'name': '标准', 'ms': 900}, {'name': '慢', 'ms': 1800}], persist=True)
        presets = host.list_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_freq_presets()
        assert any(p.get('name') == '快' for p in presets), presets
        v = host.apply_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_freq_preset('慢', persist=True)
        assert v == 1800, v
        import json, tempfile
        with tempfile.TemporaryDirectory() as td:
            p = str(Path(td) / 'freq.json')
            host._cycle_key_suggest_history_filter_presets_reorder_badge_freq_export_smoke_path = p
            assert host.export_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_freq(p) == p
            data = json.loads(Path(p).read_text(encoding='utf-8'))
            assert data.get('freq_ms') == 1800 and data.get('presets'), data
            host.set_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_freq_ms(900, persist=True)
            host._cycle_key_suggest_history_filter_presets_reorder_badge_freq_import_smoke_path = p
            imp = host.import_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_freq(p, persist=True)
            assert int(imp.get('freq_ms') or 0) == 1800, imp
        assert host.show_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_context_menu() is True
        smoke = getattr(host, '_last_cycle_key_suggest_history_filter_presets_reorder_badge_menu_smoke', {})
        assert 'presets' in smoke.get('actions', []) and 'export' in smoke.get('actions', []), smoke
        ok('1 badge freq presets/export')
    except Exception as e:
        bad(f'1 badge freq presets/export: {e}')

    # --- 2 ignore by role ---
    try:
        host.clear_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore(persist=True)
        host.set_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role({}, persist=True)
        host.add_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_role('Ctrl+S', 'reserved', persist=True)
        host.add_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_role('Ctrl+Alt+K', 'jitter', persist=True)
        by = host.list_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role()
        assert 'Ctrl+S' in by.get('reserved', []) and 'Ctrl+Alt+K' in by.get('jitter', []), by
        flat = host.list_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore()
        assert 'Ctrl+S' in flat and 'Ctrl+Alt+K' in flat, flat
        host.remove_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_role('Ctrl+S', 'reserved', persist=True)
        by2 = host.list_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_by_role()
        assert 'Ctrl+S' not in by2.get('reserved', []), by2
        assert host.show_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_menu() is True
        ms = getattr(host, '_last_ics_strategy_shortcut_conflict_ignore_menu_smoke', {})
        assert 'by_role' in ms.get('actions', []) and isinstance(ms.get('by_role'), dict), ms
        ok('2 ignore by role')
    except Exception as e:
        bad(f'2 ignore by role: {e}')

    # --- 3 DST conflict history ---
    try:
        host.clear_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history(persist=True)
        assert host.list_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history() == []
        cf = host.detect_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflicts('Ctrl+S', which='undo')
        assert cf, cf
        hist = host.list_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history()
        assert hist and hist[0].get('key') == 'Ctrl+S' and hist[0].get('which') == 'undo', hist
        assert hist[0].get('reasons'), hist
        host.clear_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history(persist=True)
        assert host.list_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflict_history() == []
        ok('3 DST conflict history')
    except Exception as e:
        bad(f'3 DST conflict history: {e}')

    # --- 4 AB slots reorder / default ---
    try:
        host._ab_trial_fallback_import_conflict_preview_layout_slots = []
        try:
            host._host_settings().setValue(
                'host/stalePruneUndoColorScaleAbMirrorChannelPresetImportConflictPreviewLayoutSlots', '[]')
        except Exception:
            pass
        host.save_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_slot(
            '甲', {'dialog_w': 401}, persist=True)
        host.save_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_slot(
            '乙', {'dialog_w': 402}, persist=True)
        # save prepends, so order may be 乙,甲
        reo = host.reorder_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_slots(['甲', '乙'], persist=True)
        names = [s.get('name') for s in reo]
        assert names[:2] == ['甲', '乙'], names
        assert host.set_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_default_slot('甲', persist=True, apply=False) == '甲'
        assert host.stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_default_slot() == '甲'
        assert host.show_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_slots_dialog() is True
        ds = getattr(host, '_last_ab_trial_fallback_import_conflict_preview_layout_slots_dialog_smoke', {})
        assert 'reorder' in ds.get('actions', []) and 'default' in ds.get('actions', []) and ds.get('default') == '甲', ds
        assert 'InternalMove' in hsm_src or 'DragDropMode.InternalMove' in hsm_src
        ok('4 AB slots reorder/default')
    except Exception as e:
        bad(f'4 AB slots reorder/default: {e}')

    # --- 5 jitter long-press config / flash ---
    try:
        _keep = []
        host._smoke_wave94_keep = _keep
        _pw = QWidget(host); _keep.append(_pw)
        try:
            host._make_undo_color_scale_eyedropper_history_row(_pw, which='hi')
        except Exception:
            pass
        lab = getattr(host, '_last_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab', None)
        assert lab is not None, 'lab missing'
        host._jitter_reorder_undo_long_press_ms_smoke = 900
        out = host.show_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_long_press_ms_dialog()
        assert out == 900, out
        assert host.merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_long_press_ms() == 900
        host._refresh_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_ui(1)
        tip = lab.toolTip() or ''
        assert '900ms' in tip or '长按' in tip, tip
        assert host.flash_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab(ms=200) is True
        assert getattr(host, '_last_jitter_reorder_undo_depth_lab_flash', False) is True
        # menu smoke includes long_press_ms
        class _E:
            def button(self):
                from PySide6.QtCore import Qt
                return Qt.MouseButton.RightButton
            def pos(self):
                from PySide6.QtCore import QPoint
                return QPoint(0, 0)
            def accept(self):
                pass
        host._jitter_reorder_undo_lab_menu_no_exec = True
        try:
            lab.mousePressEvent(_E())
        except Exception:
            pass
        smoke = getattr(host, '_last_jitter_reorder_undo_lab_menu_smoke', {})
        assert 'long_press_ms' in smoke.get('actions', []), smoke
        # restore
        host.set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_long_press_ms(650, persist=True)
        ok('5 jitter long-press config/flash')
    except Exception as e:
        bad(f'5 jitter long-press config/flash: {e}')

    try:
        host.close()
    except Exception:
        pass
    print(f'\nRESULT: {pass_n} passed, {fail_n} failed')
    return 0 if fail_n == 0 else 1

if __name__ == '__main__':
    raise SystemExit(main())
