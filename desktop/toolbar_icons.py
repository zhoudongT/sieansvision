"""Monochrome toolbar icons — VisionMaster-style dense chrome (no emoji glyphs)."""
from __future__ import annotations

from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import QPainter, QColor, QPen, QPixmap, QIcon, QPolygonF

# Neutral light-gray stroke on dark header (VM charcoal workbench)
INK = '#c4c4c4'
INK_MUTED = '#9a9a9a'
ACCENT = '#e67a2e'


def mono_icon(kind: str, size: int = 18, color: str | None = None, accent: bool = False) -> QIcon:
    ink = QColor(ACCENT if accent else (color or INK))
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(ink, 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    s = float(size)
    m = 2.5  # margin

    if kind == 'open':
        # folder
        p.drawRoundedRect(QRectF(m, 6, s - 2 * m, s - 8), 1.5, 1.5)
        p.drawLine(QPointF(m + 1, 6), QPointF(m + 5, 3))
        p.drawLine(QPointF(m + 5, 3), QPointF(m + 10, 3))
        p.drawLine(QPointF(m + 10, 3), QPointF(m + 12, 6))
    elif kind == 'save':
        # floppy / disk
        p.drawRoundedRect(QRectF(m, m, s - 2 * m, s - 2 * m), 1.5, 1.5)
        p.drawRect(QRectF(m + 3, m, s - 2 * m - 6, 5))
        p.drawRect(QRectF(m + 4, s - m - 6, s - 2 * m - 8, 5))
    elif kind == 'image':
        p.drawRect(QRectF(m, m + 1, s - 2 * m, s - 2 * m - 1))
        p.drawLine(QPointF(m, s - 6), QPointF(s / 2 - 1, s / 2))
        p.drawLine(QPointF(s / 2 - 1, s / 2), QPointF(s - m, s - 5))
        p.drawEllipse(QRectF(s - m - 6, m + 3, 3.5, 3.5))
    elif kind == 'reference':
        # image + pin
        p.drawRect(QRectF(m, m + 2, s - 2 * m - 2, s - 2 * m - 2))
        p.drawEllipse(QRectF(s / 2 - 1, m, 4, 4))
        p.drawLine(QPointF(s / 2 + 1, m + 4), QPointF(s / 2 + 1, s / 2))
    elif kind == 'demo':
        # play-in-rect
        p.drawRoundedRect(QRectF(m, m, s - 2 * m, s - 2 * m), 2, 2)
        tri = QPolygonF([QPointF(m + 5, m + 3), QPointF(m + 5, s - m - 3), QPointF(s - m - 2, s / 2)])
        p.setBrush(ink)
        p.drawPolygon(tri)
        p.setBrush(Qt.BrushStyle.NoBrush)
    elif kind == 'return':
        # curved back arrow
        p.drawArc(QRectF(m + 1, m + 2, s - 2 * m - 2, s - 2 * m - 2), 60 * 16, 240 * 16)
        p.drawLine(QPointF(m + 2, m + 4), QPointF(m + 2, m + 9))
        p.drawLine(QPointF(m + 2, m + 4), QPointF(m + 7, m + 4))
    elif kind == 'camera':
        p.drawRoundedRect(QRectF(m, 5, s - 2 * m, s - 9), 1.5, 1.5)
        p.drawEllipse(QRectF(s / 2 - 3.5, 7, 7, 7))
        p.drawRoundedRect(QRectF(s - m - 5, 3, 4, 3), 0.8, 0.8)
    elif kind == 'comm':
        p.drawEllipse(QRectF(m + 1, m + 1, 6, 6))
        p.drawEllipse(QRectF(s - m - 7, s - m - 7, 6, 6))
        p.drawLine(QPointF(m + 6, m + 6), QPointF(s - m - 6, s - m - 6))
    elif kind == 'host':
        # monitor
        p.drawRoundedRect(QRectF(m, m, s - 2 * m, s - 2 * m - 4), 1.5, 1.5)
        p.drawLine(QPointF(s / 2, s - m - 4), QPointF(s / 2, s - m))
        p.drawLine(QPointF(m + 3, s - m), QPointF(s - m - 3, s - m))
    elif kind == 'chain':
        # link
        p.drawRoundedRect(QRectF(m, m + 4, 7, 5), 2, 2)
        p.drawRoundedRect(QRectF(s - m - 7, s - m - 9, 7, 5), 2, 2)
        p.drawLine(QPointF(m + 6, m + 6.5), QPointF(s - m - 6, s - m - 6.5))
    elif kind == 'var':
        # braces { x } — variable glyph
        font = p.font()
        font.setPixelSize(max(10, int(s * 0.72)))
        font.setBold(True)
        p.setFont(font)
        p.drawText(pix.rect(), int(Qt.AlignmentFlag.AlignCenter), '{x}')
    elif kind == 'trigger':
        # bolt
        bolt = QPolygonF([
            QPointF(s * 0.55, m),
            QPointF(s * 0.35, s * 0.48),
            QPointF(s * 0.52, s * 0.48),
            QPointF(s * 0.40, s - m),
            QPointF(s * 0.70, s * 0.42),
            QPointF(s * 0.52, s * 0.42),
        ])
        p.setBrush(ink)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawPolygon(bolt)
    elif kind == 'inject_run':
        # inbound arrow + small play (distinct from run_once accent play)
        p.drawLine(QPointF(m, s / 2), QPointF(m + 5, s / 2))
        p.drawLine(QPointF(m + 3, s / 2 - 2.5), QPointF(m + 5.5, s / 2))
        p.drawLine(QPointF(m + 3, s / 2 + 2.5), QPointF(m + 5.5, s / 2))
        tri = QPolygonF([
            QPointF(m + 7, m + 2.5),
            QPointF(m + 7, s - m - 2.5),
            QPointF(s - m, s / 2),
        ])
        p.setBrush(ink)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawPolygon(tri)
    elif kind == 'inject_stop':
        # inbound arrow + small stop square
        p.drawLine(QPointF(m, s / 2), QPointF(m + 5, s / 2))
        p.drawLine(QPointF(m + 3, s / 2 - 2.5), QPointF(m + 5.5, s / 2))
        p.drawLine(QPointF(m + 3, s / 2 + 2.5), QPointF(m + 5.5, s / 2))
        p.setBrush(ink)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(QRectF(m + 7, m + 3, s - m - 9, s - 2 * m - 6), 1.2, 1.2)
    elif kind == 'run_once':
        tri = QPolygonF([QPointF(m + 1, m), QPointF(m + 1, s - m), QPointF(s - m - 1, s / 2)])
        p.setBrush(QColor(ACCENT))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawPolygon(tri)
    elif kind == 'run_cont':
        # double chevron
        p.setPen(QPen(QColor(ACCENT), 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        for dx in (0, 5):
            p.drawLine(QPointF(m + 2 + dx, m + 2), QPointF(m + 7 + dx, s / 2))
            p.drawLine(QPointF(m + 7 + dx, s / 2), QPointF(m + 2 + dx, s - m - 2))
    elif kind == 'stop':
        p.setBrush(QColor('#e35d6a'))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(QRectF(m + 1, m + 1, s - 2 * m - 2, s - 2 * m - 2), 1.5, 1.5)
    elif kind == 'run_selected':
        p.drawRoundedRect(QRectF(m, m, s - 2 * m, s - 2 * m), 2, 2)
        tri = QPolygonF([QPointF(m + 4, m + 3), QPointF(m + 4, s - m - 3), QPointF(s - m - 2, s / 2)])
        p.setBrush(ink)
        p.drawPolygon(tri)
    else:
        p.drawRoundedRect(QRectF(m, m, s - 2 * m, s - 2 * m), 2, 2)
    p.end()
    return QIcon(pix)


# toolbar action key → (icon kind, Chinese tooltip)
TOOLBAR_SPEC = {
    'open': ('open', '打开方案 (Ctrl+O)'),
    'save': ('save', '保存方案 (Ctrl+S)'),
    'image': ('image', '打开图像'),
    'reference': ('reference', '设置参考图'),
    'demo': ('demo', '演示工程'),
    'return_demo': ('return', '返回原工程'),
    'camera': ('camera', '相机管理'),
    'comm': ('comm', '通信管理（设备 / 收发 / 心跳）'),
    'host': ('host', '一键套用上位机运行壳'),
    'chain': ('chain', '插入生产任务建议链'),
    'var': ('var', '全局 / 流程变量'),
    'trigger': ('trigger', '全局触发（字符串 / 事件）'),
    'inject_run': ('inject_run', '注入字符串 RUN → 全局触发'),
    'inject_stop': ('inject_stop', '注入字符串 STOP → 全局触发'),
    'run_once': ('run_once', '单次执行流程 (Ctrl+Return)'),
    'run_cont': ('run_cont', '连续执行'),
    'stop': ('stop', '停止运行'),
    'run_selected': ('run_selected', '仅执行当前选中模块'),
}


def apply_toolbar_action(action, key: str, size: int = 18):
    """Set monochrome icon + CN tooltip; keep text for accessibility/menus."""
    kind, tip = TOOLBAR_SPEC[key]
    action.setIcon(mono_icon(kind, size=size, accent=key in ('run_once', 'run_cont')))
    action.setToolTip(tip)
    action.setIconVisibleInMenu(False)
    return action
