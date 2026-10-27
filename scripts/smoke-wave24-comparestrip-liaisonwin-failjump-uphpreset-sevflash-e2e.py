#!/usr/bin/env python3
"""细妆㉔：多选对比侧栏 · 联调CSV时段 · 失败码跳Alarm · UPH预设 · 联闪严重度."""
from __future__ import annotations
import sys
import time
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
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtCore import QPointF, QEvent
    app = QApplication.instance() or QApplication([])
    QMessageBox.information = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
    QMessageBox.warning = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)

    from desktop.operator_hmi import OperatorHmiView, ProductionStatsPanel
    from desktop.host_state_machine import HostStateMachineWidget
    from desktop.widgets.filmstrip import CompareThumbStrip
    from desktop.mainwindow import MainWindow
    from desktop.run_ui_designer import default_host_run_ui

    # --- APIs ---
    for name in ('jump_fail_code_to_alarm', '_on_fail_code_badge_click',
                 '_on_liaison_pushed'):
        assert hasattr(OperatorHmiView, name), name
    assert hasattr(ProductionStatsPanel, '_sync_uph_preset_chrome')
    for name in ('filtered_liaison_events', 'liaison_window_sec',
                 'set_liaison_window_sec', 'jump_to_alarm_for_code',
                 '_liaison_severity'):
        assert hasattr(HostStateMachineWidget, name), name
    assert hasattr(CompareThumbStrip, 'set_paths')
    src = Path('desktop/mainwindow.py').read_text(encoding='utf-8')
    assert 'compare_strip' in src and '_on_compare_strip_path' in src
    ok('wave24 APIs present')

    # --- UPH presets ---
    s = QSettings('SIEANS', 'VisionDesktop')
    s.setValue('prod/uphWindow', 24)
    s.sync()
    panel = ProductionStatsPanel()
    assert hasattr(panel, '_uph_preset_btns') and len(panel._uph_preset_btns) == 5
    panel.set_uph_window(16)
    assert panel.uph_window() == 16
    # active chrome on 16
    active = [b for b in panel._uph_preset_btns if '3ecf8e' in (b.styleSheet() or '')]
    assert any(b.text() == '16' for b in active), [b.text() for b in active]
    panel.set_uph_window(48)
    assert panel.uph_window() == 48
    ok('UPH presets 16→48 + chrome')

    # --- Liaison CSV time window + severity ---
    host = HostStateMachineWidget(compact=True)
    assert HostStateMachineWidget._liaison_severity('换型失败', 'VARIANT_EMPTY') == 'error'
    assert HostStateMachineWidget._liaison_severity('报警清除', 'ALARM_CLEAR') == 'ok'
    assert HostStateMachineWidget._liaison_severity('试跑清除', 'TRIAL_CLEAR') == 'ok'
    host.push_liaison_event('变体名为空', kind='换型失败', code='VARIANT_EMPTY')
    host.push_liaison_event('试跑失败已清除', kind='试跑清除', code='TRIAL_CLEAR')
    host.push_liaison_event('普通联调', kind='联调', code='')
    evs = host.liaison_events()
    assert len(evs) >= 3
    assert evs[-3]['severity'] == 'error'
    assert evs[-2]['severity'] == 'ok'
    assert 'epoch' in evs[-1] and 'ts_full' in evs[-1]
    host.set_liaison_window_sec(300)
    assert host.liaison_window_sec() == 300
    filtered = host.filtered_liaison_events(300)
    assert len(filtered) >= 3  # just pushed
    csv = host.liaison_events_csv(300)
    assert 'severity' in csv.splitlines()[0]
    assert 'VARIANT_EMPTY' in csv and 'error' in csv
    # far-past event excluded
    old = dict(evs[-1])
    old['epoch'] = time.time() - 99999
    old['code'] = 'OLD_CODE'
    host._liaison_events.insert(0, old)
    filtered2 = host.filtered_liaison_events(300)
    assert all(e.get('code') != 'OLD_CODE' for e in filtered2), filtered2
    host.set_liaison_window_sec(0)
    assert any(e.get('code') == 'OLD_CODE' for e in host.filtered_liaison_events(0))
    ok('liaison CSV window + severity')

    # --- Fail code → Alarm jump ---
    hmi = OperatorHmiView()
    proj = {'name': 'w24', 'runUi': default_host_run_ui(), 'steps': [], 'recipes': []}
    hmi.reload_layout(proj)
    # ensure host wired (reload may create one)
    host2 = getattr(hmi, '_host_sm', None)
    if host2 is None:
        host2 = HostStateMachineWidget(compact=True)
        hmi._wire_host_sm(host2)
    host2.push_liaison_event('变体名为空', kind='换型失败', code='APPLY_ERROR')
    hmi.set_fail_code_badge('APPLY_ERROR', 'apply boom')
    assert not hmi._fail_code_badge.isHidden()
    assert hmi.jump_fail_code_to_alarm('APPLY_ERROR') is True
    # tab should be 报警历史
    tab_texts = [host2.tabs.tabText(i) for i in range(host2.tabs.count())]
    assert '报警' in host2.tabs.tabText(host2.tabs.currentIndex()), tab_texts
    assert 'APPLY_ERROR' in (host2._alarm_filter.text() or '')
    assert host2._alarm_status_filter.currentData() == 'liaison'
    ok('fail code → Alarm jump')

    # --- Severity flash styles ---
    flashed = []
    class _Bar:
        def __init__(self):
            self._ss = ''; self._txt = ''; self._hidden = False
        def setText(self, t): self._txt = t; flashed.append(('text', t))
        def setStyleSheet(self, s): self._ss = s; flashed.append(('ss', s))
        def show(self): self._hidden = False
        def isHidden(self): return self._hidden
        def text(self): return self._txt
        def styleSheet(self): return self._ss
    hmi._fix_top = _Bar(); hmi._fix_bottom = _Bar()
    hmi._fixed_bars_cache = {}
    hmi._on_liaison_pushed({'kind': '换型失败', 'code': 'VARIANT_EMPTY',
                            'text': 'x', 'severity': 'error'})
    assert any('e35d6a' in s or '#3a1c1c' in s for k, s in flashed if k == 'ss'), flashed
    flashed.clear()
    hmi._on_liaison_pushed({'kind': '报警清除', 'code': 'ALARM_CLEAR',
                            'text': 'ok', 'severity': 'ok'})
    assert any('3ecf8e' in s or '#1c3a2a' in s for k, s in flashed if k == 'ss'), flashed
    ok('liaison flash severity colors')

    # --- CompareThumbStrip ---
    strip = CompareThumbStrip()
    assert strip.isHidden()
    # create tiny bmps
    from PySide6.QtGui import QImage
    tmp = Path('/tmp/sieans-w24')
    tmp.mkdir(exist_ok=True)
    paths = []
    for i, name in enumerate(('a.bmp', 'b.bmp', 'c.bmp')):
        fp = tmp / name
        img = QImage(32, 32, QImage.Format.Format_RGB32)
        img.fill(0xFF0000 + i * 0x003300)
        img.save(str(fp))
        paths.append(str(fp))
    strip.set_paths(paths, active=paths[1])
    assert not strip.isHidden()
    assert strip.paths() == paths
    assert strip._list.count() == 3
    assert strip._title.text().startswith('对比')
    activated = []
    strip.pathActivated.connect(lambda p: activated.append(p))
    strip._list.setCurrentRow(0)
    item = strip._list.item(0)
    strip._on_item(item)
    assert activated and activated[0] == paths[0]
    strip.clear()
    assert strip.isHidden()
    ok('CompareThumbStrip set/clear/activate')

    # --- MainWindow compare_strip wiring ---
    assert hasattr(MainWindow, '_on_compare_strip_path')
    assert 'CompareThumbStrip' in Path('desktop/mainwindow.py').read_text(encoding='utf-8')
    ok('MW compare_strip wiring present')

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
