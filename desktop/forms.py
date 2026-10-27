"""Native, schema-driven operator forms and lazily expanded result trees.

Editors keep private copies. Only committed user edits emit a complete step;
opening a form never materializes defaults or rewrites unknown saved fields.
"""
from copy import deepcopy
import re

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout, QGroupBox, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QPushButton, QScrollArea, QSpinBox,
    QStackedWidget, QTabWidget, QTableWidget, QTreeWidget, QTreeWidgetItem,
    QVBoxLayout, QWidget,
)


TYPES = [('string', '文本'), ('number', '数值'), ('integer', '整数'),
         ('boolean', '开关'), ('object', '结构体'), ('array', '数组')]
SCOPES = [('flow', '流程变量'), ('global', '全局变量'), ('module', '模块变量')]
_NAME = re.compile(r'^[A-Za-z_][A-Za-z0-9_]{0,63}$')
_PATH = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*(?:\.(?:[A-Za-z_][A-Za-z0-9_]*|[0-9]+))*$')
_FORBIDDEN = {'__proto__', 'constructor', 'prototype'}


def _valid_path(path):
    return bool(_PATH.fullmatch(path)) and not (_FORBIDDEN & set(path.split('.')))


def _kind(value):
    if isinstance(value, bool):
        return 'boolean'
    if isinstance(value, int):
        return 'integer'
    if isinstance(value, float):
        return 'number'
    if isinstance(value, dict):
        return 'object'
    if isinstance(value, list):
        return 'array'
    return 'string'


def _properties(schema):
    props = schema.get('properties', [])
    if isinstance(props, dict):
        return [dict(value, key=key) for key, value in props.items()]
    return props


def _default(schema):
    if 'default' in schema:
        return deepcopy(schema['default'])
    kind = schema.get('type', 'string')
    if kind == 'object':
        return {p['key']: _default(p) for p in _properties(schema)
                if p.get('required') or 'default' in p}
    return {'integer': 0, 'number': 0.0, 'boolean': False, 'array': []}.get(kind, '')


def _label(schema):
    label = schema.get('label', schema.get('key', '值'))
    if schema.get('unit'):
        label += ' (' + schema['unit'] + ')'
    return label + (' *' if schema.get('required') else '')


# Halcon/VisionMaster-style: separate iconic vs control, with compact type marks.
_TYPE_MARK = {
    'integer': '整', 'number': '数', 'boolean': '开关', 'string': '文',
    'object': '结构', 'array': '列表', 'any': '任意', 'image': '图',
}


def _type_badge(schema_or_type):
    kind = schema_or_type if isinstance(schema_or_type, str) else schema_or_type.get('type', 'string')
    return _TYPE_MARK.get(kind, '文')


def _section(title, hint=''):
    """VisionMaster-like property group (标题 + 可选说明)."""
    from PySide6.QtWidgets import QGroupBox, QVBoxLayout, QFormLayout, QLabel
    box = QGroupBox(title)
    box.setObjectName('propertySection')
    root = QVBoxLayout(box)
    root.setContentsMargins(10, 12, 10, 10)
    root.setSpacing(8)
    if hint:
        tip = QLabel(hint)
        tip.setWordWrap(True)
        tip.setObjectName('sectionHint')
        root.addWidget(tip)
    form = QFormLayout()
    form.setContentsMargins(0, 0, 0, 0)
    form.setSpacing(10)
    form.setHorizontalSpacing(12)
    form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
    form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
    form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    root.addLayout(form)
    return box, form


def _clear(layout):
    while layout.count():
        item = layout.takeAt(0)
        if item.widget():
            item.widget().deleteLater()
        elif item.layout():
            _clear(item.layout())


def _upstream(project, step_id):
    parents, pending = set(), [step_id]
    while pending:
        node = pending.pop()
        for edge in project.get('edges', []):
            if edge.get('to') == node and edge.get('from') not in parents:
                parents.add(edge['from'])
                pending.append(edge['from'])
    return [s for s in project.get('steps', []) if s.get('id') in parents and s.get('id') != step_id]


def _flatten_result_fields(obj, prefix='', depth=0, limit=40):
    """Collect dotted field paths from a result dict for the upstream picker."""
    out = []
    if depth > 3 or len(out) >= limit:
        return out
    if isinstance(obj, dict):
        for key, val in obj.items():
            if key in ('image', 'annotated', 'thumbnail', 'preview') and depth == 0:
                out.append(key if not prefix else f'{prefix}.{key}')
                continue
            path = key if not prefix else f'{prefix}.{key}'
            out.append(path)
            if isinstance(val, (dict, list)) and depth < 2:
                out.extend(_flatten_result_fields(val, path, depth + 1, limit - len(out)))
            if len(out) >= limit:
                break
    elif isinstance(obj, list) and obj and depth < 2:
        out.append(f'{prefix}.0' if prefix else '0')
        if isinstance(obj[0], dict):
            out.extend(_flatten_result_fields(obj[0], f'{prefix}.0' if prefix else '0', depth + 1, limit - len(out)))
    # unique preserve order
    seen, uniq = set(), []
    for p in out:
        if p not in seen:
            seen.add(p)
            uniq.append(p)
    return uniq[:limit]


