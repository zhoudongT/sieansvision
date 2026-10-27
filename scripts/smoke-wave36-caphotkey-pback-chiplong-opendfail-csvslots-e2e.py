#!/usr/bin/env python3
"""细妆㊱：容量Alt+H · Shift+Alt+P回退 · 预览钉长按落钉 · 开目录失败tip · CSV多档记忆."""
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
    from PySide6.QtWidgets import QApplication, QMessageBox
    from PySide6.QtCore import QSettings, Qt
    from PySide6.QtGui import QImage
    app = QApplication.instance() or QApplication([])
    QMessageBox.information = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)

    from desktop.host_state_machine import HostStateMachineWidget
    src = Path('desktop/host_state_machine.py').read_text(encoding='utf-8')
    for name in (
        '_on_toast_hist_cap_hotkey', '_on_sev_chip_press', '_on_sev_chip_release',
        '_on_sev_chip_long_press', '_flash_open_dir_fail_tip',
        'alarm_film_csv_dirs', 'remember_alarm_film_csv_dir',
        'save_all_alarm_film_paths_csv_to_dir',
    ):
        assert hasattr(HostStateMachineWidget, name), name
    assert 'Shift+Alt+P' in src and 'Alt+H' in src
    assert 'host/alarmFilmCsvDirs' in src
    ok('wave36 APIs present')

    s = QSettings('SIEANS', 'VisionDesktop')
    s.setValue('host/alarmSevFilter', 'all')
    s.setValue('host/alarmSevPinned', '')
    s.setValue('host/liaisonToastHistMax', 5)
    s.setValue('host/alarmFilmCsvDirs', [])
    s.setValue('host/alarmFilmCsvDir', '')
    s.sync()
    host = HostStateMachineWidget(compact=True)
    host.show()

    # --- Alt+H capacity menu hotkey ---
    host._toast_hist_cap_menu_no_exec = True
    menu = host._on_toast_hist_cap_hotkey()
    assert menu is not None
    texts = [a.text() for a in menu.actions() if a.text()]
    assert any('容量 5' in (x or '') for x in texts), texts
    assert any('[1]' in (x or '') or '容量 3' in (x or '') for x in texts), texts
    tip = host._liaison_toast_history_bar.toolTip() or ''
    assert 'Alt+H' in tip
    ok('容量菜单快捷键 Alt+H')

    # --- Shift+Alt+P reverse gear ---
    host.pin_alarm_severity_filter(False)
    host.set_alarm_severity_filter('warning', force=True)
    host._on_sev_pin_hotkey()  # pin warning
    assert host._alarm_sev_pinned_key == 'warning'
    host._on_sev_pin_hotkey()  # forward → info
    assert host._alarm_sev_pinned_key == 'info'
    host._on_sev_pin_hotkey(reverse=True)  # back → warning
    assert host._alarm_sev_pinned_key == 'warning'
    toast = host._liaison_hotkey_toast.text() or ''
    assert '切档' in toast and ('←' in toast or 'Shift' in toast)
    host._on_sev_pin_hotkey(reverse=True)  # → error
    assert host._alarm_sev_pinned_key == 'error'
    ok('Shift+Alt+P 回退切档')

    # --- preview pin long-press drop ---
    host.pin_alarm_severity_filter(False)
    host._on_sev_chip_enter(None, 'info')
    assert '📍' in (host._alarm_sev_chips['info'].text() or '')
    host._sev_chip_pin_key = 'info'
    host._on_sev_chip_long_press()
    assert host._alarm_sev_pinned and host._alarm_sev_pinned_key == 'info'
    assert '📌' in (host._alarm_sev_chips['info'].text() or '')
    assert '落钉' in (host._liaison_hotkey_toast.text() or '')
    # short release should not override after long
    host._sev_chip_long_fired = True
    host._on_sev_chip_release(None, 'error')
    assert host._alarm_sev_pinned_key == 'info'
    ok('预览钉长按落钉')

    # --- open dir fail tip ---
    host._host_toast_open_path = '/tmp/sieans-w36-no-such-dir-xyz'
    host._liaison_hotkey_toast.hide()
    got = host.open_host_toast_path()
    assert got == ''
    tt = host._liaison_hotkey_toast.text() or ''
    assert '失败' in tt or '不存在' in tt
    # empty path
    host._host_toast_open_path = ''
    host.open_host_toast_path()
    assert '失败' in (host._liaison_hotkey_toast.text() or '') or '无绑定' in (host._liaison_hotkey_toast.text() or '')
    ok('toast 开目录失败 tip')

    # --- CSV multi-slot remember ---
    tmp = Path('/tmp/sieans-w36s'); tmp.mkdir(exist_ok=True)
    d1 = tmp / 'slot1'; d2 = tmp / 'slot2'; d3 = tmp / 'slot3'
    for d in (d1, d2, d3):
        d.mkdir(exist_ok=True)
    host.remember_alarm_film_csv_dir(str(d1))
    host.remember_alarm_film_csv_dir(str(d2))
    host.remember_alarm_film_csv_dir(str(d3))
    dirs = host.alarm_film_csv_dirs()
    assert dirs[0] == str(d3) and str(d2) in dirs and str(d1) in dirs, dirs
    assert host.alarm_film_csv_dir() == str(d3)
    # re-push d1 → front
    host.remember_alarm_film_csv_dir(str(d1))
    dirs = host.alarm_film_csv_dirs()
    assert dirs[0] == str(d1) and dirs.count(str(d1)) == 1
    # save to remembered dir
    fp = tmp / 'a.bmp'
    img = QImage(8, 8, QImage.Format.Format_RGB32)
    img.fill(0xFF405060)
    img.save(str(fp))
    host._alarm_history.clear()
    host._alarm_history.append({
        'ts': '2026-10-28 02:30:00', 'reason': 'e', 'cleared': False,
        'cleared_at': '', 'severity': 'error', 'state_at': 'Alarm',
        'liaison': False, 'filmPath': str(fp),
    })
    saved = host.save_all_alarm_film_paths_csv_to_dir(str(d2))
    assert saved and Path(saved).is_file()
    assert Path(saved).parent.resolve() == d2.resolve()
    assert host.alarm_film_csv_dir() == str(d2) or host.alarm_film_csv_dirs()[0] == str(d2)
    # context menu has 最近另存目录
    host._alarm_ctx_menu_no_exec = True
    menu = host._build_alarm_list_context_menu()
    sub_texts = []
    for a in menu.actions():
        m = a.menu()
        if m is not None and '最近' in (a.text() or ''):
            sub_texts = [x.text() for x in m.actions()]
    assert sub_texts, 'missing 最近另存目录 submenu'
    ok('CSV 多档另存记忆')

    # cleanup capacity
    host.set_liaison_toast_history_max(5, persist=True)

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
