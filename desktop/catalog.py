"""Native schemas for the first migrated built-ins. Plugin schemas come from engine."""
import json
from pathlib import Path
from copy import deepcopy
def field(key, label, kind='number', default=0, **extra):
    return dict(key=key, label=label, type=kind, default=default, **extra)


def choices(*values):
    return [dict(value=v, label=label) for v, label in values]


CORE = [
    dict(operation='preprocess', name='图像预处理', category='图像处理', parameters=[
        field('method', '处理方法', 'string', 'grayscale', choices=choices(('grayscale','灰度化'),('blur','高斯模糊'),('threshold','二值化'),('canny','边缘提取'),('open','开运算'),('close','闭运算'))),
        field('threshold','二值阈值',default=127,minimum=0,maximum=255),
        field('kernel','核大小（奇数）','integer',3,minimum=1,maximum=51)]),
    dict(operation='geometry', name='几何特征查找', category='定位与测量', parameters=[
        field('feature','特征','string','contours',choices=choices(('contours','轮廓'),('lines','直线'),('circles','圆'),('edges','边缘'))),
        field('threshold','阈值',default=127,minimum=0,maximum=255),field('minArea','最小面积',default=50,minimum=1),field('invert','反色','boolean',False)]),
    dict(operation='barcode',name='条码与二维码',category='识别',parameters=[]),
    dict(operation='locate',name='模板匹配定位',category='定位与测量',parameters=[field('minScore','最低匹配分数',default=.85,minimum=0,maximum=1),field('maxMatches','最多目标数','integer',1,minimum=1,maximum=50),field('angleStart','起始角度',default=0,minimum=-180,maximum=180),field('angleEnd','终止角度',default=0,minimum=-180,maximum=180),field('angleStep','角度步长',default=10,minimum=1,maximum=180)]),
    dict(operation='defects',name='参考图差异检测',category='识别',parameters=[field('differenceThreshold','灰度差阈值',default=30,minimum=1,maximum=255),field('minArea','最小差异面积',default=20,minimum=1),field('maxDefectRatio','允许差异比例',default=0,minimum=0,maximum=1)]),
    dict(operation='delay',name='延时等待',category='流程控制',parameters=[field('milliseconds','等待时间（ms）','integer',100,minimum=0,maximum=30000)]),
    dict(operation='condition',name='条件判断',category='流程控制',parameters=[field('comparison','比较方式','string','gt',choices=choices(('eq','等于'),('ne','不等于'),('gt','大于'),('lt','小于'),('is_true','为真'),('is_false','为假'))),field('left','左侧值'),field('right','右侧值')]),
    dict(operation='branch_merge',name='分支汇合',category='流程控制',parameters=[]),
    dict(operation='yolo',name='YOLO 目标检测',category='识别',parameters=[field('model','模型文件','string','yolo11n.pt'),field('device','计算设备','string','cpu',choices=choices(('cpu','CPU'),('auto','自动'),('cuda:0','GPU 0'))),field('confidence','置信度',default=.25,minimum=0,maximum=1),field('iou','交并比阈值',default=.45,minimum=0,maximum=1),field('imageSize','推理尺寸','integer',640,minimum=32,maximum=1920)]),
]
for definition in CORE:
    definition['defaults'] = {f['key']: f['default'] for f in definition['parameters']}


