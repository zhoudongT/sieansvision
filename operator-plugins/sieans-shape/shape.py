"""Binary silhouette teaching and Hu contour matching, without pose estimation."""
import base64
import hashlib
import math
import cv2
import numpy as np


def number(p, key, low, high, integer=False):
    v = p[key]
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or not low <= v <= high or integer and int(v) != v:
        raise ValueError('参数类型或范围无效：' + key)
    return int(v) if integer else float(v)


def contour(value):
    if not isinstance(value, list) or not 3 <= len(value) <= 4096:
        raise ValueError('模型轮廓须包含 3–4096 个点')
    if any(not isinstance(row, list) or len(row) != 2 or any(isinstance(v, bool) or not isinstance(v, int) or not 0 <= v <= 32767 for v in row) for row in value):
        raise ValueError('模型轮廓坐标无效')
    c = np.asarray(value, np.int32).reshape(-1, 1, 2)
    if abs(cv2.contourArea(c)) < 4 or abs(cv2.moments(c)['m00']) < 4:
        raise ValueError('模型轮廓退化')
    return c


def model_read(model, hole_ratio):
    if not isinstance(model, dict) or model.get('kind') != 'sieans-silhouette' or type(model.get('version')) is not int or model['version'] != 1:
        raise ValueError('请绑定轮廓建模算子生成的模型')
    outer = contour(model.get('contour'))
    holes = model.get('holes')
    if not isinstance(holes, list) or len(holes) > 64:
        raise ValueError('模型孔洞记录无效')
    holes = [contour(h) for h in holes]
    if sum(len(c) for c in [outer] + holes) > 12000:
        raise ValueError('模型轮廓复杂度超限')
    for hole in holes:
        if any(cv2.pointPolygonTest(outer, (float(x), float(y)), False) <= 0 for x, y in hole[:, 0]):
            raise ValueError('模型孔洞必须在外轮廓内部')
    area = abs(cv2.contourArea(outer))
    if sum(abs(cv2.contourArea(h)) for h in holes) >= area:
        raise ValueError('模型孔洞面积无效')
    ratios = sorted((abs(cv2.contourArea(h))/area for h in holes if abs(cv2.contourArea(h))/area >= hole_ratio), reverse=True)
    return outer, area, ratios


