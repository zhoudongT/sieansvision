#!/usr/bin/env python3
"""细妆㊤：组头落点高亮/折叠态保留 · Shift色块可点跳 · 曲线剪贴板toast · 徽章色阶对齐 · α旋钮默认."""
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
        'persist_merge_diff_batch_fail_history_collapsed',
        '_ensure_merge_diff_fail_hist_drop_highlight',
        '_update_merge_diff_fail_hist_drop_highlight',
        '_hide_merge_diff_fail_hist_drop_highlight',
        '_paint_sev_pin_arc_seize_recent_shift_range_chips',
        '_on_sev_pin_arc_seize_recent_shift_range_bar_clicked',
        'stale_prune_undo_color_custom_alpha_default',
        'copy_toast_hist_cap_tip_anim_easing_curve_png_to_clipboard',
    ):
        assert hasattr(HostStateMachineWidget, name), name
    ok('wave55 APIs present')

    s = QSettings('SIEANS', 'VisionDesktop')
    s.setValue('host/alarmFilmCsvDirs', [])
    s.setValue('host/alarmFilmCsvDir', '')
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
    host._toast_hist_cap_tip_anim_curve_clipboard_toast_quiet = True
    host._stale_prune_undo_custom_rgb_no_dialog = True
    host._stale_prune_undo_custom_preview_no_exec = True
    host._path_copy_badge_fail_hist_clear_no_confirm = True
    host._merge_diff_fail_hist_no_exec = True

    now = datetime.now()
    day0 = (now - timedelta(days=2)).strftime('%Y-%m-%d %H:%M:%S')
    day1 = (now - timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')
    day2 = now.strftime('%Y-%m-%d %H:%M:%S')
    g0, g1, g2 = day0[:10], day1[:10], day2[:10]

    # --- 1. drop highlight + fold persist ---
    host._merge_diff_batch_fail_history = [
        {'ts': day0, 'paths': ['/tmp/w55-d0/a']},
        {'ts': day1, 'paths': ['/tmp/w55-d1/b']},
        {'ts': day2, 'paths': ['/tmp/w55-d2/c']},
    ]
    host._merge_diff_fail_hist_collapsed = set()
    host._merge_diff_fail_hist_group_order = []
    assert host.show_merge_diff_batch_fail_history() is True
    lst = host._last_merge_diff_batch_fail_history_list
    assert lst is not None
    hl = host._ensure_merge_diff_fail_hist_drop_highlight(lst)
    assert hl is not None
    assert hl.objectName() == 'hostMergeDiffFailHistDropHighlight'
    # highlight first header
    hdr0 = None
    for i in range(lst.count()):
        it = lst.item(i)
        if it and it.data(Qt.ItemDataRole.UserRole + 3):
            hdr0 = it
            break
    assert hdr0 is not None
    rect = lst.visualItemRect(hdr0)
    pos = QPoint(rect.center().x(), rect.center().y())
    assert host._update_merge_diff_fail_hist_drop_highlight(lst, pos) is True
    assert getattr(host, '_last_merge_diff_fail_hist_drop_highlight_visible', False)
    gk_hl = getattr(host, '_last_merge_diff_fail_hist_drop_highlight_gk', '')
    assert gk_hl
    host._hide_merge_diff_fail_hist_drop_highlight(lst)
    assert getattr(host, '_last_merge_diff_fail_hist_drop_highlight_visible', True) is False
    # fold persist
    got = host.persist_merge_diff_batch_fail_history_collapsed({g0, g2})
    assert got == {g0, g2}
    raw = s.value('host/mergeDiffFailHistCollapsed', [])
    if isinstance(raw, str):
        import json
        raw = json.loads(raw) if raw.strip() else []
    assert set(str(x) for x in raw) == {g0, g2}
    # reorder keeps fold
    host.collapse_merge_diff_batch_fail_history_groups()  # all
    before = set(host._merge_diff_fail_hist_collapsed)
    host.reorder_merge_diff_batch_fail_history_groups([g2, g1, g0])
    host._merge_diff_fail_hist_collapsed = set(before)
    host.persist_merge_diff_batch_fail_history_collapsed(before)
    assert host.show_merge_diff_batch_fail_history() is True
    lst = host._last_merge_diff_batch_fail_history_list
    # all still collapsed → only headers
    child_n = 0
    for i in range(lst.count()):
        it = lst.item(i)
        if it and not it.data(Qt.ItemDataRole.UserRole + 3):
            child_n += 1
    assert child_n == 0, (child_n, lst.count(), host._merge_diff_fail_hist_collapsed)
    host.expand_merge_diff_batch_fail_history_groups()
    ok('组头落点高亮 / 折叠态保留')

    # --- 2. Shift chips + click jump ---
    host.clear_sev_pin_arc_seize_recent_colors()
    for c in ('#ff0001', '#00ff02', '#0000ff', '#ffff04'):
        host.remember_sev_pin_arc_seize_color(c)
    drag = host._make_sev_pin_arc_seize_recent_drag_list()
    drag.clearSelection()
    for i in range(min(3, drag.count())):
        drag.item(i).setSelected(True)
    assert host._update_sev_pin_arc_seize_recent_shift_range_bar(drag) is True
    chips = getattr(host, '_last_sev_pin_arc_seize_recent_shift_range_chips', [])
    assert len(chips) >= 2
    bar = host._ensure_sev_pin_arc_seize_recent_shift_range_bar(drag)
    assert bar.width() >= 8
    # click middle of first chip
    y0, y1, row0, col0 = chips[0]
    class _E:
        def button(self):
            return Qt.MouseButton.LeftButton
        def position(self):
            class _P:
                def y(self_inner):
                    return (y0 + y1) // 2
                def toPoint(self_inner):
                    return QPoint(2, (y0 + y1) // 2)
            return _P()
        def pos(self):
            return QPoint(2, (y0 + y1) // 2)
    assert host._on_sev_pin_arc_seize_recent_shift_range_bar_clicked(_E(), drag) is True
    assert getattr(host, '_last_sev_pin_arc_seize_recent_shift_range_jump', None) == row0
    ok('Shift 区间条 可点跳/色块')

    # --- 3. clipboard toast ---
    host._toast_hist_cap_tip_anim_curve_no_exec = True
    host._toast_hist_cap_tip_anim_curve_clipboard_toast_quiet = False
    assert host.show_toast_hist_cap_tip_anim_easing_curve_compare(
        'OutCubic', 'Linear') is True
    assert host.copy_toast_hist_cap_tip_anim_easing_curve_png_to_clipboard() is True
    toast = getattr(host, '_last_toast_hist_cap_tip_anim_curve_clipboard_toast', '')
    assert '剪贴板' in str(toast)
    assert getattr(host, '_last_toast_hist_cap_tip_anim_curve_clipboard_toast_shown', False) is True
    ok('曲线剪贴板后 toast')

    # --- 4. badge bar color-scale aligned ---
    host.set_stale_prune_undo_color_scale_preset('traffic')
    host._merge_diff_batch_fail_history = [
        {'ts': day2, 'paths': ['/tmp/w55-u/a']},
        {'ts': day0, 'paths': ['/tmp/w55-u/b']},
    ]
    host._path_copy_badge_fail_history_undo_ms = 4000
    try:
        host._path_copy_badge.setText('路径已复制')
        host._path_copy_badge.show()
    except Exception:
        pass
    host.clear_path_copy_badge_fail_history(confirm=False)
    host._path_copy_badge_fail_history_undo_left_ms = 4000
    host._update_path_copy_badge_fail_hist_undo_bar()
    c_hi = getattr(host, '_last_path_copy_badge_fail_hist_undo_bar_chunk_color', '')
    expect_hi = host._stale_prune_undo_bar_chunk_color(1.0)
    assert c_hi == expect_hi
    host._path_copy_badge_fail_history_undo_left_ms = 400
    host._update_path_copy_badge_fail_hist_undo_bar()
    c_lo = getattr(host, '_last_path_copy_badge_fail_hist_undo_bar_chunk_color', '')
    expect_lo = host._stale_prune_undo_bar_chunk_color(0.1)
    assert c_lo == expect_lo
    ok('徽章倒计时条 色阶对齐 undo')

    # --- 5. custom α UI knob default ---
    adef = host.stale_prune_undo_color_custom_alpha_default()
    assert adef == 160
    host.set_stale_prune_undo_color_custom_alpha(175)
    assert host.stale_prune_undo_color_custom_alpha_default() == 175
    host._stale_prune_undo_custom_preview_no_exec = True
    assert host.show_stale_prune_undo_color_custom_preview(interactive=False) is True
    spin = getattr(host, '_last_stale_prune_undo_color_custom_preview_spin', None)
    assert spin is not None and spin.value() == 175
    assert getattr(host, '_last_stale_prune_undo_color_custom_alpha_spin_default', 0) == 175
    ok('custom α 持久化 UI 旋钮默认')

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
