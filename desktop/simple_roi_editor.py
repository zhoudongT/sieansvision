# -*- coding: utf-8 -*-
"""Simple ROI rect editor — industrial style for OCR / defects / preprocess crop (no Halcon).

Shared editor polish (wave142): aspect lock + presets, keyboard nudge, copy coords,
fit/100% zoom, crosshair guides, edge snap. Reuses caliper RoiRectItem.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QPixmap, QPainter, QColor, QPen, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFormLayout,
    QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QFileDialog, QSpinBox,
    QDialogButtonBox, QMessageBox, QCheckBox, QComboBox, QApplication,
    QGraphicsLineItem,
)


def _load_pixmap(image_data) -> QPixmap:
    pm = QPixmap()
    if image_data is None:
        return pm
    # numpy ndarray (H,W) or (H,W,C) → QImage
    try:
        import numpy as np
        if isinstance(image_data, np.ndarray):
            from PySide6.QtGui import QImage
            arr = np.ascontiguousarray(image_data)
            h, w = arr.shape[:2]
            if arr.ndim == 2:
                qimg = QImage(arr.data, w, h, w, QImage.Format.Format_Grayscale8)
            elif arr.ndim == 3 and arr.shape[2] >= 3:
                # BGR→RGB if OpenCV-ish; treat as RGB888 for soft preview
                rgb = np.ascontiguousarray(arr[:, :, :3])
                # assume RGB already for synthetic smoke; swap if needed by caller
                qimg = QImage(rgb.data, w, h, w * 3, QImage.Format.Format_RGB888)
            else:
                return pm
            return QPixmap.fromImage(qimg.copy())
    except Exception:
        pass
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
    if isinstance(image_data, str) and not image_data:
        return pm
    try:
        pm.load(str(image_data))
    except Exception:
        pass
    return pm


class SimpleRoiEditorDialog(QDialog):
    """Drag/resize orange ROI → write back [x,y,w,h]. Industrial draw polish."""

    def __init__(self, params: dict, parent=None, image_data=None, title='ROI 编辑器'):
        super().__init__(parent)
        from copy import deepcopy
        self._params = deepcopy(params or {})
        self._result = None
        self._aspect_lock = False
        self._aspect_ratio = None  # w/h when locked
        self._crosshair = True
        self.setWindowTitle(title)
        self.setObjectName('simpleRoiEditor')
        self.resize(920, 600)

        root = QVBoxLayout(self)
        tip = QLabel(
            '拖动橙框移动 ROI；拖四角缩放。方向键微调（Shift=10px）。'
            '写入后 roiMode→draw，运行时引擎按 roi 裁剪。'
        )
        tip.setWordWrap(True)
        tip.setStyleSheet('color:#888;font-size:11px;')
        tip.setObjectName('simpleRoiTip')
        root.addWidget(tip)

        body = QHBoxLayout()
        root.addLayout(body, 1)

        self.scene = QGraphicsScene(self)
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHints(self.view.renderHints() | QPainter.RenderHint.Antialiasing)
        self.view.setBackgroundBrush(QColor('#1a1d22'))
        self.view.setObjectName('simpleRoiView')
        self.view.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
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

        # --- industrial polish ---
        self.aspect_lock = QCheckBox('锁定宽高比')
        self.aspect_lock.setObjectName('simpleRoiAspectLock')
        self.aspect_lock.toggled.connect(self._on_aspect_lock)
        form.addRow(self.aspect_lock)

        self.aspect_preset = QComboBox()
        self.aspect_preset.setObjectName('simpleRoiAspectPreset')
        for lab, val in (
            ('自由', None),
            ('1:1', 1.0),
            ('4:3', 4 / 3),
            ('16:9', 16 / 9),
            ('3:2', 1.5),
        ):
            self.aspect_preset.addItem(lab, val)
        self.aspect_preset.currentIndexChanged.connect(self._on_aspect_preset)
        form.addRow('比例预设', self.aspect_preset)

        self.crosshair_cb = QCheckBox('十字参考线')
        self.crosshair_cb.setObjectName('simpleRoiCrosshair')
        self.crosshair_cb.setChecked(True)
        self.crosshair_cb.toggled.connect(self._on_crosshair)
        form.addRow(self.crosshair_cb)

        b_img = QPushButton('载入底图…')
        b_img.setObjectName('simpleRoiLoadImgBtn')
        b_img.clicked.connect(self._load_image_file)
        side.addWidget(b_img)

        zoom_row = QHBoxLayout()
        b_fit = QPushButton('适应')
        b_fit.setObjectName('simpleRoiZoomFitBtn')
        b_fit.clicked.connect(self._zoom_fit)
        b_100 = QPushButton('100%')
        b_100.setObjectName('simpleRoiZoom100Btn')
        b_100.clicked.connect(self._zoom_100)
        zoom_row.addWidget(b_fit)
        zoom_row.addWidget(b_100)
        side.addLayout(zoom_row)

        b_full = QPushButton('铺满全图')
        b_full.setObjectName('simpleRoiFullBtn')
        b_full.clicked.connect(self._fill_full)
        side.addWidget(b_full)
        b_center = QPushButton('居中半幅')
        b_center.setObjectName('simpleRoiCenterBtn')
        b_center.clicked.connect(self._fill_center)
        side.addWidget(b_center)

        snap_row = QHBoxLayout()
        for lab, obj, fn in (
            ('贴左', 'simpleRoiSnapLeftBtn', 'left'),
            ('贴顶', 'simpleRoiSnapTopBtn', 'top'),
            ('贴右', 'simpleRoiSnapRightBtn', 'right'),
            ('贴底', 'simpleRoiSnapBottomBtn', 'bottom'),
        ):
            b = QPushButton(lab)
            b.setObjectName(obj)
            b.clicked.connect(lambda _=False, e=fn: self._snap_edge(e))
            snap_row.addWidget(b)
        side.addLayout(snap_row)

        b_copy = QPushButton('复制坐标')
        b_copy.setObjectName('simpleRoiCopyBtn')
        b_copy.clicked.connect(self._copy_coords)
        side.addWidget(b_copy)

        nudge = QLabel('方向键微调 · Shift+方向键 ×10')
        nudge.setObjectName('simpleRoiNudgeHint')
        nudge.setStyleSheet('color:#666;font-size:10px;')
        side.addWidget(nudge)
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
        self._cross_h = None
        self._cross_v = None

        for sp in self.spins.values():
            sp.valueChanged.connect(self._spins_to_roi)

        # keyboard nudge shortcuts
        for key, dx, dy in (
            (Qt.Key.Key_Left, -1, 0), (Qt.Key.Key_Right, 1, 0),
            (Qt.Key.Key_Up, 0, -1), (Qt.Key.Key_Down, 0, 1),
        ):
            sc = QShortcut(QKeySequence(key), self)
            sc.activated.connect(lambda ddx=dx, ddy=dy: self._nudge(ddx, ddy, 1))
            sc2 = QShortcut(QKeySequence(Qt.KeyboardModifier.ShiftModifier | key), self)
            sc2.activated.connect(lambda ddx=dx, ddy=dy: self._nudge(ddx, ddy, 10))

        self._load_image(image_data)

    def _load_image(self, image_data):
        from desktop.caliper_roi_editor import RoiRectItem
        pm = _load_pixmap(image_data)
        if pm.isNull():
            pm = QPixmap(640, 480)
            pm.fill(QColor('#2a2e35'))
        self._img_w = pm.width()
        self._img_h = pm.height()
        self.scene.clear()
        self._cross_h = self._cross_v = None
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
        self._ensure_crosshair()
        self._on_roi_changed()
        self._zoom_fit()

    def _ensure_crosshair(self):
        if not self._crosshair:
            if self._cross_h is not None:
                self.scene.removeItem(self._cross_h)
                self.scene.removeItem(self._cross_v)
                self._cross_h = self._cross_v = None
            return
        pen = QPen(QColor(0, 188, 212, 120))
        pen.setStyle(Qt.PenStyle.DashLine)
        pen.setWidthF(1.0)
        if self._cross_h is None:
            self._cross_h = QGraphicsLineItem()
            self._cross_h.setPen(pen)
            self._cross_h.setZValue(5)
            self.scene.addItem(self._cross_h)
            self._cross_v = QGraphicsLineItem()
            self._cross_v.setPen(pen)
            self._cross_v.setZValue(5)
            self.scene.addItem(self._cross_v)
        self._update_crosshair()

    def _update_crosshair(self):
        if self._cross_h is None or self.roi_item is None:
            return
        x, y, w, h = self.roi_item.roi_list()
        cx, cy = x + w / 2, y + h / 2
        self._cross_h.setLine(0, cy, self._img_w, cy)
        self._cross_v.setLine(cx, 0, cx, self._img_h)

    def _on_crosshair(self, checked):
        self._crosshair = bool(checked)
        self._ensure_crosshair()

    def _on_aspect_lock(self, checked):
        self._aspect_lock = bool(checked)
        if self._aspect_lock and self.roi_item is not None:
            x, y, w, h = self.roi_item.roi_list()
            if h > 0:
                self._aspect_ratio = w / h

    def _on_aspect_preset(self):
        val = self.aspect_preset.currentData()
        if val is None:
            self.aspect_lock.setChecked(False)
            self._aspect_ratio = None
            return
        self._aspect_ratio = float(val)
        self.aspect_lock.setChecked(True)
        if self.roi_item is None:
            return
        x, y, w, h = self.roi_item.roi_list()
        # keep width, adjust height
        nh = max(2.0, w / self._aspect_ratio)
        if y + nh > self._img_h:
            nh = max(2.0, self._img_h - y)
            w = nh * self._aspect_ratio
        self.roi_item.setPos(x, y)
        self.roi_item.setRect(QRectF(0, 0, w, nh))
        self._on_roi_changed()

    def _load_image_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, '载入底图', '', '图像 (*.png *.bmp *.jpg *.jpeg *.tif);;所有文件 (*)'
        )
        if path:
            self._load_image(path)


    def _annotate_density_pen(self, kind='roi'):
        """wave143 shared annotate draw density pens."""
        try:
            from desktop.annotate_draw_density import pen_style, shared_editor_defaults
            return pen_style(kind), shared_editor_defaults()
        except Exception:
            return {'color': '#e8a838', 'width': 2.0, 'style': 'solid'}, {}

    def _on_roi_changed(self):
        if self.roi_item is None:
            return
        if self._aspect_lock and self._aspect_ratio and self._aspect_ratio > 0:
            # enforce aspect after drag (best-effort)
            x, y, w, h = self.roi_item.roi_list()
            target_h = max(2.0, w / self._aspect_ratio)
            if abs(target_h - h) > 0.5:
                self.roi_item.blockSignals(True) if hasattr(self.roi_item, 'blockSignals') else None
                try:
                    self.roi_item.setRect(QRectF(0, 0, w, target_h))
                finally:
                    pass
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
        self._update_crosshair()

    def _spins_to_roi(self, *_):
        if self._spin_guard or self.roi_item is None:
            return
        x = self.spins['x'].value()
        y = self.spins['y'].value()
        w = self.spins['w'].value()
        h = self.spins['h'].value()
        if self._aspect_lock and self._aspect_ratio and self._aspect_ratio > 0:
            # width drives height when locked
            h = max(1, int(round(w / self._aspect_ratio)))
            self._spin_guard = True
            try:
                self.spins['h'].setValue(h)
            finally:
                self._spin_guard = False
        self.roi_item.setPos(x, y)
        self.roi_item.setRect(QRectF(0, 0, w, h))
        self.roi_lab.setText(f'ROI: [{x}, {y}, {w}, {h}]')
        self._update_crosshair()

    def _nudge(self, dx, dy, step=1):
        if self.roi_item is None:
            return
        x, y, w, h = self.roi_item.roi_list()
        nx = max(0, min(self._img_w - w, x + dx * step))
        ny = max(0, min(self._img_h - h, y + dy * step))
        self.roi_item.setPos(nx, ny)
        self._on_roi_changed()

    def _snap_edge(self, edge):
        if self.roi_item is None:
            return
        x, y, w, h = self.roi_item.roi_list()
        if edge == 'left':
            x = 0
        elif edge == 'top':
            y = 0
        elif edge == 'right':
            x = max(0, self._img_w - w)
        elif edge == 'bottom':
            y = max(0, self._img_h - h)
        self.roi_item.setPos(x, y)
        self._on_roi_changed()

    def _copy_coords(self):
        if self.roi_item is None:
            return
        x, y, w, h = self.roi_item.roi_list()
        text = f'[{round(x, 2)}, {round(y, 2)}, {round(w, 2)}, {round(h, 2)}]'
        QApplication.clipboard().setText(text)
        self.roi_lab.setText(f'ROI: {text} · 已复制')

    def _zoom_fit(self):
        self.view.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def _zoom_100(self):
        self.view.resetTransform()
        self.view.centerOn(self.scene.sceneRect().center())

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
        if self._aspect_lock and self._aspect_ratio and self._aspect_ratio > 0:
            h = w / self._aspect_ratio
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
