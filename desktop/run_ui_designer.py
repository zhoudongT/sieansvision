"""运行界面设计器 — 对标 VM4.4；P2 C1–C3：控件库 stub / 固定栏绑定 / 界面模板元数据。"""
from copy import deepcopy
from pathlib import Path
import json
from datetime import datetime

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QListWidget,
    QListWidgetItem, QSplitter, QWidget, QComboBox, QFrame, QTabWidget,
    QMessageBox, QCheckBox, QGroupBox, QFormLayout, QToolBar, QStackedWidget,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView, QLineEdit,
    QTextEdit, QDialogButtonBox, QFileDialog,
)

from desktop.theme import TEXT, TEXT_MUTED
from desktop.widgets.switch import OrangeSwitch

# C1: 四分类控件库（中文原文标签）— 列表项即带标签 stub
CONTROL_LIBRARY = {
    '基础': [
        '图像', '多图像', '运行控制', '运行状态', 'OK/NG', '文本框', '按钮',
        '开关控制', '参数设置', '设置变量', '字符设置', '信号灯', '条件信号灯',
        'IP地址', '端口', '连接状态', '上位机状态机',
    ],
    '布局': ['组合框', '子界面', 'Tab页'],
    '图表': ['表格', '线图阵列', '多数据线图', '生产统计', '饼图', '参数组合', '文本框组合'],
    '其他': ['图片', '世界时钟', '界面日志', '信息提示栏'],
}

CONTROL_STUB_HINTS = {
    '图像': '显示流程图像 / 历史图',
    '多图像': '多路图像窗格',
    '运行控制': '单次·连续·停止',
    '运行状态': '流程运行态指示',
    'OK/NG': '判定结果灯',
    '文本框': '只读/可编文本',
    '按钮': '多触发命令',
    '开关控制': 'Toggle 开关',
    '参数设置': '参数编辑入口',
    '设置变量': '写变量',
    '字符设置': '字符参数',
    '信号灯': '状态灯',
    '条件信号灯': '条件着色灯',
    '组合框': '容器组合',
    '子界面': '嵌套界面',
    'Tab页': '多页签容器',
    '表格': '结果表',
    '线图阵列': '多曲线阵列',
    '多数据线图': '多数据曲线',
    '生产统计': '产量/良率',
    '饼图': '占比图',
    '参数组合': '参数组展示',
    '文本框组合': '多文本组合',
    '图片': '静态图',
    '世界时钟': '时钟控件',
    '界面日志': '运行日志',
    'IP地址': '上位机通讯 IP（p41 示意）',
    '端口': '上位机通讯端口',
    '连接状态': '连接状态指示',
    '信息提示栏': '运行/通讯信息',
    '上位机状态机': '手动/自动 · Idle/Run/Pause/Alarm（p41–43，无机械手 SDK）',
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
    '执行·暂停',
    '执行·继续',
    '模块动作',
    '状态·报警',
    '状态·清除报警',
]

UI_LINK_TARGETS = ['全局相机', '通讯', '变量', '日志', '综合配置']

# C2: 固定栏绑定占位选项
CAMERA_BIND_OPTIONS = [
    '未绑定',
    '相机状态·实况',
    '全局相机.连接状态',
    '全局相机.取流状态',
    '全局相机.触发状态',
]
COMM_BIND_OPTIONS = [
    '未绑定',
    '通讯状态·实况',
    'TCP.连接状态',
    '串口.连接状态',
    'PLC.通讯状态',
    'MQTT.连接状态',
]

MAX_RUN_INTERVAL_MS = 100000


def templates_dir(document=None, root=None):
    """Resolve run-UI templates folder under data or project root."""
    if root is not None:
        base = Path(root)
    elif document is not None and getattr(document, 'project', None):
        # Prefer sibling of common data layout; caller may override
        base = Path('.')
    else:
        base = Path('.')
    d = base / 'projects' / 'run-ui-templates'
    d.mkdir(parents=True, exist_ok=True)
    return d


