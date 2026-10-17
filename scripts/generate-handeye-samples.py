"""Synthetic eye-in-hand poses with known transforms; not robot measurements."""
from pathlib import Path
import json
import cv2
import numpy as np

ROOT=Path(__file__).resolve().parents[1];FOLDER=ROOT/'operator-plugins/sieans-handeye';SAMPLES=ROOT/'public/vision/samples'


def matrix(rv,t):
    m=np.eye(4);m[:3,:3]=cv2.Rodrigues(np.array(rv,dtype=float))[0];m[:3,3]=t;return m


def samples():
    x=matrix([.1,-.2,.05],[30,-20,80]);board=matrix([0,.1,.2],[400,0,900])
    camera_rotations=[[.25,.15,0],[-.3,.2,.1],[.15,-.3,-.1],[-.2,-.2,.2],[.4,-.1,-.2],[-.1,.4,.05],[.3,.3,-.12],[-.25,.3,.15],[.35,.2,.06],[-.12,-.25,.1],[.2,-.18,-.05]]
    rows=[]
    for i,rv in enumerate(camera_rotations):
        c=matrix(rv,[-80+i*3,-50+i,550+i*15]);g=board@np.linalg.inv(c)@np.linalg.inv(x)
        robot=np.r_[g[:3,3],cv2.Rodrigues(g[:3,:3])[0].ravel()];camera=np.r_[c[:3,3],rv]
        rows.append(dict(zip([prefix+part for prefix in ('robot','camera') for part in ('X','Y','Z','Rx','Ry','Rz')],map(float,np.r_[robot,camera]))))
    return rows,x,board


def field(key,label,kind,default,**kw):return dict(key=key,label=label,type=kind,default=default,required=True,**kw)
def output(key,label,kind):return dict(key=key,label=label,type=kind,required=True)


