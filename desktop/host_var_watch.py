# -*- coding: utf-8 -*-
"""Host 变量监视板 — 只读实况 + 测量链/Comm/${} 过滤（VisionMaster 变量监视风格）。"""
from __future__ import annotations

import re
from typing import Iterable

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QBrush
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QComboBox,
    QTableWidget, QTableWidgetItem, QPushButton, QHeaderView, QAbstractItemView,
    QDialog, QDialogButtonBox,
)


# Preset filters (name → predicate over (scope, key))
_MEASURE_RE = re.compile(
    r'^(ixPt|pldDist|pointDist|intersectPt|pointLineDist|pdLive|pd2|'
    r'geometry_|locate_|measure_|line_intersect|point_distance|point_line_distance|'
    r'passGate|ixJudge|pldJudge|pld$|intersect)',
    re.I,
)
_DEFECTS_OCR_RE = re.compile(r'^(defects|ocr|defLive)', re.I)
_COMM_RE = re.compile(r'^(commAccept|commRecv|commSend|commVar|\$\{)', re.I)
_TEMPLATE_RE = re.compile(r'\$\{[^}]+\}')


def classify_watch_key(name: str) -> str:
    n = str(name or '')
    if _TEMPLATE_RE.search(n) or n.startswith('${'):
        return 'template'
    if _COMM_RE.search(n):
        return 'comm'
    if _DEFECTS_OCR_RE.search(n):
        return 'defects_ocr'
    if _MEASURE_RE.search(n):
        return 'measure'
    return 'other'


def filter_entries(entries: Iterable[tuple], preset: str, query: str) -> list:
    q = (query or '').strip().lower()
    out = []
    for scope, name, value in entries:
        cat = classify_watch_key(name)
        if preset == 'measure' and cat != 'measure':
            continue
        if preset == 'comm' and cat != 'comm':
            continue
        if preset == 'defects_ocr' and cat != 'defects_ocr':
            continue
        if preset == 'template' and cat != 'template':
            # also show keys that look like flow inject commonly used in ${}
            if '${' not in str(name):
                continue
        if preset == 'inject' and cat == 'other':
            continue
        if q and q not in str(name).lower() and q not in str(scope).lower() and q not in str(value).lower():
            continue
        out.append((scope, name, value, cat))
    return out


def collect_flow_entries(document=None, last_result=None, extra_flow: dict | None = None) -> list:
    """Gather (scope, name, value) from project variables + last_result.variables."""
    entries = []
    seen = set()

    def _add(scope, bag):
        if not isinstance(bag, dict):
            return
        for k, v in bag.items():
            key = (scope, str(k))
            if key in seen:
                continue
            seen.add(key)
            entries.append((scope, str(k), v))

    if extra_flow:
        _add('flow', extra_flow)

    if last_result and isinstance(last_result, dict):
        vars_bag = last_result.get('variables') or {}
        if isinstance(vars_bag, dict):
            for scope in ('flow', 'global', 'module', 'modules'):
                bag = vars_bag.get(scope)
                if scope == 'modules' and isinstance(bag, dict):
                    for mid, mv in bag.items():
                        if isinstance(mv, dict):
                            for k, v in mv.items():
                                _add(f'module:{mid}', {k: v})
                else:
                    _add('flow' if scope == 'module' else scope, bag if isinstance(bag, dict) else {})

    try:
        proj = getattr(document, 'project', None) or {}
        _add('flow', proj.get('variables') or {})
        g = (proj.get('globalVariables') or proj.get('globals') or {})
        if isinstance(g, dict):
            _add('global', g)
    except Exception:
        pass

    # Prefer last_result values — re-merge so runtime wins
    if last_result and isinstance(last_result, dict):
        vars_bag = last_result.get('variables') or {}
        flow = vars_bag.get('flow') if isinstance(vars_bag, dict) else None
        if isinstance(flow, dict):
            # update existing flow entries
            idx = {(s, n): i for i, (s, n, _) in enumerate(entries)}
            for k, v in flow.items():
                key = ('flow', str(k))
                if key in idx:
                    entries[idx[key]] = ('flow', str(k), v)
                else:
                    entries.append(('flow', str(k), v))
    return entries


