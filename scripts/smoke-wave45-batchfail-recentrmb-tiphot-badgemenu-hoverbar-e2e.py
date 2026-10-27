#!/usr/bin/env python3
"""细妆㊺：diff批量失败汇总tip · 最近色右键清除 · tip开关热更勾 · 回退开关挂徽章菜单 · undo条悬停放大."""
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
    from PySide6.QtWidgets import QApplication, QMessageBox, QFileDialog, QProgressBar
    from PySide6.QtCore import QSettings, Qt, QEvent, QPoint
    from PySide6.QtGui import QMouseEvent
    app = QApplication.instance() or QApplication([])
    QMessageBox.information = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
    QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
    QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: ('', ''))
    QFileDialog.getOpenFileName = staticmethod(lambda *a, **k: ('', ''))

    from desktop.host_state_machine import HostStateMachineWidget
    src = Path('desktop/host_state_machine.py').read_text(encoding='utf-8')
    for name in (
        'open_merge_diff_paths', 'clear_sev_pin_arc_seize_recent_color',
        'clear_sev_pin_arc_seize_recent_colors',
        '_refresh_toast_hist_cap_keep_exit_tip_action',
        '_build_path_copy_badge_menu', '_show_path_copy_badge_menu',
        '_on_stale_prune_undo_bar_enter', '_on_stale_prune_undo_bar_leave',
        '_on_sev_pin_arc_seize_color_menu_event',
    ):
        assert hasattr(HostStateMachineWidget, name), name
    assert 'isPathCopyBadgeFallbackToggle' in src
    assert 'isSeizeRecentClearAll' in src
    assert '_last_merge_diff_batch_fail' in src
    ok('wave45 APIs present')

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

    tmp = Path('/tmp/sieans-w45s'); tmp.mkdir(exist_ok=True)
    d0, d1 = tmp / 'c0', tmp / 'c1'
    for d in (d0, d1):
        d.mkdir(exist_ok=True)
    gone = '/tmp/sieans-w45-no-such-dir-xyz'
    stale = tmp / 'gone-w45'
    if stale.exists():
        import shutil
        shutil.rmtree(stale, ignore_errors=True)

    # --- 1. batch fail summary tip ---
    batch = host.open_merge_diff_paths([str(d0), gone, str(d1), gone])
    assert len(batch) == 2, batch
    fails = getattr(host, '_last_merge_diff_batch_fail', [])
    assert len(fails) == 1 and gone in fails
    tip = getattr(host, '_last_merge_diff_batch_tip', '')
    assert '失败' in tip and ('已开' in tip or '2' in tip), tip
    assert getattr(host, '_last_merge_diff_batch_fail_n', 0) == 1
    # all fail
    batch2 = host.open_merge_diff_paths([gone, '/tmp/sieans-w45-nope2'])
    assert batch2 == []
    tip2 = getattr(host, '_last_merge_diff_batch_tip', '')
    assert '失败' in tip2, tip2
    ok('diff 批量开失败汇总 tip')

    # --- 2. recent color RMB clear ---
    host._apply_sev_pin_arc_seize_color_preset('#c0ffee')
    host._apply_sev_pin_arc_seize_color_preset('#ff66aa')
    recent = host.sev_pin_arc_seize_recent_colors()
    assert '#ff66aa' in recent and '#c0ffee' in recent
    menu = host._build_sev_pin_arc_seize_color_menu()
    recent_acts = [a for a in menu.actions() if a.property('isSeizeColorRecent')]
    assert len(recent_acts) >= 2
    # simulate RMB via handler
    target = None
    for a in recent_acts:
        if str(a.data()).lower() == '#c0ffee':
            target = a
            break
    assert target is not None
    # use clear API + menu event path
    class _Ev:
        def type(self):
            return QEvent.Type.MouseButtonPress
        def button(self):
            return Qt.MouseButton.RightButton
        def pos(self):
            # actionAt may miss — call clear directly after verifying handler exists
            return QPoint(0, 0)
    # direct clear one
    left = host.clear_sev_pin_arc_seize_recent_color('#c0ffee')
    assert '#c0ffee' not in left
    assert '#ff66aa' in left
    assert getattr(host, '_last_sev_pin_arc_seize_recent_cleared', '') == '#c0ffee'
    # clear all via menu action
    menu = host._build_sev_pin_arc_seize_color_menu()
    clear_acts = [a for a in menu.actions() if a.property('isSeizeRecentClearAll')]
    assert len(clear_acts) == 1
    clear_acts[0].trigger()
    assert host.sev_pin_arc_seize_recent_colors() == []
    # event filter path: put color back, mock actionAt
    host.remember_sev_pin_arc_seize_color('#aabbcc')
    menu = host._build_sev_pin_arc_seize_color_menu()
    recent_acts = [a for a in menu.actions() if a.property('isSeizeColorRecent')]
    assert recent_acts
    real_at = menu.actionAt
    menu.actionAt = lambda pos: recent_acts[0]
    assert host._on_sev_pin_arc_seize_color_menu_event(menu, _Ev()) is True
    assert getattr(host, '_last_sev_pin_arc_seize_recent_rmb_cleared', '') == '#aabbcc'
    assert '#aabbcc' not in host.sev_pin_arc_seize_recent_colors()
    menu.actionAt = real_at
    ok('最近色 右键清除')

    # --- 3. tip toggle hot-update menu check ---
    host.set_toast_hist_cap_keep_exit_tip_enabled(True)
    host._toast_hist_cap_menu_no_exec = True
    menu = host._build_liaison_toast_capacity_menu()
    host._last_toast_hist_cap_menu = menu
    tip_acts = [a for a in menu.actions() if a.property('isKeepExitTipToggle')]
    assert len(tip_acts) == 1 and tip_acts[0].isChecked()
    host.set_toast_hist_cap_keep_exit_tip_enabled(False)
    assert getattr(host, '_last_toast_hist_cap_keep_exit_tip_refreshed', False) is True
    assert tip_acts[0].isChecked() is False
    assert not tip_acts[0].text().startswith('✓')
    host.set_toast_hist_cap_keep_exit_tip_enabled(True)
    assert tip_acts[0].isChecked() is True
    assert tip_acts[0].text().startswith('✓')
    ok('tip 开关 热更菜单勾')

    # --- 4. fallback toggle on badge menu ---
    host.flash_path_copy_badge(str(d0))
    host._path_copy_badge_menu_no_exec = True
    class _RE:
        def button(self):
            return Qt.MouseButton.RightButton
        def globalPosition(self):
            class _P:
                def toPoint(self):
                    return QPoint(10, 10)
            return _P()
    host._on_path_copy_badge_clicked(_RE())
    menu = host._last_path_copy_badge_menu
    assert menu is not None
    assert menu.objectName() == 'hostPathCopyBadgeMenu'
    fb_acts = [a for a in menu.actions() if a.property('isPathCopyBadgeFallbackToggle')]
    copy_acts = [a for a in menu.actions() if a.property('isPathCopyBadgeCopy')]
    assert len(fb_acts) == 1 and len(copy_acts) == 1
    assert fb_acts[0].isChecked() is True
    host.set_path_copy_badge_parent_fallback_enabled(False)
    assert fb_acts[0].isChecked() is False
    fb_acts[0].trigger()  # toggle back on via menu
    assert host.path_copy_badge_parent_fallback_enabled() is True
    ok('回退开关 挂徽章菜单')

    # --- 5. undo bar hover enlarge ---
    bar = host._stale_prune_undo_bar
    assert isinstance(bar, QProgressBar)
    base_h = bar.height()
    host.clear_alarm_film_csv_dirs()
    host.remember_alarm_film_csv_dir(str(d0))
    host.remember_alarm_film_csv_dir(str(stale))
    host.set_stale_prune_undo_ms(3000)
    host.prune_stale_alarm_film_csv_dirs(confirm=False)
    assert getattr(host, '_last_stale_prune_undo_bar_visible', False)
    host._on_stale_prune_undo_bar_enter()
    assert getattr(host, '_last_stale_prune_undo_bar_hovered', False) is True
    assert bar.height() >= 16 or bar.height() > base_h
    hover_h = bar.height()
    host._on_stale_prune_undo_bar_leave()
    assert getattr(host, '_last_stale_prune_undo_bar_hovered', True) is False
    assert bar.height() < hover_h or bar.height() == int(getattr(host, '_stale_prune_undo_bar_base_h', 10))
    ok('undo 条 悬停放大')

    print(f'\nRESULT pass={pass_n} fail={fail_n}', flush=True)
    return 0 if fail_n == 0 else 1

if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:
        import traceback
        traceback.print_exc()
        bad(f'exception: {exc}')
        print(f'\nRESULT pass={pass_n} fail={fail_n}', flush=True)
        raise SystemExit(1)
