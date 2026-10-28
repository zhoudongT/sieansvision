"""色彩区域 / 灰度斑点属性浮窗 — sieans-regions 插件结果密度 (soft OpenCV).

三 Tab：基本参数 / 运行参数 / 结果显示（工业密度表 + 叠层开关）.
"""
from copy import deepcopy

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTabWidget, QFormLayout, QLineEdit,
    QComboBox, QDoubleSpinBox, QSpinBox, QScrollArea, QFrame, QCheckBox,
    QPushButton, QHBoxLayout, QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView,
)

from desktop.widgets.switch import OrangeSwitch


def _args(params) -> dict:
    p = params if isinstance(params, dict) else {}
    a = p.get('arguments')
    return a if isinstance(a, dict) else {}


def normalize_region_color_params(params=None, operator_id=None):
    p = deepcopy(params or {})
    p.setdefault('pluginId', 'sieans-regions')
    p.setdefault('pluginVersion', '1.0.0')
    if operator_id:
        p['operatorId'] = operator_id
    p.setdefault('operatorId', 'color')
    args = dict(_args(p))
    op = str(p.get('operatorId') or 'color')
    if op == 'color':
        args.setdefault('method', 'hsv')
        args.setdefault('hueMin', 170)
        args.setdefault('hueMax', 10)
        args.setdefault('saturationMin', 100)
        args.setdefault('saturationMax', 255)
        args.setdefault('valueMin', 80)
        args.setdefault('valueMax', 255)
    else:
        args.setdefault('method', 'gray')
        args.setdefault('threshold', 127)
        args.setdefault('polarity', 'bright')
    args.setdefault('roiX', 0)
    args.setdefault('roiY', 0)
    args.setdefault('roiWidth', 0)
    args.setdefault('roiHeight', 0)
    args.setdefault('minimumArea', 10)
    args.setdefault('maximumArea', 100000000)
    args.setdefault('minimumCount', 1)
    args.setdefault('maximumCount', 100)
    args.setdefault('excludeBorder', False)
    args.setdefault('connectivity', 8)
    args.setdefault('morphology', 'none')
    args.setdefault('kernelSize', 3)
    args.setdefault('outputImage', 'annotated')
    # soft overlay chrome (UI only; engine still draws annotatedImage)
    args.setdefault('showOverlay', True)
    args.setdefault('showBox', True)
    args.setdefault('showCross', True)
    args.setdefault('showLabels', True)
    args.setdefault('showEllipse', False)
    p['arguments'] = args
    p.setdefault('outputBindings', [])
    return p


