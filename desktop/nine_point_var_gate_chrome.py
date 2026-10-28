"""Nine-point + var-gate denser result chrome — soft affine path (no robot SDK).

Industrial residual table (#/err/mapped/判定), transform 3×3, 九N✓/门✓ badges,
filmstrip OK/NG density, pixel-point overlays. Result chrome only — no
spark/blink/chip/hostWatch micro-prop cascade, no Comm/HMI cobind.
"""
from __future__ import annotations

from typing import Any

NINE_OPS = ('nine_point',)
VAR_GATE_OPS = ('var_calc',)

OPERATOR_TAG_NINE = '九'
OPERATOR_TAG_GATE = '门'
OPERATOR_LABEL_NINE = '九点标定'
OPERATOR_LABEL_GATE = '变量门限'

RESIDUAL_COLUMNS = ['#', '残差', '映射X', '映射Y', '世界X', '世界Y', '像素X', '像素Y', '判定']
GATE_COLUMNS = ['名称', '值', '类型', '判定']
TRANSFORM_COLUMNS = ['行', 'c0', 'c1', 'c2']


def _as_list(v) -> list:
    return v if isinstance(v, list) else []


def _f(v, default=None):
    try:
        if v is None:
            return default
        return float(v)
    except (TypeError, ValueError):
        return default


def _unwrap_bag(result: dict | None) -> dict:
    if not isinstance(result, dict):
        return {}
    bag = result
    for key in ('output', 'outputs'):
        inner = bag.get(key) if isinstance(bag.get(key), dict) else None
        if inner is None:
            continue
        if isinstance(inner.get('result'), dict):
            return inner['result']
        if any(k in inner for k in ('transform', 'rms', 'usedPoints', 'residuals', 'values')):
            return inner
    if isinstance(bag.get('result'), dict):
        return bag['result']
    return bag


def chrome_badge_nine(judge_ok=None, status=None, *, count: int | None = None) -> str:
    """Compact badge: 九9✓ / 九3✗ / 九·."""
    mark = '·'
    if judge_ok is True or str(status or '').upper() in ('OK', 'PASS'):
        mark = '✓'
    elif judge_ok is False or str(status or '').upper() in ('NG', 'FAIL', 'NEED_POINTS', 'SINGULAR'):
        mark = '✗'
    n = int(count) if count is not None else None
    if n is not None and n >= 0:
        return f'{OPERATOR_TAG_NINE}{n}{mark}'
    return f'{OPERATOR_TAG_NINE}{mark}'


def chrome_badge_gate(judge_ok=None, status=None, *, name: str = 'passGate') -> str:
    """Compact gate badge: 门✓ / 门✗ / 门· (passGate-centric)."""
    mark = '·'
    if judge_ok is True or str(status or '').upper() in ('OK', 'PASS', '1', 'TRUE'):
        mark = '✓'
    elif judge_ok is False or str(status or '').upper() in ('NG', 'FAIL', '0', 'FALSE'):
        mark = '✗'
    tag = OPERATOR_TAG_GATE
    short = str(name or 'gate')[:8]
    if short and short not in ('passGate', 'gate', 'pass'):
        return f'{tag}{mark}'
    return f'{tag}{mark}'


def judge_color(judge_ok=None) -> str:
    if judge_ok is True:
        return '#00d250'
    if judge_ok is False:
        return '#ff5252'
    return '#ffb400'


def _point_lookup(params: dict | None) -> dict:
    p = params if isinstance(params, dict) else {}
    out = {}
    for row in _as_list(p.get('points')):
        if not isinstance(row, dict):
            continue
        try:
            idx = int(row.get('index') or 0)
        except (TypeError, ValueError):
            idx = 0
        if idx:
            out[idx] = row
    return out


