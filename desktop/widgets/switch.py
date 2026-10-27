"""Capsule toggle: ON=orange, OFF=gray (VisionMaster-style)."""
from PySide6.QtCore import Qt, Signal, QPropertyAnimation, QEasingCurve, Property, QRectF, QPointF
from PySide6.QtGui import QPainter, QColor, QPen
from PySide6.QtWidgets import QWidget


class OrangeSwitch(QWidget):
    """Custom capsule switch — do not replace with native checkboxes for primary booleans."""
    toggled = Signal(bool)

    def __init__(self, checked=False, parent=None):
        super().__init__(parent)
        self._checked = bool(checked)
        self._knob = 1.0 if checked else 0.0
        self.setFixedSize(44, 22)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip('开 / 关')
        self._anim = QPropertyAnimation(self, b'knob', self)
        self._anim.setDuration(120)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def isChecked(self):
        return self._checked

    def setChecked(self, checked, animate=True):
        checked = bool(checked)
        if checked == self._checked:
            return
        self._checked = checked
        target = 1.0 if checked else 0.0
        if animate:
            self._anim.stop()
            self._anim.setStartValue(self._knob)
            self._anim.setEndValue(target)
            self._anim.start()
        else:
            self._knob = target
            self.update()
        self.toggled.emit(checked)

    def get_knob(self):
        return self._knob

    def set_knob(self, value):
        self._knob = float(value)
        self.update()

    knob = Property(float, get_knob, set_knob)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.setChecked(not self._checked)
            event.accept()
        else:
            super().mousePressEvent(event)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        track = QRectF(1, 1, self.width() - 2, self.height() - 2)
        on = QColor('#e67a2e')
        off = QColor('#6a7380')
        color = QColor(on)
        t = self._knob
        color.setRed(int(off.red() + (on.red() - off.red()) * t))
        color.setGreen(int(off.green() + (on.green() - off.green()) * t))
        color.setBlue(int(off.blue() + (on.blue() - off.blue()) * t))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        painter.drawRoundedRect(track, track.height() / 2, track.height() / 2)
        margin = 2.5
        diameter = track.height() - margin * 2
        x = track.left() + margin + (track.width() - diameter - margin * 2) * t
        painter.setBrush(QColor('#ffffff'))
        painter.setPen(QPen(QColor(0, 0, 0, 30), 1))
        painter.drawEllipse(QRectF(x, track.top() + margin, diameter, diameter))
