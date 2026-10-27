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


def collect_pickables(last_result: dict | None, project: dict | None = None,
                      kind: str = 'line') -> list[dict[str, Any]]:
    """Build pickable features from engine last_result records.

    kind: 'line' | 'point' | 'any'
    """
    kind = (kind or 'line').lower()
    records = (last_result or {}).get('results') or []
    steps = {s.get('id'): s for s in ((project or {}).get('steps') or []) if isinstance(s, dict)}
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
                out.append({
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
                out.append({
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
                out.append({
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
                        out.append({
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
