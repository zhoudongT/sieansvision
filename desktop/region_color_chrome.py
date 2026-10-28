"""Color-region / blob result chrome — soft OpenCV path (sieans-regions plugin).

Industrial density table + filmstrip chrome for HSV color regions and gray blobs.
No Comm/HMI cobind; no spark micro-props.
"""
from __future__ import annotations

from typing import Any


OPERATOR_TAGS = {
    'color': '色',
    'blobs': '斑',
    'blob': '斑',
    'hsv': '色',
    'gray': '斑',
}

OPERATOR_LABELS = {
    'color': '色彩区域',
    'blobs': '灰度斑点',
    'blob': '灰度斑点',
    'hsv': '色彩区域',
    'gray': '灰度斑点',
}


def _as_list(v) -> list:
    if isinstance(v, list):
        return v
    return []


def _region_payload_keys(d: dict) -> bool:
    return any(k in d for k in (
        'items', 'count', 'areaPixels', 'passed', 'coveragePercent', 'largestArea',
    ))


def _unwrap_bag(result: dict | None) -> dict:
    if not isinstance(result, dict):
        return {}
    bag = result
    # Prefer output.result / outputs.result (engine-host plugin record shape)
    for key in ('output', 'outputs'):
        inner = bag.get(key) if isinstance(bag.get(key), dict) else None
        if inner is None:
            continue
        if isinstance(inner.get('result'), dict) and _region_payload_keys(inner['result']):
            return inner['result']
        if _region_payload_keys(inner):
            return inner
    if isinstance(bag.get('result'), dict) and _region_payload_keys(bag['result']):
        return bag['result']
    if _region_payload_keys(bag):
        return bag
    return bag if isinstance(bag, dict) else {}


def detect_operator(result: dict | None = None, params: dict | None = None) -> str:
    p = params or {}
    op_id = str(p.get('operatorId') or p.get('operator') or '').lower()
    if op_id in OPERATOR_TAGS:
        return 'color' if op_id in ('color', 'hsv') else 'blobs'
    method = str(p.get('method') or (p.get('arguments') or {}).get('method') or '').lower()
    if method == 'hsv':
        return 'color'
    if method == 'gray':
        return 'blobs'
    bag = _unwrap_bag(result)
    if 'coveragePercent' in bag or 'largestArea' in bag:
        # plugin regions always expose these; prefer color if hue hints present
        args = p.get('arguments') if isinstance(p.get('arguments'), dict) else p
        if isinstance(args, dict) and ('hueMin' in args or args.get('method') == 'hsv'):
            return 'color'
        if isinstance(args, dict) and (args.get('method') == 'gray' or 'threshold' in args):
            return 'blobs'
    return 'color'


def operator_tag(op: str | None) -> str:
    return OPERATOR_TAGS.get(str(op or 'color').lower(), '色')


def extract_region_items(result: dict | None = None) -> list:
    bag = _unwrap_bag(result)
    return _as_list(bag.get('items'))


def build_region_rows(items=None, *, max_rows: int = 64, operator: str = 'color') -> list:
    rows = []
    for i, it in enumerate(_as_list(items)[: max(1, int(max_rows))]):
        if not isinstance(it, dict):
            continue
        try:
            area = float(it['areaPixels']) if it.get('areaPixels') is not None else None
        except (TypeError, ValueError):
            area = None
        try:
            cx = float(it['centerX']) if it.get('centerX') is not None else None
        except (TypeError, ValueError):
            cx = None
        try:
            cy = float(it['centerY']) if it.get('centerY') is not None else None
        except (TypeError, ValueError):
            cy = None
        try:
            fill = float(it['fillRatio']) if it.get('fillRatio') is not None else None
        except (TypeError, ValueError):
            fill = None
        try:
            w = float(it['width']) if it.get('width') is not None else None
        except (TypeError, ValueError):
            w = None
        try:
            h = float(it['height']) if it.get('height') is not None else None
        except (TypeError, ValueError):
            h = None
        passed = it.get('passed')
        if passed is None:
            passed = it.get('judgeOk')
        status = it.get('judgeStatus')
        if status is None and passed is not None:
            status = 'OK' if passed else 'NG'
        rows.append({
            'index': int(it.get('index') or (i + 1)),
            'operator': operator,
            'area': area,
            'centerX': cx,
            'centerY': cy,
            'width': w,
            'height': h,
            'fillRatio': fill,
            'x': it.get('x'),
            'y': it.get('y'),
            'passed': passed if passed is None else bool(passed),
            'judgeOk': passed if passed is None else bool(passed),
            'judgeStatus': status or '—',
            'raw': it,
        })
    return rows


