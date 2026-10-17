"""Fixed adapter entry point; never interprets request data as Python source."""
import contextlib
import json
import sys
from modbus_adapter import run

try:
    request=json.load(sys.stdin)
    with contextlib.redirect_stdout(sys.stderr):
        if request.get('operation')=='serial_ports':
            from serial.tools.list_ports import comports
            data={'ports':[{'device':p.device,'description':p.description,'hwid':p.hwid} for p in comports()]}
        elif request.get('operation')=='modbus_wait':
            from modbus_wait import run as wait_run
            data=wait_run(request.get('params',{}))
        elif request.get('operation')=='serial_exchange':
            from serial_adapter import run as serial_run
            data=serial_run(request.get('params',{}))
        elif request.get('operation','').startswith('s7_'):
            from s7_adapter import run as s7_run
            data=s7_run(request['operation'],request.get('params',{}))
        elif request.get('operation','').startswith('opcua_'):
            from opcua_adapter import run as opcua_run
            data=opcua_run(request['operation'],request.get('params',{}))
        else:
            data=run(request.get('operation'),request.get('params',{}))
    response={'ok':True,'data':data}
except Exception as error:
    response={'ok':False,'error':str(error)}
print(json.dumps(response,ensure_ascii=True,allow_nan=False),flush=True)
