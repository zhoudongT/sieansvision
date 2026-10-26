"""Native three-scope variable tables, with typed nested values and no JSON editor."""
from copy import deepcopy
import math
import re

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QDialog, QDialogButtonBox,
    QFormLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QTreeWidget, QTreeWidgetItem, QVBoxLayout)

TYPE_LABELS = {'number': '数值', 'integer': '整数', 'string': '文本', 'boolean': '开关',
               'array': '数组', 'object': '结构体', 'null': '空值', 'number[]': '数值数组',
               'integer[]': '整数数组', 'string[]': '文本数组', 'boolean[]': '开关数组'}
FORBIDDEN = {'__proto__', 'constructor', 'prototype'}
NAME = re.compile(r'^[A-Za-z_][A-Za-z0-9_]{0,63}$')
MISSING = object()


def value_kind(value):
    if value is None: return 'null'
    if isinstance(value, bool): return 'boolean'
    if isinstance(value, int): return 'integer'
    if isinstance(value, float): return 'number'
    if isinstance(value, list): return 'array'
    if isinstance(value, dict): return 'object'
    return 'string'


def value_summary(value):
    if value is MISSING: return '尚无当前值'
    if value is None: return '空值'
    if isinstance(value, bool): return '是' if value else '否'
    if isinstance(value, dict): return f'结构体 · {len(value)} 个字段'
    if isinstance(value, list): return f'数组 · {len(value)} 项'
    return str(value)


def default_value(kind):
    if kind.endswith('[]'): return []
    return deepcopy({'number': 0.0, 'integer': 0, 'string': '', 'boolean': False,
                     'array': [], 'object': {}, 'null': None}[kind])


def type_matches(value, kind):
    if not kind: return True
    if kind.endswith('[]'):
        return isinstance(value, list) and all(type_matches(v, kind[:-2]) for v in value)
    if kind == 'integer':
        return type(value) in (int, float) and abs(value) <= 9007199254740991 and int(value) == value
    if kind == 'number':
        try: return type(value) in (int, float) and math.isfinite(value)
        except OverflowError: return False
    return value_kind(value) == kind


def validate_values(values, types):
    if len(types) > 1000: raise ValueError('每个作用域最多 1000 项类型定义')
    for name, kind in types.items():
        if not NAME.fullmatch(name) or name in FORBIDDEN: raise ValueError('固定类型变量名称无效：' + name)
        if kind not in TYPE_LABELS: raise ValueError('不支持的变量类型：' + str(kind))
        if name not in values: raise ValueError(name + ' 缺少初始值，请先删除类型约束')
        if not type_matches(values[name], kind): raise ValueError(name + ' 要求' + TYPE_LABELS[kind] + '，输入值类型不匹配')


class DataTree(QTreeWidget):
    """Read-only nested records; preserves false, zero, null and missing distinctly."""
    def __init__(self, value=MISSING, parent=None):
        super().__init__(parent)
        self.setHeaderLabels(['字段 / 序号', '值', '类型'])
        self.setAlternatingRowColors(True)
        self.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.itemExpanded.connect(self._expand)
        self.set_value(value)

    def set_value(self, value):
        self.clear()
        if isinstance(value, (dict, list)):
            pairs = value.items() if isinstance(value, dict) else enumerate(value)
            for key, item in pairs: self._append(self, key, item)
        else: self._append(self, '值', value)

    def _append(self, parent, key, value):
        text = value_summary(value)
        if isinstance(value, str) and value.startswith('data:image/'):
            text = '图像数据'
        item = QTreeWidgetItem(parent, [str(key), text, '' if value is MISSING else TYPE_LABELS[value_kind(value)]])
        if isinstance(value, (dict, list)) and value:
            item.setData(0, Qt.ItemDataRole.UserRole, deepcopy(value))
            QTreeWidgetItem(item, ['展开查看'])
        return item

    def _expand(self, item):
        value = item.data(0, Qt.ItemDataRole.UserRole)
        if value is None: return
        item.setData(0, Qt.ItemDataRole.UserRole, None)
        item.takeChildren()
        pairs = value.items() if isinstance(value, dict) else enumerate(value)
        for key, child in pairs: self._append(item, key, child)


