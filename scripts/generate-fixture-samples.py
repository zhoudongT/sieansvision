"""Generate textured parts with independently known image poses and follow-up ROIs."""
import json
from pathlib import Path
import cv2
import numpy as np

root=Path(__file__).resolve().parents[1];samples=root/'public/vision/samples'
template=np.full((64,80,3),20,np.uint8)
cv2.rectangle(template,(8,8),(71,55),(190,190,190),-1)
cv2.circle(template,(26,30),7,(35,35,35),-1,cv2.LINE_AA)
cv2.rectangle(template,(48,25),(59,36),(55,55,55),-1)
cv2.fillConvexPoly(template,np.array([[8,8],[23,8],[8,20]]),(90,90,90))
cv2.line(template,(15,48),(42,48),(230,230,230),2)
cv2.imwrite(str(samples/'fixture-template.png'),template)
def scene(poses):
    canvas=np.full((360,480,3),20,np.uint8)
    for x,y,angle,scale in poses:
        matrix=cv2.getRotationMatrix2D(((template.shape[1]-1)/2,(template.shape[0]-1)/2),angle,scale);matrix[:,2]+=np.array([x,y])-np.array([(template.shape[1]-1)/2,(template.shape[0]-1)/2])
        placed=cv2.warpAffine(template,matrix,(480,360),borderValue=(20,20,20))
        # Objects do not overlap; their non-background pixels are independent.
        mask=np.any(placed!=20,axis=2);canvas[mask]=placed[mask]
    return canvas
truth={
 'fixture-rotated':[[240,180,30,1.2]],
 'fixture-multiple':[[110,100,0,1],[320,110,30,1.2],[230,270,-30,.8]],
 'fixture-blank':[],
 'fixture-near-border':[[20,22,0,1]],
}
for name,poses in truth.items():cv2.imwrite(str(samples/(name+'.png')),scene(poses))
(samples/'fixture-truth.json').write_text(json.dumps(truth,indent=2)+'\n',encoding='utf-8')
def locate(args={}):return dict(operation='locate',reference='fixture-template.png',params=dict(minScore=.94,angleStart=-30,angleEnd=30,angleStep=30,scales=[.8,1,1.2],maxMatches=5,overlapThreshold=.3,**args))
def follow(task,args={},bindings=[]):return dict(operation='plugin',params=dict(pluginId='sieans-fixture',pluginVersion='1.0.0',operatorId=task,arguments=dict(pose={'$ref':'flow.partPose'},**args),outputBindings=bindings))
locate_step=locate();pose_variable=dict(operation='variables',params=dict(scope='flow',name='partPose',value={}))
cases=[
 dict(id='fixture-multiple',name='多目标定位 · 旋转与缩放去重',category='定位',image='fixture-multiple.png',description='非对称模板在三种角度/比例下出现，按旋转四边形重叠去重；每个目标提供坐标和位姿表。',expected='检出 3 个独立目标：约 (110,100)、(320,110)、(230,270) px；角度 0°、30°、−30°。',steps=[locate()]),
 dict(id='fixture-rotated',name='定位跟随 · 点位坐标转换',category='定位',image='fixture-rotated.png',description='先定位旋转且放大的工件，再将模板中的圆孔/方孔中心转换为当前图像坐标。',expected='唯一目标约 (240,180) px，30° / 1.2 倍；两条转换点位在图像范围内。',steps=[locate(),pose_variable,follow('points',dict(points=[dict(x=26,y=30),dict(x=53.5,y=30.5)]))],bindings=[dict(step=1,param='value',source=0,field='pose')]),
 dict(id='fixture-inspect',name='定位跟随 · 校正后检测双孔',category='定位',image='fixture-rotated.png',description='模板定位 → 固定模板坐标的 56×40 检测区域校正 → 灰度斑点检测；目标移动、旋转和缩放后，下游仍在固定坐标检测。',expected='校正图为 56×40，检出 2 个暗区域；圆孔中心约 (14,18) px。',steps=[locate(),pose_variable,follow('rectify',dict(cropX=12,cropY=12,cropWidth=56,cropHeight=40)),dict(operation='plugin',params=dict(pluginId='sieans-regions',pluginVersion='1.0.0',operatorId='blobs',arguments=dict(polarity='dark',threshold=100,minimumArea=30,maximumArea=500,minimumCount=2,maximumCount=2),outputBindings=[dict(field='count',scope='flow',name='holeCount')]))],bindings=[dict(step=1,param='value',source=0,field='pose')]),
 dict(id='fixture-blank',name='模板定位 · 未检出诊断',category='定位',image='fixture-blank.png',description='没有达到阈值时只返回分数、状态与空目标表，不提供伪造的定位位姿。',expected='found=false、count=0、unique=false，无 pose / center。后续跟随应由条件分支保护。',steps=[locate()]),
]
cases.append(dict(id='fixture-guard',name='定位跟随 · 唯一目标条件保护',category='定位',image='fixture-blank.png',description='仅在目标唯一且搜索结果完整时进入校正和检测。未找到、多个目标或结果截断时跳过下游，不引用缺失的位姿。可换用单目标或多目标演示图片验证分支。',expected='空图时后三步均跳过；换为单目标旋转图时校正后检出两孔；多目标图时也跳过。',steps=[locate(),dict(operation='condition',params=dict(comparison='is_true',left=False)),pose_variable,follow('rectify',dict(cropX=12,cropY=12,cropWidth=56,cropHeight=40)),cases[2]['steps'][3]],connections=[[-1,0],[0,1],[1,2,'true'],[2,3],[3,4]],bindings=[dict(step=1,param='left',source=0,field='unique'),dict(step=2,param='value',source=0,field='pose')]))
for case in cases:
    components=[dict(id='fixture-image',type='image',label='本步处理图像',x=0,y=0,w=7,h=7,color='#1095bd',fontSize=20,binding=dict(source='result',nodeId='demo-fixture',path='')),dict(id='fixture-table',type='table',label='检测明细',x=7,y=0,w=5,h=7,color='#1095bd',fontSize=20,binding=dict(source='result',nodeId='demo-fixture',path='items'))]
    case['hmi']=dict(version=1,title=case['name'],rows=7,rowHeight=60,components=components);case['hmiBindings']=[dict(component=i,step=len(case['steps'])-1) for i in range(2)]
(samples/'demos-fixture.json').write_text(json.dumps(cases,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
