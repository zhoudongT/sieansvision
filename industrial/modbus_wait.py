"""Poll one PLC value on one connection; trigger on sampled conditions, never write."""
import math
import time
from datetime import datetime, timezone
from modbus_adapter import validate, integer, AREAS, decode


def settings(params):
    config = validate('modbus_read', {**params, 'count': 1})
    comparison = params.get('comparison', 'eq')
    expected = params.get('expectedValue', 123)
    if config['bits']:
        if comparison not in ('is_true', 'is_false'):
            raise ValueError('线圈和离散输入请选择“开关为是”或“开关为否”')
    else:
        if comparison not in ('eq', 'ne', 'gt', 'gte', 'lt', 'lte'):
            raise ValueError('寄存器请选择数值比较方式')
        if isinstance(expected, bool) or not isinstance(expected, (int, float)) or not math.isfinite(expected):
            raise ValueError('比较值必须为有限数值')
    mode = params.get('triggerMode', 'level')
    policy = params.get('onTimeout', 'error')
    if mode not in ('level', 'rising', 'falling') or policy not in ('error', 'continue'):
        raise ValueError('触发方式或超时处理无效')
    timeout = integer(params, 'waitTimeoutMs', 10000, 100, 600000)
    interval = integer(params, 'pollIntervalMs', 100, 20, 10000)
    stable = integer(params, 'stableMs', 0, 0, 60000)
    if stable >= timeout:
        raise ValueError('稳定时间必须小于等待超时')
    return config, dict(comparison=comparison, expected=expected, mode=mode, policy=policy,
                        timeout=timeout, interval=interval, stable=stable)


def matches(value, comparison, expected):
    if comparison == 'is_true': return value is True
    if comparison == 'is_false': return value is False
    if comparison == 'eq': return value == expected
    if comparison == 'ne': return value != expected
    if comparison == 'gt': return value > expected
    if comparison == 'gte': return value >= expected
    if comparison == 'lt': return value < expected
    return value <= expected


class SampleTrigger:
    """Edges re-arm per invocation; debounce measures successive observed samples."""
    def __init__(self, mode, stable_ms):
        self.mode, self.stable = mode, stable_ms / 1000
        self.armed = mode == 'level'
        self.since = None

    def observe(self, predicate, now):
        desired = self.mode != 'falling'
        if predicate != desired:
            self.armed = True
            self.since = None
            return False
        if not self.armed:
            return False
        if self.since is None:
            self.since = now
        return now - self.since >= self.stable


def run(params):
    config, options = settings(params)
    from pymodbus.client import ModbusTcpClient, ModbusSerialClient
    constructor = ModbusTcpClient if config['transport'] == 'tcp' else ModbusSerialClient
    client = constructor(**config['connection'], timeout=config['timeout']/1000, retries=0)
    started = time.monotonic()
    deadline = started + options['timeout']/1000
    trigger = SampleTrigger(options['mode'], options['stable'])
    first = last = predicate = None
    samples = 0
    triggered = False
    try:
        if not client.connect():
            raise ConnectionError('无法连接 Modbus 设备，请检查端口和地址')
        while time.monotonic() < deadline:
            if not client.connected:
                raise ConnectionError('等待信号时连接已断开，请检查设备后重新启动流程')
            response = getattr(client, AREAS[config['area']])(config['address'], count=config['wireCount'], device_id=config['device'])
            if response.isError():
                raise ValueError(f'Modbus 设备异常响应，功能码 {response.function_code}，异常码 {getattr(response,"exception_code","unknown")}')
            if config['bits']:
                if not response.bits:
                    raise ValueError('设备返回的开关数量不足')
                last = bool(response.bits[0])
            else:
                if len(response.registers) != config['wireCount']:
                    raise ValueError('设备返回的寄存器数量不匹配')
                last = decode(response.registers, params)[0]
            samples += 1
            if samples == 1: first = last
            now = time.monotonic()
            predicate = matches(last, options['comparison'], options['expected'])
            # A response that arrives after the deadline must never start detection.
            if now >= deadline: break
            if trigger.observe(predicate, now):
                triggered = True
                break
            time.sleep(max(0, min(options['interval']/1000, deadline-time.monotonic())))
        elapsed = round((time.monotonic()-started)*1000, 1)
        if not triggered and options['policy'] == 'error':
            raise TimeoutError(f'等待 Modbus 信号超时（{options["timeout"]} ms，已采样 {samples} 次），未触发后续检测')
        result = dict(protocol='modbus-'+config['transport'], action='wait', area=config['area'],
                      deviceId=config['device'], address=config['address'], dataType=config['dtype'],
                      triggered=triggered, passed=triggered, reason='triggered' if triggered else 'timeout',
                      firstValue=first, value=last, predicate=predicate, samples=samples,
                      triggerMode=options['mode'], comparison=options['comparison'],
                      stableMs=options['stable'], pollIntervalMs=options['interval'], waitTimeoutMs=options['timeout'],
                      waitElapsedMs=elapsed, quality='good' if samples else 'no_sample', timestamp=datetime.now(timezone.utc).isoformat())
        if not config['bits']: result['expectedValue'] = options['expected']
        return dict(operation='modbus_wait', result=result, elapsedMs=elapsed)
    finally:
        client.close()
