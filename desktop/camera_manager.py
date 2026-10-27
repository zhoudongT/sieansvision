"""相机管理 — VM IA shell wired to real GenTL/MV session (enumerate → connect → preview)."""
from __future__ import annotations

from copy import deepcopy

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QDialogButtonBox, QFormLayout, QHBoxLayout, QInputDialog, QLabel,
    QListWidget, QListWidgetItem, QMessageBox, QPushButton, QComboBox,
    QSpinBox, QSplitter, QTabWidget, QVBoxLayout, QWidget,
)

from desktop.device_dialogs import _RpcDialog, _Preview
from desktop.widgets.switch import OrangeSwitch


class CameraManagerDialog(_RpcDialog):
    """VM-aligned: 左设备列表 | 右 常用参数/设备控制 | 连接开关驱动真实会话.

    Persistence and GenTL/MV stay in the existing session backend; this dialog
    is the short path Allen uses from 图像源 / 工具栏「相机」.
    """
    openFullWorkbench = Signal()
    acceptedDevice = Signal(str)
    # Full gentl/uvc params dict for binding 图像源 / camera_capture
    deviceParams = Signal(dict)
    frame_ready = Signal(dict)

    def __init__(self, backend, parent=None, devices=None):
        super().__init__(backend, parent)
        self.setWindowTitle('相机管理')
        self.setObjectName('cameraManager')
        self.resize(860, 560)
        self.setModal(True)
        self._devices = []  # enumerated GenTL/UVC items
        self._session = {'state': 'idle'}
        self._provider_id = ''
        self._suppress_connect = False
        self._live_pending = False
        self._last_frame = None

        root = QVBoxLayout(self)
        head = QLabel('相机管理')
        head.setObjectName('dialogTitle')
        root.addWidget(head)
        hint = QLabel(
            '设备列表与「连接相机」对齐 VisionMaster：枚举 GenTL/SDK → 选择设备 → 打开连接；'
            '成功后预览帧进入「全局图像」。完整参数/3D 请用下方「完整相机工作台」。'
        )
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
        add.setToolTip('添加相机槽位')
        add.clicked.connect(self._add_camera)
        row.addWidget(add)
        refresh = QPushButton('刷新')
        refresh.setToolTip('重新枚举 GenTL 设备')
        refresh.clicked.connect(self._refresh_devices)
        row.addWidget(refresh)
        ll.addLayout(row)
        self.devices = QListWidget()
        for name in (devices or ['1 全局相机1']):
            self.devices.addItem(QListWidgetItem(name))
        if self.devices.count():
            self.devices.setCurrentRow(0)
        self.devices.currentRowChanged.connect(lambda *_: self._buttons())
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
        self.provider = QComboBox()
        self.provider.addItem('（加载中…）', '')
        form.addRow('GenTL / SDK 驱动', self.provider)
        self.camera_pick = QComboBox()
        self.camera_pick.addItem('Close', '')
        self.camera_pick.currentIndexChanged.connect(self._pick_changed)
        form.addRow('选择相机', self.camera_pick)
        self.connect_sw = OrangeSwitch(False)
        self.connect_sw.toggled.connect(self._on_connect_toggled)
        form.addRow('连接相机', self.connect_sw)
        self.reconnect = OrangeSwitch(True)
        form.addRow('自动重连', self.reconnect)
        self.cache = QSpinBox()
        self.cache.setRange(1, 200)
        self.cache.setValue(50)
        form.addRow('图像缓存数量', self.cache)
        self.reconnect_ms = QSpinBox()
        self.reconnect_ms.setRange(10, 60000)
        self.reconnect_ms.setValue(1000)
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
        note = QLabel('曝光 / 增益 / Gamma 与触发源在完整相机工作台「采集参数」中配置，避免与持久会话冲突。')
        note.setWordWrap(True)
        cform.addRow(note)
        right.addTab(control, '设备控制')

        preview_page = QWidget()
        pv = QVBoxLayout(preview_page)
        self.preview = _Preview()
        pv.addWidget(self.preview, 1)
        self.preview_meta = QLabel('未连接')
        self.preview_meta.setWordWrap(True)
        pv.addWidget(self.preview_meta)
        grab = QPushButton('取最新缓存帧 → 全局图像')
        grab.clicked.connect(self._push_frame)
        pv.addWidget(grab)
        right.addTab(preview_page, '预览')

        split.addWidget(right)
        split.setSizes([220, 620])
        root.addWidget(split, 1)

        root.addWidget(self.message)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._ok)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        self._status_timer = QTimer(self)
        self._status_timer.setInterval(800)
        self._status_timer.timeout.connect(self._poll_status)
        self._live_timer = QTimer(self)
        self._live_timer.setInterval(120)
        self._live_timer.timeout.connect(self._live_tick)

    # ----- lifecycle -----
    def showEvent(self, event):
        super().showEvent(event)
        self._status_timer.start()
        if self.backend.is_ready:
            self.refresh()

    def hideEvent(self, event):
        self._status_timer.stop()
        self._live_timer.stop()
        super().hideEvent(event)

    def refresh(self):
        if not self.backend.is_ready:
            self.message.setText('原生引擎尚未就绪，无法枚举相机。请稍后重试或重启桌面端。')
            return
        if not self._has('camera/providers'):
            self._request('camera/providers', {}, self._on_providers, kind='status')
        if not self._has('camera/session/status'):
            self._request('camera/session/status', {}, self._on_session, kind='status')

    def _refresh_devices(self):
        if not self.backend.is_ready:
            self.message.setText('引擎未就绪，无法枚举。')
            return
        if not self.gentl.isChecked():
            # UVC fallback enumerate
            self._request('camera/list', {'driver': 'uvc'}, self._on_list)
            return
        provider = self.provider.currentData() or ''
        if not provider:
            self.message.setText('请先选择可用的 GenTL / SDK 驱动文件（CTI）。')
            return
        self.message.setText('正在枚举 GenTL 设备…')
        self._request('camera/list', {'driver': 'gentl', 'providerId': provider}, self._on_list)

    def _on_providers(self, value):
        info = value.get('result', {}) if isinstance(value, dict) else {}
        old = self.provider.currentData()
        self.provider.blockSignals(True)
        self.provider.clear()
        items = info.get('items') or []
        if not items:
            self.provider.addItem('（无 GenTL 驱动）', '')
        for item in items:
            label = item.get('name') or item.get('id') or '?'
            if not item.get('available'):
                label += '（文件不存在）'
            self.provider.addItem(label, item.get('id') or '')
        idx = self.provider.findData(old) if old else -1
        if idx < 0:
            idx = next((i for i in range(self.provider.count())
                        if (items[i].get('available') if i < len(items) else False)), 0)
        self.provider.setCurrentIndex(max(0, idx))
        self.provider.blockSignals(False)
        harv = '是' if info.get('harvesters') else '否'
        self.message.setText(
            f"GenTL 驱动 {self.provider.count()} 项 · harvesters={harv} · "
            f"RealSense={info.get('realsense') or '未装'} · Orbbec={info.get('orbbec') or '未装'}"
        )
        # Auto-enumerate when a producer is available
        if self.provider.currentData():
            self._refresh_devices()

    def _on_list(self, value):
        result = value.get('result', {}) if isinstance(value, dict) else {}
        self._devices = list(result.get('items') or [])
        current = self.camera_pick.currentData()
        self.camera_pick.blockSignals(True)
        self.camera_pick.clear()
        self.camera_pick.addItem('Close', '')
        for d in self._devices:
            label = d.get('name') or d.get('deviceId') or '?'
            extra = d.get('serial') or d.get('model') or ''
            if extra:
                label = f'{label} · {extra}'
            self.camera_pick.addItem(label, d.get('deviceId') or '')
        idx = self.camera_pick.findData(current) if current else -1
        if idx < 0 and self._devices:
            idx = 1  # first real device (0 is Close)
        self.camera_pick.setCurrentIndex(max(0, idx))
        self.camera_pick.blockSignals(False)
        n = len(self._devices)
        if n:
            self.message.setText(f'枚举完成：{n} 台。选择相机后打开「连接相机」。')
            # mirror into left list as selectable slots
            if self.devices.count() == 0:
                self.devices.addItem(QListWidgetItem('1 全局相机1'))
        else:
            sim = result.get('simulated')
            self.message.setText(
                '未发现设备。请确认 MV-CB013 USB 已插入、MVS/CTI 可用，且未被其它程序占用。'
                + ('（当前为模拟驱动）' if sim else '')
            )
        self._buttons()

    def _pick_changed(self):
        self._buttons()

    def _params(self):
        device_id = self.camera_pick.currentData() or ''
        if self.gentl.isChecked():
            return {
                'driver': 'gentl',
                'providerId': self.provider.currentData() or '',
                'deviceId': device_id,
                'timeoutMs': 5000,
                'trigger': 'freerun',
            }
        return {
            'driver': 'uvc',
            'deviceId': device_id or '0',
            'timeoutMs': 5000,
            'trigger': 'freerun',
        }

    def _on_connect_toggled(self, on):
        if self._suppress_connect:
            return
        if on:
            self._start_connect()
        else:
            self._stop_connect()

    def _start_connect(self):
        if not self.backend.is_ready:
            self._set_connect(False)
            self.message.setText('引擎未就绪，无法连接相机。')
            return
        device_id = self.camera_pick.currentData() or ''
        if not device_id:
            self._set_connect(False)
            self.message.setText('请先在「选择相机」中选中一台设备（不要选 Close）。')
            return
        if self.gentl.isChecked() and not (self.provider.currentData() or ''):
            self._set_connect(False)
            self.message.setText('缺少 GenTL / SDK 驱动（CTI）。请安装 MVS 或设置 SIEANS_GENTL_CTI。')
            return
        params = self._params()
        attempts = 2 if self.reconnect.isChecked() else 0
        body = dict(
            params=params,
            intervalMs=100,
            reconnectAttempts=attempts,
            reconnectMs=int(self.reconnect_ms.value()),
            autoStart=False,
        )
        self.message.setText(f"正在连接 {params.get('deviceId')} …")
        self._request('camera/session/start', body, self._on_session)

    def _stop_connect(self):
        if not self.backend.is_ready:
            return
        sid = self._session.get('id')
        self.message.setText('正在停止并释放设备…')
        self._request('camera/session/stop', {'id': sid} if sid else {}, self._on_session)

    def _on_session(self, state):
        if not isinstance(state, dict):
            return
        # engine may wrap in result
        if 'state' not in state and isinstance(state.get('result'), dict):
            state = state['result']
        self._session = state
        st = state.get('state') or 'idle'
        err = state.get('error') or ''
        labels = {
            'idle': '未连接',
            'opening': '正在打开设备',
            'running': '已连接 · 持续采集中',
            'reconnecting': '正在重连',
            'stopping': '正在释放设备',
            'stopped': '已停止',
            'failed': '连接失败',
            'interrupted': '应用中断，需手动重连',
        }
        text = labels.get(st, st)
        if err:
            text += ' · ' + str(err)[:300]
        self.preview_meta.setText(text)
        self.message.setText(text)
        active = st in ('opening', 'running', 'reconnecting')
        self._set_connect(active or st == 'running')
        if st == 'running':
            if not self._live_timer.isActive():
                self._live_timer.start()
            # Push device params so 图像源 can bind
            cfg = (state.get('config') or {}).get('params') or self._params()
            self.deviceParams.emit(deepcopy(cfg))
        else:
            self._live_timer.stop()
            self._live_pending = False
            if st == 'failed':
                self._set_connect(False)
        self._buttons()

    def _set_connect(self, on):
        self._suppress_connect = True
        self.connect_sw.setChecked(bool(on))
        self._suppress_connect = False

    def _poll_status(self):
        if self.backend.is_ready and not self._has('camera/session/status'):
            self._request('camera/session/status', {}, self._on_session, kind='status')

    def _live_tick(self):
        if self._live_pending or not self.backend.is_ready:
            return
        if self._session.get('state') != 'running':
            return
        if any(m == 'camera/capture' for m, _, _ in self.pending.values()):
            return
        self._live_pending = True
        sid = self._session.get('id')

        def done(value):
            self._live_pending = False
            data = value.get('result', value) if isinstance(value, dict) else value
            # camera/capture returns {annotatedImage, result, ...} at top level from engine
            frame = value if isinstance(value, dict) else {}
            image = frame.get('annotatedImage') or frame.get('image') or ''
            if not image and isinstance(frame.get('result'), dict):
                # unlikely
                pass
            if image:
                self._last_frame = deepcopy(frame)
                self.preview.set_image(image)
                meta = frame.get('result') or {}
                w = meta.get('width') or meta.get('Width')
                h = meta.get('height') or meta.get('Height')
                age = meta.get('frameAgeMs')
                bits = []
                if w and h:
                    bits.append(f'{w}×{h}')
                if age is not None:
                    bits.append(f'龄 {age} ms')
                bits.append(f"帧 #{meta.get('frameSequence', '—')}")
                self.preview_meta.setText('预览 · ' + ' · '.join(bits))

        def wrap(value):
            try:
                done(value)
            finally:
                self._live_pending = False

        self._request(
            'camera/capture',
            {
                'driver': 'session',
                'sessionId': sid,
                'framePolicy': 'latest',
                'maxAgeMs': 3000,
                'timeoutMs': 2500,
            },
            wrap,
            kind='status',
        )

    def _push_frame(self):
        if self._last_frame and (
            self._last_frame.get('annotatedImage') or self._last_frame.get('image')
        ):
            self.frame_ready.emit(deepcopy(self._last_frame))
            self.message.setText('已将最新预览帧送入全局图像。')
            return
        if self._session.get('state') != 'running':
            self.message.setText('请先打开「连接相机」，等待预览出现后再取帧。')
            return
        sid = self._session.get('id')

        def done(value):
            frame = value if isinstance(value, dict) else {}
            if frame.get('annotatedImage') or frame.get('image'):
                self._last_frame = deepcopy(frame)
                self.preview.set_image(frame.get('annotatedImage') or frame.get('image') or '')
                self.frame_ready.emit(deepcopy(frame))
                self.message.setText('已将最新缓存帧送入全局图像。')
            else:
                self.message.setText('会话尚无有效图像，请稍候再试。')

        self._request(
            'camera/capture',
            {
                'driver': 'session',
                'sessionId': sid,
                'framePolicy': 'latest',
                'maxAgeMs': 5000,
                'timeoutMs': 5000,
            },
            done,
        )

    def _add_camera(self):
        kind, ok = QInputDialog.getItem(
            self, '请选择添加相机的类型', '类型',
            ['全局相机', 'Dalsa图像采集', '迈创采集'], 0, False)
        if not ok:
            return
        if kind != '全局相机':
            QMessageBox.information(
                self, '添加相机',
                f'{kind}入口已预留，当前请使用全局相机 / GenTL（海康 MVS SDK）。')
            return
        n = self.devices.count() + 1
        self.devices.addItem(QListWidgetItem(f'{n} 全局相机{n}'))
        self.devices.setCurrentRow(self.devices.count() - 1)

    def _ok(self):
        item = self.devices.currentItem()
        name = item.text() if item else '全局相机1'
        device_id = self.camera_pick.currentData() or ''
        if device_id:
            name = f'{name} · {device_id}'
        self.acceptedDevice.emit(name)
        params = self._params()
        if device_id:
            self.deviceParams.emit(deepcopy(params))
        if self._last_frame and (
            self._last_frame.get('annotatedImage') or self._last_frame.get('image')
        ):
            self.frame_ready.emit(deepcopy(self._last_frame))
        self.accept()

    def _buttons(self):
        busy = self._busy() or not self.backend.is_ready
        has_device = bool(self.camera_pick.currentData())
        running = self._session.get('state') == 'running'
        self.camera_pick.setEnabled(not busy and not running)
        self.provider.setEnabled(not busy and not running and self.gentl.isChecked())
        self.gentl.setEnabled(not busy and not running)
        # connect switch stays enabled so user can disconnect while running
        self.connect_sw.setEnabled(not busy and (has_device or running or self.connect_sw.isChecked()))