class RegionColorPanel(QWidget):
    changed = Signal(dict)

    def __init__(self, step, definition=None, project=None, parent=None):
        super().__init__(parent)
        self.step = deepcopy(step or {})
        self.definition = definition
        self.project = project
        self.params = normalize_region_color_params(self.step.get('params'))
        self.step['params'] = self.params
        self._last_result = None
        self._building = True

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        head = QHBoxLayout()
        self.name_edit = QLineEdit(self.step.get('name') or '')
        self.name_edit.setPlaceholderText('模块名称')
        self.name_edit.editingFinished.connect(self._emit)
        head.addWidget(QLabel('名称'))
        head.addWidget(self.name_edit, 1)
        root.addLayout(head)

        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)

        self._build_basic_tab()
        self._build_run_tab()
        self._build_result_tab()

        self._building = False
        self._sync_visibility()
        try:
            self.refresh_region_density()
        except Exception:
            pass

    # ----- tabs -----
    def _scroll_form(self):
        host = QWidget()
        form = QFormLayout(host)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(host)
        return scroll, form

    def _build_basic_tab(self):
        scroll, form = self._scroll_form()
        args = _args(self.params)

        self.op_combo = QComboBox()
        self.op_combo.addItem('HSV 色彩区域', 'color')
        self.op_combo.addItem('灰度斑点', 'blobs')
        idx = self.op_combo.findData(self.params.get('operatorId') or 'color')
        if idx >= 0:
            self.op_combo.setCurrentIndex(idx)
        self.op_combo.currentIndexChanged.connect(self._on_op_changed)
        form.addRow('算子', self.op_combo)

        self.method_hint = QLabel('')
        self.method_hint.setStyleSheet('color:#666;font-size:11px;')
        form.addRow('', self.method_hint)

        # HSV
        self.hue_min = QSpinBox(); self.hue_min.setRange(0, 179); self.hue_min.setValue(int(args.get('hueMin') or 0))
        self.hue_max = QSpinBox(); self.hue_max.setRange(0, 179); self.hue_max.setValue(int(args.get('hueMax') or 0))
        self.sat_min = QSpinBox(); self.sat_min.setRange(0, 255); self.sat_min.setValue(int(args.get('saturationMin') or 0))
        self.sat_max = QSpinBox(); self.sat_max.setRange(0, 255); self.sat_max.setValue(int(args.get('saturationMax') or 255))
        self.val_min = QSpinBox(); self.val_min.setRange(0, 255); self.val_min.setValue(int(args.get('valueMin') or 0))
        self.val_max = QSpinBox(); self.val_max.setRange(0, 255); self.val_max.setValue(int(args.get('valueMax') or 255))
        for w in (self.hue_min, self.hue_max, self.sat_min, self.sat_max, self.val_min, self.val_max):
            w.valueChanged.connect(self._emit)
        form.addRow('色相 min', self.hue_min)
        form.addRow('色相 max', self.hue_max)
        form.addRow('饱和 min', self.sat_min)
        form.addRow('饱和 max', self.sat_max)
        form.addRow('亮度 min', self.val_min)
        form.addRow('亮度 max', self.val_max)

        # gray
        self.threshold = QSpinBox(); self.threshold.setRange(0, 255); self.threshold.setValue(int(args.get('threshold') or 127))
        self.polarity = QComboBox()
        self.polarity.addItem('亮目标', 'bright')
        self.polarity.addItem('暗目标', 'dark')
        pi = self.polarity.findData(args.get('polarity') or 'bright')
        if pi >= 0:
            self.polarity.setCurrentIndex(pi)
        self.threshold.valueChanged.connect(self._emit)
        self.polarity.currentIndexChanged.connect(self._emit)
        form.addRow('灰度阈值', self.threshold)
        form.addRow('极性', self.polarity)

        self.out_img = QComboBox()
        for lab, val in (('标注图', 'annotated'), ('掩膜', 'mask'), ('原图', 'original')):
            self.out_img.addItem(lab, val)
        oi = self.out_img.findData(args.get('outputImage') or 'annotated')
        if oi >= 0:
            self.out_img.setCurrentIndex(oi)
        self.out_img.currentIndexChanged.connect(self._emit)
        form.addRow('输出图像', self.out_img)

        self.tabs.addTab(scroll, '基本参数')

    def _build_run_tab(self):
        scroll, form = self._scroll_form()
        args = _args(self.params)

        self.min_area = QSpinBox(); self.min_area.setRange(1, 10**9); self.min_area.setValue(int(args.get('minimumArea') or 10))
        self.max_area = QSpinBox(); self.max_area.setRange(1, 10**9); self.max_area.setValue(int(args.get('maximumArea') or 10**8))
        self.min_count = QSpinBox(); self.min_count.setRange(0, 10000); self.min_count.setValue(int(args.get('minimumCount') or 1))
        self.max_count = QSpinBox(); self.max_count.setRange(0, 10000); self.max_count.setValue(int(args.get('maximumCount') or 100))
        for w in (self.min_area, self.max_area, self.min_count, self.max_count):
            w.valueChanged.connect(self._emit)
        form.addRow('面积下限', self.min_area)
        form.addRow('面积上限', self.max_area)
        form.addRow('数量下限', self.min_count)
        form.addRow('数量上限', self.max_count)

        self.exclude_border = OrangeSwitch()
        self.exclude_border.setChecked(bool(args.get('excludeBorder')))
        self.exclude_border.toggled.connect(lambda *_: self._emit())
        form.addRow('排除贴边', self.exclude_border)

        self.connectivity = QComboBox()
        self.connectivity.addItem('4 连通', 4)
        self.connectivity.addItem('8 连通', 8)
        ci = self.connectivity.findData(int(args.get('connectivity') or 8))
        if ci >= 0:
            self.connectivity.setCurrentIndex(ci)
        self.connectivity.currentIndexChanged.connect(self._emit)
        form.addRow('连通性', self.connectivity)

        self.morph = QComboBox()
        for lab, val in (('无', 'none'), ('开运算', 'open'), ('闭运算', 'close')):
            self.morph.addItem(lab, val)
        mi = self.morph.findData(args.get('morphology') or 'none')
        if mi >= 0:
            self.morph.setCurrentIndex(mi)
        self.morph.currentIndexChanged.connect(self._emit)
        form.addRow('形态学', self.morph)

        self.kernel = QSpinBox(); self.kernel.setRange(1, 31); self.kernel.setSingleStep(2)
        self.kernel.setValue(int(args.get('kernelSize') or 3))
        self.kernel.valueChanged.connect(self._emit)
        form.addRow('核尺寸', self.kernel)

        # ROI soft
        self.roi_x = QSpinBox(); self.roi_x.setRange(0, 100000); self.roi_x.setValue(int(args.get('roiX') or 0))
        self.roi_y = QSpinBox(); self.roi_y.setRange(0, 100000); self.roi_y.setValue(int(args.get('roiY') or 0))
        self.roi_w = QSpinBox(); self.roi_w.setRange(0, 100000); self.roi_w.setValue(int(args.get('roiWidth') or 0))
        self.roi_h = QSpinBox(); self.roi_h.setRange(0, 100000); self.roi_h.setValue(int(args.get('roiHeight') or 0))
        for w in (self.roi_x, self.roi_y, self.roi_w, self.roi_h):
            w.valueChanged.connect(self._emit)
        form.addRow('ROI X', self.roi_x)
        form.addRow('ROI Y', self.roi_y)
        form.addRow('ROI 宽(0=全)', self.roi_w)
        form.addRow('ROI 高(0=全)', self.roi_h)

        self.tabs.addTab(scroll, '运行参数')

    def _build_result_tab(self):
        scroll, form = self._scroll_form()
        args = _args(self.params)

        self.show_overlay = OrangeSwitch(); self.show_overlay.setChecked(bool(args.get('showOverlay', True)))
        self.show_box = OrangeSwitch(); self.show_box.setChecked(bool(args.get('showBox', True)))
        self.show_cross = OrangeSwitch(); self.show_cross.setChecked(bool(args.get('showCross', True)))
        self.show_labels = OrangeSwitch(); self.show_labels.setChecked(bool(args.get('showLabels', True)))
        self.show_ellipse = OrangeSwitch(); self.show_ellipse.setChecked(bool(args.get('showEllipse', False)))
        for sw in (self.show_overlay, self.show_box, self.show_cross, self.show_labels, self.show_ellipse):
            sw.toggled.connect(lambda *_: self._emit())
        form.addRow('矢量叠层', self.show_overlay)
        form.addRow('外接矩形', self.show_box)
        form.addRow('质心十字', self.show_cross)
        form.addRow('序号标签', self.show_labels)
        form.addRow('椭圆近似', self.show_ellipse)

        self._region_summary = QLabel('区域结果：空')
        self._region_summary.setObjectName('regionColorSummary')
        self._region_summary.setWordWrap(True)
        self._region_summary.setStyleSheet(
            'QLabel#regionColorSummary{color:#ddd;background:#1e2228;padding:6px 8px;border-radius:4px;}'
        )
        form.addRow('区域摘要', self._region_summary)

        self._region_table = QTableWidget(0, 7)
        self._region_table.setObjectName('regionColorResultTable')
        self._region_table.setHorizontalHeaderLabels(
            ['#', '面积', '中心X', '中心Y', '宽×高', '填充率', '判定']
        )
        self._region_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._region_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._region_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._region_table.setMaximumHeight(220)
        form.addRow(self._region_table)

        demo_row = QHBoxLayout()
        btn = QPushButton('软演示密度')
        btn.setObjectName('regionColorSoftDemoBtn')
        btn.clicked.connect(self._soft_demo_region_density)
        demo_row.addWidget(btn)
        refresh = QPushButton('刷新结果')
        refresh.clicked.connect(self.refresh_region_density)
        demo_row.addWidget(refresh)
        demo_row.addStretch(1)
        wrap = QWidget(); wrap.setLayout(demo_row)
        form.addRow(wrap)

        self.tabs.addTab(scroll, '结果显示')

    # ----- sync / emit -----
    def _on_op_changed(self, *_):
        self._sync_visibility()
        self._emit()

    def _sync_visibility(self):
        op = self.op_combo.currentData()
        is_color = op == 'color'
        for w in (self.hue_min, self.hue_max, self.sat_min, self.sat_max, self.val_min, self.val_max):
            w.setEnabled(is_color)
            w.setVisible(is_color)
        for w in (self.threshold, self.polarity):
            w.setEnabled(not is_color)
            w.setVisible(not is_color)
        self.method_hint.setText(
            'HSV 色相可跨 0 端点（如 170–10 = 红色）' if is_color else '灰度阈值 + 极性 · OpenCV 连通域'
        )

    def _collect(self):
        op = self.op_combo.currentData() or 'color'
        args = dict(_args(self.params))
        args['method'] = 'hsv' if op == 'color' else 'gray'
        if op == 'color':
            args['hueMin'] = int(self.hue_min.value())
            args['hueMax'] = int(self.hue_max.value())
            args['saturationMin'] = int(self.sat_min.value())
            args['saturationMax'] = int(self.sat_max.value())
            args['valueMin'] = int(self.val_min.value())
            args['valueMax'] = int(self.val_max.value())
        else:
            args['threshold'] = int(self.threshold.value())
            args['polarity'] = self.polarity.currentData() or 'bright'
        args['minimumArea'] = int(self.min_area.value())
        args['maximumArea'] = int(self.max_area.value())
        args['minimumCount'] = int(self.min_count.value())
        args['maximumCount'] = int(self.max_count.value())
        args['excludeBorder'] = bool(self.exclude_border.isChecked())
        args['connectivity'] = int(self.connectivity.currentData() or 8)
        args['morphology'] = self.morph.currentData() or 'none'
        ks = int(self.kernel.value())
        if ks % 2 == 0:
            ks += 1
        args['kernelSize'] = ks
        args['roiX'] = int(self.roi_x.value())
        args['roiY'] = int(self.roi_y.value())
        args['roiWidth'] = int(self.roi_w.value())
        args['roiHeight'] = int(self.roi_h.value())
        args['outputImage'] = self.out_img.currentData() or 'annotated'
        args['showOverlay'] = bool(self.show_overlay.isChecked())
        args['showBox'] = bool(self.show_box.isChecked())
        args['showCross'] = bool(self.show_cross.isChecked())
        args['showLabels'] = bool(self.show_labels.isChecked())
        args['showEllipse'] = bool(self.show_ellipse.isChecked())
        self.params['operatorId'] = op
        self.params['pluginId'] = 'sieans-regions'
        self.params['pluginVersion'] = self.params.get('pluginVersion') or '1.0.0'
        self.params['arguments'] = args
        self.step['name'] = self.name_edit.text().strip() or self.step.get('name') or '色彩区域'
        self.step['params'] = self.params
        self.step['operation'] = 'plugin'
        return self.step

    def _emit(self, *_):
        if self._building:
            return
        self.changed.emit(deepcopy(self._collect()))

    # ----- result density -----
    def set_last_result(self, result):
        self._last_result = result
        try:
            self.refresh_region_density()
        except Exception:
            pass

    def _host_last_result(self):
        lr = getattr(self, '_last_result', None)
        if lr is not None:
            return lr
        try:
            from desktop.upstream_field_picker import host_last_result
            return host_last_result(self)
        except Exception:
            return None

    def _find_step_result_bag(self):
        lr = self._host_last_result()
        if not isinstance(lr, dict):
            return None
        sid = str(self.step.get('id') or '')
        for rec in (lr.get('results') or []):
            if not isinstance(rec, dict):
                continue
            if sid and str(rec.get('id') or '') == sid:
                return rec
        # fallback: first region-like plugin
        for rec in (lr.get('results') or []):
            if not isinstance(rec, dict):
                continue
            out = rec.get('output') if isinstance(rec.get('output'), dict) else {}
            bag = out.get('result') if isinstance(out.get('result'), dict) else out
            if isinstance(bag, dict) and 'coveragePercent' in bag:
                return rec
        return None

    def _soft_demo_region_density(self):
        from desktop.region_color_chrome import soft_demo_region_items, summarize_region_result
        op = self.op_combo.currentData() or 'color'
        n = max(1, int(self.max_count.value() or 2))
        n = min(n, 4)
        items = soft_demo_region_items(op, n=n)
        total = sum(it['areaPixels'] for it in items)
        bag = {
            'count': len(items),
            'areaPixels': total,
            'coveragePercent': 12.5,
            'largestArea': items[0]['areaPixels'] if items else 0,
            'items': items,
            'passed': True,
            'roi': {'x': 0, 'y': 0, 'width': 320, 'height': 240},
        }
        self._apply_region_density(
            summarize_region_result(bag, params=self.params),
            source='soft-demo',
        )

    def refresh_region_density(self):
        from desktop.region_color_chrome import summarize_region_result
        rec = self._find_step_result_bag()
        if rec is None:
            op = self.params.get('operatorId') or 'color'
            tag = '色' if op == 'color' else '斑'
            self._region_summary.setText(f'区域结果：空 · 等待运行（{tag}）')
            self._region_table.setRowCount(0)
            return
        summ = summarize_region_result(rec, params=self.params)
        self._apply_region_density(summ, source='last-run')

    def _apply_region_density(self, summ, *, source: str = ''):
        summ = summ if isinstance(summ, dict) else {}
        lab = getattr(self, '_region_summary', None)
        if lab is not None:
            chrome = summ.get('chrome') or ''
            text = summ.get('summary') or '区域结果：空'
            if source:
                text = f'{text} · 源:{source}'
            if chrome:
                text = f'[{chrome}] {text}'
            lab.setText(text)
        table = getattr(self, '_region_table', None)
        if table is None:
            return
        rows = summ.get('rows') or []
        table.setRowCount(0)
        for r in rows:
            i = table.rowCount()
            table.insertRow(i)
            area = r.get('area')
            area_txt = f'{float(area):.0f}' if area is not None else '—'
            cx = r.get('centerX'); cy = r.get('centerY')
            cx_txt = f'{float(cx):.1f}' if cx is not None else '—'
            cy_txt = f'{float(cy):.1f}' if cy is not None else '—'
            w, h = r.get('width'), r.get('height')
            wh = f'{int(w)}×{int(h)}' if w is not None and h is not None else '—'
            fill = r.get('fillRatio')
            fill_txt = f'{float(fill):.2f}' if fill is not None else '—'
            st = str(r.get('judgeStatus') or '—')
            for c, text in enumerate((
                str(r.get('index') or i + 1), area_txt, cx_txt, cy_txt, wh, fill_txt, st,
            )):
                it = QTableWidgetItem(text)
                if st == 'OK':
                    it.setForeground(Qt.GlobalColor.darkGreen)
                elif st == 'NG':
                    it.setForeground(Qt.GlobalColor.red)
                table.setItem(i, c, it)
