import base64
import copy
import importlib.util
import json
from pathlib import Path
import sys
import unittest
import cv2
import numpy as np

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'vision'))
import template_matching as matcher
from engine import run as engine_run
spec=importlib.util.spec_from_file_location('fixture',ROOT/'operator-plugins/sieans-fixture/fixture.py');f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
manifest=json.loads((ROOT/'operator-plugins/sieans-fixture/operator-plugin.json').read_text(encoding='utf-8'));samples=ROOT/'public/vision/samples'
def encode(image):return 'data:image/png;base64,'+base64.b64encode(cv2.imencode('.png',image)[1]).decode()
def image(name):return cv2.imread(str(samples/(name+'.png')))
def locate(scene='fixture-rotated',**overrides):
    p=dict(minScore=.94,angleStart=-30,angleEnd=30,angleStep=30,scales=[.8,1,1.2],maxMatches=5);p.update(overrides)
    return engine_run(dict(operation='locate',image=encode(image(scene)),reference=encode(image('fixture-template')),params=p))['result']
def follow(task,pose,source=None,**overrides):
    op=next(op for op in manifest['operators'] if op['id']==task);p={field['key']:copy.deepcopy(field['default']) for field in op['parameters']};p.update(pose=pose,**overrides)
    return f.run(dict(params=p,image=encode(source) if source is not None else ''))


class FixtureTests(unittest.TestCase):
    def test_multi_rotation_scale_positions_and_polygon_nms(self):
        result=locate('fixture-multiple');self.assertEqual(result['count'],3,result);self.assertFalse(result['unique']);self.assertFalse(result['limitReached'])
        expected=json.loads((samples/'fixture-truth.json').read_text())['fixture-multiple']
        for x,y,angle,scale in expected:
            found=min(result['items'],key=lambda item:(item['centerX']-x)**2+(item['centerY']-y)**2)
            self.assertLess(np.linalg.norm(np.array(found['center'])-[x,y]),1.1);self.assertEqual(found['angleDeg'],angle);self.assertEqual(found['scale'],scale)
        self.assertEqual(result['items'],sorted(result['items'],key=lambda item:-item['score']))

    def test_single_unique_pose_and_independent_point_ground_truth(self):
        result=locate();self.assertTrue(result['unique']);self.assertEqual(result['count'],1);pose=result['pose'];point=np.array([26,30]);expected=cv2.getRotationMatrix2D((39.5,31.5),30,1.2);expected[:,2]+=[200.5,148.5]
        r=follow('points',pose,image('fixture-rotated'),points=[dict(x=26,y=30)])['result'];actual=np.array([r['items'][0]['targetX'],r['items'][0]['targetY']]);self.assertLess(np.linalg.norm(actual-(expected[:,:2]@point+expected[:,2])),1.1)
        back=follow('points',pose,direction='image-to-template',points=[dict(x=float(actual[0]),y=float(actual[1]))])['result']['items'][0];self.assertAlmostEqual(back['targetX'],26);self.assertAlmostEqual(back['targetY'],30)

    def test_rectification_preserves_features_and_exposes_new_frame(self):
        pose=locate()['pose'];out=follow('rectify',pose,image('fixture-rotated'),cropX=12,cropY=12,cropWidth=56,cropHeight=40)
        corrected=cv2.imdecode(np.frombuffer(base64.b64decode(out['image'].split(',')[1]),np.uint8),cv2.IMREAD_COLOR);self.assertEqual(corrected.shape,(40,56,3));self.assertEqual(out['image'],out['annotatedImage'])
        template=image('fixture-template')[12:52,12:68];self.assertLess(float(np.mean(np.abs(corrected.astype(float)-template.astype(float)))),10)
        _,binary=cv2.threshold(cv2.cvtColor(corrected,cv2.COLOR_BGR2GRAY),100,255,cv2.THRESH_BINARY_INV);count,_,stats,centers=cv2.connectedComponentsWithStats(binary)
        holes=[centers[i] for i in range(1,count) if 30<=stats[i,cv2.CC_STAT_AREA]<=500];self.assertEqual(len(holes),2);self.assertLess(min(np.linalg.norm(p-[14,18]) for p in holes),1.5)
        with self.assertRaisesRegex(ValueError,'不一致'):follow('rectify',pose,corrected)

    def test_roi_offsets_apply_to_pose_and_coordinates(self):
        result=locate(roi=[150,100,200,180]);self.assertTrue(result['unique']);self.assertLess(np.linalg.norm(np.array(result['center'])-[240,180]),1.1)
        r=follow('points',result['pose'],image('fixture-rotated'),points=[dict(x=39.5,y=31.5)])['result']['items'][0];self.assertAlmostEqual(r['targetX'],result['centerX']);self.assertAlmostEqual(r['targetY'],result['centerY'])

    def test_maximum_limit_and_no_match_do_not_claim_unique(self):
        result=locate('fixture-multiple',maxMatches=1);self.assertEqual(result['count'],1);self.assertTrue(result['limitReached']);self.assertFalse(result['unique'])
        result=locate('fixture-blank');self.assertFalse(result['found']);self.assertEqual(result['items'],[]);self.assertNotIn('pose',result);self.assertNotIn('center',result)

    def test_duplicate_scales_and_angles_do_not_duplicate_object(self):
        r=locate(scales=[1.2,1.2,1.2],angleStart=25,angleEnd=35,angleStep=5,minScore=.9);self.assertEqual(r['count'],1);self.assertTrue(r['unique']);self.assertEqual(r['searchedVariants'],3)

    def test_stale_image_and_invalid_pose_rejected(self):
        pose=locate()['pose']
        with self.assertRaisesRegex(ValueError,'同一帧'):follow('points',pose,image('fixture-blank'))
        for mutate in [lambda p:p['matrix'][0].__setitem__(0,2),lambda p:p['inverse'][0].__setitem__(2,999),lambda p:p.update(scale=True),lambda p:p.update(format='unknown'),lambda p:p.update(sourcePixelSha256='x')]:
            bad=copy.deepcopy(pose);mutate(bad)
            with self.assertRaises(ValueError):follow('points',bad)

    def test_outside_points_flagged_and_outside_image_crop_rejected(self):
        pose=locate()['pose'];out=follow('points',pose,points=[dict(x=10000,y=10000)])['result'];self.assertFalse(out['passed']);self.assertEqual(out['outsideCount'],1)
        with self.assertRaisesRegex(ValueError,'超出原图'):follow('rectify',pose,image('fixture-rotated'),cropX=-300,cropY=-300,cropWidth=80,cropHeight=64)
        with self.assertRaises(ValueError):follow('points',pose,points=[dict(x=True,y=0)])

    def test_resource_limits_and_invalid_search_parameters(self):
        for change in [dict(angleStart=-180,angleEnd=180,angleStep=1),dict(maxMatches=True),dict(maxMatches=0),dict(overlapThreshold=0),dict(scales=[True]),dict(angleStart=30,angleEnd=-30),dict(origin=[False,0])]:
            with self.subTest(change=change),self.assertRaises(ValueError):locate(**change)
        canvas=np.zeros((2000,2000,3),np.uint8)
        with self.assertRaisesRegex(ValueError,'3000 万'):matcher.locate(canvas,canvas.copy(),dict(angleStart=-40,angleEnd=40,angleStep=10),[0,0],image('fixture-template'))


if __name__=='__main__':unittest.main()
