"""OCR / defect denser industrial result tables — soft OpenCV path (no Halcon).

Beyond wave140 light item tables: multi-column density, judge chrome, bbox/conf
summaries, soft demo payloads. No Comm/HMI cobind; no spark micro-props.
"""
from __future__ import annotations

from typing import Any


OPERATOR_TAGS = {
    'ocr': '识',
    'defects': '缺',
    'defect': '缺',
}

OPERATOR_LABELS = {
    'ocr': '字符识别',
    'defects': '缺陷检测',
    'defect': '缺陷检测',
}


def _as_list(v) -> list:
    return v if isinstance(v, list) else []


def _ocr_keys(d: dict) -> bool:
    return any(k in d for k in ('text', 'confidence', 'items')) and (
        'text' in d or 'ocr' in str(d.get('resultVar') or '').lower()
        or isinstance(d.get('items'), list)
    )


def _defect_keys(d: dict) -> bool:
    return any(k in d for k in ('defectRatio', 'count', 'items', 'passed')) and (
        'defectRatio' in d or 'minArea' in d or d.get('method') in ('absdiff', 'threshold', 'blob')
        or (isinstance(d.get('items'), list) and 'area' in str(d.get('items')[:1]))
    )


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
        if _ocr_keys(inner) or _defect_keys(inner) or 'items' in inner:
            return inner
    if isinstance(bag.get('result'), dict):
        return bag['result']
    return bag


def chrome_badge(kind: str, judge_ok=None, count=None, status=None) -> str:
    tag = OPERATOR_TAGS.get(str(kind or '').lower(), '识')
    mark = '·'
    if judge_ok is True or str(status or '').upper() in ('OK', 'PASS'):
        mark = '✓'
    elif judge_ok is False or str(status or '').upper() in ('NG', 'FAIL'):
        mark = '✗'
    if count is not None:
        try:
            return f'{tag}{int(count)}{mark}'
        except (TypeError, ValueError):
            pass
    return f'{tag}{mark}'


def _bbox_text(it: dict) -> str:
    box = it.get('bbox') or it.get('box') or it.get('rect')
    if isinstance(box, dict):
        try:
            return f"[{int(box.get('x',0))},{int(box.get('y',0))},{int(box.get('w') or box.get('width') or 0)},{int(box.get('h') or box.get('height') or 0)}]"
        except (TypeError, ValueError):
            return str(box)[:24]
    if isinstance(box, (list, tuple)) and len(box) >= 4:
        try:
            return f'[{int(box[0])},{int(box[1])},{int(box[2])},{int(box[3])}]'
        except (TypeError, ValueError):
            return str(box)[:24]
    # x,y,w,h flat
    if all(k in it for k in ('x', 'y', 'w', 'h')):
        try:
            return f"[{int(it['x'])},{int(it['y'])},{int(it['w'])},{int(it['h'])}]"
        except (TypeError, ValueError):
            pass
    return '—'


def _center_text(it: dict) -> str:
    cx = it.get('centerX', it.get('cx'))
    cy = it.get('centerY', it.get('cy'))
    if cx is None and isinstance(it.get('bbox'), (list, tuple)) and len(it['bbox']) >= 4:
        try:
            b = it['bbox']
            cx = float(b[0]) + float(b[2]) / 2
            cy = float(b[1]) + float(b[3]) / 2
        except (TypeError, ValueError):
            pass
    if cx is None:
        return '—'
    try:
        return f'{float(cx):.0f},{float(cy):.0f}'
    except (TypeError, ValueError):
        return '—'


def build_ocr_rows(items=None, *, max_rows: int = 64, expected: str = '',
                   min_conf: float | None = None) -> list[dict]:
    rows = []
    exp = str(expected or '')
    for i, it in enumerate(_as_list(items)[: max(1, int(max_rows))]):
        if not isinstance(it, dict):
            # plain string item
            if isinstance(it, str):
                it = {'text': it}
            else:
                continue
        txt = str(it.get('text') or it.get('label') or '')
        conf = it.get('confidence', it.get('score'))
        try:
            conf_f = float(conf) if conf is not None else None
        except (TypeError, ValueError):
            conf_f = None
        match = None
        if exp:
            match = (txt == exp) or (exp in txt)
        judge = it.get('judgeOk')
        if judge is None and min_conf is not None and conf_f is not None:
            judge = conf_f >= float(min_conf)
            if match is False:
                judge = False
        status = it.get('judgeStatus') or (
            'OK' if judge is True else ('NG' if judge is False else '—')
        )
        rows.append({
            'index': int(it.get('index') or (i + 1)),
            'text': txt[:64],
            'confidence': conf_f,
            'bbox': _bbox_text(it),
            'center': _center_text(it),
            'matchExpected': match,
            'judgeOk': judge if judge is None else bool(judge),
            'judgeStatus': status,
            'lang': it.get('lang'),
            'raw': it,
        })
    return rows


