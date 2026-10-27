"""Interactive multi-caliper ROI editor — VM-class canvas beyond panel knobs.

Usable UI over perfect algorithms: drag ROI rect, live preview of caliper
probes (count/width/length/angle/searchDir), write back params.roi + caliper*.
No Halcon kernel.
"""
from __future__ import annotations

import base64
import math
from copy import deepcopy

from PySide6.QtCore import Qt, QRectF, QPointF, Signal
from PySide6.QtGui import QPen, QBrush, QColor, QPixmap, QPainter, QImage
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QGraphicsView,
    QGraphicsScene, QGraphicsRectItem, QGraphicsItem, QGraphicsLineItem,
    QGraphicsPolygonItem, QFormLayout, QSpinBox, QDoubleSpinBox, QComboBox,
    QWidget, QMessageBox, QFileDialog, QGroupBox,
)


HANDLE = 8


class _Handle(QGraphicsRectItem):
    def __init__(self, parent_roi, corner: str):
        super().__init__(-HANDLE / 2, -HANDLE / 2, HANDLE, HANDLE, parent_roi)
        self._roi = parent_roi
        self._corner = corner
        self.setBrush(QBrush(QColor('#e87722')))
        self.setPen(QPen(QColor('#222'), 1))
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setZValue(30)
        self.setCursor(Qt.CursorShape.SizeFDiagCursor if corner in ('tl', 'br')
                       else Qt.CursorShape.SizeBDiagCursor)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange and self.scene():
            # value is scene-ish relative to parent; keep in image bounds via parent
            return value
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            self._roi.on_handle_moved(self._corner, self.pos())
        return super().itemChange(change, value)


class RoiRectItem(QGraphicsRectItem):
    """Draggable / resizable ROI rectangle in image coordinates."""

    def __init__(self, rect: QRectF, on_changed=None):
        super().__init__(rect)
        self._on_changed = on_changed
        self.setPen(QPen(QColor('#e87722'), 2, Qt.PenStyle.SolidLine))
        self.setBrush(QBrush(QColor(232, 119, 34, 40)))
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setZValue(20)
        self._handles = {
            'tl': _Handle(self, 'tl'),
            'tr': _Handle(self, 'tr'),
            'bl': _Handle(self, 'bl'),
            'br': _Handle(self, 'br'),
        }
        self._sync_handles()
        self._updating = False

    def _sync_handles(self):
        r = self.rect()
        pos = {
            'tl': QPointF(r.left(), r.top()),
            'tr': QPointF(r.right(), r.top()),
            'bl': QPointF(r.left(), r.bottom()),
            'br': QPointF(r.right(), r.bottom()),
        }
        self._updating = True
        for k, h in self._handles.items():
            h.setPos(pos[k])
        self._updating = False

    def on_handle_moved(self, corner, local_pos: QPointF):
        if self._updating:
            return
        r = self.rect()
        x1, y1, x2, y2 = r.left(), r.top(), r.right(), r.bottom()
        if corner == 'tl':
            x1, y1 = local_pos.x(), local_pos.y()
        elif corner == 'tr':
            x2, y1 = local_pos.x(), local_pos.y()
        elif corner == 'bl':
            x1, y2 = local_pos.x(), local_pos.y()
        else:
            x2, y2 = local_pos.x(), local_pos.y()
        if x2 - x1 < 8:
            x2 = x1 + 8
        if y2 - y1 < 8:
            y2 = y1 + 8
        self.setRect(QRectF(QPointF(x1, y1), QPointF(x2, y2)))
        self._sync_handles()
        if self._on_changed:
            self._on_changed()

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            if self._on_changed:
                self._on_changed()
        return super().itemChange(change, value)

    def roi_list(self):
        """Return [x,y,w,h] in scene/image coords (item pos + rect)."""
        r = self.rect()
        p = self.pos()
        return [float(p.x() + r.x()), float(p.y() + r.y()),
                float(r.width()), float(r.height())]


def _load_pixmap(image_data) -> QPixmap:
    pm = QPixmap()
    if not image_data:
        return pm
    if isinstance(image_data, QPixmap):
        return image_data
    if isinstance(image_data, QImage):
        return QPixmap.fromImage(image_data)
    s = str(image_data)
    if s.startswith('data:image/'):
        raw = s.split(',', 1)[-1]
        try:
            pm.loadFromData(base64.b64decode(raw, validate=False))
        except Exception:
            pass
    elif Path_exists(s):
        pm.load(s)
    return pm


def Path_exists(s: str) -> bool:
    try:
        from pathlib import Path
        return Path(s).is_file()
    except Exception:
        return False


def _search_vectors(search_dir: str, proj_angle_deg: float):
    base = {
        'left_right': 0.0,
        'right_left': 180.0,
        'top_bottom': 90.0,
        'bottom_top': -90.0,
    }.get(search_dir or 'left_right', 0.0)
    angle = math.radians(base + float(proj_angle_deg or 0.0))
    scan = (math.cos(angle), math.sin(angle))
    cross = (-scan[1], scan[0])
    return scan, cross


