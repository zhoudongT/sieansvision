"""模板匹配定位（locate）属性浮窗 — VisionMaster 快速/灰度匹配四 Tab 壳.

Tabs: 基本参数 | 特征模板或灰度模板 | 运行参数 | 结果显示
matchMode: fast（快速/特征）| gray（灰度相关）.
"""
from copy import deepcopy

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTabWidget,
    QFormLayout, QLineEdit, QComboBox, QDoubleSpinBox, QSpinBox,
    QScrollArea, QFrame, QFileDialog, QCheckBox,
)

from desktop.widgets.switch import OrangeSwitch


def normalize_locate_params(params=None):
    p = deepcopy(params or {})
    mode = p.get('matchMode') or 'fast'
    if mode not in ('fast', 'gray'):
        mode = 'fast'
    p['matchMode'] = mode
    p.setdefault('minScore', 0.85)
    p.setdefault('maxMatches', 1)
    p.setdefault('angleStart', 0.0)
    p.setdefault('angleEnd', 0.0)
    p.setdefault('angleStep', 10.0)
    p.setdefault('scales', [1])
    p.setdefault('templatePath', '')
    p.setdefault('hasTemplate', False)
    p.setdefault('templateReady', False)
    p.setdefault('showMatchBox', True)
    p.setdefault('showScore', True)
    p.setdefault('showContour', True)
    p.setdefault('showOrigin', False)
    p.setdefault('resultJudgeEnable', False)
    p.setdefault('roiMode', 'inherit')  # inherit | draw
    # Gray-match extras (VM 灰度模板 / 运行参数)
    p.setdefault('grayLevel', 8)          # 灰度级数
    p.setdefault('scoreType', 'ncc')      # ncc | sad
    p.setdefault('subPixel', True)
    p.setdefault('timeoutMs', 3000)
    return p


