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

def _dist_point_to_segment(px, py, x1, y1, x2, y2) -> float:
    dx, dy = x2 - x1, y2 - y1
    len2 = dx * dx + dy * dy
    if len2 < 1e-9:
        return math.hypot(px - x1, py - y1)
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / len2))
    qx, qy = x1 + t * dx, y1 + t * dy
    return math.hypot(px - qx, py - qy)


def hit_test(pickables: list[dict], x: float, y: float, kind: str = 'line',
             tol: float = 14.0) -> dict | None:
    """Nearest pickable within tol (pixels). Prefer kind match."""
    kind = (kind or 'any').lower()
    best = None
    best_d = tol
    for p in pickables or []:
        if kind not in ('any',) and p.get('kind') != kind:
            continue
        if p.get('kind') == 'line':
            d = _dist_point_to_segment(x, y, p['x1'], p['y1'], p['x2'], p['y2'])
        else:
            d = math.hypot(x - float(p.get('x', 0)), y - float(p.get('y', 0)))
        if d <= best_d:
            best_d = d
            best = dict(p)
            best['hitDist'] = d
    return best


def overlay_specs_for_pickables(pickables: list[dict], highlight_id: str | None = None) -> list[dict]:
    """Orange dashed-style preview specs for ImageView.set_geom_overlays."""
    specs = []
    for p in pickables or []:
        hot = highlight_id and p.get('field') == highlight_id and False  # reserved
        color = '#e87722' if p.get('kind') == 'line' else '#ffcc66'
        if p.get('kind') == 'line':
            specs.append(dict(type='line', x1=p['x1'], y1=p['y1'], x2=p['x2'], y2=p['y2'], color=color))
            mx = (p['x1'] + p['x2']) / 2
            my = (p['y1'] + p['y2']) / 2
            specs.append(dict(type='label', x=mx + 4, y=my - 4, text=p.get('field') or '', color=color))
        else:
            specs.append(dict(type='point', x=p['x'], y=p['y'], r=6, color=color))
            specs.append(dict(type='label', x=float(p['x']) + 6, y=float(p['y']) - 8,
                              text=p.get('field') or '', color=color))
    return specs


def overlay_specs_for_multiframe(frames: list[dict], *,
                                 highlight_path: str | None = None) -> list[dict]:
    """Build colored overlay specs for multi-frame compare.

    frames: [{path, pickables, label?}, ...]
    Current / highlight frame uses accent; others use muted cycling colors.
    """
    COLORS = [
        '#e87722',  # accent current
        '#6eb6ff',
        '#3ecf8e',
        '#c9a0ff',
        '#e35d6a',
        '#f0c674',
    ]
    out = []
    for i, fr in enumerate(frames or []):
        if not isinstance(fr, dict):
            continue
        path = fr.get('path') or fr.get('_filmPath') or ''
        pks = fr.get('pickables') or []
        label = fr.get('label') or ''
        try:
            from pathlib import Path as _P
            leaf = _P(str(path)).name if path else (label or f'#{i}')
        except Exception:
            leaf = str(path)[-24:] if path else (label or f'#{i}')
        is_hi = bool(highlight_path) and path and str(path) == str(highlight_path)
        color = COLORS[0] if (is_hi or (not highlight_path and i == 0)) else COLORS[(i % (len(COLORS) - 1)) + 1]
        width = 2.5 if is_hi or i == 0 else 1.5
        for spec in overlay_specs_for_pickables(pks):
            s = dict(spec)
            s['color'] = color
            s['width'] = width
            s['frame'] = leaf
            s['framePath'] = path
            s['_compare'] = True
            # tag text (ImageView reads 'text')
            lab = s.get('text') or s.get('label') or ''
            if leaf and leaf not in str(lab):
                s['text'] = f'{lab} · {leaf}' if lab else leaf
            out.append(s)
    return out


def pickables_from_cached_result(result: dict | None, project: dict | None = None,
                                 kind: str = 'any') -> list[dict]:
    """Convenience: collect pickables from one filmstrip-cached last_result."""
    if not isinstance(result, dict):
        return []
    return collect_pickables(result, project, kind=kind, include_nested=True)


def summarize_pickables(pickables: list[dict], limit: int = 6) -> str:
    """Short Chinese tip for hover tooltip."""
    if not pickables:
        return '无几何缓存'
    lines = sum(1 for p in pickables if p.get('kind') == 'line')
    pts = sum(1 for p in pickables if p.get('kind') == 'point')
    bits = []
    if lines:
        bits.append(f'线 {lines}')
    if pts:
        bits.append(f'点 {pts}')
    head = ' · '.join(bits) or f'{len(pickables)} 项'
    samples = []
    for p in pickables[:limit]:
        samples.append(str(p.get('label') or p.get('field') or p.get('stepId') or '?'))
    more = f' …+{len(pickables) - limit}' if len(pickables) > limit else ''
    return f'{head}：' + '；'.join(samples) + more
