"""条件分支 / 分支模块 表格式属性浮窗 — VisionMaster p=18 / p=19.

condition: 多行规则表（AND/OR）→ 真/假出边（when=true/false）
branch: 多路路径表 → 出边 when=路径名；运行时选首条命中路径
"""
from copy import deepcopy

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTabWidget,
    QFormLayout, QLineEdit, QComboBox, QTableWidget, QTableWidgetItem, QPlainTextEdit,
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
    ('starts_with', '开头是'),
    ('ends_with', '结尾是'),
    ('regex', '正则'),
    ('empty', '为空'),
    ('not_empty', '非空'),
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
            enabled=True,
        )]
    p['rules'] = rules
    return p


def normalize_branch_params(params=None):
    p = deepcopy(params or {})
    paths = p.get('paths')
    if not isinstance(paths, list) or not paths:
        paths = [
            dict(id='path1', name='分支1', left='', comparison='eq', right='', enabled=True),
            dict(id='path2', name='分支2', left='', comparison='eq', right='', enabled=True),
            dict(id='default', name='默认', left='', comparison='is_true', right='', enabled=True),
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



def _line_text(widget):
    """Read text from a QLineEdit cell or a wrap QWidget that contains one."""
    if widget is None:
        return ''
    from PySide6.QtWidgets import QLineEdit
    if isinstance(widget, QLineEdit):
        return widget.text()
    line = widget.findChild(QLineEdit) if hasattr(widget, 'findChild') else None
    return line.text() if line is not None else ''


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
        tabs.addTab(self._wrap(self._result_tab()), '结果显示')

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
            tip = QLabel('画布出边：真分支 when=true，假分支 when=false。未填左侧值时节点红叹号。')
        else:
            dp = QComboBox()
            dp.setEditable(True)
            for path in self.params.get('paths') or []:
                dp.addItem(path.get('name') or path.get('id') or '', path.get('id') or '')
            cur = self.params.get('defaultPathId') or 'default'
            ix = dp.findData(cur)
            if ix < 0:
                dp.addItem(cur, cur); ix = dp.count() - 1
            dp.setCurrentIndex(max(0, ix))
            def _dp():
                self.params['defaultPathId'] = dp.currentData() or dp.currentText()
                self._emit()
            dp.currentIndexChanged.connect(lambda *_: _dp())
            dp.editTextChanged.connect(lambda *_: _dp())
            form.addRow('默认路径', dp)
            tip = QLabel('画布出边 when 填路径名；无命中走默认路径。禁用路径不参与匹配。')
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
        self.rules_table = QTableWidget(0, 5)
        self.rules_table.setHorizontalHeaderLabels(['启用', '左侧值', '比较', '右侧值', '操作'])
        self.rules_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.rules_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.rules_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.rules_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.rules_table.setAlternatingRowColors(True)
        self.rules_table.verticalHeader().setDefaultSectionSize(28)
        lay.addWidget(self.rules_table, 1)
        bar = QHBoxLayout()
        add = QPushButton('添加规则')
        add.clicked.connect(lambda: self._append_rule({}))
        up = QPushButton('↑')
        down = QPushButton('↓')
        up.setFixedWidth(28); down.setFixedWidth(28)
        up.clicked.connect(lambda: self._move_rule(-1))
        down.clicked.connect(lambda: self._move_rule(1))
        bar.addWidget(add)
        bar.addWidget(up)
        bar.addWidget(down)
        bar.addStretch(1)
        lay.addLayout(bar)
        tip = QLabel('左侧可填变量名（如 matchCount）或常量；比较「为空/非空/为真」时右侧可留空。')
        tip.setWordWrap(True); tip.setStyleSheet('color:#888;')
        lay.addWidget(tip)
        for rule in self.params.get('rules') or []:
            self._append_rule(rule, emit=False)
        return w

    def _append_rule(self, rule, emit=True):
        rule = rule or {}
        r = self.rules_table.rowCount()
        self.rules_table.insertRow(r)
        en = QComboBox()
        en.addItem('是', True)
        en.addItem('否', False)
        en.setCurrentIndex(0 if rule.get('enabled', True) else 1)
        en.currentIndexChanged.connect(lambda *_: self._harvest_rules())
        self.rules_table.setCellWidget(r, 0, en)

        left = QLineEdit(str(rule.get('left', '') if rule.get('left') is not None else ''))
        left.setPlaceholderText('变量 / 常量')
        left.editingFinished.connect(self._harvest_rules)
        from desktop.upstream_field_picker import pick_upstream_field
        left_wrap = QWidget()
        left_lay = QHBoxLayout(left_wrap)
        left_lay.setContentsMargins(0, 0, 0, 0)
        left_lay.setSpacing(2)
        lpick = QPushButton('↑')
        lpick.setFixedWidth(28)
        lpick.setToolTip('插入上游字段')
        def _pick_left(_checked=False, ed=left):
            # clicked(bool) must not bind into ed — keep line edit via default kwonly-ish default
            from desktop.upstream_field_picker import host_last_result
            picked = pick_upstream_field(
                self, self.project, self.step.get('id'),
                last_result=host_last_result(self),
            )
            if picked:
                ed.setText(picked[2] if len(picked) > 2 else str(picked[1]))
                self._harvest_rules()
        lpick.clicked.connect(lambda *_: _pick_left())
        left_lay.addWidget(left, 1)
        left_lay.addWidget(lpick)
        self.rules_table.setCellWidget(r, 1, left_wrap)

        cmp = QComboBox()
        for val, lab in COMPARISONS:
            cmp.addItem(lab, val)
        cur = rule.get('comparison') or 'eq'
        ci = max(0, cmp.findData(cur))
        cmp.setCurrentIndex(ci)
        cmp.currentIndexChanged.connect(lambda *_: self._harvest_rules())
        self.rules_table.setCellWidget(r, 2, cmp)

        right = QLineEdit(str(rule.get('right', '') if rule.get('right') is not None else ''))
        right.setPlaceholderText('常量 / 变量')
        right.editingFinished.connect(self._harvest_rules)
        from desktop.upstream_field_picker import pick_upstream_field
        right_wrap = QWidget()
        right_lay = QHBoxLayout(right_wrap)
        right_lay.setContentsMargins(0, 0, 0, 0)
        right_lay.setSpacing(2)
        rpick = QPushButton('↑')
        rpick.setFixedWidth(28)
        rpick.setToolTip('插入上游字段')
        def _pick_right(_checked=False, ed=right):
            from desktop.upstream_field_picker import host_last_result
            picked = pick_upstream_field(
                self, self.project, self.step.get('id'),
                last_result=host_last_result(self),
            )
            if picked:
                ed.setText(picked[2] if len(picked) > 2 else str(picked[1]))
                self._harvest_rules()
        rpick.clicked.connect(lambda *_: _pick_right())
        right_lay.addWidget(right, 1)
        right_lay.addWidget(rpick)
        self.rules_table.setCellWidget(r, 3, right_wrap)

        ops = QWidget()
        ol = QHBoxLayout(ops); ol.setContentsMargins(0, 0, 0, 0); ol.setSpacing(2)
        rm = QPushButton('删'); rm.setFixedWidth(32)
        rm.clicked.connect(lambda *_ , rr=r: self._remove_rule(rr))
        ol.addWidget(rm)
        self.rules_table.setCellWidget(r, 4, ops)
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
            ops = self.rules_table.cellWidget(r, 4)
            if ops is None:
                continue
            btn = ops.findChild(QPushButton) if hasattr(ops, 'findChild') else None
            if isinstance(btn, QPushButton):
                try:
                    btn.clicked.disconnect()
                except TypeError:
                    pass
                btn.clicked.connect(lambda *_ , rr=r: self._remove_rule(rr))

    def _move_rule(self, delta):
        row = self.rules_table.currentRow()
        if row < 0:
            return
        target = row + delta
        if target < 0 or target >= self.rules_table.rowCount():
            return
        self._harvest_rules()
        rules = list(self.params.get('rules') or [])
        rules[row], rules[target] = rules[target], rules[row]
        self.params['rules'] = rules
        self.rules_table.setRowCount(0)
        for rule in rules:
            self._append_rule(rule, emit=False)
        self.rules_table.setCurrentCell(target, 1)
        self._emit()

    def _harvest_rules(self):
        rules = []
        for r in range(self.rules_table.rowCount()):
            en_w = self.rules_table.cellWidget(r, 0)
            left_w = self.rules_table.cellWidget(r, 1)
            cmp_w = self.rules_table.cellWidget(r, 2)
            right_w = self.rules_table.cellWidget(r, 3)
            left = _line_text(left_w).strip()
            try:
                if left and left.replace('.', '', 1).replace('-', '', 1).isdigit():
                    left = float(left) if '.' in left else int(left)
            except Exception:
                pass
            right = _line_text(right_w).strip()
            try:
                if right and right.replace('.', '', 1).replace('-', '', 1).isdigit():
                    right = float(right) if '.' in right else int(right)
            except Exception:
                pass
            comparison = cmp_w.currentData() if cmp_w else 'eq'
            enabled = True
            if isinstance(en_w, QComboBox):
                enabled = bool(en_w.currentData()) if en_w.currentData() is not None else en_w.currentIndex() == 0
            rules.append(dict(left=left, comparison=comparison, right=right, enabled=enabled))
        self.params['rules'] = rules
        self._emit()
        if hasattr(self, '_refresh_condition_result'):
            try:
                self._refresh_condition_result()
            except Exception:
                pass

    def _paths_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(10, 10, 10, 10)
        self.paths_table = QTableWidget(0, 7)
        self.paths_table.setHorizontalHeaderLabels(
            ['启用', '路径ID', '路径名', '左侧值', '比较', '右侧值', '操作']
        )
        self.paths_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.paths_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.paths_table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        self.paths_table.setAlternatingRowColors(True)
        self.paths_table.verticalHeader().setDefaultSectionSize(28)
        lay.addWidget(self.paths_table, 1)
        bar = QHBoxLayout()
        add = QPushButton('添加路径')
        add.clicked.connect(lambda: self._append_path({}))
        up = QPushButton('↑'); down = QPushButton('↓')
        up.setFixedWidth(28); down.setFixedWidth(28)
        up.clicked.connect(lambda: self._move_path(-1))
        down.clicked.connect(lambda: self._move_path(1))
        bar.addWidget(add); bar.addWidget(up); bar.addWidget(down)
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
        en = QComboBox(); en.addItem('是', True); en.addItem('否', False)
        en.setCurrentIndex(0 if path.get('enabled', True) else 1)
        en.currentIndexChanged.connect(lambda *_: self._harvest_paths())
        pid = QLineEdit(str(path.get('id') or f'path{r + 1}'))
        pname = QLineEdit(str(path.get('name') or f'分支{r + 1}'))
        left = QLineEdit(str(path.get('left', '') if path.get('left') is not None else ''))
        cmp = QComboBox()
        for val, lab in COMPARISONS:
            cmp.addItem(lab, val)
        ci = max(0, cmp.findData(path.get('comparison') or 'eq'))
        cmp.setCurrentIndex(ci)
        right = QLineEdit(str(path.get('right', '') if path.get('right') is not None else ''))
        for col, widget in enumerate((en, pid, pname, left, cmp, right)):
            if isinstance(widget, QLineEdit):
                widget.editingFinished.connect(self._harvest_paths)
            else:
                widget.currentIndexChanged.connect(lambda *_: self._harvest_paths())
            self.paths_table.setCellWidget(r, col, widget)
        rm = QPushButton('删'); rm.setFixedWidth(32)
        rm.clicked.connect(lambda *_ , rr=r: self._remove_path(rr))
        self.paths_table.setCellWidget(r, 6, rm)
        if emit:
            self._harvest_paths()

    def _remove_path(self, row):
        if self.paths_table.rowCount() <= 1:
            return
        if 0 <= row < self.paths_table.rowCount():
            self.paths_table.removeRow(row)
            self._harvest_paths()

    def _move_path(self, delta):
        row = self.paths_table.currentRow()
        if row < 0:
            return
        target = row + delta
        if target < 0 or target >= self.paths_table.rowCount():
            return
        self._harvest_paths()
        paths = list(self.params.get('paths') or [])
        paths[row], paths[target] = paths[target], paths[row]
        self.params['paths'] = paths
        self.paths_table.setRowCount(0)
        for path in paths:
            self._append_path(path, emit=False)
        self.paths_table.setCurrentCell(target, 1)
        self._emit()

    def _harvest_paths(self):
        paths = []
        for r in range(self.paths_table.rowCount()):
            en_w = self.paths_table.cellWidget(r, 0)
            pid = self.paths_table.cellWidget(r, 1)
            pname = self.paths_table.cellWidget(r, 2)
            left_w = self.paths_table.cellWidget(r, 3)
            cmp_w = self.paths_table.cellWidget(r, 4)
            right_w = self.paths_table.cellWidget(r, 5)
            enabled = True
            if isinstance(en_w, QComboBox):
                enabled = bool(en_w.currentData()) if en_w.currentData() is not None else en_w.currentIndex() == 0
            paths.append(dict(
                id=(pid.text().strip() if pid else f'path{r + 1}') or f'path{r + 1}',
                name=(pname.text().strip() if pname else f'分支{r + 1}') or f'分支{r + 1}',
                left=left_w.text().strip() if left_w else '',
                comparison=cmp_w.currentData() if cmp_w else 'eq',
                right=right_w.text().strip() if right_w else '',
                enabled=enabled,
            ))
        self.params['paths'] = paths
        self._emit()
        if hasattr(self, '_refresh_condition_result'):
            try:
                self._refresh_condition_result()
            except Exception:
                pass

    def _result_tab(self):
        w = QWidget()
        form = QFormLayout(w)
        form.setContentsMargins(10, 10, 10, 10)
        if self.op == 'branch':
            tip = QLabel(
                '运行输出：pathId / pathName / passed / default。'
                '画布连线 when=路径名；禁用路径跳过。默认路径兜底。'
            )
        else:
            tip = QLabel(
                '运行输出：passed / rules[]。'
                '真出边 when=true，假出边 when=false。禁用规则不参与 AND/OR。'
            )
        tip.setWordWrap(True)
        tip.setStyleSheet('color:#888;')
        form.addRow(tip)
        summary = QLabel(self._summary_text())
        summary.setObjectName('conditionSummary')
        summary.setWordWrap(True)
        form.addRow('当前配置', summary)
        self._result_summary = summary
        self._cond_result_preview = QPlainTextEdit()
        self._cond_result_preview.setObjectName('conditionResultPreview')
        self._cond_result_preview.setReadOnly(True)
        self._cond_result_preview.setMaximumHeight(160)
        form.addRow('设计态求值', self._cond_result_preview)
        self._cond_result_meta = QLabel()
        self._cond_result_meta.setObjectName('conditionResultMeta')
        self._cond_result_meta.setWordWrap(True)
        form.addRow('摘要', self._cond_result_meta)
        refresh = QPushButton('刷新结果显示')
        refresh.setObjectName('conditionResultRefresh')
        refresh.clicked.connect(self._refresh_condition_result)
        form.addRow(refresh)
        self._refresh_condition_result()
        return w

    def _summary_text(self):
        if self.op == 'branch':
            paths = self.params.get('paths') or []
            on = [p for p in paths if p.get('enabled', True)]
            return f'路径 {len(paths)} 条（启用 {len(on)}）；默认={self.params.get("defaultPathId") or "default"}'
        rules = self.params.get('rules') or []
        on = [r for r in rules if r.get('enabled', True)]
        return f'规则 {len(rules)} 条（启用 {len(on)}）；逻辑={self.params.get("logic") or "and"}'

    def _eval_one_design(self, left, comparison, right):
        """Design-time constant eval (no variable resolve). Returns (passed, note)."""
        cmp = comparison or 'eq'
        # Treat bare identifiers as unresolved vars
        def _is_varish(v):
            s = str(v).strip()
            if s == '':
                return False
            if s.replace('.', '', 1).replace('-', '', 1).isdigit():
                return False
            if s.lower() in ('true', 'false', '1', '0', 'yes', 'no', 'ok', 'ng'):
                return False
            if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
                return False
            return True

        if cmp in ('empty', 'not_empty'):
            empty = left is None or str(left).strip() == ''
            return ((empty if cmp == 'empty' else not empty), f'{cmp}({left!r})')
        if cmp in ('is_true', 'is_false'):
            truth = str(left).strip().lower() in ('1', 'true', 'yes', 'ok', 'y')
            if _is_varish(left):
                return (None, f'变量 {left!r} 运行时求值 → {cmp}')
            return ((truth if cmp == 'is_true' else not truth), f'{cmp}({left!r})')
        if _is_varish(left) or _is_varish(right):
            return (None, f'{left!r} {cmp} {right!r}（含变量，运行时求值）')
        # unwrap quotes
        def _coerce(v):
            s = str(v).strip()
            if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
                return s[1:-1]
            if s.lower() in ('true', 'yes', 'ok'):
                return True
            if s.lower() in ('false', 'no', 'ng'):
                return False
            try:
                if s.replace('.', '', 1).replace('-', '', 1).isdigit():
                    return float(s) if '.' in s else int(s)
            except Exception:
                pass
            return s
        a, b = _coerce(left), _coerce(right)
        try:
            if cmp == 'eq':
                return (a == b, f'{a!r} == {b!r}')
            if cmp == 'ne':
                return (a != b, f'{a!r} != {b!r}')
            if cmp == 'gt':
                return (a > b, f'{a!r} > {b!r}')
            if cmp == 'gte':
                return (a >= b, f'{a!r} >= {b!r}')
            if cmp == 'lt':
                return (a < b, f'{a!r} < {b!r}')
            if cmp == 'lte':
                return (a <= b, f'{a!r} <= {b!r}')
            if cmp == 'contains':
                return (str(b) in str(a), f'{b!r} in {a!r}')
            if cmp == 'starts_with':
                return (str(a).startswith(str(b)), f'{a!r}.startswith({b!r})')
            if cmp == 'ends_with':
                return (str(a).endswith(str(b)), f'{a!r}.endswith({b!r})')
            if cmp == 'regex':
                import re
                return (bool(re.search(str(b), str(a))), f're.search({b!r}, {a!r})')
        except Exception as exc:
            return (None, f'求值失败: {exc}')
        return (None, f'未知比较 {cmp}')

    def _refresh_condition_result(self):
        if hasattr(self, '_result_summary') and self._result_summary is not None:
            self._result_summary.setText(self._summary_text())
        lines = []
        if self.op == 'branch':
            paths = self.params.get('paths') or []
            default_id = self.params.get('defaultPathId') or 'default'
            hit = None
            for i, p in enumerate(paths):
                if not p.get('enabled', True):
                    lines.append(f'#{i+1} {p.get("name") or p.get("id")} [禁用]')
                    continue
                if (p.get('id') or '') == default_id or (p.get('name') or '') == '默认':
                    lines.append(f'#{i+1} {p.get("name") or p.get("id")} [默认兜底]')
                    continue
                passed, note = self._eval_one_design(p.get('left'), p.get('comparison'), p.get('right'))
                mark = '✓' if passed is True else ('·' if passed is None else '✗')
                lines.append(f'#{i+1} {p.get("name") or p.get("id")} {mark} {note}')
                if hit is None and passed is True:
                    hit = p
            if hit:
                verdict = f'设计态命中 → {hit.get("name") or hit.get("id")}（when={hit.get("name") or hit.get("id")}）'
            else:
                verdict = f'设计态未命中常量 → 默认 {default_id}'
            meta = verdict
        else:
            rules = self.params.get('rules') or []
            logic = self.params.get('logic') or 'and'
            flags = []
            any_runtime = False
            for i, r in enumerate(rules):
                if not r.get('enabled', True):
                    lines.append(f'#{i+1} [禁用] {r.get("left")!r} {r.get("comparison")} {r.get("right")!r}')
                    continue
                passed, note = self._eval_one_design(r.get('left'), r.get('comparison'), r.get('right'))
                if passed is None:
                    any_runtime = True
                    mark = '?'
                else:
                    mark = '✓' if passed else '✗'
                    flags.append(passed)
                lines.append(f'#{i+1} {mark} {note}')
            if any_runtime or not flags:
                verdict = f'逻辑={logic} · 含变量或空规则 → 运行时求值'
                passed_preview = None
            else:
                passed_preview = any(flags) if logic == 'or' else all(flags)
                verdict = f'逻辑={logic} · 设计态 passed={passed_preview} → when={"true" if passed_preview else "false"}'
            meta = verdict
        text = '\n'.join(lines) if lines else '(无规则/路径)'
        if hasattr(self, '_cond_result_preview') and self._cond_result_preview is not None:
            self._cond_result_preview.setPlainText(text)
        if hasattr(self, '_cond_result_meta') and self._cond_result_meta is not None:
            self._cond_result_meta.setText(meta)
