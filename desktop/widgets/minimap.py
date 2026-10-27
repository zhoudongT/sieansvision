"""Canvas minimap overlay (VisionMaster 右下角小地图)."""
from PySide6.QtCore import Qt, QRectF, Signal
from PySide6.QtGui import QPainter, QColor, QPen, QBrush
from PySide6.QtWidgets import QWidget
from desktop.theme import ACCENT, RAIL_BG, LINE, TEXT_MUTED, OK


class MiniMap(QWidget):
    """Lightweight overview of the flow scene; click to pan the main view."""
    navigate = Signal(float, float)  # scene x,y center request

    def __init__(self, scene, view, parent=None):
        super().__init__(parent)
        self.scene = scene
        self.view = view
        self.setObjectName('flowMinimap')
        self.setFixedSize(160, 110)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        if scene is not None:
            scene.changed.connect(lambda *_: self.update())
        if view is not None:
            view.viewport().installEventFilter(self)

    def eventFilter(self, obj, event):
        from PySide6.QtCore import QEvent
        view = self.view
        if view is None:
            return False
        try:
            vp = view.viewport()
        except RuntimeError:
            return False
        if obj is vp and event.type() in (
            QEvent.Type.Paint, QEvent.Type.Resize, QEvent.Type.Wheel,
            QEvent.Type.MouseMove, QEvent.Type.MouseButtonRelease,
        ):
            self.update()
        return False

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(RAIL_BG))
        painter.setPen(QPen(QColor(LINE), 1))
        painter.drawRect(0, 0, self.width() - 1, self.height() - 1)
        if self.scene is None:
            return
        bounds = self.scene.itemsBoundingRect().adjusted(-40, -40, 40, 40)
        if bounds.width() < 1 or bounds.height() < 1:
            return
        scale = min((self.width() - 8) / bounds.width(), (self.height() - 8) / bounds.height())
        ox = (self.width() - bounds.width() * scale) / 2
        oy = (self.height() - bounds.height() * scale) / 2

        def map_pt(p):
            return ((p.x() - bounds.x()) * scale + ox,
                    (p.y() - bounds.y()) * scale + oy)

        # nodes
        from desktop.graph import Node, Edge
        painter.setPen(Qt.PenStyle.NoPen)
        for item in self.scene.items():
            if isinstance(item, Node):
                r = item.boundingRect()
                x, y = map_pt(item.scenePos())
                w, h = r.width() * scale, r.height() * scale
                painter.setBrush(QColor(ACCENT) if item.source else QColor(OK))
                painter.drawRoundedRect(QRectF(x, y, max(3, w), max(2, h)), 2, 2)
            elif isinstance(item, Edge):
                painter.setPen(QPen(QColor(TEXT_MUTED), 1))
                path = item.path()
                if path.elementCount() >= 2:
                    a = path.elementAt(0)
                    b = path.elementAt(path.elementCount() - 1)
                    x1, y1 = map_pt(type('P', (), {'x': lambda s=a.x: s, 'y': lambda s=a.y: s})())
                    # elementAt returns path elements with .x .y attributes
                    x1 = (a.x - bounds.x()) * scale + ox
                    y1 = (a.y - bounds.y()) * scale + oy
                    x2 = (b.x - bounds.x()) * scale + ox
                    y2 = (b.y - bounds.y()) * scale + oy
                    painter.drawLine(int(x1), int(y1), int(x2), int(y2))

        # viewport rect
        if self.view is not None:
            tl = self.view.mapToScene(self.view.viewport().rect().topLeft())
            br = self.view.mapToScene(self.view.viewport().rect().bottomRight())
            x1 = (tl.x() - bounds.x()) * scale + ox
            y1 = (tl.y() - bounds.y()) * scale + oy
            x2 = (br.x() - bounds.x()) * scale + ox
            y2 = (br.y() - bounds.y()) * scale + oy
            painter.setBrush(QColor(230, 122, 46, 40))
            painter.setPen(QPen(QColor(ACCENT), 1))
            painter.drawRect(QRectF(x1, y1, x2 - x1, y2 - y1))

        # zoom %
        if self.view is not None:
            pct = int(round(self.view.transform().m11() * 100))
            painter.setPen(QColor(TEXT_MUTED))
            painter.drawText(6, self.height() - 6, f'{pct}%')

    def mousePressEvent(self, event):
        if self.scene is None or self.view is None:
            return
        bounds = self.scene.itemsBoundingRect().adjusted(-40, -40, 40, 40)
        if bounds.width() < 1 or bounds.height() < 1:
            return
        scale = min((self.width() - 8) / bounds.width(), (self.height() - 8) / bounds.height())
        ox = (self.width() - bounds.width() * scale) / 2
        oy = (self.height() - bounds.height() * scale) / 2
        sx = bounds.x() + (event.position().x() - ox) / scale
        sy = bounds.y() + (event.position().y() - oy) / scale
        self.view.centerOn(sx, sy)
        self.navigate.emit(sx, sy)
        self.update()
