# -*- coding: utf-8 -*-
"""缺陷检测 / OCR 结果显示与判定面板（OpenCV 壳 · 无 Halcon）。

与 MeasureGeomPanel / LocateResultPanel 同风格：参数 + 结果叠层 + Host 实况绑定。
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QLabel, QComboBox, QDoubleSpinBox,
    QSpinBox, QLineEdit, QHBoxLayout, QPushButton, QTabWidget, QTextEdit,
)

from desktop.widgets.switch import OrangeSwitch


def _norm_defects(params: dict | None) -> dict:
    p = dict(params or {})
    p.setdefault('method', 'absdiff')
    p.setdefault('threshold', 30)
    p.setdefault('minArea', 50)
    p.setdefault('maxCount', 200)
    p.setdefault('blur', 3)
    p.setdefault('showOverlay', True)
    p.setdefault('showBoxes', True)
    p.setdefault('showLabels', True)
    p.setdefault('resultVar', 'defects')
    p.setdefault('writeFlowVars', True)
    p.setdefault('judgeEnable', True)
    p.setdefault('judgeMaxCount', 0)  # 0 = any defect → NG when enable
    p.setdefault('judgeMaxRatio', 0.05)
    return p


def _norm_ocr(params: dict | None) -> dict:
    p = dict(params or {})
    p.setdefault('lang', 'ch')
    p.setdefault('minConfidence', 0.5)
    p.setdefault('maxItems', 50)
    p.setdefault('showOverlay', True)
    p.setdefault('showBoxes', True)
    p.setdefault('showText', True)
    p.setdefault('resultVar', 'ocr')
    p.setdefault('writeFlowVars', True)
    p.setdefault('judgeEnable', False)
    p.setdefault('expectedText', '')
    p.setdefault('judgeMinConfidence', 0.5)
    return p


class _RecognizeShell(QWidget):
    changed = Signal(dict)

    def __init__(self, step: dict, definition=None, project=None, parent=None):
        super().__init__(parent)
        from copy import deepcopy as _dc
        self.step = _dc(step) if isinstance(step, dict) else {}
        self.definition = definition or {}
        self.project = project or {}
        self.params = dict(self.step.get('params') or {})
        self._live_lab = None
        self._build()

    def _emit(self):
        from copy import deepcopy as _dc
        self.step['params'] = _dc(self.params)
        self.changed.emit(_dc(self.step))

    def _set_param(self, key, value):
        if self.params.get(key) != value:
            self.params[key] = value
            self._emit()

    def _host_last(self) -> dict:
        try:
            from desktop.upstream_field_picker import host_last_result
            return host_last_result(self) or {}
        except Exception:
            return {}

    def _find_step_result(self) -> dict:
        lr = self._host_last()
        sid = self.step.get('id')
        for rec in (lr.get('results') or []):
            if isinstance(rec, dict) and rec.get('id') == sid:
                return (rec.get('output') or {}).get('result') or rec.get('result') or {}
        if isinstance(lr.get('results'), dict) and sid in lr['results']:
            hit = lr['results'][sid]
            if isinstance(hit, dict):
                return (hit.get('output') or {}).get('result') or hit.get('result') or hit
        return {}


class DefectsPanel(_RecognizeShell):
    """缺陷检测：阈值 + 结果显示 + 判定 + 流程变量。"""

    def _build(self):
        self.params = _norm_defects(self.params)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        tabs = QTabWidget()
        tabs.addTab(self._params_tab(), '参数')
        tabs.addTab(self._result_tab(), '结果与判定')
        root.addWidget(tabs)

    def _params_tab(self):
        w = QWidget(); form = QFormLayout(w); form.setContentsMargins(10, 10, 10, 10)
        method = QComboBox(); method.addItems(['absdiff', 'threshold', 'blob'])
        method.setCurrentText(str(self.params.get('method') or 'absdiff'))
        method.currentTextChanged.connect(lambda v: self._set_param('method', v))
        form.addRow('方法', method)
        thr = QSpinBox(); thr.setRange(1, 255); thr.setValue(int(self.params.get('threshold') or 30))
        thr.valueChanged.connect(lambda v: self._set_param('threshold', int(v)))
        form.addRow('差分阈值', thr)
        ma = QSpinBox(); ma.setRange(1, 1_000_000); ma.setValue(int(self.params.get('minArea') or 50))
        ma.valueChanged.connect(lambda v: self._set_param('minArea', int(v)))
        form.addRow('最小面积', ma)
        mc = QSpinBox(); mc.setRange(1, 5000); mc.setValue(int(self.params.get('maxCount') or 200))
        mc.valueChanged.connect(lambda v: self._set_param('maxCount', int(v)))
        form.addRow('最大缺陷数', mc)
        blur = QSpinBox(); blur.setRange(0, 31); blur.setSingleStep(2)
        blur.setValue(int(self.params.get('blur') or 3))
        blur.valueChanged.connect(lambda v: self._set_param('blur', int(v)))
        form.addRow('模糊核', blur)
        tip = QLabel('OpenCV absdiff / contour 壳 · 无 Halcon。模板图可在上游采集或绑定。')
        tip.setWordWrap(True); tip.setStyleSheet('color:#888;'); form.addRow(tip)
        return w

    def _result_tab(self):
        w = QWidget(); form = QFormLayout(w); form.setContentsMargins(10, 10, 10, 10)
        for key, lab in (
            ('showOverlay', '显示叠加'),
            ('showBoxes', '显示缺陷框'),
            ('showLabels', '显示标签'),
        ):
            sw = OrangeSwitch(bool(self.params.get(key, True)))
            sw.toggled.connect(lambda c, k=key: self._set_param(k, bool(c)))
            form.addRow(lab, sw)

        wv = OrangeSwitch(bool(self.params.get('writeFlowVars', True)))
        wv.toggled.connect(lambda c: self._set_param('writeFlowVars', bool(c)))
        form.addRow('写入流程变量', wv)
        out_var = QLineEdit(str(self.params.get('resultVar') or 'defects'))
        out_var.setObjectName('defectsResultVar')
        out_var.editingFinished.connect(
            lambda: self._set_param('resultVar', out_var.text().strip() or 'defects')
        )
        form.addRow('结果变量前缀', out_var)

        je = OrangeSwitch(bool(self.params.get('judgeEnable', True)))
        je.toggled.connect(lambda c: self._set_param('judgeEnable', bool(c)))
        form.addRow('结果判断使能', je)
        jmc = QSpinBox(); jmc.setRange(0, 5000)
        jmc.setValue(int(self.params.get('judgeMaxCount') if self.params.get('judgeMaxCount') is not None else 0))
        jmc.valueChanged.connect(lambda v: self._set_param('judgeMaxCount', int(v)))
        form.addRow('允许最大缺陷数', jmc)
        jmr = QDoubleSpinBox(); jmr.setRange(0, 1); jmr.setDecimals(4); jmr.setSingleStep(0.01)
        jmr.setValue(float(self.params.get('judgeMaxRatio') or 0.05))
        jmr.valueChanged.connect(lambda v: self._set_param('judgeMaxRatio', float(v)))
        form.addRow('允许最大缺陷比', jmr)
        tip_j = QLabel('count ≤ 最大数 且 defectRatio ≤ 最大比 → judgeOk；否则 NG。')
        tip_j.setWordWrap(True); tip_j.setStyleSheet('color:#888;font-size:11px;')
        form.addRow(tip_j)

        self._live_lab = QLabel('实况：尚未运行')
        self._live_lab.setObjectName('defectsLiveBind')
        self._live_lab.setWordWrap(True)
        self._live_lab.setStyleSheet(
            'color:#9ad;font-size:11px;padding:6px 8px;background:#1e2228;border-radius:4px;'
        )
        form.addRow('Host 实况', self._live_lab)
        brow = QHBoxLayout()
        b_ref = QPushButton('刷新实况')
        b_ref.setObjectName('defectsLiveRefreshBtn')
        b_ref.clicked.connect(self._refresh_live)
        brow.addWidget(b_ref)
        brow.addStretch(1)
        form.addRow(brow)
        try:
            self._refresh_live()
        except Exception:
            pass
        return w

    def _refresh_live(self):
        lab = self._live_lab
        if lab is None:
            return
        res = self._find_step_result()
        if not res:
            lab.setText('实况：尚无本模块运行结果')
            return
        bits = []
        for k in ('status', 'count', 'defectRatio', 'passed', 'judgeOk', 'judgeStatus', 'method'):
            if k in res and res[k] is not None:
                bits.append(f'{k}={res[k]}')
        items = res.get('items') or []
        bits.append(f'items={len(items) if isinstance(items, list) else items}')
        flow = ((self._host_last().get('variables') or {}).get('flow') or {})
        prefix = str(self.params.get('resultVar') or 'defects')
        for suffix in ('', '_count', '_ratio', '_passed', '_judgeOk', '_ok'):
            key = prefix if suffix == '' else prefix + suffix
            if key in flow:
                bits.append(f'flow.{key}={flow[key]}')
        # also defects_* inject
        for k in ('defects_count', 'defects_ratio', 'defects_passed', 'defects_judgeOk'):
            if k in flow:
                bits.append(f'flow.{k}={flow[k]}')
        lab.setText('实况：' + (' · '.join(bits[:12]) if bits else str(list(res.keys())[:8])))


class OcrPanel(_RecognizeShell):
    """OCR：参数 + 结果显示 + 文本判定 + 流程变量。"""

    def _build(self):
        self.params = _norm_ocr(self.params)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        tabs = QTabWidget()
        tabs.addTab(self._params_tab(), '参数')
        tabs.addTab(self._result_tab(), '结果与判定')
        root.addWidget(tabs)

    def _params_tab(self):
        w = QWidget(); form = QFormLayout(w); form.setContentsMargins(10, 10, 10, 10)
        lang = QComboBox(); lang.addItems(['ch', 'en', 'ch_en'])
        lang.setCurrentText(str(self.params.get('lang') or 'ch'))
        lang.currentTextChanged.connect(lambda v: self._set_param('lang', v))
        form.addRow('语言', lang)
        mc = QDoubleSpinBox(); mc.setRange(0, 1); mc.setDecimals(3); mc.setSingleStep(0.05)
        mc.setValue(float(self.params.get('minConfidence') or 0.5))
        mc.valueChanged.connect(lambda v: self._set_param('minConfidence', float(v)))
        form.addRow('最小置信度', mc)
        mi = QSpinBox(); mi.setRange(1, 500); mi.setValue(int(self.params.get('maxItems') or 50))
        mi.valueChanged.connect(lambda v: self._set_param('maxItems', int(v)))
        form.addRow('最大条目', mi)
        tip = QLabel('RapidOCR / OpenCV 壳 · 无 Halcon。文本结果写入 flow 前缀。')
        tip.setWordWrap(True); tip.setStyleSheet('color:#888;'); form.addRow(tip)
        return w

    def _result_tab(self):
        w = QWidget(); form = QFormLayout(w); form.setContentsMargins(10, 10, 10, 10)
        for key, lab in (
            ('showOverlay', '显示叠加'),
            ('showBoxes', '显示文字框'),
            ('showText', '显示识别文字'),
        ):
            sw = OrangeSwitch(bool(self.params.get(key, True)))
            sw.toggled.connect(lambda c, k=key: self._set_param(k, bool(c)))
            form.addRow(lab, sw)

        wv = OrangeSwitch(bool(self.params.get('writeFlowVars', True)))
        wv.toggled.connect(lambda c: self._set_param('writeFlowVars', bool(c)))
        form.addRow('写入流程变量', wv)
        out_var = QLineEdit(str(self.params.get('resultVar') or 'ocr'))
        out_var.setObjectName('ocrResultVar')
        out_var.editingFinished.connect(
            lambda: self._set_param('resultVar', out_var.text().strip() or 'ocr')
        )
        form.addRow('结果变量前缀', out_var)

        je = OrangeSwitch(bool(self.params.get('judgeEnable', False)))
        je.toggled.connect(lambda c: self._set_param('judgeEnable', bool(c)))
        form.addRow('结果判断使能', je)
        exp = QLineEdit(str(self.params.get('expectedText') or ''))
        exp.setObjectName('ocrExpectedText')
        exp.setPlaceholderText('期望文本（空=只看置信度）')
        exp.editingFinished.connect(lambda: self._set_param('expectedText', exp.text()))
        form.addRow('期望文本', exp)
        jmc = QDoubleSpinBox(); jmc.setRange(0, 1); jmc.setDecimals(3); jmc.setSingleStep(0.05)
        jmc.setValue(float(self.params.get('judgeMinConfidence') or 0.5))
        jmc.valueChanged.connect(lambda v: self._set_param('judgeMinConfidence', float(v)))
        form.addRow('判定最低置信度', jmc)
        tip_j = QLabel('使能后：整体 confidence ≥ 阈值，且（若填期望）识别文本包含期望 → judgeOk。')
        tip_j.setWordWrap(True); tip_j.setStyleSheet('color:#888;font-size:11px;')
        form.addRow(tip_j)

        self._text_preview = QTextEdit()
        self._text_preview.setObjectName('ocrTextPreview')
        self._text_preview.setReadOnly(True)
        self._text_preview.setMaximumHeight(90)
        self._text_preview.setPlaceholderText('识别文本预览…')
        form.addRow('文本预览', self._text_preview)

        self._live_lab = QLabel('实况：尚未运行')
        self._live_lab.setObjectName('ocrLiveBind')
        self._live_lab.setWordWrap(True)
        self._live_lab.setStyleSheet(
            'color:#9ad;font-size:11px;padding:6px 8px;background:#1e2228;border-radius:4px;'
        )
        form.addRow('Host 实况', self._live_lab)
        brow = QHBoxLayout()
        b_ref = QPushButton('刷新实况')
        b_ref.setObjectName('ocrLiveRefreshBtn')
        b_ref.clicked.connect(self._refresh_live)
        brow.addWidget(b_ref)
        brow.addStretch(1)
        form.addRow(brow)
        try:
            self._refresh_live()
        except Exception:
            pass
        return w

    def _refresh_live(self):
        lab = self._live_lab
        if lab is None:
            return
        res = self._find_step_result()
        if not res:
            lab.setText('实况：尚无本模块运行结果')
            if getattr(self, '_text_preview', None):
                self._text_preview.setPlainText('')
            return
        bits = []
        for k in ('status', 'count', 'text', 'confidence', 'passed', 'judgeOk', 'judgeStatus'):
            if k in res and res[k] is not None:
                val = res[k]
                if k == 'text' and isinstance(val, str) and len(val) > 40:
                    val = val[:40] + '…'
                bits.append(f'{k}={val}')
        if getattr(self, '_text_preview', None):
            self._text_preview.setPlainText(str(res.get('text') or ''))
        flow = ((self._host_last().get('variables') or {}).get('flow') or {})
        prefix = str(self.params.get('resultVar') or 'ocr')
        for suffix in ('', '_text', '_count', '_confidence', '_judgeOk', '_ok'):
            key = prefix if suffix == '' else prefix + suffix
            if key in flow:
                bits.append(f'flow.{key}={flow[key]}')
        for k in ('ocr_count', 'ocr_confidence', 'ocr_text', 'ocr_judgeOk'):
            if k in flow:
                bits.append(f'flow.{k}={flow[k]}')
        lab.setText('实况：' + (' · '.join(bits[:12]) if bits else str(list(res.keys())[:8])))