def build_residual_rows(result: dict | None = None, *, params: dict | None = None,
                        rms_gate: float | None = None) -> list:
    """Industrial residual rows for denser nine-point result table."""
    bag = _unwrap_bag(result)
    p = params if isinstance(params, dict) else {}
    gate = _f(rms_gate if rms_gate is not None else p.get('rmsGate') or p.get('rmsMax'), 0.5)
    if gate is None:
        gate = 0.5
    lookup = _point_lookup(p)
    residuals = bag.get('residuals')
    rows = []
    if isinstance(residuals, list) and residuals:
        for i, it in enumerate(residuals):
            if not isinstance(it, dict):
                continue
            try:
                idx = int(it.get('index') or i + 1)
            except (TypeError, ValueError):
                idx = i + 1
            err = _f(it.get('error') or it.get('residual') or it.get('err'))
            mx = _f(it.get('mappedX') or it.get('wx') or it.get('x'))
            my = _f(it.get('mappedY') or it.get('wy') or it.get('y'))
            src = lookup.get(idx) or {}
            jok = None
            if err is not None and gate is not None:
                jok = err <= gate
            st = 'OK' if jok is True else ('NG' if jok is False else '—')
            rows.append({
                'index': idx,
                'error': err,
                'mappedX': mx,
                'mappedY': my,
                'worldX': _f(src.get('worldX')),
                'worldY': _f(src.get('worldY')),
                'pixelX': _f(src.get('pixelX')),
                'pixelY': _f(src.get('pixelY')),
                'judgeOk': jok,
                'judgeStatus': st,
            })
        return rows
    # fallback: enabled design points without residuals yet
    for i, src in enumerate(_as_list(p.get('points'))):
        if not isinstance(src, dict) or not src.get('enabled', True):
            continue
        try:
            idx = int(src.get('index') or i + 1)
        except (TypeError, ValueError):
            idx = i + 1
        rows.append({
            'index': idx,
            'error': None,
            'mappedX': None,
            'mappedY': None,
            'worldX': _f(src.get('worldX')),
            'worldY': _f(src.get('worldY')),
            'pixelX': _f(src.get('pixelX')),
            'pixelY': _f(src.get('pixelY')),
            'judgeOk': None,
            'judgeStatus': '—',
        })
    return rows


def format_residual_cells(row: dict | None) -> list:
    r = row if isinstance(row, dict) else {}

    def fmt_n(v, nd=4):
        try:
            return f'{float(v):.{nd}f}'
        except (TypeError, ValueError):
            return '—'

    return [
        str(r.get('index') or ''),
        fmt_n(r.get('error'), 6),
        fmt_n(r.get('mappedX')),
        fmt_n(r.get('mappedY')),
        fmt_n(r.get('worldX')),
        fmt_n(r.get('worldY')),
        fmt_n(r.get('pixelX'), 2),
        fmt_n(r.get('pixelY'), 2),
        str(r.get('judgeStatus') or '—'),
    ]


def transform_matrix_rows(transform) -> list:
    """Flatten 3×3 / 6-param affine into display rows."""
    vals = []
    if isinstance(transform, (list, tuple)):
        vals = list(transform)
    elif isinstance(transform, dict):
        for k in ('m00', 'm01', 'm02', 'm10', 'm11', 'm12', 'm20', 'm21', 'm22'):
            if k in transform:
                vals.append(transform[k])
        if not vals:
            vals = list(transform.values())
    # 6-param affine → pad to 3×3
    if len(vals) == 6:
        vals = list(vals) + [0, 0, 1]
    while len(vals) < 9:
        vals.append(0 if len(vals) < 8 else 1)
    rows = []
    for r in range(3):
        chunk = vals[r * 3:(r + 1) * 3]

        def fmt(v):
            try:
                return f'{float(v):.6g}'
            except (TypeError, ValueError):
                return str(v)

        rows.append({
            'row': r,
            'c0': fmt(chunk[0] if len(chunk) > 0 else 0),
            'c1': fmt(chunk[1] if len(chunk) > 1 else 0),
            'c2': fmt(chunk[2] if len(chunk) > 2 else 0),
            'cells': [fmt(chunk[i]) if i < len(chunk) else '0' for i in range(3)],
        })
    return rows


