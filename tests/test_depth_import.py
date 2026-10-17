import base64
import copy
import importlib.util
import struct
import sys
from pathlib import Path
import unittest
import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'vision'))
import depth_import

PARAMS = dict(projection='rectified-z', fx=100, fy=200, cx=1, cy=1, scaleMeters=.001,
              minDepth=.1, maxDepth=2, pointStride=1, invalidValue=65535, frame='test-optical')


def encode(raw): return 'data:image/png;base64,'+base64.b64encode(cv2.imencode('.png', raw)[1]).decode()


def run(raw=None, **args):
    return depth_import.run(dict(content=encode(np.full((3, 4), 1000, np.uint16) if raw is None else raw), params={**PARAMS, **args}))


class DepthImportTests(unittest.TestCase):
    def test_known_pinhole_projection_and_non_square_focal_length(self):
        output = run()
        points = np.asarray(output['cloud']['points'])
        self.assertTrue(np.allclose(points[0], [-10, -5, 1000]))
        self.assertTrue(np.allclose(points[-1], [20, 5, 1000]))
        self.assertEqual(output['cloud']['unit'], 'mm')
        self.assertEqual(output['depth']['intrinsics']['width'], 4)
        self.assertEqual(output['depth']['intrinsics']['height'], 3)

    def test_original_values_bytes_scale_and_invalid_sentinels(self):
        raw = np.array([[0, 9750, 10000, 65535]], np.uint16)
        out = run(raw, scaleMeters=.0001)
        self.assertEqual(out['depth']['image'], encode(raw))
        restored = cv2.imdecode(np.frombuffer(base64.b64decode(out['depth']['image'][22:]), np.uint8), cv2.IMREAD_UNCHANGED)
        np.testing.assert_array_equal(restored, raw)
        self.assertEqual(out['result']['invalidDepthPixels'], 2)
        self.assertEqual(out['result']['pointCount'], 2)
        np.testing.assert_allclose(np.asarray(out['cloud']['points'])[:, 2], [975, 1000])

    def test_range_and_grid_stride_preserve_raw_image(self):
        raw = np.full((5, 7), 1000, np.uint16)
        raw[0, 0] = 0
        raw[2, 2] = 1500
        out = run(raw, pointStride=2, maxDepth=1.1)
        self.assertEqual(out['result']['pointCount'], 10)
        self.assertEqual(out['depth']['image'], encode(raw))
        self.assertEqual(out['result']['inRangePixels'], 33)
        self.assertEqual(out['result']['sampledInvalidPixels'], 2)
        preview = cv2.imdecode(np.frombuffer(base64.b64decode(out['depth']['preview'][22:]), np.uint8), cv2.IMREAD_COLOR)
        self.assertTrue(np.all(preview[0, 0] == 0))
        self.assertTrue(np.all(preview[2, 2] == 0))
        self.assertTrue(np.any(preview[1, 1] != 0))

    def test_eight_bit_color_and_fake_header_rejected(self):
        for raw in [np.full((3, 4), 100, np.uint8), np.full((3, 4, 3), 100, np.uint8), np.full((3, 4, 3), 1000, np.uint16)]:
            with self.assertRaisesRegex(ValueError, '16 位灰度'): run(raw)
        raw = bytearray(base64.b64decode(encode(np.full((3, 4), 1000, np.uint16))[22:]))
        raw[16:24] = struct.pack('>II', 100000, 100000)
        with self.assertRaisesRegex(ValueError, '400 万'): depth_import.run(dict(content='data:image/png;base64,'+base64.b64encode(raw).decode(), params=PARAMS))

    def test_empty_depth_grid_and_invalid_sampling_fail(self):
        for raw in [np.zeros((3, 4), np.uint16), np.full((3, 4), 65535, np.uint16), np.full((3, 4), 100, np.uint16)]:
            with self.assertRaisesRegex(ValueError, '有效采样点'): run(raw, minDepth=.5)
        raw = np.zeros((3, 4), np.uint16)
        raw[1, 1] = 1000
        with self.assertRaisesRegex(ValueError, '有效采样点'): run(raw, pointStride=2)

    def test_grid_limit_is_checked_before_projection(self):
        raw = np.full((500, 500), 1000, np.uint16)
        with self.assertRaisesRegex(ValueError, '20 万点'): run(raw)
        self.assertEqual(run(raw, pointStride=2)['result']['pointCount'], 62500)

    def test_required_explicit_projection_and_strict_params(self):
        for args in [dict(projection='radial'), dict(fx=True), dict(fy=0), dict(cx=float('nan')), dict(pointStride=1.5), dict(invalidValue=-1), dict(scaleMeters=0), dict(scaleMeters=float('inf')), dict(frame=''), dict(frame='a\nb'), dict(minDepth=2, maxDepth=1)]:
            with self.assertRaises(ValueError): run(**args)
        p = copy.deepcopy(PARAMS)
        del p['fx']
        with self.assertRaises(ValueError): depth_import.run(dict(content=encode(np.ones((3, 4), np.uint16)), params=p))

    def test_corrupt_file_and_projection_overflow(self):
        for content in ['', 'data:image/png;base64,@@@@', 'data:image/png;base64,AAAA', 'data:image/jpeg;base64,AAAA']:
            with self.assertRaises(ValueError): depth_import.run(dict(content=content, params=PARAMS))
        with self.assertRaisesRegex(ValueError, '坐标超限'): run(fx=.000001, cx=1e6)

    def test_open3d_independent_projection_agrees(self):
        import open3d as o3d
        raw = np.full((3, 4), 1000, np.uint16)
        out = run(raw, invalidValue=0)
        cloud = o3d.geometry.PointCloud.create_from_depth_image(o3d.geometry.Image(raw), o3d.camera.PinholeCameraIntrinsic(4, 3, 100, 200, 1, 1), depth_scale=1000, depth_trunc=2, stride=1)
        np.testing.assert_allclose(np.asarray(cloud.points)*1000, out['cloud']['points'], atol=1e-6)


if __name__ == '__main__': unittest.main()
