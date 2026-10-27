#!/usr/bin/env python3
"""细妆㉚：气泡单击筛 · 清空长按 · 复制全部paths · toast历史 · 锁徽章单击."""
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
    QMessageBox.warning = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)

    from desktop.widgets.filmstrip import CompareThumbStrip
    from desktop.host_state_machine import HostStateMachineWidget

    src_fs = Path('desktop/widgets/filmstrip.py').read_text(encoding='utf-8')
    src_h = Path('desktop/host_state_machine.py').read_text(encoding='utf-8')
    for name in ('_on_lock_badge_clicked', '_on_undo_clear_long_press',
                 '_on_undo_clear_pressed', '_on_undo_clear_released'):
        assert hasattr(CompareThumbStrip, name), name
    for name in ('_on_sev_bubble_clicked', '_collect_alarm_film_paths',
                 'copy_all_alarm_film_paths', 'liaison_toast_history'):
        assert hasattr(HostStateMachineWidget, name), name
    assert 'hostLiaisonToastHistory' in src_h
    assert '短按提示' in src_fs or '长按清空' in src_fs
    ok('wave30 APIs present')

    # --- Lock badge click toggle ---
    strip = CompareThumbStrip()
    assert not strip.is_order_locked()
    strip._on_lock_badge_clicked()
    assert strip.is_order_locked()
    assert strip._lock_badge.text() == '已锁'
    strip._on_lock_badge_clicked()
    assert not strip.is_order_locked()
    assert strip._lock_badge.text() == '未锁'
    ok('lock badge click toggle')

    # --- Undo clear: short tip / long press ---
    tmp = Path('/tmp/sieans-w30'); tmp.mkdir(exist_ok=True)
    paths = []
    for i, name in enumerate(('a.bmp', 'b.bmp')):
        fp = tmp / name
        img = QImage(8, 8, QImage.Format.Format_RGB32)
        img.fill(0xFF334455 + i)
        img.save(str(fp))
        paths.append(str(fp))
    strip.set_paths(paths)
    strip._push_order_undo(list(paths))
    strip._push_order_undo(list(reversed(paths)))
    strip._sync_undo_btn()
    assert strip.order_undo_depth() == 2
    # short press does not clear
    strip._undo_clear_long_fired = False
    strip._on_undo_clear_pressed()
    if strip._undo_clear_timer.isActive():
        strip._undo_clear_timer.stop()
    strip._on_undo_clear_released()
    assert strip.order_undo_depth() == 2
    tip = strip._undo_clear_btn.toolTip() or ''
    assert '长按' in tip or '清空' in tip
    # long press clears
    strip._on_undo_clear_long_press()
    assert strip.order_undo_depth() == 0
    assert not strip._undo_clear_btn.isEnabled()
    ok('undo clear short tip / long press')

    # --- Bubble click = sev filter ---
    s = QSettings('SIEANS', 'VisionDesktop')
    s.setValue('host/alarmSevFilter', 'all'); s.sync()
    host = HostStateMachineWidget(compact=True)
    host.show()
    host._alarm_history.clear()
    host._alarm_history.extend([
        {'ts': 't1', 'reason': 'e', 'cleared': False, 'cleared_at': '',
         'severity': 'error', 'state_at': 'Alarm', 'liaison': False, 'filmPath': paths[0]},
        {'ts': 't2', 'reason': 'w', 'cleared': False, 'cleared_at': '',
         'severity': 'warning', 'state_at': 'Alarm', 'liaison': False, 'filmPath': paths[1]},
        {'ts': 't3', 'reason': 'i', 'cleared': True, 'cleared_at': 'x',
         'severity': 'info', 'state_at': 'Idle', 'liaison': False},
    ])
    host._sync_alarm_sev_chips()
    host._on_sev_bubble_clicked(None, 'warning')
    assert str(host._alarm_sev_filter.currentData()) == 'warning'
    assert host._alarm_sev_chips['warning'].isChecked()
    host._on_sev_bubble_clicked(None, 'all')
    assert str(host._alarm_sev_filter.currentData()) == 'all'
    bub = host._alarm_sev_count_bubbles['error']
    assert bub.cursor().shape() == Qt.CursorShape.PointingHandCursor
    ok('severity bubble click filter')

    # --- Copy all paths ---
    QApplication.clipboard().setText('')
    assert host.copy_all_alarm_film_paths() is True
    clip = QApplication.clipboard().text()
    assert paths[0] in clip and paths[1] in clip
    assert host._collect_alarm_film_paths() == [paths[0], paths[1]]
    menu = host._build_alarm_list_context_menu(QPoint(2, 2))
    texts = [a.text() for a in menu.actions()]
    assert any('复制全部 paths' in (x or '') for x in texts), texts
    ok('alarm context copy all paths')

    # --- Alt+L toast history ---
    host.set_liaison_window_sec(0)
    host._liaison_toast_history.clear()
    host._on_liaison_hotkey()  # → 近5分
    host._on_liaison_hotkey()  # → 近15分
    host._on_liaison_hotkey()  # → 近1时
    hist = host.liaison_toast_history()
    assert len(hist) == 3, hist
    assert hist[0] == '近5分' and hist[-1] == '近1时'
    hbar = host._liaison_toast_history_bar
    assert not hbar.isHidden()
    assert '切窗史' in (hbar.text() or '')
    assert '→' in (hbar.text() or '')
    assert host._liaison_hotkey_toast.isVisible()
    ok('Alt+L toast history strip')

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
