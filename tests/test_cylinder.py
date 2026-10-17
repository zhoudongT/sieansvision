import importlib.util
import json
from pathlib import Path
import unittest
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
FOLDER=ROOT/'operator-plugins/sieans-cylinder'
SPEC=importlib.util.spec_from_file_location('cylinder',FOLDER/'cylinder.py')
MODULE=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(MODULE)
MANIFEST=json.loads((FOLDER/'operator-plugin.json').read_text(encoding='utf-8'))
CENTER=np.array([12.,-4.,30.]);AXIS=np.array([.3,-.4,np.sqrt(.75)])


def geometry(radius=10.,span=40.,arc=360.,axis=AXIS,center=CENTER,n=600):
    axis=np.asarray(axis,dtype=float);axis/=np.linalg.norm(axis)
    u=np.cross(axis,np.eye(3)[np.argmin(np.abs(axis))]);u/=np.linalg.norm(u);v=np.cross(axis,u)
    # Non-grid sampling exercises arbitrary angular/axial sampling and rotations.
    i=np.arange(n);angle=(i*.61803398875%1)*np.deg2rad(arc);height=np.linspace(-span/2,span/2,n)
    radial=np.cos(angle)[:,None]*u+np.sin(angle)[:,None]*v
    return center+height[:,None]*axis+radius*radial,radial


def cloud(points,unit='mm',frame='fixture'):
    return dict(unit=unit,frame=frame,points=np.asarray(points).tolist())


def run(task,c,**params):
    op=next(o for o in MANIFEST['operators'] if o['id']==task)
    p={f['key']:f['default'] for f in op['parameters']};p.update(params)
    return MODULE.run(dict(params=p,cloud=c))


def model(axis=AXIS,center=CENTER,radius=10,unit='mm',frame='fixture'):
    return dict(model='sieans-cylinder-v1',axisPoint=np.asarray(center).tolist(),axisDirection=np.asarray(axis).tolist(),radius=radius,unit=unit,frame=frame)


