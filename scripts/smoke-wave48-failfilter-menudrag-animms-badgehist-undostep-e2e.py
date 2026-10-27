#!/usr/bin/env python3
"""细妆㊽：失败历史搜索过滤 · 最近色菜单内拖拽 · tip动画时长可配 · 徽章打开历史失败 · undo延长步进可配."""
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
        QApplication, QMessageBox, QFileDialog, QAbstractItemView, QListWidget,
    )
    from PySide6.QtCore import QSettings, Qt
    app = QApplication.instance() or QApplication([])
    QMessageBox.information = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
    QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
    QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: ('', ''))
    QFileDialog.getOpenFileName = staticmethod(lambda *a, **k: ('', ''))

    from desktop.host_state_machine import HostStateMachineWidget
    src = Path('desktop/host_state_machine.py').read_text(encoding='utf-8')
    for name in (
        'filter_merge_diff_batch_fail_history',
        '_make_sev_pin_arc_seize_recent_drag_list',
        'toast_hist_cap_tip_anim_ms', 'set_toast_hist_cap_tip_anim_ms',
        'stale_prune_undo_extend_step_ms', 'set_stale_prune_undo_extend_step_ms',
    ):
        assert hasattr(HostStateMachineWidget, name), name
    assert 'isPathCopyBadgeFailHistory' in src
    assert 'isSeizeRecentDrag' in src
    assert 'isTipAnimMs' in src
    ok('wave48 APIs present')

    s = QSettings('SIEANS', 'VisionDesktop')
    s.setValue('host/alarmFilmCsvDirs', [])
    s.setValue('host/alarmFilmCsvDir', '')
    s.setValue('host/alarmFilmCsvDirsMax', 5)
    s.setValue('host/sevPinArcSeizeRecentColors', [])
    s.setValue('host/toastHistCapTipAnim', True)
    s.setValue('host/toastHistCapTipAnimMs', 320)
    s.setValue('host/stalePruneUndoExtendStepMs', 0)
    s.setValue('host/mergeDiffBatchFailHistory', [])
    s.setValue('host/mergeDiffBatchFailLast', [])
    s.setValue('host/pathCopyBadgeParentFallback', True)
    s.sync()
    host = HostStateMachineWidget(compact=True)
    host.show()
    host._toast_hist_cap_keep_exit_tip_quiet = True

    tmp = Path('/tmp/sieans-w48s'); tmp.mkdir(exist_ok=True)
    d0 = tmp / 'c0'; d0.mkdir(exist_ok=True)
    stale = tmp / 'gone-w48'
    if stale.exists():
        import shutil
        shutil.rmtree(stale, ignore_errors=True)

    # --- 1. fail history search/filter ---
    host.clear_merge_diff_batch_fail_history()
    host.remember_merge_diff_batch_fails(['/tmp/alpha-fail/x', '/tmp/other/y'])
    host.remember_merge_diff_batch_fails(['/tmp/beta-fail/z'])
    hist = host.merge_diff_batch_fail_history()
    assert len(hist) >= 2
    filtered = host.filter_merge_diff_batch_fail_history('alpha')
    assert len(filtered) == 1
    assert 'alpha-fail' in (filtered[0].get('paths') or [])[0]
    assert len(host.filter_merge_diff_batch_fail_history('nope-zzz')) == 0
    host._merge_diff_fail_hist_no_exec = True
    assert host.show_merge_diff_batch_fail_history() is True
    filt = getattr(host, '_last_merge_diff_batch_fail_history_filter_edit', None)
    assert filt is not None
    filt.setText('beta')
    assert getattr(host, '_last_merge_diff_batch_fail_history_filter', '') == 'beta'
    assert getattr(host, '_last_merge_diff_batch_fail_history_filter_n', 0) == 1
    filt.setText('')
    ok('失败历史 搜索/过滤')

    # --- 2. recent color in-menu drag ---
    host.clear_sev_pin_arc_seize_recent_colors()
    for c in ('#cc0001', '#cc0002', '#cc0003'):
        host.remember_sev_pin_arc_seize_color(c)
    menu = host._build_sev_pin_arc_seize_color_menu()
    drag_acts = [a for a in menu.actions() if a.property('isSeizeRecentDrag')]
    assert len(drag_acts) == 1, drag_acts
    lst = getattr(host, '_last_sev_pin_arc_seize_recent_drag_list', None)
    assert isinstance(lst, QListWidget)
    assert lst.dragDropMode() == QAbstractItemView.DragDropMode.InternalMove
    assert lst.count() >= 3
    # simulate reorder via API path that drag list uses
    order = ['#cc0001', '#cc0003', '#cc0002']
    host.reorder_sev_pin_arc_seize_recent_colors(order)
    # rebuild drag list and take first item move via model-like apply
    lst2 = host._make_sev_pin_arc_seize_recent_drag_list()
    assert lst2.count() == 3
    # manually reorder list items then trigger rowsMoved handler by calling reorder from list
    # take item 0 and interpret as drag result: rebuild order from list after swap
    it0 = lst2.takeItem(0)
    lst2.insertItem(2, it0)
    order2 = [str(lst2.item(i).data(Qt.ItemDataRole.UserRole)) for i in range(lst2.count())]
    host.reorder_sev_pin_arc_seize_recent_colors(order2)
    host._last_sev_pin_arc_seize_recent_menu_dragged = order2
    assert host.sev_pin_arc_seize_recent_colors() == order2
    ok('最近色菜单内 拖拽')

    # --- 3. tip anim duration configurable ---
    assert host.toast_hist_cap_tip_anim_ms() == 320
    host.set_toast_hist_cap_tip_anim_ms(500)
    assert host.toast_hist_cap_tip_anim_ms() == 500
    host._toast_hist_cap_menu_no_exec = True
    menu = host._build_liaison_toast_capacity_menu()
    host._last_toast_hist_cap_menu = menu
    ms_acts = [a for a in menu.actions() if a.property('isTipAnimMs')]
    assert len(ms_acts) == 4
    assert any(int(a.data()) == 500 and a.isChecked() for a in ms_acts)
    host.set_toast_hist_cap_tip_anim_enabled(True)
    host._flash_host_toast('anim-ms', kind='info', ms=600, animate=True)
    assert getattr(host, '_last_host_toast_pulsed', False) is True
    anim = getattr(host, '_host_toast_pulse_anim', None)
    assert anim is not None
    assert int(anim.duration()) == 500
    host.set_toast_hist_cap_tip_anim_ms(320)
    ok('tip 动画 时长可配')

    # --- 4. badge open fail history ---
    host.flash_path_copy_badge(str(d0))
    menu = host._build_path_copy_badge_menu()
    hist_acts = [a for a in menu.actions() if a.property('isPathCopyBadgeFailHistory')]
    assert len(hist_acts) == 1
    assert hist_acts[0].text().startswith('打开历史失败'), hist_acts[0].text()
    assert not hist_acts[0].icon().isNull()
    assert getattr(host, '_last_path_copy_badge_menu_shortcuts', ()) == ('C', 'F', 'H')
    host._merge_diff_fail_hist_no_exec = True
    hist_acts[0].trigger()
    assert getattr(host, '_last_merge_diff_batch_fail_history_shown', False) is True
    ok('徽章 打开历史失败')

    # --- 5. undo extend step configurable ---
    host.clear_alarm_film_csv_dirs()
    host.remember_alarm_film_csv_dir(str(d0))
    host.remember_alarm_film_csv_dir(str(stale))
    host.set_stale_prune_undo_ms(5000)
    host.set_stale_prune_undo_extend_step_ms(0)  # reset-full compat
    host.prune_stale_alarm_film_csv_dirs(confirm=False)
    host._stale_prune_undo_left_ms = 900
    assert host.extend_stale_prune_undo() == 5000
    assert host.stale_prune_undo_left_ms() == 5000
    host.set_stale_prune_undo_extend_step_ms(1500)
    assert host.stale_prune_undo_extend_step_ms() == 1500
    host._stale_prune_undo_left_ms = 1000
    got = host.extend_stale_prune_undo()
    assert got == 2500, got
    assert host.stale_prune_undo_left_ms() == 2500
    # explicit ms still wins
    assert host.extend_stale_prune_undo(3000) == 3000
    host.set_stale_prune_undo_extend_step_ms(0)
    ok('undo 延长 步进可配')

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
