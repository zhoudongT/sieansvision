import sys
import unittest
import struct
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'industrial'))
from s7_adapter import run, validate, decode
from s7_test_server import S7TestServer as Server
from snap7.type import SrvArea


class S7Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=Server()
        cls.db=bytearray(4096)
        cls.server.register_area(SrvArea.DB,1,cls.db)
        for area in (SrvArea.MK,SrvArea.PE,SrvArea.PA): cls.server.register_area(area,0,bytearray(256))
        cls.server.start_to('127.0.0.1',0)
        cls.port=cls.server.server_socket.getsockname()[1]

    @classmethod
    def tearDownClass(cls): cls.server.stop()

    def io(self,op,**p):
        return run('s7_'+op,dict(host='127.0.0.1',port=self.port,**p))['result']

    def test_numeric_types_and_arrays(self):
        for dtype,values in [('uint8',[0,255]),('int8',[-128,127]),('uint16',[0,65535]),('int16',[-32768,32767]),('uint32',[0,4294967295]),('int32',[-2147483648,2147483647]),('float32',[12.5,-3.25]),('float64',[1.25,-1234.5])]:
            with self.subTest(dtype=dtype):
                self.io('write',dataType=dtype,byteOffset=32,value=values)
                result=self.io('read',dataType=dtype,byteOffset=32,count=2)
                self.assertEqual(result['values'],values)
                self.assertEqual(result['items'][0]['byteOffset'],32)
        self.assertEqual(self.db[32:48],struct.pack('>dd',1.25,-1234.5))

    def test_bit_write_preserves_neighbors(self):
        for bit in range(8):
            self.io('write',dataType='uint8',byteOffset=100,value=170)
            self.io('write',dataType='bool',byteOffset=100,bitOffset=bit,value=True)
            self.assertEqual(self.io('read',dataType='uint8',byteOffset=100)['value'],170|(1<<bit))
            self.assertTrue(self.io('read',dataType='bool',byteOffset=100,bitOffset=bit)['value'])
            self.io('write',dataType='bool',byteOffset=100,bitOffset=bit,value=False)
            self.assertEqual(self.io('read',dataType='uint8',byteOffset=100)['value'],170&~(1<<bit))

    def test_areas_and_server_errors(self):
        for area in ('mk','pa'):
            self.io('write',area=area,byteOffset=8,value=321)
            self.assertEqual(self.io('read',area=area,byteOffset=8)['value'],321)
        self.assertEqual(self.io('read',area='pe')['value'],0)
        for p in [dict(dbNumber=99),dict(byteOffset=4095)]:
            with self.assertRaises(Exception): self.io('read',**p)
        with self.assertRaisesRegex(RuntimeError,'未自动重试'): self.io('write',dbNumber=99,value=3)

    def test_bounds_and_types_rejected_before_connection(self):
        for op,p in [('write',{'area':'pe','value':1}),('write',{'dataType':'uint16','value':65536}),('write',{'dataType':'bool','value':1}),('read',{'dataType':'bool','count':2}),('read',{'dataType':'float64','count':26}),('read',{'bitOffset':8,'dataType':'bool'}),('read',{'rack':8}),('read',{'slot':32}),('read',{'byteOffset':2097151}),('write',{'value':True}),('write',{'value':1.5}),('write',{'dataType':'float32','value':float('inf')})]:
            with self.subTest(params=p),self.assertRaises(ValueError): validate('s7_'+op,p)
        with self.assertRaises(ValueError): decode(struct.pack('>f',float('nan')),'float32',1)
        with self.assertRaises(ValueError): decode(b'\x01','uint16',1)

    def test_maximum_payload_single_request(self):
        values=list(range(100))
        self.io('write',byteOffset=200,value=values)
        self.assertEqual(self.io('read',byteOffset=200,count=100)['values'],values)


if __name__=='__main__': unittest.main()
