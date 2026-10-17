import base64
import importlib.util
import json
from pathlib import Path
import unittest
import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def operator(package, name, **overrides):
    folder = ROOT / 'operator-plugins' / package
    manifest = json.loads((folder / 'operator-plugin.json').read_text(encoding='utf-8'))
    definition = next(op for op in manifest['operators'] if op['id'] == name)
    params = {field['key']: field['default'] for field in definition['parameters']}
    params.update(overrides)
    spec = importlib.util.spec_from_file_location(package, folder / definition['entry'])
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.run, params


def image_run(image, op='blobs', **params):
    run, values = operator('sieans-regions', op, **params)
    data = base64.b64encode(cv2.imencode('.png', image)[1]).decode()
    return run(dict(image='data:image/png;base64,'+data, params=values))


def cloud_run(points, unit='mm', **params):
    run, values = operator('sieans-surface', 'plane-distance', **params)
    return run(dict(cloud=dict(points=points, unit=unit, frame='test'), params=values))


class RegionTests(unittest.TestCase):
    def test_hue_wrap_rejects_green_and_gray(self):
        hsv = np.array([[[2,255,255],[178,255,255],[60,255,255],[2,0,255]]], dtype=np.uint8)
        image = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
        r = image_run(image, 'color', minimumArea=1)['result']
        self.assertEqual((r['count'],r['areaPixels'],r['coveragePercent']), (1,2,50))
        r = image_run(image, 'color', minimumArea=1,hueMin=50,hueMax=70)['result']
        self.assertEqual(r['areaPixels'],1)

    def test_pixel_area_includes_holes_correctly_and_centroid_is_global(self):
        image = np.zeros((12,14), np.uint8)
        image[4:8,6:10] = 255
        image[5:7,7:9] = 0
        result = image_run(image,roiX=5,roiY=3,roiWidth=6,roiHeight=6)['result']
        self.assertEqual(result['areaPixels'],12)
        item = result['items'][0]
        self.assertEqual((item['x'],item['y'],item['width'],item['height']), (6,4,4,4))
        self.assertEqual((item['centerX'],item['centerY'],item['fillRatio']), (7.5,5.5,.75))

    def test_connectivity_border_and_count_failure(self):
        image = np.eye(3,dtype=np.uint8)*255
        self.assertEqual(image_run(image,minimumArea=1,connectivity=4)['result']['count'],3)
        self.assertEqual(image_run(image,minimumArea=1,connectivity=8)['result']['count'],1)
        result = image_run(image,minimumArea=1,connectivity=4,excludeBorder=True,minimumCount=2)['result']
        self.assertEqual(result['count'],1)
        self.assertFalse(result['passed'])

    def test_threshold_boundary_and_area_limits(self):
        image = np.array([[127,128],[0,255]],dtype=np.uint8)
        bright = image_run(image,minimumArea=1,threshold=127)['result']
        dark = image_run(image,minimumArea=1,threshold=127,polarity='dark')['result']
        self.assertEqual((bright['areaPixels'],dark['areaPixels']), (2,2))
        self.assertEqual(image_run(image,minimumArea=3)['result']['count'],0)

    def test_morphology_and_output_mask_pipeline(self):
        image = np.zeros((10,10),np.uint8)
        image[2:5,2:5] = 255
        image[7,7] = 255
        output = image_run(image,minimumArea=1,morphology='open',outputImage='mask')
        self.assertEqual(output['result']['areaPixels'],9)
        mask = cv2.imdecode(np.frombuffer(base64.b64decode(output['image'].split(',')[1]),np.uint8),0)
        self.assertEqual(np.count_nonzero(mask),9)
        self.assertEqual(image_run(mask,minimumArea=1)['result']['count'],1)
        self.assertNotIn('image',image_run(image,outputImage='original'))

    def test_reject_inconsistent_ranges_invalid_roi_and_kernel(self):
        image = np.zeros((10,10),np.uint8)
        for params in [dict(roiX=10),dict(roiWidth=11),dict(minimumArea=50,maximumArea=10),dict(minimumCount=2,maximumCount=1),dict(kernelSize=2)]:
            with self.subTest(params=params),self.assertRaises(ValueError):
                image_run(image,**params)
        with self.assertRaises(ValueError):
            image_run(image,'color',saturationMin=200,saturationMax=100)

    def test_detail_limit_does_not_change_count_or_total_area(self):
        image = np.zeros((50,50),np.uint8)
        image[::2,::2] = 255
        r = image_run(image,minimumArea=1,maximumCount=700)['result']
        self.assertEqual((r['count'],r['areaPixels'],len(r['items'])), (625,625,500))
        self.assertTrue(r['detailsTruncated'])
        self.assertTrue(r['passed'])


class PlaneTests(unittest.TestCase):
    def test_reference_normalization_signed_distances_colors_and_metadata(self):
        points = [[0,0,9.7],[1,0,10],[0,1,10.5]]
        response = cloud_run(points, normalZ=2,planeOffset=-20)
        r = response['result']
        self.assertEqual(r['outsideCount'],2)
        self.assertAlmostEqual(r['minimumDistance'],-.3)
        self.assertAlmostEqual(r['maximumDistance'],.5)
        self.assertAlmostEqual(r['peakToValley'],.8)
        self.assertAlmostEqual(r['rmsDistance'],np.sqrt(.34/3))
        self.assertFalse(r['passed'])
        self.assertEqual(response['cloud']['points'],points)
        self.assertEqual(response['cloud']['frame'],'test')
        self.assertEqual(response['cloud']['colors'][1],[.1,.75,.4])

    def test_units_and_inclusive_tolerance_bounds(self):
        r = cloud_run([[0,0,-.1],[1,0,.1]],unit='m')['result']
        self.assertEqual(r['unit'],'m')
        self.assertEqual(r['outsideCount'],0)
        self.assertTrue(r['passed'])
        r = cloud_run([[0,0,.11],[0,1,0]],maximumOutsidePercent=50)['result']
        self.assertTrue(r['passed'])

    def test_tilted_least_squares_plane_has_zero_residual_and_stable_sign(self):
        points = [[x,y,2*x+3*y+5] for x in range(5) for y in range(5)]
        r = cloud_run(points,planeMode='fit',lowerDistance=0,upperDistance=0)['result']
        self.assertEqual(r['outsideCount'],0)
        self.assertLess(r['rmsDistance'],1e-12)
        np.testing.assert_allclose(r['plane'],np.array([2,3,-1,5])/np.sqrt(14),atol=1e-12)

    def test_plane_degeneracy_rejected(self):
        for points in [[[0,0,0],[1,1,1]],[[0,0,0],[1,1,1],[2,2,2]],[[0,0,0]]*3]:
            with self.assertRaises(ValueError):
                cloud_run(points,planeMode='fit')
        with self.assertRaises(ValueError):
            cloud_run([[0,0,0]],normalZ=0)
        with self.assertRaises(ValueError):
            cloud_run([[0,0,0]],lowerDistance=1,upperDistance=-1)

    def test_large_cloud_requires_explicit_uncolored_mode_and_retains_full_counts(self):
        points = [[0,0,1]]*10001
        with self.assertRaises(ValueError):
            cloud_run(points)
        response = cloud_run(points,colorize=False)
        self.assertEqual(response['result']['outsideCount'],10001)
        self.assertEqual(len(response['result']['items']),500)
        self.assertTrue(response['result']['detailsTruncated'])
        self.assertNotIn('cloud',response)


if __name__ == '__main__':
    unittest.main()
