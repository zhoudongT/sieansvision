"""条件分支 / 分支模块 表格式属性浮窗 — VisionMaster p=18 / p=19.

condition: 多行规则表（AND/OR）→ 真/假出边（when=true/false）
branch: 多路路径表 → 出边 when=路径名；运行时选首条命中路径
"""
from copy import deepcopy

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTabWidget,
    QFormLayout, QLineEdit, QComboBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QScrollArea, QFrame,
)

COMPARISONS = [
    ('eq', '等于'),
    ('ne', '不等于'),
    ('gt', '大于'),
    ('gte', '大于等于'),
    ('lt', '小于'),
    ('lte', '小于等于'),
    ('contains', '包含'),
    ('is_true', '为真'),
    ('is_false', '为假'),
]


def normalize_condition_params(params=None):
    p = deepcopy(params or {})
    p.setdefault('logic', 'and')  # and | or
    p.setdefault('comparison', 'eq')
    p.setdefault('left', 0)
    p.setdefault('right', 0)
    rules = p.get('rules')
    if not isinstance(rules, list) or not rules:
        # Seed one rule from flat fields so engine + N4 stay consistent
        rules = [dict(
            left=p.get('left', 0),
            comparison=p.get('comparison') or 'eq',
            right=p.get('right', 0),
        )]
    p['rules'] = rules
    return p


def normalize_branch_params(params=None):
    p = deepcopy(params or {})
    paths = p.get('paths')
    if not isinstance(paths, list) or not paths:
        paths = [
            dict(id='path1', name='分支1', left='', comparison='eq', right=''),
            dict(id='path2', name='分支2', left='', comparison='eq', right=''),
            dict(id='default', name='默认', left='', comparison='is_true', right=''),
        ]
    p['paths'] = paths
    p.setdefault('defaultPathId', 'default')
    return p


def sync_condition_flat(params):
    """Keep left/comparison/right in sync with first rule for engine runtime."""
    rules = params.get('rules') or []
    if rules:
        r0 = rules[0]
        params['left'] = r0.get('left', 0)
        params['comparison'] = r0.get('comparison') or 'eq'
        params['right'] = r0.get('right', 0)
    return params


