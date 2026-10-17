"""One bounded Modbus transaction, with explicit wire addressing and data layout."""
from datetime import datetime, timezone
import math
import re
import struct
import time

FORMATS = {'uint16': 'H', 'int16': 'h', 'uint32': 'I', 'int32': 'i', 'float32': 'f', 'float64': 'd'}
WIDTHS = {key: struct.calcsize('>'+value)//2 for key, value in FORMATS.items()}
AREAS = {'coils': 'read_coils', 'discrete': 'read_discrete_inputs', 'holding': 'read_holding_registers', 'input': 'read_input_registers'}


def integer(p, key, default, low, high):
    value = p.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise ValueError(f'{key} 必须是 {low} 到 {high} 的整数')
    return value


def layout(p):
    dtype = p.get('dataType', 'uint16')
    byte_order, word_order = p.get('byteOrder', 'big'), p.get('wordOrder', 'big')
    if dtype not in FORMATS or byte_order not in ('big', 'little') or word_order not in ('big', 'little'):
        raise ValueError('寄存器数据类型或字节/字序无效')
    return dtype, byte_order, word_order


def wordswap(words, byte_order, word_order):
    if byte_order == 'little':
        words = [word[::-1] for word in words]
    return list(reversed(words)) if word_order == 'little' else words


def encode(values, p):
    dtype, byte_order, word_order = layout(p)
    result = []
    for value in values:
        if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
            raise ValueError('寄存器写入值必须为有限数值')
        if dtype.startswith(('uint', 'int')) and (not isinstance(value, int)):
            raise ValueError('整数寄存器不能写入小数')
        try:
            raw = struct.pack('>'+FORMATS[dtype], value)
        except (OverflowError, struct.error):
            raise ValueError(f'写入值超出 {dtype} 范围') from None
        words = wordswap([raw[i:i+2] for i in range(0,len(raw),2)], byte_order, word_order)
        result.extend(int.from_bytes(word,'big') for word in words)
    return result


def decode(registers, p):
    dtype, byte_order, word_order = layout(p)
    width = WIDTHS[dtype]
    if len(registers) % width:
        raise ValueError('返回寄存器数量与数据类型不匹配')
    values = []
    for i in range(0,len(registers),width):
        words = [word.to_bytes(2,'big') for word in registers[i:i+width]]
        raw = b''.join(wordswap(words,byte_order,word_order))
        value = struct.unpack('>'+FORMATS[dtype],raw)[0]
        if not math.isfinite(value):
            raise ValueError('设备返回 NaN/Infinity，请检查数据类型和字节序')
        values.append(value)
    return values


def validate(operation, p):
    if operation not in ('modbus_read','modbus_write') or not isinstance(p,dict):
        raise ValueError('未知工业通信操作或参数格式无效')
    transport = p.get('transport','tcp')
    if transport not in ('tcp','rtu'):
        raise ValueError('transport 仅支持 tcp 或 rtu')
    timeout = integer(p,'timeoutMs',1500,100,10000)
    device = integer(p,'deviceId',1,1 if transport=='rtu' else 0,247 if transport=='rtu' else 255)
    if transport == 'tcp':
        host = p.get('host','127.0.0.1')
        if not isinstance(host,str) or not host or len(host)>253 or re.search(r'[\s/\\\x00]',host):
            raise ValueError('host 必须是 IP 或主机名，不包含协议和路径')
        connection = {'host':host,'port':integer(p,'port',502,1,65535)}
    else:
        port = p.get('serialPort','')
        if not isinstance(port,str) or not re.fullmatch(r'COM[1-9][0-9]{0,3}|/dev/[A-Za-z0-9_./-]+',port,re.I):
            raise ValueError('serialPort 必须是 COM 端口或 /dev/ 下的串口路径')
        baudrate = integer(p,'baudrate',19200,300,4000000)
        bytesize = integer(p,'bytesize',8,7,8)
        stopbits = integer(p,'stopbits',1,1,2)
        parity = p.get('parity','N')
        if parity not in ('N','E','O'):
            raise ValueError('parity 必须为 N、E 或 O')
        connection = {'port':port,'baudrate':baudrate,'bytesize':bytesize,'stopbits':stopbits,'parity':parity}
    area = p.get('area','holding')
    if area not in AREAS:
        raise ValueError('area 必须为 coils、discrete、holding 或 input')
    writing = operation=='modbus_write'
    if writing and area not in ('coils','holding'):
        raise ValueError('离散输入和输入寄存器只读')
    bits = area in ('coils','discrete')
    dtype = 'bool' if bits else layout(p)[0]
    address = integer(p,'address',0,0,65535)
    if writing:
        values = p.get('values',p.get('value'))
        if not isinstance(values,list):
            values=[values]
        if not values or len(values)>1968:
            raise ValueError('写入值列表为空或超过协议上限')
        if bits:
            if any(type(value) is not bool for value in values):
                raise ValueError('线圈写入值必须为 true / false')
            wire = values
        else:
            wire = encode(values,p)
        count = len(values)
    else:
        count = integer(p,'count',1,1,2000 if bits else 125)
        values,wire = [],[]
    wire_count = count*(1 if bits else WIDTHS[dtype])
    if wire_count>(1968 if writing and bits else 2000 if bits else 123 if writing else 125):
        raise ValueError('读取/写入数量超出单次 Modbus 请求上限')
    if address+wire_count>65536:
        raise ValueError('地址范围越界；使用从 0 开始的协议地址')
    return {'transport':transport,'connection':connection,'timeout':timeout,'device':device,'area':area,'dtype':dtype,
            'address':address,'bits':bits,'writing':writing,'values':values,'wire':wire,'count':count,'wireCount':wire_count}


def run(operation, params):
    config = validate(operation,params)
    from pymodbus.client import ModbusTcpClient, ModbusSerialClient
    constructor = ModbusTcpClient if config['transport']=='tcp' else ModbusSerialClient
    # No automatic retries: a lost write acknowledgement is not permission to repeat it.
    client = constructor(**config['connection'],timeout=config['timeout']/1000,retries=0)
    started = time.perf_counter()
    sent = False
    try:
        if not client.connect():
            raise ConnectionError('无法连接 Modbus 设备，请检查端口和地址')
        address, device = config['address'], config['device']
        if config['writing']:
            sent = True
            if config['bits']:
                response = client.write_coil(address,config['wire'][0],device_id=device) if config['wireCount']==1 else client.write_coils(address,config['wire'],device_id=device)
            else:
                response = client.write_register(address,config['wire'][0],device_id=device) if config['wireCount']==1 else client.write_registers(address,config['wire'],device_id=device)
        else:
            response = getattr(client,AREAS[config['area']])(address,count=config['wireCount'],device_id=device)
        if response.isError():
            raise ValueError(f'Modbus 设备异常响应，功能码 {response.function_code}，异常码 {getattr(response,"exception_code","unknown")}')
        if config['writing']:
            if response.address!=address or (config['wireCount']>1 and response.count!=config['wireCount']):
                raise ValueError('设备写入确认的地址/数量不匹配')
            if config['wireCount']==1 and (response.bits[0] if config['bits'] else response.registers[0])!=config['wire'][0]:
                raise ValueError('设备写入确认的数值不匹配')
            values = config['values'] if config['bits'] else decode(config['wire'],params)
        elif config['bits']:
            values = response.bits[:config['count']]
            if len(values)!=config['count']:
                raise ValueError('设备返回的线圈数量不足')
        else:
            if len(response.registers)!=config['wireCount']:
                raise ValueError('设备返回的寄存器数量不匹配')
            values = decode(response.registers,params)
        result = {'protocol':'modbus-'+config['transport'],'action':'write' if config['writing'] else 'read','area':config['area'],
                  'deviceId':device,'address':address,'dataType':config['dtype'],'count':len(values),'values':values,
                  'value':values[0] if len(values)==1 else values,'quality':'good','timestamp':datetime.now(timezone.utc).isoformat(),
                  'items':[{'address':address+i*(1 if config['bits'] else WIDTHS[config['dtype']]),'dataType':config['dtype'],'value':value} for i,value in enumerate(values)]}
        if not config['bits']:
            result['registers']=config['wire'] if config['writing'] else response.registers
        if config['writing']:
            result['acknowledged']=True
            if values!=config['values']:
                result['requestedValues']=config['values']
            result['note']='设备已应答写请求；不等于物理动作完成。外部写入不会随流程变量回滚。'
        return {'operation':operation,'result':result,'elapsedMs':round((time.perf_counter()-started)*1000,1)}
    except Exception as error:
        if sent:
            raise RuntimeError(str(error)+'；写请求可能已到达设备，未自动重试，请读取设备状态确认') from error
        raise
    finally:
        client.close()
