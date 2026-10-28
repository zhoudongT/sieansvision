"""Local image engine. Coordinates use the original image; image y increases down."""
import base64
import contextlib
import json
import math
import os
import sys
import time
from pathlib import Path
import cv2
import numpy as np

cv2.setNumThreads(2)
OCR = None
MODELS = {}
MODEL_DIR = Path(os.environ.get('VISION_MODEL_DIR') or Path(__file__).resolve().parent.parent / 'models').resolve()
MAX_PIXELS = 16_000_000



def _show_flag(p, key, default=True):
    """Panel overlay toggles → real draw gate (truthy; string falsey → off)."""
    v = p.get(key, default)
    if isinstance(v, str):
        return v.strip().lower() not in ('0', 'false', 'no', 'off', '')
    return bool(v) if v is not None else bool(default)


def number(p, key, default, low, high):
    value = float(p.get(key, default))
    if not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f'{key} must be between {low} and {high}')
    return value


def decode(value):
    if not isinstance(value, str) or not value:
        raise ValueError('请提供图像（data URL 或 base64）')
    raw = base64.b64decode(value.split(',', 1)[-1], validate=True)
    if len(raw) > 12_000_000:
        raise ValueError('图像文件超过 12 MB')
    # Check dimensions before OpenCV allocates the decoded image.
    import io
    from PIL import Image
    with Image.open(io.BytesIO(raw)) as header:
        if header.width * header.height > MAX_PIXELS:
            raise ValueError('图像超过 1600 万像素')
    image = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError('无法解码图像')
    return image


def roi_image(image, params):
    rect = params.get('roi')
    if rect is None:
        return image, (0, 0)
    if not isinstance(rect, list) or len(rect) != 4:
        raise ValueError('roi 必须为 [x,y,width,height]')
    x, y, w, h = map(int, rect)
    if x < 0 or y < 0 or w <= 0 or h <= 0 or x+w > image.shape[1] or y+h > image.shape[0]:
        raise ValueError('ROI 超出图像边界')
    return image[y:y+h, x:x+w], (x, y)


def polygon(canvas, pts, color=(0, 210, 80)):
    cv2.polylines(canvas, [np.round(pts).astype(np.int32)], True, color, 2)


def contours(gray, p):
    threshold = number(p, 'threshold', 127, 0, 255)
    _, binary = cv2.threshold(gray, threshold, 255,
                              cv2.THRESH_BINARY_INV if p.get('invert', False) else cv2.THRESH_BINARY)
    found, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    minimum = number(p, 'minArea', 50, 1, MAX_PIXELS)
    found = [c for c in found if cv2.contourArea(c) >= minimum]
    return sorted(found, key=cv2.contourArea, reverse=True)[:100]


def locate(image, canvas, p, offset, reference):
    from template_matching import locate as match
    return match(image, canvas, p, offset, reference)