def builtin_definitions():
    metadata=json.loads(Path(__file__).with_name('builtin-catalog.json').read_text(encoding='utf-8'))
    definitions={}
    groups={'group':'流程控制','subflow':'流程控制','loop':'流程控制','condition':'流程控制','branch_merge':'流程控制','delay':'流程控制','variables':'变量与数据',
            'preprocess':'图像处理','locate':'定位与测量','geometry':'定位与测量','measure':'定位与测量','barcode':'识别','ocr':'识别','defects':'识别','yolo':'识别','yolo_segment':'识别'}
    for operation,meta in metadata.items():
        if operation=='plugin':continue
        defaults=deepcopy(meta.get('defaults',{}));parameters=[]
        for raw in meta.get('fields',[]):
            key,label,kind,*limits=raw
            definition=dict(key=key,label=label)
            if isinstance(kind,list):definition.update(type='string',choices=[dict(value=v,label=str(v)) for v in kind])
            elif kind in ('text','boolean'):definition['type']='boolean' if kind=='boolean' else 'string'
            else:
                definition.update(type='number',minimum=kind,maximum=limits[0])
                if len(limits)<2 or limits[1]==1:definition['type']='integer'
            if key in defaults:definition['default']=defaults[key]
            parameters.append(definition)
        category=groups.get(operation,'3D 点云' if operation.startswith('cloud_') else '相机采集' if operation.startswith('camera_') else '工业通信')
        definitions[operation]=dict(operation=operation,name=meta['name'],category=category,defaults=defaults,parameters=parameters,
                                    description=meta.get('description','')+'\n'+meta.get('hint',''))
    def extra(op,key,label,kind='number',default=None,**kwargs):
        d=dict(key=key,label=label,type=kind,**kwargs)
        if default is not None:d['default']=default
        definitions[op]['parameters'].append(d)
    for op in ('condition',):
        extra(op,'left','左侧值',default=0);extra(op,'right','右侧值',default=0)
    extra('variables','value','赋值内容','any',1)
    definitions['script']['category']='变量与数据'
    extra('script','arguments','脚本输入变量','object',{'count':0})
    for op in ('modbus_write','s7_write','opcua_write','mqtt_publish','socket_tcp','socket_udp','tcp_exchange','udp_exchange','serial_exchange'):
        if op in definitions:
            extra(op,'value','发送 / 写入内容','any',definitions[op]['defaults'].get('value',''))
            extra(op,'values','批量数值','array',[],items={'type':'number'})
    for op in ('preprocess','geometry','measure'):
        for key,label,value in [('cannyLow','边缘低阈值',50),('cannyHigh','边缘高阈值',150)]:extra(op,key,label,'integer',value,minimum=0,maximum=255)
    for op in ('geometry','measure'):
        for key,label,value in [('minRadius','最小半径',0),('maxRadius','最大半径',0),('minDistance','圆心最小距离',20),('votes','检测票数',30),('minLength','最短直线',30),('maxGap','最大断点间距',10)]:extra(op,key,label,default=value,minimum=0)
    for op in ('yolo','yolo_segment'):extra(op,'classes','类别编号筛选','array',[],items={'type':'integer','minimum':0})
    extra('locate','scales','搜索比例','array',[1],items={'type':'number','minimum':0.01})
    extra('locate','origin','模板坐标原点','array',items={'type':'number'},minItems=2,maxItems=2)
    extra('measure','points','测量坐标点','array',items={'type':'array','items':{'type':'number'},'minItems':2,'maxItems':2})
    extra('measure','calibration','平面比例标定','object',properties=[field('points','标定像素点','array',[],items={'type':'array','items':{'type':'number'},'minItems':2,'maxItems':2}),field('distance','实际距离',default=1),field('unit','单位','string','mm')])
    for key,label in [('minimum','裁剪最小坐标'),('maximum','裁剪最大坐标')]:extra('cloud_filter',key,label,'array',items={'type':'number'},minItems=3,maxItems=3)
    extra('cloud_register','initialTransform','初始变换矩阵','array',items={'type':'array','items':{'type':'number'},'minItems':4,'maxItems':4},minItems=4,maxItems=4)
    for op in ('subflow','loop'):
        extra(op,'subflowId','子流程编号','string','');extra(op,'arguments','输入变量','object',{})
        extra(op,'stateMode','调用状态','string','reset',choices=choices(('reset','每次重置'),('preserve','保留状态')))
    # B3 组合模块 Group（壳层：嵌套 + ImageData/InputROI + 循环设置）
    definitions['group'] = dict(
        operation='group', name='组合模块', category='流程控制',
        defaults=dict(imageData='', inputRoi='', loopEnabled=False, loopCount=1, loopIntervalMs=0,
                      inner=dict(steps=[], edges=[], sourcePosition=dict(x=300, y=40), localVariables={}),
                      io=dict(inputs=[], outputs=[], display={})),
        parameters=[
            field('imageData', 'ImageData', 'string', ''),
            field('inputRoi', 'InputROI', 'string', ''),
            field('loopEnabled', '循环使能', 'boolean', False),
            field('loopCount', '循环次数', 'integer', 1, minimum=1, maximum=100000),
            field('loopIntervalMs', '循环间隔(ms)', 'integer', 0, minimum=0, maximum=100000),
        ],
        description='组合模块（Group）：双击进入嵌套流程；进组前须绑定 ImageData / InputROI；循环设置与主流程分层。',
    )
    for key,label,kind,default in [('iterations','循环上限','integer',1),('mode','循环方式','string','count'),('frameMode','每轮输入','string','previous'),('stopField','停止条件字段','string','passed'),('stopValue','停止条件值','boolean',True)]:extra('loop',key,label,kind,default)
    return definitions


def all_definitions(plugins):
    definitions = builtin_definitions()
    for package in plugins:
        if not package.get('enabled', True):
            continue
        for op in package.get('operators', []):
            key = package['id'] + '/' + op['id']
            definitions[key] = {**op, 'operation': 'plugin', 'pluginId': package['id'],
                                'pluginVersion': package['version'], 'category': op.get('category', '扩展算子'),
                                'defaults': {f['key']: f['default'] for f in op['parameters'] if 'default' in f}}
    return definitions


def definition_for(step, definitions):
    p = step.get('params', {})
    key = p.get('pluginId','') + '/' + p.get('operatorId','') if step['operation']=='plugin' else step['operation']
    return definitions.get(key, dict(name=step.get('name',step['operation']),parameters=[],outputs=[],description='此模块的专用桌面编辑器尚未迁移，原有参数完整保留。'))
