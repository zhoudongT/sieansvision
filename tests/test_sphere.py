import importlib.util
import json
from pathlib import Path
import unittest
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
FOLDER=ROOT/'operator-plugins/sieans-sphere'
SPEC=importlib.util.spec_from_file_location('sphere',FOLDER/'sphere.py')
MODULE=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(MODULE)
MANIFEST=json.loads((FOLDER/'operator-plugin.json').read_text(encoding='utf-8'))
CENTER=np.array([12.,-4.,30.])


def directions(n=600,cap=180):
    i=np.arange(n)
    z=1-(1-np.cos(np.deg2rad(cap)))*(i+.5)/n
    phi=i*np.pi*(3-np.sqrt(5))
    r=np.sqrt(1-z*z)
    return np.column_stack((r*np.cos(phi),r*np.sin(phi),z))


def cloud(points,unit='mm',frame='fixture'):
    return dict(unit=unit,frame=frame,points=np.asarray(points).tolist())


def run(task,c,**params):
    op=next(o for o in MANIFEST['operators'] if o['id']==task)
    p={f['key']:f['default'] for f in op['parameters']};p.update(params)
    return MODULE.run(dict(params=p,cloud=c))


def model(center=CENTER,radius=10,unit='mm',frame='fixture'):
    return dict(model='sieans-sphere-v1',center=np.asarray(center).tolist(),radius=radius,unit=unit,frame=frame)