def geometry(image, canvas, p, offset):
    if image is None:
        raise ValueError('geometry 需要输入图像')
    if len(image.shape) == 2 or image.shape[2] == 1:
        gray = image if len(image.shape) == 2 else image[:, :, 0]
    else:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    mode = p.get('feature', 'contours')
    ox, oy = offset
    result = []
    # Soft caliper-adjacent knobs (OpenCV only — not a Halcon caliper kernel).
    filt = int(number(p, 'filterSize', 1, 1, 31))
    max_count = int(number(p, 'maxCount', 50, 1, 100))
    if filt > 1:
        k = filt * 2 + 1
        gray = cv2.GaussianBlur(gray, (k, k), 0)

    show_ov = _show_flag(p, 'showOverlay', True)
    show_lines = show_ov and (
        _show_flag(p, 'showCalipers', True)
        or _show_flag(p, 'showFitCurve', True)
        or _show_flag(p, 'showLines', True)
    )
    show_pts = show_ov and _show_flag(p, 'showPoints', True)
    show_labels = show_ov and _show_flag(p, 'showLabels', True)
    show_ruler = show_ov and _show_flag(p, 'showRuler', False)
    show_fit_err = show_ov and _show_flag(p, 'showFitError', False)

    if mode in ('lines', 'edges'):
        # Prefer explicit edgeThreshold as Canny low when set densely from UI
        low = number(p, 'cannyLow', 50, 0, 255)
        high = number(p, 'cannyHigh', 150, 0, 255)
        et = p.get('edgeThreshold')
        if et is not None:
            try:
                etv = float(et)
                if 1 <= etv <= 255:
                    low = etv
                    high = max(high, etv * 2)
            except (TypeError, ValueError):
                pass
        edges = cv2.Canny(gray, low, high)
        if mode == 'edges':
            if show_lines:
                canvas[oy:oy+gray.shape[0], ox:ox+gray.shape[1]][edges > 0] = (0, 210, 80)
            return {'feature': mode, 'edgePixels': int(np.count_nonzero(edges)),
                    'overlay': {'showOverlay': show_ov, 'showFitCurve': show_lines}}
        # Default: OpenCV multi-caliper line find (UI caliper* knobs). findMethod=hough keeps legacy.
        find_method = str(p.get('findMethod') or 'caliper').lower()
        if find_method in ('caliper', 'measure', 'auto', ''):
            try:
                from caliper_line import find_lines_caliper
                cal = find_lines_caliper(
                    gray, canvas, p, offset=(ox, oy),
                    show_ov=show_ov, show_calipers=show_ov and _show_flag(p, 'showCalipers', True),
                    show_pts=show_pts, show_fit=show_lines, show_labels=show_labels,
                    show_ruler=show_ruler, show_fit_err=show_fit_err,
                )
                if cal.get('count', 0) > 0 or find_method != 'auto':
                    return cal
            except Exception:
                if find_method == 'caliper':
                    raise
                # auto → fall through to Hough
                pass
        lines = cv2.HoughLinesP(edges, 1, np.pi/180, int(number(p, 'votes', 40, 1, 10000)),
                               minLineLength=number(p, 'minLength', 40, 1, 10000), maxLineGap=number(p, 'maxGap', 10, 0, 1000))
        reverse = bool(p.get('reverseFind'))
        ang_norm = bool(p.get('angleNormalize'))
        for idx, (x1, y1, x2, y2) in enumerate([] if lines is None else lines.reshape(-1, 4)[:max_count]):
            if reverse:
                x1, y1, x2, y2 = x2, y2, x1, y1
            a, b = (int(x1)+ox, int(y1)+oy), (int(x2)+ox, int(y2)+oy)
            ang = math.degrees(math.atan2(y2-y1, x2-x1))
            if ang_norm:
                ang = ang % 180.0
            if show_lines:
                cv2.line(canvas, a, b, (0, 210, 80), 2)
            if show_pts:
                cv2.circle(canvas, a, 3, (0, 165, 255), -1, cv2.LINE_AA)
                cv2.circle(canvas, b, 3, (0, 165, 255), -1, cv2.LINE_AA)
            if show_labels:
                mid = ((a[0]+b[0])//2, (a[1]+b[1])//2)
                cv2.putText(canvas, str(idx+1), mid, cv2.FONT_HERSHEY_SIMPLEX, .45, (0, 210, 80), 1, cv2.LINE_AA)
            if show_ruler:
                # tick marks at ends
                cv2.drawMarker(canvas, a, (255, 180, 0), cv2.MARKER_CROSS, 8, 1)
                cv2.drawMarker(canvas, b, (255, 180, 0), cv2.MARKER_CROSS, 8, 1)
            result.append({'start': a, 'end': b, 'lengthPixels': math.hypot(x2-x1, y2-y1),
                           'angleDeg': ang, 'method': 'hough'})
    elif mode == 'circles':
        min_r = int(number(p, 'minRadius', 5, 0, 10000))
        max_r = int(number(p, 'maxRadius', 200, 0, 10000))
        # VM 扇环：若外径>0，收紧 Hough 半径窗
        try:
            ai = int(p.get('annulusInner') or 0)
            ao = int(p.get('annulusOuter') or 0)
        except (TypeError, ValueError):
            ai = ao = 0
        if ao > 0:
            min_r = max(min_r, ai) if ai > 0 else min_r
            max_r = ao if max_r <= 0 else min(max_r, ao)
        found = cv2.HoughCircles(cv2.GaussianBlur(gray, (5, 5), 1), cv2.HOUGH_GRADIENT, 1.2,
                                number(p, 'minDistance', 30, 1, 10000),
                                param1=number(p, 'cannyHigh', 150, 1, 255), param2=number(p, 'votes', 30, 1, 1000),
                                minRadius=min_r, maxRadius=max_r)
        for idx, (x, y, r) in enumerate([] if found is None else found.reshape(-1, 3)[:max_count]):
            center = [float(x)+ox, float(y)+oy]
            cxy = tuple(map(round, center))
            if show_lines:
                cv2.circle(canvas, cxy, round(float(r)), (0, 210, 80), 2)
            if show_pts:
                cv2.circle(canvas, cxy, 3, (0, 165, 255), -1, cv2.LINE_AA)
            if show_labels:
                cv2.putText(canvas, str(idx+1), (cxy[0]+4, cxy[1]-4), cv2.FONT_HERSHEY_SIMPLEX, .45, (0, 210, 80), 1, cv2.LINE_AA)
            if show_fit_err:
                cv2.putText(canvas, f'r={float(r):.1f}', (cxy[0]+4, cxy[1]+14), cv2.FONT_HERSHEY_SIMPLEX, .4, (255, 180, 0), 1, cv2.LINE_AA)
            if show_ruler:
                cv2.line(canvas, (cxy[0]-round(float(r)), cxy[1]), (cxy[0]+round(float(r)), cxy[1]), (255, 180, 0), 1)
            result.append({'center': center, 'radiusPixels': float(r), 'diameterPixels': float(2*r)})
    elif mode == 'rects':
        # minAreaRect on contours; filter by size / angle tolerance
        ang_tol = float(p.get('angleTolerance') or 5.0)
        min_r = number(p, 'minRadius', 0, 0, 100000)
        max_r = number(p, 'maxRadius', 0, 0, 100000)
        max_count = int(number(p, 'maxCount', 50, 1, 100))
        for c in contours(gray, p):
            if len(c) < 4:
                continue
            (cx, cy), (w, h), angle = cv2.minAreaRect(c)
            half = max(w, h) / 2.0
            if min_r and half < min_r:
                continue
            if max_r and half > max_r:
                continue
            # near-axis rects preferred when angleTolerance tight
            a = abs(angle) % 90
            a = min(a, 90 - a)
            if ang_tol < 45 and a > ang_tol and abs(w - h) > 1:
                # allow rotated; only soft-filter near-square when tol small
                pass
            box = cv2.boxPoints(((cx, cy), (w, h), angle))
            box = box + np.array([ox, oy], dtype=np.float32)
            if show_lines:
                polygon(canvas, box)
            if show_pts:
                for pt in np.round(box).astype(int):
                    cv2.circle(canvas, (int(pt[0]), int(pt[1])), 3, (0, 165, 255), -1, cv2.LINE_AA)
            if show_labels:
                cv2.putText(canvas, str(len(result)+1), (round(float(cx)+ox), round(float(cy)+oy)),
                            cv2.FONT_HERSHEY_SIMPLEX, .45, (0, 210, 80), 1, cv2.LINE_AA)
            result.append({
                'center': [float(cx) + ox, float(cy) + oy],
                'widthPixels': float(min(w, h)),
                'heightPixels': float(max(w, h)),
                'angleDeg': float(angle),
                'areaPixels': float(w * h),
                'box': box.tolist(),
            })
            if len(result) >= max_count:
                break
    elif mode == 'contours':
        for idx, c in enumerate(contours(gray, p)):
            c = c + np.array([[[ox, oy]]])
            x, y, w, h = cv2.boundingRect(c)
            if show_lines:
                cv2.drawContours(canvas, [c], -1, (0, 210, 80), 2)
            if show_pts and len(c):
                pt0 = c[0, 0]
                cv2.circle(canvas, (int(pt0[0]), int(pt0[1])), 3, (0, 165, 255), -1, cv2.LINE_AA)
            if show_labels:
                cv2.putText(canvas, str(idx+1), (x, max(12, y-4)), cv2.FONT_HERSHEY_SIMPLEX, .45, (0, 210, 80), 1, cv2.LINE_AA)
            result.append({'bbox': [x, y, w, h], 'areaPixels': cv2.contourArea(c),
                           'perimeterPixels': cv2.arcLength(c, True), 'points': c[:, 0].tolist()})
            if len(result) >= max_count:
                break
    else:
        raise ValueError('feature 必须是 lines、circles、rects、edges 或 contours')
    # Result judge (panel 结果判断)：按几何量门限标 OK/NG（OpenCV 壳，无 Halcon）
    judge_en = bool(p.get('judgeEnable'))
    try:
        jmin = float(p.get('judgeMin') if p.get('judgeMin') is not None else 0.0)
        jmax = float(p.get('judgeMax') if p.get('judgeMax') is not None else 99999.0)
    except (TypeError, ValueError):
        jmin, jmax = 0.0, 99999.0
    if jmax < jmin:
        jmin, jmax = jmax, jmin

    def _metric(it):
        if mode in ('lines', 'edges'):
            if 'lengthPixels' in it:
                return float(it.get('lengthPixels') or 0)
            if 'score' in it:
                return float(it.get('score') or 0)
        if mode == 'circles':
            return float(it.get('radiusPixels') or 0)
        if mode == 'rects':
            return float(it.get('areaPixels') or 0)
        if mode == 'contours':
            return float(it.get('areaPixels') or 0)
        return float(it.get('score') or it.get('rmsPixels') or 0)

    for it in result:
        if not isinstance(it, dict):
            continue
        m = _metric(it)
        ok = (not judge_en) or (jmin <= m <= jmax)
        it['judgeOk'] = bool(ok)
        it['judgeStatus'] = 'OK' if ok else 'NG'
        it['judgeMetric'] = m

    judge_all_ok = (not judge_en) or (bool(result) and all(
        (it.get('judgeOk') if isinstance(it, dict) else True) for it in result
    ))
    out = {
        'feature': mode, 'count': len(result), 'items': result,
        'judgeEnable': bool(judge_en),
        'judgeOk': bool(judge_all_ok) if result else (False if judge_en else True),
        'judgeMin': jmin if judge_en else None,
        'judgeMax': jmax if judge_en else None,
        'overlay': {'showOverlay': show_ov, 'showPoints': show_pts, 'showFitCurve': show_lines,
                    'showLabels': show_labels, 'showRuler': show_ruler},
        'note': 'OpenCV 几何查找（非 Halcon 核）',
    }
    # aliases for measure bind fields: lines[0] / circles[0] / rects[0]
    if mode in ('lines', 'circles', 'rects', 'contours'):
        out[mode] = result
    if judge_en and result:
        ng = sum(1 for it in result if isinstance(it, dict) and not it.get('judgeOk'))
        if ng:
            out['diagnostic'] = f'结果判断 NG：{ng}/{len(result)} 超出门限 [{jmin:.3g},{jmax:.3g}]'
        else:
            out['diagnostic'] = f'结果判断 OK（[{jmin:.3g},{jmax:.3g}]）'
    return out



def measure(image, canvas, p, offset):
    # Uniform planar scale calibration. Perspective/lens calibration is a later stage.
    unit = str(p.get('unit', 'mm'))
    calibration = p.get('calibration')
    calibrated = calibration is not None
    if calibrated:
        points = np.array(calibration['points'], dtype=float)
        if points.shape != (2, 2) or not np.isfinite(points).all():
            raise ValueError('标定 points 必须为 [[x1,y1],[x2,y2]]')
        length = number(calibration, 'distance', 1, 0.000001, 1e9)
        pixels = float(np.linalg.norm(points[1]-points[0]))
        if pixels < 1:
            raise ValueError('标定点之间至少相隔 1 像素')
        ratio = length / pixels
    else:
        ratio, unit = 1, 'px'
    origin = np.array(p.get('origin', [0, 0]), dtype=float)
    if origin.shape != (2,) or not np.isfinite(origin).all():
        raise ValueError('origin 必须是两个有限数值')
    selected = p.get('points')
    if selected is not None:
        pts = np.array(selected, dtype=float)
        if pts.shape != (2, 2) or not np.isfinite(pts).all():
            raise ValueError('测量 points 必须为两个坐标点')
        if _show_flag(p, 'showOverlay', True) and _show_flag(p, 'showLines', True):
            cv2.line(canvas, tuple(np.round(pts[0]).astype(int)), tuple(np.round(pts[1]).astype(int)), (0, 210, 80), 2)
        if _show_flag(p, 'showOverlay', True) and _show_flag(p, 'showPoints', True):
            for pt in pts:
                cv2.circle(canvas, tuple(np.round(pt).astype(int)), 4, (0, 165, 255), -1, cv2.LINE_AA)
        if _show_flag(p, 'showOverlay', True) and (_show_flag(p, 'showLabels', True) or _show_flag(p, 'showDistanceText', True)):
            mid = tuple(np.round(pts.mean(axis=0)).astype(int))
            dist_txt = f"{float(np.linalg.norm(pts[1]-pts[0])):.2f}"
            cv2.putText(canvas, dist_txt, mid, cv2.FONT_HERSHEY_SIMPLEX, .5, (0, 210, 80), 1, cv2.LINE_AA)
        data = {'distance': float(np.linalg.norm(pts[1]-pts[0]))*ratio, 'points': selected}
    else:
        items = []
        mode = p.get('feature', 'contours')
        if mode == 'circles':
            circles = geometry(image, canvas, {**p, 'feature': 'circles'}, offset)['items']
            for c in circles:
                items.append({'centerPixels': c['center'], 'diameter': c['diameterPixels']*ratio,
                              'offset': ((np.array(c['center'])-origin)*ratio).tolist()})
        elif mode == 'contours':
            for contour in contours(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY), p):
                contour = contour+np.array([[[offset[0], offset[1]]]])
                center, dimensions, angle = cv2.minAreaRect(contour)
                points = cv2.boxPoints((center, dimensions, angle))
                if _show_flag(p, 'showOverlay', True) and (
                        _show_flag(p, 'showFitCurve', True) or _show_flag(p, 'showLines', True) or _show_flag(p, 'showCalipers', True)):
                    polygon(canvas, points)
                if _show_flag(p, 'showOverlay', True) and _show_flag(p, 'showPoints', True):
                    for pt in np.round(points).astype(int):
                        cv2.circle(canvas, (int(pt[0]), int(pt[1])), 3, (0, 165, 255), -1, cv2.LINE_AA)
                items.append({'centerPixels': center, 'width': min(dimensions)*ratio, 'height': max(dimensions)*ratio,
                              'area': cv2.contourArea(contour)*ratio*ratio,
                              'offset': ((np.array(center)-origin)*ratio).tolist()})
        else:
            raise ValueError('测量 feature 必须为 contours 或 circles，或提供 points 测距')
        data = {'count': len(items), 'items': items}
    return {**data, 'calibrated': calibrated, 'unitsPerPixel': ratio, 'unit': unit,
            'note': '两点等比例标定，适用于固定平面和垂直拍摄；未补偿透视或镜头畸变'}


