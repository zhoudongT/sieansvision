"""OpenCV multi-caliper line find (Halcon-style measure_pos stand-in).

Not a Halcon kernel — intensity profiles + gradient peaks + robust fit.
Used by vision.engine.geometry(feature=lines) when findMethod=caliper.
"""
from __future__ import annotations

import math
from typing import Any

import cv2
import numpy as np


def _peaks(profile: np.ndarray, positions: np.ndarray, sigma: float, threshold: float):
    step = float(positions[1] - positions[0]) if len(positions) > 1 else 1.0
    if step <= 0:
        step = 1.0
    radius = max(1, int(math.ceil(3 * sigma / step)))
    k = 2 * radius + 1
    smooth = cv2.GaussianBlur(
        profile.reshape(1, -1).astype(np.float32),
        (k, 1),
        sigma / step,
        borderType=cv2.BORDER_REPLICATE,
    )[0]
    gradient = np.gradient(smooth, step)
    strength = np.abs(gradient)
    found = []
    for i in range(radius + 2, len(profile) - radius - 2):
        if strength[i] < threshold:
            continue
        if not (strength[i] >= strength[i - 1] and strength[i] > strength[i + 1]):
            continue
        denom = strength[i - 1] - 2 * strength[i] + strength[i + 1]
        offset = 0.0 if abs(denom) < 1e-12 else float(
            np.clip(0.5 * (strength[i - 1] - strength[i + 1]) / denom, -0.5, 0.5)
        )
        found.append(dict(
            position=float(positions[i] + offset * step),
            gradient=float(gradient[i]),
            strength=float(strength[i]),
            sign=1 if gradient[i] > 0 else -1,
        ))
    return found


def _search_vectors(search_dir: str, proj_angle_deg: float):
    """Return (scan unit, cross unit) in image coords (+X right, +Y down)."""
    base = {
        'left_right': 0.0,
        'right_left': 180.0,
        'top_bottom': 90.0,
        'bottom_top': -90.0,
    }.get(search_dir or 'left_right', 0.0)
    angle = math.radians(base + float(proj_angle_deg or 0.0))
    scan = np.array([math.cos(angle), math.sin(angle)], dtype=np.float64)
    cross = np.array([-scan[1], scan[0]], dtype=np.float64)
    return scan, cross


