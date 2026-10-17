import base64
import importlib.util
import json
import math
from pathlib import Path
import unittest
import cv2
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('handeye',ROOT/'operator-plugins/sieans-handeye/handeye.py');h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)
manifest=json.loads((ROOT/'operator-plugins/sieans-handeye/operator-plugin.json').read_text(encoding='utf-8'))
truth=json.loads((ROOT/'public/vision/samples/handeye-ground-truth.json').read_text())
clone=lambda value:json.loads(json.dumps(value))


def run(task,_image=None,**params):
    definition=next(op for op in manifest['operators'] if op['id']==task);defaults={f['key']:clone(f['default']) for f in definition['parameters']};defaults.update(params)
    image='data:image/png;base64,'+base64.b64encode((ROOT/'public/vision/samples/handeye-board.png').read_bytes()).decode()
    return h.run(dict(params=defaults,image=_image or image))


def fitted(**extra):return run('fit',poses=clone(truth['poses'][:8]),**extra)['result']


class HandeyeTests(unittest.TestCase):
    def test_known_eye_in_hand_and_three_independent_poses(self):
        result=fitted();m=result['calibration'];expected=np.array(truth['cameraToTool'])
        np.testing.assert_allclose(m['rotation'],expected[:3,:3],atol=1e-10);np.testing.assert_allclose(m['translation'],expected[:3,3],atol=1e-8)
        np.testing.assert_allclose(result['reference']['boardTranslation'],np.array(truth['boardToBase'])[:3,3],atol=1e-8)
        checked=run('check',calibration=m,reference=result['reference'],poses=clone(truth['poses'][8:]))['result'];self.assertTrue(checked['passed']);self.assertLess(checked['maximumTranslationError'],1e-8)

    def test_identity_handeye_is_not_mistaken_for_a_failed_solution(self):
        rows=clone(truth['poses'][:8]);board=np.array(truth['boardToBase'])
        for row in rows:
            c=np.eye(4);c[:3,:3]=cv2.Rodrigues(np.array([row['camera'+k] for k in ['Rx','Ry','Rz']]))[0];c[:3,3]=[row['camera'+k] for k in 'XYZ']
            g=board@np.linalg.inv(c);values=np.r_[g[:3,3],cv2.Rodrigues(g[:3,:3])[0].ravel()]
            for key,v in zip(['X','Y','Z','Rx','Ry','Rz'],values):row['robot'+key]=float(v)
        result=run('fit',poses=rows)['result']['calibration']
        np.testing.assert_allclose(result['rotation'],np.eye(3),atol=1e-10);np.testing.assert_allclose(result['translation'],np.zeros(3),atol=1e-8)

    def test_independent_errors_not_refitted_away(self):
        fit=fitted();rows=clone(truth['poses'][8:]);rows[0]['robotX']+=10
        result=run('check',calibration=fit['calibration'],reference=fit['reference'],poses=rows)['result']
        self.assertFalse(result['passed']);self.assertAlmostEqual(result['maximumTranslationError'],10,places=7)
        rows=clone(truth['poses'][:8]);rows[0]['cameraX']+=25
        with self.assertRaises(ValueError):run('fit',poses=rows)

    def test_mm_camera_and_m_robot_preserve_units_and_translation(self):
        rows=clone(truth['poses'])
        for row in rows:
            for part in 'XYZ':row['robot'+part]/=1000
        result=run('fit',poses=rows[:8],robotUnit='m')['result']
        np.testing.assert_allclose(result['calibration']['translation'],np.array(truth['cameraToTool'])[:3,3]/1000,atol=1e-10)
        self.assertEqual((result['calibration']['sourceUnit'],result['calibration']['targetUnit']),('mm','m'))
        check=run('check',calibration=result['calibration'],reference=result['reference'],poses=rows[8:])['result'];self.assertTrue(check['passed'])
        rows[8]['robotX']+=.01
        check=run('check',calibration=result['calibration'],reference=result['reference'],poses=rows[8:])['result'];self.assertFalse(check['passed']);self.assertAlmostEqual(check['maximumTranslationError'],.01,places=8)

    def test_explicit_zyx_degrees_robot_convention(self):
        rows=clone(truth['poses'][:8])
        for row in rows:
            r=cv2.Rodrigues(np.array([row['robot'+part] for part in ['Rx','Ry','Rz']]))[0]
            euler=[math.atan2(r[2,1],r[2,2]),math.asin(-r[2,0]),math.atan2(r[1,0],r[0,0])]
            for key,v in zip(['Rx','Ry','Rz'],np.degrees(euler)):row['robot'+key]=float(v)
        result=run('fit',poses=rows,robotRotation='euler-zyx-deg')['result']
        np.testing.assert_allclose(result['calibration']['translation'],np.array(truth['cameraToTool'])[:3,3],atol=1e-8)

    def test_motion_degeneracy_duplicate_direction_and_bad_types_rejected(self):
        rows=clone(truth['poses'][:8])
        for row in rows:
            for key in ['robotRx','robotRy','robotRz']:row[key]=0
        with self.assertRaisesRegex(ValueError,'激励不足'):run('fit',poses=rows)
        rows=clone(truth['poses'][:8]);rows[-1]=clone(rows[0])
        with self.assertRaisesRegex(ValueError,'重复'):run('fit',poses=rows)
        rows=clone(truth['poses'][:8]);rows[0]['cameraZ']=-1
        with self.assertRaisesRegex(ValueError,'正 Z'):run('fit',poses=rows)
        rows=clone(truth['poses'][:8]);rows[0]['cameraRx']=True
        with self.assertRaises(ValueError):run('fit',poses=rows)
        with self.assertRaises(ValueError):run('fit',poses=truth['poses'][:5])
        x=np.array(truth['cameraToTool']);board=np.array(truth['boardToBase']);parallel=[]
        for i in range(8):
            g=np.eye(4);g[:3,:3]=cv2.Rodrigues(np.array([0.,0.,i*.1]))[0];g[:3,3]=[100+i,0,200]
            c=np.linalg.inv(x)@np.linalg.inv(g)@board
            values=np.r_[g[:3,3],cv2.Rodrigues(g[:3,:3])[0].ravel(),c[:3,3],cv2.Rodrigues(c[:3,:3])[0].ravel()]
            parallel.append(dict(zip(['robot'+k for k in ['X','Y','Z','Rx','Ry','Rz']]+['camera'+k for k in ['X','Y','Z','Rx','Ry','Rz']],map(float,values))))
        with self.assertRaisesRegex(ValueError,'平行'):run('fit',poses=parallel)

    def test_pnp_detects_rasterized_chessboard_with_positive_depth(self):
        result=run('pose',intrinsics=truth['intrinsics'],reverseCorners=truth['reverseCorners'])
        self.assertEqual(result['result']['cornerCount'],54);self.assertLess(result['result']['rmsPixels'],.5)
        pose=result['result']['pose'];self.assertAlmostEqual(pose['z'],550,delta=10)
        self.assertAlmostEqual(pose['rx'],.25,delta=.03);self.assertAlmostEqual(pose['ry'],.15,delta=.03)
        self.assertTrue(result['annotatedImage'].startswith('data:image/jpeg;base64,'))
        reverse=run('pose',intrinsics=truth['intrinsics'],reverseCorners=not truth['reverseCorners'])['result']['pose']
        self.assertGreater(h.angle(cv2.Rodrigues(np.array([pose[k] for k in ['rx','ry','rz']]))[0]@cv2.Rodrigues(np.array([reverse[k] for k in ['rx','ry','rz']]))[0].T),170)

    def test_intrinsics_mismatch_and_wrong_reference_contracts_rejected(self):
        with self.assertRaisesRegex(ValueError,'尺寸'):run('pose',intrinsics={**truth['intrinsics'],'width':800})
        with self.assertRaises(ValueError):run('pose',intrinsics={})
        fit=fitted();bad={**fit['calibration'],'targetUnit':'m'}
        with self.assertRaisesRegex(ValueError,'不一致'):run('check',calibration=bad,reference=fit['reference'],poses=truth['poses'][8:])
        with self.assertRaises(ValueError):run('check',calibration=fit['calibration'],reference={},poses=truth['poses'][8:])
        with self.assertRaisesRegex(ValueError,'歧义'):run('pose',intrinsics=truth['intrinsics'],minimumAmbiguityGap=10)
        with self.assertRaisesRegex(ValueError,'重投影'):run('pose',intrinsics=truth['intrinsics'],maximumReprojectionError=.001)

    def test_raster_images_to_pnp_to_handeye_and_independent_validation(self):
        rows=clone(truth['poses']);intr=truth['intrinsics'];k=np.array([[intr['fx'],0,intr['cx']],[0,intr['fy'],intr['cy']],[0,0,1.]])
        for row in rows:
            rv=np.array([row['camera'+v] for v in ['Rx','Ry','Rz']]);t=np.array([row['camera'+v] for v in 'XYZ'])
            canvas=np.full((1920,2560,3),190,np.uint8)
            for j in range(7):
                for i in range(10):
                    quad=np.array([[(i-1)*20,(j-1)*20,0],[i*20,(j-1)*20,0],[i*20,j*20,0],[(i-1)*20,j*20,0]],np.float64)
                    projected=cv2.projectPoints(quad,rv,t,k,np.zeros(5))[0].reshape(-1,2)
                    cv2.fillConvexPoly(canvas,np.round(projected*4).astype(np.int32),(255,)*3 if (i+j)%2 else (0,)*3)
            raster=cv2.resize(canvas,(640,480),interpolation=cv2.INTER_AREA)
            found,corners=cv2.findChessboardCornersSB(cv2.cvtColor(raster,cv2.COLOR_BGR2GRAY),(9,6),cv2.CALIB_CB_NORMALIZE_IMAGE);self.assertTrue(found)
            origin=cv2.projectPoints(np.zeros((1,3)),rv,t,k,np.zeros(5))[0].reshape(2);points=corners.reshape(-1,2)
            # Synthetic ground truth supplies the physical board-origin choice;
            # production requires an origin mark and operator verification.
            reverse=bool(np.linalg.norm(points[0]-origin)>np.linalg.norm(points[-1]-origin))
            image='data:image/png;base64,'+base64.b64encode(cv2.imencode('.png',raster)[1]).decode()
            pose=run('pose',_image=image,intrinsics=intr,reverseCorners=reverse)['result']['pose']
            for part,key in zip(['X','Y','Z','Rx','Ry','Rz'],['x','y','z','rx','ry','rz']):row['camera'+part]=pose[key]
        fitted=run('fit',poses=rows[:8],maximumTranslationRms=2,maximumTranslationError=4,maximumAngleError=2)['result']
        np.testing.assert_allclose(fitted['calibration']['translation'],np.array(truth['cameraToTool'])[:3,3],atol=10)
        self.assertLess(h.angle(np.array(fitted['calibration']['rotation'])@np.array(truth['cameraToTool'])[:3,:3].T),1)
        checked=run('check',poses=rows[8:],calibration=fitted['calibration'],reference=fitted['reference'],maximumTranslationRms=2,maximumTranslationError=4,maximumAngleError=2)['result']
        self.assertTrue(checked['passed'])


if __name__=='__main__':unittest.main()
