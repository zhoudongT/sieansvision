import base64
import importlib.util
import json
from pathlib import Path
import unittest
import cv2
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
FOLDER=ROOT/'operator-plugins/sieans-planar'
SPEC=importlib.util.spec_from_file_location('planar',FOLDER/'planar.py')
MODULE=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(MODULE)
MANIFEST=json.loads((FOLDER/'operator-plugin.json').read_text(encoding='utf-8'))
H=np.array([[6,.8,100],[.3,5.5,80],[.004,.0015,1.]])
WORLD=np.array([[x,y] for y in (0,30,60) for x in (0,50,100)],dtype=float)
PIXELS=cv2.perspectiveTransform(WORLD.reshape(-1,1,2),H).reshape(-1,2)
ROWS=[dict(pixelX=float(p[0]),pixelY=float(p[1]),worldX=float(w[0]),worldY=float(w[1])) for p,w in zip(PIXELS,WORLD)]


def run(task,image='',**overrides):
    op=next(o for o in MANIFEST['operators'] if o['id']==task)
    params={f['key']:f['default'] for f in op['parameters']};params.update(overrides)
    return MODULE.run(dict(params=params,image=image))


def pixels(world):
    values=cv2.perspectiveTransform(np.asarray(world,dtype=float).reshape(-1,1,2),H).reshape(-1,2)
    return [dict(x=float(p[0]),y=float(p[1])) for p in values]


def image(width=720,height=480):
    return 'data:image/png;base64,'+base64.b64encode(cv2.imencode('.png',np.zeros((height,width,3),np.uint8))[1]).decode()


class PlanarTests(unittest.TestCase):
    def calibration(self,**p): return run('calibrate',points=ROWS,**p)['result']['calibration']

    def test_perspective_calibration_maps_independent_points(self):
        out=run('calibrate',points=ROWS)['result']
        self.assertEqual((out['inlierCount'],out['rejectedCount']),(9,0))
        self.assertLess(out['rmsErrorPixels'],.0001)
        expected=[[20,15],[80,15]]
        result=run('measure',calibration=out['calibration'],points=pixels(expected))['result']
        self.assertAlmostEqual(result['length'],60,places=4)
        np.testing.assert_allclose([[p['worldX'],p['worldY']] for p in result['points']],expected,atol=.0001)
        self.assertAlmostEqual(result['items'][0]['angleDegrees'],0,places=4)

    def test_closed_perimeter_and_units(self):
        for unit in ('mm','cm','m'):
            result=run('measure',calibration=self.calibration(unit=unit),points=pixels([[20,15],[80,15],[80,45],[20,45]]),closed=True)['result']
            self.assertEqual(result['unit'],unit)
            self.assertEqual(result['segmentCount'],4)
            self.assertAlmostEqual(result['length'],180,places=4)
        with self.assertRaisesRegex(ValueError,'至少 3'): run('measure',calibration=self.calibration(),points=pixels([[20,15],[80,15]]),closed=True)

    def test_ransac_rejects_mismatched_point_and_preserves_error_rows(self):
        rows=[dict(row) for row in ROWS];rows[4]['pixelX']+=60;rows[4]['pixelY']-=40
        result=run('calibrate',points=rows)['result']
        self.assertEqual((result['inlierCount'],result['rejectedCount']),(8,1))
        self.assertFalse(result['items'][4]['inlier'])
        self.assertGreater(result['items'][4]['errorPixels'],70)
        with self.assertRaisesRegex(ValueError,'有效标定点不足'): run('calibrate',points=rows,minimumInlierRatio=1)
        with self.assertRaisesRegex(ValueError,'误差'): run('calibrate',points=rows,method='all',maximumRmsError=.01)

    def test_duplicate_collinear_and_invalid_coordinates(self):
        duplicate=[dict(row) for row in ROWS];duplicate[1]=dict(duplicate[0])
        line=[dict(pixelX=i*10,pixelY=i*20,worldX=i,worldY=i*2) for i in range(4)]
        invalid=[dict(row) for row in ROWS];invalid[0]['pixelX']=True
        for rows in (duplicate,line,invalid,ROWS[:3]):
            with self.subTest(rows=rows),self.assertRaises(ValueError): run('calibrate',points=rows)

    def test_extrapolation_is_explicit(self):
        params=dict(calibration=self.calibration(),points=pixels([[-20,15],[20,15]]))
        with self.assertRaisesRegex(ValueError,'超出标定'): run('measure',**params)
        result=run('measure',**params,allowExtrapolation=True)['result']
        self.assertTrue(result['extrapolated']);self.assertFalse(result['points'][0]['insideCalibration'])
        self.assertAlmostEqual(result['length'],40,places=4)

    def test_image_size_and_coordinates_guard_calibration_reuse(self):
        result=run('calibrate',points=ROWS,image=image())
        self.assertIn('image',result)
        cal=result['result']['calibration']
        with self.assertRaisesRegex(ValueError,'尺寸与标定'): run('measure',calibration=cal,points=pixels([[20,15],[30,15]]),image=image(700))
        with self.assertRaisesRegex(ValueError,'超出输入图像'): run('calibrate',points=ROWS,image=image(200))
        out=run('measure',calibration=cal,points=pixels([[20,15],[80,15]]),image=image())
        annotated=cv2.imdecode(np.frombuffer(base64.b64decode(out['image'].split(',')[1]),np.uint8),1)
        self.assertEqual(annotated.shape,(480,720,3));self.assertGreater(np.count_nonzero(annotated),100)

    def test_singular_calibration_infinite_line_and_wrong_model(self):
        cal=self.calibration();cal['matrix']=[[1,0,0],[0,0,0],[0,0,1]]
        with self.assertRaisesRegex(ValueError,'奇异'): run('measure',calibration=cal)
        cal=self.calibration();cal['matrix']=[[1,0,0],[0,1,0],[1,0,-5]]
        with self.assertRaisesRegex(ValueError,'无穷线'): run('measure',calibration=cal,points=[dict(x=4,y=1),dict(x=6,y=1)],allowExtrapolation=True)
        with self.assertRaisesRegex(ValueError,'无穷线'): run('measure',calibration=cal,points=[dict(x=5,y=1),dict(x=6,y=1)],allowExtrapolation=True)
        with self.assertRaisesRegex(ValueError,'完整标定结果'): run('measure',calibration={})

    def test_homography_scale_does_not_change_mapping(self):
        cal=self.calibration();cal['matrix']=(np.asarray(cal['matrix'])*1e-15).tolist()
        result=run('measure',calibration=cal,points=pixels([[20,15],[80,15]]))['result']
        self.assertAlmostEqual(result['length'],60,places=4)


if __name__=='__main__': unittest.main()
