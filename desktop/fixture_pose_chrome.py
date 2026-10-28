"""Fixture / pose_correct result chrome — soft OpenCV path (no Halcon / no robot SDK).

Industrial density for PoseCorrect live results: matrix table rows, axis vectors,
origin/axis canvas overlays. No Comm/HMI cobind; no spark micro-props.
"""
from __future__ import annotations

import math
from typing import Any


OPERATOR_TAG = '夹'
OPERATOR_LABEL = '夹具位姿'


def _as_list(v) -> list:
    return v if isinstance(v, list) else []


def _unwrap_bag(result: dict | None) -> dict:
    if not isinstance(result, dict):
        return {}
    bag = result
    for key in ('output', 'outputs'):
        inner = bag.get(key) if isinstance(bag.get(key), dict) else None
        if inner is None:
            continue
        if isinstance(inner.get('result'), dict) and _fixture_keys(inner['result']):
            return inner['result']
        if _fixture_keys(inner):
            return inner
    if isinstance(bag.get('result'), dict) and _fixture_keys(bag['result']):
        return bag['result']
    if _fixture_keys(bag):
        return bag
    return bag if isinstance(bag, dict) else {}


def _fixture_keys(d: dict) -> bool:
    return any(k in d for k in (
        'fixtureX', 'fixtureY', 'fixtureAngle', 'matrix', 'axisX', 'axisY', 'boundOk',
    ))


def chrome_badge(bound_ok=None, status=None) -> str:
    """Compact filmstrip/panel badge: 夹✓ / 夹✗ / 夹·."""
    if bound_ok is True or str(status or '').lower() == 'ok':
        if bound_ok is False:
            return f'{OPERATOR_TAG}✗'
        return f'{OPERATOR_TAG}✓'
    if bound_ok is False or str(status or '').lower() == 'unbound':
        return f'{OPERATOR_TAG}✗'
    return f'{OPERATOR_TAG}·'


def format_matrix_rows(matrix) -> list[dict]:
    """3 density rows for a row-major 3x3 similarity matrix."""
    m = _as_list(matrix)
    if len(m) < 9:
        m = list(m) + [0.0] * (9 - len(m))
    rows = []
    for r in range(3):
        a, b, c = m[r * 3], m[r * 3 + 1], m[r * 3 + 2]
        try:
            rows.append({
                'row': r,
                'c0': round(float(a), 6),
                'c1': round(float(b), 6),
                'c2': round(float(c), 6),
                'label': f'R{r}',
            })
        except (TypeError, ValueError):
            rows.append({'row': r, 'c0': a, 'c1': b, 'c2': c, 'label': f'R{r}'})
    return rows


def axis_vector_bits(axis_x=None, axis_y=None) -> dict:
    """Normalize axisX/axisY dicts into display bits."""
    def _xy(v):
        if isinstance(v, dict):
            return float(v.get('x') or 0), float(v.get('y') or 0)
        if isinstance(v, (list, tuple)) and len(v) >= 2:
            return float(v[0]), float(v[1])
        return None, None

    ax, ay = _xy(axis_x)
    bx, by = _xy(axis_y)
    out = {}
    if ax is not None:
        out['axisX'] = {'x': ax, 'y': ay}
        out['axisXText'] = f'X=({ax:.2f},{ay:.2f})'
    if bx is not None:
        out['axisY'] = {'x': bx, 'y': by}
        out['axisYText'] = f'Y=({bx:.2f},{by:.2f})'
    return out


def soft_fixture_matrix(x, y, angle_deg, scale=1.0) -> list:
    s = float(scale) if scale and math.isfinite(float(scale)) else 1.0
    rad = math.radians(float(angle_deg) or 0.0)
    c, sn = math.cos(rad) * s, math.sin(rad) * s
    return [
        c, -sn, float(x) or 0.0,
        sn, c, float(y) or 0.0,
        0.0, 0.0, 1.0,
    ]


