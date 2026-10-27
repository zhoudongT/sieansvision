"""全流程 card panel — per-flow 单次/连续/参数/使能/次数·耗时 + I/O three tabs."""
from copy import deepcopy
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea,
    QFrame, QCheckBox, QDialog, QTabWidget, QTableWidget, QTableWidgetItem,
    QHeaderView, QDialogButtonBox, QFormLayout, QGraphicsView, QGraphicsScene,
    QGraphicsRectItem, QGraphicsTextItem, QGraphicsLineItem, QGraphicsItem,
)
from PySide6.QtGui import QColor, QPen, QBrush, QFont, QPainter


class FlowParamDialog(QDialog):
    """流程参数窗：输入设置 / 输出设置 / 显示设置（可编辑并回写 io）"""
    def __init__(self, flow, parent=None):
        super().__init__(parent)
        self.flow = deepcopy(flow)
        title = f"{flow.get('name') or '流程'} 参数"
        self.setWindowTitle(title)
        self.resize(520, 420)
        lay = QVBoxLayout(self)
        head = QLabel(title)
        head.setObjectName('dialogTitle')
        lay.addWidget(head)
        hint = QLabel('流程级 I/O 与显示：表格可编辑；确定后写回 flow.io（订阅名支持 模块.字段）')
        hint.setObjectName('dialogHint')
        lay.addWidget(hint)
        self.tabs = QTabWidget()
        lay.addWidget(self.tabs, 1)
        io = flow.get('io') or {}
        self._in_table = None
        self._out_table = None
        self._global_image_sw = None
        in_w, self._in_table = self._table(io.get('inputs') or [], '输入')
        out_w, self._out_table = self._table(io.get('outputs') or [], '输出')
        self.tabs.addTab(in_w, '输入设置')
        self.tabs.addTab(out_w, '输出设置')
        self.tabs.addTab(self._display(io.get('display') or {}), '显示设置')
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._accept_save)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)

    def _table(self, rows, kind):
        w = QWidget()
        v = QVBoxLayout(w)
        table = QTableWidget(max(4, len(rows) or 2), 3)
        table.setObjectName('flowIoTable')
        table.setHorizontalHeaderLabels(['参数名称', '类型', '订阅关系'])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        if not rows:
            demo = [
                ('ImageData', 'IMAGE', '—'),
                ('InputROI', 'ROI', '—'),
            ] if kind == '输入' else [
                ('ImageData', 'IMAGE', '0 图像源1.图像[]'),
                ('Result', 'JSON', '—'),
            ]
            for r, row in enumerate(demo):
                for c, val in enumerate(row):
                    table.setItem(r, c, QTableWidgetItem(val))
        else:
            for r, row in enumerate(rows):
                table.setItem(r, 0, QTableWidgetItem(str(row.get('name', ''))))
                table.setItem(r, 1, QTableWidgetItem(str(row.get('type', ''))))
                table.setItem(r, 2, QTableWidgetItem(str(row.get('binding', ''))))
        tip = QLabel('空行忽略；订阅关系例：0 图像源1.图像[] / flow.var')
        tip.setStyleSheet('color:#888;font-size:11px;')
        v.addWidget(table, 1)
        v.addWidget(tip)
        return w, table

    def _display(self, display):
        from desktop.widgets.switch import OrangeSwitch
        w = QWidget()
        form = QFormLayout(w)
        self._global_image_sw = OrangeSwitch(bool(display.get('globalImage', True)))
        form.addRow(QLabel('显示全局图像'), self._global_image_sw)
        form.addRow(QLabel('说明'), QLabel(display.get('note') or '流程级显示：与运行界面分屏 / 固定栏配置联动'))
        return w

    def _read_table(self, table):
        rows = []
        if table is None:
            return rows
        for r in range(table.rowCount()):
            name = (table.item(r, 0).text() if table.item(r, 0) else '').strip()
            typ = (table.item(r, 1).text() if table.item(r, 1) else '').strip()
            bind = (table.item(r, 2).text() if table.item(r, 2) else '').strip()
            if not name:
                continue
            rows.append(dict(name=name, type=typ or 'ANY', binding=bind))
        return rows

    def _accept_save(self):
        io = dict(self.flow.get('io') or {})
        io['inputs'] = self._read_table(self._in_table)
        io['outputs'] = self._read_table(self._out_table)
        disp = dict(io.get('display') or {})
        if self._global_image_sw is not None:
            disp['globalImage'] = bool(self._global_image_sw.isChecked())
        io['display'] = disp
        self.flow['io'] = io
        self.accept()

    def result_io(self):
        return (self.flow.get('io') or {})


