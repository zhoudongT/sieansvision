"""Reproducible known-correspondence calibration examples and operator schema."""
from pathlib import Path
import json
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
FOLDER=ROOT/'operator-plugins/sieans-rigid'
SAMPLES=ROOT/'public/vision/samples'


def field(key,label,kind,default,**kw):return dict(key=key,label=label,type=kind,default=default,required=True,**kw)
def out(key,label,kind):return dict(key=key,label=label,type=kind,required=True)


def generate():
    FOLDER.mkdir(exist_ok=True)
    source=np.array([[0,0,0],[100,0,0],[0,100,0],[0,0,100],[100,100,100],[30,60,90],[90,30,60],[60,90,30]],dtype=float)
    rotation=np.array([[0.,-1,0],[1,0,0],[0,0,1]])
    target=source@rotation.T+[300,500,100]
    pairs=[dict(zip(['sourceX','sourceY','sourceZ','targetX','targetY','targetZ'],map(float,np.r_[a,b]))) for a,b in zip(source,target)]
    columns=[field(prefix+axis,label+' '+axis,'number',0,minimum=-1e9,maximum=1e9) for prefix,label in [('source','输入点'),('target','目标对应点')] for axis in 'XYZ']
    pair_table=field('pairs','输入/目标对应点表','array',pairs,columns=columns,minimumRows=3,maximumRows=500)
    point_table=field('points','待转换点表','array',[dict(x=10,y=20,z=30)],columns=[field(axis,axis.upper(),'number',0,minimum=-1e9,maximum=1e9) for axis in 'xyz'],minimumRows=1,maximumRows=500)
    model=field('calibration','完整三维标定结果','object',{})
    inverse=field('inverse','反向转换（目标到输入）','boolean',False)
    quality=[field('maximumRms','最大均方根误差（目标单位）','number',.2,minimum=0,maximum=1e9),field('maximumError','最大单点误差（目标单位）','number',.5,minimum=0,maximum=1e9)]
    def op(id,name,input,parameters,outputs,description):return dict(id=id,name=name,input=input,entry='rigid.py',timeoutMs=15000,description=description,parameters=[field('task','算子功能','string',id,choices=[dict(value=id,label=name)])]+parameters,outputs=outputs)
    common=[out('sourceFrame','输入坐标系','string'),out('targetFrame','输出坐标系','string'),out('sourceUnit','输入单位','string'),out('targetUnit','输出单位','string'),out('pointCount','点数','integer')]
    ops=[op('calibrate','3D 对应点刚体标定','none',[
        field('sourceFrame','输入坐标系名称','string','camera-optical'),field('targetFrame','目标坐标系名称','string','fixture-base'),
        field('sourceUnit','输入点长度单位','string','mm',choices=[dict(value='mm',label='毫米 mm'),dict(value='m',label='米 m')]),field('targetUnit','目标点长度单位','string','mm',choices=[dict(value='mm',label='毫米 mm'),dict(value='m',label='米 m')]),pair_table,
        field('method','拟合方式','string','all',choices=[dict(value='all',label='全部对应点最小二乘'),dict(value='ransac',label='RANSAC 排除错误对应')]),
        field('inlierThreshold','内点距离阈值（目标单位）','number',1,minimum=1e-9,maximum=1e9),field('minimumInlierRatio','最低内点比例','number',.8,minimum=.1,maximum=1),
        field('iterations','RANSAC 抽样次数','integer',300,minimum=10,maximum=2000),field('seed','RANSAC 随机种子','integer',0,minimum=0,maximum=2147483647)]+quality,
        [out('calibration','可绑定的三维标定结果','object'),out('inlierCount','有效对应点数','integer'),out('rejectedCount','排除对应点数','integer'),out('rmsError','拟合内点均方根误差','number'),out('maximumError','拟合内点最大误差','number'),out('unit','误差长度单位','string'),out('items','逐点残差与内点表','array'),out('note','标定范围说明','string')],
        '默认点表为合成演示，生产须替换。按行对应同一物理点。至少三个不共线点，建议六个以上并覆盖三维空间。估计旋转/平移；长度单位明确换算，不估计未知缩放。此方法不是运动式手眼标定。'),
        op('points','3D 点位坐标转换','none',[model,inverse,point_table],common+[out('items','输入/输出坐标表','array')],
        '绑定完整标定结果，点表按标定输入单位填写。反向转换会交换坐标系与单位。输出点可绑定 PLC/脚本所需变量；不自动写设备。'),
        op('cloud','3D 点云坐标转换','cloud',[model,inverse],common+[out('minimum','转换后各轴最小值','array'),out('maximum','转换后各轴最大值','array'),out('note','通道说明','string')],
        '严格检查点云单位和坐标系，转换后更新名称/单位。颜色保留、法向仅旋转；清除旧投影内外参及图像/深度通道，避免混用两种坐标。'),
        op('check','3D 标定独立点验证','none',[model,inverse,pair_table]+quality,[out('passed','独立点验证通过','boolean'),out('rmsError','验证点均方根误差','number'),out('maximumError','验证点最大误差','number'),out('unit','验证误差单位','string'),out('pointCount','验证点数','integer'),out('items','逐点误差与判定表','array')],
        '使用没有参与拟合的独立点表验证标定。超出误差门限返回不通过，供条件分支使用；不重新拟合，也不替换原标定。')]
    manifest=dict(apiVersion=1,id='sieans-rigid',name='SIEANS 三维坐标标定与转换',version='1.0.0',license='MIT',description='对应点刚体标定、独立验证、正反向点位/点云坐标转换。',operators=ops)
    (FOLDER/'operator-plugin.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    cloud=dict(points=source.tolist(),colors=[[.1,.65,.9]]*len(source),unit='mm',frame='camera-optical')
    (SAMPLES/'rigid-source.json').write_text(json.dumps(cloud,indent=2)+'\n',encoding='utf-8')
    def step(op,args={},bindings=[]):return dict(operation='plugin',params=dict(pluginId='sieans-rigid',pluginVersion='1.0.0',operatorId=op,arguments=args,outputBindings=bindings))
    calibration=step('calibrate',{},[dict(scope='flow',name='frameCalibration',field='calibration')])
    ref={'$ref':'flow.frameCalibration'}
    bad=json.loads(json.dumps(pairs));bad[-1]['targetX']+=40
    heldout=[]
    for v in [[10,20,30],[15,50,80],[60,70,10]]:
        actual=np.array(v)@rotation.T+[300,500,100]
        heldout.append(dict(zip(['sourceX','sourceY','sourceZ','targetX','targetY','targetZ'],map(float,np.r_[v,actual]))))
    failed=json.loads(json.dumps(heldout));failed[0]['targetX']+=2
    demos=[dict(id='rigid-points',name='3D 坐标标定 · 相机点转工装点',category='3D 点云',cloud='rigid-source.json',description='八组合成对应点恢复绕 Z 轴旋转 90° 及平移 (300,500,100) mm；结果绑定流程变量后转换新点。',expected='输入 (10,20,30) mm，工装坐标为 (280,510,130) mm。',steps=[calibration,step('points',dict(calibration=ref))]),
        dict(id='rigid-outlier',name='3D 对应点 · 排除一个错误配对',category='3D 点云',cloud='rigid-source.json',description='八组对应点中一个错误配对，采用 RANSAC 拟合，其余七点独立决定刚体关系。',expected='7 个内点、1 个排除点，仍输出 (280,510,130) mm。',steps=[step('calibrate',dict(pairs=bad,method='ransac')),step('points',dict(calibration={'$ref':'flow.frameCalibration'}))]),
        dict(id='rigid-cloud',name='3D 点云 · 坐标转换后测量',category='3D 点云',cloud='rigid-source.json',description='标定结果驱动整个点云进入工装坐标，再由真实 Open3D 计算包围尺寸。',expected='坐标系变为 fixture-base；范围 X=200–300、Y=500–600、Z=100–200 mm。',steps=[calibration,step('cloud',dict(calibration=ref)),dict(operation='cloud_measure',params={})]),
        dict(id='rigid-check',name='3D 标定验证 · 独立点超差',category='3D 点云',cloud='rigid-source.json',description='使用三组未参与拟合的独立点，其中一个目标坐标偏差 2 mm；验证保留原模型并返回不通过。',expected='独立验证不通过，最大误差约 2 mm。',steps=[calibration,step('check',dict(calibration=ref,pairs=failed))])]
    demos[1]['steps'][0]['params']['outputBindings']=[dict(scope='flow',name='frameCalibration',field='calibration')]
    demos.append(dict(id='rigid-modbus',name='3D 坐标 → Modbus 模拟寄存器',category='工业通信',cloud='rigid-source.json',description='标定后的点位 X 保存到流程变量，再以 float32 写入并读回本机 Modbus 模拟器，不连接现场 PLC。',expected='工装点 X=280 mm；保持寄存器 80–81 写入/读回 float32 值 280。',steps=[calibration,step('points',dict(calibration=ref),[dict(scope='flow',name='fixtureX',field='items.0.targetX')]),dict(operation='modbus_write',params=dict(transport='simulator',area='holding',address=80,dataType='float32',value={'$ref':'flow.fixtureX'},timeoutMs=1500)),dict(operation='modbus_read',params=dict(transport='simulator',area='holding',address=80,dataType='float32',count=1,timeoutMs=1500))]))
    (SAMPLES/'demos-rigid.json').write_text(json.dumps(demos,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


if __name__=='__main__':generate()
