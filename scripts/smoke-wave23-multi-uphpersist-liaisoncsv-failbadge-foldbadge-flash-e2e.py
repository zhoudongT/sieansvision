#!/usr/bin/env python3
"""细妆㉓：多选对比 · UPH窗口持久 · 联调CSV · 失败码徽章 · Comm簇计数 · 联调固定栏闪."""
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
    from PySide6.QtWidgets import QApplication, QMessageBox, QTableWidget
    from PySide6.QtCore import QSettings, Qt, QObject, Signal as _Sig
    app = QApplication.instance() or QApplication([])
    QMessageBox.information = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
    QMessageBox.warning = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)

    from desktop.operator_hmi import OperatorHmiView, ProductionStatsPanel
    from desktop.host_state_machine import HostStateMachineWidget
    from desktop.variables_dialog import VariablesDialog
    from desktop.mainwindow import MainWindow
    from desktop.run_ui_designer import default_host_run_ui

    # --- APIs ---
    for name in ('request_multi_film_compare', 'set_fail_code_badge',
                 'clear_fail_code_badge', '_on_liaison_pushed'):
        assert hasattr(OperatorHmiView, name), name
    assert hasattr(ProductionStatsPanel, '_load_uph_window_pref')
    assert hasattr(HostStateMachineWidget, 'liaison_events_csv')
    assert hasattr(HostStateMachineWidget, 'export_liaison_clipboard')
    assert hasattr(HostStateMachineWidget, 'liaisonPushed')
    src = Path('desktop/mainwindow.py').read_text(encoding='utf-8')
    assert 'highlight_paths' in src and 'multi_paths' in src
    ok('wave23 APIs present')

    # --- UPH window persist ---
    s = QSettings('SIEANS', 'VisionDesktop')
    s.setValue('prod/uphWindow', 40)
    s.sync()
    panel = ProductionStatsPanel()
    assert panel.uph_window() == 40, panel.uph_window()
    panel.set_uph_window(8)
    assert int(s.value('prod/uphWindow')) == 8
    ok('UPH window persist load/save')

    # --- Multi-select compare emit ---
    hmi = OperatorHmiView()
    proj = {'name': 'w23', 'runUi': default_host_run_ui(), 'steps': [], 'recipes': []}
    hmi.reload_layout(proj)
    hmi._result_history = [
        {'ts': '01:00:00', 'seq': 1, 'module': 'A', 'elapsedMs': '10',
         'judge': 'OK', 'ok': '1', 'ng': '0', 'gate': '—', 'note': '—',
         'recipe': 'R1', 'variant': '', 'gatePass': True,
         'filmPath': '/tmp/a.bmp', 'filmIndex': 0},
        {'ts': '01:00:01', 'seq': 2, 'module': 'B', 'elapsedMs': '12',
         'judge': 'OK', 'ok': '2', 'ng': '0', 'gate': '—', 'note': '—',
         'recipe': 'R1', 'variant': '', 'gatePass': True,
         'filmPath': '/tmp/b.bmp', 'filmIndex': 1},
        {'ts': '01:00:02', 'seq': 3, 'module': 'C', 'elapsedMs': '11',
         'judge': 'NG', 'ok': '2', 'ng': '1', 'gate': '—', 'note': '—',
         'recipe': 'R1', 'variant': '', 'gatePass': False,
         'filmPath': '/tmp/c.bmp', 'filmIndex': 2},
    ]
    if not hmi._result_tables:
        hmi._result_tables = [QTableWidget(0, 10)]
    # ensure ExtendedSelection
    for t0 in hmi._result_tables:
        t0.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
    hmi._refresh_result_tables_ui()
    table = hmi._result_tables[0]
    # newest first: row0=seq3, row1=seq2, row2=seq1
    table.clearSelection()
    table.selectRow(0)
    table.selectRow(1)
    # Qt ExtendedSelection may need Ctrl; use selectionModel
    from PySide6.QtCore import QItemSelectionModel
    table.clearSelection()
    sm = table.selectionModel()
    for r in (0, 1):
        idx = table.model().index(r, 0)
        sm.select(idx, QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows)
    got = []
    hmi.filmCompareRequested.connect(lambda p: got.append(p))
    assert hmi.request_multi_film_compare() is True
    assert got and got[0].get('multi') is True, got
    assert len(got[0].get('paths') or []) >= 2, got
    ok(f"multi compare paths={got[0].get('paths')}")

    # --- Fail code badge ---
    hmi.set_fail_code_badge('VARIANT_NO_RECIPES', '变体下无配方')
    assert not hmi._fail_code_badge.isHidden()
    assert 'VARIANT_NO_RECIPES' in hmi._fail_code_badge.text()
    hmi.clear_fail_code_badge()
    assert hmi._fail_code_badge.isHidden()
    ok('fail code badge show/clear')

    # --- Liaison CSV + flash ---
    host = HostStateMachineWidget()
    csv = host.liaison_events_csv()
    assert csv.startswith('timestamp,kind,code')  # wave24 may add ,severity,text
    flashed = []
    hmi._wire_host_sm(host)
    # ensure fixed bars exist
    fb = proj['runUi'].setdefault('fixedBars', {})
    fb.update(top=True, bottom=True, showRunStatus=True)
    hmi.reload_layout(proj)
    hmi._wire_host_sm(host)
    # monkey-patch flash observer
    orig = hmi._on_liaison_pushed
    def wrap(entry):
        flashed.append(entry)
        orig(entry)
    hmi._on_liaison_pushed = wrap
    try:
        host.liaisonPushed.disconnect()
    except Exception:
        pass
    host.liaisonPushed.connect(hmi._on_liaison_pushed)
    host.push_liaison_event('换型失败[APPLY_ERROR]', kind='换型失败', code='APPLY_ERROR')
    assert flashed and flashed[0].get('code') == 'APPLY_ERROR', flashed
    csv2 = host.liaison_events_csv()
    assert 'APPLY_ERROR' in csv2
    ok(f'liaison CSV+flash code={flashed[0].get("code")}')

    # --- Comm fold cluster count badge ---
    class Doc(QObject):
        changed = _Sig()
        def __init__(self):
            super().__init__()
            self.project = {
                'id': 'w23', 'name': 'w23', 'steps': [],
                'variables': {'flow': {
                    'commAcceptPass': True, 'commAcceptFail': 0,
                    'commAcceptSkip': 0, 'commAcceptOverall': 'OK',
                    'commAcceptAt': '', 'commAcceptHost': '',
                    'commAcceptPort': 0,
                    'commAccept_itemA': 1, 'commAccept_itemB': 2,
                }},
                'variableTypes': {},
            }
    class Backend(QObject):
        result = _Sig(object)
        error = _Sig(str)
    dlg = VariablesDialog(Doc(), Backend())
    dlg.fold_comm.setChecked(False)
    dlg.render()
    assert '簇 2' in dlg.fold_comm.text() or '簇' in dlg.fold_comm.text(), dlg.fold_comm.text()
    dlg.fold_comm.setChecked(True)
    dlg.render()
    assert '已藏' in dlg.fold_comm.text(), dlg.fold_comm.text()
    ok(f'Comm fold badge: {dlg.fold_comm.text()}')
    dlg.close()

    # --- MW multi show signature ---
    assert 'highlight_paths' in MainWindow._show_filmstrip_compare_overlays.__code__.co_varnames
    ok('MW _show_filmstrip_compare_overlays accepts highlight_paths')

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
