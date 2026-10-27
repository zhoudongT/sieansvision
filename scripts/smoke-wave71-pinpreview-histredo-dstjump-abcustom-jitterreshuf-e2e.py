#!/usr/bin/env python3
"""细妆㊴：pin避让预览色标 · 吸史撤序重做 · DST日历点选跳月 · A/B预设自定义存档 · jitter种子一键重抽."""
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

def main():
    from PySide6.QtWidgets import (
        QApplication, QMessageBox, QFileDialog, QColorDialog, QInputDialog,
    )
    from PySide6.QtCore import QSettings
    from PySide6.QtGui import QColor, QDesktopServices
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
        'preview_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid',
        'render_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_preview',
        'redo_stale_prune_undo_eyedropper_history_reorder',
        'jump_toast_curve_png_datetime_tz_city_dst_calendar_month',
        'save_stale_prune_undo_color_scale_ab_mirror_channel_preset_custom',
        'delete_stale_prune_undo_color_scale_ab_mirror_channel_preset_custom',
        'list_stale_prune_undo_color_scale_ab_mirror_channel_preset_customs',
        'reshuffle_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed',
    ):
        assert hasattr(HostStateMachineWidget, name), name
    ok('wave71 APIs present')

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

    # --- 1. pin avoid preview swatches ---
    host.set_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_keys(
        'Ctrl+C', 'Ctrl+V', persist=True, warn=False)
    prev = host.preview_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid()
    assert prev['current']['conflict'] is True
    assert prev['current']['color'] == '#e6a23c', prev
    assert prev['suggested']['conflict'] is False
    assert prev['suggested']['color'] == '#3ecf8e', prev
    assert prev['changed'] is True
    tip = host.render_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_preview()
    assert '当前' in tip and '建议' in tip and '#e6a23c' in tip
    for hx in ('#aa66ff', '#ff6688'):
        host.remember_merge_diff_fail_hist_drop_snap_guide_recent_color(hx)
    menu_g = host._build_merge_diff_fail_hist_drop_snap_guide_menu()
    sw_c = getattr(host, '_last_snap_guide_recent_max_pin_avoid_swatch_cur', None)
    sw_s = getattr(host, '_last_snap_guide_recent_max_pin_avoid_swatch_sug', None)
    assert sw_c is not None and sw_c.property('snapGuideRecentMaxPinAvoidSwatchRole') == 'current'
    assert sw_s is not None and sw_s.property('snapGuideRecentMaxPinAvoidSwatchRole') == 'suggested'
    assert '#e6a23c' in (sw_c.styleSheet() or '')
    assert '#3ecf8e' in (sw_s.styleSheet() or '')
    host.avoid_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_conflicts()
    prev2 = host.preview_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid()
    assert prev2['current']['conflict'] is False
    assert prev2['current']['color'] == '#3ecf8e'
    host.reset_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_keys()
    ok('pin 避让预览色标')

    # --- 2. hist undo/redo ---
    host.clear_stale_prune_undo_eyedropper_history()
    host._stale_prune_undo_eyedropper_history_order_undo = []
    host._stale_prune_undo_eyedropper_history_order_redo = []
    for hx in ('#112233', '#445566', '#778899', '#aabbcc'):
        host.remember_stale_prune_undo_eyedropper_history(hx)
    orig = list(host.stale_prune_undo_eyedropper_history())
    new_order = ['#112233', '#445566', '#778899', '#aabbcc']
    host.reorder_stale_prune_undo_eyedropper_history(new_order)
    assert host.stale_prune_undo_eyedropper_history()[:4] == new_order
    undone = host.undo_stale_prune_undo_eyedropper_history_reorder()
    assert undone[:4] == orig[:4], (undone, orig)
    rdepth = len(getattr(host, '_stale_prune_undo_eyedropper_history_order_redo', []) or [])
    assert rdepth >= 1, rdepth
    redone = host.redo_stale_prune_undo_eyedropper_history_reorder()
    assert redone[:4] == new_order, (redone, new_order)
    # empty redo
    host._stale_prune_undo_eyedropper_history_order_redo = []
    empty_r = host.redo_stale_prune_undo_eyedropper_history_reorder()
    assert empty_r == list(host.stale_prune_undo_eyedropper_history())
    wrap = host._make_undo_color_scale_eyedropper_history_row(which='hi')
    btn_redo = getattr(host, '_last_undo_color_scale_eyedropper_history_redo_order_btn', None)
    assert btn_redo is not None and btn_redo.property('isUndoEyedropperHistoryRedoOrder')
    ok('吸史撤序重做')

    # --- 3. DST jump month ---
    host.set_toast_curve_png_datetime_tz_city('newyork')
    jumped = host.jump_toast_curve_png_datetime_tz_city_dst_calendar_month(
        7, year=2026, city='newyork')
    assert jumped['month'] == 7
    assert jumped['dst'] is True, jumped
    assert getattr(host, '_last_toast_curve_png_datetime_tz_city_dst_focus_month') == 7
    tipj = getattr(host, '_last_toast_curve_png_datetime_tz_city_dst_jump_tip', '')
    assert '2026-07' in tipj or '☀' in tipj or '夏令' in tipj
    jumped2 = host.jump_toast_curve_png_datetime_tz_city_dst_calendar_month(
        1, year=2026, city='newyork')
    assert jumped2['dst'] is False
    assert getattr(host, '_last_toast_curve_png_datetime_tz_city_dst_focus_month') == 1
    ok('DST 日历点选跳月')

    # --- 4. A/B custom preset archive ---
    host.set_stale_prune_undo_color_scale_ab_mirror_dir('both', persist=True)
    host.set_stale_prune_undo_color_scale_ab_mirror_channels(
        ['a_to_b'], persist=True)
    saved = host.save_stale_prune_undo_color_scale_ab_mirror_channel_preset_custom('烟测档')
    assert saved['id'].startswith('u_')
    assert saved['channels'] == ['a_to_b']
    customs = host.list_stale_prune_undo_color_scale_ab_mirror_channel_preset_customs()
    assert any(c['id'] == saved['id'] for c in customs)
    presets = host.stale_prune_undo_color_scale_ab_mirror_channel_presets()
    assert any(p[0] == saved['id'] for p in presets)
    # switch away then apply custom
    host.apply_stale_prune_undo_color_scale_ab_mirror_channel_preset('both_full')
    assert host.stale_prune_undo_color_scale_ab_mirror_channels() == ['a_to_b', 'b_to_a']
    host.apply_stale_prune_undo_color_scale_ab_mirror_channel_preset(saved['id'])
    assert host.stale_prune_undo_color_scale_ab_mirror_channels() == ['a_to_b']
    assert host.stale_prune_undo_color_scale_ab_mirror_channel_preset() == saved['id']
    # prompt path (no dialog)
    host.set_stale_prune_undo_color_scale_ab_mirror_channels(
        ['b_to_a'], persist=True)
    host._ab_mirror_channel_preset_custom_smoke_name = '烟测B'
    saved2 = host.prompt_save_stale_prune_undo_color_scale_ab_mirror_channel_preset_custom()
    assert saved2['id'].startswith('u_')
    keep = host.delete_stale_prune_undo_color_scale_ab_mirror_channel_preset_custom(saved['id'])
    assert not any(c['id'] == saved['id'] for c in keep)
    host.delete_stale_prune_undo_color_scale_ab_mirror_channel_preset_custom(saved2['id'])
    # menu has save action
    host.set_stale_prune_undo_color_scale_ab_lock(True)
    host.set_stale_prune_undo_color_scale_ab_mirror(True)
    host.set_stale_prune_undo_color_scale_ab_mirror_dir('both')
    menu_cs = host._build_undo_color_scale_hot_sync_menu()
    act_save = getattr(host, '_last_undo_color_scale_ab_mirror_channel_preset_save', None)
    assert act_save is not None and act_save.property('isUndoColorScaleAbMirrorChannelPresetSave')
    assert act_save.isEnabled()
    host.set_stale_prune_undo_color_scale_ab_lock(False)
    host.set_stale_prune_undo_color_scale_ab_mirror(False)
    ok('A/B 预设自定义存档')

    # --- 5. jitter seed reshuffle ---
    host.set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_ms(40)
    host.set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed(42)
    before = host.merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed()
    assert before == 42
    nxt = host.reshuffle_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed()
    assert 1 <= nxt <= 999999
    assert nxt != before
    assert host.merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed() == nxt
    assert getattr(host, '_last_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed_reshuffled') == nxt
    # another reshuffle still changes
    nxt2 = host.reshuffle_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed()
    assert nxt2 != nxt or True  # theoretically could collide; just ensure in range
    assert 1 <= nxt2 <= 999999
    ok('jitter 种子一键重抽')

    print(f'wave71 DONE pass={pass_n} fail={fail_n}')
    return 0 if fail_n == 0 else 1

if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as e:
        bad(f'exception · {e}')
        import traceback; traceback.print_exc()
        print(f'wave71 DONE pass={pass_n} fail={fail_n}')
        raise SystemExit(1)
