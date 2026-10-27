"""真机 Comm 验收壳 — checklist UI + dry-run harness (loopback-ready, field-ready).

Does NOT require hardware: default target is tcp_device_sim :19880.
Host/port editable so field tech can point at real device later.
No robot SDK / no field hardware claims.
"""
from __future__ import annotations

import csv
import json
import io
import socket
import time
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal, QTimer
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



def dump_acceptance_to_variables(project, report, *, prefix='commAccept') -> dict:
    """细妆⑱：验收报告一键落盘到 flow 变量（含 VALUE/MEAS 解析 sibling）.

    Writes:
      flow.{prefix}Pass / Fail / Skip / At / Host / Port / Overall
      flow.{prefix}_{itemId} = PASS|FAIL|SKIP
      flow.{prefix}_{itemId}_{extraKey} from parse_protocol_writeback_extras(reply)
    Returns stats dict {written, extras, keys}.
    """
    from desktop.comm_manager import write_project_variable, parse_protocol_writeback_extras
    from datetime import datetime as _dt
    project = project if isinstance(project, dict) else {}
    report = report if isinstance(report, dict) else {}
    summary = report.get('summary') or {}
    written = 0
    extras_n = 0
    keys = []
    def _w(ref, val):
        nonlocal written
        scope, name = write_project_variable(project, ref, val)
        if name:
            written += 1
            keys.append(f'{scope or "flow"}.{name}')

    _w(f'flow.{prefix}Pass', int(summary.get('pass') or 0))
    _w(f'flow.{prefix}Fail', int(summary.get('fail') or 0))
    _w(f'flow.{prefix}Skip', int(summary.get('skip') or 0))
    _w(f'flow.{prefix}At', str(report.get('finishedAt') or _dt.now().strftime('%Y-%m-%d %H:%M:%S')))
    _w(f'flow.{prefix}Host', str(report.get('host') or ''))
    _w(f'flow.{prefix}Port', int(report.get('port') or 0))
    fail_n = int(summary.get('fail') or 0)
    _w(f'flow.{prefix}Overall', 'FAIL' if fail_n else 'PASS')

    for it in report.get('items') or []:
        if not isinstance(it, dict):
            continue
        cid = str(it.get('id') or it.get('cid') or '').strip()
        if not cid:
            continue
        # sanitize id for var name
        safe = ''.join(ch if ch.isalnum() or ch in '_-' else '_' for ch in cid)
        status = str(it.get('status') or 'SKIP')
        _w(f'flow.{prefix}_{safe}', status)
        reply = it.get('reply') or it.get('detail') or ''
        try:
            pairs = parse_protocol_writeback_extras(str(reply))
        except Exception:
            pairs = []
        for k, v in pairs or []:
            ksafe = ''.join(ch if ch.isalnum() or ch in '_-' else '_' for ch in str(k))
            if not ksafe:
                continue
            _w(f'flow.{prefix}_{safe}_{ksafe}', v)
            extras_n += 1
    return {'written': written, 'extras': extras_n, 'keys': keys}


