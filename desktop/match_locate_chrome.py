"""Match / locate denser score + candidate result chrome — soft OpenCV (no Halcon).

Industrial multi-candidate table (rank / score / Δmin / margin / pose / judge),
OK/NG overlays, filmstrip match density tags. Result chrome only — no
scoreboard/spark micro-prop cascade, no Comm/HMI cobind.
"""
from __future__ import annotations

from typing import Any


MATCH_OPS = ('locate', 'match', 'template_match')

OPERATOR_TAG = '配'
OPERATOR_LABEL = '模板匹配'


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
            'matches' in inner['result'] or 'items' in inner['result']
            or 'bestScore' in inner['result'] or 'found' in inner['result']
        ):
            return inner['result']
        if 'matches' in inner or 'items' in inner or 'bestScore' in inner:
            return inner
    if isinstance(bag.get('result'), dict) and (
        'matches' in bag['result'] or 'items' in bag['result']
        or 'bestScore' in bag['result']
    ):
        return bag['result']
    return bag


def extract_match_candidates(result: dict | None = None) -> list:
    """Prefer geom_find_chrome extractor when present; local fallback otherwise."""
    try:
        from desktop.geom_find_chrome import extract_match_items
        items = extract_match_items(result)
        if items:
            return items
    except Exception:
        pass
    bag = _unwrap_bag(result)
    items = bag.get('matches')
    if not isinstance(items, list):
        items = bag.get('items')
    return _as_list(items)


def chrome_badge(judge_ok=None, status=None, *, count: int | None = None,
                 best: float | None = None) -> str:
    """Compact badge: 配3✓ / 配2✗ / 配·."""
    mark = '·'
    if judge_ok is True or str(status or '').upper() in ('OK', 'PASS'):
        mark = '✓'
    elif judge_ok is False or str(status or '').upper() in ('NG', 'FAIL'):
        mark = '✗'
    n = int(count) if count is not None else None
    if n is not None and n >= 0:
        return f'{OPERATOR_TAG}{n}{mark}'
    if best is not None:
        try:
            return f'{OPERATOR_TAG}{float(best):.2f}{mark}'
        except (TypeError, ValueError):
            pass
    return f'{OPERATOR_TAG}{mark}'


def score_margin(score, jmin, jmax) -> dict:
    """Where score sits vs [jmin,jmax] and vs minScore floor."""
    sc = _f(score)
    lo = _f(jmin)
    hi = _f(jmax)
    out = {
        'score': sc,
        'judgeMin': lo,
        'judgeMax': hi,
        'inBand': None,
        'deltaLow': None,
        'deltaHigh': None,
        'margin': None,
        'ratio': None,
    }
    if sc is None:
        return out
    if lo is not None and hi is not None:
        out['inBand'] = lo <= sc <= hi
        out['deltaLow'] = sc - lo
        out['deltaHigh'] = hi - sc
        # margin to nearest edge (positive = inside)
        out['margin'] = min(sc - lo, hi - sc)
        span = hi - lo
        if span > 0:
            out['ratio'] = (sc - lo) / span
    elif lo is not None:
        out['inBand'] = sc >= lo
        out['deltaLow'] = sc - lo
        out['margin'] = sc - lo
    elif hi is not None:
        out['inBand'] = sc <= hi
        out['deltaHigh'] = hi - sc
        out['margin'] = hi - sc
    return out


