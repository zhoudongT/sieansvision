#!/usr/bin/env python3
"""细妆㊹：diff多选批量开目录 · 色板自定义/最近色 · 保持tip可关 · 中键回退可配 · undo条可点撤销."""
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
    from PySide6.QtWidgets import QApplication, QMessageBox, QFileDialog, QProgressBar, QListWidget
    from PySide6.QtCore import QSettings, Qt
    app = QApplication.instance() or QApplication([])
    QMessageBox.information = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
    QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
    QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: ('', ''))
    QFileDialog.getOpenFileName = staticmethod(lambda *a, **k: ('', ''))

    from desktop.host_state_machine import HostStateMachineWidget
    src = Path('desktop/host_state_machine.py').read_text(encoding='utf-8')
    for name in (
        'open_merge_diff_paths', 'open_merge_diff_selected',
        'sev_pin_arc_seize_recent_colors', 'remember_sev_pin_arc_seize_color',
        'pick_sev_pin_arc_seize_custom_color',
        'toast_hist_cap_keep_exit_tip_enabled', 'set_toast_hist_cap_keep_exit_tip_enabled',
        'path_copy_badge_parent_fallback_enabled', 'set_path_copy_badge_parent_fallback_enabled',
        '_on_stale_prune_undo_bar_clicked',
    ):
        assert hasattr(HostStateMachineWidget, name), name
    assert 'hostMergeDiffOpenBtn' in src and '打开选中' in src
    assert 'isSeizeColorRecent' in src and 'isSeizeColorCustom' in src
    assert 'isKeepExitTipToggle' in src
    assert 'pathCopyBadgeParentFallback' in src
    ok('wave44 APIs present')

    s = QSettings('SIEANS', 'VisionDesktop')
    s.setValue('host/alarmSevFilter', 'all')
    s.setValue('host/alarmSevPinned', '')
    s.setValue('host/liaisonToastHistMax', 5)
    s.setValue('host/alarmFilmCsvDirs', [])
    s.setValue('host/alarmFilmCsvDir', '')
    s.setValue('host/alarmFilmCsvDirsMax', 5)
    s.setValue('host/sevChipPinMs', 550)
    s.setValue('host/sevPinArcSeizeColor', '#ffffff')
    s.setValue('host/sevPinArcSeizeSound', True)
    s.setValue('host/sevPinArcSeizeRecentColors', [])
    s.setValue('host/toastHistCapKeepExitTip', True)
    s.setValue('host/pathCopyBadgeParentFallback', True)
    s.sync()
    host = HostStateMachineWidget(compact=True)
    host.show()

    tmp = Path('/tmp/sieans-w44s'); tmp.mkdir(exist_ok=True)
    d0, d1, d2 = tmp / 'b0', tmp / 'b1', tmp / 'b2'
    for d in (d0, d1, d2):
        d.mkdir(exist_ok=True)
    nested = tmp / 'nest' / 'leaf'; nested.mkdir(parents=True, exist_ok=True)
    stale = tmp / 'gone-w44'
    if stale.exists():
        import shutil
        shutil.rmtree(stale, ignore_errors=True)

    # --- 1. diff multi-select batch ---
    host.clear_alarm_film_csv_dirs()
    host.remember_alarm_film_csv_dir(str(d0))
    host.merge_import_alarm_film_csv_dirs_json(json.dumps({
        'max': 5, 'dirs': [str(d1), str(d0), str(d2)],
    }))
    host._merge_diff_no_exec = True
    assert host.show_last_merge_diff()
    lst = host._last_merge_diff_list
    assert lst is not None
    assert lst.selectionMode() == QListWidget.SelectionMode.ExtendedSelection
    # select all path items
    path_items = []
    for i in range(lst.count()):
        it = lst.item(i)
        if it and it.data(Qt.ItemDataRole.UserRole):
            path_items.append(it)
            it.setSelected(True)
    assert len(path_items) >= 2
    opened = {'paths': []}
    real = host.open_host_toast_path
    def _fake():
        pth = getattr(host, '_host_toast_open_path', '')
        opened['paths'].append(pth)
        return pth
    host.open_host_toast_path = _fake
    batch = host.open_merge_diff_selected(lst)
    assert len(batch) >= 2, batch
    assert len(getattr(host, '_last_merge_diff_opened_batch', []) or []) >= 2
    # also direct API
    batch2 = host.open_merge_diff_paths([str(d0), str(d1), str(d0)])
    assert len(batch2) == 2  # dedupe
    host.open_host_toast_path = real
    ok('diff 多选批量开目录')

    # --- 2. custom / recent colors ---
    host.set_sev_pin_arc_seize_color('#ffffff')
    host._sev_pin_arc_seize_recent = []
    host._seize_color_no_dialog = True
    host._seize_color_smoke_pick = '#c0ffee'
    got = host.pick_sev_pin_arc_seize_custom_color()
    assert got.lower() == '#c0ffee'
    assert '#c0ffee' in [c.lower() for c in host.sev_pin_arc_seize_recent_colors()]
    host._apply_sev_pin_arc_seize_color_preset('#ff66aa')
    recent = host.sev_pin_arc_seize_recent_colors()
    assert recent[0] == '#ff66aa'
    assert '#c0ffee' in recent
    menu = host._build_sev_pin_arc_seize_color_menu()
    recent_acts = [a for a in menu.actions() if a.property('isSeizeColorRecent')]
    custom_acts = [a for a in menu.actions() if a.property('isSeizeColorCustom')]
    assert len(recent_acts) >= 1
    assert len(custom_acts) == 1
    host.set_sev_pin_arc_seize_color('#ffffff')
    ok('色板 自定义/最近色')

    # --- 3. keep exit tip toggle ---
    host.set_toast_hist_cap_keep_exit_tip_enabled(True)
    host.set_toast_hist_cap_keep_open(True)
    host._toast_hist_cap_menu_no_exec = True
    menu = host._build_liaison_toast_capacity_menu()
    tip_acts = [a for a in menu.actions() if a.property('isKeepExitTipToggle')]
    assert len(tip_acts) == 1 and tip_acts[0].isChecked()
    host._last_toast_hist_cap_menu = menu
    assert host.exit_toast_hist_cap_keep() is True
    assert '退出保持' in (getattr(host, '_last_toast_hist_cap_keep_exit_tip', '') or '')
    # disable tip
    host.set_toast_hist_cap_keep_exit_tip_enabled(False)
    assert host.toast_hist_cap_keep_exit_tip_enabled() is False
    host.set_toast_hist_cap_keep_open(True)
    menu = host._build_liaison_toast_capacity_menu()
    host._last_toast_hist_cap_menu = menu
    assert host.exit_toast_hist_cap_keep() is True
    assert getattr(host, '_last_toast_hist_cap_keep_exit_tip', 'x') == ''
    host.set_toast_hist_cap_keep_exit_tip_enabled(True)
    ok('保持 tip 可关')

    # --- 4. mid fallback configurable ---
    host.set_path_copy_badge_parent_fallback_enabled(True)
    assert host.path_copy_badge_parent_fallback_enabled() is True
    bogus = '/tmp/sieans-w44-no-parent-xyz/leaf'
    host._path_copy_badge_path = bogus
    host.open_host_toast_path = _fake
    got_fb = host.open_path_copy_badge_parent()
    assert getattr(host, '_last_path_copy_badge_parent_fallback', False) is True
    assert bogus in (got_fb or '')
    # disable fallback
    host.set_path_copy_badge_parent_fallback_enabled(False)
    assert host.path_copy_badge_parent_fallback_enabled() is False
    host._path_copy_badge_path = bogus
    got_off = host.open_path_copy_badge_parent()
    assert got_off == ''
    assert getattr(host, '_last_path_copy_badge_parent_fallback', True) is False
    # control: nested parent works even when fallback off
    host._path_copy_badge_path = str(nested)
    got_ok = host.open_path_copy_badge_parent()
    assert str(nested.parent) in (got_ok or '')
    host.set_path_copy_badge_parent_fallback_enabled(True)
    host.open_host_toast_path = real
    ok('中键回退 可配')

    # --- 5. undo bar clickable ---
    bar = host._stale_prune_undo_bar
    assert isinstance(bar, QProgressBar)
    assert bar.cursor().shape() == Qt.CursorShape.PointingHandCursor
    host.clear_alarm_film_csv_dirs()
    host.remember_alarm_film_csv_dir(str(d0))
    host.remember_alarm_film_csv_dir(str(stale))
    host.set_stale_prune_undo_ms(3000)
    host.prune_stale_alarm_film_csv_dirs(confirm=False)
    assert host.can_undo_prune_stale_alarm_film_csv_dirs()
    assert getattr(host, '_last_stale_prune_undo_bar_visible', False)
    # simulate click
    class _E:
        def button(self):
            return Qt.MouseButton.LeftButton
    assert host._on_stale_prune_undo_bar_clicked(_E()) is True
    assert getattr(host, '_last_stale_prune_undo_bar_clicked', False) is True
    assert getattr(host, '_last_stale_prune_undone', False) is True
    assert not host.can_undo_prune_stale_alarm_film_csv_dirs()
    ok('undo 条 可点撤销')

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
