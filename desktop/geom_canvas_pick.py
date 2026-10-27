"""Canvas click-to-bind helpers for measure_geom (lines / points).

Collect pickable geometry from last_result, hit-test clicks, return bind
targets {stepId, field, kind, ...}. No Halcon.
"""
from __future__ import annotations

import math
from typing import Any


def _result_payload(record: dict) -> dict:
    out = record.get('output') or {}
    if isinstance(out, dict):
        r = out.get('result')
        if isinstance(r, dict):
            return r
        return out if any(k in out for k in ('lines', 'matches', 'circles', 'items')) else {}
    return {}


def _line_xy(item: dict):
    if not isinstance(item, dict):
        return None
    if 'start' in item and 'end' in item:
        s, e = item['start'], item['end']
        if isinstance(s, (list, tuple)) and isinstance(e, (list, tuple)) and len(s) >= 2 and len(e) >= 2:
            return float(s[0]), float(s[1]), float(e[0]), float(e[1])
    for a, b, c, d in (('x1', 'y1', 'x2', 'y2'), ('X1', 'Y1', 'X2', 'Y2')):
        if a in item and c in item:
            return float(item[a]), float(item[b]), float(item[c]), float(item[d])
    return None


def _point_xy(item: dict):
    if not isinstance(item, dict):
        return None
    if 'center' in item and isinstance(item['center'], (list, tuple)) and len(item['center']) >= 2:
        return float(item['center'][0]), float(item['center'][1])
    if 'centerPixels' in item and isinstance(item['centerPixels'], (list, tuple)):
        c = item['centerPixels']
        return float(c[0]), float(c[1])
    for xk, yk in (('x', 'y'), ('X', 'Y'), ('matchX', 'matchY'), ('intersectX', 'intersectY'),
                   ('footX', 'footY'), ('px', 'py')):
        if xk in item and yk in item:
            try:
                return float(item[xk]), float(item[yk])
            except (TypeError, ValueError):
                pass
    if 'bbox' in item and isinstance(item['bbox'], (list, tuple)) and len(item['bbox']) >= 4:
        x, y, w, h = item['bbox'][:4]
        return float(x) + float(w) / 2, float(y) + float(h) / 2
    return None


def _walk_inner_steps(project: dict | None) -> dict:
    """id → step, including nested group inner.steps (flattened)."""
    out = {}

    def walk(steps, prefix=''):
        for s in steps or []:
            if not isinstance(s, dict):
                continue
            sid = s.get('id')
            if sid:
                out[sid] = s
                if prefix:
                    out[f'{prefix}/{sid}'] = s
            if (s.get('operation') or '') == 'group':
                inner = (s.get('params') or {}).get('inner') or {}
                walk(inner.get('steps') or [], prefix=sid or prefix)

    walk((project or {}).get('steps') or [])
    return out


def _synthetic_records_from_group_trace(rec: dict, group_step: dict | None = None) -> list[dict]:
    """Expand a group/subflow record's result.trace into child-like records for picking."""
    out = []
    payload = _result_payload(rec)
    if not isinstance(payload, dict):
        return out
    gname = rec.get('name') or (group_step or {}).get('name') or rec.get('id') or '组合'
    gid = rec.get('id') or ''
    trace = payload.get('trace')
    if isinstance(trace, list):
        # keep last iteration per nodeId
        latest = {}
        for row in trace:
            if not isinstance(row, dict):
                continue
            nid = row.get('nodeId') or row.get('id')
            if not nid:
                continue
            latest[nid] = row
        for nid, row in latest.items():
            child_result = row.get('result') if isinstance(row.get('result'), dict) else {}
            # skip empty
            if not child_result:
                continue
            out.append({
                'id': nid,
                'name': f"{gname}/{row.get('operation') or nid}",
                'operation': row.get('operation') or '',
                'output': {'result': child_result},
                '_groupParent': gid,
                '_nested': True,
            })
    # also expose final value if it itself has lines/matches
    value = payload.get('value')
    if isinstance(value, dict) and any(k in value for k in ('lines', 'matches', 'circles', 'items',
                                                            'intersectX', 'footX')):
        out.append({
            'id': gid or 'group_value',
            'name': f'{gname}/输出',
            'operation': (group_step or {}).get('operation') or 'group',
            'output': {'result': value},
            '_groupParent': gid,
            '_nested': True,
        })
    return out


def flatten_result_records(last_result: dict | None, project: dict | None = None,
                           *, include_nested: bool = True) -> list[dict]:
    """Top-level results + optional nested group/subflow trace children."""
    records = list((last_result or {}).get('results') or [])
    if not include_nested:
        return records
    steps = _walk_inner_steps(project)
    extra = []
    for rec in records:
        if not isinstance(rec, dict):
            continue
        sid = rec.get('id')
        step = steps.get(sid) or {}
        op = step.get('operation') or rec.get('operation') or ''
        payload = _result_payload(rec)
        # detect group/subflow by op or by trace presence
        if op in ('group', 'subflow', 'loop') or (isinstance(payload, dict) and payload.get('trace')):
            extra.extend(_synthetic_records_from_group_trace(rec, step))
    return records + extra


