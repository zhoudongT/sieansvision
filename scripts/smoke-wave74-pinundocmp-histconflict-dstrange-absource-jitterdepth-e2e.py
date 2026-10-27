#!/usr/bin/env python3
"""细妆㊷：pin对比条应用撤销 · 吸史快捷冲突检测 · DST年范围对话框 · A/B冲突按来源 · jitter重种深度指示."""
from __future__ import annotations
import sys, json
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
        QApplication, QMessageBox, QFileDialog, QColorDialog, QInputDialog,
    )
    from PySide6.QtCore import QSettings, Qt
    from PySide6.QtGui import QColor, QDesktopServices, QMouseEvent
    from PySide6.QtCore import QPointF
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
        'undo_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar',
        'detect_stale_prune_undo_eyedropper_history_order_shortcut_conflicts',
        'format_stale_prune_undo_eyedropper_history_order_shortcut_conflicts',
        'prompt_toast_curve_png_datetime_tz_city_dst_calendar_year_range',
        'resolve_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_from_source',
        '_refresh_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_depth_ui',
    ):
        assert hasattr(HostStateMachineWidget, name), name
    ok('wave74 APIs present')

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
    s.setValue('host/mergeDiffFailHistDropPulsePreviewLoopGapMs', 120)
    s.setValue('host/mergeDiffFailHistDropPulsePreviewLoopGapJitterMs', 40)
    s.setValue('host/mergeDiffFailHistDropPulsePreviewLoopGapJitterDist', 'uniform')
    s.setValue('host/mergeDiffFailHistDropPulsePreviewLoopGapJitterSeed', 42)
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
    host._toast_curve_png_name_template_dialog_no_exec = True
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
    host._sev_pin_solo_delete_undo_ms_menu_no_exec = True
    host._merge_diff_fail_hist_drop_pulse_preview_no_exec = True
    host._stale_prune_undo_eyedropper_history_ctx_no_exec = True
    host._snap_guide_recent_max_pin_keys_no_dialog = True
    host._jitter_quantile_export_no_dialog = True
    host._ab_mirror_channel_preset_custom_no_dialog = True
    host._ab_mirror_channel_preset_custom_smoke_name = '烟测档'
    host._eyedropper_history_order_shortcuts_no_dialog = True
    host._dst_year_range_no_dialog = True

    # --- 1. pin compare-bar apply undo ---
    host._merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar_undo = []
    host.set_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_keys(
        'Ctrl+C', 'Ctrl+V', persist=True, warn=False)
    before = (
        host.merge_diff_fail_hist_drop_snap_guide_recent_max_pin_dec_key(),
        host.merge_diff_fail_hist_drop_snap_guide_recent_max_pin_inc_key(),
    )
    applied = host.apply_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar()
    assert applied['applied'] and applied['changed']
    assert applied['undo_depth'] >= 1
    assert applied['keys'] != before
    undone = host.undo_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar()
    assert undone['undone'] is True
    assert undone['keys'] == before
    assert host.merge_diff_fail_hist_drop_snap_guide_recent_max_pin_dec_key() == before[0]
    empty = host.undo_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar()
    assert empty['undone'] is False
    # UI right-click path
    host.set_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_keys(
        'Ctrl+C', 'Ctrl+V', persist=True, warn=False)
    for hx in ('#aa66ff', '#ff6688'):
        host.remember_merge_diff_fail_hist_drop_snap_guide_recent_color(hx)
    host.apply_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar()
    menu_g = host._build_merge_diff_fail_hist_drop_snap_guide_menu()
    bar_w = getattr(host, '_last_snap_guide_recent_max_pin_avoid_compare_bar', None)
    assert bar_w is not None
    assert int(bar_w.property('snapGuideRecentMaxPinAvoidCompareBarUndoDepth') or 0) >= 1
    try:
        ev = QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            QPointF(2, 2), QPointF(2, 2), QPointF(2, 2),
            Qt.MouseButton.RightButton, Qt.MouseButton.RightButton,
            Qt.KeyboardModifier.NoModifier)
        bar_w.mousePressEvent(ev)
    except TypeError:
        host.undo_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar()
    host.reset_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_keys()
    ok('pin 对比条应用撤销')

    # --- 2. hist shortcut conflict detect ---
    conf0 = host.detect_stale_prune_undo_eyedropper_history_order_shortcut_conflicts(
        'Ctrl+Shift+Z', 'Ctrl+Shift+Y')
    assert conf0 == [] or isinstance(conf0, list)
    conf_same = host.detect_stale_prune_undo_eyedropper_history_order_shortcut_conflicts(
        'Ctrl+C', 'Ctrl+C')
    assert any(c.get('reason') == '撤序/重序键相同' for c in conf_same)
    conf_rsv = host.detect_stale_prune_undo_eyedropper_history_order_shortcut_conflicts(
        'Ctrl+C', 'Ctrl+V')
    assert any('保留快捷' in str(c.get('reason', '')) for c in conf_rsv)
    tip = host.format_stale_prune_undo_eyedropper_history_order_shortcut_conflicts(conf_rsv)
    assert 'Ctrl+C' in tip
    # set with conflict should warn path (no exception)
    host.set_stale_prune_undo_eyedropper_history_order_shortcuts(
        'Ctrl+C', 'Ctrl+V', persist=True, rebind=True, warn=True)
    assert getattr(host, '_last_stale_prune_undo_eyedropper_history_order_shortcut_conflicts')
    host.reset_stale_prune_undo_eyedropper_history_order_shortcuts()
    # collide with pin keys
    host.set_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_keys(
        'Alt+-', 'Alt+=', persist=True, warn=False)
    conf_pin = host.detect_stale_prune_undo_eyedropper_history_order_shortcut_conflicts(
        'Alt+-', 'Ctrl+Shift+Y')
    assert any('钉上限' in str(c.get('reason', '')) for c in conf_pin)
    host.reset_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_keys()
    ok('吸史快捷冲突检测')

    # --- 3. DST year range dialog ---
    host._dst_year_range_smoke = '2001,2028'
    got = host.prompt_toast_curve_png_datetime_tz_city_dst_calendar_year_range()
    assert got == (2001, 2028)
    assert host.toast_curve_png_datetime_tz_city_dst_calendar_year_range() == (2001, 2028)
    host._dst_year_range_smoke = '2010-2020'
    got2 = host.prompt_toast_curve_png_datetime_tz_city_dst_calendar_year_range()
    assert got2 == (2010, 2020)
    # restore
    host.set_toast_curve_png_datetime_tz_city_dst_calendar_year_range(1990, 2035)
    ok('DST 年范围对话框')

    # --- 4. A/B conflict by source ---
    assert host.resolve_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_from_source(
        'team') == 'rename'
    assert host.resolve_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_from_source(
        'local') == 'overwrite'
    assert host.resolve_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_from_source(
        'clipboard') == 'skip'
    # payload preferred conflict wins
    assert host.resolve_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_from_source(
        '', data={'source': 'team', 'conflict': 'skip'}) == 'skip'
    host.set_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_strategy('source')
    assert host.stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_strategy() == 'source'
    host._stale_prune_undo_color_scale_ab_mirror_channel_preset_customs = [
        {'id': 'u_dup', 'label': '原档', 'channels': ['a_to_b']},
    ]
    # team → rename
    payload_team = json.dumps({
        'kind': 'sieans.ab_mirror_channel_presets', 'version': 1, 'source': 'team',
        'presets': [{'id': 'u_dup', 'label': '团档', 'channels': ['b_to_a']}],
    }, ensure_ascii=False)
    got = host.import_stale_prune_undo_color_scale_ab_mirror_channel_preset_customs(
        payload_team, merge=True)  # conflict='' → strategy source → rename
    st = getattr(host, '_last_stale_prune_undo_color_scale_ab_mirror_channel_preset_customs_import_stats')
    assert st['strategy'] == 'rename'
    assert st['rename'] >= 1
    ids = {c['id'] for c in got}
    assert 'u_dup' in ids and any(i.startswith('u_dup_') for i in ids)
    # clipboard → skip
    host._stale_prune_undo_color_scale_ab_mirror_channel_preset_customs = [
        {'id': 'u_dup', 'label': '原档', 'channels': ['a_to_b']},
    ]
    payload_clip = json.dumps({
        'kind': 'sieans.ab_mirror_channel_presets', 'version': 1, 'source': 'clipboard',
        'presets': [{'id': 'u_dup', 'label': '贴档', 'channels': ['b_to_a']}],
    }, ensure_ascii=False)
    got2 = host.import_stale_prune_undo_color_scale_ab_mirror_channel_preset_customs(
        payload_clip, merge=True)
    st2 = getattr(host, '_last_stale_prune_undo_color_scale_ab_mirror_channel_preset_customs_import_stats')
    assert st2['strategy'] == 'skip' and st2['skip'] >= 1
    by2 = {c['id']: c for c in got2}
    assert by2['u_dup']['label'] == '原档'
    # menu has source option
    host.set_stale_prune_undo_color_scale_ab_lock(True)
    host.set_stale_prune_undo_color_scale_ab_mirror(True)
    host.set_stale_prune_undo_color_scale_ab_mirror_dir('both')
    menu = host._build_undo_color_scale_hot_sync_menu()
    sub = getattr(host, '_last_undo_color_scale_ab_mirror_channel_preset_import_conflict_menu', None)
    assert sub is not None
    acts = [a for a in sub.actions() if a.property('abMirrorChannelPresetImportConflict') == 'source']
    assert acts
    host.set_stale_prune_undo_color_scale_ab_lock(False)
    host.set_stale_prune_undo_color_scale_ab_mirror(False)
    host.set_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_strategy('overwrite')
    ok('A/B 冲突策略默认按来源')

    # --- 5. jitter redo depth indicator ---
    host.set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed(42)
    host._merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_history = []
    host._merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo = []
    s1 = host.reshuffle_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed()
    host.undo_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_reshuffle()
    d = host._refresh_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_depth_ui()
    assert d >= 1
    assert getattr(host, '_last_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_depth') >= 1
    # reshuffle again then undo twice for depth 2
    host.reshuffle_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed()
    host.reshuffle_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed()
    host.undo_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_reshuffle()
    host.undo_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_reshuffle()
    d2 = len(host._merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo)
    assert d2 >= 2
    host._refresh_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_depth_ui(d2)
    # simulate UI label/button via direct call after ensuring attrs
    # (dialog not open; refresh still updates last_ depth)
    assert getattr(host, '_last_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_depth') == d2
    host.redo_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_reshuffle()
    d3 = len(host._merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo)
    assert d3 == d2 - 1
    host.reshuffle_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed()
    assert host._merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo == []
    assert host._refresh_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo_depth_ui() == 0
    ok('jitter 重种深度指示')

    print(f'wave74 DONE pass={pass_n} fail={fail_n}')
    return 0 if fail_n == 0 else 1

if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as e:
        bad(f'exception · {e}')
        import traceback; traceback.print_exc()
        print(f'wave74 DONE pass={pass_n} fail={fail_n}')
        raise SystemExit(1)
