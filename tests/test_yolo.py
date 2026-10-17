"""Optional real-weight smoke test; no synthetic predictions."""
import base64
import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
config = ROOT / 'data/yolo-config'
config.mkdir(parents=True, exist_ok=True)
os.environ['YOLO_CONFIG_DIR'] = str(config)
os.environ['YOLO_AUTOINSTALL'] = 'false'
sys.path.insert(0, str(ROOT / 'vision'))
from engine import run


class YoloTests(unittest.TestCase):
    def test_v8_and_11_real_image(self):
        import ultralytics
        sample = Path(ultralytics.__file__).parent / 'assets/bus.jpg'
        encoded = base64.b64encode(sample.read_bytes()).decode()
        for name in ('yolov8n.pt', 'yolo11n.pt'):
            with self.subTest(model=name):
                if not (ROOT / 'models' / name).is_file():
                    self.skipTest('Download trusted demo weights before running this optional test')
                output = run({'operation':'yolo','image':encoded,'params':{'model':name}})
                labels = {item['label'] for item in output['result']['items']}
                self.assertIn('person', labels)
                self.assertIn('bus', labels)
                artifact = ROOT / 'artifacts' / (name+'.jpg')
                artifact.parent.mkdir(exist_ok=True)
                artifact.write_bytes(base64.b64decode(output['annotatedImage'].split(',')[1]))
                print(name, output['result']['count'], 'detections', output['elapsedMs'], 'ms')


if __name__ == '__main__':
    unittest.main(verbosity=2)
