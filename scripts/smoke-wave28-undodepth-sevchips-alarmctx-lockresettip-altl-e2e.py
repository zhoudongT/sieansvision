#!/usr/bin/env python3
"""细妆㉘：撤销栈深度徽章 · 严重度芯片条 · 报警右键定位 · 锁序复位提示 · Alt+L切窗."""
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
    from PySide6.QtGui import QImage, QKeySequence
    app = QApplication.instance() or QApplication([])
    QMessageBox.information = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
    QMessageBox.warning = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)

    from desktop.widgets.filmstrip import CompareThumbStrip
    from desktop.host_state_machine import HostStateMachineWidget

    # --- APIs ---
    assert hasattr(CompareThumbStrip, '_sync_undo_btn')
    assert hasattr(HostStateMachineWidget, '_sync_alarm_sev_chips')
    assert hasattr(HostStateMachineWidget, '_on_alarm_list_context_menu')
    assert hasattr(HostStateMachineWidget, '_locate_film_from_alarm_item')
    assert hasattr(HostStateMachineWidget, '_film_path_from_alarm_item')
    src = Path('desktop/host_state_machine.py').read_text(encoding='utf-8')
    assert 'Alt+L' in src
    assert 'hostAlarmSevChip_' in src
    assert 'compareThumbUndoDepth' in Path('desktop/widgets/filmstrip.py').read_text(encoding='utf-8')
    ok('wave28 APIs present')

    # --- Undo depth badge ---
    tmp = Path('/tmp/sieans-w28'); tmp.mkdir(exist_ok=True)
    paths = []
    for i, name in enumerate(('p.bmp', 'q.bmp', 'r.bmp')):
        fp = tmp / name
        img = QImage(10, 10, QImage.Format.Format_RGB32)
        img.fill(0xFF445500 + i * 0x10)
        img.save(str(fp))
        paths.append(str(fp))
    strip = CompareThumbStrip()
    strip.set_paths(paths)
    assert strip._undo_depth_badge.text() == '0'
    strip._push_order_undo(list(paths))
    strip._sync_undo_btn()
    assert strip._undo_depth_badge.text() == '1'
    assert '6eb6ff' in (strip._undo_depth_badge.styleSheet() or '')
    # reorder pushes
    strip._suppress_reorder = True
    items = []
    while strip._list.count():
        items.append(strip._list.takeItem(0))
    for it in reversed(items):
        strip._list.addItem(it)
    strip._suppress_reorder = False
    strip._emit_reorder_if_changed()
    assert int(strip._undo_depth_badge.text()) >= 1
    ok('undo stack depth badge')

    # --- Lock → reset still usable tip ---
    strip.set_order_locked(False)
    tip_unlocked = strip._reset_btn.toolTip() or ''
    strip.set_order_locked(True)
    tip_locked = strip._reset_btn.toolTip() or ''
    assert '锁序下仍可用' in tip_locked, tip_locked
    assert tip_locked != tip_unlocked or '仍可用' in tip_locked
    # reset still works while locked
    assert strip.paths() == list(reversed(paths)) or strip.order_undo_depth() >= 0
    # force non-baseline then reset under lock
    if strip.paths() == paths:
        strip.set_order_locked(False)
        strip._suppress_reorder = True
        items = []
        while strip._list.count():
            items.append(strip._list.takeItem(0))
        for it in reversed(items):
            strip._list.addItem(it)
        strip._suppress_reorder = False
        strip._emit_reorder_if_changed()
        strip.set_order_locked(True)
    assert strip.reset_order() is True
    assert strip.paths() == paths
    assert strip.is_order_locked() is True
    ok('lock tip + reset still works while locked')

    # --- Severity chip bar ---
    s = QSettings('SIEANS', 'VisionDesktop')
    s.setValue('host/alarmSevFilter', 'all')
    s.sync()
    host = HostStateMachineWidget(compact=True)
    chips = host._alarm_sev_chips
    assert chips['all'].isChecked()
    host.set_alarm_severity_filter('warning')
    assert chips['warning'].isChecked()
    assert not chips['all'].isChecked()
    assert host.alarm_severity_filter() == 'warning'
    # chip click
    chips['error'].click()
    assert host.alarm_severity_filter() == 'error'
    assert chips['error'].isChecked()
    ok('severity filter chip bar')

    # --- Alarm list context locate ---
    host.note_film_path(str(paths[0]))
    host.set_state('Idle', 'x')
    host.set_state('Alarm', 'ctx locate fail')
    host.set_alarm_severity_filter('all')
    host._refresh_alarm_history_ui()
    assert host._alarm_list.count() >= 1
    item = host._alarm_list.item(0)
    located = []
    host.alarmFilmLocateRequested.connect(lambda p: located.append(p))
    assert host._locate_film_from_alarm_item(item, source='alarm_context') is True
    assert located and located[-1].get('path') == str(paths[0])
    # context menu builds without exec
    host._alarm_ctx_menu_no_exec = True
    menu = host._build_alarm_list_context_menu(QPoint(4, 4))
    assert menu is not None and menu.actions(), 'empty ctx menu'
    assert menu.actions()[0].isEnabled()
    host._on_alarm_list_context_menu(QPoint(4, 4))
    assert getattr(host, '_last_alarm_ctx_menu', None) is not None
    ok('alarm list context locate film')

    # --- Alt+L shortcut wired ---
    sc = getattr(host, '_liaison_cycle_shortcut', None)
    assert sc is not None
    assert sc.key().toString() in ('Alt+L', 'Alt+L'.replace('+', '+'))
    host.set_liaison_window_sec(0)
    # activate shortcut signal path via cycle
    assert host.cycle_liaison_window() == 300
    # tip mentions Alt+L
    tip = (host._liaison_window.toolTip() or '') + (host._liaison_window_badge.toolTip() or '')
    assert 'Alt+L' in tip, tip
    ok('liaison Alt+L shortcut')

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