def build_candidate_rows(matches=None, *, params: dict | None = None,
                         max_rows: int = 64) -> list:
    """Industrial multi-candidate density rows for locate/match result UX.

    Columns conceptually: # · rank · score · Δmin · margin · X · Y · angle · scale · judge
    """
    p = params if isinstance(params, dict) else {}
    judge_en = bool(p.get('resultJudgeEnable'))
    jmin = _f(p.get('resultJudgeMin'), 0.0)
    jmax = _f(p.get('resultJudgeMax'), 1.0)
    min_score = _f(p.get('minScore'), 0.0) or 0.0
    # when judge disabled, still compute Δmin vs minScore for density
    band_lo = jmin if judge_en else min_score
    band_hi = jmax if judge_en else 1.0

    # sort by score desc for rank (stable by index)
    raw = []
    for i, it in enumerate(_as_list(matches)):
        if not isinstance(it, dict):
            continue
        raw.append((i, it))
    raw_sorted = sorted(
        raw,
        key=lambda pair: (
            -(_f(pair[1].get('score'), -1.0) or -1.0),
            int(pair[1].get('index') or pair[0] + 1),
        ),
    )
    rank_of = {orig_i: rank + 1 for rank, (orig_i, _) in enumerate(raw_sorted)}

    rows = []
    for i, it in enumerate(_as_list(matches)[: max(1, int(max_rows))]):
        if not isinstance(it, dict):
            continue
        score = _f(it.get('score'))
        cx = it.get('centerX')
        cy = it.get('centerY')
        if cx is None or cy is None:
            c = it.get('center')
            if isinstance(c, (list, tuple)) and len(c) >= 2:
                cx, cy = c[0], c[1]
        cx_f, cy_f = _f(cx), _f(cy)
        ang = _f(it.get('angleDeg'))
        scale = _f(it.get('scale'))
        judge = it.get('judgeOk')
        status = it.get('judgeStatus')
        if judge is None and judge_en and score is not None:
            judge = bool(band_lo <= score <= band_hi)
            status = 'OK' if judge else 'NG'
        if status is None and judge is not None:
            status = 'OK' if judge else 'NG'
        band = score_margin(score, band_lo, band_hi)
        delta_min = None
        if score is not None:
            delta_min = score - min_score
        idx = int(it.get('index') or (i + 1))
        rows.append({
            'index': idx,
            'rank': rank_of.get(i, i + 1),
            'score': score,
            'deltaMin': delta_min,
            'margin': band.get('margin'),
            'bandRatio': band.get('ratio'),
            'inBand': band.get('inBand'),
            'x': cx_f,
            'y': cy_f,
            'angleDeg': ang,
            'scale': scale,
            'judgeOk': judge if judge is None else bool(judge),
            'judgeStatus': status or '—',
            'chrome': chrome_badge(judge, status, count=1),
            'polygon': it.get('polygon') or it.get('points'),
            'bbox': it.get('bbox') or it.get('box'),
            'raw': it,
        })
    return rows


CANDIDATE_COLUMNS = (
    '#', '排名', '分数', 'Δmin', '裕度', 'X', 'Y', '角度°', '缩放', '判定',
)


def format_row_cells(row: dict) -> list[str]:
    """10-cell industrial table texts for one candidate."""
    sc = row.get('score')
    sc_txt = f'{float(sc):.3f}' if sc is not None else '—'
    dmin = row.get('deltaMin')
    dmin_txt = f'{float(dmin):+.3f}' if dmin is not None else '—'
    mar = row.get('margin')
    mar_txt = f'{float(mar):+.3f}' if mar is not None else '—'
    x, y = row.get('x'), row.get('y')
    x_txt = f'{float(x):.1f}' if x is not None else '—'
    y_txt = f'{float(y):.1f}' if y is not None else '—'
    ang = row.get('angleDeg')
    ang_txt = f'{float(ang):.1f}' if ang is not None else '—'
    scale = row.get('scale')
    sca_txt = f'{float(scale):.3f}' if scale is not None else '—'
    return [
        str(row.get('index') or '—'),
        str(row.get('rank') or '—'),
        sc_txt,
        dmin_txt,
        mar_txt,
        x_txt,
        y_txt,
        ang_txt,
        sca_txt,
        str(row.get('judgeStatus') or '—'),
    ]


def overlay_flags(params: dict | None = None) -> list[str]:
    p = params if isinstance(params, dict) else {}
    flags = []
    for k, lab, default in (
        ('showMatchBox', '框', True),
        ('showScore', '分', True),
        ('showContour', '轮廓', True),
        ('showCross', '十字', True),
        ('showMatchIndex', '序号', True),
        ('showAngleDeg', '角', False),
        ('showSearchRegion', '搜索区', True),
        ('showOrigin', '原点', False),
        ('showFeaturePoints', '特征点', False),
        ('traceFullCanvas', '全画布', False),
    ):
        if p.get(k, default):
            flags.append(lab)
    return flags


