#!/usr/bin/env python3
"""细妆⑮：measure_geom 绑定 — 组合内层 trace + 胶片多源 last_result."""
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
    from desktop.geom_canvas_pick import (
        collect_pickables, flatten_result_records, merge_last_results,
    )

    fake = {'results': [{
        'id': 'g1', 'name': '组合1', 'operation': 'group',
        'output': {'result': {
            'status': 'ok',
            'trace': [
                {'nodeId': 'c1', 'operation': 'geometry', 'result': {
                    'lines': [{'x1': 0, 'y1': 0, 'x2': 10, 'y2': 0}]}},
                {'nodeId': 'c2', 'operation': 'locate', 'result': {
                    'matches': [{'x': 5, 'y': 5}]}},
            ],
            'value': {'intersectX': 1, 'intersectY': 2},
        }},
    }]}
    proj = {'steps': [{'id': 'g1', 'name': '组合1', 'operation': 'group',
                       'params': {'inner': {'steps': [
                           {'id': 'c1', 'name': '找线', 'operation': 'geometry'},
                           {'id': 'c2', 'name': '定位', 'operation': 'locate'},
                       ]}}}]}
    recs = flatten_result_records(fake, proj)
    assert any(r.get('id') == 'c1' for r in recs), recs
    ok(f'flatten nested trace → {len(recs)} records')

    pk = collect_pickables(fake, proj, kind='any', include_nested=True)
    assert any(p.get('_nested') for p in pk), pk
    assert any(p.get('field') == 'lines[0]' for p in pk)
    assert any(p.get('field') == 'matches[0]' for p in pk)
    ok(f'nested pickables={len(pk)} fields={[p.get("field") for p in pk]}')

    flat = collect_pickables(fake, proj, kind='any', include_nested=False)
    assert not any(p.get('_nested') for p in flat)
    ok(f'include_nested=False → {len(flat)} (no child tags)')

    a = {'results': [{'id': 'c1', 'name': '找线', 'operation': 'geometry',
                      'output': {'result': {'lines': [{'x1': 0, 'y1': 0, 'x2': 1, 'y2': 0}]}}}],
         '_filmPath': '/tmp/a.png'}
    b = {'results': [{'id': 'c1', 'name': '找线', 'operation': 'geometry',
                      'output': {'result': {'lines': [{'x1': 2, 'y1': 2, 'x2': 3, 'y2': 3}]}}}],
         '_filmPath': '/tmp/b.png'}
    merged = merge_last_results(a, b)
    assert len(merged['results']) >= 2
    ok(f'merge_last_results n={len(merged["results"])}')

    pk2 = collect_pickables(None, {'steps': [
        {'id': 'c1', 'name': '找线', 'operation': 'geometry'}]},
        kind='line', extra_results=[a, b])
    assert len(pk2) >= 2
    assert all(p.get('_filmPath') for p in pk2)
    ok(f'multi-source filmstrip pickables={len(pk2)}')

    mw = (ROOT / 'desktop/mainwindow.py').read_text(encoding='utf-8')
    for n in ('_filmstrip_results', 'extra_results', 'include_nested'):
        (ok if n in mw else bad)(f'mainwindow has {n}' if n in mw else f'missing {n}')

    print(f"\n{'FAIL' if fail_n else 'PASS'} {pass_n} ok / {fail_n} fail")
    return 1 if fail_n else 0

if __name__ == '__main__':
    sys.exit(main())