def soft_demo_fixture_result(*, x=120.0, y=80.0, angle=25.0, scale=1.0,
                             axis_length=48.0, bound_ok=True) -> dict:
    """Design-time demo payload for PoseCorrect density table / overlays."""
    m = soft_fixture_matrix(x, y, angle, scale)
    rad = math.radians(angle)
    L = float(axis_length) or 40.0
    return {
        'fixtureSource': 'manual',
        'fixtureX': x,
        'fixtureY': y,
        'fixtureAngle': angle,
        'fixtureScale': scale,
        'matrix': m,
        'axisLength': L,
        'axisX': {'x': L * math.cos(rad), 'y': L * math.sin(rad)},
        'axisY': {'x': -L * math.sin(rad), 'y': L * math.cos(rad)},
        'boundOk': bool(bound_ok),
        'status': 'ok' if bound_ok else 'unbound',
        'outputCoord': 'fixture',
        'followRoi': True,
        'showAxes': True,
        'showOrigin': True,
        'showMatrix': True,
        'score': 0.94 if bound_ok else None,
        'note': '软演示夹具位姿（设计态）',
    }


def summarize_fixture_result(result: dict | None = None, params: dict | None = None) -> dict:
    bag = _unwrap_bag(result)
    params = params if isinstance(params, dict) else {}
    fx = bag.get('fixtureX')
    fy = bag.get('fixtureY')
    fa = bag.get('fixtureAngle')
    fs = bag.get('fixtureScale')
    bound = bag.get('boundOk')
    status = bag.get('status')
    chrome = chrome_badge(bound, status)
    axis = axis_vector_bits(bag.get('axisX'), bag.get('axisY'))
    rows = format_matrix_rows(bag.get('matrix')) if (
        bag.get('showMatrix', True) is not False and bag.get('matrix') is not None
    ) else []
    tip_bits = [chrome]
    if fx is not None and fy is not None:
        tip_bits.append(f'原点=({fx},{fy})')
    if fa is not None:
        tip_bits.append(f'θ={fa}°')
    if fs is not None:
        tip_bits.append(f's={fs}')
    if axis.get('axisXText'):
        tip_bits.append(axis['axisXText'])
    return {
        'chrome': chrome,
        'tag': OPERATOR_TAG,
        'label': OPERATOR_LABEL,
        'fixtureX': fx,
        'fixtureY': fy,
        'fixtureAngle': fa,
        'fixtureScale': fs,
        'boundOk': bound,
        'status': status,
        'matrixRows': rows,
        'axis': axis,
        'score': bag.get('score'),
        'summary': ' · '.join(str(b) for b in tip_bits[:8]),
        'showAxes': params.get('showAxes', bag.get('showAxes', True)) not in (False, 0, 'false'),
        'showOrigin': params.get('showOrigin', bag.get('showOrigin', True)) not in (False, 0, 'false'),
        'showMatrix': params.get('showMatrix', bag.get('showMatrix', True)) not in (False, 0, 'false'),
    }


