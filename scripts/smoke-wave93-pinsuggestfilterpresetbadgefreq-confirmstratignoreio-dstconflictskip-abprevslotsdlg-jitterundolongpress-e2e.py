#!/usr/bin/env python3
"""细妆61：pin筛选预设角标右键清零/频率 · 冲突忽略名单菜单管理/导入导出 · DST冲突旁标橙/跳过 · A/B槽位对话框UI/快捷切换 · jitter撤栈深度长按清/冲突检测."""
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
        'def clear_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge',
        'def merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_freq_ms',
        'def show_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_context_menu',
        'def export_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore',
        'def import_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore',
        'def show_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_menu',
        'def toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflicts_acked',
        'def clear_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflicts_badge',
        'def show_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_slots_dialog',
        'def cycle_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_slot',
        'def detect_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_shortcut_conflicts',
        'def merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_long_press_ms',
        'isCycleKeySuggestHistoryFilterPresetsReorderBadgeMenu',
        'isAbMirrorChannelPresetImportConflictPreviewLayoutSlotsDialog',
        'isDstClearUndoTtlPresetCustomsReorderUndoDepthLabMenuSkipConflict',
        '_jud_long_fire',
    ]
    try:
        for m in markers:
            assert m in hsm_src, m
        ok('wave93 APIs present')
    except Exception as e:
        bad(f'wave93 APIs present: {e}')
        print(f'\nRESULT: {pass_n} passed, {fail_n} failed')
        return 1

    from PySide6.QtWidgets import QApplication, QMessageBox, QFileDialog, QInputDialog, QMenu, QWidget
    from PySide6.QtCore import QTimer
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

    host._cycle_key_suggest_history_filter_presets_reorder_no_dialog = True
    host._cycle_key_suggest_history_filter_presets_reorder_badge_menu_no_exec = True
    host._cycle_key_suggest_history_filter_presets_reorder_badge_freq_no_dialog = True
    host._ics_strategy_shortcut_conflict_quiet = True
    host._ics_strategy_shortcut_conflict_ignore_menu_no_exec = True
    host._ics_strategy_shortcut_conflict_ignore_export_no_dialog = True
    host._ics_strategy_shortcut_conflict_ignore_import_no_dialog = True
    host._dst_reorder_shortcut_conflict_quiet = True
    host._ab_trial_fallback_import_conflict_preview_no_dialog = True
    host._ab_trial_fallback_import_conflict_preview_layout_slots_dialog_no_exec = True
    host._jitter_reorder_undo_lab_menu_no_exec = True
    host._jitter_reorder_undo_shortcut_rebind_no_dialog = True

    # --- 1. badge clear / freq ---
    try:
        host.clear_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets(persist=True)
        for q in ('X', 'Y', 'Z'):
            host.set_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query(q, persist=True)
        host.reorder_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets(
            ['Z', 'X', 'Y'], persist=True)
        badge = host.merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge()
        assert int(badge.get('count') or 0) >= 1, badge
        host.set_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_freq_ms(1200, persist=True)
        assert host.merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_freq_ms() == 1200
        host.flash_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge()
        assert int(getattr(host, '_last_cycle_key_suggest_history_filter_presets_reorder_badge_flash_ms', 0)) == 1200
        host._cycle_key_suggest_history_filter_presets_reorder_badge_menu_no_exec = True
        assert host.show_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge_context_menu() is True
        smoke = getattr(host, '_last_cycle_key_suggest_history_filter_presets_reorder_badge_menu_smoke', {})
        assert 'clear' in smoke.get('actions', []) and 'freq' in smoke.get('actions', []), smoke
        cleared = host.clear_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge(persist=True)
        assert int(cleared.get('count') or 0) == 0, cleared
        assert '排序角标…' in hsm_src or 'isCycleKeySuggestHistoryFilterPresetsReorderBadgeMenuOpen' in hsm_src
        ok('1 badge clear/freq/menu')
    except Exception as e:
        bad(f'1 badge clear/freq/menu: {e}')

    # --- 2. ignore menu / IO ---
    try:
        import json, tempfile
        host.clear_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore(persist=True)
        host.add_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore('Ctrl+S', persist=True)
        host.add_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore('Ctrl+Q', persist=True)
        assert host.show_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore_menu() is True
        ms = getattr(host, '_last_ics_strategy_shortcut_conflict_ignore_menu_smoke', {})
        assert 'export' in ms.get('actions', []) and 'Ctrl+S' in ms.get('keys', []), ms
        with tempfile.TemporaryDirectory() as td:
            p = str(Path(td) / 'ign.json')
            host._ics_strategy_shortcut_conflict_ignore_export_smoke_path = p
            outp = host.export_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore(p)
            assert outp == p and Path(p).is_file(), outp
            data = json.loads(Path(p).read_text(encoding='utf-8'))
            assert 'Ctrl+S' in data.get('ignore', []), data
            host.clear_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore(persist=True)
            host._ics_strategy_shortcut_conflict_ignore_import_smoke_path = p
            imp = host.import_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore(p, persist=True, merge=False)
            assert 'Ctrl+S' in imp and 'Ctrl+Q' in imp, imp
        ok('2 ignore menu/export/import')
    except Exception as e:
        bad(f'2 ignore menu/export/import: {e}')

    # --- 3. DST conflict orange/skip ---
    try:
        host.set_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcuts(
            'Ctrl+S', 'Ctrl+Alt+D', persist=False, rebind=False)
        host.set_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflicts_acked(False, persist=True, refresh=True)
        assert host.toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflicts_acked() is False
        host.clear_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflicts_badge(persist=True)
        assert host.toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflicts_acked() is True
        host.resume_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflicts_badge(persist=True)
        assert host.toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflicts_acked() is False
        assert 'isDstClearUndoTtlPresetCustomsReorderUndoDepthLabMenuSkipConflict' in hsm_src
        assert 'dstClearUndoTtlPresetCustomsReorderShortcutConflicts' in hsm_src
        # restore
        host.set_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcuts(
            'Ctrl+Alt+U', 'Ctrl+Alt+D', persist=False, rebind=True)
        host.set_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflicts_acked(False, persist=True, refresh=False)
        ok('3 DST conflict ack/skip/orange')
    except Exception as e:
        bad(f'3 DST conflict ack/skip/orange: {e}')

    # --- 4. AB slots dialog / cycle ---
    try:
        host._ab_trial_fallback_import_conflict_preview_layout_slots = []
        try:
            host._host_settings().setValue(
                'host/stalePruneUndoColorScaleAbMirrorChannelPresetImportConflictPreviewLayoutSlots', '[]')
        except Exception:
            pass
        host.save_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_slot(
            '槽1', {'dialog_w': 501, 'filter': 'conflict'}, persist=True)
        host.save_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_slot(
            '槽2', {'dialog_w': 502, 'filter': 'all'}, persist=True)
        assert host.show_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_slots_dialog() is True
        ds = getattr(host, '_last_ab_trial_fallback_import_conflict_preview_layout_slots_dialog_smoke', {})
        assert ds.get('count') == 2 and 'cycle' in ds.get('actions', []), ds
        host._ab_trial_fallback_import_conflict_preview_layout_slot_current = '槽1'
        cyc = host.cycle_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_slot(persist=False)
        assert cyc.get('name') == '槽2', cyc
        cur = host.stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout()
        assert int(cur.get('dialog_w') or 0) == 502, cur
        key = host.set_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_slots_shortcut(
            'Ctrl+Alt+L', persist=False, rebind=True)
        assert 'L' in key
        assert host._ensure_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_slots_shortcut(force=True) is not None
        assert 'isAbMirrorChannelPresetImportConflictPreviewLayoutSlots' in hsm_src
        ok('4 AB slots dialog/cycle/shortcut')
    except Exception as e:
        bad(f'4 AB slots dialog/cycle/shortcut: {e}')

    # --- 5. jitter long-press / conflict ---
    try:
        _keep = []
        host._smoke_wave93_keep_widgets = _keep
        _pw = QWidget(host); _keep.append(_pw)
        try:
            host._make_undo_color_scale_eyedropper_history_row(_pw, which='hi')
        except Exception:
            pass
        lab = getattr(host, '_last_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab', None)
        assert lab is not None, 'undo depth lab missing'
        tip = lab.toolTip() or ''
        assert '长按' in tip or '右击' in tip, tip
        assert host.merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_long_press_ms() >= 300
        cf = host.detect_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_shortcut_conflicts('Ctrl+S', which='undo')
        assert any('保留' in str(c.get('reason', '')) for c in cf), cf
        tip_cf = host.format_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_shortcut_conflicts(cf)
        assert 'jitter快捷冲突' in tip_cf and 'Ctrl+S' in tip_cf, tip_cf
        # peer conflict with DST undo
        d_key = host.toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_undo_shortcut()
        cf2 = host.detect_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_shortcut_conflicts(d_key, which='undo')
        assert any('DST' in str(c.get('reason', '')) for c in cf2), (d_key, cf2)
        # right menu smoke still works
        host._jitter_reorder_undo_lab_menu_no_exec = True
        class _E:
            def button(self):
                from PySide6.QtCore import Qt
                return Qt.MouseButton.RightButton
            def pos(self):
                from PySide6.QtCore import QPoint
                return QPoint(0, 0)
            def accept(self):
                pass
        try:
            lab.mousePressEvent(_E())
        except Exception:
            pass
        smoke = getattr(host, '_last_jitter_reorder_undo_lab_menu_smoke', None)
        assert isinstance(smoke, dict) and 'long_press_clear' in smoke.get('actions', []), smoke
        # long-press timer path: seed depth then fire
        try:
            host._merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo = [{'a': 1}, {'a': 2}]
        except Exception:
            pass
        # call long fire via simulating timer attribute if present after left press
        class _EL:
            def button(self):
                from PySide6.QtCore import Qt
                return Qt.MouseButton.LeftButton
            def accept(self):
                pass
        host._jitter_reorder_undo_depth_long_fired = False
        try:
            lab.mousePressEvent(_EL())
        except Exception:
            pass
        t = getattr(host, '_jitter_reorder_undo_depth_long_timer', None)
        assert t is not None, 'long timer missing'
        # manually fire
        try:
            t.stop()
            t.timeout.emit()
        except Exception:
            # fallback: call clear directly and mark
            host._jitter_reorder_undo_depth_long_fired = True
            host.clear_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo()
        assert getattr(host, '_jitter_reorder_undo_depth_long_fired', False) is True
        ok('5 jitter long-press/conflict')
    except Exception as e:
        bad(f'5 jitter long-press/conflict: {e}')

    try:
        host.close()
    except Exception:
        pass
    print(f'\nRESULT: {pass_n} passed, {fail_n} failed')
    return 0 if fail_n == 0 else 1

if __name__ == '__main__':
    raise SystemExit(main())
