"""Record operators and no-script collection demonstrations."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1];FOLDER=ROOT/'operator-plugins/sieans-records';SAMPLES=ROOT/'public/vision/samples'


def field(key,label,kind,default,**kw):
    result=dict(key=key,label=label,type=kind,default=default,required=True);result.update(kw);return result
def output(key,label,kind):return dict(key=key,label=label,type=kind,required=True)
def choice(value,label):return dict(value=value,label=label)


def generate():
    FOLDER.mkdir(exist_ok=True)
    records=field('records','输入记录表','array',[])
    path=field('field','字段路径（点分隔）','string','value')
    error_skip=field('missing','缺失字段处理','string','error',choices=[choice('error','报错'),choice('skip','跳过该行')])
    rows_out=[output('records','输出记录表','array'),output('count','输出记录数','integer')]
    def op(id,name,params,outputs,description):return dict(id=id,name=name,description=description,entry='records.py',input='none',timeoutMs=5000,parameters=[field('task','处理功能','string',id,choices=[choice(id,name)])]+params,outputs=outputs)
    ops=[op('build','按字段创建记录',[field('fields','记录字段与绑定','object',{'value':0})],[output('record','单条记录','object'),output('fieldCount','字段数','integer')],
        '在字段表中定义名称、类型和变量/上游结果绑定，输出单条结构体。可以整理检测值或机器人与相机位姿，不运行自定义脚本。'),
        op('append','记录表追加与去重',[records,field('record','待追加记录','object',{}),field('capacity','最大保留行数','integer',100,minimum=1,maximum=1000),field('overflow','满表策略','string','error',choices=[choice('error','报错并保留原表'),choice('drop-oldest','丢弃最早一行')]),field('keyField','去重键路径（空白关闭去重）','string','',required=False),field('duplicate','键重复策略','string','error',choices=[choice('error','报错'),choice('ignore','忽略新记录'),choice('replace','原位替换')])],rows_out+[output('accepted','接收新记录','boolean'),output('replaced','替换已有行','boolean'),output('discarded','因满表丢弃行数','integer')],
        '输入/输出记录表可绑定同一个变量，流程成功后提交。默认满表和重复键报错，不静默覆盖。最多 1000 行/500 KB，新记录最多 50 KB；键区分数值、文本和开关。'),
        op('filter','记录筛选与排除',[records,path,field('comparison','比较方式','string','eq',choices=[choice(k,v) for k,v in [('eq','等于'),('ne','不等于'),('gt','大于'),('gte','大于等于'),('lt','小于'),('lte','小于等于'),('contains','文本包含'),('is_true','开关为是'),('is_false','开关为否'),('exists','字段存在'),('missing','字段缺失')]]),field('operand','比较值（value 字段）','object',{'value':0}),field('keepMatches','保留匹配行（否则排除）','boolean',True),error_skip],rows_out+[output('inputCount','输入记录数','integer'),output('matchedCount','符合条件行数','integer'),output('missingCount','缺字段行数','integer')],
        '严格按类型筛选，不把文本数字或开关隐式转成数值。字段存在/缺失比较区分空值与缺失；跳过缺字段时，该行不会进入保留或排除结果。'),
        op('sort','记录字段稳定排序',[records,path,field('direction','排序方向','string','ascending',choices=[choice('ascending','升序'),choice('descending','降序')]),field('missing','缺失或空值处理','string','error',choices=[choice('error','报错'),choice('first','放在最前'),choice('last','放在最后')])],rows_out+[output('missingCount','缺失或空值行数','integer')],
        '按同类型数值、文本或开关排序。同值保留原相对顺序；不混排文本和数值。缺失/空值的位置不受升降序影响。'),
        op('select','按行读取记录',[records,field('index','行索引（0 起，-1 末行）','integer',0,minimum=-1,maximum=999),field('outOfRange','越界处理','string','error',choices=[choice('error','报错'),choice('empty','返回未找到与空记录')])],[output('found','找到记录','boolean'),output('record','所选记录','object'),output('index','实际行索引','integer'),output('count','输入记录数','integer')],
        '索引可绑定变量或循环轮次。越界返回空记录时必须检查 found，不把缺失行当作有效测量。'),
        op('project','记录字段映射与精简',[records,field('columns','输出字段与来源路径表','array',[dict(output='value',source='value')],columns=[field('output','输出字段名','string','value'),field('source','来源字段路径','string','value')],minimumRows=1,maximumRows=100),field('missing','来源缺失处理','string','error',choices=[choice('error','报错'),choice('skip-row','跳过整行')])],rows_out+[output('inputCount','输入记录数','integer'),output('skippedCount','跳过行数','integer')],
        '只保留映射的字段，可改名、展开嵌套字段或提取数组项。适合把含采样编号的记录整理成标定算子要求的精确列集。'),
        op('summary','记录数值字段统计',[records,path,error_skip],[output('inputCount','输入记录数','integer'),output('valueCount','有效数值数','integer'),output('missingCount','缺失或空值数','integer'),output('hasValues','存在有效数值','boolean'),output('summary','数值统计表','object')],
        '计算和、均值、最小/最大、中位数及总体标准差。只接受数值；空值按缺失策略处理。没有有效值时返回空统计表和 hasValues=false，不填充假的测量值。')]
    (FOLDER/'operator-plugin.json').write_text(json.dumps(dict(apiVersion=1,id='sieans-records',name='SIEANS 流程记录处理',version='1.0.0',license='MIT',description='有界记录创建、采样累积、查询筛选、排序、映射与统计。',operators=ops),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    def step(op,args={},bindings=[]):return dict(operation='plugin',params=dict(pluginId='sieans-records',pluginVersion='1.0.0',operatorId=op,arguments=args,outputBindings=bindings))
    def bind(name,field):return dict(scope='flow',name=name,field=field)
    ref=lambda name:{'$ref':'flow.'+name}
    raw=[dict(id=1,width=3),dict(id=2,width=8),dict(id=3,width=12),dict(id=4),dict(id=5,width=6)]
    demos=[dict(id='records-inspection',name='检测记录 · 连续累积与统计',category='流程控制',image='parts.png',variables=dict(sequence=0,detectedCount=0,currentRecord={},inspectionRecords=[]),description='每轮真实 OpenCV 计数，按字段创建记录并追加到流程变量；最多保留三行，满表显式丢弃最早记录。',expected='每条 count=3；多次运行后行数最多 3，序号递增，统计平均值为 3。',steps=[dict(operation='variables',params=dict(scope='flow',name='sequence',mode='increment',value=1)),dict(operation='geometry',params=dict(feature='contours',threshold=127,minArea=50)),dict(operation='variables',params=dict(scope='flow',name='detectedCount',value=0)),step('build',dict(fields=dict(sequence=ref('sequence'),count=ref('detectedCount'),passed=True)),[bind('currentRecord','record')]),step('append',dict(records=ref('inspectionRecords'),record=ref('currentRecord'),capacity=3,overflow='drop-oldest',keyField='sequence'),[bind('inspectionRecords','records')]),step('summary',dict(records=ref('inspectionRecords'),field='count'))],bindings=[dict(step=2,param='value',source=1,field='count')]),
        dict(id='records-query',name='记录查询 · 筛选排序与最大项',category='流程控制',image='parts.png',description='筛选宽度至少 6 的记录、按宽度降序、读取首行并统计。显式跳过缺宽度的记录。',expected='保留宽度 12、8、6；首行宽度 12，统计平均值 26/3。',variables=dict(filteredRecords=[],sortedRecords=[]),steps=[step('filter',dict(records=raw,field='width',comparison='gte',operand=dict(value=6),missing='skip'),[bind('filteredRecords','records')]),step('sort',dict(records=ref('filteredRecords'),field='width',direction='descending'),[bind('sortedRecords','records')]),step('select',dict(records=ref('sortedRecords'),index=0)),step('summary',dict(records=ref('sortedRecords'),field='width'))])]
    truth=json.loads((SAMPLES/'handeye-ground-truth.json').read_text())
    poses=[dict(sampleId=i+1,**row) for i,row in enumerate(truth['poses'][:8])]
    mapping=[dict(output=key,source=key) for key in truth['poses'][0]]
    demos.append(dict(id='records-handeye',name='采样记录 → 满六组后手眼标定',category='流程控制',image='handeye-board.png',description='每次运行读取一组预制合成姿态、去重追加、提取十二列。满六组后才进入手眼求解，无需自定义脚本或复制配置文本。',expected='前五次只累积；第六次起恢复相机→工具平移 (30,-20,80) mm。共八条预制样本，第九次索引越界并保留已提交记录。',variables=dict(sampleIndex=0,poseCount=0,sampleRecord={},poseRecords=[],poseRows=[]),steps=[step('select',dict(records=poses,index=ref('sampleIndex')),[bind('sampleRecord','record')]),step('append',dict(records=ref('poseRecords'),record=ref('sampleRecord'),capacity=8,keyField='sampleId'),[bind('poseRecords','records'),bind('poseCount','count')]),step('project',dict(records=ref('poseRecords'),columns=mapping),[bind('poseRows','records')]),dict(operation='variables',params=dict(scope='flow',name='sampleIndex',mode='increment',value=1)),dict(operation='condition',params=dict(comparison='gte',left=ref('poseCount'),right=6)),dict(operation='plugin',params=dict(pluginId='sieans-handeye',pluginVersion='1.0.0',operatorId='fit',arguments=dict(poses=ref('poseRows')),outputBindings=[bind('handeyeCalibration','calibration'),bind('handeyeReference','reference')]))],connections=[[-1,0],[0,1],[1,2],[2,3],[3,4],[4,5,'true']]))
    demos[0]['variables'].update(recordCount=0,meanCount=0)
    demos[0]['steps'][4]['params']['outputBindings'].append(bind('recordCount','count'))
    demos[0]['steps'][5]['params']['outputBindings']=[bind('meanCount','summary.mean')]
    components=[]
    for i,(label,name) in enumerate([('采样序号','sequence'),('保留记录数','recordCount'),('平均检测数量','meanCount')]):
        components.append(dict(id='records-value-'+str(i),type='value',label=label,x=i*4,y=0,w=4,h=2,color='#1095bd',fontSize=32,precision=0,unit='',binding=dict(source='flow',path=name)))
    components.append(dict(id='records-history',type='table',label='检测记录表',x=0,y=2,w=7,h=6,color='#1095bd',fontSize=20,binding=dict(source='flow',path='inspectionRecords')))
    components.append(dict(id='records-image',type='image',label='本轮检测图像',x=7,y=2,w=5,h=6,color='#1095bd',fontSize=20,binding=dict(source='result',nodeId='demo-geometry',path='')))
    demos[0]['hmi']=dict(version=1,title='SIEANS 检测记录采样',rows=8,rowHeight=60,components=components)
    demos[0]['hmiBindings']=[dict(component=4,step=1)]
    (SAMPLES/'demos-records.json').write_text(json.dumps(demos,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


if __name__=='__main__':generate()
