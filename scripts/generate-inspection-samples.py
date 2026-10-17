"""Reproducible synthetic inspection fixtures; never overwrite user projects."""
import json
from pathlib import Path
import cv2
import numpy as np

root = Path(__file__).resolve().parents[1]
samples = root / 'public' / 'vision' / 'samples'
# Two red components with hue on opposite sides of the 0/179 boundary, plus distractors.
hsv = np.zeros((360, 640, 3), np.uint8)
hsv[:, :, 2] = 30
hsv[60:160, 50:170] = (2, 240, 230)
hsv[200:260, 300:380] = (178, 240, 230)
hsv[60:160, 440:540] = (60, 240, 230)
hsv[260:300, 500:580] = (110, 240, 230)
cv2.imwrite(str(samples / 'color-regions.png'), cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR))
# 121 surface points; one raised point and one depression relative to the z=10 plane.
points = [[x, y, 10.] for x in range(11) for y in range(11)]
points[24][2] = 10.5
points[96][2] = 9.7
(samples / 'cloud-deviations.json').write_text(json.dumps(dict(unit='mm', frame='fixture', points=points)), encoding='utf-8')

def step(plugin, operator, arguments, bindings=None):
    return dict(operation='plugin', params=dict(pluginId=plugin, pluginVersion='1.0.0', operatorId=operator,
                arguments=arguments, outputBindings=bindings or []))

demo_file = samples / 'demos-plugins.json'
existing = json.loads(demo_file.read_text(encoding='utf-8'))
ids = {'color-regions', 'color-to-blobs', 'surface-deviations'}
existing = [item for item in existing if item['id'] not in ids]
existing.extend([
    dict(id='color-regions', name='色彩区域 · 红色跨端点筛选', category='检测', image='color-regions.png',
         description='HSV 色相 170–10 跨越红色端点，排除绿色与蓝色。面积按像素计数，参数由插件生成表单。',
         expected='2 个红色区域，面积 12000 和 4800 px²，总面积 16800 px²；流程变量 redCount=2。',
         steps=[step('sieans-regions', 'color', dict(hueMin=170, hueMax=10, minimumCount=2, maximumCount=2, outputImage='annotated'), [dict(field='count',scope='flow',name='redCount')])]),
    dict(id='color-to-blobs', name='色彩掩膜 → 斑点尺寸筛选', category='流程', image='color-regions.png',
         description='色彩算子输出筛选后的二值图，再按像素面积保留大红色目标；展示插件图像通道的串联。',
         expected='色彩筛选得到 2 个区域；斑点面积下限 6000 后剩 1 个，面积 12000 px²，质心 (109.5, 109.5)。',
         steps=[step('sieans-regions', 'color', dict(outputImage='mask')), step('sieans-regions','blobs',dict(minimumArea=6000,minimumCount=1,maximumCount=1,outputImage='annotated'))]),
    dict(id='surface-deviations', name='3D 表面 · 凸起与凹陷偏差', category='3D', image='color-regions.png', cloud='cloud-deviations.json',
         description='以 z=10 mm 为基准面，检查 ±0.1 mm 公差带。超差点红色、合格点绿色；不代表最小区域平面度。',
         expected='121 点中 2 点超差；最大偏差 +0.5 mm、最小 -0.3 mm，判定未通过。',
         steps=[step('sieans-surface', 'plane-distance', dict(planeOffset=-10, lowerDistance=-.1, upperDistance=.1), [dict(field='outsideCount',scope='flow',name='surfaceDefects')])])
])
demo_file.write_text(json.dumps(existing, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
print('Generated 2 synthetic fixtures and 3 plugin demonstrations')
