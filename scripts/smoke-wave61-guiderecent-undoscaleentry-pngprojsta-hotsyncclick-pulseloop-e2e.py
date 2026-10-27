#!/usr/bin/env python3
"""细妆㊪：导引带最近色板 · 撤销条色阶切换 · PNG项目/工位 · 热同步点选 · 脉冲循环."""
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
    from PySide6.QtCore import QSettings, Qt, QPoint, QEvent
    from PySide6.QtGui import QColor, QDesktopServices, QMouseEvent
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
        'merge_diff_fail_hist_drop_snap_guide_recent_colors',
        'remember_merge_diff_fail_hist_drop_snap_guide_recent_color',
        'clear_merge_diff_fail_hist_drop_snap_guide_recent_colors',
        'toast_curve_png_project_name',
        'set_toast_curve_png_project_name',
        'toast_curve_png_station_name',
        'set_toast_curve_png_station_name',
        '_on_undo_color_scale_preview_bar_click',
        'set_merge_diff_fail_hist_drop_pulse_preview_loop',
        'merge_diff_fail_hist_drop_pulse_preview_loop',
    ):
        assert hasattr(HostStateMachineWidget, name), name
    ok('wave61 APIs present')

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

    now = datetime.now()
    day0 = (now - timedelta(days=2)).strftime('%Y-%m-%d %H:%M:%S')
    day1 = (now - timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')
    day2 = now.strftime('%Y-%m-%d %H:%M:%S')

    # --- 1. guide recent color palette ---
    host.clear_merge_diff_fail_hist_drop_snap_guide_recent_colors()
    assert host.merge_diff_fail_hist_drop_snap_guide_recent_colors() == []
    host.set_merge_diff_fail_hist_drop_snap_guide_custom_hex('#aa66ff')
    recent = host.merge_diff_fail_hist_drop_snap_guide_recent_colors()
    assert recent and recent[0] == '#aa66ff', recent
    host.remember_merge_diff_fail_hist_drop_snap_guide_recent_color('#ff6688')
    recent = host.merge_diff_fail_hist_drop_snap_guide_recent_colors()
    assert recent[0] == '#ff6688' and '#aa66ff' in recent, recent
    host._merge_diff_batch_fail_history = [
        {'ts': day0, 'paths': ['/tmp/w61-d0/a']},
        {'ts': day1, 'paths': ['/tmp/w61-d1/b']},
        {'ts': day2, 'paths': ['/tmp/w61-d2/c']},
    ]
    host._merge_diff_fail_hist_collapsed = set()
    menu_g = host._build_merge_diff_fail_hist_drop_snap_guide_menu()
    pals = [a for a in menu_g.actions() if a.property('isSnapGuideRecentPalette')]
    assert len(pals) == 1, len(pals)
    host.set_merge_diff_fail_hist_drop_snap_guide_custom_hex('#ff6688')
    assert host.merge_diff_fail_hist_drop_snap_guide_preset() == 'custom'
    ok('导引带最近色板记忆')

    # --- 2. solo undo bar color scale switch entry ---
    host.set_stale_prune_undo_color_scale_preset('traffic')
    host.set_sev_pin_solo_delete_undo_ms(4000)
    host.clear_sev_pin_arc_seize_recent_colors()
    for c in ('#ff0001', '#00ff02', '#0000ff'):
        host.remember_sev_pin_arc_seize_color(c)
    host._last_sev_pin_arc_seize_recent_shift_range_solo = 1
    host._last_sev_pin_arc_seize_recent_shift_range_solo_color = '#00ff02'
    host.delete_sev_pin_arc_seize_recent_shift_range_solo()
    assert host._sev_pin_solo_delete_undo is not None
    host._sev_pin_solo_delete_undo_ms_menu_no_exec = True
    assert host._show_sev_pin_solo_delete_undo_ms_menu() is True
    menu_ms = host._last_sev_pin_solo_delete_undo_ms_menu
    scales = [a for a in menu_ms.actions() if a.property('isSoloDeleteUndoColorScale')]
    assert len(scales) == 5, len(scales)
    # trigger cool
    cool = next(a for a in scales if a.data() == 'cool')
    cool.trigger()
    assert host.stale_prune_undo_color_scale_preset() == 'cool'
    host._update_sev_pin_solo_delete_undo_bar()
    assert getattr(host, '_last_sev_pin_solo_delete_undo_bar_chunk_color', '').startswith('#')
    host.undo_sev_pin_arc_seize_recent_shift_range_solo()
    host.set_stale_prune_undo_color_scale_preset('traffic')
    ok('撤销条色阶预设切换入口')

    # --- 3. PNG project/station vars ---
    host.set_toast_curve_png_project_name('demoProj')
    host.set_toast_curve_png_station_name('工位A')
    assert host.toast_curve_png_project_name() == 'demoProj'
    assert host.toast_curve_png_station_name() == '___A' or 'A' in host.toast_curve_png_station_name()
    # Chinese chars become _; re-set ascii
    host.set_toast_curve_png_station_name('staA')
    host.set_toast_curve_png_name_template('{project}-{station}-{name}-{date}.png')
    resolved = host.resolve_toast_curve_png_name(
        name='tip', when=datetime(2026, 10, 28, 3, 21, 0))
    assert resolved == 'demoProj-staA-tip-20261028.png', resolved
    host._toast_curve_png_name_template_dialog_no_exec = True
    host._toast_curve_png_name_template_smoke = '{project}-{station}-{ts}.png'
    got = host.show_toast_curve_png_name_template_dialog(interactive=False)
    assert '{project}' in got and '{station}' in got
    ok('PNG 模板项目/工位变量')

    # --- 4. hot-sync preview bar clickable presets ---
    host.set_stale_prune_undo_color_scale_preset('traffic')
    menu = host._build_undo_color_scale_hot_sync_menu()
    bar = getattr(host, '_last_undo_color_scale_preview_bar', None)
    assert bar is not None
    bar.resize(200, 16)
    # click near right edge → custom (idx 4)
    class _E:
        def position(self):
            return QPoint(190, 8)
        def pos(self):
            return QPoint(190, 8)
    got = host._on_undo_color_scale_preview_bar_click(_E(), bar)
    assert got == 'custom', got
    assert getattr(host, '_last_undo_color_scale_preview_click_preset', '') == 'custom'
    # click near left → traffic
    class _E2:
        def position(self):
            return QPoint(5, 8)
        def pos(self):
            return QPoint(5, 8)
    assert host._on_undo_color_scale_preview_bar_click(_E2(), bar) == 'traffic'
    ok('热同步预览条可点选预设')

    # --- 5. pulse preview loop ---
    host.set_merge_diff_fail_hist_drop_pulse_ms(200)
    host.set_merge_diff_fail_hist_drop_pulse_easing('Linear')
    host.set_merge_diff_fail_hist_drop_pulse_intensity_pct(70)
    host.set_merge_diff_fail_hist_drop_pulse_preview_loop(True)
    assert host.merge_diff_fail_hist_drop_pulse_preview_loop() is True
    host._merge_diff_fail_hist_drop_pulse_preview_no_exec = True
    assert host.show_merge_diff_fail_hist_drop_pulse_preview(interactive=False) is True
    assert getattr(host, '_last_merge_diff_fail_hist_drop_pulse_preview_shown', False)
    assert getattr(host, '_last_merge_diff_fail_hist_drop_pulse_preview_pulsed', False)
    chk = getattr(host, '_last_merge_diff_fail_hist_drop_pulse_preview_loop_chk', None)
    assert chk is not None and chk.objectName() == 'hostMergeDiffFailHistDropPulsePreviewLoop'
    assert chk.isChecked() is True
    assert getattr(host, '_last_merge_diff_fail_hist_drop_pulse_preview_play_n', 0) >= 1
    assert getattr(host, '_last_merge_diff_fail_hist_drop_pulse_preview_loop_armed_smoke', False) is True
    host.set_merge_diff_fail_hist_drop_pulse_preview_loop(False)
    assert host.merge_diff_fail_hist_drop_pulse_preview_loop() is False
    ok('脉冲预览可循环播放')

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
