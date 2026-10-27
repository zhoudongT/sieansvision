#!/usr/bin/env python3
"""细妆㉝：pin徽章 · CSV另存记目录 · toast容量tip · 时长预设菜单 · Alt+P钉住."""
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
    from PySide6.QtCore import QSettings, Qt, QPoint
    from PySide6.QtGui import QImage
    app = QApplication.instance() or QApplication([])
    QMessageBox.information = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)

    from desktop.widgets.filmstrip import CompareThumbStrip
    from desktop.host_state_machine import HostStateMachineWidget

    src_fs = Path('desktop/widgets/filmstrip.py').read_text(encoding='utf-8')
    src_h = Path('desktop/host_state_machine.py').read_text(encoding='utf-8')
    for name in ('_build_undo_clear_preset_menu', '_apply_undo_clear_preset'):
        assert hasattr(CompareThumbStrip, name), name
    for name in ('_on_sev_pin_hotkey', '_on_sev_pin_badge_clicked',
                 'alarm_film_csv_dir', 'set_alarm_film_csv_dir',
                 'liaison_toast_history_capacity'):
        assert hasattr(HostStateMachineWidget, name), name
    assert 'hostAlarmSevPinBadge' in src_h
    assert 'Alt+P' in src_h
    assert 'host/alarmFilmCsvDir' in src_h
    assert 'compareThumbUndoClearPresetMenu' in src_fs
    ok('wave33 APIs present')

    # --- Undo-clear preset menu (not cycle-only) ---
    strip = CompareThumbStrip()
    strip.set_undo_clear_long_ms(650, persist=False)
    strip._undo_clear_ctx_no_exec = True
    menu = strip._on_undo_clear_ctx(QPoint(0, 0))
    assert menu is not None
    texts = [a.text() for a in menu.actions()]
    assert any('400' in (x or '') for x in texts), texts
    assert any('✓' in (x or '') and '650' in (x or '') for x in texts), texts
    strip._apply_undo_clear_preset(1000)
    assert strip.undo_clear_long_ms() == 1000
    tip = strip._undo_clear_btn.toolTip() or ''
    assert '1000' in tip and ('右键' in tip or '时长' in tip), tip
    ok('undo-clear preset menu')

    # --- Pin badge on sev chip + Alt+P ---
    s = QSettings('SIEANS', 'VisionDesktop')
    s.setValue('host/alarmSevFilter', 'all')
    s.setValue('host/alarmSevPinned', '')
    s.setValue('host/liaisonToastHistMax', 5)
    s.sync()
    host = HostStateMachineWidget(compact=True)
    host.show()
    badge = host._alarm_sev_pin_badge
    assert badge is not None and badge.isHidden()
    host.set_alarm_severity_filter('warning', force=True)
    host._on_sev_pin_hotkey()  # pin warning
    assert host._alarm_sev_pinned and host._alarm_sev_pinned_key == 'warning'
    assert not badge.isHidden()
    assert '📌' in (badge.text() or '')
    chip = host._alarm_sev_chips['warning']
    assert '📌' in (chip.text() or ''), chip.text()
    # wave35: hotkey again 切档 (warning→info), still pinned
    host._on_sev_pin_hotkey()
    assert host._alarm_sev_pinned and host._alarm_sev_pinned_key == 'info'
    # badge click still clears
    host.pin_alarm_severity_filter(True, key='error')
    assert '📌' in (host._alarm_sev_chips['error'].text() or '')
    host._on_sev_pin_badge_clicked()
    assert not host._alarm_sev_pinned
    ok('pin badge on sev chip + Alt+P')

    # --- CSV remember dir ---
    tmp = Path('/tmp/sieans-w33s'); tmp.mkdir(exist_ok=True)
    sub = tmp / 'csvdir'; sub.mkdir(exist_ok=True)
    host.set_alarm_film_csv_dir(str(sub))
    assert host.alarm_film_csv_dir() == str(sub)
    # create film history and save with explicit path → updates dir
    paths = []
    for i, name in enumerate(('a.bmp', 'b.bmp')):
        fp = tmp / name
        img = QImage(8, 8, QImage.Format.Format_RGB32)
        img.fill(0xFF405060 + i)
        img.save(str(fp))
        paths.append(str(fp))
    host._alarm_history.clear()
    host._alarm_history.append({
        'ts': '2026-10-28 02:00:00', 'reason': 'e', 'cleared': False,
        'cleared_at': '', 'severity': 'error', 'state_at': 'Alarm',
        'liaison': False, 'filmPath': paths[0],
    })
    out = sub / 'saved-w33.csv'
    if out.exists():
        out.unlink()
    saved = host.save_all_alarm_film_paths_csv(str(out))
    assert saved == str(out)
    assert host.alarm_film_csv_dir() == str(sub.resolve()) or host.alarm_film_csv_dir() == str(sub)
    ok('CSV 另存 remember dir')

    # --- Toast hist capacity tip ---
    host.set_liaison_window_sec(0)
    host._liaison_toast_history.clear()
    host._liaison_toast_history_secs.clear()
    host._on_liaison_hotkey()
    host._on_liaison_hotkey()
    used, max_n = host.liaison_toast_history_capacity()
    assert used == 2 and max_n == 5, (used, max_n)
    tip = host._liaison_toast_history_bar.toolTip() or ''
    assert f'{used}/{max_n}' in tip or f'容量 {used}/{max_n}' in tip, tip
    assert '右键' in tip or '清空' in tip
    ok('toast-hist capacity tip')

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