def _roi_preset_rect(h: int, w: int, preset: str):
    preset = (preset or 'full').lower()
    if preset in ('', 'full', 'none', 'draw'):
        return None
    if preset == 'center':
        return [w // 4, h // 4, max(1, w // 2), max(1, h // 2)]
    if preset == 'left':
        return [0, 0, max(1, w // 2), h]
    if preset == 'right':
        return [w // 2, 0, max(1, w - w // 2), h]
    if preset == 'top':
        return [0, 0, w, max(1, h // 2)]
    if preset == 'bottom':
        return [0, h // 2, w, max(1, h - h // 2)]
    return None


def _fit_line(points: np.ndarray, prefer_dir: np.ndarray, max_residual: float, reject_extra: int = 0):
    if len(points) < 3:
        return None
    pts = points.astype(np.float32)
    line = cv2.fitLine(pts, cv2.DIST_HUBER, 0, 0.001, 0.001).ravel().astype(float)
    mask = np.ones(len(pts), dtype=bool)
    for _ in range(8):
        vector, origin = line[:2], line[2:]
        distances = np.abs((pts[:, 0] - origin[0]) * vector[1] - (pts[:, 1] - origin[1]) * vector[0])
        next_mask = mask & (distances <= max_residual)
        if next_mask.sum() < 3:
            return None
        # optional extra reject of worst residuals
        if reject_extra > 0 and next_mask.sum() > 3 + reject_extra:
            idx = np.where(next_mask)[0]
            order = idx[np.argsort(distances[idx])[::-1]]
            drop = order[: min(reject_extra, len(order) - 3)]
            next_mask = next_mask.copy()
            next_mask[drop] = False
        stable = np.array_equal(next_mask, mask)
        mask = next_mask
        line = cv2.fitLine(pts[mask], cv2.DIST_L2, 0, 0.001, 0.001).ravel().astype(float)
        vector, origin = line[:2], line[2:]
        distances = np.abs((pts[:, 0] - origin[0]) * vector[1] - (pts[:, 1] - origin[1]) * vector[0])
        if stable and np.all(distances[mask] <= max_residual):
            break
    if float(np.dot(vector, prefer_dir)) < 0:
        vector = -vector
    projection = (pts[mask] - origin) @ vector
    if float(np.ptp(projection)) < 1:
        return None
    begin = origin + vector * projection.min()
    end = origin + vector * projection.max()
    rms = float(np.sqrt(np.mean(distances[mask] ** 2)))
    return dict(
        vector=vector,
        origin=origin,
        start=begin.tolist(),
        end=end.tolist(),
        rmsPixels=rms,
        inlierMask=mask,
        residuals=distances,
        angleDeg=float(math.degrees(math.atan2(vector[1], vector[0]))),
        inlierCount=int(mask.sum()),
    )


def find_lines_caliper(gray: np.ndarray, canvas, p: dict, offset=(0, 0),
                       show_ov=True, show_calipers=True, show_pts=True,
                       show_fit=True, show_labels=True, show_ruler=False,
                       show_fit_err=False) -> dict[str, Any]:
    """Multi-probe caliper line find over gray ROI; draws onto full-size canvas."""
    ox, oy = offset
    h, w = gray.shape[:2]
    preset = p.get('roiPreset') or ''
    rect = _roi_preset_rect(h, w, preset)
    if rect is not None and p.get('roi') is None:
        # local crop for scanning (offset already applied to gray)
        rx, ry, rw, rh = rect
        gray_work = gray[ry:ry + rh, rx:rx + rw]
        local_off = (rx, ry)
    else:
        gray_work = gray
        local_off = (0, 0)
    wh, ww = gray_work.shape[:2]
    if wh < 8 or ww < 8:
        return {'feature': 'lines', 'count': 0, 'items': [], 'method': 'caliper',
                'diagnostic': 'ROI 过小', 'edgePoints': [], 'lines': []}

    count = max(3, min(200, int(p.get('caliperCount') or 10)))
    cal_w = max(1, min(101, int(p.get('caliperWidth') or 20)))
    cal_len = max(8, min(4096, int(p.get('caliperLength') or max(ww, wh) // 2)))
    sigma = float(p.get('caliperSigma') or 1.0)
    sigma = max(0.2, min(20.0, sigma))
    threshold = float(p.get('edgeThreshold') or p.get('minimumGradient') or 30)
    threshold = max(0.1, min(255.0, threshold))
    edge_type = str(p.get('edgeType') or 'strongest')
    polarity = str(p.get('edgePolarity') or 'any')
    search_dir = str(p.get('searchDir') or 'left_right')
    proj_ang = float(p.get('caliperProjAngle') or 0.0)
    reject_extra = max(0, min(50, int(p.get('rejectPoints') or 0)))
    min_score = float(p.get('minScore') or 0.5)
    min_score = max(0.0, min(1.0, min_score))
    max_residual = float(p.get('maximumResidual') or max(2.0, cal_w * 0.25))
    max_count = max(1, min(20, int(p.get('maxCount') or 1)))
    reverse = bool(p.get('reverseFind'))
    ang_norm = bool(p.get('angleNormalize'))
    sub_pixel = bool(p.get('subPixel', True))  # parabola interp always on; flag retained

    scan, cross = _search_vectors(search_dir, proj_ang)
    if reverse:
        scan = -scan

    # Probe centers: along cross through image mid, spanning available length
    cx = ww / 2.0
    cy = wh / 2.0
    # available half-span along cross inside ROI
    span = min(ww, wh) * 0.45
    if count > 1:
        spacing = (2 * span) / (count - 1)
    else:
        spacing = 0.0
    samples = int(math.ceil(cal_len)) + 1
    positions = np.linspace(-cal_len / 2.0, cal_len / 2.0, samples)
    offsets = np.arange(cal_w) - (cal_w - 1) / 2.0

    rows = []
    for index in range(count):
        origin = np.array([cx, cy], dtype=np.float64) + cross * ((index - (count - 1) / 2.0) * spacing)
        # remap expects (width_avg, samples) → build (cal_w, samples, 2)
        map_x = np.zeros((cal_w, samples), np.float32)
        map_y = np.zeros((cal_w, samples), np.float32)
        for wi, off in enumerate(offsets):
            pts = origin + positions[:, None] * scan + off * cross
            map_x[wi] = pts[:, 0]
            map_y[wi] = pts[:, 1]
        row = dict(probe=index + 1, probeCenterX=float(origin[0] + local_off[0] + ox),
                   probeCenterY=float(origin[1] + local_off[1] + oy),
                   valid=False, reason='未找到满足条件的边缘')
        rows.append(row)
        # draw caliper box
        corners = np.array([
            origin + positions[0] * scan + offsets[0] * cross,
            origin + positions[-1] * scan + offsets[0] * cross,
            origin + positions[-1] * scan + offsets[-1] * cross,
            origin + positions[0] * scan + offsets[-1] * cross,
        ], dtype=np.float64)
        corners_abs = corners + np.array([local_off[0] + ox, local_off[1] + oy])
        inside = bool(
            np.all(map_x >= 0) and np.all(map_x <= ww - 1)
            and np.all(map_y >= 0) and np.all(map_y <= wh - 1)
        )
        if show_ov and show_calipers and canvas is not None:
            color = (160, 110, 30) if inside else (40, 40, 220)
            cv2.polylines(canvas, [np.round(corners_abs).astype(np.int32)], True, color, 1, cv2.LINE_AA)
            tip_a = origin - scan * 6
            tip_b = origin + scan * 6
            a = tuple(np.round(tip_a + [local_off[0] + ox, local_off[1] + oy]).astype(int))
            b = tuple(np.round(tip_b + [local_off[0] + ox, local_off[1] + oy]).astype(int))
            cv2.arrowedLine(canvas, a, b, (180, 120, 20), 1, cv2.LINE_AA, tipLength=0.35)
        if not inside:
            row['reason'] = '采样区域超出图像'
            continue
        pixels = cv2.remap(gray_work.astype(np.float32), map_x, map_y, cv2.INTER_LINEAR)
        profile = pixels.mean(axis=0)
        candidates = _peaks(profile, positions, sigma, threshold)
        if not sub_pixel:
            # snap to nearest sample (UI flag: disable parabola claim)
            for c in candidates:
                c['position'] = float(positions[int(np.argmin(np.abs(positions - c['position'])))])
        # polarity filter
        if polarity == 'dark_to_light':
            edges = [e for e in candidates if e['sign'] > 0]
        elif polarity == 'light_to_dark':
            edges = [e for e in candidates if e['sign'] < 0]
        else:
            edges = list(candidates)
        if not edges:
            continue
        if edge_type == 'first':
            chosen = [edges[0]]
        elif edge_type == 'last':
            chosen = [edges[-1]]
        elif edge_type == 'all':
            chosen = edges
        else:  # strongest
            chosen = [max(edges, key=lambda e: e['strength'])]
        # keep strongest for primary fit point; stash all
        primary = max(chosen, key=lambda e: e['strength'])
        xy = origin + scan * primary['position']
        score = float(min(1.0, primary['strength'] / max(threshold * 4.0, 1.0)))
        if score < min_score:
            row['reason'] = f'分数过低 ({score:.3f}<{min_score:.3f})'
            row['score'] = score
            continue
        abs_xy = xy + np.array([local_off[0] + ox, local_off[1] + oy], dtype=np.float64)
        shift = np.array([local_off[0] + ox, local_off[1] + oy], dtype=np.float64)
        all_edges = []
        for e in chosen:
            pt = origin + scan * e['position'] + shift
            all_edges.append({
                'x': float(pt[0]), 'y': float(pt[1]),
                'strength': e['strength'], 'sign': e['sign'],
            })
        row.update(
            valid=True, reason='', score=score,
            edgeX=float(abs_xy[0]), edgeY=float(abs_xy[1]),
            gradient=primary['gradient'], strength=primary['strength'],
            allEdges=all_edges,
        )

    valid_rows = [r for r in rows if r['valid']]
    edge_points = [[r['edgeX'], r['edgeY']] for r in valid_rows]
    out_items = []
    fit_meta = None
    diagnostic = '未检出足够边缘点'
    min_length = float(p.get('minLength') or 0)

    def _item_from_fit(fitted, src_rows, band_idx=1):
        mask = fitted['inlierMask']
        for r, keep, res in zip(src_rows, mask, fitted['residuals']):
            r['inlier'] = bool(keep) if band_idx == 1 else (bool(keep) or r.get('inlier', False))
            r['residualPixels'] = float(res)
            if keep:
                r['lineIndex'] = band_idx
            elif band_idx == 1 and not keep:
                r['reason'] = '偏离拟合直线'
        inlier_ratio = fitted['inlierCount'] / max(count, 1)
        rms_score = max(0.0, 1.0 - fitted['rmsPixels'] / max(max_residual * 2, 1e-6))
        line_score = float(0.6 * inlier_ratio + 0.4 * rms_score)
        start = fitted['start']
        end = fitted['end']
        ang = fitted['angleDeg']
        if ang_norm:
            ang = ang % 180.0
        length = math.hypot(end[0] - start[0], end[1] - start[1])
        if min_length > 0 and length < min_length:
            return None, f'长度过短 ({length:.1f}<{min_length:.1f})'
        if line_score < min_score:
            return None, f'分数过低 ({line_score:.3f}<{min_score:.3f})'
        item = {
            'start': [float(start[0]), float(start[1])],
            'end': [float(end[0]), float(end[1])],
            'lengthPixels': float(length),
            'angleDeg': float(ang),
            'score': line_score,
            'rmsPixels': fitted['rmsPixels'],
            'inlierCount': fitted['inlierCount'],
            'edgePoints': [[float(r['edgeX']), float(r['edgeY'])] for r, k in zip(src_rows, mask) if k],
            'method': 'caliper',
            'lineIndex': band_idx,
        }
        return item, '卡尺直线拟合通过'

    def _draw_item(item, color=(0, 210, 80)):
        if not (show_ov and show_fit and canvas is not None):
            return
        a = tuple(map(int, np.round(item['start'])))
        b = tuple(map(int, np.round(item['end'])))
        cv2.line(canvas, a, b, color, 2, cv2.LINE_AA)
        if show_labels:
            mid = ((a[0] + b[0]) // 2, (a[1] + b[1]) // 2)
            cv2.putText(canvas, f"{item.get('lineIndex', 1)} s={item['score']:.2f}", mid,
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1, cv2.LINE_AA)
        if show_fit_err:
            cv2.putText(canvas, f"rms={item['rmsPixels']:.2f}",
                        (a[0] + 4, a[1] + 14), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 180, 0), 1, cv2.LINE_AA)
        if show_ruler:
            cv2.drawMarker(canvas, a, (255, 180, 0), cv2.MARKER_CROSS, 8, 1)
            cv2.drawMarker(canvas, b, (255, 180, 0), cv2.MARKER_CROSS, 8, 1)

    # --- band candidates from multi-edge (edgeType=all) ---
    band_point_sets = []  # list of list[row-like dicts with edgeX/edgeY]
    if edge_type == 'all' and max_count > 1:
        # Cluster by scan position: each probe's allEdges → assign to nearest band seed
        raw = []  # (scan_pos, x, y, probe)
        for r in valid_rows:
            for e in (r.get('allEdges') or [{'x': r['edgeX'], 'y': r['edgeY']}]):
                # reconstruct approx scan pos relative to probe center along scan
                dx = e['x'] - r['probeCenterX']
                dy = e['y'] - r['probeCenterY']
                spos = float(dx * scan[0] + dy * scan[1])
                raw.append((spos, float(e['x']), float(e['y']), r['probe']))
        if raw:
            raw.sort(key=lambda t: t[0])
            # greedy gap clustering along scan axis
            gap = max(3.0, cal_len * 0.08, max_residual * 2)
            clusters = []
            cur = [raw[0]]
            for pt in raw[1:]:
                if abs(pt[0] - cur[-1][0]) <= gap:
                    cur.append(pt)
                else:
                    clusters.append(cur)
                    cur = [pt]
            clusters.append(cur)
            # keep clusters that span enough distinct probes
            for cl in clusters:
                probes = {t[3] for t in cl}
                if len(probes) < 3:
                    continue
                # one point per probe (median scan in cluster for that probe)
                by_probe = {}
                for spos, x, y, pr in cl:
                    by_probe.setdefault(pr, []).append((spos, x, y))
                pts_rows = []
                for pr, lst in by_probe.items():
                    lst.sort(key=lambda t: t[0])
                    mid = lst[len(lst) // 2]
                    pts_rows.append({'edgeX': mid[1], 'edgeY': mid[2], 'probe': pr, 'inlier': False})
                if len(pts_rows) >= 3:
                    band_point_sets.append(pts_rows)

    if not band_point_sets:
        # single primary set from valid_rows
        if len(valid_rows) >= 3:
            band_point_sets = [[{'edgeX': r['edgeX'], 'edgeY': r['edgeY'], 'probe': r['probe'],
                                'inlier': False, '_src': r} for r in valid_rows]]

    # Fit each band; then residual-peel more lines if maxCount still open
    palette = [
        (0, 210, 80), (0, 180, 255), (255, 160, 40), (200, 80, 255),
        (80, 220, 200), (220, 220, 60),
    ]
    used_point_keys = set()
    band_idx = 0
    last_diag = diagnostic
    for pts_rows in band_point_sets:
        if len(out_items) >= max_count:
            break
        # skip points already claimed by a prior line
        free = [r for r in pts_rows if (round(r['edgeX'], 2), round(r['edgeY'], 2)) not in used_point_keys]
        if len(free) < 3:
            continue
        pts = np.array([[r['edgeX'], r['edgeY']] for r in free], dtype=np.float64)
        fitted = _fit_line(pts, cross, max_residual, reject_extra=reject_extra)
        if fitted is None:
            last_diag = '拟合有效点不足'
            continue
        # map residuals onto original valid_rows when primary
        src_for_meta = free
        if band_idx == 0 and '_src' in (free[0] if free else {}):
            # sync onto original valid_rows for primary diagnostics
            src_for_meta = []
            for r in free:
                src = r.get('_src')
                src_for_meta.append(src if src is not None else r)
        item, diag = _item_from_fit(fitted, src_for_meta, band_idx=band_idx + 1)
        last_diag = diag
        if item is None:
            continue
        if band_idx == 0:
            fit_meta = fitted
        out_items.append(item)
        _draw_item(item, palette[band_idx % len(palette)])
        for r, keep in zip(free, fitted['inlierMask']):
            if keep:
                used_point_keys.add((round(r['edgeX'], 2), round(r['edgeY'], 2)))
        band_idx += 1

    # Residual peel: if still need more lines and we have leftover primary points
    if len(out_items) < max_count and len(valid_rows) >= 6:
        remain = [r for r in valid_rows
                  if (round(r['edgeX'], 2), round(r['edgeY'], 2)) not in used_point_keys]
        peel_guard = 0
        while len(out_items) < max_count and len(remain) >= 3 and peel_guard < max_count:
            peel_guard += 1
            pts = np.array([[r['edgeX'], r['edgeY']] for r in remain], dtype=np.float64)
            fitted = _fit_line(pts, cross, max_residual, reject_extra=reject_extra)
            if fitted is None or fitted['inlierCount'] < 3:
                break
            item, diag = _item_from_fit(fitted, remain, band_idx=len(out_items) + 1)
            last_diag = diag
            if item is None:
                break
            out_items.append(item)
            _draw_item(item, palette[len(out_items) % len(palette)])
            mask = fitted['inlierMask']
            for r, keep in zip(remain, mask):
                if keep:
                    used_point_keys.add((round(r['edgeX'], 2), round(r['edgeY'], 2)))
            remain = [r for r, keep in zip(remain, mask) if not keep]

    if out_items:
        diagnostic = f'卡尺检出 {len(out_items)} 条直线' if len(out_items) > 1 else last_diag
    else:
        diagnostic = last_diag if len(valid_rows) >= 3 else f'有效边缘点不足 ({len(valid_rows)}/3)'

    # draw edge points (inlier / multi-line index / outlier)
    if show_ov and show_pts and canvas is not None:
        for r in valid_rows:
            li = int(r.get('lineIndex') or 0)
            if li > 0:
                color = palette[(li - 1) % len(palette)]
            elif r.get('inlier'):
                color = (60, 210, 60)
            elif fit_meta is None:
                color = (0, 165, 255)
            else:
                color = (40, 40, 230)
            cv2.circle(canvas, (round(r['edgeX']), round(r['edgeY'])), 3, color, -1, cv2.LINE_AA)
            # secondary edges from edgeType=all
            if edge_type == 'all':
                for e in (r.get('allEdges') or [])[1:]:
                    cv2.circle(canvas, (round(e['x']), round(e['y'])), 2, (180, 180, 40), -1, cv2.LINE_AA)

    out_items = out_items[:max_count]

    return {
        'feature': 'lines',
        'count': len(out_items),
        'items': out_items,
        'lines': out_items,
        'method': 'caliper',
        'edgePoints': edge_points,
        'probes': rows,
        'probeCount': count,
        'detectedCount': len(valid_rows),
        'rmsPixels': (out_items[0]['rmsPixels'] if out_items else (fit_meta['rmsPixels'] if fit_meta else None)),
        'rms': (out_items[0]['rmsPixels'] if out_items else (fit_meta['rmsPixels'] if fit_meta else None)),
        'inlierCount': sum(it.get('inlierCount', 0) for it in out_items) if out_items else (fit_meta['inlierCount'] if fit_meta else 0),
        'score': out_items[0]['score'] if out_items else 0.0,
        'scores': [it.get('score', 0.0) for it in out_items],
        'residualsSummary': [
            {'lineIndex': it.get('lineIndex', i + 1), 'rmsPixels': it.get('rmsPixels'),
             'score': it.get('score'), 'inlierCount': it.get('inlierCount'),
             'lengthPixels': it.get('lengthPixels'), 'angleDeg': it.get('angleDeg')}
            for i, it in enumerate(out_items)
        ],
        'diagnostic': diagnostic,
        'overlay': {
            'showOverlay': show_ov,
            'showPoints': show_pts,
            'showFitCurve': show_fit,
            'showLabels': show_labels,
            'showRuler': show_ruler,
            'showCalipers': show_calipers,
        },
        'note': 'OpenCV 多卡尺边缘拟合（非 Halcon 核）；亚像素为抛物线插值估计',
    }
