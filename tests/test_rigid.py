import importlib.util
import json
from pathlib import Path
import unittest
import cv2
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('rigid',ROOT/'operator-plugins/sieans-rigid/rigid.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
manifest=json.loads((ROOT/'operator-plugins/sieans-rigid/operator-plugin.json').read_text(encoding='utf-8'))


def run(task,cloud=None,**overrides):
    definition=next(op for op in manifest['operators'] if op['id']==task)
    p={f['key']:f['default'] for f in definition['parameters']};p.update(overrides)
    return module.run(dict(params=p,cloud=cloud))


def pairs(source,target):
    return [dict(zip(['sourceX','sourceY','sourceZ','targetX','targetY','targetZ'],map(float,np.r_[a,b]))) for a,b in zip(source,target)]


def calibration(**overrides):return run('calibrate',**overrides)['result']['calibration']


class RigidTests(unittest.TestCase):
    def test_known_full_rotation_translation_and_independent_points(self):
        rng=np.random.default_rng(2);source=rng.normal(0,100,(30,3));r=cv2.Rodrigues(np.array([.3,-.5,.7]))[0];t=np.array([300,500,100])
        target=source@r.T+t
        c=calibration(pairs=pairs(source,target))
        np.testing.assert_allclose(c['rotation'],r,atol=1e-12);np.testing.assert_allclose(c['translation'],t,atol=1e-10)
        hold=rng.normal(0,100,(8,3));expected=hold@r.T+t
        out=run('check',calibration=c,pairs=pairs(hold,expected))['result'];self.assertTrue(out['passed']);self.assertLess(out['maximumError'],1e-10)
        expected[0,0]+=2
        out=run('check',calibration=c,pairs=pairs(hold,expected))['result'];self.assertFalse(out['passed']);self.assertAlmostEqual(out['maximumError'],2)

    def test_unit_conversion_and_inverse_round_trip(self):
        defaults=next(op for op in manifest['operators'] if op['id']=='calibrate')['parameters']
        table=json.loads(json.dumps(next(f['default'] for f in defaults if f['key']=='pairs')))
        for row in table:
            for axis in 'XYZ':row['source'+axis]/=1000
        c=calibration(sourceUnit='m',targetUnit='mm',pairs=table)
        output=run('points',calibration=c,points=[dict(x=.01,y=.02,z=.03)])['result']
        np.testing.assert_allclose([output['items'][0]['target'+axis] for axis in 'XYZ'],[280,510,130],atol=1e-10)
        backward=run('points',calibration=c,inverse=True,points=[dict(x=280,y=510,z=130)])['result']
        np.testing.assert_allclose([backward['items'][0]['target'+axis] for axis in 'XYZ'],[.01,.02,.03],atol=1e-12)
        self.assertEqual((backward['sourceUnit'],backward['targetUnit']),('mm','m'))
        self.assertEqual((backward['sourceFrame'],backward['targetFrame']),('fixture-base','camera-optical'))

    def test_ransac_known_outliers_and_quality_rejection(self):
        rng=np.random.default_rng(7);source=rng.normal(0,100,(30,3));target=source+[1,2,3];target[-5:]+=50
        result=run('calibrate',pairs=pairs(source,target),method='ransac',minimumInlierRatio=.8)['result']
        self.assertEqual((result['inlierCount'],result['rejectedCount']),(25,5));self.assertLess(result['rmsError'],1e-10)
        with self.assertRaisesRegex(ValueError,'残差超限'):calibration(pairs=pairs(source,target))
        with self.assertRaisesRegex(ValueError,'比例不足'):calibration(pairs=pairs(source,target),method='ransac',minimumInlierRatio=.9)

    def test_planar_is_accepted_but_collinear_duplicate_and_mirror_3d_rejected(self):
        plane=np.array([[0,0,0],[100,0,0],[0,100,0],[100,100,0]],float)
        calibration(pairs=pairs(plane,plane+[1,2,3]))
        for source,target in [(plane[[0,0,1,2]],plane[[0,0,1,2]]),(np.array([[0,0,0],[1,0,0],[2,0,0]]),np.array([[0,1,0],[1,1,0],[2,1,0]]))]:
            with self.assertRaises(ValueError):calibration(pairs=pairs(source,target))
        rng=np.random.default_rng(9);source=rng.normal(0,20,(20,3));target=source*[-1,1,1]
        with self.assertRaisesRegex(ValueError,'残差超限'):calibration(pairs=pairs(source,target))

    def test_no_unknown_scale_estimation(self):
        rng=np.random.default_rng(5);source=rng.normal(0,100,(10,3))
        with self.assertRaisesRegex(ValueError,'残差超限'):calibration(pairs=pairs(source,source*1.2))

    def test_cloud_metadata_normals_colors_and_wrong_frame_or_units(self):
        c=calibration();cloud=dict(points=[[10,20,30],[20,40,60]],unit='mm',frame='camera-optical',colors=[[1,0,0],[0,1,0]],normals=[[1,0,0],[0,1,0]],intrinsics={'fx':100},extrinsics={'unused':True},timestamp='test')
        out=run('cloud',cloud,calibration=c)
        np.testing.assert_allclose(out['cloud']['points'],[[280,510,130],[260,520,160]],atol=1e-10)
        np.testing.assert_allclose(out['cloud']['normals'],[[0,1,0],[-1,0,0]],atol=1e-12)
        self.assertEqual(out['cloud']['colors'],cloud['colors']);self.assertEqual(out['cloud']['frame'],'fixture-base')
        self.assertNotIn('intrinsics',out['cloud']);self.assertNotIn('extrinsics',out['cloud']);self.assertIsNone(out['depth']);self.assertEqual(out['image'],'')
        back=run('cloud',out['cloud'],calibration=c,inverse=True)['cloud'];np.testing.assert_allclose(back['points'],cloud['points'],atol=1e-10)
        for key,value in [('frame','wrong'),('unit','m'),('colors',[[1,0,0]]),('normals',[[float('nan'),0,0],[0,1,0]])]:
            with self.assertRaises(ValueError):run('cloud',{**cloud,key:value},calibration=c)

    def test_model_rejects_reflection_scale_invalid_version_and_numeric_types(self):
        c=calibration()
        for bad in [{},{**c,'version':True},{**c,'rotation':[[1,0,0],[0,1,0],[0,0,-1]]},{**c,'rotation':[[2,0,0],[0,2,0],[0,0,2]]},{**c,'translation':[True,0,0]},{**c,'sourceFrame':' fixture-base'}]:
            with self.assertRaises(ValueError):run('points',calibration=bad)
        with self.assertRaises(ValueError):run('points',calibration=c,points=[dict(x=float('nan'),y=0,z=0)])
        with self.assertRaises(ValueError):run('points',calibration=c,points=[dict(x=1,y=2,z=3,unknown=4)])


if __name__=='__main__':unittest.main()
