#!/usr/bin/env python3
"""细妆㊵：pin避让色标对比条 · 吸史重序快捷键 · DST跳月年切换 · A/B自定义预设导出/导入 · jitter重抽历史栈."""
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
    from PySide6.QtCore import QSettings
    from PySide6.QtGui import QColor, QDesktopServices, QKeySequence
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
        'render_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar',
        '_ensure_eyedropper_history_order_shortcuts',
        'set_toast_curve_png_datetime_tz_city_dst_calendar_year',
        'bump_toast_curve_png_datetime_tz_city_dst_calendar_year',
        'export_stale_prune_undo_color_scale_ab_mirror_channel_preset_customs',
        'import_stale_prune_undo_color_scale_ab_mirror_channel_preset_customs',
        'push_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_history',
        'undo_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_reshuffle',
    ):
        assert hasattr(HostStateMachineWidget, name), name
    ok('wave72 APIs present')

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
    s.setValue('host/stalePruneUndoEyedropperHistory', [])
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

    # --- 1. pin avoid compare bar ---
    host.set_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_keys(
        'Ctrl+C', 'Ctrl+V', persist=True, warn=False)
    bar = host.render_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_compare_bar(12)
    assert '█' in bar['bar'] and '▓' in bar['bar']
    assert '冲突' in bar['text'] and '可避' in bar['text']
    assert bar['current_color'] == '#e6a23c'
    assert bar['suggested_color'] == '#3ecf8e'
    assert 'qlineargradient' in bar['css']
    assert bar['changed'] is True
    for hx in ('#aa66ff', '#ff6688'):
        host.remember_merge_diff_fail_hist_drop_snap_guide_recent_color(hx)
    menu_g = host._build_merge_diff_fail_hist_drop_snap_guide_menu()
    bar_w = getattr(host, '_last_snap_guide_recent_max_pin_avoid_compare_bar', None)
    assert bar_w is not None and bar_w.property('isSnapGuideRecentMaxPinAvoidCompareBar')
    assert '冲突' in str(bar_w.property('snapGuideRecentMaxPinAvoidCompareBarText') or '')
    host.reset_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_keys()
    ok('pin 避让色标对比条')

    # --- 2. hist order shortcuts ---
    assert host._ensure_eyedropper_history_order_shortcuts() is True
    assert getattr(host, '_last_eyedropper_history_order_undo_shortcut') == 'Ctrl+Shift+Z'
    assert getattr(host, '_last_eyedropper_history_order_redo_shortcut') == 'Ctrl+Shift+Y'
    sc_u = getattr(host, '_eyedropper_history_order_undo_shortcut', None)
    sc_r = getattr(host, '_eyedropper_history_order_redo_shortcut', None)
    assert sc_u is not None and sc_r is not None
    wrap = host._make_undo_color_scale_eyedropper_history_row(which='hi')
    btn_u = getattr(host, '_last_undo_color_scale_eyedropper_history_undo_order_btn', None)
    btn_r = getattr(host, '_last_undo_color_scale_eyedropper_history_redo_order_btn', None)
    assert btn_u is not None and btn_u.property('eyedropperHistoryOrderUndoShortcut') == 'Ctrl+Shift+Z'
    assert btn_r is not None and btn_r.property('eyedropperHistoryOrderRedoShortcut') == 'Ctrl+Shift+Y'
    assert 'Ctrl+Shift+Z' in (btn_u.toolTip() or '')
    assert 'Ctrl+Shift+Y' in (btn_r.toolTip() or '')
    # functional: undo/redo still works
    host.clear_stale_prune_undo_eyedropper_history()
    host._stale_prune_undo_eyedropper_history_order_undo = []
    host._stale_prune_undo_eyedropper_history_order_redo = []
    for hx in ('#112233', '#445566', '#778899'):
        host.remember_stale_prune_undo_eyedropper_history(hx)
    orig = list(host.stale_prune_undo_eyedropper_history())
    host.reorder_stale_prune_undo_eyedropper_history(['#778899', '#445566', '#112233'])
    host.undo_stale_prune_undo_eyedropper_history_reorder()
    assert host.stale_prune_undo_eyedropper_history()[:3] == orig[:3]
    host.redo_stale_prune_undo_eyedropper_history_reorder()
    assert host.stale_prune_undo_eyedropper_history()[:3] == ['#778899', '#445566', '#112233']
    ok('吸史重序快捷键')

    # --- 3. DST year switch ---
    host.set_toast_curve_png_datetime_tz_city('newyork')
    y = host.set_toast_curve_png_datetime_tz_city_dst_calendar_year(2025, refresh=False)
    assert y == 2025
    jumped = host.jump_toast_curve_png_datetime_tz_city_dst_calendar_month(
        7, year=2025, city='newyork')
    assert jumped['year'] == 2025 and jumped['month'] == 7
    y2 = host.bump_toast_curve_png_datetime_tz_city_dst_calendar_year(1)
    assert y2 == 2026
    assert getattr(host, '_last_toast_curve_png_datetime_tz_city_dst_calendar_year') == 2026
    y3 = host.bump_toast_curve_png_datetime_tz_city_dst_calendar_year(-1)
    assert y3 == 2025
    ok('DST 跳月年切换')

    # --- 4. A/B custom export/import ---
    host.set_stale_prune_undo_color_scale_ab_mirror_dir('both')
    host.set_stale_prune_undo_color_scale_ab_mirror_channels(['a_to_b'])
    host.save_stale_prune_undo_color_scale_ab_mirror_channel_preset_custom('导出测')
    host.set_stale_prune_undo_color_scale_ab_mirror_channels(['b_to_a'])
    host.save_stale_prune_undo_color_scale_ab_mirror_channel_preset_custom('导出测B')
    text = host.export_stale_prune_undo_color_scale_ab_mirror_channel_preset_customs(
        to_clipboard=True)
    data = json.loads(text)
    assert data['kind'] == 'sieans.ab_mirror_channel_presets'
    assert len(data['presets']) >= 2
    # clear then import
    host._stale_prune_undo_color_scale_ab_mirror_channel_preset_customs = []
    host._host_settings().setValue(
        'host/stalePruneUndoColorScaleAbMirrorChannelPresetCustoms', [])
    got = host.import_stale_prune_undo_color_scale_ab_mirror_channel_preset_customs(
        text, merge=False)
    assert len(got) >= 2
    ids = {c['id'] for c in got}
    assert any(i.startswith('u_') for i in ids)
    # merge path with extra
    extra = json.dumps({
        'kind': 'sieans.ab_mirror_channel_presets', 'version': 1,
        'presets': [{'id': 'u_extra', 'label': '额外', 'channels': ['a_to_b', 'b_to_a']}],
    }, ensure_ascii=False)
    got2 = host.import_stale_prune_undo_color_scale_ab_mirror_channel_preset_customs(
        extra, merge=True)
    assert any(c['id'] == 'u_extra' for c in got2)
    host.set_stale_prune_undo_color_scale_ab_lock(True)
    host.set_stale_prune_undo_color_scale_ab_mirror(True)
    host.set_stale_prune_undo_color_scale_ab_mirror_dir('both')
    menu = host._build_undo_color_scale_hot_sync_menu()
    act_e = getattr(host, '_last_undo_color_scale_ab_mirror_channel_preset_export', None)
    act_i = getattr(host, '_last_undo_color_scale_ab_mirror_channel_preset_import', None)
    assert act_e is not None and act_e.property('isUndoColorScaleAbMirrorChannelPresetExport')
    assert act_i is not None and act_i.property('isUndoColorScaleAbMirrorChannelPresetImport')
    host.set_stale_prune_undo_color_scale_ab_lock(False)
    host.set_stale_prune_undo_color_scale_ab_mirror(False)
    ok('A/B 自定义预设导出/导入')

    # --- 5. jitter reshuffle history ---
    host.set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_ms(40)
    host.set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed(42)
    host._merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_history = []
    s1 = host.reshuffle_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed()
    assert s1 != 42
    hist = list(getattr(host, '_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_history', []) or [])
    assert hist and hist[-1] == 42, hist
    s2 = host.reshuffle_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed()
    hist2 = list(getattr(host, '_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_history', []) or [])
    assert len(hist2) >= 2 and hist2[-1] == s1
    undone = host.undo_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_reshuffle()
    assert undone == s1
    assert host.merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed() == s1
    undone2 = host.undo_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_reshuffle()
    assert undone2 == 42
    # empty
    host._merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_history = []
    empty = host.undo_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_reshuffle()
    assert empty == host.merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed()
    ok('jitter 重抽历史栈')

    print(f'wave72 DONE pass={pass_n} fail={fail_n}')
    return 0 if fail_n == 0 else 1

if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as e:
        bad(f'exception · {e}')
        import traceback; traceback.print_exc()
        print(f'wave72 DONE pass={pass_n} fail={fail_n}')
        raise SystemExit(1)
