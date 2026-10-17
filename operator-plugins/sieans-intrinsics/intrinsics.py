"""Pinhole camera calibration; OpenCV five coefficient distortion model."""
import base64
import math
import cv2
import numpy as np


def numeric(value, label, low, high, integer=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high or integer and int(value) != value:
        raise ValueError(label+'超出范围或类型无效')
    return int(value) if integer else float(value)


def image_from(ctx):
    from PIL import Image
    import io
    raw = base64.b64decode(ctx['image'].split(',', 1)[-1], validate=True)
    if len(raw) > 12_000_000:
        raise ValueError('图像超过 12 MB')
    with Image.open(io.BytesIO(raw)) as header:
        if header.width * header.height > 16_000_000:
            raise ValueError('图像超过 1600 万像素')
    image = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError('无法解码图像')
    return image


def encode(image):
    return 'data:image/png;base64,'+base64.b64encode(cv2.imencode('.png', image)[1]).decode()


def board(p):
    cols = numeric(p['columns'], '内角点列数', 3, 15, True)
    rows = numeric(p['rows'], '内角点行数', 3, 15, True)
    if cols*rows*6 > 1000:
        raise ValueError('该棋盘六视图超过 1000 行容量，请减少内角点行列')
    square = numeric(p['squareSize'], '格边长', .001, 10000)
    obj = np.zeros((cols*rows, 3), np.float32)
    obj[:, :2] = np.mgrid[0:cols, 0:rows].T.reshape(-1, 2)*square
    return cols, rows, obj


def point_table(value, cols, rows, width, height):
    if not isinstance(value, list) or len(value) > 1000:
        raise ValueError('角点表最多 1000 行')
    groups = {}
    for row in value:
        if not isinstance(row, dict) or set(row) != {'view', 'column', 'row', 'x', 'y', 'width', 'height'}:
            raise ValueError('角点表必须包含视图、列、行、X、Y及采集尺寸')
        if row['width'] != width or row['height'] != height or isinstance(row['width'], bool) or isinstance(row['height'], bool):
            raise ValueError('累计视图的图像尺寸不一致')
        view = numeric(row['view'], '视图编号', 1, 999999, True)
        col = numeric(row['column'], '角点列', 0, cols-1, True)
        r = numeric(row['row'], '角点行', 0, rows-1, True)
        x = numeric(row['x'], '图像 X', 0, width-1)
        y = numeric(row['y'], '图像 Y', 0, height-1)
        group = groups.setdefault(view, {})
        if (col, r) in group:
            raise ValueError('同一视图有重复角点')
        group[col, r] = [x, y]
    for group in groups.values():
        if len(group) != cols*rows:
            raise ValueError('每个视图必须包含完整棋盘格角点')
    return groups


def model(value, width, height):
    keys = {'version', 'model', 'width', 'height', 'fx', 'fy', 'cx', 'cy', 'k1', 'k2', 'p1', 'p2', 'k3'}
    if not isinstance(value, dict) or set(value) != keys or value['version'] != 1 or value['model'] != 'pinhole-opencv5':
        raise ValueError('需要完整的针孔相机标定结果')
    if value['width'] != width or value['height'] != height:
        raise ValueError('图像尺寸与标定尺寸不一致；不能直接复用')
    for key in keys-{'model'}:
        numeric(value[key], key, -1e9, 1e9)
    fx = numeric(value['fx'], 'fx', 1e-6, width*100)
    fy = numeric(value['fy'], 'fy', 1e-6, height*100)
    numeric(value['cx'], 'cx', 0, width-1)
    numeric(value['cy'], 'cy', 0, height-1)
    k = np.array([[fx, 0, value['cx']], [0, fy, value['cy']], [0, 0, 1]], np.float64)
    d = np.array([value[key] for key in ['k1', 'k2', 'p1', 'p2', 'k3']], np.float64)
    if np.any(np.abs(d)>100):
        raise ValueError('畸变系数超出支持范围')
    return k, d


def run(ctx):
    p = ctx['params']
    task = p['task']
    if task == 'undistort':
        image = image_from(ctx)
        height, width = image.shape[:2]
        k, d = model(p['calibration'], width, height)
        # Keep K and full dimensions: no hidden crop or principal-point change.
        out = cv2.undistort(image, k, d, None, k)
        corrected = {**p['calibration'], **dict.fromkeys(['k1', 'k2', 'p1', 'p2', 'k3'], 0.)}
        return dict(image=encode(out), result=dict(width=width, height=height, calibration=corrected,
                    note='输出保持原尺寸和原内参；无有效源像素区域填黑。后续点位须使用校正图坐标。'))
    cols, rows, obj = board(p)
    if task == 'corners':
        image = image_from(ctx)
        height, width = image.shape[:2]
        groups = point_table(p['points'], cols, rows, width, height)
        view = numeric(p['view'], '视图编号', 1, 999999, True)
        if view in groups:
            raise ValueError('视图编号已存在，请换一个编号或清空采集变量')
        if len(p['points'])+cols*rows > 1000:
            raise ValueError('累计角点超过 1000 行，请减少视图或棋盘角点数')
        found, corners = cv2.findChessboardCornersSB(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY), (cols, rows), cv2.CALIB_CB_NORMALIZE_IMAGE)
        if not found:
            raise ValueError('未找到完整棋盘格，请检查内角点行列、清晰度及边缘留白')
        points = list(p['points'])+[dict(view=view, column=i % cols, row=i//cols, x=float(v[0]), y=float(v[1]), width=width, height=height) for i, v in enumerate(corners.reshape(-1, 2))]
        canvas = image.copy()
        cv2.drawChessboardCorners(canvas, (cols, rows), corners, True)
        return dict(annotatedImage=encode(canvas), result=dict(points=points, viewCount=len(groups)+1, width=width, height=height, cornerCount=cols*rows))
    if task != 'calibrate':
        raise ValueError('未知标定功能')
    width = numeric(p['width'], '标定图像宽度', 32, 16000, True)
    height = numeric(p['height'], '标定图像高度', 32, 16000, True)
    if width*height > 16_000_000:
        raise ValueError('图像超过 1600 万像素')
    groups = point_table(p['points'], cols, rows, width, height)
    if len(groups) < 6:
        raise ValueError('至少需要 6 个不同姿态的完整视图，建议 10–15 个')
    images = [np.array([group[c, r] for r in range(rows) for c in range(cols)], np.float32) for group in groups.values()]
    # Duplicate/frontoparallel views cannot constrain intrinsics. Zhang's V matrix
    # must have at least rank five, independently of an optimizer's low residual.
    constraints = []
    for points in images:
        h, _ = cv2.findHomography(obj[:, :2], points, 0)
        if h is None:
            raise ValueError('角点分布退化')
        def v(i, j):
            return np.array([h[0,i]*h[0,j], h[0,i]*h[1,j]+h[1,i]*h[0,j], h[1,i]*h[1,j], h[2,i]*h[0,j]+h[0,i]*h[2,j], h[2,i]*h[1,j]+h[1,i]*h[2,j], h[2,i]*h[2,j]])
        constraints.extend([v(0, 1), v(0, 0)-v(1, 1)])
    constraints = np.asarray(constraints)
    constraints /= np.linalg.norm(constraints, axis=1)[:, None]
    singular = np.linalg.svd(constraints, compute_uv=False)
    if not np.isfinite(singular).all() or singular[4]/singular[0] < 1e-8:
        raise ValueError('视图姿态退化，请增加绕不同轴倾斜的棋盘格视图')
    objects = [obj.copy() for _ in images]
    rms, k, d, rotations, translations = cv2.calibrateCamera(objects, images, (width, height), None, None,
        criteria=(cv2.TERM_CRITERIA_EPS+cv2.TERM_CRITERIA_COUNT, 60, 1e-9))
    errors = []
    for index, points in enumerate(images):
        projected, _ = cv2.projectPoints(obj, rotations[index], translations[index], k, d)
        error = float(np.sqrt(np.mean(np.sum((points-projected.reshape(-1, 2))**2, axis=1))))
        errors.append(dict(view=list(groups)[index], rmsPixels=error, cornerCount=len(points)))
    maximum = numeric(p['maxRms'], '最大重投影误差', .001, 100)
    if not math.isfinite(rms) or rms > maximum or any(v['rmsPixels'] > maximum for v in errors):
        raise ValueError('重投影误差超限，请检查角点、视图姿态及棋盘平整度')
    calibration = dict(version=1, model='pinhole-opencv5', width=width, height=height,
                       fx=float(k[0,0]), fy=float(k[1,1]), cx=float(k[0,2]), cy=float(k[1,2]),
                       **dict(zip(['k1','k2','p1','p2','k3'], map(float, d.ravel()))))
    model(calibration, width, height)
    return dict(result=dict(calibration=calibration, rmsPixels=float(rms), viewCount=len(groups), items=errors,
                note='重投影误差是拟合残差；需用独立视图和已知尺寸验收。更改焦距、裁剪或缩放后须重新标定。'))
