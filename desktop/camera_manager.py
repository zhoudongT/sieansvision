"""相机管理 modal shell (VM IA) — wraps existing CameraDialog session without breaking GenTL/MV."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QListWidget,
    QListWidgetItem, QTabWidget, QWidget, QFormLayout, QComboBox, QSpinBox,
    QDialogButtonBox, QMessageBox, QSplitter, QInputDialog,
)

from desktop.widgets.switch import OrangeSwitch


class CameraManagerDialog(QDialog):
    """VM-aligned shell: 左设备列表(+) | 右 常用参数/设备控制 | 底 确定.

    Persistence and GenTL/MV session stay in the existing CameraDialog / backend;
    this dialog is an IA facade that can open the full camera workbench.
    """
    openFullWorkbench = Signal()
    acceptedDevice = Signal(str)

    def __init__(self, parent=None, devices=None):
        super().__init__(parent)
        self.setWindowTitle('相机管理')
        self.setObjectName('cameraManager')
        self.resize(780, 520)
        self.setModal(True)
        root = QVBoxLayout(self)
        head = QLabel('相机管理')
        head.setObjectName('dialogTitle')
        root.addWidget(head)
        hint = QLabel('设备列表与常用参数对齐 VisionMaster；连接与持久会话仍使用本机 GenTL/MV 采集后端。')
        hint.setObjectName('dialogHint')
        hint.setWordWrap(True)
        root.addWidget(hint)

        split = QSplitter(Qt.Orientation.Horizontal)
        left = QWidget()
        ll = QVBoxLayout(left)
        row = QHBoxLayout()
        row.addWidget(QLabel('设备列表'), 1)
        add = QPushButton('+')
        add.setFixedWidth(28)
        add.setToolTip('添加相机')
        add.clicked.connect(self._add_camera)
        row.addWidget(add)
        ll.addLayout(row)
        self.devices = QListWidget()
        for name in (devices or ['全局相机1']):
            self.devices.addItem(QListWidgetItem(name))
        if self.devices.count():
            self.devices.setCurrentRow(0)
        ll.addWidget(self.devices, 1)
        split.addWidget(left)

        right = QTabWidget()
        common = QWidget()
        form = QFormLayout(common)
        self.gentl = OrangeSwitch(True)
        form.addRow('GenTL相机', self.gentl)
        self.enum_mode = QComboBox()
        self.enum_mode.addItems(['枚举', '跨网段IP'])
        form.addRow('类型选择', self.enum_mode)
        self.camera_pick = QComboBox()
        self.camera_pick.addItem('Close', '')
        form.addRow('选择相机', self.camera_pick)
        self.connect_sw = OrangeSwitch(False)
        form.addRow('连接相机', self.connect_sw)
        self.reconnect = OrangeSwitch(True)
        form.addRow('自动重连', self.reconnect)
        self.cache = QSpinBox()
        self.cache.setRange(1, 200)
        self.cache.setValue(50)
        form.addRow('图像缓存数量', self.cache)
        self.reconnect_ms = QSpinBox()
        self.reconnect_ms.setRange(10, 60000)
        self.reconnect_ms.setValue(100)
        form.addRow('断线重连时间 (ms)', self.reconnect_ms)
        self.soft_timeout = QSpinBox()
        self.soft_timeout.setRange(0, 60)
        self.soft_timeout.setValue(2)
        form.addRow('软触发超时', self.soft_timeout)
        open_full = QPushButton('打开完整相机工作台（连接 / 会话 / 预览）…')
        open_full.setObjectName('primaryButton')
        open_full.clicked.connect(self.openFullWorkbench.emit)
        form.addRow(open_full)
        right.addTab(common, '常用参数')

        control = QWidget()
        cform = QFormLayout(control)
        self.cam_type = QComboBox()
        self.cam_type.addItems(['标准面阵相机', '智能相机', '线阵相机'])
        cform.addRow('相机类型', self.cam_type)
        self.level = QComboBox()
        self.level.addItems(['高电平有效', '低电平有效'])
        cform.addRow('有效电平', self.level)
        note = QLabel('图像参数 / 增益 / Gamma 在完整相机工作台中配置，避免与持久会话冲突。')
        note.setWordWrap(True)
        cform.addRow(note)
        right.addTab(control, '设备控制')
        split.addWidget(right)
        split.setSizes([220, 520])
        root.addWidget(split, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self._ok)
        root.addWidget(buttons)

    def _add_camera(self):
        kind, ok = QInputDialog.getItem(
            self, '请选择添加相机的类型', '类型',
            ['全局相机', 'Dalsa图像采集', '迈创采集'], 0, False)
        if not ok:
            return
        if kind != '全局相机':
            QMessageBox.information(self, '添加相机', f'{kind}入口已预留，当前硬件裁剪下请使用全局相机 / GenTL。')
            return
        n = self.devices.count() + 1
        self.devices.addItem(QListWidgetItem(f'{n} 全局相机{n}'))
        self.devices.setCurrentRow(self.devices.count() - 1)

    def _ok(self):
        item = self.devices.currentItem()
        if item:
            self.acceptedDevice.emit(item.text())
        self.accept()
