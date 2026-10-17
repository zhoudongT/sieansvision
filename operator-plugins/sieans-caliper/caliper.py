"""Oriented intensity profiles, interpolated gradient peaks and line/width metrology.

Pixel centres use image coordinates (+X right, +Y down). Fractional locations
are numerical estimates, not a guarantee of physical measurement accuracy.
"""
import base64
import math
import cv2
import numpy as np


def number(p, key, low, high, integer=False):
    value = p[key]
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or not low <= value <= high or (integer and int(value) != value):
        raise ValueError('参数超出范围或类型无效：' + key)
    return int(value) if integer else float(value)


def peaks(profile, positions, sigma, threshold):
    step = float(positions[1] - positions[0])
    radius = int(math.ceil(3 * sigma / step))
    smooth = cv2.GaussianBlur(profile.reshape(1, -1), (2 * radius + 1, 1), sigma / step, borderType=cv2.BORDER_REPLICATE)[0]
    gradient = np.gradient(smooth, step)
    strength = np.abs(gradient)
    found = []
    # Do not use gradients whose filter support touches the search boundary.
    for i in range(radius + 2, len(profile) - radius - 2):
        if strength[i] < threshold or not (strength[i] >= strength[i-1] and strength[i] > strength[i+1]):
            continue
        denominator = strength[i-1] - 2 * strength[i] + strength[i+1]
        offset = 0.0 if abs(denominator) < 1e-12 else float(np.clip(.5 * (strength[i-1] - strength[i+1]) / denominator, -.5, .5))
        found.append(dict(position=float(positions[i] + offset * step), gradient=float(gradient[i]), sign=1 if gradient[i] > 0 else -1))
    return found


def fit_edges(rows, direction, max_residual):
    valid = [r for r in rows if r['valid']]
    if len(valid) < 3:
        return None
    points = np.array([[r['edgeX'], r['edgeY']] for r in valid], np.float32)
    line = cv2.fitLine(points, cv2.DIST_HUBER, 0, .001, .001).ravel().astype(float)
    mask = np.ones(len(points), dtype=bool)
    while True:
        vector, origin = line[:2], line[2:]
        distances = np.abs((points[:, 0] - origin[0]) * vector[1] - (points[:, 1] - origin[1]) * vector[0])
        next_mask = mask & (distances <= max_residual)
        if next_mask.sum() < 3:
            for row in valid:
                row['inlier'] = False
            return None
        stable = np.array_equal(next_mask, mask)
        mask = next_mask
        line = cv2.fitLine(points[mask], cv2.DIST_L2, 0, .001, .001).ravel().astype(float)
        # Re-evaluate after the least-squares refit, even if the robust mask held.
        vector, origin = line[:2], line[2:]
        distances = np.abs((points[:, 0] - origin[0]) * vector[1] - (points[:, 1] - origin[1]) * vector[0])
        if stable and np.all(distances[mask] <= max_residual):
            break
    if float(np.dot(vector, direction)) < 0:
        vector = -vector
    projection = (points[mask] - origin) @ vector
    if float(np.ptp(projection)) < 1:
        return None
    for row, distance, keep in zip(valid, distances, mask):
        row.update(inlier=bool(keep), residualPixels=float(distance))
        if not keep:
            row['reason'] = '偏离拟合直线'
    begin, end = origin + vector * projection.min(), origin + vector * projection.max()
    return dict(x=float(origin[0]), y=float(origin[1]), directionX=float(vector[0]), directionY=float(vector[1]),
                angleDeg=float(math.degrees(math.atan2(vector[1], vector[0]))),
                start=begin.tolist(), end=end.tolist(), rmsPixels=float(np.sqrt(np.mean(distances[mask] ** 2))), inlierCount=int(mask.sum()))


