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


def expand_payload_placeholders(project, text):
    """Expand ${name} / ${flow.name} / ${global.name} in send payloads (design + preview)."""
    import re as _re
    raw = '' if text is None else str(text)
    if '${' not in raw:
        return raw

    def _repl(m):
        ref = (m.group(1) or '').strip()
        if not ref:
            return m.group(0)
        val = read_project_variable(project, ref, None)
        if val is None:
            return m.group(0)
        return str(val)

    return _re.sub(r'\$\{([^}]+)\}', _repl, raw)



# —— 消息模板库（设计态；无现场 socket）——
DEFAULT_MESSAGE_TEMPLATES = [
    {
        'id': 'result-line',
        'name': 'OK/NG 行报文',
        'protocol': 'line',
        'body': 'RESULT ok=${flow.passGate} score=${flow.matchScore} count=${flow.matchCount}',
    },
    {
        'id': 'meas-line',
        'name': '量测上报',
        'protocol': 'line',
        'body': 'MEAS x=${flow.poseX} y=${flow.poseY} score=${flow.matchScore} ok=${flow.passGate}',
    },
    {
        'id': 'defect-line',
        'name': '缺陷上报',
        'protocol': 'line',
        'body': 'DEFECT count=${flow.defectCount} ratio=${flow.defectRatio} ok=${flow.passGate}',
    },
    {
        'id': 'json-status',
        'name': 'JSON 状态',
        'protocol': 'json',
        'body': '{"cmd":"STATUS","ok":${flow.passGate},"score":${flow.matchScore},"defects":${flow.defectCount}}',
    },
    {
        'id': 'json-meas',
        'name': 'JSON 量测',
        'protocol': 'json',
        'body': '{"cmd":"MEAS","x":${flow.poseX},"y":${flow.poseY},"score":${flow.matchScore},"ok":${flow.passGate}}',
    },
    {
        'id': 'delimited',
        'name': '分隔符字段',
        'protocol': 'delimited',
        'body': '${flow.passGate},${flow.matchScore},${flow.measureCount},${flow.defectCount}',
    },
    {
        'id': 'run',
        'name': 'RUN 触发',
        'protocol': 'line',
        'body': 'RUN',
    },
    {
        'id': 'stop',
        'name': 'STOP 触发',
        'protocol': 'line',
        'body': 'STOP',
    },
    {
        'id': 'hb',
        'name': '心跳 HB',
        'protocol': 'line',
        'body': 'HB ts=${flow.hbSeq}',
    },
]


def builtin_message_templates():
    """Return a deep copy of built-in industrial message templates."""
    from copy import deepcopy as _dc
    return _dc(DEFAULT_MESSAGE_TEMPLATES)


def merge_message_templates(project_templates=None):
    """Merge project-saved templates over builtins (by id); project entries win."""
    from copy import deepcopy as _dc
    by_id = {t['id']: _dc(t) for t in DEFAULT_MESSAGE_TEMPLATES if t.get('id')}
    for t in (project_templates or []):
        if not isinstance(t, dict):
            continue
        tid = str(t.get('id') or '').strip() or None
        if tid:
            by_id[tid] = _dc(t)
        else:
            # anonymous custom — keep with generated key
            by_id[f'custom-{len(by_id)}'] = _dc(t)
    return list(by_id.values())


def preview_expand_template(project, body, demo_vars=None):
    """Expand ${} against project vars; optionally seed demo_vars for empty projects."""
    from copy import deepcopy as _dc
    proj = _dc(project) if isinstance(project, dict) else {}
    variables = proj.setdefault('variables', {})
    if not isinstance(variables, dict):
        variables = {}
        proj['variables'] = variables
    for k, v in (demo_vars or {}).items():
        if k not in variables or variables.get(k) in (None, '', 0):
            # only fill missing/zero for richer demo — keep real values
            if k not in variables:
                variables[k] = v
    return expand_payload_placeholders(proj, body)


def resolve_send_event_payload(project, event):
    """Send event → payload: bound variable first, else message with ${} expand.

    Mirrors lib/comm-bus resolveSendMessage for design-time 试发 / 填报文.
    Returns (payload:str, source:str) where source is 'variable'|'message'|'empty'.
    """
    ev = event if isinstance(event, dict) else {}
    ref = (ev.get('variable') or ev.get('var') or '').strip()
    if ref:
        val = read_project_variable(project, ref, None)
        if val is not None:
            return str(val), 'variable'
    msg = ev.get('message') if ev.get('message') is not None else ev.get('topic')
    if msg is None:
        msg = ''
    expanded = expand_payload_placeholders(project, msg)
    if str(expanded):
        return str(expanded), 'message'
    return '', 'empty'


