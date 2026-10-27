"""变量计算（var_calc）属性浮窗 — VisionMaster p=23 壳.

表列：名称 / 表达式 / 初始值 / 输出类型 / 初始化。
运行时对简易算术表达式求值并写入 flow 变量。
"""
from copy import deepcopy

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTabWidget, QFormLayout,
    QLineEdit, QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView, QScrollArea, QFrame, QComboBox,
)


def _empty_expr(i=0):
    return dict(
        name=f'var{i}',
        expression='0',
        initial=0,
        outType='number',
        initOnRun=False,
    )


def normalize_var_calc_params(params=None):
    p = deepcopy(params or {})
    rows = p.get('expressions')
    if not isinstance(rows, list) or not rows:
        rows = [_empty_expr(0)]
    cleaned = []
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            cleaned.append(_empty_expr(i))
            continue
        name = str(row.get('name') or f'var{i}').strip() or f'var{i}'
        cleaned.append(dict(
            name=name[:64],
            expression=str(row.get('expression') if row.get('expression') is not None else '0'),
            initial=row.get('initial', 0),
            outType=row.get('outType') or 'number',
            initOnRun=bool(row.get('initOnRun', False)),
        ))
    p['expressions'] = cleaned
    p.setdefault('scope', 'flow')
    return p


class VarCalcPanel(QWidget):
    changed = Signal(dict)

    def __init__(self, step, definition, project, parent=None):
        super().__init__(parent)
        self.step = deepcopy(step)
        self.definition = definition or {}
        self.project = project or {}
        self.params = normalize_var_calc_params(step.get('params'))
        self.step['params'] = self.params
        self._syncing = False

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        hint = QLabel(
            '对齐 VisionMaster「变量计算」：表达式表（名称/公式/初始值/类型/初始化）；'
            '支持 + - * / () 与已有变量名；运行写入流程变量。'
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

    def _basic_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(10, 10, 10, 10)
        form = QFormLayout()
        name = QLineEdit(self.step.get('name') or '变量计算')
        name.setMaxLength(80)
        name.editingFinished.connect(lambda: self._set_top('name', name.text()))
        form.addRow('模块名称', name)
        scope = QComboBox()
        for s, lab in (('flow', '流程变量'), ('global', '全局变量'), ('module', '模块变量')):
            scope.addItem(lab, s)
        scope.setCurrentIndex(max(0, scope.findData(self.params.get('scope') or 'flow')))
        scope.currentIndexChanged.connect(lambda _: self._set_param('scope', scope.currentData()))
        form.addRow('写入作用域', scope)
        ops = QLabel('可用运算：+  −  ×  ÷  () ；比较：== != < > <= >=（结果 0/1）')
        ops.setStyleSheet('color:#555;')
        form.addRow(ops)
        lay.addLayout(form)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(['名称', '表达式', '初始值', '输出类型', '初始化'])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.itemChanged.connect(self._on_item)
        lay.addWidget(self.table, 1)

        bar = QHBoxLayout()
        add = QPushButton('添加')
        add.clicked.connect(lambda *_: self._add())
        rem = QPushButton('删除选中')
        rem.clicked.connect(lambda *_: self._rem())
        ins = QPushButton('插入上游字段')
        ins.setToolTip('从最近一次运行结果挑选上游模块字段，插入到当前表达式')
        ins.clicked.connect(lambda *_: self._insert_upstream_field())
        bar.addWidget(add)
        bar.addWidget(rem)
        bar.addWidget(ins)
        bar.addStretch(1)
        lay.addLayout(bar)
        self._reload()
        return w

    def _result_tab(self):
        w = QWidget()
        form = QFormLayout(w)
        form.setContentsMargins(10, 10, 10, 10)
        tip = QLabel('运行结果：values（名→值）、errors（求值失败项）。')
        tip.setWordWrap(True)
        tip.setStyleSheet('color:#888;')
        form.addRow(tip)
        return w

    def _reload(self):
        self._syncing = True
        rows = self.params.get('expressions') or []
        self.table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            vals = [
                str(row.get('name') or ''),
                str(row.get('expression') or ''),
                str(row.get('initial') if row.get('initial') is not None else ''),
                str(row.get('outType') or 'number'),
                '是' if row.get('initOnRun') else '否',
            ]
            for c, text in enumerate(vals):
                self.table.setItem(r, c, QTableWidgetItem(text))
        self._syncing = False

    def _on_item(self, item):
        if self._syncing:
            return
        r, c = item.row(), item.column()
        rows = self.params.setdefault('expressions', [])
        while len(rows) <= r:
            rows.append(_empty_expr(len(rows)))
        row = rows[r]
        text = (item.text() or '').strip()
        if c == 0:
            row['name'] = text or f'var{r}'
        elif c == 1:
            row['expression'] = text
        elif c == 2:
            try:
                row['initial'] = float(text) if '.' in text else int(text)
            except ValueError:
                row['initial'] = text
        elif c == 3:
            row['outType'] = text if text in ('number', 'string', 'boolean') else 'number'
        elif c == 4:
            row['initOnRun'] = text not in ('否', '0', 'false', 'False', 'N', 'n')
        self._emit()


    def _insert_upstream_field(self):
        """Specialized-panel field picker: insert results.<id>.<field> into expression."""
        from desktop.upstream_field_picker import pick_upstream_field, host_last_result
        picked = pick_upstream_field(
            self, self.project, step_id=self.step.get('id'),
            last_result=host_last_result(self),
        )
        if not picked:
            return
        _nid, _field, token = picked
        r = self.table.currentRow()
        if r < 0:
            r = 0 if self.table.rowCount() else -1
        if r < 0:
            self._add()
            r = 0
        item = self.table.item(r, 1)
        cur = item.text() if item else ''
        new_expr = (cur + ('+' if cur.strip() else '') + token) if cur else token
        self._syncing = True
        self.table.setItem(r, 1, QTableWidgetItem(new_expr))
        self._syncing = False
        self._on_item(self.table.item(r, 1))

    def _add(self):
        rows = self.params.setdefault('expressions', [])
        rows.append(_empty_expr(len(rows)))
        self._reload()
        self._emit()

    def _rem(self):
        idxs = sorted({i.row() for i in self.table.selectedIndexes()}, reverse=True)
        rows = self.params.setdefault('expressions', [])
        for r in idxs:
            if 0 <= r < len(rows):
                rows.pop(r)
        if not rows:
            rows.append(_empty_expr(0))
        self._reload()
        self._emit()
