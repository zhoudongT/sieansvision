"""接收数据 / 发送数据（receive_data / send_data）— VisionMaster p=11 壳.

绑定通信管理中的设备通道；收：写入变量；发：从变量或常量取内容。
"""
from copy import deepcopy

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTabWidget, QFormLayout, QLineEdit,
    QComboBox, QScrollArea, QFrame, QPlainTextEdit, QSpinBox,
)

from desktop.widgets.switch import OrangeSwitch


def _devices(project):
    cm = (project or {}).get('commManager') or {}
    devices = cm.get('devices') or cm.get('deviceList') or []
    out = []
    if isinstance(devices, list):
        for d in devices:
            if isinstance(d, dict):
                name = d.get('name') or d.get('id') or d.get('label')
                if name:
                    out.append(str(name))
            elif d:
                out.append(str(d))
    # also flatten typed tabs
    for key in ('tcp', 'udp', 'serial', 'sharedMemory', 'protocol'):
        rows = cm.get(key) or []
        if isinstance(rows, list):
            for d in rows:
                if isinstance(d, dict):
                    name = d.get('name') or d.get('id') or d.get('host')
                    if name:
                        out.append(str(name))
    # dedupe
    seen = set()
    uniq = []
    for n in out:
        if n not in seen:
            seen.add(n)
            uniq.append(n)
    return uniq


def normalize_receive_params(params=None):
    p = deepcopy(params or {})
    p.setdefault('device', '')
    p.setdefault('channel', '')
    p.setdefault('timeoutMs', 1000)
    p.setdefault('encoding', 'utf-8')
    p.setdefault('targetScope', 'flow')
    p.setdefault('targetVar', 'recvData')
    p.setdefault('triggerOnReceive', True)
    return p


def normalize_send_params(params=None):
    p = deepcopy(params or {})
    p.setdefault('device', '')
    p.setdefault('channel', '')
    p.setdefault('message', '')
    p.setdefault('sourceMode', 'text')  # text | variable
    p.setdefault('sourceScope', 'flow')
    p.setdefault('sourceVar', '')
    p.setdefault('encoding', 'utf-8')
    p.setdefault('appendCrLf', False)
    return p