class CylinderTests(unittest.TestCase):
    def assert_axis(self,result,direction=AXIS,center=CENTER,tolerance=1e-7):
        actual=np.asarray(result['axisDirection']);direction=np.asarray(direction);direction=direction/np.linalg.norm(direction)
        self.assertLess(np.linalg.norm(np.cross(actual,direction)),tolerance)
        delta=np.asarray(result['axisPoint'])-center
        self.assertLess(np.linalg.norm(delta-np.dot(delta,direction)*direction),tolerance)

    def test_free_axis_and_all_point_fit(self):
        for axis in (AXIS,[1,0,0],[0,1,0],[0,0,-1],[1,1,1]):
            for method in ('robust','all'):
                with self.subTest(axis=axis,method=method):
                    c=cloud(geometry(axis=axis)[0]);r=run('fit',c,method=method)['result']
                    self.assertTrue(r['passed'],r);self.assert_axis(r,axis)
                    self.assertAlmostEqual(r['diameter'],20,places=7)
                    self.assertEqual(r['uniqueInlierCount'],600);self.assertGreater(r['angularCoverageDeg'],350)
                    self.assertAlmostEqual(r['sampledAxialSpan'],40,places=7)
                    self.assertTrue(run('inspect',c,cylinder=r['cylinder'])['result']['passed'])

    def test_noise_outliers_and_duplicates_do_not_bias_fitting(self):
        rng=np.random.default_rng(18);points,radial=geometry()
        clean=points+rng.normal(0,.01,(len(points),1))*radial
        outside=points[::10]+3*radial[::10]
        all_points=np.vstack((clean,outside))
        out=run('fit',cloud(all_points));r=out['result']
        self.assertTrue(r['passed'],r);self.assert_axis(r,tolerance=.004)
        self.assertAlmostEqual(r['diameter'],20,delta=.004);self.assertEqual(r['outsideCount'],60)
        self.assertAlmostEqual(r['inlierRatio'],600/660)
        duplicate=run('fit',cloud(np.vstack((all_points,np.tile(outside[0],(200,1))))))['result']
        self.assertAlmostEqual(duplicate['diameter'],r['diameter'],places=10)
        self.assertEqual(duplicate['uniquePointCount'],660);self.assertEqual(duplicate['outsideCount'],260)

    def test_partial_arc_and_short_or_narrow_coverage(self):
        broad=run('fit',cloud(geometry(arc=160)[0]))['result'];self.assertTrue(broad['passed'],broad);self.assert_axis(broad)
        for params in (dict(arc=12),dict(span=.2)):
            r=run('fit',cloud(geometry(**params)[0]))['result']
            self.assertFalse(r['found'],r);self.assertFalse(r['passed']);self.assertNotIn('cylinder',r)
            self.assertRegex(r['diagnostic'],'覆盖|稳定')

    def test_rank_degenerate_clouds_do_not_get_fake_models(self):
        circle=np.column_stack((10*np.cos(np.arange(30)),10*np.sin(np.arange(30)),np.zeros(30)))
        for points in (np.zeros((20,3)),np.column_stack((np.arange(20),np.zeros((20,2)))),circle,geometry(n=11)[0]):
            r=run('fit',cloud(points))['result'];self.assertFalse(r['found']);self.assertNotIn('axisPoint',r);self.assertNotIn('diameter',r)

    def test_independent_reference_sign_colors_indices_and_axial_translation(self):
        points,radial=geometry(n=100);points[4]+=.5*radial[4];points[31]-=.3*radial[31]
        c=cloud(points);out=run('inspect',c,cylinder=model(),detailMode='outside');r=out['result']
        self.assertFalse(r['passed']);self.assertEqual(r['outsideCount'],2)
        self.assertAlmostEqual(r['maximumDistance'],.5,places=9);self.assertAlmostEqual(r['minimumDistance'],-.3,places=9)
        self.assertEqual([item['pointIndex'] for item in r['items']],[4,31]);self.assertEqual(r['outsidePercent'],2)
        self.assertEqual(out['cloud']['points'],c['points']);self.assertEqual(out['cloud']['frame'],'fixture')
        self.assertEqual(out['cloud']['colors'][4],[1.,.15,.1]);self.assertEqual(out['cloud']['colors'][5],[.1,.75,.4])
        self.assertTrue(run('inspect',c,cylinder=model(),maximumOutsidePercent=2)['result']['passed'])
        # Moving the model point along its axis or reversing the direction preserves radial distances.
        shifted=run('inspect',c,cylinder=model(center=CENTER+100*AXIS,axis=-AXIS))['result']
        self.assertAlmostEqual(shifted['maximumDistance'],r['maximumDistance'],places=9)
        self.assertEqual(shifted['outsideCount'],2)
        axis_point=run('inspect',cloud([CENTER]),cylinder=model())['result'];self.assertAlmostEqual(axis_point['minimumDistance'],-10)

    def test_metre_units_and_large_translation(self):
        r=run('fit',cloud(geometry()[0]/1000,unit='m'),minimumRadius=.001,maximumRadius=.1,inlierThreshold=.00005,
              maximumRms=.00003,minimumDiameter=.0198,maximumDiameter=.0202)['result']
        self.assertTrue(r['passed'],r);self.assertAlmostEqual(r['diameter'],.02,places=10);self.assertEqual(r['cylinder']['unit'],'m')
        center=CENTER+[1e6,2e6,-3e6];r=run('fit',cloud(geometry(center=center)[0]))['result']
        self.assertTrue(r['passed'],r);self.assert_axis(r,center=center,tolerance=1e-7)

    def test_size_failure_sampling_and_detail_limits(self):
        r=run('fit',cloud(geometry(radius=11)[0]))['result'];self.assertTrue(r['found']);self.assertFalse(r['passed']);self.assertAlmostEqual(r['diameter'],22,places=7)
        points,radial=geometry(n=1200);points[-3:]+=2*radial[-3:]
        r=run('fit',cloud(points),maximumFitPoints=100)['result']
        self.assertTrue(r['passed'],r);self.assertEqual(r['sampleCount'],100);self.assertEqual(r['uniqueInlierCount'],1197);self.assertEqual(r['outsideCount'],3)
        self.assertEqual(len(r['items']),500);self.assertTrue(r['detailsTruncated'])
        self.assertNotIn('cloud',run('inspect',cloud(points),cylinder=model(),colorize=False))

    def test_reference_validation_and_parameter_errors(self):
        c=cloud(geometry()[0])
        for changes in (dict(unit='m'),dict(frame='other'),dict(model='unknown'),dict(axisDirection=[0,0,0]),dict(axisDirection=[2,0,0]),dict(radius=False),dict(axisPoint=[0,False,0])):
            with self.subTest(changes=changes),self.assertRaises(ValueError):run('inspect',c,cylinder={**model(),**changes})
        for changes in (dict(minimumRadius=11,maximumRadius=10),dict(minimumDiameter=21,maximumDiameter=20),dict(maximumFitPoints=True),dict(minimumAngularCoverage=0),dict(seed=-1),dict(method='unknown')):
            with self.subTest(changes=changes),self.assertRaises(ValueError):run('fit',c,**changes)
        for points in ([[False,0,0]],[[float('nan'),0,0]],[[1e10,0,0]],[]):
            with self.assertRaises(ValueError):run('fit',dict(unit='mm',frame='fixture',points=points))
        with self.assertRaises(ValueError):run('inspect',c,cylinder=model(),lowerDistance=1,upperDistance=-1)
        with self.assertRaises(ValueError):run('fit',cloud(np.tile(c['points'][0],(10001,1))))


if __name__=='__main__':unittest.main()
