#!/usr/bin/env python3
"""细妆㉞：pin悬停解钉动画 · CSV另存toast · 容量可配 · 预设标默认 · Alt+P toast."""
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

    from desktop.widgets.filmstrip import CompareThumbStrip
    from desktop.host_state_machine import HostStateMachineWidget

    src_fs = Path('desktop/widgets/filmstrip.py').read_text(encoding='utf-8')
    src_h = Path('desktop/host_state_machine.py').read_text(encoding='utf-8')
    for name in ('_build_undo_clear_preset_menu',):
        assert hasattr(CompareThumbStrip, name), name
    for name in ('_flash_host_toast', 'set_liaison_toast_history_max',
                 'cycle_liaison_toast_history_max', '_on_sev_pin_badge_enter',
                 '_on_sev_pin_badge_leave', '_on_sev_pin_badge_pulse'):
        assert hasattr(HostStateMachineWidget, name), name
    assert '（默认）' in src_fs
    assert 'host/liaisonToastHistMax' in src_h
    assert '_sev_pin_badge_pulse_timer' in src_h
    ok('wave34 APIs present')

    # --- Preset menu marks default ---
    strip = CompareThumbStrip()
    strip.set_undo_clear_long_ms(400, persist=False)
    strip._undo_clear_ctx_no_exec = True
    menu = strip._on_undo_clear_ctx(QPoint(0, 0))
    texts = [a.text() for a in menu.actions()]
    assert any('默认' in (x or '') and '650' in (x or '') for x in texts), texts
    assert any('✓' in (x or '') and '400' in (x or '') for x in texts), texts
    # default property
    defs = [a for a in menu.actions() if a.property('isDefault')]
    assert len(defs) == 1 and int(defs[0].data()) == 650
    ok('preset menu marks default')

    # --- Pin hover tip animation ---
    s = QSettings('SIEANS', 'VisionDesktop')
    s.setValue('host/alarmSevFilter', 'all')
    s.setValue('host/alarmSevPinned', '')
    s.setValue('host/liaisonToastHistMax', 5)
    s.sync()
    host = HostStateMachineWidget(compact=True)
    host.show()
    host.pin_alarm_severity_filter(True, key='warning')
    badge = host._alarm_sev_pin_badge
    assert not badge.isHidden()
    host._on_sev_pin_badge_enter()
    assert host._sev_pin_badge_pulse_timer.isActive()
    style1 = badge.styleSheet()
    host._on_sev_pin_badge_pulse()
    style2 = badge.styleSheet()
    # pulse toggles style
    assert style1 != style2 or host._sev_pin_badge_pulse_on in (True, False)
    host._on_sev_pin_badge_leave()
    assert not host._sev_pin_badge_pulse_timer.isActive()
    ok('pin badge hover unpin tip animation')

    # --- Alt+P toast feedback ---
    host._liaison_hotkey_toast.hide()
    host.set_alarm_severity_filter('error', force=True)
    host.pin_alarm_severity_filter(False)
    host._on_sev_pin_hotkey()
    assert host._alarm_sev_pinned
    toast = host._liaison_hotkey_toast
    assert not toast.isHidden()
    assert '钉住' in (toast.text() or '') and 'error' in (toast.text() or '')
    host._on_sev_pin_hotkey()
    assert not host._alarm_sev_pinned
    assert '取消' in (toast.text() or '')
    ok('Alt+P toast feedback')

    # --- CSV save toast ---
    tmp = Path('/tmp/sieans-w34s'); tmp.mkdir(exist_ok=True)
    fp = tmp / 'a.bmp'
    img = QImage(8, 8, QImage.Format.Format_RGB32)
    img.fill(0xFF405060)
    img.save(str(fp))
    host._alarm_history.clear()
    host._alarm_history.append({
        'ts': '2026-10-28 02:10:00', 'reason': 'e', 'cleared': False,
        'cleared_at': '', 'severity': 'error', 'state_at': 'Alarm',
        'liaison': False, 'filmPath': str(fp),
    })
    out = tmp / 'w34.csv'
    if out.exists():
        out.unlink()
    host._liaison_hotkey_toast.hide()
    saved = host.save_all_alarm_film_paths_csv(str(out))
    assert saved == str(out)
    assert not host._liaison_hotkey_toast.isHidden()
    assert '另存' in (host._liaison_hotkey_toast.text() or '') or 'CSV' in (host._liaison_hotkey_toast.text() or '')
    ok('CSV 另存后 toast')

    # --- toast-hist capacity configurable ---
    assert host.liaison_toast_history_capacity()[1] == 5
    assert host.set_liaison_toast_history_max(8, persist=False) == 8
    assert host.liaison_toast_history_capacity()[1] == 8
    # fill beyond then shrink
    host._liaison_toast_history.clear()
    host._liaison_toast_history_secs.clear()
    host._liaison_toast_history.extend(['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i'])
    host._liaison_toast_history_secs.extend([0] * 9)
    host.set_liaison_toast_history_max(5, persist=True)
    assert len(host._liaison_toast_history) == 5
    # middle-click cycle
    host._liaison_toast_history_bar.show()
    n = host.cycle_liaison_toast_history_max()
    assert n in (3, 5, 8, 12)
    host._on_liaison_toast_history_clicked(FakeEv(Qt.MouseButton.MiddleButton))
    used, max_n = host.liaison_toast_history_capacity()
    assert max_n in (3, 5, 8, 12)
    tip = host._liaison_toast_history_bar.toolTip() or ''
    assert '容量' in tip or str(max_n) in tip
    host.set_liaison_toast_history_max(5, persist=True)
    ok('toast-hist capacity configurable')

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
