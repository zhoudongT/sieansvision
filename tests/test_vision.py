import base64
import sys
import unittest
from pathlib import Path

import cv2
import numpy as np
import zxingcpp

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'vision'))
from engine import run, decode


def encoded(image):
    return base64.b64encode(cv2.imencode('.png', image)[1]).decode()


def fixtures():
    parts = np.zeros((420, 700, 3), np.uint8)
    cv2.rectangle(parts, (50, 70), (250, 170), (240, 240, 240), -1)
    cv2.circle(parts, (450, 135), 55, (240, 240, 240), -1)
    cv2.line(parts, (80, 300), (570, 300), (255, 255, 255), 5)
    text = np.full((230, 720, 3), 255, np.uint8)
    cv2.putText(text, 'BATCH 20261015', (35, 90), cv2.FONT_HERSHEY_SIMPLEX, 1.6, (0, 0, 0), 3)
    cv2.putText(text, 'SN: ABC12345', (35, 170), cv2.FONT_HERSHEY_SIMPLEX, 1.4, (0, 0, 0), 3)
    codes = np.full((380, 720, 3), 255, np.uint8)
    for value, kind, pos, scale in [('MACHINE-QR-2026', zxingcpp.BarcodeFormat.QRCode, (30, 25), 7),
                                   ('ABC123456789', zxingcpp.BarcodeFormat.Code128, (300, 240), 2)]:
        code = np.asarray(zxingcpp.write_barcode_to_image(zxingcpp.create_barcode(value, kind), scale=scale))
        color = cv2.cvtColor(code, cv2.COLOR_GRAY2BGR)
        x, y = pos
        codes[y:y+color.shape[0], x:x+color.shape[1]] = color
    return parts, text, codes


class VisionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parts, cls.text, cls.codes = fixtures()
        cls.image = encoded(cls.parts)
        output = Path(__file__).resolve().parents[1] / 'public/vision/samples'
        output.mkdir(parents=True, exist_ok=True)
        for name, image in [('parts', cls.parts), ('text', cls.text), ('codes', cls.codes)]:
            cv2.imwrite(str(output / (name+'.png')), image)

    def test_geometry_coordinates_roi(self):
        response = run({'operation':'geometry', 'image':self.image, 'params':{'roi':[30,40,250,170]}})
        self.assertEqual(response['result']['count'], 1)
        self.assertEqual(response['result']['items'][0]['bbox'], [50,70,201,101])

    def test_lines_and_circles(self):
        lines = run({'operation':'geometry','image':self.image,'params':{'feature':'lines'}})['result']['items']
        self.assertTrue(any(item['lengthPixels'] > 400 for item in lines))
        circles = run({'operation':'geometry','image':self.image,'params':{'feature':'circles'}})['result']['items']
        self.assertTrue(any(abs(item['radiusPixels']-55)<5 for item in circles))

    def test_calibrated_distance(self):
        result = run({'operation':'measure','image':self.image,'params':{
            'points':[[50,70],[250,70]],'calibration':{'points':[[0,0],[100,0]],'distance':10},'unit':'mm'}})['result']
        self.assertAlmostEqual(result['distance'],20)
        self.assertTrue(result['calibrated'])
        self.assertEqual(result['unit'],'mm')

    def test_uncalibrated_measurement(self):
        result=run({'operation':'measure','image':self.image,'params':{'roi':[30,40,250,170]}})['result']
        self.assertEqual(result['unit'],'px')
        self.assertAlmostEqual(result['items'][0]['width'],100)
        self.assertAlmostEqual(result['items'][0]['height'],200)

    def test_template_translation_rotation(self):
        rng=np.random.default_rng(7)
        template=rng.integers(30,240,(40,60,3),dtype=np.uint8)
        image=np.full((220,300,3),10,np.uint8)
        image[80:140,130:170]=cv2.rotate(template,cv2.ROTATE_90_COUNTERCLOCKWISE)
        result=run({'operation':'locate','image':encoded(image),'reference':encoded(template),
                    'params':{'angleStart':0,'angleEnd':180,'angleStep':90,'minScore':.8}})['result']
        self.assertTrue(result['found'])
        self.assertEqual(result['angleDeg'],90)
        self.assertLess(np.linalg.norm(np.array(result['center'])-[150,110]),3)

    def test_template_rejects_no_match(self):
        template=np.zeros((30,30,3),np.uint8)
        cv2.circle(template,(15,15),8,(255,255,255),-1)
        result=run({'operation':'locate','image':encoded(np.full((80,80,3),80,np.uint8)),
                    'reference':encoded(template),'params':{'minScore':.99}})['result']
        self.assertFalse(result['found'])

    def test_barcode_and_qr(self):
        result=run({'operation':'barcode','image':encoded(self.codes)})['result']
        self.assertEqual({item['text'] for item in result['items']},{'MACHINE-QR-2026','ABC123456789'})

    def test_ocr(self):
        result=run({'operation':'ocr','image':encoded(self.text)})['result']
        self.assertIn('20261015',result['text'])
        self.assertIn('ABC12345',result['text'])

    def test_defects_good_and_bad(self):
        good=run({'operation':'defects','image':self.image,'reference':self.image})['result']
        self.assertTrue(good['passed'])
        bad=self.parts.copy()
        cv2.rectangle(bad,(100,100),(130,130),(0,0,0),-1)
        result=run({'operation':'defects','image':encoded(bad),'reference':self.image})['result']
        self.assertFalse(result['passed'])
        self.assertEqual(result['count'],1)

    def test_preprocessing_lossless(self):
        output=run({'operation':'preprocess','image':self.image,'params':{'method':'threshold'}})
        pixels=decode(output['annotatedImage'])
        self.assertEqual(set(np.unique(pixels)),{0,255})

    def test_invalid_input(self):
        for request in [
            {'operation':'geometry','image':'not an image'},
            {'operation':'geometry','image':self.image,'params':{'roi':[-1,0,10,10]}},
            {'operation':'measure','image':self.image,'params':{'calibration':{'points':[[0,0],[0,0]],'distance':1}}},
            {'operation':'defects','image':self.image},
            {'operation':'locate','image':self.image,'reference':encoded(np.zeros((20,20,3),np.uint8))},
            {'operation':'yolo','image':self.image,'params':{'model':'../private.pt'}},
            {'operation':'yolo','image':self.image,'params':{'model':'missing.pt'}},
        ]:
            with self.subTest(operation=request['operation']):
                with self.assertRaises(Exception):run(request)


if __name__=='__main__':
    unittest.main(verbosity=2)
