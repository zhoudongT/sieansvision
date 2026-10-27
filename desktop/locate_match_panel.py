"""模板匹配定位（locate）属性浮窗 — VisionMaster 快速/灰度匹配四 Tab 壳.

Tabs: 基本参数 | 特征模板或灰度模板 | 运行参数 | 结果显示
matchMode: fast（快速/特征）| gray（灰度相关）.
"""
from copy import deepcopy

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTabWidget,
    QFormLayout, QLineEdit, QComboBox, QDoubleSpinBox, QSpinBox,
    QScrollArea, QFrame, QFileDialog, QCheckBox, QDialog, QDialogButtonBox,
    QSlider,
)

from desktop.widgets.switch import OrangeSwitch


def _rebuild_scales(p):
    """Derive engine `scales` list from VM-style start/end/step (cap 8)."""
    try:
        s0 = float(p.get('scaleStart') or 1.0)
        s1 = float(p.get('scaleEnd') or s0)
        st = float(p.get('scaleStep') or 0.1)
    except (TypeError, ValueError):
        p['scales'] = [1.0]
        return
    if st <= 0:
        st = 0.1
    if s1 < s0:
        s0, s1 = s1, s0
    vals = []
    x = s0
    # inclusive end with float tolerance
    while x <= s1 + 1e-9 and len(vals) < 8:
        vals.append(round(x, 4))
        x += st
    if not vals:
        vals = [round(s0, 4)]
    p['scales'] = vals


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
    p.setdefault('showCross', True)
    p.setdefault('showSearchRegion', True)
    p.setdefault('showFeaturePoints', False)
    p.setdefault('traceFullCanvas', False)
    p.setdefault('resultJudgeEnable', False)
    p.setdefault('resultJudgeMin', 0.0)
    p.setdefault('resultJudgeMax', 1.0)
    p.setdefault('roiMode', 'inherit')  # inherit | draw
    # Gray-match extras (VM 灰度模板 / 运行参数)
    p.setdefault('grayLevel', 8)          # 灰度级数
    p.setdefault('scoreType', 'ncc')      # ncc | sad
    p.setdefault('subPixel', True)
    p.setdefault('timeoutMs', 3000)
    p.setdefault('scaleStart', 1.0)
    p.setdefault('scaleEnd', 1.0)
    p.setdefault('scaleStep', 0.1)
    p.setdefault('contrast', 20)
    p.setdefault('maxOverlap', 0.5)
    # engine template_matching reads overlapThreshold — mirror maxOverlap
    if 'overlapThreshold' not in p:
        p['overlapThreshold'] = float(p.get('maxOverlap') or 0.5)
    p.setdefault('sortBy', 'score')
    # VM p07 运行参数帧：全部搜索 / 匹配极性 / 角度·尺度使能 / 金字塔级数
    p.setdefault('fullSearch', False)
    p.setdefault('matchPolarity', 'consider')  # consider | ignore
    p.setdefault('angleEnable', True)
    p.setdefault('scaleEnable', True)
    p.setdefault('pyramidLevels', 4)
    p.setdefault('featureScale', 3.0)   # VM 模板配置·特征尺度
    p.setdefault('contrastThreshold', 30)
    p.setdefault('brushSize', 8)
    p.setdefault('thresholdMode', 'auto')  # auto | manual
    _rebuild_scales(p)
    return p



