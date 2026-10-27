#!/usr/bin/env python3
"""细妆㊻：失败项可点重开 · 最近色拖拽排序 · tip热更动画 · 徽章菜单快捷键 · undo悬停剩余秒."""
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
    from PySide6.QtWidgets import QApplication, QMessageBox, QFileDialog, QProgressBar, QAbstractItemView
    from PySide6.QtCore import QSettings, Qt, QKeyCombination
    from PySide6.QtGui import QKeySequence
    app = QApplication.instance() or QApplication([])
    QMessageBox.information = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
    QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
    QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: ('', ''))
    QFileDialog.getOpenFileName = staticmethod(lambda *a, **k: ('', ''))

    from desktop.host_state_machine import HostStateMachineWidget
    src = Path('desktop/host_state_machine.py').read_text(encoding='utf-8')
    for name in (
        'retry_merge_diff_batch_fails', 'show_merge_diff_batch_fails',
        'reorder_sev_pin_arc_seize_recent_colors',
        'move_sev_pin_arc_seize_recent_color',
        'show_sev_pin_arc_seize_recent_reorder_dialog',
        '_pulse_host_toast',
        '_refresh_stale_prune_undo_bar_hover_sec',
    ):
        assert hasattr(HostStateMachineWidget, name), name
    assert '点此重开失败' in src
    assert 'isSeizeRecentReorder' in src
    assert "QKeySequence('C')" in src and "QKeySequence('F')" in src
    assert '剩余 {sec}s' in src
    ok('wave46 APIs present')

    s = QSettings('SIEANS', 'VisionDesktop')
    s.setValue('host/alarmSevFilter', 'all')
    s.setValue('host/alarmSevPinned', '')
    s.setValue('host/liaisonToastHistMax', 5)
    s.setValue('host/alarmFilmCsvDirs', [])
    s.setValue('host/alarmFilmCsvDir', '')
    s.setValue('host/alarmFilmCsvDirsMax', 5)
    s.setValue('host/sevPinArcSeizeColor', '#ffffff')
    s.setValue('host/sevPinArcSeizeRecentColors', [])
    s.setValue('host/toastHistCapKeepExitTip', True)
    s.setValue('host/pathCopyBadgeParentFallback', True)
    s.sync()
    host = HostStateMachineWidget(compact=True)
    host.show()
    host._toast_hist_cap_keep_exit_tip_quiet = True  # suppress anim flash noise in later steps

    tmp = Path('/tmp/sieans-w46s'); tmp.mkdir(exist_ok=True)
    d0, d1 = tmp / 'c0', tmp / 'c1'
    for d in (d0, d1):
        d.mkdir(exist_ok=True)
    gone = '/tmp/sieans-w46-no-such-dir-xyz'
    stale = tmp / 'gone-w46'
    if stale.exists():
        import shutil
        shutil.rmtree(stale, ignore_errors=True)

    # --- 1. fail items clickable reopen ---
    batch = host.open_merge_diff_paths([str(d0), gone, str(d1)])
    assert len(batch) == 2, batch
    fails = getattr(host, '_last_merge_diff_batch_fail', [])
    assert fails == [gone] or gone in fails
    tip = getattr(host, '_last_merge_diff_batch_tip', '')
    assert '点此重开失败' in tip, tip
    assert getattr(host, '_host_toast_click_action', '') == 'retry_merge_diff_fails'
    # show fails dialog (no exec)
    host._merge_diff_fails_no_exec = True
    assert host.show_merge_diff_batch_fails() is True
    assert getattr(host, '_last_merge_diff_batch_fails_shown', False)
    lst = getattr(host, '_last_merge_diff_batch_fails_list', None)
    assert lst is not None and lst.count() >= 1
    # recreate gone as real dir then retry
    Path(gone).mkdir(parents=True, exist_ok=True)
    try:
        retried = host.retry_merge_diff_batch_fails()
        assert gone in [str(x) for x in retried] or len(retried) >= 1
        ok('失败项 可点重开')
    finally:
        try:
            Path(gone).rmdir()
        except Exception:
            pass

    # --- 2. recent color drag reorder ---
    host.clear_sev_pin_arc_seize_recent_colors()
    for c in ('#aa0001', '#aa0002', '#aa0003'):
        host.remember_sev_pin_arc_seize_color(c)
    recent = host.sev_pin_arc_seize_recent_colors()
    # remember inserts at front → [#aa0003, #aa0002, #aa0001]
    assert recent[0] == '#aa0003'
    reordered = host.reorder_sev_pin_arc_seize_recent_colors(
        ['#aa0001', '#aa0003', '#aa0002'])
    assert reordered == ['#aa0001', '#aa0003', '#aa0002'], reordered
    moved = host.move_sev_pin_arc_seize_recent_color('#aa0003', 0)
    assert moved[0] == '#aa0003'
    menu = host._build_sev_pin_arc_seize_color_menu()
    ord_acts = [a for a in menu.actions() if a.property('isSeizeRecentReorder')]
    assert len(ord_acts) == 1, ord_acts
    host._seize_recent_reorder_no_exec = True
    shown = host.show_sev_pin_arc_seize_recent_reorder_dialog()
    assert getattr(host, '_last_sev_pin_arc_seize_recent_reorder_shown', False)
    lst = getattr(host, '_last_sev_pin_arc_seize_recent_reorder_list', None)
    assert lst is not None
    mode = lst.dragDropMode()
    assert mode == QAbstractItemView.DragDropMode.InternalMove, mode
    assert shown  # returned current list
    ok('最近色 拖拽排序')

    # --- 3. tip hot-refresh animation ---
    host._toast_hist_cap_keep_exit_tip_quiet = False
    host._toast_hist_cap_menu_no_exec = True
    menu = host._build_liaison_toast_capacity_menu()
    host._last_toast_hist_cap_menu = menu
    host.set_toast_hist_cap_keep_exit_tip_enabled(False)
    assert getattr(host, '_last_toast_hist_cap_keep_exit_tip_refreshed', False)
    assert getattr(host, '_last_toast_hist_cap_keep_exit_tip_animated', False) is True
    # pulse API
    host._flash_host_toast('anim-test', kind='info', ms=500, animate=True)
    assert getattr(host, '_last_host_toast_pulsed', False) is True
    host._toast_hist_cap_keep_exit_tip_quiet = True
    host.set_toast_hist_cap_keep_exit_tip_enabled(True)
    ok('tip 热更 动画')

    # --- 4. badge menu shortcuts ---
    host.flash_path_copy_badge(str(d0))
    host._path_copy_badge_menu_no_exec = True
    menu = host._build_path_copy_badge_menu()
    copy_acts = [a for a in menu.actions() if a.property('isPathCopyBadgeCopy')]
    fb_acts = [a for a in menu.actions() if a.property('isPathCopyBadgeFallbackToggle')]
    assert len(copy_acts) == 1 and len(fb_acts) == 1
    sc_c = copy_acts[0].shortcut()
    sc_f = fb_acts[0].shortcut()
    assert str(sc_c).upper() in ('C', 'C') or sc_c == QKeySequence('C'), sc_c
    assert str(sc_f).upper() in ('F', 'F') or sc_f == QKeySequence('F'), sc_f
    scs = getattr(host, '_last_path_copy_badge_menu_shortcuts', ())
    assert scs[:2] == ('C', 'F') and 'C' in scs and 'F' in scs, scs
    ok('徽章菜单 快捷键')

    # --- 5. undo hover remaining seconds ---
    bar = host._stale_prune_undo_bar
    assert isinstance(bar, QProgressBar)
    host.clear_alarm_film_csv_dirs()
    host.remember_alarm_film_csv_dir(str(d0))
    host.remember_alarm_film_csv_dir(str(stale))
    host.set_stale_prune_undo_ms(5000)
    host.prune_stale_alarm_film_csv_dirs(confirm=False)
    assert host.stale_prune_undo_left_ms() > 0
    host._on_stale_prune_undo_bar_enter()
    sec = getattr(host, '_last_stale_prune_undo_bar_hover_sec', -1)
    assert sec >= 1, sec
    assert '剩余' in (bar.toolTip() or '') and 's' in (bar.toolTip() or ''), bar.toolTip()
    assert bar.isTextVisible() is True
    assert '剩余' in (bar.format() or '')
    # tick while hovered should refresh
    host._stale_prune_undo_left_ms = 2500
    host._update_stale_prune_undo_bar()
    assert getattr(host, '_last_stale_prune_undo_bar_hover_sec', 0) == 3
    host._on_stale_prune_undo_bar_leave()
    assert bar.isTextVisible() is False
    ok('undo 悬停 显示剩余秒')

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
