"""通信管理 — VisionMaster p=10 统一设备/收发/心跳壳.

集中配置通讯设备（TCP/UDP/串口/MQTT/Modbus…）；流程内收发算子可引用设备名。
持久化到 project.commManager；流程 send/receive_data 经引擎 lib/comm-bus（Local Bus / TCP·UDP socket）。
"""
from copy import deepcopy
import socket
import threading
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTabWidget,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QComboBox, QLineEdit, QWidget, QFormLayout, QSpinBox, QMessageBox,
    QSplitter, QListWidget, QListWidgetItem, QGroupBox, QPlainTextEdit,
)

from desktop.widgets.switch import OrangeSwitch


def parse_var_ref(raw):
    """Parse 'flow.xxx' / 'global.xxx' / 'g.xxx' / bare → (scope, name). Default scope=flow."""
    text = (raw or '').strip()
    if not text:
        return 'flow', ''
    lower = text.lower()
    for prefix, scope in (('flow.', 'flow'), ('global.', 'global'), ('g.', 'global')):
        if lower.startswith(prefix):
            return scope, text[len(prefix):].strip()
    return 'flow', text


def write_project_variable(project, raw_ref, value):
    """Design-time write into project.variables (flow) or project.globalVariables.
    Also mirrors into variables['global'] if that nested dict already exists.
    Returns (scope, name) or (None, '') if empty ref.
    """
    scope, name = parse_var_ref(raw_ref)
    if not name:
        return None, ''
    project = project if isinstance(project, dict) else {}
    variables = project.setdefault('variables', {})
    if not isinstance(variables, dict):
        variables = {}
        project['variables'] = variables
    if scope == 'global':
        gvars = project.setdefault('globalVariables', {})
        if not isinstance(gvars, dict):
            gvars = {}
            project['globalVariables'] = gvars
        gvars[name] = value
        if isinstance(variables.get('global'), dict):
            variables['global'][name] = value
        # also stamp a marker so Variables dialog can see persist hint
        persist = project.setdefault('variablePersist', {})
        if isinstance(persist, dict) and name not in persist:
            persist[name] = True
    else:
        variables[name] = value
    return scope, name


def read_project_variable(project, raw_ref, default=''):
    scope, name = parse_var_ref(raw_ref)
    if not name:
        return default
    project = project or {}
    variables = project.get('variables') or {}
    if scope == 'global':
        gvars = project.get('globalVariables') or {}
        if isinstance(gvars, dict) and name in gvars:
            return gvars[name]
        if isinstance(variables.get('global'), dict) and name in variables['global']:
            return variables['global'][name]
        return default
    if isinstance(variables, dict) and name in variables:
        return variables[name]
    return default


PROTOCOLS = [
    'Local Bus', 'TCP Client', 'TCP Server', 'UDP', 'Serial', 'MQTT', 'Modbus TCP', 'Modbus RTU', 'OPC UA', 'S7',
]


def default_comm_manager():
    return dict(
        devices=[],
        recvEvents=[],
        sendEvents=[],
        heartbeat=dict(enabled=False, intervalMs=5000, payload='HB'),
        response=dict(enabled=False, timeoutMs=3000, ack='OK'),
    )


def ensure_comm_manager(project):
    cm = project.setdefault('commManager', default_comm_manager())
    for key, default in default_comm_manager().items():
        cm.setdefault(key, deepcopy(default) if not isinstance(default, dict) else dict(default))
    cm.setdefault('devices', [])
    cm.setdefault('recvEvents', [])
    cm.setdefault('sendEvents', [])
    cm.setdefault('heartbeat', dict(enabled=False, intervalMs=5000, payload='HB'))
    cm.setdefault('response', dict(enabled=False, timeoutMs=3000, ack='OK'))
    # Seed LocalLoop so send/receive_data can demo without external peers.
    devices = cm.get('devices')
    if isinstance(devices, list):
        names = {(d.get('name') or '') for d in devices if isinstance(d, dict)}
        if 'LocalLoop' not in names and not devices:
            devices.append(dict(
                name='LocalLoop', protocol='Local Bus', host='', port=0,
                enabled=True, remark='进程内事件总线（桌面演示；流程 send↔receive 同进程互通）',
            ))
        elif 'LocalLoop' not in names:
            # Prefer keeping user devices; still offer LocalLoop at front for demos
            devices.insert(0, dict(
                name='LocalLoop', protocol='Local Bus', host='', port=0,
                enabled=True, remark='进程内事件总线（桌面演示）',
            ))
    return cm


