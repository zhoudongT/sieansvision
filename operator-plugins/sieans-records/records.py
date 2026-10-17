"""Bounded typed record transformations; state is committed by runtime bindings."""
import copy
import json
import math
import statistics

MAX_ROWS=1000
MAX_BYTES=500000
MISSING=object()
FORBIDDEN={'__proto__','prototype','constructor','$ref'}


def integer(value,label,low,high):
    if isinstance(value,bool) or not isinstance(value,int) or not low<=value<=high:raise ValueError(label+'范围或类型无效')
    return value


def key(value):
    if not isinstance(value,str) or not 1<=len(value)<=64 or value in FORBIDDEN or '.' in value or value.strip()!=value or any(ord(c)<32 for c in value):raise ValueError('记录字段名无效或包含保留名称')
    return value


def validate(value,maximum=MAX_BYTES):
    budget=[0]
    def walk(v,depth=0):
        budget[0]+=1
        if depth>12 or budget[0]>50000:raise ValueError('记录嵌套或元素数量超限')
        if v is None or isinstance(v,(bool,str)):return
        if isinstance(v,(int,float)) and not isinstance(v,bool):
            if not math.isfinite(v):raise ValueError('记录数值必须有限')
            return
        if isinstance(v,list):
            if len(v)>MAX_ROWS:raise ValueError('数组最多 1000 项')
            for item in v:walk(item,depth+1)
            return
        if isinstance(v,dict):
            if len(v)>100:raise ValueError('每个结构体最多 100 个字段')
            for k,item in v.items():key(k);walk(item,depth+1)
            return
        raise ValueError('记录值须为数值、文本、开关、空值或结构化字段')
    walk(value)
    if len(json.dumps(value,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode('utf-8'))>maximum:raise ValueError('记录数据超过容量上限')
    return value


def table(value):
    if not isinstance(value,list) or len(value)>MAX_ROWS or any(not isinstance(row,dict) for row in value):raise ValueError('记录表必须为最多 1000 行的结构体数组')
    return validate(value)


def path(value):
    if not isinstance(value,str) or len(value)>300:raise ValueError('字段路径无效')
    parts=value.split('.')
    if len(parts)>12:raise ValueError('字段路径过深')
    for part in parts:key(part)
    return parts


def lookup(row,parts):
    value=row
    for part in parts:
        if isinstance(value,dict) and part in value:value=value[part]
        elif isinstance(value,list) and part.isdigit() and str(int(part))==part and int(part)<len(value):value=value[int(part)]
        else:return MISSING
    return value


def kind(value):
    if value is None:return 'null'
    if isinstance(value,bool):return 'boolean'
    if isinstance(value,(int,float)):return 'number'
    if isinstance(value,str):return 'string'
    return 'structured'


def scalar_key(row,parts):
    value=lookup(row,parts)
    if value is MISSING or value is None or kind(value)=='structured':raise ValueError('去重键须为存在且非空的标量字段')
    return kind(value),value


def append(p):
    rows=copy.deepcopy(table(p['records']));record=p['record']
    if not isinstance(record,dict):raise ValueError('新记录须为结构体')
    validate(record,50000);capacity=integer(p['capacity'],'记录容量',1,MAX_ROWS)
    if len(rows)>capacity:raise ValueError('现有记录已超出容量，请先筛选或增大容量')
    if p['overflow'] not in ('error','drop-oldest') or p['duplicate'] not in ('error','ignore','replace'):raise ValueError('追加策略无效')
    replacement=-1
    if not isinstance(p['keyField'],str):raise ValueError('去重键路径须为文本')
    if p['keyField']:
        parts=path(p['keyField']);seen={}
        for i,row in enumerate(rows):
            identity=scalar_key(row,parts)
            if identity in seen:raise ValueError('已有记录存在重复去重键')
            seen[identity]=i
        replacement=seen.get(scalar_key(record,parts),-1)
    if replacement>=0:
        if p['duplicate']=='error':raise ValueError('新记录的去重键已存在')
        if p['duplicate']=='ignore':return dict(records=rows,count=len(rows),accepted=False,replaced=False,discarded=0)
        rows[replacement]=copy.deepcopy(record);validate(rows)
        return dict(records=rows,count=len(rows),accepted=True,replaced=True,discarded=0)
    discarded=0
    if len(rows)==capacity:
        if p['overflow']=='error':raise ValueError('记录表已满，未覆盖原记录')
        rows.pop(0);discarded=1
    rows.append(copy.deepcopy(record));validate(rows)
    return dict(records=rows,count=len(rows),accepted=True,replaced=False,discarded=discarded)


def matches(value,comparison,right):
    if comparison=='exists':return value is not MISSING
    if comparison=='missing':return value is MISSING
    if comparison in ('is_true','is_false'):
        if kind(value)!='boolean':raise ValueError('开关筛选要求布尔值')
        return value if comparison=='is_true' else not value
    if comparison in ('eq','ne'):
        if kind(value)=='structured' or kind(right)=='structured':raise ValueError('相等筛选只支持标量')
        equal=kind(value)==kind(right) and value==right
        return equal if comparison=='eq' else not equal
    if comparison in ('gt','gte','lt','lte'):
        if kind(value)!='number' or kind(right)!='number':raise ValueError('大小筛选要求两侧均为数值')
        return {'gt':value>right,'gte':value>=right,'lt':value<right,'lte':value<=right}[comparison]
    if comparison=='contains':
        if not isinstance(value,str) or not isinstance(right,str):raise ValueError('包含筛选要求文本')
        return right in value
    raise ValueError('未知筛选方式')


def filter_rows(p):
    rows=table(p['records']);parts=path(p['field']);comparison=p['comparison']
    if comparison not in ('exists','missing','is_true','is_false','eq','ne','gt','gte','lt','lte','contains') or p['missing'] not in ('error','skip'):raise ValueError('筛选策略无效')
    if type(p['keepMatches']) is not bool:raise ValueError('保留匹配项须为开关')
    operand=p['operand']
    if not isinstance(operand,dict) or set(operand)!={'value'}:raise ValueError('比较值需要 value 字段')
    validate(operand)
    if comparison in ('eq','ne') and kind(operand['value'])=='structured':raise ValueError('相等筛选只支持标量比较值')
    if comparison in ('gt','gte','lt','lte') and kind(operand['value'])!='number':raise ValueError('大小筛选的比较值必须为数值')
    if comparison=='contains' and not isinstance(operand['value'],str):raise ValueError('包含筛选的比较值必须为文本')
    selected=[];missing_count=0;matched=0
    for row in rows:
        value=lookup(row,parts)
        if value is MISSING:
            missing_count+=1
            if comparison not in ('exists','missing'):
                if p['missing']=='error':raise ValueError('记录缺少筛选字段：'+p['field'])
                continue
        passed=matches(value,comparison,operand['value'])
        if passed:matched+=1
        if passed==p['keepMatches']:selected.append(copy.deepcopy(row))
    return dict(records=selected,count=len(selected),inputCount=len(rows),matchedCount=matched,missingCount=missing_count)


def sort_rows(p):
    rows=table(p['records']);parts=path(p['field'])
    if p['direction'] not in ('ascending','descending') or p['missing'] not in ('error','first','last'):raise ValueError('排序策略无效')
    present=[];absent=[];types=set()
    for row in rows:
        value=lookup(row,parts)
        if value is MISSING or value is None:
            if p['missing']=='error':raise ValueError('排序字段缺失或为空')
            absent.append(row);continue
        if kind(value)=='structured':raise ValueError('排序字段应为标量')
        types.add(kind(value));present.append((value,row))
    if len(types)>1:raise ValueError('排序字段不能混用数值、文本和开关')
    ordered=[row for value,row in sorted(present,key=lambda pair:pair[0],reverse=p['direction']=='descending')]
    combined=absent+ordered if p['missing']=='first' else ordered+absent
    return dict(records=copy.deepcopy(combined),count=len(rows),missingCount=len(absent))


def select(p):
    rows=table(p['records']);index=integer(p['index'],'行索引',-1,MAX_ROWS-1)
    if p['outOfRange'] not in ('error','empty'):raise ValueError('越界策略无效')
    if index==-1:index=len(rows)-1
    if not 0<=index<len(rows):
        if p['outOfRange']=='error':raise ValueError('记录行索引越界')
        return dict(found=False,record={},index=-1,count=len(rows))
    return dict(found=True,record=copy.deepcopy(rows[index]),index=index,count=len(rows))


def project(p):
    rows=table(p['records']);columns=p['columns']
    if not isinstance(columns,list) or not 1<=len(columns)<=100 or p['missing'] not in ('error','skip-row'):raise ValueError('字段映射表或缺失策略无效')
    mappings=[];names=set()
    for column in columns:
        if not isinstance(column,dict) or set(column)!={'output','source'}:raise ValueError('映射表应包含输出字段与源路径')
        target=key(column['output'])
        if target in names:raise ValueError('输出字段不能重名')
        names.add(target);mappings.append((target,path(column['source'])))
    selected=[];skipped=0
    for row in rows:
        result={}
        for target,source in mappings:
            value=lookup(row,source)
            if value is MISSING:
                if p['missing']=='error':raise ValueError('记录缺少映射来源字段')
                break
            result[target]=copy.deepcopy(value)
        else:selected.append(result);continue
        skipped+=1
    validate(selected)
    return dict(records=selected,count=len(selected),inputCount=len(rows),skippedCount=skipped)


def summary(p):
    rows=table(p['records']);parts=path(p['field'])
    if p['missing'] not in ('error','skip'):raise ValueError('统计缺失策略无效')
    values=[];missing=0
    for row in rows:
        value=lookup(row,parts)
        if value is MISSING or value is None:
            if p['missing']=='error':raise ValueError('统计字段缺失或为空')
            missing+=1;continue
        if kind(value)!='number':raise ValueError('统计字段必须为数值，不能是文本或开关')
        values.append(value)
    metrics={}
    if values:
        try:metrics=dict(sum=math.fsum(values),mean=statistics.mean(values),minimum=min(values),maximum=max(values),median=statistics.median(values),populationStddev=statistics.pstdev(values))
        except (OverflowError,ValueError):raise ValueError('统计结果溢出') from None
        if any(not math.isfinite(v) for v in metrics.values()):raise ValueError('统计结果溢出')
    return dict(inputCount=len(rows),valueCount=len(values),missingCount=missing,hasValues=bool(values),summary=metrics)


def run(ctx):
    p=ctx['params'];task=p['task']
    if task=='build':
        record=p['fields']
        if not isinstance(record,dict):raise ValueError('记录字段应为结构体')
        validate(record,50000);result=dict(record=copy.deepcopy(record),fieldCount=len(record))
    else:
        actions={'append':append,'filter':filter_rows,'sort':sort_rows,'select':select,'project':project,'summary':summary}
        if task not in actions:raise ValueError('未知记录操作')
        result=actions[task](p)
    return dict(result=result)
