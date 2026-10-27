#!/usr/bin/env python3
"""细妆㊷：合并tip点开diff · 抢占音/色可配 · 保持徽标一键退出 · 徽章中键父目录 · undo倒计时失效."""
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
    from PySide6.QtWidgets import QApplication, QMessageBox, QFileDialog
    from PySide6.QtCore import QSettings, Qt
    app = QApplication.instance() or QApplication([])
    shown = {'n': 0, 'title': '', 'body': ''}
    def _info(parent, title, body, *a, **k):
        shown['n'] += 1
        shown['title'] = str(title)
        shown['body'] = str(body)
        return QMessageBox.StandardButton.Ok
    QMessageBox.information = staticmethod(_info)
    QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
    QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: ('', ''))
    QFileDialog.getOpenFileName = staticmethod(lambda *a, **k: ('', ''))

    from desktop.host_state_machine import HostStateMachineWidget
    src = Path('desktop/host_state_machine.py').read_text(encoding='utf-8')
    for name in (
        'show_last_merge_diff', 'set_sev_pin_arc_seize_color',
        'set_sev_pin_arc_seize_sound', 'sev_pin_arc_seize_color',
        'sev_pin_arc_seize_sound', 'exit_toast_hist_cap_keep',
        'open_path_copy_badge_parent', 'expire_stale_prune_undo',
        'set_stale_prune_undo_ms', 'stale_prune_undo_left_ms',
    ):
        assert hasattr(HostStateMachineWidget, name), name
    assert 'isKeepExit' in src and '点此退出' in src
    ok('wave42 APIs present')

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

    tmp = Path('/tmp/sieans-w42s'); tmp.mkdir(exist_ok=True)
    dirs = [tmp / f'd{i}' for i in range(6)]
    for d in dirs:
        d.mkdir(exist_ok=True)
    nested = tmp / 'nest' / 'leaf'; nested.mkdir(parents=True, exist_ok=True)
    stale = tmp / 'gone-w42'
    if stale.exists():
        import shutil
        shutil.rmtree(stale, ignore_errors=True)

    # --- 1. merge tip → diff list ---
    host.clear_alarm_film_csv_dirs()
    host.set_alarm_film_csv_dirs_max(5)
    host.remember_alarm_film_csv_dir(str(dirs[0]))
    host.remember_alarm_film_csv_dir(str(dirs[1]))
    payload = json.dumps({
        'max': 5,
        'dirs': [str(dirs[2]), str(dirs[0]), str(dirs[3])],
    })
    host.merge_import_alarm_film_csv_dirs_json(payload)
    tip = getattr(host, '_last_merge_import_tip', '') or ''
    assert '点开清单' in tip, tip
    assert getattr(host, '_host_toast_click_action', '') == 'merge_diff'
    diff = getattr(host, '_last_merge_diff', {})
    assert str(dirs[0]) in (diff.get('conflict') or [])
    assert str(dirs[2]) in (diff.get('new') or [])
    shown['n'] = 0
    assert host.show_last_merge_diff()
    assert shown['n'] == 1
    assert 'diff' in shown['title'].lower() or '合并' in shown['title']
    assert '新增' in shown['body'] and '冲突' in shown['body']
    assert getattr(host, '_last_merge_diff_shown', False)
    # toast click path
    shown['n'] = 0
    host._on_host_toast_clicked()
    assert shown['n'] == 1
    ok('合并 tip 点开 diff 清单')

    # --- 2. seize color/sound configurable ---
    assert host.sev_pin_arc_seize_color() == '#ffffff'
    assert host.set_sev_pin_arc_seize_color('#ff66aa') == '#ff66aa'
    assert host.sev_pin_arc_seize_color() == '#ff66aa'
    assert host.set_sev_pin_arc_seize_sound(False) is False
    assert host.sev_pin_arc_seize_sound() is False
    host._sev_pin_arc_owner = 'chip'
    host._last_sev_pin_arc_seize_beeped = None
    host.claim_sev_pin_arc('bubble', flash=True)
    assert getattr(host, '_last_sev_pin_arc_seize_flash_color', '') == '#ff66aa'
    assert getattr(host, '_last_sev_pin_arc_seize_beeped', True) is False
    host.set_sev_pin_arc_seize_sound(True)
    host._sev_pin_arc_owner = 'bubble'
    host.claim_sev_pin_arc('chip', flash=True)
    assert getattr(host, '_last_sev_pin_arc_seize_beeped', False) is True
    host.set_sev_pin_arc_seize_color('#ffffff')
    ok('抢占音/色可配')

    # --- 3. keep badge one-click exit ---
    host.set_liaison_toast_history_max(5, persist=False)
    host._toast_hist_cap_menu_no_exec = True
    host.set_toast_hist_cap_keep_open(True)
    menu = host._build_liaison_toast_capacity_menu()
    exit_act = None
    for a in menu.actions():
        if a.property('isKeepExit') or (
            a.property('isKeepBadge') and '退出' in (a.text() or '')
        ):
            exit_act = a
            break
    assert exit_act is not None
    assert exit_act.isEnabled()
    assert '退出' in (exit_act.text() or '')
    host._last_toast_hist_cap_menu = menu
    assert host.exit_toast_hist_cap_keep() is True
    assert host._toast_hist_cap_keep_open is False
    assert getattr(host, '_last_toast_hist_cap_keep_exited', False)
    # badge removed
    assert not any(a.property('isKeepBadge') for a in menu.actions())
    # digit now closes again
    menu2 = host._on_toast_hist_cap_hotkey()
    host._last_toast_hist_cap_menu = menu2
    r = host.toast_hist_cap_menu_key(Qt.Key.Key_3, menu2)
    assert r == ('digit', 8), r
    host.set_liaison_toast_history_max(5, persist=True)
    ok('保持徽标一键退出')

    # --- 4. badge middle-click parent ---
    host.flash_path_copy_badge(str(nested))
    opened = {'path': ''}
    real = host.open_host_toast_path
    def _fake():
        opened['path'] = getattr(host, '_host_toast_open_path', '')
        return opened['path']
    host.open_host_toast_path = _fake
    got = host.open_path_copy_badge_parent()
    assert str(nested.parent) in got or got == str(nested.parent), got
    assert opened['path'] == str(nested.parent)
    class _E:
        def button(self):
            return Qt.MouseButton.MiddleButton
    opened['path'] = ''
    host._on_path_copy_badge_clicked(_E())
    assert opened['path'] == str(nested.parent)
    host.open_host_toast_path = real
    ok('徽章中键开父目录')

    # --- 5. undo countdown expiry ---
    host.clear_alarm_film_csv_dirs()
    host.remember_alarm_film_csv_dir(str(dirs[0]))
    host.remember_alarm_film_csv_dir(str(stale))
    host.set_stale_prune_undo_ms(2000)
    assert host._stale_prune_undo_ms == 2000
    kept = host.prune_stale_alarm_film_csv_dirs(confirm=False)
    assert str(stale) not in kept
    assert host.can_undo_prune_stale_alarm_film_csv_dirs()
    assert host.stale_prune_undo_left_ms() > 0
    assert host._host_toast_click_action == 'undo_prune'
    # force expire
    assert host.expire_stale_prune_undo() is True
    assert not host.can_undo_prune_stale_alarm_film_csv_dirs()
    assert host.stale_prune_undo_left_ms() == 0
    assert getattr(host, '_last_stale_prune_undo_expired', False)
    assert host._host_toast_click_action != 'undo_prune'
    # undo after expire fails soft
    host.remember_alarm_film_csv_dir(str(stale))
    host.prune_stale_alarm_film_csv_dirs(confirm=False)
    # simulate tick to zero
    host._stale_prune_undo_left_ms = 200
    host._on_stale_prune_undo_tick()  # -> 0 -> expire
    assert not host.can_undo_prune_stale_alarm_film_csv_dirs()
    ok('undo 倒计时失效')

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
