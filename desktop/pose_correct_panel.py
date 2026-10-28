"""位置修正（pose_correct）属性浮窗 — VisionMaster p=9 细妆.

典型链：模板匹配 → 位置修正 → 后续检测 / 预处理 ROI。
设计态：基准位姿 · 夹具坐标系 · 模板-夹具绑定 · 结果实况。
运行时：透传图像并输出 fixtureX/Y/Angle + 仿射矩阵（软 OpenCV 链，无 Halcon）。
"""
from __future__ import annotations

from copy import deepcopy
import math

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTabWidget, QFormLayout, QLineEdit,
    QPushButton, QComboBox, QDoubleSpinBox, QScrollArea, QFrame, QSpinBox,
    QTextEdit, QCheckBox,
)

from desktop.widgets.switch import OrangeSwitch


def normalize_pose_correct_params(params=None):
    p = deepcopy(params or {})
    p.setdefault('fixtureSource', 'auto')  # auto | manual | bind
    p.setdefault('baseX', 0.0)
    p.setdefault('baseY', 0.0)
    p.setdefault('baseAngle', 0.0)
    p.setdefault('baseScale', 1.0)
    p.setdefault('followRoi', True)
    p.setdefault('outputCoord', 'fixture')  # fixture | image
    p.setdefault('bindStepId', '')
    p.setdefault('bindField', 'matches[0]')
    p.setdefault('axisLength', 40.0)
    p.setdefault('showAxes', True)
    p.setdefault('showOrigin', True)
    p.setdefault('showMatrix', True)
    p.setdefault('writeFlowVars', True)
    p.setdefault('resultVar', 'fixture')
    p.setdefault('autoBindLocate', True)
    return p


def soft_fixture_matrix(x, y, angle_deg, scale=1.0):
    """2D similarity → row-major 3x3 (design-time preview; mirrors flow-control)."""
    s = float(scale) if scale and math.isfinite(float(scale)) else 1.0
    rad = math.radians(float(angle_deg) or 0.0)
    c, sn = math.cos(rad) * s, math.sin(rad) * s
    return [
        c, -sn, float(x) or 0.0,
        sn, c, float(y) or 0.0,
        0.0, 0.0, 1.0,
    ]


