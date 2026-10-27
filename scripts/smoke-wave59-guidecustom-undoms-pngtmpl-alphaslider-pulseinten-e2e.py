#!/usr/bin/env python3
"""细妆㊨：导引带自定义色 · 撤销条可拖时长 · PNG命名模板 · 热同步α滑条 · 脉冲强度."""
from __future__ import annotations
import sys
import tempfile
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
    from PySide6.QtCore import QSettings, Qt, QPoint
    from PySide6.QtGui import QColor, QPixmap, QDesktopServices
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
        'merge_diff_fail_hist_drop_snap_guide_custom_hex',
        'set_merge_diff_fail_hist_drop_snap_guide_custom_hex',
        'prompt_merge_diff_fail_hist_drop_snap_guide_custom_color',
        'sev_pin_solo_delete_undo_ms',
        'set_sev_pin_solo_delete_undo_ms',
        '_show_sev_pin_solo_delete_undo_ms_menu',
        'toast_curve_png_name_template',
        'set_toast_curve_png_name_template',
        'resolve_toast_curve_png_name',
        'merge_diff_fail_hist_drop_pulse_intensity_pct',
        'set_merge_diff_fail_hist_drop_pulse_intensity_pct',
    ):
        assert hasattr(HostStateMachineWidget, name), name
    ok('wave59 APIs present')

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
    host._stale_prune_undo_custom_rgb_no_dialog = True
    host._stale_prune_undo_custom_preview_no_exec = True
    host._path_copy_badge_fail_hist_clear_no_confirm = True
    host._path_copy_badge_fail_hist_undo_bar_menu_no_exec = True
    host._merge_diff_fail_hist_no_exec = True
    host._stale_prune_undo_step_menu_no_exec = True
    host._snap_guide_custom_color_no_dialog = True
    host._sev_pin_solo_delete_undo_ms_menu_no_exec = True

    now = datetime.now()
    day0 = (now - timedelta(days=2)).strftime('%Y-%m-%d %H:%M:%S')
    day1 = (now - timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')
    day2 = now.strftime('%Y-%m-%d %H:%M:%S')

    # --- 1. guide custom color pick ---
    assert host.merge_diff_fail_hist_drop_snap_guide_preset() == 'green'
    assert host.merge_diff_fail_hist_drop_snap_guide_custom_hex() == '#3ecf8e'
    host._snap_guide_custom_color_smoke_pick = '#aa66ff'
    got = host.prompt_merge_diff_fail_hist_drop_snap_guide_custom_color()
    assert got == '#aa66ff'
    assert host.merge_diff_fail_hist_drop_snap_guide_preset() == 'custom'
    assert host._snap_guide_preset_hex() == '#aa66ff'
    assert host.set_merge_diff_fail_hist_drop_snap_guide_custom_hex('#ff8800') == '#ff8800'
    host._merge_diff_batch_fail_history = [
        {'ts': day0, 'paths': ['/tmp/w59-d0/a']},
        {'ts': day1, 'paths': ['/tmp/w59-d1/b']},
        {'ts': day2, 'paths': ['/tmp/w59-d2/c']},
    ]
    host._merge_diff_fail_hist_collapsed = set()
    assert host.show_merge_diff_batch_fail_history() is True
    lst = host._last_merge_diff_batch_fail_history_list
    guide = host._ensure_merge_diff_fail_hist_drop_snap_guide(lst)
    assert guide is not None
    assert host._apply_merge_diff_fail_hist_drop_snap_guide_style(guide) is True
    st = getattr(host, '_last_merge_diff_fail_hist_drop_snap_guide_style', {})
    assert st.get('hex') == '#ff8800'
    menu_g = host._build_merge_diff_fail_hist_drop_snap_guide_menu()
    picks = [a for a in menu_g.actions() if a.property('isSnapGuideCustomPick')]
    customs = [a for a in menu_g.actions()
               if a.property('isSnapGuidePreset') and str(a.data()) == 'custom']
    assert len(picks) == 1 and len(customs) == 1
    ok('导引带自定义色拾取')

    # --- 2. undo bar draggable duration ---
    assert host.sev_pin_solo_delete_undo_ms() == 4000
    assert host.set_sev_pin_solo_delete_undo_ms(6000) == 6000
    assert host.sev_pin_solo_delete_undo_ms() == 6000
    host.clear_sev_pin_arc_seize_recent_colors()
    for c in ('#ff0001', '#00ff02', '#0000ff'):
        host.remember_sev_pin_arc_seize_color(c)
    host._last_sev_pin_arc_seize_recent_shift_range_solo = 1
    host._last_sev_pin_arc_seize_recent_shift_range_solo_color = '#00ff02'
    host.delete_sev_pin_arc_seize_recent_shift_range_solo()
    assert host._sev_pin_solo_delete_undo is not None
    # remaining should start near 6000
    assert host._sev_pin_solo_delete_undo_left_ms >= 5500
    # rescale while armed
    left_before = host._sev_pin_solo_delete_undo_left_ms
    host.set_sev_pin_solo_delete_undo_ms(3000, rescale_left=True)
    assert host.sev_pin_solo_delete_undo_ms() == 3000
    assert host._sev_pin_solo_delete_undo_left_ms < left_before
    bar = host._ensure_sev_pin_solo_delete_undo_bar()
    assert bar is not None
    assert '滚轮' in (bar.toolTip() or '') or '拖' in (bar.toolTip() or '')
    host._sev_pin_solo_delete_undo_ms_menu_no_exec = True
    assert host._show_sev_pin_solo_delete_undo_ms_menu() is True
    mms = getattr(host, '_last_sev_pin_solo_delete_undo_ms_menu', None)
    assert mms is not None
    ms_acts = [a for a in mms.actions() if a.property('isSoloDeleteUndoMs')]
    assert len(ms_acts) == 5
    host.set_sev_pin_solo_delete_undo_ms(4000)
    host.undo_sev_pin_arc_seize_recent_shift_range_solo()
    ok('撤销条可拖时长')

    # --- 3. PNG naming template ---
    assert '{easing}' in host.toast_curve_png_name_template()
    assert host.set_toast_curve_png_name_template(
        'curve-{name}-{date}-{easing}.png') == 'curve-{name}-{date}-{easing}.png'
    host.set_toast_hist_cap_tip_anim_easing('OutBounce')
    resolved = host.resolve_toast_curve_png_name(
        easing='OutBounce', name='tip-anim',
        when=datetime(2026, 10, 28, 3, 15, 0))
    assert resolved == 'curve-tip-anim-20261028-OutBounce.png', resolved
    # default template with ts
    host.set_toast_curve_png_name_template('tip-anim-{easing}-{ts}.png')
    resolved2 = host.resolve_toast_curve_png_name(
        easing='Linear', when=datetime(2026, 10, 28, 12, 0, 0))
    assert resolved2 == 'tip-anim-Linear-20261028-120000.png', resolved2
    # export uses remembered dir + template (no dialog path override)
    host._toast_hist_cap_tip_anim_curve_no_exec = True
    assert host.show_toast_hist_cap_tip_anim_easing_curve_compare(
        'OutCubic', 'Linear') is True
    assert host.copy_toast_hist_cap_tip_anim_easing_curve_png_to_clipboard() is True
    tmpdir = Path(tempfile.mkdtemp(prefix='w59-png-'))
    outp = tmpdir / host.resolve_toast_curve_png_name(easing='OutCubic')
    host._toast_hist_cap_tip_anim_curve_clipboard_preview_save_no_dialog = True
    host._toast_hist_cap_tip_anim_curve_clipboard_preview_save_path = str(outp)
    assert host.export_toast_hist_cap_tip_anim_curve_clipboard_preview_png(
        str(outp), interactive=False) == str(outp)
    assert outp.exists()
    ok('PNG 导出命名模板')

    # --- 4. hot-sync α slider ---
    host.set_stale_prune_undo_color_custom_alpha(160)
    host.set_stale_prune_undo_color_scale_preset('traffic')
    menu = host._build_undo_color_scale_hot_sync_menu()
    slider_acts = [a for a in menu.actions() if a.property('isUndoColorAlphaSlider')]
    assert len(slider_acts) == 1
    slider = getattr(host, '_last_undo_color_alpha_slider', None)
    assert slider is not None
    assert slider.objectName() == 'hostUndoColorAlphaSlider'
    assert slider.value() == 160
    slider.setValue(200)
    assert host.stale_prune_undo_color_custom_rgb()['alpha'] == 200
    host.set_stale_prune_undo_color_custom_alpha(100)
    assert host.refresh_undo_color_scale_hot_sync_menu(menu) is True
    assert slider.value() == 100
    assert getattr(host, '_last_undo_color_scale_hot_sync_menu_alpha', -1) == 100
    ok('热同步 α 滑条')

    # --- 5. pulse intensity knob ---
    assert host.merge_diff_fail_hist_drop_pulse_intensity_pct() == 100
    assert host.set_merge_diff_fail_hist_drop_pulse_intensity_pct(60) == 60
    assert host.set_merge_diff_fail_hist_drop_pulse_intensity_pct(30) == 40  # clamp
    assert host.set_merge_diff_fail_hist_drop_pulse_intensity_pct(120) == 100
    host.set_merge_diff_fail_hist_drop_pulse_intensity_pct(50)
    hl = host._ensure_merge_diff_fail_hist_drop_highlight(lst)
    assert host._pulse_merge_diff_fail_hist_drop_highlight(hl) is True
    assert getattr(host, '_last_merge_diff_fail_hist_drop_highlight_pulse_intensity', 0) == 50
    vals = getattr(host, '_last_merge_diff_fail_hist_drop_highlight_pulse_vals', {})
    assert abs(vals.get('peak', 0) - 0.5) < 0.01
    assert abs(vals.get('start', 0) - 0.175) < 0.01
    # menu embeds intensity slider
    menu_g2 = host._build_merge_diff_fail_hist_drop_snap_guide_menu()
    inten_acts = [a for a in menu_g2.actions()
                  if a.property('isDropPulseIntensitySlider')]
    assert len(inten_acts) == 1
    sl_i = getattr(host, '_last_merge_diff_fail_hist_drop_pulse_intensity_slider', None)
    assert sl_i is not None and sl_i.objectName() == 'hostMergeDiffFailHistDropPulseIntensitySlider'
    sl_i.setValue(80)
    assert host.merge_diff_fail_hist_drop_pulse_intensity_pct() == 80
    ok('脉冲强度独立旋钮')

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