def result_field_index(last_result, nodes, definitions=None):
    """Map upstream step id → suggested field paths from last run (fallback: common keys)."""
    records = (last_result or {}).get('results') or []
    by_id = {r.get('id'): r for r in records if isinstance(r, dict) and r.get('id')}
    defs = definitions or {}
    index = {}
    for node in nodes or []:
        nid = node.get('id')
        if not nid:
            continue
        rec = by_id.get(nid) or {}
        result = (rec.get('output') or {}).get('result') if isinstance(rec.get('output'), dict) else None
        if result is None:
            result = rec.get('result') if isinstance(rec.get('result'), dict) else {}
        paths = _flatten_result_fields(result) if result else []
        if not paths:
            op = node.get('operation') or ''
            # light fallbacks by op + generic
            fallback = {
                'receive_data': ['payload', 'ok', 'device', 'bytes'],
                'send_data': ['ok', 'device', 'bytes', 'payload'],
                'var_calc': ['value', 'ok', 'expression', 'error'],
                'group': ['ok', 'status', 'outputs'],
            }.get(op, ['ok', 'status', 'value', 'count', 'payload'])
            # definition outputs if available
            dout = (defs.get(op) or {}).get('outputs') if isinstance(defs, dict) else None
            if dout:
                from_def = []
                for o in dout:
                    if isinstance(o, dict):
                        from_def.append(o.get('key') or o.get('name') or '')
                    elif isinstance(o, str):
                        from_def.append(o)
                fallback = [x for x in from_def if x] or fallback
            paths = fallback
        index[nid] = paths
    return index


class ReferenceEditor(QWidget):
    """Build a runtime reference without requiring reference syntax from users."""
    changed = Signal(object)

    def __init__(self, value, nodes, parent=None, field_index=None):
        super().__init__(parent)
        self._field_index = field_index or {}
        self.scope = QComboBox()
        self.scope.setObjectName('referenceScope')
        for key, label in SCOPES + [('results', '上游结果')]:
            self.scope.addItem(label, key)
        self.node = QComboBox()
        self.node.setObjectName('referenceNode')
        for node in nodes:
            self.node.addItem(node.get('name', node['id']), node['id'])
        self.field = QComboBox()
        self.field.setObjectName('referenceField')
        self.field.setEditable(True)
        self.field.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.field.lineEdit().setPlaceholderText('选择或输入上游字段…')
        self.path = QLineEdit()
        self.path.setObjectName('referencePath')
        self.path.setPlaceholderText('变量名 / 字段路径，例如 point.x 或 rows.0.value')
        self.error = QLabel()
        self.error.setWordWrap(True)
        self.error.setObjectName('validationError')
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        row = QHBoxLayout()
        row.addWidget(self.scope)
        row.addWidget(self.node)
        layout.addLayout(row)
        layout.addWidget(self.field)
        layout.addWidget(self.path)
        layout.addWidget(self.error)
        ref = value.get('$ref', '') if isinstance(value, dict) else ''
        parts = ref.split('.')
        if parts[0] and self.scope.findData(parts[0]) < 0:
            self.scope.addItem('已有范围：' + parts[0], parts[0])
        self.scope.setCurrentIndex(max(0, self.scope.findData(parts[0])))
        if parts[0] == 'results':
            node_id = parts[1] if len(parts) > 1 else ''
            if node_id and self.node.findData(node_id) < 0:
                self.node.addItem('不可用的上游：' + node_id, node_id)
            self.node.setCurrentIndex(self.node.findData(node_id))
            self.path.setText('.'.join(parts[2:]))
        else:
            self.path.setText('.'.join(parts[1:]))
        self._reload_fields(select_path=self.path.text().strip())
        show_results = self.scope.currentData() == 'results'
        self.node.setVisible(show_results)
        self.field.setVisible(show_results)
        self.scope.currentIndexChanged.connect(self._on_scope_or_node)
        self.node.currentIndexChanged.connect(self._on_scope_or_node)
        self.field.activated.connect(self._on_field_picked)
        self.field.lineEdit().editingFinished.connect(self._on_field_picked)
        self.path.editingFinished.connect(self._commit)

    def _reload_fields(self, select_path=''):
        self.field.blockSignals(True)
        self.field.clear()
        self.field.addItem('（手填路径）', '')
        nid = self.node.currentData()
        for path in self._field_index.get(nid) or []:
            self.field.addItem(path, path)
        if select_path:
            idx = self.field.findData(select_path)
            if idx < 0:
                self.field.addItem(select_path, select_path)
                idx = self.field.findData(select_path)
            self.field.setCurrentIndex(max(0, idx))
        self.field.blockSignals(False)

    def _on_scope_or_node(self, *_):
        show_results = self.scope.currentData() == 'results'
        self.node.setVisible(show_results)
        self.field.setVisible(show_results)
        if show_results:
            self._reload_fields(select_path=self.path.text().strip())
        self._commit()

    def _on_field_picked(self, *_):
        data = self.field.currentData()
        text = (self.field.currentText() or '').strip()
        path = data if data else text
        if path and path != '（手填路径）':
            self.path.setText(path)
        self._commit()

    def reference(self):
        scope, path = self.scope.currentData(), self.path.text().strip()
        if not _valid_path(path):
            return None
        if scope == 'results':
            if not self.node.currentData():
                return None
            return {'$ref': '.'.join([scope, self.node.currentData(), path])}
        if scope not in dict(SCOPES):
            return None
        return {'$ref': scope + '.' + path}

    def _commit(self, *_):
        show_results = self.scope.currentData() == 'results'
        self.node.setVisible(show_results)
        self.field.setVisible(show_results)
        value = self.reference()
        self.error.setText('' if value else '请选择可用范围、上游模块并填写有效字段路径。')
        if value is not None:
            self.changed.emit(value)


