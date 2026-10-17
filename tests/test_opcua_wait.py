import asyncio
import logging
from pathlib import Path
import sys
import time
from types import SimpleNamespace
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'industrial'))
from asyncua import ua
from opcua_adapter import run_async
from opcua_simulator import create_server
from opcua_wait import Handler,condition,validate,wait_for_value

logging.getLogger('asyncua').setLevel(logging.CRITICAL)


class ConfigTests(unittest.TestCase):
    def test_strict_wait_configuration_and_scalar_quality(self):
        for p in [dict(waitTimeoutMs=True),dict(publishingIntervalMs=0),dict(triggerMode='other'),dict(comparison='contains'),dict(expectedValue=float('nan')),dict(expectedValue=True),dict(onTimeout='ignore')]:
            with self.assertRaises(ValueError):validate(p)
        for value,kind,p in [(True,ua.VariantType.Boolean,{}),('1',ua.VariantType.String,{}),([1],ua.VariantType.Int32,{}),(2**63,ua.VariantType.UInt64,{}),(1,ua.VariantType.Int32,dict(comparison='is_true'))]:
            with self.assertRaises(ValueError):condition(ua.DataValue(ua.Variant(value,kind)),p)
        for code in [ua.StatusCodes.BadSensorFailure,ua.StatusCodes.Uncertain,0x480]:
            with self.assertRaisesRegex(ValueError,'质量|溢出'):condition(ua.DataValue(ua.Variant(1,ua.VariantType.Int32),StatusCode=ua.StatusCode(code)),{})


class ProtocolTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.server,self.ns,self.nodes=await create_server()
        await self.server.start()
        self.endpoint=f'opc.tcp://127.0.0.1:{self.server.bserver.port}/sieans/'
        self.server.set_endpoint(self.endpoint)
        for endpoint in self.server.iserver.endpoints:endpoint.EndpointUrl=self.endpoint

    async def asyncTearDown(self):await self.server.stop()

    async def call(self,node='Count',**params):
        return (await run_async('opcua_wait',dict(endpoint=self.endpoint,nodeId=f'ns={self.ns};s=SIEANS.{node}',timeoutMs=2000,waitTimeoutMs=3000,publishingIntervalMs=20,**params)))['result']

    async def subscribed(self):
        for _ in range(300):
            subscriptions=self.server.iserver.subscription_service.subscriptions
            if any(s.monitored_item_srv._monitored_items for s in subscriptions.values()):return
            await asyncio.sleep(.01)
        raise AssertionError('no actual monitored item created')

    async def test_level_initial_value_and_namespace_mapping(self):
        result=await run_async('opcua_wait',dict(endpoint=self.endpoint,nodeId='ns=99;s=SIEANS.Count',namespaceUri='urn:sieans:simulator',comparison='eq',expectedValue=0,publishingIntervalMs=20,timeoutMs=2000,waitTimeoutMs=3000))
        self.assertTrue(result['result']['triggered'])
        self.assertEqual(result['result']['firstValue'],0)
        self.assertEqual(result['result']['notificationCount'],1)

    async def test_real_subscription_rising_and_falling(self):
        for mode,baseline,changed in [('rising',0,5),('falling',5,0)]:
            await self.nodes['Count'].write_value(ua.Variant(baseline,ua.VariantType.UInt32))
            task=asyncio.create_task(self.call(comparison='gt',expectedValue=2,triggerMode=mode))
            await self.subscribed()
            await asyncio.sleep(.12)
            await self.nodes['Count'].write_value(ua.Variant(changed,ua.VariantType.UInt32))
            r=await task
            self.assertTrue(r['triggered'])
            self.assertEqual(r['firstValue'],baseline)
            self.assertGreaterEqual(r['notificationCount'],2)
            await asyncio.sleep(.05)
            self.assertFalse(self.server.iserver.subscription_service.subscriptions)

    async def test_initial_target_is_not_a_new_edge_and_timeout_modes(self):
        r=await run_async('opcua_wait',dict(endpoint=self.endpoint,nodeId=f'ns={self.ns};s=SIEANS.Count',comparison='eq',expectedValue=0,triggerMode='rising',onTimeout='continue',publishingIntervalMs=20,timeoutMs=1000,waitTimeoutMs=500))
        self.assertFalse(r['result']['triggered'])
        self.assertTrue(r['result']['timedOut'])
        with self.assertRaisesRegex(ValueError,'等待 OPC UA 信号超时'):
            await run_async('opcua_wait',dict(endpoint=self.endpoint,nodeId=f'ns={self.ns};s=SIEANS.Count',comparison='gt',expectedValue=2,publishingIntervalMs=20,timeoutMs=1000,waitTimeoutMs=500))

    async def test_boolean_and_bad_quality_do_not_trigger(self):
        r=await self.call('Passed',comparison='is_false')
        self.assertTrue(r['triggered'])
        await self.nodes['Height'].write_value(ua.DataValue(ua.Variant(12.5,ua.VariantType.Double),StatusCode=ua.StatusCode(ua.StatusCodes.BadSensorFailure)))
        with self.assertRaisesRegex(ValueError,'数据质量不合格'):await self.call('Height',comparison='gt',expectedValue=10,onTimeout='continue')
        with self.assertRaisesRegex(ValueError,'标量|安全数值'):await self.call('Samples')

    async def test_cancellation_deletes_session_subscription(self):
        task=asyncio.create_task(self.call(expectedValue=99))
        await self.subscribed()
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):await task
        await asyncio.sleep(.05)
        self.assertFalse(self.server.iserver.subscription_service.subscriptions)

    async def test_connection_error_is_not_timeout_continue(self):
        with self.assertRaisesRegex(ValueError,'BadNodeIdUnknown'):
            await self.call('Missing',onTimeout='continue')


class HandlerTests(unittest.IsolatedAsyncioTestCase):
    async def test_bounded_queue_and_subscription_status_failure(self):
        handler=Handler()
        for i in range(101):handler.offer((time.monotonic(),i))
        self.assertEqual(handler.queue.qsize(),100)
        self.assertIn('溢出',str(handler.fault))
        handler=Handler()
        handler.status_change_notification(SimpleNamespace(Status=ua.StatusCode(ua.StatusCodes.BadTimeout)))
        self.assertIsNotNone(handler.fault)
        self.assertIsNone(await handler.queue.get())

    async def test_no_initial_data_and_late_notification_never_continue_or_trigger(self):
        class Subscription:
            async def subscribe_data_change(self,*args,**kwargs):pass
            async def delete(self):pass
        class Client:
            async def create_subscription(self,period,handler):return Subscription()
            async def check_connection(self):pass
        with self.assertRaisesRegex(ValueError,'未收到有效初始数据'):
            await wait_for_value(Client(),None,dict(onTimeout='continue'),time.monotonic()+.03)

    async def test_late_confirmation_value_does_not_become_a_trigger(self):
        class Subscription:
            async def subscribe_data_change(self,*args,**kwargs):pass
            async def delete(self):pass
        class Client:
            async def create_subscription(self,period,handler):
                handler.offer((time.monotonic(),ua.DataValue(ua.Variant(0,ua.VariantType.UInt32))))
                return Subscription()
            async def check_connection(self):pass
        class Node:
            async def read_data_value(self,**kwargs):return ua.DataValue(ua.Variant(99,ua.VariantType.UInt32))
        result=await wait_for_value(Client(),Node(),dict(expectedValue=99,onTimeout='continue'),time.monotonic()+.03)
        self.assertFalse(result['triggered'])
        self.assertTrue(result['timedOut'])
        self.assertEqual(result['value'],0)


if __name__=='__main__':unittest.main()
