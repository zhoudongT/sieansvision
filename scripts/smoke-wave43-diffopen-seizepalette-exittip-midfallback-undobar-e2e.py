#!/usr/bin/env python3
"""细妆㊸：diff清单可点开目录 · 抢占预设色板 · 保持退出确认tip · 中键失败回退本级 · undo进度条."""
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
    from PySide6.QtCore import QSettings, Qt
    app = QApplication.instance() or QApplication([])
    QMessageBox.information = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
    QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
    QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: ('', ''))
    QFileDialog.getOpenFileName = staticmethod(lambda *a, **k: ('', ''))

    from desktop.host_state_machine import HostStateMachineWidget
    src = Path('desktop/host_state_machine.py').read_text(encoding='utf-8')
    for name in (
        'show_last_merge_diff', 'open_merge_diff_path',
        'sev_pin_arc_seize_color_presets', '_build_sev_pin_arc_seize_color_menu',
        '_apply_sev_pin_arc_seize_color_preset', 'exit_toast_hist_cap_keep',
        'open_path_copy_badge_parent', '_show_stale_prune_undo_bar',
        '_hide_stale_prune_undo_bar', '_update_stale_prune_undo_bar',
    ):
        assert hasattr(HostStateMachineWidget, name), name
    assert 'hostMergeDiffDialog' in src and 'hostStalePruneUndoBar' in src
    assert 'isSeizeColorPreset' in src and 'isSeizeColorMenu' in src
    ok('wave43 APIs present')

    s = QSettings('SIEANS', 'VisionDesktop')
    s.setValue('host/alarmSevFilter', 'all')
    s.setValue('host/alarmSevPinned', '')
    s.setValue('host/liaisonToastHistMax', 5)
    s.setValue('host/alarmFilmCsvDirs', [])
    s.setValue('host/alarmFilmCsvDir', '')
    s.setValue('host/alarmFilmCsvDirsMax', 5)
    s.setValue('host/sevChipPinMs', 550)
    s.setValue('host/sevChipPinArcColor', '#f0c040')
    s.setValue('host/sevPinArcSeizeColor', '#ffffff')
    s.setValue('host/sevPinArcSeizeSound', True)
    s.sync()
    host = HostStateMachineWidget(compact=True)
    host.show()

    tmp = Path('/tmp/sieans-w43s'); tmp.mkdir(exist_ok=True)
    d0, d1, d2 = tmp / 'a0', tmp / 'a1', tmp / 'a2'
    for d in (d0, d1, d2):
        d.mkdir(exist_ok=True)
    nested = tmp / 'nest' / 'leaf'; nested.mkdir(parents=True, exist_ok=True)
    stale = tmp / 'gone-w43'
    if stale.exists():
        import shutil
        shutil.rmtree(stale, ignore_errors=True)

    # --- 1. diff list openable ---
    host.clear_alarm_film_csv_dirs()
    host.remember_alarm_film_csv_dir(str(d0))
    host.merge_import_alarm_film_csv_dirs_json(json.dumps({
        'max': 5, 'dirs': [str(d1), str(d0), str(d2)],
    }))
    host._merge_diff_no_exec = True
    assert host.show_last_merge_diff()
    lst = host._last_merge_diff_list
    assert lst is not None and lst.count() >= 2
    # find an item with UserRole path
    path_item = None
    for i in range(lst.count()):
        it = lst.item(i)
        if it and it.data(Qt.ItemDataRole.UserRole):
            path_item = it
            break
    assert path_item is not None
    opened = {'p': ''}
    real = host.open_host_toast_path
    def _fake():
        opened['p'] = getattr(host, '_host_toast_open_path', '')
        return opened['p']
    host.open_host_toast_path = _fake
    got = host.open_merge_diff_path(str(path_item.data(Qt.ItemDataRole.UserRole)))
    assert str(d1) in got or str(d0) in got or str(d2) in got or opened['p']
    host.open_host_toast_path = real
    ok('diff 清单可点开目录')

    # --- 2. seize color palette menu ---
    presets = host.sev_pin_arc_seize_color_presets()
    assert len(presets) >= 6
    menu = host._build_sev_pin_arc_seize_color_menu()
    assert menu.objectName() == 'hostSevPinArcSeizeColorMenu'
    preset_acts = [a for a in menu.actions() if a.property('isSeizeColorPreset')]
    assert len(preset_acts) >= 6
    snd_acts = [a for a in menu.actions() if a.property('isSeizeSoundToggle')]
    assert len(snd_acts) == 1
    host._apply_sev_pin_arc_seize_color_preset('#ff66aa')
    assert host.sev_pin_arc_seize_color() == '#ff66aa'
    assert getattr(host, '_last_sev_pin_arc_seize_preset', '') == '#ff66aa'
    # alarm context embeds menu
    host._alarm_ctx_menu_no_exec = True
    am = host._build_alarm_list_context_menu()
    found_seize = False
    for a in am.actions():
        m = a.menu()
        if m is None:
            continue
        # recent submenu
        for x in m.actions():
            if x.property('isSeizeColorMenu') or (
                x.menu() and x.menu().objectName() == 'hostSevPinArcSeizeColorMenu'
            ):
                found_seize = True
            xm = x.menu()
            if xm is not None and xm.objectName() == 'hostSevPinArcSeizeColorMenu':
                found_seize = True
    assert found_seize
    host.set_sev_pin_arc_seize_color('#ffffff')
    ok('抢占预设色板菜单')

    # --- 3. keep exit confirm tip ---
    host.set_toast_hist_cap_keep_open(True)
    host._toast_hist_cap_menu_no_exec = True
    menu = host._build_liaison_toast_capacity_menu()
    host._last_toast_hist_cap_menu = menu
    assert host.exit_toast_hist_cap_keep() is True
    tip = getattr(host, '_last_toast_hist_cap_keep_exit_tip', '') or ''
    assert '退出保持' in tip and '数字' in tip, tip
    toast = host._liaison_hotkey_toast
    assert toast is not None
    assert '退出保持' in (toast.text() or tip)
    ok('保持退出确认短 tip')

    # --- 4. mid-click fail → fallback 本级 ---
    # use a path whose parent does not exist (synthetic)
    bogus_parent_child = '/tmp/sieans-w43-no-such-parent-xyz/leaf'
    host.flash_path_copy_badge(bogus_parent_child)
    opened = {'p': ''}
    host.open_host_toast_path = _fake
    # also make nested work first as control
    host._path_copy_badge_path = str(nested)
    got_ok = host.open_path_copy_badge_parent()
    assert not getattr(host, '_last_path_copy_badge_parent_fallback', True)
    assert str(nested.parent) in (got_ok or '')
    # now fail case: parent missing
    host._path_copy_badge_path = bogus_parent_child
    # stub open: parent fails (return ''), then 本级 succeeds
    calls = {'n': 0, 'paths': []}
    def _fake2():
        calls['n'] += 1
        pth = getattr(host, '_host_toast_open_path', '')
        calls['paths'].append(pth)
        # first call (parent) fail; second (本级) ok if path equals badge
        if pth == bogus_parent_child:
            return pth
        # parent path won't exist — open_host_toast_path normally returns ''
        # Our open_path_copy_badge_parent checks _parent_openable first
        return ''
    host.open_host_toast_path = _fake2
    # _parent_openable is False for missing parent → fallback before open
    got_fb = host.open_path_copy_badge_parent()
    assert getattr(host, '_last_path_copy_badge_parent_fallback', False) is True
    assert bogus_parent_child in (got_fb or '') or bogus_parent_child in calls['paths']
    host.open_host_toast_path = real
    ok('中键失败回退本级')

    # --- 5. undo progress bar ---
    bar = host._stale_prune_undo_bar
    assert isinstance(bar, QProgressBar)
    assert bar.objectName() == 'hostStalePruneUndoBar'
    host.clear_alarm_film_csv_dirs()
    host.remember_alarm_film_csv_dir(str(d0))
    host.remember_alarm_film_csv_dir(str(stale))
    host.set_stale_prune_undo_ms(3000)
    host.prune_stale_alarm_film_csv_dirs(confirm=False)
    assert host.can_undo_prune_stale_alarm_film_csv_dirs()
    assert getattr(host, '_last_stale_prune_undo_bar_visible', False)
    assert not bar.isHidden()
    assert bar.value() > 0
    v0 = bar.value()
    host._stale_prune_undo_left_ms = host._stale_prune_undo_ms // 2
    host._update_stale_prune_undo_bar()
    assert bar.value() < v0 or bar.value() == 500
    host.expire_stale_prune_undo()
    assert bar.isHidden() or not getattr(host, '_last_stale_prune_undo_bar_visible', True)
    ok('undo 进度条可视化')

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