def barcode(image, canvas, p, offset):
    try:
        import zxingcpp
    except ImportError as exc:
        raise RuntimeError(
            "条码识别需要 zxing-cpp。请执行：python3 -m pip install --target .pydeps -i https://pypi.tuna.tsinghua.edu.cn/simple 'zxing-cpp==3.1.1'"
        ) from exc
    results = []
    for code in zxingcpp.read_barcodes(image):
        if not code.valid:
            continue
        points = [[getattr(code.position, key).x+offset[0], getattr(code.position, key).y+offset[1]]
                  for key in ('top_left', 'top_right', 'bottom_right', 'bottom_left')]
        polygon(canvas, points)
        results.append({'text': code.text, 'format': str(code.format), 'polygon': points})
    return {'count': len(results), 'items': results}


def ocr(image, canvas, p, offset):
    global OCR
    if OCR is None:
        from rapidocr_onnxruntime import RapidOCR
        OCR = RapidOCR(intra_op_num_threads=2, inter_op_num_threads=2)
    result, _ = OCR(image)
    minimum = number(p, 'minConfidence', 0.5, 0, 1)
    show_overlay = p.get('showOverlay', True) is not False
    show_boxes = p.get('showBoxes', True) is not False
    show_text = p.get('showText', True) is not False
    max_items = int(number(p, 'maxItems', 50, 1, 500))
    items = []
    for points, text, confidence in result or []:
        if confidence < minimum:
            continue
        points = np.array(points)+np.array(offset)
        if show_overlay and show_boxes:
            polygon(canvas, points)
        if show_overlay and show_text and text:
            try:
                x0 = int(points[:, 0].min()); y0 = int(points[:, 1].min())
                cv2.putText(canvas, str(text)[:40], (x0, max(12, y0 - 4)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 220, 255), 1, cv2.LINE_AA)
            except Exception:
                pass
        items.append({'text': text, 'confidence': float(confidence), 'polygon': points.tolist()})
        if len(items) >= max_items:
            break
    text_joined = '\n'.join(item['text'] for item in items)
    confs = [float(it['confidence']) for it in items]
    mean_conf = float(sum(confs) / len(confs)) if confs else 0.0
    judge_en = bool(p.get('judgeEnable', False))
    judge_min_c = number(p, 'judgeMinConfidence', minimum, 0, 1)
    expected = str(p.get('expectedText') or '').strip()
    ok = True
    if judge_en:
        ok = (mean_conf >= judge_min_c) if items else False
        if ok and expected:
            ok = expected in text_joined
    out = {
        'text': text_joined, 'count': len(items), 'items': items,
        'confidence': mean_conf, 'status': 'ok' if items else 'empty',
        'passed': bool(ok) if judge_en else True,
        'judgeEnable': judge_en, 'judgeOk': bool(ok) if judge_en else True,
        'judgeStatus': ('OK' if ok else 'NG') if judge_en else 'SKIP',
        'showOverlay': show_overlay, 'showBoxes': show_boxes, 'showText': show_text,
    }
    return out