def build_defect_rows(items=None, *, max_rows: int = 64,
                      min_area: float | None = None) -> list[dict]:
    rows = []
    for i, it in enumerate(_as_list(items)[: max(1, int(max_rows))]):
        if not isinstance(it, dict):
            continue
        area = it.get('area', it.get('areaPixels'))
        try:
            area_f = float(area) if area is not None else None
        except (TypeError, ValueError):
            area_f = None
        judge = it.get('judgeOk')
        if judge is None and min_area is not None and area_f is not None:
            judge = area_f >= float(min_area)
        status = it.get('judgeStatus') or (
            'OK' if judge is True else ('NG' if judge is False else '缺')
        )
        # defects: presence usually means NG for the item itself
        if judge is None and status == '缺':
            status = 'NG'
            judge = False
        rows.append({
            'index': int(it.get('index') or (i + 1)),
            'area': area_f,
            'bbox': _bbox_text(it),
            'center': _center_text(it),
            'score': it.get('score') or it.get('intensity'),
            'aspect': it.get('aspect') or it.get('aspectRatio'),
            'judgeOk': judge if judge is None else bool(judge),
            'judgeStatus': status,
            'raw': it,
        })
    return rows


def summarize_ocr_result(result: dict | None = None, params: dict | None = None) -> dict:
    bag = _unwrap_bag(result)
    params = params if isinstance(params, dict) else {}
    items = _as_list(bag.get('items'))
    # synthesize items from top-level text if empty
    if not items and bag.get('text'):
        items = [{'text': bag.get('text'), 'confidence': bag.get('confidence'),
                  'bbox': bag.get('bbox'), 'judgeOk': bag.get('judgeOk')}]
    min_conf = params.get('judgeMinConfidence', bag.get('judgeMinConfidence'))
    try:
        min_conf_f = float(min_conf) if min_conf is not None else None
    except (TypeError, ValueError):
        min_conf_f = None
    expected = str(params.get('expectedText') or bag.get('expectedText') or '')
    rows = build_ocr_rows(items, expected=expected, min_conf=min_conf_f)
    count = bag.get('count')
    if count is None:
        count = len(rows)
    judge = bag.get('judgeOk')
    if judge is None and bag.get('passed') is not None:
        judge = bool(bag.get('passed'))
    status = bag.get('judgeStatus') or (
        'OK' if judge is True else ('NG' if judge is False else None)
    )
    chrome = chrome_badge('ocr', judge, count, status)
    text = bag.get('text') or ' '.join(r['text'] for r in rows[:4])
    conf = bag.get('confidence')
    if conf is None and rows:
        confs = [r['confidence'] for r in rows if r.get('confidence') is not None]
        conf = (sum(confs) / len(confs)) if confs else None
    tip = [chrome, f'n={count}']
    if conf is not None:
        try:
            tip.append(f'conf={float(conf):.3f}')
        except (TypeError, ValueError):
            tip.append(f'conf={conf}')
    if text:
        tip.append(f'"{str(text)[:24]}"')
    if expected:
        tip.append(f'期望={expected[:16]}')
    if judge is True:
        tip.append('OK')
    elif judge is False:
        tip.append('NG')
    return {
        'kind': 'ocr',
        'tag': '识',
        'label': OPERATOR_LABELS['ocr'],
        'chrome': chrome,
        'count': count,
        'text': text,
        'confidence': conf,
        'judgeOk': judge,
        'judgeStatus': status,
        'expectedText': expected,
        'summary': ' · '.join(str(t) for t in tip[:8]),
        'rows': rows,
        'okCount': sum(1 for r in rows if r.get('judgeOk') is True),
        'ngCount': sum(1 for r in rows if r.get('judgeOk') is False),
    }