class ValueEditor(QWidget):
    """Typed constant or reference — Halcon/VM style: value first, bind on the side."""
    changed = Signal(object)

    def __init__(self, schema, value, nodes=(), parent=None, field_index=None):
        super().__init__(parent)
        self.schema, self._value = deepcopy(schema), deepcopy(value)
        self._field_index = field_index or {}
        is_ref = isinstance(value, dict) and set(value) == {'$ref'}
        self._literal = _default(schema) if is_ref else deepcopy(value)
        self.mode = QComboBox()
        self.mode.setObjectName('valueMode')
        self.mode.addItem('固定值', 'literal')
        self.mode.addItem('绑定上游', 'reference')
        self.mode.setMaximumWidth(96)
        self.binding_hint = QLabel('绑定：scope.path 或 results.模块.字段（可从上游字段下拉挑选）')
        self.binding_hint.setObjectName('bindingHint')
        self.binding_hint.setStyleSheet('color:#6a7a8a;font-size:10px;')
        self.binding_hint.setVisible(False)
        self.mode.setToolTip('固定值 = 直接填写；绑定上游 = 订阅变量 / 上游模块结果（VisionMaster ⛓ 同款）。切换后在右侧选范围与字段路径。')
        self.stack = QStackedWidget()
        self.literal = self._make_literal(self._literal, nodes)
        self.reference = ReferenceEditor(value if is_ref else {}, nodes, field_index=self._field_index)
        self.stack.addWidget(self.literal)
        self.stack.addWidget(self.reference)
        self.mode.setCurrentIndex(int(is_ref))
        self.stack.setCurrentIndex(int(is_ref))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        # Compact row: editor fills width, mode sits beside (not stacked above).
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        mark = QLabel(_type_badge(schema))
        mark.setObjectName('typeMark')
        mark.setFixedWidth(28)
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # Styling via theme QLabel#typeMark
        mark.setToolTip('类型：' + str(schema.get('type', 'string')))
        row.addWidget(mark)
        row.addWidget(self.stack, 1)
        row.addWidget(self.mode)
        layout.addLayout(row)
        layout.addWidget(self.binding_hint)
        self.binding_hint.setVisible(bool(is_ref))
        self.mode.currentIndexChanged.connect(self._mode_changed)
        self.reference.changed.connect(self._reference_changed)
        if schema.get('description'):
            self.setToolTip(schema['description'])

    def _make_literal(self, value, nodes):
        schema = self.schema
        kind = schema.get('type', _kind(value))
        if kind == 'any':
            control=QWidget();layout=QVBoxLayout(control);layout.setContentsMargins(0,0,0,0)
            types=QComboBox();layout.addWidget(types);holder=QVBoxLayout();layout.addLayout(holder)
            for key,label in TYPES:types.addItem(label,key)
            types.setCurrentIndex(max(0,types.findData(_kind(value))))
            def rebuild(new_value,emit=False):
                while holder.count():
                    child=holder.takeAt(0).widget()
                    if child:child.deleteLater()
                editor=ValueEditor({'type':types.currentData()},new_value,nodes);editor.mode.hide()
                editor.changed.connect(self._literal_changed);holder.addWidget(editor)
                if emit:self._literal_changed(new_value)
            rebuild(value)
            types.currentIndexChanged.connect(lambda _:rebuild(_default({'type':types.currentData()}),True))
        elif schema.get('choices'):
            control = QComboBox()
            for choice in schema['choices']:
                raw = choice.get('value') if isinstance(choice, dict) else choice
                label = choice.get('label', str(raw)) if isinstance(choice, dict) else str(raw)
                control.addItem(label, raw)
            index = next((i for i in range(control.count()) if control.itemData(i) == value), -1)
            if index < 0:
                control.addItem('已有值：' + str(value), deepcopy(value))
                index = control.count() - 1
            control.setCurrentIndex(index)
            control.currentIndexChanged.connect(lambda _: self._literal_changed(control.currentData()))
        elif kind == 'boolean':
            control = QCheckBox('启用')
            control.setChecked(value is True)
            control.toggled.connect(self._literal_changed)
        elif kind in ('integer', 'number'):
            if kind == 'integer' and all(abs(schema.get(k, 0)) <= 2147483647 for k in ('minimum', 'maximum')) and isinstance(value, (int, float)) and abs(value) <= 2147483647:
                control = QSpinBox()
                control.setRange(schema.get('minimum', -2147483647), schema.get('maximum', 2147483647))
                control.setValue(int(value))
            else:
                control = QDoubleSpinBox()
                control.setDecimals(0 if kind == 'integer' else 8)
                control.setRange(schema.get('minimum', -1e100), schema.get('maximum', 1e100))
                control.setValue(float(value) if isinstance(value, (float, int)) else 0)
                control.setSingleStep(1 if kind == 'integer' else .1)
            control.setKeyboardTracking(False)
            control.valueChanged.connect(lambda v: self._literal_changed(int(v) if kind == 'integer' else v))
        elif kind in ('object', 'array'):
            control = StructureEditor(schema, value, nodes)
            control.changed.connect(self._literal_changed)
        else:
            control = QLineEdit('' if value is None else str(value))
            if schema.get('maximumLength'):
                control.setMaxLength(schema['maximumLength'])
            control.editingFinished.connect(lambda: self._literal_changed(control.text()))
        control.setObjectName('literalValue')
        return control

    def _literal_changed(self, value):
        self._literal = deepcopy(value)
        if self.mode.currentIndex() == 0:
            self._publish(value)

    def _reference_changed(self, value):
        if self.mode.currentIndex() == 1:
            self._publish(value)

    def _mode_changed(self, index):
        self.stack.setCurrentIndex(index)
        if hasattr(self, 'binding_hint'):
            self.binding_hint.setVisible(index == 1)
            if index == 1:
                ref = self.reference.reference() if hasattr(self.reference, 'reference') else None
                path = (ref or {}).get('$ref', '') if isinstance(ref, dict) else ''
                self.binding_hint.setText('订阅路径：' + (path or '选择范围与字段（例 flow.count / results.<模块>.count）'))
        if index == 0:
            self._publish(self._literal)
        else:
            self.reference._commit()

    def _publish(self, value):
        if value != self._value or type(value) is not type(self._value):
            self._value = deepcopy(value)
            self.changed.emit(deepcopy(value))


