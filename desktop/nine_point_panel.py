"""九点标定（nine_point）属性浮窗 — VisionMaster p=20 壳.

像素点 ↔ 机械点对照表；运行时若 ≥3 点则估简易仿射，否则仅回显表。
"""
from copy import deepcopy

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTabWidget, QFormLayout,
    QLineEdit, QComboBox, QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QScrollArea, QFrame, QDoubleSpinBox,
)


def _empty_row(i=0):
    return dict(index=i + 1, pixelX=0.0, pixelY=0.0, worldX=0.0, worldY=0.0, enabled=True)


def normalize_nine_point_params(params=None):
    p = deepcopy(params or {})
    p.setdefault('coordSystem', '机械坐标系')
    p.setdefault('unit', 'mm')
    points = p.get('points')
    if not isinstance(points, list) or len(points) < 1:
        points = [_empty_row(i) for i in range(9)]
    # pad / trim soft to at least 9 for VM look
    while len(points) < 9:
        points.append(_empty_row(len(points)))
    for i, row in enumerate(points):
        if not isinstance(row, dict):
            points[i] = _empty_row(i)
            continue
        row.setdefault('index', i + 1)
        for k in ('pixelX', 'pixelY', 'worldX', 'worldY'):
            try:
                row[k] = float(row.get(k) or 0)
            except (TypeError, ValueError):
                row[k] = 0.0
        row['enabled'] = bool(row.get('enabled', True))
    p['points'] = points
    p.setdefault('method', 'affine')  # affine | perspective
    p.setdefault('rms', None)
    return p


