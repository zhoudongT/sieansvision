"""Unified image overlay density for find / match / contour / color (soft).

Not filmstrip spark micro-props — canvas vector overlays only.
Consumes geometry-find, locate/match, contour/blob, and sieans-regions results.
"""
from __future__ import annotations

from typing import Any


DEFAULT_CAP = 48
COLORS = (
    '#00d250', '#00bcd4', '#ffb400', '#7c4dff', '#ff5252', '#26a69a',
)


def _as_list(v) -> list:
    return v if isinstance(v, list) else []


def _step_map(project) -> dict:
    steps = []
    if isinstance(project, dict):
        steps = project.get('steps') or []
    elif project is not None:
        steps = getattr(project, 'get', lambda *_: None)('steps') or []
    return {str(s.get('id') or ''): s for s in steps if isinstance(s, dict)}


def _unwrap(rec: dict) -> dict:
    bag = rec
    out = bag.get('output') if isinstance(bag.get('output'), dict) else None
    if out is not None:
        if isinstance(out.get('result'), dict):
            return out['result']
        return out
    if isinstance(bag.get('result'), dict):
        return bag['result']
    return bag if isinstance(bag, dict) else {}


def _color_cycle(i: int, ok=None) -> str:
    if ok is False:
        return '#ff5252'
    return COLORS[i % len(COLORS)]


def overlays_from_geometry_item(it: dict, feature: str, *, index: int = 0,
                                show_labels: bool = True) -> list:
    specs = []
    f = str(feature or '').lower()
    ok = it.get('judgeOk')
    color = _color_cycle(index, ok)
    if f in ('lines', 'edges'):
        # line may be x1,y1,x2,y2 or points
        if it.get('x1') is not None and it.get('x2') is not None:
            specs.append({
                'type': 'line',
                'x1': float(it['x1']), 'y1': float(it['y1']),
                'x2': float(it['x2']), 'y2': float(it['y2']),
                'color': color, 'width': 1.8,
            })
        pts = it.get('points')
        if isinstance(pts, list) and len(pts) >= 2 and not specs:
            try:
                specs.append({
                    'type': 'line',
                    'x1': float(pts[0][0]), 'y1': float(pts[0][1]),
                    'x2': float(pts[-1][0]), 'y2': float(pts[-1][1]),
                    'color': color, 'width': 1.8,
                })
            except (TypeError, ValueError, IndexError):
                pass
    elif f == 'circles':
        c = it.get('center')
        r = it.get('radiusPixels') or it.get('radius')
        cx = cy = None
        if isinstance(c, (list, tuple)) and len(c) >= 2:
            cx, cy = c[0], c[1]
        if cx is None:
            cx, cy = it.get('centerX'), it.get('centerY')
        if cx is not None and cy is not None and r is not None:
            specs.append({
                'type': 'ellipse',
                'x': float(cx), 'y': float(cy),
                'rx': float(r), 'ry': float(r),
                'color': color, 'width': 1.8,
            })
            specs.append({
                'type': 'cross', 'x': float(cx), 'y': float(cy),
                'size': 7, 'color': color, 'width': 1.2,
            })
    elif f == 'rects':
        bb = it.get('bbox')
        if isinstance(bb, (list, tuple)) and len(bb) >= 4:
            specs.append({
                'type': 'rect',
                'x': float(bb[0]), 'y': float(bb[1]),
                'w': float(bb[2]), 'h': float(bb[3]),
                'color': color, 'width': 1.6,
            })
        elif it.get('x') is not None and it.get('width') is not None:
            specs.append({
                'type': 'rect',
                'x': float(it['x']), 'y': float(it['y']),
                'w': float(it['width']), 'h': float(it['height']),
                'color': color, 'width': 1.6,
            })
    elif f in ('contours', 'blob'):
        try:
            from desktop.geom_find_chrome import build_contour_blob_overlays
            return build_contour_blob_overlays(
                [it], feature=f, max_items=1,
                show_poly=True, show_bbox=True, show_cross=True, show_labels=show_labels,
                color_ok=color, color_ng='#ff5252',
            )
        except Exception:
            bb = it.get('bbox')
            if isinstance(bb, (list, tuple)) and len(bb) >= 4:
                specs.append({
                    'type': 'rect',
                    'x': float(bb[0]), 'y': float(bb[1]),
                    'w': float(bb[2]), 'h': float(bb[3]),
                    'color': color, 'width': 1.5,
                })
    if show_labels and specs:
        # label near first geometry
        idx = it.get('index') or (index + 1)
        anchor = specs[0]
        lx = ly = None
        if anchor.get('type') == 'line':
            lx = (float(anchor['x1']) + float(anchor['x2'])) / 2
            ly = (float(anchor['y1']) + float(anchor['y2'])) / 2
        elif anchor.get('type') in ('ellipse', 'cross', 'point'):
            lx, ly = float(anchor.get('x', 0)), float(anchor.get('y', 0))
        elif anchor.get('type') == 'rect':
            lx = float(anchor['x']) + 2
            ly = float(anchor['y']) - 2
        if lx is not None:
            specs.append({
                'type': 'label', 'x': lx + 4, 'y': ly - 6,
                'text': f'#{idx}', 'color': color,
            })
    return specs


