"""畸变矫正（distort_correct）属性浮窗 — VisionMaster p=13 壳.

设计态：标定文件路径 / 棋盘格规格 / 畸变系数占位；运行时透传图像并报告参数。
"""
from copy import deepcopy

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTabWidget, QFormLayout, QLineEdit,
    QComboBox, QDoubleSpinBox, QSpinBox, QScrollArea, QFrame, QHBoxLayout,
    QPushButton, QFileDialog,
)

from desktop.widgets.switch import OrangeSwitch


def normalize_distort_params(params=None):
    p = deepcopy(params or {})
    p.setdefault('calibPath', '')
    p.setdefault('mode', 'file')  # file | coeffs | chessboard
    p.setdefault('fx', 1000.0)
    p.setdefault('fy', 1000.0)
    p.setdefault('cx', 0.0)
    p.setdefault('cy', 0.0)
    p.setdefault('k1', 0.0)
    p.setdefault('k2', 0.0)
    p.setdefault('p1', 0.0)
    p.setdefault('p2', 0.0)
    p.setdefault('k3', 0.0)
    p.setdefault('boardCols', 9)
    p.setdefault('boardRows', 6)
    p.setdefault('squareSize', 10.0)
    p.setdefault('alpha', 0.0)
    p.setdefault('enabled', True)
    p.setdefault('keepSize', True)
    p.setdefault('showGrid', False)
    p.setdefault('interp', 'linear')
    return p


