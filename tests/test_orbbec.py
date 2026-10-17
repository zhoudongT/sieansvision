"""Native SDK software frames + isolated lifecycle mocks; no hardware claim."""
import base64
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
import cv2
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'cameras'))
import adapter as camera
import orbbec_adapter as adapter
ob=adapter.sdk()

def decode(uri):
    return cv2.imdecode(np.frombuffer(base64.b64decode(uri.split(',')[1]),np.uint8),cv2.IMREAD_UNCHANGED)

def video(kind,fmt,w,h,fx,cx,data):
    frame=ob.Frame.create_video_frame(kind,fmt,w,h)
    profile=frame.get_stream_profile().as_video_stream_profile()
    intr=ob.OBCameraIntrinsic();intr.width=w;intr.height=h;intr.fx=fx;intr.fy=fx;intr.cx=cx;intr.cy=(h-1)/2
    profile.set_intrinsic(intr)
    dist=ob.OBCameraDistortion();dist.model=ob.OBCameraDistortionModel.NONE;profile.set_distortion(dist)
    if data is not None:frame.update_data(data.ravel().view(np.uint8))
    return frame,profile

def software_frames(fmt='RGB'):
    raw=np.full((12,16),2000,np.uint16);raw[0,0]=0;raw[-1,-1]=4000
    df,dp=video(ob.OBFrameType.DEPTH_FRAME,ob.OBFormat.Y16,16,12,10,7.5,raw)
    df=df.as_depth_frame();df.set_value_scale(.5)
    rgb=np.zeros((24,32,3),np.uint8);rgb[:,:,0]=np.arange(32)*7;rgb[:,:,1]=80;rgb[:,:,2]=160
    data=rgb if fmt=='RGB' else rgb[:,:,::-1].copy()
    if fmt in ('YUYV','UYVY'):data=np.full((24,32,2),128,np.uint8)
    if fmt in ('NV12','NV21'):data=np.full((36,32),128,np.uint8)
    if fmt=='MJPG':data=cv2.imencode('.jpg',rgb[:,:,::-1])[1]
    # Compressed frames have variable buffers, so retain a native color profile.
    if fmt=='MJPG':
        dummy,cp=video(ob.OBFrameType.COLOR_FRAME,ob.OBFormat.MJPG,32,24,20,15,None)
        cf=ob.Frame.create_frame(ob.OBFrameType.COLOR_FRAME,ob.OBFormat.MJPG,data.size)
        cf.set_stream_profile(cp);cf.update_data(data)
    else:cf,cp=video(ob.OBFrameType.COLOR_FRAME,getattr(ob.OBFormat,fmt),32,24,20,15,data)
    extr=ob.OBExtrinsic();extr.rot=np.eye(3,dtype=np.float32);extr.transform=np.array([100.,0.,0.],np.float32)
    dp.bind_extrinsic_to(cp,extr)
    frames=ob.Frame.create_frame_set();frames.push_frame(df);frames.push_frame(cf)
    return frames,raw

class NativeFrames(unittest.TestCase):
    def test_depth_scale_preserves_raw_and_metric_points(self):
        frames,raw=software_frames()
        _,stats,d,cloud=adapter.process_frames(frames,dict(deviceId='software-test',pointStride=1,enableColor=False),ob)
        np.testing.assert_array_equal(decode(d['image']),raw)
        self.assertEqual(d['scaleMeters'],.0005);self.assertEqual(stats['pointPositionScaleMeters'],.0005)
        self.assertEqual(len(cloud['points']),191);self.assertEqual(cloud['unit'],'mm')
        np.testing.assert_allclose(cloud['points'][-1],[1500,1100,2000],atol=.001)
        np.testing.assert_allclose(cloud['points'][86],[-50,-50,1000],atol=.001)
        self.assertNotIn('colors',cloud)

    def test_color_alignment_uses_calibration_not_resize(self):
        for fmt in adapter.COLOR_FORMATS:
            with self.subTest(format=fmt):
                frames,raw=software_frames(fmt)
                image,stats,d,cloud=adapter.process_frames(frames,dict(deviceId='software-test',pointStride=1),ob)
                np.testing.assert_array_equal(decode(d['image']),raw);self.assertEqual(image.shape,(12,16,3))
                self.assertEqual(stats['calibration']['color']['width'],32)
                self.assertEqual(cloud['extrinsics']['translation'],[.1,0,0])
                if fmt in ('RGB','BGR','MJPG'):
                    # x=-50 mm, z=1000 mm; tx=100 mm -> color u=16, red=112.
                    np.testing.assert_allclose(image[5,7],[160,80,112],atol=3 if fmt=='MJPG' else 0)
                np.testing.assert_allclose(cloud['colors'][86],image[5,7,::-1]/255,atol=1e-8)
                self.assertFalse(stats['colorCoverageKnown']);self.assertNotIn('mappedColorPoints',stats)

    def test_rotation_storage_matches_native_transformation(self):
        ex=ob.OBExtrinsic();ex.rot=np.array([[0,-1,0],[1,0,0],[0,0,1]],np.float32);ex.transform=np.array([100,20,30],np.float32)
        point=ob.transformation3dto3d(ob.OBPoint3f(1,2,3),ex)
        np.testing.assert_allclose([point.x,point.y,point.z],np.asarray(ex.rot)@np.array([1,2,3])+ex.transform)

    def test_range_stride_and_missing_frames(self):
        frames,raw=software_frames()
        _,stats,d,cloud=adapter.process_frames(frames,dict(deviceId='software',enableColor=False,pointStride=2,maxDepth=1.5),ob)
        self.assertEqual(len(cloud['points']),47);np.testing.assert_array_equal(decode(d['image']),raw)
        with self.assertRaisesRegex(ValueError,'没有有效'):
            adapter.process_frames(frames,dict(deviceId='software',enableColor=False,minDepth=3,maxDepth=4),ob)
        with self.assertRaisesRegex(ValueError,'缺少深度'):
            adapter.process_frames(ob.Frame.create_frame_set(),dict(deviceId='software'),ob)
        only=ob.Frame.create_frame_set();only.push_frame(frames.get_depth_frame())
        with self.assertRaisesRegex(ValueError,'缺少请求的彩色'):
            adapter.process_frames(only,dict(deviceId='software'),ob)

    def test_invalid_types_and_buffer_bounds(self):
        for extra in [dict(enableColor='false'),dict(discoverNetwork=1),dict(fps=12.5),dict(colorFormat='Y16'),dict(trigger='software'),dict(pointStride=0),dict(minDepth=5,maxDepth=2),dict(exposureTime=1),dict(colorWidth=4096,colorHeight=4096)]:
            with self.subTest(extra=extra),self.assertRaises(ValueError):camera.config(dict(driver='orbbec',**extra))
        f=MagicMock();f.get_width.return_value=4;f.get_height.return_value=3;f.get_format.return_value=ob.OBFormat.Y16;f.get_data.return_value=np.zeros(4,np.uint16)
        with self.assertRaisesRegex(ValueError,'缓冲区'):adapter.raw_depth(f,ob)
        f.get_format.return_value=ob.OBFormat.RGB
        with self.assertRaisesRegex(ValueError,'缓冲区'):adapter.color_image(f,ob)

