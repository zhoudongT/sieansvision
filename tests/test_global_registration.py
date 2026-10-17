"""Numerical acceptance tests on known synthetic surfaces, not camera validation."""
import copy
import sys
import unittest
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'vision'))
from cloud_engine import run


def surface(n=1800, phase=0):
    i = np.arange(n)
    z = 1 - 2 * (i + .5) / n
    phi = i * np.pi * (3 - np.sqrt(5)) + phase
    r = np.sqrt(1-z*z)
    direction = np.column_stack((r*np.cos(phi), r*np.sin(phi), z))
    shape = 1 + .22*np.sin(3*phi)*(1-z*z) + .14*z + .12*np.cos(5*phi)*r*r
    return direction * shape[:, None] * [16, 10, 7]


def pose():
    a, b = np.deg2rad([67, 41])
    rz = np.array([[np.cos(a), -np.sin(a), 0], [np.sin(a), np.cos(a), 0], [0, 0, 1]])
    rx = np.array([[1, 0, 0], [0, np.cos(b), -np.sin(b)], [0, np.sin(b), np.cos(b)]])
    return rz @ rx, np.array([70, -45, 25])


def fixture(independent=False, noise=0, scale=1):
    points = surface()
    rotation, translation = pose()
    target = surface(2400, .23) if independent else points.copy()
    target += np.random.default_rng(14).normal(0, noise, target.shape)
    unit = 'm' if scale == .001 else 'mm'
    source = dict(points=((points@rotation.T+translation)*scale).tolist(), unit=unit, frame='camera',
                  timestamp=1234, intrinsics={'fx':100,'fy':100,'cx':0,'cy':0},
                  extrinsics=np.eye(4).tolist(), colors=np.tile([.1,.6,.9],(len(points),1)).tolist())
    reference = dict(points=(target*scale).tolist(), unit=unit, frame='fixture')
    params = dict(method='global',targetCloud=reference,voxelSize=1.3*scale,maxDistance=.9*scale,
                  maxRmsError=.5*scale,minFitness=.9,minTargetFitness=.8,iterations=80)
    return source, params


def invoke(source, params):
    return run(dict(operation='cloud_register',cloud=source,params=params))


class GlobalRegistrationTests(unittest.TestCase):
    def test_large_pose_recovers_expected_inverse_and_preserves_source(self):
        source, params = fixture()
        original = copy.deepcopy(source)
        out = invoke(source, params)
        r = out['result']; matrix = np.asarray(r['transformation'])
        rotation, translation = pose()
        self.assertTrue(r['found']); self.assertTrue(r['passed'])
        np.testing.assert_allclose(matrix[:3,:3],rotation.T,atol=1e-6)
        np.testing.assert_allclose(matrix[:3,3],-rotation.T@translation,atol=1e-6)
        np.testing.assert_allclose(out['cloud']['points'],params['targetCloud']['points'],atol=1e-6)
        self.assertEqual(r['fitness'],1); self.assertEqual(r['targetFitness'],1)
        self.assertEqual(out['cloud']['frame'],'fixture')
        self.assertEqual(out['cloud']['colors'],source['colors'])
        self.assertEqual(out['cloud']['timestamp'],1234)
        self.assertNotIn('intrinsics',out['cloud']); self.assertNotIn('extrinsics',out['cloud'])
        self.assertEqual(source,original)
        with self.assertRaisesRegex(ValueError,'没有有效对应'):
            invoke(source,{**params,'method':'icp'})

    def test_independent_resampling_noise_and_partial_overlap(self):
        source, params = fixture(independent=True,noise=.025)
        # Missing cap: different density and coverage, not identical point indices.
        target = np.asarray(params['targetCloud']['points'])
        params['targetCloud']['points'] = target[target[:,2]>-5].tolist()
        params['minFitness'] = .7
        r = invoke(source,params)['result']
        self.assertTrue(r['found'],r)
        rotation, translation = pose(); matrix = np.asarray(r['transformation'])
        np.testing.assert_allclose(matrix[:3,:3],rotation.T,atol=.015)
        np.testing.assert_allclose(matrix[:3,3],-rotation.T@translation,atol=.5)
        self.assertLess(r['rmsError'],.5)

    def test_meter_units_and_duplicate_points_do_not_inflate_quality(self):
        source, params = fixture(scale=.001)
        source['points'] *= 2; source['colors'] *= 2
        out = invoke(source,params)
        self.assertTrue(out['result']['found'])
        self.assertEqual(out['result']['matchedPoints'],1800)
        self.assertEqual(out['result']['sourceUniquePoints'],1800)
        self.assertEqual(out['result']['pointCount'],3600)
        self.assertEqual(out['cloud']['unit'],'m')
        np.testing.assert_allclose(out['cloud']['points'][:1800],params['targetCloud']['points'],atol=1e-8)

    def test_quality_rejection_keeps_original_frame_calibration_and_no_pose(self):
        source, params = fixture(noise=.03)
        params['maxRmsError'] = .001
        out = invoke(source,params); r = out['result']
        self.assertFalse(r['found']); self.assertFalse(r['passed'])
        self.assertNotIn('transformation',r); self.assertIn('均方根',r['reason'])
        self.assertEqual(out['cloud'],source)

    def test_different_shape_is_rejected_at_strict_coverage(self):
        source, params = fixture()
        params['targetCloud']['points'] = (surface()*[1,2,1]).tolist()
        params.update(maxDistance=.2,minFitness=.95,minTargetFitness=.95,maxRmsError=.1)
        out = invoke(source,params)
        self.assertFalse(out['result']['found'],out['result'])
        self.assertNotIn('transformation',out['result'])
        self.assertEqual(out['cloud'],source)

    def test_degenerate_and_sparse_surfaces_fail_with_diagnostic(self):
        _, params = fixture()
        cases=[([[0,0,0]]*100,'独立点'),([[x,y,0] for x in range(10) for y in range(10)],'平面'),
               ([[x,x,x] for x in range(100)],'共线'),((surface()*100).tolist(),'有效邻域')]
        for points, reason in cases:
            with self.subTest(reason=reason), self.assertRaisesRegex(ValueError,reason):
                invoke({'unit':'mm','points':points},params)

    def test_invalid_global_configuration_rejected_before_matching(self):
        source, params = fixture()
        bad={'voxelSize':[0,True,float('nan')], 'ransacIterations':[99,100001,100.5],
             'iterations':[.5,501,50.5], 'ransacConfidence':[.5,1], 'minFitness':[-.1,1.1],
             'minTargetFitness':[-1,2], 'maxRmsError':[0,float('inf')], 'method':['bad']}
        for key, values in bad.items():
            for value in values:
                with self.subTest(key=key,value=value), self.assertRaises(ValueError):
                    invoke(source,{**params,key:value})
        with self.assertRaisesRegex(ValueError,'单位'):
            invoke(source,{**params,'targetCloud':{**params['targetCloud'],'unit':'m'}})

    def test_fewer_mutual_pairs_return_failure_without_fallback(self):
        # Controlled descriptor degeneracy covers Open3D's usual fallback corner.
        from unittest.mock import patch
        import global_registration as module
        import open3d as o3d
        points=surface(40); pc=o3d.geometry.PointCloud(o3d.utility.Vector3dVector(points))
        with patch.object(module,'prepare',return_value=(pc,pc,np.zeros((40,33)))):
            result, transform=module.register(points,points,{},o3d)
        self.assertFalse(result['found']); self.assertIsNone(transform)
        self.assertLess(result['featureMatches'],6)


if __name__=='__main__':
    unittest.main(verbosity=2)
