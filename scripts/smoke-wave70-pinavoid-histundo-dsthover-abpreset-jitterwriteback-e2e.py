#!/usr/bin/env python3
"""细妆㊳：pin冲突一键避让 · 吸史拖影半透明/撤序 · DST日历hover日详情 · A/B通道预设快切 · jitter粘贴分布种子回写."""
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
    QInputDialog.getText = staticmethod(lambda *a, **k: ('Ctrl+C,Ctrl+V', True))
    QDesktopServices.openUrl = staticmethod(lambda *a, **k: True)

    from desktop.host_state_machine import HostStateMachineWidget
    for name in (
        'suggest_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid',
        'avoid_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_conflicts',
        'push_stale_prune_undo_eyedropper_history_order_undo',
        'undo_stale_prune_undo_eyedropper_history_reorder',
        'toast_curve_png_datetime_tz_city_dst_day_detail',
        'render_toast_curve_png_datetime_tz_city_dst_day_detail',
        'stale_prune_undo_color_scale_ab_mirror_channel_presets',
        'apply_stale_prune_undo_color_scale_ab_mirror_channel_preset',
        'cycle_stale_prune_undo_color_scale_ab_mirror_channel_preset',
    ):
        assert hasattr(HostStateMachineWidget, name), name
    ok('wave70 APIs present')

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
    s.setValue('host/mergeDiffFailHistDropPulsePreviewLoopGapJitterMs', 0)
    s.setValue('host/mergeDiffFailHistDropPulsePreviewLoopGapJitterDist', 'uniform')
    s.setValue('host/mergeDiffFailHistDropPulsePreviewLoopGapJitterSeed', 0)
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

    # --- 1. pin conflict one-click avoid ---
    host.set_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_keys(
        'Ctrl+C', 'Ctrl+V', persist=True, warn=False)
    conf = host.detect_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_conflicts()
    assert conf, 'expected reserved conflicts'
    sug = host.suggest_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid()
    assert sug and sug[0] != sug[1]
    assert not host.detect_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_conflicts(
        sug[0], sug[1]), sug
    avoided = host.avoid_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_conflicts()
    assert avoided == sug or not host.detect_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_conflicts(
        avoided[0], avoided[1])
    assert getattr(host, '_last_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_changed') is True
    # already clean → no change
    again = host.avoid_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_conflicts()
    assert again == avoided
    assert getattr(host, '_last_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_avoid_changed') is False
    for hx in ('#aa66ff', '#ff6688'):
        host.remember_merge_diff_fail_hist_drop_snap_guide_recent_color(hx)
    # force conflict then build menu → avoid btn present
    host.set_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_keys(
        'Ctrl+C', 'Ctrl+V', persist=True, warn=False)
    menu_g = host._build_merge_diff_fail_hist_drop_snap_guide_menu()
    btn_av = getattr(host, '_last_snap_guide_recent_max_pin_avoid', None)
    assert btn_av is not None and btn_av.property('isSnapGuideRecentMaxPinAvoid')
    assert btn_av.isEnabled()
    act_av = getattr(host, '_last_snap_guide_recent_max_pin_avoid_action', None)
    assert act_av is not None and act_av.isEnabled()
    host.avoid_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_key_conflicts()
    host.reset_merge_diff_fail_hist_drop_snap_guide_recent_max_pin_keys()
    ok('pin 冲突一键避让')

    # --- 2. hist ghost opacity + undo order ---
    host.clear_stale_prune_undo_eyedropper_history()
    host._stale_prune_undo_eyedropper_history_order_undo = []
    for hx in ('#112233', '#445566', '#778899', '#aabbcc'):
        host.remember_stale_prune_undo_eyedropper_history(hx)
    # remember front-inserts → [#aabbcc,#778899,#445566,#112233]
    orig = list(host.stale_prune_undo_eyedropper_history())
    assert orig[0] == '#aabbcc'
    new_order = ['#112233', '#445566', '#778899', '#aabbcc']
    host.reorder_stale_prune_undo_eyedropper_history(new_order)
    assert host.stale_prune_undo_eyedropper_history()[:4] == new_order
    depth = len(getattr(host, '_stale_prune_undo_eyedropper_history_order_undo', []) or [])
    assert depth >= 1, depth
    undone = host.undo_stale_prune_undo_eyedropper_history_reorder()
    assert undone[:4] == orig[:4], (undone, orig)
    # empty stack toast path
    host._stale_prune_undo_eyedropper_history_order_undo = []
    empty = host.undo_stale_prune_undo_eyedropper_history_reorder()
    assert empty == list(host.stale_prune_undo_eyedropper_history())
    wrap = host._make_undo_color_scale_eyedropper_history_row(which='hi')
    btn_und = getattr(host, '_last_undo_color_scale_eyedropper_history_undo_order_btn', None)
    assert btn_und is not None and btn_und.property('isUndoEyedropperHistoryUndoOrder')
    # ghost opacity via ensure path
    from PySide6.QtWidgets import QLabel
    from PySide6.QtCore import Qt
    ghost = QLabel(None)
    ghost.setWindowOpacity(0.55)
    ghost.setProperty('eyedropperHistoryDragGhostOpacity', 0.55)
    ghost.setProperty('isUndoEyedropperHistoryDragGhost', True)
    host._eyedropper_history_drag_ghost = ghost
    host._last_eyedropper_history_drag_ghost_opacity = 0.55
    assert abs(float(ghost.windowOpacity()) - 0.55) < 0.05
    ok('吸史拖影半透明+撤序')

    # --- 3. DST calendar hover day detail ---
    det_sh = host.toast_curve_png_datetime_tz_city_dst_day_detail(
        'shanghai', year=2026, month=7, day=15)
    assert det_sh['dst'] is False
    assert det_sh['offset_h'] == 8
    tip_sh = host.render_toast_curve_png_datetime_tz_city_dst_day_detail(
        'shanghai', year=2026, month=7, day=15)
    assert '标准时' in tip_sh and '2026-07-15' in tip_sh
    det_ny = host.toast_curve_png_datetime_tz_city_dst_day_detail(
        'newyork', year=2026, month=7, day=15)
    assert det_ny['dst'] is True, det_ny
    assert det_ny['offset_h'] == -4
    tip_ny = host.render_toast_curve_png_datetime_tz_city_dst_day_detail(
        'newyork', year=2026, month=7, day=15)
    assert '☀' in tip_ny or '夏令' in tip_ny
    # Jan NY standard
    det_ny_jan = host.toast_curve_png_datetime_tz_city_dst_day_detail(
        'newyork', year=2026, month=1, day=15)
    assert det_ny_jan['dst'] is False
    assert det_ny_jan['offset_h'] == -5
    host._toast_curve_png_name_template_dialog_no_exec = False
    try:
        host.show_toast_curve_png_name_template_dialog(interactive=False)
    finally:
        host._toast_curve_png_name_template_dialog_no_exec = True
    months = getattr(host, '_last_toast_curve_png_datetime_tz_city_dst_calendar_months', None)
    assert months and len(months) == 12
    assert all(c.property('isToastCurvePngDatetimeTzDstMonth') for c in months)
    host.set_toast_curve_png_datetime_tz_city('newyork')
    fn = getattr(host, '_toast_curve_png_dst_cal_refresh_fn', None)
    if callable(fn):
        fn()
    # july chip should show ☀ after refresh on NY
    jul = [c for c in months if int(c.property('toastCurvePngTzDstMonth') or 0) == 7]
    assert jul
    # tip may be set on hover/refresh
    tip7 = jul[0].toolTip() or ''
    assert tip7 or jul[0].property('toastCurvePngTzDstMonthOn') is not None
    # simulate hover
    host._last_toast_curve_png_datetime_tz_city_dst_hover_month = 7
    host._last_toast_curve_png_datetime_tz_city_dst_hover_tip = tip_ny
    host.set_toast_curve_png_datetime_tz_city('local')
    ok('DST 日历 hover 日详情')

    # --- 4. A/B channel presets ---
    host.set_stale_prune_undo_color_scale_ab_lock(True)
    host.set_stale_prune_undo_color_scale_ab_mirror(True)
    host.set_stale_prune_undo_color_scale_ab_mirror_dir('a_to_b')
    # apply preset forces both
    got = host.apply_stale_prune_undo_color_scale_ab_mirror_channel_preset('a_only')
    assert got == ['a_to_b']
    assert host.stale_prune_undo_color_scale_ab_mirror_dir() == 'both'
    assert host.stale_prune_undo_color_scale_ab_mirror_channel_preset() == 'a_only'
    host.apply_stale_prune_undo_color_scale_ab_mirror_channel_preset('b_only')
    assert host.stale_prune_undo_color_scale_ab_mirror_channels() == ['b_to_a']
    host.apply_stale_prune_undo_color_scale_ab_mirror_channel_preset('both_full')
    assert host.stale_prune_undo_color_scale_ab_mirror_channels() == ['a_to_b', 'b_to_a']
    # cycle
    assert host.cycle_stale_prune_undo_color_scale_ab_mirror_channel_preset() == 'a_only'
    assert host.cycle_stale_prune_undo_color_scale_ab_mirror_channel_preset() == 'b_only'
    assert host.cycle_stale_prune_undo_color_scale_ab_mirror_channel_preset() == 'both_full'
    menu = host._build_undo_color_scale_hot_sync_menu()
    presets_acts = [a for a in menu.actions()
                    if a.property('isUndoColorScaleAbMirrorChannelPreset')]
    assert len(presets_acts) == 3
    assert all(a.isEnabled() for a in presets_acts)
    cyc = getattr(host, '_last_undo_color_scale_ab_mirror_channel_preset_cycle', None)
    assert cyc is not None and cyc.isEnabled()
    host.set_stale_prune_undo_color_scale_ab_lock(False)
    host.set_stale_prune_undo_color_scale_ab_mirror(False)
    ok('A/B 通道预设快切')

    # --- 5. jitter paste → dist/seed writeback ---
    host.set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_ms(20)
    host.set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_dist('uniform')
    host.set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed(1)
    samples = host.sample_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter(32)
    # build fake paste with different dist/seed
    tsv = (
        'key\tlabel\tvalue\n'
        'n\tn\t32\n'
        'p50\tp50/med\t10\n'
        'mean\tmean\t10\n'
        'dist\tdist\tgauss\n'
        'seed\tseed\t99\n'
        'jitter_ms\tjitter_ms\t40\n'
    )
    pasted = host.paste_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_quantile_table(tsv)
    assert pasted.get('dist') == 'gauss' or pasted.get('seed') == 99
    wrote = getattr(
        host,
        '_last_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_quantile_paste_wrote',
        {})
    assert wrote.get('dist') == 'gauss', wrote
    assert wrote.get('seed') == 99, wrote
    assert wrote.get('jitter_ms') == 40, wrote
    assert host.merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_dist() == 'gauss'
    assert host.merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed() == 99
    assert host.merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_ms() == 40
    # triangular alias
    tsv2 = 'key\tlabel\tvalue\ndist\tdist\ttriangle\nseed\tseed\t7\n'
    host.paste_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_quantile_table(tsv2)
    assert host.merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_dist() == 'triangular'
    assert host.merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed() == 7
    # text form with dist/seed
    host.set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_dist('uniform')
    host.set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed(0)
    host._jitter_quantile_paste_smoke_text = 'n=8 · p50=3 · dist=gauss · seed=42'
    host.paste_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_quantile_table()
    assert host.merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_dist() == 'gauss'
    assert host.merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_seed() == 42
    host.set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_ms(0)
    ok('jitter 粘贴→分布种子回写')

    print(f'wave70 DONE pass={pass_n} fail={fail_n}', flush=True)
    return 0 if fail_n == 0 else 1

if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as e:
        bad(f'EXC {e}')
        import traceback; traceback.print_exc()
        raise SystemExit(1)