class StructureEditor(QWidget):
    """Native nested forms with typed add/remove controls for free-form data."""
    changed = Signal(object)

    def __init__(self, schema, value, nodes=(), parent=None):
        super().__init__(parent)
        self.schema, self.nodes = deepcopy(schema), nodes
        self.is_array = schema.get('type') == 'array'
        self._value = deepcopy(value) if isinstance(value, list if self.is_array else dict) else ([] if self.is_array else {})
        self._root = QVBoxLayout(self)
        self._root.setContentsMargins(0, 0, 0, 0)
        self.body = QWidget()
        self.form = QFormLayout(self.body)
        self.form.setContentsMargins(4, 0, 0, 0)
        self.form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self._root.addWidget(self.body)
        tools = QHBoxLayout()
        self.new_key = QLineEdit()
        self.new_key.setObjectName('newFieldName')
        self.new_key.setPlaceholderText('新字段名')
        self.new_type = QComboBox()
        self.new_type.setObjectName('newFieldType')
        for key, label in TYPES:
            self.new_type.addItem(label, key)
        self.add_button = QPushButton('添加一项' if self.is_array else '添加字段')
        self.add_button.setObjectName('addField')
        tools.addWidget(self.new_key)
        tools.addWidget(self.new_type)
        tools.addWidget(self.add_button)
        self._root.addLayout(tools)
        self.error = QLabel()
        self.error.setWordWrap(True)
        self._root.addWidget(self.error)
        declared = bool(_properties(schema))
        self.new_key.setVisible(not self.is_array and not declared)
        self.new_type.setVisible((self.is_array and not self._item_schema()) or (not self.is_array and not declared))
        self.add_button.setVisible(self.is_array or not declared)
        self.add_button.clicked.connect(self._add)
        self._render()

    def _item_schema(self):
        if self.schema.get('columns'):
            return {'type': 'object', 'properties': self.schema['columns']}
        return self.schema.get('items', {})

    def _render(self):
        while self.form.rowCount():
            self.form.removeRow(0)
        declared = {p['key']: p for p in _properties(self.schema)}
        keys = range(len(self._value)) if self.is_array else list(declared) + [k for k in self._value if k not in declared]
        for key in keys:
            schema = self._item_schema() if self.is_array else declared.get(key, {})
            value = self._value[key] if key in self._value or self.is_array else _default(schema)
            schema = dict(schema)
            schema.setdefault('type', _kind(value))
            editor = ValueEditor(schema, value, self.nodes)
            editor.setObjectName('entry:' + str(key))
            editor.changed.connect(lambda value, key=key: self._edit(key, value))
            wrapper = QWidget()
            row = QHBoxLayout(wrapper)
            row.setContentsMargins(0, 0, 0, 0)
            row.addWidget(editor, 1)
            if self.is_array or key not in declared or not schema.get('required'):
                remove = QPushButton('移除')
                remove.setObjectName('remove:' + str(key))
                remove.setEnabled(self.is_array or key in self._value)
                remove.clicked.connect(lambda _, key=key: self._remove(key))
                row.addWidget(remove, 0, Qt.AlignmentFlag.AlignTop)
            label = '第 ' + str(key + 1) + ' 项' if self.is_array else _label(dict(schema, key=key))
            self.form.addRow(label, wrapper)
        limit = self.schema.get('maximumRows', 1000)
        self.add_button.setEnabled(not self.is_array or len(self._value) < limit)

    def _edit(self, key, value):
        self._value[key] = deepcopy(value)
        self.changed.emit(deepcopy(self._value))

    def _add(self):
        if self.is_array:
            if len(self._value) >= self.schema.get('maximumRows', 1000):
                return
            self._value.append(_default(self._item_schema() or {'type': self.new_type.currentData()}))
        else:
            key = self.new_key.text().strip()
            if not _NAME.fullmatch(key) or key in _FORBIDDEN:
                self.error.setText('字段名须以字母或下划线开头，只含字母、数字和下划线。')
                return
            if key in self._value:
                self.error.setText('此字段名已存在。')
                return
            self._value[key] = _default({'type': self.new_type.currentData()})
            self.new_key.clear()
        self.error.clear()
        self._render()
        self.changed.emit(deepcopy(self._value))

    def _remove(self, key):
        if self.is_array and len(self._value) <= self.schema.get('minimumRows', 0):
            self.error.setText('不能少于 ' + str(self.schema['minimumRows']) + ' 项。')
            return
        if self.is_array or key in self._value:
            del self._value[key]
            self.error.clear()
            self._render()
            self.changed.emit(deepcopy(self._value))


