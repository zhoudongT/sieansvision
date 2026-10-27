#!/usr/bin/env python3
"""细妆㊡：失败历史全展/全折 · Ctrl+A · 双缓动对比 · 清历史撤销 · undo色阶预设."""
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
        QApplication, QMessageBox, QFileDialog, QAbstractItemView,
    )
    from PySide6.QtCore import QSettings, Qt, QEvent
    from PySide6.QtGui import QKeyEvent
    app = QApplication.instance() or QApplication([])
    QMessageBox.information = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
    QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)
    QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: ('', ''))
    QFileDialog.getOpenFileName = staticmethod(lambda *a, **k: ('', ''))

    from desktop.host_state_machine import HostStateMachineWidget
    src = Path('desktop/host_state_machine.py').read_text(encoding='utf-8')
    for name in (
        'expand_merge_diff_batch_fail_history_groups',
        'collapse_merge_diff_batch_fail_history_groups',
        'undo_path_copy_badge_fail_history_clear',
        'can_undo_path_copy_badge_fail_history_clear',
        'show_toast_hist_cap_tip_anim_easing_curve_compare',
        'set_stale_prune_undo_color_scale_preset',
        'stale_prune_undo_color_scale_preset',
    ):
        assert hasattr(HostStateMachineWidget, name), name
    assert 'isUndoColorScalePreset' in src and 'isPathCopyBadgeFailHistoryUndo' in src
    ok('wave52 APIs present')

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

    tmp = Path('/tmp/sieans-w52s'); tmp.mkdir(exist_ok=True)
    d0 = tmp / 'c0'; d0.mkdir(exist_ok=True)
    stale = tmp / 'gone-w52'
    if stale.exists():
        import shutil
        shutil.rmtree(stale, ignore_errors=True)

    # --- 1. expand / collapse all ---
    now = datetime.now()
    day0 = (now - timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')
    day1 = now.strftime('%Y-%m-%d %H:%M:%S')
    host._merge_diff_batch_fail_history = [
        {'ts': day0, 'paths': ['/tmp/w52-d0/a']},
        {'ts': day1, 'paths': ['/tmp/w52-d1/b']},
        {'ts': day1, 'paths': ['/tmp/w52-d1/c']},
    ]
    host._merge_diff_fail_hist_no_exec = True
    host._merge_diff_fail_hist_collapsed = set()
    assert host.show_merge_diff_batch_fail_history() is True
    assert getattr(host, '_last_merge_diff_batch_fail_history_expand_btn', None) is not None
    assert getattr(host, '_last_merge_diff_batch_fail_history_collapse_btn', None) is not None
    keys = host.collapse_merge_diff_batch_fail_history_groups()
    assert len(keys) >= 2
    assert getattr(host, '_last_merge_diff_batch_fail_history_all_collapsed', False) is True
    assert host.show_merge_diff_batch_fail_history() is True
    n_col = host._last_merge_diff_batch_fail_history_list.count()
    # only headers when collapsed
    assert n_col == getattr(host, '_last_merge_diff_batch_fail_history_groups', 0)
    host.expand_merge_diff_batch_fail_history_groups()
    assert getattr(host, '_last_merge_diff_batch_fail_history_all_expanded', False) is True
    assert host.show_merge_diff_batch_fail_history() is True
    n_exp = host._last_merge_diff_batch_fail_history_list.count()
    assert n_exp > n_col
    ok('失败历史 组头全展/全折')

    # --- 2. Ctrl+A ---
    host.clear_sev_pin_arc_seize_recent_colors()
    for c in ('#dd0001', '#dd0002', '#dd0003'):
        host.remember_sev_pin_arc_seize_color(c)
    drag = host._make_sev_pin_arc_seize_recent_drag_list()
    drag.clearSelection()
    assert len(drag.selectedItems()) == 0
    ev_a = QKeyEvent(
        QEvent.Type.KeyPress, Qt.Key.Key_A,
        Qt.KeyboardModifier.ControlModifier)
    drag.keyPressEvent(ev_a)
    assert getattr(host, '_last_sev_pin_arc_seize_recent_key_select_all', False) is True
    assert len(drag.selectedItems()) == drag.count()
    assert getattr(host, '_last_sev_pin_arc_seize_recent_key_select_all_n', 0) == drag.count()
    ok('拖拽列表 Ctrl+A')

    # --- 3. dual curve compare ---
    host._toast_hist_cap_tip_anim_curve_no_exec = True
    assert host.show_toast_hist_cap_tip_anim_easing_curve_compare(
        'OutCubic', 'OutBounce') is True
    assert getattr(host, '_last_toast_hist_cap_tip_anim_curve_compare_shown', False) is True
    assert getattr(host, '_last_toast_hist_cap_tip_anim_curve_name', '') == 'OutCubic'
    assert getattr(host, '_last_toast_hist_cap_tip_anim_curve_compare', '') == 'OutBounce'
    pane = getattr(host, '_last_toast_hist_cap_tip_anim_curve_pane', None)
    assert pane is not None and pane._pts_b is not None and pane._name_b == 'OutBounce'
    box_b = getattr(host, '_last_toast_hist_cap_tip_anim_curve_box_b', None)
    assert box_b is not None
    ok('曲线小窗 对比双缓动')

    # --- 4. badge clear undo ---
    host._merge_diff_batch_fail_history = [
        {'ts': day1, 'paths': ['/tmp/w52-undo/a']},
        {'ts': day0, 'paths': ['/tmp/w52-undo/b']},
    ]
    host._path_copy_badge_fail_history_can_undo = False
    host._path_copy_badge_fail_history_undo = None
    host._path_copy_badge_fail_hist_clear_no_confirm = True
    snap = host.clear_path_copy_badge_fail_history(confirm=False)
    assert len(snap) == 2
    assert len(host.merge_diff_batch_fail_history()) == 0
    assert host.can_undo_path_copy_badge_fail_history_clear() is True
    menu = host._build_path_copy_badge_menu()
    undo_acts = [a for a in menu.actions() if a.property('isPathCopyBadgeFailHistoryUndo')]
    assert len(undo_acts) == 1 and undo_acts[0].isEnabled() is True
    restored = host.undo_path_copy_badge_fail_history_clear()
    assert len(restored) == 2
    assert len(host.merge_diff_batch_fail_history()) == 2
    assert host.can_undo_path_copy_badge_fail_history_clear() is False
    menu2 = host._build_path_copy_badge_menu()
    undo2 = [a for a in menu2.actions() if a.property('isPathCopyBadgeFailHistoryUndo')]
    assert undo2[0].isEnabled() is False
    ok('徽章清历史 撤销')

    # --- 5. undo color scale presets ---
    assert host.stale_prune_undo_color_scale_preset() == 'traffic'
    host.clear_alarm_film_csv_dirs()
    host.remember_alarm_film_csv_dir(str(d0))
    host.remember_alarm_film_csv_dir(str(stale))
    host.set_stale_prune_undo_ms(8000)
    host.prune_stale_alarm_film_csv_dirs(confirm=False)
    host._stale_prune_can_undo = True
    host._stale_prune_undo_left_ms = 8000
    host._show_stale_prune_undo_bar()
    host.set_stale_prune_undo_color_scale_preset('cool')
    assert host.stale_prune_undo_color_scale_preset() == 'cool'
    host._update_stale_prune_undo_bar()
    assert getattr(host, '_last_stale_prune_undo_color_scale_used', '') == 'cool'
    c_cool = getattr(host, '_last_stale_prune_undo_bar_chunk_color', '')
    assert c_cool in ('#5b9cff', '#6ec8ff')
    host.set_stale_prune_undo_color_scale_preset('sunset')
    host._stale_prune_undo_left_ms = 800
    host._update_stale_prune_undo_bar()
    assert getattr(host, '_last_stale_prune_undo_bar_chunk_color', '') == '#e35d6a'
    host.set_stale_prune_undo_color_scale_preset('mono')
    host._stale_prune_undo_left_ms = 8000
    host._update_stale_prune_undo_bar()
    assert getattr(host, '_last_stale_prune_undo_bar_chunk_color', '') == '#f0c040'
    host._stale_prune_undo_step_menu_no_exec = True
    menu = host._build_stale_prune_undo_step_menu()
    cs_acts = [a for a in menu.actions() if a.property('isUndoColorScalePreset')]
    assert len(cs_acts) >= 4
    host.set_stale_prune_undo_color_scale_preset('traffic')
    ok('undo 色阶 预设')

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
