# -*- coding: utf-8 -*-
"""Simple ROI rect editor — industrial style for OCR / defects crop (no Halcon).

Reuses caliper RoiRectItem; writes params.roi + roiMode='draw'.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QPixmap, QPainter, QColor, QPen
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFormLayout,
    QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QFileDialog, QSpinBox,
    QDialogButtonBox, QMessageBox,
)


def _load_pixmap(image_data) -> QPixmap:
    pm = QPixmap()
    if not image_data:
        return pm
    if isinstance(image_data, str) and image_data.startswith('data:image'):
        import base64
        b64 = image_data.split(',', 1)[-1]
        try:
            pm.loadFromData(base64.b64decode(b64))
        except Exception:
            pass
        return pm
    if isinstance(image_data, (bytes, bytearray)):
        pm.loadFromData(bytes(image_data))
        return pm
    try:
        pm.load(str(image_data))
    except Exception:
        pass
    return pm


class SimpleRoiEditorDialog(QDialog):
    """Drag/resize orange ROI → write back [x,y,w,h]."""

    def __init__(self, params: dict, parent=None, image_data=None, title='ROI 编辑器'):
        super().__init__(parent)
        from copy import deepcopy
        self._params = deepcopy(params or {})
        self._result = None
        self.setWindowTitle(title)
        self.setObjectName('simpleRoiEditor')
        self.resize(860, 560)

        root = QVBoxLayout(self)
        tip = QLabel('拖动橙框移动 ROI；拖四角缩放。写入后 roiMode→draw，运行时引擎按 roi 裁剪。')
        tip.setWordWrap(True)
        tip.setStyleSheet('color:#888;font-size:11px;')
        root.addWidget(tip)

        body = QHBoxLayout()
        root.addLayout(body, 1)

        self.scene = QGraphicsScene(self)
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHints(self.view.renderHints() | QPainter.RenderHint.Antialiasing)
        self.view.setBackgroundBrush(QColor('#1a1d22'))
        self.view.setObjectName('simpleRoiView')
        body.addWidget(self.view, 1)

        side = QVBoxLayout()
        body.addLayout(side)
        form = QFormLayout()
        side.addLayout(form)
        self.roi_lab = QLabel('ROI: —')
        self.roi_lab.setObjectName('simpleRoiLabel')
        self.roi_lab.setStyleSheet('color:#9ad;font-size:11px;')
        form.addRow(self.roi_lab)

        self.spins = {}
        for key, lab, mx in (('x', 'X', 20000), ('y', 'Y', 20000), ('w', '宽', 20000), ('h', '高', 20000)):
            sp = QSpinBox()
            sp.setRange(0 if key in ('x', 'y') else 1, mx)
            sp.setObjectName(f'simpleRoiSpin_{key}')
            self.spins[key] = sp
            form.addRow(lab, sp)

        b_img = QPushButton('载入底图…')
        b_img.setObjectName('simpleRoiLoadImgBtn')
        b_img.clicked.connect(self._load_image_file)
        side.addWidget(b_img)
        b_full = QPushButton('铺满全图')
        b_full.setObjectName('simpleRoiFullBtn')
        b_full.clicked.connect(self._fill_full)
        side.addWidget(b_full)
        b_center = QPushButton('居中半幅')
        b_center.setObjectName('simpleRoiCenterBtn')
        b_center.clicked.connect(self._fill_center)
        side.addWidget(b_center)
        side.addStretch(1)

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self._accept)
        bb.rejected.connect(self.reject)
        root.addWidget(bb)

        self._img_w = 640
        self._img_h = 480
        self._pix_item = None
        self.roi_item = None
        self._spin_guard = False

        for sp in self.spins.values():
            sp.valueChanged.connect(self._spins_to_roi)

        self._load_image(image_data)

    def _load_image(self, image_data):
        from desktop.caliper_roi_editor import RoiRectItem
        pm = _load_pixmap(image_data)
        if pm.isNull():
            # blank canvas
            pm = QPixmap(640, 480)
            pm.fill(QColor('#2a2e35'))
        self._img_w = pm.width()
        self._img_h = pm.height()
        self.scene.clear()
        self._pix_item = QGraphicsPixmapItem(pm)
        self.scene.addItem(self._pix_item)
        self.scene.setSceneRect(0, 0, self._img_w, self._img_h)

        roi = self._params.get('roi')
        if isinstance(roi, list) and len(roi) == 4:
            x, y, w, h = [float(v) for v in roi]
        else:
            w = max(40.0, self._img_w * 0.5)
            h = max(40.0, self._img_h * 0.5)
            x = (self._img_w - w) / 2
            y = (self._img_h - h) / 2
        self.roi_item = RoiRectItem(QRectF(0, 0, w, h), on_changed=self._on_roi_changed)
        self.roi_item.setPos(x, y)
        self.scene.addItem(self.roi_item)
        self._on_roi_changed()
        self.view.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def _load_image_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, '载入底图', '', '图像 (*.png *.bmp *.jpg *.jpeg *.tif);;所有文件 (*)'
        )
        if path:
            self._load_image(path)

    def _on_roi_changed(self):
        if self.roi_item is None:
            return
        x, y, w, h = self.roi_item.roi_list()
        self.roi_lab.setText(f'ROI: [{x:.0f}, {y:.0f}, {w:.0f}, {h:.0f}]')
        self._spin_guard = True
        try:
            self.spins['x'].setValue(int(round(x)))
            self.spins['y'].setValue(int(round(y)))
            self.spins['w'].setValue(max(1, int(round(w))))
            self.spins['h'].setValue(max(1, int(round(h))))
        finally:
            self._spin_guard = False

    def _spins_to_roi(self, *_):
        if self._spin_guard or self.roi_item is None:
            return
        x = self.spins['x'].value()
        y = self.spins['y'].value()
        w = self.spins['w'].value()
        h = self.spins['h'].value()
        self.roi_item.setPos(x, y)
        self.roi_item.setRect(QRectF(0, 0, w, h))
        self.roi_lab.setText(f'ROI: [{x}, {y}, {w}, {h}]')

    def _fill_full(self):
        if self.roi_item is None:
            return
        self.roi_item.setPos(0, 0)
        self.roi_item.setRect(QRectF(0, 0, self._img_w, self._img_h))
        self._on_roi_changed()

    def _fill_center(self):
        if self.roi_item is None:
            return
        w = max(40.0, self._img_w * 0.5)
        h = max(40.0, self._img_h * 0.5)
        self.roi_item.setPos((self._img_w - w) / 2, (self._img_h - h) / 2)
        self.roi_item.setRect(QRectF(0, 0, w, h))
        self._on_roi_changed()

    def _accept(self):
        if self.roi_item is None:
            QMessageBox.warning(self, 'ROI', '无有效 ROI')
            return
        x, y, w, h = self.roi_item.roi_list()
        if w < 2 or h < 2:
            QMessageBox.warning(self, 'ROI', 'ROI 宽高过小')
            return
        self._result = {
            'roi': [round(x, 2), round(y, 2), round(w, 2), round(h, 2)],
            'roiMode': 'draw',
        }
        self.accept()

    def result_params(self) -> dict:
        return dict(self._result or {})