class PoseCorrectPanel(QWidget):
    """四 Tab：基本参数 / 基准位姿 / 夹具坐标系 / 输出与实况."""
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
            '对齐 VisionMaster「位置修正」：用上游匹配位姿建立夹具坐标系，校正后续 ROI。'
            '软链 OpenCV 模板匹配 → 本节点；无 Halcon / 无机械手 SDK。'
        )
        hint.setObjectName('dialogHint')
        hint.setWordWrap(True)
        hint.setStyleSheet('color:#666;padding:8px 10px 4px;')
        root.addWidget(hint)

        self.tabs = QTabWidget()
        self.tabs.setObjectName('poseCorrectTabs')
        root.addWidget(self.tabs, 1)
        self.tabs.addTab(self._wrap(self._basic_tab()), '基本参数')
        self.tabs.addTab(self._wrap(self._pose_tab()), '基准位姿')
        self.tabs.addTab(self._wrap(self._frame_tab()), '夹具坐标系')
        self.tabs.addTab(self._wrap(self._out_tab()), '输出与实况')

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
        nid, field, _token = picked
        self._bind_id.setText(nid)
        self._bind_field.setText(field)
        self._set_param('bindStepId', nid)
        self._set_param('bindField', field)
        self._set_param('fixtureSource', 'bind')
        src = getattr(self, '_fixture_src', None)
        if src is not None:
            idx = src.findData('bind')
            if idx >= 0 and src.currentIndex() != idx:
                src.blockSignals(True)
                src.setCurrentIndex(idx)
                src.blockSignals(False)
        self._refresh_matrix_preview()
        self._refresh_bind_status()

    def _auto_bind_locate(self):
        """Prefer nearest prior locate step → bind matches[0]."""
        steps = list((self.project or {}).get('steps') or [])
        my_id = self.step.get('id')
        locate_id = ''
        for s in steps:
            if not isinstance(s, dict):
                continue
            if s.get('id') == my_id:
                break
            if s.get('operation') == 'locate':
                locate_id = s.get('id') or ''
        if not locate_id:
            # fall back: any locate in project
            for s in reversed(steps):
                if isinstance(s, dict) and s.get('operation') == 'locate' and s.get('id') != my_id:
                    locate_id = s.get('id') or ''
                    break
        if not locate_id:
            self._bind_status.setText('自动绑定：流程中无「模板匹配定位」节点')
            return
        self._bind_id.setText(locate_id)
        self._bind_field.setText('matches[0]')
        self._set_param('bindStepId', locate_id)
        self._set_param('bindField', 'matches[0]')
        self._set_param('fixtureSource', 'bind' if self.params.get('fixtureSource') == 'manual' else self.params.get('fixtureSource') or 'auto')
        # keep auto if was auto; only force bind when user was on manual
        if self.params.get('fixtureSource') == 'manual':
            self._set_param('fixtureSource', 'bind')
            src = getattr(self, '_fixture_src', None)
            if src is not None:
                idx = src.findData('bind')
                if idx >= 0:
                    src.blockSignals(True)
                    src.setCurrentIndex(idx)
                    src.blockSignals(False)
        else:
            # ensure auto + bindStep filled
            self._set_param('fixtureSource', 'auto')
            src = getattr(self, '_fixture_src', None)
            if src is not None:
                idx = src.findData('auto')
                if idx >= 0:
                    src.blockSignals(True)
                    src.setCurrentIndex(idx)
                    src.blockSignals(False)
        name = next((s.get('name') for s in steps if s.get('id') == locate_id), locate_id)
        self._bind_status.setText(f'已绑定上游定位：{name} · matches[0]')
        self._refresh_matrix_preview()
        self._refresh_bind_status()

    def _emit(self):
        self.step['params'] = deepcopy(self.params)
        self.changed.emit(deepcopy(self.step))

    def _set_param(self, key, value):
        if self.params.get(key) != value:
            self.params[key] = deepcopy(value)
            self._emit()
            if key in ('baseX', 'baseY', 'baseAngle', 'baseScale', 'fixtureSource'):
                self._refresh_matrix_preview()
            if key in ('baseAngle', 'axisLength', 'baseX', 'baseY'):
                self._refresh_frame_hint()

    def _set_top(self, key, value):
        if self.step.get(key) != value:
            self.step[key] = deepcopy(value)
            self._emit()

    def _refresh_incomplete(self):
        banner = getattr(self, '_incomplete_banner', None)
        if banner is None:
            return
        from desktop.config_status import step_incomplete, step_incomplete_reason
        bang = step_incomplete(self.step, self.project)
        if bang:
            why = step_incomplete_reason(self.step, self.project) or '请检查输入源'
            banner.setText('⚠ 组件参数未配置完整：' + why)
            banner.setStyleSheet(
                'color:#c62828;background:#ffebee;padding:6px 8px;border-radius:3px;'
            )
        else:
            banner.setText('组件配置完成')
            banner.setStyleSheet('color:#2e7d32;padding:4px 8px;')
        banner.setObjectName('incompleteBanner')
        banner.setVisible(True)

    def _basic_tab(self):
        w = QWidget()
        form = QFormLayout(w)
        form.setContentsMargins(10, 10, 10, 10)
        form.setSpacing(8)

        self._incomplete_banner = QLabel()
        form.addRow(self._incomplete_banner)
        self._refresh_incomplete()

        name = QLineEdit(self.step.get('name') or '位置修正')
        name.setObjectName('poseCorrectName')
        name.setMaxLength(80)
        name.editingFinished.connect(lambda: self._set_top('name', name.text()))
        form.addRow('模块名称', name)

        image_from = QComboBox()
        image_from.setObjectName('poseCorrectImageFrom')
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
        soft_ops = ('locate', 'preprocess', 'geometry', 'distort_correct', 'output_image')
        for s in self.project.get('steps', []):
            if s.get('id') == self.step.get('id'):
                continue
            if s.get('operation') in soft_ops and image_from.findData(s['id']) < 0:
                image_from.addItem(_sub_label(s['id']) + '（可选）', s['id'])
        if image_from.findData('source') < 0:
            image_from.addItem(_sub_label('source') + '（可选）', 'source')
        current = self.step.get('imageFrom')
        if current and image_from.findData(current) < 0:
            image_from.addItem('已断开：' + _sub_label(current), current)
        image_from.setCurrentIndex(max(0, image_from.findData(current)))
        image_from.currentIndexChanged.connect(
            lambda _: (self._set_top('imageFrom', image_from.currentData()), self._refresh_incomplete())
        )
        form.addRow('输入源', image_from)

        src = QComboBox()
        src.setObjectName('poseCorrectFixtureSource')
        src.addItem('自动（上游匹配结果）', 'auto')
        src.addItem('手动基准位姿', 'manual')
        src.addItem('绑定步骤字段', 'bind')
        idx = max(0, src.findData(self.params.get('fixtureSource') or 'auto'))
        src.setCurrentIndex(idx)
        src.currentIndexChanged.connect(lambda _: self._set_param('fixtureSource', src.currentData()))
        self._fixture_src = src
        form.addRow('位姿来源', src)

        follow = OrangeSwitch(bool(self.params.get('followRoi', True)))
        follow.setObjectName('poseCorrectFollowRoi')
        follow.toggled.connect(lambda c: self._set_param('followRoi', bool(c)))
        form.addRow('跟随 ROI', follow)

        auto = OrangeSwitch(bool(self.params.get('autoBindLocate', True)))
        auto.setObjectName('poseCorrectAutoBindLocate')
        auto.toggled.connect(lambda c: self._set_param('autoBindLocate', bool(c)))
        form.addRow('优先自动绑定位', auto)

        row = QHBoxLayout()
        btn = QPushButton('一键绑定上游定位')
        btn.setObjectName('poseCorrectAutoBindBtn')
        btn.setToolTip('查找流程中最近的模板匹配定位 → bindStepId + matches[0]')
        btn.clicked.connect(self._auto_bind_locate)
        row.addWidget(btn)
        row.addStretch(1)
        form.addRow(row)

        self._bind_status = QLabel(self._bind_summary())
        self._bind_status.setObjectName('poseCorrectBindStatus')
        self._bind_status.setWordWrap(True)
        self._bind_status.setStyleSheet(
            'color:#9ad;font-size:11px;padding:6px 8px;background:#1e2228;border-radius:4px;'
        )
        form.addRow('模板-夹具绑定', self._bind_status)

        tip = QLabel('建议上游为「模板匹配定位」；未连线时画布显示红叹号。')
        tip.setWordWrap(True)
        tip.setStyleSheet('color:#888;')
        form.addRow(tip)
        return w

    def _bind_summary(self) -> str:
        src = self.params.get('fixtureSource') or 'auto'
        bid = str(self.params.get('bindStepId') or '').strip()
        field = str(self.params.get('bindField') or 'matches[0]')
        if src == 'manual':
            return f'来源=手动 · 基准 ({self.params.get("baseX")}, {self.params.get("baseY")}, ∠{self.params.get("baseAngle")}°)'
        if bid:
            name = next(
                (s.get('name') for s in (self.project.get('steps') or []) if s.get('id') == bid),
                bid,
            )
            return f'来源={src} · 绑定 {name}.{field}'
        return f'来源={src} · 运行时自动取最近 locate.matches[0]'

    def _refresh_bind_status(self):
        lab = getattr(self, '_bind_status', None)
        if lab is not None:
            lab.setText(self._bind_summary())

    def _pose_tab(self):
        w = QWidget()
        form = QFormLayout(w)
        form.setContentsMargins(10, 10, 10, 10)
        form.setSpacing(8)

        tip = QLabel('手动模式下填写基准 X/Y/角度/比例；自动模式运行时取上游 matches[0]。')
        tip.setWordWrap(True)
        tip.setStyleSheet('color:#555;')
        form.addRow(tip)

        for key, label, lo, hi, step, obj in (
            ('baseX', '基准 X', -1e6, 1e6, 0.1, 'poseCorrectBaseX'),
            ('baseY', '基准 Y', -1e6, 1e6, 0.1, 'poseCorrectBaseY'),
            ('baseAngle', '基准角度 (°)', -360, 360, 0.1, 'poseCorrectBaseAngle'),
            ('baseScale', '基准比例', 0.01, 10.0, 0.01, 'poseCorrectBaseScale'),
        ):
            sp = QDoubleSpinBox()
            sp.setObjectName(obj)
            sp.setRange(lo, hi)
            sp.setDecimals(4)
            sp.setSingleStep(step)
            sp.setValue(float(self.params.get(key) or (1.0 if key == 'baseScale' else 0)))
            sp.valueChanged.connect(lambda v, k=key: self._set_param(k, float(v)))
            form.addRow(label, sp)

        bind_id = QLineEdit(str(self.params.get('bindStepId') or ''))
        bind_id.setObjectName('poseCorrectBindStepId')
        bind_id.setPlaceholderText('上游步骤 id（绑定模式）')
        bind_id.editingFinished.connect(
            lambda: (self._set_param('bindStepId', bind_id.text().strip()), self._refresh_bind_status())
        )
        self._bind_id = bind_id
        form.addRow('绑定步骤', bind_id)

        bind_row = QHBoxLayout()
        bind_field = QLineEdit(str(self.params.get('bindField') or 'matches[0]'))
        bind_field.setObjectName('poseCorrectBindField')
        bind_field.editingFinished.connect(
            lambda: (self._set_param('bindField', bind_field.text().strip()), self._refresh_bind_status())
        )
        self._bind_field = bind_field
        pick = QPushButton('插入上游字段')
        pick.setObjectName('poseCorrectPickUpstreamBtn')
        pick.setToolTip('挑选上游模块与字段，写入绑定步骤/字段')
        pick.clicked.connect(self._insert_upstream_field)
        bind_row.addWidget(bind_field, 1)
        bind_row.addWidget(pick)
        form.addRow('绑定字段', bind_row)

        self._matrix_preview = QLabel()
        self._matrix_preview.setObjectName('poseCorrectMatrixPreview')
        self._matrix_preview.setWordWrap(True)
        self._matrix_preview.setStyleSheet(
            'color:#cde;font-family:monospace;font-size:11px;'
            'padding:8px;background:#161a20;border-radius:4px;'
        )
        form.addRow('仿射预览', self._matrix_preview)
        self._refresh_matrix_preview()
        return w

    def _refresh_matrix_preview(self):
        lab = getattr(self, '_matrix_preview', None)
        if lab is None:
            return
        m = soft_fixture_matrix(
            self.params.get('baseX') or 0,
            self.params.get('baseY') or 0,
            self.params.get('baseAngle') or 0,
            self.params.get('baseScale') or 1,
        )
        lab.setText(
            f'[{m[0]:.4f}  {m[1]:.4f}  {m[2]:.2f}]\n'
            f'[{m[3]:.4f}  {m[4]:.4f}  {m[5]:.2f}]\n'
            f'[{m[6]:.0f}       {m[7]:.0f}       {m[8]:.0f}]'
            f'  · 来源={self.params.get("fixtureSource") or "auto"}（手动基准预览；运行时以绑定位姿为准）'
        )

    def _frame_tab(self):
        w = QWidget()
        form = QFormLayout(w)
        form.setContentsMargins(10, 10, 10, 10)
        form.setSpacing(8)

        tip = QLabel(
            '夹具坐标系（fixture frame）：原点=匹配中心，X 轴沿角度方向。'
            '设计态开关供画布/结果叠加；引擎透传图像并输出 matrix / axis 字段。'
        )
        tip.setWordWrap(True)
        tip.setStyleSheet('color:#555;')
        form.addRow(tip)

        axis = QDoubleSpinBox()
        axis.setObjectName('poseCorrectAxisLength')
        axis.setRange(4, 2000)
        axis.setDecimals(1)
        axis.setValue(float(self.params.get('axisLength') or 40))
        axis.valueChanged.connect(lambda v: self._set_param('axisLength', float(v)))
        form.addRow('坐标轴长度 (px)', axis)

        for key, lab, obj in (
            ('showAxes', '显示 XY 轴', 'poseCorrectShowAxes'),
            ('showOrigin', '显示原点十字', 'poseCorrectShowOrigin'),
            ('showMatrix', '结果中附带矩阵', 'poseCorrectShowMatrix'),
        ):
            sw = OrangeSwitch(bool(self.params.get(key, True)))
            sw.setObjectName(obj)
            sw.toggled.connect(lambda c, k=key: self._set_param(k, bool(c)))
            form.addRow(lab, sw)

        coord = QComboBox()
        coord.setObjectName('poseCorrectOutputCoord')
        coord.addItem('夹具坐标系 (fixture)', 'fixture')
        coord.addItem('图像坐标系 (image)', 'image')
        idx = max(0, coord.findData(self.params.get('outputCoord') or 'fixture'))
        coord.setCurrentIndex(idx)
        coord.currentIndexChanged.connect(lambda _: self._set_param('outputCoord', coord.currentData()))
        form.addRow('输出坐标系', coord)

        self._frame_live = QLabel('坐标轴预览：运行后刷新实况页')
        self._frame_live.setObjectName('poseCorrectFrameLive')
        self._frame_live.setWordWrap(True)
        self._frame_live.setStyleSheet(
            'color:#9ad;font-size:11px;padding:6px 8px;background:#1e2228;border-radius:4px;'
        )
        form.addRow('轴向量提示', self._frame_live)
        self._refresh_frame_hint()
        return w

    def _refresh_frame_hint(self):
        lab = getattr(self, '_frame_live', None)
        if lab is None:
            return
        ang = float(self.params.get('baseAngle') or 0)
        L = float(self.params.get('axisLength') or 40)
        rad = math.radians(ang)
        dx, dy = L * math.cos(rad), L * math.sin(rad)
        lab.setText(
            f'手动基准轴：X=({dx:.1f},{dy:.1f}) · Y=({-dy:.1f},{dx:.1f}) · L={L:.0f}px'
            '（图像 y 向下；运行绑定后以 match 角度为准）'
        )

    def _out_tab(self):
        w = QWidget()
        form = QFormLayout(w)
        form.setContentsMargins(10, 10, 10, 10)
        form.setSpacing(8)

        tip = QLabel(
            '运行结果字段：fixtureX / fixtureY / fixtureAngle / fixtureScale / matrix / '
            'axisX / axisY / boundOk / status。'
        )
        tip.setWordWrap(True)
        tip.setStyleSheet('color:#888;')
        form.addRow(tip)

        wv = OrangeSwitch(bool(self.params.get('writeFlowVars', True)))
        wv.setObjectName('poseCorrectWriteFlowVars')
        wv.toggled.connect(lambda c: self._set_param('writeFlowVars', bool(c)))
        form.addRow('写入流程变量', wv)

        out_var = QLineEdit(str(self.params.get('resultVar') or 'fixture'))
        out_var.setObjectName('poseCorrectResultVar')
        out_var.setPlaceholderText('flow 前缀，如 fixture')
        out_var.editingFinished.connect(
            lambda: self._set_param('resultVar', out_var.text().strip() or 'fixture')
        )
        form.addRow('结果变量前缀', out_var)

        self._result_box = QTextEdit()
        self._result_box.setObjectName('poseCorrectResultBox')
        self._result_box.setReadOnly(True)
        self._result_box.setMaximumHeight(120)
        self._result_box.setPlaceholderText('最近一次位置修正结果…')
        form.addRow('结果预览', self._result_box)

        self._live_lab = QLabel('实况：尚未运行')
        self._live_lab.setObjectName('poseCorrectLiveBind')
        self._live_lab.setWordWrap(True)
        self._live_lab.setStyleSheet(
            'color:#9ad;font-size:11px;padding:6px 8px;background:#1e2228;border-radius:4px;'
        )
        form.addRow('Host 实况', self._live_lab)

        brow = QHBoxLayout()
        b_ref = QPushButton('刷新实况')
        b_ref.setObjectName('poseCorrectLiveRefreshBtn')
        b_ref.clicked.connect(self._refresh_live)
        brow.addWidget(b_ref)
        brow.addStretch(1)
        form.addRow(brow)
        try:
            self._refresh_live()
        except Exception:
            pass
        return w

    def _host_last(self):
        from desktop.upstream_field_picker import host_last_result
        return host_last_result(self) or {}

    def _find_step_result(self):
        last = self._host_last()
        sid = self.step.get('id')
        results = last.get('results') if isinstance(last, dict) else None
        if isinstance(results, list):
            for row in results:
                if not isinstance(row, dict):
                    continue
                if row.get('id') == sid or row.get('stepId') == sid:
                    out = row.get('output') or row.get('result') or row
                    if isinstance(out, dict) and 'result' in out and isinstance(out['result'], dict):
                        return out['result']
                    return out if isinstance(out, dict) else None
        # map form
        if isinstance(results, dict) and sid in results:
            out = results[sid]
            if isinstance(out, dict) and 'result' in out:
                return out['result']
            return out
        return None

    def _refresh_live(self):
        lab = getattr(self, '_live_lab', None)
        if lab is None:
            return
        res = self._find_step_result()
        if not res:
            lab.setText('实况：尚无本模块运行结果')
            if getattr(self, '_result_box', None):
                self._result_box.setPlainText('')
            return
        bits = []
        for k in (
            'status', 'boundOk', 'fixtureX', 'fixtureY', 'fixtureAngle', 'fixtureScale',
            'boundFrom', 'score', 'outputCoord', 'followRoi',
        ):
            if k in res and res[k] is not None:
                bits.append(f'{k}={res[k]}')
        if getattr(self, '_result_box', None):
            import json
            try:
                self._result_box.setPlainText(json.dumps(res, ensure_ascii=False, indent=2)[:2000])
            except Exception:
                self._result_box.setPlainText(str(res)[:2000])
        flow = ((self._host_last().get('variables') or {}).get('flow') or {})
        prefix = str(self.params.get('resultVar') or 'fixture')
        for suffix in ('', '_x', '_y', '_angle', '_scale', '_ok', '_status'):
            key = prefix if suffix == '' else prefix + suffix
            if key in flow:
                bits.append(f'flow.{key}={flow[key]}')
        lab.setText('实况：' + (' · '.join(bits[:14]) if bits else str(list(res.keys())[:8])))
        # update frame hint from live angle when present
        fl = getattr(self, '_frame_live', None)
        if fl is not None and res.get('fixtureAngle') is not None:
            try:
                ang = float(res.get('fixtureAngle') or 0)
                L = float(self.params.get('axisLength') or 40)
                rad = math.radians(ang)
                dx, dy = L * math.cos(rad), L * math.sin(rad)
                fl.setText(
                    f'实况轴：X=({dx:.1f},{dy:.1f}) · Y=({-dy:.1f},{dx:.1f}) · '
                    f'原点=({res.get("fixtureX")},{res.get("fixtureY")})'
                )
            except Exception:
                pass
