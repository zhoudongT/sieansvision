import base64
import importlib.util
import json
from pathlib import Path
import sys
import unittest
import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('intrinsics', ROOT/'operator-plugins/sieans-intrinsics/intrinsics.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
manifest = json.loads((ROOT/'operator-plugins/sieans-intrinsics/operator-plugin.json').read_text(encoding='utf-8'))
demos = json.loads((ROOT/'public/vision/samples/demos-intrinsics.json').read_text(encoding='utf-8'))


def run(task, image=None, **overrides):
    definition = next(op for op in manifest['operators'] if op['id'] == task)
    params = {f['key']: f['default'] for f in definition['parameters']}
    params.update(overrides)
    return module.run(dict(params=params, image=image))


def fixture(name):
    return 'data:image/png;base64,'+base64.b64encode((ROOT/'public/vision/samples'/name).read_bytes()).decode()


def points():
    return json.loads(json.dumps(demos[1]['steps'][0]['params']['arguments']['points']))


class IntrinsicsTests(unittest.TestCase):
    def test_known_intrinsics_and_distortion_recovered(self):
        result = run('calibrate', points=points())['result']
        c = result['calibration']
        for key, expected, tolerance in [('fx',710,.1),('fy',725,.1),('cx',320,.1),('cy',240,.1),('k1',-.12,.001),('k2',.035,.005),('p1',.001,.0001),('p2',-.002,.0001)]:
            self.assertAlmostEqual(c[key], expected, delta=tolerance)
        self.assertLess(result['rmsPixels'], .001)
        self.assertEqual(result['viewCount'], 8)
        self.assertEqual(len(result['items']), 8)

    def test_corner_collection_and_duplicate_id(self):
        image = fixture('intrinsics-board.png')
        out = run('corners', image)['result']
        self.assertEqual(out['cornerCount'], 54)
        self.assertEqual(out['viewCount'], 1)
        self.assertEqual(len(out['points']), 54)
        next_view = run('corners', image, view=2, points=out['points'])['result']
        self.assertEqual(next_view['viewCount'], 2)
        with self.assertRaisesRegex(ValueError, '编号已存在'):
            run('corners', image, points=out['points'])
        with self.assertRaisesRegex(ValueError, '未找到'):
            run('corners', fixture('intrinsics-grid.png'))

    def test_undistort_pixel_reference_and_image_channel(self):
        c = run('calibrate', points=points())['result']['calibration']
        image = fixture('intrinsics-grid.png')
        result = run('undistort', image, calibration=c)
        source = module.image_from(dict(image=image))
        k, d = module.model(c, 640, 480)
        expected = cv2.undistort(source, k, d, None, k)
        actual = module.image_from(result)
        np.testing.assert_array_equal(actual, expected)
        self.assertFalse(np.array_equal(actual, source))
        self.assertEqual(actual.shape, source.shape)
        self.assertEqual(result['result']['calibration']['k1'], 0)
        self.assertEqual(c['k1'] == 0, False)
        with self.assertRaisesRegex(ValueError, '尺寸'):
            run('undistort', image, calibration={**c, 'width':800})

    def test_partial_duplicate_nonfinite_and_mixed_size_rejected(self):
        table = points()
        for bad in [table[:-1],table+[table[0]]]:
            with self.assertRaises(ValueError): run('calibrate',points=bad)
        for key, value in [('x',float('nan')),('view',True),('width',800),('column',1.5),('y',480)]:
            bad = points();bad[0][key]=value
            with self.assertRaises(ValueError):run('calibrate',points=bad)
        with self.assertRaises(ValueError):run('corners',fixture('intrinsics-board.png'),points=[{**p,'width':800} for p in table[:54]])

    def test_too_few_and_identical_views_rejected(self):
        with self.assertRaisesRegex(ValueError,'至少需要'):
            run('calibrate',points=points()[:54*5])
        first=points()[:54]
        repeated=[{**row,'view':i} for i in range(1,9) for row in first]
        with self.assertRaisesRegex(ValueError,'姿态退化'):
            run('calibrate',points=repeated)

    def test_bad_correspondence_exceeds_quality_limit(self):
        bad=points();bad[0]['x']+=20
        with self.assertRaisesRegex(ValueError,'误差超限'):
            run('calibrate',points=bad,maxRms=.1)

    def test_model_contract_is_strict(self):
        c=run('calibrate',points=points())['result']['calibration']
        for bad in [{},{**c,'fx':0},{**c,'k1':float('nan')},{**c,'model':'fisheye'},{**c,'cx':900}]:
            with self.assertRaises(ValueError):run('undistort',fixture('intrinsics-grid.png'),calibration=bad)

    def test_rasterized_views_detect_then_calibrate_end_to_end(self):
        k=np.array([[710.,0,320],[0,725.,240],[0,0,1]])
        accumulated=[]
        rotations=[[.25,.15,0],[-.3,.2,.1],[.15,-.3,-.1],[-.2,-.2,.2],[.4,-.1,-.2],[-.1,.4,.05],[.3,.3,-.12],[-.25,.3,.15]]
        for i,rotation in enumerate(rotations):
            # Supersampled independent raster images exercise the detector rather
            # than feeding its expected corner coordinates into the solver.
            canvas=np.full((960,1280,3),180,np.uint8)
            for row in range(7):
                for col in range(10):
                    quad=np.array([[(col-1)*20,(row-1)*20,0],[col*20,(row-1)*20,0],[col*20,row*20,0],[(col-1)*20,row*20,0]],np.float64)
                    pixels,_=cv2.projectPoints(quad,np.array(rotation),np.array([-80.+i*2,-50.+i,530.+i*13]),k,np.zeros(5))
                    cv2.fillConvexPoly(canvas,np.round(pixels.reshape(-1,2)*2).astype(np.int32),(255,)*3 if (row+col)%2 else (0,)*3)
            canvas=cv2.resize(canvas,(640,480),interpolation=cv2.INTER_AREA)
            image='data:image/png;base64,'+base64.b64encode(cv2.imencode('.png',canvas)[1]).decode()
            accumulated=run('corners',image,view=i+1,points=accumulated)['result']['points']
        result=run('calibrate',points=accumulated,maxRms=1)['result']
        self.assertEqual(result['viewCount'],8)
        self.assertAlmostEqual(result['calibration']['fx'],710,delta=25)
        self.assertAlmostEqual(result['calibration']['fy'],725,delta=25)
        self.assertLess(result['rmsPixels'],.5)


if __name__=='__main__':unittest.main()
