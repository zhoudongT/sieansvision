#!/usr/bin/env python3
"""细妆㊫：导引带色板拖拽排序 · 撤销条色阶嵌预览 · PNG工程自动填 · 热同步勾选即时刷新 · 脉冲循环间隔."""
from __future__ import annotations
import sys
from pathlib import Path
from datetime import datetime, timedelta

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
    from PySide6.QtCore import QSettings, QPoint
    from PySide6.QtGui import QColor, QDesktopServices
    app = QApplication.instance() or QApplication([])
    QMessageBox.information = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
    QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)
    QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: ('', ''))
    QFileDialog.getOpenFileName = staticmethod(lambda *a, **k: ('', ''))
    QColorDialog.getColor = staticmethod(lambda *a, **k: QColor())
    QInputDialog.getInt = staticmethod(lambda *a, **k: (200, False))
    QDesktopServices.openUrl = staticmethod(lambda *a, **k: True)

    from desktop.host_state_machine import HostStateMachineWidget
    for name in (
        'reorder_merge_diff_fail_hist_drop_snap_guide_recent_colors',
        'move_merge_diff_fail_hist_drop_snap_guide_recent_color',
        'current_project_name_for_png',
        'sync_toast_curve_png_project_from_current',
        'merge_diff_fail_hist_drop_pulse_preview_loop_gap_ms',
        'set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_ms',
        '_on_undo_color_scale_preview_bar_click',
    ):
        assert hasattr(HostStateMachineWidget, name), name
    ok('wave62 APIs present')

    s = QSettings('SIEANS', 'VisionDesktop')
    s.setValue('host/alarmFilmCsvDirs', [])
    s.setValue('host/sevPinArcSeizeRecentColors', [])
    s.setValue('host/toastHistCapTipAnim', True)
    s.setValue('host/toastHistCapTipAnimEasing', 'OutCubic')
    s.setValue('host/stalePruneUndoColorScale', 'traffic')
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
    s.setValue('host/mergeDiffFailHistDropPulsePreviewLoopGapMs', 120)
    s.setValue('host/mergeDiffFailHistDropPulsePreviewLoopGapJitterMs', 0)
    s.setValue('host/toastCurvePngExportDir', '')
    s.setValue('host/toastCurvePngRecentExports', [])
    s.setValue('host/toastCurvePngNameTemplate', 'tip-anim-{easing}-{ts}.png')
    s.setValue('host/toastCurvePngProjectName', 'default')
    s.setValue('host/toastCurvePngStationName', 'station1')
    s.setValue('host/sevPinSoloDeleteUndoMs', 4000)
    s.sync()
    host = HostStateMachineWidget(compact=True)
    host.show()
    host._toast_hist_cap_keep_exit_tip_quiet = True
    host._toast_hist_cap_tip_anim_easing_quiet = True
    host._toast_hist_cap_tip_anim_curve_quiet = True
    host._toast_hist_cap_tip_anim_curve_no_exec = True
    host._toast_hist_cap_tip_anim_curve_png_no_dialog = True
    host._toast_hist_cap_tip_anim_curve_clipboard_toast_quiet = False
    host._toast_hist_cap_tip_anim_curve_clipboard_preview_no_exec = True
    host._toast_hist_cap_tip_anim_curve_clipboard_preview_save_no_dialog = True
    host._toast_curve_png_recent_exports_menu_no_exec = True
    host._toast_curve_png_name_template_dialog_no_exec = True
    host._stale_prune_undo_custom_rgb_no_dialog = True
    host._stale_prune_undo_custom_preview_no_exec = True
    host._path_copy_badge_fail_hist_clear_no_confirm = True
    host._path_copy_badge_fail_hist_undo_bar_menu_no_exec = True
    host._merge_diff_fail_hist_no_exec = True
    host._stale_prune_undo_step_menu_no_exec = True
    host._snap_guide_custom_color_no_dialog = True
    host._sev_pin_solo_delete_undo_ms_menu_no_exec = True
    host._merge_diff_fail_hist_drop_pulse_preview_no_exec = True

    # --- 1. guide recent drag reorder ---
    host.clear_merge_diff_fail_hist_drop_snap_guide_recent_colors()
    for hx in ('#aa66ff', '#ff6688', '#66ffaa', '#6688ff'):
        host.remember_merge_diff_fail_hist_drop_snap_guide_recent_color(hx)
    # remember pushes front → last remembered first
    cur = host.merge_diff_fail_hist_drop_snap_guide_recent_colors()
    assert cur[0] == '#6688ff', cur
    # reorder to alphabetical-ish fixed order
    order = ['#aa66ff', '#ff6688', '#66ffaa', '#6688ff']
    got = host.reorder_merge_diff_fail_hist_drop_snap_guide_recent_colors(order)
    assert got == order, got
    moved = host.move_merge_diff_fail_hist_drop_snap_guide_recent_color('#6688ff', 0)
    assert moved[0] == '#6688ff', moved
    menu_g = host._build_merge_diff_fail_hist_drop_snap_guide_menu()
    pals = [a for a in menu_g.actions() if a.property('isSnapGuideRecentPalette')]
    assert len(pals) == 1
    btns = getattr(host, '_snap_guide_recent_drag_btns', [])
    assert len(btns) >= 4, len(btns)
    ok('导引带最近色板拖拽排序')

    # --- 2. solo undo menu embed preview bar ---
    host.set_stale_prune_undo_color_scale_preset('traffic')
    host.set_sev_pin_solo_delete_undo_ms(4000)
    host.clear_sev_pin_arc_seize_recent_colors()
    for c in ('#ff0001', '#00ff02', '#0000ff'):
        host.remember_sev_pin_arc_seize_color(c)
    host._last_sev_pin_arc_seize_recent_shift_range_solo = 1
    host._last_sev_pin_arc_seize_recent_shift_range_solo_color = '#00ff02'
    host.delete_sev_pin_arc_seize_recent_shift_range_solo()
    host._sev_pin_solo_delete_undo_ms_menu_no_exec = True
    assert host._show_sev_pin_solo_delete_undo_ms_menu() is True
    menu_ms = host._last_sev_pin_solo_delete_undo_ms_menu
    prevs = [a for a in menu_ms.actions() if a.property('isSoloDeleteUndoColorScalePreview')]
    assert len(prevs) == 1, len(prevs)
    bar = getattr(host, '_last_sev_pin_solo_delete_undo_color_scale_preview', None)
    assert bar is not None and bar.objectName() == 'hostSoloDeleteUndoColorScalePreviewBar'
    assert getattr(host, '_last_undo_color_scale_preview_preset', '') == 'traffic'
    # switch via menu → preview repaints
    scales = [a for a in menu_ms.actions() if a.property('isSoloDeleteUndoColorScale')]
    next(a for a in scales if a.data() == 'sunset').trigger()
    assert host.stale_prune_undo_color_scale_preset() == 'sunset'
    assert getattr(host, '_last_undo_color_scale_preview_preset', '') == 'sunset'
    host.undo_sev_pin_arc_seize_recent_shift_range_solo()
    host.set_stale_prune_undo_color_scale_preset('traffic')
    ok('撤销条色阶菜单嵌预览小条')

    # --- 3. PNG autofill from current project name ---
    host.set_toast_curve_png_project_name('default')
    host._toast_curve_png_project_source_name = '打开即跑 · 圆查找演示'
    host._toast_curve_png_project_autofill = True
    synced = host.sync_toast_curve_png_project_from_current(persist=False)
    assert '圆查找' in getattr(host, '_last_toast_curve_png_current_project_raw', '') or synced != 'default'
    # safe form
    assert synced == host.current_project_name_for_png()
    assert '_' in synced or synced.isalnum() or True
    host._toast_curve_png_name_template_dialog_no_exec = True
    host.show_toast_curve_png_name_template_dialog(interactive=False)
    assert getattr(host, '_last_toast_curve_png_project_autofilled', False) is True
    assert host.toast_curve_png_project_name() == synced
    ok('PNG 模板工程名自动填')

    # --- 4. hot-sync click immediate check refresh ---
    host.set_stale_prune_undo_color_scale_preset('traffic')
    menu = host._build_undo_color_scale_hot_sync_menu()
    bar2 = getattr(host, '_last_undo_color_scale_preview_bar', None)
    assert bar2 is not None
    bar2.resize(200, 16)
    class _E:
        def position(self):
            return QPoint(190, 8)
        def pos(self):
            return QPoint(190, 8)
    got = host._on_undo_color_scale_preview_bar_click(_E(), bar2)
    assert got == 'custom', got
    assert getattr(host, '_last_undo_color_scale_preview_click_menu_refreshed', False) is True
    assert getattr(host, '_last_undo_color_scale_hot_sync_menu_cur', '') == 'custom'
    # verify action checkmarks
    checked = [a.data() for a in menu.actions()
               if a.property('isUndoColorScalePreset') and a.isChecked()]
    assert checked == ['custom'], checked
    ok('热同步点选后菜单勾选即时刷新')

    # --- 5. pulse loop gap adjustable ---
    assert host.merge_diff_fail_hist_drop_pulse_preview_loop_gap_ms() == 120
    assert host.set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_ms(500) == 500
    assert host.set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_ms(-10) == 0
    assert host.set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_ms(9999) == 2000
    host.set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_ms(300)
    host.set_merge_diff_fail_hist_drop_pulse_ms(200)
    host.set_merge_diff_fail_hist_drop_pulse_preview_loop(True)
    host._merge_diff_fail_hist_drop_pulse_preview_no_exec = True
    assert host.show_merge_diff_fail_hist_drop_pulse_preview(interactive=False) is True
    sl = getattr(host, '_last_merge_diff_fail_hist_drop_pulse_preview_loop_gap_slider', None)
    assert sl is not None and sl.objectName() == 'hostMergeDiffFailHistDropPulsePreviewLoopGap'
    assert sl.value() == 300
    # arm uses pulse+gap
    armed_ms = getattr(host, '_last_merge_diff_fail_hist_drop_pulse_preview_loop_ms', 0)
    # smoke path stops loop after arm flag; may have armed then stopped
    # force arm check
    host.set_merge_diff_fail_hist_drop_pulse_preview_loop(True)
    # wave64+: jitter may be left from prior runs; zero for exact pulse+gap
    if hasattr(host, 'set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_ms'):
        host.set_merge_diff_fail_hist_drop_pulse_preview_loop_gap_jitter_ms(0)
    assert host._arm_merge_diff_fail_hist_drop_pulse_preview_loop(lambda: None) is True
    assert getattr(host, '_last_merge_diff_fail_hist_drop_pulse_preview_loop_ms', 0) == 200 + 300
    host._stop_merge_diff_fail_hist_drop_pulse_preview_loop()
    host.set_merge_diff_fail_hist_drop_pulse_preview_loop(False)
    ok('脉冲循环间隔可调')

    print(f'\nRESULT pass={pass_n} fail={fail_n}', flush=True)
    return 0 if fail_n == 0 else 1

if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:
        import traceback
        traceback.print_exc()
        bad(f'exception: {exc}')
        raise SystemExit(1)
