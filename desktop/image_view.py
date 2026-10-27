import base64
from PySide6.QtCore import Qt, Signal, QRectF, QTimer
from PySide6.QtGui import QPixmap, QColor, QPen, QPainter, QBrush
from PySide6.QtWidgets import QGraphicsView, QGraphicsScene

from desktop.theme import CANVAS, TEXT_MUTED


class ImageView(QGraphicsView):
    """Full-frame KeepAspectRatio image pane (全局图像 / 模块结果 / 深度图).

    fitInView while the viewport is hidden or tiny is a Qt no-op — transform
    stays ~1:1 and the user only sees a dark top strip of the frame
    (「图像只有上面一条」). Defer fit until the view is visible with a real size.
    """
    roi_changed = Signal(list)

    def __init__(self):
        super().__init__()
        self.setScene(QGraphicsScene(self))
        self.setBackgroundBrush(QBrush(QColor(CANVAS)))
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setMinimumSize(230, 180)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        # Scrollbars during fitInView shrink the viewport mid-fit and leave a
        # letterboxed / top-strip look; zoom still works via Ctrl+wheel + hand drag.
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.select_roi = False
        self.origin = None
        self.overlay = None
        self.bounds = QRectF()
        self._needs_fit = False
        self._fit_mode = 'contain'  # contain | cover | actual (Display 适应模式)
        self._empty_hint = self.scene().addText('打开图像，或载入演示')
        self._empty_hint.setDefaultTextColor(QColor(TEXT_MUTED))

    def drawBackground(self, painter, rect):
        # VisionMaster-style dark gray checkerboard when empty / around image
        painter.fillRect(rect, QColor(CANVAS))
        cell = 12
        c0 = QColor('#2a2c30')
        c1 = QColor('#34363b')
        left = int(rect.left() // cell) * cell
        top = int(rect.top() // cell) * cell
        y = top
        while y < rect.bottom() + cell:
            x = left
            row = int(y // cell)
            while x < rect.right() + cell:
                col = int(x // cell)
                painter.fillRect(QRectF(x, y, cell, cell), c0 if (row + col) % 2 == 0 else c1)
                x += cell
            y += cell

    def show_data(self, data):
        pixmap = QPixmap()
        if data and isinstance(data, str):
            try:
                raw = data.split(',', 1)[-1]
                pixmap.loadFromData(base64.b64decode(raw, validate=False))
            except Exception:
                pixmap = QPixmap()
        if not pixmap.isNull():
            image = pixmap.toImage()
            if image.format() not in (
                image.Format.Format_RGB32,
                image.Format.Format_ARGB32,
                image.Format.Format_ARGB32_Premultiplied,
            ):
                pixmap = QPixmap.fromImage(image.convertToFormat(image.Format.Format_RGB32))
        self.scene().clear()
        self.overlay = None
        self.bounds = QRectF()
        self._empty_hint = None
        if not pixmap.isNull():
            self.scene().addPixmap(pixmap)
            self.bounds = QRectF(pixmap.rect())
            self.scene().setSceneRect(self.bounds)
            self._needs_fit = True
            self.fit()
            # Layout / tab show often finishes after this call — refit next tick.
            QTimer.singleShot(0, self.fit)
        else:
            self._needs_fit = False
            self._empty_hint = self.scene().addText('打开图像，或载入演示')
            self._empty_hint.setDefaultTextColor(QColor(TEXT_MUTED))
            self.scene().setSceneRect(QRectF(0, 0, 400, 300))

    def set_roi_mode(self, enabled):
        self.select_roi = enabled
        self.setDragMode(
            QGraphicsView.DragMode.NoDrag if enabled else QGraphicsView.DragMode.ScrollHandDrag
        )
        self.setCursor(Qt.CursorShape.CrossCursor if enabled else Qt.CursorShape.ArrowCursor)

    def show_roi(self, roi):
        if self.overlay:
            self.scene().removeItem(self.overlay)
            self.overlay = None
        if isinstance(roi, list) and len(roi) == 4 and all(isinstance(x, (int, float)) for x in roi):
            pen = QPen(QColor('#e67a2e'), 2, Qt.PenStyle.DashLine)
            pen.setCosmetic(True)
            self.overlay = self.scene().addRect(QRectF(*roi), pen)
            self.overlay.setZValue(10)

    def set_fit_mode(self, mode):
        """Display fitMode → 模块结果 pane: contain | cover | actual."""
        mode = mode if mode in ('contain', 'cover', 'actual') else 'contain'
        self._fit_mode = mode
        if not self.bounds.isEmpty():
            self.fit()

    def fit(self):
        """Fit per _fit_mode. Defer when hidden / viewport still tiny."""
        if self.bounds.isEmpty():
            self._needs_fit = False
            return
        if (
            not self.isVisible()
            or self.viewport().width() < 8
            or self.viewport().height() < 8
        ):
            self._needs_fit = True
            return
        mode = getattr(self, '_fit_mode', 'contain') or 'contain'
        if mode == 'actual':
            self.resetTransform()
            # Center on image
            self.centerOn(self.bounds.center())
            self._needs_fit = False
            self.viewport().update()
            return
        h_policy = self.horizontalScrollBarPolicy()
        v_policy = self.verticalScrollBarPolicy()
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        aspect = (
            Qt.AspectRatioMode.KeepAspectRatioByExpanding
            if mode == 'cover'
            else Qt.AspectRatioMode.KeepAspectRatio
        )
        self.fitInView(self.bounds, aspect)
        self.setHorizontalScrollBarPolicy(h_policy)
        self.setVerticalScrollBarPolicy(v_policy)
        self._needs_fit = False
        self.viewport().update()

    def showEvent(self, event):
        super().showEvent(event)
        if not self.bounds.isEmpty():
            QTimer.singleShot(0, self.fit)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not self.bounds.isEmpty():
            self.fit()

    def wheelEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            scale = 1.2 if event.angleDelta().y() > 0 else 1 / 1.2
            if .01 < self.transform().m11() * scale < 40:
                self.scale(scale, scale)
        else:
            super().wheelEvent(event)

    def mousePressEvent(self, event):
        if self.select_roi and event.button() == Qt.MouseButton.LeftButton and not self.bounds.isEmpty():
            self.origin = self.mapToScene(event.position().toPoint())
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.origin is not None:
            rect = QRectF(self.origin, self.mapToScene(event.position().toPoint())).normalized().intersected(self.bounds)
            self.show_roi([rect.x(), rect.y(), rect.width(), rect.height()])
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.origin is not None:
            rect = QRectF(self.origin, self.mapToScene(event.position().toPoint())).normalized().intersected(self.bounds).toAlignedRect()
            self.origin = None
            if rect.width() >= 2 and rect.height() >= 2:
                self.roi_changed.emit([rect.x(), rect.y(), rect.width(), rect.height()])
            event.accept()
        else:
            super().mouseReleaseEvent(event)