class NinePointPanel(QWidget):
    """两 Tab：基本参数（九点表） / 结果显示."""
    changed = Signal(dict)

    def __init__(self, step, definition, project, parent=None):
        super().__init__(parent)
        self.step = deepcopy(step)
        self.definition = definition or {}
        self.project = project or {}
        self.params = normalize_nine_point_params(step.get('params'))
        self.step['params'] = self.params
        self._syncing = False

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        hint = QLabel(
            '对齐 VisionMaster「平移九点标定」：填写像素点与世界坐标对照表；'
            '运行时对启用点估仿射（≥3 点），输出 transform / rms。'
        )
        hint.setWordWrap(True)
        hint.setStyleSheet('color:#666;padding:8px 10px 4px;')
        root.addWidget(hint)

        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)
        self.tabs.addTab(self._wrap(self._basic_tab()), '基本参数')
        self.tabs.addTab(self._wrap(self._result_tab()), '结果显示')

    def _wrap(self, inner):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(inner)
        return scroll

    def _emit(self):
        self.step['params'] = deepcopy(self.params)
        self.changed.emit(deepcopy(self.step))

    def _set_param(self, key, value):
        if self.params.get(key) != value:
            self.params[key] = deepcopy(value)
            self._emit()

    def _set_top(self, key, value):
        if self.step.get(key) != value:
            self.step[key] = deepcopy(value)
            self._emit()

    def _basic_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(10, 10, 10, 10)
        form = QFormLayout()
        name = QLineEdit(self.step.get('name') or '九点标定')
        name.setMaxLength(80)
        name.editingFinished.connect(lambda: self._set_top('name', name.text()))
        form.addRow('模块名称', name)

        image_from = QComboBox()
        image_from.addItem('（无图像输入）', None)
        incoming = {e['from'] for e in self.project.get('edges', []) if e.get('to') == self.step.get('id')}
        index_map = {'source': 0}
        names = {'source': '图像源1'}
        for i, s in enumerate(self.project.get('steps', []), start=1):
            index_map[s['id']] = i
            names[s['id']] = s.get('name', s['id'])
        def _sub(n):
            return f"{index_map.get(n, '?')} {names.get(n, n)}.图像"
        for node in sorted(incoming, key=lambda n: (index_map.get(n, 999), n)):
            image_from.addItem(_sub(node), node)
        cur = self.step.get('imageFrom')
        if cur and image_from.findData(cur) < 0:
            image_from.addItem('已断开：' + _sub(cur), cur)
        image_from.setCurrentIndex(max(0, image_from.findData(cur)))
        image_from.currentIndexChanged.connect(lambda _: self._set_top('imageFrom', image_from.currentData()))
        form.addRow('输入源', image_from)

        cs = QLineEdit(str(self.params.get('coordSystem') or '机械坐标系'))
        cs.editingFinished.connect(lambda: self._set_param('coordSystem', cs.text().strip()))
        form.addRow('坐标系', cs)
        unit = QComboBox()
        for u in ('mm', 'cm', 'm', 'px'):
            unit.addItem(u, u)
        unit.setCurrentIndex(max(0, unit.findData(self.params.get('unit') or 'mm')))
        unit.currentIndexChanged.connect(lambda _: self._set_param('unit', unit.currentData()))
        form.addRow('单位', unit)
        method = QComboBox()
        method.addItem('仿射 (≥3 点)', 'affine')
        method.addItem('透视 (≥4 点)', 'perspective')
        method.setCurrentIndex(max(0, method.findData(self.params.get('method') or 'affine')))
        method.currentIndexChanged.connect(lambda _: self._set_param('method', method.currentData()))
        form.addRow('求解方法', method)
        lay.addLayout(form)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(['序号', '像素X', '像素Y', '世界X', '世界Y', '启用'])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.itemChanged.connect(self._on_item)
        lay.addWidget(self.table, 1)

        bar = QHBoxLayout()
        add = QPushButton('添加点')
        add.clicked.connect(self._add_row)
        rem = QPushButton('删除选中')
        rem.clicked.connect(self._remove_rows)
        reset = QPushButton('重置 9 点')
        reset.clicked.connect(self._reset9)
        bar.addWidget(add)
        bar.addWidget(rem)
        bar.addWidget(reset)
        bar.addStretch(1)
        lay.addLayout(bar)
        self._reload_table()
        return w

    def _result_tab(self):
        w = QWidget()
        form = QFormLayout(w)
        form.setContentsMargins(10, 10, 10, 10)
        tip = QLabel('运行结果：transform（3×3）/ rms / usedPoints / unit。设计态保存对照表即可。')
        tip.setWordWrap(True)
        tip.setStyleSheet('color:#888;')
        form.addRow(tip)
        return w

    def _reload_table(self):
        self._syncing = True
        pts = self.params.get('points') or []
        self.table.setRowCount(len(pts))
        for r, row in enumerate(pts):
            vals = [
                str(row.get('index', r + 1)),
                f"{float(row.get('pixelX') or 0):.4f}",
                f"{float(row.get('pixelY') or 0):.4f}",
                f"{float(row.get('worldX') or 0):.4f}",
                f"{float(row.get('worldY') or 0):.4f}",
                '是' if row.get('enabled', True) else '否',
            ]
            for c, text in enumerate(vals):
                item = QTableWidgetItem(text)
                if c == 0:
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(r, c, item)
        self._syncing = False

    def _on_item(self, item):
        if self._syncing:
            return
        r, c = item.row(), item.column()
        pts = self.params.setdefault('points', [])
        while len(pts) <= r:
            pts.append(_empty_row(len(pts)))
        row = pts[r]
        text = (item.text() or '').strip()
        if c == 5:
            row['enabled'] = text not in ('否', '0', 'false', 'False', 'N', 'n')
        elif c in (1, 2, 3, 4):
            key = ('pixelX', 'pixelY', 'worldX', 'worldY')[c - 1]
            try:
                row[key] = float(text)
            except ValueError:
                row[key] = 0.0
        self._emit()

    def _add_row(self):
        pts = self.params.setdefault('points', [])
        pts.append(_empty_row(len(pts)))
        self._reload_table()
        self._emit()

    def _remove_rows(self):
        rows = sorted({i.row() for i in self.table.selectedIndexes()}, reverse=True)
        pts = self.params.setdefault('points', [])
        for r in rows:
            if 0 <= r < len(pts):
                pts.pop(r)
        for i, row in enumerate(pts):
            row['index'] = i + 1
        self._reload_table()
        self._emit()

    def _reset9(self):
        self.params['points'] = [_empty_row(i) for i in range(9)]
        self._reload_table()
        self._emit()
