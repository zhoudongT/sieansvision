"""Opt-in Windows virtual pair fixture; refuses ordinary/physical ports."""
import json
import sys
import time
import serial
from serial.tools.list_ports import comports

client, peer = sys.argv[1:3]
ports = {p.device.upper(): p.description for p in comports()}
for device, other in [(client, peer), (peer, client)]:
    description = ports.get(device.upper(), '')
    if 'ELTIMA Virtual Serial Port' not in description or f'{device.upper()}->{other.upper()}' not in description.upper():
        raise RuntimeError('仅允许明确配对的 ELTIMA 虚拟串口；当前设备描述不匹配')
with serial.Serial(peer, baudrate=115200, timeout=.05, write_timeout=1) as port:
    print('READY', flush=True)
    buffer = bytearray()
    while True:
        buffer.extend(port.read(max(1, min(port.in_waiting, 4096))))
        if b'\r\n' not in buffer:
            continue
        request, _, rest = buffer.partition(b'\r\n')
        buffer = bytearray(rest)
        if request == b'SCAN':
            reply = 'SIEANS 虚拟串口 42\r\n'.encode()
        elif request == b'MEASURE':
            reply = json.dumps(dict(count=3, width=12.5, passed=True)).encode()+b'\r\n'
        elif request == b'BINARY':
            reply = b'\x03\x00\x00\x00\x00\x80\xff'
        else:
            print('RECEIVED '+request.decode('ascii', errors='replace'), flush=True)
            continue
        port.write(reply[:1]);time.sleep(.01);port.write(reply[1:4]);time.sleep(.01);port.write(reply[4:])
