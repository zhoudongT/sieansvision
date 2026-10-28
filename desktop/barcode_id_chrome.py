"""Barcode / ID denser result chrome — soft OpenCV / zxing path (no Halcon).

Industrial multi-code table (#/文本/码制/中心/bbox/判定), 码N✓/✗ badge,
filmstrip OK/NG density as result chrome, denser polygon overlays.
Result chrome only — no spark/blink/chip/hostWatch micro-prop cascade,
no Comm/HMI cobind.
"""
from __future__ import annotations

from typing import Any

BARCODE_OPS = ('barcode',)

OPERATOR_TAG = '码'
OPERATOR_LABEL = '条码/ID'

BARCODE_COLUMNS = ['#', '文本', '码制', '中心X', '中心Y', '宽', '高', '判定']


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
        if isinstance(inner.get('result'), dict) and (
            'items' in inner['result'] or 'count' in inner['result']
            or 'text' in inner['result']
        ):
            return inner['result']
        if 'items' in inner or 'count' in inner:
            return inner
    if isinstance(bag.get('result'), dict) and (
        'items' in bag['result'] or 'count' in bag['result']
    ):
        return bag['result']
    return bag


def extract_barcode_items(result: dict | None = None) -> list:
    bag = _unwrap_bag(result)
    items = bag.get('items')
    if not isinstance(items, list):
        items = bag.get('codes')
    if not isinstance(items, list):
        items = bag.get('barcodes')
    return _as_list(items)


def chrome_badge(judge_ok=None, status=None, *, count: int | None = None) -> str:
    """Compact badge: 码2✓ / 码0✗ / 码·."""
    mark = '·'
    if judge_ok is True or str(status or '').upper() in ('OK', 'PASS'):
        mark = '✓'
    elif judge_ok is False or str(status or '').upper() in ('NG', 'FAIL'):
        mark = '✗'
    n = int(count) if count is not None else None
    if n is not None and n >= 0:
        return f'{OPERATOR_TAG}{n}{mark}'
    return f'{OPERATOR_TAG}{mark}'


def _poly_bbox(poly) -> tuple | None:
    if not isinstance(poly, (list, tuple)) or len(poly) < 2:
        return None
    xs, ys = [], []
    for pt in poly:
        if isinstance(pt, (list, tuple)) and len(pt) >= 2:
            try:
                xs.append(float(pt[0]))
                ys.append(float(pt[1]))
            except (TypeError, ValueError):
                pass
    if not xs or not ys:
        return None
    x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
    return (x0, y0, max(1.0, x1 - x0), max(1.0, y1 - y0))


def _item_center(it: dict) -> tuple:
    if not isinstance(it, dict):
        return (None, None)
    for key in ('center', 'centerXY'):
        c = it.get(key)
        if isinstance(c, (list, tuple)) and len(c) >= 2:
            return (_f(c[0]), _f(c[1]))
    cx = _f(it.get('centerX') or it.get('x'))
    cy = _f(it.get('centerY') or it.get('y'))
    if cx is not None and cy is not None:
        return (cx, cy)
    bb = it.get('bbox')
    if isinstance(bb, (list, tuple)) and len(bb) >= 4:
        try:
            return (float(bb[0]) + float(bb[2]) / 2, float(bb[1]) + float(bb[3]) / 2)
        except (TypeError, ValueError):
            pass
    poly = it.get('polygon') or it.get('points')
    box = _poly_bbox(poly)
    if box:
        return (box[0] + box[2] / 2, box[1] + box[3] / 2)
    return (None, None)


def build_barcode_rows(items, *, params: dict | None = None,
                       expected: str = '') -> list:
    """Industrial multi-code rows for denser result table."""
    p = params if isinstance(params, dict) else {}
    expect = str(expected or p.get('expectedText') or p.get('expectedCode') or '').strip()
    min_count = int(p.get('judgeMinCount') or p.get('minCount') or 1)
    rows = []
    for i, it in enumerate(_as_list(items)):
        if not isinstance(it, dict):
            continue
        text = str(it.get('text') or it.get('data') or it.get('value') or '')
        fmt = str(it.get('format') or it.get('symbology') or it.get('type') or '—')
        cx, cy = _item_center(it)
        poly = it.get('polygon') or it.get('points')
        bb = it.get('bbox')
        if not (isinstance(bb, (list, tuple)) and len(bb) >= 4):
            box = _poly_bbox(poly)
            bb = list(box) if box else None
        w = h = None
        if isinstance(bb, (list, tuple)) and len(bb) >= 4:
            try:
                w, h = float(bb[2]), float(bb[3])
            except (TypeError, ValueError):
                w = h = None
        jok = it.get('judgeOk')
        if jok is None:
            # Found code is OK; expected match tracked separately as matchesExpected.
            jok = bool(text)
        st = it.get('judgeStatus') or ('OK' if jok else 'NG')
        rows.append({
            'index': int(it.get('index') or i + 1),
            'text': text,
            'format': fmt,
            'x': cx,
            'y': cy,
            'width': w,
            'height': h,
            'bbox': bb,
            'polygon': poly,
            'judgeOk': bool(jok) if jok is not None else None,
            'judgeStatus': str(st),
            'matchesExpected': (expect in text) if expect else None,
        })
    # overall gate used by callers via summarize — keep min_count on summary
    _ = min_count
    return rows


