#!/usr/bin/env python3
"""细妆⑳：结果表行点击 ↔ 胶片定位加深."""
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
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])

    from desktop.widgets.filmstrip import FilmstripBar
    from desktop.operator_hmi import OperatorHmiView
    from desktop.run_ui_designer import default_host_run_ui

    fs = FilmstripBar()
    assert hasattr(fs, 'select_path') and hasattr(fs, 'select_index')
    ok('FilmstripBar.select_path/select_index present')

    # synthetic paths (no real images needed for select_index)
    fs._paths = ['/tmp/a.bmp', '/tmp/b.bmp', '/tmp/c.bmp']
    fs._index = 0
    # rebuild thumbs minimally
    from PySide6.QtWidgets import QListWidgetItem
    fs.thumbs.clear()
    for pth in fs._paths:
        fs.thumbs.addItem(QListWidgetItem(Path(pth).name))
    assert fs.select_index(2, emit=False) is True
    assert fs.current_index() == 2
    ok('select_index(2) → current=2')
    assert fs.select_path('/tmp/b.bmp', emit=False) is True
    assert fs.current_index() == 1
    ok('select_path(/tmp/b.bmp) → index 1')
    assert fs.select_path('missing-xyz.png', emit=False) is False
    ok('select_path missing → False')

    hmi = OperatorHmiView()
    assert hasattr(hmi, 'filmLocateRequested')
    assert hasattr(hmi, 'set_film_stamp')
    assert hasattr(hmi, 'highlight_rows_for_film')
    assert hasattr(hmi, '_on_result_row_clicked')
    ok('HMI film locate APIs present')

    proj = {'name': 'film-loc', 'runUi': default_host_run_ui(), 'steps': [], 'recipes': []}
    # ensure result table exists
    ui = proj['runUi']
    # default host ui should have 结果表 somewhere; force inject via reload
    hmi.reload_layout(proj)
    # manually seed history with film stamps
    hmi._result_history = [
        {'ts': '2026-10-28 01:00:00', 'seq': 1, 'module': 'A', 'elapsedMs': '10',
         'judge': 'OK', 'ok': '1', 'ng': '0', 'gate': '—', 'note': '—',
         'recipe': 'R1', 'variant': '', 'gatePass': True,
         'filmPath': '/tmp/a.bmp', 'filmIndex': 0},
        {'ts': '2026-10-28 01:00:01', 'seq': 2, 'module': 'B', 'elapsedMs': '12',
         'judge': 'NG', 'ok': '1', 'ng': '1', 'gate': '—', 'note': '—',
         'recipe': 'R1', 'variant': '', 'gatePass': False,
         'filmPath': '/tmp/b.bmp', 'filmIndex': 1},
    ]
    # ensure at least one result table
    if not hmi._result_tables:
        from PySide6.QtWidgets import QTableWidget
        t = QTableWidget(0, 10)
        hmi._result_tables = [t]
    hmi._refresh_result_tables_ui()
    table = hmi._result_tables[0]
    # newest first → row0 is seq2
    it = table.item(0, 0)
    meta = it.data(__import__('PySide6.QtCore', fromlist=['Qt']).Qt.ItemDataRole.UserRole) or {}
    assert meta.get('filmPath') == '/tmp/b.bmp', meta
    ok(f'refresh stamps UserRole filmPath={meta.get("filmPath")}')

    got = []
    hmi.filmLocateRequested.connect(lambda p: got.append(p))
    hmi._on_result_row_clicked(0, 0)
    assert got and got[0].get('path') == '/tmp/b.bmp', got
    ok(f'row click → filmLocateRequested {got[0].get('path')}')

    # reverse highlight
    matched = hmi.highlight_rows_for_film('/tmp/a.bmp', 0)
    assert matched, f'expected match got {matched}'
    ok(f'highlight_rows_for_film matched rows={matched}')

    # stamp API
    hmi.set_film_stamp('/tmp/c.bmp', 2)
    assert hmi._pending_film_stamp.get('path') == '/tmp/c.bmp'
    ok('set_film_stamp pending')

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
