"""局部变量 ↔ 控件订阅 / 绑定对话框（⛓ 入口）。"""
from copy import deepcopy

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QListWidget,
    QListWidgetItem, QLineEdit, QTabWidget, QWidget, QFormLayout, QMessageBox,
)


def collect_local_variables(project, group_step=None):
    """Gather flow-level and optional Group-local variables for bind UI."""
    items = []
    # Flow / scheme locals
    flow_vars = project.get('variables') or {}
    for name, value in flow_vars.items():
        items.append(dict(scope='流程局部', path=f'flow.{name}', name=name, value=value))
    local = project.get('localVariables') or {}
    for name, value in local.items():
        items.append(dict(scope='流程局部', path=f'local.{name}', name=name, value=value))
    # Active flow entry locals if multi-flow
    for flow in project.get('flows') or []:
        if flow.get('id') != project.get('activeFlowId'):
            continue
        for name, value in (flow.get('localVariables') or {}).items():
            items.append(dict(
                scope=f"流程 · {flow.get('name') or '流程'}",
                path=f"flow:{flow['id']}.{name}",
                name=name,
                value=value,
            ))
    if group_step:
        params = group_step.get('params') or {}
        inner = params.get('inner') or {}
        for name, value in (inner.get('localVariables') or {}).items():
            items.append(dict(
                scope=f"Group · {group_step.get('name') or '组合模块'}",
                path=f"group:{group_step['id']}.{name}",
                name=name,
                value=value,
            ))
    # Operator IO labels (VM-style) — always listed for ImageData / ROI binding
    items.insert(0, dict(scope='图像源', path='0 图像源1.图像', name='图像', value=''))
    items.insert(1, dict(scope='图像源', path='0 图像源1.ROI', name='ROI', value=''))
    items.insert(2, dict(scope='图像源', path='0 图像源1.ImageData', name='ImageData', value=''))
    for i, s in enumerate(project.get('steps') or [], start=1):
        if group_step and s.get('id') == group_step.get('id'):
            continue
        label = s.get('name') or s.get('operation') or s.get('id')
        items.append(dict(scope='模块输出', path=f'{i} {label}.图像', name='图像', value=''))
        items.append(dict(scope='模块输出', path=f'{i} {label}.ROI', name='ROI', value=''))
        items.append(dict(scope='模块输出', path=f'{i} {label}.Output', name='Output', value=''))
    # Demo placeholders when empty so UX is discoverable
    if len(items) <= 3:
        items.extend([
            dict(scope='流程局部', path='local.ResultOK', name='ResultOK', value=True),
            dict(scope='流程局部', path='local.Count', name='Count', value=0),
            dict(scope='流程局部', path='local.StatusText', name='StatusText', value=''),
        ])
    return items


