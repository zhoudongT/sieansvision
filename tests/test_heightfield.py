import copy
import importlib.util
import json
from pathlib import Path
import unittest
import numpy as np

ROOT=Path(__file__).resolve().parents[1];samples=ROOT/'public/vision/samples';folder=ROOT/'operator-plugins/sieans-heightfield'
spec=importlib.util.spec_from_file_location('heightfield',folder/'heightfield.py');h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)
manifest=json.loads((folder/'operator-plugin.json').read_text(encoding='utf-8'));truth=json.loads((samples/'heightfield-truth.json').read_text());model=truth['plane']
def cloud(name='heightfield-block'):return json.loads((samples/(name+'.json')).read_text())
def run(task='integrate',data=None,**overrides):
    op=next(op for op in manifest['operators'] if op['id']==task);p={f['key']:copy.deepcopy(f['default']) for f in op['parameters']}
    if task=='integrate':p['plane']=copy.deepcopy(model)
    p.update(overrides);return h.run(dict(params=p,cloud=data or cloud()))
def fitted(**overrides):
    params=dict(points=truth['points'],frame=model['frame'],normalHint=model['normal'],axisHint=model['axisU']);params.update(overrides);return run('fit',**params)['result']


class HeightfieldTests(unittest.TestCase):
    def test_independent_tilted_plane_and_metric_volume(self):
        result=fitted();self.assertTrue(result['passed']);origin,basis=h.plane_read(result['plane']);self.assertTrue(np.allclose(origin,model['origin'],atol=1e-10));self.assertTrue(np.allclose(basis[:,2],model['normal'],atol=1e-10))
        out=run(plane=result['plane'])['result'];self.assertTrue(out['passed'],out);self.assertEqual(out['validCells'],100);self.assertEqual(out['coverage'],1);self.assertAlmostEqual(out['maximumHeight'],2,delta=1e-10);self.assertAlmostEqual(out['positiveVolume'],32,delta=1e-9)
        wrong=np.array(cloud()['points'])[:,2]-30;self.assertGreater(abs(float(wrong.max())-2),.4)

    def test_mm_to_m_area_and_cubic_volume(self):
        mm=run()['result'];metres=cloud();metres['unit']='m';metres['points']=(np.array(metres['points'])/1000).tolist();m=copy.deepcopy(model);m['unit']='m';m['origin']=(np.array(m['origin'])/1000).tolist()
        result=run(data=metres,plane=m,uMinimum=-.005,vMinimum=-.005,cellSize=.001,maximumCellSpread=.0005,maximumHeight=.01)['result']
        self.assertTrue(result['passed']);self.assertAlmostEqual(result['positiveVolume'],mm['positiveVolume']*1e-9,delta=1e-15);self.assertAlmostEqual(result['roiArea'],mm['roiArea']*1e-6,delta=1e-15);self.assertAlmostEqual(result['maximumHeight'],.002,delta=1e-12)

    def test_normal_hint_defines_height_sign(self):
        result=fitted(normalHint=(-np.array(model['normal'])).tolist());self.assertTrue(result['found']);self.assertLess(float(np.dot(result['plane']['normal'],model['normal'])),-.999)
        measured=run(plane=result['plane'],minimumHeight=-3,maximumHeight=0,maximumPositiveVolume=0)['result'];self.assertTrue(measured['passed']);self.assertAlmostEqual(measured['negativeVolume'],32,delta=1e-9)

    def test_missing_cells_are_not_filled_or_normalized(self):
        result=run(data=cloud('heightfield-missing'))['result'];self.assertFalse(result['passed']);self.assertTrue(result['found']);self.assertEqual(result['missingCells'],10);self.assertEqual(result['coverage'],.9);self.assertAlmostEqual(result['positiveVolume'],24,delta=1e-9);self.assertEqual(result['observedArea'],90)
        missing=[r for r in result['items'] if not r['valid']];self.assertEqual(len(missing),10);self.assertTrue(all('height' not in row and 'signedVolume' not in row for row in missing))

    def test_signed_height_separates_protrusion_cavity_and_net(self):
        result=run(data=cloud('heightfield-signed'),minimumHeight=-1,maximumHeight=2.01)['result'];self.assertTrue(result['passed']);self.assertAlmostEqual(result['positiveVolume'],32,delta=1e-9);self.assertAlmostEqual(result['negativeVolume'],10,delta=1e-9);self.assertAlmostEqual(result['netVolume'],22,delta=1e-9)
        failed=run(data=cloud('heightfield-signed'))['result'];self.assertFalse(failed['passed']);self.assertEqual(failed['outsideHeightCells'],10)

    def test_zero_plane_bounds_allow_only_floating_roundoff(self):
        data=cloud();points=np.array(data['points']);origin=np.array(model['origin']);normal=np.array(model['normal']);points-=((points-origin)@normal)[:,None]*normal;data['points']=points.tolist()
        result=run(data=data,minimumHeight=0,maximumHeight=0,minimumPositiveVolume=0,maximumPositiveVolume=0)['result'];self.assertTrue(result['passed'],result);self.assertLess(result['positiveVolume'],1e-9)

    def test_multilayer_spread_and_mean_maximum_statistics(self):
        data=cloud('heightfield-layered');result=run(data=data,minimumCoverage=1)['result'];self.assertEqual(result['spreadRejectedCells'],1);self.assertEqual(result['validCells'],99);self.assertFalse(result['passed']);self.assertAlmostEqual(result['positiveVolume'],30,delta=1e-9)
        maximum=run(data=data,maximumCellSpread=4)['result'];mean=run(data=data,maximumCellSpread=4,cellStatistic='mean')['result'];self.assertAlmostEqual(maximum['positiveVolume'],35,delta=1e-9);self.assertAlmostEqual(mean['positiveVolume'],33.5,delta=1e-9)

    def test_duplicate_points_do_not_create_extra_coverage_or_samples(self):
        data=cloud();data['points']*=3;out=run(data=data,minimumSamples=2)['result'];self.assertEqual(out['uniquePointCount'],100);self.assertEqual(out['pointCount'],300);self.assertEqual(out['insufficientCells'],100);self.assertFalse(out['found']);self.assertNotIn('positiveVolume',out);self.assertNotIn('maximumHeight',out)
        distinct=cloud();points=np.array(distinct['points']);distinct['points']+= (points+.05*np.array(model['axisU'])).tolist();self.assertTrue(run(data=distinct,minimumSamples=2)['result']['passed'])

    def test_half_open_roi_boundary_and_outside_points(self):
        p=copy.deepcopy(model);p.update(origin=[0,0,0],axisU=[1,0,0],axisV=[0,1,0],normal=[0,0,1]);data=dict(unit='mm',frame=p['frame'],points=[[0,0,2],[1,1,2],[2,1,2],[-.1,0,2]])
        r=run(data=data,plane=p,uMinimum=0,vMinimum=0,cellsU=2,cellsV=2)['result'];self.assertEqual(r['roiPointCount'],2);self.assertEqual(r['outsideRoiPointCount'],2);self.assertEqual(r['validCells'],2);self.assertAlmostEqual(r['positiveVolume'],4)

    def test_color_output_and_detail_truncation_preserve_geometry_and_metadata(self):
        data=cloud();data.update(serial='fixture',intrinsics={'marker':'unchanged'});before=copy.deepcopy(data);out=run(data=data,detailLimit=7);self.assertEqual(data,before);self.assertEqual(out['cloud']['points'],before['points']);self.assertEqual(out['cloud']['intrinsics'],before['intrinsics']);self.assertEqual(len(out['cloud']['colors']),100);self.assertTrue(out['result']['detailsTruncated']);self.assertEqual(len(out['result']['items']),7)
        rejected=run(data=cloud('heightfield-layered'),detailMode='invalid');self.assertEqual(len(rejected['result']['items']),1);self.assertTrue(any(color==[1.,.6,.1] for color in rejected['cloud']['colors']))

    def test_plane_fit_refuses_degenerate_or_poor_reference_and_direction(self):
        with self.assertRaises(ValueError):fitted(points=[dict(x=i,y=i,z=i) for i in range(4)])
        with self.assertRaises(ValueError):fitted(normalHint=model['axisU'])
        with self.assertRaises(ValueError):fitted(axisHint=model['normal'])
        points=copy.deepcopy(truth['points']);points[0]['z']+=1
        result=fitted(points=points,maximumRms=.001,maximumError=.002);self.assertFalse(result['found']);self.assertNotIn('plane',result)
        rows=truth['points']*3;result=fitted(points=rows);self.assertEqual(result['uniquePointCount'],4)

    def test_invalid_identity_basis_input_and_resource_bounds(self):
        for change in [dict(unit='m'),dict(frame='other'),dict(axisV=model['axisU']),dict(normal=[0,0,0]),dict(origin=[True,0,0])]:
            with self.subTest(change=change),self.assertRaises(ValueError):run(plane={**model,**change})
        for change in [dict(cellsU=512,cellsV=512),dict(cellSize=1e-20),dict(minimumHeight=20,maximumHeight=1),dict(maximumPositiveVolume=0,minimumPositiveVolume=1),dict(minimumSamples=True),dict(cellStatistic='median')]:
            with self.subTest(change=change),self.assertRaises(ValueError):run(**change)
        data=cloud();data['points']*=101
        with self.assertRaises(ValueError):run(data=data)
        r=run(data=data,colorize=False)['result'];self.assertEqual(r['pointCount'],10100);self.assertEqual(r['uniquePointCount'],100)


if __name__=='__main__':unittest.main()
