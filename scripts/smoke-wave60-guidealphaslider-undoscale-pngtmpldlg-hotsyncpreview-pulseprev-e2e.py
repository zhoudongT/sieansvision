#!/usr/bin/env python3
"""细妆㊩：导引带α连续滑条 · 撤销条色阶对齐 · PNG模板编辑对话框 · 热同步色阶预览条 · 脉冲预览小窗."""
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
    from PySide6.QtCore import QSettings
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
        'set_merge_diff_fail_hist_drop_snap_guide_alpha_pct',
        'merge_diff_fail_hist_drop_snap_guide_alpha_pct',
        'show_toast_curve_png_name_template_dialog',
        '_make_undo_color_scale_preview_bar',
        '_paint_undo_color_scale_preview_bar',
        'show_merge_diff_fail_hist_drop_pulse_preview',
    ):
        assert hasattr(HostStateMachineWidget, name), name
    ok('wave60 APIs present')

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
    s.setValue('host/toastCurvePngExportDir', '')
    s.setValue('host/toastCurvePngRecentExports', [])
    s.setValue('host/toastCurvePngNameTemplate', 'tip-anim-{easing}-{ts}.png')
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

    # --- 1. guide α continuous slider ---
    assert host.merge_diff_fail_hist_drop_snap_guide_alpha_pct() == 12
    assert host.set_merge_diff_fail_hist_drop_snap_guide_alpha_pct(15) == 15
    assert host.set_merge_diff_fail_hist_drop_snap_guide_alpha_pct(3) == 4  # clamp
    assert host.set_merge_diff_fail_hist_drop_snap_guide_alpha_pct(50) == 40
    assert host.set_merge_diff_fail_hist_drop_snap_guide_alpha_pct(8) == 8  # shortcut still
    host._merge_diff_batch_fail_history = [
        {'ts': day0, 'paths': ['/tmp/w60-d0/a']},
        {'ts': day1, 'paths': ['/tmp/w60-d1/b']},
        {'ts': day2, 'paths': ['/tmp/w60-d2/c']},
    ]
    host._merge_diff_fail_hist_collapsed = set()
    assert host.show_merge_diff_batch_fail_history() is True
    lst = host._last_merge_diff_batch_fail_history_list
    guide = host._ensure_merge_diff_fail_hist_drop_snap_guide(lst)
    host.set_merge_diff_fail_hist_drop_snap_guide_alpha_pct(18)
    assert host._apply_merge_diff_fail_hist_drop_snap_guide_style(guide) is True
    st = getattr(host, '_last_merge_diff_fail_hist_drop_snap_guide_style', {})
    assert st.get('alpha_pct') == 18
    menu_g = host._build_merge_diff_fail_hist_drop_snap_guide_menu()
    alphas = [a for a in menu_g.actions() if a.property('isSnapGuideAlpha')]
    sliders = [a for a in menu_g.actions() if a.property('isSnapGuideAlphaSlider')]
    assert len(alphas) == 3 and len(sliders) == 1
    sl = getattr(host, '_last_merge_diff_fail_hist_drop_snap_guide_alpha_slider', None)
    assert sl is not None and sl.objectName() == 'hostMergeDiffFailHistDropSnapGuideAlphaSlider'
    sl.setValue(25)
    assert host.merge_diff_fail_hist_drop_snap_guide_alpha_pct() == 25
    ok('导引带 α 连续滑条')

    # --- 2. solo delete undo bar color scale ---
    host.set_stale_prune_undo_color_scale_preset('traffic')
    host.set_sev_pin_solo_delete_undo_ms(4000)
    host.clear_sev_pin_arc_seize_recent_colors()
    for c in ('#ff0001', '#00ff02', '#0000ff'):
        host.remember_sev_pin_arc_seize_color(c)
    host._last_sev_pin_arc_seize_recent_shift_range_solo = 1
    host._last_sev_pin_arc_seize_recent_shift_range_solo_color = '#00ff02'
    host.delete_sev_pin_arc_seize_recent_shift_range_solo()
    assert host._sev_pin_solo_delete_undo is not None
    # near start → green-ish (ratio ~1.0)
    chunk_hi = getattr(host, '_last_sev_pin_solo_delete_undo_bar_chunk_color', '')
    assert chunk_hi in ('#3ecf8e', '#8fd46a'), chunk_hi
    # force low ratio → red
    host._sev_pin_solo_delete_undo_left_ms = 400  # 10% of 4000
    host._update_sev_pin_solo_delete_undo_bar()
    chunk_lo = getattr(host, '_last_sev_pin_solo_delete_undo_bar_chunk_color', '')
    assert chunk_lo == '#e35d6a', chunk_lo
    # mid → amber
    host._sev_pin_solo_delete_undo_left_ms = 1600  # 40%
    host._update_sev_pin_solo_delete_undo_bar()
    chunk_mid = getattr(host, '_last_sev_pin_solo_delete_undo_bar_chunk_color', '')
    assert chunk_mid == '#f0c040', chunk_mid
    host.undo_sev_pin_arc_seize_recent_shift_range_solo()
    ok('撤销条色阶对齐')

    # --- 3. PNG template edit dialog ---
    host._toast_curve_png_name_template_dialog_no_exec = True
    host._toast_curve_png_name_template_smoke = 'curve-{name}-{date}.png'
    got = host.show_toast_curve_png_name_template_dialog(interactive=False)
    assert got == 'curve-{name}-{date}.png'
    assert getattr(host, '_last_toast_curve_png_name_template_dialog_shown', False)
    resolved = host.resolve_toast_curve_png_name(
        name='tip', when=datetime(2026, 10, 28, 3, 19, 0))
    assert resolved == 'curve-tip-20261028.png', resolved
    mrec = host._build_toast_curve_png_recent_exports_menu()
    tmpls = [a for a in mrec.actions() if a.property('isToastCurvePngNameTemplateEdit')]
    assert len(tmpls) == 1
    host.set_toast_curve_png_name_template('tip-anim-{easing}-{ts}.png')
    ok('PNG 模板编辑对话框')

    # --- 4. hot-sync color scale preview bar ---
    host.set_stale_prune_undo_color_scale_preset('traffic')
    menu = host._build_undo_color_scale_hot_sync_menu()
    prevs = [a for a in menu.actions() if a.property('isUndoColorScalePreviewBar')]
    assert len(prevs) == 1
    bar = getattr(host, '_last_undo_color_scale_preview_bar', None)
    assert bar is not None and bar.objectName() == 'hostUndoColorScalePreviewBar'
    assert getattr(host, '_last_undo_color_scale_preview_preset', '') == 'traffic'
    hi = getattr(host, '_last_undo_color_scale_preview_hi', '')
    lo = getattr(host, '_last_undo_color_scale_preview_lo', '')
    assert hi in ('#3ecf8e', '#8fd46a') and lo == '#e35d6a'
    host.set_stale_prune_undo_color_scale_preset('cool')
    assert host.refresh_undo_color_scale_hot_sync_menu(menu) is True
    assert getattr(host, '_last_undo_color_scale_preview_preset', '') == 'cool'
    assert getattr(host, '_last_undo_color_scale_preview_hi', '').startswith('#')
    ok('热同步色阶预览条')

    # --- 5. pulse preview mini window ---
    host.set_merge_diff_fail_hist_drop_pulse_ms(200)
    host.set_merge_diff_fail_hist_drop_pulse_easing('Linear')
    host.set_merge_diff_fail_hist_drop_pulse_intensity_pct(70)
    host._merge_diff_fail_hist_drop_pulse_preview_no_exec = True
    assert host.show_merge_diff_fail_hist_drop_pulse_preview(interactive=False) is True
    assert getattr(host, '_last_merge_diff_fail_hist_drop_pulse_preview_shown', False)
    assert getattr(host, '_last_merge_diff_fail_hist_drop_pulse_preview_pulsed', False)
    pane = getattr(host, '_last_merge_diff_fail_hist_drop_pulse_preview_pane', None)
    assert pane is not None and pane.objectName() == 'hostMergeDiffFailHistDropPulsePreviewPane'
    assert getattr(host, '_last_merge_diff_fail_hist_drop_highlight_pulse_intensity', 0) == 70
    menu_g2 = host._build_merge_diff_fail_hist_drop_snap_guide_menu()
    pps = [a for a in menu_g2.actions() if a.property('isDropPulsePreview')]
    assert len(pps) == 1
    ok('脉冲预览小窗')

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