def summarize_defect_result(result: dict | None = None, params: dict | None = None) -> dict:
    bag = _unwrap_bag(result)
    params = params if isinstance(params, dict) else {}
    items = _as_list(bag.get('items'))
    try:
        min_area = float(params.get('minArea')) if params.get('minArea') is not None else None
    except (TypeError, ValueError):
        min_area = None
    rows = build_defect_rows(items, min_area=min_area)
    count = bag.get('count')
    if count is None:
        count = len(rows)
    judge = bag.get('judgeOk')
    if judge is None and bag.get('passed') is not None:
        judge = bool(bag.get('passed'))
    status = bag.get('judgeStatus') or (
        'OK' if judge is True else ('NG' if judge is False else None)
    )
    chrome = chrome_badge('defects', judge, count, status)
    ratio = bag.get('defectRatio')
    tip = [chrome, f'n={count}']
    if ratio is not None:
        try:
            tip.append(f'ratio={float(ratio):.4g}')
        except (TypeError, ValueError):
            tip.append(f'ratio={ratio}')
    method = bag.get('method') or params.get('method')
    if method:
        tip.append(str(method))
    if judge is True:
        tip.append('OK')
    elif judge is False:
        tip.append('NG')
    areas = [r['area'] for r in rows if r.get('area') is not None]
    return {
        'kind': 'defects',
        'tag': '缺',
        'label': OPERATOR_LABELS['defects'],
        'chrome': chrome,
        'count': count,
        'defectRatio': ratio,
        'passed': bag.get('passed'),
        'judgeOk': judge,
        'judgeStatus': status,
        'method': method,
        'largestArea': max(areas) if areas else bag.get('largestArea'),
        'totalArea': sum(areas) if areas else None,
        'summary': ' · '.join(str(t) for t in tip[:8]),
        'rows': rows,
        'okCount': sum(1 for r in rows if r.get('judgeOk') is True),
        'ngCount': sum(1 for r in rows if r.get('judgeOk') is False),
    }


def build_ocr_overlays(result: dict | None = None, params: dict | None = None,
                       *, max_specs: int = 64) -> list:
    bag = _unwrap_bag(result)
    params = params if isinstance(params, dict) else {}
    if params.get('showOverlay') in (False, 0, 'false', 'False'):
        return []
    show_boxes = params.get('showBoxes', True) not in (False, 0, 'false')
    show_text = params.get('showText', True) not in (False, 0, 'false')
    specs: list[dict[str, Any]] = []
    items = _as_list(bag.get('items'))
    if not items and bag.get('text'):
        items = [{'text': bag.get('text'), 'confidence': bag.get('confidence'),
                  'bbox': bag.get('bbox'), 'judgeOk': bag.get('judgeOk')}]
    for i, it in enumerate(items[:24]):
        if not isinstance(it, dict):
            continue
        judge = it.get('judgeOk', bag.get('judgeOk'))
        color = '#00d250' if judge is True else ('#ff5252' if judge is False else '#42a5f5')
        box = it.get('bbox') or it.get('box') or it.get('rect')
        x = y = w = h = None
        if isinstance(box, (list, tuple)) and len(box) >= 4:
            x, y, w, h = float(box[0]), float(box[1]), float(box[2]), float(box[3])
        elif isinstance(box, dict):
            try:
                x = float(box.get('x') or 0)
                y = float(box.get('y') or 0)
                w = float(box.get('w') or box.get('width') or 0)
                h = float(box.get('h') or box.get('height') or 0)
            except (TypeError, ValueError):
                pass
        elif all(k in it for k in ('x', 'y', 'w', 'h')):
            x, y, w, h = float(it['x']), float(it['y']), float(it['w']), float(it['h'])
        if show_boxes and x is not None and w and h:
            specs.append(dict(type='rect', x=x, y=y, w=w, h=h, color=color, width=1.6))
            specs.append(dict(type='cross', x=x + w / 2, y=y + h / 2, size=6, color=color))
        if show_text and it.get('text') and x is not None:
            conf = it.get('confidence')
            conf_s = f' {float(conf):.2f}' if conf is not None else ''
            specs.append(dict(
                type='label', x=x, y=max(0, y - 14),
                text=f'{str(it["text"])[:20]}{conf_s}', color=color,
            ))
        if len(specs) >= max_specs:
            break
    # ROI outline if draw mode
    roi = params.get('roi') or bag.get('roi')
    if isinstance(roi, (list, tuple)) and len(roi) == 4:
        specs.append(dict(
            type='rect', x=float(roi[0]), y=float(roi[1]),
            w=float(roi[2]), h=float(roi[3]),
            color='#ffb400', width=1.2,
        ))
    return specs[:max_specs]