def summarize_match_locate(result: dict | None = None, *,
                           params: dict | None = None) -> dict:
    """Dense locate/match result summary — scores / candidates / overlays."""
    p = params if isinstance(params, dict) else {}
    bag = _unwrap_bag(result)
    items = extract_match_candidates(result)
    rows = build_candidate_rows(items, params=p)
    scores = [r['score'] for r in rows if r.get('score') is not None]
    best = max(scores) if scores else _f(bag.get('bestScore') or bag.get('score'))
    ok_n = sum(1 for r in rows if r.get('judgeOk') is True)
    ng_n = sum(1 for r in rows if r.get('judgeOk') is False)
    judge = bag.get('judgeOk')
    if judge is None:
        if ng_n:
            judge = False
        elif rows and ok_n == len(rows):
            judge = True
        elif not p.get('resultJudgeEnable'):
            judge = True if rows else None
    status = bag.get('judgeStatus') or (
        'OK' if judge is True else ('NG' if judge is False else None)
    )
    count = len(rows)
    chrome = chrome_badge(judge, status, count=count, best=best)
    flags = overlay_flags(p)
    tip = [chrome, f'候选×{count}']
    if best is not None:
        tip.append(f'best={best:.3f}')
    if p.get('resultJudgeEnable'):
        tip.append(f'OK {ok_n}/NG {ng_n}')
        tip.append(
            f'T=[{_f(p.get("resultJudgeMin"), 0):.2f},{_f(p.get("resultJudgeMax"), 1):.2f}]'
        )
    min_score = _f(p.get('minScore'))
    if min_score is not None:
        tip.append(f'min={min_score:.2f}')
    if flags:
        tip.append('叠层:' + '·'.join(flags))
    return {
        'op': 'locate',
        'tag': OPERATOR_TAG,
        'label': OPERATOR_LABEL,
        'chrome': chrome,
        'count': count,
        'okCount': ok_n,
        'ngCount': ng_n,
        'bestScore': best,
        'judgeOk': judge,
        'judgeStatus': status,
        'judgeEnable': bool(p.get('resultJudgeEnable')),
        'judgeMin': _f(p.get('resultJudgeMin'), 0.0),
        'judgeMax': _f(p.get('resultJudgeMax'), 1.0),
        'minScore': min_score,
        'overlayFlags': flags,
        'summary': ' · '.join(str(t) for t in tip[:10]),
        'rows': rows,
        'columns': list(CANDIDATE_COLUMNS),
        'found': bool(bag.get('found')) if 'found' in bag else bool(rows),
    }


def judge_color(judge_ok=None) -> str:
    if judge_ok is True:
        return '#00d250'
    if judge_ok is False:
        return '#ff5252'
    return '#ffb400'


def build_match_overlays(result: dict | None = None, params: dict | None = None,
                         *, max_specs: int = 64) -> list:
    """Vector overlays for match candidates with OK/NG coloring."""
    p = params if isinstance(params, dict) else {}
    show_box = p.get('showMatchBox', True) not in (False, 0, 'false', 'False')
    show_contour = p.get('showContour', True) not in (False, 0, 'false', 'False')
    show_cross = p.get('showCross', True) not in (False, 0, 'false', 'False')
    show_score = p.get('showScore', True) not in (False, 0, 'false', 'False')
    show_idx = p.get('showMatchIndex', True) not in (False, 0, 'false', 'False')
    show_ang = p.get('showAngleDeg', False) not in (False, 0, 'false', 'False', None, '')
    rows = build_candidate_rows(extract_match_candidates(result), params=p)
    specs: list[dict[str, Any]] = []
    for r in rows:
        if len(specs) >= max_specs:
            break
        color = judge_color(r.get('judgeOk'))
        poly = r.get('polygon')
        if show_contour and isinstance(poly, list) and len(poly) >= 2:
            pts = []
            for pt in poly:
                if isinstance(pt, (list, tuple)) and len(pt) >= 2:
                    try:
                        pts.append([float(pt[0]), float(pt[1])])
                    except (TypeError, ValueError):
                        pass
            if len(pts) >= 2:
                specs.append({
                    'type': 'polygon', 'points': pts, 'color': color, 'width': 1.6,
                })
        bb = r.get('bbox')
        if show_box and isinstance(bb, (list, tuple)) and len(bb) >= 4:
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
        if show_cross and cx is not None and cy is not None:
            specs.append({
                'type': 'cross', 'x': float(cx), 'y': float(cy),
                'size': 10, 'color': color, 'width': 1.5,
            })
        if (show_score or show_idx or show_ang) and cx is not None and cy is not None:
            bits = []
            if show_idx:
                bits.append(f"#{r.get('index')}")
            if show_score and r.get('score') is not None:
                bits.append(f"{float(r['score']):.3f}")
            if show_ang and r.get('angleDeg') is not None:
                bits.append(f"{float(r['angleDeg']):.1f}°")
            st = r.get('judgeStatus')
            if st in ('OK', 'NG'):
                bits.append(st)
            if bits:
                specs.append({
                    'type': 'label',
                    'x': float(cx) + 8, 'y': float(cy) - 10,
                    'text': ' '.join(bits), 'color': color,
                })
    return specs[:max_specs]


