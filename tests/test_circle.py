import base64
import importlib.util
import json
import math
from pathlib import Path
import unittest
import cv2
import numpy as np

ROOT=Path(__file__).resolve().parents[1];FOLDER=ROOT/'operator-plugins/sieans-circle'
spec=importlib.util.spec_from_file_location('circle',FOLDER/'circle.py');c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)
manifest=json.loads((FOLDER/'operator-plugin.json').read_text(encoding='utf-8'));samples=ROOT/'public/vision/samples'
def encode(image):return 'data:image/png;base64,'+base64.b64encode(cv2.imencode('.png',image)[1]).decode()
def run(image=None,task='caliper',**overrides):
    op=next(op for op in manifest['operators'] if op['id']==task);p={f['key']:f['default'] for f in op['parameters']};p.update(overrides)
    if image is None and task=='caliper':image=cv2.imread(str(samples/'circle-hole.png'),cv2.IMREAD_GRAYSCALE)
    return c.run(dict(params=p,image=encode(image) if image is not None else None))
def model(radius=80,x=320,y=240):return dict(format='sieans-circle-v1',width=640,height=480,centerX=x,centerY=y,radiusPixels=radius,unit='px',unitsPerPixel=1,imageSha256='a'*64)


class CircleTests(unittest.TestCase):
    def test_fractional_center_diameter_and_uniform_scale(self):
        out=run(unitsPerPixel=.1,unit='mm',minimumDiameter=16,maximumDiameter=16.2);r=out['result']
        self.assertTrue(r['passed'],r);self.assertEqual(r['inlierCount'],72);self.assertAlmostEqual(r['centerX'],321.35,delta=.1);self.assertAlmostEqual(r['centerY'],239.65,delta=.1);self.assertAlmostEqual(r['diameter'],16.08,delta=.02);self.assertLess(r['rmsPixels'],.1)
        self.assertTrue(out['annotatedImage'].startswith('data:image/jpeg;base64,'));self.assertNotIn('image',out);self.assertEqual(len(r['circle']['imageSha256']),64)

    def test_dark_hole_polarity_and_no_edge(self):
        image=cv2.imread(str(samples/'circle-hole.png'),0)
        r=run(255-image,polarity='rising')['result'];self.assertTrue(r['passed'])
        for scene,args in [(image,dict(polarity='rising')),(np.full((480,640),100,np.uint8),{}),(image,dict(centerX=10,centerY=10))]:
            r=run(scene,**args)['result'];self.assertFalse(r['found']);self.assertFalse(r['passed']);self.assertNotIn('circle',r);self.assertNotIn('diameter',r)
            self.assertTrue(all(row['reason'] for row in r['items']))

    def test_select_inner_outer_edges(self):
        image=cv2.imread(str(samples/'circle-ring.png'),0)
        params=dict(expectedRadius=100,searchLength=90,polarity='either',minimumDiameter=100,maximumDiameter=300)
        inner=run(image,selection='inner',**params)['result'];outer=run(image,selection='outer',**params)['result']
        self.assertTrue(inner['passed']);self.assertTrue(outer['passed']);self.assertAlmostEqual(inner['radiusPixels'],80.4,delta=.15);self.assertAlmostEqual(outer['radiusPixels'],120.7,delta=.15)

    def test_outliers_occlusion_and_ratio_guard(self):
        image=cv2.imread(str(samples/'circle-outliers.png'),0);r=run(image)['result']
        self.assertTrue(r['passed'],r);self.assertGreater(r['rejectedCount'],3);self.assertAlmostEqual(r['radiusPixels'],80.4,delta=.15);self.assertEqual(sum(row['valid'] and not row['inlier'] for row in r['items']),r['rejectedCount'])
        stricter=run(image,minimumValidRatio=.99)['result'];self.assertTrue(stricter['found']);self.assertFalse(stricter['passed'])
        r=run(cv2.imread(str(samples/'circle-occluded.png'),0))['result'];self.assertTrue(r['passed'],r);self.assertGreater(r['missingCount'],5)

    def test_partial_arc_and_insufficient_coverage(self):
        r=run(startAngle=350,arcSpan=140,minimumCoverage=100)['result'];self.assertTrue(r['passed'],r);self.assertAlmostEqual(r['radiusPixels'],80.4,delta=.25)
        image=cv2.imread(str(samples/'circle-hole.png'),0);y,x=np.mgrid[:480,:640];angles=np.mod(np.degrees(np.arctan2(y-240,x-320)),360);image[(angles>80)&(angles<360)]=20
        r=run(image,minimumCoverage=200,minimumValidRatio=.1)['result'];self.assertFalse(r['found']);self.assertNotIn('circle',r)

    def test_noise_and_oversized_diameter(self):
        original=cv2.imread(str(samples/'circle-hole.png'),0);noise=np.random.default_rng(5).normal(0,3,original.shape);r=run(np.clip(original.astype(float)+noise,0,255).astype(np.uint8))['result'];self.assertTrue(r['passed'],r);self.assertAlmostEqual(r['diameterPixels'],160.8,delta=.3)
        r=run(cv2.imread(str(samples/'circle-oversize.png'),0),minimumDiameter=160,maximumDiameter=162)['result'];self.assertTrue(r['found']);self.assertFalse(r['passed']);self.assertAlmostEqual(r['diameterPixels'],170.4,delta=.2)

    def test_noncircular_contour_fails_quality(self):
        y,x=np.mgrid[:480,:640];d=np.hypot(x-320,y-240);a=np.arctan2(y-240,x-320);radius=80+3*np.cos(2*a);image=20+210*.5*(1+np.tanh((radius-d)/1.5))
        r=run(np.rint(image).astype(np.uint8))['result'];self.assertFalse(r['passed'])

    def test_numeric_fit_large_offset_degeneracy_and_minimum_points(self):
        angles=np.linspace(0,2*np.pi,90,endpoint=False);points=np.column_stack((1e5+80*np.cos(angles),2e5+80*np.sin(angles)))
        fitted=c.fit_circle(points,.1,60,100);self.assertIsNotNone(fitted);self.assertTrue(np.allclose(fitted[0],[1e5,2e5,80],atol=1e-6))
        self.assertIsNone(c.fit_circle(points[:5],.1,60,100));self.assertIsNone(c.fit_circle(np.column_stack((np.arange(30),np.arange(30))),.1,60,100));self.assertIsNone(c.fit_circle(np.ones((30,2)),.1,60,100))

    def test_nested_distance_wall_extrema_and_noncontained(self):
        r=run(task='nested',innerCircle=model(80,321,240),outerCircle=model(120),maximumCenterDistance=2,minimumWall=38,maximumWall=42)['result'];self.assertTrue(r['passed']);self.assertEqual(r['centerDistancePixels'],1);self.assertEqual(r['minimumWall'],39);self.assertEqual(r['maximumWall'],41)
        r=run(task='nested',innerCircle=model(80,327,240),outerCircle=model(120))['result'];self.assertFalse(r['passed']);self.assertEqual(r['centerDistancePixels'],7)
        r=run(task='nested',innerCircle=model(80,365,240),outerCircle=model(120))['result'];self.assertFalse(r['nested']);self.assertFalse(r['passed']);self.assertNotIn('minimumWall',r)

    def test_model_image_space_and_units_rejected(self):
        for change in [dict(width=800),dict(imageSha256='b'*64),dict(unit='mm',unitsPerPixel=.1),dict(radiusPixels=130),dict(centerX=True),dict(imageSha256='invalid')]:
            with self.subTest(change=change),self.assertRaises(ValueError):run(task='nested',innerCircle={**model(),**change},outerCircle=model(120))

    def test_invalid_configuration(self):
        for change in [dict(probeCount=True),dict(probeCount=11),dict(searchLength=160),dict(sigma=5,searchLength=16),dict(expectedRadius=16000,probeCount=360,searchLength=2048,caliperWidth=51),dict(minimumDiameter=200,maximumDiameter=100),dict(arcSpan=120,minimumCoverage=240),dict(unit='px',unitsPerPixel=.1),dict(centerX=9999),dict(selection='bad'),dict(minimumGradient=float('nan'))]:
            with self.subTest(change=change),self.assertRaises(ValueError):run(**change)


if __name__=='__main__':unittest.main()
