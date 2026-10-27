"""测量几何壳 — 线线交点 / 点点距 / 点线距（VM p=14/16/17）.

ops: line_intersect | point_distance | point_line_distance
绑定上游几何结果字段，运行时做解析几何计算。
"""
from copy import deepcopy

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTabWidget, QFormLayout, QLineEdit,
    QComboBox, QDoubleSpinBox, QScrollArea, QFrame,
)

from desktop.widgets.switch import OrangeSwitch

OP_META = {
    'line_intersect': ('线与线交点', '绑定两条直线（或四点），求交点。'),
    'point_distance': ('点与点距离', '绑定两个点坐标，求欧氏距离。'),
    'point_line_distance': ('点与线距离', '绑定一点与一条直线，求垂距。'),
}


def normalize_measure_geom_params(op, params=None):
    p = deepcopy(params or {})
    p.setdefault('mode', 'bind')
    if op == 'line_intersect':
        p.setdefault('line1From', ''); p.setdefault('line1Field', 'lines[0]')
        p.setdefault('line2From', ''); p.setdefault('line2Field', 'lines[0]')
        p.setdefault('x1', 0.0); p.setdefault('y1', 0.0)
        p.setdefault('x2', 100.0); p.setdefault('y2', 0.0)
        p.setdefault('x3', 50.0); p.setdefault('y3', -50.0)
        p.setdefault('x4', 50.0); p.setdefault('y4', 50.0)
    elif op == 'point_distance':
        p.setdefault('point1From', ''); p.setdefault('point1Field', 'matches[0]')
        p.setdefault('point2From', ''); p.setdefault('point2Field', 'matches[0]')
        p.setdefault('x1', 0.0); p.setdefault('y1', 0.0)
        p.setdefault('x2', 100.0); p.setdefault('y2', 0.0)
    else:
        p.setdefault('pointFrom', ''); p.setdefault('pointField', 'matches[0]')
        p.setdefault('lineFrom', ''); p.setdefault('lineField', 'lines[0]')
        p.setdefault('px', 0.0); p.setdefault('py', 0.0)
        p.setdefault('x1', 0.0); p.setdefault('y1', 0.0)
        p.setdefault('x2', 100.0); p.setdefault('y2', 0.0)
    p.setdefault('unit', 'px')
    p.setdefault('scale', 1.0)
    p.setdefault('showOverlay', True)
    p.setdefault('showPoints', True)
    p.setdefault('showLines', True)
    p.setdefault('showLabels', True)
    p.setdefault('showDistanceText', True)
    return p


