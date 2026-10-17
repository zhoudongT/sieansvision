"""Generate deterministic synthetic camera-calibration demo and plugin manifest."""
import json
from pathlib import Path
import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT/'operator-plugins/sieans-intrinsics'
SAMPLES = ROOT/'public/vision/samples'


def field(key, label, kind, default, **kw):
    return dict(key=key, label=label, type=kind, default=default, required=True, **kw)


def synthetic():
    obj = np.zeros((54, 3), np.float32)
    obj[:, :2] = np.mgrid[0:9, 0:6].T.reshape(-1, 2)*20
    k = np.array([[710.,0,320],[0,725,240],[0,0,1]])
    points = []
    for i, rotation in enumerate([[.25,.15,0],[-.3,.2,.1],[.15,-.3,-.1],[-.2,-.2,.2],[.4,-.1,-.2],[-.1,.4,.05],[.3,.3,-.12],[-.25,.3,.15]]):
        pixels, _ = cv2.projectPoints(obj, np.array(rotation), np.array([-80.+i*2,-50.+i,530.+i*13]), k, np.array([-.12,.035,.001,-.002,.0]))
        points.extend(dict(view=i+1,column=j%9,row=j//9,x=float(pt[0]),y=float(pt[1]),width=640,height=480) for j,pt in enumerate(pixels.reshape(-1,2)))
    return points


def generate():
    FOLDER.mkdir(exist_ok=True)
    columns = [field('view','视图编号','integer',1,minimum=1,maximum=999999),field('column','角点列（从 0 开始）','integer',0,minimum=0,maximum=14),field('row','角点行（从 0 开始）','integer',0,minimum=0,maximum=14),field('x','图像 X (px)','number',0,minimum=0,maximum=15999),field('y','图像 Y (px)','number',0,minimum=0,maximum=15999)]
    columns += [field('width','采集宽度 (px)','integer',640,minimum=32,maximum=16000),field('height','采集高度 (px)','integer',480,minimum=32,maximum=16000)]
    table = field('points','累计角点表','array',[],columns=columns,minimumRows=0,maximumRows=1000)
    board = [field('columns','棋盘内角点列数','integer',9,minimum=3,maximum=15),field('rows','棋盘内角点行数','integer',6,minimum=3,maximum=15),field('squareSize','棋盘格边长（同一长度单位）','number',20,minimum=.001,maximum=10000)]
    size = [field('width','标定图像宽度 (px)','integer',640,minimum=32,maximum=16000),field('height','标定图像高度 (px)','integer',480,minimum=32,maximum=16000)]
    def output(key,label,kind): return dict(key=key,label=label,type=kind)
    def op(id,name,input,parameters,outputs,description):
        return dict(id=id,name=name,input=input,entry='intrinsics.py',timeoutMs=30000,description=description,
            parameters=[field('task','算子功能','string',id,choices=[dict(value=id,label=name)])]+parameters,outputs=outputs)
    ops = [op('corners','棋盘格角点采集','image',board+[field('view','本次视图编号','integer',1,minimum=1,maximum=999999),table],
        [output('points','累计角点表','array'),output('viewCount','累计视图数','integer'),output('width','图像宽度','integer'),output('height','图像高度','integer'),output('cornerCount','本次角点数','integer')],
        '内角点行列不含外围方格。将累计角点表输入与输出绑定同一流程变量，逐次更换棋盘姿态、递增视图编号并执行。各次图像必须来自同一分辨率、焦距和相机。'),
        op('calibrate','相机内参标定','none',board+size+[table,field('maxRms','最大重投影误差 (px)','number',1,minimum=.001,maximum=100)],
        [output('calibration','针孔相机标定结果','object'),output('rmsPixels','总重投影均方根误差 (px)','number'),output('viewCount','有效视图数','integer'),output('items','逐视图误差表','array'),output('note','使用说明','string')],
        '至少六个不同倾斜姿态；建议 10–15 个。针孔模型包含 k1/k2/p1/p2/k3，非鱼眼模型。错误或退化视图拒绝输出。低拟合误差不代表现场测量准确度。'),
        op('undistort','镜头畸变校正','image',[field('calibration','针孔相机标定结果','object',{})],
        [output('width','输出宽度','integer'),output('height','输出高度','integer'),output('calibration','校正图内参（畸变系数置零）','object'),output('note','坐标说明','string')],
        '绑定完整标定结果；尺寸必须一致。校正图进入下游图像通道，保持原尺寸及内参，边缘无效区填黑。校正后重新采集平面标定点，不得套用畸变原图的点位。')]
    manifest = dict(apiVersion=1,id='sieans-intrinsics',name='SIEANS 相机内参与畸变校正',version='1.0.0',license='MIT',description='基于 OpenCV 的多视图棋盘格针孔标定、角点累积与图像畸变校正。',operators=ops)
    (FOLDER/'operator-plugin.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    board_image = np.full((480,640,3),220,np.uint8)
    for row in range(7):
        for col in range(10):
            cv2.rectangle(board_image,(120+col*40,100+row*40),(159+col*40,139+row*40),(255,255,255) if (row+col)%2 else (0,0,0),-1)
    cv2.imwrite(str(SAMPLES/'intrinsics-board.png'),board_image)
    grid = np.full((480,640,3),245,np.uint8)
    for x in range(0,640,40): cv2.line(grid,(x,0),(x,479),(30,110,160),1)
    for y in range(0,480,40): cv2.line(grid,(0,y),(639,y),(30,110,160),1)
    cv2.putText(grid,'SYNTHETIC CALIBRATION',(80,225),cv2.FONT_HERSHEY_SIMPLEX,.7,(40,40,40),2)
    cv2.imwrite(str(SAMPLES/'intrinsics-grid.png'),grid)
    def step(op,args,bindings=[]): return dict(operation='plugin',params=dict(pluginId=manifest['id'],pluginVersion='1.0.0',operatorId=op,arguments=args,outputBindings=bindings))
    calibration = step('calibrate',dict(points=synthetic()),[dict(scope='flow',name='cameraCalibration',field='calibration')])
    demos = [dict(id='intrinsics-corners',name='棋盘格角点 · 检测与采集',category='定位与测量',image='intrinsics-board.png',description='合成棋盘格检测 54 个内角点，结果以点位表展示。单张图不能完成内参标定。',steps=[step('corners',{})]),
        dict(id='intrinsics-calibrate',name='相机标定 · 八视图内参求解',category='定位与测量',image='intrinsics-grid.png',description='八组合成投影点求解已知针孔参数；fx=710、fy=725，非真实相机精度验收。',steps=[calibration]),
        dict(id='intrinsics-undistort',name='镜头校正 · 标定结果驱动图像',category='定位与测量',image='intrinsics-grid.png',description='合成标定结果绑定流程变量，驱动畸变校正并输出新图像。网格为效果演示，不是实拍畸变图。',steps=[calibration,step('undistort',dict(calibration={'$ref':'flow.cameraCalibration'}))])]
    for demo in demos: demo['expected'] = demo['description']
    (SAMPLES/'demos-intrinsics.json').write_text(json.dumps(demos,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


if __name__ == '__main__': generate()
