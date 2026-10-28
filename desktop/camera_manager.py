"""相机管理 — Soft / UVC / GenTL live preview (wave153–154 real camera path).

Enumerate → connect → persistent session → continuous live preview (PreviewFrameGate).
wave154: UVC VideoCapture real grab + GenTL producer open/grab into same preview path.
GenTL never fakes frames (empty device list when producer loaded but no camera).
"""
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
        self.setMinimumSize(640, 420)
        self.setModal(True)
        self._devices = []  # enumerated GenTL/UVC items
        self._session = {'state': 'idle'}
        self._provider_id = ''
        self._suppress_connect = False
        self._live_pending = False
        self._last_frame = None
        # wave152: UI throttle + drop-old coalesce for continuous soft preview
        try:
            from desktop.soft_acquisition_chrome import PreviewFrameGate, live_preview_ui_min_interval_ms
            self._preview_gate = PreviewFrameGate(live_preview_ui_min_interval_ms())
        except Exception:
            self._preview_gate = None
        self._gate_flush_timer = QTimer(self)
        self._gate_flush_timer.setSingleShot(True)
        self._gate_flush_timer.timeout.connect(self._flush_preview_gate)

        root = QVBoxLayout(self)
        head = QLabel('相机管理')
        head.setObjectName('dialogTitle')
        root.addWidget(head)
        hint = QLabel(
            'wave156：Soft / UVC / GenTL 连续 live · 曝光/增益/触发软控 · 多设备选择器 · 记忆上次设备 · 断线重连。'
            'UVC：VideoCapture 打开一次跨帧 grab；GenTL：CTI→枚举→开流（无相机空列表）。'
            '预览 PreviewFrameGate → ImageView.show_live_frame / 全局图像。'
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
        refresh.setToolTip('按当前采集后端重新枚举设备（Soft / UVC / GenTL）')
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
        # wave153: Soft vs UVC vs GenTL(placeholder) picker
        self.backend_kind = QComboBox()
        self.backend_kind.setObjectName('cameraBackendKind')
        try:
            from desktop.camera_backends import picker_choices
            for lab, kind in picker_choices():
                self.backend_kind.addItem(lab, kind)
            idx_uvc = self.backend_kind.findData('uvc')
            self.backend_kind.setCurrentIndex(idx_uvc if idx_uvc >= 0 else 0)
        except Exception:
            self.backend_kind.addItem('软模拟 Soft', 'soft')
            self.backend_kind.addItem('USB UVC', 'uvc')
            self.backend_kind.addItem('GenTL / GigE', 'gentl')
            self.backend_kind.setCurrentIndex(1)
        self.backend_kind.currentIndexChanged.connect(self._backend_kind_changed)
        form.addRow('采集后端', self.backend_kind)
        self.backend_status = QLabel('—')
        self.backend_status.setObjectName('dialogHint')
        self.backend_status.setWordWrap(True)
        form.addRow('后端状态', self.backend_status)
        # Keep gentl switch as hidden alias (legacy tests / bindings)
        self.gentl = OrangeSwitch(False)
        self.gentl.setVisible(False)
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
        self.exposure_us = QSpinBox()
        self.exposure_us.setObjectName('cameraExposureUs')
        self.exposure_us.setRange(100, 10_000_000)
        self.exposure_us.setValue(10000)
        self.exposure_us.setSuffix(' µs')
        self.exposure_us.setToolTip('软曝光：UVC 尝试 CAP_PROP_EXPOSURE；Soft 在预览帧上仿真')
        cform.addRow('曝光', self.exposure_us)
        self.gain_db = QSpinBox()
        self.gain_db.setObjectName('cameraGainDb')
        self.gain_db.setRange(0, 48)
        self.gain_db.setValue(0)
        self.gain_db.setSuffix(' dB')
        self.gain_db.setToolTip('软增益：UVC CAP_PROP_GAIN（若驱动允许）；Soft 仿真')
        cform.addRow('增益', self.gain_db)
        self.trigger_mode = QComboBox()
        self.trigger_mode.setObjectName('cameraTriggerMode')
        try:
            from desktop.camera_backends import TRIGGER_MODES
            for t in TRIGGER_MODES:
                self.trigger_mode.addItem(
                    {'freerun': '自由运行', 'software': '软触发', 'line0': 'Line0'}.get(t, t), t
                )
        except Exception:
            self.trigger_mode.addItem('自由运行', 'freerun')
            self.trigger_mode.addItem('软触发', 'software')
            self.trigger_mode.addItem('Line0', 'line0')
        cform.addRow('触发', self.trigger_mode)
        apply_btn = QPushButton('应用曝光/增益到会话')
        apply_btn.setObjectName('cameraApplySoftControls')
        apply_btn.setToolTip('对已打开的 UVC/Soft live 会话热更新；否则下次连接生效')
        apply_btn.clicked.connect(self._apply_soft_controls)
        cform.addRow(apply_btn)
        note = QLabel('后端允许时写入驱动；Soft 始终在预览帧仿真。完整工作台仍可调 Gamma 等高级项。')
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
        self._right_tabs = right
        right.currentChanged.connect(self._on_right_tab)

        split.addWidget(right)
        split.setSizes([220, 620])
        split.setStretchFactor(0, 0)
        split.setStretchFactor(1, 1)
        split.setChildrenCollapsible(False)
        left.setMinimumWidth(160)
        right.setMinimumWidth(360)
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
        self._refresh_backend_status()
        if not self.backend.is_ready:
            self.message.setText('原生引擎尚未就绪，无法枚举相机。请稍后重试或重启桌面端。')
            # Soft/UVC can still local-enumerate for UI
            if self._current_kind() in ('soft', 'uvc'):
                self._refresh_devices()
            return
        kind = self._current_kind()
        if kind == 'gentl' and not self._has('camera/providers'):
            self._request('camera/providers', {}, self._on_providers, kind='status')
        elif kind in ('soft', 'uvc'):
            self._refresh_devices()
        if not self._has('camera/session/status'):
            self._request('camera/session/status', {}, self._on_session, kind='status')

    def _current_kind(self) -> str:
        if hasattr(self, 'backend_kind'):
            return str(self.backend_kind.currentData() or 'uvc')
        return 'gentl' if self.gentl.isChecked() else 'uvc'

    def _backend_kind_changed(self, *_):
        kind = self._current_kind()
        self._suppress_connect = True
        try:
            self.gentl.setChecked(kind == 'gentl')
        finally:
            self._suppress_connect = False
        self._refresh_backend_status()
        self.provider.setEnabled(kind == 'gentl')
        self.provider.setVisible(kind == 'gentl')
        if kind == 'gentl':
            if self.backend.is_ready and not self._has('camera/providers'):
                self._request('camera/providers', {}, self._on_providers, kind='status')
            elif self.provider.currentData():
                self._refresh_devices()
        else:
            self._refresh_devices()
        self._buttons()

    def _refresh_backend_status(self):
        if not hasattr(self, 'backend_status'):
            return
        try:
            from desktop.camera_backends import get_backend
            avail = get_backend(self._current_kind()).availability()
            zh = avail.get('statusZh') or avail.get('status') or '—'
            st = avail.get('status') or ''
            self.backend_status.setText(f'[{st}] {zh}')
            if st in ('unsupported', 'not_loaded') and self._current_kind() == 'gentl':
                self.message.setText(zh)
        except Exception as exc:
            self.backend_status.setText(f'状态读取失败：{exc}')

    def _refresh_devices(self):
        kind = self._current_kind()
        if kind == 'soft':
            try:
                from desktop.camera_backends import SoftBackend
                items = SoftBackend().enumerate_local()
                self._on_list({'result': {'items': items, 'simulated': True}})
                self.message.setText('软模拟设备已列出（无需硬件）。')
            except Exception as exc:
                self.message.setText(f'软模拟枚举失败：{exc}')
            return
        if not self.backend.is_ready:
            if kind == 'uvc':
                try:
                    from desktop.camera_backends import UvcBackend, soft_fallback_devices
                    items = UvcBackend().enumerate_local()
                    if not items:
                        items = soft_fallback_devices()
                        self._on_list({'result': {'items': items, 'simulated': True}})
                        self.message.setText('引擎未就绪且无 UVC 设备 — 已软回退到模拟相机（CI-safe）。')
                    else:
                        self._on_list({'result': {'items': items}})
                        self.message.setText(f'引擎未就绪；本机 UVC 枚举到 {len(items)} 台（连接仍需引擎）。')
                except Exception as exc:
                    self.message.setText(f'引擎未就绪，无法枚举：{exc}')
            elif kind == 'gentl':
                try:
                    from desktop.camera_backends import GentlBackend, gentl_load_producer
                    load = gentl_load_producer()
                    items = GentlBackend().enumerate_local() if load.get('loaded') else []
                    self._on_list({'result': {'items': items}})
                    if load.get('loaded') and not items:
                        self.message.setText(
                            (load.get('statusZh') or 'Producer 已加载')
                            + ' — 未发现相机（诚实空列表，不伪造帧）。连接仍需引擎。'
                        )
                    elif items:
                        self.message.setText(
                            f"引擎未就绪；本机 GenTL 枚举到 {len(items)} 台（连接仍需引擎）。"
                        )
                    else:
                        self.message.setText(load.get('statusZh') or '引擎未就绪且 GenTL 未加载。')
                    self._refresh_backend_status()
                except Exception as exc:
                    self.message.setText(f'引擎未就绪，无法枚举 GenTL：{exc}')
            else:
                self.message.setText('引擎未就绪，无法枚举。')
            return
        try:
            from desktop.camera_backends import get_backend
            be = get_backend(kind)
            avail = be.availability()
            if kind == 'gentl' and not avail.get('available'):
                self._on_list({'result': {'items': []}})
                self.message.setText(avail.get('statusZh') or 'GenTL 未加载')
                self._refresh_backend_status()
                return
            provider = self.provider.currentData() or ''
            if kind == 'gentl' and not provider:
                self.message.setText('请先选择可用的 GenTL / SDK 驱动文件（CTI）。')
                return
            self.message.setText(f'正在枚举 {be.label()} 设备…')
            self._request('camera/list', be.list_rpc_params(provider_id=provider), self._on_list)
        except Exception:
            if kind == 'uvc':
                self._request('camera/list', {'driver': 'uvc'}, self._on_list)
            elif kind == 'gentl':
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
        # Auto-enumerate when GenTL kind + producer available
        if self._current_kind() == 'gentl' and self.provider.currentData():
            self._refresh_devices()
        self._refresh_backend_status()

    def _on_list(self, value):
        result = value.get('result', {}) if isinstance(value, dict) else {}
        self._devices = list(result.get('items') or [])
        current = self.camera_pick.currentData()
        self.camera_pick.blockSignals(True)
        self.camera_pick.clear()
        self.camera_pick.addItem('Close', '')
        kind = self._current_kind()
        try:
            from desktop.camera_backends import format_device_picker_label, load_last_device, pick_last_or_first
        except Exception:
            format_device_picker_label = None
            load_last_device = None
            pick_last_or_first = None
        for d in self._devices:
            if format_device_picker_label:
                label = format_device_picker_label(d, kind=kind)
            else:
                label = d.get('name') or d.get('deviceId') or '?'
                extra = d.get('serial') or d.get('model') or ''
                if extra:
                    label = f'{label} · {extra}'
            self.camera_pick.addItem(label, d.get('deviceId') or '')
        prefer = current
        if not prefer and load_last_device:
            last = load_last_device()
            if last.get('kind') == kind and last.get('deviceId'):
                prefer = last.get('deviceId')
        idx = self.camera_pick.findData(prefer) if prefer else -1
        if idx < 0 and self._devices:
            if pick_last_or_first:
                chosen = pick_last_or_first(self._devices, kind=kind)
                if chosen:
                    idx = self.camera_pick.findData(chosen.get('deviceId') or '')
            if idx < 0:
                idx = 1  # first real device (0 is Close)
        self.camera_pick.setCurrentIndex(max(0, idx))
        self.camera_pick.blockSignals(False)
        n = len(self._devices)
        if n:
            self.message.setText(
                f'枚举完成：{n} 台 · 后端 {kind}。选择相机后打开「连接相机」（已记忆上次设备）。'
            )
            # mirror into left list as selectable slots
            if self.devices.count() == 0:
                self.devices.addItem(QListWidgetItem('1 全局相机1'))
        else:
            sim = result.get('simulated')
            kind = self._current_kind()
            if kind == 'gentl':
                try:
                    from desktop.camera_backends import get_backend
                    zh = get_backend('gentl').availability().get('statusZh') or ''
                except Exception:
                    zh = ''
                self.message.setText(
                    (zh + ' — ') if zh else ''
                    + '未发现 GenTL 设备。请确认 CTI/Producer 与相机在线，且未被占用。'
                    + ('（当前为模拟驱动）' if sim else '')
                )
            elif kind == 'uvc':
                self.message.setText(
                    '未发现 UVC 设备。可插入 USB 摄像头后点刷新；无硬件时可选「软模拟 Soft」。'
                    + ('（当前为模拟驱动）' if sim else '')
                )
            else:
                self.message.setText(
                    '未发现设备。'
                    + ('（当前为模拟驱动）' if sim else '')
                )
        self._buttons()

    def _pick_changed(self):
        self._buttons()

    def _params(self):
        device_id = self.camera_pick.currentData() or ''
        kind = self._current_kind()
        exposure = int(self.exposure_us.value()) if hasattr(self, 'exposure_us') else 10000
        gain = float(self.gain_db.value()) if hasattr(self, 'gain_db') else 0.0
        trigger = 'freerun'
        try:
            trigger = self.trigger_mode.currentData() or 'freerun'
        except Exception:
            pass
        try:
            from desktop.camera_backends import get_backend, save_last_device, format_device_picker_label
            params = get_backend(kind).connect_params(
                device_id or ('synthetic-parts' if kind == 'soft' else '0'),
                provider_id=self.provider.currentData() or '',
                exposureUs=exposure,
                gainDb=gain,
                trigger=trigger,
            )
            if device_id:
                try:
                    lab = self.camera_pick.currentText() or device_id
                    save_last_device(kind=kind, device_id=device_id, label=lab,
                                     extra=dict(exposureUs=exposure, gainDb=gain, trigger=trigger))
                except Exception:
                    pass
            return params
        except Exception:
            if kind == 'gentl' or self.gentl.isChecked():
                return {
                    'driver': 'gentl',
                    'providerId': self.provider.currentData() or '',
                    'deviceId': device_id,
                    'timeoutMs': 5000,
                    'trigger': trigger,
                    'exposureUs': exposure,
                    'gainDb': gain,
                    'sessionPersist': True,
                }
            if kind == 'soft':
                return {
                    'driver': 'simulator',
                    'deviceId': device_id or 'synthetic-parts',
                    'timeoutMs': 5000,
                    'trigger': trigger,
                    'exposureUs': exposure,
                    'gainDb': gain,
                    'sessionPersist': True,
                }
            return {
                'driver': 'uvc',
                'deviceId': device_id or '0',
                'timeoutMs': 5000,
                'trigger': trigger,
                'exposureUs': exposure,
                'gainDb': gain,
                'sessionPersist': True,
            }

    def _apply_soft_controls(self):
        exposure = int(self.exposure_us.value()) if hasattr(self, 'exposure_us') else 10000
        gain = float(self.gain_db.value()) if hasattr(self, 'gain_db') else 0.0
        trigger = 'freerun'
        try:
            trigger = self.trigger_mode.currentData() or 'freerun'
        except Exception:
            pass
        live = getattr(self, '_uvc_live', None) or getattr(self, '_live_session', None)
        if live is not None and hasattr(live, 'set_soft_controls'):
            try:
                st = live.set_soft_controls(exposure_us=exposure, gain_db=gain, trigger=trigger)
                self.message.setText(
                    f"已应用软控 exposure={st.get('exposureUs')}µs gain={st.get('gainDb')}dB "
                    f"trigger={st.get('trigger')}"
                )
                return
            except Exception as exc:
                self.message.setText(f'软控应用失败：{exc}')
                return
        self.message.setText(
            f'软控已记录（下次连接生效）：exposure={exposure}µs gain={gain}dB trigger={trigger}'
        )


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
        if self._current_kind() == 'gentl' and not (self.provider.currentData() or ''):
            self._set_connect(False)
            try:
                from desktop.camera_backends import get_backend
                zh = get_backend('gentl').availability().get('statusZh') or ''
            except Exception:
                zh = ''
            self.message.setText(
                zh or '缺少 GenTL / SDK 驱动（CTI）。请安装 MVS 或设置 SIEANS_GENTL_CTI。'
            )
            return
        # Soft always has a device after enumerate; UVC needs a real pick
        if self._current_kind() == 'soft' and not device_id:
            # auto-pick synthetic
            pass
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
        # wave150: soft acquisition chrome densify on session strip
        try:
            from desktop.soft_acquisition_chrome import summarize_session, live_preview_interval_ms
            summ = summarize_session(state)
            chrome = summ.get('summary') or text
            self.preview_meta.setText(chrome)
            self.preview_meta.setToolTip(text)
            # Keep actionable status (含「已连接」) on message; chrome densify on preview_meta
            self.message.setText(text if (st == 'running' or err) else (chrome or text))
            want = live_preview_interval_ms(manager=True)
            if self._live_timer.interval() != want:
                self._live_timer.setInterval(want)
        except Exception:
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

    def _on_right_tab(self, _index=None):
        # Frames often arrive while Preview tab is hidden; Qt fitInView is then a no-op.
        if getattr(self, '_right_tabs', None) is None:
            return
        if self._right_tabs.tabText(self._right_tabs.currentIndex()) != '预览':
            return
        if hasattr(self.preview, 'fit_image'):
            QTimer.singleShot(0, self.preview.fit_image)

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
                self._paint_live_preview(image, frame)
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
                try:
                    from desktop.soft_acquisition_chrome import chrome_badge, is_soft_driver
                    from desktop.camera_backends import kind_of_driver
                    params = (self._session.get('config') or {}).get('params') or {}
                    soft = is_soft_driver(params.get('driver'))
                    bkind = params.get('backendKind') or kind_of_driver(
                        params.get('driver'), nested=self._session.get('config')
                    ) or self._current_kind()
                    badge = chrome_badge(
                        soft=soft, frame_seq=meta.get('frameSequence'), ready=True,
                        status='RUNNING', backend_kind=bkind, driver=params.get('driver'),
                    )
                    self.preview_meta.setText(f'{badge} · 预览 · ' + ' · '.join(bits))
                except Exception:
                    self.preview_meta.setText('预览 · ' + ' · '.join(bits))

        def wrap(value):
            try:
                done(value)
            finally:
                self._live_pending = False

        try:
            from desktop.soft_acquisition_chrome import live_capture_frame_policy
            policy = live_capture_frame_policy()
        except Exception:
            policy = 'latest'
        self._request(
            'camera/capture',
            {
                'driver': 'session',
                'sessionId': sid,
                'framePolicy': policy,
                'maxAgeMs': 3000,
                'timeoutMs': 2500,
            },
            wrap,
            kind='status',
        )


    def _paint_live_preview(self, image, frame=None):
        """wave152: gate + in-place preview paint (drop-old / UI throttle)."""
        gate = getattr(self, '_preview_gate', None)
        seq = None
        if isinstance(frame, dict):
            meta = frame.get('result') or frame
            seq = meta.get('frameSequence') if isinstance(meta, dict) else None
        paintable = image
        if gate is not None:
            paintable = gate.offer(image, seq=seq)
            if paintable is None:
                # Coalesced — schedule flush when min interval elapses
                if gate.has_pending() and hasattr(self, '_gate_flush_timer'):
                    ms = max(1, gate.ms_until_due())
                    if not self._gate_flush_timer.isActive():
                        self._gate_flush_timer.start(ms)
                return
        if hasattr(self.preview, 'show_live_frame'):
            self.preview.show_live_frame(paintable)
        else:
            self.preview.set_image(paintable)
        if hasattr(self.preview, 'fit_image') and self.preview.isVisible():
            if getattr(self.preview, '_needs_fit', False):
                self.preview.fit_image()

    def _flush_preview_gate(self):
        gate = getattr(self, '_preview_gate', None)
        if gate is None:
            return
        payload = gate.flush_due()
        if payload:
            if hasattr(self.preview, 'show_live_frame'):
                self.preview.show_live_frame(payload)
            else:
                self.preview.set_image(payload)
            if hasattr(self.preview, 'fit_image') and self.preview.isVisible():
                if getattr(self.preview, '_needs_fit', False):
                    self.preview.fit_image()
        elif gate.has_pending():
            ms = max(1, gate.ms_until_due())
            self._gate_flush_timer.start(ms)

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
        kind = self._current_kind()
        # Soft enumerate works without engine; connect still needs engine except soft-sim path messaging
        engine_needed = kind != 'soft'
        busy = self._busy() or (engine_needed and not self.backend.is_ready)
        has_device = bool(self.camera_pick.currentData())
        running = self._session.get('state') == 'running'
        self.camera_pick.setEnabled(not busy and not running)
        if hasattr(self, 'backend_kind'):
            self.backend_kind.setEnabled(not busy and not running)
        self.provider.setEnabled(not busy and not running and kind == 'gentl')
        self.provider.setVisible(kind == 'gentl')
        self.gentl.setEnabled(False)  # hidden alias; kind combo is source of truth
        # connect switch stays enabled so user can disconnect while running
        soft_ok = kind == 'soft' and has_device
        self.connect_sw.setEnabled(
            (not busy and (has_device or running or self.connect_sw.isChecked()))
            or (soft_ok and not running)
            or running
        )
