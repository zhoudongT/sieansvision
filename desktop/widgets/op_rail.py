"""Left category icon rail (VisionMaster 算子纵栏)."""
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QPainter, QColor, QPen, QPixmap, QIcon
from PySide6.QtWidgets import QWidget, QVBoxLayout, QToolButton, QButtonGroup, QSizePolicy


# (category key used in toolbox, tooltip, glyph drawer key)
RAIL_ITEMS = [
    ('相机采集', '图像采集', 'camera'),
    ('图像处理', '图像处理', 'image'),
    ('定位与测量', '定位/匹配', 'locate'),
    ('识别', '识别 / OCR', 'ocr'),
    ('3D 点云', '3D / 点云', 'cloud'),
    ('流程控制', '逻辑 / 流程', 'logic'),
    ('工业通信', '通信', 'comm'),
    ('变量与数据', '变量与数据', 'var'),
    ('扩展算子', '扩展', 'ext'),
]


def _icon(kind, size=28, active=False):
    accent = QColor('#e67a2e' if active else '#9aa7b5')
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(QPen(accent, 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    p.setBrush(Qt.BrushStyle.NoBrush)
    s = size
    if kind == 'camera':
        p.drawRoundedRect(5, 9, 18, 12, 2, 2)
        p.drawEllipse(10, 11, 8, 8)
        p.drawRoundedRect(18, 6, 5, 4, 1, 1)
    elif kind == 'image':
        p.drawRect(5, 6, 18, 16)
        p.drawLine(5, 16, 12, 11)
        p.drawLine(12, 11, 18, 17)
        p.drawEllipse(16, 9, 4, 4)
    elif kind == 'locate':
        p.drawEllipse(7, 7, 14, 14)
        p.drawLine(s/2, 4, s/2, s-4)
        p.drawLine(4, s/2, s-4, s/2)
    elif kind == 'ocr':
        p.drawRoundedRect(5, 5, 18, 18, 2, 2)
        p.drawLine(8, 11, 20, 11)
        p.drawLine(8, 15, 17, 15)
        p.drawLine(8, 19, 19, 19)
    elif kind == 'cloud':
        from PySide6.QtCore import QPointF
        from PySide6.QtGui import QPolygonF
        p.drawPolygon(QPolygonF([
            QPointF(14, 4), QPointF(22, 9), QPointF(22, 19),
            QPointF(14, 24), QPointF(6, 19), QPointF(6, 9),
        ]))
    elif kind == 'logic':
        from PySide6.QtCore import QPointF
        from PySide6.QtGui import QPolygonF
        p.drawPolygon(QPolygonF([
            QPointF(14, 4), QPointF(24, 14), QPointF(14, 24), QPointF(4, 14),
        ]))
    elif kind == 'comm':
        p.drawEllipse(6, 6, 7, 7)
        p.drawEllipse(15, 15, 7, 7)
        p.drawLine(12, 12, 16, 16)
    elif kind == 'var':
        p.drawText(pix.rect(), Qt.AlignmentFlag.AlignCenter, 'x')
    else:
        p.drawRoundedRect(6, 6, 16, 16, 3, 3)
        p.drawText(pix.rect(), Qt.AlignmentFlag.AlignCenter, '+')
    p.end()
    return QIcon(pix)


class OperatorRail(QWidget):
    """Narrow vertical category rail. Emits category filter ('' = all)."""
    categorySelected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('operatorRail')
        self.setFixedWidth(48)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 8, 4, 8)
        layout.setSpacing(4)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        all_btn = QToolButton()
        all_btn.setCheckable(True)
        all_btn.setChecked(True)
        all_btn.setToolTip('全部算子')
        all_btn.setIcon(_icon('ext', active=True))
        all_btn.setIconSize(QSize(28, 28))
        all_btn.setObjectName('railButton')
        all_btn.setProperty('category', '')
        self.group.addButton(all_btn)
        layout.addWidget(all_btn)
        self._buttons = [all_btn]
        for category, tip, kind in RAIL_ITEMS:
            btn = QToolButton()
            btn.setCheckable(True)
            btn.setToolTip(tip)
            btn.setIcon(_icon(kind))
            btn.setIconSize(QSize(28, 28))
            btn.setObjectName('railButton')
            btn.setProperty('category', category)
            self.group.addButton(btn)
            layout.addWidget(btn)
            self._buttons.append(btn)
        layout.addStretch(1)
        self.group.buttonClicked.connect(self._clicked)

    def _clicked(self, button):
        category = button.property('category') or ''
        for btn in self._buttons:
            active = btn is button
            kind = 'ext'
            for cat, _tip, k in RAIL_ITEMS:
                if btn.property('category') == cat:
                    kind = k
                    break
            if not btn.property('category'):
                kind = 'ext'
            btn.setIcon(_icon(kind, active=active))
        self.categorySelected.emit(category)
