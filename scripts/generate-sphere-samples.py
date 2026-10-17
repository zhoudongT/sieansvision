"""Reproducible synthetic sphere samples, with known geometry and defects."""
import json
from pathlib import Path
import numpy as np

samples=Path(__file__).resolve().parents[1]/'public/vision/samples'
center=np.array([12.,-4.,30.])
def directions(n,cap=180):
    i=np.arange(n);z=1-(1-np.cos(np.deg2rad(cap)))*(i+.5)/n;phi=i*np.pi*(3-np.sqrt(5));r=np.sqrt(1-z*z)
    return np.column_stack((r*np.cos(phi),r*np.sin(phi),z))
unit=directions(600)
clean=center+10*unit
robust=np.vstack((clean,center+13*directions(40)))
defects=clean.copy();defects[20]=center+10.5*unit[20];defects[180]=center+9.7*unit[180]
for name,points in [('sphere-outliers',robust),('sphere-defects',defects),('sphere-narrow-cap',center+10*directions(600,5)),('sphere-oversize',center+11*unit)]:
    (samples/(name+'.json')).write_text(json.dumps(dict(unit='mm',frame='sphere-fixture',points=points.tolist()),separators=(',',':'))+'\n',encoding='utf-8')
def bind(field,name,scope='flow'):return dict(field=field,name=name,scope=scope)
def step(task,args,bindings):return dict(operation='plugin',params=dict(pluginId='sieans-sphere',pluginVersion='1.0.0',operatorId=task,arguments=args,outputBindings=bindings))
reference=dict(model='sieans-sphere-v1',center=center.tolist(),radius=10,unit='mm',frame='sphere-fixture')
fit=step('fit',dict(detailMode='outside'),[bind('sphere','sphereReference'),bind('diameter','sphereDiameter'),bind('passed','sphereFitOK')])
cases=[
 dict(id='sphere-fit',name='3D 球面拟合 · 离群点剔除',category='3D',cloud='sphere-outliers.json',description='600 个半径 10 mm 的球面点，另外加入 40 个外侧离群点；RANSAC 与几何优化恢复球心和直径。',expected='球心 (12,-4,30) mm，直径 20 mm；独立内点 600/640，拟合通过。红色为拟合离群点。',steps=[fit]),
 dict(id='sphere-inspect',name='3D 球面偏差 · 凸起与凹陷',category='3D',cloud='sphere-defects.json',description='与已知球面基准比较；在 ±0.1 mm 公差下找出 0.5 mm 凸起和 0.3 mm 凹陷。',expected='2 个超差点标红；最大偏差 +0.5 mm，最小偏差 -0.3 mm，检测不通过。',steps=[step('inspect',dict(sphere=reference,detailMode='outside'),[bind('outsideCount','sphereDefects'),bind('passed','sphereOK')])]),
 dict(id='sphere-chain',name='3D 球面拟合 → 偏差检测',category='3D',cloud='sphere-defects.json',description='先拟合主体球面并将模型写入流程变量，再由下一算子读取变量检查所有点。自拟合基准用于形状偏差，不用于绝对位置偏差。',expected='拟合通过、直径约 20 mm；后续仍检出 2 个局部超差点。模型以字段表展示和绑定。',steps=[fit,step('inspect',dict(sphere={'$ref':'flow.sphereReference'},detailMode='outside'),[bind('outsideCount','sphereDefects'),bind('passed','sphereOK')])]),
 dict(id='sphere-narrow',name='3D 球面拟合 · 覆盖不足诊断',category='3D',cloud='sphere-narrow-cap.json',description='输入仅覆盖 5° 球冠，拟合条件数过大。拒绝输出不稳定的球心/直径，点云显示为灰色。',expected='found 与 passed 为否；显示覆盖过窄的诊断，不输出球面模型。',steps=[step('fit',dict(detailMode='outside'),[bind('found','sphereFound')])]),
 dict(id='sphere-size',name='3D 球面直径 · 尺寸超差',category='3D',cloud='sphere-oversize.json',description='半径 11 mm 的完整球面可以可靠拟合，但超出设定的 19.8–20.2 mm 直径公差。绿色点代表拟合内点，合格与否看结果判定。',expected='found 为是、直径 22 mm、passed 为否。',steps=[step('fit',dict(detailMode='outside'),[bind('diameter','sphereDiameter'),bind('passed','sphereFitOK')])])
]
(samples/'demos-sphere.json').write_text(json.dumps(cases,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
