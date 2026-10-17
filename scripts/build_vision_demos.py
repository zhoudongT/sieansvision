"""Generate deterministic teaching fixtures and validate every configured demo."""
import base64
import json
import sys
from pathlib import Path
import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'public/vision/samples'
OUT.mkdir(parents=True, exist_ok=True)

def save(name, image):
    cv2.imwrite(str(OUT / name), image)
    return name

def step(operation, params=None, reference=None):
    return dict(operation=operation, params=params or {}, **({'reference': reference} if reference else {}))

# An asymmetric textured part makes orientation observable and avoids a symmetric match.
template = np.full((80, 110, 3), 45, np.uint8)
cv2.rectangle(template, (5, 5), (104, 74), (210, 210, 210), -1)
cv2.circle(template, (25, 24), 12, (30, 30, 30), -1)
cv2.circle(template, (83, 54), 8, (30, 30, 30), -1)
cv2.arrowedLine(template, (45, 22), (90, 22), (55, 55, 55), 5, tipLength=.3)
cv2.putText(template, 'S1', (43, 61), cv2.FONT_HERSHEY_SIMPLEX, .65, (65, 65, 65), 2)
save('demo-template.png', template)
for name, patch, pos in [('demo-locate.png', template, (310, 160)),
                          ('demo-rotate.png', cv2.rotate(template, cv2.ROTATE_90_COUNTERCLOCKWISE), (430, 130))]:
    scene = np.full((420, 720, 3), 25, np.uint8)
    for x in range(0, 720, 40): cv2.line(scene, (x, 0), (x, 419), (32, 32, 32), 1)
    for y in range(0, 420, 40): cv2.line(scene, (0, y), (719, y), (32, 32, 32), 1)
    cv2.rectangle(scene, (55, 65), (180, 140), (100, 100, 100), -1)
    cv2.circle(scene, (160, 300), 38, (130, 130, 130), -1)
    x, y = pos
    scene[y:y+patch.shape[0], x:x+patch.shape[1]] = patch
    save(name, scene)
parts = cv2.imread(str(OUT / 'parts.png'))
bad = parts.copy()
cv2.rectangle(bad, (100, 100), (130, 130), (0, 0, 0), -1)
save('demo-defect.png', bad)
rect_roi = [30, 40, 250, 170]
calibration = {'points': [[0, 0], [100, 0]], 'distance': 10}
DEMOS = []
def demo(id, category, name, description, image, steps, expected, check):
    DEMOS.append(dict(id=id, category=category, name=name, description=description,
                      image=image, steps=steps, expected=expected, check=check))

demo('locate', '定位', '模板平移定位', '从多个形状中找到指定零件，输出中心位置和匹配分数。', 'demo-locate.png',
     [step('locate', {'minScore': .9}, 'demo-template.png')], '找到目标；中心约 (365, 200)，角度 0°。', {'found': True, 'angleDeg': 0})
demo('rotate', '定位', '90° 旋转定位', '同一零件旋转后搜索位置及方向，比较模板旋转角度。', 'demo-rotate.png',
     [step('locate', {'minScore': .85, 'angleStart': 0, 'angleEnd': 180, 'angleStep': 90}, 'demo-template.png')],
     '找到目标；角度 90°，中心约 (470, 185)。', {'found': True, 'angleDeg': 90})
demo('codes', '识别', '条码与二维码同时读取', '一张图同时读取 QR 和 Code128，查看码制及内容。', 'codes.png',
     [step('barcode')], '读出 MACHINE-QR-2026 和 ABC123456789 两条内容。', {'count': 2})
demo('qr-roi', '识别', 'ROI 指定区域读码', '使用矩形 ROI 仅识别左上方二维码，忽略一维条码。', 'codes.png',
     [step('barcode', {'roi': [0, 0, 270, 230]})], '仅返回二维码 MACHINE-QR-2026。', {'count': 1})
demo('ocr', '识别', '批次号与序列号 OCR', '读取两行标签文字，查看文本、置信度与顶点坐标。', 'text.png',
     [step('ocr', {'minConfidence': .5})], '包含批次号 20261015 和序列号 ABC12345；首次加载模型稍慢。', {'textContains': ['20261015', 'ABC12345']})
demo('contours', '几何', '轮廓与面积查找', '提取矩形、圆形和线条的轮廓，对比包围框及面积。', 'parts.png',
     [step('geometry', {'feature': 'contours', 'threshold': 127, 'minArea': 50})], '返回 3 个轮廓；矩形面积 20000 px²。', {'count': 3})
demo('circle', '几何', '圆心与直径检测', '在圆所在区域查找圆，输出圆心、半径和直径。', 'parts.png',
     [step('geometry', {'feature': 'circles', 'roi': [350, 40, 220, 200], 'minRadius': 45, 'maxRadius': 65, 'minDistance': 80})],
     '圆心约 (450, 135)，半径约 55 px。', {'minCount': 1})
