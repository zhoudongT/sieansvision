"""Dedicated real-CUDA acceptance. Missing GPU or weights fail rather than skip."""
import base64
import os
from pathlib import Path
import sys
import unittest
import cv2
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'vision'))
os.environ['YOLO_CONFIG_DIR']=str(ROOT/'data/gpu-yolo-config');os.environ['YOLO_AUTOINSTALL']='false';os.environ['YOLO_OFFLINE']='true'
from engine import run
from compute_device import device_info,select_device

class RealGPUTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not device_info()['cudaAvailable']:raise RuntimeError('CUDA GPU is required for this acceptance suite')
        cls.image=base64.b64encode((ROOT/'public/vision/samples/segmentation-bus.jpg').read_bytes()).decode()

    def invoke(self,operation,model,device):return run(dict(operation=operation,image=self.image,params=dict(model=model,device=device,classes=[5],confidence=.25)))

    def test_v8_v11_actual_cuda_detection_and_cpu_cache_switch(self):
        for model in ['yolov8n.pt','yolo11n.pt']:
            with self.subTest(model=model):
                gpu=self.invoke('yolo',model,'cuda:0');cpu=self.invoke('yolo',model,'cpu')
                self.assertEqual(gpu['result']['device'],'cuda:0');self.assertEqual(cpu['result']['device'],'cpu')
                self.assertEqual(gpu['result']['count'],1);self.assertEqual(cpu['result']['count'],1)
                a,b=gpu['result']['items'][0],cpu['result']['items'][0]
                self.assertEqual(a['label'],'bus');self.assertAlmostEqual(a['confidence'],b['confidence'],delta=.02)
                np.testing.assert_allclose(a['bbox'],b['bbox'],atol=3)
                print(model,'GPU',gpu['elapsedMs'],'ms','CPU',cpu['elapsedMs'],'ms')

    def test_v8_v11_actual_cuda_masks_match_cpu_and_auto_is_explicit(self):
        for model in ['yolov8n-seg.pt','yolo11n-seg.pt']:
            with self.subTest(model=model):
                gpu=self.invoke('yolo_segment',model,'auto');cpu=self.invoke('yolo_segment',model,'cpu')
                self.assertEqual(gpu['result']['device'],'cuda:0');self.assertEqual(gpu['result']['requestedDevice'],'auto')
                self.assertEqual(gpu['result']['count'],1);self.assertEqual(cpu['result']['count'],1)
                masks=[cv2.imdecode(np.frombuffer(base64.b64decode(o['maskImage'].split(',')[1]),np.uint8),cv2.IMREAD_GRAYSCALE)>0 for o in [gpu,cpu]]
                iou=np.count_nonzero(masks[0]&masks[1])/np.count_nonzero(masks[0]|masks[1]);self.assertGreater(iou,.97)
                print(model,'mask IoU',iou)

    def test_unavailable_gpu_rejected_and_onnx_cpu_provider_does_not_claim_cuda(self):
        with self.assertRaisesRegex(ValueError,'不可用'):self.invoke('yolo','yolo11n.pt','cuda:99')
        import onnxruntime
        if 'CUDAExecutionProvider' not in onnxruntime.get_available_providers():
            with self.assertRaisesRegex(ValueError,'CUDAExecutionProvider'):select_device('cuda:0','onnx')
            self.assertEqual(select_device('auto','onnx')['device'],'cpu')

if __name__=='__main__':unittest.main(verbosity=2)
