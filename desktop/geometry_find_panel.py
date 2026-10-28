"""几何查找属性浮窗 — 直线/圆/矩形（VM p=5/6/15）.

三 Tab：基本参数（输入源、ROI、特征）/ 运行参数 / 结果显示。
写入 geometry.params.feature = lines|circles|rects。
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

FEATURE_LABELS = {
    'lines': '直线查找',
    'circles': '圆查找',
    'rects': '矩形查找',
    'contours': '轮廓查找',
    'edges': '边缘查找',
}


def normalize_geometry_params(params=None, feature=None):
    p = deepcopy(params or {})
    if feature:
        p['feature'] = feature
    p.setdefault('feature', 'lines')
    p.setdefault('roiMode', 'draw')  # draw | inherit
    p.setdefault('roiShape', 'rect')  # rect | rotated | circle_roi
    p.setdefault('followPose', False)
    p.setdefault('threshold', 127)
    p.setdefault('minArea', 50)
    p.setdefault('invert', False)
    p.setdefault('edgePolarity', 'any')  # any | dark_to_light | light_to_dark
    p.setdefault('edgeThreshold', 30)
    p.setdefault('maxCount', 1)
    p.setdefault('minScore', 0.5)
    p.setdefault('minLength', 30)
    p.setdefault('maxGap', 10)
    p.setdefault('minRadius', 0)
    p.setdefault('maxRadius', 0)
    p.setdefault('minDistance', 20)
    p.setdefault('votes', 30)
    p.setdefault('angleTolerance', 5.0)
    p.setdefault('showOverlay', True)
    p.setdefault('showPoints', True)
    p.setdefault('judgeEnable', False)
    p.setdefault('judgeMin', 0.0)
    p.setdefault('judgeMax', 99999.0)
    p.setdefault('searchDir', 'left_right')
    p.setdefault('caliperCount', 10)
    p.setdefault('caliperWidth', 20)   # VM 卡尺宽（Length2）
    p.setdefault('caliperLength', 40)  # VM 卡尺投影长（Length1）
    p.setdefault('caliperSigma', 1.0)
    p.setdefault('caliperProjAngle', 0.0)
    p.setdefault('edgeType', 'strongest')  # strongest|first|last|all — VM 边缘类型
    p.setdefault('filterSize', 1)      # VM 滤波尺寸
    p.setdefault('rejectPoints', 0)    # VM 剔除点数
    p.setdefault('reverseFind', False)  # VM 直线查找反向
    p.setdefault('angleNormalize', False)  # VM 角度归一化
    p.setdefault('annulusInner', 0)    # VM 扇环内半径（圆）
    p.setdefault('annulusOuter', 0)    # VM 扇环外半径（圆）
    p.setdefault('initialLocate', False)  # VM 初定位（圆）
    p.setdefault('showCalipers', True)
    p.setdefault('showFitError', False)
    p.setdefault('showFitCurve', True)
    p.setdefault('showLabels', True)
    p.setdefault('showRuler', False)
    p.setdefault('subPixel', False)   # UI 旗标；引擎不伪称 Halcon 亚像素核
    p.setdefault('cannyLow', 50)
    p.setdefault('cannyHigh', 150)
    p.setdefault('findMethod', 'caliper')  # caliper | hough | auto
    p.setdefault('roiPreset', 'full')     # full|center|left|right|top|bottom
    p.setdefault('maximumResidual', 2.0)
    return p


class GeometryFindPanel(QWidget):
    changed = Signal(dict)

    def __init__(self, step, definition, project, parent=None, force_feature=None):
        super().__init__(parent)
        self.step = deepcopy(step)
        self.definition = definition or {}
        self.project = project or {}
        feat = force_feature or (step.get('params') or {}).get('feature') or 'lines'
        self.params = normalize_geometry_params(step.get('params'), feature=feat)
        self.step['params'] = self.params
        title = FEATURE_LABELS.get(self.params.get('feature'), '几何查找')

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        hint = QLabel(f'对齐 VisionMaster「{title}」：基本参数 / 运行参数 / 结果显示。')
        hint.setWordWrap(True)
        hint.setStyleSheet('color:#666;padding:8px 10px 4px;')
        root.addWidget(hint)
        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)
        self.tabs.addTab(self._wrap(self._basic_tab()), '基本参数')
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
            self._emit()
            try:
                self._refresh_caliper_hint()
            except Exception:
                pass

    def _set_top(self, key, value):
        if self.step.get(key) != value:
            self.step[key] = deepcopy(value)
            self._emit()

    def _basic_tab(self):
        w = QWidget()
        form = QFormLayout(w)
        form.setContentsMargins(10, 10, 10, 10)
        form.setSpacing(8)
        feat = self.params.get('feature') or 'lines'
        name = QLineEdit(self.step.get('name') or FEATURE_LABELS.get(feat, '几何查找'))
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

        feat_box = QComboBox()
        for k, lab in FEATURE_LABELS.items():
            feat_box.addItem(lab, k)
        feat_box.setCurrentIndex(max(0, feat_box.findData(feat)))
        feat_box.currentIndexChanged.connect(lambda _: self._set_param('feature', feat_box.currentData()))
        form.addRow('特征类型', feat_box)

        roi = QComboBox()
        roi.addItem('绘制 ROI', 'draw')
        roi.addItem('继承上游 ROI', 'inherit')
        roi.setCurrentIndex(max(0, roi.findData(self.params.get('roiMode') or 'draw')))
        roi.currentIndexChanged.connect(lambda _: self._set_param('roiMode', roi.currentData()))
        form.addRow('ROI 创建', roi)

        shape = QComboBox()
        for k, lab in (('rect', '矩形'), ('rotated', '旋转矩形'), ('circle_roi', '圆环/圆 ROI')):
            shape.addItem(lab, k)
        shape.setCurrentIndex(max(0, shape.findData(self.params.get('roiShape') or 'rect')))
        shape.currentIndexChanged.connect(lambda _: self._set_param('roiShape', shape.currentData()))
        form.addRow('ROI 形状', shape)

        preset = QComboBox()
        for k, lab in (
            ('full', '全图'),
            ('center', '中心半幅'),
            ('left', '左半'),
            ('right', '右半'),
            ('top', '上半'),
            ('bottom', '下半'),
        ):
            preset.addItem(lab, k)
        preset.setCurrentIndex(max(0, preset.findData(self.params.get('roiPreset') or 'full')))
        preset.currentIndexChanged.connect(lambda _: self._set_param('roiPreset', preset.currentData()))
        form.addRow('ROI 预设', preset)

        pose = OrangeSwitch(bool(self.params.get('followPose', False)))
        pose.toggled.connect(lambda c: self._set_param('followPose', bool(c)))
        form.addRow('位置修正跟随', pose)

        from desktop.upstream_field_picker import make_upstream_ref_row
        uref_row, self._upstream_ref = make_upstream_ref_row(
            self, self.project, self.step.get('id'), self.params, self._set_param,
        )
        form.addRow('上游参考', uref_row)
        return w

    def _run_tab(self):
        w = QWidget()
        form = QFormLayout(w)
        form.setContentsMargins(10, 10, 10, 10)
        form.setSpacing(8)
        feat = self.params.get('feature') or 'lines'

        if feat in ('lines', 'edges'):
            fm = QComboBox()
            for k, lab in (
                ('caliper', '多卡尺边缘拟合'),
                ('hough', 'Hough 直线'),
                ('auto', '自动（卡尺失败回退）'),
            ):
                fm.addItem(lab, k)
            fm.setCurrentIndex(max(0, fm.findData(self.params.get('findMethod') or 'caliper')))
            fm.currentIndexChanged.connect(lambda _: self._set_param('findMethod', fm.currentData()))
            form.addRow('查找方法', fm)
            mr = QDoubleSpinBox(); mr.setRange(0.01, 100); mr.setDecimals(2)
            mr.setValue(float(self.params.get('maximumResidual') or 2.0))
            mr.valueChanged.connect(lambda v: self._set_param('maximumResidual', float(v)))
            form.addRow('最大残差(px)', mr)

        # —— VM 卡尺级（对齐 p05/p06 运行参数帧）——
        if feat == 'circles':
            ai = QSpinBox(); ai.setRange(0, 100000); ai.setValue(int(self.params.get('annulusInner') or 0))
            ai.valueChanged.connect(lambda v: self._set_param('annulusInner', int(v)))
            form.addRow('扇环内半径', ai)
            ao = QSpinBox(); ao.setRange(0, 100000); ao.setValue(int(self.params.get('annulusOuter') or 0))
            ao.valueChanged.connect(lambda v: self._set_param('annulusOuter', int(v)))
            form.addRow('扇环外半径', ao)

        etype = QComboBox()
        for k, lab in (
            ('strongest', '最强'),
            ('first', '第一条'),
            ('last', '最后一条'),
            ('all', '全部'),
        ):
            etype.addItem(lab, k)
        etype.setCurrentIndex(max(0, etype.findData(self.params.get('edgeType') or 'strongest')))
        etype.currentIndexChanged.connect(lambda _: self._set_param('edgeType', etype.currentData()))
        form.addRow('边缘类型', etype)

        pol = QComboBox()
        for k, lab in (('any', '任意极性'), ('dark_to_light', '黑到白'), ('light_to_dark', '白到黑')):
            pol.addItem(lab, k)
        pol.setCurrentIndex(max(0, pol.findData(self.params.get('edgePolarity') or 'any')))
        pol.currentIndexChanged.connect(lambda _: self._set_param('edgePolarity', pol.currentData()))
        form.addRow('边缘极性', pol)

        et = QSpinBox(); et.setRange(1, 255); et.setValue(int(self.params.get('edgeThreshold') or 30))
        et.valueChanged.connect(lambda v: self._set_param('edgeThreshold', int(v)))
        form.addRow('边缘阈值', et)

        fs = QSpinBox(); fs.setRange(1, 31); fs.setValue(int(self.params.get('filterSize') or 1))
        fs.valueChanged.connect(lambda v: self._set_param('filterSize', int(v)))
        form.addRow('滤波尺寸', fs)

        cc = QSpinBox(); cc.setRange(1, 200); cc.setValue(int(self.params.get('caliperCount') or 10))
        cc.valueChanged.connect(lambda v: self._set_param('caliperCount', int(v)))
        form.addRow('卡尺数量', cc)

        cw = QSpinBox(); cw.setRange(1, 10000); cw.setValue(int(self.params.get('caliperWidth') or 20))
        cw.valueChanged.connect(lambda v: self._set_param('caliperWidth', int(v)))
        form.addRow('卡尺宽度', cw)
        clen = QSpinBox(); clen.setRange(1, 10000); clen.setValue(int(self.params.get('caliperLength') or 40))
        clen.valueChanged.connect(lambda v: self._set_param('caliperLength', int(v)))
        form.addRow('卡尺投影长', clen)

        sig = QDoubleSpinBox(); sig.setRange(0.1, 50); sig.setDecimals(2); sig.setSingleStep(0.5)
        sig.setValue(float(self.params.get('caliperSigma') or 1.0))
        sig.valueChanged.connect(lambda v: self._set_param('caliperSigma', float(v)))
        form.addRow('卡尺高斯σ', sig)
        ang = QDoubleSpinBox(); ang.setRange(-180, 180); ang.setDecimals(1); ang.setSingleStep(1)
        ang.setValue(float(self.params.get('caliperProjAngle') or 0))
        ang.valueChanged.connect(lambda v: self._set_param('caliperProjAngle', float(v)))
        form.addRow('卡尺投影角°', ang)

        rp = QSpinBox(); rp.setRange(0, 200); rp.setValue(int(self.params.get('rejectPoints') or 0))
        rp.valueChanged.connect(lambda v: self._set_param('rejectPoints', int(v)))
        form.addRow('剔除点数', rp)

        if feat in ('lines', 'edges'):
            rev = OrangeSwitch(bool(self.params.get('reverseFind', False)))
            rev.toggled.connect(lambda c: self._set_param('reverseFind', bool(c)))
            form.addRow('直线查找反向', rev)
            an = OrangeSwitch(bool(self.params.get('angleNormalize', False)))
            an.toggled.connect(lambda c: self._set_param('angleNormalize', bool(c)))
            form.addRow('角度归一化', an)

        if feat == 'circles':
            il = OrangeSwitch(bool(self.params.get('initialLocate', False)))
            il.toggled.connect(lambda c: self._set_param('initialLocate', bool(c)))
            form.addRow('初定位', il)

        sd = QComboBox()
        for k, lab in (('left_right', '左→右'), ('right_left', '右→左'), ('top_bottom', '上→下'), ('bottom_top', '下→上')):
            sd.addItem(lab, k)
        sd.setCurrentIndex(max(0, sd.findData(self.params.get('searchDir') or 'left_right')))
        sd.currentIndexChanged.connect(lambda _: self._set_param('searchDir', sd.currentData()))
        form.addRow('搜索方向', sd)

        mx = QSpinBox(); mx.setRange(1, 100); mx.setValue(int(self.params.get('maxCount') or 1))
        mx.valueChanged.connect(lambda v: self._set_param('maxCount', int(v)))
        form.addRow('最大个数', mx)

        sc = QDoubleSpinBox(); sc.setRange(0, 1); sc.setDecimals(3); sc.setSingleStep(0.05)
        sc.setValue(float(self.params.get('minScore') or 0.5))
        sc.valueChanged.connect(lambda v: self._set_param('minScore', float(v)))
        form.addRow('最低分数', sc)

        if feat in ('lines', 'edges', 'rects'):
            ml = QSpinBox(); ml.setRange(1, 100000); ml.setValue(int(self.params.get('minLength') or 30))
            ml.valueChanged.connect(lambda v: self._set_param('minLength', int(v)))
            form.addRow('最短长度', ml)
            gap = QSpinBox(); gap.setRange(0, 10000); gap.setValue(int(self.params.get('maxGap') or 10))
            gap.valueChanged.connect(lambda v: self._set_param('maxGap', int(v)))
            form.addRow('最大断点', gap)

        if feat in ('circles', 'rects'):
            r0 = QSpinBox(); r0.setRange(0, 100000); r0.setValue(int(self.params.get('minRadius') or 0))
            r0.valueChanged.connect(lambda v: self._set_param('minRadius', int(v)))
            form.addRow('最小半径/半宽', r0)
            r1 = QSpinBox(); r1.setRange(0, 100000); r1.setValue(int(self.params.get('maxRadius') or 0))
            r1.valueChanged.connect(lambda v: self._set_param('maxRadius', int(v)))
            form.addRow('最大半径/半宽', r1)
            md = QSpinBox(); md.setRange(0, 100000); md.setValue(int(self.params.get('minDistance') or 20))
            md.valueChanged.connect(lambda v: self._set_param('minDistance', int(v)))
            form.addRow('圆心最小距离', md)
            vt = QSpinBox(); vt.setRange(1, 500); vt.setValue(int(self.params.get('votes') or 30))
            vt.valueChanged.connect(lambda v: self._set_param('votes', int(v)))
            form.addRow('检测票数', vt)

        if feat == 'rects':
            ang = QDoubleSpinBox(); ang.setRange(0, 90); ang.setDecimals(2)
            ang.setValue(float(self.params.get('angleTolerance') or 5))
            ang.valueChanged.connect(lambda v: self._set_param('angleTolerance', float(v)))
            form.addRow('角度容差 (°)', ang)

        if feat in ('lines', 'edges', 'circles'):
            cl = QSpinBox(); cl.setRange(0, 255); cl.setValue(int(self.params.get('cannyLow') or 50))
            cl.valueChanged.connect(lambda v: self._set_param('cannyLow', int(v)))
            form.addRow('Canny 低', cl)
            ch = QSpinBox(); ch.setRange(0, 255); ch.setValue(int(self.params.get('cannyHigh') or 150))
            ch.valueChanged.connect(lambda v: self._set_param('cannyHigh', int(v)))
            form.addRow('Canny 高', ch)

        thr = QSpinBox(); thr.setRange(0, 255); thr.setValue(int(self.params.get('threshold') or 127))
        thr.valueChanged.connect(lambda v: self._set_param('threshold', int(v)))
        form.addRow('二值阈值', thr)

        sub = OrangeSwitch(bool(self.params.get('subPixel', False)))
        sub.toggled.connect(lambda c: self._set_param('subPixel', bool(c)))
        form.addRow('亚像素（旗标）', sub)

        inv = OrangeSwitch(bool(self.params.get('invert', False)))
        inv.toggled.connect(lambda c: self._set_param('invert', bool(c)))
        form.addRow('反色', inv)
        tip = QLabel('卡尺级字段已接入引擎多卡尺边缘拟合（OpenCV；非 Halcon）。边缘类型=全部+最大个数>1 → 多直线分带；可切 Hough。未选输入源 → N4 红叹号。')
        tip.setWordWrap(True); tip.setStyleSheet('color:#888;')
        form.addRow(tip)
        if feat in ('lines', 'edges'):
            btn = QPushButton('多卡尺 ROI 编辑器…')
            btn.setObjectName('caliperRoiEditorBtn')
            btn.setToolTip('交互式拖拽 ROI + 卡尺探针预览（写入 roi / caliper*）')
            btn.clicked.connect(self._open_caliper_roi_editor)
            form.addRow(btn)
        return w

    def _result_tab(self):
        w = QWidget()
        form = QFormLayout(w)
        form.setContentsMargins(10, 10, 10, 10)
        ov = OrangeSwitch(bool(self.params.get('showOverlay', True)))
        ov.toggled.connect(lambda c: self._set_param('showOverlay', bool(c)))
        form.addRow('显示叠加', ov)
        pts = OrangeSwitch(bool(self.params.get('showPoints', True)))
        pts.toggled.connect(lambda c: self._set_param('showPoints', bool(c)))
        form.addRow('显示特征点', pts)
        cal = OrangeSwitch(bool(self.params.get('showCalipers', True)))
        cal.toggled.connect(lambda c: self._set_param('showCalipers', bool(c)))
        form.addRow('显示卡尺', cal)
        fe = OrangeSwitch(bool(self.params.get('showFitError', False)))
        fe.toggled.connect(lambda c: self._set_param('showFitError', bool(c)))
        form.addRow('显示拟合误差', fe)
        fc = OrangeSwitch(bool(self.params.get('showFitCurve', True)))
        fc.toggled.connect(lambda c: self._set_param('showFitCurve', bool(c)))
        form.addRow('显示拟合曲线', fc)
        lb = OrangeSwitch(bool(self.params.get('showLabels', True)))
        lb.toggled.connect(lambda c: self._set_param('showLabels', bool(c)))
        form.addRow('显示标签', lb)
        ru = OrangeSwitch(bool(self.params.get('showRuler', False)))
        ru.toggled.connect(lambda c: self._set_param('showRuler', bool(c)))
        form.addRow('显示卡尺标尺', ru)
        tip_ov = QLabel('叠层：卡尺框 / 特征点 / 拟合曲线 / 标签 / 标尺可独立开关（对齐 VM 几何查找结果显示）。')
        tip_ov.setWordWrap(True)
        tip_ov.setStyleSheet('color:#888;font-size:11px;')
        form.addRow(tip_ov)
        je = OrangeSwitch(bool(self.params.get('judgeEnable', False)))
        je.toggled.connect(lambda c: self._set_param('judgeEnable', bool(c)))
        form.addRow('结果判断', je)
        jmin = QDoubleSpinBox(); jmin.setRange(-1e9, 1e9); jmin.setValue(float(self.params.get('judgeMin') or 0))
        jmin.valueChanged.connect(lambda v: self._set_param('judgeMin', float(v)))
        form.addRow('判断下限', jmin)
        jmax = QDoubleSpinBox(); jmax.setRange(-1e9, 1e9); jmax.setValue(float(self.params.get('judgeMax') or 99999))
        jmax.valueChanged.connect(lambda v: self._set_param('judgeMax', float(v)))
        form.addRow('判断上限', jmax)
        tip = QLabel('直线：起点/终点/角度/score/rms；圆：中心/半径；矩形：中心/宽高/角度。引擎沿用 geometry。')
        tip.setWordWrap(True)
        tip.setStyleSheet('color:#888;')
        form.addRow(tip)
        tip = QLabel('叠层开关已接入引擎实绘（关则不画线/点/标签）。开启「显示拟合误差」可在叠层标注 rms。')
        tip.setWordWrap(True)
        tip.setStyleSheet('color:#888;')
        form.addRow(tip)

        # 结果诊断字段说明（运行后由引擎 residualsSummary / diagnostic 回填到结果面板）
        diag = QLabel(
            '诊断字段：diagnostic · score · rmsPixels · inlierCount · residualsSummary[]\n'
            '多直线：边缘类型=全部 + 最大个数>1 → 按扫描轴分带拟合；不足时残差剥离补线。\n'
            '各线含 lineIndex / score / rmsPixels / lengthPixels / angleDeg。'
        )
        diag.setWordWrap(True)
        diag.setObjectName('geometryDiagHint')
        diag.setStyleSheet('color:#9ab;font-size:11px;padding:4px 0;')
        form.addRow('结果诊断', diag)
        self._caliper_hint = QLabel('')
        self._caliper_hint.setWordWrap(True)
        self._caliper_hint.setObjectName('geometryCaliperHint')
        self._caliper_hint.setStyleSheet('color:#9ab;font-size:11px;padding:2px 0;')
        form.addRow('卡尺回显', self._caliper_hint)
        self._judge_hint = QLabel('')
        self._judge_hint.setWordWrap(True)
        self._judge_hint.setObjectName('geometryJudgeHint')
        self._judge_hint.setStyleSheet(
            'color:#9ad;font-size:11px;padding:6px 8px;background:#1e2228;border-radius:4px;'
        )
        form.addRow('判断回显', self._judge_hint)
        tip_j = QLabel(
            '结果判断：直线用 lengthPixels；圆用 radiusPixels；矩形用 areaPixels；'
            '卡尺线亦可用 score。超出门限 → items[].judgeOk=False / judgeStatus=NG（OpenCV 壳，无 Halcon）。'
        )
        tip_j.setWordWrap(True)
        tip_j.setStyleSheet('color:#888;')
        form.addRow(tip_j)

        # wave140: geometry-find result density table (non-measure)
        self._find_summary = QLabel('查找结果：尚未运行')
        self._find_summary.setObjectName('geometryFindSummary')
        self._find_summary.setWordWrap(True)
        self._find_summary.setStyleSheet(
            'color:#9ad;font-size:11px;padding:6px 8px;background:#1e2228;border-radius:4px;'
        )
        form.addRow('查找摘要', self._find_summary)

        self._find_table = QTableWidget(0, 6)
        self._find_table.setObjectName('geometryFindResultTable')
        self._find_table.setHorizontalHeaderLabels(['#', '度量', '分数', 'rms', '角度°', '判定'])
        self._find_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._find_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._find_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._find_table.setMaximumHeight(160)
        form.addRow('查找明细', self._find_table)

        brow = QHBoxLayout()
        b_live = QPushButton('刷新查找实况')
        b_live.setObjectName('geometryFindLiveRefreshBtn')
        b_live.setToolTip('从 Host last_result 拉取本模块 geometry items（无硬件）')
        b_live.clicked.connect(self.refresh_find_density)
        b_demo = QPushButton('软演示明细')
        b_demo.setObjectName('geometryFindSoftDemoBtn')
        b_demo.setToolTip('填入确定性软演示 items，便于 UI 点测')
        b_demo.clicked.connect(self._soft_demo_find_density)
        brow.addWidget(b_live)
        brow.addWidget(b_demo)
        brow.addStretch(1)
        form.addRow(brow)

        tip_f = QLabel(
            '几何查找胶片铬：特征标签 L/C/R/B/E + 个数 + ✓/✗（与测量卡尺链 OK/NG 徽章分离）。'
            'OpenCV 壳 · 无 Halcon · 无火花线微联级。'
        )
        tip_f.setWordWrap(True)
        tip_f.setStyleSheet('color:#888;font-size:11px;')
        form.addRow(tip_f)

        self._refresh_caliper_hint()
        try:
            self.refresh_find_density()
        except Exception:
            pass
        return w

    def set_last_result(self, result):
        """Cache engine last_result for geometry-find density (soft OK)."""
        self._last_result = result
        try:
            self.refresh_find_density()
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
            op = str(rec.get('operation') or '')
            if op == 'geometry' and not sid:
                return rec
        return None

    def _soft_demo_find_density(self):
        from desktop.geom_find_chrome import soft_demo_geom_items, summarize_geom_find_result
        feat = self.params.get('feature') or 'lines'
        items = soft_demo_geom_items(feat, n=int(self.params.get('maxCount') or 3))
        bag = {'feature': feat, 'items': items, 'count': len(items), 'judgeOk': True}
        self._apply_find_density(summarize_geom_find_result(bag), source='soft-demo')

    def refresh_find_density(self):
        from desktop.geom_find_chrome import summarize_geom_find_result
        rec = self._find_step_result_bag()
        if rec is None:
            # empty state: still show feature chrome hint
            feat = self.params.get('feature') or 'lines'
            summ = summarize_geom_find_result({'feature': feat, 'items': [], 'count': 0})
            self._apply_find_density(summ, source='empty')
            return summ
        summ = summarize_geom_find_result(rec)
        self._apply_find_density(summ, source='engine')
        return summ

    def _apply_find_density(self, summ, *, source: str = ''):
        summ = summ if isinstance(summ, dict) else {}
        lab = getattr(self, '_find_summary', None)
        if lab is not None:
            chrome = summ.get('chrome') or ''
            text = summ.get('summary') or '查找结果：空'
            if source:
                text = f'{text} · 源:{source}'
            if chrome:
                text = f'[{chrome}] {text}'
            lab.setText(text)
        table = getattr(self, '_find_table', None)
        if table is None:
            return
        rows = summ.get('rows') or []
        table.setRowCount(0)
        for r in rows:
            i = table.rowCount()
            table.insertRow(i)
            mlab = r.get('metricLabel') or '—'
            mval = r.get('metric')
            mtxt = f'{mlab}={mval:.3g}' if isinstance(mval, (int, float)) else mlab
            sc = r.get('score')
            sc_txt = f'{float(sc):.3f}' if sc is not None else '—'
            rms = r.get('rms')
            rms_txt = f'{float(rms):.3f}' if rms is not None else '—'
            ang = r.get('angleDeg')
            ang_txt = f'{float(ang):.1f}' if ang is not None else '—'
            # wave141: contour/blob soft density — peri / fill in rms/angle columns
            feat = str(r.get('feature') or self.params.get('feature') or '').lower()
            if feat in ('contours', 'blob'):
                peri = r.get('perimeter')
                fill = r.get('fillRatio')
                if peri is not None:
                    rms_txt = f'P={float(peri):.1f}'
                if fill is not None:
                    ang_txt = f'f={float(fill):.2f}'
                elif r.get('circularity') is not None:
                    ang_txt = f'c={float(r["circularity"]):.2f}'
                cx, cy = r.get('centerX'), r.get('centerY')
                if sc is None and cx is not None and cy is not None:
                    sc_txt = f'{float(cx):.0f},{float(cy):.0f}'
            st = str(r.get('judgeStatus') or '—')
            for c, text in enumerate((
                str(r.get('index') or i + 1), mtxt, sc_txt, rms_txt, ang_txt, st,
            )):
                it = QTableWidgetItem(text)
                if st == 'OK':
                    it.setForeground(Qt.GlobalColor.green)
                elif st == 'NG':
                    it.setForeground(Qt.GlobalColor.red)
                table.setItem(i, c, it)
        self._last_find_density = dict(summ)

    def _refresh_caliper_hint(self):
        lab = getattr(self, '_caliper_hint', None)
        if lab is not None:
            p = self.params
            lab.setText(
                f'卡尺级参数：count={int(p.get("caliperCount") or 10)} · '
                f'width={int(p.get("caliperWidth") or 20)} · '
                f'length={int(p.get("caliperLength") or 40)} · '
                f'sigma={float(p.get("caliperSigma") or 1):.1f} · '
                f'projAngle={float(p.get("caliperProjAngle") or 0):.1f}° · '
                f'method={p.get("findMethod") or "caliper"} · '
                f'edgeType={p.get("edgeType") or "strongest"}（无 Halcon 核）。'
            )
        jlab = getattr(self, '_judge_hint', None)
        if jlab is not None:
            p = self.params
            if p.get('judgeEnable'):
                jlab.setText(
                    f'判断开 · 范围 [{float(p.get("judgeMin") or 0):.3g}, {float(p.get("judgeMax") or 99999):.3g}] · '
                    f'feature={p.get("feature") or "lines"} · maxCount={int(p.get("maxCount") or 1)}'
                )
            else:
                jlab.setText(f'判断关 · feature={p.get("feature") or "lines"} · 叠层按 show* 实绘')

    def _open_caliper_roi_editor(self):
        """打开多卡尺 ROI 编辑器，写回 roi / caliper*（OpenCV 壳，无 Halcon）。"""
        try:
            from desktop.caliper_roi_editor import CaliperRoiEditorDialog
        except Exception as exc:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, '卡尺 ROI', f'无法加载编辑器：{exc}')
            return
        sample = None
        try:
            from pathlib import Path as _P
            cand = _P(__file__).resolve().parents[1] / 'public/vision/samples/caliper-line.png'
            if cand.is_file():
                sample = str(cand)
        except Exception:
            sample = None
        dlg = CaliperRoiEditorDialog(self.params, parent=self, sample_fallback=sample)
        def _apply(patch):
            if not isinstance(patch, dict):
                return
            for k, v in patch.items():
                self.params[k] = deepcopy(v)
            self._emit()
            try:
                self._refresh_caliper_hint()
            except Exception:
                pass
        try:
            dlg.paramsApplied.connect(_apply)
        except Exception:
            pass
        if dlg.exec():
            try:
                patch = dlg.result_params()
            except Exception:
                patch = None
            if isinstance(patch, dict):
                _apply(patch)
