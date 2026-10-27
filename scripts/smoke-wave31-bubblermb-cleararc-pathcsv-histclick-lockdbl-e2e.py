#!/usr/bin/env python3
"""细妆㉛：气泡右/中键 · 长按进度弧 · paths CSV · toast史回切 · 锁徽章双击复位."""
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

class FakeEv:
    def __init__(self, button, x=10):
        self._b = button
        self._x = x
    def button(self):
        return self._b
    def x(self):
        return self._x
    def position(self):
        class P:
            def __init__(self, x): self._x = x
            def x(self): return self._x
        return P(self._x)

def main():
    from PySide6.QtWidgets import QApplication, QMessageBox
    from PySide6.QtCore import QSettings, Qt, QPoint
    from PySide6.QtGui import QImage
    app = QApplication.instance() or QApplication([])
    QMessageBox.information = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)

    from desktop.widgets.filmstrip import CompareThumbStrip, _UndoClearProgressArc
    from desktop.host_state_machine import HostStateMachineWidget

    src_fs = Path('desktop/widgets/filmstrip.py').read_text(encoding='utf-8')
    src_h = Path('desktop/host_state_machine.py').read_text(encoding='utf-8')
    for name in ('_on_lock_badge_double', '_on_undo_clear_tick', '_show_undo_clear_arc',
                 '_hide_undo_clear_arc'):
        assert hasattr(CompareThumbStrip, name), name
    for name in ('_collect_alarm_film_rows', '_on_liaison_toast_history_clicked'):
        assert hasattr(HostStateMachineWidget, name), name
    assert 'compareThumbUndoClearArc' in src_fs
    assert '复制全部 paths CSV' in src_h or 'as_csv' in src_h
    ok('wave31 APIs present')

    # --- Progress arc ---
    strip = CompareThumbStrip()
    assert isinstance(strip._undo_clear_arc, _UndoClearProgressArc)
    strip._push_order_undo(['/a', '/b'])
    strip._on_undo_clear_pressed()
    assert not strip._undo_clear_arc.isHidden()
    strip._on_undo_clear_tick()
    assert strip._undo_clear_arc._p > 0
    # release early = tip, no clear
    strip._on_undo_clear_released()
    assert strip.order_undo_depth() == 1
    assert strip._undo_clear_arc.isHidden()
    strip._on_undo_clear_long_press()
    assert strip.order_undo_depth() == 0
    ok('undo clear progress arc')

    # --- Lock badge double = reset + unlock ---
    tmp = Path('/tmp/sieans-w31s'); tmp.mkdir(exist_ok=True)
    paths = []
    for i, name in enumerate(('a.bmp', 'b.bmp', 'c.bmp')):
        fp = tmp / name
        img = QImage(8, 8, QImage.Format.Format_RGB32)
        img.fill(0xFF405060 + i)
        img.save(str(fp))
        paths.append(str(fp))
    strip.set_paths(paths)  # baseline
    strip._paths = [paths[2], paths[0], paths[1]]
    strip.set_order_locked(True, persist=False)
    assert strip.is_order_locked()
    strip._on_lock_badge_double()
    assert not strip.is_order_locked()
    assert list(strip._paths) == paths
    ok('lock badge double reset+unlock')

    # --- Bubble RMB / MMB ---
    s = QSettings('SIEANS', 'VisionDesktop')
    s.setValue('host/alarmSevFilter', 'all'); s.sync()
    host = HostStateMachineWidget(compact=True)
    host.show()
    host._on_sev_bubble_clicked(FakeEv(Qt.MouseButton.RightButton), 'warning')
    assert str(host._alarm_sev_filter.currentData()) == 'warning'
    host._on_sev_bubble_clicked(FakeEv(Qt.MouseButton.MiddleButton), 'error')
    assert str(host._alarm_sev_filter.currentData()) == 'all'
    host._on_sev_bubble_clicked(FakeEv(Qt.MouseButton.LeftButton), 'info')
    assert str(host._alarm_sev_filter.currentData()) == 'info'
    ok('bubble right=sev / middle=clear')

    # --- Copy all CSV with timestamps ---
    host._alarm_history.clear()
    host._alarm_history.extend([
        {'ts': '2026-10-28 01:10:00', 'reason': 'e', 'cleared': False, 'cleared_at': '',
         'severity': 'error', 'state_at': 'Alarm', 'liaison': False, 'filmPath': paths[0]},
        {'ts': '2026-10-28 01:11:00', 'reason': 'w', 'cleared': False, 'cleared_at': '',
         'severity': 'warning', 'state_at': 'Alarm', 'liaison': False, 'filmPath': paths[1]},
        {'ts': '2026-10-28 01:12:00', 'reason': 'e2', 'cleared': False, 'cleared_at': '',
         'severity': 'error', 'state_at': 'Alarm', 'liaison': False, 'filmPath': paths[0]},
    ])
    rows = host._collect_alarm_film_rows()
    assert len(rows) == 2
    QApplication.clipboard().setText('')
    assert host.copy_all_alarm_film_paths(as_csv=True)
    clip = QApplication.clipboard().text()
    assert clip.startswith('ts,severity,path,reason')
    assert paths[0] in clip and paths[1] in clip
    assert '2026-10-28 01:10:00' in clip
    menu = host._build_alarm_list_context_menu(QPoint(2, 2))
    texts = [a.text() for a in menu.actions()]
    assert any('CSV' in (x or '') for x in texts), texts
    ok('copy all paths CSV with timestamps')

    # --- Toast history click restore ---
    host.set_liaison_window_sec(0)
    host._liaison_toast_history.clear()
    host._liaison_toast_history_secs.clear()
    host._on_liaison_hotkey()  # 近5分 300
    host._on_liaison_hotkey()  # 近15分 900
    host._on_liaison_hotkey()  # 近1时 3600
    assert host.liaison_window_sec() == 3600
    hist = host.liaison_toast_history()
    assert hist == ['近5分', '近15分', '近1时'], hist
    host._liaison_toast_history_bar.setFixedWidth(300)
    # click left third → 近5分 / 300
    host._on_liaison_toast_history_clicked(FakeEv(Qt.MouseButton.LeftButton, x=30))
    assert host.liaison_window_sec() == 300, host.liaison_window_sec()
    # click middle → 近15分 / 900
    host._on_liaison_toast_history_clicked(FakeEv(Qt.MouseButton.LeftButton, x=150))
    assert host.liaison_window_sec() == 900, host.liaison_window_sec()
    ok('toast history click restore')

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