def run(ctx):
    p = ctx['params']
    task = p['task']
    if task not in ('line', 'width'):
        raise ValueError('未知卡尺功能')
    center = np.array([number(p, 'centerX', 0, 32766), number(p, 'centerY', 0, 32766)])
    angle = math.radians(number(p, 'scanAngle', -180, 180))
    length = number(p, 'searchLength', 16, 2048)
    width = number(p, 'caliperWidth', 1, 51, True)
    count = number(p, 'probeCount', 3, 100, True)
    spacing = number(p, 'probeSpacing', 1, 1000)
    sigma = number(p, 'sigma', .2, 5)
    threshold = number(p, 'minimumGradient', .1, 255)
    minimum_ratio = number(p, 'minimumValidRatio', .1, 1)
    if length <= 2 * (math.ceil(3*sigma) + 3):
        raise ValueError('搜索长度过短，请增加长度或减小平滑尺度')
    samples = int(math.ceil(length)) + 1
    if samples * width * count > 2_000_000:
        raise ValueError('卡尺采样量超过 200 万，请减少数量、宽度或搜索长度')
    if task == 'line':
        if p['polarity'] not in ('rising', 'falling', 'either') or p['selection'] not in ('strongest', 'first', 'last'):
            raise ValueError('边缘极性或选择方式无效')
        max_residual = number(p, 'maximumResidual', .01, 100)
        max_rms = number(p, 'maximumRms', .001, 100)
    else:
        if p['bandPolarity'] not in ('bright', 'dark') or p['unit'] not in ('px', 'mm', 'cm', 'm'):
            raise ValueError('条带极性或单位无效')
        scale = number(p, 'unitsPerPixel', .000001, 10000)
        if p['unit'] == 'px' and scale != 1:
            raise ValueError('像素单位要求每像素比例为 1')
        min_sep = number(p, 'minimumSeparation', 1, 2048)
        max_sep = number(p, 'maximumSeparation', 1, 2048)
        low = number(p, 'minimumWidth', 0, 1e9)
        high = number(p, 'maximumWidth', 0, 1e9)
        if min_sep > max_sep or max_sep > length or low > high:
            raise ValueError('边缘间距或合格宽度范围无效')
    raw = base64.b64decode(ctx['image'].split(',', 1)[-1], validate=True)
    image = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError('无法解码卡尺输入图像')
    height, image_width = image.shape[:2]
    if max(height, image_width) >= 32767:
        raise ValueError('卡尺输入图像单边必须小于 32767 像素')
    if center[0] >= image_width or center[1] >= height:
        raise ValueError('卡尺中心超出图像')
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY).astype(np.float32)
    scan = np.array([math.cos(angle), math.sin(angle)])
    cross = np.array([-scan[1], scan[0]])
    positions = np.linspace(-length/2, length/2, samples)
    offsets = np.arange(width) - (width - 1)/2
    rows = []
    for index in range(count):
        origin = center + cross * (index - (count - 1)/2) * spacing
        coordinates = origin + positions[None, :, None]*scan + offsets[:, None, None]*cross
        row = dict(probe=index+1, probeCenterX=float(origin[0]), probeCenterY=float(origin[1]), valid=False, reason='未找到满足条件的边缘')
        rows.append(row)
        corners = np.array([coordinates[0, 0], coordinates[0, -1], coordinates[-1, -1], coordinates[-1, 0]])
        inside = bool(np.all(coordinates[..., 0] >= 0) and np.all(coordinates[..., 0] <= image_width-1) and
                      np.all(coordinates[..., 1] >= 0) and np.all(coordinates[..., 1] <= height-1))
        cv2.polylines(image, [np.round(corners).astype(np.int32)], True, (160, 110, 30) if inside else (40, 40, 220), 1, cv2.LINE_AA)
        if not inside:
            row['reason'] = '采样区域超出图像'
            continue
        pixels = cv2.remap(gray, coordinates[..., 0].astype(np.float32), coordinates[..., 1].astype(np.float32), cv2.INTER_LINEAR)
        candidates = peaks(pixels.mean(axis=0), positions, sigma, threshold)
        cv2.arrowedLine(image, tuple(np.round(origin-scan*8).astype(int)), tuple(np.round(origin+scan*8).astype(int)), (180, 120, 20), 1, cv2.LINE_AA, tipLength=.3)
        if task == 'line':
            edges = [e for e in candidates if p['polarity'] == 'either' or e['sign'] == (1 if p['polarity'] == 'rising' else -1)]
            if not edges:
                continue
            edge = edges[0] if p['selection'] == 'first' else edges[-1] if p['selection'] == 'last' else max(edges, key=lambda e: abs(e['gradient']))
            xy = origin + scan * edge['position']
            row.update(valid=True, reason='', edgeX=float(xy[0]), edgeY=float(xy[1]), gradient=edge['gradient'], inlier=False)
        else:
            sign = 1 if p['bandPolarity'] == 'bright' else -1
            pairs = [(a,b) for a,b in zip(candidates,candidates[1:]) if a['sign'] == sign and b['sign'] == -sign and min_sep <= b['position']-a['position'] <= max_sep]
            if not pairs:
                row['reason'] = '未找到相邻的有效边缘对'
                continue
            first, last = max(pairs, key=lambda pair: min(abs(pair[0]['gradient']), abs(pair[1]['gradient'])))
            a, b = origin + scan*first['position'], origin + scan*last['position']
            distance = last['position'] - first['position']
            measured = distance*scale
            row.update(valid=True, reason='', firstX=float(a[0]), firstY=float(a[1]), secondX=float(b[0]), secondY=float(b[1]),
                       firstGradient=first['gradient'], secondGradient=last['gradient'], widthPixels=distance, width=measured, passed=bool(low <= measured <= high))
            cv2.line(image, tuple(np.round(a).astype(int)), tuple(np.round(b).astype(int)), (60, 200, 60) if row['passed'] else (40, 40, 230), 2, cv2.LINE_AA)
            for xy in (a, b):
                cv2.circle(image, tuple(np.round(xy).astype(int)), 3, (0, 230, 255), -1, cv2.LINE_AA)
    detected = sum(r['valid'] for r in rows)
    result = dict(items=rows, probeCount=count, detectedCount=detected, missingCount=count-detected, found=False, passed=False)
    if task == 'line':
        fitted = fit_edges(rows, cross, max_residual)
        inliers = fitted['inlierCount'] if fitted else 0
        result.update(inlierCount=inliers, validRatio=inliers/count)
        if fitted:
            result.update(line=fitted, rmsPixels=fitted['rmsPixels'], found=True, passed=bool(inliers/count >= minimum_ratio and fitted['rmsPixels'] <= max_rms))
            cv2.line(image, tuple(np.round(fitted['start']).astype(int)), tuple(np.round(fitted['end']).astype(int)), (0, 255, 255), 2, cv2.LINE_AA)
        else:
            for row in rows:
                if row['valid']:
                    row['reason'] = '拟合有效点不足'
        for row in rows:
            if row['valid']:
                cv2.circle(image, (round(row['edgeX']), round(row['edgeY'])), 3, (60, 210, 60) if row.get('inlier') else (40, 40, 230), -1, cv2.LINE_AA)
    else:
        widths = [r['width'] for r in rows if r['valid']]
        result.update(unit=p['unit'], unitsPerPixel=scale, validRatio=detected/count, outOfToleranceCount=sum(not r['passed'] for r in rows if r['valid']))
        if widths:
            result.update(found=True, meanWidth=float(np.mean(widths)), minimumWidth=min(widths), maximumWidth=max(widths),
                          widthStdDev=float(np.std(widths)), passed=bool(detected/count >= minimum_ratio and all(r['passed'] for r in rows if r['valid'])))
    result['diagnostic'] = '测量通过' if result['passed'] else '未形成有效测量' if not result['found'] else '有效卡尺比例、拟合误差或宽度公差不满足要求'
    cv2.putText(image, 'PASS' if result['passed'] else 'FAIL', (15, 30), cv2.FONT_HERSHEY_SIMPLEX, .8, (60, 200, 60) if result['passed'] else (40, 40, 230), 2, cv2.LINE_AA)
    encoded = cv2.imencode('.jpg', image, [cv2.IMWRITE_JPEG_QUALITY, 85])[1]
    return dict(result=result, annotatedImage='data:image/jpeg;base64,'+base64.b64encode(encoded).decode())
