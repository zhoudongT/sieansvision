"""VisionMaster-style multi-flow tab bar: 全流程 | 流程N [▶][↻] | +"""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QPushButton, QLabel, QMenu, QFrame, QSizePolicy,
)


class FlowTabBar(QWidget):
    """Tab strip for scheme flows + 全流程 entry."""
    allFlowsRequested = Signal()
    flowSelected = Signal(str)          # flow_id
    addFlowRequested = Signal()
    runOnceRequested = Signal(str)      # flow_id
    runContinuousRequested = Signal(str)
    contextAction = Signal(str, str)    # flow_id, action_key

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('flowTabBar')
        self._active = None
        self._showing_all = False
        self._flows = []
        root = QHBoxLayout(self)
        root.setContentsMargins(6, 4, 6, 4)
        root.setSpacing(4)

        self.all_btn = QPushButton('全流程')
        self.all_btn.setObjectName('flowAllButton')
        self.all_btn.setCheckable(True)
        self.all_btn.setToolTip('打开全流程编排视图')
        self.all_btn.clicked.connect(self._on_all)
        root.addWidget(self.all_btn)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet('color:#3a4552;')
        root.addWidget(sep)

        self.tabs_host = QWidget()
        self.tabs_layout = QHBoxLayout(self.tabs_host)
        self.tabs_layout.setContentsMargins(0, 0, 0, 0)
        self.tabs_layout.setSpacing(4)
        self.tabs_layout.addStretch(1)
        root.addWidget(self.tabs_host, 1)

        self.add_btn = QPushButton('+')
        self.add_btn.setObjectName('flowAddButton')
        self.add_btn.setFixedWidth(28)
        self.add_btn.setToolTip('新建流程')
        self.add_btn.clicked.connect(self.addFlowRequested.emit)
        root.addWidget(self.add_btn)

        hint = QLabel('')
        hint.setObjectName('flowTabHint')
        self._hint = hint
        root.addWidget(hint)

    def _on_all(self):
        self._showing_all = True
        self.all_btn.setChecked(True)
        self._refresh_checks()
        self.allFlowsRequested.emit()

    def set_flows(self, flows, active_id=None, showing_all=False):
        self._flows = list(flows or [])
        self._active = active_id
        self._showing_all = bool(showing_all)
        self.all_btn.setChecked(self._showing_all)
        # Clear old tab widgets (keep stretch at end)
        while self.tabs_layout.count() > 1:
            item = self.tabs_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        for flow in self._flows:
            self.tabs_layout.insertWidget(self.tabs_layout.count() - 1, self._make_tab(flow))
        self._refresh_checks()

    def _make_tab(self, flow):
        fid = flow.get('id')
        name = flow.get('name') or '流程'
        wrap = QWidget()
        wrap.setObjectName('flowTab')
        wrap.setProperty('flowId', fid)
        wrap.setProperty('active', fid == self._active and not self._showing_all)
        lay = QHBoxLayout(wrap)
        lay.setContentsMargins(2, 0, 2, 0)
        lay.setSpacing(2)

        name_btn = QPushButton(name)
        name_btn.setObjectName('flowTabName')
        name_btn.setCheckable(True)
        name_btn.setChecked(fid == self._active and not self._showing_all)
        name_btn.setToolTip(f'切换到「{name}」')
        name_btn.clicked.connect(lambda _=False, i=fid: self._select(i))
        name_btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        name_btn.customContextMenuRequested.connect(
            lambda pos, i=fid, b=name_btn: self._menu(i, b.mapToGlobal(pos)))
        lay.addWidget(name_btn)

        once = QPushButton('▶')
        once.setObjectName('flowTabRun')
        once.setFixedWidth(24)
        once.setToolTip('单次执行此流程')
        once.clicked.connect(lambda _=False, i=fid: self.runOnceRequested.emit(i))
        lay.addWidget(once)

        cont = QPushButton('↻')
        cont.setObjectName('flowTabRun')
        cont.setFixedWidth(24)
        cont.setToolTip('连续执行此流程')
        cont.clicked.connect(lambda _=False, i=fid: self.runContinuousRequested.emit(i))
        lay.addWidget(cont)

        wrap.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        wrap.customContextMenuRequested.connect(
            lambda pos, i=fid, w=wrap: self._menu(i, w.mapToGlobal(pos)))
        wrap.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
        return wrap

    def _select(self, flow_id):
        self._showing_all = False
        self._active = flow_id
        self.all_btn.setChecked(False)
        self._refresh_checks()
        self.flowSelected.emit(flow_id)

    def _refresh_checks(self):
        for i in range(self.tabs_layout.count() - 1):
            w = self.tabs_layout.itemAt(i).widget()
            if not w:
                continue
            fid = w.property('flowId')
            active = fid == self._active and not self._showing_all
            w.setProperty('active', active)
            name_btn = w.findChild(QPushButton, 'flowTabName')
            if name_btn:
                name_btn.setChecked(active)
            w.style().unpolish(w)
            w.style().polish(w)

    def _menu(self, flow_id, global_pos):
        menu = QMenu(self)
        actions = [
            ('export', '流程导出'),
            ('copy', '流程拷贝'),
            ('delete', '删除'),
            None,
            ('interval', '设置运行间隔'),
            ('stop_on_ng', '流程执行NG时停止'),
            ('rename', '重命名'),
            ('timeout', '设置流程超时时间'),
        ]
        flow = next((f for f in self._flows if f.get('id') == flow_id), {})
        for item in actions:
            if item is None:
                menu.addSeparator()
                continue
            key, label = item
            act = menu.addAction(label)
            if key == 'stop_on_ng':
                act.setCheckable(True)
                act.setChecked(bool(flow.get('stopOnNg')))
            act.triggered.connect(lambda _=False, k=key, i=flow_id: self.contextAction.emit(i, k))
        menu.exec(global_pos)