class DataIoPanel(QWidget):
    changed = Signal(dict)

    def __init__(self, step, definition, project, parent=None):
        super().__init__(parent)
        self.step = deepcopy(step)
        self.definition = definition or {}
        self.project = project or {}
        self.op = step.get('operation') or 'receive_data'
        if self.op == 'send_data':
            self.params = normalize_send_params(step.get('params'))
        else:
            self.params = normalize_receive_params(step.get('params'))
        self.step['params'] = self.params

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        title = '发送数据' if self.op == 'send_data' else '接收数据'
        hint = QLabel(
            f'对齐 VisionMaster「{title}」：绑定通信管理中的设备；'
            '未选设备时红叹号。实际收发依赖通信后端（设计态可完整配置）。'
        )
        hint.setWordWrap(True)
        hint.setStyleSheet('color:#666;padding:8px 10px 4px;')
        root.addWidget(hint)

        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)
        self.tabs.addTab(self._wrap(self._basic_tab()), '基本参数')
        self.tabs.addTab(self._wrap(self._result_tab()), '结果显示')

    def _wrap(self, inner):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(inner)
        return scroll

    def _emit(self):
        self.step['params'] = deepcopy(self.params)
        self.changed.emit(deepcopy(self.step))

    def _set_param(self, key, value):
        if self.params.get(key) != value:
            self.params[key] = deepcopy(value)
            self._emit()

    def _set_top(self, key, value):
        if self.step.get(key) != value:
            self.step[key] = deepcopy(value)
            self._emit()

    def _basic_tab(self):
        w = QWidget()
        form = QFormLayout(w)
        form.setContentsMargins(10, 10, 10, 10)
        form.setSpacing(8)
        default_name = '发送数据' if self.op == 'send_data' else '接收数据'
        name = QLineEdit(self.step.get('name') or default_name)
        name.setMaxLength(80)
        name.editingFinished.connect(lambda: self._set_top('name', name.text()))
        form.addRow('模块名称', name)

        devices = _devices(self.project)
        device = QComboBox()
        device.setEditable(True)
        device.addItem('（未选择设备）', '')
        for d in devices:
            device.addItem(d, d)
        cur = self.params.get('device') or ''
        if cur and device.findData(cur) < 0:
            device.addItem(cur, cur)
        device.setCurrentIndex(max(0, device.findData(cur)))
        if cur and device.currentData() != cur:
            device.setEditText(cur)
        def _dev_changed():
            val = device.currentData()
            if val is None:
                val = device.currentText().strip()
            self._set_param('device', val or '')
        device.currentIndexChanged.connect(lambda _: _dev_changed())
        device.editTextChanged.connect(lambda t: self._set_param('device', t.strip()))
        form.addRow('通信设备', device)

        ch = QLineEdit(str(self.params.get('channel') or ''))
        ch.setPlaceholderText('通道 / 端口别名（可选）')
        ch.editingFinished.connect(lambda: self._set_param('channel', ch.text().strip()))
        form.addRow('通道', ch)

        enc = QComboBox()
        for e in ('utf-8', 'gbk', 'ascii', 'hex'):
            enc.addItem(e, e)
        enc.setCurrentIndex(max(0, enc.findData(self.params.get('encoding') or 'utf-8')))
        enc.currentIndexChanged.connect(lambda _: self._set_param('encoding', enc.currentData()))
        form.addRow('编码', enc)

        if self.op == 'receive_data':
            to = QSpinBox(); to.setRange(0, 600000); to.setValue(int(self.params.get('timeoutMs') or 1000))
            to.valueChanged.connect(lambda v: self._set_param('timeoutMs', int(v)))
            form.addRow('超时 (ms)', to)
            scope = QComboBox()
            for s, lab in (('flow', '流程'), ('global', '全局'), ('module', '模块')):
                scope.addItem(lab, s)
            scope.setCurrentIndex(max(0, scope.findData(self.params.get('targetScope') or 'flow')))
            scope.currentIndexChanged.connect(lambda _: self._set_param('targetScope', scope.currentData()))
            form.addRow('写入作用域', scope)
            var = QLineEdit(str(self.params.get('targetVar') or 'recvData'))
            var.editingFinished.connect(lambda: self._set_param('targetVar', var.text().strip() or 'recvData'))
            form.addRow('目标变量', var)
            trig = OrangeSwitch(bool(self.params.get('triggerOnReceive', True)))
            trig.toggled.connect(lambda c: self._set_param('triggerOnReceive', bool(c)))
            form.addRow('收到后触发', trig)
        else:
            mode = QComboBox()
            mode.addItem('文本常量', 'text')
            mode.addItem('变量', 'variable')
            mode.setCurrentIndex(max(0, mode.findData(self.params.get('sourceMode') or 'text')))
            mode.currentIndexChanged.connect(lambda _: self._set_param('sourceMode', mode.currentData()))
            form.addRow('内容来源', mode)
            msg = QPlainTextEdit()
            msg.setPlainText(str(self.params.get('message') or ''))
            msg.setPlaceholderText('发送内容…')
            msg.setMaximumHeight(120)
            msg.textChanged.connect(lambda: self._set_param('message', msg.toPlainText()))
            form.addRow('发送内容', msg)
            svar = QLineEdit(str(self.params.get('sourceVar') or ''))
            svar.setPlaceholderText('变量名（变量模式）')
            svar.editingFinished.connect(lambda: self._set_param('sourceVar', svar.text().strip()))
            form.addRow('源变量', svar)
            crlf = OrangeSwitch(bool(self.params.get('appendCrLf', False)))
            crlf.toggled.connect(lambda c: self._set_param('appendCrLf', bool(c)))
            form.addRow('追加 CRLF', crlf)

        tip = QLabel('可在「工具 → 通信管理」中维护设备列表。')
        tip.setStyleSheet('color:#888;')
        form.addRow(tip)
        return w

    def _result_tab(self):
        w = QWidget()
        form = QFormLayout(w)
        form.setContentsMargins(10, 10, 10, 10)
        if self.op == 'receive_data':
            tip = QLabel('运行结果：payload / bytes / device / status。')
        else:
            tip = QLabel('运行结果：sent / bytes / device / status。')
        tip.setWordWrap(True)
        tip.setStyleSheet('color:#888;')
        form.addRow(tip)
        return w