class CommAcceptanceDialog(QDialog):
    """Acceptance checklist shell — dry-run on sim, ready for field host/port."""

    def __init__(self, parent=None, default_host='127.0.0.1', default_port=19880, data_dir=None):
        super().__init__(parent)
        self.setWindowTitle('真机 Comm 验收壳（干跑就绪）')
        self.setObjectName('commAcceptanceDialog')
        self.resize(860, 560)
        self._runner = None
        self._report = None
        self._data_dir = Path(data_dir) if data_dir else None
        self._ensure_sim = True

        lay = QVBoxLayout(self)
        tip = QLabel(
            '现场通讯验收清单：默认对环回模拟器 :19880 干跑；改 Host/Port 即可对真机复测。'
            '不宣称已接现场设备 / 无机械手 SDK。'
        )
        tip.setWordWrap(True)
        tip.setStyleSheet('color:#888;font-size:12px;')
        lay.addWidget(tip)
        self.last_banner = QLabel('上次验收：尚无记录')
        self.last_banner.setObjectName('commAcceptLastBanner')
        self.last_banner.setWordWrap(True)
        self.last_banner.setStyleSheet('color:#9ad;font-size:12px;padding:4px 2px;')
        lay.addWidget(self.last_banner)
        b_row = QHBoxLayout()
        b_show = QPushButton('载入上次报告')
        b_show.setObjectName('commAcceptLoadLastBtn')
        b_show.setToolTip('从磁盘读取上次验收 JSON 并回填表格')
        b_show.clicked.connect(self._load_last_report)
        b_row.addWidget(b_show)
        b_diff = QPushButton('对比上次↔当前')
        b_diff.setObjectName('commAcceptDiffBtn')
        b_diff.setToolTip('对比磁盘上次报告与当前内存报告（项级 PASS/FAIL 差分）')
        b_diff.clicked.connect(self._compare_last_vs_now)
        b_row.addWidget(b_diff)
        b_row.addStretch(1)
        lay.addLayout(b_row)

        # 细妆⑮：定时复测 schedule
        sched_box = QGroupBox('定时复测')
        sched_box.setObjectName('commAcceptScheduleBox')
        sform = QHBoxLayout(sched_box)
        self.chk_schedule = QCheckBox('启用')
        self.chk_schedule.setObjectName('commAcceptScheduleChk')
        self.chk_schedule.setToolTip('按间隔自动重跑验收干跑（对比上次差分写入日志）')
        sform.addWidget(self.chk_schedule)
        sform.addWidget(QLabel('间隔(分)'))
        self.schedule_spin = QSpinBox()
        self.schedule_spin.setObjectName('commAcceptScheduleMin')
        self.schedule_spin.setRange(1, 24 * 60)
        self.schedule_spin.setValue(30)
        self.schedule_spin.setToolTip('复测间隔（分钟）')
        sform.addWidget(self.schedule_spin)
        self.schedule_status = QLabel('定时：关')
        self.schedule_status.setObjectName('commAcceptScheduleStatus')
        self.schedule_status.setStyleSheet('color:#9ad;font-size:11px;')
        sform.addWidget(self.schedule_status, 1)
        # 细妆⑯：定时历史 spark + FAIL toast
        self._schedule_hist = []  # newest-first bool pass?
        self.schedule_spark = QLabel('复测序列  · · ·  ·  等待定时')
        self.schedule_spark.setObjectName('commAcceptScheduleSpark')
        self.schedule_spark.setStyleSheet('color:#9ad;font-size:11px;font-family:monospace;padding:2px 4px;')
        self.schedule_spark.setToolTip('定时复测 PASS/FAIL 序列（高=整次 PASS · 低=有 FAIL）')
        lay.addWidget(sched_box)
        lay.addWidget(self.schedule_spark)
        self._schedule_timer = QTimer(self)
        self._schedule_timer.setSingleShot(False)
        self._schedule_timer.timeout.connect(self._on_schedule_fire)
        self.chk_schedule.toggled.connect(self._on_schedule_toggled)
        self.schedule_spin.valueChanged.connect(self._on_schedule_interval)

        self.diff_banner = QLabel('差分：尚未对比')
        self.diff_banner.setObjectName('commAcceptDiffBanner')
        self.diff_banner.setWordWrap(True)
        self.diff_banner.setStyleSheet('color:#c9a;font-size:12px;padding:4px 2px;')
        lay.addWidget(self.diff_banner)

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
        self.btn_dump_vars = QPushButton('一键写入变量')
        self.btn_dump_vars.setObjectName('commAcceptDumpVarsBtn')
        self.btn_dump_vars.setToolTip(
            '把验收 PASS/FAIL/汇总 + 回包 VALUE/MEAS 解析写入工程 flow 变量（需主窗 document）'
        )
        self.btn_dump_vars.setStyleSheet(
            'QPushButton{background:#2a3a4a;color:#9ad;font-weight:600;padding:6px 12px;}'
        )
        self.btn_dump_vars.clicked.connect(self._dump_vars)
        row.addWidget(self.btn_dump_vars)
        self.summary_lab = QLabel('尚未运行')
        self.summary_lab.setObjectName('commAcceptSummary')
        row.addWidget(self.summary_lab)
        row.addStretch(1)
        b_close = QPushButton('关闭')
        b_close.clicked.connect(self.accept)
        row.addWidget(b_close)
        lay.addLayout(row)
        self._bootstrap_last()


    
    def _dump_vars(self):
        """细妆⑱：验收→变量一键落盘."""
        report = self._report
        if not report:
            # try last on disk
            try:
                path = self.last_report_path()
                if path.is_file():
                    report = json.loads(path.read_text(encoding='utf-8'))
                    self._report = report
            except Exception:
                report = None
        if not report:
            QMessageBox.information(self, '写入变量', '尚无验收报告。请先干跑或载入上次报告。')
            return
        # resolve project from parent MainWindow
        project = None
        doc = None
        w = self.parent()
        while w is not None and not hasattr(w, 'document'):
            try:
                w = w.parent()
            except Exception:
                w = None
                break
        if w is not None and hasattr(w, 'document'):
            doc = w.document
            project = getattr(doc, 'project', None)
        if not isinstance(project, dict):
            QMessageBox.warning(
                self, '写入变量',
                '未找到主窗工程（document.project）。请从主程序「真机 Comm 验收」打开本对话框。',
            )
            return
        try:
            stats = dump_acceptance_to_variables(project, report)
        except Exception as err:
            QMessageBox.warning(self, '写入变量失败', str(err))
            return
        try:
            if doc is not None:
                if hasattr(doc, 'mark_dirty'):
                    doc.mark_dirty()
                if hasattr(doc, 'changed'):
                    doc.changed.emit()
        except Exception:
            pass
        msg = (
            f"已写入 {stats.get('written', 0)} 个变量"
            f"（含 extras {stats.get('extras', 0)}）\n"
            + '、'.join((stats.get('keys') or [])[:8])
            + ('…' if len(stats.get('keys') or []) > 8 else '')
        )
        self._log('变量落盘 · ' + msg.replace('\n', ' · '))
        try:
            if w is not None and hasattr(w, 'log'):
                w.log('Comm 验收变量落盘 · ' + msg.replace('\n', ' · '))
            if w is not None and hasattr(w, 'statusBar'):
                w.statusBar().showMessage(
                    f"Comm验收→变量 · 写入{stats.get('written', 0)}", 5000,
                )
        except Exception:
            pass
        # 细妆⑲：Variables 面板即时高亮刚写入的 keys
        try:
            keys = list(stats.get('keys') or [])
            if w is not None and keys and hasattr(w, 'highlight_variables_keys'):
                w.highlight_variables_keys(keys)
            elif w is not None and keys:
                # fallback: open variables dialog then highlight
                dlg = None
                try:
                    dlg = (getattr(w, 'dialogs', None) or {}).get('variables')
                except Exception:
                    dlg = None
                if dlg is None and hasattr(w, 'open_dialog'):
                    try:
                        w.open_dialog('variables')
                        dlg = (getattr(w, 'dialogs', None) or {}).get('variables')
                    except Exception:
                        dlg = None
                if dlg is not None and hasattr(dlg, 'highlight_written_keys'):
                    try:
                        dlg.show(); dlg.raise_()
                    except Exception:
                        pass
                    dlg.highlight_written_keys(keys)
        except Exception:
            pass
        QMessageBox.information(self, '变量已落盘', msg)

    def _bootstrap_last(self):
        try:
            path = self.last_report_path()
            if path.is_file():
                report = json.loads(path.read_text(encoding='utf-8'))
                self._report = report
                self._update_last_banner(report)
                s = report.get('summary') or {}
                self.summary_lab.setText(
                    f"上次 PASS {s.get('pass', 0)} · FAIL {s.get('fail', 0)} · SKIP {s.get('skip', 0)}"
                )
        except Exception:
            pass

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
        # Capture previous disk report BEFORE overwrite for last-vs-now diff
        prev = None
        try:
            path0 = self.last_report_path()
            if path0.is_file():
                prev = json.loads(path0.read_text(encoding='utf-8'))
        except Exception:
            prev = None
        self._report = report
        self.btn_run.setEnabled(True)
        self.btn_stop.setEnabled(False)
        s = report.get('summary') or {}
        self.summary_lab.setText(
            f"PASS {s.get('pass', 0)} · FAIL {s.get('fail', 0)} · SKIP {s.get('skip', 0)}"
        )
        self._log(f"验收结束 {report.get('finishedAt')} @ {report.get('host')}:{report.get('port')}")
        if prev:
            try:
                self._show_diff(prev, report, label='上次↔本次')
            except Exception as err:
                self._log(f'差分失败：{err}')
        path = self._persist_report(report)
        if path:
            self._log(f'报告已落盘 {path}')
        self._update_last_banner(report)
        # 细妆⑯：schedule hist spark + FAIL alert toast
        try:
            self._record_schedule_hist(report)
        except Exception as err:
            self._log(f'复测序列记录失败：{err}')
        try:
            fail_n = int((report.get('summary') or {}).get('fail') or 0)
            if fail_n > 0:
                self._fail_alert_toast(report)
        except Exception as err:
            self._log(f'FAIL toast 失败：{err}')
        # Keep schedule ticking if enabled
        if getattr(self, 'chk_schedule', None) and self.chk_schedule.isChecked():
            self._refresh_schedule_status()


    def _report_dir(self) -> Path:
        base = self._data_dir or Path('data/native-desktop')
        d = Path(base) / 'comm-acceptance'
        d.mkdir(parents=True, exist_ok=True)
        return d

    def last_report_path(self) -> Path:
        return self._report_dir() / 'last-report.json'

    def _persist_report(self, report: dict):
        try:
            path = self.last_report_path()
            path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
            # also stamp a history copy
            stamp = (report.get('finishedAt') or '').replace(':', '').replace(' ', '_')
            if stamp:
                hist = self._report_dir() / f'report-{stamp}.json'
                try:
                    hist.write_text(path.read_text(encoding='utf-8'), encoding='utf-8')
                except Exception:
                    pass
            return str(path)
        except Exception as err:
            self._log(f'落盘失败：{err}')
            return None

    def _update_last_banner(self, report: dict | None):
        if not hasattr(self, 'last_banner'):
            return
        if not report:
            self.last_banner.setText('上次验收：尚无记录')
            return
        s = report.get('summary') or {}
        self.last_banner.setText(
            f"上次验收 {report.get('finishedAt') or '—'} @ {report.get('host')}:{report.get('port')} — "
            f"PASS {s.get('pass', 0)} · FAIL {s.get('fail', 0)} · SKIP {s.get('skip', 0)}"
        )

    def _load_last_report(self):
        path = self.last_report_path()
        if not path.is_file():
            QMessageBox.information(self, '上次报告', f'尚无落盘报告：\n{path}')
            return
        try:
            report = json.loads(path.read_text(encoding='utf-8'))
        except Exception as err:
            QMessageBox.warning(self, '读取失败', str(err))
            return
        self._report = report
        self._apply_report_to_table(report)
        self._update_last_banner(report)
        s = report.get('summary') or {}
        self.summary_lab.setText(
            f"PASS {s.get('pass', 0)} · FAIL {s.get('fail', 0)} · SKIP {s.get('skip', 0)}（已载入）"
        )
        self._log(f'已载入上次报告 {path}')

    def _apply_report_to_table(self, report: dict):
        items = {it.get('id'): it for it in (report.get('items') or []) if isinstance(it, dict)}
        for i, (cid, title, cmd, _) in enumerate(CHECKLIST):
            it = items.get(cid) or {}
            status = it.get('status') or '—'
            detail = it.get('detail') or ''
            reply = it.get('reply') or ''
            self.table.item(i, 3).setText(str(status))
            text = detail
            if reply:
                text = f'{detail} | {reply}' if detail else reply
            self.table.item(i, 4).setText(text)
        # host/port
        try:
            if report.get('host'):
                self.host_edit.setText(str(report['host']))
            if report.get('port'):
                self.port_spin.setValue(int(report['port']))
        except Exception:
            pass


    # ----- 细妆⑮：schedule / last-vs-now diff -----

    def _on_schedule_toggled(self, on: bool):
        if on:
            mins = int(self.schedule_spin.value())
            self._schedule_timer.start(max(1, mins) * 60 * 1000)
            self._refresh_schedule_status()
            self._log(f'定时复测已启用 · 每 {mins} 分钟')
        else:
            self._schedule_timer.stop()
            self.schedule_status.setText('定时：关')
            self._log('定时复测已关闭')

    def _on_schedule_interval(self, *_):
        if self.chk_schedule.isChecked():
            mins = int(self.schedule_spin.value())
            self._schedule_timer.start(max(1, mins) * 60 * 1000)
            self._refresh_schedule_status()

    def _refresh_schedule_status(self):
        if not self.chk_schedule.isChecked():
            self.schedule_status.setText('定时：关')
            return
        mins = int(self.schedule_spin.value())
        remain = self._schedule_timer.remainingTime()
        if remain < 0:
            self.schedule_status.setText(f'定时：每 {mins} 分')
        else:
            sec = max(0, remain // 1000)
            self.schedule_status.setText(f'定时：每 {mins} 分 · 下次约 {sec // 60}分{sec % 60}秒')

    def _on_schedule_fire(self):
        if self._runner and self._runner.isRunning():
            self._log('定时触发跳过：上次验收仍在跑')
            return
        self._log('定时触发 → 开始验收干跑')
        self._start()


    def schedule_spark_text(self, width=24):
        gh = getattr(self, '_schedule_hist', None) or []
        if not gh:
            return '· · ·  ·  等待定时'
        seq = list(reversed(gh[:width]))
        s = ''.join('▇' if v else '▁' for v in seq)
        passed = sum(1 for v in gh if v)
        return f'{s}  ·  复测 {passed}/{len(gh)} 通 (高=整次PASS)'

    def _refresh_schedule_spark(self):
        lab = getattr(self, 'schedule_spark', None)
        if lab is None:
            return
        text = self.schedule_spark_text()
        lab.setText(f'复测序列  {text}')
        fail_recent = any(not v for v in (getattr(self, '_schedule_hist', None) or [])[:3])
        color = '#e35d6a' if fail_recent else '#9ad'
        lab.setStyleSheet(f'color:{color};font-size:11px;font-family:monospace;padding:2px 4px;')

    def _record_schedule_hist(self, report: dict):
        s = (report or {}).get('summary') or {}
        fail_n = int(s.get('fail') or 0)
        ok = fail_n == 0
        gh = getattr(self, '_schedule_hist', None)
        if gh is None:
            self._schedule_hist = []
            gh = self._schedule_hist
        gh.insert(0, bool(ok))
        del gh[48:]
        self._refresh_schedule_spark()

    def _fail_alert_toast(self, report: dict):
        """Non-modal FAIL alert: banner + status + optional parent statusBar."""
        s = (report or {}).get('summary') or {}
        fail_n = int(s.get('fail') or 0)
        msg = (
            f"⚠ Comm 验收 FAIL ×{fail_n}  @ {report.get('host')}:{report.get('port')}  "
            f"{report.get('finishedAt') or ''}"
        )
        # paint diff banner red
        if hasattr(self, 'diff_banner'):
            self.diff_banner.setStyleSheet('color:#e35d6a;font-size:12px;padding:4px 2px;font-weight:600;')
            prev = self.diff_banner.text() or ''
            self.diff_banner.setText(f'FAIL 告警：{msg}' + (f' · {prev}' if prev and not prev.startswith('FAIL') else ''))
        self._log(msg)
        # toast via parent statusBar if available
        parent = self.parent()
        try:
            if parent is not None and hasattr(parent, 'statusBar'):
                parent.statusBar().showMessage(msg, 8000)
        except Exception:
            pass
        # brief non-blocking message box alternative: QToolTip / flash summary
        if hasattr(self, 'summary_lab'):
            self.summary_lab.setStyleSheet('color:#e35d6a;font-weight:600;')
            # restore color later
            QTimer.singleShot(6000, lambda: self.summary_lab.setStyleSheet(''))

    @staticmethod
    def diff_reports(prev: dict | None, now: dict | None) -> dict:
        """Compare two acceptance reports item-by-item.

        Returns {changed:[{id,title,from,to,detail}], same, added, removed, summary}.
        """
        prev = prev or {}
        now = now or {}
        pmap = {it.get('id'): it for it in (prev.get('items') or []) if isinstance(it, dict) and it.get('id')}
        nmap = {it.get('id'): it for it in (now.get('items') or []) if isinstance(it, dict) and it.get('id')}
        changed, same = [], []
        for cid, nit in nmap.items():
            pit = pmap.get(cid)
            if not pit:
                changed.append({
                    'id': cid, 'title': nit.get('title') or cid,
                    'from': '—', 'to': nit.get('status'),
                    'detail': nit.get('detail') or '',
                })
                continue
            if (pit.get('status') or '') != (nit.get('status') or ''):
                changed.append({
                    'id': cid, 'title': nit.get('title') or cid,
                    'from': pit.get('status'), 'to': nit.get('status'),
                    'detail': f"{pit.get('detail') or ''} → {nit.get('detail') or ''}",
                })
            else:
                same.append(cid)
        removed = [cid for cid in pmap if cid not in nmap]
        ps = prev.get('summary') or {}
        ns = now.get('summary') or {}
        return {
            'changed': changed,
            'same': same,
            'removed': removed,
            'prevSummary': ps,
            'nowSummary': ns,
            'prevAt': prev.get('finishedAt'),
            'nowAt': now.get('finishedAt'),
        }

    def _show_diff(self, prev, now, label='上次↔当前'):
        d = self.diff_reports(prev, now)
        ch = d['changed']
        ps, ns = d['prevSummary'], d['nowSummary']
        head = (
            f"{label} · 变更 {len(ch)} 项 · 相同 {len(d['same'])}"
            f" · 摘要 PASS {ps.get('pass', 0)}→{ns.get('pass', 0)}"
            f" / FAIL {ps.get('fail', 0)}→{ns.get('fail', 0)}"
        )
        if ch:
            bits = [f"{c['title']}:{c['from']}→{c['to']}" for c in ch[:8]]
            head += ' · ' + '；'.join(bits)
            if len(ch) > 8:
                head += f' …共{len(ch)}'
        else:
            head += ' · 无状态变化'
        if hasattr(self, 'diff_banner'):
            color = '#e35d6a' if ch else '#3ecf8e'
            self.diff_banner.setStyleSheet(f'color:{color};font-size:12px;padding:4px 2px;')
            self.diff_banner.setText(f'差分：{head}')
        self._log(f'差分 {head}')
        return d

    def _compare_last_vs_now(self):
        path = self.last_report_path()
        if not path.is_file():
            QMessageBox.information(self, '对比', f'尚无上次报告：\n{path}')
            return
        try:
            prev = json.loads(path.read_text(encoding='utf-8'))
        except Exception as err:
            QMessageBox.warning(self, '读取失败', str(err))
            return
        now = self._report
        if not now:
            QMessageBox.information(self, '对比', '当前尚无内存报告，请先跑一次验收或载入后再对比。')
            return
        # If now is same object as disk (just loaded), try to use table snapshot as "now"
        d = self._show_diff(prev, now, label='磁盘上次↔内存当前')
        # Also paint table column tip for changed rows
        try:
            changed_ids = {c['id'] for c in d['changed']}
            for i, (cid, title, cmd, _) in enumerate(CHECKLIST):
                if cid in changed_ids:
                    item = self.table.item(i, 3)
                    if item:
                        item.setToolTip('相对上次报告状态已变更')
        except Exception:
            pass

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
