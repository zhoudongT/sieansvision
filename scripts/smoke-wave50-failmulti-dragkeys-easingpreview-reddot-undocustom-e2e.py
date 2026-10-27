#!/usr/bin/env python3
"""细妆㊟：失败历史多选重开/导出 · Del/Home · easing预览 · 徽章红点 · undo自定义ms."""
from __future__ import annotations
import json
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
    QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
    QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: ('', ''))
    QFileDialog.getOpenFileName = staticmethod(lambda *a, **k: ('', ''))

    from desktop.host_state_machine import HostStateMachineWidget
    src = Path('desktop/host_state_machine.py').read_text(encoding='utf-8')
    for name in (
        'export_merge_diff_batch_fail_history',
        'retry_merge_diff_batch_fail_history_selected',
        'preview_toast_hist_cap_tip_anim_easing',
        '_path_copy_badge_fail_history_icon',
        'prompt_stale_prune_undo_extend_step_ms',
        'prompt_stale_prune_undo_extend_ms',
    ):
        assert hasattr(HostStateMachineWidget, name), name
    assert 'isUndoStepCustom' in src and 'Key_Home' in src
    ok('wave50 APIs present')

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

    tmp = Path('/tmp/sieans-w50s'); tmp.mkdir(exist_ok=True)
    d0 = tmp / 'c0'; d0.mkdir(exist_ok=True)
    stale = tmp / 'gone-w50'
    if stale.exists():
        import shutil
        shutil.rmtree(stale, ignore_errors=True)

    # --- 1. fail hist multi reopen / export ---
    host.clear_merge_diff_batch_fail_history()
    host.remember_merge_diff_batch_fails(['/tmp/w50-a/x', '/tmp/w50-a/y'])
    host.remember_merge_diff_batch_fails(['/tmp/w50-b/z'])
    host._merge_diff_fail_hist_no_exec = True
    assert host.show_merge_diff_batch_fail_history() is True
    lst = host._last_merge_diff_batch_fail_history_list
    assert lst.selectionMode() == QAbstractItemView.SelectionMode.ExtendedSelection
    assert getattr(host, '_last_merge_diff_batch_fail_history_multi_btn', None) is not None
    assert getattr(host, '_last_merge_diff_batch_fail_history_export_btn', None) is not None
    lst.selectAll()
    assert len(lst.selectedItems()) >= 2
    # API multi retry
    ents = [it.data(Qt.ItemDataRole.UserRole + 1) for it in lst.selectedItems()]
    # open_merge_diff_paths may no-op on fake paths — still records
    out = host.retry_merge_diff_batch_fail_history_selected(ents)
    assert isinstance(out, list)
    assert len(host._last_merge_diff_batch_fail) >= 2
    exp = tmp / 'fail-hist.json'
    host._merge_diff_fail_hist_export_no_dialog = True
    host._merge_diff_fail_hist_export_path = str(exp)
    path = host.export_merge_diff_batch_fail_history(ents)
    assert path == str(exp)
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    assert isinstance(data, list) and len(data) >= 2
    assert getattr(host, '_last_merge_diff_batch_fail_history_export_n', 0) >= 2
    ok('失败历史 多选批量重开/导出')

    # --- 2. Delete / Home on drag list ---
    host.clear_sev_pin_arc_seize_recent_colors()
    for c in ('#bb0001', '#bb0002', '#bb0003'):
        host.remember_sev_pin_arc_seize_color(c)
    drag = host._make_sev_pin_arc_seize_recent_drag_list()
    # select #bb0002
    row = None
    for i in range(drag.count()):
        it = drag.item(i)
        if it and str(it.data(Qt.ItemDataRole.UserRole)).lower() == '#bb0002':
            drag.setCurrentRow(i)
            row = i
            break
    assert row is not None
    # Home → pin
    ev_home = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Home, Qt.KeyboardModifier.NoModifier)
    drag.keyPressEvent(ev_home)
    assert host.sev_pin_arc_seize_recent_colors()[0] == '#bb0002'
    assert getattr(host, '_last_sev_pin_arc_seize_recent_key_pinned', '') == '#bb0002'
    # reselect #bb0003 and Delete
    drag = host._make_sev_pin_arc_seize_recent_drag_list()
    for i in range(drag.count()):
        it = drag.item(i)
        if it and str(it.data(Qt.ItemDataRole.UserRole)).lower() == '#bb0003':
            drag.setCurrentRow(i)
            break
    ev_del = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Delete, Qt.KeyboardModifier.NoModifier)
    drag.keyPressEvent(ev_del)
    assert '#bb0003' not in host.sev_pin_arc_seize_recent_colors()
    assert getattr(host, '_last_sev_pin_arc_seize_recent_key_deleted', '') == '#bb0003'
    ok('最近色拖拽列表 Delete/Home')

    # --- 3. tip easing preview pulse ---
    host._toast_hist_cap_tip_anim_easing_quiet = True  # set without auto
    host.set_toast_hist_cap_tip_anim_easing('Linear')
    host.set_toast_hist_cap_tip_anim_enabled(True)
    assert host.preview_toast_hist_cap_tip_anim_easing('Linear') is True
    assert getattr(host, '_last_toast_hist_cap_tip_anim_easing_previewed', False) is True
    assert getattr(host, '_last_host_toast_pulsed', False) is True
    # auto preview on set when quiet off
    host._toast_hist_cap_tip_anim_easing_quiet = False
    host.set_toast_hist_cap_tip_anim_easing('InOutQuad')
    assert host.toast_hist_cap_tip_anim_easing() == 'InOutQuad'
    assert getattr(host, '_last_toast_hist_cap_tip_anim_easing_previewed', False) is True
    host._toast_hist_cap_tip_anim_easing_quiet = True
    host.set_toast_hist_cap_tip_anim_easing('OutCubic')
    ok('tip easing 预览脉冲')

    # --- 4. badge red-dot (hide when zero) ---
    n = len(host.merge_diff_batch_fail_history())
    assert n >= 1
    menu = host._build_path_copy_badge_menu()
    hist_acts = [a for a in menu.actions() if a.property('isPathCopyBadgeFailHistory')]
    assert len(hist_acts) == 1
    assert hist_acts[0].property('isPathCopyBadgeFailHistoryBadge') is True
    assert getattr(host, '_last_path_copy_badge_fail_history_red_dot', False) is True
    assert not hist_acts[0].icon().isNull()
    # clear → zero hides badge
    host.clear_merge_diff_batch_fail_history()
    menu0 = host._build_path_copy_badge_menu()
    acts0 = [a for a in menu0.actions() if a.property('isPathCopyBadgeFailHistory')]
    assert acts0[0].text() == '打开历史失败'
    assert acts0[0].property('isPathCopyBadgeFailHistoryBadge') is False
    assert acts0[0].property('failHistoryCount') == 0
    assert getattr(host, '_last_path_copy_badge_fail_history_red_dot', True) is False
    ok('徽章角标 红点样式（零时隐藏）')

    # --- 5. undo custom ms ---
    host.clear_alarm_film_csv_dirs()
    host.remember_alarm_film_csv_dir(str(d0))
    host.remember_alarm_film_csv_dir(str(stale))
    host.set_stale_prune_undo_ms(8000)
    host.prune_stale_alarm_film_csv_dirs(confirm=False)
    host._stale_prune_undo_custom_no_dialog = True
    host._stale_prune_undo_custom_step_ms = 2500
    assert host.prompt_stale_prune_undo_extend_step_ms() == 2500
    assert getattr(host, '_last_stale_prune_undo_step_custom', 0) == 2500
    host._stale_prune_undo_left_ms = 2000
    host._stale_prune_undo_custom_extend_ms = 4500
    assert host.prompt_stale_prune_undo_extend_ms() == 4500
    assert getattr(host, '_last_stale_prune_undo_extend_custom', 0) == 4500
    # menu actions present
    host._stale_prune_undo_step_menu_no_exec = True
    class _RE:
        def button(self):
            return Qt.MouseButton.RightButton
        def globalPosition(self):
            class _P:
                def toPoint(self):
                    return QPoint(12, 12)
            return _P()
    host._on_stale_prune_undo_bar_clicked(_RE())
    menu = host._last_stale_prune_undo_step_menu
    cust_step = [a for a in menu.actions() if a.property('isUndoStepCustom')]
    cust_ext = [a for a in menu.actions() if a.property('isUndoExtendCustom')]
    assert len(cust_step) == 1 and len(cust_ext) == 1
    ok('undo 预设 自定义 ms 输入')

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