def defects(image, canvas, p, offset, reference):
    if reference is None:
        raise ValueError('缺陷检测需要同尺寸、同位置、相同光照的良品参考图')
    if image.shape != reference.shape:
        raise ValueError('良品参考图必须与检测区域尺寸一致')
    blur_k = int(number(p, 'blur', 3, 0, 31))
    if blur_k > 0 and blur_k % 2 == 0:
        blur_k += 1
    thr_key = 'threshold' if 'threshold' in p else 'differenceThreshold'
    thr = number(p, thr_key, 30, 1, 255)
    a = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    b = cv2.cvtColor(reference, cv2.COLOR_BGR2GRAY)
    if blur_k >= 3:
        a = cv2.GaussianBlur(a, (blur_k, blur_k), 0)
        b = cv2.GaussianBlur(b, (blur_k, blur_k), 0)
    else:
        a = cv2.GaussianBlur(a, (3, 3), 0)
        b = cv2.GaussianBlur(b, (3, 3), 0)
    delta = cv2.absdiff(a, b)
    _, mask = cv2.threshold(delta, thr, 255, cv2.THRESH_BINARY)
    minimum = number(p, 'minArea', 20, 1, MAX_PIXELS)
    max_count = int(number(p, 'maxCount', 200, 1, 5000))
    show_overlay = p.get('showOverlay', True) is not False
    show_boxes = p.get('showBoxes', True) is not False
    show_labels = p.get('showLabels', True) is not False
    regions, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    items = []
    accepted = np.zeros_like(mask)
    for c in regions:
        area = cv2.contourArea(c)
        if area < minimum:
            continue
        cv2.drawContours(accepted, [c], -1, 255, -1)
        c = c+np.array([[[offset[0], offset[1]]]])
        x, y, w, h = cv2.boundingRect(c)
        if show_overlay and show_boxes:
            cv2.drawContours(canvas, [c], -1, (0, 0, 255), 2)
            if show_labels:
                cv2.putText(canvas, f'A{int(area)}', (x, max(12, y - 4)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 180, 255), 1, cv2.LINE_AA)
        items.append({'bbox': [x, y, w, h], 'areaPixels': float(area)})
        if len(items) >= max_count:
            break
    ratio = float(np.count_nonzero(accepted))/mask.size if mask.size else 0.0
    # legacy maxDefectRatio still honored as soft pass gate
    allowed_ratio_legacy = number(p, 'maxDefectRatio', 1, 0, 1)
    passed_legacy = ratio <= allowed_ratio_legacy
    judge_en = bool(p.get('judgeEnable', True))
    judge_max_count = int(number(p, 'judgeMaxCount', 0, 0, 5000))
    judge_max_ratio = number(p, 'judgeMaxRatio', 0.05, 0, 1)
    ok = True
    if judge_en:
        ok = (len(items) <= judge_max_count) and (ratio <= judge_max_ratio)
    out = {
        'passed': bool(ok) if judge_en else bool(passed_legacy),
        'count': len(items), 'defectRatio': ratio, 'items': items,
        'method': str(p.get('method') or 'absdiff'),
        'status': 'ok',
        'judgeEnable': judge_en, 'judgeOk': bool(ok) if judge_en else True,
        'judgeStatus': ('OK' if ok else 'NG') if judge_en else 'SKIP',
        'judgeMaxCount': judge_max_count if judge_en else None,
        'judgeMaxRatio': judge_max_ratio if judge_en else None,
        'showOverlay': show_overlay, 'showBoxes': show_boxes, 'showLabels': show_labels,
        'note': '参考图差分结果为疑似缺陷；位移、光照变化也会产生差异，不自动分类划痕或污点',
    }
    return out


