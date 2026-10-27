#!/usr/bin/env python3
"""细妆㉟：CSV toast单击开目录 · 容量右键菜单 · 解钉tip驻留 · chip悬停预览钉 · Alt+P切档."""
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
    def pos(self):
        from PySide6.QtCore import QPoint
        return QPoint(self._x, 4)
    def position(self):
        class P:
            def __init__(self, x): self._x = x
            def x(self): return self._x
            def toPoint(self):
                from PySide6.QtCore import QPoint
                return QPoint(self._x, 4)
        return P(self._x)

def main():
    from PySide6.QtWidgets import QApplication, QMessageBox
    from PySide6.QtCore import QSettings, Qt, QPoint
    from PySide6.QtGui import QImage
    app = QApplication.instance() or QApplication([])
    QMessageBox.information = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)

    from desktop.host_state_machine import HostStateMachineWidget

    src = Path('desktop/host_state_machine.py').read_text(encoding='utf-8')
    for name in (
        '_on_host_toast_clicked', 'open_host_toast_path',
        '_build_liaison_toast_capacity_menu', '_apply_toast_hist_capacity',
        '_show_sev_pin_confirm_tip', '_hide_sev_pin_confirm_tip',
        '_on_sev_chip_enter', '_on_sev_chip_leave',
    ):
        assert hasattr(HostStateMachineWidget, name), name
    assert 'open_path' in src and 'QDesktopServices' in src
    assert '切档' in src and '悬停预览钉' in src
    ok('wave35 APIs present')

    s = QSettings('SIEANS', 'VisionDesktop')
    s.setValue('host/alarmSevFilter', 'all')
    s.setValue('host/alarmSevPinned', '')
    s.setValue('host/liaisonToastHistMax', 5)
    s.sync()
    host = HostStateMachineWidget(compact=True)
    host.show()

    # --- CSV toast click open dir ---
    tmp = Path('/tmp/sieans-w35s'); tmp.mkdir(exist_ok=True)
    fp = tmp / 'a.bmp'
    img = QImage(8, 8, QImage.Format.Format_RGB32)
    img.fill(0xFF405060)
    img.save(str(fp))
    host._alarm_history.clear()
    host._alarm_history.append({
        'ts': '2026-10-28 02:20:00', 'reason': 'e', 'cleared': False,
        'cleared_at': '', 'severity': 'error', 'state_at': 'Alarm',
        'liaison': False, 'filmPath': str(fp),
    })
    out = tmp / 'w35.csv'
    if out.exists():
        out.unlink()
    saved = host.save_all_alarm_film_paths_csv(str(out))
    assert saved == str(out)
    assert host._host_toast_open_path
    tip = host._liaison_hotkey_toast.toolTip() or ''
    assert '单击' in tip or '目录' in tip
    # open without relying on desktop env: call helper
    opened = host.open_host_toast_path()
    assert opened and Path(opened).is_dir()
    assert Path(opened).resolve() == tmp.resolve()
    ok('CSV toast 单击开目录')

    # --- capacity right-click menu ---
    host._toast_hist_cap_menu_no_exec = True
    host._liaison_toast_history_bar.show()
    menu = host._on_liaison_toast_history_clicked(FakeEv(Qt.MouseButton.RightButton))
    assert menu is not None
    texts = [a.text() for a in menu.actions() if a.text()]
    assert any('容量 3' in (x or '') for x in texts), texts
    assert any('容量 5' in (x or '') and '默认' in (x or '') for x in texts), texts
    assert any('清空' in (x or '') for x in texts), texts
    defs = [a for a in menu.actions() if a.property('isDefault')]
    assert len(defs) == 1 and int(defs[0].data()) == 5
    host._apply_toast_hist_capacity(8)
    assert host.liaison_toast_history_capacity()[1] == 8
    host.set_liaison_toast_history_max(5, persist=True)
    tip = host._liaison_toast_history_bar.toolTip() or ''
    assert '右键' in tip and '容量' in tip
    ok('容量右键菜单')

    # --- pin badge confirm tip dwell ---
    host.pin_alarm_severity_filter(True, key='warning')
    assert host._alarm_sev_pinned
    host._on_sev_pin_badge_clicked()
    assert not host._alarm_sev_pinned
    assert host._sev_pin_confirm_tip_timer.isActive()
    # badge shows confirm glyph during dwell
    badge = host._alarm_sev_pin_badge
    assert not badge.isHidden()
    assert '✓' in (badge.text() or '') or '解钉' in (badge.toolTip() or '')
    host._hide_sev_pin_confirm_tip()
    assert badge.isHidden() or not (badge.text() or '').strip() or badge.text() == ''
    ok('pin 徽章解钉确认 tip 驻留')

    # --- sev chip hover preview pin ---
    chip = host._alarm_sev_chips['error']
    before = chip.styleSheet()
    host._on_sev_chip_enter(None, 'error')
    assert host._sev_chip_hover_key == 'error'
    assert '📍' in (chip.text() or '') or 'dashed' in (chip.styleSheet() or '')
    assert '预览' in (chip.toolTip() or '')
    host._on_sev_chip_leave(None, 'error')
    assert '📌' not in (chip.text() or '') or not host._alarm_sev_pinned
    # restored (no real pin)
    assert '📍' not in (chip.text() or '')
    ok('sev chip 悬停预览钉')

    # --- Alt+P 再按切档 toast ---
    host.pin_alarm_severity_filter(False)
    host.set_alarm_severity_filter('error', force=True)
    host._liaison_hotkey_toast.hide()
    host._on_sev_pin_hotkey()
    assert host._alarm_sev_pinned_key == 'error'
    assert '钉住' in (host._liaison_hotkey_toast.text() or '')
    host._on_sev_pin_hotkey()
    assert host._alarm_sev_pinned and host._alarm_sev_pinned_key == 'warning'
    assert '切档' in (host._liaison_hotkey_toast.text() or '')
    host._on_sev_pin_hotkey()
    assert host._alarm_sev_pinned_key == 'info'
    # badge still unpins
    host._on_sev_pin_badge_clicked()
    assert not host._alarm_sev_pinned
    ok('Alt+P 再按切档 toast')

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
