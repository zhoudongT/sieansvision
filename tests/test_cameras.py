import base64
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch, MagicMock
import cv2
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'cameras'))
import adapter as a


class CameraTests(unittest.TestCase):
    def test_simulated_frame_is_real_png_with_three_shapes(self):
        out = a.run(dict(operation='camera_capture', params=dict(driver='simulator')))
        image = cv2.imdecode(np.frombuffer(base64.b64decode(out['annotatedImage'].split(',')[1]), np.uint8), cv2.IMREAD_GRAYSCALE)
        contours, _ = cv2.findContours(image, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        self.assertEqual(len(contours), 3)
        self.assertEqual(image.shape, (400, 640))
        self.assertTrue(out['result']['simulated'])
        self.assertIsNone(out['cloud'])

    def test_configuration_rejects_bad_size_types_trigger(self):
        for params in [dict(driver='none'), dict(driver='simulator', width=True), dict(driver='simulator', width=8192, height=8192),
                       dict(driver='simulator', timeoutMs=0), dict(driver='uvc', trigger='software'), dict(driver='uvc', exposureTime=100)]:
            with self.assertRaises(ValueError):
                a.config(params)

    def test_raw_formats_color_order_bits_and_copy(self):
        data = np.array([255, 0, 0, 0, 255, 0], np.uint8)
        component = NS(width=2, height=1, data_format='RGB8', data=data)
        image, info = a.pixels(component)
        self.assertEqual(image.tolist(), [[[0, 0, 255], [0, 255, 0]]])
        data[:] = 0
        self.assertEqual(int(image[0, 0, 2]), 255)
        for bits in (10, 12, 16):
            image, info = a.pixels(NS(width=2, height=1, data_format='Mono'+str(bits), data=np.array([0, (1<<bits)-1], np.uint16)))
            self.assertEqual(image.tolist(), [[0, 255]])
            self.assertEqual(info['sourceBits'], bits)
        raw = np.zeros((8,8), np.uint8);raw[::2,::2] = 255
        image, _ = a.pixels(NS(width=8, height=8, data_format='BayerRG8', data=raw.ravel()))
        self.assertEqual(image[4,4].tolist(), [0,0,255])

    def test_unknown_packed_and_inconsistent_buffers_rejected(self):
        for fmt, data in [('Mono12p', np.zeros(4, np.uint8)), ('RGB8', np.zeros(4, np.uint8)), ('Mono8', np.zeros(4, np.uint16))]:
            with self.assertRaises(ValueError):
                a.pixels(NS(width=2, height=2, data_format=fmt, data=data))

    def test_provider_allowlist_and_no_client_cti_path(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'fake.cti';path.write_bytes(b'')
            with patch.dict(os.environ, {'SIEANS_GENTL_CTI': str(path)}):
                items = a.providers();self.assertEqual(len(items), 1);self.assertTrue(items[0]['available'])
                with self.assertRaisesRegex(ValueError, '未配置'):
                    a.harvester(str(path))

    def test_uvc_selection_release_and_readback(self):
        device = dict(deviceId='stable-path', name='camera', index=4, backend=cv2.CAP_DSHOW)
        cap = MagicMock();cap.isOpened.return_value=True;cap.set.return_value=True;cap.get.return_value=640
        cap.read.return_value=(True,np.zeros((400,640,3), np.uint8))
        with patch.object(a,'uvc_devices',return_value=[device]),patch.object(a.cv2,'VideoCapture',return_value=cap) as factory:
            image, _ = a.acquire_uvc(dict(deviceId='stable-path',width=640,warmupFrames=1))
            self.assertEqual(cap.read.call_count, 2);factory.assert_called_with(4,cv2.CAP_DSHOW);cap.release.assert_called_once()
            cap.reset_mock();cap.get.return_value=320
            with self.assertRaisesRegex(ValueError,'回读'):
                a.acquire_uvc(dict(deviceId='stable-path',width=640))
            cap.release.assert_called_once()
            cap.reset_mock();cap.read.return_value=(False,None)
            with self.assertRaisesRegex(ValueError,'有效图像'):
                a.acquire_uvc(dict(deviceId='stable-path'))
            cap.release.assert_called_once()
            with self.assertRaisesRegex(ValueError,'不存在'):
                a.acquire_uvc(dict(deviceId='different-device'))

    def test_gentl_buffer_queued_and_device_destroyed_even_on_bad_frame(self):
        component=NS(width=2,height=2,data_format='Mono8',data=np.array([0,1,2,3],np.uint8))
        buffer=NS(payload=NS(components=[component]),module=NS(is_complete=lambda:True),timestamp_ns=42)
        context=MagicMock();context.__enter__.return_value=buffer
        ia=MagicMock();ia.__enter__.return_value=ia;ia.fetch.return_value=context
        h=MagicMock();h.create.return_value=ia
        with patch.object(a,'harvester',return_value=h),patch.object(a,'gentl_devices',return_value=[dict(deviceId='s1')]),patch.object(a,'set_feature'):
            p=dict(providerId='cti',deviceId='s1',trigger='software',timeoutMs=100)
            image, info=a.acquire_gentl(p)
            self.assertEqual(image.tolist(),[[0,1],[2,3]]);self.assertEqual(info['deviceTimestampNs'],'42')
            ia.remote_device.node_map.TriggerSoftware.execute.assert_called_once();context.__exit__.assert_called_once();ia.stop.assert_called_once();ia.__exit__.assert_called_once();h.reset.assert_called_once()
            ia.reset_mock();h.reset_mock();context.reset_mock();buffer.module.is_complete=lambda:False
            with self.assertRaisesRegex(ValueError,'不完整帧'):
                a.acquire_gentl(p)
            context.__exit__.assert_called_once();ia.stop.assert_called_once();h.reset.assert_called_once()
            buffer.module.is_complete=lambda:True;buffer.payload.components=[component,component]
            with self.assertRaisesRegex(ValueError,'多分量'):
                a.acquire_gentl(p)

    def test_gentl_fetch_timeout_releases_device(self):
        ia=MagicMock();ia.__enter__.return_value=ia;ia.fetch.side_effect=TimeoutError('test timeout')
        h=MagicMock();h.create.return_value=ia
        with patch.object(a,'harvester',return_value=h),patch.object(a,'gentl_devices',return_value=[dict(deviceId='s1')]),patch.object(a,'set_feature'):
            with self.assertRaises(TimeoutError):
                a.acquire_gentl(dict(deviceId='s1',trigger='freerun',timeoutMs=100))
            ia.stop.assert_called_once();ia.__exit__.assert_called_once();h.reset.assert_called_once()

    def test_genicam_settings_verify_actual_values(self):
        class Node:
            @property
            def value(self): return 12
            @value.setter
            def value(self,value): pass
        with patch('genicam.genapi.is_writable',return_value=True):
            with self.assertRaisesRegex(ValueError,'回读'):
                a.set_feature(NS(Width=Node()),'Width',640,[])


if __name__ == '__main__': unittest.main(verbosity=2)
