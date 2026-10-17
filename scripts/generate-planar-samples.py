"""Known planar dimensions projected by a fixed synthetic pinhole homography."""
import json
from pathlib import Path
import cv2
import numpy as np

root=Path(__file__).resolve().parents[1]
samples=root/'public/vision/samples'
h=np.array([[6,.8,100],[.3,5.5,80],[.004,.0015,1.]])
world=np.array([[x,y] for y in (0,30,60) for x in (0,50,100)],dtype=float)
def projected(points): return cv2.perspectiveTransform(np.asarray(points,dtype=float).reshape(-1,1,2),h).reshape(-1,2)
pixels=projected(world)
image=np.full((480,720,3),245,np.uint8)
for x in range(0,101,10): cv2.line(image,*[tuple(np.rint(p).astype(int)) for p in projected([[x,0],[x,60]])],(215,225,228),1,cv2.LINE_AA)
for y in range(0,61,10): cv2.line(image,*[tuple(np.rint(p).astype(int)) for p in projected([[0,y],[100,y]])],(215,225,228),1,cv2.LINE_AA)
outline=projected([[20,15],[80,15],[80,45],[20,45]])
cv2.polylines(image,[np.rint(outline).astype(np.int32)],True,(180,90,20),2,cv2.LINE_AA)
for i,p in enumerate(pixels):
 at=tuple(np.rint(p).astype(int));cv2.circle(image,at,4,(70,70,70),-1,cv2.LINE_AA)
 cv2.putText(image,'C'+str(i+1),(at[0]+8,at[1]+14),cv2.FONT_HERSHEY_SIMPLEX,.4,(80,80,80),1,cv2.LINE_AA)
cv2.putText(image,'Known plane: 100 x 60 mm',(70,420),cv2.FONT_HERSHEY_SIMPLEX,.6,(130,70,20),1,cv2.LINE_AA)
cv2.putText(image,'Inner rectangle: 60 x 30 mm',(70,450),cv2.FONT_HERSHEY_SIMPLEX,.6,(130,70,20),1,cv2.LINE_AA)
cv2.imwrite(str(samples/'planar-calibration.png'),image)
rows=[dict(pixelX=float(p[0]),pixelY=float(p[1]),worldX=float(w[0]),worldY=float(w[1])) for p,w in zip(pixels,world)]
def step(op,args,bindings): return dict(operation='plugin',params=dict(pluginId='sieans-planar',pluginVersion='1.0.0',operatorId=op,arguments=args,outputBindings=bindings))
def bind(field,name): return dict(field=field,name=name,scope='flow')
def chain(closed=False,outlier=False):
 data=[dict(r) for r in rows]
 if outlier: data[4]['pixelX']+=60;data[4]['pixelY']-=40
 points=outline if closed else outline[:2]
 return [step('calibrate',dict(points=data),[bind('calibration','planeCalibration')]),step('measure',dict(calibration={'$ref':'flow.planeCalibration'},points=[dict(x=float(p[0]),y=float(p[1])) for p in points],closed=closed),[bind('length','measuredLength')])]
items=[
 dict(id='planar-length',name='透视标定 → 实际长度测量',category='测量',image='planar-calibration.png',description='九组图像与实际坐标建立平面标定，保存到流程变量，再测量倾斜图像中的已知线段。',expected='9 个有效标定点；测量长度约 60 mm。只适用于当前成像配置和同一平面。',steps=chain()),
 dict(id='planar-perimeter',name='标定平面 → 矩形周长',category='测量',image='planar-calibration.png',description='按四个角点计算闭合周长，分别列出每段长度、方向和转换后的坐标。',expected='四条边约 60、30、60、30 mm；周长约 180 mm。',steps=chain(closed=True)),
 dict(id='planar-outlier',name='平面标定 → 剔除错误对应点',category='测量',image='planar-calibration.png',description='人为将第 5 个图像点偏移，RANSAC 标记并剔除该错误对应点，再验证已知长度。',expected='有效点 8、剔除点 1；测量长度仍约 60 mm。四点精确拟合不能独立证明标定精度。',steps=chain(outlier=True))]
file=samples/'demos-plugins.json';existing=json.loads(file.read_text(encoding='utf-8'))
existing=[item for item in existing if item['id'] not in {d['id'] for d in items}]
file.write_text(json.dumps(existing+items,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('Generated planar fixture and 3 demonstrations')