class LocateMatchPanel(QWidget):
    """四 Tab：基本参数 / 特征或灰度模板 / 运行参数 / 结果显示."""
    changed = Signal(dict)

    def __init__(self, step, definition, project, parent=None):
        super().__init__(parent)
        self.step = deepcopy(step)
        self.definition = definition or {}
        self.project = project or {}
        self.params = normalize_locate_params(step.get('params'))
        self.step['params'] = self.params

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        mode = self.params.get('matchMode') or 'fast'
        mode_label = '灰度模板匹配' if mode == 'gray' else '快速匹配'
        tpl_label = '灰度模板' if mode == 'gray' else '特征模板'
        hint = QLabel(f'对齐 VisionMaster「{mode_label}」：基本参数 / {tpl_label} / 运行参数 / 结果显示')
        hint.setObjectName('dialogHint')
        hint.setWordWrap(True)
        hint.setStyleSheet('color:#666;padding:8px 10px 4px;')
        root.addWidget(hint)

        self.tabs = QTabWidget()
        self.tabs.setObjectName('locateMatchTabs')
        root.addWidget(self.tabs, 1)

        self.tabs.addTab(self._wrap(self._basic_tab()), '基本参数')
        self.tabs.addTab(self._wrap(self._template_tab()), tpl_label)
        self.tabs.addTab(self._wrap(self._run_tab()), '运行参数')
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
            # Keep templateReady in sync with path / flag
            if key in ('templatePath', 'hasTemplate'):
                self.params['templateReady'] = bool(
                    self.params.get('hasTemplate') or str(self.params.get('templatePath') or '').strip()
                )
                self.params['hasTemplate'] = self.params['templateReady']
            self._emit()

    def _set_top(self, key, value):
        if self.step.get(key) != value:
            self.step[key] = deepcopy(value)
            self._emit()

    def _on_match_mode(self, mode):
        """Switch fast↔gray; refresh tab title + default module name hint."""
        if mode not in ('fast', 'gray'):
            mode = 'fast'
        if self.params.get('matchMode') == mode:
            return
        self.params['matchMode'] = mode
        # Rename second tab
        if hasattr(self, 'tabs') and self.tabs.count() >= 2:
            self.tabs.setTabText(1, '灰度模板' if mode == 'gray' else '特征模板')
        # Soft-rename module if still default-ish
        cur = (self.step.get('name') or '').strip()
        if cur in ('', '模板匹配定位', '快速匹配', '灰度模板匹配', '快速模板匹配'):
            self.step['name'] = '灰度模板匹配' if mode == 'gray' else '模板匹配定位'
        self._emit()

    def _basic_tab(self):
        w = QWidget()
        form = QFormLayout(w)
        form.setContentsMargins(10, 10, 10, 10)
        form.setSpacing(8)

        name = QLineEdit(self.step.get('name') or self.definition.get('name') or '模板匹配定位')
        name.setMaxLength(80)
        name.editingFinished.connect(lambda: self._set_top('name', name.text()))
        form.addRow('模块名称', name)

        mode = QComboBox()
        mode.addItem('快速匹配（特征）', 'fast')
        mode.addItem('灰度模板匹配', 'gray')
        mi = max(0, mode.findData(self.params.get('matchMode') or 'fast'))
        mode.setCurrentIndex(mi)
        mode.currentIndexChanged.connect(lambda _: self._on_match_mode(mode.currentData()))
        form.addRow('匹配模式', mode)

        # 输入源 — VM「0 图像源1.图像」
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

        roi = QComboBox()
        roi.addItem('继承（连线 ROI / 全图）', 'inherit')
        roi.addItem('绘制 ROI', 'draw')
        idx = max(0, roi.findData(self.params.get('roiMode') or 'inherit'))
        roi.setCurrentIndex(idx)
        roi.currentIndexChanged.connect(lambda _: self._set_param('roiMode', roi.currentData()))
        form.addRow('ROI区域', roi)

        tip = QLabel('先连图像源再选输入源；未配置完整时画布节点显示红叹号。')
        tip.setWordWrap(True)
        tip.setStyleSheet('color:#888;')
        form.addRow(tip)
        return w

    def _template_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(10, 10, 10, 10)

        tip = QLabel(
            'VisionMaster「灰度模板」：创建 / 载入灰度模板。' if (self.params.get('matchMode') == 'gray') else 'VisionMaster「特征模板」：创建 / 载入 / 编辑模板；对比度阈值与画笔在模板配置子窗。'
            '此处落地载入路径与就绪标志（算法模板编辑器后续迭代）。'
        )
        tip.setWordWrap(True)
        tip.setStyleSheet('color:#555;')
        lay.addWidget(tip)

        form = QFormLayout()
        path_edit = QLineEdit(str(self.params.get('templatePath') or ''))
        path_edit.setPlaceholderText('模板文件路径 / 方案内引用')
        path_edit.editingFinished.connect(lambda: self._set_param('templatePath', path_edit.text().strip()))
        form.addRow('模板路径', path_edit)

        row = QHBoxLayout()
        load_btn = QPushButton('载入模板…')
        create_btn = QPushButton('标记已创建')
        clear_btn = QPushButton('清除')

        def _load():
            path, _ = QFileDialog.getOpenFileName(
                self, '载入特征模板', '', '模板/图像 (*.png *.bmp *.jpg *.jpeg *.tif *.json);;所有文件 (*)'
            )
            if path:
                path_edit.setText(path)
                self._set_param('templatePath', path)
                self._set_param('hasTemplate', True)

        def _mark():
            self._set_param('hasTemplate', True)
            status.setText('模板状态：已就绪（已创建/载入）')

        def _clear():
            path_edit.clear()
            self.params['templatePath'] = ''
            self.params['hasTemplate'] = False
            self.params['templateReady'] = False
            status.setText('模板状态：未配置')
            self._emit()

        load_btn.clicked.connect(_load)
        create_btn.clicked.connect(_mark)
        clear_btn.clicked.connect(_clear)
        row.addWidget(load_btn)
        row.addWidget(create_btn)
        row.addWidget(clear_btn)
        row.addStretch(1)
        form.addRow('操作', row)
        lay.addLayout(form)

        ready = bool(self.params.get('hasTemplate') or str(self.params.get('templatePath') or '').strip())
        status = QLabel('模板状态：已就绪（已创建/载入）' if ready else '模板状态：未配置')
        status.setObjectName('locateTemplateStatus')
        status.setStyleSheet('font-weight:600;color:#c62828;' if not ready else 'font-weight:600;color:#2e7d32;')
        lay.addWidget(status)
        self._tpl_status = status
        lay.addStretch(1)
        return w

    def _run_tab(self):
        w = QWidget()
        form = QFormLayout(w)
        form.setContentsMargins(10, 10, 10, 10)
        form.setSpacing(8)

        score = QDoubleSpinBox()
        score.setRange(0.0, 1.0)
        score.setSingleStep(0.01)
        score.setDecimals(3)
        score.setValue(float(self.params.get('minScore') or 0.85))
        score.valueChanged.connect(lambda v: self._set_param('minScore', float(v)))
        form.addRow('最小匹配分数', score)

        matches = QSpinBox()
        matches.setRange(1, 50)
        matches.setValue(int(self.params.get('maxMatches') or 1))
        matches.valueChanged.connect(lambda v: self._set_param('maxMatches', int(v)))
        form.addRow('最大匹配个数', matches)

        a0 = QDoubleSpinBox(); a0.setRange(-180, 180); a0.setValue(float(self.params.get('angleStart') or 0))
        a1 = QDoubleSpinBox(); a1.setRange(-180, 180); a1.setValue(float(self.params.get('angleEnd') or 0))
        a_step = QDoubleSpinBox(); a_step.setRange(0.1, 180); a_step.setValue(float(self.params.get('angleStep') or 10))
        a0.valueChanged.connect(lambda v: self._set_param('angleStart', float(v)))
        a1.valueChanged.connect(lambda v: self._set_param('angleEnd', float(v)))
        a_step.valueChanged.connect(lambda v: self._set_param('angleStep', float(v)))
        form.addRow('起始角度', a0)
        form.addRow('终止角度', a1)
        form.addRow('角度步长', a_step)

        if (self.params.get('matchMode') or 'fast') == 'gray':
            gray_lv = QSpinBox(); gray_lv.setRange(2, 256)
            gray_lv.setValue(int(self.params.get('grayLevel') or 8))
            gray_lv.valueChanged.connect(lambda v: self._set_param('grayLevel', int(v)))
            form.addRow('灰度级数', gray_lv)

            score_type = QComboBox()
            score_type.addItem('NCC 归一化相关', 'ncc')
            score_type.addItem('SAD 绝对差', 'sad')
            si = max(0, score_type.findData(self.params.get('scoreType') or 'ncc'))
            score_type.setCurrentIndex(si)
            score_type.currentIndexChanged.connect(
                lambda _: self._set_param('scoreType', score_type.currentData())
            )
            form.addRow('评分方式', score_type)

            sub = OrangeSwitch(bool(self.params.get('subPixel', True)))
            sub.toggled.connect(lambda c: self._set_param('subPixel', bool(c)))
            form.addRow('亚像素', sub)

            timeout = QSpinBox(); timeout.setRange(0, 60000)
            timeout.setValue(int(self.params.get('timeoutMs') or 3000))
            timeout.valueChanged.connect(lambda v: self._set_param('timeoutMs', int(v)))
            form.addRow('超时(ms)', timeout)

        tip = QLabel('对应 VM「运行参数」：分数/个数/角度；灰度模式另含级数/评分/亚像素/超时。')
        tip.setWordWrap(True)
        tip.setStyleSheet('color:#888;')
        form.addRow(tip)
        return w

    def _result_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(10, 10, 10, 10)

        tip = QLabel('对应 VM「结果显示」：匹配框 / 分数 / 轮廓 / 原点等叠加开关。')
        tip.setWordWrap(True)
        tip.setStyleSheet('color:#555;')
        lay.addWidget(tip)

        form = QFormLayout()

        def _sw(key, label, default=True):
            sw = OrangeSwitch(bool(self.params.get(key, default)))
            sw.toggled.connect(lambda checked, k=key: self._set_param(k, bool(checked)))
            form.addRow(label, sw)

        _sw('showMatchBox', '显示匹配框', True)
        _sw('showScore', '显示匹配分数', True)
        _sw('showContour', '显示轮廓', True)
        _sw('showOrigin', '显示模板原点', False)
        _sw('resultJudgeEnable', '结果判断使能', False)
        lay.addLayout(form)
        lay.addStretch(1)
        return w
