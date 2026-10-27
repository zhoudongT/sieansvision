"""Native three-scope variable tables, with typed nested values and no JSON editor."""
from copy import deepcopy
import math
import re

from PySide6.QtCore import Qt, QTimer, QSettings
from PySide6.QtGui import QGuiApplication, QColor, QBrush
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QDialog, QDialogButtonBox,
    QFormLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QTreeWidget, QTreeWidgetItem, QVBoxLayout,
    QCheckBox)

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
    def __init__(self, name='', value=None, fixed='', editable_type=True, parent=None, note='', persist=True, show_persist=False):
        super().__init__(parent); self.setWindowTitle('变量定义 / 当前值'); self.resize(460, 300)
        self.value = deepcopy(value)
        layout = QFormLayout(self)
        self.name = QLineEdit(name); layout.addRow('变量名称', self.name)
        self.fixed = QComboBox(); self.fixed.addItem('动态（不限制）', '')
        for kind, label in TYPE_LABELS.items(): self.fixed.addItem(label, kind)
        self.fixed.setCurrentIndex(max(0, self.fixed.findData(fixed))); self.fixed.setEnabled(editable_type)
        layout.addRow('固定类型', self.fixed)
        self.value_button = QPushButton(value_summary(value)); self.value_button.clicked.connect(self.edit_value)
        layout.addRow('变量值', self.value_button)
        self.note = QLineEdit(note); self.note.setPlaceholderText('备注（可选）'); layout.addRow('备注', self.note)
        self.persist = QCheckBox('跨运行持久化'); self.persist.setChecked(bool(persist)); self.persist.setVisible(show_persist)
        if show_persist: layout.addRow('持久', self.persist)
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
        self.scope = QComboBox(); self.search = QLineEdit(); self.search.setPlaceholderText('搜索名称 / 备注')
        self.global_only = QCheckBox('仅全局')
        self.global_only.setToolTip('快速过滤全局变量表（VM 全局变量窗习惯）')
        self.fold_comm = QCheckBox('折叠 commAccept*')
        self.fold_comm.setObjectName('varsFoldCommCluster')
        self.fold_comm.setToolTip(
            '折叠分组：隐藏 commAccept_<项> 明细，保留 Pass/Fail/Skip/Overall/At/Host/Port 摘要'
        )
        self.fold_comm.setChecked(self._load_fold_comm_pref())
        self.count_label = QLabel('0 项')
        row.addWidget(self.mode); row.addWidget(self.scope); row.addWidget(self.global_only)
        row.addWidget(self.fold_comm); row.addWidget(self.search, 1); row.addWidget(self.count_label)
        refresh = QPushButton('重新读取（撤销当前值编辑）'); refresh.clicked.connect(self.refresh); row.addWidget(refresh)
        self.hint = QLabel(); self.hint.setWordWrap(True); layout.addWidget(self.hint)
        self.table = QTableWidget(0, 8); self.table.setObjectName('variableTable')
        self.table.setHorizontalHeaderLabels(['作用域', '名称', '固定类型', '工程初始值', '运行当前值', '备注', '持久', '校验'])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.cellDoubleClicked.connect(lambda *_: self.edit_variable())
        layout.addWidget(self.table, 1)
        bar = QHBoxLayout(); layout.addLayout(bar)
        self.add_button = QPushButton('新增变量'); self.edit_button = QPushButton('编辑所选'); self.remove_button = QPushButton('删除所选')
        self.dup_button = QPushButton('复制变量'); self.copy_name_button = QPushButton('复制名称')
        for button, callback in [(self.add_button, self.add_variable), (self.edit_button, self.edit_variable),
                                 (self.dup_button, self.duplicate_variable), (self.copy_name_button, self.copy_selected_name),
                                 (self.remove_button, self.remove_variable)]:
            button.clicked.connect(callback); bar.addWidget(button)
        bar.addStretch(); self.apply_button = QPushButton('应用'); self.apply_button.clicked.connect(self.apply); bar.addWidget(self.apply_button)
        close = QPushButton('关闭'); close.clicked.connect(self.reject); bar.addWidget(close)
        self.message = QLabel(); self.message.setWordWrap(True); layout.addWidget(self.message)
        self._load_definitions()
        self.mode.currentIndexChanged.connect(self.render); self.scope.currentIndexChanged.connect(self.render); self.search.textChanged.connect(self.render); self.global_only.toggled.connect(self.render)
        self.fold_comm.toggled.connect(self._on_fold_comm_toggled)
        self.document.changed.connect(self._document_changed)
        self.backend.result.connect(self._result); self.backend.error.connect(self._error)
        self.finished.connect(self._disconnect)
        self.render(); QTimer.singleShot(0, self.refresh)

    @staticmethod
    def _settings():
        return QSettings('SIEANS', 'VisionDesktop')

    def _load_fold_comm_pref(self) -> bool:
        """wave22: Comm 折叠态持久（跨会话）."""
        try:
            v = self._settings().value('vars/foldCommAccept', False)
            if isinstance(v, str):
                return v.lower() in ('1', 'true', 'yes')
            return bool(v)
        except Exception:
            return False

    def _save_fold_comm_pref(self, on: bool):
        try:
            self._settings().setValue('vars/foldCommAccept', bool(on))
        except Exception:
            pass

    def _on_fold_comm_toggled(self, on: bool):
        self._save_fold_comm_pref(bool(on))
        self.render()

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
        self.notes = deepcopy(p.get('variableNotes', {}))  # scope -> {name: note}
        if 'global' not in self.notes: self.notes['global'] = {}
        if 'flow' not in self.notes: self.notes['flow'] = {}
        self.persist = deepcopy(p.get('variablePersist', {}))  # global name -> bool
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

    def live_patch_flow_var(self, name, value):
        """Live-update a flow variable (e.g. heartbeatTick) without full engine re-read."""
        name = str(name or '').strip()
        if not name:
            return
        try:
            variables = self.document.project.setdefault('variables', {})
            if isinstance(variables, dict):
                variables[name] = value
        except Exception:
            pass
        self.initial.setdefault('flow', {})[name] = value
        if self.runtime_draft is None:
            self.runtime_draft = {'flow': {}, 'global': {}, 'modules': {}, 'revision': 0}
        flow = self.runtime_draft.setdefault('flow', {})
        if not isinstance(flow, dict):
            self.runtime_draft['flow'] = {}
            flow = self.runtime_draft['flow']
        flow[name] = value
        try:
            summary = value_summary(value)
        except Exception:
            summary = str(value)
        matched = False
        try:
            for r in range(self.table.rowCount()):
                name_item = self.table.item(r, 1)
                if name_item is None or name_item.text() != name:
                    continue
                scope_item = self.table.item(r, 0)
                scope_txt = scope_item.text() if scope_item else ''
                if scope_txt and ('流程' not in scope_txt) and scope_txt not in ('flow',):
                    continue
                cur = self.table.item(r, 4)
                if cur is None:
                    self.table.setItem(r, 4, QTableWidgetItem(summary))
                else:
                    cur.setText(summary)
                matched = True
                try:
                    self.highlight_written_keys([f'flow.{name}'], duration_ms=1600)
                except Exception:
                    pass
                break
            if not matched and self.mode.currentData() in ('current', 'overview'):
                self.render()
                try:
                    self.highlight_written_keys([f'flow.{name}'], duration_ms=1600)
                except Exception:
                    pass
            elif matched:
                self.message.setText(f'实时 · flow.{name} = {summary}')
        except Exception:
            try:
                self.render()
            except Exception:
                pass


    def highlight_written_keys(self, keys, *, duration_ms=2200):
        """细妆⑲：Comm dump / 实时写回 → Variables 面板行即时高亮.

        keys: iterable of 'flow.name' / 'global.name' / bare name (assumed flow).
        """
        if not keys:
            return
        wanted = set()
        for k in keys:
            s = str(k or '').strip()
            if not s:
                continue
            if '.' in s:
                scope, name = s.split('.', 1)
            else:
                scope, name = 'flow', s
            wanted.add((scope, name))
            wanted.add(('', name))  # bare match by name
        if not wanted:
            return
        # prefer current/overview so runtime column is visible
        try:
            mode = self.mode.currentData()
            if mode not in ('current', 'overview'):
                for i in range(self.mode.count()):
                    if self.mode.itemData(i) in ('current', 'overview'):
                        self.mode.setCurrentIndex(i)
                        break
        except Exception:
            pass
        hi = QColor('#2a4a2a')
        hi_fg = QColor('#b8f0c4')
        cluster_hi = QColor('#1e3a4a')
        cluster_fg = QColor('#9ed9f0')
        matched_rows = []
        matched_names = []
        try:
            for r in range(self.table.rowCount()):
                name_item = self.table.item(r, 1)
                scope_item = self.table.item(r, 0)
                if name_item is None:
                    continue
                name = name_item.text()
                scope_txt = scope_item.text() if scope_item else ''
                scope_key = 'flow'
                if '全局' in scope_txt or scope_txt == 'global':
                    scope_key = 'global'
                elif '模块' in scope_txt:
                    scope_key = 'module'
                hit = (scope_key, name) in wanted or ('', name) in wanted or ('flow', name) in wanted
                if not hit:
                    # also accept bare flow.xxx in wanted by name alone when scope is 流程
                    if ('流程' in scope_txt or scope_txt in ('flow', '')) and any(n == name for _, n in wanted):
                        hit = True
                if not hit:
                    continue
                matched_rows.append(r)
                matched_names.append(name)
                is_cluster = str(name).startswith('commAccept')
                bg, fg = (cluster_hi, cluster_fg) if is_cluster else (hi, hi_fg)
                for c in range(self.table.columnCount()):
                    it = self.table.item(r, c)
                    if it is None:
                        it = QTableWidgetItem('')
                        self.table.setItem(r, c, it)
                    it.setBackground(QBrush(bg))
                    it.setForeground(QBrush(fg))
        except Exception:
            return
        if matched_rows:
            # 细妆⑳：优先滚到 commAccept* 簇（首条 cluster 行）；否则滚到首条命中
            cluster_rows = [
                r for r, n in zip(matched_rows, matched_names)
                if str(n).startswith('commAccept')
            ]
            focus_row = cluster_rows[0] if cluster_rows else matched_rows[0]
            try:
                self.table.selectRow(focus_row)
                focus_item = self.table.item(focus_row, 1)
                if focus_item is not None:
                    from PySide6.QtWidgets import QAbstractItemView
                    self.table.scrollToItem(
                        focus_item, QAbstractItemView.ScrollHint.PositionAtCenter
                    )
            except Exception:
                try:
                    self.table.scrollToItem(self.table.item(focus_row, 1))
                except Exception:
                    pass
            # also soft-select whole cluster range if contiguous-ish
            try:
                if cluster_rows:
                    from PySide6.QtWidgets import QTableWidgetSelectionRange
                    self.table.setRangeSelected(
                        QTableWidgetSelectionRange(
                            min(cluster_rows), 0, max(cluster_rows),
                            max(0, self.table.columnCount() - 1)
                        ),
                        True,
                    )
            except Exception:
                pass
            n_cluster = len(cluster_rows)
            tip = f'即时高亮 · 写入 {len(matched_rows)} 行'
            if n_cluster:
                tip += f' · 已滚到 commAccept* 簇（{n_cluster}）'
            tip += f'（{duration_ms}ms）'
            self.message.setText(tip)
            # clear highlight after duration
            def _clear(rows=list(matched_rows)):
                try:
                    for r in rows:
                        for c in range(self.table.columnCount()):
                            it = self.table.item(r, c)
                            if it is None:
                                continue
                            it.setBackground(QBrush())
                            it.setForeground(QBrush())
                except Exception:
                    pass
            QTimer.singleShot(max(400, int(duration_ms)), _clear)

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

    def _count_comm_detail_keys(self) -> int:
        """wave23: count commAccept_<id> detail keys across scopes."""
        names = set()
        try:
            for scope, bucket in (self.initial or {}).items():
                if isinstance(bucket, dict):
                    names.update(str(k) for k in bucket)
        except Exception:
            pass
        try:
            draft = self.runtime_draft or {}
            for scope in ('flow', 'global', 'modules'):
                bucket = self._scope_values(draft, scope) if hasattr(self, '_scope_values') else {}
                if isinstance(bucket, dict):
                    names.update(str(k) for k in bucket)
            gtypes = draft.get('globalTypes') or {}
            if isinstance(gtypes, dict):
                names.update(str(k) for k in gtypes)
        except Exception:
            pass
        try:
            types = self.types or {}
            for bucket in types.values():
                if isinstance(bucket, dict):
                    names.update(str(k) for k in bucket)
        except Exception:
            pass
        try:
            proj_vars = (self.document.project.get('variables') or {}) if self.document else {}
            for bucket in proj_vars.values():
                if isinstance(bucket, dict):
                    names.update(str(k) for k in bucket)
        except Exception:
            pass
        return sum(1 for n in names if str(n).startswith('commAccept_'))

    def render(self, *_):
        mode = self.mode.currentData(); initial = mode == 'initial'; overview = mode == 'overview'
        self.hint.setText('初始定义随工程保存；全局变量在“运行当前值”管理。支持备注 / 复制变量 / 仅全局过滤。' if initial else '值为最近读取的快照。全局表支持备注与持久化开关；可用「仅全局」快速过滤。')
        editable = not overview and not self.busy and not self.stale and (initial or self.runtime_draft is not None)
        self.add_button.setEnabled(editable); self.edit_button.setEnabled(not self.stale and (overview or editable)); self.remove_button.setEnabled(editable)
        self.apply_button.setEnabled(editable and not self.pending); self.apply_button.setText('应用初始定义到工程' if initial else '写入当前值')
        self.apply_button.setVisible(not overview)
        self.table.setRowCount(0)
        # global appears first in current/overview for VM-like table
        ordered = list(self.labels.items())
        if not initial:
            ordered = sorted(ordered, key=lambda kv: (0 if kv[0] == 'global' else 1, kv[1]))
        for scope, label in ordered:
            if self.global_only.isChecked() and scope != 'global': continue
            if self.scope.currentData() and scope != self.scope.currentData(): continue
            if initial and scope == 'global': continue
            initials = self.initial.get(scope, {}); current = self._scope_values(self.runtime_draft, scope)
            types = (self.runtime_draft or {}).get('globalTypes', {}) if scope == 'global' else self.types.get(scope, {})
            self.notes.setdefault(scope, {})
            names = list(dict.fromkeys([*initials, *current, *types, *(self.notes.get(scope) or {}).keys()]))
            q = self.search.text().lower()
            fold = bool(getattr(self, 'fold_comm', None) and self.fold_comm.isChecked())
            # wave21: summary keys kept; detail commAccept_<id> folded
            _COMM_SUMMARY = {
                'commAcceptPass', 'commAcceptFail', 'commAcceptSkip',
                'commAcceptOverall', 'commAcceptAt', 'commAcceptHost', 'commAcceptPort',
            }
            def _is_comm_detail(n):
                return str(n).startswith('commAccept_')
            hidden_n = 0
            if fold:
                hidden_n = sum(1 for n in names if _is_comm_detail(n))
                if hidden_n:
                    # group header row
                    grow = self.table.rowCount(); self.table.insertRow(grow)
                    gtexts = [
                        label,
                        f'▼ commAccept* 簇（已折叠 {hidden_n} 项明细）',
                        '—', '—',
                        f'摘要保留 Pass/Fail/… · 明细隐藏 {hidden_n}',
                        '折叠分组', '—', '—',
                    ]
                    for column, text in enumerate(gtexts):
                        item = QTableWidgetItem(text)
                        if column == 1:
                            item.setForeground(QBrush(QColor('#9ed9f0')))
                        self.table.setItem(grow, column, item)
                    self.table.item(grow, 0).setData(Qt.ItemDataRole.UserRole, (scope, '__commAccept_fold__'))
            for name in names:
                if fold and _is_comm_detail(name):
                    continue
                note = str((self.notes.get(scope) or {}).get(name) or '')
                if q and q not in name.lower() and q not in note.lower(): continue
                value = initials.get(name, MISSING) if initial else current.get(name, MISSING)
                fixed = types.get(name, ''); state = '动态类型' if not fixed else '符合类型' if value is not MISSING and type_matches(value, fixed) else '缺少值 / 类型不符'
                row = self.table.rowCount(); self.table.insertRow(row)
                initial_text = value_summary(initials[name]) if name in initials else '全局持久值' if scope == 'global' else '未定义'
                persist = '是' if scope == 'global' and self.persist.get(name, True) else ('—' if scope != 'global' else '否')
                for column, text in enumerate([label, name, TYPE_LABELS.get(fixed, '动态'), initial_text, value_summary(current.get(name, MISSING)), note, persist, state]):
                    item = QTableWidgetItem(text); self.table.setItem(row, column, item)
                self.table.item(row, 0).setData(Qt.ItemDataRole.UserRole, (scope, name))
                if str(name).startswith('commAccept'):
                    try:
                        for c in range(self.table.columnCount()):
                            it = self.table.item(row, c)
                            if it is not None:
                                it.setBackground(QBrush(QColor('#1a2a33')))
                    except Exception:
                        pass
        self.count_label.setText(f'{self.table.rowCount()} 项')
        # wave23: Comm 折叠按簇计数徽章（扫 initial / runtime / project.variables）
        try:
            fc = getattr(self, 'fold_comm', None)
            if fc is not None:
                detail_n = self._count_comm_detail_keys()
                if fc.isChecked():
                    fc.setText(f'折叠 commAccept* · 已藏 {detail_n}')
                else:
                    fc.setText(
                        f'折叠 commAccept* · 簇 {detail_n}' if detail_n else '折叠 commAccept*'
                    )
                fc.setToolTip(
                    '折叠分组：隐藏 commAccept_<项> 明细，保留 Pass/Fail/Skip/Overall/At/Host/Port 摘要'
                    + (f'（当前簇 {detail_n} 项明细）' if detail_n else '')
                )
        except Exception:
            pass
        editable = not overview and not self.busy and not self.stale and (initial or self.runtime_draft is not None)
        self.dup_button.setEnabled(editable); self.copy_name_button.setEnabled(self.table.rowCount() > 0)

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
        note = (self.notes.get(scope) or {}).get(old or '', '')
        dialog = VariableRowDialog(old or '', values.get(old, 0), types.get(old, ''), can_type, self,
                                   note=note, persist=self.persist.get(old or '', True), show_persist=(scope == 'global'))
        if old and not can_type and old in types: dialog.name.setReadOnly(True)
        if dialog.exec() != QDialog.DialogCode.Accepted: return
        name, kind = dialog.name.text(), dialog.fixed.currentData()
        if name != old and name in values: self.message.setText('同一作用域变量名称不能重复。'); return
        if old and old != name:
            values.pop(old, None); types.pop(old, None)
            (self.notes.get(scope) or {}).pop(old, None)
            self.persist.pop(old, None)
        values[name] = deepcopy(dialog.value)
        self.notes.setdefault(scope, {})[name] = dialog.note.text().strip()
        if scope == 'global':
            self.persist[name] = bool(dialog.persist.isChecked())
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

    def duplicate_variable(self):
        if self.busy or self.stale or self.mode.currentData() == 'overview': return
        selected = self._selected()
        if not selected: return
        scope, name = selected
        values, types = self._values_types(scope)
        if name not in values and name not in types:
            self.message.setText('所选行无可复制的值。'); return
        base = name + '_copy'; cand = base; i = 2
        while cand in values or cand in types:
            cand = f'{base}{i}'; i += 1
        values[cand] = deepcopy(values.get(name, default_value(types.get(name) or 'number')))
        if name in types: types[cand] = types[name]
        notes = self.notes.setdefault(scope, {})
        if name in notes: notes[cand] = notes[name]
        if scope == 'global' and name in self.persist:
            self.persist[cand] = self.persist[name]
        self.message.setText(f'已复制为 {cand}'); self.render()

    def copy_selected_name(self):
        selected = self._selected()
        if not selected: return
        _, name = selected
        QGuiApplication.clipboard().setText(name)
        self.message.setText(f'已复制名称：{name}')

    def apply(self):
        if self.busy or self.stale or self.pending: return
        try:
            if self.mode.currentData() == 'initial':
                project = deepcopy(self.document.project)
                for scope in self.initial: validate_values(self.initial[scope], self.types[scope])
                for scope, target in [('flow', project), *[('module:' + s['id'], s) for s in project['steps']]]:
                    if self.initial[scope] != self.original_initial[scope]: target['variables'] = deepcopy(self.initial[scope])
                    if self.types[scope] != self.original_types[scope]: target['variableTypes'] = deepcopy(self.types[scope])
                project['variableNotes'] = deepcopy(self.notes)
                project['variablePersist'] = deepcopy(self.persist)
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
