"""Unified「图像源」node properties (本地图像 / 相机 / SDK)."""
from copy import deepcopy

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QComboBox, QSpinBox, QDoubleSpinBox,
    QLabel, QGroupBox, QHBoxLayout, QPushButton, QLineEdit, QScrollArea,
)

from desktop.widgets.switch import OrangeSwitch


DEFAULT_SOURCE = dict(
    mode='local',  # local | camera | sdk
    pixelFormat='RGB24',
    intervalMs=0,
    saveInSolution=False,
    showImageName=True,
    snStart=0,
    imageCache=0,
    outputMono8=False,
    stitchEnable=False,
    stitchStartY=0,
    stitchHeight=0,
    stitchClearOnTrigger=False,
    autoSwitch=False,
    stopAtLast=False,
    charFilterEnable=False,
    inputChar='',
    triggerChar='',
    cameraId='',
    cameraParams={},
    exposure=0.0,
    gain=0.0,
    images=[],
    currentIndex=0,
    imageFormatFilter='全部',
)


def normalize_source(config=None):
    value = deepcopy(DEFAULT_SOURCE)
    if isinstance(config, dict):
        value.update({k: deepcopy(v) for k, v in config.items() if k in value or k in DEFAULT_SOURCE})
        for k, v in config.items():
            if k not in value:
                value[k] = deepcopy(v)
    return value


def _row_switch(form, label, checked, on_toggle):
    sw = OrangeSwitch(checked)
    sw.toggled.connect(on_toggle)
    form.addRow(label, sw)
    return sw


def _spin(form, label, value, lo, hi, on_change, bind=True):
    box = QHBoxLayout()
    spin = QSpinBox()
    spin.setRange(lo, hi)
    spin.setValue(int(value))
    spin.setKeyboardTracking(False)
    spin.valueChanged.connect(on_change)
    box.addWidget(spin, 1)
    if bind:
        btn = QPushButton('⛓')
        btn.setObjectName('bindButton')
        btn.setFixedWidth(28)
        btn.setToolTip('绑定变量（P1）')
        btn.setEnabled(False)
        box.addWidget(btn)
    wrap = QWidget()
    wrap.setLayout(box)
    form.addRow(label, wrap)
    return spin


def _dspin(form, label, value, lo, hi, on_change):
    box = QHBoxLayout()
    spin = QDoubleSpinBox()
    spin.setDecimals(3)
    spin.setRange(lo, hi)
    spin.setValue(float(value or 0))
    spin.setKeyboardTracking(False)
    spin.valueChanged.connect(on_change)
    box.addWidget(spin, 1)
    btn = QPushButton('⛓')
    btn.setObjectName('bindButton')
    btn.setFixedWidth(28)
    btn.setToolTip('绑定变量（P1）')
    btn.setEnabled(False)
    box.addWidget(btn)
    wrap = QWidget()
    wrap.setLayout(box)
    form.addRow(label, wrap)
    return spin