class SphereTests(unittest.TestCase):
    def test_exact_sphere_diameter_center_and_reference_reuse(self):
        c=cloud(CENTER+10*directions())
        for method in ('all','ransac'):
            result=run('fit',c,method=method)['result']
            self.assertTrue(result['passed'],result)
            np.testing.assert_allclose(result['center'],CENTER,atol=1e-8)
            self.assertAlmostEqual(result['diameter'],20,places=8)
            self.assertEqual(result['uniqueInlierCount'],600)
            self.assertLess(result['rmsDistance'],1e-8)
            inspected=run('inspect',c,sphere=result['sphere'],detailMode='outside')['result']
            self.assertTrue(inspected['passed']);self.assertEqual(inspected['items'],[])

    def test_noise_outliers_and_duplicates(self):
        rng=np.random.default_rng(12)
        clean=CENTER+directions()*rng.normal(10,.01,(600,1))
        outside=CENTER+directions(80)*rng.uniform(12,18,(80,1))
        points=np.vstack((clean,outside))
        result=run('fit',cloud(points))['result']
        self.assertTrue(result['passed'],result)
        self.assertEqual(result['outsideCount'],80)
        self.assertAlmostEqual(result['inlierRatio'],600/680,places=8)
        np.testing.assert_allclose(result['center'],CENTER,atol=.004)
        duplicated=run('fit',cloud(np.vstack((points,np.tile(outside[0],(200,1))))))['result']
        np.testing.assert_allclose(duplicated['center'],result['center'],atol=1e-9)
        self.assertEqual(duplicated['uniquePointCount'],680);self.assertEqual(duplicated['outsideCount'],280)

    def test_partial_sphere_and_narrow_cap_diagnostics(self):
        broad=run('fit',cloud(CENTER+10*directions(cap=60)))['result']
        self.assertTrue(broad['passed'],broad)
        narrow=run('fit',cloud(CENTER+10*directions(cap=5)))['result']
        self.assertFalse(narrow['found']);self.assertFalse(narrow['passed']);self.assertNotIn('sphere',narrow)
        self.assertGreater(narrow['conditionNumber'],100)
        self.assertIn('覆盖',narrow['diagnostic'])

    def test_coplanar_collinear_duplicate_or_insufficient_points_are_not_spheres(self):
        for points in (np.zeros((10,3)),np.column_stack((np.arange(10),np.zeros((10,2)))),np.column_stack((np.cos(np.arange(20)),np.sin(np.arange(20)),np.zeros(20))),CENTER+10*directions(7)):
            with self.subTest(points=points.shape):
                result=run('fit',cloud(points))['result']
                self.assertFalse(result['found']);self.assertFalse(result['passed']);self.assertNotIn('center',result);self.assertNotIn('diameter',result)

    def test_reference_radial_signs_coloring_and_tolerance(self):
        unit=directions(100)
        points=CENTER+10*unit;points[4]=CENTER+10.5*unit[4];points[31]=CENTER+9.7*unit[31]
        c=cloud(points);out=run('inspect',c,sphere=model(),detailMode='outside')
        r=out['result'];self.assertFalse(r['passed']);self.assertEqual(r['outsideCount'],2)
        self.assertAlmostEqual(r['maximumDistance'],.5,places=9);self.assertAlmostEqual(r['minimumDistance'],-.3,places=9)
        self.assertEqual([i['pointIndex'] for i in r['items']],[4,31]);self.assertAlmostEqual(r['outsidePercent'],2)
        self.assertEqual(out['cloud']['points'],c['points']);self.assertEqual(out['cloud']['frame'],'fixture')
        self.assertEqual(out['cloud']['colors'][4],[1.,.15,.1]);self.assertEqual(out['cloud']['colors'][5],[.1,.75,.4])
        self.assertTrue(run('inspect',c,sphere=model(),maximumOutsidePercent=2)['result']['passed'])
        center=run('inspect',cloud([CENTER]),sphere=model())['result'];self.assertAlmostEqual(center['minimumDistance'],-10)

    def test_units_and_large_translation_preserve_geometry(self):
        c=cloud((CENTER+10*directions())/1000,unit='m')
        r=run('fit',c,minimumRadius=.001,maximumRadius=.1,inlierThreshold=.00005,maximumRms=.00003,minimumDiameter=.0198,maximumDiameter=.0202)['result']
        self.assertTrue(r['passed']);self.assertEqual(r['sphere']['unit'],'m');self.assertAlmostEqual(r['diameter'],.02,places=10)
        moved=CENTER+[1e6,2e6,-3e6]
        r=run('fit',cloud(moved+10*directions()))['result'];self.assertTrue(r['passed']);np.testing.assert_allclose(r['center'],moved,atol=1e-7)

    def test_diameter_failure_and_all_point_verification(self):
        r=run('fit',cloud(CENTER+11*directions()))['result'];self.assertTrue(r['found']);self.assertFalse(r['passed']);self.assertAlmostEqual(r['diameter'],22,places=8)
        points=CENTER+10*directions(1200);points[-3:]=CENTER+12*directions(3)
        r=run('fit',cloud(points),maximumFitPoints=100)['result'];self.assertEqual(r['sampleCount'],100)
        self.assertEqual(r['pointCount'],1200);self.assertEqual(r['outsideCount'],3);self.assertEqual(r['uniqueInlierCount'],1197)
        self.assertEqual(len(r['items']),500);self.assertTrue(r['detailsTruncated'])

    def test_invalid_reference_and_parameters_fail_explicitly(self):
        c=cloud(CENTER+10*directions(20))
        for reference in (dict(model(),unit='m'),dict(model(),frame='other'),dict(model(),radius=0),dict(model(),center=[True,1,2]),dict(model(),model='wrong')):
            with self.subTest(reference=reference),self.assertRaises(ValueError):run('inspect',c,sphere=reference)
        for params in (dict(minimumRadius=20,maximumRadius=10),dict(iterations=True),dict(minimumDiameter=30,maximumDiameter=20),dict(maximumCondition=1)):
            with self.subTest(params=params),self.assertRaises(ValueError):run('fit',c,**params)
        with self.assertRaises(ValueError):run('inspect',c,sphere=model(),lowerDistance=1,upperDistance=-1)
        with self.assertRaises(ValueError):run('fit',cloud([[float('nan'),1,2]]))

    def test_large_cloud_requires_explicit_no_color_and_preserves_finite_results(self):
        c=cloud(CENTER+10*directions(11000))
        with self.assertRaisesRegex(ValueError,'10000'):run('inspect',c,sphere=model())
        out=run('inspect',c,sphere=model(),colorize=False,detailMode='outside')
        self.assertNotIn('cloud',out);self.assertTrue(out['result']['passed']);json.dumps(out,allow_nan=False)


if __name__=='__main__':unittest.main()
