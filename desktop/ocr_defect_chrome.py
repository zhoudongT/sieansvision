"""OCR / defect denser industrial result chrome — soft OpenCV path (no Halcon).

wave147: VisionMaster-style density parity with barcode/match/nine-point —
multi-col OCR/defect tables (#/文本/置信度/中心/宽高/bbox/判定), 识N✓/缺N✓
badges, filmstrip OK/NG density, denser ROI/char/region overlays.
Result chrome only — no Comm/HMI cobind; no spark/blink/chip/hostWatch cascade.
"""
from __future__ import annotations

from typing import Any

OCR_OPS = ('ocr',)
DEFECT_OPS = ('defects', 'defect')

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

OCR_COLUMNS = ['#', '文本', '置信度', '中心X', '中心Y', '宽', '高', '判定']
DEFECT_COLUMNS = ['#', '面积', '分数', '中心X', '中心Y', '宽', '高', '判定']


def _as_list(v) -> list:
    return v if isinstance(v, list) else []


def _f(v, default=None):
    try:
        if v is None:
            return default
        return float(v)
    except (TypeError, ValueError):
        return default


def _ocr_keys(d: dict) -> bool:
    return any(k in d for k in ('text', 'confidence', 'items')) and (
        'text' in d or 'ocr' in str(d.get('resultVar') or '').lower()
        or isinstance(d.get('items'), list)
    )


