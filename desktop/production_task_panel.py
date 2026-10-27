"""生产任务 — VisionMaster p=40 可模仿薄壳（无机械手 SDK）。

设计态：任务名/配方/状态变量 + 建议流程链（图像→匹配→修正→查找→物理坐标→偏差→发送）。
运行态：productionTask 写入变量；真正视觉步骤由用户用既有算子串接。
"""
from copy import deepcopy

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTabWidget, QFormLayout, QLineEdit,
    QComboBox, QScrollArea, QFrame, QPlainTextEdit, QHBoxLayout, QCheckBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView, QPushButton,
)

from desktop.widgets.switch import OrangeSwitch

# Align with p40 mind-map (UI/流程 only; no robot SDK)
DEFAULT_CHAIN = [
    {'step': '读取图像', 'op': '图像源 / camera_capture', 'vars': ''},
    {'step': '模板匹配', 'op': 'locate', 'vars': ''},
    {'step': '位置修正', 'op': 'pose_correct', 'vars': ''},
    {'step': '圆/特征查找', 'op': 'geometry (circles)', 'vars': 'target_X, target_Y'},
    {'step': '基准→物理坐标', 'op': 'nine_point / var_calc', 'vars': 'start_X_M, start_Y_M'},
    {'step': '目标→物理坐标', 'op': 'nine_point / var_calc', 'vars': 'target_X_M, target_Y_M'},
    {'step': '偏差', 'op': 'var_calc', 'vars': 'dx, dy'},
    {'step': '最终移动量', 'op': 'var_calc', 'vars': 'MoveX, MoveY'},
    {'step': '发送上位机', 'op': 'send_data / format_data', 'vars': ''},
]


def normalize_production_task_params(params=None):
    p = deepcopy(params or {})
    p.setdefault('taskName', '')
    p.setdefault('recipe', '')
    p.setdefault('autoStart', False)
    p.setdefault('statusVar', 'taskStatus')
    p.setdefault('scope', 'global')
    p.setdefault('note', '')
    chain = p.get('chain')
    if not isinstance(chain, list) or not chain:
        p['chain'] = deepcopy(DEFAULT_CHAIN)
    else:
        # keep user chain; ensure keys
        norm = []
        for row in chain[:40]:
            if not isinstance(row, dict):
                continue
            norm.append({
                'step': str(row.get('step') or ''),
                'op': str(row.get('op') or ''),
                'vars': str(row.get('vars') or ''),
            })
        p['chain'] = norm or deepcopy(DEFAULT_CHAIN)
    return p


class ProductionTaskPanel(QWidget):
    changed = Signal(dict)

    def __init__(self, step, definition, project, parent=None):
        super().__init__(parent)
        self.step = deepcopy(step)
        self.definition = definition or {}
        self.project = project or {}
        self.params = normalize_production_task_params(step.get('params'))
        self.step['params'] = self.params

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        hint = QLabel(
            '对齐 VisionMaster「生产任务设计」(p40)：任务名/配方写入变量，并给出可复用流程链示意。'
            '不接机械手/产线 SDK；请用既有算子（locate / pose_correct / nine_point / var_calc / send_data）串接。'
        )
        hint.setWordWrap(True)
        hint.setStyleSheet('color:#666;padding:8px 10px 4px;')
        root.addWidget(hint)
        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)
        self.tabs.addTab(self._wrap(self._basic_tab()), '基本参数')
        self.tabs.addTab(self._wrap(self._chain_tab()), '建议流程链')
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

    def _set(self, key, value):
        self.params[key] = value
        self._emit()

    def _basic_tab(self):
        w = QWidget()
        form = QFormLayout(w)
        form.setContentsMargins(12, 12, 12, 12)
        name = QLineEdit(str(self.params.get('taskName') or ''))
        name.setPlaceholderText('例如：对位贴合任务1')
        name.textChanged.connect(lambda t: self._set('taskName', t))
        form.addRow('任务名称', name)

        recipe = QLineEdit(str(self.params.get('recipe') or ''))
        recipe.setPlaceholderText('配方/方案名')
        recipe.textChanged.connect(lambda t: self._set('recipe', t))
        form.addRow('配方/方案', recipe)

        scope = QComboBox()
        for k, lab in (('global', '全局'), ('flow', '流程')):
            scope.addItem(lab, k)
        i = scope.findData(self.params.get('scope') or 'global')
        scope.setCurrentIndex(i if i >= 0 else 0)
        scope.currentIndexChanged.connect(lambda *_: self._set('scope', scope.currentData()))
        form.addRow('变量作用域', scope)

        sv = QLineEdit(str(self.params.get('statusVar') or 'taskStatus'))
        sv.textChanged.connect(lambda t: self._set('statusVar', t.strip() or 'taskStatus'))
        form.addRow('状态变量', sv)

        auto = OrangeSwitch(bool(self.params.get('autoStart')))
        auto.toggled.connect(lambda on: self._set('autoStart', bool(on)))
        form.addRow('自动启动标记', auto)

        note = QPlainTextEdit(str(self.params.get('note') or ''))
        note.setPlaceholderText('备注（不落运行）')
        note.setMaximumHeight(80)
        note.textChanged.connect(lambda: self._set('note', note.toPlainText()))
        form.addRow('备注', note)
        return w

    def _chain_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 12, 12, 12)
        tip = QLabel('p40 典型链（可编辑示意；运行不自动执行这些步骤）：')
        tip.setStyleSheet('color:#666;')
        lay.addWidget(tip)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(['步骤', '建议算子', '变量'])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.itemChanged.connect(self._on_chain_edit)
        lay.addWidget(self.table, 1)
        bar = QHBoxLayout()
        reset = QPushButton('恢复默认链')
        reset.clicked.connect(self._reset_chain)
        add = QPushButton('添加行')
        add.clicked.connect(self._add_row)
        bar.addWidget(reset)
        bar.addWidget(add)
        bar.addStretch(1)
        lay.addLayout(bar)
        self._reload_chain()
        return w

    def _reload_chain(self):
        self.table.blockSignals(True)
        self.table.setRowCount(0)
        for row in self.params.get('chain') or []:
            r = self.table.rowCount()
            self.table.insertRow(r)
            for c, key in enumerate(('step', 'op', 'vars')):
                self.table.setItem(r, c, QTableWidgetItem(str(row.get(key) or '')))
        self.table.blockSignals(False)

    def _on_chain_edit(self, *_):
        rows = []
        for r in range(self.table.rowCount()):
            rows.append({
                'step': (self.table.item(r, 0).text() if self.table.item(r, 0) else ''),
                'op': (self.table.item(r, 1).text() if self.table.item(r, 1) else ''),
                'vars': (self.table.item(r, 2).text() if self.table.item(r, 2) else ''),
            })
        self.params['chain'] = rows
        self._emit()

    def _reset_chain(self):
        self.params['chain'] = deepcopy(DEFAULT_CHAIN)
        self._reload_chain()
        self._emit()

    def _add_row(self):
        self.table.blockSignals(True)
        r = self.table.rowCount()
        self.table.insertRow(r)
        for c in range(3):
            self.table.setItem(r, c, QTableWidgetItem(''))
        self.table.blockSignals(False)
        self._on_chain_edit()

    def _result_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 12, 12, 12)
        lab = QLabel(
            '运行结果字段：taskName / recipe / status(ready|running|unconfigured) / statusVar / scope。\n会写入 {statusVar}、{statusVar}_name、{statusVar}_recipe。'
        )
        lab.setWordWrap(True)
        lay.addWidget(lab)
        lay.addStretch(1)
        return w
