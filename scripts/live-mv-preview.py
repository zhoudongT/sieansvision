#!/usr/bin/env python3
"""Native continuous live view for Hikrobot MV GenTL (PySide6 App path).

Avoids OpenCV HighGUI (known to flicker / tear on Linux X11) and the web
PNG-over-HTTP path. Mono8 frames go straight into QImage → QLabel.setPixmap
(atomic paint). Grab runs on a worker thread; UI updates on the GUI thread.
Close the window or press Q / Esc to exit.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '.pydeps'))
sys.path.insert(0, str(ROOT))

os.environ.setdefault(
    'SIEANS_GENTL_CTI',
    '/opt/MVS/lib/64/MvProducerU3V.cti:/opt/MVS/lib/64/MvProducerGEV.cti',
)
os.environ.setdefault('MVCAM_COMMON_RUNENV', '/opt/MVS/lib')
ld = os.environ.get('LD_LIBRARY_PATH', '')
mvs = '/opt/MVS/lib/64'
if mvs not in ld.split(':'):
    os.environ['LD_LIBRARY_PATH'] = mvs + (':' + ld if ld else '')

import numpy as np  # noqa: E402
from PySide6.QtCore import Qt, QThread, Signal, Slot  # noqa: E402
from PySide6.QtGui import QImage, QPixmap, QPainter, QColor, QFont, QKeySequence, QShortcut  # noqa: E402
from PySide6.QtWidgets import QApplication, QLabel, QMainWindow, QVBoxLayout, QWidget  # noqa: E402
from harvesters.core import Harvester  # noqa: E402
from cameras.gentl_compat import hikrobot_transport  # noqa: E402

CTI = Path('/opt/MVS/lib/64/MvProducerU3V.cti')
DEVICE_HINT = os.environ.get('SIEANS_LIVE_DEVICE', 'MV-CB013')
STATUS_PATH = Path('/tmp/sieans-live-mv.status')
PREVIEW_PATH = ROOT / 'artifacts' / 'live_mv_preview_frame.png'


class GrabWorker(QThread):
    frame_ready = Signal(object, int, int, float)  # bytes, w, h, fps
    failed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        try:
            self._run()
        except Exception as exc:  # noqa: BLE001 — surface to UI
            self.failed.emit(f'{type(exc).__name__}: {exc}')

    def _run(self):
        if not CTI.is_file():
            self.failed.emit(f'找不到 CTI: {CTI}')
            return
        with hikrobot_transport(str(CTI)):
            h = Harvester()
            h.add_file(str(CTI))
            h.update()
            if not h.device_info_list:
                self.failed.emit('未枚举到 GenTL 设备（请关闭 MVS / 网页 / 其它预览）')
                return
            index = 0
            for i, info in enumerate(h.device_info_list):
                label = ' '.join(
                    str(getattr(info, k, '') or '')
                    for k in ('vendor', 'model', 'serial_number', 'display_name')
                )
                print(f'  [{i}] {label}', flush=True)
                if DEVICE_HINT.lower() in label.lower():
                    index = i
            print('使用设备 index', index, flush=True)
            ia = h.create(index)
            try:
                ia.start()
                frames = 0
                t0 = time.time()
                last_status = 0.0
                while not self._stop:
                    with ia.fetch(timeout=3) as buffer:
                        component = buffer.payload.components[0]
                        try:
                            h_px = int(component.height)
                            w_px = int(component.width)
                        except Exception:
                            n = int(np.asarray(component.data).size)
                            w_px, h_px = 1280, 1024
                            if n != w_px * h_px and n > 0:
                                w_px = int(n ** 0.5)
                                while w_px > 1 and n % w_px:
                                    w_px -= 1
                                h_px = n // max(1, w_px)
                        # Own the pixels before GenTL reuses the buffer.
                        payload = np.asarray(component.data).reshape(h_px, w_px)
                        if payload.dtype != np.uint8:
                            payload = cv2_normalize(payload)
                        else:
                            payload = np.ascontiguousarray(payload)
                        blob = payload.tobytes()
                    frames += 1
                    fps = frames / max(1e-6, time.time() - t0)
                    now = time.time()
                    # Display ≤ ~60 Hz; still drain GenTL full rate so buffer stays fresh.
                    if not hasattr(self, '_last_emit'):
                        self._last_emit = 0.0
                    if now - self._last_emit >= (1.0 / 60.0):
                        self.frame_ready.emit(blob, w_px, h_px, fps)
                        self._last_emit = now
                    if now - last_status >= 1.0:
                        STATUS_PATH.write_text(
                            f'fps={fps:.1f} frames={frames} size={w_px}x{h_px}\n',
                            encoding='utf-8',
                        )
                        print(f'live {fps:.1f} fps  frames={frames}  {w_px}x{h_px}', flush=True)
                        last_status = now
                print(f'结束：共 {frames} 帧，平均 {frames / max(1e-6, time.time() - t0):.1f} fps', flush=True)
            finally:
                try:
                    ia.stop()
                except Exception:
                    pass
                ia.destroy()
                h.reset()


def cv2_normalize(data: np.ndarray) -> np.ndarray:
    scaled = data.astype(np.float32)
    lo, hi = float(scaled.min()), float(scaled.max())
    if hi <= lo:
        return np.zeros(data.shape, dtype=np.uint8)
    return np.ascontiguousarray(((scaled - lo) * (255.0 / (hi - lo))).clip(0, 255).astype(np.uint8))


class LiveWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('SIEANS MV 连续预览（原生 App）')
        self.resize(1280, 1024)
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        self.label = QLabel('正在打开相机…')
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setStyleSheet('background:#111; color:#9f9; font-size:16px;')
        self.label.setMinimumSize(640, 480)
        # Opaque paint avoids compositor clear→flash between frames.
        self.label.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        layout.addWidget(self.label)
        self._last_save = 0.0
        self._busy = False
        QShortcut(QKeySequence('Q'), self, activated=self.close)
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self, activated=self.close)

    @Slot(object, int, int, float)
    def on_frame(self, blob: object, width: int, height: int, fps: float):
        if self._busy:
            return  # drop stale queued frames — keeps latest-feel without flash backlog
        self._busy = True
        try:
            self._paint_frame(blob, width, height, fps)
        finally:
            self._busy = False

    def _paint_frame(self, blob: object, width: int, height: int, fps: float):
        raw = bytes(blob) if not isinstance(blob, (bytes, bytearray)) else blob
        image = QImage(raw, width, height, width, QImage.Format.Format_Grayscale8).copy()
        painter = QPainter(image)
        painter.setPen(QColor(0, 220, 0))
        painter.setFont(QFont('Sans', 16, QFont.Weight.Bold))
        painter.drawText(12, 28, f'{fps:.1f} fps  {width}x{height}')
        painter.end()
        pixmap = QPixmap.fromImage(image)
        # KeepAspectRatioByExpanding would crop; KeepAspectRatio + letterbox is stable.
        target = self.label.size()
        if target.width() > 2 and target.height() > 2:
            pixmap = pixmap.scaled(
                target,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.FastTransformation,
            )
        self.label.setPixmap(pixmap)
        now = time.time()
        if now - self._last_save >= 1.0:
            PREVIEW_PATH.parent.mkdir(parents=True, exist_ok=True)
            image.save(str(PREVIEW_PATH))
            self._last_save = now

    @Slot(str)
    def on_fail(self, message: str):
        self.label.setText(message)
        print(message, file=sys.stderr, flush=True)


def main() -> int:
    print('打开 GenTL:', CTI, flush=True)
    print('目标设备包含:', DEVICE_HINT, flush=True)
    print('按 Q / Esc 或关闭窗口结束', flush=True)
    # GNOME here is Wayland; PySide6 xcb needs libxcb-cursor0 (may be missing).
    # Prefer wayland when available; allow override via QT_QPA_PLATFORM.
    if not os.environ.get('QT_QPA_PLATFORM'):
        os.environ['QT_QPA_PLATFORM'] = 'wayland' if os.environ.get('WAYLAND_DISPLAY') or os.environ.get('XDG_SESSION_TYPE') == 'wayland' else 'xcb'
    app = QApplication(sys.argv)
    app.setApplicationName('SIEANS MV Live')
    win = LiveWindow()
    worker = GrabWorker()
    worker.frame_ready.connect(win.on_frame, Qt.ConnectionType.QueuedConnection)
    worker.failed.connect(win.on_fail, Qt.ConnectionType.QueuedConnection)
    worker.finished.connect(app.quit)
    win.show()
    worker.start()

    def _shutdown():
        worker.stop()
        worker.wait(5000)

    app.aboutToQuit.connect(_shutdown)
    code = app.exec()
    _shutdown()
    return int(code)


if __name__ == '__main__':
    raise SystemExit(main())