class SaveUiTemplateDialog(QDialog):
    """C3: 保存模板字段 — 名称 / 创建人 / 推荐使用场景 / 描述。"""

    def __init__(self, meta=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle('保存模板')
        self.resize(420, 320)
        meta = meta or {}
        lay = QVBoxLayout(self)
        form = QFormLayout()
        self.name_edit = QLineEdit(meta.get('name') or '运行界面模板')
        self.author_edit = QLineEdit(meta.get('author') or '')
        self.scenario_edit = QLineEdit(meta.get('scenario') or '')
        self.scenario_edit.setPlaceholderText('例：产线操作员 / 调试 / 复检')
        self.desc_edit = QTextEdit()
        self.desc_edit.setPlainText(meta.get('description') or '')
        self.desc_edit.setPlaceholderText('模板描述…')
        self.desc_edit.setMaximumHeight(100)
        form.addRow('名称', self.name_edit)
        form.addRow('创建人', self.author_edit)
        form.addRow('推荐使用场景', self.scenario_edit)
        form.addRow('描述', self.desc_edit)
        lay.addLayout(form)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)

    def meta(self):
        return dict(
            name=(self.name_edit.text() or '').strip() or '未命名模板',
            author=(self.author_edit.text() or '').strip(),
            scenario=(self.scenario_edit.text() or '').strip(),
            description=(self.desc_edit.toPlainText() or '').strip(),
        )


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
    """独立「运行界面设计」窗口：控件库 / 分割 / 固定栏绑定 / 模板元数据。"""
    previewRequested = Signal()
    exportRequested = Signal()

    def __init__(self, document=None, parent=None, templates_root=None):
        super().__init__(parent)
        self.document = document
        self.templates_root = Path(templates_root) if templates_root else None
        self._control_state = {}  # name -> {binding, commands, placed}
        self._placements = []  # list of {name, cell, category}
        self._current_control = None
        self._cell_labels = []  # per-page list of QLabel hosts
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
        self.template_combo.addItems([f'分割模板 {i}' for i in range(1, 8)])
        self.template_combo.addItem('保存模板…')
        self.template_combo.addItem('载入模板…')
        bar.addWidget(QLabel(' 模板 '))
        bar.addWidget(self.template_combo)
        self.template_combo.activated.connect(self._on_template_action)
        bar.addSeparator()
        preview_btn = QPushButton('预览')
        preview_btn.setObjectName('primaryButton')
        preview_btn.clicked.connect(self._preview)
        export_btn = QPushButton('导出')
        export_btn.clicked.connect(self._export)
        save_tpl_btn = QPushButton('保存模板')
        save_tpl_btn.clicked.connect(self._save_template)
        market_btn = QPushButton('模板市场…')
        market_btn.setToolTip('行业模板库 + 本地云同步站（:19779；无真实远端/无厂商 SDK）')
        market_btn.clicked.connect(self._open_template_market)
        bar.addWidget(market_btn)
        vm_btn = QPushButton('VM默认运行壳')
        vm_btn.setToolTip('一键放入：图像 + 运行控制 + OK/NG + 运行状态（对标课内 Play/Stop/判定灯）')
        vm_btn.clicked.connect(self._apply_vm_default_shell)
        bar.addWidget(preview_btn)
        bar.addWidget(export_btn)
        bar.addWidget(save_tpl_btn)
        bar.addWidget(vm_btn)
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
        total = sum(len(v) for v in CONTROL_LIBRARY.values())
        lib_hint = QLabel(f'基础 / 布局 / 图表 / 其他 · {total} 个带标签 stub')
        lib_hint.setObjectName('libraryHint')
        ll.addWidget(lib_hint)
        self.lib_tabs = QTabWidget()
        self._lib_lists = {}
        for cat, items in CONTROL_LIBRARY.items():
            lst = QListWidget()
            for name in items:
                item = QListWidgetItem(f'▣ {name}')
                item.setData(Qt.ItemDataRole.UserRole, name)
                hint = CONTROL_STUB_HINTS.get(name, '')
                item.setToolTip(f'[{cat}] {name}' + (f' — {hint}' if hint else '')
                                + '\n单击编辑属性 · 双击放入预览窗格')
                lst.addItem(item)
            lst.itemDoubleClicked.connect(lambda it, c=cat: self._place_stub(it, c))
            self.lib_tabs.addTab(lst, f'{cat} ({len(items)})')
            self._lib_lists[cat] = lst
        ll.addWidget(self.lib_tabs, 1)
        tip = QLabel('点选控件编辑属性；双击放入预览窗格；按钮可配多条触发命令；⛓ 绑定局部变量。')
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

        # Fixed-bar chrome strips (C2 visual)
        self.fix_top_bar = QLabel('')
        self.fix_top_bar.setObjectName('runFixedBar')
        self.fix_top_bar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.fix_top_bar.hide()
        cl.addWidget(self.fix_top_bar)

        mid_row = QHBoxLayout()
        self.fix_left_bar = QLabel('')
        self.fix_left_bar.setObjectName('runFixedBarSide')
        self.fix_left_bar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.fix_left_bar.setFixedWidth(28)
        self.fix_left_bar.hide()
        mid_row.addWidget(self.fix_left_bar)

        self.preview_stack = QStackedWidget()
        self._build_split_pages()
        mid_row.addWidget(self.preview_stack, 1)

        self.fix_right_bar = QLabel('')
        self.fix_right_bar.setObjectName('runFixedBarSide')
        self.fix_right_bar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.fix_right_bar.setFixedWidth(28)
        self.fix_right_bar.hide()
        mid_row.addWidget(self.fix_right_bar)
        cl.addLayout(mid_row, 1)

        self.fix_bottom_bar = QLabel('')
        self.fix_bottom_bar.setObjectName('runFixedBar')
        self.fix_bottom_bar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.fix_bottom_bar.hide()
        cl.addWidget(self.fix_bottom_bar)

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

        grp = QGroupBox('固定栏绑定')
        gf = QFormLayout(grp)
        self.cam_bind = QComboBox()
        self.cam_bind.addItems(CAMERA_BIND_OPTIONS)
        self.cam_bind.setToolTip('绑定相机状态（固定栏实况 / 会话提示）')
        self.comm_bind = QComboBox()
        self.comm_bind.addItems(COMM_BIND_OPTIONS)
        self.comm_bind.setToolTip('绑定通讯状态（固定栏实况 / 徽章）')
        self.cam_bind.currentIndexChanged.connect(self._on_bind_changed)
        self.comm_bind.currentIndexChanged.connect(self._on_bind_changed)
        gf.addRow(QLabel('相机状态'), self.cam_bind)
        gf.addRow(QLabel('通讯状态'), self.comm_bind)
        sw = OrangeSwitch(False)
        gf.addRow(QLabel('使能预览开关'), sw)
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
            lst.currentItemChanged.connect(self._pick_control_item)

        foot = QLabel('  C1 控件库（表格/饼图/线图/组合框容器）· C2 固定栏绑相机/通讯实况 · C3 模板市场+元数据；按钮触发与 ⛓ 已接入。')
        foot.setObjectName('dialogHint')
        foot.setWordWrap(True)
        root.addWidget(foot)

        # Restore saved designer stub from project if any
        if document is not None:
            ui = (document.project or {}).get('runUi') or {}
            self._control_state = deepcopy(ui.get('controls') or {})
            self._placements = deepcopy(ui.get('placements') or [])
            fb = ui.get('fixedBars') or {}
            self.fix_top.setChecked(bool(fb.get('top')))
            self.fix_bottom.setChecked(bool(fb.get('bottom')))
            self.fix_left.setChecked(bool(fb.get('left')))
            self.fix_right.setChecked(bool(fb.get('right')))
            cam = fb.get('cameraBind') or CAMERA_BIND_OPTIONS[0]
            comm = fb.get('commBind') or COMM_BIND_OPTIONS[0]
            ci = self.cam_bind.findText(cam)
            self.cam_bind.setCurrentIndex(ci if ci >= 0 else 0)
            cj = self.comm_bind.findText(comm)
            self.comm_bind.setCurrentIndex(cj if cj >= 0 else 0)
            split = ui.get('split') or '1'
            if split in SPLIT_PRESETS:
                self.split_combo.setCurrentIndex(SPLIT_PRESETS.index(split))
            meta = ui.get('templateMeta') or {}
            self._template_meta = dict(meta)
            self._apply_placements_to_cells()
            self._refresh_fixed_chrome()
        else:
            self._template_meta = {}

    def _apply_vm_default_shell(self):
        """Highest-impact HMI gap fill from VM p=28–29: Play/Stop + OK/NG layout."""
        if '4' in SPLIT_PRESETS:
            self.split_combo.setCurrentIndex(SPLIT_PRESETS.index('4'))
        else:
            self.split_combo.setCurrentIndex(3)
        self._placements = [
            dict(name='图像', page=0, cell=0, category='基础'),
            dict(name='OK/NG', page=0, cell=1, category='基础'),
            dict(name='运行控制', page=0, cell=2, category='基础'),
            dict(name='运行状态', page=0, cell=3, category='基础'),
        ]
        for name in ('图像', 'OK/NG', '运行控制', '运行状态'):
            st = self._control_state.setdefault(name, dict(binding='', commands=[], placed=False))
            st['placed'] = True
            if name == '运行控制' and not st.get('commands'):
                st['commands'] = [dict(type='执行·单次', config='')]
        self.fix_top.setChecked(True)
        self.fix_bottom.setChecked(True)
        self._apply_placements_to_cells()
        self._refresh_fixed_chrome()
        self._persist()
        QMessageBox.information(self, '运行界面', '已应用 VM 默认运行壳：图像 / OK·NG / 运行控制 / 运行状态。')

    def _templates_path(self):
        if self.templates_root is not None:
            d = Path(self.templates_root) / 'projects' / 'run-ui-templates'
            d.mkdir(parents=True, exist_ok=True)
            return d
        # Fall back: sibling of common repo via parent MainWindow.root
        parent = self.parent()
        root = getattr(parent, 'root', None)
        if root:
            d = Path(root) / 'projects' / 'run-ui-templates'
            d.mkdir(parents=True, exist_ok=True)
            return d
        d = Path('projects') / 'run-ui-templates'
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _build_split_pages(self):
        layouts = {
            0: [(1, 1)], 1: [(1, 2)], 2: [(1, 3)], 3: [(2, 2)],
            4: [(2, 3)], 5: [(2, 4)], 6: [(3, 3)], 7: [(2, 2)],
        }
        self._cell_labels = []
        for idx, cells in layouts.items():
            page = QWidget()
            page.setObjectName('runPreviewPage')
            rows, cols = cells[0]
            grid_host = QVBoxLayout(page)
            grid_host.setSpacing(4)
            page_labels = []
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
                    lab.setStyleSheet(f'color:{TEXT_MUTED};font-size:12px;')
                    lab.setWordWrap(True)
                    lab.setProperty('cellIndex', cell_i)
                    cv.addStretch(1)
                    cv.addWidget(lab)
                    cv.addStretch(1)
                    row.addWidget(cell, 1)
                    page_labels.append(lab)
                    cell_i += 1
                grid_host.addLayout(row, 1)
            self.preview_stack.addWidget(page)
            self._cell_labels.append(page_labels)

    def _on_split(self, index):
        self.preview_stack.setCurrentIndex(max(0, min(index, self.preview_stack.count() - 1)))
        self._apply_placements_to_cells()
        self._refresh_fixed_chrome()
        self._persist()

    def _ensure_state(self, name):
        st = self._control_state.setdefault(name, dict(binding='', commands=[], placed=False))
        st.setdefault('binding', '')
        st.setdefault('commands', [])
        st.setdefault('placed', False)
        return st

    def _pick_control_item(self, current, _previous=None):
        if current is None:
            return
        name = current.data(Qt.ItemDataRole.UserRole) or current.text().lstrip('▣ ').strip()
        self._pick_control(name)

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

    def _place_stub(self, item, category):
        name = item.data(Qt.ItemDataRole.UserRole) or item.text().lstrip('▣ ').strip()
        if not name:
            return
        self._pick_control(name)
        page_idx = self.preview_stack.currentIndex()
        labels = self._cell_labels[page_idx] if page_idx < len(self._cell_labels) else []
        # Find next empty cell or wrap
        used = {p.get('cell') for p in self._placements if p.get('page') == page_idx}
        cell = 0
        for i in range(len(labels)):
            if i not in used:
                cell = i
                break
        else:
            cell = len(self._placements) % max(1, len(labels))
        # Replace existing at same cell
        self._placements = [p for p in self._placements
                            if not (p.get('page') == page_idx and p.get('cell') == cell)]
        self._placements.append(dict(name=name, category=category, page=page_idx, cell=cell))
        self._ensure_state(name)['placed'] = True
        self._apply_placements_to_cells()
        self._persist()

    def _apply_placements_to_cells(self):
        page_idx = self.preview_stack.currentIndex()
        labels = self._cell_labels[page_idx] if page_idx < len(self._cell_labels) else []
        for i, lab in enumerate(labels):
            lab.setText(f'窗格 {i + 1}')
            lab.setStyleSheet(f'color:{TEXT_MUTED};font-size:12px;')
        for p in self._placements:
            if p.get('page') != page_idx:
                continue
            cell = int(p.get('cell') or 0)
            if 0 <= cell < len(labels):
                cat = p.get('category') or ''
                name = p.get('name') or ''
                hint = CONTROL_STUB_HINTS.get(name, '')
                labels[cell].setText(f'▣ {name}\n[{cat}]' + (f'\n{hint}' if hint else ''))
                labels[cell].setStyleSheet(f'color:{TEXT};font-weight:600;font-size:12px;')

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

    def _on_bind_changed(self, *_):
        self._refresh_fixed_chrome()

    def _persist(self):
        if self.document is None:
            return
        p = deepcopy(self.document.project)
        ui = p.setdefault('runUi', {})
        ui['controls'] = deepcopy(self._control_state)
        ui['placements'] = deepcopy(self._placements)
        ui['split'] = SPLIT_PRESETS[self.split_combo.currentIndex()]
        ui['fixedBars'] = dict(
            top=self.fix_top.isChecked(),
            bottom=self.fix_bottom.isChecked(),
            left=self.fix_left.isChecked(),
            right=self.fix_right.isChecked(),
            cameraBind=self.cam_bind.currentText(),
            commBind=self.comm_bind.currentText(),
        )
        if getattr(self, '_template_meta', None):
            ui['templateMeta'] = deepcopy(self._template_meta)
        try:
            self.document.commit(p)
        except Exception:
            self.document.project = p
            self.document.changed.emit()

    def _refresh_fixed_chrome(self, *_):
        cam = self.cam_bind.currentText()
        comm = self.comm_bind.currentText()
        parts = []
        if self.fix_top.isChecked():
            parts.append('顶')
            self.fix_top_bar.setText(f'顶部固定栏 · 相机:{cam} · 通讯:{comm}')
            self.fix_top_bar.show()
        else:
            self.fix_top_bar.hide()
        if self.fix_bottom.isChecked():
            parts.append('底')
            self.fix_bottom_bar.setText(f'底部固定栏 · 相机:{cam} · 通讯:{comm}')
            self.fix_bottom_bar.show()
        else:
            self.fix_bottom_bar.hide()
        if self.fix_left.isChecked():
            parts.append('左')
            self.fix_left_bar.setText('左\n固\n定\n栏')
            self.fix_left_bar.setToolTip(f'相机:{cam} · 通讯:{comm}')
            self.fix_left_bar.show()
        else:
            self.fix_left_bar.hide()
        if self.fix_right.isChecked():
            parts.append('右')
            self.fix_right_bar.setText('右\n固\n定\n栏')
            self.fix_right_bar.setToolTip(f'相机:{cam} · 通讯:{comm}')
            self.fix_right_bar.show()
        else:
            self.fix_right_bar.hide()
        chrome = '、'.join(parts) if parts else '无'
        self.preview_label.setText(
            f'运行界面预览 · {SPLIT_PRESETS[self.split_combo.currentIndex()]} 分屏 · 固定栏：{chrome}')
        self._persist()

    def _snapshot(self):
        return dict(
            format='sieans.runUiTemplate',
            version=1,
            meta=deepcopy(getattr(self, '_template_meta', {}) or {}),
            split=SPLIT_PRESETS[self.split_combo.currentIndex()],
            controls=deepcopy(self._control_state),
            placements=deepcopy(self._placements),
            fixedBars=dict(
                top=self.fix_top.isChecked(),
                bottom=self.fix_bottom.isChecked(),
                left=self.fix_left.isChecked(),
                right=self.fix_right.isChecked(),
                cameraBind=self.cam_bind.currentText(),
                commBind=self.comm_bind.currentText(),
            ),
            savedAt=datetime.now().isoformat(timespec='seconds'),
        )

    def _apply_snapshot(self, data):
        if not isinstance(data, dict):
            return
        self._control_state = deepcopy(data.get('controls') or {})
        self._placements = deepcopy(data.get('placements') or [])
        self._template_meta = deepcopy(data.get('meta') or {})
        split = data.get('split') or '1'
        if split in SPLIT_PRESETS:
            self.split_combo.blockSignals(True)
            self.split_combo.setCurrentIndex(SPLIT_PRESETS.index(split))
            self.split_combo.blockSignals(False)
            self.preview_stack.setCurrentIndex(SPLIT_PRESETS.index(split))
        fb = data.get('fixedBars') or {}
        for cb, key in ((self.fix_top, 'top'), (self.fix_bottom, 'bottom'),
                        (self.fix_left, 'left'), (self.fix_right, 'right')):
            cb.blockSignals(True)
            cb.setChecked(bool(fb.get(key)))
            cb.blockSignals(False)
        cam = fb.get('cameraBind') or CAMERA_BIND_OPTIONS[0]
        comm = fb.get('commBind') or COMM_BIND_OPTIONS[0]
        ci = self.cam_bind.findText(cam)
        self.cam_bind.blockSignals(True)
        self.cam_bind.setCurrentIndex(ci if ci >= 0 else 0)
        self.cam_bind.blockSignals(False)
        cj = self.comm_bind.findText(comm)
        self.comm_bind.blockSignals(True)
        self.comm_bind.setCurrentIndex(cj if cj >= 0 else 0)
        self.comm_bind.blockSignals(False)
        self._apply_placements_to_cells()
        self._refresh_fixed_chrome()

    def _on_template_action(self, index):
        # 0..6 = 分割模板 1-7；7=保存；8=载入
        if index < 7:
            # Apply split preset skeleton matching template index (1→1, 2→2, … map to SPLIT)
            map_idx = min(index, len(SPLIT_PRESETS) - 2)  # keep 自定义 last
            self.split_combo.setCurrentIndex(map_idx)
            return
        if index == 7:
            self._save_template()
            self.template_combo.setCurrentIndex(0)
            return
        if index == 8:
            self._load_template()
            self.template_combo.setCurrentIndex(0)


    def _open_template_market(self):
        """行业模板市场 + 本地云同步站（HTTP :19779，无真实远端）。"""
        from PySide6.QtWidgets import (
            QDialog, QVBoxLayout, QListWidget, QListWidgetItem, QDialogButtonBox,
            QLabel, QHBoxLayout, QPushButton, QMessageBox, QLineEdit,
        )
        from desktop import template_market_local as tml

        folder = self._templates_path()
        folder.mkdir(parents=True, exist_ok=True)
        # Seed industry samples if empty/missing
        samples = {
            '行业-电子元件点检.ruitpl.json': {
                'meta': {
                    'name': '电子元件点检',
                    'author': 'SIEANS',
                    'scenario': 'SMT/插件外观 OK-NG',
                    'description': '图像 + OK/NG + 表格统计 + 信息栏（示意）',
                },
                'version': 1,
                'split': 2,
                'placements': [
                    {'name': '图像', 'category': '显示'},
                    {'name': '运行控制', 'category': '控制'},
                    {'name': 'OK', 'category': '控制'},
                    {'name': 'NG', 'category': '控制'},
                    {'name': '表格', 'category': '显示'},
                    {'name': '信息提示栏', 'category': '显示'},
                ],
            },
            '行业-尺寸测量台.ruitpl.json': {
                'meta': {
                    'name': '尺寸测量台',
                    'author': 'SIEANS',
                    'scenario': '卡尺/几何量测',
                    'description': '图像 + 多数据线图 + 表格 + 运行状态',
                },
                'version': 1,
                'split': 3,
                'placements': [
                    {'name': '图像', 'category': '显示'},
                    {'name': '多数据线图', 'category': '显示'},
                    {'name': '表格', 'category': '显示'},
                    {'name': '运行状态', 'category': '显示'},
                    {'name': '运行控制', 'category': '控制'},
                ],
            },
            '行业-包装缺陷分拣.ruitpl.json': {
                'meta': {
                    'name': '包装缺陷分拣',
                    'author': 'SIEANS',
                    'scenario': '包装/标签缺陷',
                    'description': '图像 + 饼图 + OK/NG + 组合框容器壳',
                },
                'version': 1,
                'split': 2,
                'placements': [
                    {'name': '图像', 'category': '显示'},
                    {'name': '饼图', 'category': '显示'},
                    {'name': '组合框', 'category': '容器'},
                    {'name': 'OK', 'category': '控制'},
                    {'name': 'NG', 'category': '控制'},
                    {'name': '信息提示栏', 'category': '显示'},
                ],
            },
            '行业-印刷字符读码.ruitpl.json': {
                'meta': {
                    'name': '印刷字符读码',
                    'author': 'SIEANS',
                    'scenario': '包装/标签 OCR · 字符比对',
                    'description': '图像 + OCR结果表 + OK/NG + 运行控制 + 信息栏（UI-only）',
                },
                'version': 1,
                'split': 4,
                'placements': [
                    {'name': '图像', 'category': '显示'},
                    {'name': '表格', 'category': '显示'},
                    {'name': 'OK/NG', 'category': '控制'},
                    {'name': '运行控制', 'category': '控制'},
                    {'name': '信息提示栏', 'category': '显示'},
                    {'name': '文本框', 'category': '显示'},
                ],
            },
        }
        for fname, payload in samples.items():
            path = folder / fname
            if not path.exists():
                path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')

        # Local "cloud" store under data dir when available
        parent = self.parent()
        data_root = getattr(parent, 'data', None) or getattr(parent, 'data_dir', None)
        store = Path(data_root) / 'template-market' if data_root else Path('data/native-desktop/template-market')
        tml.configure(seed_dir=folder, store_dir=store)
        try:
            tml.start()
        except OSError as err:
            # port busy — still allow file-only browse
            pass

        dlg = QDialog(self)
        dlg.setWindowTitle('运行界面 · 模板市场（本地云同步）')
        dlg.resize(560, 420)
        lay = QVBoxLayout(dlg)
        st = tml.status()
        head = QLabel(
            f'行业示意模板 · 本地站 {st.get("url")}  '
            f'{"●运行中" if st.get("running") else "○未启动"}（无真实远端后端）'
        )
        head.setWordWrap(True)
        lay.addWidget(head)
        url_edit = QLineEdit(st.get('url') or 'http://127.0.0.1:19779')
        url_edit.setPlaceholderText('本地/局域网模板市场 URL')
        lay.addWidget(url_edit)
        lst = QListWidget()
        lay.addWidget(lst, 1)
        tip = QLabel('双击或「载入选中」应用；「云同步」拉取本地站列表；「发布当前」上传设计器快照。')
        tip.setStyleSheet('color:#666;font-size:11px;')
        lay.addWidget(tip)

        def _fill(items):
            lst.clear()
            for it in items:
                if isinstance(it, dict):
                    label = f"{it.get('title') or it.get('name')}  ·  {it.get('scenario') or ''}  [{it.get('origin') or 'local'}]"
                    path_or_name = it.get('name')
                    meta = it
                else:
                    # Path
                    f = Path(it)
                    try:
                        data = json.loads(f.read_text(encoding='utf-8'))
                        meta = data.get('meta') or {}
                        label = f"{meta.get('name') or f.stem}  ·  {meta.get('scenario') or ''}"
                    except Exception:
                        label = f.stem
                        meta = {}
                    path_or_name = str(f)
                item = QListWidgetItem(label)
                item.setData(256, path_or_name)
                item.setData(257, meta if isinstance(meta, dict) else {})
                lst.addItem(item)

        def _refresh_local():
            files = sorted(folder.glob('*.ruitpl.json')) + sorted(folder.glob('*.json'))
            seen = set()
            paths = []
            for f in files:
                if f.name in seen:
                    continue
                seen.add(f.name)
                paths.append(f)
            # merge store
            if store.exists():
                for f in sorted(store.glob('*.ruitpl.json')):
                    if f.name not in seen:
                        seen.add(f.name)
                        paths.append(f)
            _fill(paths)

        def _sync_cloud():
            base = (url_edit.text() or '').strip() or st.get('url')
            try:
                # ensure local server if pointing at default
                if '127.0.0.1:19779' in base or 'localhost:19779' in base:
                    try:
                        tml.start()
                    except OSError:
                        pass
                data = tml.client_sync(base)
                items = data.get('templates') or []
                _fill(items)
                QMessageBox.information(dlg, '云同步', f'已同步 {len(items)} 个模板（本地站）。')
            except Exception as err:
                QMessageBox.warning(dlg, '云同步', f'同步失败：{err}\n可仍使用本地文件列表。')
                _refresh_local()

        def _load():
            item = lst.currentItem()
            if not item:
                QMessageBox.information(dlg, '模板市场', '请先选择模板。')
                return
            key = item.data(256)
            data = None
            try:
                path = Path(str(key))
                if path.is_file():
                    data = json.loads(path.read_text(encoding='utf-8'))
                else:
                    base = (url_edit.text() or '').strip() or st.get('url')
                    data = tml.client_download(str(key), base)
            except Exception as err:
                QMessageBox.warning(dlg, '模板市场', f'读取失败：{err}')
                return
            try:
                if hasattr(self, '_apply_snapshot'):
                    self._apply_snapshot(data)
            except Exception:
                pass
            self._template_meta = dict(data.get('meta') or {})
            QMessageBox.information(
                dlg, '模板市场',
                f"已载入示意模板「{self._template_meta.get('name') or key}」。\n"
                '可继续调整控件与固定栏绑定。',
            )
            dlg.accept()

        def _publish():
            try:
                snap = self._snapshot() if hasattr(self, '_snapshot') else {
                    'meta': dict(getattr(self, '_template_meta', None) or {}),
                    'format': 'sieans.runUiTemplate',
                    'version': 1,
                }
                meta = dict(snap.get('meta') or getattr(self, '_template_meta', None) or {})
                if not meta.get('name'):
                    meta['name'] = '未命名界面'
                snap['meta'] = meta
                base = (url_edit.text() or '').strip() or st.get('url')
                if '127.0.0.1:19779' in base or 'localhost:19779' in base:
                    try:
                        tml.start()
                    except OSError:
                        pass
                info = tml.client_publish(snap, base_url=base)
                _sync_cloud()
                QMessageBox.information(dlg, '发布', f"已发布到本地站：{info.get('name')}")
            except Exception as err:
                QMessageBox.warning(dlg, '发布', f'发布失败：{err}')

        row = QHBoxLayout()
        btn_sync = QPushButton('云同步')
        btn_sync.setToolTip('从本地模板站拉取列表（云同步替身）')
        btn_sync.clicked.connect(_sync_cloud)
        btn_pub = QPushButton('发布当前')
        btn_pub.setToolTip('把当前设计器快照 POST 到本地站')
        btn_pub.clicked.connect(_publish)
        btn_start = QPushButton('启动本地站')
        def _ensure():
            try:
                info = tml.start()
                url_edit.setText(info.get('url') or url_edit.text())
                head.setText(
                    f'行业示意模板 · 本地站 {info.get("url")}  ●运行中（无真实远端后端）'
                )
                QMessageBox.information(dlg, '本地站', f'已启动 {info.get("url")}')
            except Exception as err:
                QMessageBox.warning(dlg, '本地站', str(err))
        btn_start.clicked.connect(_ensure)
        row.addWidget(btn_start)
        row.addWidget(btn_sync)
        row.addWidget(btn_pub)
        row.addStretch(1)
        lay.addLayout(row)

        bb = QDialogButtonBox()
        load_btn = bb.addButton('载入选中', QDialogButtonBox.ButtonRole.AcceptRole)
        bb.addButton(QDialogButtonBox.StandardButton.Close)
        lay.addWidget(bb)
        load_btn.clicked.connect(_load)
        lst.itemDoubleClicked.connect(lambda *_: _load())
        bb.rejected.connect(dlg.reject)
        _refresh_local()
        dlg.exec()


    def _save_template(self):
        dlg = SaveUiTemplateDialog(self._template_meta, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        self._template_meta = dlg.meta()
        snap = self._snapshot()
        folder = self._templates_path()
        safe = ''.join(c if c.isalnum() or c in '-_' else '_' for c in self._template_meta['name'])[:40]
        path = folder / f'{safe or "run_ui"}.ruitpl.json'
        # Allow choose path
        chosen, _ = QFileDialog.getSaveFileName(
            self, '保存运行界面模板', str(path),
            '运行界面模板 (*.ruitpl.json *.json)')
        if not chosen:
            return
        Path(chosen).write_text(json.dumps(snap, ensure_ascii=False, indent=2), encoding='utf-8')
        self._persist()
        QMessageBox.information(
            self, '保存模板',
            f'已保存模板「{self._template_meta["name"]}」\n'
            f'创建人：{self._template_meta.get("author") or "—"}\n'
            f'场景：{self._template_meta.get("scenario") or "—"}\n{chosen}')

    def _load_template(self):
        folder = self._templates_path()
        chosen, _ = QFileDialog.getOpenFileName(
            self, '载入运行界面模板', str(folder),
            '运行界面模板 (*.ruitpl.json *.json);;全部 (*.*)')
        if not chosen:
            return
        try:
            data = json.loads(Path(chosen).read_text(encoding='utf-8-sig'))
        except Exception as err:
            QMessageBox.warning(self, '载入模板', f'无法读取：{err}')
            return
        if data.get('format') not in ('sieans.runUiTemplate', None) and 'controls' not in data and 'fixedBars' not in data:
            # still try if it looks like a snapshot
            if 'split' not in data and 'meta' not in data:
                QMessageBox.warning(self, '载入模板', '不是有效的运行界面模板。')
                return
        self._apply_snapshot(data)
        self._persist()
        name = (self._template_meta or {}).get('name') or Path(chosen).stem
        QMessageBox.information(self, '载入模板', f'已载入模板「{name}」。')

    def _preview(self):
        self.previewRequested.emit()
        n_btn = sum(1 for k, v in self._control_state.items()
                    if k in ('按钮', '运行控制', '开关控制') and v.get('commands'))
        QMessageBox.information(
            self, '预览',
            f'运行界面预览：已配置控件 {len(self._control_state)} 个，'
            f'窗格放置 {len(self._placements)} 个，含触发命令的按钮类 {n_btn} 个。\n'
            f'固定栏相机：{self.cam_bind.currentText()} · 通讯：{self.comm_bind.currentText()}\n'
            '操作员态将按布局与命令执行：按钮/开关 → 全局触发（单次/连续/停止/注入 RUN）；图像与状态格由运行壳刷新。')

    def _export(self):
        self.exportRequested.emit()
        # Export = save template skeleton shortcut
        if not self._template_meta:
            self._template_meta = dict(name='导出模板', author='', scenario='', description='')
        self._save_template()


def default_host_run_ui():
    """p41–43 style layout metadata: split-2 with 图像 + 上位机状态机."""
    return {
        'split': '2',
        'placements': [
            {'name': '图像', 'page': 1, 'cell': 0, 'category': '基础'},
            {'name': '上位机状态机', 'page': 1, 'cell': 1, 'category': '基础'},
        ],
        'controls': {
            '图像': {'commands': [], 'binding': 'source'},
            '上位机状态机': {
                'commands': [
                    {'type': '执行·连续', 'config': ''},
                    {'type': '执行·停止', 'config': ''},
                ],
                'binding': 'host',
            },
        },
        'fixedBars': {
            'top': False, 'bottom': True, 'left': False, 'right': False,
            'cameraBind': '未绑定', 'commBind': 'TCP.连接状态',
            'showRunStatus': True, 'showOkNg': True,
        },
        'meta': {'template': 'host_state_machine', 'version': 1},
    }