demo('line', '几何', '直线与角度检测', '在下方 ROI 查找直线，观察端点、长度及角度。', 'parts.png',
     [step('geometry', {'feature': 'lines', 'roi': [40, 260, 600, 90], 'minLength': 300})],
     '检测到长度超过 400 px 的水平线；粗线可能产生多条边缘。', {'minCount': 1})
demo('measure', '测量', '标定后的矩形测量', '用 100 px = 10 mm 的标定比例测量矩形长短边。', 'parts.png',
     [step('measure', {'roi': rect_roi, 'calibration': calibration, 'unit': 'mm'})],
     '短边约 10 mm、长边约 20 mm；单位为 mm。', {'count': 1, 'unit': 'mm'})
demo('distance', '测量', '两点距离测量', '指定矩形上边两个端点，演示像素到物理距离的换算。', 'parts.png',
     [step('measure', {'points': [[50, 70], [250, 70]], 'calibration': calibration, 'unit': 'mm'})],
     '两点距离为 20 mm。', {'distance': 20, 'unit': 'mm'})
demo('defect', '检测', '缺口差分检测', '将带缺口的图像与良品对比，输出疑似缺陷区域。', 'demo-defect.png',
     [step('defects', {'differenceThreshold': 30, 'minArea': 20}, 'parts.png')],
     '返回 1 处差异区域，判定不通过。', {'count': 1, 'passed': False})
demo('good', '检测', '良品对照验证', '输入图与良品参考图一致，用于观察无缺陷的输出。', 'parts.png',
     [step('defects', {}, 'parts.png')], '缺陷数量 0，判定通过。', {'count': 0, 'passed': True})
demo('pipeline', '流程', '滤波 → 二值化 → 轮廓', '串联三个算子，观察预处理图像如何传给下一个模块。', 'parts.png',
     [step('preprocess', {'method': 'blur', 'kernel': 5}), step('preprocess', {'method': 'threshold', 'threshold': 127}),
      step('geometry', {'feature': 'contours', 'minArea': 50})], '流程执行 3 步，最后返回 3 个轮廓。', {'count': 3})
demo('branches', '流程', '分支与汇合 · 无序连线', '图像源分成预处理与圆检测两路，轮廓节点等待两路完成，选择预处理图像作为输入。', 'parts.png',
     [step('geometry', {'feature': 'contours', 'minArea': 50}),
      step('preprocess', {'method': 'threshold', 'threshold': 127}),
      step('geometry', {'feature': 'circles', 'roi': [350, 40, 220, 200], 'minRadius': 45, 'maxRadius': 65, 'minDistance': 80})],
     '节点 02、03 先执行，节点 01 汇合后返回 3 个轮廓；移动位置不改变执行关系。', {'count': 3})
DEMOS[-1]['connections'] = [[-1, 1], [-1, 2], [1, 0], [2, 0]]
DEMOS[-1]['imageParents'] = [1, -1, -1]
demo('python-vars', '流程', '识别结果 → Python → 三级变量', '轮廓检测后由 Python 判定数量，并保存全局、流程和模块变量。载入后勾选“运行可信脚本”再运行。', 'parts.png',
     [step('geometry', {'feature': 'contours', 'minArea': 50}), step('script', {'timeoutMs': 5000, 'code': '''def run(ctx):
    detection = next(v for v in ctx["results"].values() if "count" in v)
    count = detection["count"]
    values = ctx["vars"]
    values["global"]["demoCycles"] = values["global"].get("demoCycles", 0) + 1
    values["flow"]["lastCount"] = count
    values["module"]["calls"] = values["module"].get("calls", 0) + 1
    print("Detected", count, "objects")
    return {"result": {"count": count, "passed": count == 3}, "variables": values}
'''})], '返回 count=3、passed=true；变量管理中可查看三级变量。', {'count': 3, 'passed': True})
(OUT / 'demos.json').write_text(json.dumps(DEMOS, ensure_ascii=False, indent=2), encoding='utf-8')

if '--verify' in sys.argv:
    sys.path.insert(0, str(ROOT / 'vision'))
    from engine import run
    def encoded(name): return base64.b64encode((OUT / name).read_bytes()).decode()
    for case in DEMOS:
        if case.get('connections') or any(s['operation'] in ('script', 'variables') for s in case['steps']):
            continue  # Validated through the graph runner in tests/test_flow_graph.cjs.
        image = encoded(case['image'])
        for node in case['steps']:
            response = run(dict(operation=node['operation'], image=image, params=node['params'],
                                reference=encoded(node['reference']) if node.get('reference') else ''))
            if node['operation'] == 'preprocess': image = response['annotatedImage']
        result = response['result']
        for key, expected in case['check'].items():
            if key == 'minCount': assert result['count'] >= expected, (case['id'], result)
            elif key == 'textContains': assert all(text in result['text'] for text in expected), (case['id'], result)
            else: assert result[key] == expected, (case['id'], key, result)
        print('PASS', case['id'], flush=True)
print(f'Generated {len(DEMOS)} demos')