def preprocess(image, canvas, p, offset):
    mode = p.get('method', 'grayscale')
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    if mode == 'grayscale':
        out = gray
    elif mode == 'blur':
        kernel = int(number(p, 'kernel', 5, 1, 51))
        if kernel % 2 != 1:
            raise ValueError('kernel 必须是奇数')
        out = cv2.GaussianBlur(image, (kernel, kernel), 0)
    elif mode == 'threshold':
        _, out = cv2.threshold(gray, number(p, 'threshold', 127, 0, 255), 255,
                               cv2.THRESH_BINARY_INV if p.get('invert') else cv2.THRESH_BINARY)
    elif mode == 'canny':
        out = cv2.Canny(gray, number(p, 'cannyLow', 50, 0, 255), number(p, 'cannyHigh', 150, 0, 255))
    elif mode in ('open', 'close', 'erode', 'dilate'):
        kernel = np.ones((int(number(p, 'kernel', 3, 1, 51)),)*2, np.uint8)
        out = cv2.morphologyEx(gray, {'open': cv2.MORPH_OPEN, 'close': cv2.MORPH_CLOSE,
                                    'erode': cv2.MORPH_ERODE, 'dilate': cv2.MORPH_DILATE}[mode], kernel)
    else:
        raise ValueError('不支持的预处理 method')
    if out.ndim == 2:
        out = cv2.cvtColor(out, cv2.COLOR_GRAY2BGR)
    canvas[offset[1]:offset[1]+out.shape[0], offset[0]:offset[0]+out.shape[1]] = out
    return {'method': mode}