def build_fixture_overlays(result: dict | None = None, params: dict | None = None,
                           *, max_specs: int = 24) -> list:
    """Canvas overlays: origin cross + X (green) / Y (cyan) axes + labels."""
    bag = _unwrap_bag(result)
    params = params if isinstance(params, dict) else {}
    try:
        ox = float(bag.get('fixtureX'))
        oy = float(bag.get('fixtureY'))
    except (TypeError, ValueError):
        return []
    show_axes = params.get('showAxes', bag.get('showAxes', True)) not in (False, 0, 'false')
    show_origin = params.get('showOrigin', bag.get('showOrigin', True)) not in (False, 0, 'false')
    show_matrix = params.get('showMatrix', bag.get('showMatrix', True)) not in (False, 0, 'false')
    bound = bag.get('boundOk')
    origin_color = '#00d250' if bound is not False else '#ff5252'
    specs: list[dict[str, Any]] = []

    axis = axis_vector_bits(bag.get('axisX'), bag.get('axisY'))
    ax = axis.get('axisX') or {}
    ay = axis.get('axisY') or {}
    if show_axes and ax:
        specs.append({
            'type': 'line',
            'x1': ox, 'y1': oy,
            'x2': ox + float(ax.get('x') or 0), 'y2': oy + float(ax.get('y') or 0),
            'color': '#00d250', 'width': 2.2,
        })
        specs.append({
            'type': 'label',
            'x': ox + float(ax.get('x') or 0) + 4,
            'y': oy + float(ax.get('y') or 0) - 4,
            'text': 'X', 'color': '#00d250',
        })
    if show_axes and ay:
        specs.append({
            'type': 'line',
            'x1': ox, 'y1': oy,
            'x2': ox + float(ay.get('x') or 0), 'y2': oy + float(ay.get('y') or 0),
            'color': '#00bcd4', 'width': 2.2,
        })
        specs.append({
            'type': 'label',
            'x': ox + float(ay.get('x') or 0) + 4,
            'y': oy + float(ay.get('y') or 0) - 4,
            'text': 'Y', 'color': '#00bcd4',
        })
    if show_origin:
        specs.append({
            'type': 'cross', 'x': ox, 'y': oy,
            'size': 12, 'color': origin_color, 'width': 1.8,
        })
        specs.append({
            'type': 'point', 'x': ox, 'y': oy, 'color': origin_color,
        })
    if show_matrix and bag.get('matrix') is not None:
        try:
            ang = float(bag.get('fixtureAngle') or 0)
            sc = float(bag.get('fixtureScale') or 1)
            specs.append({
                'type': 'label',
                'x': ox + 10, 'y': oy + 18,
                'text': f'夹 θ={ang:.1f}° s={sc:.2f}',
                'color': '#ffb400',
            })
        except (TypeError, ValueError):
            pass
    return specs[:max_specs]


def density_pose_rows(result: dict | None = None) -> list[dict]:
    """Flat key/value density rows for PoseCorrect result table."""
    bag = _unwrap_bag(result)
    keys = (
        'status', 'boundOk', 'fixtureSource', 'fixtureX', 'fixtureY',
        'fixtureAngle', 'fixtureScale', 'outputCoord', 'followRoi',
        'boundFrom', 'bindStepId', 'bindField', 'score', 'axisLength', 'note',
    )
    rows = []
    for k in keys:
        if k in bag and bag[k] is not None:
            rows.append({'key': k, 'value': bag[k]})
    axis = axis_vector_bits(bag.get('axisX'), bag.get('axisY'))
    if axis.get('axisXText'):
        rows.append({'key': 'axisX', 'value': axis['axisXText']})
    if axis.get('axisYText'):
        rows.append({'key': 'axisY', 'value': axis['axisYText']})
    return rows


def chrome_map_from_film_cache(film_cache: dict | None, project_steps=None) -> dict:
    """path → chrome badge for pose_correct frames."""
    out = {}
    steps = {str(s.get('id') or ''): s for s in (project_steps or []) if isinstance(s, dict)}
    if not isinstance(film_cache, dict):
        return out
    for path, bag in film_cache.items():
        if not isinstance(bag, dict):
            continue
        records = bag.get('results') or []
        badge = ''
        for rec in records if isinstance(records, list) else []:
            if not isinstance(rec, dict):
                continue
            sid = str(rec.get('id') or '')
            step = steps.get(sid) or {}
            op = step.get('operation') or rec.get('operation') or ''
            if op != 'pose_correct' and not _fixture_keys(_unwrap_bag(rec)):
                continue
            summ = summarize_fixture_result(rec, step.get('params') if isinstance(step.get('params'), dict) else {})
            badge = summ.get('chrome') or ''
            if badge:
                break
        if badge:
            out[path] = badge
    return out
