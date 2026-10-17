"""Real official weights plus exact binary-mask geometry tests."""
import base64
import os
from pathlib import Path
import sys
import unittest
import cv2
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
os.environ['YOLO_CONFIG_DIR']=str(ROOT/'data/yolo-config')
os.environ['YOLO_AUTOINSTALL']='false'
sys.path.insert(0,str(ROOT/'vision'))
from engine import run
from yolo_segmentation import mask_record


def encode(image):
    return base64.b64encode(cv2.imencode('.png',image)[1]).decode()


def invoke(image,**params):
    return run(dict(operation='yolo_segment',image=encode(image),params=params))


def decoded(out,key='maskImage'):
    return cv2.imdecode(np.frombuffer(base64.b64decode(out[key].split(',')[1]),np.uint8),cv2.IMREAD_GRAYSCALE)


class SegmentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import ultralytics
        cls.image=cv2.imread(str(Path(ultralytics.__file__).parent/'assets/bus.jpg'))
        # Missing weights must fail this dedicated acceptance suite, never silently skip.
        for name in ['yolo11n-seg.pt','yolov8n-seg.pt']:
            if not (ROOT/'models'/name).is_file():raise RuntimeError('Install trusted official segmentation weights: '+name)

    def test_real_v8_and_11_masks_have_area_and_contours(self):
        for name in ['yolov8n-seg.pt','yolo11n-seg.pt']:
            with self.subTest(model=name):
                out=invoke(self.image,model=name); r=out['result'];mask=decoded(out)
                labels={item['label'] for item in r['items']}
                self.assertIn('person',labels);self.assertIn('bus',labels)
                self.assertEqual(r['unionAreaPixels'],np.count_nonzero(mask))
                self.assertEqual(mask.shape,self.image.shape[:2]);self.assertEqual(set(np.unique(mask)),{0,255})
                self.assertGreaterEqual(r['summedAreaPixels'],r['unionAreaPixels'])
                self.assertTrue(all(item['contours'] and item['areaPixels']>0 for item in r['items']))
                self.assertTrue(any(item['areaPixels']<item['maskBbox'][2]*item['maskBbox'][3]*.8 for item in r['items']))
                (ROOT/'artifacts'/f'{name}-overlay.jpg').write_bytes(base64.b64decode(out['annotatedImage'].split(',')[1]))

    def test_roi_offsets_and_black_mask_outside_roi(self):
        image=cv2.resize(self.image,(324,432)); full=np.full((492,424,3),127,np.uint8);full[30:462,50:374]=image
        a=invoke(image,output='mask');b=invoke(full,roi=[50,30,324,432],output='mask')
        self.assertEqual(a['result']['count'],b['result']['count'])
        np.testing.assert_array_equal(decoded(a),decoded(b)[30:462,50:374])
        mask=decoded(b);self.assertEqual(np.count_nonzero(mask),np.count_nonzero(mask[30:462,50:374]))
        np.testing.assert_array_equal(decoded(b),decoded(b,'annotatedImage'))
        for original,shifted in zip(a['result']['items'],b['result']['items']):
            self.assertEqual(original['areaPixels'],shifted['areaPixels'])
            np.testing.assert_allclose(np.asarray(original['center'])+[50,30],shifted['center'])
            for ca,cb in zip(original['contours'],shifted['contours']):
                np.testing.assert_allclose(np.asarray(ca['points'])+[50,30],cb['points'])

    def test_holes_disconnected_islands_and_simplification_preserve_pixel_area(self):
        mask=np.zeros((40,50),np.uint8);mask[5:25,5:25]=255;mask[10:20,10:20]=0;mask[13:17,13:17]=255;mask[30:35,35:40]=255
        result=mask_record(mask,[20,30],2)
        self.assertEqual(result['areaPixels'],341);self.assertEqual(sum(c['isHole'] for c in result['contours']),1)
        self.assertEqual(len(result['contours']),4)
        ys,xs=np.nonzero(mask);np.testing.assert_allclose(result['center'],[xs.mean()+20,ys.mean()+30])
        self.assertEqual(result['maskBbox'],[25,35,35,30]);self.assertIsNone(mask_record(np.zeros((5,5),np.uint8),[0,0],0))

    def test_empty_class_filter_area_filter_and_target_limit(self):
        out=invoke(self.image,classes=[]);self.assertEqual(out['result']['count'],0);self.assertEqual(np.count_nonzero(decoded(out)),0)
        out=invoke(self.image,minArea=16_000_000);self.assertEqual(out['result']['count'],0);self.assertGreater(out['result']['filteredCount'],0)
        out=invoke(self.image,maxDetections=1,classes=[0]);self.assertEqual(out['result']['count'],1);self.assertTrue(out['result']['limitReached']);self.assertEqual(out['result']['items'][0]['classId'],0)

    def test_model_mismatch_missing_and_configuration_errors(self):
        for p in [{'model':'yolo11n.pt'},{'model':'absent.pt'},{'model':'../yolo11n-seg.pt'},{'model':'model.onnx'},
                  {'classes':[True]},{'imageSize':641},{'maxDetections':0},{'maxDetections':1.5},
                  {'imageSize':1280,'maxDetections':100},{'output':'bad'},{'overlayAlpha':2},{'contourTolerance':-1}]:
            with self.subTest(params=p),self.assertRaises(ValueError):invoke(self.image,**p)


if __name__=='__main__':unittest.main(verbosity=2)
