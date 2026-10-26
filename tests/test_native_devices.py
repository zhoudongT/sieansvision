"""Native device windows: no physical device or training is started."""
import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QObject, Signal, QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication
from desktop.device_dialogs import CameraDialog, TrainingDialog, AnnotationDialog, ContinuousDialog
from desktop.model import Document


class FakeBackend(QObject):
    ready = Signal()
    result = Signal(str, object)
    error = Signal(str, str)
    is_ready = True

    def __init__(self):
        super().__init__()
        self.requests = []

    def request(self, method, params=None):
        identifier = str(len(self.requests)+1)
        self.requests.append((identifier, method, params or {}))
        return identifier

    def respond(self, method, value):
        identifier = next(row[0] for row in reversed(self.requests) if row[1] == method)
        self.result.emit(identifier, value)


class DeviceDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.backend = FakeBackend()
        self.windows = []

    def tearDown(self):
        for window in self.windows:
            if hasattr(window, 'dirty'):
                window.dirty = False
            window.close()
            window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def window(self, cls, *args):
        window = cls(self.backend, *args)
        self.windows.append(window)
        return window

    def test_camera_open_reads_metadata_only_and_filters_shared_responses(self):
        window = self.window(CameraDialog)
        window.show()
        self.app.processEvents()
        self.assertEqual({row[1] for row in self.backend.requests}, {'camera/providers', 'camera/session/status'})
        self.backend.result.emit('another-window', {'state': 'running', 'active': True})
        self.backend.error.emit('another-window', 'unrelated')
        self.assertEqual(window.state['state'], 'idle')
        self.assertNotEqual(window.message.text(), 'unrelated')

    def test_camera_manual_capture_and_cancel_leave_continuous_session_open(self):
        window = self.window(CameraDialog)
        window.show()
        window.capture()
        request = self.backend.requests[-1]
        self.assertEqual(request[1], 'camera/capture')
        self.assertEqual(request[2]['driver'], 'simulator')
        window.hide()
        self.assertEqual(self.backend.requests[-1], (str(len(self.backend.requests)), 'camera/cancel', {'requestId': request[0]}))
        self.assertNotIn('camera/session/stop', [r[1] for r in self.backend.requests])

    def test_camera_session_binding_and_rgbd_frame_are_not_lost(self):
        window = self.window(CameraDialog)
        window._session({'state': 'running', 'id': 'session-one', 'bindingId': 'device:stable', 'active': True, 'config': {'params': {'driver': 'rgbd_simulator'}}})
        selected, frames = [], []
        window.camera_selected.connect(lambda p, apply: selected.append((p, apply)))
        window.frame_ready.connect(frames.append)
        window.use_session(False)
        self.assertEqual(selected[0][0]['sessionId'], 'device:stable')
        self.assertEqual(selected[0][0]['framePolicy'], 'next')
        window.frame = {'annotatedImage': 'preview', 'cloud': {'points': [[1, 2, 3]]}, 'depth': {'width': 1}}
        window.use_frame()
        self.assertEqual(frames[0]['cloud']['points'], [[1, 2, 3]])
        self.assertEqual(frames[0]['depth']['width'], 1)

    def test_camera_parameters_preserve_optional_device_settings(self):
        window = self.window(CameraDialog)
        self.assertNotIn('width', window.params())
        window.set_params(dict(driver='gentl', providerId='provider-1', deviceId='cam-1', timeoutMs=7000, dataMode='pointcloud', rangeComponent=2, pointStride=8))
        self.assertEqual(window.params()['providerId'], 'provider-1')
        self.assertEqual(window.params()['dataMode'], 'pointcloud')
        self.assertEqual(window.params()['rangeComponent'], 2)
        self.assertEqual(window.params()['pointStride'], 8)
        window.start_session()
        request = self.backend.requests[-1]
        self.assertEqual(request[1], 'camera/session/start')
        self.assertFalse(request[2]['autoStart'])

    def test_training_open_and_dataset_create_do_not_start_training(self):
        window = self.window(TrainingDialog)
        window.show()
        self.app.processEvents()
        self.assertEqual([row[1] for row in self.backend.requests], ['training/status'])
        self.backend.respond('training/status', {'datasets': [], 'models': ['yolo11n.pt'], 'busy': False})
        window.new_id.setText('parts-native')
        window.create_dataset(False)
        self.assertEqual(self.backend.requests[-1][1:], ('training/datasets/create', {'id': 'parts-native', 'task': 'detect', 'names': ['part'], 'demo': False}))
        self.assertNotIn('training/start', [r[1] for r in self.backend.requests])

    def test_training_status_and_explicit_start_use_native_values(self):
        window = self.window(TrainingDialog)
        state = {'datasets': [dict(id='parts', task='segment', folder='C:/temp/parts', names=['part'])], 'models': ['yolo11n-seg.pt'], 'busy': False, 'job': {'state': 'completed', 'published': 'trained-parts.pt', 'task': 'segment', 'metrics': [{'epoch': 1, 'train/seg_loss': .25}]}}
        window._status(state)
        selected = []
        window.model_selected.connect(lambda op, model: selected.append((op, model)))
        window.add_model()
        self.assertEqual(selected, [('yolo_segment', 'trained-parts.pt')])
        window.start_training()
        params = self.backend.requests[-1][2]
        self.assertEqual(params['datasetId'], 'parts')
        self.assertEqual(params['imageSize'] % 32, 0)
        self.assertEqual(params['device'], 'cpu')

    def test_annotations_save_revision_and_edit_native_coordinates(self):
        window = self.window(AnnotationDialog, dict(id='parts', task='detect', names=['part']))
        window._loaded({'name': 'part.png', 'split': 'train', 'revision': 'v1', 'image': '', 'width': 100, 'height': 80, 'records': []})
        window.add_record({'classId': 0, 'box': [.5, .5, .4, .2]})
        window.change_coordinate(0, 0, 0, .6, True)
        self.assertTrue(window.dirty)
        window.save()
        method, params = self.backend.requests[-1][1:]
        self.assertEqual(method, 'training/annotations')
        self.assertEqual(params['action'], 'save')
        self.assertEqual(params['body']['revision'], 'v1')
        self.assertEqual(params['body']['records'][0]['box'][0], .6)
        self.backend.respond('training/annotations', {'revision': 'v2', 'objects': 1})
        self.assertFalse(window.dirty)
        self.assertEqual(window.loaded['revision'], 'v2')

    def test_continuous_dialog_does_not_connect_until_start_and_keeps_stop_enabled(self):
        document = Document()
        window = ContinuousDialog(document, self.backend)
        self.windows.append(window)
        window.set_input('image-data', {'points': [[1, 2, 3]]})
        window.show()
        self.app.processEvents()
        self.assertEqual({row[1] for row in self.backend.requests}, {'continuous/status', 'mqtt/status'})
        window.trust_continuous.setChecked(True)
        window.start_continuous()
        params = self.backend.requests[-1][2]
        self.assertEqual(params['image'], 'image-data')
        self.assertEqual(params['cloud']['points'], [[1, 2, 3]])
        self.assertTrue(params['allowScripts'])
        self.assertFalse(window.trust_continuous.isChecked())
        signals = []
        window.busy_changed.connect(signals.append)
        self.backend.respond('continuous/start', {'id': 'run-1', 'state': 'waiting', 'busy': True})
        window.set_busy(True)
        self.assertTrue(window.stop_button.isEnabled())
        window.hide()
        self.assertTrue(window.timer.isActive())
        window._state('continuous', {'state': 'completed', 'busy': False})
        self.assertEqual(signals, [True, False])
        self.assertFalse(window.timer.isActive())

    def test_mqtt_dialog_sends_structured_native_configuration_only_explicitly(self):
        window = ContinuousDialog(Document(), self.backend)
        self.windows.append(window)
        window.start_mqtt()
        method, params = self.backend.requests[-1][1:]
        self.assertEqual(method, 'mqtt/start')
        self.assertEqual(params['connection']['connection'], 'simulator')
        self.assertEqual(params['connection']['encoding'], 'structured')
        self.assertFalse(params['connection']['acceptRetained'])
        self.assertEqual(params['overflow'], 'stop')

    def test_continuous_result_signal_updates_once_per_completed_round(self):
        document = Document()
        window = ContinuousDialog(document, self.backend)
        self.windows.append(window)
        values = []
        window.result_ready.connect(values.append)
        state = {'id':'session', 'state':'waiting', 'busy':True, 'projectId':document.project['id'], 'lastJobId':'job-1'}
        window._state('continuous', state)
        result = {'projectId':document.project['id'], 'status':{'id':'job-1','state':'completed','elapsedMs':5}, 'results':[{'id':'vision','output':{'annotatedImage':'frame'}}]}
        self.backend.respond('runtime/view', result)
        self.assertEqual(values[0]['results'][0]['output']['annotatedImage'], 'frame')
        window._runtime_view(result)
        self.assertEqual(len(values), 1)
        self.assertTrue(window._announced_busy)
        window._state('continuous', {'state':'stopped', 'busy':False})


if __name__ == '__main__':
    unittest.main()
