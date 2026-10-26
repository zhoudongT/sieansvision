"""Exercise the actual QProcess bridge with a Qt event loop and owned host."""
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from PySide6.QtCore import QCoreApplication, QEventLoop, QProcess, QTimer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from desktop.backend import Backend, _python_executable


class NativeBackendTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(prefix="native-qt-test-")
        self.backend = Backend()
        self.results = {}
        self.errors = {}
        self.stopped = False
        self.backend.result.connect(lambda request_id, value: self.results.__setitem__(request_id, value))
        self.backend.error.connect(lambda request_id, value: self.errors.__setitem__(request_id, value))
        self.backend.stopped.connect(lambda: setattr(self, "stopped", True))

    def until(self, predicate, seconds=15):
        started = time.monotonic()
        while not predicate() and time.monotonic() - started < seconds:
            loop = QEventLoop()
            QTimer.singleShot(10, loop.quit)
            loop.exec()
        self.assertTrue(predicate(), f"Qt condition timed out; errors: {self.errors}")

    def tearDown(self):
        self.backend.shutdown()
        self.until(lambda: self.backend.process.state() == QProcess.ProcessState.NotRunning)
        self.backend.deleteLater()
        self.app.processEvents()
        self.folder.cleanup()

    def test_real_process_async_request_cancel_and_shutdown(self):
        self.backend.start(ROOT, Path(self.folder.name))
        self.until(lambda: self.backend.is_ready)
        self.assertEqual(self.backend.info["protocolVersion"], 1)
        plugins = self.backend.request("plugins/list")
        self.until(lambda: plugins in self.results)
        self.assertIsInstance(self.results[plugins], list)
        project = {"version": 1, "id": "qt-test", "name": "Qt异步验证", "steps": [
            {"id": "wait", "operation": "delay", "params": {"milliseconds": 30000}}
        ]}
        ticks = []
        timer = QTimer()
        timer.timeout.connect(lambda: ticks.append(True))
        timer.start(10)
        run = self.backend.request("run", {"project": project})
        self.until(lambda: len(ticks) >= 5)
        stop = self.backend.request("stop")
        self.until(lambda: run in self.results and stop in self.results)
        timer.stop()
        self.assertEqual(self.results[run]["state"], "cancelled")
        self.assertEqual(self.results[stop]["state"], "cancelled")
        self.backend.shutdown()
        self.until(lambda: self.stopped)
        self.assertEqual(self.backend.process.state(), QProcess.ProcessState.NotRunning)
        self.assertFalse(self.errors, json.dumps(self.errors, ensure_ascii=False))

    def test_start_failure_is_reported_and_shutdown_is_idempotent(self):
        self.backend.start(Path(self.folder.name), Path(self.folder.name) / "data")
        self.until(lambda: self.stopped)
        self.assertIn("找不到原生引擎", self.errors[""])
        self.backend.shutdown()
        self.backend.shutdown()

    def test_shutdown_while_qprocess_is_starting(self):
        self.backend.start(ROOT, Path(self.folder.name))
        self.backend.shutdown()
        self.until(lambda: self.stopped)
        self.assertEqual(self.backend.process.state(), QProcess.ProcessState.NotRunning)
        self.assertFalse(self.errors, self.errors)

    def test_engine_crash_is_reported(self):
        self.backend.start(ROOT, Path(self.folder.name))
        self.until(lambda: self.backend.is_ready)
        self.backend.process.kill()
        self.until(lambda: self.stopped)
        self.assertIn("", self.errors)
        self.assertFalse(self.backend.is_ready)

    def test_frozen_app_selects_real_python_and_honors_override(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(sys, "frozen", True, create=True):
            local = ROOT / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
            self.assertEqual(_python_executable(ROOT), str(local))
            with patch("desktop.backend.shutil.which", return_value=None):
                self.assertIsNone(_python_executable(Path(self.folder.name)))
            with patch("desktop.backend.shutil.which", return_value="/python/runtime"):
                self.assertEqual(_python_executable(Path(self.folder.name)), "/python/runtime")
            with patch.dict(os.environ, {"VISION_PYTHON": "C:/vision/python.exe"}):
                self.assertEqual(_python_executable(ROOT), "C:/vision/python.exe")


if __name__ == "__main__":
    unittest.main()
