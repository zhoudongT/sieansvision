#!/usr/bin/env python3
"""细妆㉗：对比锁序持久 · 运行报警带filmPath · 严重度筛持久 · 徽章切窗 · 复位撤销栈."""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
pass_n = fail_n = 0

def ok(m):
    global pass_n; pass_n += 1; print('PASS:', m)
def bad(m):
    global fail_n; fail_n += 1; print('FAIL:', m)

def main():
    from PySide6.QtWidgets import QApplication, QMessageBox
    from PySide6.QtCore import QSettings, Qt
    from PySide6.QtGui import QImage
    app = QApplication.instance() or QApplication([])
    QMessageBox.information = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
    QMessageBox.warning = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)

    from desktop.widgets.filmstrip import CompareThumbStrip
    from desktop.host_state_machine import HostStateMachineWidget
    from desktop.mainwindow import MainWindow

    # --- APIs ---
    for name in ('load_order_lock_pref', 'save_order_lock_pref', 'undo_order',
                 'order_undo_depth', '_push_order_undo'):
        assert hasattr(CompareThumbStrip, name), name
    for name in ('note_film_path', 'current_film_path', 'cycle_liaison_window',
                 '_on_liaison_badge_clicked', '_save_alarm_sev_filter_pref'):
        assert hasattr(HostStateMachineWidget, name), name
    src_mw = Path('desktop/mainwindow.py').read_text(encoding='utf-8')
    assert 'load_order_lock_pref' in src_mw
    assert 'host.note_film_path' in src_mw
    ok('wave27 APIs present')

    s = QSettings('SIEANS', 'VisionDesktop')

    # --- Compare lock QSettings persist ---
    s.setValue('film/compareOrderLocked', True)
    s.sync()
    strip = CompareThumbStrip()
    assert strip.load_order_lock_pref() is True
    assert strip.is_order_locked() is True
    strip.set_order_locked(False, persist=True)
    assert str(s.value('film/compareOrderLocked')).lower() in ('false', '0')
    # toggle path also persists
    strip._on_lock_toggled(True)
    assert str(s.value('film/compareOrderLocked')).lower() in ('true', '1')
    ok('compare order lock QSettings persist')

    # --- Undo stack on reset / reorder ---
    tmp = Path('/tmp/sieans-w27'); tmp.mkdir(exist_ok=True)
    paths = []
    for i, name in enumerate(('u.bmp', 'v.bmp', 'w.bmp')):
        fp = tmp / name
        img = QImage(12, 12, QImage.Format.Format_RGB32)
        img.fill(0xFF334400 + i * 0x11)
        img.save(str(fp))
        paths.append(str(fp))
    strip2 = CompareThumbStrip()
    strip2.set_paths(paths)
    assert strip2.order_undo_depth() == 0
    # simulate reorder
    strip2._suppress_reorder = True
    items = []
    while strip2._list.count():
        items.append(strip2._list.takeItem(0))
    for it in reversed(items):
        strip2._list.addItem(it)
    strip2._suppress_reorder = False
    strip2._emit_reorder_if_changed()
    assert strip2.paths() == list(reversed(paths))
    assert strip2.order_undo_depth() >= 1
    # reset → baseline, depth grows
    depth_before = strip2.order_undo_depth()
    assert strip2.reset_order() is True
    assert strip2.paths() == paths
    assert strip2.order_undo_depth() >= depth_before
    # undo → back to reversed
    assert strip2.undo_order() is True
    assert strip2.paths() == list(reversed(paths)), strip2.paths()
    ok('compare reset undo stack')

    # --- Runtime alarm carries filmPath ---
    s.setValue('host/alarmSevFilter', 'all')
    s.sync()
    host = HostStateMachineWidget(compact=True)
    host.note_film_path(str(paths[1]))
    assert host.current_film_path() == str(paths[1])
    host.set_state('Idle', 'reset')
    host.set_state('Alarm', '运行失败·e2e')
    assert host._alarm_history, 'no alarm recorded'
    last = host._alarm_history[-1]
    assert last.get('filmPath') == str(paths[1]), last
    # list UserRole also has it after refresh
    host._refresh_alarm_history_ui()
    # may be filtered — ensure all
    host.set_alarm_severity_filter('all')
    found = False
    for i in range(host._alarm_list.count()):
        data = host._alarm_list.item(i).data(Qt.ItemDataRole.UserRole) or {}
        if isinstance(data, dict) and data.get('filmPath') == str(paths[1]):
            found = True
            break
    assert found, 'filmPath not on list item'
    ok('runtime alarm auto filmPath')

    # --- Severity filter persist ---
    host.set_alarm_severity_filter('warning')
    assert str(s.value('host/alarmSevFilter') or '') == 'warning'
    host2 = HostStateMachineWidget(compact=True)
    assert host2.alarm_severity_filter() == 'warning'
    host2.set_alarm_severity_filter('all')
    assert str(s.value('host/alarmSevFilter') or '') == 'all'
    ok('severity filter QSettings persist')

    # --- Liaison badge click cycles window ---
    host.set_liaison_window_sec(0)
    assert host.liaison_window_sec() == 0
    sec1 = host.cycle_liaison_window()
    assert sec1 == 300, sec1
    sec2 = host.cycle_liaison_window()
    assert sec2 == 900, sec2
    # badge click handler
    host._on_liaison_badge_clicked()
    assert host.liaison_window_sec() == 3600
    badge = host._liaison_window_badge.text() or ''
    assert badge.strip(), badge
    ok('liaison badge cycles window')

    # --- MW wiring present ---
    assert hasattr(MainWindow, '_sync_host_sm_state')
    assert 'load_order_lock_pref' in src_mw
    ok('MW lock+film wiring present')

    print(f'\nRESULT pass={pass_n} fail={fail_n}')
    return 0 if fail_n == 0 else 1

if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:
        import traceback
        traceback.print_exc()
        bad(f'exception: {exc}')
        print(f'\nRESULT pass={pass_n} fail={fail_n}')
        raise SystemExit(1)