def overlays_from_match_item(it: dict, *, index: int = 0,
                             show_box: bool = True,
                             show_cross: bool = True,
                             show_labels: bool = True,
                             show_score: bool = True) -> list:
    specs = []
    ok = it.get('judgeOk')
    color = _color_cycle(index, ok)
    cx = it.get('centerX')
    cy = it.get('centerY')
    if cx is None:
        c = it.get('center')
        if isinstance(c, (list, tuple)) and len(c) >= 2:
            cx, cy = c[0], c[1]
    w = it.get('width') or it.get('w') or it.get('templateWidth')
    h = it.get('height') or it.get('h') or it.get('templateHeight')
    bb = it.get('bbox') or it.get('box')
    if show_box and isinstance(bb, (list, tuple)) and len(bb) >= 4:
        specs.append({
            'type': 'rect',
            'x': float(bb[0]), 'y': float(bb[1]),
            'w': float(bb[2]), 'h': float(bb[3]),
            'color': color, 'width': 1.6,
        })
    elif show_box and cx is not None and cy is not None and w and h:
        specs.append({
            'type': 'rect',
            'x': float(cx) - float(w) / 2, 'y': float(cy) - float(h) / 2,
            'w': float(w), 'h': float(h),
            'color': color, 'width': 1.6,
        })
    if show_cross and cx is not None and cy is not None:
        specs.append({
            'type': 'cross', 'x': float(cx), 'y': float(cy),
            'size': 10, 'color': color, 'width': 1.5,
        })
    if (show_labels or show_score) and cx is not None and cy is not None:
        idx = it.get('index') or (index + 1)
        bits = [f'#{idx}']
        if show_score and it.get('score') is not None:
            try:
                bits.append(f"{float(it['score']):.3f}")
            except (TypeError, ValueError):
                pass
        specs.append({
            'type': 'label', 'x': float(cx) + 8, 'y': float(cy) - 10,
            'text': ' '.join(bits), 'color': color,
        })
    return specs


def build_unified_overlays(records=None, project=None, *,
                           max_specs: int = 200,
                           max_per_module: int = DEFAULT_CAP) -> list:
    """Build combined overlay specs from a run's module records."""
    steps = _step_map(project)
    specs: list = []
    for rec in records or []:
        if not isinstance(rec, dict):
            continue
        if len(specs) >= max_specs:
            break
        sid = str(rec.get('id') or '')
        step = steps.get(sid) or {}
        op = str(step.get('operation') or rec.get('operation') or '')
        params = step.get('params') if isinstance(step.get('params'), dict) else {}
        # skip if overlay explicitly off
        if params.get('showOverlay') in (False, 0, 'false', 'False'):
            continue
        bag = _unwrap(rec)
        show_labels = params.get('showLabels', True) not in (False, 0, 'false')
        show_pts = params.get('showPoints', True) not in (False, 0, 'false')

        if op in ('geometry', 'rect_find', 'blob') or bag.get('feature'):
            feat = str(params.get('feature') or bag.get('feature') or 'lines')
            if op == 'rect_find':
                feat = 'rects'
            items = bag.get('items')
            if not isinstance(items, list):
                items = bag.get(feat) if isinstance(bag.get(feat), list) else []
            for i, it in enumerate(_as_list(items)[:max_per_module]):
                if not isinstance(it, dict):
                    continue
                specs.extend(overlays_from_geometry_item(
                    it, feat, index=i, show_labels=show_labels and show_pts,
                ))
                if len(specs) >= max_specs:
                    break
            continue

        if op in ('locate', 'match', 'template_match'):
            items = bag.get('matches')
            if not isinstance(items, list):
                items = bag.get('items')
            show_box = params.get('showMatchBox', True) not in (False, 0, 'false')
            show_cross = params.get('showCross', True) not in (False, 0, 'false')
            show_score = params.get('showScore', True) not in (False, 0, 'false')
            for i, it in enumerate(_as_list(items)[:max_per_module]):
                if not isinstance(it, dict):
                    continue
                specs.extend(overlays_from_match_item(
                    it, index=i, show_box=show_box, show_cross=show_cross,
                    show_labels=show_labels, show_score=show_score,
                ))
                if len(specs) >= max_specs:
                    break
            continue

        # sieans-regions plugin / color / blobs
        plugin_id = str(params.get('pluginId') or '')
        looks = (
            plugin_id == 'sieans-regions'
            or (isinstance(bag.get('items'), list) and 'coveragePercent' in bag)
            or op in ('color', 'regions')
        )
        if looks or (op == 'plugin' and isinstance(bag.get('items'), list)
                     and bag.get('count') is not None):
            try:
                from desktop.region_color_chrome import build_region_overlays
                args = params.get('arguments') if isinstance(params.get('arguments'), dict) else {}
                show_box = args.get('showBox', params.get('showOverlay', True)) not in (False, 0, 'false')
                region_specs = build_region_overlays(
                    bag.get('items'),
                    max_items=max_per_module,
                    show_box=show_box,
                    show_cross=True,
                    show_labels=show_labels,
                    show_ellipse=bool(params.get('showEllipse') or args.get('showEllipse')),
                    roi=bag.get('roi') if isinstance(bag.get('roi'), dict) else None,
                )
                specs.extend(region_specs)
            except Exception:
                pass
            continue

    return specs[:max_specs]


def summarize_overlay_density(specs=None) -> dict:
    specs = _as_list(specs)
    counts: dict[str, int] = {}
    for s in specs:
        if not isinstance(s, dict):
            continue
        t = str(s.get('type') or '?')
        counts[t] = counts.get(t, 0) + 1
    return {
        'total': len(specs),
        'byType': counts,
        'summary': '叠层·' + ('+'.join(f'{k}{v}' for k, v in counts.items()) or '空'),
    }
