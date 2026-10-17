import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'vision'))
from compute_device import device_info,select_device,predict

class DeviceTests(unittest.TestCase):
    def test_cpu_default_and_auto_report_actual_selection(self):
        info=device_info();self.assertEqual(info['devices'][0]['id'],'cpu')
        self.assertEqual(select_device()['device'],'cpu')
        if info['cudaAvailable']:self.assertIn('CUDA',select_device(info['devices'][1]['id'])['deviceReason'])
        auto=select_device('auto');self.assertEqual(auto['requestedDevice'],'auto');self.assertEqual(auto['device'],info['devices'][1]['id'] if info['cudaAvailable'] else 'cpu');self.assertTrue(auto['deviceReason'])

    def test_invalid_or_unavailable_devices_never_silently_fall_back(self):
        for value in [None,True,0,'gpu','cuda','cuda:-1','cuda:100','0,1']:
            with self.subTest(device=value),self.assertRaises(ValueError):select_device(value)
        with self.assertRaisesRegex(ValueError,'不可用'):select_device('cuda:99')

    def test_oom_is_an_error_and_does_not_retry_on_cpu(self):
        import torch
        class Model:
            calls=0
            def predict(self,*a,**kw):self.calls+=1;raise torch.cuda.OutOfMemoryError('test')
        model=Model()
        with patch('torch.cuda.empty_cache') as empty,self.assertRaisesRegex(ValueError,'显存不足'):predict(model,None,dict(device='cuda:0'))
        self.assertEqual(model.calls,1);empty.assert_called_once()

if __name__=='__main__':unittest.main(verbosity=2)
