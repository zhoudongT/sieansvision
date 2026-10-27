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
        field('feature','特征','string','contours',choices=choices(('contours','轮廓'),('lines','直线'),('circles','圆'),('rects','矩形'),('edges','边缘'))),
        field('threshold','阈值',default=127,minimum=0,maximum=255),field('minArea','最小面积',default=50,minimum=1),field('invert','反色','boolean',False)]),
    dict(operation='barcode',name='条码与二维码',category='识别',parameters=[]),
    dict(operation='locate',name='模板匹配定位',category='定位与测量',parameters=[field('matchMode','匹配模式','string','fast',choices=choices(('fast','快速匹配'),('gray','灰度模板匹配'))),field('minScore','最低匹配分数',default=.85,minimum=0,maximum=1),field('maxMatches','最多目标数','integer',1,minimum=1,maximum=50),field('angleStart','起始角度',default=0,minimum=-180,maximum=180),field('angleEnd','终止角度',default=0,minimum=-180,maximum=180),field('angleStep','角度步长',default=10,minimum=1,maximum=180)]),
    dict(operation='defects',name='参考图差异检测',category='识别',parameters=[field('differenceThreshold','灰度差阈值',default=30,minimum=1,maximum=255),field('minArea','最小差异面积',default=20,minimum=1),field('maxDefectRatio','允许差异比例',default=0,minimum=0,maximum=1)]),
    dict(operation='delay',name='延时等待',category='流程控制',parameters=[field('milliseconds','等待时间（ms）','integer',100,minimum=0,maximum=30000)]),
    dict(operation='condition',name='条件判断',category='流程控制',parameters=[field('comparison','比较方式','string','gt',choices=choices(('eq','等于'),('ne','不等于'),('gt','大于'),('lt','小于'),('is_true','为真'),('is_false','为假'))),field('left','左侧值'),field('right','右侧值')]),
    dict(operation='branch_merge',name='分支汇合',category='流程控制',parameters=[]),
    dict(operation='branch',name='分支模块',category='流程控制',parameters=[]),
    dict(operation='pose_correct',name='位置修正',category='定位与测量',parameters=[
        field('fixtureSource','位姿来源','string','auto',choices=choices(('auto','自动上游'),('manual','手动'),('bind','绑定字段'))),
        field('baseX','基准X',default=0),field('baseY','基准Y',default=0),field('baseAngle','基准角度',default=0),
        field('followRoi','跟随ROI','boolean',True)]),
    dict(operation='yolo',name='YOLO 目标检测',category='识别',parameters=[field('model','模型文件','string','yolo11n.pt'),field('device','计算设备','string','cpu',choices=choices(('cpu','CPU'),('auto','自动'),('cuda:0','GPU 0'))),field('confidence','置信度',default=.25,minimum=0,maximum=1),field('iou','交并比阈值',default=.45,minimum=0,maximum=1),field('imageSize','推理尺寸','integer',640,minimum=32,maximum=1920)]),
]
for definition in CORE:
    definition['defaults'] = {f['key']: f['default'] for f in definition['parameters']}