def parse_protocol_writeback_extras(text):
    """Parse sim/live protocol replies into extra var writes (no field-HW claim).

    VALUE score=0.91 → [('score','0.91')]
    VALUE a=1 b=2 / VALUE a=1,b=2 → multiple pairs
    MEAS {"ok":1,"x":..} → [('measOk',1),('measX',..),...]
    bare JSON object → flatten top-level scalars as json_<key>
    """
    import json as _json
    import re as _re
    raw = (text or '').strip()
    if not raw:
        return []
    out = []
    up = raw.upper()
    if up.startswith('VALUE ') or up.startswith('VALUE\t'):
        body = raw.split(None, 1)[1].strip()
        # pairs: k=v separated by whitespace or commas; also allow k:v
        parts = [p for p in _re.split(r'[\s,;]+', body) if p]
        if len(parts) == 1 and ('=' in body or ':' in body) and ' ' not in body.strip():
            # single pair may contain spaces in value — prefer first =/:
            sep = '=' if '=' in body else ':'
            k, v = body.split(sep, 1)
            k = k.strip()
            if k:
                out.append((k, v))
            return out
        for part in parts:
            if '=' in part:
                k, v = part.split('=', 1)
            elif ':' in part:
                k, v = part.split(':', 1)
            else:
                continue
            k = k.strip()
            if k:
                out.append((k, v))
        return out
    if up.startswith('MEAS ') or (up.startswith('MEAS{')):
        body = raw[4:].strip() if up.startswith('MEAS') else ''
        if up.startswith('MEAS '):
            body = raw.split(None, 1)[1].strip()
        try:
            obj = _json.loads(body)
        except Exception:
            return out
        if isinstance(obj, dict):
            mapping = {
                'ok': 'measOk', 'x': 'measX', 'y': 'measY', 'z': 'measZ',
                'score': 'measScore', 'seq': 'measSeq', 'ts': 'measTs',
                'angle': 'measAngle', 'dist': 'measDist', 'distance': 'measDist',
                'status': 'measStatus', 'pass': 'measPass', 'passed': 'measPass',
            }
            for src, dst in mapping.items():
                if src in obj:
                    out.append((dst, obj[src]))
            # also stamp any leftover scalar under meas_<key>
            known = set(mapping)
            for k, v in obj.items():
                if k in known:
                    continue
                if isinstance(v, (str, int, float, bool)) or v is None:
                    out.append((f'meas_{k}', v if v is not None else ''))
        return out
    if raw.startswith('{') and raw.endswith('}'):
        try:
            obj = _json.loads(raw)
        except Exception:
            return out
        if isinstance(obj, dict):
            for k, v in obj.items():
                if isinstance(v, (str, int, float, bool)) or v is None:
                    out.append((f'json_{k}', v if v is not None else ''))
        return out
    return out


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
            '发送事件可绑定流程变量；运行时 send_data / 试发优先读该变量，报文支持 ${flow.x} 占位。'
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
            fill.setToolTip('用绑定变量当前值覆盖「报文」列（设计态预览）；支持 ${var} 展开')
            fill.clicked.connect(self._fill_from_variables)
            bar.addWidget(fill)
            trial = QPushButton('试发(读变量)')
            trial.setToolTip(
                '按「读变量优先 → 报文 ${} 展开」解析载荷，写入 flow.lastSendPayload '
                '并投递 LocalLoop（无真实 TCP）'
            )
            trial.clicked.connect(self._trial_send_from_variables)
            bar.addWidget(trial)
        pick = QPushButton('挑选变量…')
        pick.setToolTip('从工程流程/全局变量表挑选，写入当前行「变量」列')
        pick.clicked.connect(self._pick_variable_into_row)
        bar.addWidget(pick)
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
                # 细妆⑰：VALUE/MEAS/JSON → sibling 字段一并写回
                try:
                    extras = parse_protocol_writeback_extras(msg)
                except Exception:
                    extras = []
                for ek, ev in extras:
                    s2, n2 = write_project_variable(p, f'{scope}.{ek}', ev)
                    if n2:
                        written.append(f'{s2}.{n2}')
        if written:
            doc.commit(p)
            QMessageBox.information(self, '接收事件', '已写回：\n' + '\n'.join(written))
        else:
            QMessageBox.information(self, '接收事件', '没有绑定变量的事件行。')


    def _pick_variable_into_row(self):
        """细妆：收发事件表 ← 工程变量名挑选。"""
        from PySide6.QtWidgets import QInputDialog, QMessageBox
        dlg = self.window()
        doc = getattr(dlg, 'document', None) if dlg else None
        project = getattr(doc, 'project', None) if doc else None
        if not isinstance(project, dict):
            # walk parents for document
            w = self.parent()
            while w is not None and project is None:
                doc = getattr(w, 'document', None)
                if doc is not None and hasattr(doc, 'project'):
                    project = doc.project
                    break
                w = w.parent()
        names = []
        if isinstance(project, dict):
            for k in (project.get('variables') or {}):
                if k == 'global':
                    continue
                names.append(f'flow.{k}')
            g = project.get('globalVariables') or {}
            if isinstance(g, dict):
                for k in g:
                    names.append(f'global.{k}')
            nested = (project.get('variables') or {}).get('global')
            if isinstance(nested, dict):
                for k in nested:
                    token = f'global.{k}'
                    if token not in names:
                        names.append(token)
        if not names:
            names = ['flow.tcpLastRecv', 'flow.udpLastRecv', 'global.triggerPayload']
            QMessageBox.information(
                self, '挑选变量',
                '工程尚无自定义变量，提供常用占位名；也可手改变量列。',
            )
        choice, ok = QInputDialog.getItem(self, '挑选变量', '写入当前行变量列', names, 0, True)
        if not ok or not choice:
            return
        r = self.table.currentRow()
        if r < 0:
            r = 0
        if self.table.rowCount() == 0:
            self._append({})
            r = 0
        var_w = self.table.cellWidget(r, 4)
        if var_w is not None:
            var_w.setText(choice.strip())

    def _fill_from_variables(self):
        doc = getattr(self, '_document', None)
        if doc is None:
            return
        p = doc.project or {}
        n = 0
        for r in range(self.table.rowCount()):
            var_w = self.table.cellWidget(r, 4)
            msg_w = self.table.cellWidget(r, 3)
            if not var_w or not msg_w:
                continue
            ref = var_w.text().strip()
            msg = msg_w.text()
            if ref:
                val = read_project_variable(p, ref, None)
                if val is not None:
                    msg_w.setText(str(val))
                    n += 1
                    continue
            if '${' in (msg or ''):
                expanded = expand_payload_placeholders(p, msg)
                if expanded != msg:
                    msg_w.setText(expanded)
                    n += 1
        if n:
            QMessageBox.information(self, '发送事件', f'已从变量/占位展开 {n} 行报文。')

    def _trial_send_from_variables(self):
        """Design-time 试发：resolve payload → flow.lastSendPayload + LocalLoop inbox note."""
        doc = getattr(self, '_document', None)
        if doc is None:
            QMessageBox.information(self, '试发', '无工程文档。')
            return
        rows = self.rows()
        if not rows:
            QMessageBox.information(self, '试发', '发送事件表为空。')
            return
        p = deepcopy(doc.project)
        lines = []
        for row in rows:
            payload, src = resolve_send_event_payload(p, row)
            name = (row.get('name') or '').strip() or '事件'
            device = (row.get('device') or '').strip() or 'LocalLoop'
            if not payload:
                lines.append(f'· {name} @ {device}：空载荷（跳过）')
                continue
            write_project_variable(p, 'flow.lastSendPayload', payload)
            write_project_variable(p, 'flow.lastSendDevice', device)
            write_project_variable(p, 'flow.lastSendEvent', name)
            write_project_variable(p, 'flow.lastSendSource', src)
            # Stamp device-bound var if present so recv/demo can round-trip
            ref = (row.get('variable') or row.get('var') or '').strip()
            if ref and src != 'variable':
                # keep variable as-is; payload came from message
                pass
            lines.append(f'· {name} @ {device} ← {src}：{payload[:80]!r}')
        doc.commit(p)
        QMessageBox.information(
            self, '试发(读变量)',
            '已解析并写入 flow.lastSendPayload（无真实 TCP）：\n' + '\n'.join(lines),
        )

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
        link = QHBoxLayout()
        link_lab = QLabel('收数 → 字符串触发：试收报文可派发全局触发（RUN/STOP…）')
        link_lab.setStyleSheet('color:#666;font-size:11px;')
        link.addWidget(link_lab, 1)
        open_gt = QPushButton('打开全局触发…')
        open_gt.setToolTip('配置字符串/事件触发表（与通信试收联调）')
        open_gt.clicked.connect(self._open_global_triggers)
        link.addWidget(open_gt)
        open_var = QPushButton('变量联调…')
        open_var.setToolTip('收发事件可读写运行时变量；打开变量/全局变量面板指引')
        open_var.clicked.connect(self._open_variables_hint)
        link.addWidget(open_var)
        root.addLayout(link)

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
        resp_lay = QVBoxLayout(resp)
        resp_lay.setContentsMargins(12, 12, 12, 12)
        resp_form = QFormLayout()
        self.resp_enabled = OrangeSwitch(False)
        self.resp_timeout = QSpinBox()
        self.resp_timeout.setRange(0, 120000)
        self.resp_timeout.setValue(3000)
        self.resp_ack = QLineEdit('OK')
        resp_form.addRow('启用应答', self.resp_enabled)
        resp_form.addRow('超时(ms)', self.resp_timeout)
        resp_form.addRow('应答内容', self.resp_ack)
        resp_lay.addLayout(resp_form)
        # Page-level soft auto-ack / grouped reply timeline (not prop chips)
        tip_ack = QLabel(
            'recvEvents ↔ LocalBus 软自动应答：按接收事件设备分组投递 RX，'
            '再按上方应答内容回 ACK（设计态；无现场 TCP）。页级时间线，非属性芯片。'
        )
        tip_ack.setWordWrap(True)
        tip_ack.setStyleSheet('color:#888;')
        resp_lay.addWidget(tip_ack)
        self.ack_reply_timeline = QPlainTextEdit()
        self.ack_reply_timeline.setObjectName('commRecvAutoAckTimeline')
        self.ack_reply_timeline.setReadOnly(True)
        self.ack_reply_timeline.setMaximumHeight(180)
        self.ack_reply_timeline.setStyleSheet(
            'font-family:monospace;font-size:11px;background:#1a2430;color:#80cbc4;'
        )
        self.ack_reply_timeline.setPlaceholderText(
            'recvEvents ↔ LocalBus auto-ack / grouped reply timeline'
        )
        resp_lay.addWidget(QLabel('自动应答分组时间线（页铬）'))
        resp_lay.addWidget(self.ack_reply_timeline)
        self.ack_reply_meta = QLabel('(尚未软收→应答)')
        self.ack_reply_meta.setObjectName('commRecvAutoAckMeta')
        self.ack_reply_meta.setWordWrap(True)
        self.ack_reply_meta.setStyleSheet('color:#666;font-size:11px;')
        resp_lay.addWidget(self.ack_reply_meta)
        self._ack_reply_lines = []
        ack_bar = QHBoxLayout()
        self.ack_soft_btn = QPushButton('recvEvents 软收→自动应答')
        self.ack_soft_btn.setObjectName('commRecvAutoAckBtn')
        self.ack_soft_btn.setToolTip(
            '把演示载荷软投递到 recvEvents 绑定设备 LocalBus，并按应答配置自动 ACK；刷新分组时间线'
        )
        self.ack_soft_btn.clicked.connect(self._soft_recv_auto_ack_timeline)
        ack_bar.addWidget(self.ack_soft_btn)
        self.ack_demo_payload = QLineEdit('RESULT ok=1 score=0.92')
        self.ack_demo_payload.setObjectName('commRecvAutoAckPayload')
        self.ack_demo_payload.setPlaceholderText('软收演示载荷')
        ack_bar.addWidget(self.ack_demo_payload, 1)
        self.ack_clear_btn = QPushButton('清空时间线')
        self.ack_clear_btn.setObjectName('commRecvAutoAckClear')
        self.ack_clear_btn.clicked.connect(self._clear_recv_auto_ack_timeline)
        ack_bar.addWidget(self.ack_clear_btn)
        self.ack_rt_btn = QPushButton('应答→sendEvents/format 软往返')
        self.ack_rt_btn.setObjectName('commAutoAckSendFormatRoundTripBtn')
        self.ack_rt_btn.setToolTip(
            'recvEvents 软收→自动应答后，按 sendEvents 做 format_data 风格 ${} 展开并 LocalBus 软 TX；页级往返条'
        )
        self.ack_rt_btn.clicked.connect(self._soft_autoack_sendevents_format_roundtrip)
        ack_bar.addWidget(self.ack_rt_btn)
        resp_lay.addLayout(ack_bar)
        # Page strip: auto-ack → sendEvents / format_data soft round-trip
        tip_rt = QLabel(
            '自动应答闭环 → sendEvents / format_data 软往返：ACK 后按发送事件展开 ${flow.*} 并 LocalBus 软投递（无现场 TCP）。'
        )
        tip_rt.setWordWrap(True)
        tip_rt.setStyleSheet('color:#888;')
        resp_lay.addWidget(tip_rt)
        self.ack_rt_strip = QPlainTextEdit()
        self.ack_rt_strip.setObjectName('commAutoAckSendFormatRoundTripStrip')
        self.ack_rt_strip.setReadOnly(True)
        self.ack_rt_strip.setMaximumHeight(150)
        self.ack_rt_strip.setStyleSheet(
            'font-family:monospace;font-size:11px;background:#1c2a1c;color:#c5e1a5;'
        )
        self.ack_rt_strip.setPlaceholderText(
            'auto-ack → sendEvents / format_data soft round-trip page strip'
        )
        resp_lay.addWidget(QLabel('应答→发送/格式化 软往返条（页铬）'))
        resp_lay.addWidget(self.ack_rt_strip)
        self.ack_rt_meta = QLabel('(尚未应答→发送往返)')
        self.ack_rt_meta.setObjectName('commAutoAckSendFormatRoundTripMeta')
        self.ack_rt_meta.setWordWrap(True)
        self.ack_rt_meta.setStyleSheet('color:#666;font-size:11px;')
        resp_lay.addWidget(self.ack_rt_meta)

        # Page strip: production_task result OK/NG → sendEvents soft TX (closed-loop out)
        tip_okng = QLabel(
            '生产任务结果 OK/NG → sendEvents 软 TX：按判定展开 ${flow.okng}/${flow.resultOk} 等并 LocalBus 出站（无现场 TCP）。'
        )
        tip_okng.setWordWrap(True)
        tip_okng.setStyleSheet('color:#888;')
        resp_lay.addWidget(tip_okng)
        okng_bar = QHBoxLayout()
        self.result_okng_tx_btn = QPushButton('结果OK/NG→sendEvents 软TX')
        self.result_okng_tx_btn.setObjectName('commResultOkNgSendTxBtn')
        self.result_okng_tx_btn.setToolTip(
            '用演示判定 OK/NG 驱动 sendEvents format_data 风格展开并 LocalBus 软 TX（闭环出站）'
        )
        self.result_okng_tx_btn.clicked.connect(lambda: self.soft_result_okng_send_tx(judge='OK'))
        okng_bar.addWidget(self.result_okng_tx_btn)
        self.result_okng_ng_btn = QPushButton('演示 NG 出站')
        self.result_okng_ng_btn.setObjectName('commResultOkNgSendTxNgBtn')
        self.result_okng_ng_btn.clicked.connect(lambda: self.soft_result_okng_send_tx(judge='NG'))
        okng_bar.addWidget(self.result_okng_ng_btn)
        okng_bar.addStretch(1)
        resp_lay.addLayout(okng_bar)
        self.result_okng_tx_strip = QPlainTextEdit()
        self.result_okng_tx_strip.setObjectName('commResultOkNgSendTxStrip')
        self.result_okng_tx_strip.setReadOnly(True)
        self.result_okng_tx_strip.setMaximumHeight(120)
        self.result_okng_tx_strip.setStyleSheet(
            'font-family:monospace;font-size:11px;background:#1a2030;color:#9ec9f0;'
        )
        self.result_okng_tx_strip.setPlainText('(尚无结果 OK/NG → sendEvents 软 TX)')
        self.result_okng_tx_strip.setToolTip(
            'production_task result OK/NG → Comm sendEvents soft TX page strip'
        )
        resp_lay.addWidget(QLabel('结果 OK/NG → sendEvents 软 TX 条（页铬 · LocalBus）'))
        resp_lay.addWidget(self.result_okng_tx_strip)
        self.result_okng_tx_meta = QLabel('(结果→sendEvents 软 TX 待命)')
        self.result_okng_tx_meta.setObjectName('commResultOkNgSendTxMeta')
        self.result_okng_tx_meta.setWordWrap(True)
        self.result_okng_tx_meta.setStyleSheet('color:#666;font-size:11px;')
        resp_lay.addWidget(self.result_okng_tx_meta)

        # Page chrome: sendEvents result-out → Host SM / HMI status rail closed-loop
        tip_loop = QLabel(
            'sendEvents 结果出站 → Host SM / HMI 状态轨 闭环页铬：出站后回写上位机状态与操作员状态轨（无现场 TCP）。'
        )
        tip_loop.setWordWrap(True)
        tip_loop.setStyleSheet('color:#888;')
        resp_lay.addWidget(tip_loop)
        self.tx_status_rail_loop_strip = QPlainTextEdit()
        self.tx_status_rail_loop_strip.setObjectName('commSendEventsHostSmStatusRailLoopStrip')
        self.tx_status_rail_loop_strip.setReadOnly(True)
        self.tx_status_rail_loop_strip.setMaximumHeight(100)
        self.tx_status_rail_loop_strip.setStyleSheet(
            'font-family:monospace;font-size:11px;background:#1a2430;color:#9ec9f0;'
        )
        self.tx_status_rail_loop_strip.setPlainText('(尚无 sendEvents→Host SM/HMI 状态轨闭环)')
        self.tx_status_rail_loop_strip.setToolTip(
            'Comm sendEvents result-out → Host SM / HMI status rail closed-loop page chrome'
        )
        resp_lay.addWidget(QLabel('sendEvents → Host SM / HMI 状态轨 闭环条（页铬）'))
        resp_lay.addWidget(self.tx_status_rail_loop_strip)
        self.tx_status_rail_loop_meta = QLabel('(出站→状态轨闭环待命)')
        self.tx_status_rail_loop_meta.setObjectName('commSendEventsHostSmStatusRailLoopMeta')
        self.tx_status_rail_loop_meta.setWordWrap(True)
        self.tx_status_rail_loop_meta.setStyleSheet('color:#666;font-size:11px;')
        resp_lay.addWidget(self.tx_status_rail_loop_meta)

        # Page chrome: Host SM liaison timeline ↔ sendEvents ack/response co-bind
        tip_liaison = QLabel(
            'Host SM 联调时间线 ↔ Comm sendEvents 应答/响应 页共绑：'
            '出站应答回写联调条，联调事件驱动应答页铬（无现场 TCP）。'
        )
        tip_liaison.setWordWrap(True)
        tip_liaison.setStyleSheet('color:#888;')
        resp_lay.addWidget(tip_liaison)
        liaison_bar = QHBoxLayout()
        self.liaison_ack_cobind_btn = QPushButton('联调↔sendEvents应答 共绑')
        self.liaison_ack_cobind_btn.setObjectName('commLiaisonSendAckResponseCoBindBtn')
        self.liaison_ack_cobind_btn.setToolTip(
            'Host SM liaison timeline ↔ Comm sendEvents ack/response page co-bind'
        )
        self.liaison_ack_cobind_btn.clicked.connect(
            lambda: self.soft_co_bind_liaison_send_ack_response(judge='OK')
        )
        liaison_bar.addWidget(self.liaison_ack_cobind_btn)
        self.liaison_ack_cobind_ng_btn = QPushButton('演示 NG 共绑')
        self.liaison_ack_cobind_ng_btn.setObjectName('commLiaisonSendAckResponseCoBindNgBtn')
        self.liaison_ack_cobind_ng_btn.clicked.connect(
            lambda: self.soft_co_bind_liaison_send_ack_response(judge='NG')
        )
        liaison_bar.addWidget(self.liaison_ack_cobind_ng_btn)
        liaison_bar.addStretch(1)
        resp_lay.addLayout(liaison_bar)
        self.liaison_ack_cobind_strip = QPlainTextEdit()
        self.liaison_ack_cobind_strip.setObjectName('commLiaisonSendAckResponseCoBindStrip')
        self.liaison_ack_cobind_strip.setReadOnly(True)
        self.liaison_ack_cobind_strip.setMaximumHeight(110)
        self.liaison_ack_cobind_strip.setStyleSheet(
            'font-family:monospace;font-size:11px;background:#1a2430;color:#9ec9f0;'
        )
        self.liaison_ack_cobind_strip.setPlainText('(尚无 Host SM 联调 ↔ sendEvents 应答/响应 共绑)')
        self.liaison_ack_cobind_strip.setToolTip(
            'Host SM liaison timeline ↔ Comm sendEvents ack/response page co-bind'
        )
        resp_lay.addWidget(QLabel('联调时间线 ↔ sendEvents 应答/响应 共绑条（页铬）'))
        resp_lay.addWidget(self.liaison_ack_cobind_strip)
        self.liaison_ack_cobind_meta = QLabel('(联调↔应答共绑待命)')
        self.liaison_ack_cobind_meta.setObjectName('commLiaisonSendAckResponseCoBindMeta')
        self.liaison_ack_cobind_meta.setWordWrap(True)
        self.liaison_ack_cobind_meta.setStyleSheet('color:#666;font-size:11px;')
        resp_lay.addWidget(self.liaison_ack_cobind_meta)

        # Page chrome: OK-NG dashboard ↔ recvEvents auto-ack co-update
        tip_okng_ack = QLabel(
            'OK-NG 看板 ↔ Comm recvEvents 自动应答 页共更：'
            '看板判定驱动软收应答时间线，应答回写看板（LocalBus · 无现场 TCP）。'
        )
        tip_okng_ack.setWordWrap(True)
        tip_okng_ack.setStyleSheet('color:#888;')
        resp_lay.addWidget(tip_okng_ack)
        okng_ack_bar = QHBoxLayout()
        self.okng_recv_ack_btn = QPushButton('OK-NG↔recv自动应答 共更')
        self.okng_recv_ack_btn.setObjectName('commOkNgRecvAutoAckCoUpdateBtn')
        self.okng_recv_ack_btn.setToolTip(
            'OK-NG dashboard ↔ Comm recvEvents auto-ack page co-update'
        )
        self.okng_recv_ack_btn.clicked.connect(
            lambda: self.soft_co_update_okng_recv_autoack(judge='OK')
        )
        okng_ack_bar.addWidget(self.okng_recv_ack_btn)
        self.okng_recv_ack_ng_btn = QPushButton('演示 NG 共更')
        self.okng_recv_ack_ng_btn.setObjectName('commOkNgRecvAutoAckCoUpdateNgBtn')
        self.okng_recv_ack_ng_btn.clicked.connect(
            lambda: self.soft_co_update_okng_recv_autoack(judge='NG')
        )
        okng_ack_bar.addWidget(self.okng_recv_ack_ng_btn)
        okng_ack_bar.addStretch(1)
        resp_lay.addLayout(okng_ack_bar)
        self.okng_recv_ack_strip = QPlainTextEdit()
        self.okng_recv_ack_strip.setObjectName('commOkNgRecvAutoAckCoUpdateStrip')
        self.okng_recv_ack_strip.setReadOnly(True)
        self.okng_recv_ack_strip.setMaximumHeight(110)
        self.okng_recv_ack_strip.setStyleSheet(
            'font-family:monospace;font-size:11px;background:#1a2430;color:#c5e1a5;'
        )
        self.okng_recv_ack_strip.setPlainText('(尚无 OK-NG 看板 ↔ recvEvents 自动应答 共更)')
        self.okng_recv_ack_strip.setToolTip(
            'OK-NG dashboard ↔ Comm recvEvents auto-ack page co-update'
        )
        resp_lay.addWidget(QLabel('OK-NG 看板 ↔ recvEvents 自动应答 共更条（页铬）'))
        resp_lay.addWidget(self.okng_recv_ack_strip)
        self.okng_recv_ack_meta = QLabel('(OK-NG↔recv自动应答共更待命)')
        self.okng_recv_ack_meta.setObjectName('commOkNgRecvAutoAckCoUpdateMeta')
        self.okng_recv_ack_meta.setWordWrap(True)
        self.okng_recv_ack_meta.setStyleSheet('color:#666;font-size:11px;')
        resp_lay.addWidget(self.okng_recv_ack_meta)

        resp_lay.addStretch(1)
        self.tabs.addTab(resp, '响应')

        # --- 消息模板（${} 展开演示 · 无现场 socket）---
        tpl = QWidget()
        tpl_lay = QVBoxLayout(tpl)
        tpl_lay.setContentsMargins(12, 12, 12, 12)
        tip = QLabel(
            '工业报文模板库：选模板 → 编辑正文（支持 ${flow.x} / ${global.y}）→ 实况展开预览；'
            '可填入发送事件或 TCP/UDP「发送」框。设计态演示，不建立现场设备连接。'
        )
        tip.setWordWrap(True)
        tip.setStyleSheet('color:#666;')
        tpl_lay.addWidget(tip)
        split = QSplitter(Qt.Orientation.Horizontal)
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.addWidget(QLabel('模板列表'))
        self.tpl_list = QListWidget()
        self.tpl_list.setObjectName('commMessageTemplateList')
        self.tpl_list.currentRowChanged.connect(self._tpl_load_form)
        ll.addWidget(self.tpl_list, 1)
        brow = QHBoxLayout()
        add_tpl = QPushButton('+ 自定义')
        add_tpl.setObjectName('commMessageTemplateAdd')
        add_tpl.clicked.connect(self._tpl_add_custom)
        reset_tpl = QPushButton('恢复内置')
        reset_tpl.setObjectName('commMessageTemplateReset')
        reset_tpl.setToolTip('丢弃工程自定义，恢复内置模板库')
        reset_tpl.clicked.connect(self._tpl_reset_builtin)
        brow.addWidget(add_tpl)
        brow.addWidget(reset_tpl)
        brow.addStretch(1)
        ll.addLayout(brow)
        split.addWidget(left)
        right = QWidget()
        form = QFormLayout(right)
        form.setContentsMargins(12, 8, 12, 8)
        self.tpl_name = QLineEdit()
        self.tpl_name.setObjectName('commMessageTemplateName')
        self.tpl_proto = QComboBox()
        self.tpl_proto.setObjectName('commMessageTemplateProtocol')
        for lab, data in (
            ('行报文', 'line'),
            ('JSON', 'json'),
            ('分隔符', 'delimited'),
            ('TCP Client', 'TCP Client'),
            ('UDP', 'UDP'),
            ('Local Bus', 'Local Bus'),
        ):
            self.tpl_proto.addItem(lab, data)
        self.tpl_body = QPlainTextEdit()
        self.tpl_body.setObjectName('commMessageTemplateBody')
        self.tpl_body.setPlaceholderText('报文正文，支持 ${flow.passGate} / ${flow.matchScore} …')
        self.tpl_body.setMinimumHeight(100)
        self.tpl_preview = QPlainTextEdit()
        self.tpl_preview.setObjectName('commMessageTemplatePreview')
        self.tpl_preview.setReadOnly(True)
        self.tpl_preview.setPlaceholderText('实况展开预览…')
        self.tpl_preview.setMaximumHeight(90)
        form.addRow('名称', self.tpl_name)
        form.addRow('协议风格', self.tpl_proto)
        form.addRow('正文', self.tpl_body)
        form.addRow('展开预览', self.tpl_preview)
        prow = QHBoxLayout()
        self.tpl_expand_btn = QPushButton('刷新展开')
        self.tpl_expand_btn.setObjectName('commMessageTemplateExpand')
        self.tpl_expand_btn.setToolTip('用当前工程变量展开 ${}；缺省时用演示种子值')
        self.tpl_expand_btn.clicked.connect(self._tpl_refresh_preview)
        self.tpl_to_send = QPushButton('填入发送事件')
        self.tpl_to_send.setObjectName('commMessageTemplateToSend')
        self.tpl_to_send.clicked.connect(self._tpl_apply_to_send_event)
        self.tpl_to_tcp = QPushButton('填入 TCP 发送')
        self.tpl_to_tcp.setObjectName('commMessageTemplateToTcp')
        self.tpl_to_tcp.clicked.connect(lambda: self._tpl_apply_to_test('tcp'))
        self.tpl_to_udp = QPushButton('填入 UDP 发送')
        self.tpl_to_udp.setObjectName('commMessageTemplateToUdp')
        self.tpl_to_udp.clicked.connect(lambda: self._tpl_apply_to_test('udp'))
        prow.addWidget(self.tpl_expand_btn)
        prow.addStretch(1)
        prow.addWidget(self.tpl_to_send)
        prow.addWidget(self.tpl_to_tcp)
        prow.addWidget(self.tpl_to_udp)
        form.addRow(prow)
        demo = QLabel(
            '演示种子（工程变量为空时）：passGate=1 matchScore=0.92 measureCount=3 '
            'defectCount=1 poseX=120 poseY=80'
        )
        demo.setWordWrap(True)
        demo.setStyleSheet('color:#888;font-size:11px;')
        form.addRow(demo)
        # Multi-device LocalBus inbox soft timeline (design-time; no field TCP)
        form.addRow(QLabel('多设备 LocalBus 软投递'))
        self.tpl_device_list = QListWidget()
        self.tpl_device_list.setObjectName('commMessageTemplateDeviceList')
        self.tpl_device_list.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        self.tpl_device_list.setMaximumHeight(90)
        self.tpl_device_list.setToolTip('选择要软投递的设备（默认含 LocalLoop）；无现场 TCP')
        form.addRow('目标设备', self.tpl_device_list)
        self.tpl_inbox_timeline = QPlainTextEdit()
        self.tpl_inbox_timeline.setObjectName('commMessageTemplateInboxTimeline')
        self.tpl_inbox_timeline.setReadOnly(True)
        self.tpl_inbox_timeline.setMaximumHeight(140)
        self.tpl_inbox_timeline.setStyleSheet(
            'font-family:monospace;font-size:11px;background:#1a2430;color:#80cbc4;'
        )
        self.tpl_inbox_timeline.setPlaceholderText(
            '多设备 LocalBus 收件箱软时间线（选模板 → 软投递后在此汇总）'
        )
        form.addRow('收件箱时间线', self.tpl_inbox_timeline)
        self.tpl_inbox_meta = QLabel('(尚未软投递)')
        self.tpl_inbox_meta.setObjectName('commMessageTemplateInboxMeta')
        self.tpl_inbox_meta.setWordWrap(True)
        self.tpl_inbox_meta.setStyleSheet('color:#666;font-size:11px;')
        form.addRow(self.tpl_inbox_meta)
        fan_row = QHBoxLayout()
        self.tpl_fanout_btn = QPushButton('多设备 LocalBus 软投递')
        self.tpl_fanout_btn.setObjectName('commMessageTemplateFanoutBtn')
        self.tpl_fanout_btn.setToolTip(
            '把当前模板展开正文软投递到所选设备 LocalBus 收件箱，并刷新时间线（无现场 TCP）'
        )
        self.tpl_fanout_btn.clicked.connect(self._tpl_soft_fanout_timeline)
        self.tpl_inbox_clear_btn = QPushButton('清空时间线')
        self.tpl_inbox_clear_btn.setObjectName('commMessageTemplateInboxClear')
        self.tpl_inbox_clear_btn.clicked.connect(self._tpl_clear_inbox_timeline)
        fan_row.addWidget(self.tpl_fanout_btn)
        fan_row.addWidget(self.tpl_inbox_clear_btn)
        fan_row.addStretch(1)
        form.addRow(fan_row)
        # live refresh
        self.tpl_body.textChanged.connect(self._tpl_refresh_preview)
        self.tpl_name.editingFinished.connect(self._tpl_commit_form)
        self.tpl_proto.currentIndexChanged.connect(lambda *_: self._tpl_commit_form())
        split.addWidget(right)
        split.setStretchFactor(1, 2)
        tpl_lay.addWidget(split, 1)
        self.tabs.addTab(tpl, '消息模板')
        self._tpl_items = []
        self._tpl_inbox_lines = []

        # --- TCP 测试（对标 VM 通信管理连通性）---
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
        self.tcp_preset = QComboBox()
        self.tcp_preset.setObjectName('tcpProtocolPreset')
        for lab, payload in (
            ('自定义', ''),
            ('PING', 'PING'),
            ('STATUS', 'STATUS'),
            ('HELP', 'HELP'),
            ('RUN', 'RUN'),
            ('STOP', 'STOP'),
            ('GET ok', 'GET ok'),
            ('SET ok 1', 'SET ok 1'),
            ('VARS', 'VARS'),
            ('MEAS (假量测)', 'MEAS'),
            ('JSON RUN', '{"cmd":"RUN"}'),
            ('JSON GET ok', '{"cmd":"GET","key":"ok"}'),
        ):
            self.tcp_preset.addItem(lab, payload)
        self.tcp_preset.setToolTip('环回模拟器协议预设（:19880；非现场设备）。选后填入「发送」。')
        self.tcp_preset.currentIndexChanged.connect(self._tcp_preset_apply)
        form.addRow('协议预设', self.tcp_preset)
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

        # —— 环回设备模拟器（无现场硬件）——
        sim_row = QHBoxLayout()
        self.tcp_sim_lamp = QLabel('○ 模拟器')
        self.tcp_sim_lamp.setToolTip('本地 TCP/UDP 环回协议模拟器（默认 19880/19881）')
        self.tcp_sim_start = QPushButton('启动环回模拟器')
        self.tcp_sim_start.setToolTip('监听 127.0.0.1:19880(TCP)/19881(UDP)；PING/GET/SET/VARS/MEAS/JSON；非现场硬件')
        self.tcp_sim_start.clicked.connect(self._tcp_sim_start)
        self.tcp_sim_stop = QPushButton('停止')
        self.tcp_sim_stop.clicked.connect(self._tcp_sim_stop)
        self.tcp_sim_fill = QPushButton('填入模拟器地址')
        self.tcp_sim_fill.clicked.connect(self._tcp_sim_fill_addr)
        sim_row.addWidget(self.tcp_sim_lamp)
        sim_row.addWidget(self.tcp_sim_start)
        sim_row.addWidget(self.tcp_sim_stop)
        sim_row.addWidget(self.tcp_sim_fill)
        sim_row.addStretch(1)
        tcp_lay.addLayout(sim_row)
        self._refresh_tcp_sim_lamp()

        # --- Real TCP transport (alongside LocalBus soft) ---
        real_box = QGroupBox('实时 TCP（Soft/LocalBus 旁路 · 真套接字）')
        real_box.setObjectName('commRealTcpBox')
        real_lay = QVBoxLayout(real_box)
        real_form = QFormLayout()
        self.tcp_transport = QComboBox()
        self.tcp_transport.setObjectName('commTcpTransport')
        self.tcp_transport.addItem('Soft / LocalBus（设计态软路径）', 'soft')
        self.tcp_transport.addItem('TCP 真套接字（listen/connect）', 'tcp')
        self.tcp_transport.setToolTip(
            'Soft=既有 LocalBus 软收发/自动应答；TCP=本页真实 bind/listen/connect，'
            '报文进下方真套接字抄本（无现场 PLC 时用 127.0.0.1 环回）'
        )
        self.tcp_transport.currentIndexChanged.connect(self._tcp_transport_changed)
        self.tcp_role = QComboBox()
        self.tcp_role.setObjectName('commTcpRole')
        self.tcp_role.addItem('TCP Server · 监听', 'server')
        self.tcp_role.addItem('TCP Client · 连接', 'client')
        self.tcp_real_host = QLineEdit('127.0.0.1')
        self.tcp_real_host.setObjectName('commTcpRealHost')
        self.tcp_real_port = QSpinBox()
        self.tcp_real_port.setObjectName('commTcpRealPort')
        self.tcp_real_port.setRange(0, 65535)
        self.tcp_real_port.setValue(19955)
        self.tcp_real_port.setToolTip('0=系统分配临时端口（仅 Server listen）')
        self.tcp_real_ack = QLineEdit('OK')
        self.tcp_real_ack.setObjectName('commTcpRealAck')
        self.tcp_real_autoack = OrangeSwitch(True)
        self.tcp_real_payload = QLineEdit('PING')
        self.tcp_real_payload.setObjectName('commTcpRealPayload')
        real_form.addRow('传输路径', self.tcp_transport)
        real_form.addRow('角色', self.tcp_role)
        real_form.addRow('地址', self.tcp_real_host)
        real_form.addRow('端口', self.tcp_real_port)
        real_form.addRow('自动应答', self.tcp_real_autoack)
        real_form.addRow('应答内容', self.tcp_real_ack)
        real_form.addRow('发送载荷', self.tcp_real_payload)
        real_lay.addLayout(real_form)
        brow = QHBoxLayout()
        self.tcp_real_status = QLabel('○ Soft / LocalBus')
        self.tcp_real_status.setObjectName('commTcpRealStatus')
        self.tcp_real_status.setToolTip('listen/connect 状态灯')
        self.tcp_real_listen_btn = QPushButton('Listen')
        self.tcp_real_listen_btn.setObjectName('commTcpRealListen')
        self.tcp_real_listen_btn.setToolTip('TCP Server：bind+listen 可配置 host:port')
        self.tcp_real_listen_btn.clicked.connect(self._tcp_real_listen)
        self.tcp_real_connect_btn = QPushButton('Connect')
        self.tcp_real_connect_btn.setObjectName('commTcpRealConnect')
        self.tcp_real_connect_btn.setToolTip('TCP Client：connect 到 host:port')
        self.tcp_real_connect_btn.clicked.connect(self._tcp_real_connect)
        self.tcp_real_send_btn = QPushButton('Send')
        self.tcp_real_send_btn.setObjectName('commTcpRealSend')
        self.tcp_real_send_btn.clicked.connect(self._tcp_real_send)
        self.tcp_real_stop_btn = QPushButton('Disconnect')
        self.tcp_real_stop_btn.setObjectName('commTcpRealStop')
        self.tcp_real_stop_btn.clicked.connect(self._tcp_real_stop)
        self.tcp_real_loop_btn = QPushButton('环回 e2e')
        self.tcp_real_loop_btn.setObjectName('commTcpRealLoopback')
        self.tcp_real_loop_btn.setToolTip(
            '127.0.0.1 listen→connect→send→recv→ack（真套接字，无外部 PLC）'
        )
        self.tcp_real_loop_btn.clicked.connect(self._tcp_real_loopback)
        brow.addWidget(self.tcp_real_status, 1)
        brow.addWidget(self.tcp_real_listen_btn)
        brow.addWidget(self.tcp_real_connect_btn)
        brow.addWidget(self.tcp_real_send_btn)
        brow.addWidget(self.tcp_real_stop_btn)
        brow.addWidget(self.tcp_real_loop_btn)
        real_lay.addLayout(brow)
        self.tcp_real_transcript = QPlainTextEdit()
        self.tcp_real_transcript.setObjectName('commTcpRealTranscript')
        self.tcp_real_transcript.setReadOnly(True)
        self.tcp_real_transcript.setPlaceholderText(
            '真套接字抄本：LISTEN/ACCEPT/TX/RX/ACK（Soft 模式不写此抄本）…'
        )
        self.tcp_real_transcript.setMinimumHeight(120)
        real_lay.addWidget(self.tcp_real_transcript, 1)
        tcp_lay.addWidget(real_box)
        self._tcp_real_session = None
        self._tcp_transport_changed()

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
        self.udp_preset = QComboBox()
        self.udp_preset.setObjectName('udpProtocolPreset')
        for lab, payload in (
            ('自定义', ''),
            ('PING', 'PING'),
            ('STATUS', 'STATUS'),
            ('RUN', 'RUN'),
            ('STOP', 'STOP'),
            ('MEAS (假量测)', 'MEAS'),
            ('JSON STATUS', '{"cmd":"STATUS"}'),
        ):
            self.udp_preset.addItem(lab, payload)
        self.udp_preset.setToolTip('UDP 协议预设（环回模拟器 :19881；非现场设备）')
        self.udp_preset.currentIndexChanged.connect(self._udp_preset_apply)

        self.udp_timeout = QSpinBox(); self.udp_timeout.setRange(100, 10000); self.udp_timeout.setValue(1500)
        self.udp_timeout.setSuffix(' ms')
        uform.addRow('主机', self.udp_host)
        uform.addRow('端口', self.udp_port)
        uform.addRow('发送', self.udp_payload)
        uform.addRow('协议预设', self.udp_preset)
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
        self._tpl_load_from_project(cm.get('messageTemplates'))
        try:
            self._tpl_refresh_device_list()
        except Exception:
            pass
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


    def _refresh_tcp_sim_lamp(self):
        try:
            from desktop import tcp_device_sim as tds
            st = tds.status()
        except Exception:
            st = {'running': False}
        if not hasattr(self, 'tcp_sim_lamp'):
            return
        if st.get('running'):
            self.tcp_sim_lamp.setText(f"● 模拟器 :{st.get('tcpPort')}/{st.get('udpPort')}")
            self.tcp_sim_lamp.setStyleSheet('color:#3dcc6d;font-weight:600;')
        else:
            self.tcp_sim_lamp.setText('○ 模拟器')
            self.tcp_sim_lamp.setStyleSheet('color:#888;')

    def _tcp_sim_start(self):
        from desktop import tcp_device_sim as tds
        from datetime import datetime
        try:
            st = tds.start()
            self._refresh_tcp_sim_lamp()
            host = st.get('host') or '127.0.0.1'
            port = int(st.get('tcpPort') or 19880)
            found = False
            for d in self._devices:
                if (d.get('protocol') or '') == 'TCP Client' and int(d.get('port') or 0) == port:
                    found = True
                    break
            if not found:
                self._devices.append(dict(
                    id='tcp-loopback-sim', name='TcpLoopbackSim', protocol='TCP Client',
                    enabled=True, host=host, port=port,
                    remark='环回协议模拟器（无现场硬件）',
                ))
                self.device_list.addItem(QListWidgetItem(self._devices[-1]['name']))
                self._refresh_event_devices()
                self._refresh_tcp_devices()
            self.tcp_host.setText(host)
            self.tcp_port.setValue(port)
            ts = datetime.now().strftime('%H:%M:%S')
            self.tcp_log.appendPlainText(
                f'[{ts}] 环回模拟器已启动 TCP :{port} UDP :{st.get("udpPort")} · PING/GET/SET/VARS/MEAS/JSON（模拟，非现场）'
            )
        except OSError as err:
            self.tcp_log.appendPlainText(f'启动模拟器失败：{err}')
            QMessageBox.warning(self, '环回模拟器', str(err))

    def _tcp_sim_stop(self):
        from desktop import tcp_device_sim as tds
        from datetime import datetime
        tds.stop()
        self._refresh_tcp_sim_lamp()
        ts = datetime.now().strftime('%H:%M:%S')
        self.tcp_log.appendPlainText(f'[{ts}] 环回模拟器已停止')

    def _tcp_sim_fill_addr(self):
        from desktop import tcp_device_sim as tds
        st = tds.status()
        self.tcp_host.setText(st.get('host') or '127.0.0.1')
        self.tcp_port.setValue(int(st.get('tcpPort') or 19880))
        self.tcp_payload.setText('PING')
        self.tcp_log.appendPlainText('已填入模拟器地址；可点「发送并读回」或先「启动环回模拟器」')

    def _tcp_preset_apply(self, _idx=None):
        """Fill tcp_payload from protocol preset (sim verbs; not field HW)."""
        try:
            payload = self.tcp_preset.currentData()
        except Exception:
            payload = None
        if payload:
            self.tcp_payload.setText(str(payload))

    @staticmethod
    def _parse_protocol_writeback_extras(text):
        """Thin wrapper → module-level parse_protocol_writeback_extras."""
        return parse_protocol_writeback_extras(text)

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



    # ----- Real TCP transport (wave155) -----
    def _tcp_transport_changed(self, *_args):
        mode = 'soft'
        try:
            mode = self.tcp_transport.currentData() or 'soft'
        except Exception:
            mode = 'soft'
        is_tcp = mode == 'tcp'
        for w in (
            getattr(self, 'tcp_role', None),
            getattr(self, 'tcp_real_host', None),
            getattr(self, 'tcp_real_port', None),
            getattr(self, 'tcp_real_ack', None),
            getattr(self, 'tcp_real_autoack', None),
            getattr(self, 'tcp_real_payload', None),
            getattr(self, 'tcp_real_listen_btn', None),
            getattr(self, 'tcp_real_connect_btn', None),
            getattr(self, 'tcp_real_send_btn', None),
            getattr(self, 'tcp_real_stop_btn', None),
            getattr(self, 'tcp_real_loop_btn', None),
        ):
            if w is not None:
                try:
                    w.setEnabled(is_tcp)
                except Exception:
                    pass
        if hasattr(self, 'tcp_real_status') and self.tcp_real_status is not None:
            if not is_tcp:
                self.tcp_real_status.setText('○ Soft / LocalBus')
            else:
                self._tcp_real_refresh_status()

    def _tcp_real_cfg(self):
        host = (self.tcp_real_host.text() or '').strip() or '127.0.0.1'
        port = int(self.tcp_real_port.value())
        role = self.tcp_role.currentData() or 'server'
        ack = (self.tcp_real_ack.text() or 'OK').strip() or 'OK'
        auto = bool(self.tcp_real_autoack.isChecked()) if hasattr(self, 'tcp_real_autoack') else True
        payload = self.tcp_real_payload.text() if hasattr(self, 'tcp_real_payload') else 'PING'
        return host, port, role, ack, auto, payload

    def _tcp_real_append_transcript(self, lines):
        box = getattr(self, 'tcp_real_transcript', None)
        if box is None:
            return
        cur = box.toPlainText().strip()
        chunk = '\n'.join(lines or [])
        text = (cur + '\n' + chunk).strip() if cur else chunk
        # keep last ~120 lines
        parts = text.splitlines()
        if len(parts) > 120:
            parts = parts[-120:]
        box.setPlainText('\n'.join(parts))
        try:
            box.verticalScrollBar().setValue(box.verticalScrollBar().maximum())
        except Exception:
            pass

    def _tcp_real_refresh_status(self):
        sess = getattr(self, '_tcp_real_session', None)
        lab = getattr(self, 'tcp_real_status', None)
        if lab is None:
            return
        mode = 'soft'
        try:
            mode = self.tcp_transport.currentData() or 'soft'
        except Exception:
            pass
        if mode != 'tcp':
            lab.setText('○ Soft / LocalBus')
            return
        if sess is None:
            lab.setText('○ TCP 空闲')
            return
        st = sess.status()
        lamp = '●' if st.get('status') in ('listening', 'connected') else '○'
        peer = st.get('peer') or ''
        lab.setText(
            f"{lamp} TCP {st.get('role')} · {st.get('status')} · "
            f"{st.get('host')}:{st.get('port')}"
            + (f' · peer {peer}' if peer else '')
            + f" · RX {st.get('recvCount', 0)} TX {st.get('sendCount', 0)}"
        )

    def _tcp_real_stop(self):
        sess = getattr(self, '_tcp_real_session', None)
        if sess is not None:
            try:
                sess.stop()
                self._tcp_real_append_transcript(sess.transcript(20) or ['[sys] stopped'])
            except Exception as exc:
                self._tcp_real_append_transcript([f'[err] stop {exc}'])
        self._tcp_real_session = None
        self._tcp_real_refresh_status()

    def _tcp_real_listen(self):
        if (self.tcp_transport.currentData() or 'soft') != 'tcp':
            self.tcp_transport.setCurrentIndex(self.tcp_transport.findData('tcp'))
        host, port, _role, ack, auto, _payload = self._tcp_real_cfg()
        self._tcp_real_stop()
        from desktop.tcp_realtime import RealTcpSession, ROLE_SERVER
        sess = RealTcpSession(
            host=host, port=port, role=ROLE_SERVER,
            auto_ack=auto, ack=ack, framing='lf',
        )
        # Do not touch Qt widgets from the accept/recv worker thread.
        # Transcript is pulled onto the UI thread via refresh/send/stop.
        st = sess.start()
        self._tcp_real_session = sess
        # reflect ephemeral port
        try:
            if int(st.get('port') or 0) > 0:
                self.tcp_real_port.setValue(int(st['port']))
        except Exception:
            pass
        self.tcp_role.setCurrentIndex(self.tcp_role.findData('server'))
        self._tcp_real_append_transcript(sess.transcript() or [f"LISTEN {st}"])
        self._tcp_real_refresh_status()
        return st

    def _tcp_real_connect(self):
        if (self.tcp_transport.currentData() or 'soft') != 'tcp':
            self.tcp_transport.setCurrentIndex(self.tcp_transport.findData('tcp'))
        host, port, _role, ack, auto, _payload = self._tcp_real_cfg()
        self._tcp_real_stop()
        from desktop.tcp_realtime import RealTcpSession, ROLE_CLIENT
        sess = RealTcpSession(
            host=host, port=port, role=ROLE_CLIENT,
            auto_ack=False, ack=ack, framing='lf',
        )
        st = sess.start()
        self._tcp_real_session = sess
        self.tcp_role.setCurrentIndex(self.tcp_role.findData('client'))
        self._tcp_real_append_transcript(sess.transcript() or [f"CONNECT {st}"])
        self._tcp_real_refresh_status()
        return st

    def _tcp_real_send(self):
        host, port, role, ack, auto, payload = self._tcp_real_cfg()
        # expand ${} with demo / project vars when natural
        try:
            from desktop.tcp_realtime import expand_payload
            bag = dict(getattr(self, '_TPL_DEMO_VARS', {}) or {})
            bag.setdefault('okng', 'OK')
            bag.setdefault('resultOk', 1)
            payload = expand_payload(payload, bag)
        except Exception:
            pass
        sess = getattr(self, '_tcp_real_session', None)
        if sess is None or (sess.status().get('status') not in ('listening', 'connected')):
            # oneshot against configured host:port
            from desktop.tcp_realtime import RealTcpSession
            tmp = RealTcpSession(host=host, port=port, role='client', auto_ack=False)
            res = tmp.send(payload, wait_reply=True, timeout_s=2.0)
            self._tcp_real_append_transcript(tmp.transcript() or [str(res)])
            if res.get('ok'):
                self._tcp_real_append_transcript([
                    f"oneshot TX {payload!r} → reply {res.get('reply')!r}"
                ])
            else:
                self._tcp_real_append_transcript([f"oneshot FAIL {res.get('error')}"])
            self._tcp_real_refresh_status()
            return res
        res = sess.send(payload, wait_reply=(role == 'client'), timeout_s=2.0)
        self._tcp_real_append_transcript(sess.transcript(30))
        self._tcp_real_refresh_status()
        return res

    def _tcp_real_loopback(self):
        """Product smoke from UI: listen→connect→send→recv→ack on 127.0.0.1."""
        if (self.tcp_transport.currentData() or 'soft') != 'tcp':
            self.tcp_transport.setCurrentIndex(self.tcp_transport.findData('tcp'))
        _host, _port, _role, ack, auto, payload = self._tcp_real_cfg()
        self._tcp_real_stop()
        from desktop.tcp_realtime import loopback_e2e
        # Prefer 127.0.0.1 + ephemeral to avoid clashing with sim :19880 / App :19777
        result = loopback_e2e(
            host='127.0.0.1', port=0, payload=payload or 'PING',
            ack=ack or 'OK', auto_ack=bool(auto),
        )
        lines = list(result.get('transcript') or [])
        lines.append(
            f"e2e {'PASS' if result.get('ok') else 'FAIL'} steps={result.get('steps')} "
            f"port={result.get('port')} reply={result.get('reply')!r} "
            f"err={result.get('error') or '—'}"
        )
        self._tcp_real_append_transcript(lines)
        if result.get('port'):
            try:
                self.tcp_real_port.setValue(int(result['port']))
            except Exception:
                pass
        self.tcp_real_host.setText('127.0.0.1')
        self._tcp_real_refresh_status()
        # Persist last real TCP e2e note on commManager (no Host cobind cascade)
        try:
            proj = self.document.project if self.document else {}
            cm = proj.setdefault('commManager', {}) if isinstance(proj, dict) else {}
            if isinstance(cm, dict):
                cm['lastRealTcpE2e'] = {
                    'ok': bool(result.get('ok')),
                    'port': result.get('port'),
                    'steps': result.get('steps'),
                    'reply': result.get('reply'),
                    'path': 'tcp-real-loopback',
                }
                cm['tcpTransport'] = 'tcp'
        except Exception:
            pass
        return result

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
        """Write test reply into flow/global vars; honor scope combo or flow./global. prefix.
        Also forward payload to MainWindow.fire_string_trigger for live RUN etc.
        """
        raw = (var_edit.text() or '').strip() if var_edit else ''
        # Always try string-trigger dispatch (even when no var binding)
        host = self.parent()
        while host is not None and not hasattr(host, 'fire_string_trigger'):
            host = host.parent() if hasattr(host, 'parent') else None
        fired = False
        if host is not None and text is not None and str(text) != '':
            try:
                fired = bool(host.fire_string_trigger(text, reason='通信试收'))
            except Exception as err:
                log_widget.appendPlainText(f'字符串触发异常：{err}')
        if not raw or not hasattr(self, 'document'):
            if fired:
                prefix = f'[{ts}] ' if ts else ''
                log_widget.appendPlainText(f'{prefix}已派发字符串触发')
            return
        # If user typed bare name, prefix with combo scope
        if '.' not in raw and scope_combo is not None:
            scope = scope_combo.currentData() or 'flow'
            raw = f'{scope}.{raw}'
        p = deepcopy(self.document.project)
        scope, name = write_project_variable(p, raw, text)
        if not name:
            if fired:
                prefix = f'[{ts}] ' if ts else ''
                log_widget.appendPlainText(f'{prefix}已派发字符串触发')
            return
        # remember prefs
        cm = ensure_comm_manager(p)
        prefs = cm.setdefault('testPrefs', {})
        prefs['lastVar'] = raw
        prefs['lastScope'] = scope
        # 细妆：结构化读回 — VALUE k=v / MEAS JSON / 纯 JSON → 额外写 sibling 字段
        extras = []
        try:
            extras = self._parse_protocol_writeback_extras(text)
        except Exception:
            extras = []
        for ek, ev in extras:
            write_project_variable(p, f'{scope}.{ek}', ev)
        self.document.commit(p)
        prefix = f'[{ts}] ' if ts else ''
        extra = ' · 已派发字符串触发' if fired else ''
        extra2 = f' · 解析字段 {",".join(k for k,_ in extras)}' if extras else ''
        log_widget.appendPlainText(f'{prefix}已写入变量 {scope}.{name}{extra}{extra2}')

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
            messageTemplates=self._tpl_collect(),
        )
        self.document.commit(p)
        n = len(p['commManager']['devices'])
        QMessageBox.information(self, '通信管理', f'已保存 {n} 个通讯设备及收发/心跳/响应配置。')
        self.accept()


    # ----- 消息模板（${} 展开）-----
    _TPL_DEMO_VARS = {
        'passGate': 1,
        'matchScore': 0.92,
        'matchCount': 2,
        'measureCount': 3,
        'defectCount': 1,
        'defectRatio': 0.05,
        'poseX': 120,
        'poseY': 80,
        'hbSeq': 1,
    }

    def _tpl_load_from_project(self, saved=None):
        """Populate template list from project + builtins."""
        self._tpl_items = merge_message_templates(saved)
        self.tpl_list.blockSignals(True)
        self.tpl_list.clear()
        for t in self._tpl_items:
            self.tpl_list.addItem(QListWidgetItem(t.get('name') or t.get('id') or '未命名'))
        self.tpl_list.blockSignals(False)
        if self._tpl_items:
            self.tpl_list.setCurrentRow(0)
            self._tpl_load_form(0)
        else:
            self.tpl_name.clear()
            self.tpl_body.clear()
            self.tpl_preview.clear()

    def _tpl_load_form(self, row):
        if row is None or row < 0 or row >= len(self._tpl_items):
            return
        t = self._tpl_items[row]
        self.tpl_name.blockSignals(True)
        self.tpl_body.blockSignals(True)
        self.tpl_proto.blockSignals(True)
        self.tpl_name.setText(str(t.get('name') or ''))
        body = str(t.get('body') or t.get('message') or '')
        self.tpl_body.setPlainText(body)
        proto = str(t.get('protocol') or 'line')
        idx = self.tpl_proto.findData(proto)
        if idx < 0:
            # try by text
            idx = max(0, self.tpl_proto.findText(proto))
        self.tpl_proto.setCurrentIndex(idx if idx >= 0 else 0)
        self.tpl_name.blockSignals(False)
        self.tpl_body.blockSignals(False)
        self.tpl_proto.blockSignals(False)
        self._tpl_refresh_preview()

    def _tpl_commit_form(self):
        row = self.tpl_list.currentRow()
        if row < 0 or row >= len(self._tpl_items):
            return
        t = self._tpl_items[row]
        t['name'] = self.tpl_name.text().strip() or t.get('id') or '未命名'
        t['body'] = self.tpl_body.toPlainText()
        t['protocol'] = self.tpl_proto.currentData() or self.tpl_proto.currentText()
        item = self.tpl_list.item(row)
        if item is not None:
            item.setText(t['name'])
        self._tpl_refresh_preview()

    def _tpl_refresh_preview(self):
        """Live ${} expand against project variables (+ demo seeds for empties)."""
        if not hasattr(self, 'tpl_preview'):
            return
        body = self.tpl_body.toPlainText() if hasattr(self, 'tpl_body') else ''
        proj = {}
        if self.document is not None:
            proj = getattr(self.document, 'project', None) or {}
        # Merge current form into item first so preview matches editor
        row = self.tpl_list.currentRow() if hasattr(self, 'tpl_list') else -1
        if 0 <= row < len(getattr(self, '_tpl_items', [])):
            self._tpl_items[row]['body'] = body
            self._tpl_items[row]['name'] = self.tpl_name.text().strip() or self._tpl_items[row].get('name')
        expanded = preview_expand_template(proj, body, demo_vars=self._TPL_DEMO_VARS)
        # If nothing changed and body had placeholders, still show demo expand
        if expanded == body and '${' in body:
            # force demo overlay
            seed = dict(self._TPL_DEMO_VARS)
            # wipe zeros that blocked fill
            fake = {'variables': dict(seed)}
            expanded = expand_payload_placeholders(fake, body)
        self.tpl_preview.setPlainText(expanded)
        self.tpl_preview.setProperty('expanded', expanded)
        self.tpl_preview.setToolTip('展开结果（设计态；无现场发送）')

    def _tpl_collect(self):
        self._tpl_commit_form()
        from copy import deepcopy as _dc
        return _dc(self._tpl_items or [])

    def _tpl_add_custom(self):
        n = len(self._tpl_items) + 1
        item = {
            'id': f'custom-{n}',
            'name': f'自定义模板{n}',
            'protocol': 'line',
            'body': 'RESULT ok=${flow.passGate}',
        }
        self._tpl_items.append(item)
        self.tpl_list.addItem(QListWidgetItem(item['name']))
        self.tpl_list.setCurrentRow(len(self._tpl_items) - 1)

    def _tpl_reset_builtin(self):
        self._tpl_items = builtin_message_templates()
        self.tpl_list.blockSignals(True)
        self.tpl_list.clear()
        for t in self._tpl_items:
            self.tpl_list.addItem(QListWidgetItem(t.get('name') or t.get('id') or '未命名'))
        self.tpl_list.blockSignals(False)
        if self._tpl_items:
            self.tpl_list.setCurrentRow(0)

    def _tpl_refresh_device_list(self):
        """Populate multi-select device list for soft fan-out (LocalLoop first)."""
        lw = getattr(self, 'tpl_device_list', None)
        if lw is None:
            return
        names = []
        for d in (getattr(self, '_devices', None) or []):
            if isinstance(d, dict):
                n = str(d.get('name') or '').strip()
                if n:
                    names.append(n)
        if 'LocalLoop' not in names:
            names.insert(0, 'LocalLoop')
        # de-dupe keep order
        seen = set()
        ordered = []
        for n in names:
            if n in seen:
                continue
            seen.add(n)
            ordered.append(n)
        prev = {it.text() for it in lw.selectedItems()}
        lw.blockSignals(True)
        lw.clear()
        for n in ordered:
            item = QListWidgetItem(n)
            lw.addItem(item)
            if (not prev and n == 'LocalLoop') or n in prev:
                item.setSelected(True)
        # ensure at least LocalLoop selected
        if not lw.selectedItems() and lw.count():
            lw.item(0).setSelected(True)
        lw.blockSignals(False)

    def _tpl_selected_devices(self):
        lw = getattr(self, 'tpl_device_list', None)
        if lw is None:
            return ['LocalLoop']
        names = [it.text() for it in lw.selectedItems() if it and it.text()]
        return names or ['LocalLoop']

    def _tpl_soft_fanout_timeline(self):
        """Expand current template and soft-fanout into multi-device LocalBus inbox timeline."""
        self._tpl_commit_form()
        self._tpl_refresh_preview()
        body = ''
        if hasattr(self, 'tpl_preview'):
            body = self.tpl_preview.toPlainText() or self.tpl_body.toPlainText()
        else:
            body = self.tpl_body.toPlainText() if hasattr(self, 'tpl_body') else ''
        name = self.tpl_name.text().strip() if hasattr(self, 'tpl_name') else '模板'
        devices = self._tpl_selected_devices()
        from datetime import datetime
        ts = datetime.now().strftime('%H:%M:%S')
        lines = list(getattr(self, '_tpl_inbox_lines', []) or [])
        lines.append(f'── [{ts}] soft fan-out · tpl={name or "模板"} · devices={",".join(devices)} · no field TCP')
        bytes_n = len(body.encode('utf-8'))
        for dev in devices:
            line = (
                f'[{ts}] TX→inbox {dev}/default tpl={name or "模板"} '
                f'bytes={bytes_n} │ {body[:80]}'
            )
            lines.append(line)
            # soft RX mirror
            lines.append(
                f'[{ts}] RX  {dev}/default path=softFanout-inbox bytes={bytes_n} │ {body[:80]}'
            )
        # keep last ~60 lines
        self._tpl_inbox_lines = lines[-60:]
        if hasattr(self, 'tpl_inbox_timeline') and self.tpl_inbox_timeline is not None:
            # group view
            grouped = ['── multi-device LocalBus inbox soft timeline ──']
            by = {}
            for ln in self._tpl_inbox_lines:
                if 'TX→inbox ' in ln or ln.startswith('[') and '] RX  ' in ln:
                    # extract device
                    try:
                        if 'TX→inbox ' in ln:
                            dev = ln.split('TX→inbox ', 1)[1].split('/', 1)[0]
                        else:
                            dev = ln.split('] RX  ', 1)[1].split('/', 1)[0]
                    except Exception:
                        dev = 'LocalLoop'
                    by.setdefault(dev, []).append(ln)
                else:
                    grouped.append(ln)
            for dev, lst in by.items():
                grouped.append(f'▶ {dev} · {len(lst)} 条')
                grouped.extend('  ' + x for x in lst[-8:])
            self.tpl_inbox_timeline.setPlainText('\n'.join(grouped))
        if hasattr(self, 'tpl_inbox_meta') and self.tpl_inbox_meta is not None:
            self.tpl_inbox_meta.setText(
                f'已软投递 {len(devices)} 设备 · tpl={name or "模板"} · '
                f'bytes={bytes_n} · LocalBus inbox · 无现场 TCP'
            )
        # Also try node softFanout when available (engine parity); ignore failures
        try:
            import subprocess, json as _json
            from pathlib import Path as _P
            root = _P(__file__).resolve().parents[1]
            js = (
                "const bus=require('./lib/comm-bus.cjs');"
                f"const r=bus.softFanoutTimeline({_json.dumps(devices)},{_json.dumps(body)},"
                f"{{template:{_json.dumps(name or '模板')}}});"
                "process.stdout.write(JSON.stringify({n:r.entries.length,timeline:r.timeline.slice(0,200)}));"
            )
            subprocess.run(
                ['node', '-e', js], cwd=str(root),
                capture_output=True, text=True, timeout=3,
            )
        except Exception:
            pass
        return {
            'devices': devices,
            'template': name,
            'bytes': bytes_n,
            'body': body,
            'lines': list(self._tpl_inbox_lines),
        }


    def _soft_recv_auto_ack_timeline(self):
        """recvEvents soft RX → LocalBus inbox → auto-ack grouped reply timeline (page chrome)."""
        try:
            enabled = bool(self.resp_enabled.isChecked()) if hasattr(self, 'resp_enabled') else False
        except Exception:
            enabled = False
        ack = self.resp_ack.text().strip() if hasattr(self, 'resp_ack') else 'OK'
        if not ack:
            ack = 'OK'
        try:
            timeout_ms = int(self.resp_timeout.value()) if hasattr(self, 'resp_timeout') else 3000
        except Exception:
            timeout_ms = 3000
        payload = ''
        if hasattr(self, 'ack_demo_payload') and self.ack_demo_payload is not None:
            payload = self.ack_demo_payload.text().strip()
        if not payload:
            payload = 'RESULT ok=1 score=0.92'
        recv_rows = []
        try:
            recv_rows = list(self.recv_table.rows() or [])
        except Exception:
            recv_rows = []
        devices = []
        seen = set()
        for ev in recv_rows:
            if not isinstance(ev, dict):
                continue
            d = str(ev.get('device') or ev.get('deviceName') or '').strip() or 'LocalLoop'
            if d in seen:
                continue
            seen.add(d)
            devices.append(d)
        if not devices:
            for d in (self._devices or []):
                n = str((d or {}).get('name') or '').strip()
                if n and n not in seen:
                    seen.add(n)
                    devices.append(n)
            if not devices:
                devices = ['LocalLoop']
        from datetime import datetime
        ts = datetime.now().strftime('%H:%M:%S')
        lines = list(getattr(self, '_ack_reply_lines', []) or [])
        lines.append(
            f'── [{ts}] soft recv→auto-ack · devices={",".join(devices)} · '
            f'ack={ack!r} · enabled={enabled} · no field TCP'
        )
        bytes_n = len(payload.encode('utf-8'))
        abytes = len(ack.encode('utf-8'))
        for dev in devices:
            lines.append(
                f'[{ts}] RX  {dev}/default path=recvEvent-soft bytes={bytes_n} │ {payload[:80]}'
            )
            tag = 'autoAck-reply' if enabled else 'autoAck-reply(forced)'
            lines.append(
                f'[{ts}] TX→ack {dev}/default path={tag} bytes={abytes} │ {ack[:80]}'
            )
        self._ack_reply_lines = lines[-80:]
        grouped = self._format_grouped_ack_timeline(self._ack_reply_lines)
        if hasattr(self, 'ack_reply_timeline') and self.ack_reply_timeline is not None:
            self.ack_reply_timeline.setPlainText(grouped)
        if hasattr(self, 'ack_reply_meta') and self.ack_reply_meta is not None:
            self.ack_reply_meta.setText(
                f'已软收 {len(devices)} 设备 · ACK={ack!r} · '
                f'{"应答开" if enabled else "应答关·强制演示"} · '
                f'timeout={timeout_ms}ms · LocalBus · 无现场 TCP'
            )
        try:
            proj = self.document.project if self.document else {}
            cm = proj.setdefault('commManager', {}) if isinstance(proj, dict) else {}
            if isinstance(cm, dict):
                cm['lastSoftAutoAck'] = {
                    'devices': devices,
                    'ack': ack,
                    'enabled': enabled,
                    'payload': payload[:200],
                    'timeoutMs': timeout_ms,
                }
        except Exception:
            pass
        try:
            import subprocess, json as _json
            from pathlib import Path as _P
            root = _P(__file__).resolve().parents[1]
            eng_proj = {
                'commManager': {
                    'recvEvents': recv_rows or [
                        {'device': d, 'variable': 'flow.lastRecv'} for d in devices
                    ],
                    'response': {
                        'enabled': True,
                        'timeoutMs': timeout_ms,
                        'ack': ack,
                    },
                    'devices': [
                        {'name': d, 'protocol': 'Local Bus'} for d in devices
                    ],
                }
            }
            js = (
                "const bus=require('./lib/comm-bus.cjs');bus.reset();"
                f"const r=bus.softAutoAckFromRecvEvents({_json.dumps(eng_proj)},{_json.dumps(payload)},"
                f"{{forceAck:true,ack:{_json.dumps(ack)}}});"
                "process.stdout.write(JSON.stringify({n:r.entries.length,devs:r.devices}));"
            )
            subprocess.run(
                ['node', '-e', js], cwd=str(root),
                capture_output=True, text=True, timeout=3,
            )
        except Exception:
            pass
        bag = {
            'devices': devices,
            'ack': ack,
            'enabled': enabled,
            'payload': payload,
            'lines': list(self._ack_reply_lines),
            'grouped': grouped,
        }
        # Soft co-update OK-NG dashboard page strip when auto-ack fires (page chrome)
        try:
            # Infer soft judge from payload
            low = str(payload or '').lower()
            judge = 'NG' if ('okng=ng' in low or ' ok=0' in low or 'ng=1' in low) else 'OK'
            if 'okng=ok' in low or ' ok=1' in low:
                judge = 'OK'
            # Only paint local strip + HMI when co-update widgets exist; avoid recursion
            if hasattr(self, 'okng_recv_ack_strip') and self.okng_recv_ack_strip is not None:
                # Lightweight local mirror without re-entering auto-ack
                from datetime import datetime as _dt
                _ts = _dt.now().strftime('%H:%M:%S')
                ok_n = 1 if judge == 'OK' else 0
                ng_n = 0 if judge == 'OK' else 1
                page = (
                    f'── OK-NG ↔ recvEvents auto-ack co-update (from auto-ack) ──\n'
                    f'[{_ts}] okng={judge} · OK {ok_n} NG {ng_n} · ack={ack!r} · '
                    f'devices={",".join(devices) or "—"} · enabled={enabled}'
                )
                self.okng_recv_ack_strip.setPlainText(page)
                if hasattr(self, 'okng_recv_ack_meta') and self.okng_recv_ack_meta is not None:
                    self.okng_recv_ack_meta.setText(
                        f'共更(自应答) · okng={judge} · ack={ack!r} · '
                        f'devices={",".join(devices) or "—"}'
                    )
                # Push HMI/host without re-calling auto-ack
                hmi = None
                host = None
                try:
                    w = self.parent()
                    for _ in range(8):
                        if w is None:
                            break
                        hmi = getattr(w, 'operator_hmi', None) or hmi
                        host = getattr(w, 'host_state_machine', None) or getattr(w, 'host_sm', None) or host
                        if hmi is not None or host is not None:
                            break
                        w = w.parent() if hasattr(w, 'parent') else None
                    if hmi is not None and host is None:
                        host = getattr(hmi, '_host_sm', None)
                except Exception:
                    pass
                if hmi is not None and hasattr(hmi, 'co_update_okng_recv_autoack'):
                    try:
                        hmi.co_update_okng_recv_autoack(
                            judge=judge, ok_n=ok_n, ng_n=ng_n, ack=ack,
                            devices=devices, enabled=enabled,
                            host_state='Idle' if judge == 'OK' else 'Alarm',
                            payload=payload,
                        )
                    except Exception:
                        pass
                if host is not None and hasattr(host, 'set_okng_recv_autoack_co_update_strip'):
                    try:
                        host.set_okng_recv_autoack_co_update_strip(
                            f'OK-NG↔recv自动应答 · okng={judge} · ack={ack!r}',
                            okng=judge, ok_n=ok_n, ng_n=ng_n, ack=ack,
                        )
                    except Exception:
                        pass
                bag['okngCoUpdate'] = {'okng': judge, 'ok': ok_n, 'ng': ng_n}
        except Exception:
            pass
        return bag

    def _format_grouped_ack_timeline(self, lines=None):
        """Page-chrome grouped RX/ACK view by device."""
        lines = list(lines if lines is not None else getattr(self, '_ack_reply_lines', []) or [])
        if not lines:
            return '(recvEvents 自动应答分组时间线空)'
        grouped = ['── recvEvents ↔ LocalBus auto-ack / grouped reply ──']
        by = {}
        headers = []
        for ln in lines:
            if ln.startswith('──'):
                headers.append(ln)
                continue
            dev = 'LocalLoop'
            try:
                if '] RX  ' in ln:
                    dev = ln.split('] RX  ', 1)[1].split('/', 1)[0]
                elif '] TX→ack ' in ln:
                    dev = ln.split('] TX→ack ', 1)[1].split('/', 1)[0]
            except Exception:
                pass
            by.setdefault(dev, []).append(ln)
        grouped.extend(headers[-3:])
        for dev, lst in by.items():
            rx_n = sum(1 for x in lst if '] RX  ' in x)
            ack_n = sum(1 for x in lst if 'TX→ack ' in x)
            grouped.append(f'▶ {dev} · RX {rx_n} · ACK {ack_n}')
            grouped.extend('  ' + x for x in lst[-10:])
        return '\n'.join(grouped)

    def _clear_recv_auto_ack_timeline(self):
        self._ack_reply_lines = []
        if hasattr(self, 'ack_reply_timeline') and self.ack_reply_timeline is not None:
            self.ack_reply_timeline.setPlainText('(recvEvents 自动应答分组时间线空)')
        if hasattr(self, 'ack_reply_meta') and self.ack_reply_meta is not None:
            self.ack_reply_meta.setText('(尚未软收→应答)')


    def _soft_autoack_sendevents_format_roundtrip(self):
        """auto-ack reply → sendEvents / format_data soft round-trip page strip (no field TCP)."""
        ack_result = self._soft_recv_auto_ack_timeline() or {}
        ack = ack_result.get('ack') or (self.resp_ack.text().strip() if hasattr(self, 'resp_ack') else 'OK') or 'OK'
        payload = ack_result.get('payload') or ''
        if hasattr(self, 'ack_demo_payload') and self.ack_demo_payload is not None and not payload:
            payload = self.ack_demo_payload.text().strip()
        if not payload:
            payload = 'RESULT ok=1 score=0.92'
        send_rows = []
        try:
            send_rows = list(self.send_table.rows() or [])
        except Exception:
            send_rows = []
        from datetime import datetime
        import re
        ts = datetime.now().strftime('%H:%M:%S')
        # Soft vars bag for ${} expand (format_data style)
        vars_bag = {
            'flow': {'lastRecv': payload, 'ack': ack, 'score': '0.92'},
            'global': {'taskStatus': 'ready', 'hmiRecipe': '—'},
        }
        try:
            proj = self.document.project if self.document else {}
            if isinstance(proj, dict):
                g = (proj.get('variables') or {}).get('global') or {}
                f = (proj.get('variables') or {}).get('flow') or {}
                if isinstance(g, dict):
                    vars_bag['global'].update({k: str(v) for k, v in g.items()})
                if isinstance(f, dict):
                    vars_bag['flow'].update({k: str(v) for k, v in f.items()})
                vars_bag['flow']['lastRecv'] = payload
                vars_bag['flow']['ack'] = ack
        except Exception:
            pass

        def _expand(text):
            raw = text if text is not None else ''
            raw = str(raw)
            if '${' not in raw:
                return raw
            def repl(m):
                inner = (m.group(1) or '').strip()
                if '.' in inner:
                    scope, name = inner.split('.', 1)
                else:
                    scope, name = 'flow', inner
                bag = vars_bag.get(scope) or {}
                if name in bag:
                    return str(bag[name])
                return m.group(0)
            return re.sub(r'\$\{([^}]+)\}', repl, raw)

        if not send_rows:
            devs = ack_result.get('devices') or ['LocalLoop']
            send_rows = [{
                'name': 'format→send soft',
                'device': devs[0],
                'message': 'FMT ${flow.lastRecv} ACK=${flow.ack} status=${global.taskStatus}',
                'topic': '', 'variable': '',
            }]
        lines = [
            '── auto-ack → sendEvents / format_data soft round-trip ──',
            f'[{ts}] ACK devices={",".join(ack_result.get("devices") or [])} · ack={ack!r}',
        ]
        # Mirror a few ack timeline lines
        for ln in list(ack_result.get('lines') or [])[-4:]:
            if not str(ln).startswith('──'):
                lines.append(str(ln))
        tx_n = 0
        devices = []
        for ev in send_rows:
            if not isinstance(ev, dict):
                continue
            dev = str(ev.get('device') or ev.get('deviceName') or 'LocalLoop').strip() or 'LocalLoop'
            devices.append(dev)
            raw = str(ev.get('message') or '')
            formatted = _expand(raw or 'RESULT ${flow.lastRecv}')
            note = 'format_data-expand' if '${' in raw else 'sendEvent-plain'
            lines.append(
                f'[{ts}] TX→send {dev}/default path={note} bytes={len(formatted.encode("utf-8"))} │ {formatted[:80]}'
            )
            tx_n += 1
        page = '\n'.join(lines)
        if hasattr(self, 'ack_rt_strip') and self.ack_rt_strip is not None:
            self.ack_rt_strip.setPlainText(page)
        if hasattr(self, 'ack_rt_meta') and self.ack_rt_meta is not None:
            self.ack_rt_meta.setText(
                f'软往返 · ACK={ack!r} · sendEvents TX={tx_n} · devices={",".join(dict.fromkeys(devices))} · '
                f'format_data ${{}} · LocalBus · 无现场 TCP'
            )
        try:
            proj = self.document.project if self.document else {}
            cm = proj.setdefault('commManager', {}) if isinstance(proj, dict) else {}
            if isinstance(cm, dict):
                cm['lastSoftAckSendFormatRt'] = {
                    'ack': ack, 'payload': payload[:200], 'tx': tx_n, 'devices': list(dict.fromkeys(devices)),
                }
        except Exception:
            pass
        # Engine soft path
        try:
            import subprocess, json as _json
            from pathlib import Path as _P
            root = _P(__file__).resolve().parents[1]
            eng_proj = {
                'commManager': {
                    'recvEvents': [
                        {'device': d, 'variable': 'flow.lastRecv'}
                        for d in (ack_result.get('devices') or ['LocalLoop'])
                    ],
                    'sendEvents': send_rows,
                    'response': {'enabled': True, 'timeoutMs': 3000, 'ack': ack},
                    'devices': [
                        {'name': d, 'protocol': 'Local Bus'}
                        for d in list(dict.fromkeys(
                            list(ack_result.get('devices') or []) + devices
                        )) or ['LocalLoop']
                    ],
                }
            }
            js = (
                "const bus=require('./lib/comm-bus.cjs');bus.reset();"
                f"const r=bus.softAutoAckSendEventsFormatRoundTrip({_json.dumps(eng_proj)},{_json.dumps(payload)},"
                f"{{forceAck:true,ack:{_json.dumps(ack)}}});"
                "process.stdout.write(JSON.stringify({tx:r.sendEntries.length,devs:r.devices,ack:r.ack&&r.ack.ack}));"
            )
            subprocess.run(
                ['node', '-e', js], cwd=str(root),
                capture_output=True, text=True, timeout=3,
            )
        except Exception:
            pass
        return {
            'ack': ack_result,
            'tx': tx_n,
            'devices': list(dict.fromkeys(devices)),
            'pageStrip': page,
        }


    def soft_result_okng_send_tx(self, *, judge='OK', recipe='', status_var='', vars_bag=None, snapshot=None):
        """production_task result OK/NG → sendEvents soft TX page strip (LocalBus only)."""
        from datetime import datetime
        j = str(judge or 'OK')
        upper = j.upper()
        is_ok = upper in ('OK', 'PASS', '良', '通过', 'TRUE', '1')
        snap = dict(snapshot or {})
        recipe = str(recipe or snap.get('recipe') or '')
        status_var = str(status_var or '')
        ts = datetime.now().strftime('%H:%M:%S')
        # Collect sendEvents from table or project
        try:
            send_rows = list(self.send_table.rows() or [])
        except Exception:
            send_rows = []
        proj = {}
        try:
            proj = dict(self.document.project or {})
        except Exception:
            proj = {}
        cm = proj.get('commManager') or {}
        if not send_rows:
            send_rows = list(cm.get('sendEvents') or [])
        soft_vars = dict(vars_bag or {})
        soft_vars.setdefault('flow', {})
        soft_vars.setdefault('global', {})
        soft_vars['flow'].update({
            'okng': j, 'judge': j,
            'resultOk': 1 if is_ok else 0,
            'resultNg': 0 if is_ok else 1,
            'lastResult': j,
            'taskStatus': 'ready' if is_ok else 'alarm',
            'recipe': recipe,
        })
        soft_vars['global'].update({
            'taskStatus': soft_vars['flow']['taskStatus'],
            'recipe': recipe,
        })
        # Merge project vars lightly
        try:
            for scope_k, bag in (proj.get('variables') or {}).items():
                if isinstance(bag, dict):
                    soft_vars.setdefault(scope_k, {}).update(bag)
        except Exception:
            pass

        def _expand(msg, bag):
            out = str(msg or '')
            flat = {}
            for sk, vals in (bag or {}).items():
                if isinstance(vals, dict):
                    for k, v in vals.items():
                        flat[f'{sk}.{k}'] = v
                        flat[k] = v
            i = 0
            while '${' in out and i < 64:
                i += 1
                s = out.find('${')
                e = out.find('}', s)
                if s < 0 or e < 0:
                    break
                key = out[s + 2:e].strip()
                out = out[:s] + str(flat.get(key, '')) + out[e + 1:]
            return out

        if not send_rows:
            send_rows = [
                {'name': 'resultOkNg', 'device': 'LocalLoop',
                 'message': 'RESULT okng=${flow.okng} ok=${flow.resultOk} ng=${flow.resultNg} recipe=${flow.recipe}'},
                {'name': 'status', 'device': 'LocalLoop',
                 'message': 'status=${flow.taskStatus} judge=${flow.judge}'},
            ]
        devices = []
        entries = []
        for ev in send_rows:
            if not isinstance(ev, dict):
                continue
            device = str(ev.get('device') or ev.get('deviceName') or 'LocalLoop')
            channel = str(ev.get('name') or ev.get('channel') or ev.get('topic') or 'result')
            raw = str(ev.get('message') or '')
            formatted = _expand(raw or f'RESULT okng={j}', soft_vars)
            note = 'format_data-expand' if '${' in raw else 'sendEvent-plain'
            line = (
                f'[{ts}] TX→result {device}/{channel} okng={j} path={note} '
                f'bytes={len(formatted.encode("utf-8"))} │ {formatted[:80]}'
            )
            entries.append({
                'device': device, 'channel': channel, 'payload': formatted,
                'note': note, 'okng': j, 'line': line, 'raw': raw,
            })
            if device not in devices:
                devices.append(device)
        tx_n = len(entries)
        hdr = '── production_task result OK/NG → Comm sendEvents soft TX ──'
        page = hdr + '\n' + f'okng={j} · resultOk={1 if is_ok else 0} · TX={tx_n} · devices={",".join(devices) or "—"} · LocalBus\n'
        page += '\n'.join(e['line'] for e in entries)
        if hasattr(self, 'result_okng_tx_strip') and self.result_okng_tx_strip is not None:
            self.result_okng_tx_strip.setPlainText(page)
            if is_ok:
                self.result_okng_tx_strip.setStyleSheet(
                    'font-family:monospace;font-size:11px;background:#1c2a1c;color:#9ed9a8;'
                )
            else:
                self.result_okng_tx_strip.setStyleSheet(
                    'font-family:monospace;font-size:11px;background:#2a1c1c;color:#ffb4b4;'
                )
        if hasattr(self, 'result_okng_tx_meta') and self.result_okng_tx_meta is not None:
            self.result_okng_tx_meta.setText(
                f'闭环出站 · okng={j!r} · sendEvents TX={tx_n} · devices={",".join(devices) or "—"} · '
                f'format_data ${{}} · LocalBus · 无现场 TCP'
                + (f' · {status_var}' if status_var else '')
            )
        # Engine parity
        try:
            import subprocess, json as _json
            from pathlib import Path as _P
            root = _P(__file__).resolve().parents[1]
            eng_proj = {
                'commManager': {
                    'devices': cm.get('devices') or [{'name': d, 'protocol': 'Local Bus'} for d in (devices or ['LocalLoop'])],
                    'sendEvents': send_rows,
                }
            }
            js = (
                "const bus=require('./lib/comm-bus.cjs');bus.reset();"
                f"const r=bus.softResultOkNgSendEventsTx({_json.dumps(eng_proj)},{_json.dumps(j)},"
                f"{_json.dumps({'recipe': recipe, 'taskStatus': soft_vars['flow']['taskStatus']})});"
                "process.stdout.write(JSON.stringify({tx:(r.sendEntries||[]).length,okng:r.okng}));"
            )
            subprocess.run(
                ['node', '-e', js], cwd=str(root),
                capture_output=True, text=True, timeout=4,
            )
        except Exception:
            pass
        # Closed-loop page chrome: result-out → Host SM / HMI status rail
        loop_bag = {}
        try:
            loop_bag = self._soft_close_loop_host_sm_status_rail(
                judge=j, recipe=recipe, status_var=status_var,
                tx_n=tx_n, devices=devices, is_ok=is_ok, snap=snap,
            )
        except Exception:
            loop_bag = {}
        return {
            'okng': j, 'tx': tx_n, 'devices': devices, 'entries': entries,
            'resultOk': 1 if is_ok else 0, 'pageStrip': page,
            'statusRailLoop': loop_bag,
        }

    def _soft_close_loop_host_sm_status_rail(self, *, judge='OK', recipe='', status_var='',
                                            tx_n=0, devices=None, is_ok=True, snap=None):
        """sendEvents result-out → Host SM / HMI status rail closed-loop page chrome."""
        from datetime import datetime
        snap = dict(snap or {})
        j = str(judge or 'OK')
        devices = list(devices or [])
        ts = datetime.now().strftime('%H:%M:%S')
        host_state = 'Idle' if is_ok else 'Alarm'
        rail_status = 'ready' if is_ok else 'alarm'
        # Resolve Host SM + HMI from document/parent window
        hmi = None
        host = None
        try:
            parent = self.parent()
            # walk up to MainWindow-ish
            w = parent
            for _ in range(8):
                if w is None:
                    break
                hmi = getattr(w, 'operator_hmi', None) or hmi
                host = getattr(w, 'host_state_machine', None) or getattr(w, 'host_sm', None) or host
                if hmi is not None or host is not None:
                    break
                w = w.parent() if hasattr(w, 'parent') else None
            if hmi is not None and host is None:
                host = getattr(hmi, '_host_sm', None)
        except Exception:
            pass
        liaison = []
        if host is not None:
            try:
                if hasattr(host, 'set_state'):
                    host.set_state(host_state, f'sendEvents 出站 {j} · {recipe or "—"}')
                if hasattr(host, 'push_liaison_event'):
                    code = 'TX_OK_RAIL' if is_ok else 'TX_NG_RAIL'
                    kind = '出站通过' if is_ok else '出站报警'
                    host.push_liaison_event(
                        f'sendEvents→状态轨 · {j} · TX={tx_n} · {",".join(devices) or "LocalLoop"}',
                        kind=kind, code=code,
                    )
                    liaison.append(code)
                if hasattr(host, 'set_comm_tx_status_rail_loop_strip'):
                    host.set_comm_tx_status_rail_loop_strip(
                        f'出站闭环 · okng={j} · host={host_state} · TX={tx_n} · '
                        f'devices={",".join(devices) or "—"} · rail={rail_status}',
                        okng=j, host_state=host_state, tx_n=tx_n,
                    )
            except Exception:
                pass
        # HMI status rail / page chrome
        if hmi is not None and hasattr(hmi, 'apply_comm_tx_status_rail_closed_loop'):
            try:
                hmi.apply_comm_tx_status_rail_closed_loop(
                    judge=j, recipe=recipe, status_var=status_var,
                    host_state=host_state, rail_status=rail_status,
                    tx_n=tx_n, devices=devices, snap=snap,
                )
            except Exception:
                pass
        lines = [
            '── sendEvents result-out → Host SM / HMI status rail closed-loop ──',
            f'[{ts}] okng={j} · host→{host_state} · rail={rail_status} · TX={tx_n} · '
            f'devices={",".join(devices) or "—"} · liaison={",".join(liaison) or "—"}',
            f'  statusVar={status_var or "—"} · recipe={recipe or "—"} · LocalBus · 页铬非芯片',
            f'  targets=hostStateRail · hmiStatusRail · pageChromeBanner · fixedBars',
        ]
        page = '\n'.join(lines)
        if hasattr(self, 'tx_status_rail_loop_strip') and self.tx_status_rail_loop_strip is not None:
            self.tx_status_rail_loop_strip.setPlainText(page)
            if is_ok:
                self.tx_status_rail_loop_strip.setStyleSheet(
                    'font-family:monospace;font-size:11px;background:#1c2a1c;color:#9ed9a8;'
                )
            else:
                self.tx_status_rail_loop_strip.setStyleSheet(
                    'font-family:monospace;font-size:11px;background:#2a1c1c;color:#ffb4b4;'
                )
        if hasattr(self, 'tx_status_rail_loop_meta') and self.tx_status_rail_loop_meta is not None:
            self.tx_status_rail_loop_meta.setText(
                f'闭环 · okng={j} · host={host_state} · rail={rail_status} · TX={tx_n} · '
                f'liaison={",".join(liaison) or "—"} · 状态轨页铬'
            )
        return {
            'okng': j, 'hostState': host_state, 'railStatus': rail_status,
            'tx': tx_n, 'devices': devices, 'liaison': liaison, 'pageStrip': page,
        }

    def soft_co_bind_liaison_send_ack_response(self, *, judge='OK', recipe='', ack='',
                                               status_var='', snapshot=None):
        """Host SM liaison timeline ↔ Comm sendEvents ack/response page co-bind (no field TCP)."""
        from datetime import datetime
        j = str(judge or 'OK')
        upper = j.upper()
        is_ok = upper in ('OK', 'PASS', '良', '通过', 'TRUE', '1', 'ACK')
        snap = dict(snapshot or {})
        recipe = str(recipe or snap.get('recipe') or '')
        status_var = str(status_var or snap.get('statusVar') or '')
        ts = datetime.now().strftime('%H:%M:%S')
        # Resolve ack text from response tab
        if not ack:
            try:
                ack = self.resp_ack.text().strip() if hasattr(self, 'resp_ack') else ''
            except Exception:
                ack = ''
        if not ack:
            ack = 'ACK_OK' if is_ok else 'ACK_NG'
        try:
            enabled = bool(self.resp_enabled.isChecked()) if hasattr(self, 'resp_enabled') else True
        except Exception:
            enabled = True
        # Collect sendEvents
        try:
            send_rows = list(self.send_table.rows() or [])
        except Exception:
            send_rows = []
        proj = {}
        try:
            proj = dict(self.document.project or {})
        except Exception:
            proj = {}
        cm = proj.get('commManager') or {}
        if not send_rows:
            send_rows = list(cm.get('sendEvents') or [])
        if not send_rows:
            send_rows = [
                {'name': 'ackResponse', 'device': 'LocalLoop',
                 'message': 'ACK okng=${flow.okng} ack=${flow.ack} recipe=${flow.recipe}'},
            ]
        soft_vars = {
            'flow': {
                'okng': j, 'judge': j, 'ack': ack,
                'resultOk': 1 if is_ok else 0,
                'resultNg': 0 if is_ok else 1,
                'taskStatus': 'ready' if is_ok else 'alarm',
                'recipe': recipe,
            },
            'global': {
                'taskStatus': 'ready' if is_ok else 'alarm',
                'recipe': recipe, 'ack': ack,
            },
        }
        def _expand(msg, bag):
            out = str(msg or '')
            flat = {}
            for sk, vals in (bag or {}).items():
                if isinstance(vals, dict):
                    for k, v in vals.items():
                        flat[f'{sk}.{k}'] = v
                        flat[k] = v
            i = 0
            while '${' in out and i < 64:
                i += 1
                s = out.find('${')
                e = out.find('}', s)
                if s < 0 or e < 0:
                    break
                key = out[s + 2:e].strip()
                out = out[:s] + str(flat.get(key, '')) + out[e + 1:]
            return out
        devices = []
        entries = []
        for ev in send_rows:
            if not isinstance(ev, dict):
                continue
            device = str(ev.get('device') or ev.get('deviceName') or 'LocalLoop')
            channel = str(ev.get('name') or ev.get('channel') or 'ack')
            raw = str(ev.get('message') or '')
            formatted = _expand(raw or f'ACK okng={j} ack={ack}', soft_vars)
            line = (
                f'[{ts}] TX→ack {device}/{channel} okng={j} ack={ack!r} '
                f'bytes={len(formatted.encode("utf-8"))} │ {formatted[:72]}'
            )
            entries.append({
                'device': device, 'channel': channel, 'payload': formatted,
                'ack': ack, 'okng': j, 'line': line,
            })
            if device not in devices:
                devices.append(device)
        tx_n = len(entries)
        # Resolve Host SM + HMI
        hmi = None
        host = None
        try:
            w = self.parent()
            for _ in range(8):
                if w is None:
                    break
                hmi = getattr(w, 'operator_hmi', None) or hmi
                host = getattr(w, 'host_state_machine', None) or getattr(w, 'host_sm', None) or host
                if hmi is not None or host is not None:
                    break
                w = w.parent() if hasattr(w, 'parent') else None
            if hmi is not None and host is None:
                host = getattr(hmi, '_host_sm', None)
        except Exception:
            pass
        liaison_codes = []
        host_state = 'Idle' if is_ok else 'Alarm'
        if host is not None:
            try:
                if hasattr(host, 'set_state'):
                    host.set_state(host_state, f'sendEvents 应答 {ack} · {j}')
                if hasattr(host, 'push_liaison_event'):
                    code = 'ACK_OK_LIAISON' if is_ok else 'ACK_NG_LIAISON'
                    kind = '应答通过' if is_ok else '应答报警'
                    host.push_liaison_event(
                        f'sendEvents应答↔联调 · {j} · ack={ack} · TX={tx_n} · '
                        f'{",".join(devices) or "LocalLoop"}',
                        kind=kind, code=code,
                    )
                    liaison_codes.append(code)
                if hasattr(host, 'co_bind_liaison_send_ack_response'):
                    host.co_bind_liaison_send_ack_response(
                        judge=j, ack=ack, recipe=recipe, tx_n=tx_n,
                        devices=devices, host_state=host_state,
                        liaison=liaison_codes, enabled=enabled,
                    )
            except Exception:
                pass
        if hmi is not None and hasattr(hmi, 'co_bind_liaison_send_ack_response'):
            try:
                hmi.co_bind_liaison_send_ack_response(
                    judge=j, ack=ack, recipe=recipe, status_var=status_var,
                    tx_n=tx_n, devices=devices, host_state=host_state,
                    liaison=liaison_codes, enabled=enabled,
                )
            except Exception:
                pass
        # Pull recent liaison timeline for page strip
        lia_lines = []
        if host is not None and hasattr(host, 'filtered_liaison_events'):
            try:
                for e in list(host.filtered_liaison_events(0) or [])[-6:]:
                    lia_lines.append(
                        f"  [{e.get('ts') or '?'}] {e.get('code') or '—'} · "
                        f"{e.get('kind') or ''} · {str(e.get('text') or '')[:60]}"
                    )
            except Exception:
                pass
        lines = [
            '── Host SM liaison timeline ↔ Comm sendEvents ack/response page co-bind ──',
            f'[{ts}] okng={j} · ack={ack!r} · enabled={enabled} · host→{host_state} · '
            f'TX={tx_n} · devices={",".join(devices) or "—"} · '
            f'liaison={",".join(liaison_codes) or "—"}',
            f'  statusVar={status_var or "—"} · recipe={recipe or "—"} · LocalBus · 页铬非芯片',
            '  ── sendEvents ack TX ──',
        ]
        lines.extend(f'  {e["line"]}' for e in entries)
        if lia_lines:
            lines.append('  ── Host SM liaison (recent) ──')
            lines.extend(lia_lines)
        page = '\n'.join(lines)
        if hasattr(self, 'liaison_ack_cobind_strip') and self.liaison_ack_cobind_strip is not None:
            self.liaison_ack_cobind_strip.setPlainText(page)
            if is_ok:
                self.liaison_ack_cobind_strip.setStyleSheet(
                    'font-family:monospace;font-size:11px;background:#1c2a1c;color:#9ed9a8;'
                )
            else:
                self.liaison_ack_cobind_strip.setStyleSheet(
                    'font-family:monospace;font-size:11px;background:#2a1c1c;color:#ffb4b4;'
                )
        if hasattr(self, 'liaison_ack_cobind_meta') and self.liaison_ack_cobind_meta is not None:
            self.liaison_ack_cobind_meta.setText(
                f'共绑 · okng={j} · ack={ack!r} · host={host_state} · TX={tx_n} · '
                f'liaison={",".join(liaison_codes) or "—"} · 联调↔应答页铬'
            )
        return {
            'okng': j, 'ack': ack, 'tx': tx_n, 'devices': devices,
            'hostState': host_state, 'liaison': liaison_codes,
            'enabled': enabled, 'pageStrip': page,
        }

    def soft_co_update_okng_recv_autoack(self, *, judge='OK', recipe='', ok_n=None, ng_n=None,
                                         snapshot=None, payload=''):
        """OK-NG dashboard ↔ Comm recvEvents auto-ack page co-update (LocalBus only)."""
        from datetime import datetime
        j = str(judge or 'OK')
        upper = j.upper()
        is_ok = upper in ('OK', 'PASS', '良', '通过', 'TRUE', '1')
        snap = dict(snapshot or {})
        recipe = str(recipe or snap.get('recipe') or '')
        ts = datetime.now().strftime('%H:%M:%S')
        if ok_n is None:
            ok_n = 1 if is_ok else 0
        if ng_n is None:
            ng_n = 0 if is_ok else 1
        ok_n = int(ok_n or 0)
        ng_n = int(ng_n or 0)
        # Drive recv auto-ack timeline with OK/NG-flavored payload
        if not payload:
            payload = (
                f'RESULT okng={j} ok={ok_n} ng={ng_n} recipe={recipe or "-"}'
            )
        # Temporarily set demo payload if widget present
        prev_payload = ''
        if hasattr(self, 'ack_demo_payload') and self.ack_demo_payload is not None:
            try:
                prev_payload = self.ack_demo_payload.text()
                self.ack_demo_payload.setText(payload)
            except Exception:
                pass
        ack_bag = {}
        try:
            ack_bag = self._soft_recv_auto_ack_timeline() or {}
        except Exception:
            ack_bag = {}
        if hasattr(self, 'ack_demo_payload') and self.ack_demo_payload is not None and prev_payload:
            try:
                self.ack_demo_payload.setText(prev_payload)
            except Exception:
                pass
        ack = str(ack_bag.get('ack') or 'OK')
        devices = list(ack_bag.get('devices') or [])
        enabled = bool(ack_bag.get('enabled'))
        # Resolve HMI / Host for OK-NG dashboard co-update
        hmi = None
        host = None
        try:
            w = self.parent()
            for _ in range(8):
                if w is None:
                    break
                hmi = getattr(w, 'operator_hmi', None) or hmi
                host = getattr(w, 'host_state_machine', None) or getattr(w, 'host_sm', None) or host
                if hmi is not None or host is not None:
                    break
                w = w.parent() if hasattr(w, 'parent') else None
            if hmi is not None and host is None:
                host = getattr(hmi, '_host_sm', None)
        except Exception:
            pass
        host_state = 'Idle' if is_ok else 'Alarm'
        if hmi is not None:
            try:
                if hasattr(hmi, 'co_update_okng_recv_autoack'):
                    hmi.co_update_okng_recv_autoack(
                        judge=j, recipe=recipe, ok_n=ok_n, ng_n=ng_n,
                        ack=ack, devices=devices, enabled=enabled,
                        host_state=host_state, payload=payload,
                    )
                elif hasattr(hmi, 'refresh_okng_dashboard_strip'):
                    hmi.refresh_okng_dashboard_strip(
                        ok_n=ok_n, ng_n=ng_n, judge=j, host_state=host_state,
                        recipe=recipe or None,
                    )
            except Exception:
                pass
        if host is not None and hasattr(host, 'set_okng_recv_autoack_co_update_strip'):
            try:
                host.set_okng_recv_autoack_co_update_strip(
                    f'OK-NG↔recv自动应答 · okng={j} · OK {ok_n} NG {ng_n} · '
                    f'ack={ack!r} · devices={",".join(devices) or "—"}',
                    okng=j, ok_n=ok_n, ng_n=ng_n, ack=ack,
                )
            except Exception:
                pass
        total = ok_n + ng_n
        ytxt = f'{(100.0 * ok_n / total):.1f}%' if total else '—'
        lines = [
            '── OK-NG dashboard ↔ Comm recvEvents auto-ack page co-update ──',
            f'[{ts}] okng={j} · OK {ok_n} NG {ng_n} 良率 {ytxt} · ack={ack!r} · '
            f'enabled={enabled} · host={host_state}',
            f'  devices={",".join(devices) or "—"} · recipe={recipe or "—"} · '
            f'payload={payload[:60]} · LocalBus · 页铬非芯片',
            f'  targets=okNgDashboard · recvAutoAckTimeline · groupedReply · pageChrome',
        ]
        # Append last few ack timeline lines
        for ln in list(ack_bag.get('lines') or [])[-6:]:
            lines.append(f'  {ln}')
        page = '\n'.join(lines)
        if hasattr(self, 'okng_recv_ack_strip') and self.okng_recv_ack_strip is not None:
            self.okng_recv_ack_strip.setPlainText(page)
            if is_ok:
                self.okng_recv_ack_strip.setStyleSheet(
                    'font-family:monospace;font-size:11px;background:#1c2a1c;color:#9ed9a8;'
                )
            else:
                self.okng_recv_ack_strip.setStyleSheet(
                    'font-family:monospace;font-size:11px;background:#2a1c1c;color:#ffb4b4;'
                )
        if hasattr(self, 'okng_recv_ack_meta') and self.okng_recv_ack_meta is not None:
            self.okng_recv_ack_meta.setText(
                f'共更 · okng={j} · OK {ok_n} NG {ng_n} · ack={ack!r} · '
                f'devices={",".join(devices) or "—"} · recv自动应答页铬'
            )
        return {
            'okng': j, 'ok': ok_n, 'ng': ng_n, 'ack': ack, 'devices': devices,
            'enabled': enabled, 'hostState': host_state, 'pageStrip': page,
            'ackBag': ack_bag,
        }

    def _clear_autoack_send_format_roundtrip(self):
        if hasattr(self, 'ack_rt_strip') and self.ack_rt_strip is not None:
            self.ack_rt_strip.setPlainText('(应答→发送/格式化 软往返条空)')
        if hasattr(self, 'ack_rt_meta') and self.ack_rt_meta is not None:
            self.ack_rt_meta.setText('(尚未应答→发送往返)')


    def _tpl_clear_inbox_timeline(self):
        self._tpl_inbox_lines = []
        if hasattr(self, 'tpl_inbox_timeline') and self.tpl_inbox_timeline is not None:
            self.tpl_inbox_timeline.setPlainText('(多设备 LocalBus 收件箱时间线空)')
        if hasattr(self, 'tpl_inbox_meta') and self.tpl_inbox_meta is not None:
            self.tpl_inbox_meta.setText('(尚未软投递)')

    def _tpl_apply_to_send_event(self):
        """Append / fill first send-event row with template body (expanded optional)."""
        self._tpl_commit_form()
        body = self.tpl_body.toPlainText()
        name = self.tpl_name.text().strip() or '模板报文'
        # Prefer raw template with ${} so runtime expands; also offer expanded in message if user held Shift — keep raw.
        rows = self.send_table.rows()
        devices = [d.get('name') or '' for d in (self._devices or [])]
        dev = devices[0] if devices else 'LocalLoop'
        rows.append({
            'name': name,
            'device': dev,
            'message': body,
            'topic': '',
            'variable': '',
        })
        self.send_table.set_rows(rows, devices)
        # jump UI to send tab
        try:
            idx = self.tabs.indexOf(self.send_table)
            if idx >= 0:
                self.tabs.setCurrentIndex(idx)
        except Exception:
            pass
        # Offscreen / smoke: skip modal (would hang QT_QPA_PLATFORM=offscreen)
        import os as _os
        if _os.environ.get('QT_QPA_PLATFORM') == 'offscreen' or _os.environ.get('SIEANS_SMOKE') == '1':
            return
        QMessageBox.information(
            self, '消息模板',
            f'已追加发送事件「{name}」。\n报文保留 ${{}} 占位，试发/运行时展开。',
        )

    def _tpl_apply_to_test(self, which='tcp'):
        self._tpl_commit_form()
        # Use expanded preview for immediate test-box fill
        text = self.tpl_preview.toPlainText() or self.tpl_body.toPlainText()
        if which == 'udp':
            self.udp_payload.setText(text)
            try:
                idx = self.tabs.indexOf(self.udp_payload.parent())
            except Exception:
                idx = -1
            # find UDP tab by title
            for i in range(self.tabs.count()):
                if self.tabs.tabText(i) == 'UDP 测试':
                    self.tabs.setCurrentIndex(i)
                    break
        else:
            self.tcp_payload.setText(text)
            for i in range(self.tabs.count()):
                if self.tabs.tabText(i) == 'TCP 测试':
                    self.tabs.setCurrentIndex(i)
                    break

    def _udp_preset_apply(self, _idx=None):
        """Fill udp_payload from protocol preset (sim verbs; not field HW)."""
        if not hasattr(self, 'udp_preset'):
            return
        payload = self.udp_preset.currentData()
        if payload:
            self.udp_payload.setText(str(payload))


    def _open_global_triggers(self):
        """细妆：通信管理 → 全局触发联调入口。"""
        w = self.parent()
        while w is not None:
            if hasattr(w, 'open_global_triggers'):
                try:
                    w.open_global_triggers()
                    return
                except Exception as err:
                    QMessageBox.warning(self, '通信管理', f'打开全局触发失败：{err}')
                    return
            w = w.parent()
        QMessageBox.information(
            self,
            '通信管理',
            '请通过主窗口「设置 → 全局触发…」配置字符串/事件表。\n'
            '通信试收报文会匹配字符串触发（如 RUN → 执行·单次）。',
        )

    def _open_variables_hint(self):
        """细妆：通信收发 ↔ 运行时变量联调指引。"""
        w = self.parent()
        while w is not None:
            for attr in ('open_variable_manager', 'open_variables', 'show_variables_panel', 'open_global_variables'):
                if hasattr(w, attr):
                    try:
                        getattr(w, attr)()
                        return
                    except Exception as err:
                        QMessageBox.warning(self, '通信管理', f'打开变量面板失败：{err}')
                        return
            w = w.parent()
        QMessageBox.information(
            self,
            '通信 · 变量联调',
            '收发事件可将报文写入全局/流程变量，或从变量取数下发。\n'
            '· 试收命中 → 字符串触发 / 写变量\n'
            '· 试发载荷可用 ${var} 占位（见事件表）\n'
            '请在主窗口「变量」或流程变量表中核对绑定。',
        )

