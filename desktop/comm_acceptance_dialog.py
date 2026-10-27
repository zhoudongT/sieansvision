"""真机 Comm 验收壳 — checklist UI + dry-run harness (loopback-ready, field-ready).

Does NOT require hardware: default target is tcp_device_sim :19880.
Host/port editable so field tech can point at real device later.
No robot SDK / no field hardware claims.
"""
from __future__ import annotations

import csv
import io
import socket
import time
from datetime import datetime

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QLineEdit, QSpinBox, QFormLayout,
    QGroupBox, QFileDialog, QMessageBox, QTextEdit, QCheckBox, QApplication,
)


CHECKLIST = [
    ('ping', 'PING → PONG', 'PING', lambda r: r.strip().upper() == 'PONG'),
    ('status', 'STATUS 含 sim/ready', 'STATUS', lambda r: 'sim=' in r or 'ready' in r.lower() or 'ok' in r.lower()),
    ('help', 'HELP 列动词', 'HELP', lambda r: 'PING' in r.upper() and ('GET' in r.upper() or 'MEAS' in r.upper())),
    ('set', 'SET 键值', 'SET accept_probe 1', lambda r: r.upper().startswith('ACK')),
    ('get', 'GET 键值', 'GET accept_probe', lambda r: 'VALUE' in r.upper() or 'accept_probe' in r),
    ('vars', 'VARS 转储', 'VARS', lambda r: '=' in r or 'accept_probe' in r),
    ('meas', 'MEAS JSON 桩', 'MEAS', lambda r: r.upper().startswith('MEAS') or '{' in r),
    ('json', 'JSON GET', 'JSON {"cmd":"GET","key":"accept_probe"}',
     lambda r: 'value' in r.lower() or 'accept_probe' in r),
    ('run_echo', 'RUN 触发回显（若设备支持）', 'RUN',
     lambda r: bool(r.strip())),  # any reply counts; field devices vary
]


def _tcp_exchange(host: str, port: int, payload: str, timeout: float = 2.0) -> str:
    data = (payload.rstrip('\n') + '\n').encode('utf-8', errors='replace')
    with socket.create_connection((host, int(port)), timeout=timeout) as sock:
        sock.settimeout(timeout)
        sock.sendall(data)
        buf = b''
        while b'\n' not in buf and len(buf) < 65536:
            chunk = sock.recv(4096)
            if not chunk:
                break
            buf += chunk
    return buf.decode('utf-8', errors='replace').strip()


