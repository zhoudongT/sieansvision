import base64
import copy
import importlib.util
import json
from pathlib import Path
import unittest
import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT/'operator-plugins/sieans-shape'
spec = importlib.util.spec_from_file_location('shape', FOLDER/'shape.py')
shape = importlib.util.module_from_spec(spec)
spec.loader.exec_module(shape)
manifest = json.loads((FOLDER/'operator-plugin.json').read_text(encoding='utf-8'))
spec = importlib.util.spec_from_file_location('shape_samples', ROOT/'scripts/generate-shape-samples.py')
samples = importlib.util.module_from_spec(spec)
spec.loader.exec_module(samples)


def encode(image): return 'data:image/png;base64,'+base64.b64encode(cv2.imencode('.png', image)[1]).decode()


def run(image, task='teach', **args):
    op = next(o for o in manifest['operators'] if o['id'] == task)
    params = {f['key']: copy.deepcopy(f['default']) for f in op['parameters']}
    params.update(args)
    return shape.run(dict(params=params, image=encode(image)))


def teach(image=None):
    return run(samples.scene('multi') if image is None else image, roiX=20, roiY=20, roiWidth=130, roiHeight=170)['result']['model']


class ShapeTests(unittest.TestCase):
    def test_multi_rotation_scale_and_distractor(self):
        image = samples.scene('multi')
        out = run(image, 'match', model=teach(), roiX=200, minimumCount=3, maximumCount=3)
        r = out['result']
        self.assertEqual(r['candidateCount'], 4)
        self.assertEqual(r['count'], 3)
        self.assertTrue(r['passed'])
        self.assertTrue(all(row['huDifference'] < .08 for row in r['items'] if row['matched']))
        self.assertEqual(sorted(round(row['areaScale'], 1) for row in r['items'] if row['matched']), [.8, 1.0, 1.2])
        centers = [(row['centerX'], row['centerY']) for row in r['items']]
        self.assertTrue(all(x > 200 and 0 < y < 480 for x, y in centers))
        self.assertNotIn('image', out)
        self.assertTrue(out['annotatedImage'].startswith('data:image/jpeg;base64,'))
        self.assertNotIn('pose', r)

    def test_model_reused_on_new_image_with_translation_and_holes(self):
        image = np.full((480, 640), 20, np.uint8)
        samples.target(image, [350, 250], 35, 1)
        r = run(image, 'match', model=teach())['result']
        self.assertTrue(r['passed'])
        self.assertEqual(r['count'], 1)
        self.assertEqual(r['items'][0]['holeCount'], 1)
        self.assertEqual(r['items'][0]['longSidePixels'] > 90, True)
        # The reported center is the outer polygon moment, not the drawing anchor or net material centroid.
        c = np.array(teach()['contour'], np.int32).reshape(-1, 1, 2)
        self.assertGreater(cv2.contourArea(c), 5000)

    def test_missing_and_wrong_size_holes_are_rejected(self):
        model = teach()
        image = samples.scene('hole-missing')
        r = run(image, 'match', model=model, roiX=200)['result']
        self.assertFalse(r['found'])
        self.assertIn('孔洞', r['items'][0]['reason'])
        self.assertTrue(run(image, 'match', model=model, roiX=200, checkHoles=False)['result']['passed'])
        image = np.full((480, 640), 20, np.uint8)
        samples.target(image, [350, 250], 0, 1)
        cv2.circle(image, (330, 225), 14, 20, -1)
        r = run(image, 'match', model=model, maximumHoleRatioError=.005)['result']
        self.assertFalse(r['passed'])
        self.assertEqual(r['items'][0]['holeCount'], 1)

    def test_scale_and_unique_guards(self):
        image = samples.scene('multi')
        r = run(image, 'match', model=teach(), roiX=200)['result']
        self.assertTrue(r['found'])
        self.assertFalse(r['passed'])
        r = run(image, 'match', model=teach(), roiX=200, minimumScale=.9, maximumScale=1.1)['result']
        self.assertEqual(r['count'], 1)
        self.assertTrue(r['passed'])
        self.assertEqual(sum('比例超限' in row['reason'] for row in r['items']), 2)

    def test_no_target_and_touching_border(self):
        image = np.full((200, 200), 20, np.uint8)
        r = run(image, 'match', model=teach())['result']
        self.assertFalse(r['found'])
        self.assertFalse(r['passed'])
        self.assertEqual(r['items'], [])
        cv2.rectangle(image, (0, 50), (80, 150), 230, -1)
        r = run(image, 'match', model=teach())['result']
        self.assertEqual(r['boundaryRejectedCount'], 1)
        self.assertFalse(r['found'])
        with self.assertRaisesRegex(ValueError, '恰好'): run(image)

    def test_ambiguous_or_empty_teaching_fails(self):
        for image in [samples.scene('multi'), np.full((100, 100), 20, np.uint8)]:
            with self.assertRaisesRegex(ValueError, '恰好'): run(image)

    def test_dark_polarity_and_roi_coordinates(self):
        image = 255-samples.scene('multi')
        model = run(image, roiX=20, roiY=20, roiWidth=130, roiHeight=170, polarity='dark')['result']['model']
        r = run(image, 'match', model=model, polarity='dark', roiX=200, roiY=20, minimumCount=3, maximumCount=3)['result']
        self.assertEqual(r['count'], 3)
        self.assertTrue(r['passed'])

    def test_model_validation_and_complexity(self):
        for model in [{}, dict(kind='sieans-silhouette', version=1, contour=[[0, 0], [1, 1], [2, 2]], holes=[]), dict(kind='sieans-silhouette', version=True)]:
            with self.assertRaises(ValueError): run(samples.scene('multi'), 'match', model=model)
        model = teach()
        model['contour'][0][0] = float('nan')
        with self.assertRaisesRegex(ValueError, '坐标'): run(samples.scene('multi'), 'match', model=model)
        model = teach()
        model['holes'] = [[[1000, 1000], [1010, 1000], [1010, 1010]]]
        with self.assertRaisesRegex(ValueError, '内部'): run(samples.scene('multi'), 'match', model=model)
        model = teach()
        model['contour'] *= 4096
        with self.assertRaisesRegex(ValueError, '4096'): run(samples.scene('multi'), 'match', model=model)

    def test_roi_threshold_and_range_validation(self):
        for args in [dict(roiX=640), dict(roiWidth=700), dict(minimumArea=200, maximumArea=100), dict(threshold=True)]:
            with self.assertRaises(ValueError): run(samples.scene('multi'), **args)
        for args in [dict(minimumScale=2, maximumScale=1), dict(minimumCount=3, maximumCount=1), dict(checkHoles=1)]:
            with self.assertRaises(ValueError): run(samples.scene('multi'), 'match', model=teach(), **args)

    def test_too_many_candidates_fails_instead_of_partial_count(self):
        image = np.full((600, 600), 20, np.uint8)
        for y in range(10, 590, 35):
            for x in range(10, 590, 35): cv2.rectangle(image, (x, y), (x+20, y+20), 230, -1)
        with self.assertRaisesRegex(ValueError, '不返回不完整计数'): run(image, 'match', model=teach())


if __name__ == '__main__': unittest.main()
