#!/usr/bin/env python3
"""细妆㊶：pin对比条点击应用 · 吸史快捷自定义 · DST年范围/本月 · A/B导入冲突策略 · jitter撤种重做栈."""
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
    from PySide6.QtGui import QColor, QDesktopServices, QKeySequence, QMouseEvent
    from PySide6.QtCore import QPointF, QPoint
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
        'apply_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar',
        'set_stale_prune_undo_eyedropper_history_order_shortcuts',
        'prompt_stale_prune_undo_eyedropper_history_order_shortcuts',
        'reset_stale_prune_undo_eyedropper_history_order_shortcuts',
        'toast_curve_png_datetime_tz_city_dst_calendar_year_range',
        'set_toast_curve_png_datetime_tz_city_dst_calendar_year_range',
        'jump_toast_curve_png_datetime_tz_city_dst_calendar_current_month',
        'stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_strategy',
        'set_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_strategy',
        'redo_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_reshuffle',
    ):
        assert hasattr(HostStateMachineWidget, name), name
    ok('wave73 APIs present')

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

    # --- 1. pin compare bar click apply ---
    host.set_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_keys(
        'Ctrl+C', 'Ctrl+V', persist=True, warn=False)
    conf = host.detect_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_conflicts(
        'Ctrl+C', 'Ctrl+V')
    assert conf, 'expected conflict for Ctrl+C/V'
    applied = host.apply_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar()
    assert applied['applied'] is True
    assert applied['changed'] is True
    keys = applied['keys']
    assert keys != ('Ctrl+C', 'Ctrl+V')
    assert not host.detect_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_conflicts(*keys)
    # UI: build menu → bar clickable（需有最近色才渲染钉上限行）
    host.set_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_keys(
        'Ctrl+C', 'Ctrl+V', persist=True, warn=False)
    for hx in ('#aa66ff', '#ff6688'):
        host.remember_merge_diff_fail_hist_drop_snap_guide_recent_color(hx)
    menu_g = host._build_merge_diff_fail_hist_drop_snap_guide_menu()
    bar_w = getattr(host, '_last_snap_guide_recent_max_pin_avoid_compare_bar', None)
    assert bar_w is not None
    assert bar_w.property('isSnapGuideRecentMaxPinAvoidCompareBarClickable')
    # simulate click
    try:
        ev = QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            QPointF(2, 2), QPointF(2, 2), QPointF(2, 2),
            Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier)
    except TypeError:
        ev = None
    if ev is not None:
        bar_w.mousePressEvent(ev)
    else:
        host.apply_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar()
    assert bar_w.property('snapGuideRecentMaxPinAvoidCompareBarApplied')
    host.reset_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_keys()
    ok('pin 避让对比条点击一键应用')

    # --- 2. hist shortcut custom ---
    host._eyedropper_history_order_shortcuts_smoke = 'Alt+Z,Alt+Y'
    got = host.prompt_stale_prune_undo_eyedropper_history_order_shortcuts()
    assert got[0] in ('Alt+Z', 'Alt+Z'.replace('+','+'))
    # QKeySequence may normalize
    assert 'Z' in got[0] and 'Y' in got[1]
    assert getattr(host, '_last_eyedropper_history_order_undo_shortcut') == got[0]
    assert getattr(host, '_last_eyedropper_history_order_redo_shortcut') == got[1]
    wrap = host._make_undo_color_scale_eyedropper_history_row(which='hi')
    btn_u = getattr(host, '_last_undo_color_scale_eyedropper_history_undo_order_btn', None)
    btn_r = getattr(host, '_last_undo_color_scale_eyedropper_history_redo_order_btn', None)
    btn_k = getattr(host, '_last_undo_color_scale_eyedropper_history_order_shortcut_cfg_btn', None)
    assert btn_u is not None and btn_u.property('eyedropperHistoryOrderUndoShortcut') == got[0]
    assert btn_r is not None and btn_r.property('eyedropperHistoryOrderRedoShortcut') == got[1]
    assert btn_k is not None and btn_k.property('isUndoEyedropperHistoryOrderShortcutCfg')
    reset = host.reset_stale_prune_undo_eyedropper_history_order_shortcuts()
    assert reset == ('Ctrl+Shift+Z', 'Ctrl+Shift+Y') or (
        'Z' in reset[0] and 'Y' in reset[1] and 'Ctrl' in reset[0])
    ok('吸史快捷键自定义')

    # --- 3. DST year range + current month ---
    rng = host.set_toast_curve_png_datetime_tz_city_dst_calendar_year_range(2000, 2030)
    assert rng == (2000, 2030)
    assert host.toast_curve_png_datetime_tz_city_dst_calendar_year_range() == (2000, 2030)
    # clamp year outside range
    y = host.set_toast_curve_png_datetime_tz_city_dst_calendar_year(2099, refresh=False)
    assert y == 2030
    y2 = host.set_toast_curve_png_datetime_tz_city_dst_calendar_year(1980, refresh=False)
    assert y2 == 2000
    host.set_toast_curve_png_datetime_tz_city('newyork')
    jumped = host.jump_toast_curve_png_datetime_tz_city_dst_calendar_current_month(city='newyork')
    import datetime as _dt
    now = _dt.datetime.now()
    assert jumped['month'] == now.month
    assert jumped['year'] == max(2000, min(2030, now.year))
    # restore wider range for other tests
    host.set_toast_curve_png_datetime_tz_city_dst_calendar_year_range(1990, 2035)
    ok('DST 年范围/本月跳回')

    # --- 4. A/B import conflict strategy ---
    host.set_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_strategy('overwrite')
    assert host.stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_strategy() == 'overwrite'
    host._stale_prune_undo_color_scale_ab_mirror_channel_preset_customs = [
        {'id': 'u_dup', 'label': '原档', 'channels': ['a_to_b']},
    ]
    host._host_settings().setValue(
        'host/stalePruneUndoColorScaleAbMirrorChannelPresetCustoms',
        list(host._stale_prune_undo_color_scale_ab_mirror_channel_preset_customs))
    payload = json.dumps({
        'kind': 'sieans.ab_mirror_channel_presets', 'version': 1,
        'presets': [
            {'id': 'u_dup', 'label': '新档', 'channels': ['b_to_a']},
            {'id': 'u_new', 'label': '全新', 'channels': ['a_to_b', 'b_to_a']},
        ],
    }, ensure_ascii=False)
    # overwrite
    got = host.import_stale_prune_undo_color_scale_ab_mirror_channel_preset_customs(
        payload, merge=True, conflict='overwrite')
    by = {c['id']: c for c in got}
    assert by['u_dup']['label'] == '新档'
    assert by['u_dup']['channels'] == ['b_to_a']
    st = getattr(host, '_last_stale_prune_undo_color_scale_ab_mirror_channel_preset_customs_import_stats')
    assert st['overwrite'] >= 1 and st['added'] >= 1
    # skip
    host._stale_prune_undo_color_scale_ab_mirror_channel_preset_customs = [
        {'id': 'u_dup', 'label': '原档', 'channels': ['a_to_b']},
    ]
    got2 = host.import_stale_prune_undo_color_scale_ab_mirror_channel_preset_customs(
        payload, merge=True, conflict='skip')
    by2 = {c['id']: c for c in got2}
    assert by2['u_dup']['label'] == '原档'
    st2 = getattr(host, '_last_stale_prune_undo_color_scale_ab_mirror_channel_preset_customs_import_stats')
    assert st2['skip'] >= 1
    # rename
    host._stale_prune_undo_color_scale_ab_mirror_channel_preset_customs = [
        {'id': 'u_dup', 'label': '原档', 'channels': ['a_to_b']},
    ]
    got3 = host.import_stale_prune_undo_color_scale_ab_mirror_channel_preset_customs(
        payload, merge=True, conflict='rename')
    ids3 = {c['id'] for c in got3}
    assert 'u_dup' in ids3
    assert any(i.startswith('u_dup_') for i in ids3)
    st3 = getattr(host, '_last_stale_prune_undo_color_scale_ab_mirror_channel_preset_customs_import_stats')
    assert st3['rename'] >= 1
    host.set_stale_prune_undo_color_scale_ab_lock(True)
    host.set_stale_prune_undo_color_scale_ab_mirror(True)
    host.set_stale_prune_undo_color_scale_ab_mirror_dir('both')
    host.set_stale_prune_undo_color_scale_ab_mirror_channel_preset_import_conflict_strategy('rename')
    menu = host._build_undo_color_scale_hot_sync_menu()
    sub = getattr(host, '_last_undo_color_scale_ab_mirror_channel_preset_import_conflict_menu', None)
    assert sub is not None
    assert sub.property('isUndoColorScaleAbMirrorChannelPresetImportConflictMenu')
    host.set_stale_prune_undo_color_scale_ab_lock(False)
    host.set_stale_prune_undo_color_scale_ab_mirror(False)
    ok('A/B 导入冲突策略')

    # --- 5. jitter redo stack ---
    host.set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_ms(40)
    host.set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed(42)
    host._merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_history = []
    host._merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo = []
    s1 = host.reshuffle_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed()
    assert s1 != 42
    assert host._merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo == []
    undone = host.undo_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_reshuffle()
    assert undone == 42
    redo = list(host._merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo)
    assert redo and redo[-1] == s1
    redone = host.redo_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_reshuffle()
    assert redone == s1
    assert host.merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed() == s1
    # empty redo
    host._merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo = []
    empty = host.redo_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_reshuffle()
    assert empty == host.merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed()
    # reshuffle clears redo
    host.undo_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_reshuffle()
    assert host._merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo
    host.reshuffle_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed()
    assert host._merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_redo == []
    ok('jitter 撤种重做栈')

    print(f'wave73 DONE pass={pass_n} fail={fail_n}')
    return 0 if fail_n == 0 else 1

if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as e:
        bad(f'exception · {e}')
        import traceback; traceback.print_exc()
        print(f'wave73 DONE pass={pass_n} fail={fail_n}')
        raise SystemExit(1)