def _defect_keys(d: dict) -> bool:
    return any(k in d for k in ('defectRatio', 'count', 'items', 'passed')) and (
        'defectRatio' in d or 'minArea' in d
        or d.get('method') in ('absdiff', 'threshold', 'blob')
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
    """Compact badge: 识3✓ / 缺2✗ / 识·."""
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


def judge_color(judge_ok=None) -> str:
    if judge_ok is True:
        return '#00d250'
    if judge_ok is False:
        return '#ff5252'
    return '#42a5f5'


def _bbox_tuple(it: dict) -> tuple | None:
    if not isinstance(it, dict):
        return None
    box = it.get('bbox') or it.get('box') or it.get('rect')
    if isinstance(box, dict):
        try:
            return (
                float(box.get('x', 0)),
                float(box.get('y', 0)),
                float(box.get('w') or box.get('width') or 0),
                float(box.get('h') or box.get('height') or 0),
            )
        except (TypeError, ValueError):
            return None
    if isinstance(box, (list, tuple)) and len(box) >= 4:
        try:
            return (float(box[0]), float(box[1]), float(box[2]), float(box[3]))
        except (TypeError, ValueError):
            return None
    if all(k in it for k in ('x', 'y', 'w', 'h')):
        try:
            return (float(it['x']), float(it['y']), float(it['w']), float(it['h']))
        except (TypeError, ValueError):
            return None
    return None


def _bbox_text(it: dict) -> str:
    bb = _bbox_tuple(it)
    if bb is None:
        return '—'
    try:
        return f'[{int(bb[0])},{int(bb[1])},{int(bb[2])},{int(bb[3])}]'
    except (TypeError, ValueError):
        return '—'


def _center_xy(it: dict) -> tuple:
    if not isinstance(it, dict):
        return (None, None)
    cx = _f(it.get('centerX', it.get('cx')))
    cy = _f(it.get('centerY', it.get('cy')))
    if cx is not None and cy is not None:
        return (cx, cy)
    bb = _bbox_tuple(it)
    if bb is not None:
        return (bb[0] + bb[2] / 2, bb[1] + bb[3] / 2)
    return (None, None)


def _center_text(it: dict) -> str:
    cx, cy = _center_xy(it)
    if cx is None:
        return '—'
    try:
        return f'{float(cx):.0f},{float(cy):.0f}'
    except (TypeError, ValueError):
        return '—'


def build_ocr_rows(items=None, *, max_rows: int = 64, expected: str = '',
                   min_conf: float | None = None, params: dict | None = None) -> list[dict]:
    p = params if isinstance(params, dict) else {}
    exp = str(expected or p.get('expectedText') or '')
    if min_conf is None:
        try:
            min_conf = float(p['judgeMinConfidence']) if p.get('judgeMinConfidence') is not None else (
                float(p['minConfidence']) if p.get('minConfidence') is not None else None
            )
        except (TypeError, ValueError, KeyError):
            min_conf = None
    rows = []
    for i, it in enumerate(_as_list(items)[: max(1, int(max_rows))]):
        if not isinstance(it, dict):
            if isinstance(it, str):
                it = {'text': it}
            else:
                continue
        txt = str(it.get('text') or it.get('label') or '')
        conf = it.get('confidence', it.get('score'))
        conf_f = _f(conf)
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
        bb = _bbox_tuple(it)
        cx, cy = _center_xy(it)
        rows.append({
            'index': int(it.get('index') or (i + 1)),
            'text': txt[:64],
            'confidence': conf_f,
            'x': cx,
            'y': cy,
            'width': bb[2] if bb else None,
            'height': bb[3] if bb else None,
            'bbox': _bbox_text(it),
            'bboxTuple': bb,
            'center': _center_text(it),
            'matchExpected': match,
            'judgeOk': judge if judge is None else bool(judge),
            'judgeStatus': status,
            'lang': it.get('lang'),
            'line': it.get('line') or it.get('lineIndex'),
            'raw': it,
        })
    return rows


def build_defect_rows(items=None, *, max_rows: int = 64,
                      min_area: float | None = None,
                      params: dict | None = None) -> list[dict]:
    p = params if isinstance(params, dict) else {}
    if min_area is None:
        try:
            min_area = float(p['minArea']) if p.get('minArea') is not None else None
        except (TypeError, ValueError, KeyError):
            min_area = None
    rows = []
    for i, it in enumerate(_as_list(items)[: max(1, int(max_rows))]):
        if not isinstance(it, dict):
            continue
        area = it.get('area', it.get('areaPixels'))
        area_f = _f(area)
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
        bb = _bbox_tuple(it)
        cx, cy = _center_xy(it)
        score = it.get('score') or it.get('intensity')
        rows.append({
            'index': int(it.get('index') or (i + 1)),
            'area': area_f,
            'score': _f(score),
            'x': cx,
            'y': cy,
            'width': bb[2] if bb else None,
            'height': bb[3] if bb else None,
            'bbox': _bbox_text(it),
            'bboxTuple': bb,
            'center': _center_text(it),
            'aspect': it.get('aspect') or it.get('aspectRatio'),
            'judgeOk': judge if judge is None else bool(judge),
            'judgeStatus': status,
            'raw': it,
        })
    return rows


def format_ocr_cells(row: dict | None) -> list:
    r = row if isinstance(row, dict) else {}

    def fmt_n(v, nd=1):
        try:
            return f'{float(v):.{nd}f}'
        except (TypeError, ValueError):
            return '—'

    conf = r.get('confidence')
    conf_s = f'{float(conf):.3f}' if isinstance(conf, (int, float)) else '—'
    return [
        str(r.get('index') or ''),
        str(r.get('text') or '')[:40],
        conf_s,
        fmt_n(r.get('x')),
        fmt_n(r.get('y')),
        fmt_n(r.get('width')),
        fmt_n(r.get('height')),
        str(r.get('judgeStatus') or '—'),
    ]


def format_defect_cells(row: dict | None) -> list:
    r = row if isinstance(row, dict) else {}

    def fmt_n(v, nd=1):
        try:
            return f'{float(v):.{nd}f}'
        except (TypeError, ValueError):
            return '—'

    area = r.get('area')
    area_s = f'{float(area):.0f}' if isinstance(area, (int, float)) else '—'
    score = r.get('score')
    score_s = f'{float(score):.3f}' if isinstance(score, (int, float)) else '—'
    return [
        str(r.get('index') or ''),
        area_s,
        score_s,
        fmt_n(r.get('x')),
        fmt_n(r.get('y')),
        fmt_n(r.get('width')),
        fmt_n(r.get('height')),
        str(r.get('judgeStatus') or '—'),
    ]


# aliases used by barcode-style callers
format_row_cells = format_ocr_cells


def overlay_flags_ocr(params: dict | None = None) -> list:
    p = params if isinstance(params, dict) else {}
    flags = []
    for k, lab, default in (
        ('showOverlay', '叠层', True),
        ('showBoxes', '框', True),
        ('showText', '文本', True),
        ('showConf', '置信度', True),
        ('showIndex', '序号', True),
        ('showRoi', 'ROI', True),
    ):
        if p.get(k, default) not in (False, 0, 'false', 'False'):
            flags.append(lab)
    return flags


def overlay_flags_defect(params: dict | None = None) -> list:
    p = params if isinstance(params, dict) else {}
    flags = []
    for k, lab, default in (
        ('showOverlay', '叠层', True),
        ('showBoxes', '框', True),
        ('showLabels', '标签', True),
        ('showArea', '面积', True),
        ('showIndex', '序号', True),
        ('showRoi', 'ROI', True),
    ):
        if p.get(k, default) not in (False, 0, 'false', 'False'):
            flags.append(lab)
    return flags


def overlay_flags(params: dict | None = None, *, kind: str = 'ocr') -> list:
    if str(kind or '').lower() in ('defects', 'defect'):
        return overlay_flags_defect(params)
    return overlay_flags_ocr(params)


def summarize_ocr_result(result: dict | None = None, params: dict | None = None) -> dict:
    bag = _unwrap_bag(result)
    params = params if isinstance(params, dict) else {}
    items = _as_list(bag.get('items'))
    if not items and bag.get('text'):
        items = [{'text': bag.get('text'), 'confidence': bag.get('confidence'),
                  'bbox': bag.get('bbox'), 'judgeOk': bag.get('judgeOk')}]
    min_conf = params.get('judgeMinConfidence', bag.get('judgeMinConfidence'))
    if min_conf is None:
        min_conf = params.get('minConfidence')
    try:
        min_conf_f = float(min_conf) if min_conf is not None else None
    except (TypeError, ValueError):
        min_conf_f = None
    expected = str(params.get('expectedText') or bag.get('expectedText') or '')
    rows = build_ocr_rows(items, expected=expected, min_conf=min_conf_f, params=params)
    count = bag.get('count')
    if count is None:
        count = len(rows)
    judge_enable = bool(params.get('judgeEnable', True))
    judge = bag.get('judgeOk')
    if judge is None and bag.get('passed') is not None:
        judge = bool(bag.get('passed'))
    if judge is None and judge_enable:
        if expected and rows:
            judge = any(r.get('matchExpected') for r in rows)
        elif min_conf_f is not None and rows:
            judge = all(
                (r.get('confidence') or 0) >= min_conf_f
                for r in rows if r.get('confidence') is not None
            ) if any(r.get('confidence') is not None for r in rows) else bool(count)
        else:
            judge = bool(count) if count else False
    status = bag.get('judgeStatus') or (
        'OK' if judge is True else ('NG' if judge is False else None)
    )
    chrome = chrome_badge('ocr', judge, count, status)
    text = bag.get('text') or ' '.join(r['text'] for r in rows[:4])
    conf = bag.get('confidence')
    if conf is None and rows:
        confs = [r['confidence'] for r in rows if r.get('confidence') is not None]
        conf = (sum(confs) / len(confs)) if confs else None
    ok_n = sum(1 for r in rows if r.get('judgeOk') is True)
    ng_n = sum(1 for r in rows if r.get('judgeOk') is False)
    flags = overlay_flags_ocr(params)
    tip = [chrome, f'字×{count}']
    if conf is not None:
        try:
            tip.append(f'conf={float(conf):.3f}')
        except (TypeError, ValueError):
            tip.append(f'conf={conf}')
    if text:
        tip.append(f'"{str(text)[:24]}"')
    if expected:
        tip.append(f'期望={expected[:16]}')
    if judge_enable:
        tip.append(f'OK {ok_n}/NG {ng_n}')
    if judge is True:
        tip.append('OK')
    elif judge is False:
        tip.append('NG')
    if flags:
        tip.append('叠层:' + '·'.join(flags[:4]))
    return {
        'kind': 'ocr',
        'op': 'ocr',
        'tag': '识',
        'label': OPERATOR_LABELS['ocr'],
        'chrome': chrome,
        'count': count,
        'text': text,
        'confidence': conf,
        'judgeOk': judge,
        'judgeStatus': status,
        'judgeEnable': judge_enable,
        'expectedText': expected,
        'overlayFlags': flags,
        'summary': ' · '.join(str(t) for t in tip[:10]),
        'rows': rows,
        'columns': list(OCR_COLUMNS),
        'okCount': ok_n,
        'ngCount': ng_n,
        'found': bool(count),
    }


def summarize_defect_result(result: dict | None = None, params: dict | None = None) -> dict:
    bag = _unwrap_bag(result)
    params = params if isinstance(params, dict) else {}
    items = _as_list(bag.get('items'))
    try:
        min_area = float(params.get('minArea')) if params.get('minArea') is not None else None
    except (TypeError, ValueError):
        min_area = None
    rows = build_defect_rows(items, min_area=min_area, params=params)
    count = bag.get('count')
    if count is None:
        count = len(rows)
    judge_enable = bool(params.get('judgeEnable', True))
    judge = bag.get('judgeOk')
    if judge is None and bag.get('passed') is not None:
        judge = bool(bag.get('passed'))
    max_count = params.get('judgeMaxCount', bag.get('judgeMaxCount'))
    try:
        max_count = int(max_count) if max_count is not None else None
    except (TypeError, ValueError):
        max_count = None
    if judge is None and judge_enable:
        # zero defects = OK when maxCount gate present; else passed-like
        if max_count is not None:
            judge = count <= max_count
        else:
            judge = count == 0
    status = bag.get('judgeStatus') or (
        'OK' if judge is True else ('NG' if judge is False else None)
    )
    chrome = chrome_badge('defects', judge, count, status)
    ratio = bag.get('defectRatio')
    method = bag.get('method') or params.get('method')
    ok_n = sum(1 for r in rows if r.get('judgeOk') is True)
    ng_n = sum(1 for r in rows if r.get('judgeOk') is False)
    flags = overlay_flags_defect(params)
    tip = [chrome, f'缺×{count}']
    if ratio is not None:
        try:
            tip.append(f'ratio={float(ratio):.4g}')
        except (TypeError, ValueError):
            tip.append(f'ratio={ratio}')
    if method:
        tip.append(str(method))
    if judge_enable:
        tip.append(f'OK {ok_n}/NG {ng_n}')
    if judge is True:
        tip.append('OK')
    elif judge is False:
        tip.append('NG')
    if flags:
        tip.append('叠层:' + '·'.join(flags[:4]))
    areas = [r['area'] for r in rows if r.get('area') is not None]
    return {
        'kind': 'defects',
        'op': 'defects',
        'tag': '缺',
        'label': OPERATOR_LABELS['defects'],
        'chrome': chrome,
        'count': count,
        'defectRatio': ratio,
        'passed': bag.get('passed'),
        'judgeOk': judge,
        'judgeStatus': status,
        'judgeEnable': judge_enable,
        'judgeMaxCount': max_count,
        'method': method,
        'largestArea': max(areas) if areas else bag.get('largestArea'),
        'totalArea': sum(areas) if areas else None,
        'overlayFlags': flags,
        'summary': ' · '.join(str(t) for t in tip[:10]),
        'rows': rows,
        'columns': list(DEFECT_COLUMNS),
        'okCount': ok_n,
        'ngCount': ng_n,
        'found': bool(count),
    }


def build_ocr_overlays(result: dict | None = None, params: dict | None = None,
                       *, max_specs: int = 64) -> list:
    bag = _unwrap_bag(result)
    params = params if isinstance(params, dict) else {}
    if params.get('showOverlay') in (False, 0, 'false', 'False'):
        return []
    show_boxes = params.get('showBoxes', True) not in (False, 0, 'false', 'False')
    show_text = params.get('showText', True) not in (False, 0, 'false', 'False')
    show_conf = params.get('showConf', True) not in (False, 0, 'false', 'False')
    show_idx = params.get('showIndex', True) not in (False, 0, 'false', 'False')
    show_roi = params.get('showRoi', True) not in (False, 0, 'false', 'False')
    specs: list[dict[str, Any]] = []
    rows = build_ocr_rows(
        _as_list(bag.get('items')) or (
            [{'text': bag.get('text'), 'confidence': bag.get('confidence'),
              'bbox': bag.get('bbox'), 'judgeOk': bag.get('judgeOk')}]
            if bag.get('text') else []
        ),
        params=params,
        expected=str(params.get('expectedText') or ''),
    )
    for r in rows:
        if len(specs) >= max_specs:
            break
        color = judge_color(r.get('judgeOk'))
        bb = r.get('bboxTuple')
        cx, cy = r.get('x'), r.get('y')
        if show_boxes and isinstance(bb, tuple) and len(bb) >= 4 and bb[2] and bb[3]:
            specs.append(dict(
                type='rect', x=bb[0], y=bb[1], w=bb[2], h=bb[3],
                color=color, width=1.6,
            ))
            if cx is None:
                cx, cy = bb[0] + bb[2] / 2, bb[1] + bb[3] / 2
        if cx is not None and cy is not None:
            specs.append(dict(
                type='cross', x=float(cx), y=float(cy), size=6, color=color, width=1.3,
            ))
        if (show_text or show_conf or show_idx) and cx is not None and cy is not None:
            bits = []
            if show_idx:
                bits.append(f"#{r.get('index')}")
            if show_text and r.get('text'):
                bits.append(str(r['text'])[:18])
            if show_conf and r.get('confidence') is not None:
                try:
                    bits.append(f"{float(r['confidence']):.2f}")
                except (TypeError, ValueError):
                    pass
            st = r.get('judgeStatus')
            if st in ('OK', 'NG'):
                bits.append(st)
            if bits:
                lx = float(bb[0]) if isinstance(bb, tuple) else float(cx)
                ly = (float(bb[1]) - 14) if isinstance(bb, tuple) else float(cy) - 14
                specs.append(dict(
                    type='label', x=lx, y=max(0, ly),
                    text=' '.join(bits), color=color,
                ))
    if show_roi:
        roi = params.get('roi') or bag.get('roi')
        if isinstance(roi, (list, tuple)) and len(roi) == 4:
            specs.append(dict(
                type='rect', x=float(roi[0]), y=float(roi[1]),
                w=float(roi[2]), h=float(roi[3]),
                color='#ffb400', width=1.2,
            ))
            specs.append(dict(
                type='label', x=float(roi[0]), y=max(0, float(roi[1]) - 12),
                text='ROI', color='#ffb400',
            ))
    return specs[:max_specs]


def build_defect_overlays(result: dict | None = None, params: dict | None = None,
                          *, max_specs: int = 64) -> list:
    bag = _unwrap_bag(result)
    params = params if isinstance(params, dict) else {}
    if params.get('showOverlay') in (False, 0, 'false', 'False'):
        return []
    show_boxes = params.get('showBoxes', True) not in (False, 0, 'false', 'False')
    show_labels = params.get('showLabels', True) not in (False, 0, 'false', 'False')
    show_area = params.get('showArea', True) not in (False, 0, 'false', 'False')
    show_idx = params.get('showIndex', True) not in (False, 0, 'false', 'False')
    show_roi = params.get('showRoi', True) not in (False, 0, 'false', 'False')
    specs: list[dict[str, Any]] = []
    rows = build_defect_rows(_as_list(bag.get('items')), params=params)
    for r in rows:
        if len(specs) >= max_specs:
            break
        # defect findings are NG-colored by default
        color = '#ff5252' if r.get('judgeOk') is not True else '#00d250'
        bb = r.get('bboxTuple')
        cx, cy = r.get('x'), r.get('y')
        if show_boxes and isinstance(bb, tuple) and len(bb) >= 4 and bb[2] and bb[3]:
            specs.append(dict(
                type='rect', x=bb[0], y=bb[1], w=bb[2], h=bb[3],
                color=color, width=1.8,
            ))
        if cx is not None and cy is not None:
            specs.append(dict(
                type='cross', x=float(cx), y=float(cy), size=7, color=color, width=1.4,
            ))
        if (show_labels or show_area or show_idx) and (cx is not None or isinstance(bb, tuple)):
            bits = []
            if show_idx:
                bits.append(f"#{r.get('index')}")
            if show_area and r.get('area') is not None:
                try:
                    bits.append(f"A={float(r['area']):.0f}")
                except (TypeError, ValueError):
                    pass
            st = r.get('judgeStatus')
            if st in ('OK', 'NG', '缺'):
                bits.append(st)
            if bits:
                lx = float(bb[0]) if isinstance(bb, tuple) else float(cx)
                ly = (float(bb[1]) - 12) if isinstance(bb, tuple) else float(cy) - 12
                specs.append(dict(
                    type='label', x=lx, y=max(0, ly),
                    text=' '.join(bits), color=color,
                ))
    if show_roi:
        roi = params.get('roi') or bag.get('roi')
        if isinstance(roi, (list, tuple)) and len(roi) == 4:
            specs.append(dict(
                type='rect', x=float(roi[0]), y=float(roi[1]),
                w=float(roi[2]), h=float(roi[3]),
                color='#ffb400', width=1.2,
            ))
    return specs[:max_specs]


def soft_demo_ocr_result(*, ok: bool = True, n: int = 3) -> dict:
    texts = ['BATCH', 'SN-1024', 'OK'] if ok else ['BATCH', 'SN-????', 'NG']
    items = []
    for i in range(max(1, min(int(n), len(texts)))):
        conf = 0.96 - i * 0.04 if ok else 0.55 - i * 0.1
        jok = conf >= 0.5 and (ok or i == 0)
        items.append({
            'index': i + 1,
            'text': texts[i],
            'confidence': conf,
            'bbox': [40 + i * 110, 80, 90, 28],
            'centerX': 40 + i * 110 + 45,
            'centerY': 94,
            'line': 1,
            'judgeOk': jok,
            'judgeStatus': 'OK' if jok else 'NG',
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
        'roi': [20, 40, 400, 120],
        'note': '软演示 OCR · RapidOCR 壳 · 无 Halcon',
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
        'roi': [10, 10, 500, 400],
        'note': '软演示缺陷 · OpenCV absdiff · 无 Halcon',
    }


def density_summary_rows(summ: dict | None = None) -> list[dict]:
    """Chinese key/value rows for OCR/defect density side table."""
    s = summ if isinstance(summ, dict) else {}
    kind = str(s.get('kind') or s.get('op') or 'ocr')
    if kind in ('defects', 'defect'):
        rows = [
            {'key': '徽标', 'value': s.get('chrome') or '缺·'},
            {'key': '缺陷数', 'value': s.get('count')},
            {'key': '判定', 'value': s.get('judgeStatus') or '—'},
            {'key': 'OK/NG', 'value': f"{s.get('okCount', 0)}/{s.get('ngCount', 0)}"},
            {'key': '占比', 'value': s.get('defectRatio') if s.get('defectRatio') is not None else '—'},
            {'key': '方法', 'value': s.get('method') or '—'},
            {'key': '最大面积', 'value': s.get('largestArea') if s.get('largestArea') is not None else '—'},
            {'key': '总面积', 'value': s.get('totalArea') if s.get('totalArea') is not None else '—'},
            {'key': '摘要', 'value': s.get('summary') or '—'},
        ]
    else:
        rows = [
            {'key': '徽标', 'value': s.get('chrome') or '识·'},
            {'key': '字数', 'value': s.get('count')},
            {'key': '判定', 'value': s.get('judgeStatus') or '—'},
            {'key': 'OK/NG', 'value': f"{s.get('okCount', 0)}/{s.get('ngCount', 0)}"},
            {'key': '置信度', 'value': s.get('confidence') if s.get('confidence') is not None else '—'},
            {'key': '文本', 'value': (str(s.get('text') or '')[:48] or '—')},
            {'key': '期望', 'value': s.get('expectedText') or '—'},
            {'key': '摘要', 'value': s.get('summary') or '—'},
        ]
    return rows


def _iter_ocr_defect_recs(bag: dict, steps: dict):
    for rec in bag.get('results') or []:
        if not isinstance(rec, dict):
            continue
        sid = str(rec.get('id') or '')
        step = steps.get(sid) or {}
        op = str(step.get('operation') or rec.get('operation') or '')
        if op in OCR_OPS or op in DEFECT_OPS:
            yield rec, step, op
            continue
        ub = _unwrap_bag(rec)
        if _ocr_keys(ub) and 'text' in ub:
            yield rec, step, 'ocr'
        elif _defect_keys(ub):
            yield rec, step, 'defects'


def chrome_map_from_film_cache(cache: dict | None = None,
                               project_steps=None) -> dict:
    """path → 识N✓ / 缺N✗ for filmstrip OCR+defect density (result chrome)."""
    chrome = {}
    steps = {
        str(s.get('id') or ''): s
        for s in (project_steps or []) if isinstance(s, dict)
    }
    for path, bag in (cache or {}).items():
        key = str(path or '').strip()
        if not key or not isinstance(bag, dict):
            continue
        badges = []
        for rec, step, op in _iter_ocr_defect_recs(bag, steps):
            params = step.get('params') if isinstance(step.get('params'), dict) else {}
            if op in OCR_OPS or op == 'ocr':
                summ = summarize_ocr_result(rec, params)
            else:
                summ = summarize_defect_result(rec, params)
            b = summ.get('chrome') or ''
            if b:
                badges.append(str(b))
        if badges:
            # combine if both OCR+defect on same frame: 识3✓缺0✓
            chrome[key] = ''.join(badges)[:16]
    return chrome


def okng_map_from_film_cache(cache: dict | None = None,
                             project_steps=None) -> dict:
    """path → OK|NG from OCR/defect judge (filmstrip density, not spark)."""
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
        any_ng = False
        any_ok = False
        for rec, step, op in _iter_ocr_defect_recs(bag, steps):
            params = step.get('params') if isinstance(step.get('params'), dict) else {}
            if op in OCR_OPS or op == 'ocr':
                summ = summarize_ocr_result(rec, params)
            else:
                summ = summarize_defect_result(rec, params)
            if summ.get('judgeOk') is False:
                any_ng = True
            elif summ.get('judgeOk') is True:
                any_ok = True
        if any_ng:
            tag = 'NG'
        elif any_ok:
            tag = 'OK'
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
        for rec, step, op in _iter_ocr_defect_recs(bag, {
            str(s.get('id') or ''): s
            for s in (project_steps or []) if isinstance(s, dict)
        }):
            params = step.get('params') if isinstance(step.get('params'), dict) else {}
            name = str(step.get('name') or (
                OPERATOR_LABELS['ocr'] if op in OCR_OPS or op == 'ocr'
                else OPERATOR_LABELS['defects']
            ))
            if op in OCR_OPS or op == 'ocr':
                r = summarize_ocr_result(rec, params)
            else:
                r = summarize_defect_result(rec, params)
            bits.append(f"{name} {r.get('chrome')}")
    if not bits:
        return ''
    head = f'OCR/缺陷 · {len(bits)}'
    body = ' ｜ '.join(bits[:8])
    if len(bits) > 8:
        body += f' ｜ …+{len(bits) - 8}'
    return f'{head} · {body}'
