"""Measure / caliper denser live result chrome — soft OpenCV path (no Halcon).

Industrial density for measure_geom + caliper-line results: judge/tolerance bands,
metric tables, canvas overlays with OK/NG coloring. No Comm/HMI cobind; no spark.
"""
from __future__ import annotations

from typing import Any


MEASURE_OPS = (
    'line_intersect', 'point_distance', 'point_line_distance',
    'line_angle', 'point_circle_distance', 'circle_circle_distance',
)

OPERATOR_TAGS = {
    'line_intersect': '交',
    'point_distance': '距',
    'point_line_distance': '垂',
    'line_angle': '角',
    'point_circle_distance': '点圆',
    'circle_circle_distance': '圆隙',
    'caliper': '尺',
    'geometry': '尺',
}

OPERATOR_LABELS = {
    'line_intersect': '直线交点',
    'point_distance': '点距',
    'point_line_distance': '点线垂距',
    'line_angle': '夹角',
    'point_circle_distance': '点圆距',
    'circle_circle_distance': '圆圆间隙',
    'caliper': '多卡尺直线',
    'geometry': '几何/卡尺',
}


def _as_list(v) -> list:
    return v if isinstance(v, list) else []


def _measure_keys(d: dict) -> bool:
    return any(k in d for k in (
        'distance', 'angleDeg', 'intersectX', 'intersectY', 'gap',
        'judgeOk', 'judgeStatus', 'footX', 'centerDist', 'parallel',
    ))


def _caliper_keys(d: dict) -> bool:
    if d.get('method') == 'caliper':
        return True
    if d.get('feature') == 'lines' and isinstance(d.get('items'), list):
        items = d['items']
        if items and isinstance(items[0], dict) and items[0].get('method') == 'caliper':
            return True
        if 'caliperCount' in d or 'judgeMin' in d:
            return True
    return False


def _unwrap_bag(result: dict | None) -> dict:
    if not isinstance(result, dict):
        return {}
    bag = result
    for key in ('output', 'outputs'):
        inner = bag.get(key) if isinstance(bag.get(key), dict) else None
        if inner is None:
            continue
        if isinstance(inner.get('result'), dict) and (
            _measure_keys(inner['result']) or _caliper_keys(inner['result'])
        ):
            return inner['result']
        if _measure_keys(inner) or _caliper_keys(inner):
            return inner
    if isinstance(bag.get('result'), dict) and (
        _measure_keys(bag['result']) or _caliper_keys(bag['result'])
    ):
        return bag['result']
    if _measure_keys(bag) or _caliper_keys(bag):
        return bag
    return bag if isinstance(bag, dict) else {}


def detect_operator(result: dict | None = None, params: dict | None = None,
                    operation: str | None = None) -> str:
    op = str(operation or (params or {}).get('operation') or '').lower()
    if op in OPERATOR_TAGS:
        return op if op != 'geometry' else 'caliper'
    bag = _unwrap_bag(result)
    if _caliper_keys(bag) or bag.get('feature') == 'lines':
        return 'caliper'
    for k in MEASURE_OPS:
        # heuristic: presence of distinctive fields
        pass
    if bag.get('intersectX') is not None:
        return 'line_intersect'
    if bag.get('angleDeg') is not None and bag.get('x3') is not None:
        return 'line_angle'
    if bag.get('footX') is not None:
        return 'point_line_distance'
    if bag.get('gap') is not None or (
        bag.get('cx') is not None and bag.get('cx2') is not None
    ):
        return 'circle_circle_distance'
    if bag.get('cx') is not None and bag.get('px') is not None:
        return 'point_circle_distance'
    if bag.get('distance') is not None and bag.get('x1') is not None:
        return 'point_distance'
    return op or 'point_distance'


def operator_tag(op: str | None) -> str:
    return OPERATOR_TAGS.get(str(op or '').lower(), '测')


def chrome_badge(judge_ok=None, status=None, *, op: str | None = None,
                 count: int | None = None) -> str:
    """Compact badge: 距✓ / 尺3✗ / 交·."""
    tag = operator_tag(op)
    mark = ''
    if judge_ok is True or str(status or '').upper() in ('OK', 'PASS'):
        mark = '✓'
    elif judge_ok is False or str(status or '').upper() in ('NG', 'FAIL'):
        mark = '✗'
    else:
        mark = '·'
    if count is not None and int(count) >= 0 and str(op or '') in ('caliper', 'geometry'):
        return f'{tag}{int(count)}{mark}'
    return f'{tag}{mark}'


