"""Deterministic raster fixtures for radial calipers and nested-circle demos."""
import json
from pathlib import Path
import cv2
import numpy as np

root=Path(__file__).resolve().parents[1];samples=root/'public/vision/samples'
y,x=np.mgrid[:480,:640];center=(321.35,239.65);distance=np.hypot(x-center[0],y-center[1]);angle=np.mod(np.degrees(np.arctan2(y-center[1],x-center[0])),360)
ramp=lambda d:.5*(1+np.tanh(d/1.5))
scenes={
 'circle-hole':20+210*ramp(80.4-distance),
 'circle-oversize':20+210*ramp(85.2-distance),
 'circle-outliers':20+210*ramp(80.4+np.where((angle>20)&(angle<60),6,0)-distance),
 'circle-occluded':np.where((angle>20)&(angle<75),20,20+210*ramp(80.4-distance)),
 'circle-no-edge':np.full((480,640),100),
 'circle-ring':20+210*(ramp(120.7-np.hypot(x-320.5,y-240.2))-ramp(80.4-distance)),
 'circle-ring-offset':20+210*(ramp(120.7-np.hypot(x-320.5,y-240.2))-ramp(80.4-np.hypot(x-327.5,y-240.2))),
}
for name,image in scenes.items():cv2.imwrite(str(samples/(name+'.png')),np.clip(np.rint(image),0,255).astype(np.uint8))
def step(operator,args,bindings):return dict(operation='plugin',params=dict(pluginId='sieans-circle',pluginVersion='1.0.0',operatorId=operator,arguments=args,outputBindings=bindings))
def bind(field,name):return dict(field=field,scope='flow',name=name)
cases=[]
for name,title,description,expected,args in [
 ('circle-hole','圆形卡尺 · 圆孔定位与直径','72 组向外灰度扫描，亚像素梯度峰值与几何圆拟合。0.1 mm/px 为演示比例，真实尺寸需先标定。','圆心约 (321.35,239.65) px，直径约 16.08 mm，判定通过。',dict(unitsPerPixel=.1,unit='mm',minimumDiameter=16,maximumDiameter=16.2)),
 ('circle-oversize','圆形卡尺 · 直径超差','使用相同公差检测更大的圆；测量成功和公差通过是两个独立结果。','直径约 17.04 mm，找到圆但公差不通过。',dict(unitsPerPixel=.1,unit='mm',minimumDiameter=16,maximumDiameter=16.2)),
 ('circle-outliers','圆形卡尺 · 局部边缘偏移剔除','局部边缘偏移 6 px，RANSAC 排除该段。剔除点在明细表中保留，拟合残差仅描述采用点。','圆心和直径接近正常样本；部分点被剔除，判定通过。',{}),
 ('circle-occluded','圆形卡尺 · 部分遮挡','约 55° 扇区被遮挡，缺失点不作为零坐标参与拟合。','未检出部分卡尺，其余有效点覆盖足够，仍能测得圆。',{}),
 ('circle-no-edge','圆形卡尺 · 无边缘诊断','均匀图像没有边缘，不输出伪造的圆心、半径或直径。','找到圆和公差通过均为否，结果显示各卡尺原因。',{}),
]:cases.append(dict(id=name,name=title,category='测量',image=name+'.png',description=description,expected=expected,steps=[step('caliper',args,[bind('passed','circleOK'),bind('detectedCount','circleEdges')])]))
for name,expected in [('circle-ring','中心距离约 0.10 mm，理想圆壁厚约 3.93–4.13 mm，通过。'),('circle-ring-offset','中心偏移约 0.70 mm，超过 0.2 mm 公差，不通过。')]:
 cases.append(dict(id=name,name='双圆检测 · '+('正常圆环' if name=='circle-ring' else '偏心圆环'),category='测量',image=name+'.png',description='两次圆形卡尺分别提取内外边缘，再绑定圆模型计算中心偏移与理想圆壁厚。两圆需来自同一图像坐标系；不等同沿真实轮廓测壁厚。',expected=expected,steps=[step('caliper',dict(expectedRadius=80,polarity='rising',unitsPerPixel=.1,unit='mm',minimumDiameter=15,maximumDiameter=18),[bind('circle','innerCircle')]),step('caliper',dict(expectedRadius=120,polarity='falling',unitsPerPixel=.1,unit='mm',minimumDiameter=23,maximumDiameter=25),[bind('circle','outerCircle')]),step('nested',dict(innerCircle={'$ref':'flow.innerCircle'},outerCircle={'$ref':'flow.outerCircle'},maximumCenterDistance=.2,minimumWall=3.8,maximumWall=4.3),[bind('passed','ringOK'),bind('centerDistance','centerOffset')])]))
for demo in [cases[0],cases[5],cases[6]]:
    ring=demo['id'].startswith('circle-ring');last=2 if ring else 0
    components=[]
    for i,(kind,label,path,unit) in enumerate([('value','中心距离' if ring else '测量直径','centerDistance' if ring else 'diameter','mm'),('lamp','检测通过','passed','')]):
        component=dict(id='circle-summary-'+str(i),type=kind,label=label,x=i*6,y=0,w=6,h=2,color='#1095bd',fontSize=32,binding=dict(source='result',nodeId='demo-circle',path=path))
        if kind=='value':component.update(precision=3,unit=unit)
        components.append(component)
    components.append(dict(id='circle-image',type='image',label='圆测量标记图',x=0,y=2,w=6,h=6,color='#1095bd',fontSize=20,binding=dict(source='result',nodeId='demo-circle',path='')))
    components.append(dict(id='circle-details',type='table',label='双圆尺寸表' if ring else '逐卡尺检测明细',x=6,y=2,w=6,h=6,color='#1095bd',fontSize=20,binding=dict(source='result',nodeId='demo-circle',path='items')))
    demo['hmi']=dict(version=1,title=demo['name'],rows=8,rowHeight=60,components=components)
    demo['hmiBindings']=[dict(component=i,step=last) for i in range(len(components))]
(samples/'demos-circle.json').write_text(json.dumps(cases,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
