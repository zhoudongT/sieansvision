"""Geometry-find (non-measure) result chrome helpers — soft / no Halcon / no spark cascade.

Distinct from measure caliper-chain OK/NG badges: feature-typed tags (L/C/R/B/E)
plus count and judge for filmstrip thumbs and panel density tables.
Also soft multi-match density rows for locate/template-match result UX.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

FEATURE_TAGS = {
    'lines': 'L',
    'edges': 'E',
    'circles': 'C',
    'rects': 'R',
    'contours': 'B',  # blob-ish contour find
    'blob': 'B',
}

FEATURE_LABELS = {
    'lines': '直线',
    'edges': '边缘',
    'circles': '圆',
    'rects': '矩形',
    'contours': '轮廓/斑点',
    'blob': '斑点',
}


def feature_tag(feature: str | None) -> str:
    f = str(feature or 'lines').lower()
    return FEATURE_TAGS.get(f, 'G')


def _as_list(v) -> list:
    if isinstance(v, list):
        return v
    return []


def extract_geom_items(result: dict | None) -> tuple[str, list]:
    """Pull (feature, items[]) from a geometry engine/module result bag."""
    if not isinstance(result, dict):
        return 'lines', []
    # unwrap record.output.result / record.outputs / record.result
    bag = result
    for key in ('output', 'outputs', 'result'):
        inner = bag.get(key) if isinstance(bag.get(key), dict) else None
        if inner is None:
            continue
        has_payload = (
            'items' in inner or 'feature' in inner
            or any(k in inner for k in ('lines', 'circles', 'rects', 'contours', 'edges'))
            or isinstance(inner.get('result'), dict)
        )
        if not has_payload:
            continue
        bag = inner
        if key in ('output', 'outputs') and isinstance(inner.get('result'), dict):
            bag = inner['result']
        break
    if 'result' in bag and isinstance(bag['result'], dict) and (
        'items' in bag['result'] or 'feature' in bag['result']
        or any(k in bag['result'] for k in ('lines', 'circles', 'rects', 'contours', 'edges'))
    ):
        bag = bag['result']
    feat = str(bag.get('feature') or '')
    items = bag.get('items')
    if not isinstance(items, list):
        for k in ('lines', 'circles', 'rects', 'contours', 'edges'):
            if isinstance(bag.get(k), list):
                items = bag[k]
                feat = feat or k
                break
    if not feat:
        feat = 'lines'
    return feat, _as_list(items)


def item_metric(it: dict, feature: str) -> tuple[str, float | None]:
    """Primary metric label+value for a geometry-find item (non-measure)."""
    if not isinstance(it, dict):
        return '—', None
    f = str(feature or '').lower()
    if f in ('lines', 'edges'):
        if it.get('lengthPixels') is not None:
            try:
                return 'len', float(it['lengthPixels'])
            except (TypeError, ValueError):
                pass
        if it.get('score') is not None:
            try:
                return 'score', float(it['score'])
            except (TypeError, ValueError):
                pass
    if f == 'circles':
        if it.get('radiusPixels') is not None:
            try:
                return 'r', float(it['radiusPixels'])
            except (TypeError, ValueError):
                pass
    if f == 'rects':
        if it.get('areaPixels') is not None:
            try:
                return 'area', float(it['areaPixels'])
            except (TypeError, ValueError):
                pass
        if it.get('widthPixels') is not None:
            try:
                return 'w', float(it['widthPixels'])
            except (TypeError, ValueError):
                pass
    if f in ('contours', 'blob'):
        if it.get('areaPixels') is not None:
            try:
                return 'area', float(it['areaPixels'])
            except (TypeError, ValueError):
                pass
    if it.get('judgeMetric') is not None:
        try:
            return 'm', float(it['judgeMetric'])
        except (TypeError, ValueError):
            pass
    if it.get('score') is not None:
        try:
            return 'score', float(it['score'])
        except (TypeError, ValueError):
            pass
    return '—', None


def build_geom_find_rows(items=None, feature: str = 'lines', *, max_rows: int = 64) -> list:
    """Dense table rows for geometry-find result UX."""
    rows = []
    for i, it in enumerate(_as_list(items)[: max(1, int(max_rows))]):
        if not isinstance(it, dict):
            continue
        mlab, mval = item_metric(it, feature)
        score = it.get('score')
        try:
            score_f = float(score) if score is not None else None
        except (TypeError, ValueError):
            score_f = None
        rms = it.get('rmsPixels')
        try:
            rms_f = float(rms) if rms is not None else None
        except (TypeError, ValueError):
            rms_f = None
        ang = it.get('angleDeg')
        try:
            ang_f = float(ang) if ang is not None else None
        except (TypeError, ValueError):
            ang_f = None
        judge = it.get('judgeOk')
        status = it.get('judgeStatus')
        if status is None and judge is not None:
            status = 'OK' if judge else 'NG'
        # contour/blob extras (soft density)
        cx = cy = peri = fill = circ = None
        if str(feature or '').lower() in ('contours', 'blob'):
            try:
                cx = float(it['centerX']) if it.get('centerX') is not None else None
            except (TypeError, ValueError):
                cx = None
            try:
                cy = float(it['centerY']) if it.get('centerY') is not None else None
            except (TypeError, ValueError):
                cy = None
            if cx is None or cy is None:
                c = it.get('center')
                if isinstance(c, (list, tuple)) and len(c) >= 2:
                    try:
                        cx, cy = float(c[0]), float(c[1])
                    except (TypeError, ValueError):
                        pass
            if cx is None:
                bb = it.get('bbox')
                if isinstance(bb, (list, tuple)) and len(bb) >= 4:
                    try:
                        cx = float(bb[0]) + float(bb[2]) / 2.0
                        cy = float(bb[1]) + float(bb[3]) / 2.0
                    except (TypeError, ValueError):
                        pass
            try:
                peri = float(it['perimeterPixels']) if it.get('perimeterPixels') is not None else None
            except (TypeError, ValueError):
                peri = None
            try:
                fill = float(it['fillRatio']) if it.get('fillRatio') is not None else None
            except (TypeError, ValueError):
                fill = None
            try:
                circ = float(it['circularity']) if it.get('circularity') is not None else None
            except (TypeError, ValueError):
                circ = None
            if circ is None and mval and peri and peri > 0:
                # 4πA/P² soft estimate
                try:
                    circ = float(4.0 * 3.141592653589793 * float(mval) / (float(peri) ** 2))
                except (TypeError, ValueError, ZeroDivisionError):
                    circ = None
        rows.append({
            'index': int(it.get('index') or it.get('lineIndex') or (i + 1)),
            'feature': feature,
            'metricLabel': mlab,
            'metric': mval,
            'score': score_f,
            'rms': rms_f,
            'angleDeg': ang_f,
            'centerX': cx,
            'centerY': cy,
            'perimeter': peri,
            'fillRatio': fill,
            'circularity': circ,
            'judgeOk': judge if judge is None else bool(judge),
            'judgeStatus': status or '—',
            'raw': it,
        })
    return rows


def summarize_geom_find_result(result: dict | None = None) -> dict:
    """Filmstrip/panel summary for one geometry-find module result."""
    feat, items = extract_geom_items(result)
    rows = build_geom_find_rows(items, feat)
    ok_n = sum(1 for r in rows if r.get('judgeOk') is True)
    ng_n = sum(1 for r in rows if r.get('judgeOk') is False)
    scores = [r['score'] for r in rows if r.get('score') is not None]
    best = max(scores) if scores else None
    tag = feature_tag(feat)
    count = len(rows)
    judge = None
    if isinstance(result, dict):
        bag = result
        if isinstance(bag.get('result'), dict):
            bag = bag['result']
        if isinstance(bag.get('output'), dict) and isinstance(bag['output'].get('result'), dict):
            bag = bag['output']['result']
        if 'judgeOk' in bag:
            judge = bool(bag.get('judgeOk'))
    if judge is None:
        if ng_n:
            judge = False
        elif ok_n and ok_n == count:
            judge = True
    mark = ''
    if judge is True:
        mark = '✓'
    elif judge is False:
        mark = '✗'
    chrome = f'{tag}{count}{mark}' if count or mark else tag
    label = FEATURE_LABELS.get(feat, feat)
    summary = f'{label}查找 · {tag}×{count}'
    if best is not None:
        summary += f' · best={best:.3f}'
    if judge is True:
        summary += ' · OK'
    elif judge is False:
        summary += f' · NG({ng_n})'
    return {
        'feature': feat,
        'tag': tag,
        'count': count,
        'okCount': ok_n,
        'ngCount': ng_n,
        'bestScore': best,
        'judgeOk': judge,
        'chrome': chrome,
        'summary': summary,
        'rows': rows,
        'label': label,
    }


def geom_find_records_from_run(last_result: dict | None = None) -> list:
    """Collect geometry-find module summaries from a full run last_result."""
    if not isinstance(last_result, dict):
        return []
    records = last_result.get('results') or []
    out = []
    for rec in records:
        if not isinstance(rec, dict):
            continue
        op = str(rec.get('operation') or rec.get('op') or '')
        if op not in ('geometry', 'blob'):
            # also accept nested output.feature
            out_bag = rec.get('output') if isinstance(rec.get('output'), dict) else {}
            res = out_bag.get('result') if isinstance(out_bag.get('result'), dict) else out_bag
            if not (isinstance(res, dict) and (res.get('feature') or res.get('items'))):
                continue
        summ = summarize_geom_find_result(rec)
        summ['id'] = str(rec.get('id') or '')
        summ['name'] = str(rec.get('name') or summ.get('label') or '')
        summ['operation'] = op or 'geometry'
        out.append(summ)
    return out


def chrome_map_from_film_cache(cache: dict | None = None) -> dict:
    """path → chrome tag (e.g. L3✓) for geometry-find, distinct from measure OK/NG."""
    chrome = {}
    for path, bag in (cache or {}).items():
        key = str(path or '').strip()
        if not key or not isinstance(bag, dict):
            continue
        records = geom_find_records_from_run(bag)
        if not records:
            continue
        # Prefer first geometry record; compose multi as L3+C2
        bits = [r.get('chrome') for r in records if r.get('chrome')]
        if not bits:
            continue
        joined = '+'.join(bits[:3])
        if len(bits) > 3:
            joined += f'+{len(bits)-3}'
        chrome[key] = joined[:16]
    return chrome


def strip_summary_from_film_cache(cache: dict | None = None, *, current_path: str = '') -> str:
    """HTML-ish plain summary for geom-find strip under filmstrip."""
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
        for r in geom_find_records_from_run(bag):
            name = r.get('name') or r.get('label') or '几何'
            bits.append(f"{name} {r.get('chrome')}")
    if not bits:
        return ''
    head = f'几何查找 · {len(bits)}'
    body = ' ｜ '.join(bits[:8])
    if len(bits) > 8:
        body += f' ｜ …+{len(bits)-8}'
    return f'{head} · {body}'


# ----- soft multi-match density (locate / template-match) -----

def extract_match_items(result: dict | None = None) -> list:
    if not isinstance(result, dict):
        return []
    bag = result
    for key in ('output', 'outputs', 'result'):
        inner = bag.get(key) if isinstance(bag.get(key), dict) else None
        if inner is None:
            continue
        if 'matches' in inner or 'items' in inner or 'bestScore' in inner:
            bag = inner
            if key == 'output' and isinstance(inner.get('result'), dict):
                bag = inner['result']
            break
    if isinstance(bag.get('result'), dict) and (
        'matches' in bag['result'] or 'items' in bag['result']
    ):
        bag = bag['result']
    items = bag.get('matches')
    if not isinstance(items, list):
        items = bag.get('items')
    return _as_list(items)


def build_multi_match_rows(matches=None, *, max_rows: int = 50,
                           judge_enable: bool = False,
                           judge_min: float = 0.0,
                           judge_max: float = 1.0) -> list:
    rows = []
    for i, it in enumerate(_as_list(matches)[: max(1, int(max_rows))]):
        if not isinstance(it, dict):
            continue
        try:
            score = float(it.get('score')) if it.get('score') is not None else None
        except (TypeError, ValueError):
            score = None
        cx = it.get('centerX', (it.get('center') or [None, None])[0] if isinstance(it.get('center'), (list, tuple)) else None)
        cy = it.get('centerY', (it.get('center') or [None, None])[1] if isinstance(it.get('center'), (list, tuple)) else None)
        try:
            cx_f = float(cx) if cx is not None else None
        except (TypeError, ValueError):
            cx_f = None
        try:
            cy_f = float(cy) if cy is not None else None
        except (TypeError, ValueError):
            cy_f = None
        try:
            ang = float(it.get('angleDeg')) if it.get('angleDeg') is not None else None
        except (TypeError, ValueError):
            ang = None
        try:
            scale = float(it.get('scale')) if it.get('scale') is not None else None
        except (TypeError, ValueError):
            scale = None
        judge = it.get('judgeOk')
        status = it.get('judgeStatus')
        if judge is None and judge_enable and score is not None:
            judge = bool(judge_min <= score <= judge_max)
            status = 'OK' if judge else 'NG'
        if status is None and judge is not None:
            status = 'OK' if judge else 'NG'
        rows.append({
            'index': int(it.get('index') or (i + 1)),
            'score': score,
            'x': cx_f,
            'y': cy_f,
            'angleDeg': ang,
            'scale': scale,
            'judgeOk': judge if judge is None else bool(judge),
            'judgeStatus': status or '—',
            'raw': it,
        })
    return rows


def summarize_multi_match(result: dict | None = None, *, params: dict | None = None) -> dict:
    """Dense locate/match result summary (scores / multi-match table), no spark cascade."""
    p = params or {}
    items = extract_match_items(result)
    judge_en = bool(p.get('resultJudgeEnable'))
    try:
        jmin = float(p.get('resultJudgeMin') or 0)
        jmax = float(p.get('resultJudgeMax') or 1)
    except (TypeError, ValueError):
        jmin, jmax = 0.0, 1.0
    rows = build_multi_match_rows(
        items, judge_enable=judge_en, judge_min=jmin, judge_max=jmax,
    )
    scores = [r['score'] for r in rows if r.get('score') is not None]
    best = max(scores) if scores else None
    if best is None and isinstance(result, dict):
        bag = result.get('result') if isinstance(result.get('result'), dict) else result
        if isinstance(bag.get('output'), dict) and isinstance(bag['output'].get('result'), dict):
            bag = bag['output']['result']
        try:
            best = float(bag.get('bestScore')) if bag.get('bestScore') is not None else None
        except (TypeError, ValueError):
            best = None
    ok_n = sum(1 for r in rows if r.get('judgeOk') is True)
    ng_n = sum(1 for r in rows if r.get('judgeOk') is False)
    overlay_flags = []
    for k, lab in (
        ('showMatchBox', '框'), ('showScore', '分'), ('showContour', '轮廓'),
        ('showCross', '十字'), ('showMatchIndex', '序号'), ('showAngleDeg', '角'),
        ('showSearchRegion', '搜索区'), ('showOrigin', '原点'),
        ('showFeaturePoints', '特征点'), ('traceFullCanvas', '全画布'),
    ):
        default_on = k in (
            'showMatchBox', 'showScore', 'showContour', 'showCross',
            'showMatchIndex', 'showSearchRegion',
        )
        if p.get(k, default_on):
            overlay_flags.append(lab)
    summary = f'匹配×{len(rows)}'
    if best is not None:
        summary += f' · best={best:.3f}'
    if judge_en:
        summary += f' · 判定OK {ok_n}/NG {ng_n}'
    if overlay_flags:
        summary += ' · 叠层:' + '·'.join(overlay_flags)
    return {
        'count': len(rows),
        'bestScore': best,
        'okCount': ok_n,
        'ngCount': ng_n,
        'rows': rows,
        'overlayFlags': overlay_flags,
        'summary': summary,
        'judgeEnable': judge_en,
        'judgeMin': jmin,
        'judgeMax': jmax,
    }


def soft_demo_geom_items(feature: str = 'lines', n: int = 3) -> list:
    """Deterministic soft demo items for panel empty-state density (no hardware)."""
    f = str(feature or 'lines').lower()
    n = max(1, min(int(n or 1), 8))
    items = []
    for i in range(n):
        if f in ('lines', 'edges'):
            items.append({
                'index': i + 1, 'lengthPixels': 80.0 + i * 12,
                'angleDeg': 5.0 * i, 'score': 0.92 - i * 0.04,
                'rmsPixels': 0.4 + i * 0.1, 'judgeOk': i < n - 1,
                'judgeStatus': 'OK' if i < n - 1 else 'NG',
            })
        elif f == 'circles':
            items.append({
                'index': i + 1, 'center': [100.0 + i * 20, 80.0 + i * 10],
                'radiusPixels': 18.0 + i * 3, 'score': 0.9 - i * 0.05,
                'judgeOk': True, 'judgeStatus': 'OK',
            })
        elif f == 'rects':
            items.append({
                'index': i + 1, 'center': [50.0 + i * 15, 40.0],
                'widthPixels': 30 + i * 2, 'heightPixels': 40 + i,
                'areaPixels': (30 + i * 2) * (40 + i), 'angleDeg': i * 2.0,
                'judgeOk': True, 'judgeStatus': 'OK',
            })
        else:
            # contours / blob soft demo — industrial density fields
            bx, by = 20 + i * 35, 30 + i * 12
            bw, bh = 28 + i * 4, 24 + i * 3
            area = float(bw * bh) * (0.72 + i * 0.04)
            peri = 2.0 * (bw + bh) * 0.9
            items.append({
                'index': i + 1,
                'bbox': [bx, by, bw, bh],
                'areaPixels': area,
                'perimeterPixels': peri,
                'centerX': bx + bw / 2.0,
                'centerY': by + bh / 2.0,
                'fillRatio': round(area / max(1.0, float(bw * bh)), 3),
                'circularity': round(4.0 * 3.141592653589793 * area / max(1.0, peri ** 2), 3),
                'points': [
                    [bx, by], [bx + bw, by], [bx + bw, by + bh], [bx, by + bh],
                ],
                'judgeOk': i < n - 1 or n == 1,
                'judgeStatus': 'OK' if (i < n - 1 or n == 1) else 'NG',
            })
    return items


def soft_demo_matches(n: int = 4) -> list:
    n = max(1, min(int(n or 1), 12))
    out = []
    for i in range(n):
        out.append({
            'index': i + 1,
            'score': round(0.97 - i * 0.03, 3),
            'centerX': 120.0 + i * 15,
            'centerY': 90.0 + i * 8,
            'angleDeg': -5.0 + i * 2.5,
            'scale': round(1.0 + i * 0.02, 3),
            'judgeOk': i < 3,
            'judgeStatus': 'OK' if i < 3 else 'NG',
        })
    return out



def build_contour_blob_overlays(items=None, feature: str = 'contours', *,
                                max_items: int = 32,
                                show_poly: bool = True,
                                show_bbox: bool = True,
                                show_cross: bool = True,
                                show_labels: bool = True,
                                color_ok: str = '#00d250',
                                color_ng: str = '#ff4d4f') -> list:
    """Vector overlays for soft contour/blob find (polygon + bbox + cross)."""
    specs = []
    f = str(feature or 'contours').lower()
    for i, it in enumerate(_as_list(items)[: max(1, int(max_items))]):
        if not isinstance(it, dict):
            continue
        ok = it.get('judgeOk')
        color = color_ok if ok is not False else color_ng
        pts = it.get('points')
        if show_poly and isinstance(pts, list) and len(pts) >= 2:
            poly = []
            for p in pts:
                if isinstance(p, (list, tuple)) and len(p) >= 2:
                    try:
                        poly.append([float(p[0]), float(p[1])])
                    except (TypeError, ValueError):
                        pass
            if len(poly) >= 2:
                specs.append({'type': 'polygon', 'points': poly, 'color': color, 'width': 1.5})
        bb = it.get('bbox')
        if show_bbox and isinstance(bb, (list, tuple)) and len(bb) >= 4:
            try:
                specs.append({
                    'type': 'rect',
                    'x': float(bb[0]), 'y': float(bb[1]),
                    'w': float(bb[2]), 'h': float(bb[3]),
                    'color': color, 'width': 1.5,
                })
            except (TypeError, ValueError):
                pass
        cx = it.get('centerX')
        cy = it.get('centerY')
        if cx is None or cy is None:
            c = it.get('center')
            if isinstance(c, (list, tuple)) and len(c) >= 2:
                cx, cy = c[0], c[1]
        if cx is None and isinstance(bb, (list, tuple)) and len(bb) >= 4:
            try:
                cx = float(bb[0]) + float(bb[2]) / 2.0
                cy = float(bb[1]) + float(bb[3]) / 2.0
            except (TypeError, ValueError):
                cx = cy = None
        if show_cross and cx is not None and cy is not None:
            try:
                specs.append({
                    'type': 'cross', 'x': float(cx), 'y': float(cy),
                    'size': 8, 'color': color, 'width': 1.5,
                })
            except (TypeError, ValueError):
                pass
        if show_labels and cx is not None and cy is not None:
            idx = it.get('index') or (i + 1)
            area = it.get('areaPixels')
            lab = f'#{idx}'
            if area is not None:
                try:
                    lab += f' {float(area):.0f}px'
                except (TypeError, ValueError):
                    pass
            try:
                specs.append({
                    'type': 'label', 'x': float(cx) + 6, 'y': float(cy) - 8,
                    'text': lab, 'color': color,
                })
            except (TypeError, ValueError):
                pass
    return specs