def summarize_region_result(result: dict | None = None, *, params: dict | None = None) -> dict:
    op = detect_operator(result, params)
    bag = _unwrap_bag(result)
    items = _as_list(bag.get('items'))
    rows = build_region_rows(items, operator=op)
    try:
        count = int(bag['count']) if bag.get('count') is not None else len(rows)
    except (TypeError, ValueError):
        count = len(rows)
    try:
        total_area = float(bag['areaPixels']) if bag.get('areaPixels') is not None else None
    except (TypeError, ValueError):
        total_area = None
    if total_area is None:
        areas = [r['area'] for r in rows if r.get('area') is not None]
        total_area = sum(areas) if areas else None
    try:
        coverage = float(bag['coveragePercent']) if bag.get('coveragePercent') is not None else None
    except (TypeError, ValueError):
        coverage = None
    try:
        largest = float(bag['largestArea']) if bag.get('largestArea') is not None else None
    except (TypeError, ValueError):
        largest = None
    passed = bag.get('passed')
    if passed is None and 'judgeOk' in bag:
        passed = bag.get('judgeOk')
    if passed is not None:
        passed = bool(passed)
    tag = operator_tag(op)
    mark = ''
    if passed is True:
        mark = '✓'
    elif passed is False:
        mark = '✗'
    chrome = f'{tag}{count}{mark}' if count or mark else tag
    label = OPERATOR_LABELS.get(op, op)
    summary = f'{label} · {tag}×{count}'
    if total_area is not None:
        summary += f' · ΣA={total_area:.0f}'
    if coverage is not None:
        summary += f' · cov={coverage:.1f}%'
    if passed is True:
        summary += ' · OK'
    elif passed is False:
        summary += ' · NG'
    return {
        'operator': op,
        'tag': tag,
        'count': count,
        'totalArea': total_area,
        'coveragePercent': coverage,
        'largestArea': largest,
        'passed': passed,
        'judgeOk': passed,
        'chrome': chrome,
        'summary': summary,
        'rows': rows,
        'label': label,
        'roi': bag.get('roi') if isinstance(bag.get('roi'), dict) else None,
    }


def region_records_from_run(last_result: dict | None = None,
                            project_steps: list | None = None) -> list:
    """Collect sieans-regions plugin summaries from a full run."""
    if not isinstance(last_result, dict):
        return []
    steps = {str(s.get('id') or ''): s for s in (project_steps or []) if isinstance(s, dict)}
    out = []
    for rec in last_result.get('results') or []:
        if not isinstance(rec, dict):
            continue
        op = str(rec.get('operation') or rec.get('op') or '')
        sid = str(rec.get('id') or '')
        step = steps.get(sid) or {}
        params = step.get('params') if isinstance(step.get('params'), dict) else {}
        plugin_id = str(params.get('pluginId') or '')
        # Accept explicit plugin sieans-regions, or bags that look like region results
        bag = _unwrap_bag(rec)
        looks_region = bool(
            bag and ('coveragePercent' in bag or 'largestArea' in bag)
            and isinstance(bag.get('items'), list)
        )
        if plugin_id == 'sieans-regions' or (
            op == 'plugin' and looks_region
        ) or (looks_region and op in ('plugin', 'blob', 'color', 'regions')):
            summ = summarize_region_result(rec, params=params)
            summ['id'] = sid
            summ['name'] = str(rec.get('name') or step.get('name') or summ.get('label') or '')
            summ['operation'] = op or 'plugin'
            summ['pluginId'] = plugin_id or 'sieans-regions'
            out.append(summ)
    return out


def chrome_map_from_film_cache(cache: dict | None = None,
                               project_steps: list | None = None) -> dict:
    """path → chrome tag (e.g. 色2✓) for color-region / blob results."""
    chrome = {}
    for path, bag in (cache or {}).items():
        key = str(path or '').strip()
        if not key or not isinstance(bag, dict):
            continue
        records = region_records_from_run(bag, project_steps=project_steps)
        if not records:
            continue
        bits = [r.get('chrome') for r in records if r.get('chrome')]
        if not bits:
            continue
        joined = '+'.join(bits[:3])
        if len(bits) > 3:
            joined += f'+{len(bits)-3}'
        chrome[key] = joined[:16]
    return chrome


