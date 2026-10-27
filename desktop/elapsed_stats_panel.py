"""耗时统计（elapsed_stats）属性浮窗 — VisionMaster p=27 壳.

开始/结束模块下拉；运行时累加区间内各步 elapsedMs。
"""
from copy import deepcopy

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTabWidget, QFormLayout, QLineEdit,
    QComboBox, QScrollArea, QFrame,
)


def normalize_elapsed_stats_params(params=None):
    p = deepcopy(params or {})
    p.setdefault('startStepId', '')
    p.setdefault('endStepId', '')
    p.setdefault('includeEnds', True)
    p.setdefault('unit', 'ms')
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

        tip = QLabel('起止均未选时红叹号；统计按流程拓扑顺序，含起止节点本身。')
        tip.setWordWrap(True)
        tip.setStyleSheet('color:#888;')
        form.addRow(tip)
        return w

    def _result_tab(self):
        w = QWidget()
        form = QFormLayout(w)
        form.setContentsMargins(10, 10, 10, 10)
        tip = QLabel('运行结果：elapsedMs / startStepId / endStepId / breakdown[]。')
        tip.setWordWrap(True)
        tip.setStyleSheet('color:#888;')
        form.addRow(tip)
        return w