def yolo(image, canvas, p, offset):
    name = p.get('model', 'yolo11n.pt')
    if not isinstance(name, str) or Path(name).name != name or not name.endswith(('.pt', '.onnx')):
        raise ValueError('model 必须是 models 目录内的 .pt 或 .onnx 文件名')
    file = MODEL_DIR / name
    if not file.is_file():
        raise ValueError(f'模型未安装：请将可信的 {name} 放入 models 目录；不会自动下载模型')
    from ultralytics import YOLO, settings
    from compute_device import select_device,predict
    selection=select_device(p.get('device','cpu'),'onnx' if name.endswith('.onnx') else 'pt')
    settings.update({'sync': False})
    key = (name, file.stat().st_mtime_ns,selection['device'])
    if key not in MODELS:
        MODELS.clear()  # Bound model memory usage to one loaded model.
        MODELS[key] = YOLO(str(file), task='detect')
    model = MODELS[key]
    if model.task != 'detect':
        raise ValueError('当前节点支持目标检测模型；分割、分类和姿态模型需要独立算子')
    classes = p.get('classes')
    if classes is not None and (not isinstance(classes, list) or any(not isinstance(x, int) or x < 0 for x in classes)):
        raise ValueError('classes 必须是非负类别编号数组')
    prediction = predict(model,image,selection,conf=number(p, 'confidence', 0.25, 0, 1),
                               iou=number(p, 'iou', 0.45, 0, 1), imgsz=int(number(p, 'imageSize', 640, 32, 1920)),
                               classes=classes, max_det=300, verbose=False)
    items = []
    if prediction.boxes is not None:
        for box in prediction.boxes:
            x1, y1, x2, y2 = box.xyxy[0].cpu().tolist()
            x1 += offset[0]; x2 += offset[0]; y1 += offset[1]; y2 += offset[1]
            category = int(box.cls[0])
            score = float(box.conf[0])
            label = prediction.names[category]
            cv2.rectangle(canvas, (round(x1), round(y1)), (round(x2), round(y2)), (0, 210, 80), 2)
            cv2.putText(canvas, f'{label} {score:.2f}', (round(x1), max(16, round(y1)-6)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 210, 80), 1)
            items.append({'classId': category, 'label': label, 'confidence': score, 'bbox': [x1, y1, x2-x1, y2-y1]})
    return {'model': name, 'count': len(items), 'items': items, **selection}



def distort_correct(image, canvas, p, offset):
    """Real OpenCV undistort. Modes: coeffs (inline) or file (JSON calib)."""
    import json as _json
    from pathlib import Path as _Path
    mode = str(p.get('mode') or 'file')
    alpha = float(p.get('alpha') or 0)
    K = None
    D = None
    note = ''
    if mode == 'coeffs' or (p.get('fx') and not p.get('calibPath')):
        fx = float(p.get('fx') or 0); fy = float(p.get('fy') or 0)
        cx = float(p.get('cx') or 0); cy = float(p.get('cy') or 0)
        if fx <= 0 or fy <= 0:
            # fall back to image center estimate only if user left zeros — still mark uncalibrated
            h, w = image.shape[:2]
            if fx <= 0: fx = w * 0.9
            if fy <= 0: fy = h * 0.9
            if cx <= 0: cx = w / 2.0
            if cy <= 0: cy = h / 2.0
            note = '内参缺省用图像尺寸估计'
        K = np.array([[fx, 0, cx], [0, fy, cy], [0, 0, 1]], np.float64)
        D = np.array([float(p.get('k1') or 0), float(p.get('k2') or 0),
                      float(p.get('p1') or 0), float(p.get('p2') or 0),
                      float(p.get('k3') or 0)], np.float64)
    else:
        path = str(p.get('calibPath') or '').strip()
        if not path:
            raise ValueError('未配置标定文件或内参；拒绝静默透传')
        raw = _Path(path).read_text(encoding='utf-8')
        cal = _json.loads(raw)
        # accept sieans-intrinsics model or flat keys
        if 'fx' in cal:
            fx, fy, cx, cy = float(cal['fx']), float(cal['fy']), float(cal['cx']), float(cal['cy'])
            K = np.array([[fx, 0, cx], [0, fy, cy], [0, 0, 1]], np.float64)
            D = np.array([float(cal.get(k) or 0) for k in ('k1','k2','p1','p2','k3')], np.float64)
        elif 'cameraMatrix' in cal:
            K = np.array(cal['cameraMatrix'], np.float64)
            D = np.array(cal.get('distCoeffs') or cal.get('distortion') or [0,0,0,0,0], np.float64).ravel()[:5]
        else:
            raise ValueError('标定文件格式无法识别（需 fx/fy/cx/cy 或 cameraMatrix）')
        note = 'from file: ' + path
    h, w = image.shape[:2]
    newK, _ = cv2.getOptimalNewCameraMatrix(K, D, (w, h), alpha, (w, h))
    und = cv2.undistort(image, K, D, None, newK)
    canvas[:] = und if und.shape == canvas.shape else cv2.resize(und, (canvas.shape[1], canvas.shape[0]))
    # also write into ROI region if offset used — canvas is full source copy
    return {
        'status': 'ok',
        'mode': mode,
        'width': w, 'height': h,
        'cameraMatrix': K.tolist(),
        'newCameraMatrix': newK.tolist(),
        'distCoeffs': D.tolist(),
        'alpha': alpha,
        'note': note or 'undistort ok',
    }


