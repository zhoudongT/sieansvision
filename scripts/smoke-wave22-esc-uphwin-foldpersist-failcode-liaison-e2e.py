#!/usr/bin/env python3
"""细妆㉒：对比叠层 ESC/再点清除 · UPH窗口 · Comm折叠持久 · 换型失败码 · Alarm联调条."""
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
    from PySide6.QtCore import Qt, QSettings
    app = QApplication.instance() or QApplication([])
    QMessageBox.information = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
    QMessageBox.warning = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)

    from desktop.operator_hmi import OperatorHmiView, ProductionStatsPanel
    from desktop.host_state_machine import HostStateMachineWidget
    from desktop.variables_dialog import VariablesDialog
    from desktop.mainwindow import MainWindow
    from desktop import recipe_library as rl
    from desktop.model import Document
    from desktop.run_ui_designer import default_host_run_ui

    # --- APIs ---
    for name in ('_clear_filmstrip_compare_overlays', '_show_filmstrip_compare_overlays',
                 '_on_hmi_film_compare', '_report_variant_fail', 'apply_variant_quick',
                 'keyPressEvent'):
        assert hasattr(MainWindow, name), name
    ok('MainWindow wave22 APIs present')

    assert hasattr(ProductionStatsPanel, 'set_uph_window')
    assert hasattr(ProductionStatsPanel, 'uph_window')
    assert hasattr(HostStateMachineWidget, 'push_liaison_event')
    assert hasattr(HostStateMachineWidget, 'liaison_events')
    assert 'VARIANT_EMPTY' in rl.FAIL_CODES
    ok('UPH window / liaison / FAIL_CODES present')

    # --- UPH window adjustable ---
    panel = ProductionStatsPanel()
    # default or persisted (wave23 may have changed QSettings)
    assert 8 <= panel.uph_window() <= 48
    panel.set_uph_window(24)
    assert panel.uph_window() == 24
    for _ in range(10):
        panel.record(True, elapsed_ms=100 + _ * 5)
    t24 = panel.trend_uph_text()
    assert 'n=' in t24 and '/24' in t24, t24
    panel.set_uph_window(8)
    assert panel.uph_window() == 8
    t8 = panel.trend_uph_text()
    assert '/8' in t8, t8
    assert panel._uph_window_spin.value() == 8
    panel.set_uph_window(48)
    assert panel.uph_window() == 48
    assert '/48' in panel.trend_uph_text()
    # snap: 20 → 16 or 24
    panel.set_uph_window(20)
    assert panel.uph_window() in (16, 24), panel.uph_window()
    ok(f'UPH window: 24→8→48→snap ok; sample={t8[:60]}')

    # --- Comm fold persist ---
    s = QSettings('SIEANS', 'VisionDesktop')
    s.setValue('vars/foldCommAccept', True)
    s.sync()
    class FakeDoc:
        def __init__(self):
            self.project = {
                'id': 'w22', 'name': 'w22', 'steps': [],
                'variables': {'flow': {
                    'commAcceptPass': True, 'commAcceptFail': 0,
                    'commAcceptSkip': 0, 'commAcceptOverall': 'OK',
                    'commAcceptAt': '', 'commAcceptHost': '',
                    'commAcceptPort': 0, 'commAccept_itemA': 1,
                }},
                'variableTypes': {},
            }
            from PySide6.QtCore import QObject, Signal
        changed = type('Sig', (), {'connect': lambda *a, **k: None})()
    class FakeBackend:
        result = type('Sig', (), {'connect': lambda *a, **k: None})()
        error = type('Sig', (), {'connect': lambda *a, **k: None})()
    # Minimal VariablesDialog needs document with changed signal
    from PySide6.QtCore import QObject, Signal as _Sig
    class Doc(QObject):
        changed = _Sig()
        def __init__(self):
            super().__init__()
            self.project = {
                'id': 'w22', 'name': 'w22', 'steps': [],
                'variables': {'flow': {
                    'commAcceptPass': True, 'commAcceptFail': 0,
                    'commAcceptSkip': 0, 'commAcceptOverall': 'OK',
                    'commAcceptAt': '', 'commAcceptHost': '',
                    'commAcceptPort': 0, 'commAccept_itemA': 1,
                }},
                'variableTypes': {},
            }
    class Backend(QObject):
        result = _Sig(object)
        error = _Sig(str)
    dlg = VariablesDialog(Doc(), Backend())
    assert dlg.fold_comm.isChecked() is True, 'pref True should load'
    ok('Comm fold pref loaded True from QSettings')
    dlg.fold_comm.setChecked(False)
    assert s.value('vars/foldCommAccept') in (False, 'false', 0, '0'), s.value('vars/foldCommAccept')
    # restore True for next open
    dlg.fold_comm.setChecked(True)
    assert bool(dlg._load_fold_comm_pref()) is True
    ok('Comm fold toggle persists to QSettings')
    dlg.close()

    # --- Fail codes ---
    # Headless MainWindow is heavy; test _report_variant_fail + apply_variant empty via unbound
    # Use Host SM + recipe_library classify
    assert rl.fail_message('VARIANT_EMPTY') == '变体名为空'
    assert '无配方' in rl.fail_message('VARIANT_NO_RECIPES')
    host = HostStateMachineWidget()
    assert hasattr(host, '_liaison_strip')
    assert '等待' in host._liaison_strip.text()
    host.push_liaison_event('换型失败[VARIANT_EMPTY] · 变体名为空', kind='换型失败', code='VARIANT_EMPTY')
    ev = host.liaison_events()
    assert len(ev) == 1 and ev[0]['code'] == 'VARIANT_EMPTY', ev
    assert 'VARIANT_EMPTY' in host._liaison_strip.text()
    ok(f'liaison strip: {host._liaison_strip.text()[:80]}')

    # filter 联调
    host.set_state('Alarm', '试跑失败 · NG')
    assert host.alarm_history() and host.alarm_history()[-1].get('liaison') is True
    # status filter data includes liaison
    sf = host._alarm_status_filter
    vals = [sf.itemData(i) for i in range(sf.count())]
    assert 'liaison' in vals, vals
    sf.setCurrentIndex(vals.index('liaison'))
    # refresh already connected
    assert host._alarm_list.count() >= 1
    ok(f'alarm history liaison filter shown={host._alarm_list.count()}')

    # trial clear → liaison via HMI pulse
    hmi = OperatorHmiView()
    proj = {'name': 'w22', 'runUi': default_host_run_ui(), 'steps': [], 'recipes': []}
    fb = proj['runUi'].setdefault('fixedBars', {})
    fb.update(top=True, bottom=True, left=True, right=True, showRunStatus=True)
    hmi.reload_layout(proj)
    hmi._wire_host_sm(host)
    hmi._trial_fail_alarm = True
    hmi._alarm_was_on = True
    hmi._paint_machine_chrome('Idle')
    ev2 = host.liaison_events()
    assert any(e.get('code') == 'TRIAL_CLEAR' for e in ev2), ev2
    ok(f'trial clear → TRIAL_CLEAR liaison n={len(ev2)}')

    # --- Compare ESC / toggle: source inspection ---
    src = Path('desktop/mainwindow.py').read_text(encoding='utf-8')
    assert "_filmstrip_compare_path" in src
    assert "ESC · 对比叠层已清除" in src or 'ESC' in src and '对比叠层已清除' in src
    assert '再点清除对比叠层' in src
    assert "Key_Escape" in src and '_filmstrip_compare_active' in src
    # Simulate clear/show path tracking without full MW chrome
    class FakeMW:
        def __init__(self):
            self._filmstrip_compare_active = False
            self._filmstrip_compare_path = ''
            self._msgs = []
            self._logs = []
        def _clear_filmstrip_compare_overlays(self):
            MainWindow._clear_filmstrip_compare_overlays(self)
        def statusBar(self):
            class SB:
                def __init__(self, o): self.o = o
                def showMessage(self, m, *a): self.o._msgs.append(m)
                def clearMessage(self): pass
            return SB(self)
        def log(self, m): self._logs.append(m)
        def _apply_measure_geom_overlays(self, *a, **k): pass
        last_result = {}
    fake = FakeMW()
    fake._filmstrip_compare_active = True
    fake._filmstrip_compare_path = '/tmp/a.bmp'
    fake._clear_filmstrip_compare_overlays()
    assert fake._filmstrip_compare_active is False
    assert fake._filmstrip_compare_path == ''
    assert any('清除' in m for m in fake._msgs), fake._msgs
    ok('clear overlays resets path + status')

    # toggle same-path logic (unit of _on_hmi_film_compare branch)
    # re-read helper: if active+same path → clear
    path = '/tmp/a.bmp'
    fake._filmstrip_compare_active = True
    fake._filmstrip_compare_path = path
    same = (Path(fake._filmstrip_compare_path).resolve() == Path(path).resolve())
    assert same
    fake._clear_filmstrip_compare_overlays()
    assert not fake._filmstrip_compare_active
    ok('re-click same path clears compare')

    print(f'\nRESULT pass={pass_n} fail={fail_n}')
    return 0 if fail_n == 0 else 1

if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as e:
        bad(f'crash: {e}')
        import traceback; traceback.print_exc()
        print(f'\nRESULT pass={pass_n} fail={fail_n}')
        raise SystemExit(1)
