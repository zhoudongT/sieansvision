"""Pixel-area region inspection using OpenCV; coordinates refer to the full image."""
import base64
import cv2
import numpy as np


def run(ctx):
    p = ctx['params']
    image = cv2.imdecode(np.frombuffer(base64.b64decode(ctx['image'].split(',', 1)[-1]), np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError('无法解码输入图像')
    height, width = image.shape[:2]
    x, y = p['roiX'], p['roiY']
    w, h = p['roiWidth'] or width - x, p['roiHeight'] or height - y
    if x >= width or y >= height or x + w > width or y + h > height:
        raise ValueError('检测区域超出输入图像；宽高为 0 表示延伸至图像边界')
    if p['minimumArea'] > p['maximumArea'] or p['minimumCount'] > p['maximumCount']:
        raise ValueError('面积或数量的下限不能大于上限')
    kernel = p['kernelSize']
    if kernel % 2 == 0:
        raise ValueError('形态学核尺寸必须为奇数')
    crop = image[y:y+h, x:x+w]
    if p['method'] == 'hsv':
        if p['saturationMin'] > p['saturationMax'] or p['valueMin'] > p['valueMax']:
            raise ValueError('饱和度或亮度的下限不能大于上限')
        hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
        low, high = p['hueMin'], p['hueMax']
        def band(a, b):
            return cv2.inRange(hsv, (a, p['saturationMin'], p['valueMin']), (b, p['saturationMax'], p['valueMax']))
        mask = band(low, high) if low <= high else cv2.bitwise_or(band(low, 179), band(0, high))
    else:
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        kind = cv2.THRESH_BINARY if p['polarity'] == 'bright' else cv2.THRESH_BINARY_INV
        _, mask = cv2.threshold(gray, p['threshold'], 255, kind)
    if p['morphology'] != 'none':
        operation = cv2.MORPH_OPEN if p['morphology'] == 'open' else cv2.MORPH_CLOSE
        mask = cv2.morphologyEx(mask, operation, np.ones((kernel, kernel), np.uint8))
    count, labels, stats, centers = cv2.connectedComponentsWithStats(mask, connectivity=p['connectivity'])
    keep = []
    for label in range(1, count):
        bx, by, bw, bh, area = map(int, stats[label])
        border = bx == 0 or by == 0 or bx + bw == w or by + bh == h
        if p['minimumArea'] <= area <= p['maximumArea'] and not (p['excludeBorder'] and border):
            keep.append(label)
    # Stable area order, with image position as a tie breaker; retain all counts even when the detail table is capped.
    keep.sort(key=lambda i: (-int(stats[i, cv2.CC_STAT_AREA]), int(stats[i, cv2.CC_STAT_TOP]), int(stats[i, cv2.CC_STAT_LEFT])))
    items = []
    for label in keep[:500]:
        bx, by, bw, bh, area = map(int, stats[label])
        items.append(dict(index=len(items)+1, areaPixels=area, x=bx+x, y=by+y, width=bw, height=bh,
                          centerX=float(centers[label][0]+x), centerY=float(centers[label][1]+y), fillRatio=area/(bw*bh)))
    areas = [int(stats[i, cv2.CC_STAT_AREA]) for i in keep]
    result = dict(count=len(keep), areaPixels=sum(areas), coveragePercent=sum(areas)*100/(w*h),
                  largestArea=max(areas, default=0), roi=dict(x=x, y=y, width=w, height=h), items=items,
                  detailsTruncated=len(keep)>500, passed=p['minimumCount'] <= len(keep) <= p['maximumCount'])
    output = p['outputImage']
    if output == 'original':
        return dict(result=result)
    if output == 'mask':
        selected = np.zeros(count, np.uint8)
        selected[keep] = 255
        shown = np.zeros((height, width), np.uint8)
        shown[y:y+h, x:x+w] = selected[labels]
    else:
        shown = image.copy()
        cv2.rectangle(shown, (x, y), (x+w-1, y+h-1), (200, 140, 0), 1)
        for item in items:
            a, b = item['x'], item['y']
            cv2.rectangle(shown, (a, b), (a+item['width']-1, b+item['height']-1), (0, 220, 0), 1)
            cv2.putText(shown, str(item['index']), (a, max(12, b-3)), cv2.FONT_HERSHEY_SIMPLEX, .45, (0, 180, 0), 1)
    ok, data = cv2.imencode('.png', shown)
    if not ok:
        raise ValueError('无法编码输出图像')
    return dict(result=result, image='data:image/png;base64,'+base64.b64encode(data).decode())