class MeasureGeomPanel(QWidget):
    changed = Signal(dict)

    def __init__(self, step, definition, project, parent=None):
        super().__init__(parent)
        self.step = deepcopy(step)
        self.definition = definition or {}
        self.project = project or {}
        self.op = step.get('operation') or 'point_distance'
        title, tip = OP_META.get(self.op, ('几何测量', ''))
        self.params = normalize_measure_geom_params(self.op, step.get('params'))
        self.step['params'] = self.params
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        hint = QLabel('对齐 VisionMaster「%s」。%s' % (title, tip))
        hint.setWordWrap(True)
        hint.setStyleSheet('color:#666;padding:8px 10px 4px;')
        root.addWidget(hint)
        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)
        self.tabs.addTab(self._wrap(self._basic_tab(title)), '基本参数')
        self.tabs.addTab(self._wrap(self._manual_tab()), '手动坐标')
        self.tabs.addTab(self._wrap(self._result_tab()), '结果显示')

    def _wrap(self, inner):
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame); scroll.setWidget(inner); return scroll

    def _emit(self):
        self.step['params'] = deepcopy(self.params)
        self.changed.emit(deepcopy(self.step))

    def _set_param(self, key, value):
        if self.params.get(key) != value:
            self.params[key] = deepcopy(value); self._emit()

    def _set_top(self, key, value):
        if self.step.get(key) != value:
            self.step[key] = deepcopy(value); self._emit()

    def _step_items(self):
        items = [('', '（未绑定）'), ('source', '0 图像源1')]
        for i, s in enumerate(self.project.get('steps', []), start=1):
            if s.get('id') == self.step.get('id'):
                continue
            items.append((s['id'], '%d %s' % (i, s.get('name') or s.get('operation'))))
        return items

    def _bind_row(self, form, label, id_key, field_key, default_field):
        box = QComboBox()
        for data, lab in self._step_items():
            box.addItem(lab, data)
        cur = self.params.get(id_key) or ''
        idx = box.findData(cur)
        if idx < 0 and cur:
            box.addItem('已丢失：' + cur, cur); idx = box.findData(cur)
        box.setCurrentIndex(max(0, idx))
        box.currentIndexChanged.connect(lambda _: self._set_param(id_key, box.currentData() or ''))
        form.addRow(label + ' 来源', box)
        field = QLineEdit(str(self.params.get(field_key) or default_field))
        field.setPlaceholderText(default_field)
        field.editingFinished.connect(lambda: self._set_param(field_key, field.text().strip() or default_field))
        from PySide6.QtWidgets import QHBoxLayout, QPushButton
        from desktop.upstream_field_picker import fill_line_from_picker
        frow = QHBoxLayout()
        pick = QPushButton('插入上游字段')
        pick.clicked.connect(
            lambda *_ , e=field, fk=field_key, df=default_field: (
                fill_line_from_picker(self, self.project, self.step.get('id'), e, self._set_param, fk)
                or (e.setText(df) if not e.text().strip() else None)
            )
        )
        frow.addWidget(field, 1)
        frow.addWidget(pick)
        form.addRow(label + ' 字段', frow)

    def _basic_tab(self, title):
        w = QWidget(); form = QFormLayout(w); form.setContentsMargins(10, 10, 10, 10)
        name = QLineEdit(self.step.get('name') or title)
        name.setMaxLength(80)
        name.editingFinished.connect(lambda: self._set_top('name', name.text()))
        form.addRow('模块名称', name)
        mode = QComboBox()
        mode.addItem('绑定上游结果', 'bind')
        mode.addItem('手动坐标', 'manual')
        mode.setCurrentIndex(max(0, mode.findData(self.params.get('mode') or 'bind')))
        mode.currentIndexChanged.connect(lambda _: self._set_param('mode', mode.currentData()))
        form.addRow('输入模式', mode)
        if self.op == 'line_intersect':
            self._bind_row(form, '直线1', 'line1From', 'line1Field', 'lines[0]')
            self._bind_row(form, '直线2', 'line2From', 'line2Field', 'lines[0]')
        elif self.op == 'point_distance':
            self._bind_row(form, '点1', 'point1From', 'point1Field', 'matches[0]')
            self._bind_row(form, '点2', 'point2From', 'point2Field', 'matches[0]')
        else:
            self._bind_row(form, '点', 'pointFrom', 'pointField', 'matches[0]')
            self._bind_row(form, '直线', 'lineFrom', 'lineField', 'lines[0]')
        unit = QComboBox()
        for u in ('px', 'mm', 'cm'):
            unit.addItem(u, u)
        unit.setCurrentIndex(max(0, unit.findData(self.params.get('unit') or 'px')))
        unit.currentIndexChanged.connect(lambda _: self._set_param('unit', unit.currentData()))
        form.addRow('单位', unit)
        scale = QDoubleSpinBox(); scale.setRange(1e-9, 1e6); scale.setDecimals(6)
        scale.setValue(float(self.params.get('scale') or 1))
        scale.valueChanged.connect(lambda v: self._set_param('scale', float(v)))
        form.addRow('像素比例', scale)
        tip = QLabel('绑定字段示例：lines[0]、matches[0]、center；手动模式在「手动坐标」Tab 填写。')
        tip.setWordWrap(True); tip.setStyleSheet('color:#888;'); form.addRow(tip)
        return w

    def _manual_tab(self):
        w = QWidget(); form = QFormLayout(w); form.setContentsMargins(10, 10, 10, 10)
        if self.op == 'line_intersect':
            keys = [('x1','线1 X1'),('y1','线1 Y1'),('x2','线1 X2'),('y2','线1 Y2'),
                    ('x3','线2 X1'),('y3','线2 Y1'),('x4','线2 X2'),('y4','线2 Y2')]
        elif self.op == 'point_distance':
            keys = [('x1','点1 X'),('y1','点1 Y'),('x2','点2 X'),('y2','点2 Y')]
        else:
            keys = [('px','点 X'),('py','点 Y'),('x1','线 X1'),('y1','线 Y1'),('x2','线 X2'),('y2','线 Y2')]
        for key, lab in keys:
            sp = QDoubleSpinBox(); sp.setRange(-1e9, 1e9); sp.setDecimals(4)
            sp.setValue(float(self.params.get(key) or 0))
            sp.valueChanged.connect(lambda v, k=key: self._set_param(k, float(v)))
            form.addRow(lab, sp)
        return w

    def _result_tab(self):
        w = QWidget(); form = QFormLayout(w); form.setContentsMargins(10, 10, 10, 10)
        for key, lab in (
            ('showOverlay', '显示叠加'),
            ('showPoints', '显示点'),
            ('showLines', '显示线'),
            ('showLabels', '显示标签'),
            ('showDistanceText', '显示距离文字'),
        ):
            sw = OrangeSwitch(bool(self.params.get(key, True)))
            sw.toggled.connect(lambda c, k=key: self._set_param(k, bool(c)))
            form.addRow(lab, sw)
        tip = {
            'line_intersect': '结果：intersectX / intersectY / parallel / status · 叠层随开关',
            'point_distance': '结果：distance / dx / dy / status · 叠层随开关',
            'point_line_distance': '结果：distance / footX / footY / status · 叠层随开关',
        }.get(self.op, '结果字段见引擎')
        lab = QLabel(tip); lab.setWordWrap(True); lab.setStyleSheet('color:#888;'); form.addRow(lab)
        return w
