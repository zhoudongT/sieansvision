"""Classic S7 byte/bit transactions; the worker process owns the deadline."""
from datetime import datetime, timezone
import math
import re
import struct
import time
from modbus_adapter import integer

FORMATS = {'uint8':'B', 'int8':'b', 'uint16':'H', 'int16':'h', 'uint32':'I', 'int32':'i', 'float32':'f', 'float64':'d'}
WIDTHS = {key:struct.calcsize('>'+fmt) for key,fmt in FORMATS.items()}


def validate(operation, p):
    if operation not in ('s7_read','s7_write') or not isinstance(p,dict):
        raise ValueError('S7 操作或参数无效')
    host = p.get('host','127.0.0.1')
    if not isinstance(host,str) or not host or len(host)>253 or re.search(r'[\s/\\\x00]',host):
        raise ValueError('设备地址必须为 IP 或主机名，不包含协议或路径')
    connection = p.get('connection','plc')
    if connection not in ('plc','simulator'):
        raise ValueError('S7 连接方式无效')
    port = integer(p,'port',102,1,65535)
    rack,slot = integer(p,'rack',0,0,7),integer(p,'slot',1,0,31)
    integer(p,'timeoutMs',3000,100,10000)
    area,dtype = p.get('area','db'),p.get('dataType','uint16')
    writing = operation=='s7_write'
    if area not in ('db','mk','pe','pa'):
        raise ValueError('S7 数据区仅支持 DB、M、I、Q')
    if writing and area=='pe':
        raise ValueError('输入区 I 仅支持读取')
    if dtype not in (*FORMATS,'bool'):
        raise ValueError('S7 数据类型无效')
    db = integer(p,'dbNumber',1,1,65535) if area=='db' else 0
    offset = integer(p,'byteOffset',0,0,2097151)
    bit = integer(p,'bitOffset',0,0,7) if dtype=='bool' else 0
    values,raw = [],b''
    if writing:
        values = p.get('values',p.get('value'))
        if not isinstance(values,list): values=[values]
        if not values or len(values)>200:
            raise ValueError('写入值不能为空，单次最多 200 字节')
        for value in values:
            if dtype=='bool':
                if type(value) is not bool: raise ValueError('BOOL 写入必须使用开关类型')
                raw+=bytes([int(value)])
            else:
                if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):
                    raise ValueError('S7 写入必须为有限数值')
                if dtype.startswith(('uint','int')) and not isinstance(value,int):
                    raise ValueError('整数类型不能写入小数')
                try: raw+=struct.pack('>'+FORMATS[dtype],value)
                except (OverflowError,struct.error): raise ValueError('写入值超出 '+dtype+' 范围') from None
        count=len(values)
    else:
        count=integer(p,'count',1,1,200)
    if dtype=='bool' and count!=1:
        raise ValueError('BOOL 每次访问一个位；批量位请使用字节类型或多个节点')
    size=count*(WIDTHS.get(dtype,1))
    if size>200: raise ValueError('S7 单次数据最多 200 字节，请减少数量')
    if offset+size>2097152: raise ValueError('S7 字节地址范围越界')
    return dict(host=host,port=port,rack=rack,slot=slot,area=area,dtype=dtype,db=db,offset=offset,bit=bit,
                writing=writing,values=values,raw=raw,count=count,size=size)


def decode(raw, dtype, count):
    if len(raw)!=count*WIDTHS.get(dtype,1): raise ValueError('S7 返回字节数量不匹配')
    if dtype=='bool':
        if raw[0] not in (0,1): raise ValueError('S7 返回的位值无效')
        return [bool(raw[0])]
    values=list(struct.unpack('>'+FORMATS[dtype]*count,raw))
    if any(not math.isfinite(value) for value in values): raise ValueError('设备返回非有限数值，请检查地址和类型')
    return values


def run(operation, params):
    c=validate(operation,params)
    from s7 import Client
    from snap7.type import Area, WordLen, Parameter
    client=Client(auto_reconnect=False,max_retries=0)
    # Minimum standard PDU fits our 200-byte payload in one request, never chunks writes.
    client.set_param(Parameter.PDURequest,240)
    started=time.perf_counter()
    sent=False
    try:
        client.connect(c['host'],c['rack'],c['slot'],tcp_port=c['port'])
        area={'db':Area.DB,'mk':Area.MK,'pe':Area.PE,'pa':Area.PA}[c['area']]
        is_bit=c['dtype']=='bool'
        address=c['offset']*8+c['bit'] if is_bit else c['offset']
        word_len=WordLen.Bit if is_bit else WordLen.Byte
        if c['writing']:
            sent=True
            response=client.write_area(area,c['db'],address,bytearray(c['raw']),word_len=word_len)
            if response!=0: raise ValueError('S7 写入应答异常')
            raw=c['raw']
        else:
            raw=bytes(client.read_area(area,c['db'],address,c['size'],word_len=word_len))
        values=decode(raw,c['dtype'],c['count'])
        result=dict(protocol='s7',action='write' if c['writing'] else 'read',area=c['area'],dbNumber=c['db'],
                    byteOffset=c['offset'],dataType=c['dtype'],count=c['count'],values=values,
                    value=values[0] if len(values)==1 else values,quality='good',timestamp=datetime.now(timezone.utc).isoformat(),
                    items=[dict(byteOffset=c['offset']+i*WIDTHS.get(c['dtype'],1),dataType=c['dtype'],value=v,**({'bitOffset':c['bit']} if is_bit else {})) for i,v in enumerate(values)])
        if is_bit: result['bitOffset']=c['bit']
        else: result['rawBytes']=list(raw)
        if c['writing']:
            result['acknowledged']=True
            result['note']='设备已应答，不代表物理动作完成；外部写入不随流程回滚。'
            if values!=c['values']: result['requestedValues']=c['values']
        return dict(operation=operation,result=result,elapsedMs=round((time.perf_counter()-started)*1000,1))
    except Exception as error:
        if sent: raise RuntimeError(str(error)+'；写请求可能已到达设备，未自动重试，请读取设备状态确认') from error
        raise
    finally:
        client.disconnect()
