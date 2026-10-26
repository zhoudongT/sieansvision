"""Native, asynchronous camera, dataset and training controls.

Dialogs share Backend without consuming responses belonging to other widgets.
Opening a dialog reads metadata only; hardware and training require a button click.
"""
from __future__ import annotations

import base64
from copy import deepcopy
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal, QRectF, QPointF
from PySide6.QtGui import QPixmap, QColor, QPen, QPolygonF, QDesktopServices
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDialog, QDialogButtonBox,
    QDoubleSpinBox, QFileDialog, QFormLayout, QGraphicsPixmapItem, QGraphicsScene, QGraphicsView,
    QGroupBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox,
    QPushButton, QScrollArea, QSpinBox, QSplitter, QTabWidget, QTableWidget,
    QTableWidgetItem, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from .catalog import builtin_definitions


def _button(label, callback, layout):
    button = QPushButton(label)
    button.clicked.connect(callback)
    layout.addWidget(button)
    return button


def _spin(low, high, value, step=1):
    widget = QSpinBox()
    widget.setRange(low, high)
    widget.setSingleStep(step)
    widget.setValue(value)
    return widget


def _number(low, high, value, decimals=6):
    widget = QDoubleSpinBox()
    widget.setDecimals(decimals)
    widget.setRange(low, high)
    widget.setValue(value)
    return widget


def _combo(items):
    widget = QComboBox()
    for label, value in items:
        widget.addItem(label, value)
    return widget


