"""Light property float over dark canvas (VisionMaster 属性浮窗)."""
from copy import deepcopy

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QWidget,
    QFrame,
)

from desktop.forms import ParameterPanel
from desktop.image_source import ImageSourceForm
from desktop.theme import PROPERTY_FLOAT_QSS


class PropertyFloat(QDialog):
    """浅色面板叠在深色画布上；深色标题条 + 橙线 + 底栏 连续执行/执行/确定。"""
    changed = Signal(dict)
    sourceChanged = Signal(dict)
    runModule = Signal(object)
    runModuleContinuous = Signal(object)
    paramAudited = Signal(str, str, object, object)
    openCameraManager = Signal()
    enterGroup = Signal(object)  # node_id

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('propertyFloat')
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setModal(False)
        self.resize(420, 560)
        self._node_id = None
        self._drag = None
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.title_bar = QFrame()
        self.title_bar.setObjectName('propertyFloatTitle')
        title_layout = QHBoxLayout(self.title_bar)
        title_layout.setContentsMargins(12, 6, 6, 6)
        self.title = QLabel('属性')
        self.title.setObjectName('propertyFloatTitleLabel')
        title_layout.addWidget(self.title, 1)
        close = QPushButton('✕')
        close.setObjectName('propertyFloatClose')
        close.setFixedSize(26, 26)
        close.clicked.connect(self.close)
        title_layout.addWidget(close)
        root.addWidget(self.title_bar)
        self.body = QVBoxLayout()
        self.body.setContentsMargins(0, 0, 0, 0)
        body_wrap = QWidget()
        body_wrap.setObjectName('propertyFloatBody')
        body_wrap.setLayout(self.body)
        root.addWidget(body_wrap, 1)
        self.footer = QFrame()
        self.footer.setObjectName('propertyFloatFooter')
        foot = QHBoxLayout(self.footer)
        foot.setContentsMargins(10, 6, 10, 8)
        self.cont_btn = QPushButton('连续执行')
        self.exec_btn = QPushButton('执行')
        self.exec_btn.setObjectName('primaryButton')
        self.ok_btn = QPushButton('确定')
        self.cont_btn.clicked.connect(lambda: self.runModuleContinuous.emit(self._node_id))
        self.exec_btn.clicked.connect(lambda: self.runModule.emit(self._node_id))
        self.ok_btn.clicked.connect(self.close)
        foot.addWidget(self.cont_btn)
        foot.addStretch(1)
        foot.addWidget(self.exec_btn)
        foot.addWidget(self.ok_btn)
        root.addWidget(self.footer)
        self._panel = None
        self._source_form = None
        self.setStyleSheet(PROPERTY_FLOAT_QSS)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.title_bar.geometry().contains(event.position().toPoint()):
            self._drag = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag)
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag = None
        super().mouseReleaseEvent(event)

    def _clear_body(self):
        while self.body.count():
            item = self.body.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._panel = None
        self._source_form = None

    def show_source(self, config, title='0 图像源'):
        self._node_id = 'source'
        self._clear_body()
        self.title.setText(title)
        form = ImageSourceForm(config)
        form.changed.connect(self.sourceChanged.emit)
        form.openCameraManager.connect(self.openCameraManager.emit)
        form.paramAudited.connect(lambda p, o, n: self.paramAudited.emit('图像源1', p, o, n))
        self.body.addWidget(form)
        self._source_form = form
        self.show(); self.raise_(); self.activateWindow()

    def show_step(self, step, definition, project, index=1):
        self._node_id = step['id'] if step else None
        self._clear_body()
        name = (definition or {}).get('name') or (step or {}).get('name') or '模块'
        self.title.setText(f'{index} {name}')
        # B3: 组合模块专用四 Tab 面板
        if step and step.get('operation') == 'group':
            from desktop.group_module import GroupParamPanel, normalize_group_params
            step = deepcopy(step)
            step['params'] = normalize_group_params(step.get('params'))
            panel = GroupParamPanel(step, project)
            panel.changed.connect(self._on_step_changed)
            panel.enterGroup.connect(lambda: self.enterGroup.emit(self._node_id))
            self.body.addWidget(panel)
            self._panel = panel
            self._last_step = deepcopy(step)
            self.show(); self.raise_(); self.activateWindow()
            return
        # P1-9 / JGTech: 模板匹配定位 → VM 快速/灰度匹配四 Tab
        if step and step.get('operation') == 'locate':
            from desktop.locate_match_panel import LocateMatchPanel, normalize_locate_params
            step = deepcopy(step)
            step['params'] = normalize_locate_params(step.get('params'))
            panel = LocateMatchPanel(step, definition, project)
            panel.changed.connect(self._on_step_changed)
            self.body.addWidget(panel)
            self._panel = panel
            self._last_step = deepcopy(step)
            self.show(); self.raise_(); self.activateWindow()
            return
        # Wave2: 位置修正
        if step and step.get('operation') == 'pose_correct':
            from desktop.pose_correct_panel import PoseCorrectPanel, normalize_pose_correct_params
            step = deepcopy(step)
            step['params'] = normalize_pose_correct_params(step.get('params'))
            panel = PoseCorrectPanel(step, definition, project)
            panel.changed.connect(self._on_step_changed)
            self.body.addWidget(panel)
            self._panel = panel
            self._last_step = deepcopy(step)
            self.show(); self.raise_(); self.activateWindow()
            return
        # Wave2: 条件分支 / 分支模块 表
        if step and step.get('operation') in ('condition', 'branch'):
            from desktop.condition_branch_panel import (
                ConditionBranchPanel, normalize_condition_params, normalize_branch_params,
                sync_condition_flat,
            )
            step = deepcopy(step)
            if step.get('operation') == 'branch':
                step['params'] = normalize_branch_params(step.get('params'))
            else:
                step['params'] = normalize_condition_params(step.get('params'))
                sync_condition_flat(step['params'])
            panel = ConditionBranchPanel(step, definition, project)
            panel.changed.connect(self._on_step_changed)
            self.body.addWidget(panel)
            self._panel = panel
            self._last_step = deepcopy(step)
            self.show(); self.raise_(); self.activateWindow()
            return
        panel = ParameterPanel()
        panel.setStyleSheet(
            'QWidget#propertyPanel{background:#f0f0f0;border:0;}'
            'QLabel{color:#222222;}'
        )
        panel.set_step(step, definition, project)
        panel.changed.connect(self._on_step_changed)
        self.body.addWidget(panel)
        self._panel = panel
        self._last_step = deepcopy(step)
        self.show(); self.raise_(); self.activateWindow()

    def _on_step_changed(self, step):
        old = getattr(self, '_last_step', None) or {}
        old_params = old.get('params') or {}
        new_params = step.get('params') or {}
        module = step.get('name') or step.get('operation') or '模块'
        for key in set(old_params) | set(new_params):
            if old_params.get(key) != new_params.get(key):
                self.paramAudited.emit(module, key, old_params.get(key), new_params.get(key))
        if old.get('name') != step.get('name'):
            self.paramAudited.emit(module, 'name', old.get('name'), step.get('name'))
        if old.get('imageFrom') != step.get('imageFrom'):
            self.paramAudited.emit(module, 'imageFrom', old.get('imageFrom'), step.get('imageFrom'))
        self._last_step = deepcopy(step)
        self.changed.emit(step)