def summarize_nine_point(result: dict | None = None, *,
                         params: dict | None = None) -> dict:
    """Dense nine-point result summary — rms / residuals / transform / gate."""
    p = params if isinstance(params, dict) else {}
    bag = _unwrap_bag(result)
    rms = _f(bag.get('rms') if bag.get('rms') is not None else p.get('rms'))
    used = bag.get('usedPoints')
    if used is None:
        used = sum(1 for r in _as_list(p.get('points')) if isinstance(r, dict) and r.get('enabled', True))
    try:
        used = int(used)
    except (TypeError, ValueError):
        used = 0
    status = str(bag.get('status') or '')
    rms_gate = _f(p.get('rmsGate') or p.get('rmsMax'), 0.5) or 0.5
    min_points = int(p.get('judgeMinPoints') or p.get('minPoints') or 9)
    judge_enable = bool(p.get('judgeEnable', True))
    rows = build_residual_rows(bag, params=p, rms_gate=rms_gate)
    ok_n = sum(1 for r in rows if r.get('judgeOk') is True)
    ng_n = sum(1 for r in rows if r.get('judgeOk') is False)
    judge = bag.get('judgeOk')
    if judge is None and judge_enable:
        status_ok = status in ('ok', 'pass', 'OK', 'PASS') or (
            status == '' and rms is not None and used >= 3
        )
        if status in ('need_points', 'singular'):
            status_ok = False
        gate_ok = bool(status_ok) and used >= min_points and (
            rms is not None and rms < rms_gate
        )
        judge = gate_ok if (rms is not None or used >= 3) else None
        if used < 3:
            judge = False
    elif judge is None and not judge_enable:
        judge = True if status in ('ok', 'pass', 'OK') else None
    jstatus = bag.get('judgeStatus') or (
        'OK' if judge is True else ('NG' if judge is False else None)
    )
    chrome = chrome_badge_nine(judge, jstatus, count=used)
    tip = [chrome, f'点×{used}', f'rms={rms if rms is not None else "—"}']
    tip.append(f'门限<{rms_gate:g}')
    tip.append(f'min≥{min_points}')
    if judge_enable:
        tip.append(f'残差 OK {ok_n}/NG {ng_n}')
    tip.append(str(bag.get('unit') or p.get('unit') or 'mm'))
    tip.append(str(bag.get('method') or p.get('method') or 'affine'))
    return {
        'op': 'nine_point',
        'tag': OPERATOR_TAG_NINE,
        'label': OPERATOR_LABEL_NINE,
        'chrome': chrome,
        'usedPoints': used,
        'count': used,
        'rms': rms,
        'rmsGate': rms_gate,
        'minPoints': min_points,
        'okCount': ok_n,
        'ngCount': ng_n,
        'judgeOk': judge,
        'judgeStatus': jstatus,
        'judgeEnable': judge_enable,
        'status': status or jstatus,
        'unit': bag.get('unit') or p.get('unit') or 'mm',
        'method': bag.get('method') or p.get('method') or 'affine',
        'transform': bag.get('transform'),
        'transformRows': transform_matrix_rows(bag.get('transform')),
        'summary': ' · '.join(str(t) for t in tip[:10]),
        'rows': rows,
        'columns': list(RESIDUAL_COLUMNS),
        'note': bag.get('note') or '',
    }


def build_gate_rows(result: dict | None = None, *, params: dict | None = None) -> list:
    """Industrial var_calc values table with gate-ish OK/NG hints."""
    bag = _unwrap_bag(result)
    p = params if isinstance(params, dict) else {}
    values = bag.get('values') if isinstance(bag.get('values'), dict) else {}
    errors = bag.get('errors')
    err_map = {}
    if isinstance(errors, dict):
        err_map = errors
    elif isinstance(errors, list):
        for e in errors:
            if isinstance(e, dict) and e.get('name'):
                err_map[str(e['name'])] = e.get('error') or 'err'
    exprs = {
        str(r.get('name') or ''): r
        for r in _as_list(p.get('expressions')) if isinstance(r, dict) and r.get('name')
    }
    names = list(values.keys()) or list(exprs.keys())
    # prefer declaration order
    ordered = [str(r.get('name')) for r in _as_list(p.get('expressions')) if isinstance(r, dict) and r.get('name')]
    seen = set()
    final = []
    for n in ordered + names:
        if n and n not in seen:
            seen.add(n)
            final.append(n)
    rows = []
    for name in final:
        val = values.get(name)
        expr = exprs.get(name) or {}
        out_type = str(expr.get('outType') or (
            'boolean' if isinstance(val, bool) else (
                'number' if isinstance(val, (int, float)) else 'string'
            )
        ))
        jok = None
        st = '—'
        lname = name.lower()
        if name in err_map:
            jok = False
            st = 'ERR'
        elif any(k in lname for k in ('passgate', 'ok', 'gate', 'pass', 'judge')):
            try:
                if isinstance(val, bool):
                    jok = val
                elif isinstance(val, (int, float)):
                    jok = float(val) > 0
                elif str(val).upper() in ('OK', 'PASS', 'TRUE', '1'):
                    jok = True
                elif str(val).upper() in ('NG', 'FAIL', 'FALSE', '0'):
                    jok = False
            except (TypeError, ValueError):
                jok = None
            st = 'OK' if jok is True else ('NG' if jok is False else '—')
        rows.append({
            'name': name,
            'value': val,
            'outType': out_type,
            'judgeOk': jok,
            'judgeStatus': st,
            'error': err_map.get(name),
        })
    return rows