def merge_last_results(*sources: dict | None) -> dict:
    """Merge multiple last_result dicts (filmstrip multi-source) into one pick bag.

    Later sources append records; ids get `#srcN` suffix on collision with different payload.
    """
    merged = {'results': []}
    seen = set()
    for si, src in enumerate(sources):
        if not isinstance(src, dict):
            continue
        for rec in (src.get('results') or []):
            if not isinstance(rec, dict):
                continue
            rid = rec.get('id') or f'r{len(merged["results"])}'
            key = (rid, id(rec))
            # allow same step from different filmstrip frames: tag source
            tag = src.get('_filmPath') or src.get('_sourceTag') or ''
            out = dict(rec)
            if tag:
                out = {**out, 'name': f"{out.get('name') or rid} · {Path_name(tag)}",
                       '_filmPath': tag}
            # dedupe exact same object id only
            oid = (rid, tag, str(out.get('name')))
            if oid in seen:
                continue
            seen.add(oid)
            merged['results'].append(out)
        # keep variables from last non-empty
        if src.get('variables') and not merged.get('variables'):
            merged['variables'] = src.get('variables')
    return merged


def Path_name(tag: str) -> str:
    try:
        from pathlib import Path as _P
        return _P(str(tag)).name
    except Exception:
        return str(tag)[-24:]


def collect_pickables(last_result: dict | None, project: dict | None = None,
                      kind: str = 'line', *, include_nested: bool = True,
                      extra_results: list | None = None) -> list[dict[str, Any]]:
    """Build pickable features from engine last_result (+ nested group / extras).

    kind: 'line' | 'point' | 'any'
    include_nested: expand group/subflow result.trace into child pickables
    extra_results: additional last_result dicts (e.g. filmstrip path caches)
    """
    kind = (kind or 'line').lower()
    if extra_results:
        bag = merge_last_results(last_result, *[e for e in extra_results if e])
    else:
        bag = last_result or {}
    records = flatten_result_records(bag, project, include_nested=include_nested)
    steps = _walk_inner_steps(project)
    out: list[dict[str, Any]] = []

    for rec in records:
        if not isinstance(rec, dict):
            continue
        sid = rec.get('id')
        if not sid:
            continue
        step = steps.get(sid) or {}
        name = rec.get('name') or step.get('name') or sid
        op = step.get('operation') or rec.get('operation') or ''
        payload = _result_payload(rec)
        nested = bool(rec.get('_nested'))
        film = rec.get('_filmPath') or ''

        def _emit(d, _nested=nested, _film=film):
            if _nested:
                d['_nested'] = True
            if _film:
                d['_filmPath'] = _film
                try:
                    from pathlib import Path as _P
                    leaf = _P(str(_film)).name
                except Exception:
                    leaf = str(_film)[-24:]
                if leaf and leaf not in str(d.get('label') or ''):
                    d['label'] = f"{d.get('label')} · {leaf}"
            out.append(d)

        # lines alias / items for geometry
        if kind in ('line', 'any'):
            lines = payload.get('lines')
            if not isinstance(lines, list):
                if payload.get('feature') in ('lines', 'edges') and isinstance(payload.get('items'), list):
                    lines = payload['items']
                else:
                    lines = []
            for i, item in enumerate(lines):
                xy = _line_xy(item) if isinstance(item, dict) else None
                if not xy:
                    continue
                x1, y1, x2, y2 = xy
                _emit({
                    'kind': 'line',
                    'stepId': sid,
                    'stepName': name,
                    'operation': op,
                    'field': f'lines[{i}]',
                    'index': i,
                    'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2,
                    'label': f'{name} · lines[{i}]',
                })

        if kind in ('point', 'any'):
            # matches (locate)
            matches = payload.get('matches')
            if not isinstance(matches, list):
                matches = []
            for i, item in enumerate(matches):
                xy = _point_xy(item) if isinstance(item, dict) else None
                if not xy:
                    continue
                _emit({
                    'kind': 'point', 'stepId': sid, 'stepName': name, 'operation': op,
                    'field': f'matches[{i}]', 'index': i,
                    'x': xy[0], 'y': xy[1],
                    'label': f'{name} · matches[{i}]',
                })
            circles = payload.get('circles')
            if not isinstance(circles, list):
                if payload.get('feature') == 'circles' and isinstance(payload.get('items'), list):
                    circles = payload['items']
                else:
                    circles = []
            for i, item in enumerate(circles):
                xy = _point_xy(item) if isinstance(item, dict) else None
                if not xy:
                    continue
                _emit({
                    'kind': 'point', 'stepId': sid, 'stepName': name, 'operation': op,
                    'field': f'circles[{i}]', 'index': i,
                    'x': xy[0], 'y': xy[1],
                    'label': f'{name} · circles[{i}]',
                })
            # measure_geom result points
            for field, xk, yk in (
                ('intersect', 'intersectX', 'intersectY'),
                ('foot', 'footX', 'footY'),
            ):
                if xk in payload and yk in payload:
                    try:
                        _emit({
                            'kind': 'point', 'stepId': sid, 'stepName': name, 'operation': op,
                            'field': field, 'index': 0,
                            'x': float(payload[xk]), 'y': float(payload[yk]),
                            'label': f'{name} · {field}',
                        })
                    except (TypeError, ValueError):
                        pass

    return out


