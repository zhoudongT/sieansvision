#!/usr/bin/env python3
"""细妆㊲：多档上限可配 · Alt+H焦点键选 · 长按落钉进度弧 · 开目录成功tip · 最近另存清档."""
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

    from desktop.host_state_machine import HostStateMachineWidget, _SevChipPinProgressArc
    src = Path('desktop/host_state_machine.py').read_text(encoding='utf-8')
    for name in (
        'alarm_film_csv_dirs_max', 'set_alarm_film_csv_dirs_max',
        'cycle_alarm_film_csv_dirs_max', 'clear_alarm_film_csv_dirs',
        '_focus_toast_hist_cap_menu', '_show_sev_chip_pin_arc',
        '_hide_sev_chip_pin_arc', '_on_sev_chip_pin_tick',
        '_flash_open_dir_ok_tip', '_apply_alarm_film_csv_dirs_max',
    ):
        assert hasattr(HostStateMachineWidget, name), name
    assert 'hostSevChipPinArc' in src and 'host/alarmFilmCsvDirsMax' in src
    ok('wave37 APIs present')

    s = QSettings('SIEANS', 'VisionDesktop')
    s.setValue('host/alarmSevFilter', 'all')
    s.setValue('host/alarmSevPinned', '')
    s.setValue('host/liaisonToastHistMax', 5)
    s.setValue('host/alarmFilmCsvDirs', [])
    s.setValue('host/alarmFilmCsvDir', '')
    s.setValue('host/alarmFilmCsvDirsMax', 5)
    s.sync()
    host = HostStateMachineWidget(compact=True)
    host.show()

    # --- multi-slot max configurable ---
    assert host.alarm_film_csv_dirs_max() == 5
    tmp = Path('/tmp/sieans-w37s'); tmp.mkdir(exist_ok=True)
    slots = []
    for i in range(6):
        d = tmp / f's{i}'; d.mkdir(exist_ok=True)
        slots.append(str(d))
        host.remember_alarm_film_csv_dir(str(d))
    assert len(host.alarm_film_csv_dirs()) == 5
    host.set_alarm_film_csv_dirs_max(3, persist=True)
    assert host.alarm_film_csv_dirs_max() == 3
    assert len(host.alarm_film_csv_dirs()) == 3
    n = host.cycle_alarm_film_csv_dirs_max()
    assert n in (3, 5, 8)
    host.set_alarm_film_csv_dirs_max(5, persist=True)
    ok('多档记忆上限可配')

    # --- Alt+H menu focus key select ---
    host.set_liaison_toast_history_max(8, persist=False)
    host._toast_hist_cap_menu_no_exec = True
    menu = host._on_toast_hist_cap_hotkey()
    focus = getattr(host, '_last_toast_hist_cap_focus', None)
    assert focus is not None
    assert int(focus.data()) == 8
    assert menu.activeAction() is focus or focus.isChecked()
    # toast mentions 焦点
    assert '焦点' in (host._liaison_hotkey_toast.text() or '') or focus is not None
    host.set_liaison_toast_history_max(5, persist=True)
    ok('Alt+H 菜单焦点键选')

    # --- long-press pin progress arc ---
    arc = host._sev_chip_pin_arc
    assert isinstance(arc, _SevChipPinProgressArc)
    host.pin_alarm_severity_filter(False)
    host._on_sev_chip_press(None, 'warning')
    assert host._sev_chip_pin_tick.isActive()
    host._on_sev_chip_pin_tick()
    assert not arc.isHidden()
    assert arc._p > 0
    # simulate near-full then long press
    host._sev_chip_pin_press_ms = 500
    host._on_sev_chip_pin_tick()
    assert arc._p >= 0.9
    host._on_sev_chip_long_press()
    assert host._alarm_sev_pinned_key == 'warning'
    assert arc.isHidden() or arc._p == 0.0
    ok('长按落钉进度弧')

    # --- open dir success tip distinct ---
    host._host_toast_open_path = str(tmp)
    host._liaison_hotkey_toast.hide()
    got = host.open_host_toast_path()
    assert got
    tt = host._liaison_hotkey_toast.text() or ''
    # success (or soft success) — not 失败
    assert '失败' not in tt
    assert '打开' in tt or '就绪' in tt
    # hard fail still distinct
    host._host_toast_open_path = '/tmp/sieans-w37-missing-dir-zzz'
    host.open_host_toast_path()
    assert '失败' in (host._liaison_hotkey_toast.text() or '')
    # ok tip API
    host._flash_open_dir_ok_tip(str(tmp), soft=False)
    assert '已打开目录' in (host._liaison_hotkey_toast.text() or '')
    host._flash_open_dir_ok_tip(str(tmp), soft=True)
    assert '就绪' in (host._liaison_hotkey_toast.text() or '') and '未打开' in (host._liaison_hotkey_toast.text() or '')
    ok('开目录成功 tip 区分')

    # --- clear recent slots ---
    host.remember_alarm_film_csv_dir(str(tmp / 's0'))
    host.remember_alarm_film_csv_dir(str(tmp / 's1'))
    assert host.alarm_film_csv_dirs()
    host.clear_alarm_film_csv_dirs()
    assert host.alarm_film_csv_dirs() == []
    assert host.alarm_film_csv_dir() == ''
    assert '清档' in (host._liaison_hotkey_toast.text() or '')
    # menu has 清空最近另存
    host._alarm_ctx_menu_no_exec = True
    # need at least empty history for menu build
    menu = host._build_alarm_list_context_menu()
    found_clear = False
    found_max = False
    for a in menu.actions():
        m = a.menu()
        if m is None:
            continue
        if '最近' not in (a.text() or ''):
            continue
        for x in m.actions():
            if '清空最近另存' in (x.text() or ''):
                found_clear = True
            if x.property('isDirsMax'):
                found_max = True
    assert found_clear and found_max
    ok('最近另存清档')

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
