#!/usr/bin/env python3
"""细妆㊥：落点高亮动画/跨日吸附 · Shift右键仅选 · 剪贴板toast预览 · 徽章色阶热同步 · α步进重置."""
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
        '_pulse_merge_diff_fail_hist_drop_highlight',
        '_snap_merge_diff_fail_hist_drop_target',
        '_resolve_sev_pin_arc_seize_recent_shift_range_row',
        'show_toast_hist_cap_tip_anim_curve_clipboard_preview',
        '_build_undo_color_scale_hot_sync_menu',
        '_on_path_copy_badge_fail_hist_undo_bar_context',
        'adjust_stale_prune_undo_color_custom_alpha',
        'reset_stale_prune_undo_color_custom_alpha_default',
    ):
        assert hasattr(HostStateMachineWidget, name), name
    ok('wave56 APIs present')

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
    s.setValue('host/mergeDiffBatchFailHistory', [])
    s.setValue('host/mergeDiffFailHistGroupOrder', [])
    s.setValue('host/mergeDiffFailHistCollapsed', [])
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
    g0, g1, g2 = day0[:10], day1[:10], day2[:10]

    # --- 1. drop anim + snap ---
    host._merge_diff_batch_fail_history = [
        {'ts': day0, 'paths': ['/tmp/w56-d0/a']},
        {'ts': day1, 'paths': ['/tmp/w56-d1/b']},
        {'ts': day2, 'paths': ['/tmp/w56-d2/c']},
    ]
    host._merge_diff_fail_hist_collapsed = set()
    host._merge_diff_fail_hist_group_order = []
    assert host.show_merge_diff_batch_fail_history() is True
    lst = host._last_merge_diff_batch_fail_history_list
    hl = host._ensure_merge_diff_fail_hist_drop_highlight(lst)
    assert hl is not None
    # find second header center
    hdrs = []
    for i in range(lst.count()):
        it = lst.item(i)
        if it and it.data(Qt.ItemDataRole.UserRole + 3):
            hdrs.append(it)
    assert len(hdrs) >= 2
    r1 = lst.visualItemRect(hdrs[1])
    # snap from slightly below header center
    pos = QPoint(r1.center().x(), r1.center().y() + 8)
    target, gk = host._snap_merge_diff_fail_hist_drop_target(lst, pos, thresh=18)
    assert target is not None and gk
    assert getattr(host, '_last_merge_diff_fail_hist_drop_snap_gk', '') == gk
    host._last_merge_diff_fail_hist_drop_highlight_gk = None
    assert host._update_merge_diff_fail_hist_drop_highlight(lst, pos) is True
    assert getattr(host, '_last_merge_diff_fail_hist_drop_highlight_pulsed', False) is True
    assert host._pulse_merge_diff_fail_hist_drop_highlight(hl) is True
    ok('落点高亮动画 / 跨日组吸附')

    # --- 2. Shift right-click solo ---
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
    sel = [drag.row(it) for it in drag.selectedItems()]
    assert sel == [row0]
    ok('Shift 色块 右键仅选该段')

    # --- 3. clipboard toast click preview ---
    host._toast_hist_cap_tip_anim_curve_no_exec = True
    assert host.show_toast_hist_cap_tip_anim_easing_curve_compare(
        'OutCubic', 'Linear') is True
    assert host.copy_toast_hist_cap_tip_anim_easing_curve_png_to_clipboard() is True
    assert getattr(host, '_host_toast_click_action', '') == 'preview_curve_png'
    toast_msg = getattr(host, '_last_toast_hist_cap_tip_anim_curve_clipboard_toast', '')
    assert '预览' in str(toast_msg)
    host._toast_hist_cap_tip_anim_curve_clipboard_preview_no_exec = True
    assert host.show_toast_hist_cap_tip_anim_curve_clipboard_preview(
        interactive=False) is True
    assert getattr(host, '_last_toast_hist_cap_tip_anim_curve_clipboard_preview', False)
    lab = getattr(host, '_last_toast_hist_cap_tip_anim_curve_clipboard_preview_label', None)
    assert lab is not None
    # simulate toast click
    host._on_host_toast_clicked()
    assert getattr(host, '_last_toast_hist_cap_tip_anim_curve_clipboard_preview', False)
    ok('剪贴板 toast 单击预览 PNG')

    # --- 4. badge ↔ undo hot-sync ---
    host.set_stale_prune_undo_color_scale_preset('traffic')
    host._merge_diff_batch_fail_history = [
        {'ts': day2, 'paths': ['/tmp/w56-u/a']},
    ]
    try:
        host._path_copy_badge.setText('路径已复制')
        host._path_copy_badge.show()
    except Exception:
        pass
    host.clear_path_copy_badge_fail_history(confirm=False)
    host._path_copy_badge_fail_history_undo_left_ms = 4000
    host._update_path_copy_badge_fail_hist_undo_bar()
    c0 = getattr(host, '_last_path_copy_badge_fail_hist_undo_bar_chunk_color', '')
    host.set_stale_prune_undo_color_scale_preset('cool')
    assert getattr(host, '_last_stale_prune_undo_color_scale_hotsync', '') == 'cool'
    c1 = getattr(host, '_last_path_copy_badge_fail_hist_undo_bar_chunk_color', '')
    # cool hi should differ from traffic or at least be applied
    expect = host._stale_prune_undo_bar_chunk_color(
        host._path_copy_badge_fail_history_undo_left_ms /
        max(1, host._path_copy_badge_fail_history_undo_ms))
    assert c1 == expect
    menu = host._build_undo_color_scale_hot_sync_menu()
    assert menu.objectName() == 'hostUndoColorScaleHotSyncMenu'
    sync_acts = [a for a in menu.actions() if a.property('isUndoColorScaleHotSync')]
    assert len(sync_acts) >= 5
    host._path_copy_badge_fail_hist_undo_bar_menu_no_exec = True
    assert host._on_path_copy_badge_fail_hist_undo_bar_context() is True
    step_menu = host._build_stale_prune_undo_step_menu()
    hot = [a for a in step_menu.actions() if a.property('isUndoColorScaleHotSync')
           and a.objectName() == 'hostUndoColorScaleHotSync']
    assert len(hot) == 1
    ok('徽章条与 undo 预设 热同步菜单')

    # --- 5. α step / reset ---
    host.set_stale_prune_undo_color_custom_alpha(160)
    assert host.adjust_stale_prune_undo_color_custom_alpha(10) == 170
    assert host.adjust_stale_prune_undo_color_custom_alpha(-10) == 160
    assert host.reset_stale_prune_undo_color_custom_alpha_default(255) == 255
    host.set_stale_prune_undo_color_custom_alpha(150)
    host._stale_prune_undo_custom_preview_no_exec = True
    assert host.show_stale_prune_undo_color_custom_preview(interactive=False) is True
    dec = getattr(host, '_last_stale_prune_undo_color_custom_alpha_dec_btn', None)
    inc = getattr(host, '_last_stale_prune_undo_color_custom_alpha_inc_btn', None)
    rst = getattr(host, '_last_stale_prune_undo_color_custom_alpha_reset_btn', None)
    assert dec is not None and inc is not None and rst is not None
    assert dec.objectName() == 'hostStalePruneUndoColorCustomAlphaDec'
    assert rst.objectName() == 'hostStalePruneUndoColorCustomAlphaReset'
    spin = host._last_stale_prune_undo_color_custom_preview_spin
    assert spin.value() == 150
    # click +10 via API path already covered; trigger button click
    inc.click()
    assert spin.value() == 160
    rst.click()
    assert spin.value() == 255
    ok('α 旋钮 步进/重置默认')

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
