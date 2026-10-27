#!/usr/bin/env python3
"""细妆㉜：气泡长按钉住 · 进度弧可配时长 · CSV另存/cleared · toast史右键清空 · 锁双击可撤销."""
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
    from PySide6.QtWidgets import QApplication, QMessageBox, QFileDialog
    from PySide6.QtCore import QSettings, Qt, QPoint
    from PySide6.QtGui import QImage
    app = QApplication.instance() or QApplication([])
    QMessageBox.information = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)

    from desktop.widgets.filmstrip import CompareThumbStrip
    from desktop.host_state_machine import HostStateMachineWidget

    src_fs = Path('desktop/widgets/filmstrip.py').read_text(encoding='utf-8')
    src_h = Path('desktop/host_state_machine.py').read_text(encoding='utf-8')
    for name in ('set_undo_clear_long_ms', 'undo_clear_long_ms', '_on_undo_clear_ctx',
                 '_on_lock_badge_double', '_undo_should_relock'):
        assert name in src_fs, name
    for name in ('_on_sev_bubble_press', '_on_sev_bubble_release', '_on_sev_bubble_long_press',
                 'pin_alarm_severity_filter', 'save_all_alarm_film_paths_csv',
                 '_format_alarm_film_csv', 'clear_liaison_toast_history'):
        assert hasattr(HostStateMachineWidget, name), name
    assert 'film/undoClearLongMs' in src_fs
    assert 'host/alarmSevPinned' in src_h
    assert '另存 paths CSV' in src_h
    ok('wave32 APIs present')

    # --- Progress arc configurable duration ---
    strip = CompareThumbStrip()
    assert strip.undo_clear_long_ms() in (400, 650, 1000, 1500) or strip.undo_clear_long_ms() >= 300
    strip.set_undo_clear_long_ms(1000, persist=False)
    assert strip.undo_clear_long_ms() == 1000
    strip._on_undo_clear_ctx()  # cycle
    assert strip.undo_clear_long_ms() == 1500
    strip.set_undo_clear_long_ms(650, persist=False)
    tip = strip._undo_clear_btn.toolTip() or ''
    assert '650' in tip or '长按' in tip, tip
    ok('progress arc configurable duration tip')

    # --- Lock double-click undoable ---
    tmp = Path('/tmp/sieans-w32s'); tmp.mkdir(exist_ok=True)
    paths = []
    for i, name in enumerate(('a.bmp', 'b.bmp', 'c.bmp')):
        fp = tmp / name
        img = QImage(8, 8, QImage.Format.Format_RGB32)
        img.fill(0xFF405060 + i)
        img.save(str(fp))
        paths.append(str(fp))
    strip.set_paths(paths)
    strip._paths = [paths[2], paths[0], paths[1]]
    strip.set_order_locked(True, persist=False)
    assert strip.is_order_locked()
    depth0 = strip.order_undo_depth()
    strip._on_lock_badge_double()
    assert not strip.is_order_locked()
    assert list(strip._paths) == paths
    assert strip.order_undo_depth() == depth0 + 1
    assert getattr(strip, '_undo_should_relock', False) is True
    assert strip.undo_order()
    assert list(strip._paths) == [paths[2], paths[0], paths[1]]
    assert strip.is_order_locked(), 'undo should restore lock'
    ok('lock double-click undoable + relock')

    # --- Bubble long-press pin ---
    s = QSettings('SIEANS', 'VisionDesktop')
    s.setValue('host/alarmSevFilter', 'all')
    s.setValue('host/alarmSevPinned', '')
    s.sync()
    host = HostStateMachineWidget(compact=True)
    host.show()
    # short click via press+release
    host._on_sev_bubble_press(FakeEv(Qt.MouseButton.LeftButton), 'warning')
    host._on_sev_bubble_release(FakeEv(Qt.MouseButton.LeftButton), 'warning')
    assert str(host._alarm_sev_filter.currentData()) == 'warning'
    assert not host._alarm_sev_pinned
    # long press pin
    host._sev_bubble_pin_key = 'error'
    host._on_sev_bubble_long_press()
    assert host._alarm_sev_pinned and host._alarm_sev_pinned_key == 'error'
    assert str(host._alarm_sev_filter.currentData()) == 'error'
    # gated: cannot switch without force
    assert host.set_alarm_severity_filter('info') is False
    assert str(host._alarm_sev_filter.currentData()) == 'error'
    # short click other while pinned blocked
    host._sev_bubble_long_fired = False
    host._on_sev_bubble_press(FakeEv(Qt.MouseButton.LeftButton), 'info')
    host._on_sev_bubble_release(FakeEv(Qt.MouseButton.LeftButton), 'info')
    assert str(host._alarm_sev_filter.currentData()) == 'error'
    # middle unpins
    host._on_sev_bubble_press(FakeEv(Qt.MouseButton.MiddleButton), 'error')
    assert not host._alarm_sev_pinned
    assert host.set_alarm_severity_filter('info') is True
    ok('bubble long-press pin / gate / middle unpin')

    # --- CSV save with cleared cols ---
    host._alarm_history.clear()
    host._alarm_history.extend([
        {'ts': '2026-10-28 01:40:00', 'reason': 'e', 'cleared': True,
         'cleared_at': '2026-10-28 01:41:00', 'severity': 'error',
         'state_at': 'Alarm', 'liaison': False, 'filmPath': paths[0]},
        {'ts': '2026-10-28 01:42:00', 'reason': 'w', 'cleared': False,
         'cleared_at': '', 'severity': 'warning',
         'state_at': 'Alarm', 'liaison': False, 'filmPath': paths[1]},
    ])
    rows = host._collect_alarm_film_rows()
    assert len(rows) == 2
    assert rows[0].get('cleared') == '1' and rows[0].get('cleared_at')
    assert rows[1].get('cleared') == '0'
    csv = host._format_alarm_film_csv(rows)
    assert csv.startswith('ts,cleared,cleared_at,severity,path,reason')
    assert '2026-10-28 01:41:00' in csv
    out = tmp / 'paths-w32.csv'
    if out.exists():
        out.unlink()
    saved = host.save_all_alarm_film_paths_csv(str(out))
    assert saved == str(out)
    body = out.read_text(encoding='utf-8')
    assert 'cleared_at' in body and paths[0] in body
    QApplication.clipboard().setText('')
    assert host.copy_all_alarm_film_paths(as_csv=True)
    clip = QApplication.clipboard().text()
    assert clip.startswith('ts,cleared,cleared_at')
    menu = host._build_alarm_list_context_menu(QPoint(2, 2))
    texts = [a.text() for a in menu.actions()]
    assert any('另存' in (x or '') for x in texts), texts
    ok('CSV save file + cleared columns')

    # --- Toast history RMB clear ---
    host.set_liaison_window_sec(0)
    host._liaison_toast_history.clear()
    host._liaison_toast_history_secs.clear()
    host._on_liaison_hotkey()
    host._on_liaison_hotkey()
    assert len(host.liaison_toast_history()) >= 2
    host._liaison_toast_history_bar.show()
    host._on_liaison_toast_history_clicked(FakeEv(Qt.MouseButton.RightButton, x=10))
    assert host.liaison_toast_history() == []
    assert host._liaison_toast_history_bar.isHidden() or not (host._liaison_toast_history_bar.text() or '').strip()
    ok('toast history right-click clear')

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
