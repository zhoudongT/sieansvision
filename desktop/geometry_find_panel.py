"""几何查找属性浮窗 — 直线/圆/矩形（VM p=5/6/15）.

三 Tab：基本参数（输入源、ROI、特征）/ 运行参数 / 结果显示。
写入 geometry.params.feature = lines|circles|rects。
"""
from copy import deepcopy

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTabWidget, QFormLayout, QLineEdit,
    QComboBox, QDoubleSpinBox, QSpinBox, QScrollArea, QFrame, QCheckBox,
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
    p.setdefault('subPixel', False)   # UI 旗标；引擎不伪称 Halcon 亚像素核
    p.setdefault('cannyLow', 50)
    p.setdefault('cannyHigh', 150)
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

        pose = OrangeSwitch(bool(self.params.get('followPose', False)))
        pose.toggled.connect(lambda c: self._set_param('followPose', bool(c)))
        form.addRow('位置修正跟随', pose)
        return w

    def _run_tab(self):
        w = QWidget()
        form = QFormLayout(w)
        form.setContentsMargins(10, 10, 10, 10)
        form.setSpacing(8)
        feat = self.params.get('feature') or 'lines'

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
        tip = QLabel('卡尺级字段对齐 VM p05/p06；引擎为 OpenCV（滤波/个数/半径），不伪称 Halcon 卡尺核。未选输入源 → N4 红叹号。')
        tip.setWordWrap(True); tip.setStyleSheet('color:#888;')
        form.addRow(tip)
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
        je = OrangeSwitch(bool(self.params.get('judgeEnable', False)))
        je.toggled.connect(lambda c: self._set_param('judgeEnable', bool(c)))
        form.addRow('结果判断', je)
        jmin = QDoubleSpinBox(); jmin.setRange(-1e9, 1e9); jmin.setValue(float(self.params.get('judgeMin') or 0))
        jmin.valueChanged.connect(lambda v: self._set_param('judgeMin', float(v)))
        form.addRow('判断下限', jmin)
        jmax = QDoubleSpinBox(); jmax.setRange(-1e9, 1e9); jmax.setValue(float(self.params.get('judgeMax') or 99999))
        jmax.valueChanged.connect(lambda v: self._set_param('judgeMax', float(v)))
        form.addRow('判断上限', jmax)
        tip = QLabel('直线：起点/终点/角度；圆：中心/半径；矩形：中心/宽高/角度。引擎沿用 geometry。')
        tip.setWordWrap(True)
        tip.setStyleSheet('color:#888;')
        form.addRow(tip)
        return w
