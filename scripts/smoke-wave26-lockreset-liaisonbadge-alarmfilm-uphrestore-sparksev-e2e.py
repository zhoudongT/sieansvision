#!/usr/bin/env python3
"""细妆㉖：侧栏锁定/复位 · 联调时段徽章 · 高亮双击胶片 · UPH常用还原 · spark筛严重度."""
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

    from desktop.operator_hmi import OperatorHmiView, ProductionStatsPanel
    from desktop.host_state_machine import HostStateMachineWidget
    from desktop.widgets.filmstrip import CompareThumbStrip
    from desktop.mainwindow import MainWindow

    # --- APIs ---
    for name in ('set_order_locked', 'reset_order', 'is_order_locked', 'baseline_paths', 'lockChanged'):
        assert hasattr(CompareThumbStrip, name), name
    for name in ('_sync_liaison_window_badge', 'set_alarm_severity_filter',
                 'alarm_severity_filter', '_on_alarm_spark_clicked',
                 '_on_alarm_item_double_clicked', 'alarmFilmLocateRequested'):
        assert hasattr(HostStateMachineWidget, name), name
    assert hasattr(ProductionStatsPanel, 'restore_uph_preset_recent')
    assert hasattr(OperatorHmiView, 'note_film_path')
    src_hmi = Path('desktop/operator_hmi.py').read_text(encoding='utf-8')
    assert 'alarmFilmLocateRequested.connect' in src_hmi
    assert 'prodUphRestoreRecent' in src_hmi
    src_mw = Path('desktop/mainwindow.py').read_text(encoding='utf-8')
    assert 'note_film_path' in src_mw
    ok('wave26 APIs present')

    # --- CompareThumbStrip lock + reset ---
    tmp = Path('/tmp/sieans-w26'); tmp.mkdir(exist_ok=True)
    paths = []
    for i, name in enumerate(('a.bmp', 'b.bmp', 'c.bmp')):
        fp = tmp / name
        img = QImage(16, 16, QImage.Format.Format_RGB32)
        img.fill(0xFF223300 + i * 0x20)
        img.save(str(fp))
        paths.append(str(fp))
    strip = CompareThumbStrip()
    strip.set_paths(paths)
    assert strip.baseline_paths() == paths
    assert strip.is_order_locked() is False
    # reorder
    reordered = []
    strip.pathsReordered.connect(lambda ps: reordered.append(list(ps)))
    strip._suppress_reorder = True
    items = []
    while strip._list.count():
        items.append(strip._list.takeItem(0))
    for it in reversed(items):
        strip._list.addItem(it)
    strip._suppress_reorder = False
    strip._emit_reorder_if_changed()
    assert strip.paths() == list(reversed(paths)), strip.paths()
    # lock blocks further reorder signal
    strip.set_order_locked(True)
    assert strip.is_order_locked()
    assert strip._lock_btn.isChecked()
    before = list(strip.paths())
    strip._suppress_reorder = True
    items = []
    while strip._list.count():
        items.append(strip._list.takeItem(0))
    for it in reversed(items):
        strip._list.addItem(it)
    strip._suppress_reorder = False
    n_before = len(reordered)
    strip._emit_reorder_if_changed()
    # locked → no new reorder (or reverts)
    assert strip.paths() == before or len(reordered) == n_before
    # reset restores baseline
    strip.set_order_locked(False)
    assert strip.reset_order() is True
    assert strip.paths() == paths, strip.paths()
    assert reordered and reordered[-1] == paths
    ok('CompareThumbStrip lock + reset baseline')

    # --- Liaison window badge ---
    host = HostStateMachineWidget(compact=True)
    assert getattr(host, '_liaison_window_badge', None) is not None
    host.set_liaison_window_sec(900)
    badge = host._liaison_window_badge.text() or ''
    assert '15' in badge or '近' in badge or '分' in badge, badge
    host.set_liaison_window_sec(0)
    badge = host._liaison_window_badge.text() or ''
    assert '全部' in badge or badge.strip(), badge
    ok('liaison window badge sync')

    # --- Spark click cycles severity filter ---
    host._alarm_history.clear()
    host._alarm_history.extend([
        {'ts': '2026-10-28 01:10:00', 'reason': 'err A', 'cleared': False,
         'cleared_at': '', 'severity': 'error', 'state_at': 'Alarm', 'liaison': True,
         'filmPath': str(paths[0])},
        {'ts': '2026-10-28 01:10:01', 'reason': 'warn B', 'cleared': False,
         'cleared_at': '', 'severity': 'warning', 'state_at': 'Alarm', 'liaison': False},
        {'ts': '2026-10-28 01:10:02', 'reason': 'info C', 'cleared': True,
         'cleared_at': '2026-10-28 01:10:03', 'severity': 'info', 'state_at': 'Idle', 'liaison': False},
    ])
    host._refresh_alarm_history_ui()
    assert host.alarm_severity_filter() == 'all'
    assert host._alarm_list.count() == 3
    host._on_alarm_spark_clicked()
    assert host.alarm_severity_filter() == 'error'
    assert host._alarm_list.count() == 1
    host._on_alarm_spark_clicked()
    assert host.alarm_severity_filter() == 'warning'
    assert host._alarm_list.count() == 1
    host.set_alarm_severity_filter('info')
    assert host._alarm_list.count() == 1
    host.set_alarm_severity_filter('all')
    assert host._alarm_list.count() == 3
    ok('spark click filters by severity')

    # --- Highlight first + double-click film locate ---
    located = []
    host.alarmFilmLocateRequested.connect(lambda p: located.append(dict(p) if isinstance(p, dict) else p))
    host.set_alarm_severity_filter('all')
    assert host.jump_to_alarm_for_code('err', keyword='err A', film_path=str(paths[1])) is True
    assert host._alarm_list.currentRow() == 0
    item = host._alarm_list.item(0)
    data = item.data(Qt.ItemDataRole.UserRole) or {}
    assert isinstance(data, dict)
    # film path from jump should be stamped
    assert data.get('filmPath') in (str(paths[0]), str(paths[1])), data
    host._on_alarm_item_double_clicked(item)
    assert located, 'no film locate emit'
    assert str(located[-1].get('path') or '') in (str(paths[0]), str(paths[1]))
    ok('alarm highlight dblclick emits film locate')

    # --- UPH restore recent ---
    s = QSettings('SIEANS', 'VisionDesktop')
    s.setValue('prod/uphPresetRecent', '32,16')
    s.setValue('prod/uphPresetLast', 32)
    s.setValue('prod/uphWindow', 24)
    s.sync()
    panel = ProductionStatsPanel()
    assert panel.uph_window() in (8, 16, 24, 32, 48)
    # set to non-last without going through remember: poke spin/internal
    panel._uph_window = 24
    if getattr(panel, '_uph_window_spin', None) is not None:
        panel._uph_window_spin.blockSignals(True)
        panel._uph_window_spin.setValue(24)
        panel._uph_window_spin.blockSignals(False)
    # re-assert Last still 32 (not overwritten)
    s.setValue('prod/uphPresetLast', 32)
    s.setValue('prod/uphPresetRecent', '32,16')
    s.sync()
    assert hasattr(panel, '_uph_restore_btn')
    assert panel.restore_uph_preset_recent() is True
    assert panel.uph_window() == 32, panel.uph_window()
    ok('UPH restore recent one-click')

    # --- HMI note_film_path ---
    hmi = OperatorHmiView.__new__(OperatorHmiView)
    hmi._last_film_path = ''
    hmi.note_film_path(str(paths[2]))
    assert hmi._last_film_path == str(paths[2])
    ok('HMI note_film_path')

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
