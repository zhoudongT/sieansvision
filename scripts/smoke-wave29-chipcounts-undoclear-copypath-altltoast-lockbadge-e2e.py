#!/usr/bin/env python3
"""细妆㉙：芯片计数气泡 · 撤销清空 · 右键复制path · Alt+L全局提示 · 锁序徽章."""
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

    # --- APIs ---
    for name in ('clear_order_undo',):
        assert hasattr(CompareThumbStrip, name), name
    src_fs = Path('desktop/widgets/filmstrip.py').read_text(encoding='utf-8')
    assert 'compareThumbLockBadge' in src_fs
    assert 'compareThumbUndoClear' in src_fs
    for name in ('_alarm_severity_counts', 'copy_alarm_film_path',
                 '_flash_liaison_hotkey_toast', '_on_liaison_hotkey'):
        assert hasattr(HostStateMachineWidget, name), name
    src_h = Path('desktop/host_state_machine.py').read_text(encoding='utf-8')
    assert 'hostAlarmSevCount_' in src_h
    assert 'hostLiaisonHotkeyToast' in src_h
    ok('wave29 APIs present')

    # --- Lock badge ---
    strip = CompareThumbStrip()
    assert strip._lock_badge.text() == '未锁'
    strip.set_order_locked(True)
    assert strip._lock_badge.text() == '已锁'
    assert 'e0b84a' in (strip._lock_badge.styleSheet() or '')
    strip.set_order_locked(False)
    assert strip._lock_badge.text() == '未锁'
    ok('compare lock badge')

    # --- Undo clear button ---
    tmp = Path('/tmp/sieans-w29'); tmp.mkdir(exist_ok=True)
    paths = []
    for i, name in enumerate(('a.bmp', 'b.bmp')):
        fp = tmp / name
        img = QImage(8, 8, QImage.Format.Format_RGB32)
        img.fill(0xFF556600 + i)
        img.save(str(fp))
        paths.append(str(fp))
    strip.set_paths(paths)
    strip._push_order_undo(list(paths))
    strip._push_order_undo(list(reversed(paths)))
    strip._sync_undo_btn()
    assert strip.order_undo_depth() == 2
    assert strip._undo_clear_btn.isEnabled()
    assert strip.clear_order_undo() is True
    assert strip.order_undo_depth() == 0
    assert strip._undo_depth_badge.text() == '0'
    assert not strip._undo_clear_btn.isEnabled()
    assert strip.clear_order_undo() is False
    ok('undo stack clear button')

    # --- Chip count bubbles ---
    s = QSettings('SIEANS', 'VisionDesktop')
    s.setValue('host/alarmSevFilter', 'all')
    s.sync()
    host = HostStateMachineWidget(compact=True)
    host._alarm_history.clear()
    host._alarm_history.extend([
        {'ts': 't1', 'reason': 'e1', 'cleared': False, 'cleared_at': '',
         'severity': 'error', 'state_at': 'Alarm', 'liaison': False},
        {'ts': 't2', 'reason': 'e2', 'cleared': False, 'cleared_at': '',
         'severity': 'error', 'state_at': 'Alarm', 'liaison': False},
        {'ts': 't3', 'reason': 'w1', 'cleared': False, 'cleared_at': '',
         'severity': 'warning', 'state_at': 'Alarm', 'liaison': False},
        {'ts': 't4', 'reason': 'i1', 'cleared': True, 'cleared_at': 'x',
         'severity': 'info', 'state_at': 'Idle', 'liaison': False},
    ])
    host._sync_alarm_sev_chips()
    bubbles = host._alarm_sev_count_bubbles
    assert bubbles['all'].text() == '4'
    assert bubbles['error'].text() == '2'
    assert bubbles['warning'].text() == '1'
    assert bubbles['info'].text() == '1'
    assert 'e35d6a' in (bubbles['error'].styleSheet() or '')
    ok('severity chip count bubbles')

    # --- Copy path via context menu action ---
    host._alarm_history.clear()
    host.note_film_path(str(paths[0]))
    host.set_state('Idle', 'reset')
    host.set_state('Alarm', 'copy-path-case')
    host.set_alarm_severity_filter('all')
    host._refresh_alarm_history_ui()
    assert host._alarm_list.count() >= 1
    # find item with filmPath
    item = None
    for i in range(host._alarm_list.count()):
        it = host._alarm_list.item(i)
        data = it.data(Qt.ItemDataRole.UserRole) or {}
        if isinstance(data, dict) and data.get('filmPath'):
            item = it
            break
    assert item is not None
    host._alarm_list.setCurrentItem(item)
    QApplication.clipboard().setText('')
    assert host.copy_alarm_film_path(item) is True
    assert QApplication.clipboard().text() == str(paths[0])
    menu = host._build_alarm_list_context_menu(QPoint(2, 2))
    texts = [a.text() for a in menu.actions()]
    assert any('复制 path' in (x or '') for x in texts), texts
    ok('alarm context copy path')

    # --- Alt+L global toast ---
    host.show()  # ancestors visible so toast.isVisible works
    host.set_liaison_window_sec(0)
    host._on_liaison_hotkey()
    assert host.liaison_window_sec() == 300
    toast = host._liaison_hotkey_toast
    assert not toast.isHidden(), 'toast should be shown after Alt+L'
    assert toast.isVisible() or toast.isVisibleTo(host)
    assert 'Alt+L' in (toast.text() or '')
    assert '近5分' in (toast.text() or '') or '5' in (toast.text() or '')
    tip = host.statusTip() or ''
    assert 'Alt+L' in tip or 'Alt+L' in (host.toolTip() or '')
    ok('Alt+L global status toast')

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
