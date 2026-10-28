"""测量几何壳 — 线线交点 / 点点距 / 点线距 / 夹角 / 点圆距 / 圆圆距（VM 几何测量）.

ops: line_intersect | point_distance | point_line_distance |
     line_angle | point_circle_distance | circle_circle_distance
绑定上游几何结果字段，运行时做解析几何计算（软 OpenCV 路径，无 Halcon）。
"""
from copy import deepcopy

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QWidget, QVBoxLayout, QLabel, QTabWidget, QFormLayout, QLineEdit,
    QComboBox, QDoubleSpinBox, QScrollArea, QFrame, QPushButton, QHBoxLayout,
)

from desktop.widgets.switch import OrangeSwitch

OP_META = {
    'line_intersect': ('线与线交点', '绑定两条直线（或四点），求交点。'),
    'point_distance': ('点与点距离', '绑定两个点坐标，求欧氏距离。'),
    'point_line_distance': ('点与线距离', '绑定一点与一条直线，求垂距。'),
    'line_angle': ('线与线夹角', '绑定两条直线，求无向锐夹角 0–90°。'),
    'point_circle_distance': ('点与圆距离', '绑定一点与一圆，求到圆心或边缘距离。'),
    'circle_circle_distance': ('圆与圆距离', '绑定两圆，求中心距 / 间隙 / 外包距。'),
}

