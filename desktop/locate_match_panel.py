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
    QSlider, QListWidget, QListWidgetItem, QMessageBox, QInputDialog,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
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
    # 模板库：[{id,name,path,note}] — 工业 UX 选用/预览/增删（非 Halcon）
    if not isinstance(p.get('templateLibrary'), list):
        p['templateLibrary'] = []
    p.setdefault('activeTemplateId', '')
    p.setdefault('batchScoreThreshold', float(p.get('minScore') or 0.85))
    if not isinstance(p.get('lastBatchScoreboard'), dict):
        p['lastBatchScoreboard'] = {}
    if not isinstance(p.get('matchScoreTrend'), dict):
        p['matchScoreTrend'] = {'capacity': 32, 'points': []}
    p.setdefault('showMatchBox', True)
    p.setdefault('showScore', True)
    p.setdefault('showContour', True)
    p.setdefault('showOrigin', False)
    p.setdefault('showCross', True)
    p.setdefault('showSearchRegion', True)
    p.setdefault('showFeaturePoints', False)
    p.setdefault('showMatchIndex', True)
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
    # 结果显示 / 判断（引擎 template_matching 读取）
    p.setdefault('showMatchBox', True)
    p.setdefault('showScore', True)
    p.setdefault('showContour', True)
    p.setdefault('showOrigin', False)
    p.setdefault('showCross', True)
    p.setdefault('showSearchRegion', True)
    p.setdefault('showFeaturePoints', False)
    p.setdefault('showMatchIndex', True)
    p.setdefault('showAngleDeg', False)
    p.setdefault('traceFullCanvas', False)
    p.setdefault('resultJudgeEnable', False)
    p.setdefault('resultJudgeMin', 0.0)
    p.setdefault('resultJudgeMax', 1.0)
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
            if key == 'angleEnable' and not value:
                self.params['angleStart'] = 0.0
                self.params['angleEnd'] = 0.0
            self._emit()
            # live 结果显示摘要
            try:
                self._refresh_result_summary()
            except Exception:
                pass

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
        lay.setSpacing(8)

        tip = QLabel(
            'VisionMaster「灰度模板」：创建 / 载入 / 模板库选用。' if (self.params.get('matchMode') == 'gray')
            else 'VisionMaster「特征模板」：创建 / 载入 / 模板库选用；对比度阈值与画笔在模板配置子窗。'
            ' 模板库支持 加入 / 选用 / 预览 / 移除（本机文件，无 Halcon / 无云）。'
        )
        tip.setWordWrap(True)
        tip.setStyleSheet('color:#555;')
        lay.addWidget(tip)

        form = QFormLayout()
        path_edit = QLineEdit(str(self.params.get('templatePath') or ''))
        path_edit.setObjectName('locateTemplatePath')
        path_edit.setPlaceholderText('当前选用模板路径 / 方案内引用')
        path_edit.editingFinished.connect(lambda: self._set_param('templatePath', path_edit.text().strip()))
        form.addRow('当前模板', path_edit)
        self._tpl_path_edit = path_edit

        row = QHBoxLayout()
        load_btn = QPushButton('载入模板…')
        load_btn.setObjectName('locateTplLoadBtn')
        create_btn = QPushButton('创建模板…')
        create_btn.setObjectName('locateTplCreateBtn')
        clear_btn = QPushButton('清除当前')
        clear_btn.setObjectName('locateTplClearBtn')

        def _load():
            path, _ = QFileDialog.getOpenFileName(
                self, '载入特征模板', '', '模板/图像 (*.png *.bmp *.jpg *.jpeg *.tif *.json);;所有文件 (*)'
            )
            if path:
                path_edit.setText(path)
                self._set_param('templatePath', path)
                self._set_param('hasTemplate', True)
                self._set_param('templateReady', True)
                self._sync_tpl_status()

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
            self._set_param('hasTemplate', True)
            self._set_param('templateReady', True)
            self._sync_tpl_status()

        def _clear():
            path_edit.clear()
            self.params['templatePath'] = ''
            self.params['hasTemplate'] = False
            self.params['templateReady'] = False
            self.params['activeTemplateId'] = ''
            self._sync_tpl_status()
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

        # ---- 模板库（工业 UX：列表 + 加入/选用/预览/移除）----
        lib_frame = QFrame()
        lib_frame.setObjectName('locateTemplateLibraryFrame')
        lib_frame.setStyleSheet(
            'QFrame#locateTemplateLibraryFrame{border:1px solid #3a3f46;border-radius:4px;'
            'background:#1a1e24;}'
        )
        lib_lay = QVBoxLayout(lib_frame)
        lib_lay.setContentsMargins(8, 8, 8, 8)
        lib_lay.setSpacing(6)
        lib_head = QHBoxLayout()
        lib_title = QLabel('模板库')
        lib_title.setStyleSheet('font-weight:600;color:#c8d0d8;')
        lib_head.addWidget(lib_title)
        self._tpl_lib_count = QLabel('0')
        self._tpl_lib_count.setObjectName('locateTplLibCount')
        self._tpl_lib_count.setStyleSheet('color:#888;')
        lib_head.addWidget(self._tpl_lib_count)
        lib_head.addStretch(1)
        lib_lay.addLayout(lib_head)

        self._tpl_lib_list = QListWidget()
        self._tpl_lib_list.setObjectName('locateTemplateLibraryList')
        self._tpl_lib_list.setMinimumHeight(110)
        self._tpl_lib_list.setStyleSheet(
            'QListWidget{background:#12151a;color:#c8d0d8;font-size:12px;}'
            'QListWidget::item:selected{background:#2a4a3a;}'
        )
        self._tpl_lib_list.setToolTip('双击选用 · 选中后可预览/移除')
        self._tpl_lib_list.itemDoubleClicked.connect(lambda *_: self._tpl_lib_select())
        self._tpl_lib_list.currentItemChanged.connect(lambda *_: self._tpl_lib_preview())
        lib_lay.addWidget(self._tpl_lib_list)

        self._tpl_lib_preview_lab = QLabel('预览：选中库条目查看路径/备注')
        self._tpl_lib_preview_lab.setObjectName('locateTplLibPreview')
        self._tpl_lib_preview_lab.setWordWrap(True)
        self._tpl_lib_preview_lab.setStyleSheet('color:#8ab;font-size:11px;padding:2px 0;')
        lib_lay.addWidget(self._tpl_lib_preview_lab)

        lib_btns = QHBoxLayout()
        add_btn = QPushButton('加入库')
        add_btn.setObjectName('locateTplLibAddBtn')
        add_btn.setToolTip('将当前模板路径加入模板库（可改名）')
        add_btn.clicked.connect(self._tpl_lib_add)
        sel_btn = QPushButton('选用')
        sel_btn.setObjectName('locateTplLibSelectBtn')
        sel_btn.setToolTip('将选中库条目设为当前模板')
        sel_btn.clicked.connect(self._tpl_lib_select)
        prev_btn = QPushButton('预览')
        prev_btn.setObjectName('locateTplLibPreviewBtn')
        prev_btn.clicked.connect(lambda *_: self._tpl_lib_preview())
        rm_btn = QPushButton('移除')
        rm_btn.setObjectName('locateTplLibRemoveBtn')
        rm_btn.setToolTip('从模板库移除（不删磁盘文件）')
        rm_btn.clicked.connect(self._tpl_lib_remove)
        for b in (add_btn, sel_btn, prev_btn, rm_btn):
            lib_btns.addWidget(b)
        lib_btns.addStretch(1)
        lib_lay.addLayout(lib_btns)

        # ---- 多模板批量记分板（工业：阈值 / 最优选用）----
        sb_head = QHBoxLayout()
        sb_title = QLabel('批量记分板')
        sb_title.setStyleSheet('font-weight:600;color:#c8d0d8;font-size:12px;')
        sb_head.addWidget(sb_title)
        self._tpl_sb_summary = QLabel('未评分')
        self._tpl_sb_summary.setObjectName('locateBatchScoreSummary')
        self._tpl_sb_summary.setStyleSheet('color:#8ab;font-size:11px;')
        sb_head.addWidget(self._tpl_sb_summary, 1)
        lib_lay.addLayout(sb_head)

        thr_row = QHBoxLayout()
        thr_row.addWidget(QLabel('阈值'))
        self._tpl_sb_thr = QDoubleSpinBox()
        self._tpl_sb_thr.setObjectName('locateBatchScoreThr')
        self._tpl_sb_thr.setRange(0.0, 1.0)
        self._tpl_sb_thr.setDecimals(3)
        self._tpl_sb_thr.setSingleStep(0.01)
        self._tpl_sb_thr.setValue(float(self.params.get('batchScoreThreshold')
                                       or self.params.get('minScore') or 0.85))
        self._tpl_sb_thr.valueChanged.connect(
            lambda v: self._set_param('batchScoreThreshold', float(v))
        )
        thr_row.addWidget(self._tpl_sb_thr)
        score_btn = QPushButton('批量评分')
        score_btn.setObjectName('locateBatchScoreBtn')
        score_btn.setToolTip('对模板库全员打分（软估或注入分）；无 Halcon / 无相机')
        score_btn.clicked.connect(self._tpl_batch_score)
        thr_row.addWidget(score_btn)
        best_btn = QPushButton('选用最优')
        best_btn.setObjectName('locateBatchBestBtn')
        best_btn.setToolTip('按记分板选用最高分且过阈值的模板')
        best_btn.clicked.connect(self._tpl_select_best)
        thr_row.addWidget(best_btn)
        thr_row.addStretch(1)
        lib_lay.addLayout(thr_row)

        self._tpl_sb_table = QTableWidget(0, 4)
        self._tpl_sb_table.setObjectName('locateBatchScoreTable')
        self._tpl_sb_table.setHorizontalHeaderLabels(['模板', '分数', '判定', '序'])
        self._tpl_sb_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._tpl_sb_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._tpl_sb_table.setMaximumHeight(130)
        self._tpl_sb_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._tpl_sb_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self._tpl_sb_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._tpl_sb_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self._tpl_sb_table.setStyleSheet(
            'QTableWidget{background:#12151a;color:#c8d0d8;font-size:11px;}'
        )
        self._tpl_sb_table.itemDoubleClicked.connect(lambda *_: self._tpl_lib_select())
        lib_lay.addWidget(self._tpl_sb_table)

        self._tpl_trend_lab = QLabel('趋势：暂无分数')
        self._tpl_trend_lab.setObjectName('locateMatchScoreTrend')
        self._tpl_trend_lab.setWordWrap(True)
        self._tpl_trend_lab.setStyleSheet(
            'QLabel#locateMatchScoreTrend{color:#9ad;font-size:11px;font-family:monospace;'
            'padding:5px 8px;background:#12161c;border:1px solid #2a3a4a;border-radius:3px;}'
        )
        self._tpl_trend_lab.setToolTip(
            '匹配分趋势火花线（相对缩放 · Δ · OK率）· 运行/试批写入 · 无硬件'
        )
        trend_row = QHBoxLayout()
        trend_row.setSpacing(6)
        try:
            from desktop.locate_scoreboard import MatchScoreSparkWidget
            self._tpl_trend_spark = MatchScoreSparkWidget(None, width=128, height=28)
            if hasattr(self._tpl_trend_spark, 'setObjectName'):
                pass  # already named inside
            self._spark_jump_lab = QLabel('')
            self._spark_jump_lab.setObjectName('locateMatchSparkJumpLab')
            self._spark_jump_lab.setStyleSheet('color:#9ad;font-size:11px;')
            self._spark_jump_lab.setVisible(False)
            if hasattr(self._tpl_trend_spark, 'set_jump_handler'):
                self._tpl_trend_spark.set_jump_handler(self._on_spark_frame_jump)
            try:
                if hasattr(self._tpl_trend_spark, 'frameJumpRequested'):
                    self._tpl_trend_spark.frameJumpRequested.connect(self._on_spark_frame_jump)
            except Exception:
                pass
            trend_row.addWidget(self._tpl_trend_spark, 0)
            trend_row.addWidget(self._spark_jump_lab, 0)
        except Exception:
            self._tpl_trend_spark = None
            self._spark_jump_lab = None
        trend_row.addWidget(self._tpl_trend_lab, 1)
        lib_lay.addLayout(trend_row)
        self._restore_score_trend_label()
        self._refresh_batch_scoreboard_table()

        lay.addWidget(lib_frame)

        ready = bool(self.params.get('hasTemplate') or str(self.params.get('templatePath') or '').strip())
        status = QLabel('模板状态：已就绪（已创建/载入）' if ready else '模板状态：未配置')
        status.setObjectName('locateTemplateStatus')
        status.setStyleSheet('font-weight:600;color:#c62828;' if not ready else 'font-weight:600;color:#2e7d32;')
        lay.addWidget(status)
        self._tpl_status = status
        self._refresh_tpl_library_list()
        lay.addStretch(1)
        return w

    def _tpl_library(self) -> list:
        lib = self.params.get('templateLibrary')
        if not isinstance(lib, list):
            lib = []
            self.params['templateLibrary'] = lib
        return lib

    def _refresh_tpl_library_list(self):
        lw = getattr(self, '_tpl_lib_list', None)
        if lw is None:
            return
        lib = self._tpl_library()
        active = str(self.params.get('activeTemplateId') or '')
        cur_path = str(self.params.get('templatePath') or '').strip()
        lw.blockSignals(True)
        lw.clear()
        restore_row = -1
        for i, entry in enumerate(lib):
            if not isinstance(entry, dict):
                continue
            name = str(entry.get('name') or entry.get('id') or f'模板{i+1}')
            path = str(entry.get('path') or '')
            eid = str(entry.get('id') or '')
            mark = ''
            if eid and eid == active:
                mark = ' ★'
                restore_row = lw.count()
            elif path and path == cur_path:
                mark = ' ●'
                if restore_row < 0:
                    restore_row = lw.count()
            item = QListWidgetItem(f'{name}{mark}')
            item.setData(Qt.ItemDataRole.UserRole, entry)
            tip = path or '(无路径)'
            if entry.get('note'):
                tip += f"\n{entry.get('note')}"
            item.setToolTip(tip)
            lw.addItem(item)
        if restore_row >= 0:
            lw.setCurrentRow(restore_row)
        lw.blockSignals(False)
        cnt = getattr(self, '_tpl_lib_count', None)
        if cnt is not None:
            cnt.setText(f'{lw.count()} 项')
        try:
            self._refresh_batch_scoreboard_table()
        except Exception:
            pass

    def _sync_tpl_status(self):
        status = getattr(self, '_tpl_status', None)
        path_edit = getattr(self, '_tpl_path_edit', None)
        ready = bool(self.params.get('hasTemplate') or str(self.params.get('templatePath') or '').strip())
        if path_edit is not None:
            path_edit.setText(str(self.params.get('templatePath') or ''))
        if status is not None:
            status.setText('模板状态：已就绪（已创建/载入）' if ready else '模板状态：未配置')
            status.setStyleSheet(
                'font-weight:600;color:#2e7d32;' if ready else 'font-weight:600;color:#c62828;'
            )
        self._refresh_tpl_library_list()

    def _tpl_lib_add(self):
        path = str(self.params.get('templatePath') or '').strip()
        if not path:
            # allow browse-to-add
            path, _ = QFileDialog.getOpenFileName(
                self, '加入模板库', '', '模板/图像 (*.png *.bmp *.jpg *.jpeg *.tif *.json);;所有文件 (*)'
            )
            if not path:
                return
        from pathlib import Path as _P
        default_name = _P(path).stem or '模板'
        name, ok = QInputDialog.getText(self, '加入模板库', '模板名称：', text=default_name)
        if not ok:
            return
        name = (name or default_name).strip() or default_name
        import uuid
        entry = {
            'id': uuid.uuid4().hex[:12],
            'name': name,
            'path': path,
            'note': '',
        }
        lib = self._tpl_library()
        # replace same path
        lib[:] = [e for e in lib if not (isinstance(e, dict) and e.get('path') == path)]
        lib.append(entry)
        self._set_param('templateLibrary', list(lib))
        # if no current template, also select it
        if not str(self.params.get('templatePath') or '').strip():
            self._set_param('templatePath', path)
            self._set_param('hasTemplate', True)
            self._set_param('templateReady', True)
            self._set_param('activeTemplateId', entry['id'])
        self._sync_tpl_status()

    def _tpl_lib_selected_entry(self):
        lw = getattr(self, '_tpl_lib_list', None)
        if lw is None:
            return None
        it = lw.currentItem()
        if it is None:
            return None
        data = it.data(Qt.ItemDataRole.UserRole)
        return data if isinstance(data, dict) else None

    def _tpl_lib_select(self):
        entry = self._tpl_lib_selected_entry()
        if not entry:
            QMessageBox.information(self, '模板库', '请先选中一条模板')
            return
        path = str(entry.get('path') or '').strip()
        if not path:
            QMessageBox.warning(self, '模板库', '该条目无路径')
            return
        self._set_param('templatePath', path)
        self._set_param('hasTemplate', True)
        self._set_param('templateReady', True)
        self._set_param('activeTemplateId', str(entry.get('id') or ''))
        self._sync_tpl_status()
        prev = getattr(self, '_tpl_lib_preview_lab', None)
        if prev is not None:
            prev.setText(f"已选用「{entry.get('name')}」→ {path}")
            prev.setStyleSheet('color:#2e7d32;font-size:11px;font-weight:600;')

    def _tpl_lib_preview(self, *_):
        entry = self._tpl_lib_selected_entry()
        if not entry:
            # fall back to activeTemplateId after refresh
            aid = str(self.params.get('activeTemplateId') or '')
            if aid:
                for e in self._tpl_library():
                    if isinstance(e, dict) and str(e.get('id') or '') == aid:
                        entry = e
                        break
        prev = getattr(self, '_tpl_lib_preview_lab', None)
        if prev is None:
            return
        if not entry:
            prev.setText('预览：选中库条目查看路径/备注')
            prev.setStyleSheet('color:#8ab;font-size:11px;padding:2px 0;')
            return
        name = entry.get('name') or '—'
        path = entry.get('path') or '(无路径)'
        note = entry.get('note') or ''
        active = str(entry.get('id') or '') == str(self.params.get('activeTemplateId') or '')
        mark = ' · 当前选用' if active else ''
        txt = f'预览「{name}」{mark}\n路径：{path}'
        if note:
            txt += f'\n备注：{note}'
        # soft existence hint (no Halcon)
        try:
            from pathlib import Path as _P
            exists = _P(path).is_file() if path and not path.startswith('（') else None
            if exists is True:
                txt += '\n磁盘：存在'
            elif exists is False:
                txt += '\n磁盘：未找到（仍可引用方案内路径）'
        except Exception:
            pass
        prev.setText(txt)
        prev.setStyleSheet('color:#9ad;font-size:11px;padding:2px 0;')

    def _tpl_lib_remove(self):
        entry = self._tpl_lib_selected_entry()
        if not entry:
            QMessageBox.information(self, '模板库', '请先选中要移除的条目')
            return
        ans = QMessageBox.question(
            self, '移除模板',
            f"从模板库移除「{entry.get('name')}」？\n（不删除磁盘文件）",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if ans != QMessageBox.StandardButton.Yes:
            return
        eid = str(entry.get('id') or '')
        lib = self._tpl_library()
        lib[:] = [e for e in lib if not (isinstance(e, dict) and str(e.get('id') or '') == eid)]
        if str(self.params.get('activeTemplateId') or '') == eid:
            self.params['activeTemplateId'] = ''
        self._set_param('templateLibrary', list(lib))
        self._sync_tpl_status()
        prev = getattr(self, '_tpl_lib_preview_lab', None)
        if prev is not None:
            prev.setText('预览：选中库条目查看路径/备注')
            prev.setStyleSheet('color:#8ab;font-size:11px;padding:2px 0;')


    def _batch_threshold(self) -> float:
        thr_w = getattr(self, '_tpl_sb_thr', None)
        if thr_w is not None:
            return float(thr_w.value())
        return float(self.params.get('batchScoreThreshold')
                     or self.params.get('minScore') or 0.85)

    def _refresh_batch_scoreboard_table(self, board=None):
        from desktop.locate_scoreboard import build_batch_scoreboard
        table = getattr(self, '_tpl_sb_table', None)
        if table is None:
            return
        if board is None:
            board = self.params.get('lastBatchScoreboard')
            if not isinstance(board, dict) or not board.get('rows'):
                board = build_batch_scoreboard(
                    self._tpl_library(),
                    {},
                    threshold=self._batch_threshold(),
                    active_id=str(self.params.get('activeTemplateId') or ''),
                )
        rows = board.get('rows') or []
        table.setRowCount(0)
        for r in rows:
            i = table.rowCount()
            table.insertRow(i)
            name = str(r.get('name') or r.get('id') or '')
            if r.get('active'):
                name += ' ★'
            sc = r.get('score')
            sc_txt = '—' if sc is None else f'{float(sc):.3f}'
            if r.get('pending'):
                judge = '待评'
            else:
                judge = 'OK' if r.get('ok') else 'NG'
            rank = r.get('rank') or ''
            for c, text in enumerate((name, sc_txt, judge, str(rank) if rank else '—')):
                it = QTableWidgetItem(text)
                it.setData(Qt.ItemDataRole.UserRole, r)
                if judge == 'OK':
                    it.setForeground(Qt.GlobalColor.green)
                elif judge == 'NG':
                    it.setForeground(Qt.GlobalColor.red)
                table.setItem(i, c, it)
        lab = getattr(self, '_tpl_sb_summary', None)
        if lab is not None:
            lab.setText(str(board.get('summary') or '未评分'))

    def _resolve_live_engine_scores(self, last_result=None) -> dict:
        """Pull soft-engine match scores when available (no Halcon / no camera)."""
        from desktop.locate_scoreboard import ingest_engine_scores, scores_for_library
        lr = last_result
        if lr is None:
            try:
                from desktop.upstream_field_picker import host_last_result
                lr = host_last_result(self)
            except Exception:
                lr = None
        if lr is None:
            lr = getattr(self, '_last_result', None)
        bag = ingest_engine_scores(lr, step_id=str(self.step.get('id') or ''))
        return scores_for_library(bag, self._tpl_library()), bag

    def ingest_live_match_scores(self, last_result=None, *, soft_fallback: bool = True,
                                 seed: str = '') -> dict:
        """Wire live engine scores into the batch scoreboard; soft estimates fill gaps."""
        live, bag = self._resolve_live_engine_scores(last_result)
        src = 'engine' if live else 'soft'
        board = self.run_batch_scoreboard(
            live or None, soft=bool(soft_fallback), seed=seed, source=src,
        )
        if bag.get('__best__') is not None:
            self.push_match_score(
                bag['__best__'],
                label='engine',
                ok=True,
                template_id=str(
                    next((k for k in bag if not str(k).startswith('_') and not str(k).startswith('step:')), '')
                    or board.get('bestId') or ''
                ),
            )
        return board

    def run_batch_scoreboard(self, scores_by_id=None, *, soft: bool = True,
                             seed: str = '', source: str = '') -> dict:
        """Score all templates; prefer injected/engine scores, soft fills missing."""
        from desktop.locate_scoreboard import (
            build_batch_scoreboard, soft_estimate_scores,
        )
        lib = self._tpl_library()
        scores = dict(scores_by_id or {})
        used_source = source or ('inject' if scores else '')
        if not scores:
            # auto-ingest live engine when caller did not supply a map
            try:
                live, _bag = self._resolve_live_engine_scores()
                if live:
                    scores.update(live)
                    used_source = used_source or 'engine'
            except Exception:
                pass
        if soft:
            est = soft_estimate_scores(lib, seed=seed or str(self.params.get('templatePath') or ''))
            for k, v in est.items():
                scores.setdefault(k, v)
            if not used_source:
                used_source = 'soft'
            elif used_source == 'engine' and any(
                k in est and scores.get(k) == est.get(k) for k in est
            ):
                used_source = 'engine+soft'
        board = build_batch_scoreboard(
            lib, scores,
            threshold=self._batch_threshold(),
            active_id=str(self.params.get('activeTemplateId') or ''),
        )
        board['source'] = used_source or 'soft'
        # annotate summary with source
        if used_source and used_source != 'soft':
            board['summary'] = f"{board.get('summary')} · 源:{used_source}"
        self._set_param('lastBatchScoreboard', board)
        self._set_param('batchScoreThreshold', self._batch_threshold())
        self._refresh_batch_scoreboard_table(board)
        # push best into trend
        if board.get('bestScore') is not None:
            self.push_match_score(
                board['bestScore'],
                label=used_source or 'batch',
                ok=bool(board.get('passCount')),
                template_id=str(board.get('bestId') or ''),
            )
        return board

    def _tpl_batch_score(self):
        board = self.ingest_live_match_scores(soft_fallback=True)
        prev = getattr(self, '_tpl_lib_preview_lab', None)
        if prev is not None:
            src = board.get('source') or 'soft'
            prev.setText(f"记分板[{src}]：{board.get('summary')}")
            prev.setStyleSheet('color:#9ad;font-size:11px;padding:2px 0;')

    def _tpl_select_best(self):
        from desktop.locate_scoreboard import select_best_template, build_batch_scoreboard
        board = self.params.get('lastBatchScoreboard')
        if not isinstance(board, dict) or not board.get('rows'):
            board = self.run_batch_scoreboard(soft=True)
        best = select_best_template(board)
        if not best:
            QMessageBox.information(self, '记分板', '没有可选用的评分结果')
            return
        thr = self._batch_threshold()
        if best.get('score') is not None and float(best['score']) < thr:
            ans = QMessageBox.question(
                self, '选用最优',
                f"最优「{best.get('name')}」={best.get('score'):.3f} 低于阈值 {thr:.3f}，仍选用？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if ans != QMessageBox.StandardButton.Yes:
                return
        # select into library list then apply
        lw = getattr(self, '_tpl_lib_list', None)
        if lw is not None:
            for i in range(lw.count()):
                it = lw.item(i)
                data = it.data(Qt.ItemDataRole.UserRole) if it else None
                if isinstance(data, dict) and str(data.get('id') or '') == str(best.get('id') or ''):
                    lw.setCurrentRow(i)
                    break
        path = str(best.get('path') or '').strip()
        if not path:
            QMessageBox.warning(self, '记分板', '最优条目无路径')
            return
        self._set_param('templatePath', path)
        self._set_param('hasTemplate', True)
        self._set_param('templateReady', True)
        self._set_param('activeTemplateId', str(best.get('id') or ''))
        self._sync_tpl_status()
        self._refresh_batch_scoreboard_table(
            build_batch_scoreboard(
                self._tpl_library(),
                {r['id']: r.get('score') for r in (board.get('rows') or []) if r.get('id')},
                threshold=thr,
                active_id=str(best.get('id') or ''),
            )
        )
        prev = getattr(self, '_tpl_lib_preview_lab', None)
        if prev is not None:
            prev.setText(
                f"已选用最优「{best.get('name')}」={float(best.get('score') or 0):.3f} → {path}"
            )
            prev.setStyleSheet('color:#2e7d32;font-size:11px;font-weight:600;')


    def set_filmstrip_seek_handler(self, fn):
        """Optional explicit seek callback (tests / host inject). Soft."""
        self._filmstrip_seek_handler = fn

    def set_compare_strip_sync_handler(self, fn):
        """Optional spark→compare-strip sync callback (tests / host inject). Soft."""
        self._compare_strip_sync_handler = fn

    def _resolve_filmstrip(self):
        """Find host FilmstripBar: explicit handler host → window().filmstrip."""
        fn = getattr(self, '_filmstrip_seek_handler', None)
        if callable(fn):
            return ('handler', fn)
        try:
            w = self.window() if hasattr(self, 'window') else None
        except Exception:
            w = None
        fs = getattr(w, 'filmstrip', None) if w is not None else None
        if fs is not None:
            return ('filmstrip', fs)
        # property_float host may stash mainwindow
        host = getattr(w, 'host', None) if w is not None else None
        fs = getattr(host, 'filmstrip', None) if host is not None else None
        if fs is not None:
            return ('filmstrip', fs)
        return ('none', None)

    def _resolve_compare_strip(self):
        """Find host CompareThumbStrip: explicit handler → window().compare_strip."""
        fn = getattr(self, '_compare_strip_sync_handler', None)
        if callable(fn):
            return ('handler', fn)
        try:
            w = self.window() if hasattr(self, 'window') else None
        except Exception:
            w = None
        cs = getattr(w, 'compare_strip', None) if w is not None else None
        if cs is not None:
            return ('compare', cs)
        host = getattr(w, 'host', None) if w is not None else None
        cs = getattr(host, 'compare_strip', None) if host is not None else None
        if cs is not None:
            return ('compare', cs)
        return ('none', None)

    def _on_spark_frame_jump(self, bag=None):
        """Spark click → jump hint + filmstrip seek wire (soft / no hardware)."""
        bag = bag if isinstance(bag, dict) else {}
        frame = str(bag.get('frame') or '')
        label = str(bag.get('label') or '')
        idx = bag.get('index')
        score = bag.get('score')
        ok = bag.get('ok')
        tip_bits = []
        if frame:
            tip_bits.append(f'帧 {frame}')
        if label:
            tip_bits.append(label)
        if idx is not None:
            tip_bits.append(f'#{int(idx) + 1}')
        if score is not None:
            try:
                tip_bits.append(f'{float(score):.3f}')
            except Exception:
                pass
        if ok is False:
            tip_bits.append('✗')
        elif ok is True:
            tip_bits.append('✓')
        text = '跳帧 · ' + ' · '.join(tip_bits) if tip_bits else '跳帧'
        seek_info = {'ok': False, 'reason': 'pending'}
        kind, target = self._resolve_filmstrip()
        try:
            if kind == 'handler':
                seek_info = target(bag) or {'ok': False, 'reason': 'handler empty'}
            elif kind == 'filmstrip':
                from desktop.locate_scoreboard import seek_filmstrip_from_spark_jump
                seek_info = seek_filmstrip_from_spark_jump(target, bag)
            else:
                seek_info = {'ok': False, 'reason': 'no filmstrip'}
        except Exception as err:
            seek_info = {'ok': False, 'reason': str(err)}
        if seek_info.get('ok'):
            tip_bits.append(
                f"胶片#{int(seek_info.get('index', -1)) + 1}"
                if seek_info.get('index', -1) >= 0 else '胶片✓'
            )
            text = '跳帧 · ' + ' · '.join(tip_bits) if tip_bits else '跳帧'
        lab = getattr(self, '_spark_jump_lab', None)
        if lab is not None:
            lab.setText(text)
            lab.setVisible(True)
            how = seek_info.get('matchedBy') or seek_info.get('reason') or '—'
            lab.setToolTip(
                f"火花线点击跳帧 · frame={frame or '—'} · label={label or '—'} · "
                f"seek={how} · 无硬件"
            )
        trend_lab = getattr(self, '_tpl_trend_lab', None)
        if trend_lab is not None and tip_bits:
            try:
                trend_lab.setToolTip(
                    (trend_lab.toolTip() or '') + f'\n跳帧 → {text}'
                )
            except Exception:
                pass
        # spark → compare-strip sync (activate if path already on strip)
        sync_info = {'ok': False, 'reason': 'pending'}
        try:
            sync_bag = dict(bag)
            if seek_info.get('path'):
                sync_bag['path'] = seek_info.get('path')
            sk, st = self._resolve_compare_strip()
            if sk == 'handler':
                sync_info = st(sync_bag) or {'ok': False, 'reason': 'handler empty'}
            elif sk == 'compare':
                from desktop.locate_scoreboard import sync_compare_strip_from_spark_jump
                sync_info = sync_compare_strip_from_spark_jump(st, sync_bag)
            else:
                sync_info = {'ok': False, 'reason': 'no compare strip'}
        except Exception as err:
            sync_info = {'ok': False, 'reason': str(err)}
        if sync_info.get('ok') and lab is not None:
            try:
                lab.setText((lab.text() or text) + ' · 对比✓')
            except Exception:
                pass

        self._last_spark_jump = dict(bag)
        self._last_spark_seek = dict(seek_info) if isinstance(seek_info, dict) else {}
        self._last_spark_compare_sync = dict(sync_info) if isinstance(sync_info, dict) else {}
        bag = dict(bag)
        bag['seek'] = dict(self._last_spark_seek)
        bag['compareSync'] = dict(self._last_spark_compare_sync)
        return bag

    def _score_trend(self):
        from desktop.locate_scoreboard import MatchScoreTrend
        t = getattr(self, '_match_score_trend', None)
        if t is None:
            t = MatchScoreTrend(32)
            bag = self.params.get('matchScoreTrend')
            if isinstance(bag, dict):
                t.load_dict(bag)
            self._match_score_trend = t
        return t

    def _restore_score_trend_label(self):
        lab = getattr(self, '_tpl_trend_lab', None)
        if lab is None:
            return
        trend = self._score_trend()
        lab.setText(trend.summary(industrial=True) if hasattr(trend, 'summary') else '趋势：暂无分数')
        try:
            if hasattr(trend, 'summary_rich'):
                lab.setToolTip(trend.summary_rich())
        except Exception:
            pass
        spark = getattr(self, '_tpl_trend_spark', None)
        if spark is not None and hasattr(spark, 'set_from_trend'):
            try:
                spark.set_from_trend(trend)
            except Exception:
                pass

    def set_last_result(self, result):
        """Cache engine last_result for scoreboard ingest (soft OK)."""
        self._last_result = result

    def push_match_score(self, score, *, label: str = '', ok=None,
                         template_id: str = '', frame: str = '') -> str:
        """Append a match score into the trend strip (runs/frames, no hardware)."""
        trend = self._score_trend()
        trend.push(score, label=label, ok=ok, template_id=template_id, frame=frame)
        self._set_param('matchScoreTrend', trend.to_dict())
        lab = getattr(self, '_tpl_trend_lab', None)
        summary = trend.summary(industrial=True)
        if lab is not None:
            lab.setText(summary)
            try:
                rich = trend.summary_rich() if hasattr(trend, 'summary_rich') else summary
                lab.setToolTip(rich)
            except Exception:
                pass
            # soft color cue on last delta
            try:
                dlt = trend.delta() if hasattr(trend, 'delta') else None
                if dlt is not None and dlt > 1e-6:
                    lab.setStyleSheet(
                        'QLabel#locateMatchScoreTrend{color:#8d8;font-size:11px;font-family:monospace;'
                        'padding:5px 8px;background:#12161c;border:1px solid #2a4a3a;border-radius:3px;}'
                    )
                elif dlt is not None and dlt < -1e-6:
                    lab.setStyleSheet(
                        'QLabel#locateMatchScoreTrend{color:#d98;font-size:11px;font-family:monospace;'
                        'padding:5px 8px;background:#1a1412;border:1px solid #4a3a2a;border-radius:3px;}'
                    )
                else:
                    lab.setStyleSheet(
                        'QLabel#locateMatchScoreTrend{color:#9ad;font-size:11px;font-family:monospace;'
                        'padding:5px 8px;background:#12161c;border:1px solid #2a3a4a;border-radius:3px;}'
                    )
            except Exception:
                pass
        spark = getattr(self, '_tpl_trend_spark', None)
        if spark is not None and hasattr(spark, 'set_from_trend'):
            try:
                spark.set_from_trend(trend)
            except Exception:
                pass
        return summary

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

        tip = QLabel('对应 VM「结果显示」：匹配框 / 分数 / 轮廓 / 原点等叠加开关 + 多匹配明细表。')
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
        _sw('showMatchIndex', '显示匹配序号', True)
        _sw('showAngleDeg', '显示角度标注', False)
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
        self._result_summary = QLabel('')
        self._result_summary.setObjectName('locateResultSummary')
        self._result_summary.setWordWrap(True)
        self._result_summary.setStyleSheet(
            'color:#9ad;font-size:11px;padding:6px 8px;background:#1e2228;border-radius:4px;'
        )
        form.addRow('结果回显', self._result_summary)

        # wave140: dense multi-match table (scores/overlays) — not scoreboard micro-prop cascade
        self._match_density_lab = QLabel('多匹配：尚未运行')
        self._match_density_lab.setObjectName('locateMatchDensitySummary')
        self._match_density_lab.setWordWrap(True)
        self._match_density_lab.setStyleSheet(
            'color:#9ad;font-size:11px;padding:6px 8px;background:#182028;border-radius:4px;'
        )
        form.addRow('匹配密度', self._match_density_lab)

        self._match_density_table = QTableWidget(0, 7)
        self._match_density_table.setObjectName('locateMatchDensityTable')
        self._match_density_table.setHorizontalHeaderLabels(
            ['#', '分数', 'X', 'Y', '角度°', '缩放', '判定']
        )
        self._match_density_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._match_density_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._match_density_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._match_density_table.setMaximumHeight(180)
        form.addRow('匹配明细', self._match_density_table)

        brow = QHBoxLayout()
        b_live = QPushButton('刷新匹配明细')
        b_live.setObjectName('locateMatchDensityRefreshBtn')
        b_live.clicked.connect(self.refresh_match_density)
        b_demo = QPushButton('软演示多匹配')
        b_demo.setObjectName('locateMatchSoftDemoBtn')
        b_demo.setToolTip('填入确定性软多匹配行（无硬件 / 无火花线联级）')
        b_demo.clicked.connect(self._soft_demo_match_density)
        brow.addWidget(b_live)
        brow.addWidget(b_demo)
        brow.addStretch(1)
        form.addRow(brow)

        tip = QLabel(
            '匹配框/分数/序号/角度/全画布描摹/结果判断已接入 OpenCV 引擎实绘（无 Halcon 核）。'
            '多匹配表明细独立于模板库记分板；不做火花线/blink 微属性联级。'
        )
        tip.setWordWrap(True)
        tip.setStyleSheet('color:#888;')
        form.addRow(tip)
        lay.addLayout(form)
        lay.addStretch(1)
        self._refresh_result_summary()
        try:
            self.refresh_match_density()
        except Exception:
            pass
        return w

    def _refresh_result_summary(self):
        lab = getattr(self, '_result_summary', None)
        if lab is None:
            return
        p = self.params
        flags = []
        for k, labn in (
            ('showMatchBox', '框'), ('showScore', '分'), ('showContour', '轮廓'),
            ('showCross', '十字'), ('showMatchIndex', '序号'), ('showAngleDeg', '角'),
            ('showSearchRegion', '搜索区'), ('traceFullCanvas', '全画布'),
            ('showOrigin', '原点'), ('showFeaturePoints', '特征点'),
        ):
            if p.get(k, k in ('showMatchBox', 'showScore', 'showContour', 'showCross',
                               'showMatchIndex', 'showSearchRegion')):
                flags.append(labn)
        ang = '角度开' if p.get('angleEnable', True) else '角度关→单角'
        judge = (
            f'判断[{float(p.get("resultJudgeMin") or 0):.3f},{float(p.get("resultJudgeMax") or 1):.3f}]'
            if p.get('resultJudgeEnable') else '判断关'
        )
        lab.setText(
            f'叠层：{" · ".join(flags) or "（无）"} · {ang} · {judge} · '
            f'maxMatches={int(p.get("maxMatches") or 1)} · minScore={float(p.get("minScore") or 0):.2f} · '
            f'pyramid={int(p.get("pyramidLevels") or 4)}'
        )
        # keep density summary in sync with overlay toggles
        try:
            self.refresh_match_density(keep_rows=True)
        except Exception:
            pass

    def _soft_demo_match_density(self):
        from desktop.geom_find_chrome import soft_demo_matches, summarize_multi_match
        n = int(self.params.get('maxMatches') or 4)
        matches = soft_demo_matches(n=n)
        bag = {'matches': matches, 'items': matches, 'count': len(matches),
               'bestScore': matches[0]['score'] if matches else None, 'found': True}
        summ = summarize_multi_match(bag, params=self.params)
        self._apply_match_density(summ, source='soft-demo')

    def refresh_match_density(self, *, keep_rows: bool = False):
        """Dense multi-match table from last_result / soft empty (no spark cascade)."""
        from desktop.geom_find_chrome import summarize_multi_match, extract_match_items
        lr = getattr(self, '_last_result', None)
        if lr is None:
            try:
                from desktop.upstream_field_picker import host_last_result
                lr = host_last_result(self)
            except Exception:
                lr = None
        # Prefer this step's record
        bag = None
        sid = str(self.step.get('id') or '')
        if isinstance(lr, dict):
            for rec in (lr.get('results') or []):
                if not isinstance(rec, dict):
                    continue
                if sid and str(rec.get('id') or '') == sid:
                    bag = rec
                    break
                op = str(rec.get('operation') or '')
                if op in ('locate', 'match', 'template_match') and bag is None:
                    bag = rec
            if bag is None and extract_match_items(lr):
                bag = lr
        if bag is None:
            if keep_rows and getattr(self, '_last_match_density', None):
                summ = dict(self._last_match_density)
                # refresh overlay flags only
                summ2 = summarize_multi_match({'matches': []}, params=self.params)
                summ['overlayFlags'] = summ2.get('overlayFlags')
                summ['summary'] = (
                    f"匹配×{summ.get('count') or 0}"
                    + (f" · best={summ['bestScore']:.3f}" if summ.get('bestScore') is not None else '')
                    + (' · 叠层:' + '·'.join(summ.get('overlayFlags') or []) if summ.get('overlayFlags') else '')
                )
                self._apply_match_density(summ, source='params')
                return summ
            summ = summarize_multi_match({'matches': []}, params=self.params)
            self._apply_match_density(summ, source='empty')
            return summ
        summ = summarize_multi_match(bag, params=self.params)
        self._apply_match_density(summ, source='engine')
        return summ

    def _apply_match_density(self, summ, *, source: str = ''):
        summ = summ if isinstance(summ, dict) else {}
        lab = getattr(self, '_match_density_lab', None)
        if lab is not None:
            text = summ.get('summary') or '多匹配：空'
            if source:
                text = f'{text} · 源:{source}'
            lab.setText(text)
        table = getattr(self, '_match_density_table', None)
        if table is None:
            return
        rows = summ.get('rows') or []
        table.setRowCount(0)
        for r in rows:
            i = table.rowCount()
            table.insertRow(i)
            sc = r.get('score')
            sc_txt = f'{float(sc):.3f}' if sc is not None else '—'
            x = r.get('x'); y = r.get('y')
            x_txt = f'{float(x):.1f}' if x is not None else '—'
            y_txt = f'{float(y):.1f}' if y is not None else '—'
            ang = r.get('angleDeg')
            ang_txt = f'{float(ang):.1f}' if ang is not None else '—'
            scale = r.get('scale')
            sca_txt = f'{float(scale):.3f}' if scale is not None else '—'
            st = str(r.get('judgeStatus') or '—')
            for c, text in enumerate((
                str(r.get('index') or i + 1), sc_txt, x_txt, y_txt, ang_txt, sca_txt, st,
            )):
                it = QTableWidgetItem(text)
                if st == 'OK':
                    it.setForeground(Qt.GlobalColor.green)
                elif st == 'NG':
                    it.setForeground(Qt.GlobalColor.red)
                table.setItem(i, c, it)
        self._last_match_density = dict(summ)
