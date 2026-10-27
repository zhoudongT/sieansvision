"""Grouped native operator tiles with vector icons and flow drag payloads."""
import math

from PySide6.QtCore import Qt, QSize, QRectF, QPointF, QMimeData, Signal
from PySide6.QtGui import QColor, QDrag, QIcon, QPainter, QPen, QPixmap, QPolygonF, QFont, QPalette
from PySide6.QtWidgets import (
    QAbstractItemView, QListWidget, QListWidgetItem, QScrollArea, QToolButton,
    QVBoxLayout, QHBoxLayout, QWidget, QLabel, QStyledItemDelegate, QStyle, QFrame,
)

from desktop.theme import ACCENT, PANEL, category_color, TOOLBOX_QSS


def operator_icon(key, definition, size=28):
    """Compact industrial glyph for toolbox density (VM-like)."""
    name = (key + ' ' + definition['name']).lower()
    accent = QColor(category_color(definition.get('category', '')))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    # Flat dark tile behind glyph
    painter.setPen(Qt.PenStyle.NoPen)
    soft = QColor(accent); soft.setAlpha(28)
    painter.setBrush(soft if soft.alpha() else QColor('#2a2e34'))
    painter.drawRoundedRect(QRectF(0.5, 0.5, size - 1, size - 1), 2, 2)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.setPen(QPen(accent if accent.isValid() else QColor('#e67a2e'), 1.4, Qt.PenStyle.SolidLine,
                        Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    # Draw glyphs in 0..44 space scaled into size
    scale = size / 44.0
    painter.scale(scale, scale)

    def line(x, y, xx, yy):
        painter.drawLine(QPointF(x, y), QPointF(xx, yy))

    if any(word in name for word in ('条码', 'barcode', '二维码')):
        for x, width in ((10, 2), (15, 1), (19, 3), (25, 1), (29, 2), (34, 1)):
            painter.fillRect(QRectF(x, 12, width, 20), accent)
    elif any(word in name for word in ('ocr', '文字', '字符')):
        painter.drawRoundedRect(QRectF(10, 10, 24, 24), 3, 3)
        line(14, 18, 30, 18); line(14, 24, 26, 24); line(14, 30, 28, 30)
    elif any(word in name for word in ('相机', 'camera', '采集')):
        painter.drawRoundedRect(QRectF(9, 14, 26, 18), 3, 3)
        painter.drawEllipse(QRectF(16, 17, 12, 12))
        painter.drawRoundedRect(QRectF(28, 10, 7, 5), 1, 1)
    elif any(word in name for word in ('延时', 'delay')):
        painter.drawEllipse(QRectF(10, 10, 24, 24)); line(22, 15, 22, 22); line(22, 22, 28, 26)
    elif any(word in name for word in ('条件', '汇合', 'condition', 'merge')):
        painter.drawPolygon(QPolygonF([QPointF(22, 8), QPointF(32, 18), QPointF(22, 28), QPointF(12, 18)]))
        line(12, 18, 7, 18); line(7, 18, 7, 35); line(32, 18, 37, 18); line(37, 18, 37, 35)
    elif any(word in name for word in ('3d', '点云', '体积')):
        painter.drawPolygon(QPolygonF([QPointF(22, 7), QPointF(35, 14), QPointF(35, 30), QPointF(22, 37), QPointF(9, 30), QPointF(9, 14)]))
        line(9, 14, 22, 22); line(35, 14, 22, 22); line(22, 22, 22, 37)
    elif any(word in name for word in ('圆', 'circle')):
        painter.drawEllipse(QRectF(11, 11, 22, 22)); line(7, 22, 37, 22); line(22, 7, 22, 37)
    elif any(word in name for word in ('标定', '棋盘', 'intrinsics', 'calibr')):
        for row in range(4):
            for column in range(4):
                if (row + column) % 2 == 0:
                    painter.fillRect(QRectF(10 + column * 6, 10 + row * 6, 6, 6), accent)
        painter.drawRect(QRectF(10, 10, 24, 24))
    elif any(word in name for word in ('记录', '字段', 'record', '排序', '变量', '脚本')):
        painter.drawRoundedRect(QRectF(9, 9, 26, 26), 3, 3)
        for y in (17, 24):
            line(9, y, 35, y)
        line(18, 9, 18, 35)
    elif any(word in name for word in ('yolo', '识别', '定位', 'locate', 'fixture', '模板')):
        for x, y, sx, sy in ((9, 9, 1, 1), (35, 9, -1, 1), (9, 35, 1, -1), (35, 35, -1, -1)):
            line(x, y, x + sx * 7, y); line(x, y, x, y + sy * 7)
        painter.drawEllipse(QRectF(16, 16, 12, 12)); line(22, 13, 22, 31); line(13, 22, 31, 22)
    elif any(word in name for word in ('差异', '缺陷', 'defect')):
        painter.drawRect(QRectF(9, 10, 26, 24)); line(24, 12, 18, 22); line(18, 22, 26, 23); line(26, 23, 20, 32)
    elif any(word in name for word in ('测', '几何', 'geometry', 'caliper', '尺寸')):
        line(10, 13, 34, 13); line(10, 10, 10, 31); line(34, 10, 34, 31); line(10, 29, 34, 29)
        for x in (16, 22, 28):
            line(x, 13, x, 18)
    elif any(word in name for word in ('modbus', 'mqtt', 'opc', 's7', 'tcp', 'udp', '串口', '通信', 'plc')):
        painter.drawEllipse(QRectF(8, 18, 8, 8)); painter.drawEllipse(QRectF(28, 18, 8, 8))
        line(16, 22, 28, 22); line(12, 14, 12, 18); line(32, 14, 32, 18)
    elif any(word in name for word in ('预处理', 'preprocess', '滤波', 'filter')):
        painter.drawRoundedRect(QRectF(9, 12, 26, 20), 3, 3)
        painter.drawPolyline(QPolygonF([QPointF(12, 26), QPointF(18, 18), QPointF(23, 24), QPointF(30, 15), QPointF(34, 20)]))
    else:
        painter.drawRoundedRect(QRectF(8, 10, 28, 24), 3, 3)
        painter.drawEllipse(QRectF(13, 14, 5, 5))
        painter.drawPolyline(QPolygonF([QPointF(10, 31), QPointF(19, 22), QPointF(24, 27), QPointF(30, 19), QPointF(35, 25)]))
    painter.end()
    return QIcon(pixmap)


class TileDelegate(QStyledItemDelegate):
    """Compact industrial tiles — flatter, tighter than marketing cards."""
    CELL_W, CELL_H = 72, 58

    def paint(self, painter, option, index):
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = option.rect.adjusted(2, 2, -2, -2)
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)
        if selected:
            fill, border, bw = QColor('#3a2a1c'), QColor('#e67a2e'), 1.3
        elif hovered:
            fill, border, bw = QColor('#323840'), QColor('#e67a2e'), 1.0
        else:
            fill, border, bw = QColor('#2a2e34'), QColor('#3a4048'), 1.0
        painter.setBrush(fill)
        painter.setPen(QPen(border, bw))
        painter.drawRoundedRect(QRectF(rect), 2, 2)
        icon = index.data(Qt.ItemDataRole.DecorationRole)
        if icon:
            icon.paint(painter, rect.center().x() - 12, rect.top() + 3, 24, 24)
        font = QFont(option.font)
        font.setPixelSize(10)
        font.setWeight(QFont.Weight.Normal)
        painter.setFont(font)
        painter.setPen(QColor('#d8d8d8'))
        text_rect = rect.adjusted(2, 30, -2, -1)
        painter.setClipRect(text_rect)
        painter.drawText(
            text_rect,
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap,
            index.data(),
        )
        painter.restore()

    def sizeHint(self, option, index):
        return QSize(self.CELL_W, self.CELL_H)


class OperatorTiles(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('operatorTiles')
        self.setViewMode(QListWidget.ViewMode.IconMode)
        self.setItemDelegate(TileDelegate(self))
        self.setMouseTracking(True)
        self.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.setMovement(QListWidget.Movement.Static)
        self.setWrapping(True)
        self.setWordWrap(True)
        self.setIconSize(QSize(28, 28))
        self.setGridSize(QSize(72, 58))
        self.setSpacing(0)
        self.setDragEnabled(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragOnly)
        self.setDefaultDropAction(Qt.DropAction.CopyAction)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFrameShape(QListWidget.Shape.NoFrame)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setAutoFillBackground(True)
        tpal = self.palette()
        tpal.setColor(QPalette.ColorRole.Base, QColor(PANEL))
        tpal.setColor(QPalette.ColorRole.Window, QColor(PANEL))
        self.setPalette(tpal)
        self.viewport().setAutoFillBackground(True)
        self.viewport().setPalette(tpal)
        self.setStyleSheet(
            f'QListWidget#operatorTiles {{ background: {PANEL}; border: 0; outline: 0; }}'
            f'QListWidget#operatorTiles::item {{ background: transparent; border: 0; }}'
        )

    def resizeEvent(self, event):
        super().resizeEvent(event)
        columns = max(1, self.viewport().width() // 72)
        height = math.ceil(self.count() / columns) * 58 + 4
        if self.height() != height:
            self.setFixedHeight(height)

    def startDrag(self, actions):
        item = self.currentItem() or (self.selectedItems()[0] if self.selectedItems() else None)
        if item is None:
            return
        key = item.data(Qt.ItemDataRole.UserRole)
        if not key:
            return
        if isinstance(key, bytes):
            payload = key
        else:
            payload = str(key).encode('utf-8')
        mime = QMimeData()
        mime.setData('application/x-sieans-operator', payload)
        drag = QDrag(self)
        drag.setMimeData(mime)
        pix = item.icon().pixmap(28, 28)
        if not pix.isNull():
            drag.setPixmap(pix)
            drag.setHotSpot(pix.rect().center())
        self.setCursor(Qt.CursorShape.ClosedHandCursor)
        try:
            # Copy-only so FlowView can accept without Move/Link negotiation.
            drag.exec(Qt.DropAction.CopyAction, Qt.DropAction.CopyAction)
        finally:
            self.setCursor(Qt.CursorShape.OpenHandCursor)


class Toolbox(QScrollArea):
    operatorActivated = Signal(str)

    def __init__(self):
        super().__init__()
        self.collapsed = set()
        self.groups = []
        self.setWidgetResizable(True)
        self.setMinimumWidth(200)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFrameShape(QScrollArea.Shape.NoFrame)
        self.setObjectName('operatorToolbox')
        self.setAcceptDrops(False)
        self.setStyleSheet(TOOLBOX_QSS)
        self.setAutoFillBackground(True)
        pal = self.palette()
        pal.setColor(QPalette.ColorRole.Window, QColor(PANEL))
        pal.setColor(QPalette.ColorRole.Base, QColor(PANEL))
        self.setPalette(pal)
        self.viewport().setAutoFillBackground(True)
        self.viewport().setPalette(pal)
        self.viewport().setStyleSheet(f'background: {PANEL};')

    def populate(self, definitions, query=''):
        query = query.strip().lower()
        groups = {}
        for key, definition in definitions.items():
            category = definition.get('category', '扩展算子')
            if query and query not in (definition['name'] + ' ' + key + ' ' + category).lower():
                continue
            groups.setdefault(category, []).append((key, definition))
        old = self.takeWidget()
        if old:
            old.deleteLater()
        content = QWidget()
        content.setObjectName('toolboxContent')
        content.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        content.setAutoFillBackground(True)
        cpal = content.palette()
        cpal.setColor(QPalette.ColorRole.Window, QColor(PANEL))
        cpal.setColor(QPalette.ColorRole.Base, QColor(PANEL))
        content.setPalette(cpal)
        content.setStyleSheet(f'QWidget#toolboxContent {{ background: {PANEL}; }}')
        layout = QVBoxLayout(content)
        layout.setContentsMargins(2, 2, 2, 6)
        layout.setSpacing(4)
        self.groups = []
        # Prefer a stable industrial order
        order = [
            '相机采集', '图像处理', '定位与测量', '识别', '3D 点云',
            '流程控制', '工业通信', '变量与数据', '扩展算子',
        ]
        categories = sorted(groups.keys(), key=lambda c: (order.index(c) if c in order else 99, c))
        for category in categories:
            entries = groups[category]
            color = category_color(category)
            header = QToolButton()
            header.setObjectName('categoryHeader')
            header.setText(f'  {category}    {len(entries)}')
            header.setCheckable(True)
            expanded = bool(query) or category not in self.collapsed
            header.setChecked(expanded)
            header.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            header.setArrowType(Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow)
            header.setCursor(Qt.CursorShape.PointingHandCursor)
            # Left color bar via stylesheet border
            header.setStyleSheet(
                f'QToolButton#categoryHeader{{border-left: 3px solid {color};}}'
            )
            layout.addWidget(header)
            tiles = OperatorTiles()
            tiles.setAccessibleName(category + '算子图标')
            self.groups.append(tiles)
            for key, definition in entries:
                item = QListWidgetItem(operator_icon(key, definition), definition['name'], tiles)
                item.setData(Qt.ItemDataRole.UserRole, key)
                item.setData(Qt.ItemDataRole.UserRole + 1, color)
                item.setTextAlignment(Qt.AlignmentFlag.AlignHCenter)
                tip = definition['name']
                if definition.get('description'):
                    tip += '\n' + definition['description']
                tip += '\n\n拖入画布，或双击添加'
                item.setToolTip(tip)
            tiles.itemDoubleClicked.connect(
                lambda item: self.operatorActivated.emit(item.data(Qt.ItemDataRole.UserRole))
            )
            layout.addWidget(tiles)
            tiles.setVisible(expanded)
            header.toggled.connect(
                lambda checked, c=category, b=header, t=tiles: self.toggle(c, b, t, checked)
            )
        if not groups:
            empty = QLabel('未找到匹配的算子\n试试清空搜索，或换个关键词')
            empty.setObjectName('emptyOps')
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(empty)
        else:
            foot = QLabel('拖入画布 · 双击添加')
            foot.setObjectName('emptyOps')
            foot.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(foot)
        layout.addStretch()
        self.setWidget(content)

    def toggle(self, category, header, tiles, expanded):
        if expanded:
            self.collapsed.discard(category)
        else:
            self.collapsed.add(category)
        header.setArrowType(Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow)
        tiles.setVisible(expanded)