def annotate_geom(canvas, p):
    """Draw measure_geom overlays (line_intersect / point_distance / point_line_distance) onto canvas.

    Params carry both show* toggles and geometry scalars from flow-control results.
    """
    show_ov = _show_flag(p, 'showOverlay', True)
    if not show_ov:
        return {'annotated': False, 'reason': 'showOverlay=false'}
    show_pts = _show_flag(p, 'showPoints', True)
    show_lines = _show_flag(p, 'showLines', True)
    show_labels = _show_flag(p, 'showLabels', True)
    show_dist = _show_flag(p, 'showDistanceText', True)
    kind = str(p.get('kind') or p.get('op') or 'auto')
    color_line = (0, 210, 80)
    color_pt = (0, 165, 255)
    color_txt = (0, 200, 255)

    def _pt(x, y):
        return (int(round(float(x))), int(round(float(y))))

    drawn = []
    # line_intersect: two lines + intersection
    if kind in ('line_intersect', 'auto') and p.get('intersectX') is not None and p.get('x1') is not None:
        if show_lines:
            cv2.line(canvas, _pt(p['x1'], p['y1']), _pt(p['x2'], p['y2']), color_line, 2, cv2.LINE_AA)
            cv2.line(canvas, _pt(p['x3'], p['y3']), _pt(p['x4'], p['y4']), color_line, 2, cv2.LINE_AA)
            drawn.append('lines')
        ix, iy = p['intersectX'], p['intersectY']
        if show_pts and ix is not None and iy is not None:
            cv2.circle(canvas, _pt(ix, iy), 5, color_pt, -1, cv2.LINE_AA)
            drawn.append('intersect')
        if show_labels and ix is not None:
            cv2.putText(canvas, '交点', _pt(float(ix) + 6, float(iy) - 6), cv2.FONT_HERSHEY_SIMPLEX, .5, color_txt, 1, cv2.LINE_AA)
        return {'annotated': True, 'kind': 'line_intersect', 'drawn': drawn}

    # point_distance
    if kind in ('point_distance', 'auto') and p.get('x1') is not None and p.get('x2') is not None and p.get('distance') is not None:
        a, b = _pt(p['x1'], p['y1']), _pt(p['x2'], p['y2'])
        if show_lines:
            cv2.line(canvas, a, b, color_line, 2, cv2.LINE_AA)
            drawn.append('segment')
        if show_pts:
            cv2.circle(canvas, a, 4, color_pt, -1, cv2.LINE_AA)
            cv2.circle(canvas, b, 4, color_pt, -1, cv2.LINE_AA)
            drawn.append('points')
        if show_dist or show_labels:
            mid = ((a[0] + b[0]) // 2, (a[1] + b[1]) // 2)
            unit = str(p.get('unit') or 'px')
            cv2.putText(canvas, f"{float(p['distance']):.3f}{unit}", mid, cv2.FONT_HERSHEY_SIMPLEX, .5, color_txt, 1, cv2.LINE_AA)
            drawn.append('distance')
        return {'annotated': True, 'kind': 'point_distance', 'drawn': drawn}

    # point_line_distance
    if kind in ('point_line_distance', 'auto') and p.get('px') is not None and p.get('x1') is not None:
        ln_a, ln_b = _pt(p['x1'], p['y1']), _pt(p['x2'], p['y2'])
        pt = _pt(p['px'], p['py'])
        if show_lines:
            cv2.line(canvas, ln_a, ln_b, color_line, 2, cv2.LINE_AA)
            drawn.append('line')
        fx, fy = p.get('footX'), p.get('footY')
        if fx is not None and fy is not None and show_lines:
            foot = _pt(fx, fy)
            cv2.line(canvas, pt, foot, (255, 180, 0), 1, cv2.LINE_AA)
            drawn.append('perp')
            if show_pts:
                cv2.circle(canvas, foot, 3, (255, 180, 0), -1, cv2.LINE_AA)
        if show_pts:
            cv2.circle(canvas, pt, 4, color_pt, -1, cv2.LINE_AA)
            drawn.append('point')
        if (show_dist or show_labels) and p.get('distance') is not None:
            unit = str(p.get('unit') or 'px')
            cv2.putText(canvas, f"{float(p['distance']):.3f}{unit}", (pt[0] + 6, pt[1] - 6),
                        cv2.FONT_HERSHEY_SIMPLEX, .5, color_txt, 1, cv2.LINE_AA)
            drawn.append('distance')
        return {'annotated': True, 'kind': 'point_line_distance', 'drawn': drawn}

    return {'annotated': False, 'reason': 'no matching geometry fields'}



def run(request):
    if request.get('operation') == 'depth_import':
        from depth_import import run as run_depth_import
        return run_depth_import(request)
    if request.get('operation')=='compute_devices':
        from compute_device import device_info
        return {'operation':'compute_devices','result':device_info()}
    if str(request.get('operation', '')).startswith('cloud_'):
        from cloud_engine import run as run_cloud
        return run_cloud(request)
    started = time.perf_counter()
    source = decode(request.get('image'))
    p = request.get('params', {})
    if not isinstance(p, dict):
        raise ValueError('params 必须为对象')
    image, offset = roi_image(source, p)
    canvas = source.copy()
    operation = request.get('operation')
    reference = decode(request['reference']) if request.get('reference') else None
    if p.get('templateRoi') is not None:
        reference, _ = roi_image(source, {'roi': p['templateRoi']})
    if operation == 'locate':
        data = locate(image, canvas, p, offset, reference)
    elif operation == 'geometry':
        data = geometry(image, canvas, p, offset)
    elif operation == 'measure':
        data = measure(image, canvas, p, offset)
    elif operation == 'barcode':
        data = barcode(image, canvas, p, offset)
    elif operation == 'ocr':
        data = ocr(image, canvas, p, offset)
    elif operation == 'defects':
        if reference is not None and reference.shape == source.shape:
            reference, _ = roi_image(reference, p)
        data = defects(image, canvas, p, offset, reference)
    elif operation == 'preprocess':
        data = preprocess(image, canvas, p, offset)
    elif operation == 'yolo':
        data = yolo(image, canvas, p, offset)
    elif operation == 'yolo_segment':
        from yolo_segmentation import segment
        data, mask_image = segment(image, canvas, p, offset, MODEL_DIR, MODELS)
    elif operation == 'distort_correct':
        data = distort_correct(image, canvas, p, offset)
    elif operation == 'display':
        # Design-time 图像显示：透传上游图；channel 分离；可选叠加模块名
        ch = (p.get('channel') or 'auto')
        try:
            if ch in ('r', 'g', 'b') and canvas.ndim == 3 and canvas.shape[2] >= 3:
                # OpenCV BGR
                idx = {'b': 0, 'g': 1, 'r': 2}[ch]
                plane = canvas[:, :, idx]
                canvas[:] = cv2.merge([plane, plane, plane]) if canvas.shape[2] == 3 else canvas
                # assign back — canvas may be writeable view
                for c in range(min(3, canvas.shape[2])):
                    canvas[:, :, c] = plane
            elif ch == 'gray':
                if canvas.ndim == 3:
                    gray = cv2.cvtColor(canvas, cv2.COLOR_BGR2GRAY)
                    canvas[:] = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
        except Exception:
            pass
        data = {
            'shown': True,
            'fitMode': p.get('fitMode') or 'contain',
            'channel': ch,
            'showOverlay': bool(p.get('showOverlay', True)),
            'showName': bool(p.get('showName', True)),
        }
        if data['showName']:
            try:
                label = str(p.get('_stepName') or '显示')
                cv2.putText(canvas, label, (12, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 200, 255), 2, cv2.LINE_AA)
            except Exception:
                pass
    elif operation == 'annotate_geom':
        data = annotate_geom(canvas, p)
    else:
        raise ValueError('未知视觉操作')
    extension = '.png' if operation in ('preprocess', 'distort_correct', 'display', 'annotate_geom') or (operation == 'yolo_segment' and p.get('output') == 'mask') else '.jpg'
    _, encoded = cv2.imencode(extension, canvas, [] if extension == '.png' else [cv2.IMWRITE_JPEG_QUALITY, 88])
    return {'operation': operation, 'result': data, 'elapsedMs': round((time.perf_counter()-started)*1000, 1),
            **({'maskImage':mask_image} if operation == 'yolo_segment' else {}),
            'imageSize': {'width': source.shape[1], 'height': source.shape[0]},
            'annotatedImage': ('data:image/png;base64,' if extension == '.png' else 'data:image/jpeg;base64,')+base64.b64encode(encoded).decode()}


if __name__ == '__main__':
    for line in sys.stdin:
        request = {}
        try:
            request = json.loads(line)
            # Keep any model library log output out of the JSON protocol.
            with contextlib.redirect_stdout(sys.stderr):
                result = run(request)
            response = {'id': request['id'], 'ok': True, 'data': result}
        except Exception as error:
            response = {'id': request.get('id'), 'ok': False, 'error': str(error)}
        print(json.dumps(response, ensure_ascii=True, allow_nan=False), flush=True)