MEASURE_GEOM_OPS = tuple(OP_META.keys())


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
    elif op == 'point_line_distance':
        p.setdefault('pointFrom', ''); p.setdefault('pointField', 'matches[0]')
        p.setdefault('lineFrom', ''); p.setdefault('lineField', 'lines[0]')
        p.setdefault('px', 0.0); p.setdefault('py', 0.0)
        p.setdefault('x1', 0.0); p.setdefault('y1', 0.0)
        p.setdefault('x2', 100.0); p.setdefault('y2', 0.0)
    elif op == 'line_angle':
        p.setdefault('line1From', ''); p.setdefault('line1Field', 'lines[0]')
        p.setdefault('line2From', ''); p.setdefault('line2Field', 'lines[0]')
        p.setdefault('x1', 0.0); p.setdefault('y1', 0.0)
        p.setdefault('x2', 100.0); p.setdefault('y2', 0.0)
        p.setdefault('x3', 0.0); p.setdefault('y3', 0.0)
        p.setdefault('x4', 0.0); p.setdefault('y4', 100.0)
        p.setdefault('parallelTolDeg', 0.001)
        p.setdefault('perpTolDeg', 0.5)
    elif op == 'point_circle_distance':
        p.setdefault('pointFrom', ''); p.setdefault('pointField', 'matches[0]')
        p.setdefault('circleFrom', ''); p.setdefault('circleField', 'circles[0]')
        p.setdefault('px', 0.0); p.setdefault('py', 0.0)
        p.setdefault('cx', 50.0); p.setdefault('cy', 50.0); p.setdefault('radius', 20.0)
        p.setdefault('circleMode', 'edge')  # edge|center|signed
    elif op == 'circle_circle_distance':
        p.setdefault('circle1From', ''); p.setdefault('circle1Field', 'circles[0]')
        p.setdefault('circle2From', ''); p.setdefault('circle2Field', 'circles[0]')
        p.setdefault('cx1', 40.0); p.setdefault('cy1', 50.0); p.setdefault('r1', 15.0)
        p.setdefault('cx2', 80.0); p.setdefault('cy2', 50.0); p.setdefault('r2', 15.0)
        p.setdefault('circleMode', 'gap')  # gap|center|outer
    else:
        p.setdefault('pointFrom', ''); p.setdefault('pointField', 'matches[0]')
        p.setdefault('lineFrom', ''); p.setdefault('lineField', 'lines[0]')
        p.setdefault('px', 0.0); p.setdefault('py', 0.0)
        p.setdefault('x1', 0.0); p.setdefault('y1', 0.0)
        p.setdefault('x2', 100.0); p.setdefault('y2', 0.0)
    p.setdefault('unit', 'deg' if op == 'line_angle' else 'px')
    p.setdefault('scale', 1.0)
    p.setdefault('showOverlay', True)
    p.setdefault('showPoints', True)
    p.setdefault('showLines', True)
    p.setdefault('showLabels', True)
    p.setdefault('showDistanceText', True)
    # 测量链 → 流程变量 / 结果判断 / Host 显示
    p.setdefault('resultVar', {
        'line_intersect': 'intersectPt',
        'point_distance': 'pointDist',
        'point_line_distance': 'pointLineDist',
        'line_angle': 'lineAngle',
        'point_circle_distance': 'pointCircleDist',
        'circle_circle_distance': 'circleGap',
    }.get(op, 'measureGeom'))
    p.setdefault('writeFlowVars', True)
    p.setdefault('judgeEnable', False)
    p.setdefault('showTolerance', True)
    p.setdefault('judgeMin', 0.0)
    p.setdefault('judgeMax', 99999.0 if op != 'line_angle' else 90.0)
    p.setdefault('hostDisplayFields', True)
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

    def _bind_kind(self, default_field):
        """line vs point vs circle bind kind from default field hint."""
        df = str(default_field or '')
        if 'circle' in df:
            return 'circle'
        if 'match' in df or df.startswith('center') or 'point' in df:
            return 'point'
        return 'line'

    def _suggest_field(self, upstream_id, default_field):
        from desktop.upstream_field_picker import default_bind_field_for_op
        op = ''
        for s in self.project.get('steps') or []:
            if s.get('id') == upstream_id:
                op = s.get('operation') or ''
                break
        return default_bind_field_for_op(op, self._bind_kind(default_field)) or default_field

    def _bind_row(self, form, label, id_key, field_key, default_field):
        box = QComboBox()
        for data, lab in self._step_items():
            box.addItem(lab, data)
        cur = self.params.get(id_key) or ''
        idx = box.findData(cur)
        if idx < 0 and cur:
            box.addItem('已丢失：' + cur, cur); idx = box.findData(cur)
        box.setCurrentIndex(max(0, idx))
        field = QLineEdit(str(self.params.get(field_key) or default_field))
        field.setPlaceholderText(default_field)
        field.setToolTip(
            '绑定字段路径：lines[0] / lines.0 / matches[0] / circles[0]\n'
            '切换来源会按上游算子自动建议；「插入上游字段」只写入字段名并同步来源。'
        )
        field.editingFinished.connect(lambda: self._set_param(field_key, field.text().strip() or default_field))

        def _on_source_changed(*_):
            nid = box.currentData() or ''
            self._set_param(id_key, nid)
            if nid:
                sug = self._suggest_field(nid, default_field)
                # only auto-fill when empty or still a generic default
                cur_f = field.text().strip()
                if not cur_f or cur_f in ('lines[0]', 'lines.0', 'matches[0]', 'circles[0]', default_field):
                    field.setText(sug)
                    self._set_param(field_key, sug)

        box.currentIndexChanged.connect(_on_source_changed)
        form.addRow(label + ' 来源', box)
        from PySide6.QtWidgets import QHBoxLayout, QPushButton
        from desktop.upstream_field_picker import fill_line_from_picker
        frow = QHBoxLayout()
        pick = QPushButton('插入上游字段')
        pick.setToolTip('挑选上游模块字段 → 同步「来源」并只写入字段路径（非整段 results.* 令牌）')

        def _pick(*_, e=field, fk=field_key, df=default_field, src=box):
            picked = fill_line_from_picker(
                self, self.project, self.step.get('id'), e, self._set_param, fk, field_only=True,
            )
            if not picked:
                if not e.text().strip():
                    e.setText(df); self._set_param(fk, df)
                return
            nid, _field, _token = picked
            if nid:
                i = src.findData(nid)
                if i < 0:
                    # upstream may be missing from list (e.g. source)
                    src.addItem(nid, nid); i = src.findData(nid)
                if i >= 0:
                    src.blockSignals(True)
                    src.setCurrentIndex(i)
                    src.blockSignals(False)
                    self._set_param(id_key, nid)

        pick.clicked.connect(_pick)
        canvas_btn = QPushButton('画布点选')
        canvas_btn.setObjectName('measureGeomCanvasPickBtn')
        canvas_btn.setToolTip('在模块结果/全局图像上点击直线或点，写入来源+字段（需先运行出几何结果）')
        kind = self._bind_kind(default_field)

        def _canvas_pick(*_, e=field, fk=field_key, df=default_field, src=box, ik=id_key, k=kind):
            host = self.window()
            begin = getattr(host, 'begin_geom_canvas_pick', None) if host is not None else None
            if not callable(begin):
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.information(self, '画布点选', '当前窗口不支持画布点选（需主工作台）。')
                return

            def _on_hit(hit):
                if not hit:
                    return
                nid = hit.get('stepId') or ''
                field_path = hit.get('field') or df
                if nid:
                    i = src.findData(nid)
                    if i < 0:
                        src.addItem(hit.get('stepName') or nid, nid)
                        i = src.findData(nid)
                    if i >= 0:
                        src.blockSignals(True)
                        src.setCurrentIndex(i)
                        src.blockSignals(False)
                    self._set_param(ik, nid)
                e.setText(field_path)
                self._set_param(fk, field_path)

            begin(k, _on_hit, status=f'点选{label}（{k}）')

        canvas_btn.clicked.connect(_canvas_pick)
        frow.addWidget(field, 1)
        frow.addWidget(pick)
        frow.addWidget(canvas_btn)
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
        elif self.op == 'point_line_distance':
            self._bind_row(form, '点', 'pointFrom', 'pointField', 'matches[0]')
            self._bind_row(form, '直线', 'lineFrom', 'lineField', 'lines[0]')
        elif self.op == 'line_angle':
            self._bind_row(form, '直线1', 'line1From', 'line1Field', 'lines[0]')
            self._bind_row(form, '直线2', 'line2From', 'line2Field', 'lines[0]')
        elif self.op == 'point_circle_distance':
            self._bind_row(form, '点', 'pointFrom', 'pointField', 'matches[0]')
            self._bind_row(form, '圆', 'circleFrom', 'circleField', 'circles[0]')
            cm = QComboBox()
            for d, lab in (('edge', '到边缘'), ('center', '到圆心'), ('signed', '有符号(外+/内-)')):
                cm.addItem(lab, d)
            cm.setCurrentIndex(max(0, cm.findData(self.params.get('circleMode') or 'edge')))
            cm.currentIndexChanged.connect(lambda _: self._set_param('circleMode', cm.currentData()))
            form.addRow('圆距模式', cm)
        elif self.op == 'circle_circle_distance':
            self._bind_row(form, '圆1', 'circle1From', 'circle1Field', 'circles[0]')
            self._bind_row(form, '圆2', 'circle2From', 'circle2Field', 'circles[0]')
            cm = QComboBox()
            for d, lab in (('gap', '间隙(边缘)'), ('center', '中心距'), ('outer', '外包距')):
                cm.addItem(lab, d)
            cm.setCurrentIndex(max(0, cm.findData(self.params.get('circleMode') or 'gap')))
            cm.currentIndexChanged.connect(lambda _: self._set_param('circleMode', cm.currentData()))
            form.addRow('圆距模式', cm)
        else:
            self._bind_row(form, '点', 'pointFrom', 'pointField', 'matches[0]')
            self._bind_row(form, '直线', 'lineFrom', 'lineField', 'lines[0]')
        unit = QComboBox()
        units = ('deg',) if self.op == 'line_angle' else ('px', 'mm', 'cm')
        for u in units:
            unit.addItem(u, u)
        unit.setCurrentIndex(max(0, unit.findData(self.params.get('unit') or 'px')))
        unit.currentIndexChanged.connect(lambda _: self._set_param('unit', unit.currentData()))
        form.addRow('单位', unit)
        scale = QDoubleSpinBox(); scale.setRange(1e-9, 1e6); scale.setDecimals(6)
        scale.setValue(float(self.params.get('scale') or 1))
        scale.valueChanged.connect(lambda v: self._set_param('scale', float(v)))
        form.addRow('像素比例', scale)
        wiz = QPushButton('绑定制导…')
        wiz.setObjectName('measureGeomBindWizardBtn')
        wiz.setToolTip('按步骤引导操作员完成上游绑定（画布点选 / 插入字段 / 跳过）')
        wiz.clicked.connect(self._run_bind_wizard)
        form.addRow('操作员', wiz)
        tip = QLabel('绑定字段示例：lines[0]、matches[0]、circles[0]；夹角/点圆/圆圆同绑定语义。「画布点选」：先运行几何/定位，再在图像上点击目标线/点写入绑定。「绑定制导」逐步走完所有槽位。叠层随「结果显示」开关。打开即跑链：预处理→卡尺→交点/点线距→门限；换型后可切运行态单次试跑。')
        tip.setWordWrap(True); tip.setStyleSheet('color:#888;'); form.addRow(tip)
        return w

    def _manual_tab(self):
        w = QWidget(); form = QFormLayout(w); form.setContentsMargins(10, 10, 10, 10)
        if self.op in ('line_intersect', 'line_angle'):
            keys = [('x1','线1 X1'),('y1','线1 Y1'),('x2','线1 X2'),('y2','线1 Y2'),
                    ('x3','线2 X1'),('y3','线2 Y1'),('x4','线2 X2'),('y4','线2 Y2')]
        elif self.op == 'point_distance':
            keys = [('x1','点1 X'),('y1','点1 Y'),('x2','点2 X'),('y2','点2 Y')]
        elif self.op == 'point_circle_distance':
            keys = [('px','点 X'),('py','点 Y'),('cx','圆心 X'),('cy','圆心 Y'),('radius','半径')]
        elif self.op == 'circle_circle_distance':
            keys = [('cx1','圆1 X'),('cy1','圆1 Y'),('r1','圆1 半径'),
                    ('cx2','圆2 X'),('cy2','圆2 Y'),('r2','圆2 半径')]
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

        # 测量链 → 流程变量
        wv = OrangeSwitch(bool(self.params.get('writeFlowVars', True)))
        wv.toggled.connect(lambda c: self._set_param('writeFlowVars', bool(c)))
        form.addRow('写入流程变量', wv)
        default_var = {
            'line_intersect': 'intersectPt',
            'point_distance': 'pointDist',
            'point_line_distance': 'pointLineDist',
            'line_angle': 'lineAngle',
            'point_circle_distance': 'pointCircleDist',
            'circle_circle_distance': 'circleGap',
        }.get(self.op, 'measureGeom')
        out_var = QLineEdit(str(self.params.get('resultVar') or default_var))
        out_var.setObjectName('measureGeomResultVar')
        out_var.editingFinished.connect(
            lambda: self._set_param('resultVar', out_var.text().strip() or default_var)
        )
        form.addRow('结果变量前缀', out_var)
        tip_var = QLabel(
            '运行后写入 flow：{prefix} / {prefix}_x/_y/_distance/_dx/_dy/_ok/_judgeOk '
            '（与 var_calc 注入的 point_distance_* / line_intersect_* 并存）。'
        )
        tip_var.setWordWrap(True)
        tip_var.setStyleSheet('color:#888;font-size:11px;')
        form.addRow(tip_var)

        je = OrangeSwitch(bool(self.params.get('judgeEnable', False)))
        je.toggled.connect(lambda c: self._set_param('judgeEnable', bool(c)))
        form.addRow('结果判断使能', je)
        jmin = QDoubleSpinBox(); jmin.setRange(-1e9, 1e9); jmin.setDecimals(4)
        jmin.setValue(float(self.params.get('judgeMin') or 0))
        jmin.valueChanged.connect(lambda v: self._set_param('judgeMin', float(v)))
        form.addRow('判断下限', jmin)
        jmax = QDoubleSpinBox(); jmax.setRange(-1e9, 1e9); jmax.setDecimals(4)
        jmax.setValue(float(self.params.get('judgeMax') or 99999))
        jmax.valueChanged.connect(lambda v: self._set_param('judgeMax', float(v)))
        form.addRow('判断上限', jmax)
        tip_j = QLabel(
            '交点：用 status==ok 且非 parallel；点距/点线距：用 distance 落在 [下限,上限] → judgeOk。'
        )
        tip_j.setWordWrap(True)
        tip_j.setStyleSheet('color:#888;font-size:11px;')
        form.addRow(tip_j)

        tip = {
            'line_intersect': '结果：intersectX / intersectY / parallel / status / judgeOk',
            'point_distance': '结果：distance / dx / dy / status / judgeOk',
            'point_line_distance': '结果：distance / footX / footY / status / judgeOk',
            'line_angle': '结果：angleDeg / parallel / perpendicular / status / judgeOk',
            'point_circle_distance': '结果：distance / signed / centerDist / inside / status / judgeOk',
            'circle_circle_distance': '结果：distance / gap / centerDist / overlapping / status / judgeOk',
        }.get(self.op, '结果字段见引擎')
        lab = QLabel((tip or '') + ' · 叠层开关已接入 annotate_geom（关则不画）。')
        lab.setWordWrap(True); lab.setStyleSheet('color:#888;'); form.addRow(lab)

        self._live_lab = QLabel('实况：尚未运行')
        self._live_lab.setObjectName('measureGeomLiveBind')
        self._live_lab.setWordWrap(True)
        self._live_lab.setStyleSheet(
            'color:#9ad;font-size:11px;padding:6px 8px;background:#1e2228;border-radius:4px;'
        )
        form.addRow('Host 实况', self._live_lab)
        brow = QHBoxLayout()
        b_ref = QPushButton('刷新实况')
        b_ref.setObjectName('measureGeomLiveRefreshBtn')
        b_ref.clicked.connect(self._refresh_live_bind)
        brow.addWidget(b_ref)
        brow.addStretch(1)
        form.addRow(brow)
        # wave143: denser measure live chrome (judge/tolerance table)
        self._chrome_lab = QLabel('测·')
        self._chrome_lab.setObjectName('measureGeomChromeBadge')
        self._chrome_lab.setStyleSheet(
            'color:#0d0;font-size:14px;font-weight:600;padding:4px 8px;'
            'background:#1a2220;border-radius:4px;'
        )
        form.addRow('结果徽标', self._chrome_lab)

        show_tol = OrangeSwitch(bool(self.params.get('showTolerance', True)))
        show_tol.setObjectName('measureGeomShowTolerance')
        show_tol.toggled.connect(lambda c: self._set_param('showTolerance', bool(c)))
        form.addRow('显示公差带标注', show_tol)

        self._measure_table = QTableWidget(0, 6)
        self._measure_table.setObjectName('measureGeomResultTable')
        self._measure_table.setHorizontalHeaderLabels(['#', '算子', '度量', '下限', '上限', '判定'])
        self._measure_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._measure_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._measure_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._measure_table.setMaximumHeight(140)
        form.addRow('测量明细', self._measure_table)

        self._density_table = QTableWidget(0, 2)
        self._density_table.setObjectName('measureGeomDensityTable')
        self._density_table.setHorizontalHeaderLabels(['字段', '值'])
        self._density_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self._density_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._density_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._density_table.setMaximumHeight(150)
        form.addRow('密度表', self._density_table)

        brow2 = QHBoxLayout()
        b_demo = QPushButton('软演示明细')
        b_demo.setObjectName('measureGeomSoftDemoBtn')
        b_demo.setToolTip('填入确定性软演示测量结果（OpenCV 壳 · 无 Halcon）')
        b_demo.clicked.connect(self._soft_demo_measure_density)
        brow2.addWidget(b_demo)
        brow2.addStretch(1)
        form.addRow(brow2)

        tip143 = QLabel(
            '测量/卡尺铬：徽标 距✓/交✗ + 公差带 [min,max] + OK/NG 叠色（wave143）。'
            '与几何查找 L/C/R/B 铬分离 · 无 Comm/HMI 联级 · 无火花线。'
        )
        tip143.setWordWrap(True)
        tip143.setStyleSheet('color:#888;font-size:11px;')
        form.addRow(tip143)

        try:
            self._refresh_live_bind()
        except Exception:
            pass
        return w

    def set_last_result(self, result):
        """Cache engine last_result for measure density chrome (soft OK)."""
        self._last_result = result
        try:
            bag = None
            sid = self.step.get('id')
            if isinstance(result, dict):
                for rec in (result.get('results') or []):
                    if isinstance(rec, dict) and rec.get('id') == sid:
                        bag = (rec.get('output') or {}).get('result') or rec.get('result')
                        break
                if bag is None and isinstance(result.get('results'), dict):
                    hit = result['results'].get(sid)
                    if isinstance(hit, dict):
                        bag = (hit.get('output') or {}).get('result') or hit.get('result') or hit
                if bag is None and (result.get('distance') is not None or result.get('judgeOk') is not None
                                    or result.get('x') is not None or result.get('angle') is not None):
                    bag = result
            if isinstance(bag, dict):
                from desktop.measure_caliper_chrome import summarize_measure_result
                self._apply_measure_density(
                    summarize_measure_result(bag, self.params, op=self.op), source='ingest',
                )
            self._refresh_live_bind()
        except Exception:
            pass

    def _soft_demo_measure_density(self):
        from desktop.measure_caliper_chrome import soft_demo_measure_result, summarize_measure_result
        demo = soft_demo_measure_result(self.op, ok=True)
        self._apply_measure_density(summarize_measure_result(demo, self.params, op=self.op), source='soft-demo')

    def _apply_measure_density(self, summ, *, source: str = ''):
        summ = summ if isinstance(summ, dict) else {}
        chrome = summ.get('chrome') or '测·'
        lab = getattr(self, '_chrome_lab', None)
        if lab is not None:
            lab.setText(str(chrome))
            jok = summ.get('judgeOk')
            if jok is True:
                lab.setStyleSheet(
                    'color:#0d0;font-size:14px;font-weight:600;padding:4px 8px;'
                    'background:#1a2220;border-radius:4px;'
                )
            elif jok is False:
                lab.setStyleSheet(
                    'color:#f55;font-size:14px;font-weight:600;padding:4px 8px;'
                    'background:#2a1a1a;border-radius:4px;'
                )
        table = getattr(self, '_measure_table', None)
        if table is not None:
            table.setRowCount(0)
            for r in (summ.get('rows') or []):
                i = table.rowCount()
                table.insertRow(i)
                st = str(r.get('judgeStatus') or '—')
                cells = (
                    str(r.get('index') or i + 1),
                    str(r.get('opLabel') or r.get('op') or self.op),
                    str(r.get('metricText') or '—'),
                    str(r.get('judgeMin') if r.get('judgeMin') is not None else '—'),
                    str(r.get('judgeMax') if r.get('judgeMax') is not None else '—'),
                    st,
                )
                for c, t in enumerate(cells):
                    it = QTableWidgetItem(t)
                    if st == 'OK':
                        it.setForeground(Qt.GlobalColor.green)
                    elif st == 'NG':
                        it.setForeground(Qt.GlobalColor.red)
                    table.setItem(i, c, it)
        dt = getattr(self, '_density_table', None)
        if dt is not None:
            dt.setRowCount(0)
            for r in (summ.get('densityRows') or []):
                i = dt.rowCount()
                dt.insertRow(i)
                dt.setItem(i, 0, QTableWidgetItem(str(r.get('key') or '')))
                dt.setItem(i, 1, QTableWidgetItem(str(r.get('value'))))
        live = getattr(self, '_live_lab', None)
        if live is not None and summ.get('summary'):
            src = f' · 源:{source}' if source else ''
            live.setText(f"实况：[{chrome}] {summ.get('summary')}{src}")
        self._last_measure_density = dict(summ)

    def _refresh_live_bind(self):
        """测量链 last_result → Host 显示字段。"""
        lab = getattr(self, '_live_lab', None)
        if lab is None:
            return
        try:
            from desktop.upstream_field_picker import host_last_result
            lr = host_last_result(self) or {}
        except Exception:
            lr = {}
        sid = self.step.get('id')
        hit = None
        for rec in (lr.get('results') or []):
            if isinstance(rec, dict) and rec.get('id') == sid:
                hit = rec
                break
        # also map-style
        if not hit and isinstance(lr.get('results'), dict):
            hit = lr['results'].get(sid)
        if not hit:
            # bind summary from params even without run
            binds = []
            for k in ('line1From', 'line2From', 'point1From', 'point2From', 'pointFrom', 'lineFrom', 'circleFrom', 'circle1From', 'circle2From'):
                if self.params.get(k):
                    binds.append(f'{k}={self.params.get(k)}')
            lab.setText(
                '实况：尚无本模块运行结果 · 绑定 '
                + (' · '.join(binds) if binds else '（未绑定）')
            )
            return
        res = (hit.get('output') or {}).get('result') or hit.get('result') or {}
        bits = []
        for k in ('status', 'distance', 'angleDeg', 'intersectX', 'intersectY', 'dx', 'dy',
                  'footX', 'footY', 'gap', 'centerDist', 'signed', 'inside', 'overlapping',
                  'parallel', 'perpendicular', 'judgeOk', 'judgeStatus', 'unit'):
            if k in res and res[k] is not None:
                bits.append(f'{k}={res[k]}')
        flow = ((lr.get('variables') or {}).get('flow') or {})
        prefix = str(self.params.get('resultVar') or '')
        if prefix:
            for suffix in ('', '_x', '_y', '_distance', '_ok', '_judgeOk'):
                key = prefix if suffix == '' else prefix + suffix
                if key in flow:
                    bits.append(f'flow.{key}={flow[key]}')
        # also injected op scalars
        for k, v in list(flow.items())[:40]:
            if any(k.startswith(p) for p in (
                'point_distance', 'line_intersect', 'point_line', 'line_angle',
                'point_circle', 'circle_circle', 'circleGap', 'pointCircle', 'lineAngle',
            )):
                if k not in [b.split('=')[0].replace('flow.', '') for b in bits]:
                    bits.append(f'flow.{k}={v}')
        lab.setText('实况：' + (' · '.join(bits[:14]) if bits else str(list(res.keys())[:8])))
        try:
            from desktop.measure_caliper_chrome import summarize_measure_result
            summ = summarize_measure_result(res, self.params, op=self.op)
            self._apply_measure_density(summ, source='engine')
        except Exception:
            pass


    def _bind_slots(self):
        """Ordered bind slots for guided wizard: (label, id_key, field_key, default_field)."""
        if self.op in ('line_intersect', 'line_angle'):
            return [
                ('直线1', 'line1From', 'line1Field', 'lines[0]'),
                ('直线2', 'line2From', 'line2Field', 'lines[0]'),
            ]
        if self.op == 'point_distance':
            return [
                ('点1', 'point1From', 'point1Field', 'matches[0]'),
                ('点2', 'point2From', 'point2Field', 'matches[0]'),
            ]
        if self.op == 'point_circle_distance':
            return [
                ('点', 'pointFrom', 'pointField', 'matches[0]'),
                ('圆', 'circleFrom', 'circleField', 'circles[0]'),
            ]
        if self.op == 'circle_circle_distance':
            return [
                ('圆1', 'circle1From', 'circle1Field', 'circles[0]'),
                ('圆2', 'circle2From', 'circle2Field', 'circles[0]'),
            ]
        return [
            ('点', 'pointFrom', 'pointField', 'matches[0]'),
            ('直线', 'lineFrom', 'lineField', 'lines[0]'),
        ]

    def _run_bind_wizard(self):
        """Short guided bind flow for operators (VM-like 绑定向导)."""
        from PySide6.QtWidgets import (
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
            QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
            QComboBox, QLineEdit, QMessageBox, QProgressBar,
        )
        slots = self._bind_slots()
        if not slots:
            QMessageBox.information(self, '绑定制导', '当前算子无需绑定槽位。')
            return
        # Force bind mode
        if (self.params.get('mode') or 'bind') != 'bind':
            self._set_param('mode', 'bind')

        dlg = QDialog(self)
        dlg.setWindowTitle('几何测量 · 绑定制导')
        dlg.setMinimumWidth(460)
        lay = QVBoxLayout(dlg)
        head = QLabel('按步骤完成上游绑定。可「画布点选」或「插入字段」；「跳过」保留现值。')
        head.setWordWrap(True)
        head.setStyleSheet('color:#888;')
        lay.addWidget(head)
        prog = QProgressBar()
        prog.setRange(0, len(slots))
        prog.setValue(0)
        prog.setFormat('%v / %m')
        lay.addWidget(prog)
        step_lab = QLabel('')
        step_lab.setStyleSheet('font-weight:700;font-size:13px;')
        lay.addWidget(step_lab)
        status = QLabel('')
        status.setWordWrap(True)
        status.setStyleSheet('color:#6eb6ff;font-size:11px;')
        lay.addWidget(status)

        src_box = QComboBox()
        for data, lab in self._step_items():
            src_box.addItem(lab, data)
        lay.addWidget(QLabel('来源模块'))
        lay.addWidget(src_box)
        field_edit = QLineEdit()
        lay.addWidget(QLabel('字段路径'))
        lay.addWidget(field_edit)

        state = {'i': 0, 'done': []}

        def _load_slot():
            i = state['i']
            if i >= len(slots):
                return
            label, id_key, field_key, default_field = slots[i]
            step_lab.setText(f'步骤 {i+1}/{len(slots)} · 绑定「{label}」')
            prog.setValue(i)
            cur_id = self.params.get(id_key) or ''
            idx = src_box.findData(cur_id)
            if idx < 0 and cur_id:
                src_box.addItem('已丢失：' + cur_id, cur_id)
                idx = src_box.findData(cur_id)
            src_box.setCurrentIndex(max(0, idx))
            field_edit.setText(str(self.params.get(field_key) or default_field))
            kind = self._bind_kind(default_field)
            status.setText(f'当前：{label}（{kind}） · 来源={cur_id or "（未绑定）"} · 字段={field_edit.text()}')

        def _apply_current():
            i = state['i']
            if i >= len(slots):
                return
            label, id_key, field_key, default_field = slots[i]
            nid = src_box.currentData() or ''
            fp = field_edit.text().strip() or default_field
            self._set_param(id_key, nid)
            self._set_param(field_key, fp)
            state['done'].append(label)
            status.setText(f'已写入 {label} → {nid or "（空）"}.{fp}')

        def _next():
            _apply_current()
            state['i'] += 1
            if state['i'] >= len(slots):
                prog.setValue(len(slots))
                QMessageBox.information(
                    dlg, '绑定制导',
                    '已完成：' + '、'.join(state['done']) + '\n可在基本参数中复查或再跑制导。',
                )
                dlg.accept()
                return
            _load_slot()

        def _skip():
            i = state['i']
            if i < len(slots):
                state['done'].append(slots[i][0] + '(跳过)')
            state['i'] += 1
            if state['i'] >= len(slots):
                prog.setValue(len(slots))
                dlg.accept()
                return
            _load_slot()

        def _pick_field():
            i = state['i']
            if i >= len(slots):
                return
            label, id_key, field_key, default_field = slots[i]
            from desktop.upstream_field_picker import fill_line_from_picker
            picked = fill_line_from_picker(
                self, self.project, self.step.get('id'), field_edit, self._set_param, field_key, field_only=True,
            )
            if not picked:
                return
            nid, _field, _token = picked
            if nid:
                idx = src_box.findData(nid)
                if idx < 0:
                    src_box.addItem(nid, nid)
                    idx = src_box.findData(nid)
                if idx >= 0:
                    src_box.setCurrentIndex(idx)
                self._set_param(id_key, nid)
            status.setText(f'已挑选字段 → {field_edit.text()}')

        def _canvas():
            i = state['i']
            if i >= len(slots):
                return
            label, id_key, field_key, default_field = slots[i]
            host = self.window()
            begin = getattr(host, 'begin_geom_canvas_pick', None) if host is not None else None
            if not callable(begin):
                QMessageBox.information(dlg, '画布点选', '当前窗口不支持画布点选（需主工作台）。')
                return
            kind = self._bind_kind(default_field)

            def _on_hit(hit):
                if not hit:
                    return
                nid = hit.get('stepId') or ''
                field_path = hit.get('field') or default_field
                if nid:
                    idx = src_box.findData(nid)
                    if idx < 0:
                        src_box.addItem(hit.get('stepName') or nid, nid)
                        idx = src_box.findData(nid)
                    if idx >= 0:
                        src_box.setCurrentIndex(idx)
                    self._set_param(id_key, nid)
                field_edit.setText(field_path)
                self._set_param(field_key, field_path)
                status.setText(f'画布点选 → {nid}.{field_path} · 点「下一步」确认')

            # Keep wizard visible; canvas pick is modal-ish via host status
            begin(kind, _on_hit, status=f'制导点选{label}（{kind}）')

        row = QHBoxLayout()
        b_field = QPushButton('插入上游字段')
        b_field.clicked.connect(_pick_field)
        b_canvas = QPushButton('画布点选')
        b_canvas.setObjectName('measureGeomWizardCanvasBtn')
        b_canvas.clicked.connect(_canvas)
        b_skip = QPushButton('跳过')
        b_skip.clicked.connect(_skip)
        b_next = QPushButton('下一步')
        b_next.setObjectName('primaryButton')
        b_next.clicked.connect(_next)
        b_cancel = QPushButton('取消')
        b_cancel.clicked.connect(dlg.reject)
        for b in (b_field, b_canvas, b_skip, b_next, b_cancel):
            row.addWidget(b)
        lay.addLayout(row)
        _load_slot()
        dlg.exec()

