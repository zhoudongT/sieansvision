import base64
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
import numpy as np
import cv2
import pyrealsense2 as rs
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'cameras'))
import adapter as camera
import depth_adapter as depth


def decode(data):
    return cv2.imdecode(np.frombuffer(base64.b64decode(data.split(',')[1]),np.uint8),cv2.IMREAD_UNCHANGED)


class DepthTests(unittest.TestCase):
    def test_raw_depth_preserved_and_metric_projection(self):
        out=camera.run(dict(operation='camera_capture',params=dict(driver='rgbd_simulator')))
        raw=decode(out['depth']['image']);self.assertEqual(raw.dtype,np.uint16);self.assertEqual(raw.shape,(48,64))
        self.assertEqual(raw[0,0],0);self.assertEqual(raw[20,25],975);self.assertEqual(raw[10,10],1000)
        cloud=out['cloud'];self.assertEqual(cloud['unit'],'mm');self.assertEqual(len(cloud['points']),3071)
        target=np.asarray(cloud['points']);target=target[np.isclose(target[:,2],975)]
        self.assertEqual(len(target),200);np.testing.assert_allclose(np.ptp(target,axis=0),[185.25,87.75,0],atol=1e-8)
        self.assertTrue(out['result']['simulated']);self.assertEqual(out['result']['depthBits'],16)

    def test_distance_filter_stride_and_empty_rejection(self):
        p=dict(driver='rgbd_simulator',minDepth=.97,maxDepth=.98,pointStride=2)
        out=camera.run(dict(operation='camera_capture',params=p))
        self.assertEqual(out['result']['pointCount'],50);self.assertEqual(out['result']['inRangePixels'],200)
        self.assertTrue(np.allclose(np.asarray(out['cloud']['points'])[:,2],975))
        self.assertEqual(decode(out['depth']['image'])[10,10],1000) # range does not overwrite raw data
        with self.assertRaisesRegex(ValueError,'没有有效'):
            camera.run(dict(operation='camera_capture',params={**p,'minDepth':2,'maxDepth':3}))

    def test_invalid_config_bounds_types_and_large_point_grid(self):
        for p in [dict(driver='realsense',enableColor='false'),dict(driver='realsense',fps=12.5),dict(driver='rgbd_simulator',pointStride=0),dict(driver='realsense',minDepth=5,maxDepth=2),dict(driver='realsense',trigger='software')]:
            with self.assertRaises(ValueError):camera.config(p)
        with self.assertRaisesRegex(ValueError,'20 万点'):
            depth.pack(np.ones((500,500),np.uint16),.001,np.ones((250000,3)),{'pointStride':1},{'depth':{}},'test')

    def test_real_sdk_software_frame_deprojection_and_depth_units(self):
        # Actual SDK processing on software-fed sensor, not a hardware acquisition claim.
        device=rs.software_device();sensor=device.add_sensor('Depth')
        intr=rs.intrinsics();intr.width=4;intr.height=3;intr.fx=2;intr.fy=2;intr.ppx=1;intr.ppy=1;intr.model=rs.distortion.none;intr.coeffs=[0.]*5
        stream=rs.video_stream();stream.type=rs.stream.depth;stream.index=0;stream.uid=1;stream.width=4;stream.height=3;stream.fps=30;stream.bpp=2;stream.fmt=rs.format.z16;stream.intrinsics=intr
        profile=sensor.add_video_stream(stream).as_video_stream_profile();sensor.add_read_only_option(rs.option.depth_units,.001)
        queue=rs.frame_queue(1);sensor.open(profile);sensor.start(queue)
        raw=np.full((3,4),1000,np.uint16);raw[0,0]=0;raw[2,3]=2000
        frame=rs.software_video_frame();frame.pixels=raw;frame.stride=8;frame.bpp=2;frame.timestamp=12;frame.domain=rs.timestamp_domain.hardware_clock;frame.frame_number=8;frame.profile=profile;frame.depth_units=.001
        try:
            sensor.on_video_frame(frame);df=queue.wait_for_frame(1000).as_depth_frame();points=rs.pointcloud().calculate(df)
            vertices=np.asanyarray(points.get_vertices()).view(np.float32).reshape(-1,3).copy()
            d,cloud,stats,_=depth.pack(np.asanyarray(df.get_data()).copy(),df.get_units(),vertices,{'pointStride':1},{'depth':depth.intrinsics(profile.get_intrinsics())},'software-device')
            self.assertEqual(len(cloud['points']),11);np.testing.assert_allclose(cloud['points'][-1],[2000,1000,2000],atol=.001)
            self.assertEqual(cloud['points'][4],[0.,0.,1000.]);self.assertEqual(decode(d['image'])[2,3],2000)
        finally:sensor.stop();sensor.close()

    def test_color_texture_mapping_preserves_out_of_view_points(self):
        raw=np.full((2,2),1000,np.uint16);xyz=np.array([[0,0,1],[1,0,1],[0,1,1],[1,1,1]],np.float32)
        color=np.array([[[0,0,255],[0,255,0]],[[255,0,0],[255,255,255]]],np.uint8)
        uv=np.array([[0,0],[.5,0],[-1,0],[float('nan'),.5]])
        _,cloud,stats,_=depth.pack(raw,.001,xyz,{'pointStride':1},{'depth':{}},'test',color,uv)
        self.assertEqual(cloud['colors'],[[1.,0.,0.],[0.,1.,0.],[.5,.5,.5],[.5,.5,.5]])
        self.assertEqual(len(cloud['points']),4);self.assertEqual(stats['mappedColorPoints'],2)

    def test_failed_frame_wait_stops_started_pipeline(self):
        sdk=MagicMock();device=MagicMock();device.get_info.return_value='serial';sdk.context.return_value.query_devices.return_value=[device]
        pipe=sdk.pipeline.return_value;pipe.wait_for_frames.side_effect=RuntimeError('camera disconnected')
        with self.assertRaisesRegex(RuntimeError,'disconnected'):
            depth.acquire(dict(deviceId='serial',timeoutMs=5000,warmupFrames=0),rs=sdk)
        sdk.config.return_value.enable_device.assert_called_once_with('serial');pipe.stop.assert_called_once()

    def test_missing_device_does_not_open_arbitrary_camera(self):
        sdk=MagicMock();sdk.context.return_value.query_devices.return_value=[]
        with self.assertRaisesRegex(ValueError,'不存在'):
            depth.acquire(dict(deviceId='not-found',timeoutMs=5000),rs=sdk)
        sdk.pipeline.assert_not_called()


if __name__=='__main__':unittest.main(verbosity=2)
