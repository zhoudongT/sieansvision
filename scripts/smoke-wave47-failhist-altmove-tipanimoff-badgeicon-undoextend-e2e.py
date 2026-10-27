#!/usr/bin/env python3
"""细妆㊼：失败清单持久化/历史 · 最近色Alt↑↓ · tip动画可关 · 徽章菜单图标 · undo点击延长."""
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
    from PySide6.QtWidgets import QApplication, QMessageBox, QFileDialog, QProgressBar
    from PySide6.QtCore import QSettings, Qt, QEvent, QPoint
    from PySide6.QtGui import QKeyEvent, QIcon
    app = QApplication.instance() or QApplication([])
    QMessageBox.information = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
    QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
    QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: ('', ''))
    QFileDialog.getOpenFileName = staticmethod(lambda *a, **k: ('', ''))

    from desktop.host_state_machine import HostStateMachineWidget
    src = Path('desktop/host_state_machine.py').read_text(encoding='utf-8')
    for name in (
        'remember_merge_diff_batch_fails', 'merge_diff_batch_fail_history',
        'show_merge_diff_batch_fail_history', 'clear_merge_diff_batch_fail_history',
        'toast_hist_cap_tip_anim_enabled', 'set_toast_hist_cap_tip_anim_enabled',
        'extend_stale_prune_undo', '_path_copy_badge_menu_icon',
    ):
        assert hasattr(HostStateMachineWidget, name), name
    assert 'isTipAnimToggle' in src
    assert 'AltModifier' in src
    ok('wave47 APIs present')

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
    s.setValue('host/toastHistCapTipAnim', True)
    s.setValue('host/pathCopyBadgeParentFallback', True)
    s.setValue('host/mergeDiffBatchFailHistory', [])
    s.setValue('host/mergeDiffBatchFailLast', [])
    s.sync()
    host = HostStateMachineWidget(compact=True)
    host.show()
    host._toast_hist_cap_keep_exit_tip_quiet = True

    tmp = Path('/tmp/sieans-w47s'); tmp.mkdir(exist_ok=True)
    d0 = tmp / 'c0'; d0.mkdir(exist_ok=True)
    gone = '/tmp/sieans-w47-no-such-dir-xyz'
    stale = tmp / 'gone-w47'
    if stale.exists():
        import shutil
        shutil.rmtree(stale, ignore_errors=True)

    # --- 1. fail list persist / history ---
    host.clear_merge_diff_batch_fail_history()
    assert host.merge_diff_batch_fail_history() == []
    host.open_merge_diff_paths([str(d0), gone])
    hist = host.merge_diff_batch_fail_history()
    assert len(hist) >= 1, hist
    assert gone in (hist[0].get('paths') or [])
    assert getattr(host, '_last_merge_diff_batch_fail_remembered', []) 
    # persist round-trip via remember API
    host.remember_merge_diff_batch_fails(['/tmp/a', '/tmp/b'])
    assert len(host.merge_diff_batch_fail_history()) >= 1
    host._merge_diff_fail_hist_no_exec = True
    assert host.show_merge_diff_batch_fail_history() is True
    assert getattr(host, '_last_merge_diff_batch_fail_history_shown', False)
    lst = getattr(host, '_last_merge_diff_batch_fail_history_list', None)
    assert lst is not None and lst.count() >= 1
    # new host loads last from settings
    host2 = HostStateMachineWidget(compact=True)
    loaded = host2.merge_diff_batch_fail_history()
    assert any('/tmp/a' in (e.get('paths') or []) for e in loaded), loaded
    assert '/tmp/a' in host2._last_merge_diff_batch_fail
    host.clear_merge_diff_batch_fail_history()
    ok('失败清单 持久化/历史')

    # --- 2. recent color Alt Up/Down ---
    host.clear_sev_pin_arc_seize_recent_colors()
    for c in ('#bb0001', '#bb0002', '#bb0003'):
        host.remember_sev_pin_arc_seize_color(c)
    # recent front-inserted: #bb0003, #bb0002, #bb0001
    menu = host._build_sev_pin_arc_seize_color_menu()
    recent_acts = [a for a in menu.actions() if a.property('isSeizeColorRecent')]
    assert len(recent_acts) >= 3
    # activate middle (#bb0002) and Alt+Up → index 0
    target = None
    for a in recent_acts:
        if str(a.data()).lower() == '#bb0002':
            target = a
            break
    assert target is not None
    menu.setActiveAction(target)

    class _Key:
        def __init__(self, key):
            self._key = key
        def type(self):
            return QEvent.Type.KeyPress
        def key(self):
            return self._key
        def modifiers(self):
            return Qt.KeyboardModifier.AltModifier

    assert host._on_sev_pin_arc_seize_color_menu_event(menu, _Key(Qt.Key.Key_Up)) is True
    assert getattr(host, '_last_sev_pin_arc_seize_recent_alt_moved', '') == '#bb0002'
    assert host.sev_pin_arc_seize_recent_colors()[0] == '#bb0002'
    # Alt+Down moves back
    # rebuild may have new actions; find #bb0002 and activate
    menu = getattr(host, '_last_sev_pin_arc_seize_color_menu', menu)
    for a in menu.actions():
        if a.property('isSeizeColorRecent') and str(a.data()).lower() == '#bb0002':
            menu.setActiveAction(a)
            break
    assert host._on_sev_pin_arc_seize_color_menu_event(menu, _Key(Qt.Key.Key_Down)) is True
    assert host.sev_pin_arc_seize_recent_colors()[1] == '#bb0002'
    ok('最近色菜单 Alt↑↓')

    # --- 3. tip anim can disable ---
    host.set_toast_hist_cap_tip_anim_enabled(True)
    host._toast_hist_cap_menu_no_exec = True
    menu = host._build_liaison_toast_capacity_menu()
    host._last_toast_hist_cap_menu = menu
    anim_acts = [a for a in menu.actions() if a.property('isTipAnimToggle')]
    assert len(anim_acts) == 1 and anim_acts[0].isChecked()
    host._flash_host_toast('pulse-on', kind='info', ms=400, animate=True)
    assert getattr(host, '_last_host_toast_pulsed', False) is True
    host.set_toast_hist_cap_tip_anim_enabled(False)
    assert getattr(host, '_last_toast_hist_cap_tip_anim_refreshed', False) is True
    assert anim_acts[0].isChecked() is False
    assert host.toast_hist_cap_tip_anim_enabled() is False
    host._flash_host_toast('pulse-off', kind='info', ms=400, animate=True)
    assert getattr(host, '_last_host_toast_pulse_skipped', False) is True
    assert getattr(host, '_last_host_toast_pulsed', True) is False
    host.set_toast_hist_cap_tip_anim_enabled(True)
    ok('tip 动画 可关')

    # --- 4. badge menu icons ---
    host.flash_path_copy_badge(str(d0))
    menu = host._build_path_copy_badge_menu()
    assert getattr(host, '_last_path_copy_badge_menu_icons', False) is True
    copy_acts = [a for a in menu.actions() if a.property('isPathCopyBadgeCopy')]
    fb_acts = [a for a in menu.actions() if a.property('isPathCopyBadgeFallbackToggle')]
    assert len(copy_acts) == 1 and len(fb_acts) == 1
    assert not copy_acts[0].icon().isNull(), 'copy icon'
    assert not fb_acts[0].icon().isNull(), 'fb icon'
    ic = host._path_copy_badge_menu_icon('copy')
    assert isinstance(ic, QIcon) and not ic.isNull()
    ok('徽章菜单 图标')

    # --- 5. undo click extend countdown ---
    host.clear_alarm_film_csv_dirs()
    host.remember_alarm_film_csv_dir(str(d0))
    host.remember_alarm_film_csv_dir(str(stale))
    host.set_stale_prune_undo_ms(4000)
    host.prune_stale_alarm_film_csv_dirs(confirm=False)
    assert host.can_undo_prune_stale_alarm_film_csv_dirs()
    host._stale_prune_undo_left_ms = 800
    before = host.stale_prune_undo_left_ms()
    assert before == 800
    got = host.extend_stale_prune_undo()
    assert got == 4000
    assert host.stale_prune_undo_left_ms() == 4000
    assert getattr(host, '_last_stale_prune_undo_extended', 0) == 4000
    # middle click path
    host._stale_prune_undo_left_ms = 500
    class _ME:
        def button(self):
            return Qt.MouseButton.MiddleButton
    assert host._on_stale_prune_undo_bar_clicked(_ME()) is True
    assert getattr(host, '_last_stale_prune_undo_bar_extend_clicked', False) is True
    assert host.stale_prune_undo_left_ms() == 4000
    # left still undoes
    class _LE:
        def button(self):
            return Qt.MouseButton.LeftButton
    assert host._on_stale_prune_undo_bar_clicked(_LE()) is True
    assert getattr(host, '_last_stale_prune_undo_bar_clicked', False) is True
    assert host.can_undo_prune_stale_alarm_film_csv_dirs() is False
    ok('undo 点击 延长倒计时')

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
