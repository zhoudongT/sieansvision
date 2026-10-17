import base64
import importlib.util
import json
from pathlib import Path
import unittest
import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT/'operator-plugins/sieans-caliper'
SPEC = importlib.util.spec_from_file_location('caliper', FOLDER/'caliper.py')
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
MANIFEST = json.loads((FOLDER/'operator-plugin.json').read_text(encoding='utf-8'))


def encode(image):
    return 'data:image/png;base64,' + base64.b64encode(cv2.imencode('.png', image)[1]).decode()


def scene(task='line', angle=0, offset=1.35, width=80.4, dark=False, noise=0, outlier=False):
    y, x = np.mgrid[:480, :640]
    radians = np.deg2rad(angle)
    distance = (x-320)*np.cos(radians) + (y-240)*np.sin(radians) - offset
    if outlier:
        distance = distance - np.where(y > 330, 15, 0)
    ramp = lambda a: .5*(1+np.tanh(a/1.5))
    intensity = ramp(distance) if task == 'line' else ramp(distance+width/2)-ramp(distance-width/2)
    if dark:
        intensity = 1-intensity
    image = 20+210*intensity
    if noise:
        image += np.random.default_rng(42).normal(0, noise, image.shape)
    return np.clip(np.rint(image), 0, 255).astype(np.uint8)


def run(task, image, **params):
    op = next(o for o in MANIFEST['operators'] if o['id'] == 'edge-'+task)
    args = {p['key']:p['default'] for p in op['parameters']}
    args.update(params)
    return MODULE.run(dict(params=args, image=encode(image)))


class CaliperTests(unittest.TestCase):
    def test_fractional_edge_coordinates_at_several_orientations(self):
        for angle in (0, 27, 90, -45, 180):
            with self.subTest(angle=angle):
                result = run('line', scene(angle=angle), scanAngle=angle)['result']
                self.assertTrue(result['passed'])
                self.assertEqual(result['inlierCount'], 15)
                normal = np.array([np.cos(np.deg2rad(angle)), np.sin(np.deg2rad(angle))])
                for row in result['items']:
                    distance = (np.array([row['edgeX'], row['edgeY']])-[320,240]) @ normal
                    self.assertAlmostEqual(distance, 1.35, delta=.15)
                self.assertLess(result['rmsPixels'], .1)

    def test_bright_dark_and_reverse_scan_widths(self):
        for angle, scan_angle, dark in ((0,0,False),(28,28,False),(28,-152,False),(-35,-35,True),(90,90,True)):
            with self.subTest(angle=angle,scan=scan_angle,dark=dark):
                result = run('width', scene('width',angle=angle,dark=dark), scanAngle=scan_angle,bandPolarity='dark' if dark else 'bright',unitsPerPixel=.1,unit='mm',minimumWidth=8,maximumWidth=8.1)['result']
                self.assertTrue(result['passed'], result)
                self.assertEqual(result['detectedCount'],15)
                self.assertAlmostEqual(result['meanWidth'],8.04,delta=.015)
                self.assertEqual(result['unit'],'mm')

    def test_polarity_and_first_last_selection(self):
        image=scene('width',width=80)
        first=run('line',image,polarity='either',selection='first')['result']
        last=run('line',image,polarity='either',selection='last')['result']
        self.assertAlmostEqual(last['line']['x']-first['line']['x'],80,delta=.15)
        wrong=run('line',scene(),polarity='falling')['result']
        self.assertFalse(wrong['found']);self.assertFalse(wrong['passed'])
        reversed_line=run('line',scene(),scanAngle=180,polarity='falling')['result']
        self.assertTrue(reversed_line['passed'])

    def test_uniform_no_edge_and_border_do_not_report_zero_measurements(self):
        for task in ('line','width'):
            for image,params in [(np.full((480,640),100,np.uint8),{}),(scene(task),dict(centerX=40))]:
                result=run(task,image,**params)['result']
                self.assertFalse(result['found']);self.assertFalse(result['passed'])
                self.assertEqual(result['detectedCount'],0)
                self.assertNotIn('meanWidth',result);self.assertNotIn('rmsPixels',result)
                self.assertTrue(all(not r['valid'] and r['reason'] for r in result['items']))
        result=run('line',scene(offset=78))['result']
        self.assertFalse(result['found'])

    def test_partial_coverage_and_width_tolerance_are_independent(self):
        result=run('width',scene('width'),centerY=30)['result']
        self.assertTrue(result['found']);self.assertFalse(result['passed'])
        self.assertGreater(result['missingCount'],0)
        accepted=run('width',scene('width'),centerY=30,minimumValidRatio=.4)['result']
        self.assertTrue(accepted['passed'])
        rejected=run('width',scene('width',width=86),minimumWidth=78,maximumWidth=82)['result']
        self.assertEqual(rejected['detectedCount'],15);self.assertFalse(rejected['passed'])
        self.assertEqual(rejected['outOfToleranceCount'],15)

    def test_noise_and_outliers_leave_diagnostics(self):
        result=run('line',scene(noise=3,outlier=True),minimumValidRatio=.8)['result']
        self.assertTrue(result['passed'],result)
        self.assertEqual(result['detectedCount'],15)
        self.assertEqual(result['inlierCount'],13)
        self.assertTrue(all(r.get('residualPixels',0)>10 for r in result['items'] if not r['inlier']))
        self.assertAlmostEqual(result['line']['x'],321.35,delta=.15)

    def test_invalid_configuration_is_rejected(self):
        cases=[('line',dict(probeCount=True)),('line',dict(probeCount=2)),('line',dict(centerX=640)),('line',dict(sigma=5,searchLength=16)),('line',dict(probeCount=100,caliperWidth=51,searchLength=2048)),('width',dict(minimumWidth=100,maximumWidth=1)),('width',dict(maximumSeparation=200)),('width',dict(unitsPerPixel=.1)),('line',dict(polarity='bad'))]
        for task,params in cases:
            with self.subTest(params=params),self.assertRaises(ValueError):
                run(task,scene(task),**params)

    def test_annotation_is_separate_and_all_results_are_finite(self):
        image=scene('width');out=run('width',image)
        self.assertNotIn('image',out)
        overlay=cv2.imdecode(np.frombuffer(base64.b64decode(out['annotatedImage'].split(',')[1]),np.uint8),1)
        self.assertEqual(overlay.shape,(480,640,3))
        self.assertGreater(np.count_nonzero(overlay[:,:,0]!=overlay[:,:,1]),100)
        json.dumps(out['result'],allow_nan=False)


if __name__ == '__main__':
    unittest.main()