def strip_summary_from_film_cache(cache: dict | None = None, *,
                                  current_path: str = '',
                                  project_steps: list | None = None) -> str:
    bags = []
    cache = cache or {}
    if current_path and current_path in cache:
        bags.append(cache[current_path])
    for p, bag in cache.items():
        if p == current_path:
            continue
        bags.append(bag)
        if len(bags) >= 4:
            break
    bits = []
    for bag in bags:
        for r in region_records_from_run(bag, project_steps=project_steps):
            name = r.get('name') or r.get('label') or '区域'
            bits.append(f"{name} {r.get('chrome')}")
    if not bits:
        return ''
    head = f'色彩/斑点 · {len(bits)}'
    body = ' ｜ '.join(bits[:8])
    if len(bits) > 8:
        body += f' ｜ …+{len(bits)-8}'
    return f'{head} · {body}'


def soft_demo_region_items(operator: str = 'color', n: int = 2) -> list:
    """Deterministic soft demo for empty-state density (no hardware)."""
    op = str(operator or 'color').lower()
    n = max(1, min(int(n or 1), 8))
    items = []
    for i in range(n):
        # Match public/vision/samples/color-regions.png soft expectations loosely
        area = 12000.0 if i == 0 else (4800.0 if i == 1 else 2400.0 + i * 100)
        w = 110 if i == 0 else (70 if i == 1 else 40 + i * 4)
        h = 110 if i == 0 else (70 if i == 1 else 40 + i * 3)
        cx = 109.5 + i * 80
        cy = 109.5 + i * 20
        items.append({
            'index': i + 1,
            'areaPixels': area,
            'x': int(cx - w / 2),
            'y': int(cy - h / 2),
            'width': w,
            'height': h,
            'centerX': cx,
            'centerY': cy,
            'fillRatio': round(0.85 - i * 0.05, 3),
            'passed': True,
            'judgeOk': True,
            'judgeStatus': 'OK',
            '_softOp': op,
        })
    return items


def build_region_overlays(items=None, *, max_items: int = 32,
                          show_box: bool = True,
                          show_cross: bool = True,
                          show_labels: bool = True,
                          show_ellipse: bool = False,
                          color_ok: str = '#00c853',
                          color_ng: str = '#ff5252',
                          roi: dict | None = None) -> list:
    """Vector overlays for color/blob region results."""
    specs = []
    if isinstance(roi, dict) and roi.get('width') and roi.get('height'):
        try:
            specs.append({
                'type': 'rect',
                'x': float(roi.get('x') or 0),
                'y': float(roi.get('y') or 0),
                'w': float(roi['width']),
                'h': float(roi['height']),
                'color': '#c88c00',
                'width': 1.0,
            })
        except (TypeError, ValueError):
            pass
    for i, it in enumerate(_as_list(items)[: max(1, int(max_items))]):
        if not isinstance(it, dict):
            continue
        ok = it.get('passed')
        if ok is None:
            ok = it.get('judgeOk')
        color = color_ok if ok is not False else color_ng
        x, y = it.get('x'), it.get('y')
        w, h = it.get('width'), it.get('height')
        cx, cy = it.get('centerX'), it.get('centerY')
        if show_box and x is not None and y is not None and w is not None and h is not None:
            try:
                specs.append({
                    'type': 'rect',
                    'x': float(x), 'y': float(y),
                    'w': float(w), 'h': float(h),
                    'color': color, 'width': 1.5,
                })
            except (TypeError, ValueError):
                pass
        if show_ellipse and cx is not None and cy is not None and w is not None and h is not None:
            try:
                specs.append({
                    'type': 'ellipse',
                    'x': float(cx), 'y': float(cy),
                    'rx': float(w) / 2.0, 'ry': float(h) / 2.0,
                    'color': color, 'width': 1.2,
                })
            except (TypeError, ValueError):
                pass
        if show_cross and cx is not None and cy is not None:
            try:
                specs.append({
                    'type': 'cross', 'x': float(cx), 'y': float(cy),
                    'size': 9, 'color': color, 'width': 1.5,
                })
            except (TypeError, ValueError):
                pass
        if show_labels and cx is not None and cy is not None:
            idx = it.get('index') or (i + 1)
            area = it.get('areaPixels')
            lab = f'#{idx}'
            if area is not None:
                try:
                    lab += f' {float(area):.0f}'
                except (TypeError, ValueError):
                    pass
            try:
                specs.append({
                    'type': 'label',
                    'x': float(cx) + 6, 'y': float(cy) - 10,
                    'text': lab, 'color': color,
                })
            except (TypeError, ValueError):
                pass
    return specs