def format_row_cells(row: dict | None) -> list:
    r = row if isinstance(row, dict) else {}
    def fmt_n(v, nd=1):
        try:
            return f'{float(v):.{nd}f}'
        except (TypeError, ValueError):
            return '—'
    return [
        str(r.get('index') or ''),
        str(r.get('text') or '')[:40],
        str(r.get('format') or '—'),
        fmt_n(r.get('x')),
        fmt_n(r.get('y')),
        fmt_n(r.get('width')),
        fmt_n(r.get('height')),
        str(r.get('judgeStatus') or '—'),
    ]


def overlay_flags(params: dict | None = None) -> list:
    p = params if isinstance(params, dict) else {}
    flags = []
    for k, lab, default in (
        ('showOverlay', '叠层', True),
        ('showBoxes', '框', True),
        ('showText', '文本', True),
        ('showFormat', '码制', True),
        ('showIndex', '序号', True),
    ):
        if p.get(k, default) not in (False, 0, 'false', 'False'):
            flags.append(lab)
    return flags


def summarize_barcode(result: dict | None = None, *,
                      params: dict | None = None) -> dict:
    """Dense barcode/ID result summary — codes / formats / overlays."""
    p = params if isinstance(params, dict) else {}
    bag = _unwrap_bag(result)
    items = extract_barcode_items(result)
    expect = str(p.get('expectedText') or p.get('expectedCode') or '').strip()
    rows = build_barcode_rows(items, params=p, expected=expect)
    count = len(rows)
    texts = [r['text'] for r in rows if r.get('text')]
    formats = sorted({r['format'] for r in rows if r.get('format') and r['format'] != '—'})
    ok_n = sum(1 for r in rows if r.get('judgeOk') is True)
    ng_n = sum(1 for r in rows if r.get('judgeOk') is False)
    min_count = int(p.get('judgeMinCount') or p.get('minCount') or 1)
    max_count = p.get('judgeMaxCount')
    try:
        max_count = int(max_count) if max_count is not None else None
    except (TypeError, ValueError):
        max_count = None
    judge_enable = bool(p.get('judgeEnable', True))
    judge = bag.get('judgeOk')
    if judge is None and judge_enable:
        # Expected text = at least one match (industrial multi-code); extras may differ.
        gate_ok = count >= min_count
        if max_count is not None and count > max_count:
            gate_ok = False
        if expect and not any(expect in t for t in texts):
            gate_ok = False
        judge = gate_ok if count else False
    elif judge is None and not judge_enable:
        judge = True if count else None
    status = bag.get('judgeStatus') or (
        'OK' if judge is True else ('NG' if judge is False else None)
    )
    chrome = chrome_badge(judge, status, count=count)
    flags = overlay_flags(p)
    tip = [chrome, f'码×{count}']
    if formats:
        tip.append('/'.join(formats[:4]))
    if texts:
        tip.append(texts[0][:24] + ('…' if len(texts[0]) > 24 else ''))
    if judge_enable:
        tip.append(f'OK {ok_n}/NG {ng_n}')
        tip.append(f'min≥{min_count}')
        if expect:
            tip.append(f'期望={expect[:16]}')
    if flags:
        tip.append('叠层:' + '·'.join(flags))
    joined = '\n'.join(texts)
    return {
        'op': 'barcode',
        'tag': OPERATOR_TAG,
        'label': OPERATOR_LABEL,
        'chrome': chrome,
        'count': count,
        'okCount': ok_n,
        'ngCount': ng_n,
        'texts': texts,
        'text': joined,
        'formats': formats,
        'judgeOk': judge,
        'judgeStatus': status,
        'judgeEnable': judge_enable,
        'judgeMinCount': min_count,
        'judgeMaxCount': max_count,
        'expectedText': expect,
        'overlayFlags': flags,
        'summary': ' · '.join(str(t) for t in tip[:10]),
        'rows': rows,
        'columns': list(BARCODE_COLUMNS),
        'found': bool(count),
    }


