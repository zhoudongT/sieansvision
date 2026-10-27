#!/usr/bin/env python3
"""细妆60：pin筛选预设拖拽排序持久动画/角标 · 冲突检测历史/忽略名单 · DST快捷冲突检测 · A/B布局多槽位/命名 · jitter撤栈旁标右键清栈/可改绑."""
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
        'def merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge',
        'def note_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder',
        'def flash_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge',
        'def list_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_history',
        'def list_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore',
        'def detect_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflicts',
        'def list_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_slots',
        'def save_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_slot',
        'def show_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_shortcut_rebind_dialog',
        'isJitterSeedRedoClearUndoTtlPresetCustomsReorderUndoDepthLabMenu',
        'isCycleKeySuggestHistoryFilterPresetsReorderBadge',
    ]
    try:
        for m in markers:
            assert m in hsm_src, m
        ok('wave92 APIs present')
    except Exception as e:
        bad(f'wave92 APIs present: {e}')
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

    host._cycle_key_suggest_history_filter_presets_reorder_no_dialog = True
    host._swatch_conflict_preview_menu_no_exec = True
    host._ics_strategy_shortcut_conflict_quiet = True
    host._dst_reorder_shortcut_conflict_quiet = True
    host._dst_reorder_shortcuts_rebind_no_dialog = True
    host._jitter_reorder_undo_shortcut_rebind_no_dialog = True
    host._jitter_reorder_undo_lab_menu_no_exec = True
    host._ab_trial_fallback_import_conflict_preview_no_dialog = True

    # --- 1. filter presets reorder badge ---
    try:
        host.clear_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets(persist=True)
        for q in ('A', 'B', 'C'):
            host.set_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query(q, persist=True)
        before = host.merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge()
        b0 = int(before.get('count') or 0)
        out = host.reorder_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets(
            ['C', 'A', 'B'], persist=True)
        assert out[:3] == ['C', 'A', 'B'], out
        after = host.merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge()
        assert int(after.get('count') or 0) == b0 + 1, (before, after)
        assert int(after.get('last_len') or 0) >= 3, after
        flash = host.flash_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo_swatch_conflict_preview_cycle_key_suggest_history_filter_query_presets_reorder_badge()
        assert flash is True
        assert '筛选预设排序' in str(getattr(host, '_last_cycle_key_suggest_history_filter_presets_reorder_badge_flash', ''))
        assert 'isCycleKeySuggestHistoryFilterPresetsReorderBadge' in hsm_src
        ok('1 filter presets reorder badge/anim')
    except Exception as e:
        bad(f'1 filter presets reorder badge/anim: {e}')

    # --- 2. conflict history / ignore ---
    try:
        host.clear_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_history(persist=True)
        host.clear_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore(persist=True)
        cf = host.detect_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflicts('Ctrl+S')
        assert any('保留' in str(c.get('reason', '')) for c in cf), cf
        hist = host.list_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_history()
        assert hist and hist[0].get('key') == 'Ctrl+S', hist
        ign = host.add_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore('Ctrl+S', persist=True)
        assert 'Ctrl+S' in ign, ign
        cf2 = host.detect_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflicts('Ctrl+S')
        assert cf2 == [], cf2
        host.remove_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflict_ignore('Ctrl+S', persist=True)
        cf3 = host.detect_stale_prune_undo_eyedropper_history_order_shortcut_conflict_fix_candidate_confirm_undo_import_conflict_strategy_shortcut_conflicts('Ctrl+S')
        assert any('保留' in str(c.get('reason', '')) for c in cf3), cf3
        ok('2 conflict history/ignore')
    except Exception as e:
        bad(f'2 conflict history/ignore: {e}')

    # --- 3. DST shortcut conflict ---
    try:
        cf_s = host.detect_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflicts('Ctrl+S', which='undo')
        assert any('保留' in str(c.get('reason', '')) for c in cf_s), cf_s
        tip = host.format_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflicts(cf_s)
        assert 'DST快捷冲突' in tip and 'Ctrl+S' in tip, tip
        j_key = host.merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_shortcut()
        cf_j = host.detect_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcut_conflicts(j_key, which='undo')
        assert any('jitter' in str(c.get('reason', '')) for c in cf_j), (j_key, cf_j)
        host._dst_reorder_shortcut_conflict_quiet = True
        host.set_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcuts(
            'Ctrl+S', 'Ctrl+Alt+D', persist=False, rebind=False)
        pair = getattr(host, '_last_dst_reorder_shortcut_conflicts_pair', {})
        assert pair.get('undo'), pair
        # restore
        host.set_toast_curve_png_datetime_tz_city_dst_calendar_year_range_recent_apply_all_undo_clear_undo_ttl_preset_customs_reorder_shortcuts(
            'Ctrl+Alt+U', 'Ctrl+Alt+D', persist=False, rebind=True)
        ok('3 DST shortcut conflict detect')
    except Exception as e:
        bad(f'3 DST shortcut conflict detect: {e}')

    # --- 4. AB layout slots ---
    try:
        # clear slots via settings overwrite
        host._ab_trial_fallback_import_conflict_preview_layout_slots = []
        try:
            host._host_settings().setValue(
                'host/stalePruneUndoColorScaleAbMirrorChannelPresetImportConflictPreviewLayoutSlots', '[]')
        except Exception:
            pass
        lay = host.stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout()
        lay2 = dict(lay); lay2['dialog_w'] = 500; lay2['filter'] = 'conflict'
        saved = host.save_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_slot('产线A', lay2, persist=True)
        assert saved.get('name') == '产线A', saved
        slots = host.list_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_slots()
        assert any(s.get('name') == '产线A' for s in slots), slots
        host.set_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout(
            {'dialog_w': 420, 'filter': 'all'}, persist=False)
        loaded = host.load_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_slot('产线A', apply=True, persist=False)
        assert loaded.get('name') == '产线A', loaded
        cur = host.stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout()
        assert int(cur.get('dialog_w') or 0) == 500, cur
        assert cur.get('filter') == 'conflict', cur
        assert host.rename_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_slot('产线A', '产线B', persist=True)
        assert host.delete_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_slot('产线B', persist=True)
        assert host.list_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_preview_layout_slots() == []
        ok('4 AB layout named slots')
    except Exception as e:
        bad(f'4 AB layout named slots: {e}')

    # --- 5. jitter undo lab menu / rebind ---
    try:
        _keep = []
        host._smoke_wave92_keep_widgets = _keep
        _pw = QWidget(host); _keep.append(_pw)
        try:
            host._make_undo_color_scale_eyedropper_history_row(_pw, which='hi')
        except Exception:
            pass
        lab = getattr(host, '_last_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_depth_lab', None)
        assert lab is not None, 'undo depth lab missing'
        tip = lab.toolTip() or ''
        assert '右击' in tip or '改绑' in tip, tip
        host._jitter_reorder_undo_shortcut_rebind_smoke = 'Ctrl+Alt+Shift+K'
        host._jitter_reorder_undo_shortcut_rebind_no_dialog = True
        outk = host.show_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_shortcut_rebind_dialog()
        assert 'Shift' in outk and 'K' in outk, outk
        # simulate right menu smoke
        host._jitter_reorder_undo_lab_menu_no_exec = True
        class _E:
            def button(self):
                from PySide6.QtCore import Qt
                return Qt.MouseButton.RightButton
            def pos(self):
                from PySide6.QtCore import QPoint
                return QPoint(0, 0)
        try:
            lab.mousePressEvent(_E())
        except Exception:
            pass
        smoke = getattr(host, '_last_jitter_reorder_undo_lab_menu_smoke', None)
        assert isinstance(smoke, dict) and 'clear_undo' in smoke.get('actions', []), smoke
        assert 'isJitterSeedRedoClearUndoTtlPresetCustomsReorderUndoDepthLabMenu' in hsm_src
        # restore key
        host.set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_clear_undo_ttl_preset_customs_reorder_undo_shortcut(
            'Ctrl+Alt+K', persist=False, rebind=True)
        ok('5 jitter undo lab menu/rebind')
    except Exception as e:
        bad(f'5 jitter undo lab menu/rebind: {e}')

    try:
        host.close()
    except Exception:
        pass
    print(f'\nRESULT: {pass_n} passed, {fail_n} failed')
    return 0 if fail_n == 0 else 1

if __name__ == '__main__':
    raise SystemExit(main())
