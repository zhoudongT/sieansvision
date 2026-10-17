"""Local S7 protocol server. Memory is volatile and resets on restart."""
import json
import struct
import sys
from s7_test_server import S7TestServer as Server
from snap7.type import SrvArea

server=Server()
db=bytearray(4096)
db[0:2]=struct.pack('>H',123)
db[4:8]=struct.pack('>f',12.5)
server.register_area(SrvArea.DB,1,db)
for area in (SrvArea.MK,SrvArea.PE,SrvArea.PA):
    server.register_area(area,0,bytearray(256))
try:
    server.start_to('127.0.0.1',0)
    # Version-pinned simulator introspection obtains the OS-assigned ephemeral port.
    port=server.server_socket.getsockname()[1]
    print(json.dumps(dict(ready=True,host='127.0.0.1',port=port)),flush=True)
    sys.stdin.buffer.read()
finally:
    server.stop()
