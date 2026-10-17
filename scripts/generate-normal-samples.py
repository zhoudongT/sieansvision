"""Deterministic 30-degree planar surface and insufficient-support demos."""
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / 'public/vision/samples'
points = [[x, y, x/math.sqrt(3)] for y in range(11) for x in range(11)]
(SAMPLES/'cloud-slope.json').write_text(json.dumps(dict(unit='mm', frame='synthetic-slope', points=points)), encoding='utf-8')
path = SAMPLES/'demos-plugins.json'
demos = [d for d in json.loads(path.read_text(encoding='utf-8')) if not d['id'].startswith('normals-')]
for suffix, name, args, expected in [
    ('pass', '3D 法向 → 30° 斜面合格', dict(maximumSlopeDegrees=35), '121 个有效点，坡度 30°；零超差，判定通过，绿色显示。'),
    ('fail', '3D 法向 → 坡度超差', dict(maximumSlopeDegrees=20), '121 个有效点，坡度 30°；121 点超出 20° 上限，判定不通过，红色显示。'),
    ('invalid', '3D 法向 → 邻域不足诊断', dict(radius=.5), '121 个点均只有自身邻居，法向无效，判定不通过，灰色显示；不显示虚假的零坡度。'),
]:
    demos.append(dict(id='normals-'+suffix, name=name, category='3D', image='parts.png', cloud='cloud-slope.json',
                      description='合成倾斜平面；使用局部邻域拟合，结果按法向、坡度和拟合残差明细表显示。', expected=expected,
                      steps=[dict(operation='plugin',params=dict(pluginId='sieans-normals',pluginVersion='1.0.0',operatorId='inspect',arguments=args,
                        outputBindings=[dict(field='passed',scope='flow',name='slopeOK'),dict(field='invalidCount',scope='flow',name='invalidNormals')]))]))
path.write_text(json.dumps(demos,ensure_ascii=False,indent=2)+'\n', encoding='utf-8')
