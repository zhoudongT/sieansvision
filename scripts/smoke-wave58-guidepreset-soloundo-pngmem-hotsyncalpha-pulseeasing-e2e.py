#!/usr/bin/env python3
"""细妆㊧：导引带色/透明度预设 · 仅选删色短撤销 · PNG目录记忆/最近导出 · 热同步α步进 · 脉冲缓动."""
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
        'merge_diff_fail_hist_drop_snap_guide_preset',
        'set_merge_diff_fail_hist_drop_snap_guide_preset',
        'merge_diff_fail_hist_drop_snap_guide_alpha_pct',
        'set_merge_diff_fail_hist_drop_snap_guide_alpha_pct',
        '_build_merge_diff_fail_hist_drop_snap_guide_menu',
        'undo_sev_pin_arc_seize_recent_shift_range_solo',
        '_arm_sev_pin_solo_delete_undo',
        'toast_curve_png_export_dir',
        'remember_toast_curve_png_export',
        'toast_curve_png_recent_exports',
        'clear_toast_curve_png_recent_exports',
        'merge_diff_fail_hist_drop_pulse_easing',
        'set_merge_diff_fail_hist_drop_pulse_easing',
    ):
        assert hasattr(HostStateMachineWidget, name), name
    ok('wave58 APIs present')

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
    s.setValue('host/mergeDiffFailHistDropSnapGuidePreset', 'green')
    s.setValue('host/mergeDiffFailHistDropSnapGuideAlphaPct', 12)
    s.setValue('host/toastCurvePngExportDir', '')
    s.setValue('host/toastCurvePngRecentExports', [])
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

    now = datetime.now()
    day0 = (now - timedelta(days=2)).strftime('%Y-%m-%d %H:%M:%S')
    day1 = (now - timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')
    day2 = now.strftime('%Y-%m-%d %H:%M:%S')

    # --- 1. guide preset / alpha + menu ---
    assert host.merge_diff_fail_hist_drop_snap_guide_preset() == 'green'
    assert host.set_merge_diff_fail_hist_drop_snap_guide_preset('amber') == 'amber'
    assert host._snap_guide_preset_hex() == '#f0c040'
    assert host.set_merge_diff_fail_hist_drop_snap_guide_alpha_pct(20) == 20
    assert host.set_merge_diff_fail_hist_drop_snap_guide_preset('soft') == 'soft'
    assert host.merge_diff_fail_hist_drop_snap_guide_alpha_pct() == 8
    assert host.set_merge_diff_fail_hist_drop_snap_guide_preset('cyan') == 'cyan'
    assert host.set_merge_diff_fail_hist_drop_snap_guide_alpha_pct(12) == 12
    host._merge_diff_batch_fail_history = [
        {'ts': day0, 'paths': ['/tmp/w58-d0/a']},
        {'ts': day1, 'paths': ['/tmp/w58-d1/b']},
        {'ts': day2, 'paths': ['/tmp/w58-d2/c']},
    ]
    host._merge_diff_fail_hist_collapsed = set()
    assert host.show_merge_diff_batch_fail_history() is True
    lst = host._last_merge_diff_batch_fail_history_list
    guide = host._ensure_merge_diff_fail_hist_drop_snap_guide(lst)
    assert guide is not None
    assert host._apply_merge_diff_fail_hist_drop_snap_guide_style(guide) is True
    st = getattr(host, '_last_merge_diff_fail_hist_drop_snap_guide_style', {})
    assert st.get('hex') == '#40c0f0'
    assert st.get('alpha_pct') == 12
    menu_g = host._build_merge_diff_fail_hist_drop_snap_guide_menu()
    assert menu_g.objectName() == 'hostMergeDiffFailHistDropSnapGuideMenu'
    presets = [a for a in menu_g.actions() if a.property('isSnapGuidePreset')]
    alphas = [a for a in menu_g.actions() if a.property('isSnapGuideAlpha')]
    easings = [a for a in menu_g.actions() if a.property('isDropPulseEasing')]
    assert len(presets) == 5 and len(alphas) == 3 and len(easings) == 4
    ok('吸附导引带透明度/颜色预设菜单')

    # --- 2. solo delete short undo ---
    host.clear_sev_pin_arc_seize_recent_colors()
    for c in ('#ff0001', '#00ff02', '#0000ff'):
        host.remember_sev_pin_arc_seize_color(c)
    host._last_sev_pin_arc_seize_recent_shift_range_solo = 1
    host._last_sev_pin_arc_seize_recent_shift_range_solo_color = '#00ff02'
    before = host.sev_pin_arc_seize_recent_colors()
    assert '#00ff02' in before
    host.delete_sev_pin_arc_seize_recent_shift_range_solo()
    assert '#00ff02' not in host.sev_pin_arc_seize_recent_colors()
    assert getattr(host, '_last_sev_pin_solo_delete_undo_armed', '') == '#00ff02'
    assert getattr(host, '_host_toast_click_action', '') == 'undo_solo_delete'
    assert host._sev_pin_solo_delete_undo is not None
    assert host._sev_pin_solo_delete_undo_left_ms > 0
    bar = getattr(host, '_sev_pin_solo_delete_undo_bar', None)
    assert bar is not None and bar.objectName() == 'hostSevPinSoloDeleteUndoBar'
    assert getattr(host, '_last_sev_pin_solo_delete_undo_bar_shown', False)
    # undo via API
    restored = host.undo_sev_pin_arc_seize_recent_shift_range_solo()
    assert '#00ff02' in restored
    assert getattr(host, '_last_sev_pin_solo_delete_undo_restored', '') == '#00ff02'
    assert host._sev_pin_solo_delete_undo is None
    # toast click path
    host._last_sev_pin_arc_seize_recent_shift_range_solo_color = '#ff0001'
    host._last_sev_pin_arc_seize_recent_shift_range_solo = 0
    host.delete_sev_pin_arc_seize_recent_shift_range_solo()
    assert '#ff0001' not in host.sev_pin_arc_seize_recent_colors()
    host._on_host_toast_clicked()
    assert '#ff0001' in host.sev_pin_arc_seize_recent_colors()
    ok('仅选删色撤销条（短 undo）')

    # --- 3. PNG dir memory + recent ---
    host._toast_hist_cap_tip_anim_curve_no_exec = True
    assert host.show_toast_hist_cap_tip_anim_easing_curve_compare(
        'OutCubic', 'Linear') is True
    assert host.copy_toast_hist_cap_tip_anim_easing_curve_png_to_clipboard() is True
    host._toast_hist_cap_tip_anim_curve_clipboard_preview_no_exec = True
    assert host.show_toast_hist_cap_tip_anim_curve_clipboard_preview(
        interactive=False) is True
    recent_btn = getattr(
        host, '_last_toast_hist_cap_tip_anim_curve_clipboard_preview_recent_btn', None)
    assert recent_btn is not None
    assert recent_btn.objectName() == 'hostToastTipAnimEasingCurveClipboardPreviewRecent'
    tmpdir = Path(tempfile.mkdtemp(prefix='w58-png-'))
    p1 = tmpdir / 'a.png'
    p2 = tmpdir / 'b.png'
    host._toast_hist_cap_tip_anim_curve_clipboard_preview_save_no_dialog = True
    host._toast_hist_cap_tip_anim_curve_clipboard_preview_save_path = str(p1)
    assert host.export_toast_hist_cap_tip_anim_curve_clipboard_preview_png(
        str(p1), interactive=False) == str(p1)
    assert host.toast_curve_png_export_dir() == str(tmpdir)
    assert str(p1) in host.toast_curve_png_recent_exports()
    host.export_toast_hist_cap_tip_anim_curve_clipboard_preview_png(
        str(p2), interactive=False)
    recent = host.toast_curve_png_recent_exports()
    assert recent[0] == str(p2) and str(p1) in recent
    mrec = host._build_toast_curve_png_recent_exports_menu()
    assert mrec.objectName() == 'hostToastCurvePngRecentExportsMenu'
    items = [a for a in mrec.actions() if a.property('isToastCurvePngRecentExport')]
    assert len(items) >= 2
    host.clear_toast_curve_png_recent_exports()
    assert host.toast_curve_png_recent_exports() == []
    ok('PNG 另存默认目录记忆 + 最近导出清单')

    # --- 4. hot-sync α step shortcuts ---
    host.set_stale_prune_undo_color_custom_alpha_step(10)
    host.set_stale_prune_undo_color_scale_preset('traffic')
    menu = host._build_undo_color_scale_hot_sync_menu()
    step_acts = [a for a in menu.actions() if a.property('isUndoColorAlphaStep')]
    adj_acts = [a for a in menu.actions() if a.property('isUndoColorAlphaAdjust')]
    assert len(step_acts) == 3 and len(adj_acts) == 2
    checked = [a for a in step_acts if a.isChecked()]
    assert len(checked) == 1 and int(checked[0].data()) == 10
    host.set_stale_prune_undo_color_custom_alpha_step(5)
    assert host.refresh_undo_color_scale_hot_sync_menu(menu) is True
    assert getattr(host, '_last_undo_color_scale_hot_sync_menu_alpha_step', 0) == 5
    checked5 = [a for a in step_acts if a.isChecked()]
    assert len(checked5) == 1 and int(checked5[0].data()) == 5
    assert '✓' in checked5[0].text()
    # adjust actions reflect step
    assert any('5' in a.text() for a in adj_acts)
    host.set_stale_prune_undo_color_custom_alpha(150)
    host.adjust_stale_prune_undo_color_custom_alpha(5)
    assert host.stale_prune_undo_color_custom_rgb()['alpha'] == 155
    ok('热同步菜单内嵌 α 步进快捷项')

    # --- 5. pulse easing ---
    assert host.merge_diff_fail_hist_drop_pulse_easing() == 'OutCubic'
    assert host.set_merge_diff_fail_hist_drop_pulse_easing('OutBounce') == 'OutBounce'
    assert host.set_merge_diff_fail_hist_drop_pulse_easing('InOutQuad') == 'InOutQuad'
    assert host.set_merge_diff_fail_hist_drop_pulse_easing('bogus') == 'OutCubic'
    host.set_merge_diff_fail_hist_drop_pulse_easing('Linear')
    hl = host._ensure_merge_diff_fail_hist_drop_highlight(lst)
    assert host._pulse_merge_diff_fail_hist_drop_highlight(hl) is True
    assert getattr(host, '_last_merge_diff_fail_hist_drop_highlight_pulse_easing', '') == 'Linear'
    # align names with toast
    for ez in ('OutCubic', 'InOutQuad', 'OutBounce', 'Linear'):
        host.set_merge_diff_fail_hist_drop_pulse_easing(ez)
        assert host.merge_diff_fail_hist_drop_pulse_easing() == ez
        host.set_toast_hist_cap_tip_anim_easing(ez)
        assert host.toast_hist_cap_tip_anim_easing() == ez
    ok('脉冲 easing 曲线可选（对齐 toast easing）')

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