class FlowCard(QFrame):
    runOnce = Signal(str)
    runContinuous = Signal(str)
    paramsRequested = Signal(str)
    enableChanged = Signal(str, bool)
    openFlow = Signal(str)

    def __init__(self, flow, parent=None):
        super().__init__(parent)
        self.flow_id = flow.get('id')
        self.setObjectName('flowCard')
        self.setFixedSize(240, 150)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(6)

        top = QHBoxLayout()
        self.title = QLabel(flow.get('name') or '流程')
        self.title.setObjectName('flowCardTitle')
        top.addWidget(self.title, 1)
        self.enable = QCheckBox('使能')
        self.enable.setChecked(bool(flow.get('enabled', True)))
        self.enable.toggled.connect(lambda v: self.enableChanged.emit(self.flow_id, v))
        top.addWidget(self.enable)
        lay.addLayout(top)

        stats = QLabel(f"{int(flow.get('runCount') or 0)}次 · {float(flow.get('lastElapsedMs') or 0):.2f}ms")
        stats.setObjectName('flowCardStats')
        self.stats = stats
        lay.addWidget(stats)

        row = QHBoxLayout()
        once = QPushButton('▶ 单次')
        once.setObjectName('primaryButton')
        once.clicked.connect(lambda: self.runOnce.emit(self.flow_id))
        cont = QPushButton('↻ 连续')
        cont.clicked.connect(lambda: self.runContinuous.emit(self.flow_id))
        gear = QPushButton('⚙ 参数')
        gear.clicked.connect(lambda: self.paramsRequested.emit(self.flow_id))
        row.addWidget(once)
        row.addWidget(cont)
        row.addWidget(gear)
        lay.addLayout(row)

        open_btn = QPushButton('打开流程画布')
        open_btn.clicked.connect(lambda: self.openFlow.emit(self.flow_id))
        lay.addWidget(open_btn)

    def update_flow(self, flow):
        self.title.setText(flow.get('name') or '流程')
        self.enable.blockSignals(True)
        self.enable.setChecked(bool(flow.get('enabled', True)))
        self.enable.blockSignals(False)
        self.stats.setText(f"{int(flow.get('runCount') or 0)}次 · {float(flow.get('lastElapsedMs') or 0):.2f}ms")


class AllFlowsPanel(QWidget):
    """全流程视图：流程卡片栅格 + 流程间连线占位说明。"""
    runOnce = Signal(str)
    runContinuous = Signal(str)
    openFlow = Signal(str)
    metaChanged = Signal(str, dict)  # flow_id, meta

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('allFlowsPanel')
        self._flows = []
        self._cards = {}
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        head = QHBoxLayout()
        title = QLabel('全流程')
        title.setObjectName('dialogTitle')
        head.addWidget(title)
        tip = QLabel('流程卡片编排 · 单次/连续/参数/使能 · 流程间连线（壳层）')
        tip.setObjectName('dialogHint')
        head.addWidget(tip, 1)
        root.addLayout(head)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.host = QWidget()
        self.grid = QHBoxLayout(self.host)  # simple wrap via nested rows
        self.grid.setContentsMargins(4, 4, 4, 4)
        self.grid.setSpacing(12)
        self.grid.addStretch(1)
        self.scroll.setWidget(self.host)
        root.addWidget(self.scroll, 1)

        self.link_hint = QLabel('流程间连线：在后续批次中支持拖拽编排；当前可在各流程 Tab 内编辑模块。')
        self.link_hint.setObjectName('dialogHint')
        root.addWidget(self.link_hint)

    def set_flows(self, flows):
        self._flows = list(flows or [])
        # rebuild
        while self.grid.count():
            item = self.grid.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self._cards.clear()
        for flow in self._flows:
            card = FlowCard(flow)
            card.runOnce.connect(self.runOnce.emit)
            card.runContinuous.connect(self.runContinuous.emit)
            card.openFlow.connect(self.openFlow.emit)
            card.paramsRequested.connect(self._open_params)
            card.enableChanged.connect(lambda fid, en: self.metaChanged.emit(fid, {'enabled': en}))
            self._cards[flow.get('id')] = card
            self.grid.addWidget(card)
        self.grid.addStretch(1)

    def _open_params(self, flow_id):
        flow = next((f for f in self._flows if f.get('id') == flow_id), None)
        if not flow:
            return
        dlg = FlowParamDialog(flow, self)
        if dlg.exec():
            io = dlg.result_io()
            flow['io'] = io
            self.metaChanged.emit(flow_id, {'io': io})
