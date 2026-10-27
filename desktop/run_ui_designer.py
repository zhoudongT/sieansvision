"""运行界面设计器骨架 — 对标 VM4.4 运行界面设计入口。

控件库四类 / 布局分割 / 固定栏 / 预览·导出占位。完整绑定与触发命令见后续批次。
"""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QListWidget,
    QListWidgetItem, QSplitter, QWidget, QComboBox, QFrame, QTabWidget,
    QTreeWidget, QTreeWidgetItem, QMessageBox, QCheckBox, QGroupBox,
    QFormLayout, QToolBar, QSizePolicy, QStackedWidget,
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


class RunUiDesignerDialog(QDialog):
    """独立「运行界面设计」窗口骨架。"""
    previewRequested = Signal()
    exportRequested = Signal()

    def __init__(self, document=None, parent=None):
        super().__init__(parent)
        self.document = document
        self.setWindowTitle('运行界面设计')
        self.resize(1280, 820)
        self.setMinimumSize(960, 640)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Top bar
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

        # Left: control library
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
        tip = QLabel('拖入预览区（本批为骨架：点选列出控件名）')
        tip.setObjectName('dialogHint')
        tip.setWordWrap(True)
        ll.addWidget(tip)
        body.addWidget(left)

        # Center: split preview
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

        # Right: fixed bars + props
        right = QWidget()
        right.setObjectName('imagePane')
        right.setMinimumWidth(240)
        right.setMaximumWidth(340)
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
        pf.addRow(QLabel('数据源'), QLabel('可订阅流程输出 / 局部变量'))
        pf.addRow(QLabel('触发命令'), QLabel('多条命令自上而下（P1）'))
        rl.addWidget(props)
        rl.addStretch(1)
        body.addWidget(right)

        body.setSizes([260, 720, 280])

        # Wire list selection → prop
        for i in range(self.lib_tabs.count()):
            lst = self.lib_tabs.widget(i)
            lst.currentTextChanged.connect(self._pick_control)

        foot = QLabel('  预览 / 导出为占位；完整 HMI 仍可用「工程管理 → 运行画面编辑」。本设计器对标 VM4.4 入口与信息架构。')
        foot.setObjectName('dialogHint')
        foot.setWordWrap(True)
        root.addWidget(foot)

    def _build_split_pages(self):
        # Build simple grid previews for 1/2/3/4/6/8/9
        layouts = {
            0: [(1, 1)],
            1: [(1, 2)],
            2: [(1, 3)],
            3: [(2, 2)],
            4: [(2, 3)],
            5: [(2, 4)],
            6: [(3, 3)],
            7: [(2, 2)],  # 自定义 — same as 4 for shell
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
            # Fixed bar chrome placeholders
            self.preview_stack.addWidget(page)
        self._chrome = {}

    def _on_split(self, index):
        self.preview_stack.setCurrentIndex(max(0, min(index, self.preview_stack.count() - 1)))
        self.preview_label.setText(f'运行界面预览 · {SPLIT_PRESETS[index]} 分屏')

    def _pick_control(self, name):
        if name:
            self.prop_name.setText(name)

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

    def _preview(self):
        self.previewRequested.emit()
        QMessageBox.information(self, '预览', '运行界面预览（骨架）：操作员态将按此布局展示。完整数据绑定见后续批次。')

    def _export(self):
        self.exportRequested.emit()
        QMessageBox.information(self, '导出', '导出占位：后续将写出运行界面模板（名称/创建人/推荐使用场景/描述）。')