def density_summary_rows(summ: dict | None = None) -> list:
    s = summ if isinstance(summ, dict) else {}
    rows = [
        {'key': '徽标', 'value': s.get('chrome') or '码·'},
        {'key': '码数', 'value': s.get('count')},
        {'key': '判定', 'value': s.get('judgeStatus') or '—'},
        {'key': 'OK/NG', 'value': f"{s.get('okCount', 0)}/{s.get('ngCount', 0)}"},
        {'key': '码制', 'value': '/'.join(s.get('formats') or []) or '—'},
        {'key': '期望', 'value': s.get('expectedText') or '—'},
        {'key': '摘要', 'value': s.get('summary') or '—'},
    ]
    return rows


def judge_color(judge_ok=None) -> str:
    if judge_ok is True:
        return '#00d250'
    if judge_ok is False:
        return '#ff5252'
    return '#ffb400'


def build_barcode_overlays(result: dict | None = None, params: dict | None = None,
                           *, max_specs: int = 64) -> list:
    """Vector overlays for barcode polygons with OK/NG coloring + text labels."""
    p = params if isinstance(params, dict) else {}
    show_overlay = p.get('showOverlay', True) not in (False, 0, 'false', 'False')
    if not show_overlay:
        return []
    show_box = p.get('showBoxes', True) not in (False, 0, 'false', 'False')
    show_text = p.get('showText', True) not in (False, 0, 'false', 'False')
    show_fmt = p.get('showFormat', True) not in (False, 0, 'false', 'False')
    show_idx = p.get('showIndex', True) not in (False, 0, 'false', 'False')
    rows = build_barcode_rows(
        extract_barcode_items(result), params=p,
        expected=str(p.get('expectedText') or ''),
    )
    specs: list[dict[str, Any]] = []
    for r in rows:
        if len(specs) >= max_specs:
            break
        color = judge_color(r.get('judgeOk'))
        poly = r.get('polygon')
        if show_box and isinstance(poly, list) and len(poly) >= 2:
            pts = []
            for pt in poly:
                if isinstance(pt, (list, tuple)) and len(pt) >= 2:
                    try:
                        pts.append([float(pt[0]), float(pt[1])])
                    except (TypeError, ValueError):
                        pass
            if len(pts) >= 2:
                specs.append({
                    'type': 'polygon', 'points': pts, 'color': color, 'width': 1.8,
                })
        bb = r.get('bbox')
        if show_box and isinstance(bb, (list, tuple)) and len(bb) >= 4 and not poly:
            try:
                specs.append({
                    'type': 'rect',
                    'x': float(bb[0]), 'y': float(bb[1]),
                    'w': float(bb[2]), 'h': float(bb[3]),
                    'color': color, 'width': 1.6,
                })
            except (TypeError, ValueError):
                pass
        cx, cy = r.get('x'), r.get('y')
        if cx is not None and cy is not None:
            specs.append({
                'type': 'cross', 'x': float(cx), 'y': float(cy),
                'size': 8, 'color': color, 'width': 1.4,
            })
        if (show_text or show_fmt or show_idx) and cx is not None and cy is not None:
            bits = []
            if show_idx:
                bits.append(f"#{r.get('index')}")
            if show_fmt and r.get('format'):
                bits.append(str(r['format'])[:12])
            if show_text and r.get('text'):
                bits.append(str(r['text'])[:18])
            st = r.get('judgeStatus')
            if st in ('OK', 'NG'):
                bits.append(st)
            if bits:
                specs.append({
                    'type': 'label',
                    'x': float(cx) + 6, 'y': float(cy) - 10,
                    'text': ' '.join(bits), 'color': color,
                })
    return specs[:max_specs]


