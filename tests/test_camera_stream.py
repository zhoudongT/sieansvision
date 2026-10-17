import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import MagicMock, patch
import cv2
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'cameras'))
import adapter as a
import depth_adapter as depth
import orbbec_adapter as orbbec


class StreamTests(unittest.TestCase):
    def test_uvc_opens_and_warms_once_then_reads_many_and_releases_once(self):
        device=dict(deviceId='uvc',index=1,backend=cv2.CAP_DSHOW)
        cap=MagicMock();cap.isOpened.return_value=True;cap.read.return_value=(True,np.zeros((16,16,3),np.uint8))
        with patch.object(a,'uvc_devices',return_value=[device]),patch.object(a.cv2,'VideoCapture',return_value=cap) as factory:
            stream=a.capture_frames(dict(driver='uvc',deviceId='uvc',warmupFrames=2))
            for _ in range(4):self.assertEqual(next(stream)['result']['width'],16)
            factory.assert_called_once();self.assertEqual(cap.read.call_count,6);cap.release.assert_not_called()
            stream.close();cap.release.assert_called_once()

    def test_gentl_connection_and_buffer_lifetimes_are_distinct(self):
        component=NS(width=2,height=2,data_format='Mono8',data=np.arange(4,dtype=np.uint8))
        buffer=NS(payload=NS(components=[component]),module=NS(is_complete=lambda:True),timestamp_ns=123)
        fetched=MagicMock();fetched.__enter__.return_value=buffer
        ia=MagicMock();ia.__enter__.return_value=ia;ia.fetch.return_value=fetched
        h=MagicMock();h.create.return_value=ia
        with patch.object(a,'harvester',return_value=h),patch.object(a,'gentl_devices',return_value=[dict(deviceId='g')]),patch.object(a,'set_feature'):
            stream=a.capture_frames(dict(driver='gentl',deviceId='g',trigger='freerun'))
            for _ in range(3):self.assertEqual(next(stream)['result']['deviceTimestampNs'],'123')
            self.assertEqual(fetched.__exit__.call_count,3);ia.start.assert_called_once();ia.stop.assert_not_called();h.reset.assert_not_called()
            ia.fetch.side_effect=TimeoutError('disconnected')
            with self.assertRaises(TimeoutError):next(stream)
            ia.stop.assert_called_once();h.reset.assert_called_once();ia.__exit__.assert_called_once()

    def test_gentl_3d_many_frames_preserve_cloud_and_close_resources(self):
        import contextlib
        import io
        with contextlib.redirect_stdout(io.StringIO()):
            from gentl3d_fixture import fixture,params
        components,calibration=fixture();buffer=NS(payload=NS(components=components),module=NS(is_complete=lambda:True),timestamp_ns=456)
        fetched=MagicMock();fetched.__enter__.return_value=buffer
        ia=MagicMock();ia.__enter__.return_value=ia;ia.fetch.return_value=fetched
        h=MagicMock();h.create.return_value=ia
        with patch.object(a,'harvester',return_value=h),patch.object(a,'gentl_devices',return_value=[dict(deviceId='fixture-camera')]),patch.object(a,'set_feature'),patch.object(a.gentl3d,'configure',return_value=calibration):
            stream=a.capture_frames(params())
            first=next(stream);second=next(stream)
            self.assertEqual(first['cloud']['unit'],'mm');self.assertEqual(first['cloud']['points'],second['cloud']['points'])
            ia.start.assert_called_once();ia.stop.assert_not_called();stream.close();ia.stop.assert_called_once()

    def test_realsense_pipeline_kept_open_across_frames(self):
        sdk=MagicMock();device=MagicMock();device.get_info.return_value='serial';sdk.context.return_value.query_devices.return_value=[device]
        pipe=sdk.pipeline.return_value;frames=pipe.wait_for_frames.return_value;df=frames.get_depth_frame.return_value
        profile=df.profile.as_video_stream_profile.return_value
        profile.width.return_value=4;profile.height.return_value=3;profile.fps.return_value=30;profile.format.return_value=sdk.format.z16
        df.get_data.return_value=np.ones((3,4),np.uint16);df.get_units.return_value=.001
        sdk.pointcloud.return_value.calculate.return_value.get_vertices.return_value=np.ones((12,3),np.float32)
        packed=({}, {'points':[[0,0,1]],'unit':'mm'}, {}, np.zeros((3,4,3),np.uint8))
        with patch.object(depth,'intrinsics',return_value={}),patch.object(depth,'pack',return_value=packed):
            stream=depth.acquire_frames(dict(deviceId='serial',timeoutMs=1000,warmupFrames=1,enableColor=False,width=4,height=3,fps=30),rs=sdk)
            for _ in range(3):next(stream)
            self.assertEqual(pipe.wait_for_frames.call_count,4);pipe.start.assert_called_once();pipe.stop.assert_not_called()
            stream.close();pipe.stop.assert_called_once()

    def test_orbbec_pipeline_kept_open_and_stopped_after_missing_frame_timeout(self):
        sdk=MagicMock();device=MagicMock();pipe=sdk.Pipeline.return_value;items=sdk.Context.return_value.query_devices.return_value
        items.get_device_by_serial_number.return_value=device
        packed=(np.zeros((16,16,3),np.uint8),{},dict(timestamp='time'),{'points':[[0,0,1]],'unit':'mm'})
        with patch.object(orbbec,'context',return_value=sdk.Context.return_value),patch.object(orbbec,'device_rows',return_value=[dict(deviceId='serial')]),patch.object(orbbec,'check_profile'),patch.object(orbbec,'process_frames',return_value=packed):
            stream=orbbec.acquire_frames(dict(deviceId='serial',timeoutMs=100,enableColor=False,warmupFrames=0),ob=sdk)
            for _ in range(3):next(stream)
            pipe.start.assert_called_once();pipe.stop.assert_not_called();self.assertEqual(pipe.wait_for_frames.call_count,3)
            pipe.wait_for_frames.return_value=None
            with self.assertRaises(TimeoutError):next(stream)
            pipe.stop.assert_called_once()


if __name__=='__main__':unittest.main()
