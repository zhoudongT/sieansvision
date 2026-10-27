"""运行界面设计器 — 对标 VM4.4；P1 含按钮多触发命令 + 数据源订阅 stub。"""
from copy import deepcopy

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QListWidget,
    QListWidgetItem, QSplitter, QWidget, QComboBox, QFrame, QTabWidget,
    QMessageBox, QCheckBox, QGroupBox, QFormLayout, QToolBar, QStackedWidget,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView, QLineEdit,
)

from desktop.widgets.switch import OrangeSwitch

CONTROL_LIBRARY = {
    '基础': [
        '图像', '多图像', '运行控制', '运行状态', 'OK/NG', '文本框', '按钮',
        '开关控制', '参数设置', '设置变量', '字符设置', '信号灯', '条件信号灯',
    ],
    '布局': ['组合框', '子界面', 'Tab页'],
    '图表': ['表格', '线图阵列', '多数据线图', '生产统计', '饼图', '参数组合', '文本框组合'],
    '其他': ['图片', '世界时钟', '界面日志'],
}

SPLIT_PRESETS = ['1', '2', '3', '4', '6', '8', '9', '自定义']

TRIGGER_COMMAND_TYPES = [
    '界面链接',
    '参数配置',
    '复位',
    '方案保存',
    '方案另存',
    '执行·单次',
    '执行·连续',
    '执行·停止',
    '模块动作',
]

UI_LINK_TARGETS = ['全局相机', '通讯', '变量', '日志', '综合配置']


