import asyncio
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'industrial'))
from modbus_wait import run, settings, SampleTrigger
from modbus_adapter import encode
from simulator import device
from pymodbus.server import ModbusTcpServer


class ConditionTests(unittest.TestCase):
    def test_edges_require_observed_baseline_and_stability_restarts_after_bounce(self):
        for mode, before, after in [('rising', False, True), ('falling', True, False)]:
            trigger = SampleTrigger(mode, 100)
            self.assertFalse(trigger.observe(after, 0))  # first sample is already high/low
            self.assertFalse(trigger.observe(after, 1))
            self.assertFalse(trigger.observe(before, 2))
            self.assertFalse(trigger.observe(after, 3))
            self.assertFalse(trigger.observe(before, 3.05))
            self.assertFalse(trigger.observe(after, 4))
            self.assertFalse(trigger.observe(after, 4.09))
            self.assertTrue(trigger.observe(after, 4.11))
        self.assertTrue(SampleTrigger('level', 0).observe(True, 0))

    def test_configuration_rejected_before_connect(self):
        bad = [{'waitTimeoutMs':True}, {'waitTimeoutMs':600001}, {'pollIntervalMs':19},
               {'stableMs':100, 'waitTimeoutMs':100}, {'triggerMode':'change'}, {'onTimeout':'ignore'},
               {'area':'coils','comparison':'eq'}, {'comparison':'is_true'}, {'expectedValue':float('nan')},
               {'expectedValue':True}, {'expectedValue':{}}, {'address':65535,'dataType':'float64'}]
        for p in bad:
            with self.subTest(p=p), self.assertRaises(ValueError): settings(p)
        self.assertEqual(settings({'area':'discrete','comparison':'is_true','expectedValue':{}})[0]['wireCount'],1)


class ProtocolTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.server = ModbusTcpServer(device(), address=('127.0.0.1',0))
        await self.server.serve_forever(background=True)
        self.params = dict(host='127.0.0.1', port=self.server.transport.sockets[0].getsockname()[1],
                           timeoutMs=100, pollIntervalMs=20, waitTimeoutMs=1000)

    async def asyncTearDown(self):
        await self.server.shutdown()

    async def request(self, **p):
        return await asyncio.to_thread(run, {**self.params, **p})

    async def test_level_stable_on_one_real_tcp_connection(self):
        from pymodbus.client import ModbusTcpClient
        clients=[]
        def create(**kwargs):
            self.assertEqual(kwargs['retries'],0)
            client=ModbusTcpClient(**kwargs);clients.append(client);return client
        with patch('pymodbus.client.ModbusTcpClient',side_effect=create):
            result=(await self.request(expectedValue=123,stableMs=80))['result']
        self.assertTrue(result['triggered']);self.assertGreaterEqual(result['samples'],3)
        self.assertGreaterEqual(result['waitElapsedMs'],80);self.assertEqual(len(clients),1)
        self.assertFalse(clients[0].connected)

    async def test_rising_waits_for_a_new_transition_even_if_initially_true(self):
        async def change():
            await asyncio.sleep(.15);await self.server.async_setValues(1,3,0,[0])
            await asyncio.sleep(.15);await self.server.async_setValues(1,3,0,[123])
        task=asyncio.create_task(change())
        try: result=(await self.request(expectedValue=123,triggerMode='rising'))['result']
        finally: await task
        self.assertTrue(result['triggered']);self.assertEqual(result['firstValue'],123)
        self.assertEqual(result['value'],123);self.assertGreaterEqual(result['waitElapsedMs'],280)

    async def test_falling_coil_and_readonly_discrete_input(self):
        await self.server.async_setValues(1,1,0,[True])
        async def change():
            await asyncio.sleep(.12);await self.server.async_setValues(1,1,0,[False])
        task=asyncio.create_task(change())
        try: result=(await self.request(area='coils',comparison='is_true',triggerMode='falling'))['result']
        finally: await task
        self.assertTrue(result['triggered']);self.assertIs(result['value'],False)
        self.assertIs(result['predicate'],False)
        self.assertTrue((await self.request(area='discrete',comparison='is_true'))['result']['triggered'])

    async def test_float_endian_comparison_and_input_register(self):
        p=dict(dataType='float32',byteOrder='little',wordOrder='little')
        await self.server.async_setValues(1,3,20,encode([-3.25],p))
        result=(await self.request(address=20,comparison='lt',expectedValue=0,**p))['result']
        self.assertTrue(result['triggered']);self.assertEqual(result['value'],-3.25)
        self.assertTrue((await self.request(area='input',expectedValue=100))['result']['triggered'])

    async def test_timeout_policy_and_first_sample_does_not_trigger_edge(self):
        result=(await self.request(waitTimeoutMs=100,triggerMode='rising',onTimeout='continue'))['result']
        self.assertFalse(result['triggered']);self.assertFalse(result['passed']);self.assertEqual(result['reason'],'timeout')
        with self.assertRaisesRegex(TimeoutError,'未触发后续检测'):
            await self.request(waitTimeoutMs=100,expectedValue=-1)

    async def test_device_exception_and_nonfinite_are_errors_even_with_continue_policy(self):
        with self.assertRaisesRegex(ValueError,'异常响应'):
            await self.request(address=1000,onTimeout='continue')
        await self.server.async_setValues(1,3,40,[0x7f80,0])
        with self.assertRaisesRegex(ValueError,'NaN/Infinity'):
            await self.request(address=40,dataType='float32',onTimeout='continue')

    async def test_late_matching_response_is_not_a_trigger(self):
        # Delay the transport itself: the PLC replies correctly, but past waitTimeoutMs.
        import struct
        async def slow(reader,writer):
            try:
                request=await reader.readexactly(12)
                await asyncio.sleep(.16)
                writer.write(request[:2]+b'\x00\x00\x00\x05'+request[6:7]+b'\x03\x02'+struct.pack('>H',123))
                await writer.drain()
            finally: writer.close();await writer.wait_closed()
        server=await asyncio.start_server(slow,'127.0.0.1',0)
        try:
            result=(await self.request(port=server.sockets[0].getsockname()[1],timeoutMs=500,waitTimeoutMs=100,onTimeout='continue'))['result']
            self.assertEqual(result['value'],123);self.assertFalse(result['triggered'])
        finally: server.close();await server.wait_closed()


if __name__=='__main__':unittest.main(verbosity=2)
