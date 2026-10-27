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
    '方案保存',
    '方案另存',
    '执行·单次',
    '执行·连续',
    '执行·停止',
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
        """Runtime helper: full or partial string match (VM 部分匹配)."""
        needle = str(row.get('match') or row.get('event') or '')
        text = '' if received is None else str(received)
        if not needle:
            return False
        if row.get('partial', True):
            return needle in text
        return needle == text


class GlobalTriggersDialog(QDialog):
    """设置级全局触发壳：事件触发 / 字符串触发。"""

    def __init__(self, document, parent=None):
        super().__init__(parent)
        self.document = document
        self.setWindowTitle('全局触发')
        self.resize(780, 480)
        root = QVBoxLayout(self)
        title = QLabel('全局触发')
        title.setObjectName('dialogTitle')
        root.addWidget(title)
        hint = QLabel('事件 → 命令 / 字符串触发（支持部分匹配）→ 执行流程。列：序号、触发事件、部分匹配、命令类型、配置、操作。配置随方案保存。')
        hint.setObjectName('dialogHint')
        hint.setWordWrap(True)
        root.addWidget(hint)

        self.tabs = QTabWidget()
        self.event_table = _TriggerTable('event')
        self.string_table = _TriggerTable('string')
        self.tabs.addTab(self.event_table, '事件触发')
        self.tabs.addTab(self.string_table, '字符串触发')
        root.addWidget(self.tabs, 1)

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
        self.event_table.set_rows(gt.get('events') or [])
        self.string_table.set_rows(gt.get('strings') or [])

    def accept_save(self):
        p = deepcopy(self.document.project)
        p['globalTriggers'] = dict(
            events=self.event_table.rows(),
            strings=self.string_table.rows(),
        )
        self.document.commit(p)
        QMessageBox.information(self, '全局触发', f'已保存事件 {len(p["globalTriggers"]["events"])} 条、字符串 {len(p["globalTriggers"]["strings"])} 条。')
        self.accept()