def format_gate_cells(row: dict | None) -> list:
    r = row if isinstance(row, dict) else {}
    v = r.get('value')
    if isinstance(v, float):
        text = f'{v:.6g}'
    else:
        text = str(v) if v is not None else '—'
    if r.get('error'):
        text = f"ERR:{r['error']}"
    return [
        str(r.get('name') or ''),
        text[:48],
        str(r.get('outType') or '—'),
        str(r.get('judgeStatus') or '—'),
    ]


def summarize_var_gate(result: dict | None = None, *,
                       params: dict | None = None,
                       gate_name: str = 'passGate') -> dict:
    """Dense var_calc / gate summary — values table + 门✓ badge."""
    p = params if isinstance(params, dict) else {}
    bag = _unwrap_bag(result)
    rows = build_gate_rows(bag, params=p)
    gname = str(gate_name or p.get('gateVar') or 'passGate')
    gate_row = next((r for r in rows if r.get('name') == gname), None)
    if gate_row is None:
        # soft fallback: first *Gate / *Ok name
        for r in rows:
            ln = str(r.get('name') or '').lower()
            if 'passgate' in ln or ln.endswith('gate') or ln.endswith('ok'):
                gate_row = r
                gname = str(r.get('name'))
                break
    judge = None
    if gate_row is not None:
        judge = gate_row.get('judgeOk')
        if judge is None:
            v = gate_row.get('value')
            try:
                if isinstance(v, bool):
                    judge = v
                elif isinstance(v, (int, float)):
                    judge = float(v) > 0
            except (TypeError, ValueError):
                judge = None
    status = 'OK' if judge is True else ('NG' if judge is False else None)
    chrome = chrome_badge_gate(judge, status, name=gname)
    err_n = sum(1 for r in rows if r.get('judgeStatus') == 'ERR')
    tip = [chrome, f'变量×{len(rows)}']
    if gate_row is not None:
        tip.append(f'{gname}={gate_row.get("value")}')
    if err_n:
        tip.append(f'err×{err_n}')
    tip.append(str(bag.get('scope') or p.get('scope') or 'flow'))
    return {
        'op': 'var_calc',
        'tag': OPERATOR_TAG_GATE,
        'label': OPERATOR_LABEL_GATE,
        'chrome': chrome,
        'gateName': gname,
        'gateValue': None if gate_row is None else gate_row.get('value'),
        'count': len(rows),
        'errorCount': err_n,
        'judgeOk': judge,
        'judgeStatus': status,
        'summary': ' · '.join(str(t) for t in tip[:8]),
        'rows': rows,
        'columns': list(GATE_COLUMNS),
        'scope': bag.get('scope') or p.get('scope') or 'flow',
    }


def density_summary_rows_nine(summ: dict | None = None) -> list:
    s = summ if isinstance(summ, dict) else {}
    return [
        {'key': '徽标', 'value': s.get('chrome') or '九·'},
        {'key': '点数', 'value': s.get('usedPoints')},
        {'key': 'RMS', 'value': s.get('rms') if s.get('rms') is not None else '—'},
        {'key': '门限', 'value': s.get('rmsGate')},
        {'key': '判定', 'value': s.get('judgeStatus') or '—'},
        {'key': '残差OK/NG', 'value': f"{s.get('okCount', 0)}/{s.get('ngCount', 0)}"},
        {'key': '方法', 'value': s.get('method') or 'affine'},
        {'key': '摘要', 'value': s.get('summary') or '—'},
    ]


def density_summary_rows_gate(summ: dict | None = None) -> list:
    s = summ if isinstance(summ, dict) else {}
    return [
        {'key': '徽标', 'value': s.get('chrome') or '门·'},
        {'key': '门限名', 'value': s.get('gateName') or 'passGate'},
        {'key': '门限值', 'value': s.get('gateValue')},
        {'key': '判定', 'value': s.get('judgeStatus') or '—'},
        {'key': '变量数', 'value': s.get('count')},
        {'key': '错误', 'value': s.get('errorCount')},
        {'key': '摘要', 'value': s.get('summary') or '—'},
    ]


