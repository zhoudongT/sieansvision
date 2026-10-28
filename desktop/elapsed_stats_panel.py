"""耗时统计（elapsed_stats）属性浮窗 — VisionMaster p=27 壳.

开始/结束模块下拉；运行时累加区间内各步 elapsedMs。
"""
from copy import deepcopy

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTabWidget, QFormLayout, QLineEdit,
    QComboBox, QScrollArea, QFrame, QPlainTextEdit, QPushButton, QSpinBox,
)
from desktop.widgets.switch import OrangeSwitch


def normalize_elapsed_stats_params(params=None):
    p = deepcopy(params or {})
    p.setdefault('startStepId', '')
    p.setdefault('endStepId', '')
    p.setdefault('includeEnds', True)
    p.setdefault('unit', 'ms')
    p.setdefault('showTotal', True)
    p.setdefault('showPerStep', True)
    p.setdefault('showSparkline', False)
    p.setdefault('targetVar', 'elapsedTotalMs')
    p.setdefault('targetScope', 'flow')
    p.setdefault('warnMs', 0)  # 0=off soft threshold
    return p


class ElapsedStatsPanel(QWidget):
    changed = Signal(dict)

    def __init__(self, step, definition, project, parent=None):
        super().__init__(parent)
        self.step = deepcopy(step)
        self.definition = definition or {}
        self.project = project or {}
        self.params = normalize_elapsed_stats_params(step.get('params'))
        self.step['params'] = self.params

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        hint = QLabel(
            '对齐 VisionMaster「耗时统计」：选择开始/结束模块，'
            '运行时统计区间累计耗时（依赖各步 elapsedMs）。'
        )
        hint.setWordWrap(True)
        hint.setStyleSheet('color:#666;padding:8px 10px 4px;')
        root.addWidget(hint)

        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)
        self.tabs.addTab(self._wrap(self._basic_tab()), '基本参数')
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
            self._maybe_refresh_elapsed()

    def _set_top(self, key, value):
        if self.step.get(key) != value:
            self.step[key] = deepcopy(value)
            self._emit()

    def _step_choices(self):
        items = [('（未选择）', '')]
        items.append(('0 图像源1', 'source'))
        for i, s in enumerate(self.project.get('steps', []), start=1):
            if s.get('id') == self.step.get('id'):
                continue
            label = f"{i} {s.get('name') or s.get('operation') or s['id']}"
            items.append((label, s['id']))
        return items

    def _fill_combo(self, combo, current):
        combo.clear()
        for lab, data in self._step_choices():
            combo.addItem(lab, data)
        idx = combo.findData(current or '')
        if idx < 0 and current:
            combo.addItem(f'已丢失：{current}', current)
            idx = combo.findData(current)
        combo.setCurrentIndex(max(0, idx))

    def _basic_tab(self):
        w = QWidget()
        form = QFormLayout(w)
        form.setContentsMargins(10, 10, 10, 10)
        form.setSpacing(8)

        name = QLineEdit(self.step.get('name') or '耗时统计')
        name.setMaxLength(80)
        name.editingFinished.connect(lambda: self._set_top('name', name.text()))
        form.addRow('模块名称', name)

        start = QComboBox()
        self._fill_combo(start, self.params.get('startStepId'))
        start.currentIndexChanged.connect(lambda _: self._set_param('startStepId', start.currentData() or ''))
        form.addRow('开始模块', start)

        end = QComboBox()
        self._fill_combo(end, self.params.get('endStepId'))
        end.currentIndexChanged.connect(lambda _: self._set_param('endStepId', end.currentData() or ''))
        form.addRow('结束模块', end)

        unit = QComboBox()
        for v, lab in (('ms', '毫秒'), ('s', '秒')):
            unit.addItem(lab, v)
        unit.setCurrentIndex(max(0, unit.findData(self.params.get('unit') or 'ms')))
        unit.currentIndexChanged.connect(lambda _: self._set_param('unit', unit.currentData()))
        form.addRow('单位', unit)

        incl = OrangeSwitch(bool(self.params.get('includeEnds', True)))
        incl.toggled.connect(lambda c: self._set_param('includeEnds', bool(c)))
        form.addRow('含起止节点', incl)

        tvar = QLineEdit(str(self.params.get('targetVar') or 'elapsedTotalMs'))
        tvar.editingFinished.connect(lambda: self._set_param('targetVar', tvar.text().strip() or 'elapsedTotalMs'))
        form.addRow('合计变量', tvar)

        scope = QComboBox()
        for v, lab in (('flow', '流程'), ('global', '全局'), ('module', '模块')):
            scope.addItem(lab, v)
        scope.setCurrentIndex(max(0, scope.findData(self.params.get('targetScope') or 'flow')))
        scope.currentIndexChanged.connect(lambda _: self._set_param('targetScope', scope.currentData()))
        form.addRow('变量作用域', scope)

        warn = QSpinBox()
        warn.setRange(0, 600000)
        warn.setSpecialValueText('关闭')
        warn.setValue(int(self.params.get('warnMs') or 0))
        warn.setToolTip('软告警阈值（ms）；0=关闭。结果显示页对照。')
        warn.valueChanged.connect(lambda v: self._set_param('warnMs', int(v)))
        form.addRow('软告警阈值(ms)', warn)

        tip = QLabel('起止均未选时红叹号；统计按流程拓扑顺序，含起止节点本身。')
        tip.setWordWrap(True)
        tip.setStyleSheet('color:#888;')
        form.addRow(tip)
        return w

    def _maybe_refresh_elapsed(self):
        if hasattr(self, '_refresh_elapsed_result'):
            try:
                self._refresh_elapsed_result()
            except Exception:
                pass

    def _result_tab(self):
        w = QWidget()
        form = QFormLayout(w)
        form.setContentsMargins(10, 10, 10, 10)
        tip = QLabel('运行写回 elapsedMs / breakdown[] / status；下方为设计态区间模块预览（耗时待运行）。')
        tip.setWordWrap(True)
        tip.setStyleSheet('color:#888;')
        form.addRow(tip)
        for key, lab, default in (
            ('showTotal', '显示合计', True),
            ('showPerStep', '显示分步耗时', True),
            ('showSparkline', '显示趋势条', False),
        ):
            sw = OrangeSwitch(bool(self.params.get(key, default)))
            sw.toggled.connect(lambda c, k=key: self._set_param(k, bool(c)))
            form.addRow(lab, sw)
        self._elapsed_result_preview = QPlainTextEdit()
        self._elapsed_result_preview.setObjectName('elapsedStatsResultPreview')
        self._elapsed_result_preview.setReadOnly(True)
        self._elapsed_result_preview.setMaximumHeight(160)
        form.addRow('区间模块', self._elapsed_result_preview)
        self._elapsed_result_meta = QLabel()
        self._elapsed_result_meta.setObjectName('elapsedStatsResultMeta')
        self._elapsed_result_meta.setWordWrap(True)
        form.addRow('摘要', self._elapsed_result_meta)
        btn = QPushButton('刷新结果显示')
        btn.setObjectName('elapsedStatsResultRefresh')
        btn.clicked.connect(self._refresh_elapsed_result)
        form.addRow(btn)
        self._refresh_elapsed_result()
        return w

    def _refresh_elapsed_result(self):
        start_id = self.params.get('startStepId') or ''
        end_id = self.params.get('endStepId') or ''
        order = ['source']
        names = {'source': '图像源1'}
        for s in self.project.get('steps') or []:
            order.append(s['id'])
            names[s['id']] = s.get('name') or s.get('operation') or s['id']
        lines = []
        meta = ''
        if not start_id or not end_id:
            lines.append('(请选择开始/结束模块)')
            meta = 'status=missing_bounds'
        else:
            try:
                i0 = order.index(start_id)
                i1 = order.index(end_id)
            except ValueError:
                lines.append('(起止模块不在当前流程)')
                meta = 'status=missing_bounds'
            else:
                if i1 < i0:
                    i0, i1 = i1, i0
                slice_ids = order[i0:i1 + 1]
                if not self.params.get('includeEnds', True) and len(slice_ids) > 2:
                    slice_ids = slice_ids[1:-1]
                for j, sid in enumerate(slice_ids):
                    if sid == 'source':
                        continue
                    label = names.get(sid, sid)
                    lines.append(f'{j + 1}. {label}  ·  elapsedMs=（运行后）')
                unit = self.params.get('unit') or 'ms'
                tvar = self.params.get('targetVar') or 'elapsedTotalMs'
                scope = self.params.get('targetScope') or 'flow'
                warn = int(self.params.get('warnMs') or 0)
                n_steps = len([x for x in slice_ids if x != 'source'])
                warn_txt = '关闭' if warn <= 0 else f'{warn} ms'
                meta = f'区间 {n_steps} 步 · 单位={unit} · 写入 {scope}.{tvar} · 软告警={warn_txt}'
        nl = chr(10)
        text = nl.join(lines) if lines else '(空区间)'
        if hasattr(self, '_elapsed_result_preview') and self._elapsed_result_preview is not None:
            self._elapsed_result_preview.setPlainText(text)
        if hasattr(self, '_elapsed_result_meta') and self._elapsed_result_meta is not None:
            self._elapsed_result_meta.setText(meta)
