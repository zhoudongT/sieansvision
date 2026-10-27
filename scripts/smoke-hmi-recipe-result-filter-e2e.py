#!/usr/bin/env python3
"""细妆⑲：结果表/胶片 ↔ 配方徽章联动（筛选 + 配方列 + strip 提示）."""
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

    from desktop.operator_hmi import OperatorHmiView
    from desktop.run_ui_designer import default_host_run_ui

    hmi = OperatorHmiView()
    proj = {
        'name': 'recipe-filter',
        'runUi': default_host_run_ui(),
        'steps': [],
    }
    hmi.reload_layout(proj)
    # Force-create a 结果表 widget (layout may be 图像+状态机 only);
    # keep Python ref so Qt child QTableWidget is not GC'd.
    _result_cell = hmi._build_control('结果表', {})
    assert hmi._result_tables, 'no result tables after _build_control'
    ok('result table widget built')

    assert hasattr(hmi, '_toggle_recipe_filter')
    assert hasattr(hmi, '_sync_filmstrip_recipe_hint')
    ok('recipe filter APIs present')

    hmi.set_recipe_chrome('型号甲', 'V1')
    assert '型号甲' in hmi._recipe_badge.text()
    ok('set_recipe_chrome stamps live recipe')

    hmi._live_recipe = '型号甲'
    hmi._live_variant = 'V1'
    hmi._result_history = [
        {'ts': 't1', 'seq': 1, 'module': 'A', 'elapsedMs': '10', 'judge': 'OK',
         'ok': '1', 'ng': '0', 'gate': '—', 'note': '—', 'gatePass': True,
         'recipe': '型号甲', 'variant': 'V1'},
        {'ts': 't2', 'seq': 2, 'module': 'B', 'elapsedMs': '12', 'judge': 'NG',
         'ok': '1', 'ng': '1', 'gate': '—', 'note': '—', 'gatePass': False,
         'recipe': '型号乙', 'variant': ''},
        {'ts': 't3', 'seq': 3, 'module': 'C', 'elapsedMs': '11', 'judge': 'OK',
         'ok': '2', 'ng': '1', 'gate': '—', 'note': '—', 'gatePass': True,
         'recipe': '型号甲', 'variant': 'V1'},
    ]
    hmi._recipe_filter_active = False
    hmi._refresh_result_tables_ui()
    tables = hmi._result_tables
    assert tables, 'no result tables'
    assert tables[0].columnCount() >= 10
    assert tables[0].horizontalHeaderItem(9).text() == '配方'
    ok(f'result table has 配方 col (cols={tables[0].columnCount()})')

    csv = hmi.result_history_csv()
    assert 'recipe' in csv.splitlines()[0]
    assert '型号甲' in csv
    ok('CSV headers include recipe/variant')

    hmi._toggle_recipe_filter()
    assert hmi._recipe_filter_active is True
    hmi._refresh_result_tables_ui()
    rows = tables[0].rowCount()
    recipes_shown = []
    for r in range(rows):
        it = tables[0].item(r, 9)
        if it:
            recipes_shown.append(it.text())
    assert all('型号甲' in x for x in recipes_shown if x and x != '—'), recipes_shown
    assert not any('型号乙' in x for x in recipes_shown)
    ok(f'recipe filter shows only 型号甲 ({rows} rows): {recipes_shown}')

    tip = hmi._strip_recipe_lab.text()
    assert '筛选' in tip or '型号甲' in tip
    ok(f'strip recipe hint: {tip}')

    hmi._toggle_recipe_filter()
    assert hmi._recipe_filter_active is False
    ok('filter toggle off')

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
