"""Raw PNG16 fixtures with explicit rectified intrinsics and known top-plane extents."""
import json
from pathlib import Path
import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT/'public/vision/samples'
PARAMS = dict(projection='rectified-z', fx=100, fy=100, cx=31.5, cy=23.5, scaleMeters=.001,
              minDepth=.1, maxDepth=2, pointStride=1, invalidValue=65535, frame='depth-file-optical')


def generate():
    raw = np.full((48, 64), 1000, np.uint16)
    raw[18:28, 22:42] = 975
    raw[0, 0] = 0
    raw[-1, -1] = 65535
    cv2.imwrite(str(SAMPLES/'depth-file-mm.png'), raw)
    fine = np.where(raw == 65535, 65535, raw.astype(np.uint32)*10).astype(np.uint16)
    cv2.imwrite(str(SAMPLES/'depth-file-tenth-mm.png'), fine)
    cases = []
    for id, title, file, changes, width, count in [
        ('depth-file-top', '深度文件 · 原始 PNG16 到顶面测量', 'depth-file-mm.png', {}, 185.25, 200),
        ('depth-file-stride', '深度文件 · 采样步长影响', 'depth-file-mm.png', dict(pointStride=2), 175.5, 50),
        ('depth-file-scale', '深度文件 · 0.1 毫米原始单位', 'depth-file-tenth-mm.png', dict(scaleMeters=.0001), 185.25, 200),
    ]:
        steps = [dict(operation='cloud_filter', params=dict(method='crop', minimum=[-1000, -1000, 970], maximum=[1000, 1000, 980])),
                 dict(operation='cloud_measure', params={}),
                 dict(operation='variables', params=dict(scope='flow', name='topWidth', value={'$ref': 'results.placeholder.sizeX'}))]
        components = [dict(id='depth-width', type='value', label='采样顶面宽度', x=0, y=0, w=6, h=2, color='#1095bd', fontSize=32, precision=2, unit='mm', binding=dict(source='result', nodeId='measure', path='sizeX')),
                      dict(id='depth-count', type='value', label='采样点数', x=6, y=0, w=6, h=2, color='#1095bd', fontSize=32, precision=0, unit='', binding=dict(source='result', nodeId='measure', path='pointCount')),
                      dict(id='depth-cloud', type='cloud', label='采样顶面点云', x=0, y=2, w=12, h=6, color='#1095bd', fontSize=20, maxPoints=12000, pointSize=3, initialView='iso', binding=dict(source='result', nodeId='measure', path=''))]
        cases.append(dict(id=id, name=title, category='3D', depthFile=file, depthParams={**PARAMS, **changes},
                          description='原始光轴 Z 深度，已知针孔内参；原始深度保留，裁剪点云不裁剪深度栅格。测量是采样可见顶面尺寸，不是物体实体尺寸。',
                          expected=f'裁剪后 {count} 点，采样顶面宽度 {width} mm；深度标签仍显示完整 64 × 48 原始图。', steps=steps,
                          bindings=[dict(step=2, param='value', source=1, field='sizeX')],
                          hmi=dict(version=1, title=title, rows=8, rowHeight=60, components=components), hmiBindings=[dict(component=i, step=1) for i in range(3)]))
    (SAMPLES/'demos-depth-file.json').write_text(json.dumps(cases, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


if __name__ == '__main__': generate()
