"""Known full cuboid surfaces, rotations and dimension limits."""
import json
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT/'public/vision/samples'


def surface(dimensions):
    size = np.asarray(dimensions)
    points = []
    for axis in range(3):
        other = [k for k in range(3) if k != axis]
        for sign in (-1, 1):
            for a in np.linspace(-.5, .5, 7):
                for b in np.linspace(-.5, .5, 7):
                    p = np.zeros(3)
                    p[axis] = sign*.5
                    p[other] = (a, b)
                    points.append(p*size)
    return np.unique(points, axis=0)


def rotation():
    a, b, c = np.radians([33, -24, 17])
    rz = np.array([[np.cos(a), -np.sin(a), 0], [np.sin(a), np.cos(a), 0], [0, 0, 1]])
    ry = np.array([[np.cos(b), 0, np.sin(b)], [0, 1, 0], [-np.sin(b), 0, np.cos(b)]])
    rx = np.array([[1, 0, 0], [0, np.cos(c), -np.sin(c)], [0, np.sin(c), np.cos(c)]])
    return rz@ry@rx


def generate():
    cases = []
    for name, title, sizes, unit, factor, expected in [
        ('box-rotated', '旋转包围盒 · 完整长方体', [20, 10, 5], 'mm', 1, '旋转包围盒 20 / 10 / 5 mm，通过；原坐标轴尺寸更大。'),
        ('box-oversize', '旋转包围盒 · 长边超差', [22, 10, 5], 'mm', 1, '长边 22 mm，超过 20.1 mm 公差上限，未通过。'),
        ('box-meters', '旋转包围盒 · 米单位输入', [20, 10, 5], 'm', .001, '尺寸 0.02 / 0.01 / 0.005 m；单位不自动换成毫米。'),
        ('box-equal', '旋转包围盒 · 等边方向提示', [10, 10, 10], 'mm', 1, '三个尺寸约 10 mm，近等长边为是；包围盒方向不等于唯一工件姿态。'),
    ]:
        points = (surface(sizes)@rotation().T+[50, -20, 100])*factor
        cloud = dict(points=points.tolist(), unit=unit, frame='fixture', colors=[[.1, .6, .8]]*len(points))
        (SAMPLES/(name+'.json')).write_text(json.dumps(cloud, separators=(',', ':'))+'\n', encoding='utf-8')
        limits = [10, 10, 10] if name == 'box-equal' else [20, 10, 5]
        args = {prefix+axis: (limits[i]+delta)*factor for prefix, delta in [('minimum', -.1), ('maximum', .1)] for i, axis in enumerate(('Long', 'Middle', 'Short'))}
        args['minimumThickness'] = .001*factor
        steps = [dict(operation='plugin', params=dict(pluginId='sieans-box', pluginVersion='1.0.0', operatorId='measure', arguments=args, outputBindings=[dict(field='length', scope='flow', name='boxLength'), dict(field='passed', scope='flow', name='boxOK')]))]
        components = []
        for i, (kind, label, field) in enumerate([('value', '旋转包围盒长边', 'length'), ('lamp', '尺寸公差', 'passed'), ('cloud', '原始点云', ''), ('table', '长中短边公差', 'items')]):
            component = dict(id='box-'+str(i), type=kind, label=label, x=(i%2)*6, y=0 if i<2 else 2, w=6, h=2 if i<2 else 6, color='#1095bd', fontSize=32 if i<2 else 20, binding=dict(source='result', nodeId='box', path=field))
            if kind == 'value': component.update(precision=4 if unit == 'm' else 2, unit=unit)
            if kind == 'cloud': component.update(maxPoints=12000, pointSize=3, initialView='iso')
            components.append(component)
        cases.append(dict(id=name, name=title, category='3D', cloud=name+'.json', description='完整长方体合成表面，三轴旋转。包围盒尺寸仅描述输入点集，不代表遮挡面的实物尺寸或实体体积，不提供唯一定位姿态。', expected=expected, steps=steps, hmi=dict(version=1, title='旋转包围盒测量', rows=8, rowHeight=60, components=components), hmiBindings=[dict(component=i, step=0) for i in range(4)]))
    (SAMPLES/'demos-box.json').write_text(json.dumps(cases, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


if __name__ == '__main__': generate()