class CaliperRoiEditorDialog(QDialog):
    """Canvas editor: ROI + multi-caliper probe preview → write params."""

    paramsApplied = Signal(dict)

    def __init__(self, params: dict, image_data=None, parent=None, sample_fallback=None):
        super().__init__(parent)
        self.setWindowTitle('多卡尺 ROI 编辑器')
        self.setObjectName('caliperRoiEditor')
        self.resize(980, 640)
        self._params = deepcopy(params or {})
        self._caliper_items = []

        root = QHBoxLayout(self)
        # canvas
        left = QVBoxLayout()
        self.scene = QGraphicsScene(self)
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.view.setObjectName('caliperRoiView')
        self.view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        left.addWidget(self.view, 1)
        tip = QLabel('拖动橙框移动 ROI；拖四角缩放。右侧改卡尺数量/宽/投影长即时预览。写入后 roiPreset→draw。')
        tip.setWordWrap(True)
        tip.setStyleSheet('color:#888;font-size:11px;')
        left.addWidget(tip)
        root.addLayout(left, 3)

        # knobs
        right = QVBoxLayout()
        box = QGroupBox('卡尺参数')
        form = QFormLayout(box)
        self.sp_count = QSpinBox(); self.sp_count.setRange(3, 200)
        self.sp_count.setValue(int(self._params.get('caliperCount') or 10))
        self.sp_count.valueChanged.connect(self._redraw_calipers)
        form.addRow('卡尺数量', self.sp_count)

        self.sp_width = QSpinBox(); self.sp_width.setRange(1, 200)
        self.sp_width.setValue(int(self._params.get('caliperWidth') or 20))
        self.sp_width.valueChanged.connect(self._redraw_calipers)
        form.addRow('卡尺宽度', self.sp_width)

        self.sp_len = QSpinBox(); self.sp_len.setRange(8, 4096)
        self.sp_len.setValue(int(self._params.get('caliperLength') or 40))
        self.sp_len.valueChanged.connect(self._redraw_calipers)
        form.addRow('卡尺投影长', self.sp_len)

        self.sp_ang = QDoubleSpinBox(); self.sp_ang.setRange(-180, 180); self.sp_ang.setDecimals(1)
        self.sp_ang.setValue(float(self._params.get('caliperProjAngle') or 0))
        self.sp_ang.valueChanged.connect(self._redraw_calipers)
        form.addRow('投影角°', self.sp_ang)

        self.cb_dir = QComboBox()
        for k, lab in (('left_right', '左→右'), ('right_left', '右→左'),
                       ('top_bottom', '上→下'), ('bottom_top', '下→上')):
            self.cb_dir.addItem(lab, k)
        self.cb_dir.setCurrentIndex(max(0, self.cb_dir.findData(
            self._params.get('searchDir') or 'left_right')))
        self.cb_dir.currentIndexChanged.connect(self._redraw_calipers)
        form.addRow('搜索方向', self.cb_dir)

        self.roi_lab = QLabel('ROI: —')
        self.roi_lab.setObjectName('caliperRoiLabel')
        self.roi_lab.setStyleSheet('color:#aaa;font-size:11px;')
        form.addRow(self.roi_lab)
        right.addWidget(box)

        b_fit = QPushButton('适应窗口')
        b_fit.clicked.connect(lambda: self.view.fitInView(self.scene.sceneRect(),
                                                          Qt.AspectRatioMode.KeepAspectRatio))
        right.addWidget(b_fit)
        b_img = QPushButton('载入底图…')
        b_img.clicked.connect(self._load_image_file)
        right.addWidget(b_img)
        right.addStretch(1)

        row = QHBoxLayout()
        b_ok = QPushButton('写入参数')
        b_ok.setObjectName('caliperRoiApplyBtn')
        b_ok.setStyleSheet('QPushButton{background:#e87722;color:#111;font-weight:600;padding:8px 16px;}')
        b_ok.clicked.connect(self._apply)
        row.addWidget(b_ok)
        b_cancel = QPushButton('取消')
        b_cancel.clicked.connect(self.reject)
        row.addWidget(b_cancel)
        right.addLayout(row)
        root.addLayout(right, 1)

        pm = _load_pixmap(image_data)
        if pm.isNull() and sample_fallback:
            pm = _load_pixmap(sample_fallback)
        if pm.isNull():
            # blank canvas
            self.scene.setSceneRect(0, 0, 640, 480)
            self.scene.addRect(0, 0, 640, 480, QPen(QColor('#333')), QBrush(QColor('#1a1a1a')))
            self._img_w, self._img_h = 640, 480
        else:
            self.scene.addPixmap(pm)
            self.scene.setSceneRect(QRectF(pm.rect()))
            self._img_w, self._img_h = pm.width(), pm.height()

        roi = self._params.get('roi')
        if isinstance(roi, list) and len(roi) == 4:
            x, y, w, h = [float(v) for v in roi]
        else:
            # center default like roiPreset=center
            w = max(40.0, self._img_w / 2)
            h = max(40.0, self._img_h / 2)
            x = (self._img_w - w) / 2
            y = (self._img_h - h) / 2
        self.roi_item = RoiRectItem(QRectF(0, 0, w, h), on_changed=self._on_roi_changed)
        self.roi_item.setPos(x, y)
        self.scene.addItem(self.roi_item)
        self._redraw_calipers()
        self.view.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def _on_roi_changed(self):
        self._update_roi_label()
        self._redraw_calipers()

    def _update_roi_label(self):
        x, y, w, h = self.roi_item.roi_list()
        self.roi_lab.setText(f'ROI: [{x:.0f}, {y:.0f}, {w:.0f}, {h:.0f}]')

    def _clear_calipers(self):
        for it in self._caliper_items:
            self.scene.removeItem(it)
        self._caliper_items.clear()

    def _redraw_calipers(self, *_):
        self._clear_calipers()
        self._update_roi_label()
        x, y, ww, wh = self.roi_item.roi_list()
        if ww < 8 or wh < 8:
            return
        count = int(self.sp_count.value())
        cal_w = int(self.sp_width.value())
        cal_len = int(self.sp_len.value())
        ang = float(self.sp_ang.value())
        search_dir = self.cb_dir.currentData()
        scan, cross = _search_vectors(search_dir, ang)
        cx = x + ww / 2.0
        cy = y + wh / 2.0
        span = min(ww, wh) * 0.45
        spacing = (2 * span) / (count - 1) if count > 1 else 0.0
        pen = QPen(QColor('#c48a2a'), 1)
        tip_pen = QPen(QColor('#e8a838'), 1)
        for index in range(count):
            ox = cx + cross[0] * ((index - (count - 1) / 2.0) * spacing)
            oy = cy + cross[1] * ((index - (count - 1) / 2.0) * spacing)
            # rectangle along scan × cross (width)
            half_l = cal_len / 2.0
            half_w = cal_w / 2.0
            corners = []
            for sl, cw in ((-half_l, -half_w), (half_l, -half_w), (half_l, half_w), (-half_l, half_w)):
                px = ox + scan[0] * sl + cross[0] * cw
                py = oy + scan[1] * sl + cross[1] * cw
                corners.append(QPointF(px, py))
            from PySide6.QtGui import QPolygonF
            poly = QGraphicsPolygonItem(QPolygonF(corners))
            poly.setPen(pen)
            poly.setBrush(QBrush(Qt.BrushStyle.NoBrush))
            poly.setZValue(25)
            self.scene.addItem(poly)
            self._caliper_items.append(poly)
            # scan arrow
            ax0 = ox - scan[0] * 6
            ay0 = oy - scan[1] * 6
            ax1 = ox + scan[0] * 6
            ay1 = oy + scan[1] * 6
            line = QGraphicsLineItem(ax0, ay0, ax1, ay1)
            line.setPen(tip_pen)
            line.setZValue(26)
            self.scene.addItem(line)
            self._caliper_items.append(line)

    def _load_image_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, '载入底图', '', 'Images (*.png *.jpg *.jpeg *.bmp);;All (*)')
        if not path:
            return
        pm = QPixmap(path)
        if pm.isNull():
            QMessageBox.warning(self, '载入失败', path)
            return
        self.scene.clear()
        self._caliper_items.clear()
        self.scene.addPixmap(pm)
        self.scene.setSceneRect(QRectF(pm.rect()))
        self._img_w, self._img_h = pm.width(), pm.height()
        w = max(40.0, self._img_w / 2)
        h = max(40.0, self._img_h / 2)
        self.roi_item = RoiRectItem(QRectF(0, 0, w, h), on_changed=self._on_roi_changed)
        self.roi_item.setPos((self._img_w - w) / 2, (self._img_h - h) / 2)
        self.scene.addItem(self.roi_item)
        self._redraw_calipers()
        self.view.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def _apply(self):
        x, y, w, h = self.roi_item.roi_list()
        out = {
            'roi': [round(x, 2), round(y, 2), round(w, 2), round(h, 2)],
            'roiMode': 'draw',
            'roiPreset': 'draw',
            'caliperCount': int(self.sp_count.value()),
            'caliperWidth': int(self.sp_width.value()),
            'caliperLength': int(self.sp_len.value()),
            'caliperProjAngle': float(self.sp_ang.value()),
            'searchDir': self.cb_dir.currentData(),
        }
        self.paramsApplied.emit(out)
        self.accept()

    def result_params(self) -> dict:
        """If accepted, caller should have caught paramsApplied; also recompute."""
        x, y, w, h = self.roi_item.roi_list()
        return {
            'roi': [round(x, 2), round(y, 2), round(w, 2), round(h, 2)],
            'roiMode': 'draw',
            'roiPreset': 'draw',
            'caliperCount': int(self.sp_count.value()),
            'caliperWidth': int(self.sp_width.value()),
            'caliperLength': int(self.sp_len.value()),
            'caliperProjAngle': float(self.sp_ang.value()),
            'searchDir': self.cb_dir.currentData(),
        }