def tolerance_band(value, jmin, jmax) -> dict:
    """Describe where a metric sits vs [jmin,jmax]."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return {'inBand': None, 'deltaLow': None, 'deltaHigh': None, 'span': None, 'ratio': None}
    try:
        lo = float(jmin) if jmin is not None else None
    except (TypeError, ValueError):
        lo = None
    try:
        hi = float(jmax) if jmax is not None else None
    except (TypeError, ValueError):
        hi = None
    in_band = None
    if lo is not None and hi is not None:
        in_band = lo <= v <= hi
    elif lo is not None:
        in_band = v >= lo
    elif hi is not None:
        in_band = v <= hi
    span = None
    ratio = None
    if lo is not None and hi is not None and hi > lo:
        span = hi - lo
        ratio = (v - lo) / span
    return {
        'inBand': in_band,
        'deltaLow': (v - lo) if lo is not None else None,
        'deltaHigh': (hi - v) if hi is not None else None,
        'span': span,
        'ratio': ratio,
        'value': v,
        'judgeMin': lo,
        'judgeMax': hi,
    }


def primary_metric(bag: dict, op: str | None = None) -> tuple[str, Any]:
    op = detect_operator(bag, operation=op)
    if op == 'line_intersect':
        if bag.get('intersectX') is not None:
            return 'intersect', (bag.get('intersectX'), bag.get('intersectY'))
        return 'status', bag.get('status')
    if op == 'line_angle':
        return 'angleDeg', bag.get('angleDeg')
    if op in ('point_distance', 'point_line_distance', 'point_circle_distance',
              'circle_circle_distance'):
        if bag.get('distance') is not None:
            return 'distance', bag.get('distance')
        if bag.get('gap') is not None:
            return 'gap', bag.get('gap')
    if op == 'caliper':
        items = _as_list(bag.get('items'))
        return 'count', len(items) if items else bag.get('count')
    for k in ('distance', 'angleDeg', 'gap', 'count'):
        if bag.get(k) is not None:
            return k, bag.get(k)
    return 'status', bag.get('status')


def format_metric(label: str, value) -> str:
    if value is None:
        return '—'
    if label == 'intersect' and isinstance(value, (list, tuple)) and len(value) >= 2:
        try:
            return f'({float(value[0]):.2f},{float(value[1]):.2f})'
        except (TypeError, ValueError):
            return str(value)
    try:
        if isinstance(value, bool):
            return '是' if value else '否'
        if isinstance(value, float):
            return f'{value:.4g}'
        if isinstance(value, int):
            return str(value)
    except Exception:
        pass
    return str(value)


def density_measure_rows(result: dict | None = None, params: dict | None = None,
                         *, op: str | None = None) -> list[dict]:
    """Key/value density rows for MeasureGeom live table."""
    bag = _unwrap_bag(result)
    params = params if isinstance(params, dict) else {}
    op = detect_operator(bag, params, op)
    keys = (
        'status', 'judgeOk', 'judgeStatus', 'judgeEnable',
        'distance', 'angleDeg', 'gap', 'dx', 'dy',
        'intersectX', 'intersectY', 'footX', 'footY',
        'centerDist', 'signed', 'inside', 'overlapping',
        'parallel', 'perpendicular', 'unit', 'scale',
        'px', 'py', 'cx', 'cy', 'cx2', 'cy2', 'r', 'r2',
        'judgeMin', 'judgeMax', 'note',
    )
    rows = []
    for k in keys:
        if k in bag and bag[k] is not None:
            rows.append({'key': k, 'value': bag[k], 'label': k})
    # tolerance band summary
    metric_lab, metric_val = primary_metric(bag, op)
    jmin = bag.get('judgeMin', params.get('judgeMin'))
    jmax = bag.get('judgeMax', params.get('judgeMax'))
    if params.get('judgeEnable') or bag.get('judgeEnable'):
        if metric_lab in ('distance', 'angleDeg', 'gap') and metric_val is not None:
            band = tolerance_band(metric_val, jmin, jmax)
            rows.append({
                'key': 'tolerance',
                'value': (
                    f'[{band.get("judgeMin")}, {band.get("judgeMax")}] · '
                    f'inBand={band.get("inBand")} · ratio='
                    f'{None if band.get("ratio") is None else round(band["ratio"], 3)}'
                ),
                'label': 'tolerance',
                'band': band,
            })
    return rows


def build_measure_table_rows(result: dict | None = None, params: dict | None = None,
                             *, op: str | None = None) -> list[dict]:
    """Single-row industrial table for one measure_geom result (or multi for caliper items)."""
    bag = _unwrap_bag(result)
    params = params if isinstance(params, dict) else {}
    op = detect_operator(bag, params, op)
    if op == 'caliper' or _caliper_keys(bag):
        return build_caliper_item_rows(bag, params)

    metric_lab, metric_val = primary_metric(bag, op)
    judge = bag.get('judgeOk')
    status = bag.get('judgeStatus') or (
        'OK' if judge is True else ('NG' if judge is False else '—')
    )
    jmin = bag.get('judgeMin', params.get('judgeMin'))
    jmax = bag.get('judgeMax', params.get('judgeMax'))
    band = tolerance_band(metric_val, jmin, jmax) if metric_lab in (
        'distance', 'angleDeg', 'gap'
    ) else {}
    unit = str(bag.get('unit') or params.get('unit') or 'px')
    return [{
        'index': 1,
        'op': op,
        'opLabel': OPERATOR_LABELS.get(op, op),
        'metricLabel': metric_lab,
        'metric': metric_val,
        'metricText': format_metric(metric_lab, metric_val),
        'unit': unit,
        'judgeOk': judge if judge is None else bool(judge),
        'judgeStatus': status,
        'judgeMin': jmin,
        'judgeMax': jmax,
        'inBand': band.get('inBand'),
        'bandRatio': band.get('ratio'),
        'chrome': chrome_badge(judge, status, op=op),
        'raw': bag,
    }]


def build_caliper_item_rows(result: dict | None = None, params: dict | None = None,
                            *, max_rows: int = 64) -> list[dict]:
    bag = _unwrap_bag(result)
    params = params if isinstance(params, dict) else {}
    items = _as_list(bag.get('items'))
    jmin = bag.get('judgeMin', params.get('judgeMin'))
    jmax = bag.get('judgeMax', params.get('judgeMax'))
    rows = []
    for i, it in enumerate(items[: max(1, int(max_rows))]):
        if not isinstance(it, dict):
            continue
        metric = it.get('lengthPixels')
        if metric is None:
            metric = it.get('score')
        judge = it.get('judgeOk')
        status = it.get('judgeStatus') or (
            'OK' if judge is True else ('NG' if judge is False else '—')
        )
        band = tolerance_band(metric, jmin, jmax) if metric is not None else {}
        rows.append({
            'index': int(it.get('index') or it.get('lineIndex') or (i + 1)),
            'op': 'caliper',
            'opLabel': '卡尺线',
            'metricLabel': 'length' if it.get('lengthPixels') is not None else 'score',
            'metric': metric,
            'metricText': format_metric('length', metric),
            'unit': 'px',
            'score': it.get('score'),
            'rms': it.get('rms') or it.get('rmsPixels'),
            'angleDeg': it.get('angleDeg') or it.get('angle'),
            'judgeOk': judge if judge is None else bool(judge),
            'judgeStatus': status,
            'judgeMin': jmin,
            'judgeMax': jmax,
            'inBand': band.get('inBand'),
            'bandRatio': band.get('ratio'),
            'chrome': chrome_badge(judge, status, op='caliper'),
            'raw': it,
        })
    return rows


def summarize_measure_result(result: dict | None = None, params: dict | None = None,
                             *, op: str | None = None) -> dict:
    bag = _unwrap_bag(result)
    params = params if isinstance(params, dict) else {}
    op = detect_operator(bag, params, op)
    rows = build_measure_table_rows(bag, params, op=op)
    ok_n = sum(1 for r in rows if r.get('judgeOk') is True)
    ng_n = sum(1 for r in rows if r.get('judgeOk') is False)
    judge = bag.get('judgeOk')
    if judge is None:
        if ng_n:
            judge = False
        elif ok_n and ok_n == len(rows) and rows:
            judge = True
    status = bag.get('judgeStatus') or (
        'OK' if judge is True else ('NG' if judge is False else None)
    )
    count = len(rows) if op == 'caliper' else (bag.get('count') if bag.get('count') is not None else len(rows))
    chrome = chrome_badge(judge, status, op=op, count=count if op == 'caliper' else None)
    metric_lab, metric_val = primary_metric(bag, op)
    label = OPERATOR_LABELS.get(op, op)
    tip = [chrome, label]
    if metric_val is not None and metric_lab != 'count':
        tip.append(f'{metric_lab}={format_metric(metric_lab, metric_val)}')
    if op == 'caliper':
        tip.append(f'n={count}')
    jmin = bag.get('judgeMin', params.get('judgeMin'))
    jmax = bag.get('judgeMax', params.get('judgeMax'))
    if params.get('judgeEnable') or bag.get('judgeEnable'):
        tip.append(f'T=[{jmin},{jmax}]')
    if judge is True:
        tip.append('OK')
    elif judge is False:
        tip.append(f'NG({ng_n})' if ng_n else 'NG')
    return {
        'op': op,
        'tag': operator_tag(op),
        'label': label,
        'chrome': chrome,
        'count': count,
        'okCount': ok_n,
        'ngCount': ng_n,
        'judgeOk': judge,
        'judgeStatus': status,
        'metricLabel': metric_lab,
        'metric': metric_val,
        'judgeMin': jmin,
        'judgeMax': jmax,
        'unit': bag.get('unit') or params.get('unit') or 'px',
        'summary': ' · '.join(str(t) for t in tip[:8]),
        'rows': rows,
        'densityRows': density_measure_rows(bag, params, op=op),
    }


def judge_color(judge_ok=None) -> str:
    if judge_ok is True:
        return '#00d250'
    if judge_ok is False:
        return '#ff5252'
    return '#ffb400'


def build_measure_overlays(result: dict | None = None, params: dict | None = None,
                           *, op: str | None = None, max_specs: int = 48) -> list:
    """Canvas overlays with OK/NG coloring + tolerance label for measure_geom."""
    bag = _unwrap_bag(result)
    params = params if isinstance(params, dict) else {}
    if params.get('showOverlay') in (False, 0, 'false', 'False'):
        return []
    op = detect_operator(bag, params, op)
    if op == 'caliper' or _caliper_keys(bag):
        return build_caliper_overlays(bag, params, max_specs=max_specs)

    show_pts = params.get('showPoints', True) not in (False, 0, 'false')
    show_lines = params.get('showLines', True) not in (False, 0, 'false')
    show_labels = params.get('showLabels', True) not in (False, 0, 'false')
    show_dist = params.get('showDistanceText', True) not in (False, 0, 'false')
    show_tol = params.get('showTolerance', True) not in (False, 0, 'false')
    color = judge_color(bag.get('judgeOk'))
    specs: list[dict[str, Any]] = []

    def _f(k, default=None):
        v = bag.get(k)
        return default if v is None else v

    if op == 'line_intersect' and _f('x1') is not None:
        if show_lines:
            specs.append(dict(type='line', x1=_f('x1'), y1=_f('y1'), x2=_f('x2'), y2=_f('y2'),
                              color=color, width=2))
            specs.append(dict(type='line', x1=_f('x3'), y1=_f('y3'), x2=_f('x4'), y2=_f('y4'),
                              color=color, width=2))
        if show_pts and _f('intersectX') is not None:
            specs.append(dict(type='cross', x=float(_f('intersectX')), y=float(_f('intersectY')),
                              size=10, color=color, width=1.8))
            specs.append(dict(type='point', x=_f('intersectX'), y=_f('intersectY'), color=color))
        if show_labels and _f('intersectX') is not None:
            specs.append(dict(type='label', x=float(_f('intersectX')) + 8,
                              y=float(_f('intersectY')) - 8,
                              text=f'交·{bag.get("judgeStatus") or ("OK" if bag.get("judgeOk") else "·")}',
                              color=color))
    elif op == 'point_distance' and _f('x1') is not None:
        if show_lines:
            specs.append(dict(type='line', x1=_f('x1'), y1=_f('y1'), x2=_f('x2'), y2=_f('y2'),
                              color=color, width=2))
        if show_pts:
            specs.append(dict(type='point', x=_f('x1'), y=_f('y1'), color=color))
            specs.append(dict(type='point', x=_f('x2'), y=_f('y2'), color=color))
        if (show_dist or show_labels) and _f('distance') is not None:
            mx = (float(_f('x1')) + float(_f('x2'))) / 2
            my = (float(_f('y1')) + float(_f('y2'))) / 2
            unit = str(bag.get('unit') or 'px')
            specs.append(dict(type='label', x=mx, y=my,
                              text=f'{float(_f("distance")):.3f}{unit}', color=color))
    elif op == 'point_line_distance' and _f('x1') is not None:
        if show_lines:
            specs.append(dict(type='line', x1=_f('x1'), y1=_f('y1'), x2=_f('x2'), y2=_f('y2'),
                              color=color, width=2))
            if _f('footX') is not None and _f('px') is not None:
                specs.append(dict(type='line', x1=_f('px'), y1=_f('py'),
                                  x2=_f('footX'), y2=_f('footY'),
                                  color='#ffb400', width=1.5))
        if show_pts and _f('px') is not None:
            specs.append(dict(type='cross', x=float(_f('px')), y=float(_f('py')),
                              size=8, color=color))
            specs.append(dict(type='point', x=_f('px'), y=_f('py'), color=color))
        if (show_dist or show_labels) and _f('distance') is not None and _f('px') is not None:
            unit = str(bag.get('unit') or 'px')
            specs.append(dict(type='label', x=float(_f('px')) + 8, y=float(_f('py')) - 8,
                              text=f'{float(_f("distance")):.3f}{unit}', color=color))
    elif op == 'line_angle' and _f('x1') is not None:
        if show_lines:
            specs.append(dict(type='line', x1=_f('x1'), y1=_f('y1'), x2=_f('x2'), y2=_f('y2'),
                              color=color, width=2))
            specs.append(dict(type='line', x1=_f('x3'), y1=_f('y3'), x2=_f('x4'), y2=_f('y4'),
                              color=color, width=2))
        if (show_dist or show_labels) and _f('angleDeg') is not None:
            mx = (float(_f('x1')) + float(_f('x2'))) / 2
            my = (float(_f('y1')) + float(_f('y2'))) / 2
            specs.append(dict(type='label', x=mx, y=my,
                              text=f'{float(_f("angleDeg")):.2f}°', color=color))
    elif op == 'point_circle_distance' and _f('cx') is not None:
        if show_pts:
            specs.append(dict(type='cross', x=float(_f('cx')), y=float(_f('cy')),
                              size=8, color=color))
            if _f('px') is not None:
                specs.append(dict(type='point', x=_f('px'), y=_f('py'), color=color))
        if show_lines and _f('px') is not None:
            specs.append(dict(type='line', x1=_f('cx'), y1=_f('cy'),
                              x2=_f('px'), y2=_f('py'), color='#ffb400', width=1.5))
        if _f('r') is not None:
            specs.append(dict(type='circle', x=_f('cx'), y=_f('cy'), r=float(_f('r')),
                              color=color, width=1.5))
        if (show_dist or show_labels) and _f('distance') is not None:
            specs.append(dict(type='label', x=float(_f('cx')) + 8, y=float(_f('cy')) - 8,
                              text=f'{float(_f("distance")):.3f}{bag.get("unit") or "px"}',
                              color=color))
    elif op == 'circle_circle_distance' and _f('cx') is not None and _f('cx2') is not None:
        if show_pts:
            specs.append(dict(type='point', x=_f('cx'), y=_f('cy'), color=color))
            specs.append(dict(type='point', x=_f('cx2'), y=_f('cy2'), color=color))
        if show_lines:
            specs.append(dict(type='line', x1=_f('cx'), y1=_f('cy'),
                              x2=_f('cx2'), y2=_f('cy2'), color='#ffb400', width=1.5))
        if (show_dist or show_labels) and _f('distance') is not None:
            mx = (float(_f('cx')) + float(_f('cx2'))) / 2
            my = (float(_f('cy')) + float(_f('cy2'))) / 2
            specs.append(dict(type='label', x=mx, y=my,
                              text=f'{float(_f("distance")):.3f}{bag.get("unit") or "px"}',
                              color=color))

    if show_tol and (params.get('judgeEnable') or bag.get('judgeEnable')):
        jmin = bag.get('judgeMin', params.get('judgeMin'))
        jmax = bag.get('judgeMax', params.get('judgeMax'))
        metric_lab, metric_val = primary_metric(bag, op)
        if metric_lab in ('distance', 'angleDeg', 'gap') and metric_val is not None:
            band = tolerance_band(metric_val, jmin, jmax)
            # place tolerance chip near first label-ish point
            tx = ty = 12.0
            for s in specs:
                if s.get('type') == 'label':
                    tx, ty = float(s['x']), float(s['y']) + 16
                    break
            in_b = band.get('inBand')
            tcol = '#00d250' if in_b else ('#ff5252' if in_b is False else '#ffb400')
            specs.append(dict(
                type='label', x=tx, y=ty,
                text=f'T[{jmin},{jmax}]',
                color=tcol,
            ))
    return specs[:max_specs]


def build_caliper_overlays(result: dict | None = None, params: dict | None = None,
                           *, max_specs: int = 80) -> list:
    """Soft overlays for caliper line items (endpoints + judge color)."""
    bag = _unwrap_bag(result)
    params = params if isinstance(params, dict) else {}
    if params.get('showOverlay') in (False, 0, 'false', 'False'):
        return []
    show_labels = params.get('showLabels', True) not in (False, 0, 'false')
    specs: list[dict[str, Any]] = []
    for i, it in enumerate(_as_list(bag.get('items'))[:32]):
        if not isinstance(it, dict):
            continue
        color = judge_color(it.get('judgeOk') if 'judgeOk' in it else bag.get('judgeOk'))
        x1 = it.get('x1', it.get('beginX'))
        y1 = it.get('y1', it.get('beginY'))
        x2 = it.get('x2', it.get('endX'))
        y2 = it.get('y2', it.get('endY'))
        if x1 is None or x2 is None:
            continue
        specs.append(dict(type='line', x1=x1, y1=y1, x2=x2, y2=y2, color=color, width=2))
        specs.append(dict(type='point', x=x1, y=y1, color=color))
        specs.append(dict(type='point', x=x2, y=y2, color=color))
        if show_labels:
            mx = (float(x1) + float(x2)) / 2
            my = (float(y1) + float(y2)) / 2
            st = it.get('judgeStatus') or ('OK' if it.get('judgeOk') else '·')
            length = it.get('lengthPixels')
            txt = f'#{i+1}{st}'
            if length is not None:
                try:
                    txt += f' L={float(length):.1f}'
                except (TypeError, ValueError):
                    pass
            specs.append(dict(type='label', x=mx, y=my, text=txt, color=color))
        if len(specs) >= max_specs:
            break
    return specs[:max_specs]


def soft_demo_measure_result(op: str = 'point_distance', *, ok: bool = True) -> dict:
    """Design-time demo payload for MeasureGeom density / overlays."""
    op = str(op or 'point_distance')
    if op == 'line_intersect':
        return {
            'status': 'ok', 'intersectX': 160.0, 'intersectY': 120.0,
            'x1': 40, 'y1': 40, 'x2': 280, 'y2': 200,
            'x3': 40, 'y3': 200, 'x4': 280, 'y4': 40,
            'parallel': False, 'unit': 'px',
            'judgeEnable': True, 'judgeOk': ok, 'judgeStatus': 'OK' if ok else 'NG',
            'judgeMin': 0, 'judgeMax': 99999, 'note': '软演示交点',
        }
    if op == 'line_angle':
        return {
            'status': 'ok', 'angleDeg': 45.0 if ok else 12.0,
            'x1': 50, 'y1': 150, 'x2': 250, 'y2': 150,
            'x3': 150, 'y3': 50, 'x4': 150, 'y4': 250,
            'parallel': False, 'perpendicular': True if ok else False,
            'unit': 'deg', 'judgeEnable': True,
            'judgeOk': ok, 'judgeStatus': 'OK' if ok else 'NG',
            'judgeMin': 40, 'judgeMax': 50, 'note': '软演示夹角',
        }
    if op == 'point_line_distance':
        return {
            'status': 'ok', 'distance': 24.5 if ok else 80.0,
            'px': 180, 'py': 60, 'x1': 40, 'y1': 120, 'x2': 300, 'y2': 120,
            'footX': 180, 'footY': 120, 'unit': 'px',
            'judgeEnable': True, 'judgeOk': ok, 'judgeStatus': 'OK' if ok else 'NG',
            'judgeMin': 10, 'judgeMax': 40, 'note': '软演示垂距',
        }
    if op == 'point_circle_distance':
        return {
            'status': 'ok', 'distance': 15.0 if ok else 55.0,
            'px': 200, 'py': 100, 'cx': 160, 'cy': 120, 'r': 40,
            'signed': -15.0, 'inside': True, 'centerDist': 25.0, 'unit': 'px',
            'judgeEnable': True, 'judgeOk': ok, 'judgeStatus': 'OK' if ok else 'NG',
            'judgeMin': 0, 'judgeMax': 30, 'note': '软演示点圆距',
        }
    if op == 'circle_circle_distance':
        return {
            'status': 'ok', 'distance': 20.0 if ok else 5.0, 'gap': 20.0 if ok else -5.0,
            'cx': 100, 'cy': 120, 'r': 30, 'cx2': 180, 'cy2': 120, 'r2': 30,
            'centerDist': 80.0, 'overlapping': not ok, 'unit': 'px',
            'judgeEnable': True, 'judgeOk': ok, 'judgeStatus': 'OK' if ok else 'NG',
            'judgeMin': 10, 'judgeMax': 40, 'note': '软演示圆隙',
        }
    # default point_distance
    return {
        'status': 'ok', 'distance': 128.0 if ok else 12.0,
        'dx': 100.0, 'dy': 80.0,
        'x1': 60, 'y1': 80, 'x2': 160, 'y2': 160, 'unit': 'px',
        'judgeEnable': True, 'judgeOk': ok, 'judgeStatus': 'OK' if ok else 'NG',
        'judgeMin': 80, 'judgeMax': 200, 'note': '软演示点距',
    }


def soft_demo_caliper_result(*, n: int = 3, ok: bool = True) -> dict:
    items = []
    for i in range(max(1, int(n))):
        length = 180.0 - i * 12 if ok else (40.0 + i * 5)
        j = True if ok else (i == 0)
        items.append({
            'index': i + 1,
            'x1': 40, 'y1': 60 + i * 40,
            'x2': 40 + length, 'y2': 60 + i * 40,
            'lengthPixels': length,
            'score': 0.92 - i * 0.05,
            'rms': 0.4 + i * 0.1,
            'angleDeg': 0.0 + i * 0.5,
            'method': 'caliper',
            'judgeOk': j,
            'judgeStatus': 'OK' if j else 'NG',
            'judgeMetric': length,
        })
    return {
        'feature': 'lines', 'method': 'caliper', 'count': len(items),
        'items': items, 'judgeEnable': True,
        'judgeOk': all(it['judgeOk'] for it in items),
        'judgeStatus': 'OK' if all(it['judgeOk'] for it in items) else 'NG',
        'judgeMin': 100.0, 'judgeMax': 250.0,
        'note': '软演示多卡尺',
    }


def chrome_map_from_film_cache(film_cache: dict | None, project_steps=None) -> dict:
    """path → measure/caliper chrome badge."""
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
            op = str(step.get('operation') or rec.get('operation') or '')
            if op not in MEASURE_OPS and op not in ('geometry', 'caliper'):
                continue
            # prefer measure_geom over plain geometry unless caliper method
            params = step.get('params') if isinstance(step.get('params'), dict) else {}
            if op == 'geometry' and str(params.get('findMethod') or 'caliper') not in (
                'caliper', 'measure', 'auto', ''
            ):
                continue
            summ = summarize_measure_result(rec, params, op=op if op != 'geometry' else 'caliper')
            badge = summ.get('chrome') or ''
            if badge and op in MEASURE_OPS:
                break
        if badge:
            out[path] = badge
    return out