class HostVarWatchBoard(QWidget):
    """Read-only live watch table for Host / measure / Comm vars."""

    refreshRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('hostVarWatchBoard')
        self._document = None
        self._last_result = None
        self._auto = True

        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(6)

        head = QHBoxLayout()
        title = QLabel('变量监视板')
        title.setObjectName('hostVarWatchTitle')
        title.setStyleSheet('font-weight:600;color:#ddd;')
        head.addWidget(title)
        self.count_lab = QLabel('0 项')
        self.count_lab.setObjectName('hostVarWatchCount')
        self.count_lab.setStyleSheet('color:#888;')
        head.addWidget(self.count_lab)
        head.addStretch(1)
        root.addLayout(head)

        row = QHBoxLayout()
        self.preset = QComboBox()
        self.preset.setObjectName('hostVarWatchPreset')
        for lab, key in (
            ('全部', 'all'),
            ('测量链', 'measure'),
            ('缺陷/OCR', 'defects_ocr'),
            ('Comm / 收发', 'comm'),
            ('注入标量', 'inject'),
            ('${} 模板', 'template'),
        ):
            self.preset.addItem(lab, key)
        self.search = QLineEdit()
        self.search.setObjectName('hostVarWatchSearch')
        self.search.setPlaceholderText('过滤名称 / 值 / ${flow.xxx}')
        self.refresh_btn = QPushButton('刷新')
        self.refresh_btn.setObjectName('hostVarWatchRefreshBtn')
        self.refresh_btn.clicked.connect(self._on_refresh_clicked)
        row.addWidget(self.preset)
        row.addWidget(self.search, 1)
        row.addWidget(self.refresh_btn)
        root.addLayout(row)

        tip = QLabel('只读 · 运行后自动跟随 last_result.variables.flow / Comm 注入 / 测量链 resultVar')
        tip.setStyleSheet('color:#666;font-size:11px;')
        tip.setWordWrap(True)
        root.addWidget(tip)

        self.table = QTableWidget(0, 4)
        self.table.setObjectName('hostVarWatchTable')
        self.table.setHorizontalHeaderLabels(['作用域', '名称', '值', '类'])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        root.addWidget(self.table, 1)

        self.preset.currentIndexChanged.connect(self.render)
        self.search.textChanged.connect(self.render)

        self._timer = QTimer(self)
        self._timer.setInterval(800)
        self._timer.timeout.connect(self._auto_tick)
        self._timer.start()

    def bind(self, document=None, last_result=None):
        self._document = document
        self._last_result = last_result
        self.render()

    def set_last_result(self, result):
        self._last_result = result
        self.render()

    def _on_refresh_clicked(self):
        self.refreshRequested.emit()
        self.render()

    def _auto_tick(self):
        if not self._auto or not self.isVisible():
            return
        # pull latest from parent host if available
        try:
            host = self.window()
            lr = getattr(host, 'last_result', None)
            if lr is not None and lr is not self._last_result:
                self._last_result = lr
                self.render()
                return
            doc = getattr(host, 'document', None)
            if doc is not None:
                self._document = doc
        except Exception:
            pass

    def render(self, *_):
        entries = collect_flow_entries(self._document, self._last_result)
        preset = self.preset.currentData() or 'all'
        rows = filter_entries(entries, preset if preset != 'all' else 'all', self.search.text())
        # when preset all, filter_entries with 'all' — need to allow all
        if preset == 'all':
            q = (self.search.text() or '').strip().lower()
            rows = []
            for scope, name, value in entries:
                cat = classify_watch_key(name)
                if q and q not in str(name).lower() and q not in str(scope).lower() and q not in str(value).lower():
                    continue
                rows.append((scope, name, value, cat))

        self.table.setRowCount(0)
        cat_colors = {
            'measure': QColor('#1a2e24'),
            'defects_ocr': QColor('#2a1e2e'),
            'comm': QColor('#1a2a33'),
            'template': QColor('#2e2a1a'),
            'other': QColor('#1e2228'),
        }
        cat_labels = {
            'measure': '测量',
            'defects_ocr': '缺陷OCR',
            'comm': 'Comm',
            'template': '${}',
            'other': '—',
        }
        for scope, name, value, cat in rows:
            r = self.table.rowCount()
            self.table.insertRow(r)
            texts = [str(scope), str(name), _fmt(value), cat_labels.get(cat, '—')]
            bg = cat_colors.get(cat)
            for c, text in enumerate(texts):
                it = QTableWidgetItem(text)
                if bg is not None:
                    it.setBackground(QBrush(bg))
                self.table.setItem(r, c, it)
        self.count_lab.setText(f'{self.table.rowCount()} 项')


def _fmt(value) -> str:
    if value is None:
        return '空'
    if isinstance(value, bool):
        return '是' if value else '否'
    if isinstance(value, float):
        return f'{value:.6g}'
    s = str(value)
    return s if len(s) <= 120 else s[:117] + '…'


class HostVarWatchDialog(QDialog):
    """Dialog shell around HostVarWatchBoard."""

    def __init__(self, document=None, last_result=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Host 变量监视板')
        self.setObjectName('hostVarWatchDialog')
        self.resize(720, 480)
        lay = QVBoxLayout(self)
        self.board = HostVarWatchBoard(self)
        self.board.bind(document, last_result)
        lay.addWidget(self.board, 1)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        bb.rejected.connect(self.reject)
        bb.accepted.connect(self.accept)
        close = bb.button(QDialogButtonBox.StandardButton.Close)
        if close:
            close.clicked.connect(self.reject)
        lay.addWidget(bb)
