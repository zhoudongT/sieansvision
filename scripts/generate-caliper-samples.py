"""Generate deterministic metrology scenes and demos; no hardware or user data."""
import json
from pathlib import Path
import cv2
import numpy as np

root = Path(__file__).resolve().parents[1]
samples = root/'public/vision/samples'
y, x = np.mgrid[:480, :640]
ramp = lambda d: .5 * (1 + np.tanh(d / 1.5))
distance = (x - 320)*np.cos(np.deg2rad(28)) + (y - 240)*np.sin(np.deg2rad(28)) - 1.35
scenes = {
    'caliper-line': 20+210*ramp(x-321.35-np.where(y>330, 15, 0)),
    'caliper-width-pass': 20+210*(ramp(distance+40.2)-ramp(distance-40.2)),
    'caliper-width-fail': 20+210*(ramp(distance+43)-ramp(distance-43)),
    'caliper-no-edge': np.full((480,640),100),
}
for name, image in scenes.items():
    cv2.imwrite(str(samples/(name+'.png')), np.clip(np.rint(image),0,255).astype(np.uint8))
def step(task, args, bindings):
    return dict(operation='plugin',params=dict(pluginId='sieans-caliper',pluginVersion='1.0.0',operatorId='edge-'+task,arguments=args,outputBindings=bindings))
def bind(field, name):
    return dict(field=field,scope='flow',name=name)
cases = [
 dict(id='caliper-line',name='边缘卡尺 · 离群点剔除',category='测量',image='caliper-line.png',description='15 组灰度扫描提取亚像素边缘，末端两组偏移 15 px；稳健拟合剔除离群点。标记图用于显示，原图保留给下游。',expected='检出 15 点、拟合采用 13 点；直线 X 约 321.35 px，判定通过。',steps=[step('line',{},[bind('passed','lineOK'),bind('inlierCount','linePoints')])]),
 dict(id='caliper-width-pass',name='双边缘测宽 · 倾斜亮条带',category='测量',image='caliper-width-pass.png',description='按 28° 方向垂直扫描倾斜条带，使用演示比例 0.1 mm/px；这不是实物标定。',expected='15 组测宽约 8.04 mm；公差 8.0–8.1 mm，判定通过。',steps=[step('width',dict(scanAngle=28,unitsPerPixel=.1,unit='mm',minimumWidth=8,maximumWidth=8.1),[bind('passed','widthOK'),bind('meanWidth','measuredWidth')])]),
 dict(id='caliper-width-fail',name='双边缘测宽 · 宽度超差',category='测量',image='caliper-width-fail.png',description='同样的参数检测更宽的条带，逐条报告宽度及超差判定。',expected='宽度约 8.60 mm，15 组超差；流程执行完成，但检测判定为否。',steps=[step('width',dict(scanAngle=28,unitsPerPixel=.1,unit='mm',minimumWidth=8,maximumWidth=8.1),[bind('passed','widthOK'),bind('meanWidth','measuredWidth')])]),
 dict(id='caliper-no-edge',name='边缘卡尺 · 无边缘诊断',category='测量',image='caliper-no-edge.png',description='均匀图像无边缘，显示每个卡尺的未检出原因，不输出伪造的零坐标或零宽度。',expected='检出 0 点、found 和 passed 均为否；没有拟合直线。',steps=[step('line',{},[bind('passed','lineOK'),bind('detectedCount','edgeCount')])]),
]
(samples/'demos-caliper.json').write_text(json.dumps(cases,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