def run(ctx):
    p = ctx['params']
    task = p['task']
    if task not in ('teach', 'match') or p['polarity'] not in ('bright', 'dark'):
        raise ValueError('算子功能或极性无效')
    x, y = [number(p, k, 0, 32767, True) for k in ('roiX', 'roiY')]
    w, h = [number(p, k, 0, 32768, True) for k in ('roiWidth', 'roiHeight')]
    threshold = number(p, 'threshold', 0, 255, True)
    minimum_area = number(p, 'minimumArea', 4, 16000000)
    maximum_area = number(p, 'maximumArea', 4, 16000000)
    hole_ratio = number(p, 'minimumHoleRatio', 0, 1)
    if minimum_area > maximum_area:
        raise ValueError('面积下限不能大于上限')
    if task == 'match':
        max_score = number(p, 'maximumScore', 0, 10)
        min_scale = number(p, 'minimumScale', .01, 100)
        max_scale = number(p, 'maximumScale', .01, 100)
        min_count = number(p, 'minimumCount', 1, 200, True)
        max_count = number(p, 'maximumCount', 1, 200, True)
        hole_error = number(p, 'maximumHoleRatioError', 0, 1)
        if min_scale > max_scale or min_count > max_count:
            raise ValueError('比例或数量下限不能大于上限')
        if type(p['checkHoles']) is not bool:
            raise ValueError('孔洞检查必须为开关')
        reference, ref_area, ref_holes = model_read(p['model'], hole_ratio)
    try:
        raw = base64.b64decode(ctx['image'].split(',', 1)[1], validate=True)
    except (ValueError, KeyError, AttributeError, IndexError):
        raise ValueError('输入图像无效') from None
    image = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError('无法解码输入图像')
    height, width = image.shape[:2]
    if width > 32768 or height > 32768 or width*height > 16000000:
        raise ValueError('图像最多 1600 万像素且单边不超过 32768')
    w, h = w or width-x, h or height-y
    if x >= width or y >= height or w < 1 or h < 1 or x+w > width or y+h > height:
        raise ValueError('检测区域超出图像')
    gray = cv2.cvtColor(image[y:y+h, x:x+w], cv2.COLOR_BGR2GRAY)
    _, mask = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY if p['polarity'] == 'bright' else cv2.THRESH_BINARY_INV)
    contours, hierarchy = cv2.findContours(mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    if len(contours) > 10000:
        raise ValueError('分割碎片过多，请调整阈值或缩小区域')
    candidates, boundary = [], 0
    if hierarchy is not None:
        for i, c in enumerate(contours):
            if hierarchy[0][i][3] != -1:
                continue
            area = abs(cv2.contourArea(c))
            if not minimum_area <= area <= maximum_area:
                continue
            bx, by, bw, bh = cv2.boundingRect(c)
            if bx == 0 or by == 0 or bx+bw == w or by+bh == h:
                boundary += 1
                continue
            holes, child = [], int(hierarchy[0][i][2])
            while child != -1:
                holes.append(contours[child])
                child = int(hierarchy[0][child][0])
            if len(c) < 3 or len(c) > 4096 or len(holes) > 64 or any(len(k) > 4096 for k in holes) or sum(len(k) for k in [c]+holes) > 12000:
                raise ValueError('轮廓复杂度超限，请简化分割区域')
            candidates.append((c, holes, area))
    if len(candidates) > 200 or sum(len(c)+sum(len(k) for k in holes) for c, holes, _ in candidates) > 100000:
        raise ValueError('候选目标或轮廓总复杂度超限，不返回不完整计数')
    candidates.sort(key=lambda item: (cv2.boundingRect(item[0])[1], cv2.boundingRect(item[0])[0]))
    result = dict(items=[], candidateCount=len(candidates), boundaryRejectedCount=boundary, count=0, found=False, passed=False)
    shown = image.copy()
    cv2.rectangle(shown, (x, y), (x+w-1, y+h-1), (210, 150, 20), 1)
    if task == 'teach' and len(candidates) != 1:
        raise ValueError('建模区域须恰好包含一个完整且符合面积范围的目标，当前数量：' + str(len(candidates)))
    for index, (c, holes, area) in enumerate(candidates, 1):
        moments = cv2.moments(c)
        if abs(moments['m00']) < 4:
            raise ValueError('候选轮廓退化')
        ratios = sorted((abs(cv2.contourArea(k))/area for k in holes if abs(cv2.contourArea(k))/area >= hole_ratio), reverse=True)
        box = cv2.minAreaRect(c)
        bx, by, bw, bh = cv2.boundingRect(c)
        row = dict(index=index, centerX=moments['m10']/moments['m00']+x, centerY=moments['m01']/moments['m00']+y,
                   outerAreaPixels=area, longSidePixels=float(max(box[1])), shortSidePixels=float(min(box[1])),
                   holeCount=len(ratios), x=bx+x, y=by+y, width=bw, height=bh)
        if task == 'teach':
            # Keep all hole geometry so the same relative cutoff can be applied later.
            origin = np.array([[[bx, by]]], dtype=np.int32)
            result['model'] = dict(kind='sieans-silhouette', version=1, contour=(c-origin)[:, 0].tolist(),
                                   holes=[(k-origin)[:, 0].tolist() for k in holes], sourceSha256=hashlib.sha256(image.tobytes()).hexdigest())
            model_read(result['model'], hole_ratio)
            row.update(matched=True, reason='模型已建立')
        else:
            score = float(cv2.matchShapes(reference, c, cv2.CONTOURS_MATCH_I1, 0))
            scale = math.sqrt(area/ref_area)
            # Finite large scores are dissimilarity values, never confidence probabilities.
            if not math.isfinite(score):
                raise ValueError('轮廓比较产生无效数值')
            holes_ok = len(ratios) == len(ref_holes) and all(abs(a-b) <= hole_error for a, b in zip(ratios, ref_holes))
            matched = score <= max_score and min_scale <= scale <= max_scale and (holes_ok or not p['checkHoles'])
            reasons = []
            if score > max_score: reasons.append('外轮廓差异超限')
            if not min_scale <= scale <= max_scale: reasons.append('面积等效比例超限')
            if p['checkHoles'] and not holes_ok: reasons.append('孔洞数量或面积比例不符')
            row.update(matched=bool(matched), huDifference=score, areaScale=scale, reason='匹配' if matched else '；'.join(reasons))
        result['items'].append(row)
        result['count'] += int(row['matched'])
        color = (40, 190, 40) if row['matched'] else (40, 40, 220)
        offset = np.array([[[x, y]]], dtype=np.int32)
        cv2.drawContours(shown, [c+offset]+[k+offset for k in holes], -1, color, 2)
        cv2.drawMarker(shown, (round(row['centerX']), round(row['centerY'])), color, cv2.MARKER_CROSS, 12, 1)
        cv2.putText(shown, str(index), (bx+x, max(12, by+y-4)), cv2.FONT_HERSHEY_SIMPLEX, .5, color, 1)
    result['found'] = result['count'] > 0
    result['passed'] = task == 'teach' or min_count <= result['count'] <= max_count
    result['diagnostic'] = '建模成功' if task == 'teach' else '匹配数量通过' if result['passed'] else '匹配数量不满足要求'
    if boundary: result['diagnostic'] += '；已排除触及区域边界的目标 ' + str(boundary)
    encoded = cv2.imencode('.jpg', shown, [cv2.IMWRITE_JPEG_QUALITY, 85])[1]
    return dict(result=result, annotatedImage='data:image/jpeg;base64,'+base64.b64encode(encoded).decode())
