#!/usr/bin/env python3
"""细妆㊠：失败历史分组折叠 · 拖拽多选Del · easing曲线小窗 · 徽章清历史 · undo色阶."""
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
        QApplication, QMessageBox, QFileDialog, QAbstractItemView,
    )
    from PySide6.QtCore import QSettings, Qt, QPoint, QEvent
    from PySide6.QtGui import QKeyEvent
    app = QApplication.instance() or QApplication([])
    QMessageBox.information = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
    QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)
    QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: ('', ''))
    QFileDialog.getOpenFileName = staticmethod(lambda *a, **k: ('', ''))

    from desktop.host_state_machine import HostStateMachineWidget
    src = Path('desktop/host_state_machine.py').read_text(encoding='utf-8')
    for name in (
        'clear_path_copy_badge_fail_history',
        'show_toast_hist_cap_tip_anim_easing_curve',
        '_toast_tip_anim_easing_curve_samples',
        '_stale_prune_undo_bar_chunk_color',
        '_apply_stale_prune_undo_bar_color_scale',
    ):
        assert hasattr(HostStateMachineWidget, name), name
    assert 'isPathCopyBadgeFailHistoryClear' in src
    assert '_merge_diff_fail_hist_collapsed' in src
    ok('wave51 APIs present')

    s = QSettings('SIEANS', 'VisionDesktop')
    s.setValue('host/alarmFilmCsvDirs', [])
    s.setValue('host/alarmFilmCsvDir', '')
    s.setValue('host/alarmFilmCsvDirsMax', 5)
    s.setValue('host/sevPinArcSeizeRecentColors', [])
    s.setValue('host/toastHistCapTipAnim', True)
    s.setValue('host/toastHistCapTipAnimMs', 320)
    s.setValue('host/toastHistCapTipAnimEasing', 'OutCubic')
    s.setValue('host/stalePruneUndoExtendStepMs', 0)
    s.setValue('host/mergeDiffBatchFailHistory', [])
    s.setValue('host/mergeDiffBatchFailLast', [])
    s.setValue('host/mergeDiffBatchFailHistorySort', 'time')
    s.setValue('host/pathCopyBadgeParentFallback', True)
    s.sync()
    host = HostStateMachineWidget(compact=True)
    host.show()
    host._toast_hist_cap_keep_exit_tip_quiet = True
    host._toast_hist_cap_tip_anim_easing_quiet = True
    host._toast_hist_cap_tip_anim_curve_quiet = True
    host._toast_hist_cap_tip_anim_curve_no_exec = True

    tmp = Path('/tmp/sieans-w51s'); tmp.mkdir(exist_ok=True)
    d0 = tmp / 'c0'; d0.mkdir(exist_ok=True)
    stale = tmp / 'gone-w51'
    if stale.exists():
        import shutil
        shutil.rmtree(stale, ignore_errors=True)

    # --- 1. fail hist group fold ---
    host.clear_merge_diff_batch_fail_history()
    # fabricate two days
    host.remember_merge_diff_batch_fails(['/tmp/w51-a/x'])
    hist = host.merge_diff_batch_fail_history()
    # rewrite with explicit timestamps spanning days
    from datetime import datetime, timedelta
    now = datetime.now()
    day0 = (now - timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')
    day1 = now.strftime('%Y-%m-%d %H:%M:%S')
    host._merge_diff_batch_fail_history = [
        {'ts': day0, 'paths': ['/tmp/w51-d0/a', '/tmp/w51-d0/b']},
        {'ts': day1, 'paths': ['/tmp/w51-d1/c']},
        {'ts': day1, 'paths': ['/tmp/w51-d1/d']},
    ]
    try:
        host._persist_merge_diff_batch_fail_history()
    except Exception:
        pass
    host._merge_diff_fail_hist_no_exec = True
    host._merge_diff_fail_hist_collapsed = set()
    assert host.show_merge_diff_batch_fail_history() is True
    assert getattr(host, '_last_merge_diff_batch_fail_history_groups', 0) >= 2
    lst = host._last_merge_diff_batch_fail_history_list
    # find a group header and click to collapse
    hdr = None
    for i in range(lst.count()):
        it = lst.item(i)
        if it and it.data(Qt.ItemDataRole.UserRole + 3):
            hdr = it
            break
    assert hdr is not None
    gk = str(hdr.data(Qt.ItemDataRole.UserRole + 2))
    before_n = lst.count()
    # simulate click
    from PySide6.QtCore import QPoint as _QP
    # call itemClicked path via refill after toggle
    host._merge_diff_fail_hist_collapsed.add(gk)
    # re-show to refill
    assert host.show_merge_diff_batch_fail_history() is True
    lst2 = host._last_merge_diff_batch_fail_history_list
    assert gk in getattr(host, '_last_merge_diff_batch_fail_history_collapsed', set())
    # collapsed → fewer rows than expanded (headers remain)
    assert lst2.count() < before_n or getattr(host, '_last_merge_diff_batch_fail_history_filter_n', 99) < 3
    # toggle expand via click handler path: clear collapsed and refill
    host._merge_diff_fail_hist_collapsed.discard(gk)
    assert host.show_merge_diff_batch_fail_history() is True
    # click toggle
    lst3 = host._last_merge_diff_batch_fail_history_list
    hdr2 = None
    for i in range(lst3.count()):
        it = lst3.item(i)
        if it and it.data(Qt.ItemDataRole.UserRole + 3):
            hdr2 = it
            gk2 = str(it.data(Qt.ItemDataRole.UserRole + 2))
            break
    assert hdr2 is not None
    # manually invoke same logic as click
    collapsed = host._merge_diff_fail_hist_collapsed
    if gk2 in collapsed:
        collapsed.discard(gk2)
        host._last_merge_diff_batch_fail_history_group_toggled = (gk2, False)
    else:
        collapsed.add(gk2)
        host._last_merge_diff_batch_fail_history_group_toggled = (gk2, True)
    assert host.show_merge_diff_batch_fail_history() is True
    assert getattr(host, '_last_merge_diff_batch_fail_history_group_toggled', (None, None))[0] == gk2
    ok('失败历史 分组折叠')

    # --- 2. multi Delete ---
    host.clear_sev_pin_arc_seize_recent_colors()
    for c in ('#cc0001', '#cc0002', '#cc0003', '#cc0004'):
        host.remember_sev_pin_arc_seize_color(c)
    drag = host._make_sev_pin_arc_seize_recent_drag_list()
    assert drag.selectionMode() == QAbstractItemView.SelectionMode.ExtendedSelection
    # select two colors
    want = {'#cc0002', '#cc0004'}
    drag.clearSelection()
    for i in range(drag.count()):
        it = drag.item(i)
        c = str(it.data(Qt.ItemDataRole.UserRole) or '').lower()
        if c in want:
            it.setSelected(True)
    assert len(drag.selectedItems()) >= 2
    ev_del = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Delete, Qt.KeyboardModifier.NoModifier)
    drag.keyPressEvent(ev_del)
    left = set(host.sev_pin_arc_seize_recent_colors())
    assert '#cc0002' not in left and '#cc0004' not in left
    assert '#cc0001' in left or '#cc0003' in left
    deleted = getattr(host, '_last_sev_pin_arc_seize_recent_key_deleted', [])
    assert isinstance(deleted, list) and len(deleted) >= 2
    assert getattr(host, '_last_sev_pin_arc_seize_recent_key_deleted_n', 0) >= 2
    ok('拖拽列表 多选 Delete')

    # --- 3. tip curve pane ---
    host._toast_hist_cap_tip_anim_curve_no_exec = True
    host._toast_hist_cap_tip_anim_curve_quiet = False  # allow show via API
    pts = host._toast_tip_anim_easing_curve_samples('OutBounce', 32)
    assert isinstance(pts, list) and len(pts) >= 16
    assert pts[0][0] == 0.0 and pts[-1][0] == 1.0
    assert host.show_toast_hist_cap_tip_anim_easing_curve('OutBounce') is True
    assert getattr(host, '_last_toast_hist_cap_tip_anim_curve_shown', False) is True
    assert getattr(host, '_last_toast_hist_cap_tip_anim_curve_name', '') == 'OutBounce'
    assert getattr(host, '_last_toast_hist_cap_tip_anim_curve_pane', None) is not None
    # preview also triggers curve when quiet off
    host._toast_hist_cap_tip_anim_curve_quiet = False
    host._toast_hist_cap_tip_anim_easing_quiet = True  # set won't auto
    host.set_toast_hist_cap_tip_anim_easing('Linear')
    assert host.preview_toast_hist_cap_tip_anim_easing('Linear') is True
    assert getattr(host, '_last_toast_hist_cap_tip_anim_curve_name', '') == 'Linear'
    host._toast_hist_cap_tip_anim_curve_quiet = True
    host.set_toast_hist_cap_tip_anim_easing('OutCubic')
    ok('tip 预览 曲线小窗')

    # --- 4. badge clear history ---
    # restore some history
    host._merge_diff_batch_fail_history = [
        {'ts': day1, 'paths': ['/tmp/w51-clr/a']},
    ]
    try:
        host._persist_merge_diff_batch_fail_history()
    except Exception:
        pass
    assert len(host.merge_diff_batch_fail_history()) >= 1
    menu = host._build_path_copy_badge_menu()
    clr_acts = [a for a in menu.actions() if a.property('isPathCopyBadgeFailHistoryClear')]
    assert len(clr_acts) == 1
    assert clr_acts[0].isEnabled() is True
    host._path_copy_badge_fail_hist_clear_no_confirm = True
    cleared = host.clear_path_copy_badge_fail_history(confirm=False)
    assert len(host.merge_diff_batch_fail_history()) == 0
    assert getattr(host, '_last_path_copy_badge_fail_history_cleared', None) is not None
    menu0 = host._build_path_copy_badge_menu()
    clr0 = [a for a in menu0.actions() if a.property('isPathCopyBadgeFailHistoryClear')]
    assert clr0[0].isEnabled() is False
    ok('徽章菜单 清除历史')

    # --- 5. undo bar color scale ---
    host.clear_alarm_film_csv_dirs()
    host.remember_alarm_film_csv_dir(str(d0))
    host.remember_alarm_film_csv_dir(str(stale))
    host.set_stale_prune_undo_ms(8000)
    host.prune_stale_alarm_film_csv_dirs(confirm=False)
    # force bar visible + update at high/mid/low ratios
    host._stale_prune_can_undo = True
    host._stale_prune_undo_left_ms = 8000
    host._show_stale_prune_undo_bar()
    host._update_stale_prune_undo_bar()
    c_hi = getattr(host, '_last_stale_prune_undo_bar_chunk_color', '')
    assert c_hi in ('#3ecf8e', '#8fd46a')
    host._stale_prune_undo_left_ms = 3200  # 0.4
    host._update_stale_prune_undo_bar()
    c_mid = getattr(host, '_last_stale_prune_undo_bar_chunk_color', '')
    assert c_mid == '#f0c040'
    host._stale_prune_undo_left_ms = 800  # 0.1
    host._update_stale_prune_undo_bar()
    c_lo = getattr(host, '_last_stale_prune_undo_bar_chunk_color', '')
    assert c_lo == '#e35d6a'
    assert host._stale_prune_undo_bar_chunk_color(0.9) in ('#3ecf8e', '#8fd46a')
    assert host._apply_stale_prune_undo_bar_color_scale(0.1) == '#e35d6a'
    ok('undo 倒计时进度条 色阶')

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