class _Runner(QThread):
    itemDone = Signal(int, str, str, str)  # row, status, detail, reply
    finishedAll = Signal(dict)

    def __init__(self, host, port, selected_ids, parent=None):
        super().__init__(parent)
        self.host = host
        self.port = int(port)
        self.selected_ids = set(selected_ids or [])
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        report = {
            'host': self.host,
            'port': self.port,
            'startedAt': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'items': [],
        }
        for i, (cid, title, cmd, pred) in enumerate(CHECKLIST):
            if self._stop:
                break
            if self.selected_ids and cid not in self.selected_ids:
                self.itemDone.emit(i, 'SKIP', '未勾选', '')
                report['items'].append({'id': cid, 'title': title, 'status': 'SKIP', 'detail': '未勾选', 'reply': ''})
                continue
            t0 = time.time()
            try:
                reply = _tcp_exchange(self.host, self.port, cmd)
                ms = int((time.time() - t0) * 1000)
                ok = bool(pred(reply))
                status = 'PASS' if ok else 'FAIL'
                detail = f'{ms} ms'
                if not ok:
                    detail += ' · 判定未通过'
            except Exception as err:
                reply = ''
                status = 'FAIL'
                detail = f'连接/收发失败：{err}'
            self.itemDone.emit(i, status, detail, reply[:500])
            report['items'].append({
                'id': cid, 'title': title, 'cmd': cmd,
                'status': status, 'detail': detail, 'reply': reply[:500],
            })
        report['finishedAt'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        pass_n = sum(1 for it in report['items'] if it['status'] == 'PASS')
        fail_n = sum(1 for it in report['items'] if it['status'] == 'FAIL')
        skip_n = sum(1 for it in report['items'] if it['status'] == 'SKIP')
        report['summary'] = {'pass': pass_n, 'fail': fail_n, 'skip': skip_n}
        self.finishedAll.emit(report)


class CommAcceptanceDialog(QDialog):
    """Acceptance checklist shell — dry-run on sim, ready for field host/port."""

    def __init__(self, parent=None, default_host='127.0.0.1', default_port=19880):
        super().__init__(parent)
        self.setWindowTitle('真机 Comm 验收壳（干跑就绪）')
        self.setObjectName('commAcceptanceDialog')
        self.resize(860, 560)
        self._runner = None
        self._report = None
        self._ensure_sim = True

        lay = QVBoxLayout(self)
        tip = QLabel(
            '现场通讯验收清单：默认对环回模拟器 :19880 干跑；改 Host/Port 即可对真机复测。'
            '不宣称已接现场设备 / 无机械手 SDK。'
        )
        tip.setWordWrap(True)
        tip.setStyleSheet('color:#888;font-size:12px;')
        lay.addWidget(tip)

        form_box = QGroupBox('目标')
        form = QFormLayout(form_box)
        row = QHBoxLayout()
        self.host_edit = QLineEdit(default_host)
        self.host_edit.setObjectName('commAcceptHost')
        row.addWidget(self.host_edit, 2)
        self.port_spin = QSpinBox(); self.port_spin.setRange(1, 65535)
        self.port_spin.setValue(int(default_port))
        self.port_spin.setObjectName('commAcceptPort')
        row.addWidget(QLabel('端口'))
        row.addWidget(self.port_spin)
        form.addRow('Host', row)
        self.chk_sim = QCheckBox('干跑前自动启动本机 tcp_device_sim（环回）')
        self.chk_sim.setChecked(True)
        self.chk_sim.setObjectName('commAcceptAutoSim')
        form.addRow(self.chk_sim)
        lay.addWidget(form_box)

        self.table = QTableWidget(len(CHECKLIST), 5)
        self.table.setObjectName('commAcceptTable')
        self.table.setHorizontalHeaderLabels(['选', '项', '命令', '结果', '详情/回包'])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self._checks = []
        for i, (cid, title, cmd, _pred) in enumerate(CHECKLIST):
            chk = QCheckBox()
            chk.setChecked(cid != 'run_echo')  # RUN optional for sim
            chk.setProperty('cid', cid)
            self.table.setCellWidget(i, 0, chk)
            self._checks.append(chk)
            self.table.setItem(i, 1, QTableWidgetItem(title))
            self.table.setItem(i, 2, QTableWidgetItem(cmd))
            self.table.setItem(i, 3, QTableWidgetItem('—'))
            self.table.setItem(i, 4, QTableWidgetItem(''))
        lay.addWidget(self.table, 1)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(100)
        self.log.setObjectName('commAcceptLog')
        lay.addWidget(self.log)

        row = QHBoxLayout()
        self.btn_run = QPushButton('开始验收干跑')
        self.btn_run.setObjectName('commAcceptRunBtn')
        self.btn_run.setStyleSheet('QPushButton{background:#e87722;color:#111;font-weight:600;padding:8px 16px;}')
        self.btn_run.clicked.connect(self._start)
        row.addWidget(self.btn_run)
        self.btn_stop = QPushButton('停止')
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self._stop)
        row.addWidget(self.btn_stop)
        b_csv = QPushButton('导出报告 CSV…')
        b_csv.setObjectName('commAcceptExportBtn')
        b_csv.clicked.connect(self._export_csv)
        row.addWidget(b_csv)
        b_clip = QPushButton('复制报告')
        b_clip.clicked.connect(self._copy_report)
        row.addWidget(b_clip)
        self.summary_lab = QLabel('尚未运行')
        self.summary_lab.setObjectName('commAcceptSummary')
        row.addWidget(self.summary_lab)
        row.addStretch(1)
        b_close = QPushButton('关闭')
        b_close.clicked.connect(self.accept)
        row.addWidget(b_close)
        lay.addLayout(row)

    def _log(self, msg: str):
        self.log.append(msg)

    def _selected_ids(self):
        ids = []
        for chk in self._checks:
            if chk.isChecked():
                ids.append(chk.property('cid'))
        return ids

    def _start(self):
        if self._runner and self._runner.isRunning():
            return
        host = self.host_edit.text().strip() or '127.0.0.1'
        port = int(self.port_spin.value())
        if self.chk_sim.isChecked() and host in ('127.0.0.1', 'localhost', '::1'):
            try:
                from desktop import tcp_device_sim as tds
                st = tds.start()
                # if user left default port, align to sim
                sim_port = int(st.get('tcpPort') or 19880)
                if port == 19880 or host in ('127.0.0.1', 'localhost'):
                    self.port_spin.setValue(sim_port)
                    port = sim_port
                self._log(f'已启动环回模拟 tcp={sim_port} udp={st.get("udpPort")}')
            except Exception as err:
                self._log(f'模拟器启动：{err}（若已在跑可忽略）')
        for i in range(self.table.rowCount()):
            self.table.item(i, 3).setText('…')
            self.table.item(i, 4).setText('')
        self.btn_run.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.summary_lab.setText('运行中…')
        self._runner = _Runner(host, port, self._selected_ids(), self)
        self._runner.itemDone.connect(self._on_item)
        self._runner.finishedAll.connect(self._on_done)
        self._runner.start()

    def _stop(self):
        if self._runner:
            self._runner.stop()

    def _on_item(self, row, status, detail, reply):
        self.table.item(row, 3).setText(status)
        color = {'PASS': '#3ecf8e', 'FAIL': '#e35d6a', 'SKIP': '#888'}.get(status, '#ccc')
        self.table.item(row, 3).setForeground(Qt.GlobalColor.white)
        self.table.item(row, 3).setData(Qt.ItemDataRole.ForegroundRole,
                                        __import__('PySide6.QtGui', fromlist=['QColor']).QColor(color))
        text = detail
        if reply:
            text = f'{detail} | {reply}' if detail else reply
        self.table.item(row, 4).setText(text)

    def _on_done(self, report):
        self._report = report
        self.btn_run.setEnabled(True)
        self.btn_stop.setEnabled(False)
        s = report.get('summary') or {}
        self.summary_lab.setText(
            f"PASS {s.get('pass', 0)} · FAIL {s.get('fail', 0)} · SKIP {s.get('skip', 0)}"
        )
        self._log(f"验收结束 {report.get('finishedAt')} @ {report.get('host')}:{report.get('port')}")

    def report_csv(self) -> str:
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(['id', 'title', 'cmd', 'status', 'detail', 'reply', 'host', 'port'])
        host = (self._report or {}).get('host', self.host_edit.text())
        port = (self._report or {}).get('port', self.port_spin.value())
        items = (self._report or {}).get('items') or []
        if not items:
            for i, (cid, title, cmd, _) in enumerate(CHECKLIST):
                st = self.table.item(i, 3).text() if self.table.item(i, 3) else ''
                det = self.table.item(i, 4).text() if self.table.item(i, 4) else ''
                w.writerow([cid, title, cmd, st, det, '', host, port])
        else:
            for it in items:
                w.writerow([it.get('id'), it.get('title'), it.get('cmd'), it.get('status'),
                            it.get('detail'), it.get('reply'), host, port])
        return buf.getvalue()

    def _export_csv(self):
        path, _ = QFileDialog.getSaveFileName(
            self, '导出验收报告', 'comm-acceptance.csv', 'CSV (*.csv);;All (*)')
        if not path:
            return
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(self.report_csv())
            self._log(f'已导出 {path}')
        except Exception as err:
            QMessageBox.warning(self, '导出失败', str(err))

    def _copy_report(self):
        QApplication.clipboard().setText(self.report_csv())
        self._log('报告 CSV 已复制到剪贴板')
