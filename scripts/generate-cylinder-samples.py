"""Deterministic cylinder samples with independent known axis, dimensions and deviations."""
import json
from pathlib import Path
import numpy as np

samples=Path(__file__).resolve().parents[1]/'public/vision/samples'
anchor=np.array([12.,-4.,30.]);axis=np.array([.3,-.4,np.sqrt(.75)])
u=np.cross(axis,[1.,0.,0.]);u/=np.linalg.norm(u);v=np.cross(axis,u)
theta=np.tile(np.arange(60)*2*np.pi/60,10);axial=np.repeat(np.linspace(-20,20,10),60)
radial=np.cos(theta)[:,None]*u+np.sin(theta)[:,None]*v
clean=anchor+axial[:,None]*axis+10*radial
robust=np.vstack((clean,anchor+axial[::15,None]*axis+13*radial[::15]))
defects=clean.copy();defects[20]+=.5*radial[20];defects[180]-=.3*radial[180]
narrow_theta=np.tile(np.linspace(0,np.deg2rad(12),60),10)
narrow=anchor+axial[:,None]*axis+10*(np.cos(narrow_theta)[:,None]*u+np.sin(narrow_theta)[:,None]*v)
oversize=anchor+axial[:,None]*axis+11*radial
for name,points in [('cylinder-outliers',robust),('cylinder-defects',defects),('cylinder-narrow',narrow),('cylinder-oversize',oversize)]:
    (samples/(name+'.json')).write_text(json.dumps(dict(unit='mm',frame='cylinder-fixture',points=points.tolist()),separators=(',',':'))+'\n',encoding='utf-8')

def bind(field,name,scope='flow'):return dict(field=field,name=name,scope=scope)
def step(task,args,bindings):return dict(operation='plugin',params=dict(pluginId='sieans-cylinder',pluginVersion='1.0.0',operatorId=task,arguments=args,outputBindings=bindings))
reference=dict(model='sieans-cylinder-v1',axisPoint=anchor.tolist(),axisDirection=axis.tolist(),radius=10,unit='mm',frame='cylinder-fixture')
fit=step('fit',dict(detailMode='outside'),[bind('cylinder','cylinderReference'),bind('diameter','cylinderDiameter'),bind('passed','cylinderFitOK')])
cases=[
    dict(id='cylinder-fit',name='3D 圆柱拟合 · 倾斜轴与离群点',category='3D',cloud='cylinder-outliers.json',description='600 个倾斜圆柱表面点和 40 个离群点，估计自由轴线与直径。采样轴向跨度用于判断覆盖，不代表实际工件长度。',expected='直径 20 mm；轴向约 (0.3,-0.4,0.866025)，独立内点 600/640；40 个离群点标红。',steps=[fit]),
    dict(id='cylinder-inspect',name='3D 圆柱侧面 · 凸起与凹陷',category='3D',cloud='cylinder-defects.json',description='对照独立圆柱基准，在 ±0.1 mm 侧面公差内检出局部凸起和凹陷。',expected='最大径向偏差 +0.5 mm、最小 -0.3 mm；2 个超差点，判定不通过。',steps=[step('inspect',dict(cylinder=reference,detailMode='outside'),[bind('outsideCount','cylinderDefects'),bind('passed','cylinderOK')])]),
    dict(id='cylinder-chain',name='3D 圆柱拟合 → 侧面偏差',category='3D',cloud='cylinder-defects.json',description='拟合模型写入流程变量，再由后续圆柱侧面算子读取。自拟合基准用于形状偏差，不检测绝对位置偏差。',expected='主体直径约 20 mm，拟合通过；后续检出 2 个局部超差点。',steps=[fit,step('inspect',dict(cylinder={'$ref':'flow.cylinderReference'},detailMode='outside'),[bind('outsideCount','cylinderDefects'),bind('passed','cylinderOK')])]),
    dict(id='cylinder-narrow',name='3D 圆柱拟合 · 覆盖不足诊断',category='3D',cloud='cylinder-narrow.json',description='输入仅有 12° 周向覆盖，拒绝输出不稳定的轴线与直径。',expected='found 和 passed 为否；点云灰色，显示覆盖或拟合稳定性诊断。',steps=[step('fit',dict(detailMode='outside'),[bind('found','cylinderFound')])]),
    dict(id='cylinder-size',name='3D 圆柱直径 · 尺寸超差',category='3D',cloud='cylinder-oversize.json',description='半径 11 mm 的圆柱可以可靠拟合，但不满足 19.8–20.2 mm 的直径公差。绿色只表示拟合内点。',expected='found 为是，直径 22 mm，passed 为否。',steps=[step('fit',dict(detailMode='outside'),[bind('diameter','cylinderDiameter'),bind('passed','cylinderFitOK')])])
]
(samples/'demos-cylinder.json').write_text(json.dumps(cases,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
