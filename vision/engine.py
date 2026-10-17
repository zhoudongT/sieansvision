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
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    mode = p.get('feature', 'contours')
    ox, oy = offset
    result = []
    if mode in ('lines', 'edges'):
        edges = cv2.Canny(gray, number(p, 'cannyLow', 50, 0, 255), number(p, 'cannyHigh', 150, 0, 255))
        if mode == 'edges':
            canvas[oy:oy+gray.shape[0], ox:ox+gray.shape[1]][edges > 0] = (0, 210, 80)
            return {'feature': mode, 'edgePixels': int(np.count_nonzero(edges))}
        lines = cv2.HoughLinesP(edges, 1, np.pi/180, int(number(p, 'votes', 40, 1, 10000)),
                               minLineLength=number(p, 'minLength', 40, 1, 10000), maxLineGap=number(p, 'maxGap', 10, 0, 1000))
        for x1, y1, x2, y2 in ([] if lines is None else lines.reshape(-1, 4)[:100]):
            a, b = (int(x1)+ox, int(y1)+oy), (int(x2)+ox, int(y2)+oy)
            cv2.line(canvas, a, b, (0, 210, 80), 2)
            result.append({'start': a, 'end': b, 'lengthPixels': math.hypot(x2-x1, y2-y1),
                           'angleDeg': math.degrees(math.atan2(y2-y1, x2-x1))})
    elif mode == 'circles':
        found = cv2.HoughCircles(cv2.GaussianBlur(gray, (5, 5), 1), cv2.HOUGH_GRADIENT, 1.2,
                                number(p, 'minDistance', 30, 1, 10000),
                                param1=number(p, 'cannyHigh', 150, 1, 255), param2=number(p, 'votes', 30, 1, 1000),
                                minRadius=int(number(p, 'minRadius', 5, 0, 10000)), maxRadius=int(number(p, 'maxRadius', 200, 0, 10000)))
        for x, y, r in ([] if found is None else found.reshape(-1, 3)[:100]):
            center = [float(x)+ox, float(y)+oy]
            cv2.circle(canvas, tuple(map(round, center)), round(float(r)), (0, 210, 80), 2)
            result.append({'center': center, 'radiusPixels': float(r), 'diameterPixels': float(2*r)})
    elif mode == 'contours':
        for c in contours(gray, p):
            c = c + np.array([[[ox, oy]]])
            x, y, w, h = cv2.boundingRect(c)
            cv2.drawContours(canvas, [c], -1, (0, 210, 80), 2)
            result.append({'bbox': [x, y, w, h], 'areaPixels': cv2.contourArea(c),
                           'perimeterPixels': cv2.arcLength(c, True), 'points': c[:, 0].tolist()})
    else:
        raise ValueError('feature 必须是 lines、circles、edges 或 contours')
    return {'feature': mode, 'count': len(result), 'items': result}


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
        cv2.line(canvas, tuple(np.round(pts[0]).astype(int)), tuple(np.round(pts[1]).astype(int)), (0, 210, 80), 2)
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
                polygon(canvas, points)
                items.append({'centerPixels': center, 'width': min(dimensions)*ratio, 'height': max(dimensions)*ratio,
                              'area': cv2.contourArea(contour)*ratio*ratio,
                              'offset': ((np.array(center)-origin)*ratio).tolist()})
        else:
            raise ValueError('测量 feature 必须为 contours 或 circles，或提供 points 测距')
        data = {'count': len(items), 'items': items}
    return {**data, 'calibrated': calibrated, 'unitsPerPixel': ratio, 'unit': unit,
            'note': '两点等比例标定，适用于固定平面和垂直拍摄；未补偿透视或镜头畸变'}


def barcode(image, canvas, p, offset):
    import zxingcpp
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
    items = []
    for points, text, confidence in result or []:
        if confidence < minimum:
            continue
        points = np.array(points)+np.array(offset)
        polygon(canvas, points)
        items.append({'text': text, 'confidence': float(confidence), 'polygon': points.tolist()})
    return {'text': '\n'.join(item['text'] for item in items), 'count': len(items), 'items': items}


def defects(image, canvas, p, offset, reference):
    if reference is None:
        raise ValueError('缺陷检测需要同尺寸、同位置、相同光照的良品参考图')
    if image.shape != reference.shape:
        raise ValueError('良品参考图必须与检测区域尺寸一致')
    a = cv2.GaussianBlur(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY), (3, 3), 0)
    b = cv2.GaussianBlur(cv2.cvtColor(reference, cv2.COLOR_BGR2GRAY), (3, 3), 0)
    delta = cv2.absdiff(a, b)
    _, mask = cv2.threshold(delta, number(p, 'differenceThreshold', 30, 1, 255), 255, cv2.THRESH_BINARY)
    minimum = number(p, 'minArea', 20, 1, MAX_PIXELS)
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
        cv2.drawContours(canvas, [c], -1, (0, 0, 255), 2)
        items.append({'bbox': [x, y, w, h], 'areaPixels': area})
    ratio = float(np.count_nonzero(accepted))/mask.size
    allowed = number(p, 'maxDefectRatio', 0, 0, 1)
    return {'passed': ratio <= allowed, 'count': len(items), 'defectRatio': ratio, 'items': items,
            'note': '参考图差分结果为疑似缺陷；位移、光照变化也会产生差异，不自动分类划痕或污点'}


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
    else:
        raise ValueError('未知视觉操作')
    extension = '.png' if operation == 'preprocess' or operation == 'yolo_segment' and p.get('output') == 'mask' else '.jpg'
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