def build_nine_point_overlays(result: dict | None = None, params: dict | None = None,
                              *, max_specs: int = 64) -> list:
    """Pixel-point crosses + residual labels for nine-point soft overlay."""
    p = params if isinstance(params, dict) else {}
    show = p.get('showOverlay', p.get('showPoints', True)) not in (False, 0, 'false', 'False')
    if not show:
        return []
    show_idx = p.get('showIndex', True) not in (False, 0, 'false', 'False')
    show_err = p.get('showResiduals', True) not in (False, 0, 'false', 'False')
    summ = summarize_nine_point(result, params=p)
    specs: list[dict[str, Any]] = []
    for r in summ.get('rows') or []:
        if len(specs) >= max_specs:
            break
        px, py = r.get('pixelX'), r.get('pixelY')
        if px is None or py is None:
            continue
        color = judge_color(r.get('judgeOk'))
        specs.append({
            'type': 'cross', 'x': float(px), 'y': float(py),
            'size': 10, 'color': color, 'width': 1.6,
        })
        bits = []
        if show_idx:
            bits.append(f"#{r.get('index')}")
        if show_err and r.get('error') is not None:
            try:
                bits.append(f"e={float(r['error']):.3f}")
            except (TypeError, ValueError):
                pass
        st = r.get('judgeStatus')
        if st in ('OK', 'NG'):
            bits.append(st)
        if bits:
            specs.append({
                'type': 'label',
                'x': float(px) + 8, 'y': float(py) - 10,
                'text': ' '.join(bits), 'color': color,
            })
    # overall chrome label near first point
    if summ.get('chrome') and specs:
        first = next((r for r in (summ.get('rows') or []) if r.get('pixelX') is not None), None)
        if first:
            specs.append({
                'type': 'label',
                'x': float(first['pixelX']) + 8,
                'y': float(first['pixelY']) + 18,
                'text': str(summ.get('chrome')),
                'color': judge_color(summ.get('judgeOk')),
            })
    return specs[:max_specs]


def soft_demo_nine_point_result(*, ok: bool = True, n: int = 9,
                                rms: float | None = None) -> dict:
    """Deterministic soft affine residual demo (no robot / no camera)."""
    n = max(3, min(int(n or 9), 12))
    # Perfect grid pixel→world with tiny noise when ok; large err when ng
    residuals = []
    points = []
    base_err = 0.05 if ok else 1.2
    if rms is not None:
        base_err = float(rms) * (0.9 if ok else 1.1)
    for i in range(n):
        col, row = i % 3, i // 3
        px, py = 100 + col * 220, 100 + row * 140
        wx, wy = 10 + col * 40, 10 + row * 30
        err = base_err * (1.0 + 0.08 * (i % 3))
        if not ok and i == n - 1:
            err = max(err, 2.5)
        residuals.append({
            'index': i + 1, 'error': err,
            'mappedX': wx + (0.01 if ok else 1.5),
            'mappedY': wy + (0.01 if ok else 1.2),
        })
        points.append({
            'index': i + 1, 'pixelX': px, 'pixelY': py,
            'worldX': wx, 'worldY': wy, 'enabled': True,
        })
    mean_rms = (sum(r['error'] ** 2 for r in residuals) / len(residuals)) ** 0.5
    transform = [0.1818, 0.0, -8.18, 0.0, 0.2143, -11.43, 0.0, 0.0, 1.0]
    return {
        'coordSystem': '机械坐标系',
        'unit': 'mm',
        'method': 'affine',
        'usedPoints': n,
        'transform': transform,
        'rms': mean_rms,
        'residuals': residuals,
        'points': points,
        'status': 'ok' if ok and n >= 3 else ('need_points' if n < 3 else 'ok'),
        'judgeOk': bool(ok),
        'judgeStatus': 'OK' if ok else 'NG',
        'note': '软演示九点仿射 · 无机械手 SDK',
    }


def soft_demo_var_gate_result(*, ok: bool = True,
                              gate_name: str = 'passGate') -> dict:
    values = {
        'calibRms': 0.12 if ok else 0.87,
        'calibPoints': 9,
        'calibOk': 1 if ok else 0,
        gate_name: 1 if ok else 0,
    }
    return {
        'scope': 'flow',
        'values': values,
        'errors': [],
        'judgeOk': bool(ok),
        'judgeStatus': 'OK' if ok else 'NG',
        'note': '软演示变量门限 · passGate',
    }


