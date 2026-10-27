"""通信管理 — VisionMaster p=10 统一设备/收发/心跳壳.

集中配置通讯设备（TCP/UDP/串口/MQTT/Modbus…）；流程内收发算子可引用设备名。
持久化到 project.commManager；运行侧仍走既有 industrial / socket 算子。
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

PROTOCOLS = [
    'TCP Client', 'TCP Server', 'UDP', 'Serial', 'MQTT', 'Modbus TCP', 'Modbus RTU', 'OPC UA', 'S7',
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
    return cm


class _EventTable(QWidget):
    COLS = ['序号', '事件名', '绑定设备', '报文/主题', '操作']

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(self.COLS)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        lay.addWidget(self.table, 1)
        bar = QHBoxLayout()
        add = QPushButton('添加')
        add.clicked.connect(lambda: self._append({}))
        bar.addWidget(add)
        bar.addStretch(1)
        lay.addLayout(bar)

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
        rm = QPushButton('删')
        rm.setFixedWidth(36)
        rm.clicked.connect(lambda *_ , rr=r: self._remove(rr))
        self.table.setCellWidget(r, 4, rm)

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
            out.append(dict(
                name=name_w.text().strip() if name_w else '',
                device=dev_w.currentData() if dev_w else '',
                message=msg_w.text().strip() if msg_w else '',
                topic=msg_w.text().strip() if msg_w else '',
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
            '流程中的 TCP/串口/MQTT/Modbus 算子可引用此处设备名。配置随方案保存。'
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
        self.recv_table = _EventTable()
        self.send_table = _EventTable()
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
        self.tcp_log = QPlainTextEdit()
        self.tcp_log.setReadOnly(True)
        self.tcp_log.setPlaceholderText('测试日志…')
        tcp_lay.addWidget(self.tcp_log, 1)
        self.tabs.addTab(tcp, 'TCP 测试')


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
