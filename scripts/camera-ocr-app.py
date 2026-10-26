#!/usr/bin/env python3
"""MV camera + RapidOCR demo (native PySide6 App).

Flow: GenTL continuous grab → latest Mono8/BGR frame → RapidOCR → overlay + text panel.
Prefer this over web continuous preview. Q/Esc closes.
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

import cv2  # noqa: E402
import numpy as np  # noqa: E402
from PySide6.QtCore import Qt, QThread, Signal, Slot, QTimer  # noqa: E402
from PySide6.QtGui import QImage, QPixmap, QFont, QKeySequence, QShortcut  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QApplication, QHBoxLayout, QLabel, QMainWindow, QMessageBox, QPushButton,
    QPlainTextEdit, QVBoxLayout, QWidget,
)
from harvesters.core import Harvester  # noqa: E402
from cameras.gentl_compat import hikrobot_transport  # noqa: E402

CTI = Path('/opt/MVS/lib/64/MvProducerU3V.cti')
DEVICE_HINT = os.environ.get('SIEANS_LIVE_DEVICE', 'MV-CB013')
STATUS_PATH = Path('/tmp/sieans-camera-ocr.status')
OUT_DIR = ROOT / 'artifacts'
MIN_CONF = float(os.environ.get('SIEANS_OCR_MIN_CONF', '0.5'))


class GrabWorker(QThread):
    frame_ready = Signal(object, int, int, float)  # gray bytes, w, h, fps
    failed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._stop = False
        self._last_emit = 0.0

    def stop(self):
        self._stop = True

    def run(self):
        try:
            self._run()
        except Exception as exc:  # noqa: BLE001
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
                self.failed.emit('未枚举到 GenTL 设备（关闭 MVS / 网页 / 其它预览）')
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
                        payload = np.ascontiguousarray(
                            np.asarray(component.data).reshape(h_px, w_px)
                        )
                        if payload.dtype != np.uint8:
                            lo, hi = float(payload.min()), float(payload.max())
                            if hi <= lo:
                                payload = np.zeros((h_px, w_px), np.uint8)
                            else:
                                payload = ((payload.astype(np.float32) - lo) * (255.0 / (hi - lo))).clip(0, 255).astype(np.uint8)
                        blob = payload.tobytes()
                    frames += 1
                    fps = frames / max(1e-6, time.time() - t0)
                    now = time.time()
                    if now - self._last_emit >= 1.0 / 30.0:
                        self.frame_ready.emit(blob, w_px, h_px, fps)
                        self._last_emit = now
                    if now - last_status >= 1.0:
                        STATUS_PATH.write_text(
                            f'fps={fps:.1f} frames={frames} size={w_px}x{h_px}\n',
                            encoding='utf-8',
                        )
                        last_status = now
            finally:
                try:
                    ia.stop()
                except Exception:
                    pass
                ia.destroy()
                h.reset()


class OcrWorker(QThread):
    finished_ok = Signal(object, object)  # items list, annotated BGR ndarray
    failed = Signal(str)

    def __init__(self, gray: np.ndarray, parent=None):
        super().__init__(parent)
        self.gray = gray

    def run(self):
        try:
            from rapidocr_onnxruntime import RapidOCR
            # engine.ocr expects BGR-like array for RapidOCR
            bgr = cv2.cvtColor(self.gray, cv2.COLOR_GRAY2BGR)
            engine = getattr(OcrWorker, '_engine', None)
            if engine is None:
                engine = RapidOCR(intra_op_num_threads=2, inter_op_num_threads=2)
                OcrWorker._engine = engine
            result, _ = engine(bgr)
            items = []
            canvas = bgr.copy()
            for points, text, confidence in result or []:
                conf = float(confidence)
                if conf < MIN_CONF:
                    continue
                pts = np.array(points, dtype=np.int32)
                cv2.polylines(canvas, [pts], True, (0, 220, 0), 2)
                x, y = int(pts[0][0]), max(18, int(pts[0][1]) - 6)
                cv2.putText(canvas, f'{text} ({conf:.2f})', (x, y),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 220, 0), 2, cv2.LINE_AA)
                items.append({'text': text, 'confidence': conf, 'polygon': pts.tolist()})
            self.finished_ok.emit(items, canvas)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(f'{type(exc).__name__}: {exc}')


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('SIEANS · 相机接入 + 字符识别（RapidOCR）')
        self.resize(1400, 900)
        root = QWidget()
        self.setCentralWidget(root)
        layout = QHBoxLayout(root)

        left = QVBoxLayout()
        self.view = QLabel('正在打开 MV 相机…')
        self.view.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.view.setMinimumSize(800, 600)
        self.view.setStyleSheet('background:#111; color:#9f9;')
        self.view.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        left.addWidget(self.view, 1)

        row = QHBoxLayout()
        self.btn_ocr = QPushButton('字符识别（当前帧）')
        self.btn_ocr.clicked.connect(self.run_ocr)
        self.btn_ocr.setEnabled(False)
        self.btn_auto = QPushButton('自动识别：关')
        self.btn_auto.setCheckable(True)
        self.btn_auto.toggled.connect(self._toggle_auto)
        self.btn_save = QPushButton('保存结果图')
        self.btn_save.clicked.connect(self.save_result)
        self.btn_save.setEnabled(False)
        row.addWidget(self.btn_ocr)
        row.addWidget(self.btn_auto)
        row.addWidget(self.btn_save)
        left.addLayout(row)
        layout.addLayout(left, 3)

        right = QVBoxLayout()
        right.addWidget(QLabel('识别结果（RapidOCR / ONNX）'))
        self.out = QPlainTextEdit()
        self.out.setReadOnly(True)
        self.out.setFont(QFont('Sans', 12))
        self.out.setPlaceholderText('点击「字符识别」对当前相机帧做 OCR…')
        right.addWidget(self.out, 1)
        self.status = QLabel('就绪')
        self.status.setWordWrap(True)
        right.addWidget(self.status)
        layout.addLayout(right, 2)

        self._gray = None
        self._annotated = None
        self._busy_paint = False
        self._ocr_busy = False
        self._ocr_thread = None
        self._fps = 0.0
        self._did_auto_once = False
        self._auto = QTimer(self)
        self._auto.setInterval(1500)
        self._auto.timeout.connect(self.run_ocr)

        QShortcut(QKeySequence('Q'), self, activated=self.close)
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self, activated=self.close)
        QShortcut(QKeySequence('Return'), self, activated=self.run_ocr)

    @Slot(object, int, int, float)
    def on_frame(self, blob, width, height, fps):
        raw = bytes(blob) if not isinstance(blob, (bytes, bytearray)) else blob
        gray = np.frombuffer(raw, dtype=np.uint8).reshape(height, width).copy()
        self._gray = gray
        self._fps = fps
        self.btn_ocr.setEnabled(True)
        if not self._did_auto_once:
            self._did_auto_once = True
            QTimer.singleShot(800, self.run_ocr)
        if self._busy_paint or self._annotated is not None and self._ocr_busy:
            # While OCR overlay is shown mid-run, still keep gray for next OCR
            if not self._ocr_busy:
                pass
            else:
                return
        if self._busy_paint:
            return
        self._busy_paint = True
        try:
            # Live view: grayscale → RGB888 for QImage (atomic QLabel setPixmap)
            rgb = cv2.cvtColor(gray, cv2.COLOR_GRAY2RGB)
            cv2.putText(rgb, f'{fps:.1f} fps  {width}x{height}  GenTL', (12, 28),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 220, 0), 2, cv2.LINE_AA)
            self._set_rgb(rgb)
            self.status.setText(f'相机连续取流中 · {fps:.1f} fps · {width}×{height} Mono8')
        finally:
            self._busy_paint = False

    def _set_rgb(self, rgb: np.ndarray):
        h, w, _ = rgb.shape
        image = QImage(rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888).copy()
        pix = QPixmap.fromImage(image)
        target = self.view.size()
        if target.width() > 2 and target.height() > 2:
            pix = pix.scaled(target, Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.FastTransformation)
        self.view.setPixmap(pix)

    @Slot(str)
    def on_fail(self, message: str):
        self.view.setText(message)
        self.status.setText(message)
        self.btn_ocr.setEnabled(False)

    def _toggle_auto(self, on: bool):
        self.btn_auto.setText('自动识别：开' if on else '自动识别：关')
        if on:
            self._auto.start()
            self.run_ocr()
        else:
            self._auto.stop()

    def run_ocr(self):
        if self._ocr_busy or self._gray is None:
            return
        self._ocr_busy = True
        self.btn_ocr.setEnabled(False)
        self.status.setText('正在字符识别（首次加载模型较慢）…')
        gray = self._gray.copy()
        self._ocr_thread = OcrWorker(gray, self)
        self._ocr_thread.finished_ok.connect(self._on_ocr_ok)
        self._ocr_thread.failed.connect(self._on_ocr_fail)
        self._ocr_thread.finished.connect(self._on_ocr_done)
        self._ocr_thread.start()

    @Slot(object, object)
    def _on_ocr_ok(self, items, canvas_bgr):
        self._annotated = canvas_bgr
        rgb = cv2.cvtColor(canvas_bgr, cv2.COLOR_BGR2RGB)
        self._set_rgb(rgb)
        lines = []
        if not items:
            lines.append('（本帧未识别到达到阈值的文字 — 请把标签对准镜头、调曝光/对焦后重试）')
        else:
            for i, it in enumerate(items, 1):
                lines.append(f"{i}. {it['text']}    置信度 {it['confidence']:.3f}")
        text = '\n'.join(lines)
        self.out.setPlainText(text)
        self.status.setText(f'OCR 完成 · {len(items)} 条 · 阈值 ≥ {MIN_CONF}')
        self.btn_save.setEnabled(True)
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(OUT_DIR / 'camera_ocr_annotated.png'), canvas_bgr)
        (OUT_DIR / 'camera_ocr_result.txt').write_text(text + '\n', encoding='utf-8')
        print('OCR items:', items, flush=True)

    @Slot(str)
    def _on_ocr_fail(self, message: str):
        self.out.setPlainText(message)
        self.status.setText('OCR 失败')
        QMessageBox.warning(self, 'OCR 失败', message)

    def _on_ocr_done(self):
        self._ocr_busy = False
        self.btn_ocr.setEnabled(self._gray is not None)

    def save_result(self):
        if self._annotated is None:
            return
        path = OUT_DIR / 'camera_ocr_annotated.png'
        cv2.imwrite(str(path), self._annotated)
        self.status.setText(f'已保存 {path}')


def main() -> int:
    if not os.environ.get('QT_QPA_PLATFORM'):
        if os.environ.get('WAYLAND_DISPLAY') or os.environ.get('XDG_SESSION_TYPE') == 'wayland':
            os.environ['QT_QPA_PLATFORM'] = 'wayland'
        else:
            os.environ['QT_QPA_PLATFORM'] = 'xcb'
    print('SIEANS camera + OCR App', flush=True)
    print('引擎: RapidOCR onnxruntime 1.4.4 · 相机: GenTL', DEVICE_HINT, flush=True)
    app = QApplication(sys.argv)
    win = MainWindow()
    worker = GrabWorker()
    worker.frame_ready.connect(win.on_frame, Qt.ConnectionType.QueuedConnection)
    worker.failed.connect(win.on_fail, Qt.ConnectionType.QueuedConnection)
    win.show()
    worker.start()

    def shutdown():
        win._auto.stop()
        worker.stop()
        worker.wait(5000)

    app.aboutToQuit.connect(shutdown)
    code = app.exec()
    shutdown()
    return int(code)


if __name__ == '__main__':
    raise SystemExit(main())