def chrome_map_from_film_cache(cache: dict | None = None,
                               project_steps=None) -> dict:
    """path → 九N✓ / 门✓ for filmstrip nine/gate density (result chrome)."""
    chrome = {}
    steps = {
        str(s.get('id') or ''): s
        for s in (project_steps or []) if isinstance(s, dict)
    }
    for path, bag in (cache or {}).items():
        key = str(path or '').strip()
        if not key or not isinstance(bag, dict):
            continue
        badge = ''
        gate_badge = ''
        for rec in bag.get('results') or []:
            if not isinstance(rec, dict):
                continue
            sid = str(rec.get('id') or '')
            step = steps.get(sid) or {}
            op = str(step.get('operation') or rec.get('operation') or '')
            params = step.get('params') if isinstance(step.get('params'), dict) else {}
            if op in NINE_OPS or 'transform' in _unwrap_bag(rec) or 'residuals' in _unwrap_bag(rec):
                summ = summarize_nine_point(rec, params=params)
                badge = summ.get('chrome') or badge
            if op in VAR_GATE_OPS or isinstance(_unwrap_bag(rec).get('values'), dict):
                if op in VAR_GATE_OPS or any(
                    str(k).lower() in ('passgate', 'calibok')
                    for k in (_unwrap_bag(rec).get('values') or {})
                ):
                    gsum = summarize_var_gate(rec, params=params)
                    gate_badge = gsum.get('chrome') or gate_badge
        # prefer nine badge; append gate if both
        out = badge or gate_badge
        if badge and gate_badge and gate_badge != badge:
            out = f'{badge}{gate_badge}'
        if out:
            chrome[key] = str(out)[:16]
    return chrome


def okng_map_from_film_cache(cache: dict | None = None,
                             project_steps=None) -> dict:
    """path → OK|NG from nine-point / passGate judge."""
    out = {}
    steps = {
        str(s.get('id') or ''): s
        for s in (project_steps or []) if isinstance(s, dict)
    }
    for path, bag in (cache or {}).items():
        key = str(path or '').strip()
        if not key or not isinstance(bag, dict):
            continue
        tag = ''
        # Prefer gate (passGate) when present; else nine judge
        for rec in bag.get('results') or []:
            if not isinstance(rec, dict):
                continue
            sid = str(rec.get('id') or '')
            step = steps.get(sid) or {}
            op = str(step.get('operation') or rec.get('operation') or '')
            params = step.get('params') if isinstance(step.get('params'), dict) else {}
            if op in VAR_GATE_OPS:
                g = summarize_var_gate(rec, params=params)
                if g.get('judgeOk') is True:
                    tag = 'OK'
                elif g.get('judgeOk') is False:
                    tag = 'NG'
            if tag:
                break
        if not tag:
            for rec in bag.get('results') or []:
                if not isinstance(rec, dict):
                    continue
                sid = str(rec.get('id') or '')
                step = steps.get(sid) or {}
                op = str(step.get('operation') or rec.get('operation') or '')
                params = step.get('params') if isinstance(step.get('params'), dict) else {}
                if op not in NINE_OPS and 'rms' not in _unwrap_bag(rec):
                    continue
                s = summarize_nine_point(rec, params=params)
                if s.get('judgeOk') is True:
                    tag = 'OK'
                elif s.get('judgeOk') is False:
                    tag = 'NG'
                if tag:
                    break
        if tag:
            out[key] = tag
    return out


def strip_summary_from_film_cache(cache: dict | None = None, *,
                                  current_path: str = '',
                                  project_steps=None) -> str:
    bags = []
    cache = cache or {}
    if current_path and current_path in cache:
        bags.append(cache[current_path])
    for pth, bag in cache.items():
        if pth == current_path:
            continue
        bags.append(bag)
        if len(bags) >= 4:
            break
    bits = []
    for bag in bags:
        for rec in bag.get('results') or []:
            if not isinstance(rec, dict):
                continue
            sid = str(rec.get('id') or '')
            params = {}
            name = ''
            op = str(rec.get('operation') or '')
            for s in (project_steps or []):
                if isinstance(s, dict) and str(s.get('id') or '') == sid:
                    params = s.get('params') if isinstance(s.get('params'), dict) else {}
                    name = str(s.get('name') or '')
                    op = str(s.get('operation') or op)
                    break
            if op in NINE_OPS or 'rms' in _unwrap_bag(rec):
                r = summarize_nine_point(rec, params=params)
                bits.append(f"{name or OPERATOR_LABEL_NINE} {r.get('chrome')}")
            elif op in VAR_GATE_OPS:
                r = summarize_var_gate(rec, params=params)
                bits.append(f"{name or OPERATOR_LABEL_GATE} {r.get('chrome')}")
    if not bits:
        return ''
    head = f'九点/门限 · {len(bits)}'
    body = ' ｜ '.join(bits[:8])
    if len(bits) > 8:
        body += f' ｜ …+{len(bits) - 8}'
    return f'{head} · {body}'
