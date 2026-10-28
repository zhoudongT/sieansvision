"""Preprocess chain result density — multi-step before/after chrome (soft OpenCV).

No Comm/HMI cobind; no spark micro-props. Consumes preprocess engine result bags
with optional methodChain / chainSteps / before-after size fields.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any


METHOD_LABELS = {
    'grayscale': '灰度化',
    'blur': '高斯模糊',
    'median': '中值滤波',
    'bilateral': '双边滤波',
    'threshold': '二值化',
    'canny': '边缘提取',
    'open': '开运算',
    'close': '闭运算',
    'erode': '腐蚀',
    'dilate': '膨胀',
}

OPERATOR_TAG = '预'
OPERATOR_LABEL = '预处理链'


def _as_list(v) -> list:
    return v if isinstance(v, list) else []


def method_label(method: str | None) -> str:
    m = str(method or 'grayscale').lower()
    return METHOD_LABELS.get(m, m)


def _unwrap_bag(result: dict | None) -> dict:
    if not isinstance(result, dict):
        return {}
    bag = result
    for key in ('output', 'outputs'):
        inner = bag.get(key) if isinstance(bag.get(key), dict) else None
        if inner is None:
            continue
        if isinstance(inner.get('result'), dict) and _pp_keys(inner['result']):
            return inner['result']
        if _pp_keys(inner):
            return inner
    if isinstance(bag.get('result'), dict) and _pp_keys(bag['result']):
        return bag['result']
    if _pp_keys(bag):
        return bag
    return bag if isinstance(bag, dict) else {}


def _pp_keys(d: dict) -> bool:
    return any(k in d for k in (
        'method', 'chainSteps', 'methodChain', 'roiApplied', 'beforeWidth', 'afterWidth',
        'width', 'height',
    ))


def normalize_method_chain(params: dict | None = None) -> list[dict]:
    """Return a list of {method, ...} steps. Empty → single method from params."""
    p = params if isinstance(params, dict) else {}
    chain = p.get('methodChain')
    out: list[dict] = []
    if isinstance(chain, list) and chain:
        for item in chain:
            if isinstance(item, str) and item.strip():
                out.append({'method': item.strip()})
            elif isinstance(item, dict) and item.get('method'):
                out.append(deepcopy(item))
    if not out and p.get('method'):
        out.append({'method': str(p.get('method') or 'grayscale')})
    return out


def chrome_badge(chain_len: int = 1, status: str | None = None, ok: bool | None = None) -> str:
    n = max(1, int(chain_len or 1))
    mark = ''
    if ok is True or str(status or '').lower() == 'ok':
        mark = '✓'
    elif ok is False or str(status or '').lower() in ('error', 'fail', 'ng'):
        mark = '✗'
    return f'{OPERATOR_TAG}{n}{mark}'


def soft_demo_chain_result(*, methods=None) -> dict:
    methods = methods or ['grayscale', 'median', 'canny']
    steps = []
    for i, m in enumerate(methods):
        steps.append({
            'index': i + 1,
            'method': m,
            'label': method_label(m),
            'status': 'ok',
            'width': 640 if i == 0 else 640,
            'height': 480,
        })
    return {
        'method': methods[-1] if methods else 'grayscale',
        'methodChain': [{'method': m} for m in methods],
        'chainSteps': steps,
        'chainLen': len(steps),
        'roiApplied': True,
        'roiMode': 'draw',
        'roi': [40, 30, 320, 240],
        'beforeWidth': 640,
        'beforeHeight': 480,
        'afterWidth': 320,
        'afterHeight': 240,
        'width': 320,
        'height': 240,
        'status': 'ok',
        'note': '软演示预处理链 · 灰度→中值→Canny',
    }


def build_chain_rows(result: dict | None = None, params: dict | None = None) -> list[dict]:
    bag = _unwrap_bag(result)
    params = params if isinstance(params, dict) else {}
    steps = bag.get('chainSteps')
    if not isinstance(steps, list) or not steps:
        chain = normalize_method_chain({**params, **({
            'method': bag.get('method'),
            'methodChain': bag.get('methodChain'),
        })})
        rows = []
        for i, step in enumerate(chain):
            m = str(step.get('method') or 'grayscale')
            rows.append({
                'index': i + 1,
                'method': m,
                'label': method_label(m),
                'status': bag.get('status') or '—',
                'width': bag.get('width'),
                'height': bag.get('height'),
            })
        return rows
    rows = []
    for i, step in enumerate(steps):
        if not isinstance(step, dict):
            continue
        m = str(step.get('method') or '')
        rows.append({
            'index': int(step.get('index') or (i + 1)),
            'method': m,
            'label': step.get('label') or method_label(m),
            'status': step.get('status') or bag.get('status') or '—',
            'width': step.get('width', bag.get('width')),
            'height': step.get('height', bag.get('height')),
        })
    return rows


def before_after_meta(result: dict | None = None) -> dict:
    bag = _unwrap_bag(result)
    bw = bag.get('beforeWidth')
    bh = bag.get('beforeHeight')
    aw = bag.get('afterWidth', bag.get('width'))
    ah = bag.get('afterHeight', bag.get('height'))
    roi = bag.get('roi')
    roi_txt = ''
    if isinstance(roi, list) and len(roi) == 4:
        roi_txt = f'[{roi[0]:.0f},{roi[1]:.0f},{roi[2]:.0f},{roi[3]:.0f}]'
    return {
        'before': f'{bw}×{bh}' if bw and bh else '—',
        'after': f'{aw}×{ah}' if aw and ah else '—',
        'roiApplied': bool(bag.get('roiApplied')),
        'roiMode': bag.get('roiMode') or 'inherit',
        'roiText': roi_txt or ('全图' if not bag.get('roiApplied') else '—'),
        'method': bag.get('method'),
        'methodLabel': method_label(bag.get('method')),
        'chainLen': int(bag.get('chainLen') or len(_as_list(bag.get('chainSteps'))) or 1),
        'status': bag.get('status'),
        'note': bag.get('note') or '',
    }


def summarize_preprocess_result(result: dict | None = None, params: dict | None = None) -> dict:
    bag = _unwrap_bag(result)
    params = params if isinstance(params, dict) else {}
    rows = build_chain_rows(bag, params)
    meta = before_after_meta(bag)
    n = meta.get('chainLen') or len(rows) or 1
    ok = None
    st = str(bag.get('status') or '')
    if st == 'ok':
        ok = True
    elif st in ('error', 'fail', 'ng'):
        ok = False
    chrome = chrome_badge(n, st, ok)
    tip = [
        chrome,
        f'{meta["before"]}→{meta["after"]}',
        meta.get('methodLabel') or '',
    ]
    if meta.get('roiApplied'):
        tip.append(f'ROI {meta.get("roiText")}')
    return {
        'chrome': chrome,
        'tag': OPERATOR_TAG,
        'label': OPERATOR_LABEL,
        'chainRows': rows,
        'beforeAfter': meta,
        'summary': ' · '.join(str(t) for t in tip if t),
        'status': bag.get('status'),
        'method': bag.get('method'),
    }


def build_preprocess_roi_overlays(result: dict | None = None, params: dict | None = None) -> list:
    """Optional ROI rect overlay for preprocess draw mode."""
    bag = _unwrap_bag(result)
    params = params if isinstance(params, dict) else {}
    show = params.get('showRoiOverlay', bag.get('showRoiOverlay', True))
    if show in (False, 0, 'false', 'False'):
        return []
    mode = str(params.get('roiMode') or bag.get('roiMode') or 'inherit')
    roi = bag.get('roi') if mode == 'draw' else None
    if not (isinstance(roi, list) and len(roi) == 4):
        roi = params.get('roi') if mode == 'draw' else None
    if not (isinstance(roi, list) and len(roi) == 4):
        return []
    try:
        x, y, w, h = [float(v) for v in roi]
    except (TypeError, ValueError):
        return []
    return [{
        'type': 'rect', 'x': x, 'y': y, 'w': w, 'h': h,
        'color': '#ff9800', 'width': 1.6,
    }, {
        'type': 'label', 'x': x + 4, 'y': y - 6,
        'text': '预ROI', 'color': '#ff9800',
    }]
