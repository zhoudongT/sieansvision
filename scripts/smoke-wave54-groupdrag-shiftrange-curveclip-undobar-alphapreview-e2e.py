#!/usr/bin/env python3
"""细妆㊣：失败历史组头拖拽重排 · Shift连选区间条 · 曲线PNG剪贴板 · 徽章撤销倒计时条 · undo色阶α/渐变预览."""
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
    from PySide6.QtCore import QSettings, Qt, QEvent
    from PySide6.QtGui import QKeyEvent, QColor, QPixmap
    app = QApplication.instance() or QApplication([])
    QMessageBox.information = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
    QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)
    QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: ('', ''))
    QFileDialog.getOpenFileName = staticmethod(lambda *a, **k: ('', ''))
    QColorDialog.getColor = staticmethod(lambda *a, **k: QColor())
    QInputDialog.getInt = staticmethod(lambda *a, **k: (200, False))

    from desktop.host_state_machine import HostStateMachineWidget
    src = Path('desktop/host_state_machine.py').read_text(encoding='utf-8')
    for name in (
        'reorder_merge_diff_batch_fail_history_groups',
        'merge_diff_batch_fail_history_group_order',
        '_update_sev_pin_arc_seize_recent_shift_range_bar',
        '_ensure_sev_pin_arc_seize_recent_shift_range_bar',
        'copy_toast_hist_cap_tip_anim_easing_curve_png_to_clipboard',
        '_show_path_copy_badge_fail_hist_undo_bar',
        '_update_path_copy_badge_fail_hist_undo_bar',
        '_hide_path_copy_badge_fail_hist_undo_bar',
        'set_stale_prune_undo_color_custom_alpha',
        'show_stale_prune_undo_color_custom_preview',
    ):
        assert hasattr(HostStateMachineWidget, name), name
    assert 'hostToastTipAnimEasingCurveCopyClipboard' in src
    assert 'hostPathCopyBadgeFailHistUndoBar' in src
    assert 'isUndoColorScaleCustomPreview' in src
    assert 'hostSevPinArcSeizeRecentShiftRangeBar' in src
    ok('wave54 APIs present')

    s = QSettings('SIEANS', 'VisionDesktop')
    s.setValue('host/alarmFilmCsvDirs', [])
    s.setValue('host/alarmFilmCsvDir', '')
    s.setValue('host/alarmFilmCsvDirsMax', 5)
    s.setValue('host/sevPinArcSeizeRecentColors', [])
    s.setValue('host/toastHistCapTipAnim', True)
    s.setValue('host/toastHistCapTipAnimMs', 320)
    s.setValue('host/toastHistCapTipAnimEasing', 'OutCubic')
    s.setValue('host/stalePruneUndoExtendStepMs', 0)
    s.setValue('host/stalePruneUndoColorScale', 'traffic')
    s.setValue('host/stalePruneUndoColorCustomHi', '#aa1122')
    s.setValue('host/stalePruneUndoColorCustomMid', '#bb3344')
    s.setValue('host/stalePruneUndoColorCustomLo', '#cc5566')
    s.setValue('host/stalePruneUndoColorCustomAlpha', 200)
    s.setValue('host/mergeDiffBatchFailHistory', [])
    s.setValue('host/mergeDiffBatchFailLast', [])
    s.setValue('host/mergeDiffBatchFailHistorySort', 'time')
    s.setValue('host/mergeDiffFailHistGroupOrder', [])
    s.setValue('host/pathCopyBadgeParentFallback', True)
    s.sync()
    host = HostStateMachineWidget(compact=True)
    host.show()
    host._toast_hist_cap_keep_exit_tip_quiet = True
    host._toast_hist_cap_tip_anim_easing_quiet = True
    host._toast_hist_cap_tip_anim_curve_quiet = True
    host._toast_hist_cap_tip_anim_curve_no_exec = True
    host._toast_hist_cap_tip_anim_curve_png_no_dialog = True
    host._stale_prune_undo_custom_rgb_no_dialog = True
    host._stale_prune_undo_custom_preview_no_exec = True
    host._path_copy_badge_fail_hist_clear_no_confirm = True
    host._merge_diff_fail_hist_no_exec = True

    tmp = Path('/tmp/sieans-w54s'); tmp.mkdir(exist_ok=True)
    d0 = tmp / 'c0'; d0.mkdir(exist_ok=True)
    stale = tmp / 'gone-w54'
    if stale.exists():
        import shutil
        shutil.rmtree(stale, ignore_errors=True)

    now = datetime.now()
    day0 = (now - timedelta(days=2)).strftime('%Y-%m-%d %H:%M:%S')
    day1 = (now - timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')
    day2 = now.strftime('%Y-%m-%d %H:%M:%S')
    g0, g1, g2 = day0[:10], day1[:10], day2[:10]

    # --- 1. group header drag reorder ---
    host._merge_diff_batch_fail_history = [
        {'ts': day0, 'paths': ['/tmp/w54-d0/a']},
        {'ts': day1, 'paths': ['/tmp/w54-d1/b']},
        {'ts': day2, 'paths': ['/tmp/w54-d2/c']},
    ]
    host._merge_diff_fail_hist_collapsed = set()
    host._merge_diff_fail_hist_group_order = []
    assert host.show_merge_diff_batch_fail_history() is True
    lst = host._last_merge_diff_batch_fail_history_list
    assert lst is not None
    # reverse order
    rev = [g2, g1, g0]
    got = host.reorder_merge_diff_batch_fail_history_groups(rev)
    assert got == rev
    assert host.merge_diff_batch_fail_history_group_order() == rev
    assert host.show_merge_diff_batch_fail_history() is True
    hdrs = []
    for i in range(lst.count()):
        it = lst.item(i)
        if it and it.data(Qt.ItemDataRole.UserRole + 3):
            hdrs.append(str(it.data(Qt.ItemDataRole.UserRole + 2) or ''))
    assert hdrs[:3] == rev
    # headers drag-enabled
    assert bool(lst.item(0).flags() & Qt.ItemFlag.ItemIsDragEnabled)
    ok('失败历史 组头拖拽重排')

    # --- 2. Shift range visual bar ---
    host.clear_sev_pin_arc_seize_recent_colors()
    for c in ('#ff0001', '#ff0002', '#ff0003', '#ff0004'):
        host.remember_sev_pin_arc_seize_color(c)
    drag = host._make_sev_pin_arc_seize_recent_drag_list()
    assert getattr(host, '_last_sev_pin_arc_seize_recent_shift_range_bar_ready', False)
    bar = host._ensure_sev_pin_arc_seize_recent_shift_range_bar(drag)
    assert bar is not None
    assert bar.objectName() == 'hostSevPinArcSeizeRecentShiftRangeBar'
    drag.clearSelection()
    assert host._update_sev_pin_arc_seize_recent_shift_range_bar(drag) is False
    drag.item(0).setSelected(True)
    drag.item(1).setSelected(True)
    drag.item(2).setSelected(True)
    assert host._update_sev_pin_arc_seize_recent_shift_range_bar(drag) is True
    assert getattr(host, '_last_sev_pin_arc_seize_recent_shift_range_bar_visible', False)
    assert getattr(host, '_last_sev_pin_arc_seize_recent_shift_range', None) == (0, 2)
    ok('Shift 连选 区间视觉条')

    # --- 3. curve PNG clipboard ---
    host._toast_hist_cap_tip_anim_curve_no_exec = True
    assert host.show_toast_hist_cap_tip_anim_easing_curve_compare(
        'OutCubic', 'Linear') is True
    btn = getattr(host, '_last_toast_hist_cap_tip_anim_curve_clipboard_btn', None)
    assert btn is not None and btn.objectName() == 'hostToastTipAnimEasingCurveCopyClipboard'
    assert host.copy_toast_hist_cap_tip_anim_easing_curve_png_to_clipboard() is True
    assert getattr(host, '_last_toast_hist_cap_tip_anim_curve_clipboard', False) is True
    pm = getattr(host, '_last_toast_hist_cap_tip_anim_curve_clipboard_pm', None)
    assert isinstance(pm, QPixmap) and not pm.isNull()
    clip_pm = QApplication.clipboard().pixmap()
    assert not clip_pm.isNull()
    ok('曲线 PNG 剪贴板')

    # --- 4. badge undo countdown bar ---
    host._merge_diff_batch_fail_history = [
        {'ts': day2, 'paths': ['/tmp/w54-undo/a']},
        {'ts': day0, 'paths': ['/tmp/w54-undo/b']},
    ]
    host._path_copy_badge_fail_history_undo_ms = 4000
    host._path_copy_badge_fail_history_can_undo = False
    host._path_copy_badge_fail_history_undo = None
    host._path_copy_badge_fail_history_undo_left_ms = 0
    host._last_path_copy_badge_fail_history_undo_expired = False
    # show badge so place works
    try:
        host._path_copy_badge.setText('路径已复制')
        host._path_copy_badge.show()
    except Exception:
        pass
    snap = host.clear_path_copy_badge_fail_history(confirm=False)
    assert len(snap) == 2
    assert getattr(host, '_last_path_copy_badge_fail_hist_undo_bar_visible', False) is True
    ubar = host._path_copy_badge_fail_hist_undo_bar
    assert ubar is not None and not ubar.isHidden()
    assert ubar.objectName() == 'hostPathCopyBadgeFailHistUndoBar'
    assert ubar.value() > 0
    host._path_copy_badge_fail_history_undo_left_ms = 500
    host._update_path_copy_badge_fail_hist_undo_bar()
    assert getattr(host, '_last_path_copy_badge_fail_hist_undo_bar_value', 0) < 200
    # click undo via bar
    class _E:
        def button(self):
            return Qt.MouseButton.LeftButton
    assert host._on_path_copy_badge_fail_hist_undo_bar_clicked(_E()) is True
    assert getattr(host, '_last_path_copy_badge_fail_hist_undo_bar_visible', True) is False
    assert len(host.merge_diff_batch_fail_history()) == 2
    ok('徽章撤销 倒计时条')

    # --- 5. custom alpha / gradient preview ---
    got = host.set_stale_prune_undo_color_custom_rgb(
        '#112233', '#445566', '#778899', alpha=180)
    assert got['alpha'] == 180
    assert host.set_stale_prune_undo_color_custom_alpha(120) == 120
    assert host.stale_prune_undo_color_custom_rgb()['alpha'] == 120
    assert host.stale_prune_undo_color_scale_preset() == 'custom'
    host.clear_alarm_film_csv_dirs()
    host.remember_alarm_film_csv_dir(str(d0))
    host.remember_alarm_film_csv_dir(str(stale))
    host.set_stale_prune_undo_ms(8000)
    host.prune_stale_alarm_film_csv_dirs(confirm=False)
    host._stale_prune_can_undo = True
    host._stale_prune_undo_left_ms = 8000
    host._show_stale_prune_undo_bar()
    host._update_stale_prune_undo_bar()
    chunk = getattr(host, '_last_stale_prune_undo_bar_chunk_color', '')
    assert chunk.startswith('rgba(') and '120)' in chunk.replace(' ', '')
    host._stale_prune_undo_custom_preview_no_exec = True
    assert host.show_stale_prune_undo_color_custom_preview(interactive=False) is True
    assert getattr(host, '_last_stale_prune_undo_color_custom_preview_shown', False)
    pane = getattr(host, '_last_stale_prune_undo_color_custom_preview_pane', None)
    assert pane is not None and pane.objectName() == 'hostStalePruneUndoColorCustomGradPane'
    spin = getattr(host, '_last_stale_prune_undo_color_custom_preview_spin', None)
    assert spin is not None
    spin.setValue(90)
    assert host.stale_prune_undo_color_custom_rgb()['alpha'] == 90
    host._stale_prune_undo_step_menu_no_exec = True
    menu = host._build_stale_prune_undo_step_menu()
    prev_acts = [a for a in menu.actions() if a.property('isUndoColorScaleCustomPreview')]
    assert len(prev_acts) == 1
    host.set_stale_prune_undo_color_scale_preset('traffic')
    ok('undo 色阶 α/渐变预览')

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
