"""Reproducible silhouettes for contour teaching, matching, holes and count guards."""
import json
from pathlib import Path
import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT/'public/vision/samples'
OUTER = np.array([[-40, -50], [40, -50], [40, -15], [10, -15], [10, 50], [-40, 50]], dtype=float)
angles = np.linspace(0, 2*np.pi, 48, endpoint=False)
HOLE = np.column_stack((-20+8*np.cos(angles), -25+8*np.sin(angles)))


def target(image, center, angle=0, scale=1, hole=True):
    a = np.radians(angle)
    matrix = np.array([[np.cos(a), -np.sin(a)], [np.sin(a), np.cos(a)]])*scale
    def points(p): return np.rint(p@matrix.T+center).astype(np.int32)
    cv2.fillPoly(image, [points(OUTER)], 230)
    if hole: cv2.fillPoly(image, [points(HOLE)], 20)


def scene(kind):
    image = np.full((480, 640), 20, np.uint8)
    target(image, [85, 100])
    if kind == 'multi':
        for center, a, scale in [([280, 110], 0, .75), ([480, 120], 35, 1), ([330, 330], -65, 1.2)]:
            target(image, center, a, scale)
        cv2.circle(image, (520, 330), 40, 230, -1)
    elif kind == 'hole-missing': target(image, [350, 250], 35, 1, False)
    return image


def step(op, args, bindings):
    return dict(operation='plugin', params=dict(pluginId='sieans-shape', pluginVersion='1.0.0', operatorId=op, arguments=args, outputBindings=bindings))


def bind(field, name): return dict(field=field, scope='flow', name=name)


def generate():
    for name, image in [('shape-multi', scene('multi')), ('shape-hole-missing', scene('hole-missing')), ('shape-empty', scene('empty')), ('shape-dark', 255-scene('multi'))]:
        cv2.imwrite(str(SAMPLES/(name+'.png')), image)
    cases = []
    for name, title, source, expected, overrides in [
        ('shape-multi', '轮廓识别 · 多角度与比例', 'shape-multi', '三个 L 形轮廓通过，圆形被排除；计数为 3。', dict(minimumCount=3, maximumCount=3)),
        ('shape-hole-missing', '轮廓识别 · 缺孔排除', 'shape-hole-missing', '外轮廓相似但孔洞缺失，不匹配、不通过。', {}),
        ('shape-empty', '轮廓识别 · 无目标诊断', 'shape-empty', '搜索区域无候选；计数 0，不通过，不产生目标坐标。', {}),
        ('shape-unique-guard', '轮廓识别 · 唯一目标保护', 'shape-multi', '三个匹配但允许数量为 1，找到为是、通过为否。', {}),
        ('shape-dark', '轮廓识别 · 暗目标', 'shape-dark', '反转前景极性，仍识别三个旋转缩放目标。', dict(polarity='dark', minimumCount=3, maximumCount=3)),
    ]:
        teaching = dict(roiX=20, roiY=20, roiWidth=130, roiHeight=170)
        if name == 'shape-dark': teaching['polarity'] = 'dark'
        matching = dict(roiX=200, model={'$ref': 'flow.silhouette'}, **overrides)
        demo = dict(id=name, name=title, category='识别', image=source+'.png',
                    description='先在左侧参考区域建模，再在右侧识别完整二值轮廓。Hu 差异不是置信度；不估计朝向、正反面或定位跟随位姿。', expected=expected,
                    steps=[step('teach', teaching, [bind('model', 'silhouette')]), step('match', matching, [bind('count', 'shapeCount'), bind('passed', 'shapeOK')])])
        components = []
        for i, (kind, label, field) in enumerate([('value', '匹配数量', 'count'), ('lamp', '数量判定', 'passed'), ('image', '候选轮廓标记', ''), ('table', '候选形状明细', 'items')]):
            components.append(dict(id='shape-'+str(i), type=kind, label=label, x=(i%2)*6, y=0 if i<2 else 2,
                                   w=6, h=2 if i<2 else 6, color='#1095bd', fontSize=32 if i<2 else 20,
                                   precision=0, unit='', binding=dict(source='result', nodeId='shape-match', path=field)))
        demo['hmi'] = dict(version=1, title=title, rows=8, rowHeight=60, components=components)
        demo['hmiBindings'] = [dict(component=i, step=1) for i in range(4)]
        cases.append(demo)
    (SAMPLES/'demos-shape.json').write_text(json.dumps(cases, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


if __name__ == '__main__': generate()