class _EventTable(QWidget):
    """收发事件表：设备 + 报文 + 流程变量绑定（p10/11）。"""
    COLS = ['序号', '事件名', '绑定设备', '报文/主题', '流程变量', '操作']

    def __init__(self, parent=None, var_role='write'):
        super().__init__(parent)
        self._var_role = var_role  # write=接收写变量；read=发送读变量
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        tip = QLabel(
            '接收：报文写入「流程变量」；发送：从「流程变量」取文本（空则用报文列）。'
            if var_role == 'write' else
            '发送事件可绑定流程变量；运行时 send_data 优先读该变量。'
        )
        tip.setWordWrap(True)
        tip.setStyleSheet('color:#888;font-size:11px;')
        lay.addWidget(tip)
        self.table = QTableWidget(0, 6)
        labels = list(self.COLS)
        if var_role == 'write':
            labels[4] = '写变量'
        else:
            labels[4] = '读变量'
        self.table.setHorizontalHeaderLabels(labels)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        lay.addWidget(self.table, 1)
        bar = QHBoxLayout()
        add = QPushButton('添加')
        add.clicked.connect(lambda: self._append({}))
        bar.addWidget(add)
        if var_role == 'write':
            sim = QPushButton('模拟写回变量')
            sim.setToolTip('把「报文」列写入绑定的流程/全局变量（设计态联调）')
            sim.clicked.connect(self._simulate_writeback)
            bar.addWidget(sim)
        else:
            fill = QPushButton('从变量填报文')
            fill.setToolTip('用绑定变量当前值覆盖「报文」列（设计态预览）')
            fill.clicked.connect(self._fill_from_variables)
            bar.addWidget(fill)
        bar.addStretch(1)
        lay.addLayout(bar)


    def bind_document(self, document):
        self._document = document

    def _simulate_writeback(self):
        doc = getattr(self, '_document', None)
        if doc is None:
            QMessageBox.information(self, '接收事件', '无工程文档，无法写变量。')
            return
        written = []
        p = deepcopy(doc.project)
        for row in self.rows():
            var = (row.get('variable') or '').strip()
            if not var:
                continue
            msg = row.get('message') or row.get('topic') or ''
            scope, name = write_project_variable(p, var, msg)
            if name:
                written.append(f'{scope}.{name}')
        if written:
            doc.commit(p)
            QMessageBox.information(self, '接收事件', '已写回：\n' + '\n'.join(written))
        else:
            QMessageBox.information(self, '接收事件', '没有绑定变量的事件行。')

    def _fill_from_variables(self):
        doc = getattr(self, '_document', None)
        if doc is None:
            return
        p = doc.project or {}
        for r in range(self.table.rowCount()):
            var_w = self.table.cellWidget(r, 4)
            msg_w = self.table.cellWidget(r, 3)
            if not var_w or not msg_w:
                continue
            ref = var_w.text().strip()
            if not ref:
                continue
            val = read_project_variable(p, ref, '')
            if val is None:
                continue
            msg_w.setText(str(val))

    def set_rows(self, rows, devices=None):
        self._devices = list(devices or [])
        self.table.setRowCount(0)
        for row in rows or []:
            self._append(row, emit=False)

    def _device_names(self):
        return self._devices if getattr(self, '_devices', None) else []

    def _append(self, row, emit=False):
        row = row or {}
        r = self.table.rowCount()
        self.table.insertRow(r)
        seq = QTableWidgetItem(str(r + 1))
        seq.setFlags(seq.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.table.setItem(r, 0, seq)
        name = QLineEdit(str(row.get('name') or f'事件{r + 1}'))
        self.table.setCellWidget(r, 1, name)
        dev = QComboBox()
        dev.addItem('（未绑定）', '')
        for d in self._device_names():
            dev.addItem(d, d)
        cur = row.get('device') or ''
        idx = max(0, dev.findData(cur))
        if cur and idx == 0 and cur:
            dev.addItem(cur, cur)
            idx = dev.findData(cur)
        dev.setCurrentIndex(max(0, idx))
        self.table.setCellWidget(r, 2, dev)
        msg = QLineEdit(str(row.get('message') or row.get('topic') or ''))
        msg.setPlaceholderText('报文 / Topic / 寄存器…')
        self.table.setCellWidget(r, 3, msg)
        var = QLineEdit(str(row.get('variable') or row.get('var') or ''))
        var.setPlaceholderText('flow.xxx' if self._var_role == 'write' else 'flow.payload')
        self.table.setCellWidget(r, 4, var)
        rm = QPushButton('删')
        rm.setFixedWidth(36)
        rm.clicked.connect(lambda *_ , rr=r: self._remove(rr))
        self.table.setCellWidget(r, 5, rm)

    def _remove(self, row):
        if 0 <= row < self.table.rowCount():
            self.table.removeRow(row)
            for r in range(self.table.rowCount()):
                item = self.table.item(r, 0)
                if item:
                    item.setText(str(r + 1))

    def rows(self):
        out = []
        for r in range(self.table.rowCount()):
            name_w = self.table.cellWidget(r, 1)
            dev_w = self.table.cellWidget(r, 2)
            msg_w = self.table.cellWidget(r, 3)
            var_w = self.table.cellWidget(r, 4)
            out.append(dict(
                name=name_w.text().strip() if name_w else '',
                device=dev_w.currentData() if dev_w else '',
                message=msg_w.text().strip() if msg_w else '',
                topic=msg_w.text().strip() if msg_w else '',
                variable=var_w.text().strip() if var_w else '',
            ))
        return out


class CommManagerDialog(QDialog):
    """通信管理：设备管理 / 接收事件 / 发送事件 / 心跳 / 响应."""

    def __init__(self, document, parent=None):
        super().__init__(parent)
        self.document = document
        self.setWindowTitle('通信管理')
        self.resize(920, 560)
        root = QVBoxLayout(self)
        title = QLabel('通信管理')
        title.setObjectName('dialogTitle')
        root.addWidget(title)
        hint = QLabel(
            '对齐 VisionMaster「通信管理」：集中配置设备与收发事件；'
            '流程中的「发送/接收数据」与 TCP/串口算子可引用此处设备名；Local Bus=进程内事件总线（同流程 send↔recv）。配置随方案保存。'
        )
        hint.setObjectName('dialogHint')
        hint.setWordWrap(True)
        root.addWidget(hint)

        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)

        # --- 设备管理 ---
        devices_page = QWidget()
        split = QSplitter(Qt.Orientation.Horizontal)
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        row = QHBoxLayout()
        row.addWidget(QLabel('设备列表'), 1)
        add_btn = QPushButton('+')
        add_btn.setFixedWidth(28)
        add_btn.clicked.connect(self._add_device)
        row.addWidget(add_btn)
        rm_btn = QPushButton('−')
        rm_btn.setFixedWidth(28)
        rm_btn.clicked.connect(self._remove_device)
        row.addWidget(rm_btn)
        ll.addLayout(row)
        self.device_list = QListWidget()
        self.device_list.currentRowChanged.connect(self._load_device_form)
        ll.addWidget(self.device_list, 1)
        split.addWidget(left)

        right = QWidget()
        form = QFormLayout(right)
        form.setContentsMargins(12, 8, 12, 8)
        self.dev_name = QLineEdit()
        self.dev_proto = QComboBox()
        self.dev_proto.addItems(PROTOCOLS)
        self.dev_host = QLineEdit()
        self.dev_host.setPlaceholderText('主机 / 串口路径')
        self.dev_port = QSpinBox()
        self.dev_port.setRange(0, 65535)
        self.dev_port.setValue(502)
        self.dev_enabled = OrangeSwitch(True)
        self.dev_remark = QLineEdit()
        form.addRow('设备名称', self.dev_name)
        form.addRow('协议', self.dev_proto)
        form.addRow('主机/路径', self.dev_host)
        form.addRow('端口', self.dev_port)
        form.addRow('启用', self.dev_enabled)
        form.addRow('备注', self.dev_remark)
        apply_btn = QPushButton('应用当前设备')
        apply_btn.clicked.connect(self._apply_device_form)
        form.addRow(apply_btn)
        tip = QLabel('协议参数为设计态壳；具体读写仍由流程通讯算子执行。')
        tip.setWordWrap(True)
        tip.setStyleSheet('color:#888;')
        form.addRow(tip)
        split.addWidget(right)
        split.setStretchFactor(1, 2)
        dv = QVBoxLayout(devices_page)
        dv.addWidget(split)
        self.tabs.addTab(devices_page, '设备管理')

        # --- 接收 / 发送事件 ---
        self.recv_table = _EventTable(var_role='write')
        self.send_table = _EventTable(var_role='read')
        self.recv_table.bind_document(self.document)
        self.send_table.bind_document(self.document)
        self.tabs.addTab(self.recv_table, '接收事件')
        self.tabs.addTab(self.send_table, '发送事件')

        # --- 心跳 ---
        hb = QWidget()
        hb_form = QFormLayout(hb)
        hb_form.setContentsMargins(12, 12, 12, 12)
        self.hb_enabled = OrangeSwitch(False)
        self.hb_interval = QSpinBox()
        self.hb_interval.setRange(100, 3600000)
        self.hb_interval.setValue(5000)
        self.hb_payload = QLineEdit('HB')
        hb_form.addRow('启用心跳', self.hb_enabled)
        hb_form.addRow('间隔(ms)', self.hb_interval)
        hb_form.addRow('心跳报文', self.hb_payload)
        self.tabs.addTab(hb, '心跳')

        # --- 响应 ---
        resp = QWidget()
        resp_form = QFormLayout(resp)
        resp_form.setContentsMargins(12, 12, 12, 12)
        self.resp_enabled = OrangeSwitch(False)
        self.resp_timeout = QSpinBox()
        self.resp_timeout.setRange(0, 120000)
        self.resp_timeout.setValue(3000)
        self.resp_ack = QLineEdit('OK')
        resp_form.addRow('启用应答', self.resp_enabled)
        resp_form.addRow('超时(ms)', self.resp_timeout)
        resp_form.addRow('应答内容', self.resp_ack)
        self.tabs.addTab(resp, '响应')

        # --- TCP 测试（对标 VM 通信管理连通性）---
        tcp = QWidget()
        tcp_lay = QVBoxLayout(tcp)
        tcp_lay.setContentsMargins(12, 12, 12, 12)
        tip = QLabel('选用设备管理中的 TCP Client/Server，或手动填写主机/端口，发送一行文本并读回（短超时）。')
        tip.setWordWrap(True)
        tip.setStyleSheet('color:#666;')
        tcp_lay.addWidget(tip)
        form = QFormLayout()
        self.tcp_device = QComboBox()
        self.tcp_device.setEditable(False)
        self.tcp_host = QLineEdit('127.0.0.1')
        self.tcp_port = QSpinBox(); self.tcp_port.setRange(1, 65535); self.tcp_port.setValue(9000)
        self.tcp_payload = QLineEdit('PING')
        self.tcp_timeout = QSpinBox(); self.tcp_timeout.setRange(100, 30000); self.tcp_timeout.setValue(2000)
        self.tcp_timeout.setSuffix(' ms')
        form.addRow('设备', self.tcp_device)
        form.addRow('主机', self.tcp_host)
        form.addRow('端口', self.tcp_port)
        form.addRow('发送', self.tcp_payload)
        form.addRow('超时', self.tcp_timeout)
        tcp_lay.addLayout(form)
        row = QHBoxLayout()
        self.tcp_send_btn = QPushButton('发送并读回')
        self.tcp_send_btn.setObjectName('primaryButton')
        self.tcp_send_btn.clicked.connect(self._tcp_test_send)
        self.tcp_fill_btn = QPushButton('从当前设备填充')
        self.tcp_fill_btn.clicked.connect(self._tcp_fill_from_device)
        row.addWidget(self.tcp_fill_btn)
        row.addStretch(1)
        row.addWidget(self.tcp_send_btn)
        tcp_lay.addLayout(row)
        vrow = QHBoxLayout()
        vrow.addWidget(QLabel('读回写变量'))
        self.tcp_var_scope = QComboBox()
        self.tcp_var_scope.addItem('流程', 'flow')
        self.tcp_var_scope.addItem('全局', 'global')
        self.tcp_var_edit = QLineEdit()
        self.tcp_var_edit.setPlaceholderText('可选，如 tcpLastRecv 或 flow.xxx')
        vrow.addWidget(self.tcp_var_scope)
        vrow.addWidget(self.tcp_var_edit, 1)
        tcp_lay.addLayout(vrow)
        self.tcp_log = QPlainTextEdit()
        self.tcp_log.setReadOnly(True)
        self.tcp_log.setPlaceholderText('测试日志…')
        tcp_lay.addWidget(self.tcp_log, 1)

        self.tabs.addTab(tcp, 'TCP 测试')

        # --- UDP 测试（薄壳）---
        udp = QWidget()
        udp_lay = QVBoxLayout(udp)
        udp_lay.setContentsMargins(12, 12, 12, 12)
        udp_lay.addWidget(QLabel('向目标主机发 UDP 报文并等待短时回包（设计态连通性）。'))
        uform = QFormLayout()
        self.udp_host = QLineEdit('127.0.0.1')
        self.udp_port = QSpinBox(); self.udp_port.setRange(1, 65535); self.udp_port.setValue(9001)
        self.udp_payload = QLineEdit('PING')
        self.udp_timeout = QSpinBox(); self.udp_timeout.setRange(100, 10000); self.udp_timeout.setValue(1500)
        self.udp_timeout.setSuffix(' ms')
        uform.addRow('主机', self.udp_host)
        uform.addRow('端口', self.udp_port)
        uform.addRow('发送', self.udp_payload)
        uform.addRow('超时', self.udp_timeout)
        udp_lay.addLayout(uform)
        urow = QHBoxLayout()
        self.udp_send_btn = QPushButton('发送 UDP')
        self.udp_send_btn.setObjectName('primaryButton')
        self.udp_send_btn.clicked.connect(self._udp_test_send)
        urow.addStretch(1); urow.addWidget(self.udp_send_btn)
        udp_lay.addLayout(urow)
        uv = QHBoxLayout()
        uv.addWidget(QLabel('读回写变量'))
        self.udp_var_scope = QComboBox()
        self.udp_var_scope.addItem('流程', 'flow')
        self.udp_var_scope.addItem('全局', 'global')
        self.udp_var_edit = QLineEdit()
        self.udp_var_edit.setPlaceholderText('可选，如 udpLastRecv')
        uv.addWidget(self.udp_var_scope)
        uv.addWidget(self.udp_var_edit, 1)
        udp_lay.addLayout(uv)
        self.udp_log = QPlainTextEdit(); self.udp_log.setReadOnly(True)
        udp_lay.addWidget(self.udp_log, 1)
        self.tabs.addTab(udp, 'UDP 测试')

        # --- 串口测试（薄壳；无 pyserial 时提示）---
        ser = QWidget()
        ser_lay = QVBoxLayout(ser)
        ser_lay.setContentsMargins(12, 12, 12, 12)
        ser_lay.addWidget(QLabel('串口写一行并读回。设备管理中协议选 Serial，主机/路径填 /dev/ttyUSB0 或 COMx。'))
        sform = QFormLayout()
        self.ser_port = QLineEdit('/dev/ttyUSB0')
        self.ser_baud = QComboBox()
        for b in (9600, 19200, 38400, 57600, 115200, 230400):
            self.ser_baud.addItem(str(b), b)
        self.ser_baud.setCurrentIndex(4)
        self.ser_payload = QLineEdit('PING')
        self.ser_timeout = QSpinBox(); self.ser_timeout.setRange(100, 10000); self.ser_timeout.setValue(2000)
        self.ser_timeout.setSuffix(' ms')
        sform.addRow('端口路径', self.ser_port)
        sform.addRow('波特率', self.ser_baud)
        sform.addRow('发送', self.ser_payload)
        sform.addRow('超时', self.ser_timeout)
        ser_lay.addLayout(sform)
        srow = QHBoxLayout()
        self.ser_fill_btn = QPushButton('从 Serial 设备填充')
        self.ser_fill_btn.clicked.connect(self._ser_fill_from_device)
        self.ser_send_btn = QPushButton('发送并读回')
        self.ser_send_btn.setObjectName('primaryButton')
        self.ser_send_btn.clicked.connect(self._ser_test_send)
        srow.addWidget(self.ser_fill_btn); srow.addStretch(1); srow.addWidget(self.ser_send_btn)
        ser_lay.addLayout(srow)
        sv = QHBoxLayout()
        sv.addWidget(QLabel('读回写变量'))
        self.ser_var_scope = QComboBox()
        self.ser_var_scope.addItem('流程', 'flow')
        self.ser_var_scope.addItem('全局', 'global')
        self.ser_var_edit = QLineEdit()
        self.ser_var_edit.setPlaceholderText('可选，如 serLastRecv')
        sv.addWidget(self.ser_var_scope)
        sv.addWidget(self.ser_var_edit, 1)
        ser_lay.addLayout(sv)
        self.ser_log = QPlainTextEdit(); self.ser_log.setReadOnly(True)
        ser_lay.addWidget(self.ser_log, 1)
        self.tabs.addTab(ser, '串口测试')



        bar = QHBoxLayout()
        ok = QPushButton('确定')
        ok.setObjectName('primaryButton')
        ok.clicked.connect(self.accept_save)
        cancel = QPushButton('取消')
        cancel.clicked.connect(self.reject)
        bar.addStretch(1)
        bar.addWidget(ok)
        bar.addWidget(cancel)
        root.addLayout(bar)

        self._devices = []
        self._load_from_project()

    def _load_from_project(self):
        cm = ensure_comm_manager(deepcopy(self.document.project))
        self._devices = list(cm.get('devices') or [])
        self.device_list.clear()
        for d in self._devices:
            self.device_list.addItem(QListWidgetItem(d.get('name') or '未命名'))
        if self._devices:
            self.device_list.setCurrentRow(0)
        names = [d.get('name') or '' for d in self._devices]
        self.recv_table.set_rows(cm.get('recvEvents') or [], names)
        self.send_table.set_rows(cm.get('sendEvents') or [], names)
        prefs = cm.get('testPrefs') or {}
        last = str(prefs.get('lastVar') or '')
        if last:
            scope, name = parse_var_ref(last)
            for edit, sc in (
                (getattr(self, 'tcp_var_edit', None), getattr(self, 'tcp_var_scope', None)),
                (getattr(self, 'udp_var_edit', None), getattr(self, 'udp_var_scope', None)),
                (getattr(self, 'ser_var_edit', None), getattr(self, 'ser_var_scope', None)),
            ):
                if edit is not None and not edit.text().strip():
                    edit.setText(name)
                if sc is not None:
                    i = sc.findData(scope)
                    if i >= 0:
                        sc.setCurrentIndex(i)
        hb = cm.get('heartbeat') or {}
        self.hb_enabled.setChecked(bool(hb.get('enabled')))
        self.hb_interval.setValue(int(hb.get('intervalMs') or 5000))
        self.hb_payload.setText(str(hb.get('payload') or 'HB'))
        resp = cm.get('response') or {}
        self.resp_enabled.setChecked(bool(resp.get('enabled')))
        self.resp_timeout.setValue(int(resp.get('timeoutMs') or 3000))
        self.resp_ack.setText(str(resp.get('ack') or 'OK'))
        self._refresh_tcp_devices()

    def _add_device(self):
        n = len(self._devices) + 1
        self._devices.append(dict(
            name=f'通讯设备{n}', protocol='TCP Client', host='127.0.0.1',
            port=502, enabled=True, remark='',
        ))
        self.device_list.addItem(QListWidgetItem(self._devices[-1]['name']))
        self.device_list.setCurrentRow(self.device_list.count() - 1)
        self._refresh_event_devices()
        self._refresh_tcp_devices()

    def _remove_device(self):
        row = self.device_list.currentRow()
        if row < 0:
            return
        self.device_list.takeItem(row)
        del self._devices[row]
        self._refresh_event_devices()
        self._refresh_tcp_devices()
        if self._devices:
            self.device_list.setCurrentRow(min(row, len(self._devices) - 1))
        else:
            self._clear_device_form()

    def _clear_device_form(self):
        self.dev_name.clear()
        self.dev_proto.setCurrentIndex(0)
        self.dev_host.clear()
        self.dev_port.setValue(502)
        self.dev_enabled.setChecked(True)
        self.dev_remark.clear()

    def _load_device_form(self, row):
        if row < 0 or row >= len(self._devices):
            self._clear_device_form()
            return
        d = self._devices[row]
        self.dev_name.setText(d.get('name') or '')
        proto = d.get('protocol') or 'TCP Client'
        i = self.dev_proto.findText(proto)
        self.dev_proto.setCurrentIndex(i if i >= 0 else 0)
        self.dev_host.setText(str(d.get('host') or ''))
        self.dev_port.setValue(int(d.get('port') or 0))
        self.dev_enabled.setChecked(bool(d.get('enabled', True)))
        self.dev_remark.setText(str(d.get('remark') or ''))

    def _apply_device_form(self):
        row = self.device_list.currentRow()
        if row < 0:
            return
        name = self.dev_name.text().strip() or f'通讯设备{row + 1}'
        self._devices[row] = dict(
            name=name,
            protocol=self.dev_proto.currentText(),
            host=self.dev_host.text().strip(),
            port=int(self.dev_port.value()),
            enabled=bool(self.dev_enabled.isChecked()),
            remark=self.dev_remark.text().strip(),
        )
        self.device_list.item(row).setText(name)
        self._refresh_event_devices()

    def _refresh_event_devices(self):
        names = [d.get('name') or '' for d in self._devices]
        recv = self.recv_table.rows()
        send = self.send_table.rows()
        self.recv_table.set_rows(recv, names)
        self.send_table.set_rows(send, names)


    def _refresh_tcp_devices(self):
        names = []
        for d in self._devices:
            proto = (d.get('protocol') or '')
            if 'TCP' in proto.upper() or proto in ('TCP Client', 'TCP Server'):
                names.append(d.get('name') or '')
        cur = self.tcp_device.currentData() if self.tcp_device.count() else ''
        self.tcp_device.blockSignals(True)
        self.tcp_device.clear()
        self.tcp_device.addItem('（手动填写）', '')
        for n in names:
            if n:
                self.tcp_device.addItem(n, n)
        if cur:
            i = self.tcp_device.findData(cur)
            if i >= 0:
                self.tcp_device.setCurrentIndex(i)
        self.tcp_device.blockSignals(False)

    def _tcp_fill_from_device(self):
        name = self.tcp_device.currentData() or ''
        d = next((x for x in self._devices if (x.get('name') or '') == name), None)
        if not d:
            # fall back to selected device list row
            row = self.device_list.currentRow()
            if 0 <= row < len(self._devices):
                d = self._devices[row]
        if not d:
            self.tcp_log.appendPlainText('无设备可填充')
            return
        self.tcp_host.setText(str(d.get('host') or '127.0.0.1'))
        self.tcp_port.setValue(int(d.get('port') or 5001))
        self.tcp_log.appendPlainText(
            f"已填充 {d.get('name')} · {d.get('protocol')} · {d.get('host')}:{d.get('port')}"
        )

    def _tcp_test_send(self):
        import socket
        from datetime import datetime
        host = (self.tcp_host.text() or '').strip() or '127.0.0.1'
        port = int(self.tcp_port.value())
        payload = self.tcp_payload.text() or ''
        timeout_ms = int(self.tcp_timeout.value())
        ts = datetime.now().strftime('%H:%M:%S')
        self.tcp_log.appendPlainText(f'[{ts}] → {host}:{port}  {payload!r}')
        try:
            with socket.create_connection((host, port), timeout=timeout_ms / 1000.0) as sock:
                sock.settimeout(timeout_ms / 1000.0)
                data = (payload + '\n').encode('utf-8', errors='replace')
                sock.sendall(data)
                buf = b''
                try:
                    while len(buf) < 4096:
                        chunk = sock.recv(1024)
                        if not chunk:
                            break
                        buf += chunk
                        if b'\n' in buf:
                            break
                except socket.timeout:
                    pass
                text = buf.decode('utf-8', errors='replace')
                self.tcp_log.appendPlainText(f'[{ts}] ← {text!r} ({len(buf)} bytes)')
                self._commit_test_writeback(self.tcp_var_edit, self.tcp_var_scope, text, self.tcp_log, ts)
        except Exception as err:
            self.tcp_log.appendPlainText(f'[{ts}] 失败：{err}')


    def _udp_test_send(self):
        import socket
        from datetime import datetime
        host = (self.udp_host.text() or '').strip() or '127.0.0.1'
        port = int(self.udp_port.value())
        payload = (self.udp_payload.text() or '').encode('utf-8', errors='replace')
        timeout = max(0.1, float(self.udp_timeout.value()) / 1000.0)
        ts = datetime.now().strftime('%H:%M:%S')
        self.udp_log.appendPlainText(f'[{ts}] → UDP {host}:{port}  {payload!r}')
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(timeout)
            sock.sendto(payload, (host, port))
            text = ''
            try:
                data, addr = sock.recvfrom(4096)
                text = data.decode('utf-8', errors='replace')
                self.udp_log.appendPlainText(f'[{ts}] ← from {addr[0]}:{addr[1]}  {text!r}')
            except socket.timeout:
                self.udp_log.appendPlainText(f'[{ts}] ← (超时无回包，已发出)')
            finally:
                sock.close()
            if text:
                self._commit_test_writeback(self.udp_var_edit, self.udp_var_scope, text, self.udp_log, ts)
        except Exception as exc:
            self.udp_log.appendPlainText(f'[{ts}] ✗ {exc}')

    def _ser_fill_from_device(self):
        for d in self._devices:
            if 'Serial' in str(d.get('protocol') or ''):
                self.ser_port.setText(str(d.get('host') or d.get('path') or ''))
                return
        self.ser_log.appendPlainText('设备列表中无 Serial 设备')

    def _ser_test_send(self):
        path = (self.ser_port.text() or '').strip()
        baud = int(self.ser_baud.currentData() or 115200)
        raw = self.ser_payload.text() or ''
        payload = (raw + chr(10)).encode('utf-8', errors='replace')
        timeout = max(0.1, float(self.ser_timeout.value()) / 1000.0)
        self.ser_log.appendPlainText(f'→ {path} @{baud}  {payload!r}')
        try:
            import serial as pyserial
        except ImportError:
            self.ser_log.appendPlainText('✗ 未安装 pyserial；配置仍可保存供流程引用设备名')
            return
        try:
            with pyserial.Serial(path, baudrate=baud, timeout=timeout) as ser:
                ser.write(payload)
                data = ser.read(4096)
                text = data.decode('utf-8', errors='replace') if data else ''
                self.ser_log.appendPlainText(f'← {text!r}' if data else '← (无数据)')
                if text:
                    self._commit_test_writeback(self.ser_var_edit, self.ser_var_scope, text, self.ser_log, '')
        except Exception as exc:
            self.ser_log.appendPlainText(f'✗ {exc}')



    def _commit_test_writeback(self, var_edit, scope_combo, text, log_widget, ts=''):
        """Write test reply into flow/global vars; honor scope combo or flow./global. prefix."""
        raw = (var_edit.text() or '').strip() if var_edit else ''
        if not raw or not hasattr(self, 'document'):
            return
        # If user typed bare name, prefix with combo scope
        if '.' not in raw and scope_combo is not None:
            scope = scope_combo.currentData() or 'flow'
            raw = f'{scope}.{raw}'
        p = deepcopy(self.document.project)
        scope, name = write_project_variable(p, raw, text)
        if not name:
            return
        # remember prefs
        cm = ensure_comm_manager(p)
        prefs = cm.setdefault('testPrefs', {})
        prefs['lastVar'] = raw
        prefs['lastScope'] = scope
        self.document.commit(p)
        prefix = f'[{ts}] ' if ts else ''
        log_widget.appendPlainText(f'{prefix}已写入变量 {scope}.{name}')

    def accept_save(self):
        # Flush current form into devices list
        if self.device_list.currentRow() >= 0:
            self._apply_device_form()
        p = deepcopy(self.document.project)
        p['commManager'] = dict(
            devices=deepcopy(self._devices),
            recvEvents=self.recv_table.rows(),
            sendEvents=self.send_table.rows(),
            heartbeat=dict(
                enabled=bool(self.hb_enabled.isChecked()),
                intervalMs=int(self.hb_interval.value()),
                payload=self.hb_payload.text(),
            ),
            response=dict(
                enabled=bool(self.resp_enabled.isChecked()),
                timeoutMs=int(self.resp_timeout.value()),
                ack=self.resp_ack.text(),
            ),
        )
        self.document.commit(p)
        n = len(p['commManager']['devices'])
        QMessageBox.information(self, '通信管理', f'已保存 {n} 个通讯设备及收发/心跳/响应配置。')
        self.accept()