class TypedValueDialog(QDialog):
    """A recursive table editor. Parsing happens at acceptance, never during typing."""
    def __init__(self, value, parent=None):
        super().__init__(parent)
        self.setWindowTitle('编辑变量值'); self.resize(650, 480)
        self.value = deepcopy(value)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel('选择类型并逐项填写；数组和结构体可选中后添加字段。'))
        self.tree = QTreeWidget(); self.tree.setHeaderLabels(['字段 / 序号', '类型', '值'])
        self.tree.header().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.tree)
        row = QHBoxLayout(); layout.addLayout(row)
        for text, callback in [('添加字段 / 数组项', self.add_item), ('删除所选项', self.remove_item)]:
            button = QPushButton(text); button.clicked.connect(callback); row.addWidget(button)
        self.error = QLabel(); self.error.setWordWrap(True); layout.addWidget(self.error)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); layout.addWidget(buttons)
        self.root = self._append(self.tree, '值', value, editable_name=False)
        self.tree.expandToDepth(1)

    def _append(self, parent, name, value, editable_name=True):
        item = QTreeWidgetItem(parent)
        name_field = QLineEdit(str(name)); name_field.setReadOnly(not editable_name)
        self.tree.setItemWidget(item, 0, name_field)
        kind = QComboBox()
        for key in ['number', 'integer', 'string', 'boolean', 'array', 'object', 'null']: kind.addItem(TYPE_LABELS[key], key)
        kind.setCurrentIndex(kind.findData(value_kind(value))); self.tree.setItemWidget(item, 1, kind)
        self._value_control(item, value)
        kind.currentIndexChanged.connect(lambda _, item=item, kind=kind: self._value_control(item, default_value(kind.currentData())))
        return item

    def _value_control(self, item, value):
        item.takeChildren()
        if isinstance(value, (dict, list)):
            self.tree.setItemWidget(item, 2, QLabel('逐项编辑'))
            pairs = value.items() if isinstance(value, dict) else enumerate(value)
            for key, child in pairs: self._append(item, key, child, isinstance(value, dict))
            item.setExpanded(True)
        elif isinstance(value, bool):
            field = QComboBox(); field.addItem('否', False); field.addItem('是', True); field.setCurrentIndex(int(value))
            self.tree.setItemWidget(item, 2, field)
        elif value is None: self.tree.setItemWidget(item, 2, QLabel('空值'))
        else: self.tree.setItemWidget(item, 2, QLineEdit(str(value)))

    def add_item(self):
        parent = self.tree.currentItem() or self.root
        kind = self.tree.itemWidget(parent, 1).currentData()
        if kind not in ('array', 'object'):
            self.error.setText('请先选择数组或结构体行。'); return
        names = {self.tree.itemWidget(parent.child(i), 0).text() for i in range(parent.childCount())}
        index = parent.childCount()
        name = str(index) if kind == 'array' else 'field' + str(index + 1)
        while name in names: index += 1; name = 'field' + str(index + 1)
        self._append(parent, name, '', kind == 'object'); parent.setExpanded(True); self.error.clear()

    def remove_item(self):
        item = self.tree.currentItem()
        if item is None or item.parent() is None: return
        parent = item.parent(); parent.takeChild(parent.indexOfChild(item))
        if self.tree.itemWidget(parent, 1).currentData() == 'array':
            for i in range(parent.childCount()): self.tree.itemWidget(parent.child(i), 0).setText(str(i))

    def _read(self, item, depth=0):
        if depth > 20: raise ValueError('嵌套内容最多 20 层')
        kind = self.tree.itemWidget(item, 1).currentData(); field = self.tree.itemWidget(item, 2)
        if kind in ('array', 'object'):
            result = [] if kind == 'array' else {}
            for i in range(item.childCount()):
                child = item.child(i); value = self._read(child, depth + 1)
                if kind == 'array': result.append(value)
                else:
                    name = self.tree.itemWidget(child, 0).text()
                    if name in FORBIDDEN or name in result: raise ValueError('字段名称重复或不可使用：' + name)
                    result[name] = value
            return result
        if kind == 'null': return None
        if kind == 'boolean': return field.currentData()
        if kind == 'string': return field.text()
        text = field.text().strip()
        try: value = int(text) if kind == 'integer' else float(text)
        except ValueError: raise ValueError('请输入有效的' + TYPE_LABELS[kind]) from None
        if not type_matches(value, kind): raise ValueError('数值必须有限；整数范围为 ±9007199254740991')
        return value

    def accept(self):
        try: self.value = self._read(self.root)
        except ValueError as error: self.error.setText(str(error)); return
        super().accept()


