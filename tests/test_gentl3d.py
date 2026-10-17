"""Real Harvesters PFNC decoding of synthetic buffers; no physical camera claims."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch, MagicMock

import numpy as np
from harvesters.core import Component2DImage
from harvesters.util.pfnc import dict_by_names

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from cameras import adapter as a, gentl3d as g


def component(data, fmt, w=16, h=12):
    raw=bytearray(data.tobytes())
    return Component2DImage(node_map=NS(),buffer=NS(raw_buffer=raw),part=NS(
        data_format=dict_by_names[fmt],data_size=len(raw),data_offset=0,width=w,height=h))


def fixture(planar=False):
    y,x=np.indices((12,16));raw=np.stack((x,y,np.full_like(x,100)),axis=2).astype('<f4')
    raw[0,0]=[-999,-999,-999];raw[0,1,0]=np.nan
    layout=raw.transpose(2,0,1).copy() if planar else raw
    fmt=g.FORMATS[int(planar)]
    coords=component(layout,fmt)
    gray=np.full((12,16),32768,np.uint16);confidence=np.full((12,16),100,np.uint16);confidence[0,2]=0
    calib=dict(unit='Millimeter',millimetersPerUnit=1.,reference='Anchor',pixelFormat=fmt,
               axes=[dict(axis=axis,scale=scale,offset=offset,invalidEnabled=True,invalidValue=-999)
                     for axis,scale,offset in [('CoordinateA',.5,10),('CoordinateB',2,-20),('CoordinateC',-1,500)]])
    return [component(gray,'Mono16'),coords,component(confidence,'Confidence16')],calib


def integer_fixture(planar=False):
    components, calib = fixture()
    y, x = np.indices((12, 16))
    raw = np.stack((x, y, np.full_like(x, 100)), axis=2).astype('<u2')
    raw[0, 0] = [65535, 65535, 65535]
    raw[0, 1, 0] = 65535
    fmt = 'Coord3D_ABC16_Planar' if planar else 'Coord3D_ABC16'
    components[1] = component(raw.transpose(2, 0, 1).copy() if planar else raw, fmt)
    calib['pixelFormat'] = fmt
    for axis in calib['axes']:
        axis['invalidValue'] = 65535
    return components, calib


def params(**kwargs):
    return a.config(dict(driver='gentl',dataMode='pointcloud',providerId='fixture',deviceId='fixture-camera',
                         **{'pointStride':1,**kwargs}))


class Feature:
    def __init__(self,value):self.value=value


def node_map():
    return NS(**{k:Feature(v) for k,v in dict(GenDCStreamingMode='On',ComponentSelector='Intensity',
        ComponentEnable=False,Scan3dOutputMode='CalibratedC',PixelFormat='Coord3D_C16',
        Scan3dCoordinateSystem='Cartesian',Scan3dDistanceUnit='Millimeter',Scan3dCoordinateSystemReference='Anchor',
        Scan3dCoordinateSelector='CoordinateC',Scan3dCoordinateScale=1.,Scan3dCoordinateOffset=0.,
        Scan3dInvalidDataFlag=True,Scan3dInvalidDataValue=-999.).items()})


class GenTL3DTests(unittest.TestCase):
    def test_native_harvesters_interleaved_and_planar_same_metric_points(self):
        clouds=[]
        for planar in (False,True):
            components,calib=fixture(planar)
            image,info,depth,cloud=g.capture(components,params(),calib)
            self.assertIsNone(depth);self.assertEqual(image.shape,(12,16,3))
            self.assertEqual(info['rangeComponent'],1);self.assertEqual(info['pointCount'],190)
            self.assertEqual(cloud['unit'],'mm');self.assertNotIn('colors',cloud)
            self.assertEqual(cloud['points'][0],[11.,-20.,400.]);self.assertEqual(cloud['points'][-1],[17.5,2.,400.])
            self.assertEqual(info['imageKind'],'coordinate-z-preview');clouds.append(cloud)
            components[1].data[:]=0
            self.assertEqual(cloud['points'][-1],[17.5,2.,400.]) # no SDK-memory alias
        self.assertEqual(clouds[0],clouds[1])

    def test_explicit_intensity_and_confidence_grid(self):
        components,calib=fixture()
        p=params(intensityComponent=0,confidenceComponent=2,alignedComponents=True,confidenceThreshold=50)
        image,info,_,cloud=g.capture(components,p,calib)
        self.assertEqual(info['pointCount'],189);self.assertEqual(info['validCoordinatePoints'],190)
        self.assertEqual(image.dtype,np.uint8);self.assertEqual(int(image[2,2]),128)
        self.assertEqual(cloud['colors'][0],[128/255]*3);self.assertEqual(info['imageKind'],'aligned-intensity-preview')
        # Native confidence codes remain native; there is no invented normalization.
        p['confidenceThreshold']=101
        with self.assertRaisesRegex(ValueError,'没有'):g.capture(components,p,calib)

    def test_inches_negative_axes_and_zero_coordinates_are_not_clipped(self):
        components,calib=fixture();calib['unit']='Inch';calib['millimetersPerUnit']=25.4
        calib['axes'][1]['offset']=-40;calib['axes'][2]['offset']=0
        _,_,_,cloud=g.capture(components,params(),calib)
        self.assertAlmostEqual(cloud['points'][0][0],279.4);self.assertEqual(cloud['points'][0][2],-2540)

    def test_native_integer_layouts_match_float_calibrated_points_and_own_buffers(self):
        expected = g.capture(fixture()[0], params(confidenceComponent=2, intensityComponent=0, alignedComponents=True), fixture()[1])[3]
        for planar in (False, True):
            components, calib = integer_fixture(planar)
            image, info, depth, cloud = g.capture(components, params(confidenceComponent=2, intensityComponent=0, alignedComponents=True), calib)
            self.assertEqual(components[1].data.dtype, np.uint16)
            self.assertEqual(info['sourceBits'], 16)
            self.assertEqual(info['validCoordinatePoints'], 190)
            self.assertEqual(info['pointCount'], 189)
            self.assertEqual(cloud, expected)
            self.assertIsNone(depth)
            self.assertEqual(int(image[2, 2]), 128)
            components[1].data[:] = 0
            self.assertEqual(cloud['points'][-1], [17.5, 2., 400.])

    def test_integer_zero_maximum_and_signed_physical_coordinates_are_not_discarded(self):
        components, calib = integer_fixture()
        components[1].data[6:9] = [65534, 0, 0]
        calib['unit'] = 'Inch'; calib['millimetersPerUnit'] = 25.4
        calib['axes'][0]['offset'] = -10
        calib['axes'][2]['scale'] = 1; calib['axes'][2]['offset'] = -30
        _, info, _, cloud = g.capture(components, params(), calib)
        self.assertEqual(info['invalidCoordinatePoints'], 2)
        np.testing.assert_allclose(cloud['points'][0], [(65534*.5-10)*25.4, -20*25.4, -30*25.4])
        self.assertTrue(any(p[0] < 0 for p in cloud['points']))

    def test_integer_marker_and_buffer_contracts_reject_unrepresentable_values(self):
        for invalid in [-1, 65536, 1.5, float('nan'), float('inf'), None, True]:
            components, calib = integer_fixture(); calib['axes'][0]['invalidValue'] = invalid
            with self.subTest(invalid=invalid), self.assertRaisesRegex(ValueError, '无效标记'):
                g.capture(components, params(), calib)
        for dtype in [np.int16, np.float32, np.dtype('>u2')]:
            components, calib = integer_fixture(); components[1] = NS(data_format=calib['pixelFormat'], width=16, height=12, data=np.zeros(576, dtype))
            with self.subTest(dtype=dtype), self.assertRaisesRegex(ValueError, 'uint16'):
                g.capture(components, params(), calib)

    @patch('genicam.genapi.is_readable', return_value=True)
    @patch('genicam.genapi.is_writable', return_value=True)
    @patch('genicam.genapi.is_available', return_value=True)
    def test_integer_range_configuration_preservation_and_selector_restore(self, *_):
        for fmt in ['Coord3D_ABC16', 'Coord3D_ABC16_Planar']:
            nm = node_map(); nm.Scan3dInvalidDataValue.value = 65535
            calib = g.configure(nm, params(coordinateFormat=fmt), [], a.set_feature)
            self.assertEqual(calib['pixelFormat'], fmt)
            self.assertEqual(nm.Scan3dCoordinateSelector.value, 'CoordinateC')
            preserved = g.configure(nm, params(configure3d=False), [], a.set_feature)
            self.assertEqual(preserved['pixelFormat'], fmt)
            nm.Scan3dInvalidDataValue.value = -1
            with self.assertRaisesRegex(ValueError, '无效标记'):
                g.configure(nm, params(configure3d=False), [], a.set_feature)
            self.assertEqual(nm.Scan3dCoordinateSelector.value, 'CoordinateC')

    def test_config_rejects_ambiguous_mapping_and_invalid_thresholds(self):
        for fields in [dict(intensityComponent=0),dict(rangeComponent=0,intensityComponent=0,alignedComponents=True),
                       dict(confidenceThreshold=0),dict(rangeComponent=64),dict(pointStride=0),
                       dict(coordinateFormat='Coord3D_C16'),dict(pixelFormat='Mono8'),dict(configure3d='yes')]:
            with self.subTest(fields=fields),self.assertRaises(ValueError):params(**fields)

    def test_rejects_wrong_payload_and_missing_components(self):
        components,calib=fixture()
        with self.assertRaisesRegex(ValueError,'唯一'):g.capture([components[1],components[1]],params(),calib)
        for p in [params(rangeComponent=0),params(rangeComponent=5),params(confidenceComponent=1,alignedComponents=True)]:
            with self.assertRaises(ValueError):g.capture(components,p,calib)
        for malformed in [NS(data_format=g.FORMATS[0],width=16,height=12,data=np.zeros(576,np.uint32)),
                          NS(data_format=g.FORMATS[0],width=16,height=12,data=np.zeros(575,np.float32)),
                          NS(data_format=g.FORMATS[0],width=4000001,height=1,data=np.zeros(1,np.float32))]:
            with self.assertRaises(ValueError):g.capture([malformed],params(),calib)

    def test_confidence_format_and_dimensions_checked(self):
        components,calib=fixture();components[2]=component(np.full(192,90,np.uint8),'Confidence8')
        with self.assertRaisesRegex(ValueError,'位深'):g.capture(components,params(confidenceComponent=2,alignedComponents=True,confidenceThreshold=256),calib)
        components[2]=component(np.full(192,90,np.uint8),'Confidence8',w=12,h=16)
        with self.assertRaisesRegex(ValueError,'栅格尺寸'):g.capture(components,params(confidenceComponent=2,alignedComponents=True),calib)

    def test_point_budget_and_all_invalid_do_not_fake_empty_cloud(self):
        components,calib=fixture()
        with patch.object(g,'MAX_POINTS',10):
            with self.assertRaisesRegex(ValueError,'采样步长'):g.capture(components,params(),calib)
        components[1].data[:]=np.nan
        with self.assertRaisesRegex(ValueError,'没有'):g.capture(components,params(),calib)

    @patch('genicam.genapi.is_readable',return_value=True)
    @patch('genicam.genapi.is_writable',return_value=True)
    @patch('genicam.genapi.is_available',return_value=True)
    def test_sfnc_configuration_and_selector_restore(self,*_):
        nm=node_map();applied=[];calib=g.configure(nm,params(),applied,a.set_feature)
        self.assertEqual(nm.GenDCStreamingMode.value,'Off');self.assertEqual(nm.ComponentSelector.value,'Range')
        self.assertEqual(nm.Scan3dCoordinateSelector.value,'CoordinateC');self.assertEqual(len(calib['axes']),3)
        for field,bad in [('Scan3dDistanceUnit','unknown'),('Scan3dCoordinateSystem','Spherical'),('Scan3dCoordinateScale',float('nan'))]:
            nm=node_map();getattr(nm,field).value=bad
            with self.assertRaises(ValueError):g.configure(nm,params(),[],a.set_feature)
            self.assertEqual(nm.Scan3dCoordinateSelector.value,'CoordinateC')
        nm=node_map();del nm.Scan3dCoordinateScale
        with self.assertRaisesRegex(ValueError,'缺少'):g.configure(nm,params(),[],a.set_feature)
        self.assertEqual(nm.Scan3dCoordinateSelector.value,'CoordinateC')

    def test_capture_lifecycle_and_metadata_serialization(self):
        for factory in (fixture, integer_fixture):
            components,calib=factory();ia=MagicMock();ia.__enter__.return_value=ia
            buffer=NS(module=NS(is_complete=lambda:True),payload=NS(components=components),timestamp_ns=123)
            context=MagicMock();context.__enter__.return_value=buffer;ia.fetch.return_value=context
            h=MagicMock();h.create.return_value=ia
            with patch.object(a,'harvester',return_value=h),patch.object(a,'gentl_devices',return_value=[dict(deviceId='fixture-camera')]),patch.object(a,'set_feature'),patch.object(g,'configure',return_value=calib):
                capture_params=params(trigger='software',coordinateFormat=calib['pixelFormat'])
                out=a.run(dict(operation='camera_capture',params=capture_params))
                self.assertEqual(out['result']['sourceBits'],16 if factory is integer_fixture else 32)
                self.assertEqual(out['cloud']['unit'],'mm');self.assertIsNone(out['depth'])
                self.assertEqual(out['result']['deviceTimestampNs'],'123');self.assertFalse(out['result']['simulated'])
                ia.remote_device.node_map.TriggerSoftware.execute.assert_called_once()
                context.__exit__.assert_called_once();ia.stop.assert_called_once();h.reset.assert_called_once()
                import json
                json.dumps(out,allow_nan=False)
                ia.fetch.side_effect=TimeoutError('fixture')
                with self.assertRaises(TimeoutError):a.acquire_gentl(capture_params)
                self.assertEqual(ia.stop.call_count,2);self.assertEqual(h.reset.call_count,2)

    @patch('genicam.genapi.is_readable',return_value=True)
    @patch('genicam.genapi.is_writable',return_value=True)
    @patch('genicam.genapi.is_available',return_value=True)
    def test_axis_selected_metadata_and_transformed_reference(self,*_):
        nm=node_map();nm.Scan3dCoordinateSystemReference.value='Transformed'
        nm.Scan3dCoordinateTransformSelector=Feature('TranslationZ')
        nm.Scan3dTransformValue=Feature(10.)
        class Selected:
            @property
            def value(self):return {'CoordinateA':.5,'CoordinateB':2.,'CoordinateC':-1.}[nm.Scan3dCoordinateSelector.value]
        nm.Scan3dCoordinateScale=Selected()
        calib=g.configure(nm,params(),[],a.set_feature)
        self.assertEqual([axis['scale'] for axis in calib['axes']],[.5,2.,-1.])
        self.assertEqual(nm.Scan3dCoordinateSelector.value,'CoordinateC')
        self.assertEqual(nm.Scan3dCoordinateTransformSelector.value,'TranslationZ')
        self.assertEqual(len(calib['transform']),6)
        components,original=fixture();calib['axes']=original['axes']
        first=g.capture(components,params(),calib)[3]
        calib['transform']['TranslationX']=20
        second=g.capture(components,params(),calib)[3]
        self.assertNotEqual(first['frame'],second['frame']);self.assertEqual(first['points'],second['points'])

    @patch('genicam.genapi.is_readable',return_value=True)
    @patch('genicam.genapi.is_writable',return_value=True)
    @patch('genicam.genapi.is_available',return_value=True)
    def test_preserve_mode_does_not_force_unsupported_range_or_serialize_nan(self,*_):
        nm=node_map()
        with self.assertRaisesRegex(ValueError,'未启用'):g.configure(nm,params(configure3d=False),[],a.set_feature)
        self.assertEqual(nm.PixelFormat.value,'Coord3D_C16');self.assertEqual(nm.Scan3dOutputMode.value,'CalibratedC')
        nm.Scan3dInvalidDataValue.value=float('nan')
        calib=g.configure(nm,params(),[],a.set_feature)
        self.assertIsNone(calib['axes'][0]['invalidValue'])
        import json
        json.dumps(a.feature_rows(nm),allow_nan=False);json.dumps(calib,allow_nan=False)


if __name__=='__main__':unittest.main(verbosity=2)
