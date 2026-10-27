"""Camera manager shell must expose a complete GenTL/SDK connect path (no dead toggles)."""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from PySide6.QtWidgets import QApplication


class CameraManagerDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _backend(self, ready=True):
        b = MagicMock()
        b.is_ready = ready
        b.result = MagicMock()
        b.error = MagicMock()
        b.ready = MagicMock()
        b.request = MagicMock(side_effect=lambda *a, **k: 'rid-' + (a[0] if a else 'x'))
        return b

    def test_connect_without_device_gives_actionable_message(self):
        from desktop.camera_manager import CameraManagerDialog
        dlg = CameraManagerDialog(self._backend(True), None)
        dlg.connect_sw.setChecked(True)
        self.assertFalse(dlg.connect_sw.isChecked())
        self.assertIn('选择相机', dlg.message.text())

    def test_connect_when_engine_down_is_honest(self):
        from desktop.camera_manager import CameraManagerDialog
        dlg = CameraManagerDialog(self._backend(False), None)
        dlg.connect_sw.setChecked(True)
        self.assertFalse(dlg.connect_sw.isChecked())
        self.assertIn('引擎未就绪', dlg.message.text())

    def test_list_result_fills_camera_pick(self):
        from desktop.camera_manager import CameraManagerDialog
        dlg = CameraManagerDialog(self._backend(True), None)
        dlg._on_list({'result': {'items': [
            {'name': 'MV-CB013', 'deviceId': 'Hikrobot MV-CB013', 'serial': 'K1', 'model': 'MV-CB013'},
        ]}})
        ids = [dlg.camera_pick.itemData(i) for i in range(dlg.camera_pick.count())]
        self.assertIn('Hikrobot MV-CB013', ids)
        self.assertIn('', ids)  # Close

    def test_session_running_sets_connect_switch(self):
        from desktop.camera_manager import CameraManagerDialog
        dlg = CameraManagerDialog(self._backend(True), None)
        dlg.camera_pick.addItem('cam', 'dev-1')
        dlg.camera_pick.setCurrentIndex(dlg.camera_pick.count() - 1)
        dlg._on_session({'state': 'running', 'id': 's1', 'config': {'params': {
            'driver': 'gentl', 'deviceId': 'dev-1', 'providerId': 'p',
        }}})
        self.assertTrue(dlg.connect_sw.isChecked())
        self.assertIn('已连接', dlg.message.text())


if __name__ == '__main__':
    unittest.main()