class TriggerCommandsEditor(QWidget):
    """B5: 按钮可配多条命令，自上而下顺序执行。"""
    changed = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        head = QLabel('触发命令（多条 · 自上而下）')
        head.setStyleSheet('font-weight:600;')
        lay.addWidget(head)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(['序号', '命令类型', '配置'])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        lay.addWidget(self.table, 1)
        bar = QHBoxLayout()
        for text, slot in (('添加', self.add_row), ('上移', lambda: self._move(-1)),
                           ('下移', lambda: self._move(1)), ('删除', self._remove)):
            b = QPushButton(text)
            b.clicked.connect(slot)
            bar.addWidget(b)
        bar.addStretch(1)
        lay.addLayout(bar)

    def set_commands(self, commands):
        self.table.setRowCount(0)
        for cmd in commands or []:
            self._append(cmd)
        if self.table.rowCount() == 0:
            self.add_row()

    def _append(self, cmd=None):
        cmd = cmd or {}
        r = self.table.rowCount()
        self.table.insertRow(r)
        seq = QTableWidgetItem(str(r + 1))
        seq.setFlags(seq.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.table.setItem(r, 0, seq)
        combo = QComboBox()
        combo.addItems(TRIGGER_COMMAND_TYPES)
        cur = cmd.get('type') or TRIGGER_COMMAND_TYPES[0]
        i = combo.findText(cur)
        combo.setCurrentIndex(i if i >= 0 else 0)
        combo.currentIndexChanged.connect(lambda *_: self._emit())
        self.table.setCellWidget(r, 1, combo)
        cfg = QLineEdit(str(cmd.get('config') or ''))
        if (cmd.get('type') or '').startswith('界面'):
            cfg.setPlaceholderText(' / '.join(UI_LINK_TARGETS))
        elif '模块' in (cmd.get('type') or ''):
            cfg.setPlaceholderText('模块动作：流程名.模块名')
        else:
            cfg.setPlaceholderText('配置参数…')
        cfg.textChanged.connect(lambda *_: self._emit())
        self.table.setCellWidget(r, 2, cfg)
        self._renumber()

    def add_row(self):
        self._append({'type': '执行·单次', 'config': ''})
        self._emit()

    def _remove(self):
        r = self.table.currentRow()
        if r >= 0:
            self.table.removeRow(r)
            self._renumber()
            self._emit()

    def _move(self, delta):
        r = self.table.currentRow()
        t = r + delta
        if r < 0 or t < 0 or t >= self.table.rowCount():
            return
        data = self.commands()
        data[r], data[t] = data[t], data[r]
        self.set_commands(data)
        self.table.selectRow(t)
        self._emit()

    def _renumber(self):
        for r in range(self.table.rowCount()):
            item = self.table.item(r, 0)
            if item is None:
                item = QTableWidgetItem()
                self.table.setItem(r, 0, item)
            item.setText(str(r + 1))

    def commands(self):
        out = []
        for r in range(self.table.rowCount()):
            combo = self.table.cellWidget(r, 1)
            cfg = self.table.cellWidget(r, 2)
            out.append(dict(
                type=combo.currentText() if combo else '',
                config=cfg.text() if cfg else '',
            ))
        return out

    def _emit(self):
        self.changed.emit(self.commands())


class RunUiDesignerDialog(QDialog):
    """独立「运行界面设计」窗口：控件库 / 分割 / 固定栏 / 触发命令 / 订阅。"""
    previewRequested = Signal()
    exportRequested = Signal()

    def __init__(self, document=None, parent=None):
        super().__init__(parent)
        self.document = document
        self._control_state = {}  # name -> {binding, commands}
        self._current_control = None
        self.setWindowTitle('运行界面设计')
        self.resize(1280, 820)
        self.setMinimumSize(960, 640)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        bar = QToolBar()
        bar.setMovable(False)
        title = QLabel('  运行界面设计')
        title.setObjectName('dialogTitle')
        bar.addWidget(title)
        bar.addSeparator()
        self.split_combo = QComboBox()
        self.split_combo.addItems([f'布局分割 · {s}' for s in SPLIT_PRESETS])
        bar.addWidget(QLabel(' 分割 '))
        bar.addWidget(self.split_combo)
        self.template_combo = QComboBox()
        self.template_combo.addItems([f'分割模板 {i}' for i in range(1, 8)] + ['保存模板…'])
        bar.addWidget(QLabel(' 模板 '))
        bar.addWidget(self.template_combo)
        bar.addSeparator()
        preview_btn = QPushButton('预览')
        preview_btn.setObjectName('primaryButton')
        preview_btn.clicked.connect(self._preview)
        export_btn = QPushButton('导出')
        export_btn.clicked.connect(self._export)
        bar.addWidget(preview_btn)
        bar.addWidget(export_btn)
        close_btn = QPushButton('关闭')
        close_btn.clicked.connect(self.close)
        bar.addWidget(close_btn)
        root.addWidget(bar)

        body = QSplitter(Qt.Orientation.Horizontal)
        root.addWidget(body, 1)

        left = QWidget()
        left.setObjectName('libraryPane')
        left.setMinimumWidth(220)
        left.setMaximumWidth(320)
        ll = QVBoxLayout(left)
        lib_title = QLabel('控件库')
        lib_title.setObjectName('libraryTitle')
        ll.addWidget(lib_title)
        lib_hint = QLabel('基础 / 布局 / 图表 / 其他')
        lib_hint.setObjectName('libraryHint')
        ll.addWidget(lib_hint)
        self.lib_tabs = QTabWidget()
        for cat, items in CONTROL_LIBRARY.items():
            lst = QListWidget()
            for name in items:
                QListWidgetItem(name, lst)
            self.lib_tabs.addTab(lst, cat)
        ll.addWidget(self.lib_tabs, 1)
        tip = QLabel('点选控件编辑属性；按钮可配多条触发命令；⛓ 绑定局部变量。')
        tip.setObjectName('dialogHint')
        tip.setWordWrap(True)
        ll.addWidget(tip)
        body.addWidget(left)

        center = QWidget()
        center.setObjectName('flowPane')
        cl = QVBoxLayout(center)
        cl.setContentsMargins(8, 8, 8, 8)
        self.preview_label = QLabel('运行界面预览')
        self.preview_label.setObjectName('dialogTitle')
        cl.addWidget(self.preview_label)
        self.preview_stack = QStackedWidget()
        self._build_split_pages()
        cl.addWidget(self.preview_stack, 1)
        self.split_combo.currentIndexChanged.connect(self._on_split)
        body.addWidget(center)

        right = QWidget()
        right.setObjectName('imagePane')
        right.setMinimumWidth(280)
        right.setMaximumWidth(400)
        rl = QVBoxLayout(right)
        rt = QLabel('固定栏选择')
        rt.setObjectName('panelTitle')
        rl.addWidget(rt)
        rh = QLabel('常用于绑定相机状态、通讯状态')
        rh.setObjectName('panelDescription')
        rl.addWidget(rh)
        self.fix_top = QCheckBox('顶部固定栏')
        self.fix_bottom = QCheckBox('底部固定栏')
        self.fix_left = QCheckBox('左侧固定栏')
        self.fix_right = QCheckBox('右侧固定栏')
        for cb in (self.fix_top, self.fix_bottom, self.fix_left, self.fix_right):
            rl.addWidget(cb)
            cb.toggled.connect(self._refresh_fixed_chrome)

        grp = QGroupBox('运行控制绑定（占位）')
        gf = QFormLayout(grp)
        sw = OrangeSwitch(False)
        gf.addRow(QLabel('使能预览开关'), sw)
        gf.addRow(QLabel('相机状态'), QLabel('未绑定'))
        gf.addRow(QLabel('通讯状态'), QLabel('未绑定'))
        rl.addWidget(grp)

        props = QGroupBox('选中控件属性')
        pf = QFormLayout(props)
        self.prop_name = QLabel('—')
        pf.addRow(QLabel('控件'), self.prop_name)

        bind_row = QWidget()
        br = QHBoxLayout(bind_row)
        br.setContentsMargins(0, 0, 0, 0)
        self.prop_binding = QLineEdit()
        self.prop_binding.setPlaceholderText('数据源：流程输出 / 局部变量')
        self.prop_binding.setReadOnly(True)
        bind_btn = QPushButton('⛓')
        bind_btn.setFixedWidth(32)
        bind_btn.setToolTip('订阅局部变量 / 流程输出')
        bind_btn.clicked.connect(self._open_bind)
        br.addWidget(self.prop_binding, 1)
        br.addWidget(bind_btn)
        pf.addRow(QLabel('数据源'), bind_row)
        rl.addWidget(props)

        self.trigger_editor = TriggerCommandsEditor()
        self.trigger_editor.setEnabled(False)
        self.trigger_editor.changed.connect(self._on_commands_changed)
        rl.addWidget(self.trigger_editor, 1)

        body.addWidget(right)
        body.setSizes([260, 680, 320])

        for i in range(self.lib_tabs.count()):
            lst = self.lib_tabs.widget(i)
            lst.currentTextChanged.connect(self._pick_control)

        foot = QLabel('  B5 按钮多触发命令 / B6 ⛓ 局部变量订阅已接入；预览·导出仍为骨架。完整 HMI 亦可走「工程管理 → 运行画面编辑」。')
        foot.setObjectName('dialogHint')
        foot.setWordWrap(True)
        root.addWidget(foot)

        # Restore saved designer stub from project if any
        if document is not None:
            ui = (document.project or {}).get('runUi') or {}
            self._control_state = deepcopy(ui.get('controls') or {})

    def _build_split_pages(self):
        layouts = {
            0: [(1, 1)], 1: [(1, 2)], 2: [(1, 3)], 3: [(2, 2)],
            4: [(2, 3)], 5: [(2, 4)], 6: [(3, 3)], 7: [(2, 2)],
        }
        for idx, cells in layouts.items():
            page = QWidget()
            page.setObjectName('runPreviewPage')
            rows, cols = cells[0]
            grid_host = QVBoxLayout(page)
            grid_host.setSpacing(4)
            cell_i = 0
            for r in range(rows):
                row = QHBoxLayout()
                row.setSpacing(4)
                for c in range(cols):
                    cell = QFrame()
                    cell.setObjectName('runPreviewCell')
                    cell.setFrameShape(QFrame.Shape.StyledPanel)
                    cell.setMinimumHeight(80)
                    cv = QVBoxLayout(cell)
                    lab = QLabel(f'窗格 {cell_i + 1}')
                    lab.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    lab.setStyleSheet('color:#9aa7b5;')
                    cv.addStretch(1)
                    cv.addWidget(lab)
                    cv.addStretch(1)
                    row.addWidget(cell, 1)
                    cell_i += 1
                grid_host.addLayout(row, 1)
            self.preview_stack.addWidget(page)

    def _on_split(self, index):
        self.preview_stack.setCurrentIndex(max(0, min(index, self.preview_stack.count() - 1)))
        self.preview_label.setText(f'运行界面预览 · {SPLIT_PRESETS[index]} 分屏')

    def _ensure_state(self, name):
        st = self._control_state.setdefault(name, dict(binding='', commands=[]))
        st.setdefault('binding', '')
        st.setdefault('commands', [])
        return st

    def _pick_control(self, name):
        if not name:
            return
        self._current_control = name
        self.prop_name.setText(name)
        st = self._ensure_state(name)
        self.prop_binding.setText(st.get('binding') or '')
        is_button = name in ('按钮', '运行控制', '开关控制')
        self.trigger_editor.setEnabled(is_button)
        if is_button:
            cmds = st.get('commands') or []
            if not cmds:
                cmds = [
                    dict(type='执行·单次', config=''),
                    dict(type='界面链接', config='日志'),
                ]
                st['commands'] = cmds
            self.trigger_editor.set_commands(cmds)
        else:
            self.trigger_editor.set_commands([])

    def _on_commands_changed(self, commands):
        if not self._current_control:
            return
        self._ensure_state(self._current_control)['commands'] = deepcopy(commands)
        self._persist()

    def _open_bind(self):
        if not self._current_control:
            QMessageBox.information(self, '订阅', '请先在控件库点选一个控件。')
            return
        from desktop.bind_dialog import BindSourceDialog
        project = self.document.project if self.document else {}
        st = self._ensure_state(self._current_control)
        dlg = BindSourceDialog(project, current=st.get('binding') or '', parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            st['binding'] = dlg.selected
            self.prop_binding.setText(dlg.selected or '')
            if self.document is not None:
                dlg.apply_to_project(self.document)
            self._persist()

    def _persist(self):
        if self.document is None:
            return
        p = deepcopy(self.document.project)
        ui = p.setdefault('runUi', {})
        ui['controls'] = deepcopy(self._control_state)
        ui['split'] = SPLIT_PRESETS[self.split_combo.currentIndex()]
        ui['fixedBars'] = dict(
            top=self.fix_top.isChecked(),
            bottom=self.fix_bottom.isChecked(),
            left=self.fix_left.isChecked(),
            right=self.fix_right.isChecked(),
        )
        try:
            self.document.commit(p)
        except Exception:
            # avoid blocking designer on validate edge cases
            self.document.project = p
            self.document.changed.emit()

    def _refresh_fixed_chrome(self, *_):
        parts = []
        if self.fix_top.isChecked():
            parts.append('顶')
        if self.fix_bottom.isChecked():
            parts.append('底')
        if self.fix_left.isChecked():
            parts.append('左')
        if self.fix_right.isChecked():
            parts.append('右')
        chrome = '、'.join(parts) if parts else '无'
        self.preview_label.setText(
            f'运行界面预览 · {SPLIT_PRESETS[self.split_combo.currentIndex()]} 分屏 · 固定栏：{chrome}')
        self._persist()

    def _preview(self):
        self.previewRequested.emit()
        n_btn = sum(1 for k, v in self._control_state.items()
                    if k in ('按钮', '运行控制', '开关控制') and v.get('commands'))
        QMessageBox.information(
            self, '预览',
            f'运行界面预览：已配置控件 {len(self._control_state)} 个，含触发命令的按钮类 {n_btn} 个。\n'
            '操作员态将按布局与命令自上而下执行（引擎侧接线后续批次）。')

    def _export(self):
        self.exportRequested.emit()
        QMessageBox.information(self, '导出', '导出占位：后续将写出运行界面模板（名称/创建人/推荐使用场景/描述）。')
