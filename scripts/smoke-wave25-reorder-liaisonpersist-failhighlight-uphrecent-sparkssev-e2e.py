#!/usr/bin/env python3
"""细妆㉕：侧栏拖拽重排 · 联调时段持久 · 跳后高亮 · UPH快捷记忆 · Alarm spark染色."""
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
    from PySide6.QtWidgets import QApplication, QMessageBox, QListWidgetItem
    from PySide6.QtCore import QSettings, Qt, QAbstractItemModel
    app = QApplication.instance() or QApplication([])
    QMessageBox.information = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
    QMessageBox.warning = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)

    from desktop.operator_hmi import OperatorHmiView, ProductionStatsPanel
    from desktop.host_state_machine import HostStateMachineWidget
    from desktop.widgets.filmstrip import CompareThumbStrip
    from desktop.mainwindow import MainWindow

    # --- APIs ---
    assert hasattr(CompareThumbStrip, 'pathsReordered')
    assert hasattr(CompareThumbStrip, '_emit_reorder_if_changed')
    assert hasattr(HostStateMachineWidget, '_save_liaison_window_pref')
    assert hasattr(HostStateMachineWidget, '_highlight_alarm_list_first')
    assert hasattr(HostStateMachineWidget, '_host_settings')
    assert hasattr(ProductionStatsPanel, '_remember_uph_preset')
    assert hasattr(ProductionStatsPanel, 'uph_preset_recent')
    src = Path('desktop/mainwindow.py').read_text(encoding='utf-8')
    assert '_on_compare_strip_reordered' in src
    ok('wave25 APIs present')

    # --- Liaison window persist ---
    s = QSettings('SIEANS', 'VisionDesktop')
    s.setValue('host/liaisonWindowSec', 900)
    s.sync()
    host = HostStateMachineWidget(compact=True)
    assert host.liaison_window_sec() == 900, host.liaison_window_sec()
    host.set_liaison_window_sec(300)
    assert int(s.value('host/liaisonWindowSec')) == 300
    host.set_liaison_window_sec(0)
    assert int(s.value('host/liaisonWindowSec') or 0) == 0
    ok('liaison window persist load/save')

    # --- Fail jump highlight first ---
    host.set_state('Alarm', '换型失败[VARIANT_EMPTY] · 变体名为空')
    host.set_state('Idle', '清除')
    host.set_state('Alarm', '换型失败[APPLY_ERROR] · apply boom')
    host.push_liaison_event('apply boom', kind='换型失败', code='APPLY_ERROR')
    # mark last alarm as liaison
    if host._alarm_history:
        host._alarm_history[-1]['liaison'] = True
        host._alarm_history[-1]['reason'] = '换型失败[APPLY_ERROR] · apply boom'
    assert host.jump_to_alarm_for_code('APPLY_ERROR') is True
    assert host._alarm_list.count() >= 1
    assert host._alarm_list.currentRow() == 0
    # highlight method returns True
    assert host._highlight_alarm_list_first(keyword='APPLY_ERROR') is True
    ok('fail jump highlights first list row')

    # --- Alarm spark severity colors ---
    host._refresh_alarm_history_ui()
    spark_txt = host._alarm_spark.text() or ''
    assert 'e35d6a' in spark_txt or '#e35d6a' in spark_txt or '报警序列' in spark_txt, spark_txt[:200]
    # force an error severity entry and recheck rich text
    host._alarm_history.append({
        'ts': '2026-10-28 01:00:00', 'reason': 'VARIANT_EMPTY fail',
        'cleared': False, 'cleared_at': '', 'severity': 'error',
        'state_at': 'Alarm', 'liaison': True,
    })
    host._alarm_history.append({
        'ts': '2026-10-28 01:00:01', 'reason': 'cleared warn',
        'cleared': True, 'cleared_at': '2026-10-28 01:00:02', 'severity': 'warning',
        'state_at': 'Idle', 'liaison': False,
    })
    host._refresh_alarm_history_ui()
    spark_txt = host._alarm_spark.text() or ''
    assert '#e35d6a' in spark_txt, spark_txt[:300]
    assert '#5a6068' in spark_txt or '#e0b84a' in spark_txt, spark_txt[:300]
    ok('alarm spark severity rich-text colors')

    # --- UPH preset recent memory ---
    s.setValue('prod/uphPresetRecent', '')
    s.setValue('prod/uphWindow', 24)
    s.sync()
    panel = ProductionStatsPanel()
    panel.set_uph_window(16)
    recent = panel.uph_preset_recent()
    assert recent and recent[0] == 16, recent
    panel.set_uph_window(48)
    recent = panel.uph_preset_recent()
    assert recent[0] == 48 and 16 in recent, recent
    raw = str(s.value('prod/uphPresetRecent') or '')
    assert '48' in raw and '16' in raw, raw
    assert int(s.value('prod/uphPresetLast') or 0) == 48
    # chrome marks recent
    panel._sync_uph_preset_chrome()
    tips = [b.toolTip() for b in panel._uph_preset_btns]
    assert any('常用' in (t or '') for t in tips), tips
    ok('UPH preset recent QSettings memory')

    # --- CompareThumbStrip reorder emit ---
    from PySide6.QtGui import QImage
    strip = CompareThumbStrip()
    tmp = Path('/tmp/sieans-w25'); tmp.mkdir(exist_ok=True)
    paths = []
    for i, name in enumerate(('x.bmp', 'y.bmp', 'z.bmp')):
        fp = tmp / name
        img = QImage(24, 24, QImage.Format.Format_RGB32)
        img.fill(0xFF112200 + i * 0x10)
        img.save(str(fp))
        paths.append(str(fp))
    strip.set_paths(paths)
    assert strip.paths() == paths
    reordered = []
    strip.pathsReordered.connect(lambda ps: reordered.append(list(ps)))
    # simulate reorder by rewriting list order (take items)
    strip._suppress_reorder = True
    items_data = []
    while strip._list.count():
        it = strip._list.takeItem(0)
        items_data.append(it)
    # reverse
    for it in reversed(items_data):
        strip._list.addItem(it)
    strip._suppress_reorder = False
    strip._emit_reorder_if_changed()
    assert reordered, 'no reorder signal'
    assert reordered[-1] == list(reversed(paths)), reordered[-1]
    assert strip.paths() == list(reversed(paths))
    ok('CompareThumbStrip pathsReordered')

    # --- MW handler present ---
    assert hasattr(MainWindow, '_on_compare_strip_reordered')
    ok('MW reorder wiring present')

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