def soft_demo_barcodes(n: int = 2, *, ok: bool = True,
                       expected: str = 'MACHINE-QR-2026') -> list:
    """Deterministic multi-code soft demo (no hardware / no camera)."""
    n = max(1, min(int(n or 1), 8))
    demos = [
        {'text': 'MACHINE-QR-2026', 'format': 'QR Code',
         'polygon': [[58, 53], [205, 53], [205, 200], [58, 200]]},
        {'text': 'ABC123456789', 'format': 'Code 128',
         'polygon': [[320, 240], [587, 240], [587, 339], [320, 339]]},
        {'text': 'SN-9006222', 'format': 'Data Matrix',
         'polygon': [[40, 280], [120, 280], [120, 360], [40, 360]]},
        {'text': 'LOT-BATCH-01', 'format': 'Code 39',
         'polygon': [[400, 40], [680, 40], [680, 100], [400, 100]]},
    ]
    out = []
    for i in range(n):
        base = dict(demos[i % len(demos)])
        base['index'] = i + 1
        text = base['text']
        if not ok and i == n - 1:
            text = 'WRONG-ID'
            base['text'] = text
        # Multi-code: extras OK when overall ok; expected match is an overall gate.
        if ok:
            jok = bool(text)
        else:
            jok = False if i == n - 1 else bool(text)
        base['judgeOk'] = jok
        base['judgeStatus'] = 'OK' if jok else 'NG'
        out.append(base)
    return out


def soft_demo_barcode_result(*, n: int = 2, ok: bool = True,
                             expected: str = 'MACHINE-QR-2026',
                             judge_enable: bool = True) -> dict:
    items = soft_demo_barcodes(n=n, ok=ok, expected=expected)
    count = len(items)
    judge_all = all(m.get('judgeOk') for m in items) if items else False
    if judge_enable:
        judge = bool(judge_all) and count >= 1 and (
            any(expected in str(m.get('text') or '') for m in items) if expected else True
        )
        if not ok:
            judge = False
    else:
        judge = True if count else None
    return {
        'count': count,
        'items': items,
        'codes': items,
        'text': '\n'.join(m['text'] for m in items),
        'judgeEnable': bool(judge_enable),
        'judgeOk': judge,
        'judgeStatus': 'OK' if judge else 'NG',
        'expectedText': expected,
        'note': '软演示多码识别 · zxing 壳 · 无 Halcon',
    }


def chrome_map_from_film_cache(cache: dict | None = None,
                               project_steps=None) -> dict:
    """path → 码N✓ / 码N✗ for filmstrip barcode density (result chrome)."""
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
        for rec in bag.get('results') or []:
            if not isinstance(rec, dict):
                continue
            sid = str(rec.get('id') or '')
            step = steps.get(sid) or {}
            op = str(step.get('operation') or rec.get('operation') or '')
            if op not in BARCODE_OPS:
                ub = _unwrap_bag(rec)
                if not (ub.get('items') or ub.get('codes')):
                    continue
                op = 'barcode'
            params = step.get('params') if isinstance(step.get('params'), dict) else {}
            summ = summarize_barcode(rec, params=params)
            badge = summ.get('chrome') or ''
            if badge:
                break
        if badge:
            chrome[key] = str(badge)[:16]
    return chrome


def okng_map_from_film_cache(cache: dict | None = None,
                             project_steps=None) -> dict:
    """path → OK|NG from barcode judge (filmstrip density, not spark)."""
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
        for rec in bag.get('results') or []:
            if not isinstance(rec, dict):
                continue
            sid = str(rec.get('id') or '')
            step = steps.get(sid) or {}
            op = str(step.get('operation') or rec.get('operation') or '')
            if op not in BARCODE_OPS and not extract_barcode_items(rec):
                continue
            params = step.get('params') if isinstance(step.get('params'), dict) else {}
            summ = summarize_barcode(rec, params=params)
            if summ.get('judgeOk') is True:
                tag = 'OK'
            elif summ.get('judgeOk') is False:
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
            name = OPERATOR_LABEL
            op = str(rec.get('operation') or '')
            for s in (project_steps or []):
                if isinstance(s, dict) and str(s.get('id') or '') == sid:
                    params = s.get('params') if isinstance(s.get('params'), dict) else {}
                    name = str(s.get('name') or OPERATOR_LABEL)
                    op = str(s.get('operation') or op)
                    break
            if op not in BARCODE_OPS and not extract_barcode_items(rec):
                continue
            r = summarize_barcode(rec, params=params)
            bits.append(f"{name} {r.get('chrome')}")
    if not bits:
        return ''
    head = f'条码/ID · {len(bits)}'
    body = ' ｜ '.join(bits[:8])
    if len(bits) > 8:
        body += f' ｜ …+{len(bits) - 8}'
    return f'{head} · {body}'