class TemplateEditorDialog(QDialog):
    """VM 式模板配置子窗：对比度阈值 / 画笔大小 / 特征尺度（设计态参数壳）。"""

    def __init__(self, params=None, parent=None, *, gray=False):
        super().__init__(parent)
        self.setWindowTitle('灰度模板编辑' if gray else '特征模板编辑')
        self.setModal(True)
        self.resize(380, 280)
        self._params = dict(params or {})
        root = QVBoxLayout(self)
        tip = QLabel(
            '对标 VisionMaster 模板配置子窗：对比度阈值与画笔大小写入模块参数；'
            '全画布描摹：结果显示 Tab 可开 traceFullCanvas / 匹配框 / 分数 / 搜索区。'
        )
        tip.setWordWrap(True)
        tip.setStyleSheet('color:#555;font-size:11px;')
        root.addWidget(tip)
        form = QFormLayout()
        self.contrast = QSpinBox()
        self.contrast.setRange(0, 255)
        self.contrast.setValue(int(self._params.get('contrastThreshold') or 30))
        form.addRow('对比度阈值', self.contrast)
        self.brush = QSpinBox()
        self.brush.setRange(1, 64)
        self.brush.setValue(int(self._params.get('brushSize') or 8))
        form.addRow('画笔大小(px)', self.brush)
        self.feat = QDoubleSpinBox()
        self.feat.setRange(0.1, 20.0)
        self.feat.setDecimals(2)
        self.feat.setSingleStep(0.1)
        self.feat.setValue(float(self._params.get('featureScale') or 3.0))
        form.addRow('特征尺度', self.feat)
        if gray:
            self.gray_lv = QSpinBox()
            self.gray_lv.setRange(2, 256)
            self.gray_lv.setValue(int(self._params.get('grayLevel') or 8))
            form.addRow('灰度级数', self.gray_lv)
        else:
            self.gray_lv = None
        preview = QLabel('▢▢▢▢  画笔预览（示意）')
        preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview.setStyleSheet(
            'background:#1a1a1a;color:#9ad;border:1px dashed #456;padding:24px;font-size:18px;'
        )
        root.addLayout(form)
        root.addWidget(preview, 1)
        self._brush_slider = QSlider(Qt.Orientation.Horizontal)
        self._brush_slider.setRange(1, 64)
        self._brush_slider.setValue(self.brush.value())
        self._brush_slider.valueChanged.connect(self.brush.setValue)
        self.brush.valueChanged.connect(self._brush_slider.setValue)

        def _upd_preview(v):
            n = max(1, min(16, int(v) // 4))
            preview.setText(('●' * n) + f'  brush={int(v)}px')
        self.brush.valueChanged.connect(_upd_preview)
        _upd_preview(self.brush.value())
        root.addWidget(QLabel('画笔'))
        root.addWidget(self._brush_slider)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def result_params(self):
        out = {
            'contrastThreshold': int(self.contrast.value()),
            'brushSize': int(self.brush.value()),
            'featureScale': float(self.feat.value()),
            'hasTemplate': True,
            'templateReady': True,
        }
        if self.gray_lv is not None:
            out['grayLevel'] = int(self.gray_lv.value())
        return out


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
            # Keep templateReady in sync with path / flag
            if key in ('templatePath', 'hasTemplate'):
                self.params['templateReady'] = bool(
                    self.params.get('hasTemplate') or str(self.params.get('templatePath') or '').strip()
                )
                self.params['hasTemplate'] = self.params['templateReady']
            if key == 'maxOverlap':
                self.params['overlapThreshold'] = float(value)
            if key in ('scaleStart', 'scaleEnd', 'scaleStep', 'scaleEnable'):
                if self.params.get('scaleEnable', True):
                    _rebuild_scales(self.params)
                else:
                    self.params['scales'] = [1.0]
            if key in ('angleStart', 'angleEnd', 'angleStep') and not self.params.get('angleEnable', True):
                self.params['angleStart'] = 0.0
                self.params['angleEnd'] = 0.0
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

        uref_row = QHBoxLayout()
        self._upstream_ref = QLineEdit(str(self.params.get('upstreamRef') or ''))
        self._upstream_ref.setPlaceholderText('results.<模块>.字段 — 点击挑选')
        self._upstream_ref.editingFinished.connect(
            lambda: self._set_param('upstreamRef', self._upstream_ref.text().strip())
        )
        uref_btn = QPushButton('插入上游字段')
        uref_btn.setToolTip('从最近运行结果挑选上游模块字段')
        uref_btn.clicked.connect(self._insert_upstream_field)
        uref_row.addWidget(self._upstream_ref, 1)
        uref_row.addWidget(uref_btn)
        form.addRow('上游参考', uref_row)

        tip = QLabel('先连图像源再选输入源；未配置完整时画布节点显示红叹号。可用「插入上游字段」订阅匹配结果。')
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
            '创建模板… 打开对比度/画笔子窗；结果显示可开关匹配框/分数/搜索区/全画布描摹。'
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
        create_btn = QPushButton('创建模板…')
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
            gray = (self.params.get('matchMode') == 'gray')
            dlg = TemplateEditorDialog(self.params, self, gray=gray)
            if dlg.exec() != QDialog.DialogCode.Accepted:
                return
            for k, v in dlg.result_params().items():
                self._set_param(k, v)
            if not str(self.params.get('templatePath') or '').strip():
                self._set_param('templatePath', '（编辑器创建）')
                path_edit.setText('（编辑器创建）')
            status.setText('模板状态：已就绪（已创建/载入）')
            status.setStyleSheet('font-weight:600;color:#2e7d32;')

        def _clear():
            path_edit.clear()
            self.params['templatePath'] = ''
            self.params['hasTemplate'] = False
            self.params['templateReady'] = False
            status.setText('模板状态：未配置')
            status.setStyleSheet('font-weight:600;color:#c62828;')
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
        mode = self.params.get('matchMode') or 'fast'

        # VM p07：全部搜索模式
        full = OrangeSwitch(bool(self.params.get('fullSearch', False)))
        full.toggled.connect(lambda c: self._set_param('fullSearch', bool(c)))
        form.addRow('全部搜索模式', full)

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

        pol = QComboBox()
        pol.addItem('考虑极性', 'consider')
        pol.addItem('忽略极性', 'ignore')
        pol.setCurrentIndex(max(0, pol.findData(self.params.get('matchPolarity') or 'consider')))
        pol.currentIndexChanged.connect(lambda _: self._set_param('matchPolarity', pol.currentData()))
        form.addRow('匹配极性', pol)

        ang_en = OrangeSwitch(bool(self.params.get('angleEnable', True)))
        ang_en.toggled.connect(lambda c: self._set_param('angleEnable', bool(c)))
        form.addRow('角度搜索使能', ang_en)

        a0 = QDoubleSpinBox(); a0.setRange(-180, 180); a0.setDecimals(2)
        a0.setValue(float(self.params.get('angleStart') or 0))
        a1 = QDoubleSpinBox(); a1.setRange(-180, 180); a1.setDecimals(2)
        a1.setValue(float(self.params.get('angleEnd') or 0))
        a_step = QDoubleSpinBox(); a_step.setRange(0.1, 180); a_step.setDecimals(2)
        a_step.setValue(float(self.params.get('angleStep') or 10))
        a0.valueChanged.connect(lambda v: self._set_param('angleStart', float(v)))
        a1.valueChanged.connect(lambda v: self._set_param('angleEnd', float(v)))
        a_step.valueChanged.connect(lambda v: self._set_param('angleStep', float(v)))
        form.addRow('起始角度', a0)
        form.addRow('终止角度', a1)
        form.addRow('角度步长', a_step)

        sc_en = OrangeSwitch(bool(self.params.get('scaleEnable', True)))
        sc_en.toggled.connect(lambda c: self._set_param('scaleEnable', bool(c)))
        form.addRow('尺度搜索使能', sc_en)

        s0 = QDoubleSpinBox(); s0.setRange(0.1, 5.0); s0.setDecimals(3); s0.setSingleStep(0.05)
        s0.setValue(float(self.params.get('scaleStart') or 1.0))
        s0.valueChanged.connect(lambda v: self._set_param('scaleStart', float(v)))
        form.addRow('起始缩放', s0)
        s1 = QDoubleSpinBox(); s1.setRange(0.1, 5.0); s1.setDecimals(3); s1.setSingleStep(0.05)
        s1.setValue(float(self.params.get('scaleEnd') or 1.0))
        s1.valueChanged.connect(lambda v: self._set_param('scaleEnd', float(v)))
        form.addRow('终止缩放', s1)
        ss = QDoubleSpinBox(); ss.setRange(0.01, 1.0); ss.setDecimals(3)
        ss.setValue(float(self.params.get('scaleStep') or 0.1))
        ss.valueChanged.connect(lambda v: self._set_param('scaleStep', float(v)))
        form.addRow('缩放步长', ss)

        ov = QDoubleSpinBox(); ov.setRange(0.01, 0.9); ov.setDecimals(2)
        ov.setValue(float(self.params.get('maxOverlap') or 0.5))
        ov.valueChanged.connect(lambda v: self._set_param('maxOverlap', float(v)))
        form.addRow('最大重叠', ov)

        sort = QComboBox()
        for k, lab in (('score', '按分数'), ('x', '按 X'), ('y', '按 Y')):
            sort.addItem(lab, k)
        sort.setCurrentIndex(max(0, sort.findData(self.params.get('sortBy') or 'score')))
        sort.currentIndexChanged.connect(lambda _: self._set_param('sortBy', sort.currentData()))
        form.addRow('排序方式', sort)

        pyr = QSpinBox(); pyr.setRange(1, 8); pyr.setValue(int(self.params.get('pyramidLevels') or 4))
        pyr.valueChanged.connect(lambda v: self._set_param('pyramidLevels', int(v)))
        form.addRow('金字塔级数', pyr)

        if mode == 'gray':
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
        else:
            ct = QSpinBox(); ct.setRange(0, 255); ct.setValue(int(self.params.get('contrast') or 20))
            ct.valueChanged.connect(lambda v: self._set_param('contrast', int(v)))
            form.addRow('对比度阈值', ct)
            fs = QDoubleSpinBox(); fs.setRange(0.5, 20); fs.setDecimals(1)
            fs.setValue(float(self.params.get('featureScale') or 3.0))
            fs.valueChanged.connect(lambda v: self._set_param('featureScale', float(v)))
            form.addRow('特征尺度', fs)
            tm = QComboBox()
            tm.addItem('自动', 'auto')
            tm.addItem('手动', 'manual')
            tm.setCurrentIndex(max(0, tm.findData(self.params.get('thresholdMode') or 'auto')))
            tm.currentIndexChanged.connect(lambda _: self._set_param('thresholdMode', tm.currentData()))
            form.addRow('阈值模式', tm)

        sub = OrangeSwitch(bool(self.params.get('subPixel', True)))
        sub.toggled.connect(lambda c: self._set_param('subPixel', bool(c)))
        form.addRow('亚像素', sub)

        timeout = QSpinBox(); timeout.setRange(0, 60000)
        timeout.setValue(int(self.params.get('timeoutMs') or 3000))
        timeout.valueChanged.connect(lambda v: self._set_param('timeoutMs', int(v)))
        form.addRow('超时(ms)', timeout)

        tip = QLabel(
            '对齐 VM「运行参数」帧：全部搜索/分数/个数/极性/角度·尺度范围；'
            'scales 与 overlapThreshold 同步写入引擎可读字段。无假 Halcon 核。'
        )
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
        _sw('showCross', '显示十字准星', True)
        _sw('showSearchRegion', '显示搜索区', True)
        _sw('showFeaturePoints', '显示特征点', False)
        _sw('traceFullCanvas', '全画布描摹', False)
        _sw('resultJudgeEnable', '结果判断使能', False)
        jmin = QDoubleSpinBox(); jmin.setRange(0, 1); jmin.setDecimals(3)
        jmin.setValue(float(self.params.get('resultJudgeMin') or 0))
        jmin.valueChanged.connect(lambda v: self._set_param('resultJudgeMin', float(v)))
        form.addRow('判断分数下限', jmin)
        jmax = QDoubleSpinBox(); jmax.setRange(0, 1); jmax.setDecimals(3)
        jmax.setValue(float(self.params.get('resultJudgeMax') or 1))
        jmax.valueChanged.connect(lambda v: self._set_param('resultJudgeMax', float(v)))
        form.addRow('判断分数上限', jmax)
        lay.addLayout(form)
        lay.addStretch(1)
        return w
