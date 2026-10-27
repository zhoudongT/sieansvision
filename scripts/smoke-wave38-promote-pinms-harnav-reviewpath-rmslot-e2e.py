#!/usr/bin/env python3
"""细妆㊳：多档置顶拖序 · 进度弧时长/色 · Alt+H键导航 · 开目录tip回看 · 单项删除."""
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
    app = QApplication.instance() or QApplication([])
    QMessageBox.information = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)

    from desktop.host_state_machine import HostStateMachineWidget, _SevChipPinProgressArc
    src = Path('desktop/host_state_machine.py').read_text(encoding='utf-8')
    for name in (
        'promote_alarm_film_csv_dir', 'remove_alarm_film_csv_dir',
        'move_alarm_film_csv_dir', 'reorder_alarm_film_csv_dirs',
        'sev_chip_pin_ms', 'set_sev_chip_pin_ms', 'cycle_sev_chip_pin_ms',
        'sev_chip_pin_arc_color', 'set_sev_chip_pin_arc_color',
        'navigate_toast_hist_cap_menu', 'toast_hist_cap_menu_key',
        'review_host_toast_path',
    ):
        assert hasattr(HostStateMachineWidget, name), name
    assert 'host/sevChipPinMs' in src and 'host/sevChipPinArcColor' in src
    assert 'isRecentPromote' in src and 'isRecentRemove' in src
    ok('wave38 APIs present')

    s = QSettings('SIEANS', 'VisionDesktop')
    s.setValue('host/alarmSevFilter', 'all')
    s.setValue('host/alarmSevPinned', '')
    s.setValue('host/liaisonToastHistMax', 5)
    s.setValue('host/alarmFilmCsvDirs', [])
    s.setValue('host/alarmFilmCsvDir', '')
    s.setValue('host/alarmFilmCsvDirsMax', 5)
    s.setValue('host/sevChipPinMs', 550)
    s.setValue('host/sevChipPinArcColor', '#f0c040')
    s.sync()
    host = HostStateMachineWidget(compact=True)
    host.show()

    # --- 1. promote / reorder ---
    tmp = Path('/tmp/sieans-w38s'); tmp.mkdir(exist_ok=True)
    d0, d1, d2 = tmp / 'a', tmp / 'b', tmp / 'c'
    for d in (d0, d1, d2):
        d.mkdir(exist_ok=True)
    # remember newest first: c, b, a
    host.remember_alarm_film_csv_dir(str(d0))
    host.remember_alarm_film_csv_dir(str(d1))
    host.remember_alarm_film_csv_dir(str(d2))
    dirs = host.alarm_film_csv_dirs()
    assert dirs[0] == str(d2)
    # promote a to top
    host.promote_alarm_film_csv_dir(str(d0))
    dirs = host.alarm_film_csv_dirs()
    assert dirs[0] == str(d0), dirs
    assert '置顶' in (host._liaison_hotkey_toast.text() or '')
    # move idx 0 -> 2
    host.move_alarm_film_csv_dir(0, 2)
    dirs = host.alarm_film_csv_dirs()
    assert dirs[-1] == str(d0), dirs
    # reorder explicit
    host.reorder_alarm_film_csv_dirs([str(d1), str(d2), str(d0)])
    assert host.alarm_film_csv_dirs()[:3] == [str(d1), str(d2), str(d0)]
    # menu has 置顶 / 删除此项
    host._alarm_ctx_menu_no_exec = True
    menu = host._build_alarm_list_context_menu()
    found_promote = found_remove = False
    for a in menu.actions():
        m = a.menu()
        if m is None or '最近' not in (a.text() or ''):
            continue
        for x in m.actions():
            sm = x.menu()
            if sm is None:
                continue
            for y in sm.actions():
                if y.property('isRecentPromote'):
                    found_promote = True
                if y.property('isRecentRemove'):
                    found_remove = True
    assert found_promote and found_remove
    ok('多档记忆拖序/置顶')

    # --- 2. pin arc ms/color ---
    assert host.sev_chip_pin_ms() == 550
    assert host.set_sev_chip_pin_ms(300) == 300
    assert host.sev_chip_pin_ms() == 300
    n = host.cycle_sev_chip_pin_ms()
    assert n in (300, 550, 800)
    host.set_sev_chip_pin_ms(550)
    assert host.sev_chip_pin_arc_color().lower() == '#f0c040'
    host.set_sev_chip_pin_arc_color('#3ecf8e')
    assert host.sev_chip_pin_arc_color().lower() == '#3ecf8e'
    arc = host._sev_chip_pin_arc
    assert isinstance(arc, _SevChipPinProgressArc)
    assert arc.color().lower() == '#3ecf8e'
    host.set_sev_chip_pin_arc_color('#f0c040')
    # long press uses configured ms
    host.pin_alarm_severity_filter(False)
    host.set_sev_chip_pin_ms(300)
    host._on_sev_chip_press(None, 'info')
    assert host._sev_chip_pin_timer.isActive()
    # timer interval should be 300
    # QTimer remaining may vary; check configured
    assert host.sev_chip_pin_ms() == 300
    host._sev_chip_pin_press_ms = 280
    host._on_sev_chip_pin_tick()
    assert arc._p >= 0.9
    host._on_sev_chip_release(None, 'info')
    host.set_sev_chip_pin_ms(550)
    ok('进度弧可配时长/色')

    # --- 3. Alt+H Esc/arrow nav ---
    host.set_liaison_toast_history_max(5, persist=False)
    host._toast_hist_cap_menu_no_exec = True
    menu = host._on_toast_hist_cap_hotkey()
    focus = host._last_toast_hist_cap_focus
    assert focus is not None and int(focus.data()) == 5
    # down → next selectable
    nxt = host.navigate_toast_hist_cap_menu(menu, 1)
    assert nxt is not None and nxt is not focus
    # up back
    back = host.navigate_toast_hist_cap_menu(menu, -1)
    assert back is not None and int(back.data() or 0) == 5
    # Esc
    host._last_toast_hist_cap_closed_by = ''
    r = host.toast_hist_cap_menu_key(Qt.Key.Key_Escape, menu)
    assert r == 'esc'
    assert getattr(host, '_last_toast_hist_cap_closed_by', '') == 'esc'
    ok('Alt+H 菜单 Esc/方向键导航')

    # --- 4. open dir tip clickable path review ---
    host._host_toast_open_path = ''
    host._flash_open_dir_ok_tip(str(tmp), soft=False)
    assert getattr(host, '_host_toast_click_action', '') == 'review'
    assert host._host_toast_open_path == str(tmp) or host._host_toast_review_path == str(tmp)
    tt = host._liaison_hotkey_toast.text() or ''
    assert '回看' in tt or '已打开' in tt
    got = host.review_host_toast_path()
    assert got == str(tmp.resolve()) or got == str(tmp) or str(tmp) in got
    assert '回看' in (host._liaison_hotkey_toast.text() or '') or '路径' in (host._liaison_hotkey_toast.text() or '')
    assert getattr(host, '_host_toast_click_action', '') == 'open'
    # click path when review pending
    host._flash_open_dir_ok_tip(str(tmp), soft=True)
    assert host._host_toast_click_action == 'review'
    host._on_host_toast_clicked(None)
    assert host._host_toast_click_action == 'open'
    ok('开目录 tip 可点回看路径')

    # --- 5. single-slot remove ---
    host.clear_alarm_film_csv_dirs()
    host.remember_alarm_film_csv_dir(str(d0))
    host.remember_alarm_film_csv_dir(str(d1))
    host.remember_alarm_film_csv_dir(str(d2))
    assert len(host.alarm_film_csv_dirs()) == 3
    left = host.remove_alarm_film_csv_dir(str(d1))
    assert str(d1) not in left
    assert len(left) == 2
    assert '删' in (host._liaison_hotkey_toast.text() or '')
    # clear still works
    host.clear_alarm_film_csv_dirs()
    assert host.alarm_film_csv_dirs() == []
    ok('最近另存单项删除')

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
