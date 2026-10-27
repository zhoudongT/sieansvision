"""全局触发对话框 — 事件触发 / 字符串触发（VM 基础操作壳）。"""
from copy import deepcopy

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTabWidget,
    QTableWidget, QTableWidgetItem, QHeaderView, QComboBox, QLineEdit,
    QWidget, QAbstractItemView, QMessageBox,
)

COMMAND_TYPES = [
    '界面链接',
    '参数配置',
    '复位',
    '注入·RUN',
    '注入·STOP',
    '方案保存',
    '方案另存',
    '执行·单次',
    '执行·连续',
    '执行·停止',
    '执行·暂停',
    '执行·继续',
    '状态·报警',
    '状态·清除报警',
    '模块动作',
]

EVENT_CHOICES = [
    '方案加载完成',
    '流程开始',
    '流程结束',
    '流程NG',
    '相机连通',
    '相机断线',
    '自定义事件',
]


def default_triggers():
    return dict(events=[], strings=[])


def ensure_triggers(project):
    gt = project.setdefault('globalTriggers', default_triggers())
    gt.setdefault('events', [])
    gt.setdefault('strings', [])
    return gt


# Seed / English action → dialog COMMAND_TYPES
ACTION_TO_COMMAND = {
    '注入 RUN': '注入·RUN',
    '注入 STOP': '注入·STOP',
    '注入RUN': '注入·RUN',
    '注入STOP': '注入·STOP',
    'run': '执行·单次',
    'run_once': '执行·单次',
    'once': '执行·单次',
    'continuous': '执行·连续',
    'run_continuous': '执行·连续',
    'stop': '执行·停止',
    'pause': '执行·暂停',
    'resume': '执行·继续',
    'continue': '执行·继续',
    'save': '方案保存',
    'save_as': '方案另存',
    'reset': '复位',
    'alarm': '状态·报警',
    'clear_alarm': '状态·清除报警',
    'module': '模块动作',
}


def _row_enabled(row):
    if not isinstance(row, dict):
        return False
    if 'enabled' in row and row.get('enabled') is False:
        return False
    return True


def _commands_from_row(row, source='', extra=None):
    """Normalize dialog rows (commandType) and seed rows (commands[{action}])."""
    out = []
    extra = dict(extra or {})
    ctype = (row or {}).get('commandType') or (row or {}).get('command') or ''
    if ctype:
        out.append(dict(type=ctype, config=(row or {}).get('config') or '', source=source, **extra))
    for c in (row or {}).get('commands') or []:
        if not isinstance(c, dict):
            continue
        action = str(c.get('action') or c.get('type') or '').strip()
        if not action or action == 'log':
            continue
        mapped = ACTION_TO_COMMAND.get(action) or (action if action in COMMAND_TYPES else '')
        if not mapped:
            continue
        cfg = c.get('config') or c.get('target') or c.get('text') or ''
        out.append(dict(type=mapped, config=cfg, source=source, **extra))
    return out


def match_string_row(received, row):
    """Full or partial string match (VM 部分匹配). Supports dialog + seed schemas."""
    text = '' if received is None else str(received)
    row = row or {}
    mode = row.get('match')
    # Seed schema: match=equals|contains, pattern=needle
    if mode in ('equals', 'contains', 'partial', 'full'):
        needle = str(row.get('pattern') or row.get('event') or '')
        if not needle:
            return False
        if mode in ('equals', 'full'):
            return needle == text
        return needle in text
    # Dialog schema: match/event is the needle; partial bool
    needle = str(row.get('event') or row.get('match') or row.get('pattern') or '')
    if not needle:
        return False
    if row.get('partial', True):
        return needle in text
    return needle == text


def collect_string_commands(project, received):
    """Return trigger-command dicts for string rows matching received text."""
    gt = ensure_triggers(project if isinstance(project, dict) else {})
    out = []
    for row in gt.get('strings') or []:
        if not _row_enabled(row):
            continue
        if match_string_row(received, row):
            needle = row.get('pattern') or row.get('event') or row.get('match') or ''
            out.extend(_commands_from_row(row, source='string', extra=dict(match=str(needle))))
    return out