def _output_paths(fields, prefix=''):
    paths = []
    for field in fields:
        path = prefix + field['key']
        paths.append((path, field.get('label', field['key'])))
        paths.extend(_output_paths(_properties(field), path + '.'))
    return paths


class OutputBindings(QWidget):
    changed = Signal(object)

    def __init__(self, bindings, outputs, parent=None):
        super().__init__(parent)
        self._bindings = deepcopy(bindings)
        self._paths = _output_paths(outputs)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.table = QTableWidget(0, 4)
        self.table.setObjectName('outputBindings')
        self.table.setHorizontalHeaderLabels(['结果字段', '写入范围', '变量名', ''])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.table)
        self.error = QLabel()
        self.error.setWordWrap(True)
        layout.addWidget(self.error)
        add = QPushButton('添加输出绑定')
        add.setObjectName('addOutputBinding')
        add.clicked.connect(self._add)
        layout.addWidget(add)
        self._render()

    def _render(self):
        self.table.setRowCount(0)
        for index, binding in enumerate(self._bindings):
            self.table.insertRow(index)
            field = QComboBox()
            field.setEditable(True)
            for path, label in self._paths:
                field.addItem(path + ' · ' + label, path)
            existing = binding.get('field', '')
            found = field.findData(existing)
            field.setCurrentIndex(found)
            if found < 0:
                field.setEditText(existing)
            scope = QComboBox()
            for key, label in SCOPES:
                scope.addItem(label, key)
            scope.setCurrentIndex(max(0, scope.findData(binding.get('scope', 'flow'))))
            name = QLineEdit(binding.get('name', ''))
            remove = QPushButton('移除')
            for column, widget in enumerate((field, scope, name, remove)):
                self.table.setCellWidget(index, column, widget)
            field.activated.connect(self._commit)
            field.lineEdit().editingFinished.connect(self._commit)
            scope.currentIndexChanged.connect(self._commit)
            name.editingFinished.connect(self._commit)
            remove.clicked.connect(lambda _, index=index: self._remove(index))

    def _read(self):
        bindings, targets = [], set()
        for index in range(self.table.rowCount()):
            field, scope, name = [self.table.cellWidget(index, c) for c in range(3)]
            selected = field.currentIndex()
            path = field.itemData(selected) if selected >= 0 and field.currentText() == field.itemText(selected) else field.currentText().strip()
            variable = name.text().strip()
            if not _valid_path(path or '') or not _NAME.fullmatch(variable) or variable in _FORBIDDEN:
                self.error.setText('请填写结果字段和有效变量名；完成后保存绑定。')
                return None
            target = (scope.currentData(), variable)
            if target in targets:
                self.error.setText('同一输出不能重复写入相同范围的变量。')
                return None
            targets.add(target)
            bindings.append({**self._bindings[index], 'field': path, 'scope': target[0], 'name': variable})
        return bindings

    def _commit(self, *_):
        bindings = self._read()
        if bindings is not None:
            self.error.clear()
            self._bindings = bindings
            self.changed.emit(deepcopy(bindings))

    def _add(self):
        if self.table.rowCount() and self._read() is None:
            return
        self._bindings.append({'field': self._paths[0][0] if self._paths else '', 'scope': 'flow', 'name': ''})
        self._render()
        self.table.cellWidget(self.table.rowCount() - 1, 2).setFocus()

    def _remove(self, index):
        del self._bindings[index]
        self._render()
        self._commit()


