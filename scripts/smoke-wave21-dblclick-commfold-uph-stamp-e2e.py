#!/usr/bin/env python3
"""细妆㉑：结果表双击对比叠层 · 试跑失败Alarm联调 · Comm折叠 · UPH趋势 · 补stamp."""
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
    from PySide6.QtCore import QObject, Signal
    app = QApplication.instance() or QApplication([])
    QMessageBox.information = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
    QMessageBox.warning = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)

    from desktop.operator_hmi import OperatorHmiView, ProductionStatsPanel
    from desktop.run_ui_designer import default_host_run_ui
    from desktop.variables_dialog import VariablesDialog
    import inspect
    from desktop.mainwindow import MainWindow

    # --- APIs present ---
    hmi = OperatorHmiView()
    for name in (
        'filmCompareRequested', 'filmStampRequest',
        '_on_result_row_double_clicked', 'request_manual_film_stamp',
        'apply_manual_film_stamp', '_filtered_result_rows',
    ):
        assert hasattr(hmi, name), name
    ok('HMI wave21 APIs present')

    assert hasattr(MainWindow, '_on_hmi_film_compare')
    assert hasattr(MainWindow, '_on_hmi_film_stamp')
    ok('MainWindow compare/stamp handlers present')

    # --- UPH trend ---
    panel = ProductionStatsPanel()
    assert hasattr(panel, 'trend_uph_text') and hasattr(panel, 'uph_history')
    assert '等待' in panel.trend_uph_text()
    panel.record(True, elapsed_ms=100)
    panel.record(True, elapsed_ms=200)
    panel.record(False, elapsed_ms=150)
    hist = panel.uph_history()
    assert len(hist) >= 3, hist
    text = panel.trend_uph_text()
    assert 'UPH' in text and '末次' in text, text
    assert panel._uph_trend_lab is not None
    assert 'UPH' in panel._uph_trend_lab.text()
    ok(f'UPH trend board: {text[:70]}')

    # --- result dblclick emits compare ---
    proj = {'name': 'w21', 'runUi': default_host_run_ui(), 'steps': [], 'recipes': []}
    hmi.reload_layout(proj)
    hmi._result_history = [
        {'ts': '2026-10-28 01:00:00', 'seq': 1, 'module': 'A', 'elapsedMs': '10',
         'judge': 'OK', 'ok': '1', 'ng': '0', 'gate': '—', 'note': '—',
         'recipe': 'R1', 'variant': '', 'gatePass': True,
         'filmPath': '/tmp/a.bmp', 'filmIndex': 0},
        {'ts': '2026-10-28 01:00:01', 'seq': 2, 'module': 'B', 'elapsedMs': '12',
         'judge': 'NG', 'ok': '1', 'ng': '1', 'gate': '—', 'note': '—',
         'recipe': 'R1', 'variant': '', 'gatePass': False,
         'filmPath': '', 'filmIndex': None},  # missing path
    ]
    if not hmi._result_tables:
        from PySide6.QtWidgets import QTableWidget
        hmi._result_tables = [QTableWidget(0, 10)]
    hmi._refresh_result_tables_ui()

    got_cmp = []
    got_loc = []
    hmi.filmCompareRequested.connect(lambda p: got_cmp.append(p))
    hmi.filmLocateRequested.connect(lambda p: got_loc.append(p))
    # newest first → row0 is seq2 (no path); row1 is seq1
    hmi._on_result_row_double_clicked(1, 0)
    assert got_cmp and got_cmp[0].get('path') == '/tmp/a.bmp', got_cmp
    assert got_loc and got_loc[0].get('path') == '/tmp/a.bmp', got_loc
    ok(f'dblclick → compare+locate path={got_cmp[0].get("path")}')

    # --- manual stamp ---
    got_stamp = []
    hmi.filmStampRequest.connect(lambda p: got_stamp.append(p))
    # select row0 (seq2 missing path) on table
    table = hmi._result_tables[0]
    table.selectRow(0)
    assert hmi.request_manual_film_stamp() is True
    assert got_stamp and got_stamp[0].get('seq') == 2, got_stamp
    ok(f'stamp request seq={got_stamp[0].get("seq")}')
    assert hmi.apply_manual_film_stamp(seq=2, path='/tmp/c.bmp', index=2) is True
    e = [x for x in hmi._result_history if x.get('seq') == 2][0]
    assert e.get('filmPath') == '/tmp/c.bmp' and e.get('filmIndex') == 2, e
    ok('apply_manual_film_stamp wrote path/index')

    # --- trial fail Alarm 联调 ---
    fb = proj['runUi'].setdefault('fixedBars', {})
    fb.update(top=True, bottom=True, left=True, right=True,
              showRunStatus=True, showOkNg=True)
    hmi.reload_layout(proj)
    hmi.set_recipe_chrome('测量链', 'A型')
    hmi.set_trial_backfill_pending(True)
    class FakePanel:
        def ok_history(self): return [False]
        def ok_count(self): return 0
        def ng_count(self): return 1
        def elapsed_history(self): return [99.0]
        def gate_key(self): return None
        def set_gate_key(self, *a, **k): pass
        def set_host_state_mirror(self, *a, **k): pass
    hmi._stats_panels = [FakePanel()]
    assert hmi.backfill_after_trial({'state': 'failed', 'elapsedMs': 99}) is True
    assert hmi._trial_fail_alarm is True
    assert getattr(hmi, '_host_state', None) == 'Alarm' or hmi._alarm_was_on is True
    ok('trial fail → _trial_fail_alarm + Alarm chrome')
    hmi._paint_machine_chrome('Idle')
    tip = hmi._fix_top.text() if hmi._fix_top else ''
    assert hmi._trial_fail_alarm is False
    assert ('联调' in tip) or ('清除' in tip), tip
    ok(f'trial-fail clear restore tip: {tip[:70]}')

    # --- Comm fold ---
    class Doc(QObject):
        changed = Signal()
        def __init__(self):
            super().__init__()
            self.project = {
                'id': 't', 'name': 't', 'steps': [],
                'variables': {
                    'other': 1,
                    'commAcceptPass': 2,
                    'commAcceptFail': 0,
                    'commAcceptOverall': 'PASS',
                    'commAccept_itemA': 'OK',
                    'commAccept_itemB': 'NG',
                    'zzz': 9,
                },
                'variableTypes': {},
            }
        def mark_dirty(self): pass
    class Backend:
        def request(self, *a, **k): return 1
        result = type('S', (), {'connect': staticmethod(lambda *a, **k: None)})()
        error = type('S', (), {'connect': staticmethod(lambda *a, **k: None)})()
    dlg = VariablesDialog(Doc(), Backend(), None)
    assert hasattr(dlg, 'fold_comm')
    dlg.runtime_draft = {
        'flow': dict(dlg.document.project['variables']),
        'global': {}, 'modules': {}, 'globalTypes': {},
    }
    dlg.snapshot = dict(dlg.runtime_draft)
    dlg.fold_comm.setChecked(False)
    dlg.render()
    names_open = [
        dlg.table.item(r, 1).text()
        for r in range(dlg.table.rowCount())
        if dlg.table.item(r, 1)
    ]
    assert 'commAccept_itemA' in names_open, names_open
    n_open = dlg.table.rowCount()
    dlg.fold_comm.setChecked(True)
    dlg.render()
    names_fold = [
        dlg.table.item(r, 1).text()
        for r in range(dlg.table.rowCount())
        if dlg.table.item(r, 1)
    ]
    assert 'commAccept_itemA' not in names_fold, names_fold
    assert any('折叠' in n for n in names_fold), names_fold
    assert 'commAcceptPass' in names_fold
    assert dlg.table.rowCount() < n_open
    ok(f'Comm fold: open={n_open} folded={dlg.table.rowCount()} names={names_fold[:6]}')

    # trend chart cell has UPH spark after reload with 线图
    ok('wave21 core checks done')

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