def collect_event_commands(project, event_name):
    """Return trigger-command dicts for event rows whose event equals event_name."""
    name = str(event_name or '').strip()
    if not name:
        return []
    gt = ensure_triggers(project if isinstance(project, dict) else {})
    out = []
    for row in gt.get('events') or []:
        if not _row_enabled(row):
            continue
        if str(row.get('event') or '').strip() == name:
            out.extend(_commands_from_row(row, source='event', extra=dict(event=name)))
    return out


def payloads_from_run_results(records, steps=None):
    """Collect receive_data payloads from a finished job's results."""
    by_id = {}
    for s in steps or []:
        if isinstance(s, dict) and s.get('id'):
            by_id[s['id']] = s
    out = []
    for rec in records or []:
        if not isinstance(rec, dict):
            continue
        sid = rec.get('id')
        step = by_id.get(sid) or {}
        op = step.get('operation') or ''
        result = (rec.get('output') or {}).get('result') or rec.get('result') or {}
        if not isinstance(result, dict):
            continue
        if op != 'receive_data':
            continue
        payload = result.get('payload')
        if payload is not None and str(payload) != '':
            out.append(str(payload))
    seen = set()
    uniq = []
    for x in out:
        if x not in seen:
            seen.add(x)
            uniq.append(x)
    return uniq