class ParameterPanel(QWidget):
    """Right-side property inspector (VisionMaster / Halcon Operator Window style).

    One scrollable panel with sections: 基本 → 图像输入 → 控制参数 → 结果输出.
    Avoids hunting across three tabs for image source vs scalars vs outputs.
    """
    changed = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('propertyPanel')
        self._step = None
        self._definition = None
        self._context = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 8)
        layout.setSpacing(4)
        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 0)
        head.setSpacing(8)
        self.title = QLabel('算子属性')
        self.title.setObjectName('panelTitle')
        head.addWidget(self.title, 1)
        self.badge = QLabel('')
        self.badge.setObjectName('typeMark')
        self.badge.setVisible(False)
        head.addWidget(self.badge)
        layout.addLayout(head)
        self.signature = QLabel('')
        self.signature.setObjectName('operatorSignature')
        self.signature.setWordWrap(True)
        layout.addWidget(self.signature)
        self.description = QLabel('在流程图中选择模块，于下方分区设置图像输入与控制参数。')
        self.description.setObjectName('panelDescription')
        self.description.setWordWrap(True)
        layout.addWidget(self.description)
        # Keep tabs object for compatibility; hide and host a single scroll inspector.
        self.tabs = QTabWidget()
        self.tabs.setObjectName('parameterTabs')
        self.tabs.tabBar().hide()
        layout.addWidget(self.tabs, 1)
        self.set_step(None, None, {})

    def _page(self, label):
        scroll = QScrollArea()
        scroll.setObjectName('propertyScroll')
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(scroll.frameShape().NoFrame)
        content = QWidget()
        outer = QVBoxLayout(content)
        outer.setContentsMargins(2, 4, 4, 12)
        outer.setSpacing(12)
        scroll.setWidget(content)
        self.tabs.addTab(scroll, label)
        return outer

    def set_step(self, step, definition, project, last_result=None):
        definition = definition or {}
        context = ([{k: s.get(k) for k in ('id', 'name')} for s in project.get('steps', [])], project.get('edges', []), id(last_result))
        if step == self._step and definition == self._definition and context == self._context:
            return
        self._step, self._definition, self._context = deepcopy(step), deepcopy(definition), deepcopy(context)
        self._last_result = last_result
        while self.tabs.count():
            widget = self.tabs.widget(0)
            self.tabs.removeTab(0)
            widget.deleteLater()
        self.tabs.setEnabled(step is not None)
        if step is None:
            self.title.setText('算子属性')
            self.signature.setText('')
            self.description.setText('在流程图中选择模块，于下方分区设置图像输入与控制参数。')
            self.badge.setVisible(False)
            self.badge.setText('')
            return
        op_name = definition.get('name', step.get('name', step.get('operation', '模块')))
        self.title.setText(op_name)
        cat = definition.get('category') or ''
        self.badge.setText((cat[:8] + '…') if len(cat) > 8 else cat)
        self.badge.setVisible(bool(cat))
        n_in = len(definition.get('inputs', []) or [])
        n_param = len(definition.get('parameters', []) or [])
        n_out = len(definition.get('outputs', []) or [])
        # Halcon-like signature strip: iconic | control | results
        self.signature.setText(
            f'图像输入 · 控制参数 {n_param} · 声明输出 {n_out}'
            + (f' · 附加输入 {n_in}' if n_in else '')
        )
        self.description.setText(definition.get('description') or '分区编辑图像来源与控制参数（工业视觉属性面板）。')

        page = self._page('属性')
        # —— 基本 ——
        basic_box, basic = _section('基本', '流程图中显示的名称')
        self.name_edit = QLineEdit(step.get('name', definition.get('name', '')))
        self.name_edit.setObjectName('stepName')
        self.name_edit.setMaxLength(80)
        self.name_edit.editingFinished.connect(lambda: self._set_top('name', self.name_edit.text()))
        basic.addRow('模块名称', self.name_edit)
        page.addWidget(basic_box)

        # —— 图像输入 (iconic) —— VisionMaster「订阅图像源」
        image_box, image_form = _section(
            '图像输入',
            '选择本算子读取的图像 / 点云来源（需先在画布连线）。',
        )
        self.image_from = QComboBox()
        self.image_from.setObjectName('imageFrom')
        self.image_from.addItem('（无图像输入）', None)
        incoming = {e['from'] for e in project.get('edges', []) if e.get('to') == step['id']}
        # B1: VM 订阅格式「序号 模块名.端口」，如 0 图像源1.图像
        index_map = {'source': 0}
        names = {'source': '图像源1'}
        for i, s in enumerate(project.get('steps', []), start=1):
            index_map[s['id']] = i
            names[s['id']] = s.get('name', s['id'])
        def _sub_label(node_id, port='图像'):
            idx = index_map.get(node_id, '?')
            return f"{idx} {names.get(node_id, node_id)}.{port}"
        # Prefer topo / y order for dropdown clarity
        ordered = sorted(incoming, key=lambda n: (index_map.get(n, 999), n))
        for node in ordered:
            self.image_from.addItem(_sub_label(node, '图像'), node)
        current = step.get('imageFrom')
        if current and self.image_from.findData(current) < 0:
            self.image_from.addItem('已断开：' + _sub_label(current), current)
        self.image_from.setCurrentIndex(max(0, self.image_from.findData(current)))
        self.image_from.currentIndexChanged.connect(lambda _: self._set_top('imageFrom', self.image_from.currentData()))
        image_form.addRow('输入源', self.image_from)
        page.addWidget(image_box)

        nodes = _upstream(project, step['id'])
        # Enrich nodes with operation for field fallbacks
        by_id = {s.get('id'): s for s in project.get('steps') or []}
        for n in nodes:
            full = by_id.get(n.get('id')) or {}
            if 'operation' not in n:
                n['operation'] = full.get('operation')
        field_index = result_field_index(getattr(self, '_last_result', None) or last_result, nodes)
        plugin = step.get('operation') == 'plugin'
        params = step.get('params', {})

        # —— 附加输入 (plugin/script typed inputs) ——
        input_defs = definition.get('inputs', []) or []
        if input_defs:
            in_box, in_form = _section('附加输入', '可填固定值，或绑定上游结果')
            values = params.get('inputs', {}) if plugin else params
            for field in input_defs:
                key = field['key']
                editor = ValueEditor(field, values.get(key, _default(field)), nodes, field_index=field_index)
                editor.setObjectName('input:' + key)
                editor.changed.connect(lambda value, key=key, group=('inputs' if plugin else None): self._set_param(group, key, value))
                in_form.addRow(_label(field), editor)
            page.addWidget(in_box)

        # —— 控制参数 (control) ——
        param_defs = definition.get('parameters', []) or []
        param_box, param_form = _section(
            '控制参数',
            '阈值、开关、枚举等；右侧可切换「固定值 / 绑定上游」。',
        )
        if step.get('operation') == 'script':
            note = QLabel('脚本通过 Python 文件导入并在外部编辑；此处仅配置输入与输出。运行前需勾选本次可信脚本执行。')
            note.setWordWrap(True)
            param_form.addRow(note)
        values = params.get('arguments', {}) if plugin else params
        group = 'arguments' if plugin else None
        shown = 0
        for field in param_defs:
            key = field['key']
            if step.get('operation') == 'script' and key == 'code':
                continue
            editor = ValueEditor(field, values.get(key, _default(field)), nodes, field_index=field_index)
            editor.setObjectName('parameter:' + key)
            editor.changed.connect(lambda value, key=key, group=group: self._set_param(group, key, value))
            param_form.addRow(_label(field), editor)
            shown += 1
        if not shown:
            note = QLabel('此模块没有可编辑的声明参数；原有配置保留。')
            note.setWordWrap(True)
            param_form.addRow(note)
        page.addWidget(param_box)

        # —— 结果输出 ——
        out_box, out_form = _section(
            '结果输出',
            '运行后写入结果树；可绑定到流程 / 全局变量。',
        )
        schema = QTreeWidget()
        schema.setObjectName('outputSchema')
        schema.setHeaderLabels(['输出字段', '类型'])
        for path, label in _output_paths(definition.get('outputs', [])):
            kind = path.rsplit('.', 1)[-1] if path else ''
            QTreeWidgetItem(schema, [label, kind or '结果'])
        if not schema.topLevelItemCount():
            QTreeWidgetItem(schema, ['运行后显示实际结果', ''])
        schema.setMinimumHeight(88)
        schema.setMaximumHeight(160)
        schema.header().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        out_form.addRow(schema)
        if plugin or step.get('operation') == 'script':
            bindings = OutputBindings(params.get('outputBindings', []), definition.get('outputs', []))
            bindings.changed.connect(lambda value: self._set_param(None, 'outputBindings', value))
            out_form.addRow(bindings)
        page.addWidget(out_box)
        page.addStretch(1)
        self.tabs.setCurrentIndex(0)

    def _set_top(self, key, value):
        if self._step is not None and self._step.get(key) != value:
            self._step[key] = deepcopy(value)
            self.changed.emit(deepcopy(self._step))

    def _set_param(self, group, key, value):
        if self._step is None:
            return
        params = self._step.setdefault('params', {})
        values = params.setdefault(group, {}) if group else params
        if key not in values or values[key] != value or type(values[key]) is not type(value):
            values[key] = deepcopy(value)
            self.changed.emit(deepcopy(self._step))


