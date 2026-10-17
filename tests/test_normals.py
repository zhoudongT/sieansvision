import importlib.util
import json
import math
from pathlib import Path
import unittest
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT/'operator-plugins/sieans-normals'
spec = importlib.util.spec_from_file_location('normals', FOLDER/'normals.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
defaults = {f['key']: f['default'] for f in json.loads((FOLDER/'operator-plugin.json').read_text(encoding='utf-8'))['operators'][0]['parameters']}


def run(points, unit='mm', **overrides):
    return module.run(dict(params=dict(defaults, **overrides),cloud=dict(points=np.asarray(points).tolist(),unit=unit,frame='test')))


def plane(n=11):
    return np.array([[x,y,x/math.sqrt(3)] for y in range(n) for x in range(n)])


class NormalTests(unittest.TestCase):
    def test_known_slope_direction_residual_and_threshold(self):
        points=plane()
        out=run(points,maximumSlopeDegrees=30,maximumResidual=0)
        r=out['result']
        self.assertTrue(r['passed'])
        self.assertEqual((r['validCount'],r['invalidCount'],r['outsideCount']),(121,0,0))
        self.assertAlmostEqual(r['meanSlopeDegrees'],30,places=8)
        self.assertAlmostEqual(r['items'][0]['normalX'],-.5)
        self.assertAlmostEqual(r['items'][0]['normalZ'],math.sqrt(3)/2)
        self.assertEqual(out['cloud']['points'],points.tolist())
        failed=run(points,maximumSlopeDegrees=20)
        self.assertEqual(failed['result']['outsideCount'],121)
        self.assertFalse(failed['result']['passed'])
        self.assertEqual(failed['cloud']['colors'][0],[1.,.15,.1])

    def test_reference_normalization_reversal_and_rotation(self):
        points=plane()
        r=run(points,referenceZ=-7)['result']
        self.assertAlmostEqual(r['meanSlopeDegrees'],30)
        self.assertLess(r['items'][0]['normalZ'],0)
        r=run(points,referenceX=-.5,referenceZ=math.sqrt(3)/2,maximumSlopeDegrees=0)['result']
        self.assertLess(r['maxSlopeDegrees'],.00001)
        self.assertTrue(r['passed'])
        for scale in [1e-200,1e300]:
            self.assertAlmostEqual(run(points,referenceZ=scale)['result']['meanSlopeDegrees'],30)
        with self.assertRaisesRegex(ValueError,'不能为零'):run(points,referenceZ=0)

    def test_insufficient_and_collinear_never_pass_even_with_allowance(self):
        for points,args in [(plane(),dict(radius=.5)),([[i,0,0] for i in range(10)],dict(radius=10)),([[1,1,1]]*10,dict(radius=10))]:
            r=run(points,maximumInvalidPercent=100,**args)['result']
            self.assertFalse(r['passed'])
            self.assertFalse(r['hasValidNormals'])
            self.assertNotIn('meanSlopeDegrees',r)
            self.assertEqual(r['invalidCount'],len(points))
            self.assertNotIn('normalZ',r['items'][0])

    def test_isotropic_neighborhood_is_not_given_arbitrary_normal(self):
        points=[[0,0,0],[1,0,0],[-1,0,0],[0,1,0],[0,-1,0],[0,0,1],[0,0,-1]]
        r=run(points,radius=3)['result']
        self.assertEqual(r['invalidCount'],7)
        self.assertIn('唯一法向',r['items'][0]['reason'])

    def test_duplicate_support_and_invalid_percent_denominators(self):
        points=np.vstack([plane(),[[100,100,100]]*3])
        r=run(points,maximumInvalidPercent=3)['result']
        self.assertTrue(r['passed'])
        self.assertEqual(r['uniquePointCount'],122)
        self.assertEqual(r['invalidCount'],3)
        self.assertEqual(r['items'][0]['neighborCount'],1)
        self.assertAlmostEqual(r['invalidPercent'],300/124)
        r=run(points,maximumInvalidPercent=3,maximumSlopeDegrees=20)['result']
        self.assertEqual(r['outsidePercent'],100)
        self.assertFalse(r['passed'])

    def test_units_scale_with_neighborhood_and_residual(self):
        points=plane();points[:,2]+=.02*np.sin(points[:,0]*2+points[:,1])
        a=run(points,maximumResidual=.0001)['result']
        b=run(points*.001,unit='m',radius=.0025,maximumResidual=.0000001)['result']
        self.assertGreater(a['outsideCount'],0)
        self.assertEqual(a['outsideCount'],b['outsideCount'])
        self.assertAlmostEqual(a['maxLocalResidual']*.001,b['maxLocalResidual'],places=12)
        self.assertAlmostEqual(a['meanSlopeDegrees'],b['meanSlopeDegrees'],places=8)

    def test_detail_limits_color_preservation_and_validation(self):
        out=run(plane(25),colorize=False)
        self.assertNotIn('cloud',out)
        self.assertEqual(len(out['result']['items']),500)
        self.assertTrue(out['result']['detailsTruncated'])
        self.assertEqual(out['result']['pointCount'],625)
        with self.assertRaisesRegex(ValueError,'最少邻居'):run(plane(),minimumNeighbors=31)
        for points in [[],[[0,0,0]],[[0,0,math.nan]]*3,[[0,0]]*3,[[0,0,0]]*20001]:
            with self.assertRaises(ValueError):run(points)
        with self.assertRaisesRegex(ValueError,'10000'):run([[0,0,0]]*10001)


if __name__=='__main__':unittest.main()