def _table(headers):
    table = QTableWidget(0, len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.setAlternatingRowColors(True)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    table.verticalHeader().hide()
    return table


def _rows(table, rows):
    table.setRowCount(len(rows))
    for row, values in enumerate(rows):
        for col, value in enumerate(values):
            table.setItem(row, col, QTableWidgetItem('—' if value is None else str(value)))


LABELS = {
    'width': '宽度', 'height': '高度', 'driver': '驱动', 'deviceId': '设备标识',
    'name': '名称', 'id': '编号', 'task': '训练类型', 'simulated': '模拟设备',
    'splits': '数据划分', 'train': '训练集', 'val': '验证集', 'images': '图片数',
    'positiveImages': '含目标图片数', 'objects': '标注目标数', 'classes': '类别',
    'fingerprint': '数据指纹', 'elapsedMs': '耗时 (ms)', 'frameAgeMs': '缓存帧龄 (ms)',
    'frameSequence': '帧序号', 'sessionId': '会话编号', 'reusedFrame': '重复缓存帧',
    'device': '计算设备', 'serial': '序列号', 'model': '型号 / 模型',
    'Width': '采集宽度', 'Height': '采集高度', 'PixelFormat': '像素格式',
    'ExposureTime': '曝光时间 (µs)', 'Gain': '增益', 'TriggerMode': '触发开关',
    'TriggerSource': '触发源', 'DeviceVendorName': '厂商', 'DeviceModelName': '型号',
    'DeviceSerialNumber': '序列号', 'OffsetX': '水平偏移', 'OffsetY': '垂直偏移',
}


def _tree_data(tree, data):
    tree.clear()

    def append(parent, key, value):
        title = LABELS.get(str(key), str(key))
        if isinstance(value, dict):
            item = QTreeWidgetItem(parent, [title, f'{len(value)} 项'])
            for k, v in value.items():
                if k not in ('annotatedImage', 'image', 'maskImage'):
                    append(item, k, v)
        elif isinstance(value, list):
            item = QTreeWidgetItem(parent, [title, f'{len(value)} 项'])
            for i, v in enumerate(value[:1000]):
                append(item, i + 1, v)
        else:
            display = '是' if value is True else '否' if value is False else '—' if value is None else str(value)
            QTreeWidgetItem(parent, [title, display])

    for key, value in data.items():
        append(tree, key, value)
    tree.expandToDepth(1)


class _Preview(QGraphicsView):
    """Image coordinates are shared by overlays and pointer annotation.

    Live camera frames update the pixmap item in place — never scene.clear()
    + fitInView every tick (that flash is the main App-side flicker).
    """
    box_drawn = Signal(object)
    polygon_drawn = Signal(object)

    def __init__(self):
        super().__init__()
        self.setScene(QGraphicsScene(self))
        self.setMinimumSize(280, 200)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.MinimalViewportUpdate)
        self.pixmap = QPixmap()
        self._pixmap_item = None
        self.records = []
        self.mode = ''
        self.origin = None
        self.vertices = []
        self.rubber = None
        self._overlay_items = []

    def set_image(self, data):
        try:
            pixels = base64.b64decode(data.split(',', 1)[1], validate=True)
            pixmap = QPixmap()
            if not pixmap.loadFromData(pixels):
                raise ValueError('图像无法解码')
            self._set_pixmap(pixmap)
        except (ValueError, IndexError):
            self.scene().clear()
            self._pixmap_item = None
            self.rubber = None
            self._overlay_items = []
            self.scene().addText('暂无可显示图像')

    def _set_pixmap(self, pixmap: QPixmap, *, refit: bool | None = None):
        size_changed = self.pixmap.isNull() or pixmap.size() != self.pixmap.size()
        self.pixmap = pixmap
        if self._pixmap_item is None:
            # Drop placeholder text etc., keep a stable pixmap item.
            self.scene().clear()
            self.rubber = None
            self._overlay_items = []
            self._pixmap_item = self.scene().addPixmap(pixmap)
            self._pixmap_item.setZValue(0)
            self.setSceneRect(QRectF(pixmap.rect()))
            self.fitInView(self.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
        else:
            self._pixmap_item.setPixmap(pixmap)
            if refit is True or (refit is None and size_changed):
                self.setSceneRect(QRectF(pixmap.rect()))
                self.fitInView(self.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
        # Annotation overlays only when present (training); live camera has none.
        if self.records or self.vertices or self.mode:
            self._redraw_overlays()

    def _clear_overlays(self):
        for item in self._overlay_items:
            self.scene().removeItem(item)
        self._overlay_items = []
        if self.rubber is not None:
            self.scene().removeItem(self.rubber)
            self.rubber = None

    def _redraw_overlays(self):
        self._clear_overlays()
        if self.pixmap.isNull():
            return
        w, h = self.pixmap.width(), self.pixmap.height()
        pen = QPen(QColor('#00d9a3'), 2)
        pen.setCosmetic(True)
        for record in self.records:
            if 'box' in record:
                x, y, bw, bh = record['box']
                item = self.scene().addRect((x-bw/2)*w, (y-bh/2)*h, bw*w, bh*h, pen)
                item.setZValue(1)
                self._overlay_items.append(item)
                anchor = QPointF((x-bw/2)*w, (y-bh/2)*h)
            else:
                points = [QPointF(x*w, y*h) for x, y in record.get('points', [])]
                if not points:
                    continue
                item = self.scene().addPolygon(QPolygonF(points), pen)
                item.setZValue(1)
                self._overlay_items.append(item)
                anchor = points[0]
            label = self.scene().addText(str(record.get('classId', 0)))
            label.setDefaultTextColor(QColor('#00d9a3'))
            label.setPos(anchor)
            label.setZValue(2)
            self._overlay_items.append(label)
        if self.vertices:
            self.rubber = self.scene().addPolygon(QPolygonF(self.vertices), QPen(QColor('#ffb545'), 2))
            self.rubber.setZValue(1)

    def redraw(self):
        if self.pixmap.isNull():
            self.scene().clear()
            self._pixmap_item = None
            self.rubber = None
            self._overlay_items = []
            return
        if self._pixmap_item is None:
            self._set_pixmap(self.pixmap, refit=True)
        else:
            self._pixmap_item.setPixmap(self.pixmap)
            self._redraw_overlays()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not self.pixmap.isNull():
            self.fitInView(self.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def _point(self, event):
        p = self.mapToScene(event.position().toPoint())
        return QPointF(max(0, min(self.pixmap.width(), p.x())), max(0, min(self.pixmap.height(), p.y())))

    def mousePressEvent(self, event):
        if self.pixmap.isNull() or not self.mode:
            return super().mousePressEvent(event)
        if event.button() == Qt.MouseButton.RightButton:
            self.finish_polygon()
            return
        if event.button() == Qt.MouseButton.LeftButton:
            if self.mode == 'detect':
                self.origin = self._point(event)
            else:
                self.vertices.append(self._point(event))
                self.redraw()

    def mouseMoveEvent(self, event):
        if self.mode == 'detect' and self.origin is not None:
            if self.rubber:
                self.scene().removeItem(self.rubber)
            self.rubber = self.scene().addRect(QRectF(self.origin, self._point(event)).normalized(), QPen(QColor('#ffb545'), 2))
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.mode == 'detect' and self.origin is not None:
            end, start = self._point(event), self.origin
            self.origin = None
            w, h = self.pixmap.width(), self.pixmap.height()
            if abs(start.x()-end.x()) >= 2 and abs(start.y()-end.y()) >= 2:
                self.box_drawn.emit([(start.x()+end.x())/(2*w), (start.y()+end.y())/(2*h), abs(end.x()-start.x())/w, abs(end.y()-start.y())/h])
            self.redraw()
            return
        super().mouseReleaseEvent(event)

    def finish_polygon(self):
        if len(self.vertices) >= 3:
            w, h = self.pixmap.width(), self.pixmap.height()
            points = [[p.x()/w, p.y()/h] for p in self.vertices]
            self.vertices = []
            self.polygon_drawn.emit(points)
        else:
            self.vertices = []
        self.redraw()


class _RpcDialog(QDialog):
    def __init__(self, backend, parent=None):
        super().__init__(parent)
        self.backend = backend
        self.pending = {}
        self.message = QLabel()
        self.message.setWordWrap(True)
        self.message.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.message.setObjectName('deviceStatus')
        backend.result.connect(self._result)
        backend.error.connect(self._error)
        backend.ready.connect(self._ready)

    def _request(self, method, params=None, callback=None, kind='action'):
        request_id = self.backend.request(method, params or {})
        self.pending[request_id] = (method, callback, kind)
        self._buttons()
        return request_id

    def _result(self, request_id, value):
        entry = self.pending.pop(request_id, None)
        if entry is None:
            return
        try:
            if entry[1]:
                entry[1](value)
        except (ValueError, KeyError, TypeError) as error:
            self.message.setText(str(error))
        self._buttons()

    def _error(self, request_id, message):
        if self.pending.pop(request_id, None) is None:
            return
        self.message.setText(message)
        self._buttons()

    def _ready(self):
        if self.isVisible():
            self.refresh()

    def _busy(self):
        return any(entry[2] == 'action' for entry in self.pending.values())

    def _has(self, method):
        return any(entry[0] == method for entry in self.pending.values())

    def _buttons(self):
        pass


class CameraDialog(_RpcDialog):
    image_ready = Signal(str)
    frame_ready = Signal(dict)
    camera_selected = Signal(dict, bool)

    def __init__(self, backend, parent=None):
        super().__init__(backend, parent)
        self.setWindowTitle('相机与连续采集')
        self.resize(1120, 790)
        self.state = {'state': 'idle'}
        self.frame = None
        self.devices = []
        self.fields = {}
        self.parameter_cache = {}
        self._driver = 'simulator'
        outer = QVBoxLayout(self)
        note = QLabel('连接后相机持续采集；关闭此窗口或停止流程仍保持连接。停止并释放设备或退出应用时释放。')
        note.setWordWrap(True)
        outer.addWidget(note)
        self.tabs = QTabWidget()
        outer.addWidget(self.tabs, 1)
        device_page = QWidget()
        device_layout = QVBoxLayout(device_page)
        selectors = QFormLayout()
        self.driver = _combo([('模拟 2D 相机', 'simulator'), ('USB UVC', 'uvc'), ('GenTL 工业相机', 'gentl'), ('RealSense 深度相机', 'realsense'), ('Orbbec 深度相机', 'orbbec'), ('模拟 RGB-D 相机', 'rgbd_simulator')])
        self.driver.setObjectName('cameraDriver')
        self.provider = QComboBox()
        self.device_id = QLineEdit('synthetic-parts')
        self.device_id.setObjectName('cameraDeviceId')
        self.network = QCheckBox('发现 Orbbec 网络设备')
        selectors.addRow('驱动', self.driver)
        selectors.addRow('GenTL 驱动文件', self.provider)
        selectors.addRow('设备标识', self.device_id)
        selectors.addRow(self.network)
        device_layout.addLayout(selectors)
        actions = QHBoxLayout()
        self.scan_button = _button('枚举设备', self.scan, actions)
        self.inspect_button = _button('读取设备参数', self.inspect, actions)
        self.capture_button = _button('采集单帧', self.capture, actions)
        self.cancel_button = _button('取消本次请求', self.cancel_request, actions)
        device_layout.addLayout(actions)
        self.device_table = _table(['设备', '设备标识', '型号', '序列号', '接口'])
        self.device_table.setMaximumHeight(170)
        device_layout.addWidget(self.device_table)
        split = QSplitter()
        self.preview = _Preview()
        self.details = QTreeWidget()
        self.details.setHeaderLabels(['参数 / 结果', '值'])
        split.addWidget(self.preview)
        split.addWidget(self.details)
        device_layout.addWidget(split, 1)
        actions = QHBoxLayout()
        self.use_frame_button = _button('用预览帧作为流程输入', self.use_frame, actions)
        self.add_button = _button('添加相机采集节点', lambda: self.use_camera(False), actions)
        self.apply_button = _button('应用到所选采集节点', lambda: self.use_camera(True), actions)
        device_layout.addLayout(actions)
        self.tabs.addTab(device_page, '设备与预览')
        self.parameter_scroll = QScrollArea()
        self.parameter_scroll.setWidgetResizable(True)
        self.tabs.addTab(self.parameter_scroll, '采集参数')
        self._build_parameters()
        session_page = QWidget()
        session_layout = QVBoxLayout(session_page)
        session_form = QFormLayout()
        self.interval = _spin(50, 60000, 100)
        self.retries = _spin(0, 5, 0)
        self.reconnect = _spin(200, 60000, 1000)
        session_form.addRow('最短采集间隔 (ms)', self.interval)
        session_form.addRow('本次会话重连总次数', self.retries)
        session_form.addRow('重连等待 (ms)', self.reconnect)
        session_layout.addLayout(session_form)
        actions = QHBoxLayout()
        self.connect_button = _button('打开所选相机并持续采集', self.start_session, actions)
        self.reopen_button = _button('按上次配置重新连接', self.reopen_session, actions)
        self.stop_button = _button('停止并释放设备', self.stop_session, actions)
        session_layout.addLayout(actions)
        actions = QHBoxLayout()
        self.session_preview_button = _button('预览最新缓存帧', self.session_preview, actions)
        self.session_add_button = _button('添加连续取帧节点', lambda: self.use_session(False), actions)
        self.session_apply_button = _button('应用到所选采集节点', lambda: self.use_session(True), actions)
        session_layout.addLayout(actions)
        self.session_label = QLabel('未连接')
        session_layout.addWidget(self.session_label)
        self.statistics = _table(['统计项', '值'])
        session_layout.addWidget(self.statistics, 1)
        hint = QLabel('连续连接仅支持自由采集。缓存容量为一帧，新帧覆盖旧帧；不用于逐帧无损记录。设备不会随应用启动自动打开。')
        hint.setWordWrap(True)
        session_layout.addWidget(hint)
        self.tabs.addTab(session_page, '连续连接与缓存')
        outer.addWidget(self.message)
        close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close.rejected.connect(self.reject)
        outer.addWidget(close)
        self.driver.currentIndexChanged.connect(self._driver_changed)
        self.device_id.textChanged.connect(self._buttons)
        self.device_table.itemSelectionChanged.connect(self._select_device)
        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.refresh)
        # Live preview: pull latest buffered frame while continuous session runs.
        # Avoids browser JPEG/HTTP paint stutter; still uses cached PNG from session.
        self.live_timer = QTimer(self)
        self.live_timer.setInterval(50)  # ~20 Hz; PNG session cache still caps real rate
        self.live_timer.timeout.connect(self._live_tick)
        self._live_pending = False
        self._buttons()

    def showEvent(self, event):
        super().showEvent(event)
        self.timer.start()
        if self.backend.is_ready:
            self.refresh()
            if not self._has('camera/providers'):
                self._request('camera/providers', callback=self._providers, kind='status')

    def hideEvent(self, event):
        self.timer.stop()
        self.live_timer.stop()
        self.cancel_request()
        super().hideEvent(event)

    def refresh(self):
        if self.backend.is_ready and not self._has('camera/session/status'):
            self._request('camera/session/status', callback=self._session, kind='status')

    def _providers(self, value):
        info = value.get('result', {})
        old = self.provider.currentData()
        self.provider.clear()
        for item in info.get('items', []):
            self.provider.addItem(item['name'] + ('' if item.get('available') else '（文件不存在）'), item['id'])
        self.provider.setCurrentIndex(max(0, self.provider.findData(old)))
        self.message.setText('GenTL 配置 ' + str(self.provider.count()) + ' 项；RealSense：' + str(info.get('realsense') or '未安装') + '；Orbbec：' + str(info.get('orbbec') or '未安装'))

    def _driver_changed(self):
        self.parameter_cache[self._driver] = self._parameter_values()
        self._driver = self.driver.currentData()
        self.device_id.setText({'simulator': 'synthetic-parts', 'rgbd_simulator': 'synthetic-rgbd', 'uvc': '0'}.get(self._driver, ''))
        self.devices = []
        self.device_table.setRowCount(0)
        self._build_parameters()
        self._buttons()

    def _build_parameters(self):
        content = QWidget()
        form = QFormLayout(content)
        self.fields = {}
        driver = self._driver
        defaults = {'trigger': 'freerun', 'timeoutMs': 5000}
        if driver in ('realsense', 'orbbec', 'rgbd_simulator'):
            defaults.update(pointStride=1 if driver == 'rgbd_simulator' else 4, minDepth=.1, maxDepth=5)
        if driver in ('realsense', 'orbbec'):
            defaults.update(width=640, height=480, fps=30, warmupFrames=5, enableColor=True, colorWidth=640, colorHeight=480, colorFormat='RGB')
        if driver == 'gentl':
            defaults.update(dataMode='image', configure3d=True, coordinateFormat='Coord3D_ABC32f', rangeComponent=-1, intensityComponent=-1, confidenceComponent=-1, confidenceThreshold=1, alignedComponents=False, pointStride=4, triggerSource='Line0')
        defaults.update(self.parameter_cache.get(driver, {}))
        common = {'timeoutMs', 'width', 'height'}
        extra = {
            'simulator': set(), 'rgbd_simulator': {'pointStride', 'minDepth', 'maxDepth'},
            'uvc': {'fps', 'warmupFrames'},
            'gentl': {'trigger', 'triggerSource', 'exposureTime', 'gain', 'pixelFormat', 'dataMode', 'configure3d', 'coordinateFormat', 'rangeComponent', 'intensityComponent', 'confidenceComponent', 'confidenceThreshold', 'alignedComponents', 'pointStride'},
            'realsense': {'fps', 'warmupFrames', 'enableColor', 'colorWidth', 'colorHeight', 'pointStride', 'minDepth', 'maxDepth'},
            'orbbec': {'fps', 'warmupFrames', 'enableColor', 'colorWidth', 'colorHeight', 'colorFormat', 'pointStride', 'minDepth', 'maxDepth'},
        }
        for spec in builtin_definitions()['camera_capture']['parameters']:
            key = spec['key']
            if key not in common | extra.get(driver, set()):
                continue
            if driver == 'rgbd_simulator' and key in ('width', 'height'):
                continue
            value = defaults.get(key, spec.get('default'))
            if spec.get('choices'):
                editor = _combo([(str(c.get('label', c['value'])), c['value']) for c in spec['choices']])
                editor.setCurrentIndex(max(0, editor.findData(value)))
            elif spec['type'] == 'boolean':
                editor = QCheckBox()
                editor.setChecked(bool(value))
            elif spec['type'] in ('integer', 'number'):
                lo, hi = spec.get('minimum', 0), spec.get('maximum', 10000000)
                editor = _spin(int(lo), int(hi), int(value or lo)) if spec['type'] == 'integer' else _number(lo, hi, value if value is not None else lo)
            else:
                editor = QLineEdit(str(value or ''))
            enabled = QCheckBox(spec['label'])
            enabled.setChecked(key in defaults)
            enabled.setToolTip('勾选后写入此参数；未勾选时沿用设备值。')
            editor.setEnabled(enabled.isChecked())
            enabled.toggled.connect(editor.setEnabled)
            editor.setObjectName('cameraParameter:' + key)
            form.addRow(enabled, editor)
            self.fields[key] = (enabled, editor)
        hint = QLabel('勾选的参数会用于采集和新建连接。GenTL 参数修改会影响设备；触发失败不自动重试。GenTL 的 XYZ、亮度和置信度分量需与设备实际配置一致。')
        hint.setWordWrap(True)
        form.addRow(hint)
        old = self.parameter_scroll.takeWidget()
        if old:
            old.deleteLater()
        self.parameter_scroll.setWidget(content)

    def _parameter_values(self):
        params = {}
        for key, (enabled, editor) in self.fields.items():
            if not enabled.isChecked():
                continue
            if isinstance(editor, QComboBox):
                params[key] = editor.currentData()
            elif isinstance(editor, QCheckBox):
                params[key] = editor.isChecked()
            elif isinstance(editor, (QSpinBox, QDoubleSpinBox)):
                params[key] = editor.value()
            else:
                params[key] = editor.text().strip()
        return params

    def params(self):
        params = {'driver': self.driver.currentData(), 'deviceId': self.device_id.text().strip(), **self._parameter_values()}
        if params['driver'] == 'gentl':
            params['providerId'] = self.provider.currentData() or ''
        if params['driver'] == 'orbbec':
            params['discoverNetwork'] = self.network.isChecked()
        return params

    def set_params(self, params):
        if params.get('driver') == 'session':
            self.tabs.setCurrentIndex(2)
            return
        index = self.driver.findData(params.get('driver', 'simulator'))
        if index >= 0:
            self.driver.setCurrentIndex(index)
        self.parameter_cache[self._driver] = deepcopy(params)
        self._build_parameters()
        self.device_id.setText(str(params.get('deviceId', '')))
        self.network.setChecked(params.get('discoverNetwork', False))
        if params.get('providerId'):
            index = self.provider.findData(params['providerId'])
            if index < 0:
                self.provider.addItem(params['providerId'], params['providerId'])
                index = self.provider.count()-1
            self.provider.setCurrentIndex(index)

    def _buttons(self, *_):
        if not hasattr(self, 'connect_button'):
            return
        busy = self._busy() or not self.backend.is_ready
        selected = bool(self.device_id.text().strip())
        active = self.state.get('active', False)
        running = self.state.get('state') == 'running'
        for button in (self.scan_button, self.driver, self.provider, self.network, self.device_id, self.parameter_scroll):
            button.setEnabled(not busy)
        self.provider.setEnabled(not busy and self.driver.currentData() == 'gentl')
        self.network.setEnabled(not busy and self.driver.currentData() == 'orbbec')
        for button in (self.inspect_button, self.capture_button, self.add_button, self.apply_button):
            button.setEnabled(not busy and selected)
        self.cancel_button.setEnabled(any(method in ('camera/list', 'camera/inspect', 'camera/capture') for method, _, _ in self.pending.values()))
        self.use_frame_button.setEnabled(not busy and self.frame is not None)
        self.connect_button.setEnabled(not busy and selected and not active)
        self.reopen_button.setEnabled(not busy and not active and bool(self.state.get('config')))
        self.stop_button.setEnabled(not busy and active)
        for button in (self.session_preview_button, self.session_add_button, self.session_apply_button):
            button.setEnabled(not busy and running)
        for field in (self.interval, self.retries, self.reconnect):
            field.setEnabled(not busy and not active)

    def scan(self):
        params = {'driver': self.driver.currentData()}
        if params['driver'] == 'gentl':
            params['providerId'] = self.provider.currentData() or ''
        if params['driver'] == 'orbbec':
            params['discoverNetwork'] = self.network.isChecked()
        self._request('camera/list', params, self._devices)

    def _devices(self, value):
        self.devices = value.get('result', {}).get('items', [])
        _rows(self.device_table, [[d.get(k) for k in ('name', 'deviceId', 'model', 'serial', 'transport')] for d in self.devices])
        self.message.setText(f'枚举完成：{len(self.devices)} 台。选择设备后可读取参数或采集。')
        if self.devices:
            self.device_table.selectRow(0)

    def _select_device(self):
        row = self.device_table.currentRow()
        if 0 <= row < len(self.devices):
            self.device_id.setText(str(self.devices[row]['deviceId']))

    def inspect(self):
        self._request('camera/inspect', self.params(), lambda value: _tree_data(self.details, {'设备参数': value.get('result', {}).get('items', [])}))

    def capture(self):
        self._request('camera/capture', self.params(), self._captured)

    def _captured(self, value):
        self.frame = deepcopy(value)
        self.preview.set_image(value.get('annotatedImage', ''))
        _tree_data(self.details, value.get('result', {}))
        self.message.setText('采集完成。预览帧可作为流程输入，设备配置可添加到流程。')
        self.tabs.setCurrentIndex(0)

    def cancel_request(self):
        for request_id, (method, _, _) in list(self.pending.items()):
            if method in ('camera/list', 'camera/inspect', 'camera/capture') and self.backend.is_ready:
                self._request('camera/cancel', {'requestId': request_id}, kind='cancel')

    def use_frame(self):
        if self.frame:
            self.frame_ready.emit(deepcopy(self.frame))
            if self.frame.get('annotatedImage'):
                self.image_ready.emit(self.frame['annotatedImage'])
            self.accept()

    def use_camera(self, apply):
        self.camera_selected.emit(self.params(), apply)
        self.accept()

    def _config(self, params):
        return dict(params=params, intervalMs=self.interval.value(), reconnectAttempts=self.retries.value(), reconnectMs=self.reconnect.value(), autoStart=False)

    def start_session(self):
        self._request('camera/session/start', self._config(self.params()), self._session)

    def reopen_session(self):
        self._request('camera/session/start', self._config(self.state['config']['params']), self._session)

    def stop_session(self):
        self._request('camera/session/stop', {'id': self.state.get('id')}, self._session)

    def session_preview(self):
        self._request('camera/capture', {'driver': 'session', 'sessionId': self.state.get('id'), 'framePolicy': 'latest', 'maxAgeMs': 5000, 'timeoutMs': 5000}, self._captured)

    def _error(self, request_id, message):
        entry = self.pending.get(request_id)
        if entry and entry[0] == 'camera/capture':
            self._live_pending = False
        super()._error(request_id, message)

    def _live_tick(self):
        if self._live_pending or not self.backend.is_ready:
            return
        if self.state.get('state') != 'running' or not self.state.get('id'):
            return
        if any(method == 'camera/capture' for method, _, _ in self.pending.values()):
            return
        self._live_pending = True

        def done(value):
            self._live_pending = False
            self.frame = deepcopy(value)
            image = value.get('annotatedImage', '')
            if image:
                self.preview.set_image(image)

        # kind=status：实时预览不锁住其它按钮；读的是会话已缓存帧。
        self._request(
            'camera/capture',
            {'driver': 'session', 'sessionId': self.state.get('id'), 'framePolicy': 'latest', 'maxAgeMs': 2000, 'timeoutMs': 2000},
            done,
            kind='status',
        )

    def use_session(self, apply):
        self.camera_selected.emit(dict(driver='session', sessionId=self.state.get('bindingId') or self.state['id'], framePolicy='next', maxAgeMs=1000, timeoutMs=5000), apply)
        self.accept()

    def _session(self, state):
        first = self.state.get('id') != state.get('id')
        self.state = state
        labels = dict(idle='未连接', opening='正在打开设备', running='持续采集中', reconnecting='正在重连', stopping='正在释放设备', stopped='已停止', failed='采集失败', interrupted='应用中断，需手动重连')
        self.session_label.setText(labels.get(state.get('state'), state.get('state', '')) + (' · ' + state['error'] if state.get('error') else ''))
        config = state.get('config', {})
        if first:
            self.interval.setValue(config.get('intervalMs', 100))
            self.retries.setValue(config.get('reconnectAttempts', 0))
            self.reconnect.setValue(config.get('reconnectMs', 1000))
        _rows(self.statistics, [('会话编号', state.get('id')), ('设备驱动', config.get('params', {}).get('driver')), ('设备标识', config.get('params', {}).get('deviceId')), ('接收帧数', state.get('received', 0)), ('流程 / 预览取帧次数', state.get('consumed', 0)), ('覆盖未取帧数', state.get('overwritten', 0)), ('重复缓存帧数', state.get('reused', 0)), ('重连次数', state.get('reconnects', 0)), ('缓存帧龄 (ms)', state.get('frameAgeMs'))])
        if state.get('state') == 'running':
            if not self.live_timer.isActive():
                self.live_timer.start()
                self.message.setText('连续采集中：原生预览刷新最新缓存帧（无 scene.clear 闪烁；速率受会话 PNG 缓存限制）。')
        else:
            self.live_timer.stop()
            self._live_pending = False


class TrainingDialog(_RpcDialog):
    model_selected = Signal(str, str)

    def __init__(self, backend, parent=None):
        super().__init__(backend, parent)
        self.setWindowTitle('数据集与模型训练')
        self.resize(1080, 800)
        self.state = {}
        self.annotation_dialog = None
        self.selected_dataset = None
        outer = QVBoxLayout(self)
        intro = QLabel('数据集检查与训练共用运行平台；关闭本窗口训练继续，退出应用会停止训练。合成示例用于验证链路，现场精度需用独立实际样本验收。')
        intro.setWordWrap(True)
        outer.addWidget(intro)
        self.tabs = QTabWidget()
        outer.addWidget(self.tabs, 1)
        data_page = QWidget()
        data_layout = QVBoxLayout(data_page)
        creation = QGroupBox('创建数据集')
        creation_form = QFormLayout(creation)
        self.new_id = QLineEdit()
        self.new_id.setMaxLength(40)
        self.new_id.setPlaceholderText('例如 parts-v1')
        self.new_id.setObjectName('trainingDatasetId')
        self.task = _combo([('目标检测 · 框标注', 'detect'), ('实例分割 · 轮廓标注', 'segment')])
        self.class_table = _table(['类别名称（行号即类别编号，从 0 起）'])
        self.class_table.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked | QAbstractItemView.EditTrigger.EditKeyPressed)
        self.class_table.setMaximumHeight(120)
        _rows(self.class_table, [['part']])
        creation_form.addRow('目录名称', self.new_id)
        creation_form.addRow('训练任务', self.task)
        creation_form.addRow('类别名称', self.class_table)
        class_actions = QHBoxLayout()
        _button('新增类别', self.add_class, class_actions)
        _button('删除所选类别', self.remove_class, class_actions)
        creation_form.addRow(class_actions)
        actions = QHBoxLayout()
        self.create_button = _button('创建空数据集', lambda: self.create_dataset(False), actions)
        self.demo_button = _button('创建合成示例', lambda: self.create_dataset(True), actions)
        creation_form.addRow(actions)
        data_layout.addWidget(creation)
        form = QFormLayout()
        self.dataset = QComboBox()
        self.dataset.setObjectName('trainingDataset')
        self.folder = QLabel()
        self.folder.setWordWrap(True)
        self.folder.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        form.addRow('已建数据集', self.dataset)
        form.addRow('本地目录', self.folder)
        data_layout.addLayout(form)
        actions = QHBoxLayout()
        self.check_button = _button('检查数据集', self.check_dataset, actions)
        self.annotate_button = _button('导入图片与标注', self.annotate, actions)
        self.folder_button = _button('打开数据集目录', self.open_folder, actions)
        data_layout.addLayout(actions)
        hint = QLabel('目录结构：images/train、images/val 存放图片，labels/train、labels/val 存放同名 YOLO 标注。训练与验证集使用不同图片。')
        hint.setWordWrap(True)
        data_layout.addWidget(hint)
        self.check_result = QTreeWidget()
        self.check_result.setHeaderLabels(['检查项', '结果'])
        data_layout.addWidget(self.check_result, 1)
        self.tabs.addTab(data_page, '数据集')
        train_page = QWidget()
        train_layout = QVBoxLayout(train_page)
        self.config_group = QGroupBox('训练参数')
        config = QFormLayout(self.config_group)
        self.model = QComboBox()
        self.device = _combo([('CPU', 'cpu'), ('自动选择', 'auto')] + [(f'CUDA GPU {i}', f'cuda:{i}') for i in range(8)])
        self.epochs = _spin(1, 300, 20)
        self.image_size = _combo([(str(n), n) for n in range(64, 641, 32)])
        self.image_size.setCurrentIndex(self.image_size.findData(320))
        self.batch = _spin(1, 8, 2)
        self.rate = _number(.000001, .1, .001)
        self.seed = _spin(0, 2147483647, 0)
        for label, widget in [('基础模型', self.model), ('计算设备', self.device), ('训练轮次', self.epochs), ('图像尺寸', self.image_size), ('批量大小', self.batch), ('学习率', self.rate), ('随机种子', self.seed)]:
            config.addRow(label, widget)
        train_layout.addWidget(self.config_group)
        hint = QLabel('开始训练时会复制数据集快照，使用 AdamW。首次验证可选 1 轮和 64 / 128 像素；训练只使用已安装的本地模型。')
        hint.setWordWrap(True)
        train_layout.addWidget(hint)
        actions = QHBoxLayout()
        self.start_button = _button('开始训练', self.start_training, actions)
        self.stop_button = _button('停止训练', self.stop_training, actions)
        train_layout.addLayout(actions)
        publish = QFormLayout()
        self.publish_name = QLineEdit()
        self.publish_name.setPlaceholderText('trained-parts-v1.pt')
        publish.addRow('模型安装名称', self.publish_name)
        train_layout.addLayout(publish)
        actions = QHBoxLayout()
        self.publish_button = _button('安装到模型目录', self.publish, actions)
        self.add_button = _button('添加为流程算子', self.add_model, actions)
        train_layout.addLayout(actions)
        train_layout.addStretch()
        self.tabs.addTab(train_page, '训练与模型安装')
        status_page = QWidget()
        status_layout = QVBoxLayout(status_page)
        self.job_table = _table(['当前 / 最近任务', '值'])
        status_layout.addWidget(self.job_table)
        self.metrics = _table(['轮次'])
        status_layout.addWidget(self.metrics, 1)
        self.tabs.addTab(status_page, '进度与指标')
        outer.addWidget(self.message)
        actions = QHBoxLayout()
        self.refresh_button = _button('刷新', self.refresh, actions)
        actions.addStretch()
        _button('关闭', self.reject, actions)
        outer.addLayout(actions)
        self.dataset.currentIndexChanged.connect(self.dataset_changed)
        self.timer = QTimer(self)
        self.timer.setInterval(2000)
        self.timer.timeout.connect(self.refresh)
        self._buttons()

    def showEvent(self, event):
        super().showEvent(event)
        self.timer.start()
        self.refresh()

    def hideEvent(self, event):
        self.timer.stop()
        super().hideEvent(event)

    def reject(self):
        if self.annotation_dialog and self.annotation_dialog.dirty:
            if not self.annotation_dialog._discard():
                return
            self.annotation_dialog.dirty = False
        super().reject()

    def refresh(self):
        if self.backend.is_ready and not self._has('training/status'):
            self._request('training/status', callback=self._status, kind='status')

    def _buttons(self):
        if not hasattr(self, 'start_button'):
            return
        busy = self._busy() or self.state.get('busy', False) or not self.backend.is_ready
        selected = bool(self.dataset.currentData())
        for button in (self.create_button, self.demo_button):
            button.setEnabled(not busy)
        for button in (self.check_button, self.annotate_button):
            button.setEnabled(not busy and selected)
        self.folder_button.setEnabled(selected)
        self.config_group.setEnabled(not busy)
        self.dataset.setEnabled(not busy)
        self.start_button.setEnabled(not busy and selected and bool(self.model.currentText()))
        job = self.state.get('job') or {}
        self.stop_button.setEnabled(job.get('state') == 'running' and not self._has('training/cancel'))
        self.publish_button.setEnabled(not busy and job.get('state') == 'completed' and not job.get('published'))
        self.add_button.setEnabled(not busy and bool(job.get('published')))

    def _status(self, state):
        self.state = state
        previous_dataset = self.dataset.currentData()
        selected = self.selected_dataset or previous_dataset
        self.selected_dataset = None
        self.dataset.blockSignals(True)
        self.dataset.clear()
        for dataset in state.get('datasets', []):
            task = '实例分割' if dataset['task'] == 'segment' else '目标检测'
            self.dataset.addItem(dataset['id'] + ' · ' + task + (' · 合成示例' if dataset.get('demo') else ''), dataset['id'])
        self.dataset.setCurrentIndex(max(0, self.dataset.findData(selected)))
        self.dataset.blockSignals(False)
        old_model = self.model.currentText()
        self.model.clear()
        self.model.addItems(state.get('models', []))
        if old_model in state.get('models', []):
            self.model.setCurrentText(old_model)
        self.dataset_changed(choose_model=previous_dataset != self.dataset.currentData())
        job = state.get('job') or {}
        labels = dict(running='训练中', stopping='正在停止', cancelled='已取消', completed='训练完成', failed='训练失败', interrupted='应用中断')
        def stamp(value):
            return datetime.fromtimestamp(value/1000).strftime('%Y-%m-%d %H:%M:%S') if value else '—'
        _rows(self.job_table, [('任务状态', labels.get(job.get('state'), '尚未训练')), ('任务编号', job.get('id')), ('数据集', job.get('datasetId')), ('基础模型', job.get('model')), ('计算设备', job.get('deviceName') or job.get('device')), ('设备说明', job.get('deviceReason')), ('完成轮次', str(job.get('epoch', 0)) + ' / ' + str(job.get('config', {}).get('epochs', '—'))), ('阶段', job.get('phase')), ('开始时间', stamp(job.get('startedAt'))), ('结束时间', stamp(job.get('endedAt'))), ('错误', job.get('error')), ('已安装模型', job.get('published'))])
        rows = job.get('metrics', [])
        keys = list(dict.fromkeys(key for row in rows for key in row))
        self.metrics.setColumnCount(len(keys) or 1)
        self.metrics.setHorizontalHeaderLabels([self._metric_name(key) for key in keys] or ['轮次'])
        _rows(self.metrics, [[round(row[k], 6) if isinstance(row.get(k), float) else row.get(k) for k in keys] for row in rows])

    @staticmethod
    def _metric_name(key):
        return key.replace('epoch', '轮次').replace('metrics/', '验证 · ').replace('train/', '训练 · ').replace('val/', '验证 · ').replace('precision', '精确率').replace('recall', '召回率').replace('box_loss', '框损失').replace('cls_loss', '分类损失').replace('dfl_loss', '分布损失').replace('seg_loss', '分割损失')

    def _dataset(self):
        return next((d for d in self.state.get('datasets', []) if d['id'] == self.dataset.currentData()), None)

    def dataset_changed(self, _index=0, choose_model=True):
        dataset = self._dataset()
        self.folder.setText(dataset['folder'] if dataset else self.state.get('datasetRoot', ''))
        if dataset and choose_model:
            model = 'yolo11n-seg.pt' if dataset['task'] == 'segment' else 'yolo11n.pt'
            if self.model.findText(model) >= 0:
                self.model.setCurrentText(model)
        self._buttons()

    def add_class(self):
        row = self.class_table.rowCount()
        if row < 100:
            self.class_table.insertRow(row)
            self.class_table.setItem(row, 0, QTableWidgetItem('类别' + str(row)))
            self.class_table.editItem(self.class_table.item(row, 0))

    def remove_class(self):
        row = self.class_table.currentRow()
        if row >= 0:
            self.class_table.removeRow(row)

    def create_dataset(self, demo):
        names = ['part'] if demo else [self.class_table.item(row, 0).text().strip() for row in range(self.class_table.rowCount())]
        self._request('training/datasets/create', dict(id=self.new_id.text().strip(), task=self.task.currentData(), names=names, demo=demo), self._created)

    def _created(self, dataset):
        self.selected_dataset = dataset['id']
        if dataset.get('demo'):
            self.epochs.setValue(1)
            self.image_size.setCurrentIndex(self.image_size.findData(64))
        self.message.setText('数据集已创建：' + dataset['id'])
        self.check_result.clear()
        self.refresh()

    def check_dataset(self):
        self._request('training/datasets/check', {'datasetId': self.dataset.currentData()}, lambda result: _tree_data(self.check_result, result.get('summary', result)))

    def start_training(self):
        params = dict(datasetId=self.dataset.currentData(), model=self.model.currentText(), device=self.device.currentData(), epochs=self.epochs.value(), imageSize=self.image_size.currentData(), batch=self.batch.value(), learningRate=self.rate.value(), seed=self.seed.value())
        self._request('training/start', params, self._training_started)

    def _training_started(self, result):
        self.state['job'] = result
        self.state['busy'] = True
        self.message.setText('训练已启动，关闭本窗口仍继续训练。')
        self.tabs.setCurrentIndex(2)
        self.refresh()

    def stop_training(self):
        self._request('training/cancel', {'id': self.state['job']['id']}, lambda _: self.refresh())

    def publish(self):
        self._request('training/publish', {'id': self.state['job']['id'], 'name': self.publish_name.text().strip()}, self._published)

    def _published(self, result):
        self.message.setText('已安装模型：' + result['name'])
        self.refresh()

    def add_model(self):
        job = self.state.get('job') or {}
        if job.get('published'):
            self.model_selected.emit('yolo_segment' if job.get('task') == 'segment' else 'yolo', job['published'])
            self.accept()

    def open_folder(self):
        dataset = self._dataset()
        if dataset:
            QDesktopServices.openUrl(QUrl.fromLocalFile(dataset['folder']))

    def annotate(self):
        dataset = self._dataset()
        if dataset:
            if self.annotation_dialog:
                self.annotation_dialog.deleteLater()
            self.annotation_dialog = AnnotationDialog(self.backend, dataset, self)
            self.annotation_dialog.show()


class AnnotationDialog(_RpcDialog):
    """YOLO boxes and polygons drawn in Qt, with revision-checked persistence."""
    def __init__(self, backend, dataset, parent=None):
        super().__init__(backend, parent)
        self.dataset = deepcopy(dataset)
        self.loaded = None
        self.dirty = False
        self.items = []
        self.records = []
        self.proposals = []
        self._upload_queue = []
        self.setWindowTitle('图片标注 · ' + dataset['id'])
        self.resize(1160, 820)
        outer = QVBoxLayout(self)
        actions = QHBoxLayout()
        self.split = _combo([('训练集', 'train'), ('验证集', 'val')])
        actions.addWidget(self.split)
        self.upload_button = _button('导入图片', self.upload, actions)
        self.refresh_button = _button('刷新图片', self.refresh, actions)
        self.save_button = _button('保存标注', self.save, actions)
        self.background_button = _button('标为背景（清空目标）', self.clear_records, actions)
        outer.addLayout(actions)
        layout = QSplitter()
        self.images = _table(['图片', '划分', '已标注'])
        self.images.setMaximumWidth(350)
        layout.addWidget(self.images)
        workspace = QWidget()
        work = QVBoxLayout(workspace)
        toolbar = QHBoxLayout()
        self.category = _combo([(str(i) + ' · ' + name, i) for i, name in enumerate(dataset['names'])])
        toolbar.addWidget(QLabel('新目标类别'))
        toolbar.addWidget(self.category)
        self.finish_button = _button('完成轮廓', self._finish_polygon, toolbar)
        self.finish_button.setVisible(dataset['task'] == 'segment')
        work.addLayout(toolbar)
        self.preview = _Preview()
        self.preview.mode = dataset['task']
        self.preview.box_drawn.connect(lambda box: self.add_record({'classId': self.category.currentData(), 'box': box}))
        self.preview.polygon_drawn.connect(lambda points: self.add_record({'classId': self.category.currentData(), 'points': points}))
        work.addWidget(self.preview, 1)
        hint = QLabel('拖动鼠标绘制目标框。坐标为 0–1 的中心 X、中心 Y、宽度、高度。' if dataset['task'] == 'detect' else '单击依次添加轮廓顶点，右键或“完成轮廓”结束。坐标为 0–1 的 X、Y。')
        hint.setWordWrap(True)
        work.addWidget(hint)
        tables = QSplitter()
        self.targets = _table(['目标', '类别'])
        self.coordinates = _table(['X', 'Y'])
        tables.addWidget(self.targets)
        tables.addWidget(self.coordinates)
        tables.setMaximumHeight(200)
        work.addWidget(tables)
        actions = QHBoxLayout()
        self.remove_button = _button('删除所选目标', self.remove_record, actions)
        self.vertex_button = _button('删除所选顶点', self.remove_vertex, actions)
        self.vertex_button.setVisible(dataset['task'] == 'segment')
        work.addLayout(actions)
        layout.addWidget(workspace)
        layout.setStretchFactor(1, 1)
        outer.addWidget(layout, 1)
        assist = QTabWidget()
        assist.setMaximumHeight(220)
        history_page = QWidget()
        history_form = QFormLayout(history_page)
        self.history = QComboBox()
        history_form.addRow('已有备份版本', self.history)
        history_actions = QHBoxLayout()
        self.history_button = _button('读取标注历史', self.load_history, history_actions)
        self.restore_button = _button('载入版本供编辑', self.restore_history, history_actions)
        history_form.addRow(history_actions)
        assist.addTab(history_page, '标注历史')
        proposal_page = QWidget()
        proposal_layout = QVBoxLayout(proposal_page)
        proposal_actions = QHBoxLayout()
        self.model = QComboBox()
        proposal_actions.addWidget(self.model)
        self.confidence = _number(.01, 1, .25, 2)
        proposal_actions.addWidget(QLabel('最低置信度'))
        proposal_actions.addWidget(self.confidence)
        self.suggest_button = _button('用本地模型生成候选', self.suggest, proposal_actions)
        self.accept_button = _button('加入所选候选', self.accept_proposal, proposal_actions)
        proposal_layout.addLayout(proposal_actions)
        self.candidate_table = _table(['模型类别', '置信度', '映射到数据集类别'])
        proposal_layout.addWidget(self.candidate_table)
        assist.addTab(proposal_page, '模型辅助候选')
        outer.addWidget(assist)
        outer.addWidget(self.message)
        close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close.rejected.connect(self.reject)
        outer.addWidget(close)
        self.images.itemSelectionChanged.connect(self.load_selected)
        self.targets.itemSelectionChanged.connect(self.select_record)
        self._buttons()

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh()
        if self.backend.is_ready:
            self._request('models/list', callback=lambda value: self.model.addItems(value.get('models', [])), kind='status')

    def _call(self, action, body=None, callback=None):
        return self._request('training/annotations', {'datasetId': self.dataset['id'], 'action': action, 'body': body or {}}, callback)

    def _buttons(self):
        if not hasattr(self, 'suggest_button'):
            return
        available = not self._busy() and self.backend.is_ready
        loaded = self.loaded is not None
        for button in (self.upload_button, self.refresh_button, self.images):
            button.setEnabled(available)
        for button in (self.save_button, self.background_button, self.remove_button, self.vertex_button, self.history_button, self.suggest_button, self.targets, self.coordinates, self.preview):
            button.setEnabled(available and loaded)
        self.restore_button.setEnabled(available and loaded and bool(self.history.currentData()))
        self.accept_button.setEnabled(available and loaded and bool(self.proposals))

    def refresh(self):
        if self.backend.is_ready and not self._busy():
            self._call('list', callback=self._listed)

    def _listed(self, result):
        self.items = result.get('items', [])
        self.images.blockSignals(True)
        _rows(self.images, [[item['name'], '训练' if item['split'] == 'train' else '验证', '是' if item['hasLabel'] else '否'] for item in self.items])
        self.images.blockSignals(False)

    def _discard(self):
        if not self.dirty:
            return True
        return QMessageBox.question(self, '尚未保存的标注', '放弃本次尚未保存的标注修改？', QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel, QMessageBox.StandardButton.Cancel) == QMessageBox.StandardButton.Discard

    def reject(self):
        if self._discard():
            super().reject()

    def load_selected(self):
        row = self.images.currentRow()
        if 0 <= row < len(self.items) and self._discard():
            self._call('load', self.items[row], self._loaded)

    def _loaded(self, result):
        self.loaded = result
        self.records = deepcopy(result.get('records', []))
        self.dirty = False
        self.proposals = []
        self.candidate_table.setRowCount(0)
        self.history.clear()
        self.preview.vertices = []
        self.preview.set_image(result['image'])
        self._render_records()
        self.message.setText(f"{result['name']} · {result['width']} × {result['height']} · {len(self.records)} 个目标")

    def _render_records(self):
        selected = self.targets.currentRow()
        self.targets.blockSignals(True)
        self.targets.setRowCount(len(self.records))
        for i, record in enumerate(self.records):
            self.targets.setItem(i, 0, QTableWidgetItem(str(i+1)))
            category = _combo([(str(c) + ' · ' + name, c) for c, name in enumerate(self.dataset['names'])])
            category.setCurrentIndex(max(0, category.findData(record['classId'])))
            category.currentIndexChanged.connect(lambda _, index=i, widget=category: self.change_category(index, widget.currentData()))
            self.targets.setCellWidget(i, 1, category)
        self.targets.blockSignals(False)
        if self.records:
            self.targets.selectRow(max(0, min(selected, len(self.records)-1)))
            self.select_record()
        else:
            self.coordinates.setRowCount(0)
        self.preview.records = deepcopy(self.records)
        self.preview.redraw()

    def change_category(self, index, value):
        self.records[index]['classId'] = value
        self.dirty = True
        self.preview.records = deepcopy(self.records)
        self.preview.redraw()

    def add_record(self, record):
        if not self.loaded or self._busy():
            return
        self.records.append(record)
        self.dirty = True
        self._render_records()
        self.targets.selectRow(len(self.records)-1)

    def _finish_polygon(self):
        self.preview.finish_polygon()

    def select_record(self):
        row = self.targets.currentRow()
        if not 0 <= row < len(self.records):
            return
        record = self.records[row]
        box = 'box' in record
        self.coordinates.setColumnCount(4 if box else 2)
        self.coordinates.setHorizontalHeaderLabels(['中心 X', '中心 Y', '宽度', '高度'] if box else ['X', 'Y'])
        values = [record['box']] if box else record['points']
        self.coordinates.setRowCount(len(values))
        for r, coords in enumerate(values):
            for c, value in enumerate(coords):
                editor = _number(0, 1, value)
                editor.valueChanged.connect(lambda v, r=r, c=c, index=row, box=box: self.change_coordinate(index, r, c, v, box))
                self.coordinates.setCellWidget(r, c, editor)

    def change_coordinate(self, index, row, col, value, box):
        record = self.records[index]
        if box:
            record['box'][col] = value
        else:
            record['points'][row][col] = value
        self.dirty = True
        self.preview.records = deepcopy(self.records)
        self.preview.redraw()

    def remove_record(self):
        row = self.targets.currentRow()
        if 0 <= row < len(self.records):
            self.records.pop(row)
            self.dirty = True
            self._render_records()

    def remove_vertex(self):
        target, row = self.targets.currentRow(), self.coordinates.currentRow()
        if 0 <= target < len(self.records) and row >= 0 and len(self.records[target].get('points', [])) > 3:
            self.records[target]['points'].pop(row)
            self.dirty = True
            self._render_records()
            self.select_record()

    def clear_records(self):
        self.records = []
        self.dirty = True
        self._render_records()

    def _identity(self):
        return {key: self.loaded[key] for key in ('name', 'split', 'revision')}

    def save(self):
        if self.loaded:
            self._call('save', {**self._identity(), 'records': deepcopy(self.records)}, self._saved)

    def _saved(self, result):
        self.loaded['revision'] = result['revision']
        self.dirty = False
        self.message.setText(f"标注已保存：{result['objects']} 个目标；{('空标注表示背景' if not result['objects'] else '历史版本已保留')}")
        self.refresh()

    def upload(self):
        filenames, _ = QFileDialog.getOpenFileNames(self, '导入训练图片', '', '图像 (*.png *.jpg *.jpeg *.bmp)')
        self._upload_queue = [(filename, self.split.currentData()) for filename in filenames]
        self._upload_next()

    def _upload_next(self, _result=None):
        if not self._upload_queue:
            self.refresh()
            return
        filename, split = self._upload_queue.pop(0)
        path = Path(filename)
        try:
            if path.stat().st_size > 12_000_000:
                raise ValueError('图片不能超过 12 MB')
            image = base64.b64encode(path.read_bytes()).decode('ascii')
        except (OSError, ValueError) as error:
            self.message.setText(str(error))
            self._upload_queue.clear()
            return
        self._call('upload', {'name': path.name, 'split': split, 'image': image}, self._upload_next)

    def load_history(self):
        self._call('history', self._identity(), self._history)

    def _history(self, result):
        self.history.clear()
        for entry in result.get('entries', []):
            if entry.get('valid'):
                title = datetime.fromtimestamp(entry['createdAt']/1000).strftime('%Y-%m-%d %H:%M:%S') + ' · ' + str(entry.get('objects', 0)) + ' 个目标'
                self.history.addItem(title, entry['id'])
        self.message.setText(f'找到 {self.history.count()} 个可载入的备份版本。载入后需点击保存才能更新标注。')

    def restore_history(self):
        if self._discard() and self.history.currentData():
            self._call('history_load', {**self._identity(), 'historyId': self.history.currentData()}, self._restored)

    def _restored(self, result):
        self.records = deepcopy(result['records'])
        self.dirty = True
        self._render_records()
        self.message.setText('已载入备份供编辑；点击保存后才会更新当前标注。')

    def suggest(self):
        self._call('suggest', {**self._identity(), 'model': self.model.currentText(), 'confidence': self.confidence.value(), 'device': 'cpu'}, self._suggested)

    def _suggested(self, result):
        self.proposals = result.get('proposals', [])
        _rows(self.candidate_table, [[p['label'], f"{p['confidence']:.3f}", ''] for p in self.proposals])
        for row, proposal in enumerate(self.proposals):
            categories = [('不采用', None)] + [(str(i) + ' · ' + name, i) for i, name in enumerate(self.dataset['names'])]
            widget = _combo(categories)
            if proposal['label'] in self.dataset['names']:
                widget.setCurrentIndex(self.dataset['names'].index(proposal['label'])+1)
            self.candidate_table.setCellWidget(row, 2, widget)
        self.message.setText(f'生成 {len(self.proposals)} 个候选；{len(result.get("rejected", []))} 项需人工绘制。逐项确认类别后加入，再保存标注。')

    def accept_proposal(self):
        row = self.candidate_table.currentRow()
        if not 0 <= row < len(self.proposals):
            return
        class_id = self.candidate_table.cellWidget(row, 2).currentData()
        if class_id is None:
            self.message.setText('请先为候选选择数据集类别。')
            return
        proposal = self.proposals.pop(row)
        record = {key: deepcopy(proposal[key]) for key in ('box', 'points') if key in proposal}
        record['classId'] = class_id
        self.add_record(record)
        self.candidate_table.removeRow(row)
        self._buttons()


class ContinuousDialog(_RpcDialog):
    """Owned continuous/queued sessions survive hiding, and stop on app shutdown."""
    busy_changed = Signal(bool)
    result_ready = Signal(dict)

    def __init__(self, document, backend, parent=None):
        super().__init__(backend, parent)
        self.document = document
        self.input_frame = {}
        self.states = {'continuous': {'state': 'idle'}, 'mqtt': {'state': 'idle'}}
        self.external_busy = False
        self._announced_busy = False
        self._last_result_id = None
        self.setWindowTitle('连续检测与事件触发')
        self.resize(920, 800)
        outer = QVBoxLayout(self)
        self.project_label = QLabel()
        outer.addWidget(self.project_label)
        hint = QLabel('启动时使用当前工程与输入快照。窗口关闭后继续运行；停止会话或退出应用时结束。执行期间编辑工程不会改变正在运行的快照。')
        hint.setWordWrap(True)
        outer.addWidget(hint)
        self.tabs = QTabWidget()
        outer.addWidget(self.tabs, 1)
        continuous_page = QWidget()
        continuous_layout = QVBoxLayout(continuous_page)
        form = QFormLayout()
        self.interval = _spin(100, 3600000, 1000)
        self.max_cycles = _spin(0, 1000000, 0)
        self.max_cycles.setSpecialValueText('持续运行，直到停止')
        self.trust_continuous = QCheckBox('允许本次连续会话运行工程中的可信 Python 脚本')
        form.addRow('轮次间隔 (ms)', self.interval)
        form.addRow('执行次数', self.max_cycles)
        form.addRow(self.trust_continuous)
        continuous_layout.addLayout(form)
        actions = QHBoxLayout()
        self.start_button = _button('启动连续检测', self.start_continuous, actions)
        self.stop_button = _button('停止连续检测', self.stop_continuous, actions)
        continuous_layout.addLayout(actions)
        self.continuous_table = _table(['连续检测状态', '值'])
        continuous_layout.addWidget(self.continuous_table, 1)
        self.tabs.addTab(continuous_page, '按间隔连续检测')
        mqtt_page = QWidget()
        mqtt_layout = QVBoxLayout(mqtt_page)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.mqtt_config = QWidget()
        mqtt_form = QFormLayout(self.mqtt_config)
        self.connection = _combo([('本机 MQTT 模拟器', 'simulator'), ('外部 MQTT Broker', 'broker')])
        self.host = QLineEdit('127.0.0.1')
        self.port = _spin(1, 65535, 1883)
        self.topic = QLineEdit('sieans/inspection')
        self.encoding = _combo([('结构化消息', 'structured'), ('文本', 'text'), ('字节数组', 'bytes')])
        self.qos = _combo([('0 · 至多一次', 0), ('1 · 至少一次', 1), ('2 · 恰好一次', 2)])
        self.qos.setCurrentIndex(1)
        self.timeout = _spin(100, 60000, 5000)
        self.client_id = QLineEdit()
        self.username = QLineEdit()
        self.password_env = QLineEdit()
        self.password_env.setPlaceholderText('保存密码的环境变量名称')
        self.security = _combo([('普通连接', 'plain'), ('TLS 加密', 'tls')])
        self.ca_file = QLineEdit()
        self.client_certificate = QLineEdit()
        self.private_key = QLineEdit()
        self.key_password_env = QLineEdit()
        self.accept_retained = QCheckBox('接收保留消息')
        self.variable = QLineEdit('mqttEvent')
        self.key_field = QLineEdit()
        self.key_field.setPlaceholderText('例如 requestId；留空不去重')
        self.capacity = _spin(1, 100, 20)
        self.max_age = _spin(100, 3600000, 30000)
        self.reconnect_ms = _spin(200, 60000, 1000)
        self.overflow = _combo([('停止会话', 'stop'), ('丢弃最早消息', 'dropOldest'), ('丢弃最新消息', 'dropNewest')])
        self.trust_mqtt = QCheckBox('允许本次事件会话运行工程中的可信 Python 脚本')
        for label, editor in [('连接方式', self.connection), ('Broker 主机', self.host), ('端口', self.port), ('主题', self.topic), ('消息格式', self.encoding), ('QoS', self.qos), ('订阅超时 (ms)', self.timeout), ('客户端标识（留空自动生成）', self.client_id), ('用户名', self.username), ('密码环境变量', self.password_env), ('连接安全', self.security), ('CA 证书文件', self.ca_file), ('客户端证书文件', self.client_certificate), ('客户端私钥文件', self.private_key), ('私钥密码环境变量', self.key_password_env), ('事件变量名', self.variable), ('去重字段路径', self.key_field), ('队列容量', self.capacity), ('消息有效期 (ms)', self.max_age), ('重连间隔 (ms)', self.reconnect_ms), ('队列溢出策略', self.overflow)]:
            mqtt_form.addRow(label, editor)
        mqtt_form.addRow(self.accept_retained)
        mqtt_form.addRow(self.trust_mqtt)
        scroll.setWidget(self.mqtt_config)
        mqtt_layout.addWidget(scroll, 1)
        actions = QHBoxLayout()
        self.mqtt_start_button = _button('启动事件订阅', self.start_mqtt, actions)
        self.mqtt_stop_button = _button('停止事件订阅', self.stop_mqtt, actions)
        self.test_button = _button('向模拟器发送测试事件', self.test_mqtt, actions)
        mqtt_layout.addLayout(actions)
        self.mqtt_table = _table(['事件触发状态', '值'])
        self.mqtt_table.setMaximumHeight(230)
        mqtt_layout.addWidget(self.mqtt_table)
        self.tabs.addTab(mqtt_page, 'MQTT 事件触发')
        outer.addWidget(self.message)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)
        self.connection.currentIndexChanged.connect(self._buttons)
        self.security.currentIndexChanged.connect(self._buttons)
        document.changed.connect(self._project_changed)
        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.refresh)
        self._project_changed()
        self._buttons()

    def set_input(self, image='', cloud=None, depth=None):
        self.input_frame = {'image': image}
        if cloud is not None:
            self.input_frame['cloud'] = deepcopy(cloud)
        if depth is not None:
            self.input_frame['depth'] = deepcopy(depth)

    def _project_changed(self):
        self.project_label.setText('当前工程：' + self.document.project.get('name', '') + ' · ' + str(len(self.document.project.get('steps', []))) + ' 个模块')

    def set_busy(self, busy):
        self.external_busy = bool(busy)
        self._buttons()

    def showEvent(self, event):
        super().showEvent(event)
        self.timer.start()
        self.refresh()

    def hideEvent(self, event):
        if not any(state.get('busy') for state in self.states.values()):
            self.timer.stop()
        super().hideEvent(event)

    def refresh(self):
        if not self.backend.is_ready:
            return
        for kind in self.states:
            if not self._has(kind + '/status'):
                self._request(kind + '/status', callback=lambda state, kind=kind: self._state(kind, state), kind='status')

    def _buttons(self, *_):
        if not hasattr(self, 'mqtt_start_button'):
            return
        active = any(state.get('busy') for state in self.states.values())
        busy = active or self._busy() or self.external_busy or not self.backend.is_ready
        for widget in (self.start_button, self.mqtt_start_button, self.interval, self.max_cycles, self.trust_continuous, self.mqtt_config):
            widget.setEnabled(not busy)
        self.stop_button.setEnabled(self.states['continuous'].get('busy', False) and not self._has('continuous/stop'))
        self.mqtt_stop_button.setEnabled(self.states['mqtt'].get('busy', False) and not self._has('mqtt/stop'))
        mqtt = self.states['mqtt']
        self.test_button.setEnabled(mqtt.get('state') == 'subscribed' and mqtt.get('config', {}).get('connection', {}).get('connection') == 'simulator' and not self._has('mqtt/test'))
        broker = self.connection.currentData() == 'broker'
        for widget in (self.host, self.port, self.username, self.password_env, self.security):
            widget.setEnabled(not busy and broker)
        tls = broker and self.security.currentData() == 'tls'
        for widget in (self.ca_file, self.client_certificate, self.private_key, self.key_password_env):
            widget.setEnabled(not busy and tls)

    def _snapshot(self):
        return {'project': deepcopy(self.document.project), **deepcopy(self.input_frame)}

    def start_continuous(self):
        params = dict(**self._snapshot(), intervalMs=self.interval.value(), maxCycles=self.max_cycles.value(), allowScripts=self.trust_continuous.isChecked())
        self.trust_continuous.setChecked(False)
        self._request('continuous/start', params, lambda state: self._state('continuous', state))

    def stop_continuous(self):
        self._request('continuous/stop', {'id': self.states['continuous'].get('id')}, lambda state: self._state('continuous', state))

    def start_mqtt(self):
        connection = dict(connection=self.connection.currentData(), topic=self.topic.text().strip(), encoding=self.encoding.currentData(), qos=self.qos.currentData(), timeoutMs=self.timeout.value(), clientId=self.client_id.text().strip(), acceptRetained=self.accept_retained.isChecked())
        if connection['connection'] == 'broker':
            connection.update(host=self.host.text().strip(), port=self.port.value(), security=self.security.currentData())
            for key, editor in [('username', self.username), ('passwordEnv', self.password_env), ('caFile', self.ca_file), ('clientCertificate', self.client_certificate), ('privateKey', self.private_key), ('keyPasswordEnv', self.key_password_env)]:
                if editor.text().strip():
                    connection[key] = editor.text().strip()
        params = dict(**self._snapshot(), connection=connection, variable=self.variable.text().strip(), keyField=self.key_field.text().strip(), capacity=self.capacity.value(), maxAgeMs=self.max_age.value(), reconnectMs=self.reconnect_ms.value(), overflow=self.overflow.currentData(), allowScripts=self.trust_mqtt.isChecked())
        self.trust_mqtt.setChecked(False)
        self._request('mqtt/start', params, lambda state: self._state('mqtt', state))

    def stop_mqtt(self):
        self._request('mqtt/stop', {'id': self.states['mqtt'].get('id')}, lambda state: self._state('mqtt', state))

    def test_mqtt(self):
        self._request('mqtt/test', callback=lambda _: self.message.setText('模拟事件已发送。'))

    def _state(self, kind, state):
        self.states[kind] = state
        labels = dict(idle='未启动', running='执行中', waiting='等待下一轮', stopping='正在停止', stopped='已停止', completed='已完成', failed='执行失败', interrupted='应用中断', connecting='正在连接', subscribed='正在订阅', reconnecting='正在重连')
        rows = [('状态', labels.get(state.get('state'), state.get('state'))), ('工程', state.get('projectName')), ('会话编号', state.get('id'))]
        if kind == 'continuous':
            rows += [('已开始轮次', state.get('startedCycles', 0)), ('已完成轮次', state.get('completedCycles', 0)), ('失败轮次', state.get('failedCycles', 0)), ('取消轮次', state.get('cancelledCycles', 0)), ('目标轮次', state.get('maxCycles') or '直到停止'), ('上轮耗时 (ms)', state.get('lastElapsedMs', 0))]
        else:
            rows += [(label, state.get(key, 0)) for key, label in [('received', '收到消息'), ('completed', '完成事件'), ('failed', '失败事件'), ('queued', '排队消息'), ('dropped', '丢弃消息'), ('expired', '过期消息'), ('duplicates', '重复消息'), ('invalid', '无效消息'), ('reconnects', '重连次数')]]
        rows += [('最近任务编号', state.get('lastJobId')), ('错误', state.get('error') or state.get('connectionError'))]
        _rows(self.continuous_table if kind == 'continuous' else self.mqtt_table, rows)
        if state.get('lastJobId') and state['lastJobId'] != self._last_result_id and state.get('projectId') == self.document.project.get('id') and not self._has('runtime/view'):
            self._request('runtime/view', {'project': deepcopy(self.document.project)}, self._runtime_view, kind='status')
        active = any(s.get('busy') for s in self.states.values())
        if active != self._announced_busy:
            self._announced_busy = active
            self.busy_changed.emit(active)
        if active:
            self.timer.start()
        elif not self.isVisible():
            self.timer.stop()

    def _runtime_view(self, view):
        status = view.get('status', {})
        if status.get('state') not in ('completed', 'failed', 'cancelled') or status.get('id') == self._last_result_id:
            return
        if view.get('projectId') != self.document.project.get('id'):
            return
        self._last_result_id = status.get('id')
        self.result_ready.emit({**deepcopy(status), 'results': deepcopy(view.get('results', [])),
                                'variables': deepcopy(view.get('variables', {})), 'monitor': deepcopy(view.get('monitor', {}))})
