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
    acquisitionBackend='soft',  # soft | uvc | gentl (wave153)
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
        # wave153–154: Soft / UVC / GenTL picker (live preview) (mirrors camera_manager)
        self.acq_backend = QComboBox()
        self.acq_backend.setObjectName('imageSourceAcqBackend')
        try:
            from desktop.camera_backends import picker_choices
            for lab, kind in picker_choices():
                self.acq_backend.addItem(lab, kind)
        except Exception:
            self.acq_backend.addItem('软模拟 Soft', 'soft')
            self.acq_backend.addItem('USB UVC', 'uvc')
            self.acq_backend.addItem('GenTL / GigE', 'gentl')
        cur_be = str(cfg.get('acquisitionBackend') or (cfg.get('cameraParams') or {}).get('backendKind') or 'soft')
        idx = self.acq_backend.findData(cur_be)
        self.acq_backend.setCurrentIndex(idx if idx >= 0 else 0)
        self.acq_backend.currentIndexChanged.connect(self._on_acq_backend)
        cam_form.addRow('采集后端', self.acq_backend)
        self.acq_backend_hint = QLabel('')
        self.acq_backend_hint.setObjectName('dialogHint')
        self.acq_backend_hint.setWordWrap(True)
        cam_form.addRow(self.acq_backend_hint)
        self._refresh_acq_backend_hint()
        self._refresh_camera_devices()
        _dspin(cam_form, '控制曝光', cfg.get('exposure', 0.0), 0, 1e9,
               lambda v: self._audit('exposure', float(v)))
        _dspin(cam_form, '控制增益', cfg.get('gain', 0.0), 0, 1e6,
               lambda v: self._audit('gain', float(v)))

        # sdk — GenTL / 厂商 SDK 取图（对齐 VM 课「SDK取图」主路径：连接会话 → 全局图像）
        self.sdk_box = QGroupBox('SDK 取图')
        self.sdk_box.setObjectName('propertySection')
        sdk_layout = QVBoxLayout(self.sdk_box)
        note = QLabel(
            'wave154：相机管理 Soft / USB UVC / GenTL 均可连续 live 预览（UVC VideoCapture · GenTL CTI）。'
            'UVC 持久 VideoCapture 会话；GenTL 无 Producer 时如实未加载。'
            '请点下方打开「相机管理」：选后端 → 枚举 → 连接；预览进「全局图像」。'
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
        tip = QLabel('外部进程 SyncRun 注入仍为后续扩展；主路径：Soft 模拟 / UVC 实机 / GenTL 可插拔壳。')
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


    def _on_acq_backend(self):
        kind = self.acq_backend.currentData() or 'soft'
        self._audit('acquisitionBackend', kind)
        params = dict(self._cfg.get('cameraParams') or {})
        params['backendKind'] = kind
        try:
            from desktop.camera_backends import driver_for_kind
            params['driver'] = driver_for_kind(kind)
        except Exception:
            params['driver'] = {'soft': 'simulator', 'uvc': 'uvc', 'gentl': 'gentl'}.get(kind, 'simulator')
        self._audit('cameraParams', params)
        self._refresh_acq_backend_hint()
        self._refresh_camera_devices()
        self._refresh_acq_chrome()

    def _refresh_camera_devices(self):
        """Fill 关联相机 / SDK combo from Soft·UVC·GenTL enumerate (so dropdown is not empty)."""
        if not hasattr(self, 'camera_combo'):
            return
        kind = 'soft'
        if hasattr(self, 'acq_backend') and self.acq_backend is not None:
            kind = self.acq_backend.currentData() or 'soft'
        cur = ''
        try:
            cur = self.camera_combo.currentData() or ''
        except Exception:
            cur = (self._cfg or {}).get('cameraId') or ''
        items = []  # list[(label, deviceId, extra_params)]
        try:
            if kind == 'soft':
                items = [('软模拟 Soft · sim-0', 'soft:sim-0', {'driver': 'simulator', 'backendKind': 'soft'})]
            elif kind == 'uvc':
                import cv2
                for i in range(6):
                    cap = cv2.VideoCapture(i)
                    ok = cap.isOpened()
                    cap.release()
                    if ok:
                        did = f'uvc:{i}'
                        items.append((f'/dev/video{i} (UVC)', did, {'driver': 'uvc', 'backendKind': 'uvc', 'deviceId': str(i)}))
            elif kind == 'gentl':
                from desktop.camera_backends import discover_gentl_ctis, gentl_load_producer, gentl_enumerate_devices, format_device_picker_label
                seen = set()
                ctis = [c for c in (discover_gentl_ctis() or []) if c.get('available')]
                # Prefer 64-bit U3V producer first (USB industrial cameras)
                def _rank(c):
                    path = str(c.get('path') or '')
                    name = str(c.get('name') or '')
                    score = 0
                    if '/64/' in path or 'Win64' in path:
                        score += 10
                    if 'U3V' in name or 'U3V' in path:
                        score += 5
                    return -score
                ctis.sort(key=_rank)
                for c in ctis:
                    pid = c.get('id')
                    try:
                        gentl_load_producer(pid)
                        for d in gentl_enumerate_devices(pid) or []:
                            did = d.get('deviceId') or ''
                            if not did or did in seen:
                                continue
                            seen.add(did)
                            try:
                                lab = format_device_picker_label(d, kind='gentl')
                            except Exception:
                                lab = d.get('name') or did
                            items.append((lab, did, {
                                'driver': 'gentl', 'backendKind': 'gentl',
                                'deviceId': did, 'providerId': d.get('providerId') or pid,
                            }))
                    except Exception as exc:
                        items.append((f'GenTL 枚举失败: {exc}', '', {}))
                        break
        except Exception as exc:
            items = [(f'枚举失败: {exc}', '', {})]
        # rebuild combos
        for combo_name in ('camera_combo', 'sdk_camera'):
            combo = getattr(self, combo_name, None)
            if combo is None:
                continue
            combo.blockSignals(True)
            combo.clear()
            if not items or (len(items) == 1 and not items[0][1]):
                combo.addItem('请选择（先切换采集后端或点📷）', '')
                for lab, did, _ in items:
                    if lab and not did:
                        combo.addItem(lab, '')
            else:
                combo.addItem('请选择', '')
                for lab, did, _ in items:
                    if did:
                        combo.addItem(lab, did)
                # restore selection
                if cur:
                    ix = combo.findData(cur)
                    if ix < 0:
                        combo.addItem(str(cur), cur)
                        ix = combo.findData(cur)
                    if ix >= 0:
                        combo.setCurrentIndex(ix)
                elif kind == 'gentl' and any(i[1] for i in items):
                    # auto-select first real GenTL device to unblock Allen
                    for i, (lab, did, _) in enumerate(items):
                        if did:
                            combo.setCurrentIndex(combo.findData(did))
                            cur = did
                            break
            combo.blockSignals(False)
        # if we auto-picked, audit + stash cameraParams
        if cur and kind == 'gentl':
            extra = None
            for lab, did, ex in items:
                if did == cur:
                    extra = ex
                    break
            if extra:
                params = dict(self._cfg.get('cameraParams') or {})
                params.update(extra)
                self._audit('cameraId', cur)
                self._audit('cameraParams', params)
            elif self.camera_combo.currentData():
                self._audit('cameraId', self.camera_combo.currentData())
        if hasattr(self, 'acq_backend_hint') and kind == 'gentl' and not any(i[1] for i in items):
            self.acq_backend_hint.setText(self.acq_backend_hint.text() + ' · 未枚举到设备，确认 USB 海康已插入')

    def _refresh_acq_backend_hint(self):
        if not hasattr(self, 'acq_backend_hint'):
            return
        kind = self.acq_backend.currentData() if hasattr(self, 'acq_backend') else 'soft'
        try:
            from desktop.camera_backends import get_backend
            avail = get_backend(kind).availability()
            self.acq_backend_hint.setText(f"[{avail.get('status')}] {avail.get('statusZh') or ''}")
        except Exception as exc:
            self.acq_backend_hint.setText(str(exc))

    def _refresh_acq_chrome(self, session=None):
        """wave150/153: densify Soft/UVC/GenTL acquisition chrome strip."""
        try:
            self._refresh_acq_backend_hint()
        except Exception:
            pass
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
