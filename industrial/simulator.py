"""Local-only development device. Explicitly separate from real PLC endpoints."""
import asyncio
import json
import sys
from pymodbus.server import ModbusTcpServer
from pymodbus.simulator import SimData, SimDevice, DataType


def device():
    return SimDevice(id=1,simdata=(
        [SimData(0,count=256,values=False,datatype=DataType.BITS)],
        [SimData(0,count=256,values=True,datatype=DataType.BITS)],
        [SimData(0,values=[123,456,250]+[0]*253,datatype=DataType.REGISTERS)],
        [SimData(0,values=[100,200,300]+[0]*253,datatype=DataType.REGISTERS)]
    ))


async def main():
    server=ModbusTcpServer(device(),address=('127.0.0.1',0))
    await server.serve_forever(background=True)
    port=server.transport.sockets[0].getsockname()[1]
    print(json.dumps({'ready':True,'host':'127.0.0.1','port':port,'deviceId':1}),flush=True)
    try:
        await asyncio.to_thread(sys.stdin.read)
    finally:
        await server.shutdown()


if __name__=='__main__':
    asyncio.run(main())