def build_defect_overlays(result: dict | None = None, params: dict | None = None,
                          *, max_specs: int = 64) -> list:
    bag = _unwrap_bag(result)
    params = params if isinstance(params, dict) else {}
    if params.get('showOverlay') in (False, 0, 'false', 'False'):
        return []
    show_boxes = params.get('showBoxes', True) not in (False, 0, 'false')
    show_labels = params.get('showLabels', True) not in (False, 0, 'false')
    specs: list[dict[str, Any]] = []
    for i, it in enumerate(_as_list(bag.get('items'))[:32]):
        if not isinstance(it, dict):
            continue
        color = '#ff5252'  # defects are findings
        box = it.get('bbox') or it.get('box') or it.get('rect')
        x = y = w = h = None
        if isinstance(box, (list, tuple)) and len(box) >= 4:
            x, y, w, h = float(box[0]), float(box[1]), float(box[2]), float(box[3])
        elif isinstance(box, dict):
            try:
                x = float(box.get('x') or 0); y = float(box.get('y') or 0)
                w = float(box.get('w') or box.get('width') or 0)
                h = float(box.get('h') or box.get('height') or 0)
            except (TypeError, ValueError):
                pass
        elif all(k in it for k in ('x', 'y', 'w', 'h')):
            x, y, w, h = float(it['x']), float(it['y']), float(it['w']), float(it['h'])
        cx = it.get('centerX', it.get('cx'))
        cy = it.get('centerY', it.get('cy'))
        if cx is None and x is not None and w is not None:
            cx, cy = x + w / 2, y + h / 2
        if show_boxes and x is not None and w and h:
            specs.append(dict(type='rect', x=x, y=y, w=w, h=h, color=color, width=1.8))
        if cx is not None:
            specs.append(dict(type='cross', x=float(cx), y=float(cy), size=7, color=color))
        if show_labels and (x is not None or cx is not None):
            area = it.get('area', it.get('areaPixels'))
            lx = x if x is not None else float(cx)
            ly = (y - 12) if y is not None else float(cy) - 12
            lab = f'#{i+1}'
            if area is not None:
                try:
                    lab += f' A={float(area):.0f}'
                except (TypeError, ValueError):
                    pass
            specs.append(dict(type='label', x=lx, y=ly, text=lab, color=color))
        if len(specs) >= max_specs:
            break
    return specs[:max_specs]


def soft_demo_ocr_result(*, ok: bool = True, n: int = 3) -> dict:
    texts = ['BATCH', 'SN-1024', 'OK'] if ok else ['BATCH', 'SN-????', 'NG']
    items = []
    for i in range(max(1, min(int(n), len(texts)))):
        conf = 0.96 - i * 0.04 if ok else 0.55 - i * 0.1
        items.append({
            'index': i + 1,
            'text': texts[i],
            'confidence': conf,
            'bbox': [40 + i * 110, 80, 90, 28],
            'centerX': 40 + i * 110 + 45,
            'centerY': 94,
            'judgeOk': conf >= 0.5 and (ok or i == 0),
            'judgeStatus': 'OK' if (conf >= 0.5 and (ok or i == 0)) else 'NG',
        })
    joined = ' '.join(it['text'] for it in items)
    return {
        'status': 'ok',
        'text': joined,
        'confidence': sum(it['confidence'] for it in items) / len(items),
        'count': len(items),
        'items': items,
        'judgeEnable': True,
        'expectedText': 'BATCH',
        'judgeOk': ok,
        'judgeStatus': 'OK' if ok else 'NG',
        'passed': ok,
        'note': '软演示 OCR',
    }


def soft_demo_defect_result(*, ok: bool = True, n: int = 3) -> dict:
    items = []
    for i in range(0 if ok else max(1, int(n))):
        area = 120 + i * 40
        items.append({
            'index': i + 1,
            'area': area,
            'areaPixels': area,
            'bbox': [60 + i * 50, 70 + i * 30, 24, 18],
            'centerX': 60 + i * 50 + 12,
            'centerY': 70 + i * 30 + 9,
            'score': 0.7 + i * 0.05,
            'aspect': 1.2 + i * 0.1,
            'judgeOk': False,
            'judgeStatus': 'NG',
        })
    count = len(items)
    ratio = 0.002 * max(1, count)
    return {
        'status': 'ok',
        'count': count,
        'defectRatio': 0.0 if ok else ratio,
        'items': items,
        'method': 'absdiff',
        'passed': ok,
        'judgeOk': ok,
        'judgeStatus': 'OK' if ok else 'NG',
        'judgeEnable': True,
        'judgeMaxCount': 0,
        'largestArea': max((it['area'] for it in items), default=0),
        'note': '软演示缺陷',
    }


def density_summary_rows(summ: dict | None = None) -> list[dict]:
    """Flat key/value rows for OCR/defect density side table."""
    summ = summ if isinstance(summ, dict) else {}
    keys = (
        'chrome', 'count', 'text', 'confidence', 'defectRatio', 'passed',
        'judgeOk', 'judgeStatus', 'method', 'expectedText', 'largestArea',
        'totalArea', 'okCount', 'ngCount', 'summary',
    )
    rows = []
    for k in keys:
        if k in summ and summ[k] is not None:
            rows.append({'key': k, 'value': summ[k]})
    return rows