def generate():
    FOLDER.mkdir(exist_ok=True);rows,x,board=samples()
    columns=[]
    for prefix,label in [('robot','工具→基座'),('camera','标定板→相机')]:
        for part in ['X','Y','Z','Rx','Ry','Rz']:
            suffix=' (rad)' if prefix=='camera' and part.startswith('R') else ''
            columns.append(field(prefix+part,label+' '+part+suffix,'number',1 if part=='Z' and prefix=='camera' else 0,minimum=-1e9,maximum=1e9))
    poses=field('poses','同步采样姿态表','array',[],columns=columns,minimumRows=0,maximumRows=100)
    quality=[field('maximumTranslationRms','最大平移 RMS (mm)','number',1,minimum=0,maximum=1e9),field('maximumTranslationError','最大单次平移误差 (mm)','number',2,minimum=0,maximum=1e9),field('maximumAngleError','最大角度误差 (°)','number',1,minimum=0,maximum=180)]
    unit_choices=[dict(value='mm',label='毫米 mm'),dict(value='m',label='米 m')]
    def op(id,name,input,parameters,outputs,description):return dict(id=id,name=name,input=input,entry='handeye.py',timeoutMs=30000,description=description,parameters=[field('task','算子功能','string',id,choices=[dict(value=id,label=name)])]+parameters,outputs=outputs)
    diagnostics=[output('sampleCount','采样姿态数量','integer'),output('rmsTranslationError','标定板平移 RMS','number'),output('maximumTranslationError','标定板最大平移误差','number'),output('maximumAngleErrorDegrees','标定板最大旋转误差 (°)','number'),output('unit','平移误差单位','string'),output('items','各姿态一致性明细','array')]
    ops=[op('pose','棋盘格位姿 · 标定板到相机','image',[
        field('intrinsics','针孔相机内参标定结果','object',{}),field('columns','棋盘内角点列数','integer',9,minimum=3,maximum=15),field('rows','棋盘内角点行数','integer',6,minimum=3,maximum=15),field('squareSize','实际格边长','number',20,minimum=.001,maximum=10000),field('unit','格边长单位','string','mm',choices=unit_choices),field('reverseCorners','反转角点顺序以核对同一原点','boolean',False),field('maximumReprojectionError','最大重投影误差 (px)','number',1,minimum=.001,maximum=100),field('minimumAmbiguityGap','候选位姿最小误差差距 (px)','number',.05,minimum=0,maximum=10)],
        [output('pose','标定板→相机的平移/旋转向量','object'),output('unit','平移长度单位','string'),output('rotationConvention','旋转向量约定','string'),output('rmsPixels','重投影 RMS (px)','number'),output('cornerCount','内角点数','integer'),output('originX','选定原点图像 X (px)','number'),output('originY','选定原点图像 Y (px)','number'),output('note','坐标及原点说明','string')],
        '使用已有内参，IPPE 求平面位姿并检查正深度、重投影及双解歧义。rvec 为弧度轴角。普通棋盘无唯一标记，跨采样须人工核对同一原点/轴向；不自动保证角点编号一致。'),
        op('fit','眼在手上 · 多姿态手眼标定','none',[
        field('cameraFrame','相机光学坐标系','string','camera-optical'),field('toolFrame','机器人工具坐标系','string','tool0'),field('baseFrame','机器人基座坐标系','string','robot-base'),field('boardFrame','固定标定板坐标系','string','calibration-board'),field('robotUnit','机器人平移单位','string','mm',choices=unit_choices),field('cameraUnit','标定板位姿平移单位','string','mm',choices=unit_choices),field('robotRotation','机器人旋转约定','string','rodrigues-rad',choices=[dict(value='rodrigues-rad',label='Rodrigues 轴角向量 · 弧度'),dict(value='euler-zyx-deg',label='固定轴 Rz(z) × Ry(y) × Rx(x) · 度')]),field('method','手眼求解方法','string','park',choices=[dict(value='park',label='Park · 旋转对齐与平移最小二乘')]),poses]+quality,
        [output('calibration','相机→工具刚体标定结果','object'),output('reference','固定标定板参考记录','object')]+diagnostics+[output('note','适用条件说明','string')],
        '相机固定在工具上、标定板固定在基座。表格必须为工具→基座及标定板→相机，且对应同一停止姿态。至少六组，建议十组以上绕不同轴旋转。旋转向量不是欧拉角；模型可传给 3D 坐标转换。'),
        op('check','手眼标定 · 独立姿态验证','none',[field('calibration','相机→工具标定结果','object',{}),field('reference','原标定板参考记录','object',{}),poses]+quality,
        [output('passed','独立姿态验证通过','boolean')]+diagnostics,
        '用未参与拟合的三组以上同步姿态，对比原标定板基座位姿，不重新拟合。约定/单位沿用参考记录；移动标定板后应重新建立标定，不能直接沿用该验证参考。')]
    (FOLDER/'operator-plugin.json').write_text(json.dumps(dict(apiVersion=1,id='sieans-handeye',name='SIEANS 眼在手上标定',version='1.0.0',license='MIT',description='棋盘位姿、同步多姿态手眼标定与独立姿态验证。',operators=ops),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    k=np.array([[710.,0,320],[0,725,240],[0,0,1]])
    rv=np.array([.25,.15,0]);t=np.array([-80.,-50,550])
    canvas=np.full((960,1280,3),190,np.uint8)
    for row in range(7):
        for col in range(10):
            quad=np.array([[(col-1)*20,(row-1)*20,0],[col*20,(row-1)*20,0],[col*20,row*20,0],[(col-1)*20,row*20,0]],np.float64)
            projected=cv2.projectPoints(quad,rv,t,k,np.zeros(5))[0].reshape(-1,2)
            cv2.fillConvexPoly(canvas,np.round(projected*2).astype(np.int32),(255,)*3 if (row+col)%2 else (0,)*3)
    raster=cv2.resize(canvas,(640,480),interpolation=cv2.INTER_AREA)
    cv2.imwrite(str(SAMPLES/'handeye-board.png'),raster)
    found,corners=cv2.findChessboardCornersSB(cv2.cvtColor(raster,cv2.COLOR_BGR2GRAY),(9,6),cv2.CALIB_CB_NORMALIZE_IMAGE)
    if not found:raise RuntimeError('Synthetic board not detected')
    true_origin=cv2.projectPoints(np.zeros((1,3)),rv,t,k,np.zeros(5))[0].reshape(2)
    ordered=corners.reshape(-1,2)
    reverse=bool(np.linalg.norm(ordered[0]-true_origin)>np.linalg.norm(ordered[-1]-true_origin))
    intrinsics=dict(model='pinhole-opencv5',version=1,width=640,height=480,fx=710.,fy=725.,cx=320.,cy=240.,k1=0.,k2=0.,p1=0.,p2=0.,k3=0.)
    def step(op,args,bindings=[]):return dict(operation='plugin',params=dict(pluginId='sieans-handeye',pluginVersion='1.0.0',operatorId=op,arguments=args,outputBindings=bindings))
    fit=step('fit',dict(poses=rows[:8]),[dict(scope='flow',name='handeyeCalibration',field='calibration'),dict(scope='flow',name='handeyeReference',field='reference')])
    check_args=dict(calibration={'$ref':'flow.handeyeCalibration'},reference={'$ref':'flow.handeyeReference'},poses=rows[8:])
    bad=json.loads(json.dumps(check_args));bad['poses'][0]['robotX']+=10
    demos=[dict(id='handeye-pose',name='棋盘格位姿 · 相机外参求解',category='定位与测量',image='handeye-board.png',description='已知合成内参，检测棋盘并输出标定板到相机的平移和轴角向量，展示坐标轴。',expected='54 个内角点；Z 约 550 mm，rvec 约 (0.25,0.15,0) rad。普通棋盘原点须核对。',steps=[step('pose',dict(intrinsics=intrinsics,reverseCorners=reverse))]),
        dict(id='handeye-fit',name='手眼标定 · 八姿态求解与独立验证',category='3D 点云',image='handeye-board.png',description='八组同步合成姿态求相机→工具关系，另三组独立验证固定标定板位置。',expected='相机→工具平移约 (30,-20,80) mm，独立验证通过。',steps=[fit,step('check',check_args)]),
        dict(id='handeye-drift',name='手眼验证 · 独立姿态误差检出',category='3D 点云',image='handeye-board.png',description='独立验证中一组机器人 X 人为偏差 10 mm；不重拟合原模型。',expected='独立验证不通过，最大平移误差约 10 mm。',steps=[fit,step('check',bad)]),
        dict(id='handeye-point',name='手眼关系 → 相机点转换到工具',category='3D 点云',image='handeye-board.png',description='手眼模型与现有刚体坐标插件兼容，将相机测得的点变换到工具坐标，不直接向机器人发送动作。',expected='输出工具坐标点；长度单位与模型一致。',steps=[fit,dict(operation='plugin',params=dict(pluginId='sieans-rigid',pluginVersion='1.0.0',operatorId='points',arguments=dict(calibration={'$ref':'flow.handeyeCalibration'},points=[dict(x=10,y=20,z=30)]),outputBindings=[]))])]
    (SAMPLES/'demos-handeye.json').write_text(json.dumps(demos,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (SAMPLES/'handeye-ground-truth.json').write_text(json.dumps(dict(cameraToTool=x.tolist(),boardToBase=board.tolist(),poses=rows,intrinsics=intrinsics,reverseCorners=reverse),indent=2)+'\n',encoding='utf-8')


if __name__=='__main__':generate()
