"""Independent tilted basis and known per-cell heights; no scanned user data."""
import json
from pathlib import Path
import numpy as np

root=Path(__file__).resolve().parents[1];samples=root/'public/vision/samples'
angle=np.deg2rad(30);u=np.array([np.cos(angle),0,-np.sin(angle)]);v=np.array([0.,1.,0.]);normal=np.cross(u,v);origin=np.array([10.,-4.,30.])
points=[dict(zip(('x','y','z'),(origin+a*u+b*v).tolist())) for a,b in [(-5,-5),(5,-5),(5,5),(-5,5)]]
model=dict(format='sieans-plane-grid-v1',unit='mm',frame='height-fixture',origin=origin.tolist(),axisU=u.tolist(),axisV=v.tolist(),normal=normal.tolist())
cells=np.array([[column-4.5,row-4.5,2. if 3<=column<7 and 3<=row<7 else 0.] for row in range(10) for column in range(10)])
scenes={'heightfield-block':cells.copy(),'heightfield-missing':cells[np.arange(100)%10!=5].copy(),'heightfield-signed':cells.copy(),'heightfield-layered':cells.copy()}
scenes['heightfield-signed'][:10,2]=-1
scenes['heightfield-layered']=np.vstack((cells,cells[[55]]+[0,0,3]))
for name,local in scenes.items():
    cloud=dict(unit='mm',frame=model['frame'],points=(origin+local[:,0,None]*u+local[:,1,None]*v+local[:,2,None]*normal).tolist())
    (samples/(name+'.json')).write_text(json.dumps(cloud,separators=(',',':'))+'\n',encoding='utf-8')
(samples/'heightfield-truth.json').write_text(json.dumps(dict(plane=model,points=points,expectedPositiveVolume=32,expectedNegativeVolume=10),indent=2)+'\n',encoding='utf-8')
def bind(field,name):return dict(field=field,name=name,scope='flow')
def step(task,args={},bindings=[]):return dict(operation='plugin',params=dict(pluginId='sieans-heightfield',pluginVersion='1.0.0',operatorId=task,arguments=args,outputBindings=bindings))
fit=step('fit',dict(unit='mm',frame=model['frame'],points=points,normalHint=normal.tolist(),axisHint=u.tolist()),[bind('plane','heightDatum')])
cases=[]
for name,title,expected,args in [
    ('heightfield-block','倾斜基准 · 法向高度与体积','基准倾斜 30°，有效覆盖 100%，最大法向高度 2 mm，正向观测体积约 32 mm³，通过。',dict(minimumPositiveVolume=31.99,maximumPositiveVolume=32.01)),
    ('heightfield-missing','倾斜高度网格 · 缺测拒绝通过','缺少 10 格，有效覆盖 90%，最低覆盖要求 95%；缺失区域不填零、不补齐，判定不通过。',{}),
    ('heightfield-signed','倾斜高度网格 · 凸起与凹槽','正向观测体积 32 mm³、负向观测体积绝对值 10 mm³、净值 22 mm³；允许 −1～2 mm 高度。',dict(minimumHeight=-1,maximumHeight=2.01)),
    ('heightfield-layered','倾斜高度网格 · 同格多层诊断','一个格同时含 2 mm 和 5 mm 点，高度跨度超限，该格无效；要求 100% 覆盖时判定不通过。',dict(minimumCoverage=1,detailMode='invalid')),
]:
    cases.append(dict(id=name,name=title,category='3D',cloud=name+'.json',description='独立基准点表标定 → 模型写流程变量 → 法向高度网格。绿色为合格有效格，红色高度超差，橙色为采样/高度跨度不合格格；测量点不参与基准拟合。',expected=expected,steps=[fit,step('integrate',dict(plane={'$ref':'flow.heightDatum'},**args),[bind('passed','heightOK'),bind('coverage','heightCoverage'),bind('validCells','heightCells')])]))
cases.append(dict(id='heightfield-reference',name='已知倾斜基准 · 直接模型测量',category='3D',cloud='heightfield-block.json',description='工程直接保存已有基准模型，法向指定高度方向，模型单位/坐标系与点云严格一致。',expected='直接得到 100 个有效格，最大高度 2 mm，正向观测体积约 32 mm³。',steps=[step('integrate',dict(plane=model),[bind('positiveVolume','observedVolume'),bind('maximumHeight','maxNormalHeight')])]))
for case in cases:
    components=[]
    for i,(kind,label,path,unit) in enumerate([('value','正向观测体积','positiveVolume','mm³'),('value','最大法向高度','maximumHeight','mm'),('value','有效格覆盖率','coverage','比例'),('lamp','测量通过','passed','')]):
        component=dict(id='heightfield-summary-'+str(i),type=kind,label=label,x=i*3,y=0,w=3,h=2,color='#1095bd',fontSize=28,binding=dict(source='result',nodeId='demo-heightfield',path=path))
        if kind=='value':component.update(precision=3,unit=unit)
        components.append(component)
    components.append(dict(id='heightfield-table',type='table',label='网格测量明细（缺测不填零）',x=7,y=2,w=5,h=6,color='#1095bd',fontSize=20,binding=dict(source='result',nodeId='demo-heightfield',path='items')))
    components.append(dict(id='heightfield-cloud',type='cloud',label='检测点云 · 拖动旋转 / 滚轮缩放',x=0,y=2,w=7,h=6,color='#1095bd',fontSize=20,maxPoints=12000,pointSize=3,initialView='iso',binding=dict(source='result',nodeId='demo-heightfield',path='')))
    case['hmi']=dict(version=1,title=case['name'],rows=8,rowHeight=60,components=components)
    case['hmiBindings']=[dict(component=i,step=len(case['steps'])-1) for i in range(len(components))]
(samples/'demos-heightfield.json').write_text(json.dumps(cases,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