class _TriggerTable(QWidget):
    """Shared table for event / string trigger rows."""

    COLS = ['序号', '触发事件', '部分匹配', '触发命令类型', '触发配置', '操作']

    def __init__(self, kind='event', parent=None):
        super().__init__(parent)
        self.kind = kind
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(self.COLS)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        lay.addWidget(self.table, 1)
        bar = QHBoxLayout()
        add = QPushButton('添加')
        add.clicked.connect(self.add_row)
        bar.addWidget(add)
        bar.addStretch(1)
        lay.addLayout(bar)

    def set_rows(self, rows):
        self.table.setRowCount(0)
        for row in rows or []:
            self._append(row)

    def _append(self, row=None):
        row = row or {}
        r = self.table.rowCount()
        self.table.insertRow(r)
        seq = QTableWidgetItem(str(r + 1))
        seq.setFlags(seq.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.table.setItem(r, 0, seq)

        if self.kind == 'event':
            ev = QComboBox()
            ev.addItems(EVENT_CHOICES)
            cur = row.get('event') or EVENT_CHOICES[0]
            idx = ev.findText(cur)
            ev.setCurrentIndex(idx if idx >= 0 else 0)
            self.table.setCellWidget(r, 1, ev)
            # 部分匹配 N/A for events — disabled checkbox-like combo
            partial = QComboBox()
            partial.addItems(['—', '是', '否'])
            partial.setCurrentIndex(0)
            partial.setEnabled(False)
            self.table.setCellWidget(r, 2, partial)
        else:
            edit = QLineEdit(str(row.get('event') or row.get('match') or ''))
            edit.setPlaceholderText('触发字符串…')
            self.table.setCellWidget(r, 1, edit)
            partial = QComboBox()
            partial.addItem('是（包含）', True)
            partial.addItem('否（全等）', False)
            want = row.get('partial')
            if want is None:
                want = True
            partial.setCurrentIndex(0 if want else 1)
            self.table.setCellWidget(r, 2, partial)

        cmd = QComboBox()
        cmd.addItems(COMMAND_TYPES)
        cur_cmd = row.get('commandType') or COMMAND_TYPES[0]
        i = cmd.findText(cur_cmd)
        cmd.setCurrentIndex(i if i >= 0 else 0)
        self.table.setCellWidget(r, 3, cmd)

        cfg = QLineEdit(str(row.get('config') or ''))
        cfg.setPlaceholderText('配置（流程名/模块/链接目标…）')
        self.table.setCellWidget(r, 4, cfg)

        ops = QWidget()
        ol = QHBoxLayout(ops)
        ol.setContentsMargins(2, 0, 2, 0)
        up = QPushButton('↑')
        down = QPushButton('↓')
        rm = QPushButton('删')
        up.setFixedWidth(28)
        down.setFixedWidth(28)
        rm.setFixedWidth(28)
        up.clicked.connect(lambda *_ , rr=r: self._move(rr, -1))
        down.clicked.connect(lambda *_ , rr=r: self._move(rr, 1))
        rm.clicked.connect(lambda *_ , rr=r: self._remove(rr))
        ol.addWidget(up)
        ol.addWidget(down)
        ol.addWidget(rm)
        self.table.setCellWidget(r, 5, ops)
        self._renumber()

    def add_row(self):
        self._append({})

    def _remove(self, row):
        if 0 <= row < self.table.rowCount():
            self.table.removeRow(row)
            self._renumber()

    def _move(self, row, delta):
        target = row + delta
        if target < 0 or target >= self.table.rowCount():
            return
        data = self.rows()
        data[row], data[target] = data[target], data[row]
        self.set_rows(data)

    def _renumber(self):
        for r in range(self.table.rowCount()):
            item = self.table.item(r, 0)
            if item is None:
                item = QTableWidgetItem()
                self.table.setItem(r, 0, item)
            item.setText(str(r + 1))
            # rebind op buttons to current row indices
            ops = self.table.cellWidget(r, 5)
            if ops is None:
                continue
            buttons = ops.findChildren(QPushButton)
            if len(buttons) >= 3:
                try:
                    buttons[0].clicked.disconnect()
                except TypeError:
                    pass
                try:
                    buttons[1].clicked.disconnect()
                except TypeError:
                    pass
                try:
                    buttons[2].clicked.disconnect()
                except TypeError:
                    pass
                buttons[0].clicked.connect(lambda *_ , rr=r: self._move(rr, -1))
                buttons[1].clicked.connect(lambda *_ , rr=r: self._move(rr, 1))
                buttons[2].clicked.connect(lambda *_ , rr=r: self._remove(rr))

    def rows(self):
        out = []
        for r in range(self.table.rowCount()):
            w1 = self.table.cellWidget(r, 1)
            w2 = self.table.cellWidget(r, 2)  # partial
            w3 = self.table.cellWidget(r, 3)  # command
            w4 = self.table.cellWidget(r, 4)  # config
            event = w1.currentText() if isinstance(w1, QComboBox) else (w1.text() if w1 else '')
            if self.kind == 'string' and isinstance(w2, QComboBox):
                partial = bool(w2.currentData()) if w2.currentData() is not None else (w2.currentIndex() == 0)
            else:
                partial = False
            cmd = w3.currentText() if w3 else ''
            cfg = w4.text() if w4 else ''
            out.append(dict(event=event, match=event, partial=partial, commandType=cmd, config=cfg))
        return out

    @staticmethod
    def match_string(received, row):
        return match_string_row(received, row)



def _ui_normalize_row(row, kind='string'):
    """Map seed {pattern,commands[{action}]} → dialog {event,commandType,config,partial}."""
    row = dict(row or {})
    cmds = _commands_from_row(row)
    if kind == 'string':
        mode = row.get('match')
        if mode in ('equals', 'contains', 'partial', 'full'):
            needle = str(row.get('pattern') or row.get('event') or '')
            partial = mode not in ('equals', 'full')
        else:
            needle = str(row.get('event') or row.get('match') or row.get('pattern') or '')
            partial = bool(row.get('partial', True))
        ctype = (cmds[0]['type'] if cmds else '') or row.get('commandType') or COMMAND_TYPES[0]
        cfg = (cmds[0].get('config') if cmds else '') or row.get('config') or ''
        return dict(event=needle, match=needle, partial=partial, commandType=ctype, config=cfg)
    # event
    ctype = (cmds[0]['type'] if cmds else '') or row.get('commandType') or COMMAND_TYPES[0]
    cfg = (cmds[0].get('config') if cmds else '') or row.get('config') or ''
    return dict(event=row.get('event') or '', match=row.get('event') or '', partial=False, commandType=ctype, config=cfg)


class GlobalTriggersDialog(QDialog):
    """设置级全局触发壳：事件触发 / 字符串触发。"""

    def __init__(self, document, parent=None, execute_commands=None):
        super().__init__(parent)
        self.document = document
        self._execute_commands = execute_commands  # optional callable(list[dict])
        self.setWindowTitle('全局触发')
        self.resize(780, 480)
        root = QVBoxLayout(self)
        title = QLabel('全局触发')
        title.setObjectName('dialogTitle')
        root.addWidget(title)
        hint = QLabel('事件 → 命令 / 字符串触发（部分匹配）→ 执行流程。运行时：流程开始/结束/NG 派发事件；receive_data 载荷、通信试收、以及 fire_string_trigger("RUN") 均匹配字符串触发（常接 执行·单次）。配置随方案保存。')
        hint.setObjectName('dialogHint')
        hint.setWordWrap(True)
        root.addWidget(hint)

        self.tabs = QTabWidget()
        self.event_table = _TriggerTable('event')
        self.string_table = _TriggerTable('string')
        self.tabs.addTab(self.event_table, '事件触发')
        self.tabs.addTab(self.string_table, '字符串触发')
        root.addWidget(self.tabs, 1)
        test = QHBoxLayout()
        test.addWidget(QLabel('试匹配（字符串）'))
        self.test_input = QLineEdit()
        self.test_input.setPlaceholderText('粘贴收到的报文…')
        test.addWidget(self.test_input, 1)
        test_btn = QPushButton('试匹配')
        test_btn.clicked.connect(self._test_match)
        test.addWidget(test_btn)
        run_btn = QPushButton('匹配并执行')
        run_btn.setObjectName('primaryButton')
        run_btn.setToolTip('按当前表匹配字符串并立刻派发触发命令（不关窗）')
        run_btn.clicked.connect(self._test_match_and_run)
        test.addWidget(run_btn)
        self.test_result = QLabel('')
        test.addWidget(self.test_result)
        root.addLayout(test)

        bar = QHBoxLayout()
        save = QPushButton('确定')
        save.setObjectName('primaryButton')
        save.clicked.connect(self.accept_save)
        cancel = QPushButton('取消')
        cancel.clicked.connect(self.reject)
        bar.addStretch(1)
        bar.addWidget(save)
        bar.addWidget(cancel)
        root.addLayout(bar)

        gt = ensure_triggers(deepcopy(document.project))
        self.event_table.set_rows([_ui_normalize_row(r, 'event') for r in (gt.get('events') or [])])
        self.string_table.set_rows([_ui_normalize_row(r, 'string') for r in (gt.get('strings') or [])])

    def _matched_commands(self, text):
        cmds = []
        hits = []
        for i, row in enumerate(self.string_table.rows(), 1):
            if _TriggerTable.match_string(text, row):
                ctype = row.get('commandType') or '?'
                hits.append(f'#{i}→{ctype}')
                if row.get('commandType'):
                    cmds.append(dict(type=row.get('commandType'), config=row.get('config') or '', source='string'))
        return hits, cmds

    def _test_match(self):
        text = self.test_input.text()
        hits, _ = self._matched_commands(text)
        if hits:
            self.test_result.setText('命中：' + '，'.join(hits))
            self.test_result.setStyleSheet('color:#2e7d32;font-weight:600;')
        else:
            self.test_result.setText('无命中')
            self.test_result.setStyleSheet('color:#c62828;')

    def _test_match_and_run(self):
        text = self.test_input.text()
        hits, cmds = self._matched_commands(text)
        if not hits:
            self.test_result.setText('无命中 · 未执行')
            self.test_result.setStyleSheet('color:#c62828;')
            return
        self.test_result.setText('命中并执行：' + '，'.join(hits))
        self.test_result.setStyleSheet('color:#2e7d32;font-weight:600;')
        if self._execute_commands:
            self._execute_commands(cmds)
        else:
            QMessageBox.information(self, '全局触发', '已匹配，但宿主未接执行回调。\n' + '，'.join(hits))

    def accept_save(self):
        p = deepcopy(self.document.project)
        p['globalTriggers'] = dict(
            events=self.event_table.rows(),
            strings=self.string_table.rows(),
        )
        self.document.commit(p)
        QMessageBox.information(self, '全局触发', f'已保存事件 {len(p["globalTriggers"]["events"])} 条、字符串 {len(p["globalTriggers"]["strings"])} 条。')
        self.accept()