class DistortCorrectPanel(QWidget):
    """三 Tab：基本参数 / 相机内参 / 结果显示."""
    changed = Signal(dict)

    def __init__(self, step, definition, project, parent=None):
        super().__init__(parent)
        self.step = deepcopy(step)
        self.definition = definition or {}
        self.project = project or {}
        self.params = normalize_distort_params(step.get('params'))
        self.step['params'] = self.params

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        hint = QLabel(
            '对齐 VisionMaster「畸变矫正」：加载标定文件或填写内参/畸变系数；'
            '引擎侧目前透传图像并回显参数（设计态可完整配置）。'
        )
        hint.setObjectName('dialogHint')
        hint.setWordWrap(True)
        hint.setStyleSheet('color:#666;padding:8px 10px 4px;')
        root.addWidget(hint)

        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)
        self.tabs.addTab(self._wrap(self._basic_tab()), '基本参数')
        self.tabs.addTab(self._wrap(self._intrinsics_tab()), '相机内参')
        self.tabs.addTab(self._wrap(self._run_tab()), '运行参数')
        self.tabs.addTab(self._wrap(self._result_tab()), '结果显示')

    def _wrap(self, inner):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(inner)
        return scroll

    def _insert_upstream_field(self):
        from desktop.upstream_field_picker import pick_upstream_field, host_last_result
        picked = pick_upstream_field(
            self, self.project, step_id=self.step.get('id'),
            last_result=host_last_result(self),
        )
        if not picked:
            return
        _nid, _field, token = picked
        self._upstream_ref.setText(token)
        self._set_param('upstreamRef', token)

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

        name = QLineEdit(self.step.get('name') or '畸变矫正')
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

        mode = QComboBox()
        mode.addItem('标定文件', 'file')
        mode.addItem('手动内参/畸变系数', 'coeffs')
        mode.addItem('棋盘格采集（占位）', 'chessboard')
        mode.setCurrentIndex(max(0, mode.findData(self.params.get('mode') or 'file')))
        mode.currentIndexChanged.connect(lambda _: self._set_param('mode', mode.currentData()))
        form.addRow('矫正模式', mode)

        row = QHBoxLayout()
        path = QLineEdit(str(self.params.get('calibPath') or ''))
        path.setPlaceholderText('标定文件路径（.yml / .json / .xml）')
        path.editingFinished.connect(lambda: self._set_param('calibPath', path.text().strip()))
        browse = QPushButton('浏览…')
        def _browse():
            f, _ = QFileDialog.getOpenFileName(self, '选择标定文件', '', '标定 (*.yml *.yaml *.json *.xml);;全部 (*)')
            if f:
                path.setText(f)
                self._set_param('calibPath', f)
        browse.clicked.connect(_browse)
        row.addWidget(path, 1)
        row.addWidget(browse)
        form.addRow('标定文件', row)

        en = OrangeSwitch(bool(self.params.get('enabled', True)))
        en.toggled.connect(lambda c: self._set_param('enabled', bool(c)))
        form.addRow('启用矫正', en)

        uref_row = QHBoxLayout()
        self._upstream_ref = QLineEdit(str(self.params.get('upstreamRef') or ''))
        self._upstream_ref.setPlaceholderText('results.<模块>.字段 — 点击挑选')
        self._upstream_ref.editingFinished.connect(
            lambda: self._set_param('upstreamRef', self._upstream_ref.text().strip())
        )
        uref_btn = QPushButton('插入上游字段')
        uref_btn.clicked.connect(self._insert_upstream_field)
        uref_row.addWidget(self._upstream_ref, 1)
        uref_row.addWidget(uref_btn)
        form.addRow('上游参考', uref_row)

        tip = QLabel('未配置标定文件且非手动系数时，画布显示红叹号。可用「插入上游字段」订阅上游结果。')
        tip.setWordWrap(True)
        tip.setStyleSheet('color:#888;')
        form.addRow(tip)
        return w

    def _intrinsics_tab(self):
        w = QWidget()
        form = QFormLayout(w)
        form.setContentsMargins(10, 10, 10, 10)
        form.setSpacing(8)
        tip = QLabel('手动模式填写相机内参与畸变系数（OpenCV 模型）。')
        tip.setWordWrap(True)
        tip.setStyleSheet('color:#555;')
        form.addRow(tip)
        for key, label, lo, hi, dec in (
            ('fx', 'fx', 0.0, 1e7, 4),
            ('fy', 'fy', 0.0, 1e7, 4),
            ('cx', 'cx', -1e7, 1e7, 4),
            ('cy', 'cy', -1e7, 1e7, 4),
            ('k1', 'k1', -10, 10, 6),
            ('k2', 'k2', -10, 10, 6),
            ('p1', 'p1', -10, 10, 6),
            ('p2', 'p2', -10, 10, 6),
            ('k3', 'k3', -10, 10, 6),
            ('alpha', '有效像素比例 alpha', 0.0, 1.0, 3),
        ):
            sp = QDoubleSpinBox()
            sp.setRange(lo, hi)
            sp.setDecimals(dec)
            sp.setValue(float(self.params.get(key) or 0))
            sp.valueChanged.connect(lambda v, k=key: self._set_param(k, float(v)))
            form.addRow(label, sp)

        cols = QSpinBox(); cols.setRange(2, 40); cols.setValue(int(self.params.get('boardCols') or 9))
        cols.valueChanged.connect(lambda v: self._set_param('boardCols', int(v)))
        form.addRow('棋盘格列数', cols)
        rows = QSpinBox(); rows.setRange(2, 40); rows.setValue(int(self.params.get('boardRows') or 6))
        rows.valueChanged.connect(lambda v: self._set_param('boardRows', int(v)))
        form.addRow('棋盘格行数', rows)
        sq = QDoubleSpinBox(); sq.setRange(0.01, 1000); sq.setDecimals(3)
        sq.setValue(float(self.params.get('squareSize') or 10))
        sq.valueChanged.connect(lambda v: self._set_param('squareSize', float(v)))
        form.addRow('方格边长', sq)
        return w

    def _run_tab(self):
        w = QWidget()
        form = QFormLayout(w)
        form.setContentsMargins(10, 10, 10, 10)
        self._run_extra_rows(form)
        tip = QLabel('未配标定文件且非手动系数时画布红叹号。')
        tip.setStyleSheet('color:#888;')
        form.addRow(tip)
        return w

    def _run_extra_rows(self, form):
        en = OrangeSwitch(bool(self.params.get('enabled', True)))
        en.toggled.connect(lambda c: self._set_param('enabled', bool(c)))
        form.addRow('使能矫正', en)
        ks = OrangeSwitch(bool(self.params.get('keepSize', True)))
        ks.toggled.connect(lambda c: self._set_param('keepSize', bool(c)))
        form.addRow('保持尺寸', ks)
        sg = OrangeSwitch(bool(self.params.get('showGrid', False)))
        sg.toggled.connect(lambda c: self._set_param('showGrid', bool(c)))
        form.addRow('叠加网格', sg)
        interp = QComboBox()
        for v, lab in (('nearest', '最近邻'), ('linear', '双线性'), ('cubic', '双三次')):
            interp.addItem(lab, v)
        interp.setCurrentIndex(max(0, interp.findData(self.params.get('interp') or 'linear')))
        interp.currentIndexChanged.connect(lambda _: self._set_param('interp', interp.currentData()))
        form.addRow('插值', interp)
        alpha = QDoubleSpinBox(); alpha.setRange(0, 1); alpha.setDecimals(3); alpha.setSingleStep(0.05)
        alpha.setValue(float(self.params.get('alpha') or 0))
        alpha.valueChanged.connect(lambda v: self._set_param('alpha', float(v)))
        form.addRow('有效区域 α', alpha)

    def _result_tab(self):
        w = QWidget()
        form = QFormLayout(w)
        form.setContentsMargins(10, 10, 10, 10)
        tip = QLabel('运行结果字段：status / mode / calibPath / coeffs（设计态可绑定）。')
        tip.setWordWrap(True)
        tip.setStyleSheet('color:#888;')
        form.addRow(tip)
        return w
