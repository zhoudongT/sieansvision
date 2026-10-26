"""Grouped native operator tiles with vector icons and flow drag payloads."""
import math

from PySide6.QtCore import Qt, QSize, QRectF, QPointF, QMimeData, Signal
from PySide6.QtGui import QColor, QDrag, QIcon, QPainter, QPen, QPixmap, QPolygonF, QFont
from PySide6.QtWidgets import (QAbstractItemView, QListWidget, QListWidgetItem,
                             QScrollArea, QToolButton, QVBoxLayout, QWidget, QLabel, QStyledItemDelegate, QStyle)


def operator_icon(key, definition):
    name = (key + ' ' + definition['name']).lower()
    pixmap = QPixmap(88, 88)
    pixmap.setDevicePixelRatio(2)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor('#e5f4fb'))
    painter.drawRoundedRect(QRectF(1, 1, 42, 42), 10, 10)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.setPen(QPen(QColor('#008fb9'), 1.8, Qt.PenStyle.SolidLine,
                        Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    def line(x, y, xx, yy): painter.drawLine(QPointF(x, y), QPointF(xx, yy))
    if any(word in name for word in ('条码', 'barcode', '二维码')):
        for x, width in ((10,2),(15,1),(19,3),(25,1),(29,2),(34,1)):
            painter.fillRect(QRectF(x, 12, width, 20), QColor('#008fb9'))
    elif any(word in name for word in ('延时', 'delay')):
        painter.drawEllipse(QRectF(10,10,24,24));line(22,15,22,22);line(22,22,28,26)
    elif any(word in name for word in ('条件', '汇合', 'condition', 'merge')):
        painter.drawPolygon(QPolygonF([QPointF(22,8),QPointF(32,18),QPointF(22,28),QPointF(12,18)]))
        line(12,18,7,18);line(7,18,7,35);line(32,18,37,18);line(37,18,37,35)
    elif any(word in name for word in ('3d', '点云', '体积')):
        painter.drawPolygon(QPolygonF([QPointF(22,7),QPointF(35,14),QPointF(35,30),QPointF(22,37),QPointF(9,30),QPointF(9,14)]))
        line(9,14,22,22);line(35,14,22,22);line(22,22,22,37)
    elif any(word in name for word in ('圆', 'circle')):
        painter.drawEllipse(QRectF(11,11,22,22));line(7,22,37,22);line(22,7,22,37)
    elif any(word in name for word in ('标定', '棋盘', 'intrinsics', 'calibr')):
        for row in range(4):
            for column in range(4):
                if (row+column)%2==0:painter.fillRect(QRectF(10+column*6,10+row*6,6,6),QColor('#008fb9'))
        painter.drawRect(QRectF(10,10,24,24))
    elif any(word in name for word in ('记录', '字段', 'record', '排序')):
        painter.drawRoundedRect(QRectF(9,9,26,26),3,3)
        for y in (17,24):line(9,y,35,y)
        line(18,9,18,35)
    elif any(word in name for word in ('yolo', '识别', '定位', 'locate', 'fixture')):
        for x,y,sx,sy in ((9,9,1,1),(35,9,-1,1),(9,35,1,-1),(35,35,-1,-1)):
            line(x,y,x+sx*7,y);line(x,y,x,y+sy*7)
        painter.drawEllipse(QRectF(16,16,12,12));line(22,13,22,31);line(13,22,31,22)
    elif any(word in name for word in ('差异', '缺陷', 'defect')):
        painter.drawRect(QRectF(9,10,26,24));line(24,12,18,22);line(18,22,26,23);line(26,23,20,32)
    elif any(word in name for word in ('测', '几何', 'geometry', 'caliper')):
        line(10,13,34,13);line(10,10,10,31);line(34,10,34,31);line(10,29,34,29)
        for x in (16,22,28):line(x,13,x,18)
    else:
        painter.drawRoundedRect(QRectF(8,10,28,24),3,3)
        painter.drawEllipse(QRectF(13,14,5,5))
        painter.drawPolyline(QPolygonF([QPointF(10,31),QPointF(19,22),QPointF(24,27),QPointF(30,19),QPointF(35,25)]))
    painter.end()
    return QIcon(pixmap)


class TileDelegate(QStyledItemDelegate):
    def paint(self,painter,option,index):
        painter.save();painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect=option.rect.adjusted(3,3,-3,-3)
        selected=bool(option.state & QStyle.StateFlag.State_Selected)
        hovered=bool(option.state & QStyle.StateFlag.State_MouseOver)
        painter.setBrush(QColor('#e3f5fc' if selected else '#f0faff' if hovered else '#ffffff'))
        painter.setPen(QPen(QColor('#009bc5' if selected else '#7cc8df' if hovered else '#e1ebf2'),1))
        painter.drawRoundedRect(rect,7,7)
        icon=index.data(Qt.ItemDataRole.DecorationRole)
        icon.paint(painter,rect.center().x()-22,rect.top()+6,44,44)
        font=QFont(option.font);font.setPixelSize(12);painter.setFont(font)
        painter.setPen(QColor('#183954'))
        text_rect=rect.adjusted(4,53,-4,-3)
        painter.setClipRect(text_rect)
        painter.drawText(text_rect,Qt.AlignmentFlag.AlignHCenter|Qt.AlignmentFlag.AlignTop|Qt.TextFlag.TextWordWrap,index.data())
        painter.restore()

    def sizeHint(self,option,index):return QSize(112,108)


class OperatorTiles(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setViewMode(QListWidget.ViewMode.IconMode)
        self.setItemDelegate(TileDelegate(self));self.setMouseTracking(True)
        self.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.setMovement(QListWidget.Movement.Static)
        self.setWrapping(True);self.setWordWrap(True)
        self.setIconSize(QSize(44,44));self.setGridSize(QSize(112,108));self.setSpacing(0)
        self.setDragEnabled(True);self.setDragDropMode(QAbstractItemView.DragDropMode.DragOnly)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFrameShape(QListWidget.Shape.NoFrame)
        self.setStyleSheet('QListWidget{background:transparent;border:0;outline:0;}'
            'QListWidget::item{background:white;border:1px solid #e1ebf2;border-radius:7px;padding:5px;margin:3px;}'
            'QListWidget::item:hover{background:#f0faff;border-color:#7cc8df;}'
            'QListWidget::item:selected{background:#e3f5fc;border:1px solid #009bc5;}')

    def resizeEvent(self,event):
        super().resizeEvent(event)
        columns=max(1,self.viewport().width()//112)
        height=math.ceil(self.count()/columns)*108+2
        if self.height()!=height:self.setFixedHeight(height)

    def startDrag(self,actions):
        item=self.currentItem()
        if item is None:return
        mime=QMimeData();mime.setData('application/x-sieans-operator',item.data(Qt.ItemDataRole.UserRole).encode())
        drag=QDrag(self);drag.setMimeData(mime);drag.setPixmap(item.icon().pixmap(44,44))
        drag.exec(Qt.DropAction.CopyAction)


class Toolbox(QScrollArea):
    operatorActivated=Signal(str)

    def __init__(self):
        super().__init__()
        self.collapsed=set();self.groups=[]
        self.setWidgetResizable(True);self.setMinimumWidth(246)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setStyleSheet('Toolbox{border:0;background:#eef4f8;}')

    def populate(self,definitions,query=''):
        query=query.strip().lower();groups={}
        for key,definition in definitions.items():
            category=definition.get('category','扩展算子')
            if query and query not in (definition['name']+' '+key+' '+category).lower():continue
            groups.setdefault(category,[]).append((key,definition))
        old=self.takeWidget()
        if old:old.deleteLater()
        content=QWidget();layout=QVBoxLayout(content);layout.setContentsMargins(0,0,0,0);layout.setSpacing(6)
        self.groups=[]
        for category,entries in groups.items():
            header=QToolButton();header.setText(f'{category}  ·  {len(entries)}');header.setCheckable(True)
            expanded=bool(query) or category not in self.collapsed
            header.setChecked(expanded);header.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            header.setArrowType(Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow)
            header.setStyleSheet('QToolButton{text-align:left;font-weight:600;border:0;padding:7px 3px;background:transparent;}')
            layout.addWidget(header)
            tiles=OperatorTiles();tiles.setAccessibleName(category+'算子图标');self.groups.append(tiles)
            for key,definition in entries:
                item=QListWidgetItem(operator_icon(key,definition),definition['name'],tiles)
                item.setData(Qt.ItemDataRole.UserRole,key);item.setTextAlignment(Qt.AlignmentFlag.AlignHCenter)
                item.setToolTip(definition['name']+'\n'+definition.get('description','双击添加模块，或拖入流程画布'))
            tiles.itemDoubleClicked.connect(lambda item:self.operatorActivated.emit(item.data(Qt.ItemDataRole.UserRole)))
            layout.addWidget(tiles);tiles.setVisible(expanded)
            header.toggled.connect(lambda checked,c=category,b=header,t=tiles:self.toggle(c,b,t,checked))
        if not groups:
            empty=QLabel('未找到匹配的算子');empty.setAlignment(Qt.AlignmentFlag.AlignCenter);layout.addWidget(empty)
        layout.addStretch();self.setWidget(content)

    def toggle(self,category,header,tiles,expanded):
        if expanded:self.collapsed.discard(category)
        else:self.collapsed.add(category)
        header.setArrowType(Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow)
        tiles.setVisible(expanded)