class ResultPanel(QWidget):
    """Lazy native tree; media payloads are represented by an image action."""
    image_requested = Signal(str)
    _RAW = int(Qt.ItemDataRole.UserRole)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('resultPanel')
        layout = QVBoxLayout(self)
        self.summary = QLabel('尚未运行')
        layout.addWidget(self.summary)
        self.tree = QTreeWidget()
        self.tree.setObjectName('resultTree')
        self.tree.setHeaderLabels(['模块 / 字段', '值', '类型'])
        self.tree.setAlternatingRowColors(True)
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tree.itemExpanded.connect(self._expand)
        self.tree.itemActivated.connect(self._activate)
        layout.addWidget(self.tree, 1)

    def set_results(self, results):
        self.tree.clear()
        self.summary.setText('共 ' + str(len(results)) + ' 个模块结果' if results else '尚无模块结果')
        for index, result in enumerate(results):
            if isinstance(result, dict):
                label = str(result.get('name', result.get('id', '模块 ' + str(index + 1))))
                item = self._item(self.tree, label, result)
                if result.get('skipped'):
                    item.setText(1, '已跳过 · ' + str(result.get('reason', '')))
                elif result.get('error'):
                    item.setText(1, '失败 · ' + str(result['error']))
                else:
                    elapsed = result.get('output', {}).get('elapsedMs') if isinstance(result.get('output'), dict) else None
                    item.setText(1, ('完成 · ' + str(elapsed) + ' ms') if elapsed is not None else '结果')
                item.setExpanded(True)
            else:
                self._item(self.tree, '结果 ' + str(index + 1), result)

    def _item(self, parent, label, value):
        item = QTreeWidgetItem(parent, [str(label), '', ''])
        if isinstance(value, (dict, list)):
            item.setText(1, str(len(value)) + (' 个字段' if isinstance(value, dict) else ' 项'))
            item.setText(2, '结构体' if isinstance(value, dict) else '数组')
            if value:
                item.setData(0, self._RAW, value)
                QTreeWidgetItem(item, ['展开查看', '', ''])
        elif isinstance(value, str) and (value.startswith('data:image/') or (str(label) in ('annotatedImage', 'image') and len(value) > 512)):
            item.setText(1, '双击查看图像')
            item.setText(2, '图像')
            item.setData(1, self._RAW, value)
        else:
            item.setText(1, '空值' if value is None else ('是' if value else '否') if isinstance(value, bool) else str(value))
            item.setText(2, dict(TYPES).get(_kind(value), '空值') if value is not None else '空值')
        return item

    def _expand(self, item):
        value = item.data(0, self._RAW)
        if value is None:
            return
        item.setData(0, self._RAW, None)
        item.takeChildren()
        iterable = value.items() if isinstance(value, dict) else enumerate(value)
        for key, child in iterable:
            self._item(item, key, child)

    def _activate(self, item, _column):
        image = item.data(1, self._RAW)
        if image:
            self.image_requested.emit(image)
