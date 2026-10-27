#!/usr/bin/env python3
"""细妆㊦：吸附预设可视化/脉冲时长 · 仅选快捷删色 · PNG另存再复制 · 热同步勾选实时 · α步进5/10/20."""
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
    from PySide6.QtGui import QColor, QPixmap
    app = QApplication.instance() or QApplication([])
    QMessageBox.information = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
    QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)
    QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: ('', ''))
    QFileDialog.getOpenFileName = staticmethod(lambda *a, **k: ('', ''))
    QColorDialog.getColor = staticmethod(lambda *a, **k: QColor())
    QInputDialog.getInt = staticmethod(lambda *a, **k: (200, False))

    from desktop.host_state_machine import HostStateMachineWidget
    for name in (
        'merge_diff_fail_hist_drop_snap_thresh',
        'set_merge_diff_fail_hist_drop_snap_thresh',
        'merge_diff_fail_hist_drop_pulse_ms',
        'set_merge_diff_fail_hist_drop_pulse_ms',
        '_ensure_merge_diff_fail_hist_drop_snap_guide',
        '_update_merge_diff_fail_hist_drop_snap_guide',
        'delete_sev_pin_arc_seize_recent_shift_range_solo',
        'export_toast_hist_cap_tip_anim_curve_clipboard_preview_png',
        'recopy_toast_hist_cap_tip_anim_curve_clipboard_preview',
        'refresh_undo_color_scale_hot_sync_menu',
        'stale_prune_undo_color_custom_alpha_step',
        'set_stale_prune_undo_color_custom_alpha_step',
        'cycle_stale_prune_undo_color_custom_alpha_step',
    ):
        assert hasattr(HostStateMachineWidget, name), name
    ok('wave57 APIs present')

    s = QSettings('SIEANS', 'VisionDesktop')
    s.setValue('host/alarmFilmCsvDirs', [])
    s.setValue('host/sevPinArcSeizeRecentColors', [])
    s.setValue('host/toastHistCapTipAnim', True)
    s.setValue('host/toastHistCapTipAnimEasing', 'OutCubic')
    s.setValue('host/stalePruneUndoColorScale', 'traffic')
    s.setValue('host/stalePruneUndoColorCustomHi', '#aa1122')
    s.setValue('host/stalePruneUndoColorCustomMid', '#bb3344')
    s.setValue('host/stalePruneUndoColorCustomLo', '#cc5566')
    s.setValue('host/stalePruneUndoColorCustomAlpha', 160)
    s.setValue('host/stalePruneUndoColorCustomAlphaStep', 10)
    s.setValue('host/mergeDiffBatchFailHistory', [])
    s.setValue('host/mergeDiffFailHistGroupOrder', [])
    s.setValue('host/mergeDiffFailHistCollapsed', [])
    s.setValue('host/mergeDiffFailHistDropSnapThresh', 18)
    s.setValue('host/mergeDiffFailHistDropPulseMs', 280)
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

    # --- 1. snap thresh viz + pulse ms ---
    assert host.merge_diff_fail_hist_drop_snap_thresh() == 18
    assert host.set_merge_diff_fail_hist_drop_snap_thresh(10) == 10
    assert host.merge_diff_fail_hist_drop_snap_thresh() == 10
    assert host.set_merge_diff_fail_hist_drop_snap_thresh(28) == 28
    assert host.set_merge_diff_fail_hist_drop_snap_thresh(18) == 18
    # nearest preset snap
    assert host.set_merge_diff_fail_hist_drop_snap_thresh(12) == 10
    assert host.set_merge_diff_fail_hist_drop_snap_thresh(18) == 18
    assert host.merge_diff_fail_hist_drop_pulse_ms() == 280
    assert host.set_merge_diff_fail_hist_drop_pulse_ms(420) == 420
    assert host.merge_diff_fail_hist_drop_pulse_ms() == 420
    host._merge_diff_batch_fail_history = [
        {'ts': day0, 'paths': ['/tmp/w57-d0/a']},
        {'ts': day1, 'paths': ['/tmp/w57-d1/b']},
        {'ts': day2, 'paths': ['/tmp/w57-d2/c']},
    ]
    host._merge_diff_fail_hist_collapsed = set()
    host._merge_diff_fail_hist_group_order = []
    assert host.show_merge_diff_batch_fail_history() is True
    # re-fetch after show (wave55 lesson)
    lst = host._last_merge_diff_batch_fail_history_list
    hl = host._ensure_merge_diff_fail_hist_drop_highlight(lst)
    guide = host._ensure_merge_diff_fail_hist_drop_snap_guide(lst)
    assert hl is not None and guide is not None
    assert guide.objectName() == 'hostMergeDiffFailHistDropSnapGuide'
    hdrs = []
    for i in range(lst.count()):
        it = lst.item(i)
        if it and it.data(Qt.ItemDataRole.UserRole + 3):
            hdrs.append(it)
    assert len(hdrs) >= 2
    r1 = lst.visualItemRect(hdrs[1])
    pos = QPoint(r1.center().x(), r1.center().y() + 6)
    host.set_merge_diff_fail_hist_drop_snap_thresh(18)
    target, gk = host._snap_merge_diff_fail_hist_drop_target(lst, pos)
    assert target is not None and gk
    host._last_merge_diff_fail_hist_drop_highlight_gk = None
    assert host._update_merge_diff_fail_hist_drop_highlight(lst, pos) is True
    assert getattr(host, '_last_merge_diff_fail_hist_drop_snap_guide_visible', False) is True
    assert getattr(host, '_last_merge_diff_fail_hist_drop_snap_guide_thresh', 0) == 18
    assert getattr(host, '_last_merge_diff_fail_hist_drop_highlight_pulse_ms', 0) == 420
    host.set_merge_diff_fail_hist_drop_pulse_ms(280)
    assert host._pulse_merge_diff_fail_hist_drop_highlight(hl) is True
    assert getattr(host, '_last_merge_diff_fail_hist_drop_highlight_pulse_ms', 0) == 280
    host._hide_merge_diff_fail_hist_drop_highlight(lst)
    assert getattr(host, '_last_merge_diff_fail_hist_drop_snap_guide_visible', True) is False
    ok('吸附预设可视化 / 脉冲时长可配')

    # --- 2. solo quick delete ---
    host.clear_sev_pin_arc_seize_recent_colors()
    for c in ('#ff0001', '#00ff02', '#0000ff', '#ffff04'):
        host.remember_sev_pin_arc_seize_color(c)
    drag = host._make_sev_pin_arc_seize_recent_drag_list()
    for i in range(min(3, drag.count())):
        drag.item(i).setSelected(True)
    assert host._update_sev_pin_arc_seize_recent_shift_range_bar(drag) is True
    chips = getattr(host, '_last_sev_pin_arc_seize_recent_shift_range_chips', [])
    assert len(chips) >= 2
    y0, y1, row0, col0 = chips[1]
    class _RE:
        def button(self):
            return Qt.MouseButton.RightButton
        def position(self):
            class _P:
                def y(self_inner):
                    return (y0 + y1) // 2
            return _P()
        def pos(self):
            return QPoint(2, (y0 + y1) // 2)
    assert host._on_sev_pin_arc_seize_recent_shift_range_bar_clicked(_RE(), drag) is True
    assert getattr(host, '_last_sev_pin_arc_seize_recent_shift_range_solo', None) == row0
    solo_color = getattr(host, '_last_sev_pin_arc_seize_recent_shift_range_solo_color', '')
    assert solo_color
    before = host.sev_pin_arc_seize_recent_colors()
    assert solo_color in before
    # second right-click same → quick delete
    assert host._on_sev_pin_arc_seize_recent_shift_range_bar_clicked(_RE(), drag) is True
    assert getattr(host, '_last_sev_pin_arc_seize_recent_shift_range_solo_deleted', '') == solo_color
    after = host.sev_pin_arc_seize_recent_colors()
    assert solo_color not in after
    assert len(after) == len(before) - 1
    # restore + API delete path
    host.remember_sev_pin_arc_seize_color('#aabbcc')
    host._last_sev_pin_arc_seize_recent_shift_range_solo = 0
    host._last_sev_pin_arc_seize_recent_shift_range_solo_color = '#aabbcc'
    got = host.delete_sev_pin_arc_seize_recent_shift_range_solo()
    assert '#aabbcc' not in got
    ok('右键仅选后快捷删色')

    # --- 3. PNG preview save / recopy ---
    host._toast_hist_cap_tip_anim_curve_no_exec = True
    assert host.show_toast_hist_cap_tip_anim_easing_curve_compare(
        'OutCubic', 'Linear') is True
    assert host.copy_toast_hist_cap_tip_anim_easing_curve_png_to_clipboard() is True
    host._toast_hist_cap_tip_anim_curve_clipboard_preview_no_exec = True
    assert host.show_toast_hist_cap_tip_anim_curve_clipboard_preview(
        interactive=False) is True
    save_btn = getattr(
        host, '_last_toast_hist_cap_tip_anim_curve_clipboard_preview_save_btn', None)
    recopy_btn = getattr(
        host, '_last_toast_hist_cap_tip_anim_curve_clipboard_preview_recopy_btn', None)
    assert save_btn is not None and recopy_btn is not None
    assert save_btn.objectName() == 'hostToastTipAnimEasingCurveClipboardPreviewSave'
    assert recopy_btn.objectName() == 'hostToastTipAnimEasingCurveClipboardPreviewRecopy'
    tmp = Path(tempfile.mkdtemp(prefix='w57-png-')) / 'curve.png'
    host._toast_hist_cap_tip_anim_curve_clipboard_preview_save_no_dialog = True
    host._toast_hist_cap_tip_anim_curve_clipboard_preview_save_path = str(tmp)
    saved = host.export_toast_hist_cap_tip_anim_curve_clipboard_preview_png(
        str(tmp), interactive=False)
    assert saved == str(tmp)
    assert tmp.is_file() and tmp.stat().st_size > 0
    assert getattr(host, '_last_toast_hist_cap_tip_anim_curve_clipboard_preview_saved', '') == str(tmp)
    # clear clipboard then recopy
    clip = QApplication.clipboard()
    clip.clear()
    assert host.recopy_toast_hist_cap_tip_anim_curve_clipboard_preview() is True
    assert getattr(host, '_last_toast_hist_cap_tip_anim_curve_clipboard_preview_recopied', False)
    rpm = clip.pixmap()
    assert rpm is not None and not rpm.isNull()
    recopy_btn.click()
    assert getattr(host, '_last_toast_hist_cap_tip_anim_curve_clipboard_preview_recopied', False)
    ok('PNG 预览窗另存/再复制')

    # --- 4. hot-sync live checkmarks ---
    host.set_stale_prune_undo_color_scale_preset('traffic')
    menu = host._build_undo_color_scale_hot_sync_menu()
    assert menu.objectName() == 'hostUndoColorScaleHotSyncMenu'
    assert host.refresh_undo_color_scale_hot_sync_menu(menu) is True
    assert getattr(host, '_last_undo_color_scale_hot_sync_menu_cur', '') == 'traffic'
    checked = [a for a in menu.actions()
               if a.property('isUndoColorScalePreset') and a.isChecked()]
    assert len(checked) == 1 and str(checked[0].data()) == 'traffic'
    assert '✓' in checked[0].text()
    host.set_stale_prune_undo_color_scale_preset('sunset')
    # set_preset should auto-refresh last menu
    assert getattr(host, '_last_undo_color_scale_hot_sync_menu_cur', '') == 'sunset'
    checked2 = [a for a in menu.actions()
                if a.property('isUndoColorScalePreset') and a.isChecked()]
    assert len(checked2) == 1 and str(checked2[0].data()) == 'sunset'
    assert '✓' in checked2[0].text()
    # traffic should lose checkmark
    traffic_act = [a for a in menu.actions()
                   if a.property('isUndoColorScalePreset') and str(a.data()) == 'traffic'][0]
    assert traffic_act.isChecked() is False
    assert '✓' not in traffic_act.text()
    host.set_stale_prune_undo_color_scale_preset('cool')
    assert host.refresh_undo_color_scale_hot_sync_menu() is True
    assert getattr(host, '_last_undo_color_scale_hot_sync_menu_refresh_n', 0) >= 5
    ok('热同步菜单勾选态实时刷新')

    # --- 5. α step 5/10/20 ---
    assert host.stale_prune_undo_color_custom_alpha_step() == 10
    assert host.set_stale_prune_undo_color_custom_alpha_step(5) == 5
    assert host.stale_prune_undo_color_custom_alpha_step() == 5
    assert host.set_stale_prune_undo_color_custom_alpha_step(20) == 20
    assert host.set_stale_prune_undo_color_custom_alpha_step(7) == 5  # nearest
    assert host.set_stale_prune_undo_color_custom_alpha_step(10) == 10
    host.set_stale_prune_undo_color_custom_alpha(160)
    assert host.adjust_stale_prune_undo_color_custom_alpha() == 170  # default +step
    assert host.adjust_stale_prune_undo_color_custom_alpha(-10) == 160
    assert host.cycle_stale_prune_undo_color_custom_alpha_step() == 20
    assert host.cycle_stale_prune_undo_color_custom_alpha_step() == 5
    assert host.cycle_stale_prune_undo_color_custom_alpha_step() == 10
    host.set_stale_prune_undo_color_custom_alpha_step(5)
    host.set_stale_prune_undo_color_custom_alpha(150)
    host._stale_prune_undo_custom_preview_no_exec = True
    assert host.show_stale_prune_undo_color_custom_preview(interactive=False) is True
    dec = host._last_stale_prune_undo_color_custom_alpha_dec_btn
    inc = host._last_stale_prune_undo_color_custom_alpha_inc_btn
    step_btn = host._last_stale_prune_undo_color_custom_alpha_step_btn
    assert dec is not None and inc is not None and step_btn is not None
    assert dec.text() == '−5'
    assert inc.text() == '+5'
    assert step_btn.objectName() == 'hostStalePruneUndoColorCustomAlphaStepCycle'
    spin = host._last_stale_prune_undo_color_custom_preview_spin
    assert spin.value() == 150
    inc.click()
    assert spin.value() == 155
    step_btn.click()
    assert host.stale_prune_undo_color_custom_alpha_step() == 10
    assert dec.text() == '−10'
    assert step_btn.text() == '步进±10'
    ok('α 步进可配 5/10/20')

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
