import asyncio
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'industrial'))
from modbus_adapter import encode,decode,run,validate
from simulator import device
from pymodbus.server import ModbusTcpServer


class CodecTests(unittest.TestCase):
    def test_independently_known_register_layouts(self):
        for byte_order,word_order,expected in [('big','big',[0x1234,0x5678]),('little','big',[0x3412,0x7856]),('big','little',[0x5678,0x1234]),('little','little',[0x7856,0x3412])]:
            p={'dataType':'uint32','byteOrder':byte_order,'wordOrder':word_order}
            self.assertEqual(encode([0x12345678],p),expected)
            self.assertEqual(decode(expected,p),[0x12345678])
        self.assertEqual(encode([1.0],{'dataType':'float32'}),[0x3f80,0])
        self.assertEqual(decode([0x3ff0,0,0,0],{'dataType':'float64'}),[1.0])
        self.assertEqual(decode([0xffff,0xfffe],{'dataType':'int32'}),[-2])
        self.assertEqual(encode([-32768,32767],{'dataType':'int16'}),[0x8000,0x7fff])

    def test_reject_overflow_nan_and_invalid_ranges_before_connect(self):
        invalid=[{'area':'discrete','value':True},{'dataType':'uint16','value':65536},{'dataType':'int16','value':1.1},{'value':float('nan')},{'area':'coils','value':1},{'dataType':'uint32','address':65535,'value':1},{'transport':'rtu','deviceId':0,'serialPort':'COM1','value':1}]
        for p in invalid:
            with self.assertRaises(ValueError):run('modbus_write',p)
        for p in ({'count':126},{'count':32,'dataType':'float64'},{'address':-1},{'timeoutMs':True},{'transport':'rtu','serialPort':'socket://127.0.0.1:1'}):
            with self.assertRaises(ValueError):validate('modbus_read',p)
        with self.assertRaises(ValueError):decode([0x7f80,0],{'dataType':'float32'})

    def test_rtu_configuration_has_explicit_serial_settings(self):
        c=validate('modbus_read',{'transport':'rtu','serialPort':'COM4','deviceId':7,'baudrate':9600,'parity':'E','stopbits':2})
        self.assertEqual(c['connection'],{'port':'COM4','baudrate':9600,'bytesize':8,'parity':'E','stopbits':2})


class ProtocolTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.server=ModbusTcpServer(device(),address=('127.0.0.1',0))
        await self.server.serve_forever(background=True)
        self.port=self.server.transport.sockets[0].getsockname()[1]

    async def asyncTearDown(self):
        await self.server.shutdown()

    async def request(self,action='read',**p):
        return await asyncio.to_thread(run,'modbus_'+action,{'host':'127.0.0.1','port':self.port,'timeoutMs':300,**p})

    async def test_four_address_spaces_and_zero_based_offsets(self):
        for area,expected in [('holding',[123,456,250]),('input',[100,200,300]),('coils',[False]*3),('discrete',[True]*3)]:
            result=await self.request(area=area,count=3)
            self.assertEqual(result['result']['values'],expected)
        self.assertEqual((await self.request(address=1))['result']['value'],456)

    async def test_single_and_multiple_register_writes_match_device_memory(self):
        await self.request('write',address=20,value=789)
        self.assertEqual(await self.server.async_getValues(1,3,20,1),[789])
        await self.request('write',address=22,dataType='uint32',wordOrder='little',values=[0x12345678,0xfedcba98])
        self.assertEqual(await self.server.async_getValues(1,3,22,4),[0x5678,0x1234,0xba98,0xfedc])
        output=await self.request(address=22,dataType='uint32',wordOrder='little',count=2)
        self.assertEqual(output['result']['values'],[0x12345678,0xfedcba98])

    async def test_coils_odd_count_does_not_expose_padding_bits(self):
        await self.request('write',area='coils',address=5,value=True)
        await self.request('write',area='coils',address=8,values=[True,False,True,True,False,False,True,False,True])
        self.assertTrue((await self.request(area='coils',address=5))['result']['value'])
        self.assertEqual((await self.request(area='coils',address=8,count=9))['result']['values'],[True,False,True,True,False,False,True,False,True])

    async def test_float_layout_and_device_nonfinite_error(self):
        await self.request('write',address=30,dataType='float32',byteOrder='little',wordOrder='little',value=12.5)
        self.assertEqual(await self.server.async_getValues(1,3,30,2),[0,0x4841])
        self.assertEqual((await self.request(address=30,dataType='float32',byteOrder='little',wordOrder='little'))['result']['value'],12.5)
        rounded=await self.request('write',address=34,dataType='float32',value=12.1)
        self.assertEqual(rounded['result']['value'],12.100000381469727)
        self.assertEqual(rounded['result']['requestedValues'],[12.1])
        await self.server.async_setValues(1,3,40,[0x7f80,0])
        with self.assertRaisesRegex(ValueError,'NaN/Infinity'):
            await self.request(address=40,dataType='float32')

    async def test_device_exception_is_not_success(self):
        with self.assertRaisesRegex(ValueError,'异常码'):
            await self.request(address=1000)

    async def test_lost_write_acknowledgement_is_not_retried(self):
        received=[]
        async def silent(reader,writer):
            try:
                while data:=await reader.read(4096):received.append(data)
            finally:
                writer.close()
        server=await asyncio.start_server(silent,'127.0.0.1',0)
        try:
            with self.assertRaisesRegex(RuntimeError,'可能已到达设备'):
                await asyncio.to_thread(run,'modbus_write',{'host':'127.0.0.1','port':server.sockets[0].getsockname()[1],'timeoutMs':100,'value':1})
            self.assertEqual(len(received),1)
        finally:
            server.close();await server.wait_closed()


if __name__=='__main__':unittest.main(verbosity=2)