class Lifecycle(unittest.TestCase):
    def setup_sdk(self):
        fake=MagicMock();fake.__file__=ob.__file__;items=MagicMock();items.get_count.return_value=1;items.get_device_serial_number_by_index.return_value='serial-1'
        items.get_device_name_by_index.return_value='Test camera';items.get_device_connection_type_by_index.return_value='USB';items.get_device_uid_by_index.return_value='uid'
        fake.Context.return_value.query_devices.return_value=items
        pipe=fake.Pipeline.return_value;dp=pipe.get_stream_profile_list.return_value.get_video_stream_profile.return_value
        dp.get_width.return_value=640;dp.get_height.return_value=480;dp.get_fps.return_value=30;dp.get_format.return_value=fake.OBFormat.Y16
        p=camera.config(dict(driver='orbbec',deviceId='serial-1',enableColor=False,warmupFrames=0))
        return fake,items,pipe,p

    def test_enumeration_does_not_open_device_or_enable_network_by_default(self):
        fake,items,pipe,p=self.setup_sdk();config_paths=[]
        def construct(file):
            config_paths.append(file)
            self.assertEqual(adapter.ET.parse(file).findtext('./Device/EnumerateNetDevice'),'false')
            return fake.Context.return_value
        fake.Context.side_effect=construct;rows=adapter.devices(p,fake)
        self.assertEqual(rows[0]['deviceId'],'serial-1');items.get_device_by_serial_number.assert_not_called();fake.Pipeline.assert_not_called()
        fake.Context.return_value.enable_net_device_enumeration.assert_called_once_with(False)
        self.assertTrue(config_paths);self.assertFalse(Path(config_paths[0]).exists())
        adapter.devices({**p,'discoverNetwork':True},fake)
        fake.Context.return_value.enable_net_device_enumeration.assert_called_with(True)

    def test_missing_or_duplicate_serial_never_opens_default_device(self):
        for count in (0,2):
            fake,items,pipe,p=self.setup_sdk();items.get_count.return_value=count
            with self.assertRaisesRegex(ValueError,'不存在或序列号不唯一'):adapter.acquire(p,ob=fake)
            fake.Pipeline.assert_not_called();items.get_device_by_serial_number.assert_not_called()

    def test_inspection_and_failed_wait_release(self):
        fake,items,pipe,p=self.setup_sdk();out=adapter.acquire(p,True,fake)
        self.assertEqual(out['device']['deviceId'],'serial-1');pipe.start.assert_not_called()
        pipe.wait_for_frames.side_effect=RuntimeError('disconnected')
        with self.assertRaisesRegex(RuntimeError,'disconnected'):adapter.acquire(p,ob=fake)
        pipe.stop.assert_called_once();items.get_device_by_serial_number.assert_called_with('serial-1')

    def test_profile_mismatch_and_total_timeout(self):
        fake,items,pipe,p=self.setup_sdk();dp=pipe.get_stream_profile_list.return_value.get_video_stream_profile.return_value;dp.get_width.return_value=320
        with self.assertRaisesRegex(ValueError,'配置与请求不一致'):adapter.acquire(p,ob=fake)
        pipe.start.assert_not_called()
        dp.get_width.return_value=640
        with patch.object(adapter.time,'monotonic',side_effect=[0,10]):
            with self.assertRaisesRegex(TimeoutError,'总时限'):adapter.acquire(p,ob=fake)
        pipe.stop.assert_called_once()

if __name__=='__main__':unittest.main(verbosity=2)
