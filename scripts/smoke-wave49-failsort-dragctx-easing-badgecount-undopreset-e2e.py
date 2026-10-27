#!/usr/bin/env python3
"""细妆㊞：失败历史排序 · 最近色右键置顶/删除 · tip easing · 徽章失败数角标 · undo步进±1s/±3s."""
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
    from PySide6.QtWidgets import QApplication, QMessageBox, QFileDialog, QComboBox
    from PySide6.QtCore import QSettings, Qt, QPoint, QEasingCurve
    app = QApplication.instance() or QApplication([])
    QMessageBox.information = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
    QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
    QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: ('', ''))
    QFileDialog.getOpenFileName = staticmethod(lambda *a, **k: ('', ''))

    from desktop.host_state_machine import HostStateMachineWidget
    src = Path('desktop/host_state_machine.py').read_text(encoding='utf-8')
    for name in (
        'sorted_merge_diff_batch_fail_history',
        'set_merge_diff_batch_fail_history_sort_mode',
        'toast_hist_cap_tip_anim_easing',
        'set_toast_hist_cap_tip_anim_easing',
        'extend_stale_prune_undo_by',
        'adjust_stale_prune_undo_extend_step_ms',
        '_build_stale_prune_undo_step_menu',
    ):
        assert hasattr(HostStateMachineWidget, name), name
    assert 'isSeizeRecentPinTop' in src
    assert 'isTipAnimEasing' in src
    assert 'isPathCopyBadgeFailHistoryBadge' in src
    ok('wave49 APIs present')

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

    tmp = Path('/tmp/sieans-w49s'); tmp.mkdir(exist_ok=True)
    d0 = tmp / 'c0'; d0.mkdir(exist_ok=True)
    stale = tmp / 'gone-w49'
    if stale.exists():
        import shutil
        shutil.rmtree(stale, ignore_errors=True)

    # --- 1. fail history sort time/path ---
    host.clear_merge_diff_batch_fail_history()
    host.remember_merge_diff_batch_fails(['/tmp/zzz-path/a'])
    # force older ts on first by rewriting hist
    hist = host.merge_diff_batch_fail_history()
    assert len(hist) >= 1
    # inject second with higher path lexically lower time via API
    host.remember_merge_diff_batch_fails(['/tmp/aaa-path/b'])
    host.set_merge_diff_batch_fail_history_sort_mode('time')
    by_time = host.sorted_merge_diff_batch_fail_history('time')
    assert len(by_time) >= 2
    # newest first: aaa remembered later
    assert 'aaa-path' in (by_time[0].get('paths') or [])[0]
    host.set_merge_diff_batch_fail_history_sort_mode('path')
    by_path = host.sorted_merge_diff_batch_fail_history('path')
    assert 'aaa-path' in (by_path[0].get('paths') or [])[0]
    assert 'zzz-path' in (by_path[-1].get('paths') or [])[0]
    host._merge_diff_fail_hist_no_exec = True
    assert host.show_merge_diff_batch_fail_history() is True
    box = getattr(host, '_last_merge_diff_batch_fail_history_sort_box', None)
    assert isinstance(box, QComboBox)
    box.setCurrentIndex(0)  # time
    assert host.merge_diff_batch_fail_history_sort_mode() == 'time'
    box.setCurrentIndex(1)  # path
    assert host.merge_diff_batch_fail_history_sort_mode() == 'path'
    ok('失败历史 时间/路径排序切换')

    # --- 2. recent drag list context: pin / delete ---
    host.clear_sev_pin_arc_seize_recent_colors()
    for c in ('#aa0001', '#aa0002', '#aa0003'):
        host.remember_sev_pin_arc_seize_color(c)
    # order newest first typically
    lst = host._make_sev_pin_arc_seize_recent_drag_list()
    host._sev_pin_arc_seize_recent_drag_ctx_no_exec = True
    # pick middle item for context
    mid = None
    for i in range(lst.count()):
        it = lst.item(i)
        if it and str(it.data(Qt.ItemDataRole.UserRole)).lower() == '#aa0002':
            mid = it
            break
    assert mid is not None
    # invoke handler with pos of mid
    rect = lst.visualItemRect(mid)
    host._sev_pin_arc_seize_recent_drag_ctx_no_exec = True
    lst.customContextMenuRequested.emit(rect.center())
    cm = getattr(host, '_last_sev_pin_arc_seize_recent_drag_ctx', None)
    assert cm is not None
    pin_acts = [a for a in cm.actions() if a.property('isSeizeRecentPinTop')]
    del_acts = [a for a in cm.actions() if a.property('isSeizeRecentDeleteOne')]
    assert len(pin_acts) == 1 and len(del_acts) == 1
    # pin #aa0001 to top via API path used by menu
    host.move_sev_pin_arc_seize_recent_color('#aa0001', 0)
    assert host.sev_pin_arc_seize_recent_colors()[0] == '#aa0001'
    host._last_sev_pin_arc_seize_recent_pinned = '#aa0001'
    left = host.clear_sev_pin_arc_seize_recent_color('#aa0003')
    assert '#aa0003' not in left
    host._last_sev_pin_arc_seize_recent_deleted = '#aa0003'
    ok('最近色拖拽列表 右键置顶/删除')

    # --- 3. tip anim easing ---
    assert host.toast_hist_cap_tip_anim_easing() == 'OutCubic'
    host.set_toast_hist_cap_tip_anim_easing('OutBounce')
    assert host.toast_hist_cap_tip_anim_easing() == 'OutBounce'
    curve = host._toast_tip_anim_easing_curve()
    assert curve.type() == QEasingCurve.Type.OutBounce
    host._toast_hist_cap_menu_no_exec = True
    menu = host._build_liaison_toast_capacity_menu()
    host._last_toast_hist_cap_menu = menu
    ez_acts = [a for a in menu.actions() if a.property('isTipAnimEasing')]
    assert len(ez_acts) == 4
    assert any(str(a.data()) == 'OutBounce' and a.isChecked() for a in ez_acts)
    host.set_toast_hist_cap_tip_anim_enabled(True)
    host._flash_host_toast('easing', kind='info', ms=600, animate=True)
    assert getattr(host, '_last_host_toast_pulsed', False) is True
    anim = getattr(host, '_host_toast_pulse_anim', None)
    assert anim is not None
    assert anim.easingCurve().type() == QEasingCurve.Type.OutBounce
    host.set_toast_hist_cap_tip_anim_easing('OutCubic')
    ok('tip 动画 easing 可配')

    # --- 4. badge fail count ---
    # history already has entries
    n = len(host.merge_diff_batch_fail_history())
    assert n >= 1
    host.flash_path_copy_badge(str(d0))
    menu = host._build_path_copy_badge_menu()
    hist_acts = [a for a in menu.actions() if a.property('isPathCopyBadgeFailHistory')]
    assert len(hist_acts) == 1
    assert hist_acts[0].property('failHistoryCount') == n
    assert hist_acts[0].property('isPathCopyBadgeFailHistoryBadge') is True
    assert f'· {n}' in hist_acts[0].text()
    assert getattr(host, '_last_path_copy_badge_fail_history_count', 0) == n
    ok('徽章菜单 失败数角标')

    # --- 5. undo step presets ±1s/±3s ---
    host.clear_alarm_film_csv_dirs()
    host.remember_alarm_film_csv_dir(str(d0))
    host.remember_alarm_film_csv_dir(str(stale))
    host.set_stale_prune_undo_ms(8000)
    host.set_stale_prune_undo_extend_step_ms(0)
    host.prune_stale_alarm_film_csv_dirs(confirm=False)
    host._stale_prune_undo_left_ms = 2000
    assert host.extend_stale_prune_undo_by(1000) == 3000
    assert getattr(host, '_last_stale_prune_undo_extended_by', 0) == 1000
    host._stale_prune_undo_left_ms = 5000
    assert host.extend_stale_prune_undo_by(3000) == 8000
    assert host.adjust_stale_prune_undo_extend_step_ms(1000) == 1000
    assert host.adjust_stale_prune_undo_extend_step_ms(2000) == 3000
    assert host.adjust_stale_prune_undo_extend_step_ms(-1000) == 2000
    host.set_stale_prune_undo_extend_step_ms(0)
    host._stale_prune_undo_step_menu_no_exec = True
    class _RE:
        def button(self):
            return Qt.MouseButton.RightButton
        def globalPosition(self):
            class _P:
                def toPoint(self):
                    return QPoint(20, 20)
            return _P()
    assert host._on_stale_prune_undo_bar_clicked(_RE()) is True
    menu = getattr(host, '_last_stale_prune_undo_step_menu', None)
    assert menu is not None
    by_acts = [a for a in menu.actions() if a.property('isUndoExtendBy')]
    preset_acts = [a for a in menu.actions() if a.property('isUndoStepPreset')]
    adj_acts = [a for a in menu.actions() if a.property('isUndoStepAdjust')]
    assert len(by_acts) == 4
    assert len(preset_acts) == 3
    assert len(adj_acts) == 2
    assert {int(a.data()) for a in by_acts} == {1000, 3000, -1000, -3000}
    ok('undo 步进 快捷预设 ±1s/±3s')

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