class ConditionBranchPanel(QWidget):
    """Shared shell for condition (规则表) and branch (路径表)."""
    changed = Signal(dict)

    def __init__(self, step, definition, project, parent=None):
        super().__init__(parent)
        self.step = deepcopy(step)
        self.definition = definition or {}
        self.project = project or {}
        self.op = step.get('operation') or 'condition'
        if self.op == 'branch':
            self.params = normalize_branch_params(step.get('params'))
        else:
            self.params = normalize_condition_params(step.get('params'))
            sync_condition_flat(self.params)
        self.step['params'] = self.params

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        if self.op == 'branch':
            hint_txt = (
                '对齐 VisionMaster「分支模块」：多路径表；出边 when=路径名。'
                '运行时按序匹配，命中则激活对应分支；否则走默认路径。'
            )
        else:
            hint_txt = (
                '对齐 VisionMaster「条件分支」：规则表 + 逻辑；'
                '出边 when=true / when=false。多规则按 AND/OR 合成 passed。'
            )
        hint = QLabel(hint_txt)
        hint.setObjectName('dialogHint')
        hint.setWordWrap(True)
        hint.setStyleSheet('color:#666;padding:8px 10px 4px;')
        root.addWidget(hint)

        tabs = QTabWidget()
        root.addWidget(tabs, 1)
        tabs.addTab(self._wrap(self._basic_tab()), '基本参数')
        if self.op == 'branch':
            tabs.addTab(self._wrap(self._paths_tab()), '分支路径')
        else:
            tabs.addTab(self._wrap(self._rules_tab()), '条件规则')

    def _wrap(self, inner):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(inner)
        return scroll

    def _emit(self):
        if self.op != 'branch':
            sync_condition_flat(self.params)
        self.step['params'] = deepcopy(self.params)
        self.changed.emit(deepcopy(self.step))

    def _set_top(self, key, value):
        if self.step.get(key) != value:
            self.step[key] = deepcopy(value)
            self._emit()

    def _basic_tab(self):
        w = QWidget()
        form = QFormLayout(w)
        form.setContentsMargins(10, 10, 10, 10)
        form.setSpacing(8)
        default_name = '分支模块' if self.op == 'branch' else '条件判断'
        name = QLineEdit(self.step.get('name') or self.definition.get('name') or default_name)
        name.setMaxLength(80)
        name.editingFinished.connect(lambda: self._set_top('name', name.text()))
        form.addRow('模块名称', name)

        if self.op != 'branch':
            logic = QComboBox()
            logic.addItem('全部满足 (AND)', 'and')
            logic.addItem('任一满足 (OR)', 'or')
            li = max(0, logic.findData(self.params.get('logic') or 'and'))
            logic.setCurrentIndex(li)
            logic.currentIndexChanged.connect(lambda _: self._set_logic(logic.currentData()))
            form.addRow('规则逻辑', logic)
            tip = QLabel('画布出边：真分支 when=true，假分支 when=false。')
        else:
            tip = QLabel('画布出边 when 填路径名（如「分支1」）；默认路径兜底。')
        tip.setWordWrap(True)
        tip.setStyleSheet('color:#888;')
        form.addRow(tip)
        return w

    def _set_logic(self, value):
        self.params['logic'] = value
        self._emit()

    def _rules_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(10, 10, 10, 10)
        self.rules_table = QTableWidget(0, 4)
        self.rules_table.setHorizontalHeaderLabels(['左侧值', '比较', '右侧值', '操作'])
        self.rules_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.rules_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.rules_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        lay.addWidget(self.rules_table, 1)
        bar = QHBoxLayout()
        add = QPushButton('添加规则')
        add.clicked.connect(lambda: self._append_rule({}))
        bar.addWidget(add)
        bar.addStretch(1)
        lay.addLayout(bar)
        for rule in self.params.get('rules') or []:
            self._append_rule(rule, emit=False)
        return w

    def _append_rule(self, rule, emit=True):
        rule = rule or {}
        r = self.rules_table.rowCount()
        self.rules_table.insertRow(r)
        left = QLineEdit(str(rule.get('left', '') if rule.get('left') is not None else ''))
        left.setPlaceholderText('变量 / 常量 / $ref')
        left.editingFinished.connect(self._harvest_rules)
        self.rules_table.setCellWidget(r, 0, left)

        cmp = QComboBox()
        for val, lab in COMPARISONS:
            cmp.addItem(lab, val)
        cur = rule.get('comparison') or 'eq'
        ci = max(0, cmp.findData(cur))
        cmp.setCurrentIndex(ci)
        cmp.currentIndexChanged.connect(lambda *_: self._harvest_rules())
        self.rules_table.setCellWidget(r, 1, cmp)

        right = QLineEdit(str(rule.get('right', '') if rule.get('right') is not None else ''))
        right.setPlaceholderText('常量 / 变量')
        right.editingFinished.connect(self._harvest_rules)
        self.rules_table.setCellWidget(r, 2, right)

        rm = QPushButton('删')
        rm.setFixedWidth(36)
        rm.clicked.connect(lambda *_ , rr=r: self._remove_rule(rr))
        self.rules_table.setCellWidget(r, 3, rm)
        if emit:
            self._harvest_rules()

    def _remove_rule(self, row):
        if self.rules_table.rowCount() <= 1:
            return  # keep at least one
        if 0 <= row < self.rules_table.rowCount():
            self.rules_table.removeRow(row)
            self._rebind_rule_buttons()
            self._harvest_rules()

    def _rebind_rule_buttons(self):
        for r in range(self.rules_table.rowCount()):
            btn = self.rules_table.cellWidget(r, 3)
            if isinstance(btn, QPushButton):
                try:
                    btn.clicked.disconnect()
                except TypeError:
                    pass
                btn.clicked.connect(lambda *_ , rr=r: self._remove_rule(rr))

    def _harvest_rules(self):
        rules = []
        for r in range(self.rules_table.rowCount()):
            left_w = self.rules_table.cellWidget(r, 0)
            cmp_w = self.rules_table.cellWidget(r, 1)
            right_w = self.rules_table.cellWidget(r, 2)
            left = left_w.text().strip() if left_w else ''
            # Try numeric coerce for engine comfort
            try:
                if left and left.replace('.', '', 1).replace('-', '', 1).isdigit():
                    left = float(left) if '.' in left else int(left)
            except Exception:
                pass
            right = right_w.text().strip() if right_w else ''
            try:
                if right and right.replace('.', '', 1).replace('-', '', 1).isdigit():
                    right = float(right) if '.' in right else int(right)
            except Exception:
                pass
            comparison = cmp_w.currentData() if cmp_w else 'eq'
            rules.append(dict(left=left, comparison=comparison, right=right))
        self.params['rules'] = rules
        self._emit()

    def _paths_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(10, 10, 10, 10)
        self.paths_table = QTableWidget(0, 6)
        self.paths_table.setHorizontalHeaderLabels(
            ['路径ID', '路径名', '左侧值', '比较', '右侧值', '操作']
        )
        self.paths_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.paths_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        lay.addWidget(self.paths_table, 1)
        bar = QHBoxLayout()
        add = QPushButton('添加路径')
        add.clicked.connect(lambda: self._append_path({}))
        bar.addWidget(add)
        bar.addStretch(1)
        lay.addLayout(bar)
        tip = QLabel('出边 when 建议填「路径名」。路径ID 供脚本/绑定引用。')
        tip.setWordWrap(True)
        tip.setStyleSheet('color:#888;')
        lay.addWidget(tip)
        for path in self.params.get('paths') or []:
            self._append_path(path, emit=False)
        return w

    def _append_path(self, path, emit=True):
        path = path or {}
        r = self.paths_table.rowCount()
        self.paths_table.insertRow(r)
        pid = QLineEdit(str(path.get('id') or f'path{r + 1}'))
        pname = QLineEdit(str(path.get('name') or f'分支{r + 1}'))
        left = QLineEdit(str(path.get('left', '') if path.get('left') is not None else ''))
        cmp = QComboBox()
        for val, lab in COMPARISONS:
            cmp.addItem(lab, val)
        ci = max(0, cmp.findData(path.get('comparison') or 'eq'))
        cmp.setCurrentIndex(ci)
        right = QLineEdit(str(path.get('right', '') if path.get('right') is not None else ''))
        for col, widget in enumerate((pid, pname, left, cmp, right)):
            if isinstance(widget, QLineEdit):
                widget.editingFinished.connect(self._harvest_paths)
            else:
                widget.currentIndexChanged.connect(lambda *_: self._harvest_paths())
            self.paths_table.setCellWidget(r, col, widget)
        rm = QPushButton('删')
        rm.setFixedWidth(36)
        rm.clicked.connect(lambda *_ , rr=r: self._remove_path(rr))
        self.paths_table.setCellWidget(r, 5, rm)
        if emit:
            self._harvest_paths()

    def _remove_path(self, row):
        if self.paths_table.rowCount() <= 1:
            return
        if 0 <= row < self.paths_table.rowCount():
            self.paths_table.removeRow(row)
            self._harvest_paths()

    def _harvest_paths(self):
        paths = []
        for r in range(self.paths_table.rowCount()):
            pid = self.paths_table.cellWidget(r, 0)
            pname = self.paths_table.cellWidget(r, 1)
            left_w = self.paths_table.cellWidget(r, 2)
            cmp_w = self.paths_table.cellWidget(r, 3)
            right_w = self.paths_table.cellWidget(r, 4)
            paths.append(dict(
                id=(pid.text().strip() if pid else f'path{r + 1}') or f'path{r + 1}',
                name=(pname.text().strip() if pname else f'分支{r + 1}') or f'分支{r + 1}',
                left=left_w.text().strip() if left_w else '',
                comparison=cmp_w.currentData() if cmp_w else 'eq',
                right=right_w.text().strip() if right_w else '',
            ))
        self.params['paths'] = paths
        self._emit()