class ImageSourceForm(QWidget):
    """Light-panel friendly form for the canvas「图像源」node."""
    changed = Signal(dict)
    openCameraManager = Signal()
    paramAudited = Signal(str, object, object)  # param, old, new

    def __init__(self, config=None, parent=None):
        super().__init__(parent)
        self.setObjectName('imageSourceForm')
        self._cfg = normalize_source(config)
        self._building = False
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(scroll.frameShape().NoFrame)
        content = QWidget()
        self.root = QVBoxLayout(content)
        self.root.setContentsMargins(8, 8, 8, 8)
        self.root.setSpacing(10)
        scroll.setWidget(content)
        outer.addWidget(scroll)
        self._build()

    def config(self):
        return deepcopy(self._cfg)

    def set_config(self, config):
        self._cfg = normalize_source(config)
        self._build()

    def _audit(self, key, new):
        old = self._cfg.get(key)
        if old == new and type(old) is type(new):
            return
        self._cfg[key] = deepcopy(new)
        self.paramAudited.emit(key, old, new)
        if not self._building:
            self.changed.emit(self.config())
            if key in ('mode', 'cameraId', 'images'):
                self._refresh_cfg_warn()

    def _build(self):
        self._building = True
        while self.root.count():
            item = self.root.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                pass
        cfg = self._cfg

        self._cfg_warn = QLabel()
        self._cfg_warn.setObjectName('incompleteBanner')
        self._cfg_warn.setWordWrap(True)
        self.root.addWidget(self._cfg_warn)
        self._refresh_cfg_warn()

        # wave150: soft acquisition operator chrome (industrial density strip)
        self._acq_chrome = QLabel()
        self._acq_chrome.setObjectName('softAcquisitionChrome')
        self._acq_chrome.setWordWrap(True)
        self._acq_chrome.setTextFormat(Qt.TextFormat.RichText)
        self.root.addWidget(self._acq_chrome)
        self._refresh_acq_chrome()

        basic = QGroupBox('基本参数')
        basic.setObjectName('propertySection')
        form = QFormLayout(basic)
        form.setSpacing(10)
        self.mode = QComboBox()
        for label, value in (('本地图像', 'local'), ('相机', 'camera'), ('SDK', 'sdk')):
            self.mode.addItem(label, value)
        self.mode.setCurrentIndex(max(0, self.mode.findData(cfg['mode'])))
        self.mode.currentIndexChanged.connect(lambda: self._on_mode())
        form.addRow('图像源', self.mode)

        self.pixel = QComboBox()
        self.pixel.addItem('MONO8', 'MONO8')
        self.pixel.addItem('RGB24', 'RGB24')
        self.pixel.setCurrentIndex(max(0, self.pixel.findData(cfg.get('pixelFormat', 'RGB24'))))
        self.pixel.currentIndexChanged.connect(
            lambda: self._audit('pixelFormat', self.pixel.currentData()))
        form.addRow('像素格式', self.pixel)

        # wave152: continuous soft preview pacing — 0 = 跟随 LIVE_PREVIEW_POLICY
        spin_iv = _spin(form, '取图间隔', cfg.get('intervalMs', 0), 0, 60000,
              lambda v: self._audit('intervalMs', int(v)))
        try:
            from desktop.soft_acquisition_chrome import live_preview_interval_ms, live_preview_ui_min_interval_ms
            spin_iv.setToolTip(
                f'连续软预览节拍(ms)。0=跟随策略({live_preview_interval_ms()}ms拉取 / '
                f'UI≥{live_preview_ui_min_interval_ms()}ms·丢旧帧)。'
            )
        except Exception:
            spin_iv.setToolTip('连续取图间隔(ms)；0 表示跟随默认预览策略')
        self.fmt_filter = QComboBox()
        for lab in ('全部', '.bmp', '.jpg', '.png', '.tif'):
            self.fmt_filter.addItem(lab, lab)
        cur_fmt = cfg.get('imageFormatFilter') or '全部'
        self.fmt_filter.setCurrentIndex(max(0, self.fmt_filter.findData(cur_fmt)))
        self.fmt_filter.currentIndexChanged.connect(
            lambda: self._audit('imageFormatFilter', self.fmt_filter.currentData() or '全部'))
        self.fmt_filter.setToolTip('与胶片条格式过滤双向对齐')
        form.addRow('胶片格式过滤', self.fmt_filter)
        _row_switch(form, '方案存图', cfg.get('saveInSolution', False),
                    lambda v: self._audit('saveInSolution', v))
        _row_switch(form, '显示图像名称', cfg.get('showImageName', True),
                    lambda v: self._audit('showImageName', v))
        _spin(form, 'SN初始值', cfg.get('snStart', 0), 0, 999999,
              lambda v: self._audit('snStart', int(v)))
        _spin(form, '图片缓存', cfg.get('imageCache', 0), 0, 120,
              lambda v: self._audit('imageCache', int(v)))
        _row_switch(form, '输出Mono8', cfg.get('outputMono8', False),
                    lambda v: self._audit('outputMono8', v))

        self.stitch = OrangeSwitch(cfg.get('stitchEnable', False))
        form.addRow('拼接使能', self.stitch)
        self.stitch_box = QWidget()
        stitch_form = QFormLayout(self.stitch_box)
        stitch_form.setContentsMargins(0, 0, 0, 0)
        _spin(stitch_form, '起始高度', cfg.get('stitchStartY', 0), 0, 100000,
              lambda v: self._audit('stitchStartY', int(v)), bind=False)
        _spin(stitch_form, '拼接高度', cfg.get('stitchHeight', 0), 0, 100000,
              lambda v: self._audit('stitchHeight', int(v)), bind=False)
        _row_switch(stitch_form, '触发清空', cfg.get('stitchClearOnTrigger', False),
                    lambda v: self._audit('stitchClearOnTrigger', v))
        form.addRow(self.stitch_box)
        self.stitch.toggled.connect(self._on_stitch)
        self.stitch_box.setVisible(bool(cfg.get('stitchEnable')))

        # camera-only
        self.camera_box = QGroupBox('相机')
        self.camera_box.setObjectName('propertySection')
        cam_form = QFormLayout(self.camera_box)
        cam_row = QHBoxLayout()
        self.camera_combo = QComboBox()
        self.camera_combo.addItem('请选择', '')
        if cfg.get('cameraId'):
            self.camera_combo.addItem(str(cfg['cameraId']), cfg['cameraId'])
            self.camera_combo.setCurrentIndex(self.camera_combo.count() - 1)
        cam_row.addWidget(self.camera_combo, 1)
        cam_btn = QPushButton('📷')
        cam_btn.setToolTip('打开相机管理')
        cam_btn.setFixedWidth(32)
        cam_btn.clicked.connect(self.openCameraManager.emit)
        cam_row.addWidget(cam_btn)
        cam_wrap = QWidget()
        cam_wrap.setLayout(cam_row)
        cam_form.addRow('关联相机', cam_wrap)
        self.camera_combo.currentIndexChanged.connect(
            lambda: self._audit('cameraId', self.camera_combo.currentData() or ''))
        _dspin(cam_form, '控制曝光', cfg.get('exposure', 0.0), 0, 1e9,
               lambda v: self._audit('exposure', float(v)))
        _dspin(cam_form, '控制增益', cfg.get('gain', 0.0), 0, 1e6,
               lambda v: self._audit('gain', float(v)))

        # sdk — GenTL / 厂商 SDK 取图（对齐 VM 课「SDK取图」主路径：连接会话 → 全局图像）
        self.sdk_box = QGroupBox('SDK 取图')
        self.sdk_box.setObjectName('propertySection')
        sdk_layout = QVBoxLayout(self.sdk_box)
        note = QLabel(
            '通过本机 GenTL / 海康 MVS SDK 连接工业相机并取图。'
            '请点下方按钮打开「相机管理」：枚举 → 选择相机 → 打开「连接相机」；'
            '预览帧进入「全局图像」后即可运行流程。'
        )
        note.setWordWrap(True)
        sdk_layout.addWidget(note)
        sdk_row = QHBoxLayout()
        self.sdk_camera = QComboBox()
        self.sdk_camera.addItem('请先在相机管理中连接', '')
        if cfg.get('cameraId'):
            self.sdk_camera.addItem(str(cfg['cameraId']), cfg['cameraId'])
            self.sdk_camera.setCurrentIndex(self.sdk_camera.count() - 1)
        sdk_row.addWidget(self.sdk_camera, 1)
        sdk_btn = QPushButton('📷 相机管理 / SDK 连接…')
        sdk_btn.setObjectName('primaryButton')
        sdk_btn.clicked.connect(self.openCameraManager.emit)
        sdk_row.addWidget(sdk_btn)
        sdk_wrap = QWidget()
        sdk_wrap.setLayout(sdk_row)
        sdk_layout.addWidget(sdk_wrap)
        self.sdk_camera.currentIndexChanged.connect(
            lambda: self._audit('cameraId', self.sdk_camera.currentData() or ''))
        tip = QLabel('外部进程 SyncRun 注入仍为后续扩展；当前主路径为 GenTL 会话取图。')
        tip.setWordWrap(True)
        tip.setObjectName('dialogHint')
        sdk_layout.addWidget(tip)

        trigger = QGroupBox('触发设置')
        trigger.setObjectName('propertySection')
        tform = QFormLayout(trigger)
        _row_switch(tform, '自动切换', cfg.get('autoSwitch', False),
                    lambda v: self._audit('autoSwitch', v))
        _row_switch(tform, '最后一张停止', cfg.get('stopAtLast', False),
                    lambda v: self._audit('stopAtLast', v))
        self.char_filter = OrangeSwitch(cfg.get('charFilterEnable', False))
        tform.addRow('字符触发过滤', self.char_filter)
        self.char_box = QWidget()
        cform = QFormLayout(self.char_box)
        cform.setContentsMargins(0, 0, 0, 0)
        inp = QLineEdit(cfg.get('inputChar', ''))
        inp.editingFinished.connect(lambda: self._audit('inputChar', inp.text()))
        cform.addRow('输入字符', inp)
        trg = QLineEdit(cfg.get('triggerChar', ''))
        trg.editingFinished.connect(lambda: self._audit('triggerChar', trg.text()))
        cform.addRow('触发字符', trg)
        tform.addRow(self.char_box)
        self.char_filter.toggled.connect(self._on_char)
        self.char_box.setVisible(bool(cfg.get('charFilterEnable')))

        self.root.addWidget(basic)
        self.root.addWidget(self.camera_box)
        self.root.addWidget(self.sdk_box)
        self.root.addWidget(trigger)
        self.root.addStretch(1)
        self._apply_mode_visibility()
        self._building = False

    def _refresh_acq_chrome(self, session=None):
        """wave150: densify soft camera / ImageSource acquisition chrome strip."""
        if not hasattr(self, '_acq_chrome') or self._acq_chrome is None:
            return
        try:
            from desktop.soft_acquisition_chrome import source_chrome_strip, html_session_strip, summarize_session
            strip = source_chrome_strip(self._cfg or {}, session=session)
            # Prefer HTML session strip when a live session is provided; else source strip summary.
            if session:
                html = html_session_strip(summarize_session(session, params=(self._cfg or {}).get('cameraParams') or {}))
            else:
                html = strip.get('html') or ''
                if not html:
                    html = (
                        f"<div style='background:#1e2430;color:#d7dde8;padding:6px 8px;"
                        f"border-radius:4px;font-size:12px'>{strip.get('summary') or '采·'}</div>"
                    )
            self._acq_chrome.setText(html)
            self._acq_chrome.setToolTip(strip.get('summary') or '软采集铬')
            self._acq_chrome.setVisible(True)
        except Exception as exc:  # pragma: no cover
            self._acq_chrome.setText(f'采· （铬暂不可用：{exc}）')

    def _refresh_cfg_warn(self):
        """Update incomplete banner without rebuilding the form (mode RT while float open)."""
        if not hasattr(self, '_cfg_warn') or self._cfg_warn is None:
            return
        from desktop.config_status import source_incomplete_reason
        cfg = self._cfg or {}
        why = source_incomplete_reason(cfg)
        if why:
            tip = '⚠ 组件参数未配置完整：' + why
            self._cfg_warn.setText(tip)
            self._cfg_warn.setStyleSheet('color:#c62828;background:#ffebee;padding:6px 8px;border-radius:3px;')
        else:
            self._cfg_warn.setText('组件配置完成')
            self._cfg_warn.setStyleSheet('color:#2e7d32;padding:4px 8px;')
        self._cfg_warn.setVisible(True)

    def _on_mode(self):
        self._audit('mode', self.mode.currentData())
        self._apply_mode_visibility()
        self._refresh_cfg_warn()
        self._refresh_acq_chrome()

    def _on_stitch(self, enabled):
        self._audit('stitchEnable', enabled)
        self.stitch_box.setVisible(enabled)

    def _on_char(self, enabled):
        self._audit('charFilterEnable', enabled)
        self.char_box.setVisible(enabled)

    def _apply_mode_visibility(self):
        mode = self._cfg.get('mode', 'local')
        self.camera_box.setVisible(mode == 'camera')
        self.sdk_box.setVisible(mode == 'sdk')
        # pixel format / local-centric fields stay visible for local; camera still shows shared ones