class BindSourceDialog(QDialog):
    """运行界面控件数据源可订阅流程输出或局部变量。"""

    def __init__(self, project, current='', group_step=None, parent=None):
        super().__init__(parent)
        self.project = project
        self.group_step = group_step
        self.selected = current or ''
        self.setWindowTitle('订阅数据源')
        self.resize(520, 420)
        root = QVBoxLayout(self)
        title = QLabel('订阅数据源 · 局部变量 / 流程输出')
        title.setObjectName('dialogTitle')
        root.addWidget(title)
        hint = QLabel('流程或 Group 内设局部变量；运行界面控件数据源可订阅该变量（⛓）。')
        hint.setObjectName('dialogHint')
        hint.setWordWrap(True)
        root.addWidget(hint)

        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)

        # Local vars tab
        local_w = QWidget()
        lv = QVBoxLayout(local_w)
        self.var_list = QListWidget()
        for item in collect_local_variables(project, group_step):
            text = f"{item['scope']}  ·  {item['name']}  ←  {item['path']}"
            li = QListWidgetItem(text)
            li.setData(Qt.ItemDataRole.UserRole, item['path'])
            self.var_list.addItem(li)
            if item['path'] == current:
                self.var_list.setCurrentItem(li)
        self.var_list.itemDoubleClicked.connect(self._pick_item)
        lv.addWidget(self.var_list, 1)
        add_row = QHBoxLayout()
        self.new_name = QLineEdit()
        self.new_name.setPlaceholderText('新建局部变量名…')
        add_btn = QPushButton('新建流程局部变量')
        add_btn.clicked.connect(self._add_local)
        add_row.addWidget(self.new_name, 1)
        add_row.addWidget(add_btn)
        lv.addLayout(add_row)
        self.tabs.addTab(local_w, '局部变量')

        # Flow outputs stub
        out_w = QWidget()
        ov = QVBoxLayout(out_w)
        self.out_list = QListWidget()
        outs = ['0 图像源1.图像', '0 图像源1.ImageData']
        for i, s in enumerate(project.get('steps') or [], start=1):
            name = s.get('name') or s.get('operation') or s['id']
            outs.append(f'{i} {name}.图像')
            outs.append(f'{i} {name}.Output')
        for path in outs:
            li = QListWidgetItem(path)
            li.setData(Qt.ItemDataRole.UserRole, path)
            self.out_list.addItem(li)
            if path == current:
                self.out_list.setCurrentItem(li)
        self.out_list.itemDoubleClicked.connect(self._pick_item)
        ov.addWidget(self.out_list)
        self.tabs.addTab(out_w, '流程输出')

        self.current_lab = QLabel(f'当前：{current or "（未绑定）"}')
        root.addWidget(self.current_lab)

        bar = QHBoxLayout()
        clear = QPushButton('清除绑定')
        clear.clicked.connect(self._clear)
        ok = QPushButton('确定')
        ok.setObjectName('primaryButton')
        ok.clicked.connect(self._accept)
        cancel = QPushButton('取消')
        cancel.clicked.connect(self.reject)
        bar.addWidget(clear)
        bar.addStretch(1)
        bar.addWidget(ok)
        bar.addWidget(cancel)
        root.addLayout(bar)

        self._created_locals = {}

    def _pick_item(self, item):
        path = item.data(Qt.ItemDataRole.UserRole)
        self.selected = path or ''
        self.current_lab.setText(f'当前：{self.selected or "（未绑定）"}')

    def _clear(self):
        self.selected = ''
        self.current_lab.setText('当前：（未绑定）')
        self.var_list.clearSelection()
        self.out_list.clearSelection()

    def _add_local(self):
        name = self.new_name.text().strip()
        if not name or not name.isidentifier():
            QMessageBox.warning(self, '局部变量', '请输入合法变量名（字母/数字/下划线）。')
            return
        path = f'local.{name}'
        self._created_locals[name] = 0
        li = QListWidgetItem(f'流程局部  ·  {name}  ←  {path}')
        li.setData(Qt.ItemDataRole.UserRole, path)
        self.var_list.addItem(li)
        self.var_list.setCurrentItem(li)
        self.selected = path
        self.current_lab.setText(f'当前：{path}')
        self.new_name.clear()

    def _accept(self):
        # Prefer current list selection if user didn't double-click
        if self.tabs.currentIndex() == 0 and self.var_list.currentItem():
            self.selected = self.var_list.currentItem().data(Qt.ItemDataRole.UserRole) or self.selected
        elif self.tabs.currentIndex() == 1 and self.out_list.currentItem():
            self.selected = self.out_list.currentItem().data(Qt.ItemDataRole.UserRole) or self.selected
        self.accept()

    def apply_to_project(self, document):
        """Persist any newly created local variables into the project."""
        if not self._created_locals:
            return
        p = deepcopy(document.project)
        locals_map = p.setdefault('localVariables', {})
        for name, value in self._created_locals.items():
            locals_map.setdefault(name, value)
        # Also mirror onto active flow if present
        for flow in p.get('flows') or []:
            if flow.get('id') == p.get('activeFlowId'):
                fl = flow.setdefault('localVariables', {})
                for name, value in self._created_locals.items():
                    fl.setdefault(name, value)
        document.commit(p)