class VariableRowDialog(QDialog):
    def __init__(self, name='', value=None, fixed='', editable_type=True, parent=None):
        super().__init__(parent); self.setWindowTitle('变量定义 / 当前值'); self.resize(430, 240)
        self.value = deepcopy(value)
        layout = QFormLayout(self)
        self.name = QLineEdit(name); layout.addRow('变量名称', self.name)
        self.fixed = QComboBox(); self.fixed.addItem('动态（不限制）', '')
        for kind, label in TYPE_LABELS.items(): self.fixed.addItem(label, kind)
        self.fixed.setCurrentIndex(max(0, self.fixed.findData(fixed))); self.fixed.setEnabled(editable_type)
        layout.addRow('固定类型', self.fixed)
        self.value_button = QPushButton(value_summary(value)); self.value_button.clicked.connect(self.edit_value)
        layout.addRow('变量值', self.value_button)
        self.error = QLabel(); self.error.setWordWrap(True); layout.addRow(self.error)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); layout.addRow(buttons)

    def edit_value(self):
        dialog = TypedValueDialog(self.value, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.value = dialog.value; self.value_button.setText(value_summary(self.value))

    def accept(self):
        name, kind = self.name.text(), self.fixed.currentData()
        if not name or name in FORBIDDEN or (kind and not NAME.fullmatch(name)):
            self.error.setText('名称不能为空或为保留字；固定类型名称须以字母或下划线开头。'); return
        if not type_matches(self.value, kind):
            self.error.setText('值不符合所选固定类型，请点击“变量值”修改。'); return
        super().accept()


class VariablesDialog(QDialog):
    def __init__(self, document, backend, parent=None):
        super().__init__(parent)
        self.document, self.backend = document, backend
        self.pending = {}; self.snapshot = None; self.runtime_draft = None; self._applying = False; self.busy = False
        self.setWindowTitle('三级变量管理'); self.resize(1080, 650)
        layout = QVBoxLayout(self)
        row = QHBoxLayout(); layout.addLayout(row)
        self.mode = QComboBox()
        for label, key in [('变量总览', 'overview'), ('工程初始定义', 'initial'), ('运行当前值', 'current')]: self.mode.addItem(label, key)
        self.scope = QComboBox(); self.search = QLineEdit(); self.search.setPlaceholderText('搜索名称')
        row.addWidget(self.mode); row.addWidget(self.scope); row.addWidget(self.search, 1)
        refresh = QPushButton('重新读取（撤销当前值编辑）'); refresh.clicked.connect(self.refresh); row.addWidget(refresh)
        self.hint = QLabel(); self.hint.setWordWrap(True); layout.addWidget(self.hint)
        self.table = QTableWidget(0, 6); self.table.setObjectName('variableTable')
        self.table.setHorizontalHeaderLabels(['作用域', '名称', '固定类型', '工程初始值', '运行当前值', '校验'])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.cellDoubleClicked.connect(lambda *_: self.edit_variable())
        layout.addWidget(self.table, 1)
        bar = QHBoxLayout(); layout.addLayout(bar)
        self.add_button = QPushButton('新增变量'); self.edit_button = QPushButton('编辑所选'); self.remove_button = QPushButton('删除所选')
        for button, callback in [(self.add_button, self.add_variable), (self.edit_button, self.edit_variable), (self.remove_button, self.remove_variable)]:
            button.clicked.connect(callback); bar.addWidget(button)
        bar.addStretch(); self.apply_button = QPushButton('应用'); self.apply_button.clicked.connect(self.apply); bar.addWidget(self.apply_button)
        close = QPushButton('关闭'); close.clicked.connect(self.reject); bar.addWidget(close)
        self.message = QLabel(); self.message.setWordWrap(True); layout.addWidget(self.message)
        self._load_definitions()
        self.mode.currentIndexChanged.connect(self.render); self.scope.currentIndexChanged.connect(self.render); self.search.textChanged.connect(self.render)
        self.document.changed.connect(self._document_changed)
        self.backend.result.connect(self._result); self.backend.error.connect(self._error)
        self.finished.connect(self._disconnect)
        self.render(); QTimer.singleShot(0, self.refresh)

    def _signature(self):
        p = self.document.project
        return deepcopy((p['id'], p.get('variables', {}), p.get('variableTypes', {}),
            [(s['id'], s.get('variables', {}), s.get('variableTypes', {})) for s in p['steps']]))

    def _load_definitions(self):
        p = self.document.project; self.base = self._signature(); self.stale = False
        self.initial = {'flow': deepcopy(p.get('variables', {}))}
        self.types = {'flow': deepcopy(p.get('variableTypes', {}))}
        self.labels = {'global': '全局', 'flow': '流程'}
        for step in p['steps']:
            scope = 'module:' + step['id']; self.labels[scope] = '模块 · ' + step.get('name', step['id'])
            self.initial[scope] = deepcopy(step.get('variables', {})); self.types[scope] = deepcopy(step.get('variableTypes', {}))
        self.original_initial, self.original_types = deepcopy(self.initial), deepcopy(self.types)
        self.scope.blockSignals(True); self.scope.clear(); self.scope.addItem('全部作用域', '')
        for key, label in self.labels.items(): self.scope.addItem(label, key)
        self.scope.blockSignals(False)

    def _document_changed(self):
        if not self._applying and self.base != self._signature():
            self.stale = True; self.message.setText('工程变量定义或模块已变更，请重新读取后继续编辑。'); self.render()

    def set_busy(self, busy):
        self.busy = bool(busy); self.render()

    def _disconnect(self, *_):
        for signal, slot in [(self.document.changed, self._document_changed), (self.backend.result, self._result), (self.backend.error, self._error)]:
            try: signal.disconnect(slot)
            except (RuntimeError, TypeError): pass
        self.pending.clear()

    def refresh(self):
        if any(tag == 'read' for tag in self.pending.values()): return
        if self.stale: self._load_definitions()
        self.pending[self.backend.request('variables/get', {'project': deepcopy(self.document.project)})] = 'read'
        self.message.setText('正在读取本机运行变量…')

    def _result(self, request_id, result):
        tag = self.pending.pop(request_id, None)
        if tag is None or self.stale: return
        self.snapshot = deepcopy(result); self.runtime_draft = deepcopy(result)
        self.message.setText('三级变量已写入。' if tag == 'write' else '已读取运行值。初始值修改不覆盖已有运行值。')
        self.render()

    def _error(self, request_id, message):
        if self.pending.pop(request_id, None) is not None:
            self.message.setText(message); self.render()

    @staticmethod
    def _scope_values(state, scope):
        if state is None: return {}
        return state.setdefault('modules', {}).setdefault(scope.split(':', 1)[1], {}) if scope.startswith('module:') else state.setdefault(scope, {})

    def _values_types(self, scope):
        if self.mode.currentData() == 'initial': return self.initial[scope], self.types[scope]
        return self._scope_values(self.runtime_draft, scope), (self.runtime_draft.setdefault('globalTypes', {}) if scope == 'global' else self.types[scope])

    def render(self, *_):
        mode = self.mode.currentData(); initial = mode == 'initial'; overview = mode == 'overview'
        self.hint.setText('初始定义随工程保存；全局变量在“运行当前值”管理。' if initial else '值为最近读取的快照。流程与模块类型在“工程初始定义”修改；全局类型随当前值持久保存。')
        editable = not overview and not self.busy and not self.stale and (initial or self.runtime_draft is not None)
        self.add_button.setEnabled(editable); self.edit_button.setEnabled(not self.stale and (overview or editable)); self.remove_button.setEnabled(editable)
        self.apply_button.setEnabled(editable and not self.pending); self.apply_button.setText('应用初始定义到工程' if initial else '写入当前值')
        self.apply_button.setVisible(not overview)
        self.table.setRowCount(0)
        for scope, label in self.labels.items():
            if self.scope.currentData() and scope != self.scope.currentData(): continue
            if initial and scope == 'global': continue
            initials = self.initial.get(scope, {}); current = self._scope_values(self.runtime_draft, scope)
            types = (self.runtime_draft or {}).get('globalTypes', {}) if scope == 'global' else self.types[scope]
            names = list(dict.fromkeys([*initials, *current, *types]))
            for name in names:
                if self.search.text().lower() not in name.lower(): continue
                value = initials.get(name, MISSING) if initial else current.get(name, MISSING)
                fixed = types.get(name, ''); state = '动态类型' if not fixed else '符合类型' if value is not MISSING and type_matches(value, fixed) else '缺少值 / 类型不符'
                row = self.table.rowCount(); self.table.insertRow(row)
                initial_text = value_summary(initials[name]) if name in initials else '全局持久值' if scope == 'global' else '未定义'
                for column, text in enumerate([label, name, TYPE_LABELS.get(fixed, '动态'), initial_text, value_summary(current.get(name, MISSING)), state]):
                    item = QTableWidgetItem(text); self.table.setItem(row, column, item)
                self.table.item(row, 0).setData(Qt.ItemDataRole.UserRole, (scope, name))

    def _selected(self):
        row = self.table.currentRow()
        return self.table.item(row, 0).data(Qt.ItemDataRole.UserRole) if row >= 0 else None

    def add_variable(self):
        scope = self.scope.currentData()
        if not scope: scope = 'flow'
        if self.mode.currentData() == 'initial' and scope == 'global':
            self.message.setText('请切换到运行当前值设置全局变量。'); return
        self._edit(scope, None)

    def edit_variable(self):
        selected = self._selected()
        if not selected: return
        scope, name = selected
        if self.mode.currentData() == 'overview':
            value = self._scope_values(self.runtime_draft, scope).get(name, self.initial.get(scope, {}).get(name, MISSING))
            dialog = QDialog(self); dialog.setWindowTitle(name + ' · 值预览'); dialog.resize(650, 450)
            QVBoxLayout(dialog).addWidget(DataTree(value)); dialog.exec(); return
        self._edit(scope, name)

    def _edit(self, scope, old):
        if self.busy or self.stale or (self.mode.currentData() == 'current' and self.runtime_draft is None): return
        values, types = self._values_types(scope); can_type = self.mode.currentData() == 'initial' or scope == 'global'
        dialog = VariableRowDialog(old or '', values.get(old, 0), types.get(old, ''), can_type, self)
        if old and not can_type and old in types: dialog.name.setReadOnly(True)
        if dialog.exec() != QDialog.DialogCode.Accepted: return
        name, kind = dialog.name.text(), dialog.fixed.currentData()
        if name != old and name in values: self.message.setText('同一作用域变量名称不能重复。'); return
        if old and old != name: values.pop(old, None); types.pop(old, None)
        values[name] = deepcopy(dialog.value)
        if can_type:
            if kind: types[name] = kind
            else: types.pop(name, None)
        self.render()

    def remove_variable(self):
        if self.busy or self.stale or self.mode.currentData() == 'overview': return
        selected = self._selected()
        if not selected: return
        scope, name = selected; values, types = self._values_types(scope)
        if self.mode.currentData() == 'current' and scope == 'global' and name in types:
            self.message.setText('请先解除固定类型约束，再删除当前值。'); return
        values.pop(name, None)
        if self.mode.currentData() == 'initial': types.pop(name, None)
        self.render()

    def apply(self):
        if self.busy or self.stale or self.pending: return
        try:
            if self.mode.currentData() == 'initial':
                project = deepcopy(self.document.project)
                for scope in self.initial: validate_values(self.initial[scope], self.types[scope])
                for scope, target in [('flow', project), *[('module:' + s['id'], s) for s in project['steps']]]:
                    if self.initial[scope] != self.original_initial[scope]: target['variables'] = deepcopy(self.initial[scope])
                    if self.types[scope] != self.original_types[scope]: target['variableTypes'] = deepcopy(self.types[scope])
                self._applying = True
                try: self.document.commit(project)
                finally: self._applying = False
                self.base = self._signature(); self.original_initial, self.original_types = deepcopy(self.initial), deepcopy(self.types)
                self.message.setText('初始定义已应用，请保存工程。运行当前值保持原快照。')
            else:
                if self.runtime_draft is None: raise ValueError('请先读取当前值')
                for scope in self.labels:
                    values, types = self._values_types(scope)
                    # Deleting a current value restores its project default on the engine.
                    validate_values({**self.initial.get(scope, {}), **values}, types)
                request_id = self.backend.request('variables/set', {'project': deepcopy(self.document.project), 'state': deepcopy(self.runtime_draft), 'revision': self.runtime_draft['revision']})
                self.pending[request_id] = 'write'; self.message.setText('正在写入当前值…'); self.render()
        except (ValueError, KeyError) as error: self.message.setText(str(error))
