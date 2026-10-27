"""位置修正（pose_correct）属性浮窗 — VisionMaster p=9 壳.

典型链：模板匹配 → 位置修正 → 后续检测。
设计态写入基准位姿 / 跟随 ROI；运行时透传图像并输出矫正矩阵字段。
"""
from copy import deepcopy

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTabWidget, QFormLayout, QLineEdit,
    QComboBox, QDoubleSpinBox, QScrollArea, QFrame, QCheckBox,
)

from desktop.widgets.switch import OrangeSwitch


def normalize_pose_correct_params(params=None):
    p = deepcopy(params or {})
    p.setdefault('fixtureSource', 'auto')  # auto | manual | bind
    p.setdefault('baseX', 0.0)
    p.setdefault('baseY', 0.0)
    p.setdefault('baseAngle', 0.0)
    p.setdefault('followRoi', True)
    p.setdefault('outputCoord', 'fixture')  # fixture | image
    p.setdefault('bindStepId', '')
    p.setdefault('bindField', 'matches[0]')
    return p


class PoseCorrectPanel(QWidget):
    """三 Tab：基本参数 / 基准位姿 / 输出."""
    changed = Signal(dict)

    def __init__(self, step, definition, project, parent=None):
        super().__init__(parent)
        self.step = deepcopy(step)
        self.definition = definition or {}
        self.project = project or {}
        self.params = normalize_pose_correct_params(step.get('params'))
        self.step['params'] = self.params

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        hint = QLabel(
            '对齐 VisionMaster「位置修正」：用上游匹配位姿校正后续 ROI / 坐标系。'
            '引擎侧透传图像并输出 fixture 字段；检测链请接在本节点之后。'
        )
        hint.setObjectName('dialogHint')
        hint.setWordWrap(True)
        hint.setStyleSheet('color:#666;padding:8px 10px 4px;')
        root.addWidget(hint)

        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)
        self.tabs.addTab(self._wrap(self._basic_tab()), '基本参数')
        self.tabs.addTab(self._wrap(self._pose_tab()), '基准位姿')
        self.tabs.addTab(self._wrap(self._out_tab()), '输出')

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
        form = QFormLayout(w)
        form.setContentsMargins(10, 10, 10, 10)
        form.setSpacing(8)

        name = QLineEdit(self.step.get('name') or '位置修正')
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

        def _sub_label(node_id, port='图像'):
            return f"{index_map.get(node_id, '?')} {names.get(node_id, node_id)}.{port}"

        for node in sorted(incoming, key=lambda n: (index_map.get(n, 999), n)):
            image_from.addItem(_sub_label(node), node)
        current = self.step.get('imageFrom')
        if current and image_from.findData(current) < 0:
            image_from.addItem('已断开：' + _sub_label(current), current)
        image_from.setCurrentIndex(max(0, image_from.findData(current)))
        image_from.currentIndexChanged.connect(
            lambda _: self._set_top('imageFrom', image_from.currentData())
        )
        form.addRow('输入源', image_from)

        src = QComboBox()
        src.addItem('自动（上游匹配结果）', 'auto')
        src.addItem('手动基准位姿', 'manual')
        src.addItem('绑定步骤字段', 'bind')
        idx = max(0, src.findData(self.params.get('fixtureSource') or 'auto'))
        src.setCurrentIndex(idx)
        src.currentIndexChanged.connect(lambda _: self._set_param('fixtureSource', src.currentData()))
        form.addRow('位姿来源', src)

        follow = OrangeSwitch(bool(self.params.get('followRoi', True)))
        follow.toggled.connect(lambda c: self._set_param('followRoi', bool(c)))
        form.addRow('跟随 ROI', follow)

        tip = QLabel('建议上游为「模板匹配定位」；未连线时画布显示红叹号。')
        tip.setWordWrap(True)
        tip.setStyleSheet('color:#888;')
        form.addRow(tip)
        return w

    def _pose_tab(self):
        w = QWidget()
        form = QFormLayout(w)
        form.setContentsMargins(10, 10, 10, 10)
        form.setSpacing(8)

        tip = QLabel('手动模式下填写基准 X/Y/角度；自动模式运行时取上游 matches[0]。')
        tip.setWordWrap(True)
        tip.setStyleSheet('color:#555;')
        form.addRow(tip)

        for key, label, lo, hi in (
            ('baseX', '基准 X', -1e6, 1e6),
            ('baseY', '基准 Y', -1e6, 1e6),
            ('baseAngle', '基准角度 (°)', -360, 360),
        ):
            sp = QDoubleSpinBox()
            sp.setRange(lo, hi)
            sp.setDecimals(4)
            sp.setValue(float(self.params.get(key) or 0))
            sp.valueChanged.connect(lambda v, k=key: self._set_param(k, float(v)))
            form.addRow(label, sp)

        bind_id = QLineEdit(str(self.params.get('bindStepId') or ''))
        bind_id.setPlaceholderText('上游步骤 id（绑定模式）')
        bind_id.editingFinished.connect(lambda: self._set_param('bindStepId', bind_id.text().strip()))
        form.addRow('绑定步骤', bind_id)

        bind_field = QLineEdit(str(self.params.get('bindField') or 'matches[0]'))
        bind_field.editingFinished.connect(lambda: self._set_param('bindField', bind_field.text().strip()))
        form.addRow('绑定字段', bind_field)
        return w

    def _out_tab(self):
        w = QWidget()
        form = QFormLayout(w)
        form.setContentsMargins(10, 10, 10, 10)
        form.setSpacing(8)

        coord = QComboBox()
        coord.addItem('夹具坐标系 (fixture)', 'fixture')
        coord.addItem('图像坐标系 (image)', 'image')
        idx = max(0, coord.findData(self.params.get('outputCoord') or 'fixture'))
        coord.setCurrentIndex(idx)
        coord.currentIndexChanged.connect(lambda _: self._set_param('outputCoord', coord.currentData()))
        form.addRow('输出坐标系', coord)

        tip = QLabel('运行结果字段：fixtureX / fixtureY / fixtureAngle / matrix（设计态可绑定）。')
        tip.setWordWrap(True)
        tip.setStyleSheet('color:#888;')
        form.addRow(tip)
        return w