def builtin_definitions():
    metadata=json.loads(Path(__file__).with_name('builtin-catalog.json').read_text(encoding='utf-8'))
    definitions={}
    groups={'group':'流程控制','subflow':'流程控制','loop':'流程控制','condition':'流程控制','branch_merge':'流程控制','branch':'流程控制','delay':'流程控制','variables':'变量与数据','var_calc':'变量与数据','format_data':'变量与数据','text_save':'变量与数据','elapsed_stats':'流程控制','receive_data':'工业通信','send_data':'工业通信','protocol_parse':'工业通信','output_image':'图像处理',
            'preprocess':'图像处理','locate':'定位与测量','pose_correct':'定位与测量','distort_correct':'标定与校正','nine_point':'标定与校正','geometry':'定位与测量','measure':'定位与测量','line_intersect':'定位与测量','point_distance':'定位与测量','point_line_distance':'定位与测量','csharp_script':'变量与数据','barcode':'识别','ocr':'识别','defects':'识别','yolo':'识别','yolo_segment':'识别'}
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
    # Wave2: 位置修正 / 分支模块（设计态壳 + 运行透传）
    definitions['pose_correct'] = dict(
        operation='pose_correct', name='位置修正', category='定位与测量',
        defaults=dict(fixtureSource='auto', baseX=0.0, baseY=0.0, baseAngle=0.0, followRoi=True,
                      outputCoord='fixture', bindStepId='', bindField='matches[0]'),
        parameters=[
            field('fixtureSource', '位姿来源', 'string', 'auto',
                  choices=choices(('auto', '自动上游'), ('manual', '手动'), ('bind', '绑定字段'))),
            field('baseX', '基准X', default=0),
            field('baseY', '基准Y', default=0),
            field('baseAngle', '基准角度', default=0),
            field('followRoi', '跟随ROI', 'boolean', True),
        ],
        description='位置修正：用匹配位姿校正后续 ROI/坐标系（VM p=9）。',
    )
    definitions['branch'] = dict(
        operation='branch', name='分支模块', category='流程控制',
        defaults=dict(paths=[], defaultPathId='default'),
        parameters=[],
        description='分支模块：多路径条件表；出边 when=路径名（VM p=19）。',
    )

    # Wave3: 畸变/九点/变量计算/耗时/收发/薄壳
    definitions['distort_correct'] = dict(
        operation='distort_correct', name='畸变矫正', category='标定与校正',
        defaults=dict(mode='file', calibPath='', enabled=True, fx=1000.0, fy=1000.0, cx=0.0, cy=0.0,
                      k1=0.0, k2=0.0, p1=0.0, p2=0.0, k3=0.0, boardCols=9, boardRows=6, squareSize=10.0, alpha=0.0),
        parameters=[
            field('mode', '矫正模式', 'string', 'file',
                  choices=choices(('file', '标定文件'), ('coeffs', '手动系数'), ('chessboard', '棋盘格'))),
            field('calibPath', '标定文件', 'string', ''),
            field('enabled', '启用矫正', 'boolean', True),
        ],
        description='畸变矫正（VM p=13）：标定文件或内参系数；运行透传并回显。',
    )
    definitions['nine_point'] = dict(
        operation='nine_point', name='九点标定', category='标定与校正',
        defaults=dict(coordSystem='机械坐标系', unit='mm', method='affine', points=[]),
        parameters=[
            field('coordSystem', '坐标系', 'string', '机械坐标系'),
            field('unit', '单位', 'string', 'mm'),
            field('method', '求解方法', 'string', 'affine',
                  choices=choices(('affine', '仿射'), ('perspective', '透视'))),
        ],
        description='平移九点标定（VM p=20）：像素↔世界对照表。',
    )
    definitions['var_calc'] = dict(
        operation='var_calc', name='变量计算', category='变量与数据',
        defaults=dict(scope='flow', expressions=[]),
        parameters=[field('scope', '作用域', 'string', 'flow')],
        description='变量计算（VM p=23）：表达式表写入变量。',
    )
    definitions['elapsed_stats'] = dict(
        operation='elapsed_stats', name='耗时统计', category='流程控制',
        defaults=dict(startStepId='', endStepId='', includeEnds=True, unit='ms'),
        parameters=[
            field('startStepId', '开始模块', 'string', ''),
            field('endStepId', '结束模块', 'string', ''),
        ],
        description='耗时统计（VM p=27）：起止模块区间累计。',
    )
    definitions['receive_data'] = dict(
        operation='receive_data', name='接收数据', category='工业通信',
        defaults=dict(device='', channel='', timeoutMs=1000, encoding='utf-8',
                      targetScope='flow', targetVar='recvData', triggerOnReceive=True),
        parameters=[
            field('device', '通信设备', 'string', ''),
            field('targetVar', '目标变量', 'string', 'recvData'),
            field('timeoutMs', '超时ms', 'integer', 1000, minimum=0, maximum=600000),
        ],
        description='接收数据（VM p=11）：绑定通信设备写入变量。',
    )
    definitions['send_data'] = dict(
        operation='send_data', name='发送数据', category='工业通信',
        defaults=dict(device='', channel='', message='', sourceMode='text',
                      sourceScope='flow', sourceVar='', encoding='utf-8', appendCrLf=False),
        parameters=[
            field('device', '通信设备', 'string', ''),
            field('message', '发送内容', 'string', ''),
        ],
        description='发送数据（VM p=11）：绑定通信设备发送文本/变量。',
    )
    definitions['format_data'] = dict(
        operation='format_data', name='格式化', category='变量与数据',
        defaults=dict(template='{0}', args='', targetVar='formatted', scope='flow'),
        parameters=[field('template', '模板', 'string', '{0}'), field('targetVar', '目标变量', 'string', 'formatted')],
        description='格式化发出数据（VM p=21）。',
    )
    definitions['output_image'] = dict(
        operation='output_image', name='输出图像', category='图像处理',
        defaults=dict(path='', format='png', quality=95, useTimestamp=True, onlyOnOk=False),
        parameters=[field('path', '保存路径', 'string', ''), field('format', '格式', 'string', 'png')],
        description='输出(保存)图像（VM p=22）。',
    )
    definitions['protocol_parse'] = dict(
        operation='protocol_parse', name='协议解析', category='工业通信',
        defaults=dict(sourceVar='recvData', sourceScope='flow', protocol='delimited',
                      delimiter=',', pattern='', fields='f0,f1,f2'),
        parameters=[field('sourceVar', '源变量', 'string', 'recvData'), field('protocol', '协议类型', 'string', 'delimited')],
        description='协议解析（VM p=24）。',
    )
    definitions['text_save'] = dict(
        operation='text_save', name='文本保存', category='变量与数据',
        defaults=dict(path='', content='', sourceVar='', append=True, encoding='utf-8', newline=True),
        parameters=[field('path', '文件路径', 'string', ''), field('append', '追加', 'boolean', True)],
        description='文本保存（VM p=25）。',
    )


    # Wave4: 矩形/几何测量 / C#脚本
    if 'geometry' in definitions:
        # ensure rects in choices if fields already built from json
        for f in definitions['geometry'].get('parameters') or []:
            if f.get('key') == 'feature' and isinstance(f.get('choices'), list):
                vals = {c.get('value') for c in f['choices']}
                if 'rects' not in vals:
                    f['choices'].append(dict(value='rects', label='矩形'))
        definitions['geometry']['description'] = (
            (definitions['geometry'].get('description') or '')
            + '\nWave4：三 Tab 几何查找（直线/圆/矩形/轮廓/边缘）；feature=rects 矩形查找。'
        )

    definitions['rect_find'] = dict(
        operation='rect_find', name='矩形查找', category='定位与测量',
        defaults=dict(feature='rects', roiMode='draw', roiShape='rect', threshold=127, minArea=50,
                      maxCount=1, angleTolerance=5.0, showOverlay=True),
        parameters=[field('feature', '特征', 'string', 'rects')],
        description='矩形查找（VM p=15/集14）：geometry.feature=rects 专用入口。',
    )
    definitions['line_intersect'] = dict(
        operation='line_intersect', name='线与线交点', category='定位与测量',
        defaults=dict(mode='bind', line1From='', line1Field='lines[0]', line2From='', line2Field='lines[0]',
                      x1=0.0, y1=0.0, x2=100.0, y2=0.0, x3=50.0, y3=-50.0, x4=50.0, y4=50.0,
                      unit='px', scale=1.0, showOverlay=True),
        parameters=[
            field('mode', '输入模式', 'string', 'bind', choices=choices(('bind', '绑定上游'), ('manual', '手动坐标'))),
            field('unit', '单位', 'string', 'px'),
        ],
        description='线与线交点（VM p=14/集13）：绑定两条直线或四点；运行解析求交。',
    )
    definitions['point_distance'] = dict(
        operation='point_distance', name='点与点距离', category='定位与测量',
        defaults=dict(mode='bind', point1From='', point1Field='matches[0]', point2From='', point2Field='matches[0]',
                      x1=0.0, y1=0.0, x2=100.0, y2=0.0, unit='px', scale=1.0, showOverlay=True),
        parameters=[
            field('mode', '输入模式', 'string', 'bind', choices=choices(('bind', '绑定上游'), ('manual', '手动坐标'))),
            field('unit', '单位', 'string', 'px'),
            field('scale', '像素比例', default=1.0),
        ],
        description='点与点距离（VM p=16/集15）：绑定两点或手动坐标。',
    )
    definitions['point_line_distance'] = dict(
        operation='point_line_distance', name='点与线距离', category='定位与测量',
        defaults=dict(mode='bind', pointFrom='', pointField='matches[0]', lineFrom='', lineField='lines[0]',
                      px=0.0, py=0.0, x1=0.0, y1=0.0, x2=100.0, y2=0.0, unit='px', scale=1.0, showOverlay=True),
        parameters=[
            field('mode', '输入模式', 'string', 'bind', choices=choices(('bind', '绑定上游'), ('manual', '手动坐标'))),
            field('unit', '单位', 'string', 'px'),
        ],
        description='点与线距离（VM p=17/集16）：点到直线垂距。',
    )
    definitions['csharp_script'] = dict(
        operation='csharp_script', name='C#脚本', category='变量与数据',
        defaults=dict(language='csharp', code='', timeoutMs=5000, entry='Script.Run', references='', arguments={}),
        parameters=[
            field('language', '语言', 'string', 'csharp', choices=choices(('csharp', 'C#'), ('python', 'Python示意'))),
            field('timeoutMs', '超时ms', 'integer', 5000, minimum=100, maximum=120000),
            field('entry', '入口', 'string', 'Script.Run'),
        ],
        description='C# 脚本（VM p=12）：设计态编辑器；本机 C# 标记 unsupported，真实执行请用 script。',
    )

    if 'locate' in definitions:
        extra('locate', 'matchMode', '匹配模式', 'string', 'fast',
              choices=choices(('fast', '快速匹配'), ('gray', '灰度模板匹配')))
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