def soft_demo_matches(n: int = 5, *, ok: bool = True,
                      min_score: float = 0.70) -> list:
    """Deterministic multi-candidate soft demo (no hardware)."""
    n = max(1, min(int(n or 1), 16))
    out = []
    for i in range(n):
        score = round(0.97 - i * 0.045, 3)
        j = (score >= min_score) if ok else (i == 0 and score >= min_score)
        if not ok and i >= max(1, n - 2):
            j = False
            score = round(min_score - 0.08 - i * 0.01, 3)
        w, h = 48.0 + i, 36.0 + i * 0.5
        cx, cy = 120.0 + i * 28, 90.0 + i * 12
        out.append({
            'index': i + 1,
            'score': score,
            'centerX': cx,
            'centerY': cy,
            'center': [cx, cy],
            'angleDeg': -8.0 + i * 3.0,
            'scale': round(1.0 + i * 0.015, 3),
            'bbox': [cx - w / 2, cy - h / 2, w, h],
            'polygon': [
                [cx - w / 2, cy - h / 2],
                [cx + w / 2, cy - h / 2],
                [cx + w / 2, cy + h / 2],
                [cx - w / 2, cy + h / 2],
            ],
            'judgeOk': j,
            'judgeStatus': 'OK' if j else 'NG',
        })
    return out


def soft_demo_match_result(*, n: int = 5, ok: bool = True,
                           min_score: float = 0.70,
                           judge_enable: bool = True) -> dict:
    matches = soft_demo_matches(n=n, ok=ok, min_score=min_score)
    best = max((m['score'] for m in matches), default=None)
    judge_all = all(m.get('judgeOk') for m in matches) if matches else False
    return {
        'found': bool(matches),
        'count': len(matches),
        'matches': matches,
        'items': matches,
        'bestScore': best,
        'score': best,
        'judgeEnable': bool(judge_enable),
        'judgeOk': bool(judge_all) if judge_enable else True,
        'judgeStatus': 'OK' if (judge_all if judge_enable else True) else 'NG',
        'judgeMin': min_score if judge_enable else None,
        'judgeMax': 1.0 if judge_enable else None,
        'note': '软演示多候选匹配 · 无 Halcon',
    }


def match_records_from_run(last_result: dict | None = None) -> list:
    if not isinstance(last_result, dict):
        return []
    out = []
    for rec in last_result.get('results') or []:
        if not isinstance(rec, dict):
            continue
        op = str(rec.get('operation') or rec.get('op') or '')
        if op not in MATCH_OPS:
            bag = _unwrap_bag(rec)
            if not (bag.get('matches') or bag.get('items') or 'bestScore' in bag):
                continue
            op = op or 'locate'
        summ = summarize_match_locate(rec, params={})
        summ['id'] = str(rec.get('id') or '')
        summ['name'] = str(rec.get('name') or OPERATOR_LABEL)
        summ['operation'] = op
        out.append(summ)
    return out


def chrome_map_from_film_cache(cache: dict | None = None,
                               project_steps=None) -> dict:
    """path → 配N✓ / 配N✗ for filmstrip match density (result chrome)."""
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
            if op not in MATCH_OPS:
                # accept bags that look like locate results
                ub = _unwrap_bag(rec)
                if not (ub.get('matches') or ub.get('items') or 'bestScore' in ub):
                    continue
                op = 'locate'
            params = step.get('params') if isinstance(step.get('params'), dict) else {}
            summ = summarize_match_locate(rec, params=params)
            badge = summ.get('chrome') or ''
            if badge:
                break
        if badge:
            chrome[key] = str(badge)[:16]
    return chrome


def okng_map_from_film_cache(cache: dict | None = None,
                             project_steps=None) -> dict:
    """path → OK|NG from match/locate judge (filmstrip density, not spark)."""
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
            if op not in MATCH_OPS and not extract_match_candidates(rec):
                continue
            params = step.get('params') if isinstance(step.get('params'), dict) else {}
            summ = summarize_match_locate(rec, params=params)
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
        for r in match_records_from_run(bag):
            # re-summarize with step params when available
            sid = r.get('id') or ''
            params = {}
            for s in (project_steps or []):
                if isinstance(s, dict) and str(s.get('id') or '') == sid:
                    params = s.get('params') if isinstance(s.get('params'), dict) else {}
                    break
            if params:
                # find original rec
                for rec in bag.get('results') or []:
                    if isinstance(rec, dict) and str(rec.get('id') or '') == sid:
                        r = summarize_match_locate(rec, params=params)
                        r['name'] = str(rec.get('name') or OPERATOR_LABEL)
                        break
            name = r.get('name') or OPERATOR_LABEL
            bits.append(f"{name} {r.get('chrome')}")
    if not bits:
        return ''
    head = f'匹配定位 · {len(bits)}'
    body = ' ｜ '.join(bits[:8])
    if len(bits) > 8:
        body += f' ｜ …+{len(bits) - 8}'
    return f'{head} · {body}'
