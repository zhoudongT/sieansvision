"""One bounded pySerial transaction. Public values are validated/encoded by Node."""
import base64
import os
import time
from datetime import datetime, timezone
import serial

DELIMITERS = {'lf': b'\n', 'crlf': b'\r\n', 'nul': b'\0'}
PREFIXES = {'length16be': (2, 'big'), 'length16le': (2, 'little'),
            'length32be': (4, 'big'), 'length32le': (4, 'little')}


def complete_frame(buffer, framing, maximum, expected=None):
    """Return payload/trailing count only after the complete bounded frame arrives."""
    if framing in DELIMITERS:
        end = buffer.find(DELIMITERS[framing])
        if end >= 0:
            if end > maximum:
                raise ValueError('接收数据超过字节上限')
            return bytes(buffer[:end]), len(buffer) - end - len(DELIMITERS[framing])
        if len(buffer) > maximum + len(DELIMITERS[framing]) - 1:
            raise ValueError('接收数据超过字节上限')
        return None
    if framing in PREFIXES:
        size, endian = PREFIXES[framing]
        if len(buffer) < size:
            return None
        length = int.from_bytes(buffer[:size], endian)
        if length > maximum:
            raise ValueError('长度前缀超过接收字节上限')
        if len(buffer) >= size + length:
            return bytes(buffer[size:size+length]), len(buffer) - size - length
        return None
    if framing == 'fixed' and type(expected) is int and 1 <= expected <= maximum:
        if len(buffer) >= expected:
            return bytes(buffer[:expected]), len(buffer) - expected
        return None
    raise ValueError('串口接收分帧方式无效')


def run(params, factory=None):
    started = time.monotonic()
    timeout = params.get('timeoutMs', 3000)
    if type(timeout) is not int or not 100 <= timeout <= 10000:
        raise ValueError('串口超时必须为 100–10000 ms')
    deadline = started + timeout / 1000
    maximum = params.get('maxBytes', 65536)
    if type(maximum) is not int or not 1 <= maximum <= 65536:
        raise ValueError('接收字节上限无效')
    mode = params.get('mode', 'exchange')
    if mode not in ('exchange', 'send', 'receive'):
        raise ValueError('串口通信方式无效')
    sending, receiving = mode != 'receive', mode != 'send'
    simulated = params.get('simulated') is True
    if simulated and mode == 'receive':
        raise ValueError('回环模拟需要先发送')
    port_name = 'loop://' if simulated else params.get('serialPort', '')
    if not isinstance(port_name, str) or not port_name or (not simulated and '://' in port_name):
        raise ValueError('串口路径无效')
    wire = base64.b64decode(params['wireBase64'], validate=True) if sending else b''
    if len(wire) > 65540 or (simulated and len(wire) > 4096):
        raise ValueError('发送报文超过上限')
    framing = params.get('rxFraming', 'crlf')
    expected = params.get('responseBytes')
    if receiving:
        complete_frame(bytearray(), framing, maximum, expected)
    port, sent = None, False

    def remaining():
        value = deadline - time.monotonic()
        if value <= 0:
            raise TimeoutError('串口操作超时，未完成完整报文收发')
        return value

    try:
        options = dict(baudrate=params.get('baudrate', 115200), bytesize=params.get('dataBits', 8),
                       parity=params.get('parity', 'N'), stopbits=params.get('stopbits', 1),
                       timeout=min(.05, remaining()), write_timeout=remaining(),
                       xonxoff=params.get('flowControl') == 'xonxoff',
                       rtscts=params.get('flowControl') == 'rtscts',
                       dsrdtr=params.get('flowControl') == 'dsrdtr')
        if not simulated and os.name == 'posix':
            options['exclusive'] = True
        # Configure DTR/RTS before opening. Some drivers can still pulse them on open.
        if factory is not None:
            port = factory(port_name, **options)
        elif simulated:
            port = serial.serial_for_url('loop://', do_not_open=True, **options)
        else:
            port = serial.Serial(port=None, **options)
            port.port = port_name
        port.rts, port.dtr = params.get('rts', True), params.get('dtr', True)
        if not port.is_open:
            port.open()
        remaining()
        discarded = 0
        if sending and params.get('clearInput', False):
            discarded = port.in_waiting
            port.reset_input_buffer()
        sent_bytes = 0
        if sending:
            while sent_bytes < len(wire):
                port.write_timeout = remaining()
                sent = True
                count = port.write(wire[sent_bytes:])
                if count is None or count <= 0:
                    raise IOError('串口写入未取得进展')
                sent_bytes += count
            # flush() may block without respecting write_timeout. Poll the driver queue
            # under the deadline instead. loop:// uses its receive queue as out_waiting.
            if not simulated:
                while port.out_waiting:
                    time.sleep(min(.005, remaining()))
        remaining()
        payload, trailing = b'', 0
        if receiving:
            buffer = bytearray()
            while True:
                port.timeout = min(.05, remaining())
                chunk = port.read(min(max(port.in_waiting, 1), 4096))
                remaining()
                buffer.extend(chunk)
                frame = complete_frame(buffer, framing, maximum, expected)
                if frame is not None:
                    payload, trailing = frame
                    break
        result = dict(protocol='Serial', mode=mode, serialPort='回环模拟' if simulated else port_name,
                      simulated=simulated, baudrate=options['baudrate'], dataBits=options['bytesize'],
                      parity=options['parity'], stopbits=options['stopbits'], flowControl=params.get('flowControl', 'none'),
                      delivery='received' if receiving else 'sent', acknowledged=False,
                      payloadBase64=base64.b64encode(payload).decode('ascii'), sentBytes=sent_bytes,
                      trailingBytes=trailing, discardedInputBytes=discarded,
                      timestamp=datetime.now(timezone.utc).isoformat())
        return dict(result=result, elapsedMs=round((time.monotonic()-started)*1000, 3))
    except Exception as error:
        caution = '；数据可能已经发出，不能回滚，未自动重试' if sent else ''
        raise RuntimeError(str(error) + caution) from error
    finally:
        if port is not None:
            port.close()
