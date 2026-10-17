import copy
import importlib.util
import json
from pathlib import Path
import unittest
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT/'operator-plugins/sieans-box'
spec = importlib.util.spec_from_file_location('box', FOLDER/'box.py')
box = importlib.util.module_from_spec(spec)
spec.loader.exec_module(box)
spec = importlib.util.spec_from_file_location('box_samples', ROOT/'scripts/generate-box-samples.py')
samples = importlib.util.module_from_spec(spec)
spec.loader.exec_module(samples)
manifest = json.loads((FOLDER/'operator-plugin.json').read_text(encoding='utf-8'))
DEFAULTS = {f['key']: f['default'] for f in manifest['operators'][0]['parameters']}


def run(points, unit='mm', **params):
    return box.run(dict(params={**DEFAULTS, **params}, cloud=dict(points=points.tolist() if isinstance(points,np.ndarray) else points, unit=unit, frame='fixture')))['result']


class BoxTests(unittest.TestCase):
    def test_rotated_cuboid_dimensions_and_containment(self):
        points = samples.surface([20, 10, 5])@samples.rotation().T+[50, -20, 100]
        r = run(points)
        np.testing.assert_allclose([r['length'], r['width'], r['thickness']], [20, 10, 5], atol=1e-8)
        self.assertAlmostEqual(r['boundingBoxVolume'], 1000, delta=.001)
        self.assertGreater(r['axisAlignedVolume'], 2000)
        axes = np.array([[row[k] for k in ('directionX', 'directionY', 'directionZ')] for row in r['axes']]).T
        np.testing.assert_allclose(axes.T@axes, np.eye(3), atol=1e-8)
        self.assertAlmostEqual(np.linalg.det(axes), 1)
        center = np.array([r[k] for k in ('boxCenterX', 'boxCenterY', 'boxCenterZ')])
        np.testing.assert_allclose(center, [50, -20, 100], atol=1e-8)
        half = np.array([r['length'], r['width'], r['thickness']])/2
        self.assertTrue(np.all(np.abs((points-center)@axes) <= half+1e-8))
        corners = np.array([[row[k] for k in ('cornerX', 'cornerY', 'cornerZ')] for row in r['corners']])
        np.testing.assert_allclose(np.abs((corners-center)@axes), np.tile(half, (8,1)), atol=1e-8)

    def test_reorder_duplicates_and_translation_do_not_bias_dimensions(self):
        points = samples.surface([20, 10, 5])@samples.rotation().T
        repeated = np.vstack([points, np.tile(points[5], (500, 1))])[::-1]+[1e7, -1e7, 3e7]
        r = run(repeated)
        np.testing.assert_allclose([r['length'], r['width'], r['thickness']], [20,10,5], atol=1e-6)
        self.assertEqual(r['pointCount'], len(repeated))
        self.assertEqual(r['uniquePointCount'], len(points))

    def test_unit_scaling_and_tolerance_failure_are_explicit(self):
        points = samples.surface([20, 10, 5])@samples.rotation().T
        r = run(points*.001, unit='m', minimumThickness=.000001, minimumLong=.019, maximumLong=.021)
        self.assertEqual(r['unit'], 'm')
        self.assertAlmostEqual(r['length'], .02)
        self.assertAlmostEqual(r['boundingBoxVolume'], 1e-6)
        self.assertTrue(r['passed'])
        r = run(points, maximumLong=19)
        self.assertTrue(r['found'])
        self.assertFalse(r['passed'])
        self.assertFalse(r['items'][0]['passed'])

    def test_equal_dimensions_are_flagged_without_claiming_unique_pose(self):
        r = run(samples.surface([10, 10, 10])@samples.rotation().T)
        self.assertTrue(r['nearEqualDimensions'])
        np.testing.assert_allclose([r['length'], r['width'], r['thickness']], [10]*3, atol=1e-8)
        self.assertNotIn('pose', r)

    def test_outlier_is_not_silently_discarded(self):
        points = samples.surface([20,10,5])
        before = run(points)
        after = run(np.vstack([points, [100, 0, 0]]))
        self.assertGreater(after['length'], 90)
        self.assertGreater(after['boundingBoxVolume'], before['boundingBoxVolume'])

    def test_degenerate_and_thin_inputs_fail_without_noise(self):
        for points in [np.zeros((4,3)), [[0,0,0],[1,0,0],[0,1,0],[1,1,0]], [[0,0,0],[1,0,0],[2,0,0],[3,0,0]]]:
            with self.assertRaisesRegex(ValueError, '独立点不足|共面'): run(points)
        with self.assertRaisesRegex(ValueError, '厚度小于'): run(samples.surface([20,10,.00001]), minimumThickness=.001)

    def test_invalid_coordinate_limits_and_parameters(self):
        points = samples.surface([20,10,5]).tolist()
        for value in [float('nan'), 1e10, True]:
            bad = copy.deepcopy(points)
            bad[0][0] = value
            with self.assertRaises(ValueError): run(bad)
        for params in [dict(minimumLong=20, maximumLong=10), dict(minimumThickness=True)]:
            with self.assertRaises(ValueError): run(points, **params)
        with self.assertRaisesRegex(ValueError, '20000'): run(np.zeros((20001,3)))

    def test_hull_complexity_refuses_truncation(self):
        i = np.arange(1100)
        z = 1-2*(i+.5)/len(i)
        a = i*np.pi*(3-np.sqrt(5))
        r = np.sqrt(1-z*z)
        with self.assertRaisesRegex(ValueError, '2048'): run(np.column_stack((r*np.cos(a),r*np.sin(a),z)))


if __name__ == '__main__': unittest.main()
