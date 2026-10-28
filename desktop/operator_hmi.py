"""Run-mode operator HMI — live widgets from project.runUi (VisionMaster-style)."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from datetime import datetime

from PySide6.QtCore import Qt, Signal, QTimer, QSettings
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QPlainTextEdit, QGridLayout, QSizePolicy, QLineEdit, QListWidget,
    QTableWidget, QTableWidgetItem, QProgressBar, QHeaderView,
    QComboBox, QTabWidget, QStackedWidget, QFileDialog, QApplication,
    QSpinBox,
)

from desktop.image_view import ImageView
from desktop.theme import TEXT, TEXT_MUTED, TEXT_DIM, CARD, LINE, OK, PANEL
from desktop.widgets.switch import OrangeSwitch
from desktop.run_ui_designer import (
    SPLIT_PRESETS, CONTROL_STUB_HINTS, CAMERA_BIND_OPTIONS, COMM_BIND_OPTIONS,
)

# split index → (rows, cols) — keep in sync with RunUiDesignerDialog._build_split_pages
SPLIT_GRID = {
    '1': (1, 1),
    '2': (1, 2),
    '3': (1, 3),
    '4': (2, 2),
    '6': (2, 3),
    '8': (2, 4),
    '9': (3, 3),
    '自定义': (2, 2),
}

DEFAULT_RUN_COMMANDS = [
    dict(type='执行·单次', config=''),
]
DEFAULT_CONT_COMMANDS = [
    dict(type='执行·连续', config=''),
]
DEFAULT_STOP_COMMANDS = [
    dict(type='执行·停止', config=''),
]
DEFAULT_INJECT_RUN_COMMANDS = [
    dict(type='注入·RUN', config=''),
]
DEFAULT_INJECT_STOP_COMMANDS = [
    dict(type='注入·STOP', config=''),
]
DEFAULT_PAUSE_COMMANDS = [
    dict(type='执行·暂停', config=''),
]
DEFAULT_RESUME_COMMANDS = [
    dict(type='执行·继续', config=''),
]
DEFAULT_CLEAR_ALARM_COMMANDS = [
    dict(type='状态·清除报警', config=''),
]
DEFAULT_ALARM_COMMANDS = [
    dict(type='状态·报警', config=''),
]


def _split_rows_cols(split: str):
    return SPLIT_GRID.get(split or '1', (1, 1))


class StatusLamp(QLabel):
    """Simple round-ish status lamp (OK/NG / 信号灯) — 细妆⑱ blink on NG."""

    def __init__(self, caption='状态', parent=None):
        super().__init__(parent)
        self._caption = caption or '状态'
        self._ok = None
        self._blink_on = False
        self._blink_timer = QTimer(self)
        self._blink_timer.setInterval(420)
        self._blink_timer.timeout.connect(self._toggle_blink)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumHeight(48)
        self.set_state(None)

    def set_caption(self, caption: str):
        self._caption = caption or self._caption or '状态'
        self.set_state(self._ok)

    def set_state(self, ok):
        prev = self._ok
        self._ok = ok
        self._blink_on = False
        self._paint_lamp()
        # NG 边沿起闪；离开 NG 停闪
        if ok is False:
            if prev is not False:
                self._blink_timer.start()
        else:
            self._blink_timer.stop()

    def _toggle_blink(self):
        if self._ok is not False:
            self._blink_timer.stop()
            return
        self._blink_on = not self._blink_on
        self._paint_lamp()

    def _paint_lamp(self):
        ok = self._ok
        if ok is True:
            color, text = '#1c3a2a', f'{self._caption}\nOK'
            border = '#3ecf8e'
        elif ok is False:
            # blink: alternate brighter border
            if self._blink_on:
                color, text = '#5a2020', f'{self._caption}\nNG'
                border = '#ff6b7a'
            else:
                color, text = '#3a1c1c', f'{self._caption}\nNG'
                border = '#e35d6a'
        else:
            color, text = '#2a3340', f'{self._caption}\n—'
            border = '#3d4a5c'
        self.setText(text)
        self.setStyleSheet(
            f'background:{color};color:{TEXT};border:2px solid {border};'
            f'border-radius:2px;font-weight:700;padding:6px;font-size:12px;'
        )



class ProductionStatsPanel(QWidget):
    """OK/NG counters + yield + recent history + pause/alarm (今日 HMI 交付)."""

    pauseToggled = Signal(bool)
    gateKeyChanged = Signal(object)  # str|None — user picked 「判定门」

    def __init__(self, parent=None):
        super().__init__(parent)
        self._ok = 0
        self._ng = 0
        self._paused = False
        self._history = []  # newest first, max 40
        self._elapsed_hist = []  # newest first ms, max 48 — drives HMI trend spark
        self._ok_hist = []  # newest first bool, max 48 — OK/NG spark
        self._uph_hist = []  # newest first UPH, max 48 — wave21 UPH trend
        self._uph_window = 24  # wave22: adjustable spark window (8..48)
        try:
            self._uph_window = self._load_uph_window_pref()
        except Exception:
            pass
        self._gate_key = None  # None → auto probe flow vars
        self._trend_listeners = []  # callables(panel) after record/reset
        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(4)

        self._alarm = QLabel('')
        self._alarm.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._alarm.setStyleSheet(
            f'background:#3a1c1c;color:#ffb4b4;border:1px solid #e35d6a;'
            f'border-radius:2px;padding:4px;font-weight:700;font-size:11px;'
        )
        self._alarm.hide()
        root.addWidget(self._alarm)

        row = QHBoxLayout()
        self._ok_lab = QLabel('OK\n0')
        self._ng_lab = QLabel('NG\n0')
        self._yield_lab = QLabel('良率\n—')
        self._total_lab = QLabel('总量\n0')
        for lab, color in (
            (self._ok_lab, '#3ecf8e'),
            (self._ng_lab, '#e35d6a'),
            (self._yield_lab, '#6eb6ff'),
            (self._total_lab, TEXT_MUTED),
        ):
            lab.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lab.setMinimumHeight(52)
            lab.setStyleSheet(
                f'background:{CARD};color:{color};border:1px solid {LINE};'
                f'border-radius:2px;font-weight:700;font-size:12px;padding:4px;'
            )
            row.addWidget(lab, 1)
        root.addLayout(row)

        btn_row = QHBoxLayout()
        self._pause_btn = QPushButton('⏸ 暂停计数')
        self._pause_btn.setCheckable(True)
        self._pause_btn.toggled.connect(self._on_pause)
        btn_row.addWidget(self._pause_btn)
        self._pause_owner_badge = QLabel('')
        self._pause_owner_badge.setObjectName('pauseOwnerBadge')
        self._pause_owner_badge.setStyleSheet(
            f'color:{TEXT_MUTED};font-size:11px;padding:0 6px;'
        )
        self._pause_owner_badge.setVisible(False)
        btn_row.addWidget(self._pause_owner_badge)
        reset = QPushButton('清零')
        reset.clicked.connect(self.reset)
        btn_row.addWidget(reset)
        copy_btn = QPushButton('复制历史')
        copy_btn.setToolTip('复制最近结果到剪贴板（便于产线交接/对账）')
        copy_btn.clicked.connect(self._copy_history)
        btn_row.addWidget(copy_btn)
        csv_btn = QPushButton('导出CSV')
        csv_btn.setObjectName('prodStatsExportCsv')
        csv_btn.setToolTip('导出生产统计历史 CSV')
        csv_btn.clicked.connect(self.export_history_file)
        btn_row.addWidget(csv_btn)
        self._gate_btn = QPushButton('判定门')
        self._gate_btn.setToolTip('选择 flow 变量作为 OK/NG 判定门（默认自动探测 passGate/commOk/…）')
        self._gate_btn.clicked.connect(self._pick_gate_key)
        btn_row.addWidget(self._gate_btn)
        btn_row.addStretch(1)
        root.addLayout(btn_row)
        self._gate_lab = QLabel('判定门：自动')
        self._gate_lab.setStyleSheet(f'color:{TEXT_MUTED};font-size:11px;')
        root.addWidget(self._gate_lab)

        # 细妆⑰：VM run-mode strip — host state + OK序列 + UPH
        self._host_state_lab = QLabel('上位机 · 空闲')
        self._host_state_lab.setObjectName('prodHostStateLab')
        self._host_state_lab.setStyleSheet(
            f'background:{CARD};color:{TEXT_MUTED};border:1px solid {LINE};'
            f'border-radius:2px;padding:3px 6px;font-size:11px;font-weight:600;'
        )
        root.addWidget(self._host_state_lab)
        # Alarm/OK-NG dashboard soft strip (page-level deepen; not micro chips)
        self._okng_dash_lab = QLabel('看板 · OK 0  NG 0  良率 —  ·  序列 —  ·  报警关')
        self._okng_dash_lab.setObjectName('prodOkNgDashboardStrip')
        self._okng_dash_lab.setWordWrap(True)
        self._okng_dash_lab.setStyleSheet(
            f'background:{CARD};color:{TEXT_MUTED};border:1px solid {LINE};'
            f'border-radius:2px;padding:4px 6px;font-size:11px;font-weight:600;'
        )
        self._okng_dash_lab.setToolTip('Alarm/OK-NG 看板软条：累计 + 序列 + 报警态（跟 Host SM / 页铬）')
        root.addWidget(self._okng_dash_lab)
        self._ok_spark_lab = QLabel('判定序列 · · ·')
        self._ok_spark_lab.setObjectName('prodOkSpark')
        self._ok_spark_lab.setStyleSheet(f'color:{TEXT_MUTED};font-size:12px;font-family:monospace;')
        self._ok_spark_lab.setToolTip('OK/NG 序列（高=OK）；与趋势图同源')
        root.addWidget(self._ok_spark_lab)
        self._uph_lab = QLabel('节拍 · —  ·  UPH —')
        self._uph_lab.setObjectName('prodUphLab')
        self._uph_lab.setStyleSheet(f'color:{TEXT_MUTED};font-size:11px;')
        self._uph_lab.setToolTip('末次/均耗时 → 估算 UPH（件/小时，按均耗时）')
        root.addWidget(self._uph_lab)
        uph_row = QHBoxLayout()
        uph_row.setSpacing(6)
        self._uph_trend_lab = QLabel('UPH趋势 · · ·  ·  等待')
        self._uph_trend_lab.setObjectName('prodUphTrend')
        self._uph_trend_lab.setStyleSheet(
            f'color:{TEXT_MUTED};font-size:12px;font-family:monospace;'
            f'background:{CARD};border:1px solid {LINE};border-radius:2px;padding:4px 6px;'
        )
        self._uph_trend_lab.setToolTip(
            '产线 UPH 趋势看板（高=更快；按每次均耗时估算件/小时）；右侧可调窗口'
        )
        uph_row.addWidget(self._uph_trend_lab, 1)
        win_lab = QLabel('窗口')
        win_lab.setStyleSheet(f'color:{TEXT_MUTED};font-size:11px;')
        uph_row.addWidget(win_lab)
        self._uph_window_spin = QSpinBox()
        self._uph_window_spin.setObjectName('prodUphWindowSpin')
        self._uph_window_spin.setRange(8, 48)
        self._uph_window_spin.setSingleStep(8)
        self._uph_window_spin.setValue(int(self._uph_window))
        self._uph_window_spin.setToolTip('UPH 趋势窗口（8–48，步进 8）；影响 spark 与均/峰统计')
        self._uph_window_spin.setMaximumWidth(72)
        self._uph_window_spin.valueChanged.connect(self._on_uph_window_changed)
        uph_row.addWidget(self._uph_window_spin)
        # wave24: UPH 窗口预设快捷
        self._uph_preset_btns = []
        for preset in (8, 16, 24, 32, 48):
            b = QPushButton(str(preset))
            b.setObjectName(f'prodUphPreset{preset}')
            b.setFixedWidth(28)
            b.setMaximumHeight(22)
            b.setToolTip(f'UPH 窗口快捷 → {preset}')
            b.clicked.connect(lambda *_a, n=preset: self.set_uph_window(n))
            uph_row.addWidget(b)
            self._uph_preset_btns.append(b)
        # wave26: 一键还原常用 UPH
        self._uph_restore_btn = QPushButton('常用')
        self._uph_restore_btn.setObjectName('prodUphRestoreRecent')
        self._uph_restore_btn.setFixedWidth(36)
        self._uph_restore_btn.setMaximumHeight(22)
        self._uph_restore_btn.setToolTip('一键还原最近常用 UPH 窗口')
        self._uph_restore_btn.clicked.connect(self.restore_uph_preset_recent)
        uph_row.addWidget(self._uph_restore_btn)
        self._sync_uph_preset_chrome()
        root.addLayout(uph_row)

        cap = QLabel('最近结果')
        cap.setStyleSheet(f'color:{TEXT_MUTED};font-size:11px;font-weight:600;')
        root.addWidget(cap)
        self._list = QListWidget()
        self._list.setMaximumHeight(140)
        self._list.setStyleSheet('font-size:11px;')
        root.addWidget(self._list, 1)
        self._refresh_labels()

    def set_pause_owner_badge(self, mode):
        """Mirror filmstrip pause-owner tip: continuous | run_all | None."""
        if not hasattr(self, '_pause_owner_badge'):
            return
        if mode == 'run_all':
            text = '模式·运行全部'
            tip = '运行全部（与连续运行共用同一暂停控件）：暂停/继续切图调度'
        elif mode == 'continuous':
            text = '模式·连续运行'
            tip = '连续运行（与运行全部共用同一暂停控件）：暂停/继续调度（可改间隔）'
        else:
            text = ''
            tip = '连续运行 / 运行全部共用：暂停/继续切图调度（可中途改间隔）'
        self._pause_owner_badge.setText(text)
        self._pause_owner_badge.setToolTip(tip)
        self._pause_owner_badge.setVisible(bool(text))
        if hasattr(self, '_pause_btn'):
            self._pause_btn.setToolTip(tip)

    def _on_pause(self, on: bool):
        self._paused = bool(on)
        self._pause_btn.setText('▶ 继续计数' if on else '⏸ 暂停计数')
        self.pauseToggled.emit(self._paused)

    def _copy_history(self):
        from PySide6.QtWidgets import QApplication
        lines = list(self._history) if self._history else ['(暂无结果)']
        QApplication.clipboard().setText('\n'.join(lines))

    def history_csv(self) -> str:
        lines = ['timestamp,tag,elapsed_ms,detail']
        for line in self._history:
            # lines look like: HH:MM:SS  OK · 12 ms  detail
            safe = str(line).replace('"', "'")
            lines.append(f'"{safe}"')
        return '\n'.join(lines) + ('\n' if lines else '')

    def export_history_file(self):
        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getSaveFileName(
            self, '导出生产统计', 'production-stats.csv', 'CSV (*.csv);;All (*)')
        if not path:
            return
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(self.history_csv())
        except Exception:
            pass

    def set_host_state_mirror(self, state: str, zh: str | None = None):
        """Mirror Host SM state into production panel (VM run-mode feel)."""
        lab = getattr(self, '_host_state_lab', None)
        if lab is None:
            return
        st = state or 'Idle'
        label = zh or st
        colors = {
            'Idle': ('#2a3340', '#8a9bb0'),
            'Running': ('#1c3a2a', '#3ecf8e'),
            'Paused': ('#3a3420', '#e0b84a'),
            'Alarm': ('#3a1c1c', '#e35d6a'),
            'Stopped': ('#2a3340', '#8a9bb0'),
        }
        bg, fg = colors.get(st, colors['Idle'])
        lab.setText(f'上位机 · {label}')
        lab.setStyleSheet(
            f'background:{bg};color:{fg};border:1px solid {fg};'
            f'border-radius:2px;padding:3px 6px;font-size:11px;font-weight:700;'
        )
        if st == 'Alarm':
            self.set_alarm(f'上位机报警 · {label}')
        elif st in ('Idle', 'Running', 'Paused', 'Stopped'):
            # don't clear NG sticky alarm unless transitioning out of Alarm via clear
            pass

    def set_gate_key(self, key: str | None, *, notify: bool = True):
        key = (key or '').strip() or None
        prev = self._gate_key
        self._gate_key = key
        if hasattr(self, '_gate_lab'):
            self._gate_lab.setText(f'判定门：{key}' if key else '判定门：自动')
        if hasattr(self, '_gate_btn'):
            self._gate_btn.setText(f'门:{key}' if key else '判定门')
        if notify and key != prev:
            try:
                self.gateKeyChanged.emit(self._gate_key)
            except Exception:
                pass

    def gate_key(self):
        return self._gate_key

    def _pick_gate_key(self):
        from PySide6.QtWidgets import QInputDialog
        options = ['(自动)', 'passGate', 'commOk', 'passed', 'ok', 'ResultOK', 'taskStatus']
        cur = self._gate_key or '(自动)'
        idx = options.index(cur) if cur in options else 0
        choice, ok = QInputDialog.getItem(
            self, '判定门变量',
            '选择 flow.* 变量名（OK 当且仅当真值）\n也可手填自定义名：',
            options, idx, True,
        )
        if not ok:
            return
        if not choice or choice == '(自动)':
            self.set_gate_key(None)
        else:
            self.set_gate_key(choice.strip())

    def reset(self):
        self._ok = 0
        self._ng = 0
        self._history.clear()
        self._elapsed_hist.clear()
        self._ok_hist.clear()
        self._uph_hist.clear()
        self._list.clear()
        self.clear_alarm()
        self._refresh_labels()
        self._notify_trend()

    def clear_alarm(self):
        self._alarm.hide()
        self._alarm.setText('')

    def set_alarm(self, message: str):
        if not message:
            self.clear_alarm()
            return
        self._alarm.setText('⚠ ' + str(message))
        self._alarm.show()

    def record(self, ok: bool | None, elapsed_ms=None, detail=''):
        if self._paused or ok is None:
            return
        if ok:
            self._ok += 1
            tag = 'OK'
        else:
            self._ng += 1
            tag = 'NG'
            self.set_alarm(detail or '检测 NG')
        if ok:
            # clear sticky alarm on next OK
            self.clear_alarm()
        ts = datetime.now().strftime('%H:%M:%S')
        ms = f' · {elapsed_ms} ms' if elapsed_ms is not None else ''
        line = f'{ts}  {tag}{ms}' + (f'  {detail}' if detail else '')
        self._history.insert(0, line)
        self._history = self._history[:40]
        try:
            em = float(elapsed_ms) if elapsed_ms is not None else None
        except (TypeError, ValueError):
            em = None
        if em is not None and em >= 0:
            self._elapsed_hist.insert(0, em)
            self._elapsed_hist = self._elapsed_hist[:48]
            avg = sum(self._elapsed_hist) / len(self._elapsed_hist)
            if avg > 0:
                self._uph_hist.insert(0, 3600000.0 / avg)
                self._uph_hist = self._uph_hist[:48]
        self._ok_hist.insert(0, bool(ok))
        self._ok_hist = self._ok_hist[:48]
        self._list.insertItem(0, line)
        while self._list.count() > 40:
            self._list.takeItem(self._list.count() - 1)
        self._refresh_labels()
        self._notify_trend()

    def _refresh_labels(self):
        total = self._ok + self._ng
        self._ok_lab.setText(f'OK\n{self._ok}')
        self._ng_lab.setText(f'NG\n{self._ng}')
        self._total_lab.setText(f'总量\n{total}')
        if total:
            y = 100.0 * self._ok / total
            self._yield_lab.setText(f'良率 {y:.1f}%\n{self._ok}/{total}')
            self._yield_lab.setToolTip(
                f'良率 = OK/(OK+NG) = {self._ok}/{total} = {y:.2f}%\n'
                '暂停计数时不累计；清零后重新统计。'
            )
        else:
            self._yield_lab.setText('良率 —\n0/0')
            self._yield_lab.setToolTip('尚无计数。运行完成后按判定门 (gate) 累计 OK/NG。')
        # 细妆⑰：inline OK spark + UPH
        spark = getattr(self, '_ok_spark_lab', None)
        if spark is not None:
            spark.setText(self.trend_ok_text())
        uph = getattr(self, '_uph_lab', None)
        if uph is not None:
            if self._elapsed_hist:
                last = self._elapsed_hist[0]
                avg = sum(self._elapsed_hist) / len(self._elapsed_hist)
                uph_v = (3600000.0 / avg) if avg > 0 else 0.0
                uph.setText(f'节拍 · 末次 {last:.0f} ms · 均 {avg:.0f} ms  ·  UPH {uph_v:.0f}')
            else:
                uph.setText('节拍 · —  ·  UPH —')
        ut = getattr(self, '_uph_trend_lab', None)
        if ut is not None:
            ut.setText(self.trend_uph_text())
        # Deepen OK/NG dashboard soft strip
        dash = getattr(self, '_okng_dash_lab', None)
        if dash is not None:
            ok_i = int(self._ok)
            ng_i = int(self._ng)
            tot = ok_i + ng_i
            ytxt = f'{(100.0 * ok_i / tot):.1f}%' if tot else '—'
            hist = list(getattr(self, '_ok_hist', []) or [])
            seq = ''.join(('O' if b else 'N') for b in reversed(hist[:24])) if hist else '—'
            alarm = getattr(self, '_alarm', None)
            alarm_on = bool(alarm is not None and alarm.isVisible() and (alarm.text() or '').strip())
            alarm_bit = ('⚠ ' + alarm.text().replace('⚠ ', '')[:28]) if alarm_on else '报警关'
            dash.setText(
                f'看板 · OK {ok_i}  NG {ng_i}  良率 {ytxt}  ·  序列 {seq}  ·  {alarm_bit}'
            )
            if alarm_on or (ng_i > ok_i and tot):
                dash.setStyleSheet(
                    'background:#3a1c1c;color:#ffb4b4;border:1px solid #e35d6a;'
                    'border-radius:2px;padding:4px 6px;font-size:11px;font-weight:700;'
                )
            elif ok_i > 0 and ng_i == 0:
                dash.setStyleSheet(
                    'background:#1c3a2a;color:#9ed9a8;border:1px solid #3ecf8e;'
                    'border-radius:2px;padding:4px 6px;font-size:11px;font-weight:700;'
                )
            else:
                dash.setStyleSheet(
                    f'background:{CARD};color:{TEXT_MUTED};border:1px solid {LINE};'
                    f'border-radius:2px;padding:4px 6px;font-size:11px;font-weight:600;'
                )

    def ok_count(self):
        return self._ok

    def ng_count(self):
        return self._ng

    def elapsed_history(self):
        return list(self._elapsed_hist)

    def ok_history(self):
        return list(self._ok_hist)

    def add_trend_listener(self, cb):
        if callable(cb):
            self._trend_listeners.append(cb)

    def _notify_trend(self):
        for cb in list(self._trend_listeners):
            try:
                cb(self)
            except Exception:
                pass

    @staticmethod
    def sparkline(values, width=24):
        """Unicode spark from newest-first values (renders left=oldest)."""
        bars = '▁▂▃▄▅▆▇█'
        if not values:
            return '·' * max(8, width // 3) + '  ·  等待运行'
        seq = list(reversed(values[:width]))
        lo = min(seq); hi = max(seq)
        span = (hi - lo) or 1.0
        out = []
        for v in seq:
            idx = int(round((float(v) - lo) / span * (len(bars) - 1)))
            idx = max(0, min(len(bars) - 1, idx))
            out.append(bars[idx])
        return ''.join(out)

    def trend_elapsed_text(self):
        spark = self.sparkline(self._elapsed_hist, 24)
        if not self._elapsed_hist:
            return f'{spark}'
        last = self._elapsed_hist[0]
        avg = sum(self._elapsed_hist) / len(self._elapsed_hist)
        return f'{spark}  ·  末次 {last:.0f} ms · 均 {avg:.0f} ms · n={len(self._elapsed_hist)}'

    def trend_ok_text(self):
        if not self._ok_hist:
            return '· · ·  ·  判定序列等待'
        # map OK→▇ NG→▁
        seq = list(reversed(self._ok_hist[:24]))
        s = ''.join('▇' if v else '▁' for v in seq)
        return f'{s}  ·  OK序列 (高=OK)'

    def uph_history(self):
        return list(self._uph_hist)

    def trend_uph_text(self):
        # wave21 UPH trend board · wave22 window adjustable
        if not self._uph_hist:
            return 'UPH趋势 · · ·  ·  等待'
        win = self.uph_window()
        slice_ = self._uph_hist[:win]
        spark = self.sparkline(slice_, win)
        last = slice_[0]
        peak = max(slice_)
        avg = sum(slice_) / len(slice_)
        return (
            f'UPH {spark}  ·  末次 {last:.0f} · 均 {avg:.0f}'
            f' · 峰 {peak:.0f} · n={len(slice_)}/{win}'
        )

    def uph_window(self) -> int:
        try:
            return max(8, min(48, int(self._uph_window)))
        except Exception:
            return 24

    def set_uph_window(self, n: int, *, persist: bool = True):
        """wave22/23: set UPH trend window (8..48); persist via QSettings."""
        try:
            n = int(n)
        except (TypeError, ValueError):
            return
        # snap to nearest 8-step within range
        n = max(8, min(48, n))
        n = 8 * max(1, round(n / 8))
        n = max(8, min(48, n))
        self._uph_window = n
        spin = getattr(self, '_uph_window_spin', None)
        if spin is not None:
            try:
                spin.blockSignals(True)
                spin.setValue(n)
                spin.blockSignals(False)
            except Exception:
                pass
        if persist:
            try:
                self._save_uph_window_pref(n)
            except Exception:
                pass
            try:
                self._remember_uph_preset(n)
            except Exception:
                pass
        self._refresh_labels()
        self._notify_trend()
        self._sync_uph_preset_chrome()

    def _sync_uph_preset_chrome(self):
        """wave24–26: highlight active UPH preset; mark recent; enable 常用."""
        cur = self.uph_window()
        recent = self._load_uph_preset_recent()
        btn_r = getattr(self, '_uph_restore_btn', None)
        if btn_r is not None:
            has = bool(recent) or False
            try:
                last = self._uph_settings().value('prod/uphPresetLast', None)
                if last is not None and int(last) in (8, 16, 24, 32, 48):
                    has = True
                    btn_r.setToolTip(f'一键还原常用 UPH → {int(last)}')
                elif recent:
                    btn_r.setToolTip(f'一键还原常用 UPH → {recent[0]}')
                else:
                    btn_r.setToolTip('一键还原最近常用 UPH 窗口（暂无记忆）')
            except Exception:
                pass
            btn_r.setEnabled(bool(has))
            if has:
                btn_r.setStyleSheet(
                    'background:#1c2a3a;color:#9ec9f0;border:1px solid #6eb6ff;'
                    'border-radius:2px;font-size:10px;font-weight:700;padding:1px;'
                )
            else:
                btn_r.setStyleSheet(
                    'background:#2a2c30;color:#6a7078;border:1px solid #3a3d42;'
                    'border-radius:2px;font-size:10px;padding:1px;'
                )
        for b in getattr(self, '_uph_preset_btns', None) or []:
            try:
                n = int(b.text() or 0)
            except Exception:
                n = 0
            is_recent = n in recent
            if n == cur:
                b.setStyleSheet(
                    'background:#1c3a2a;color:#9ed9a8;border:1px solid #3ecf8e;'
                    'border-radius:2px;font-size:10px;font-weight:700;padding:1px;'
                )
                tip = f'UPH 窗口快捷 → {n}（当前）'
            elif is_recent:
                b.setStyleSheet(
                    'background:#2a3340;color:#9ec9f0;border:1px solid #6eb6ff;'
                    'border-radius:2px;font-size:10px;font-weight:600;padding:1px;'
                )
                tip = f'UPH 窗口快捷 → {n}（常用）'
            else:
                b.setStyleSheet(
                    'background:#2a2c30;color:#9aa0a6;border:1px solid #3a3d42;'
                    'border-radius:2px;font-size:10px;padding:1px;'
                )
                tip = f'UPH 窗口快捷 → {n}'
            try:
                b.setToolTip(tip)
            except Exception:
                pass

    @staticmethod
    def _uph_settings():
        return QSettings('SIEANS', 'VisionDesktop')

    def _load_uph_window_pref(self) -> int:
        """wave23: UPH 窗口持久."""
        try:
            v = int(self._uph_settings().value('prod/uphWindow', 24) or 24)
        except (TypeError, ValueError):
            v = 24
        v = max(8, min(48, v))
        v = 8 * max(1, round(v / 8))
        return max(8, min(48, v))

    def _save_uph_window_pref(self, n: int):
        try:
            self._uph_settings().setValue('prod/uphWindow', int(n))
        except Exception:
            pass

    def _load_uph_preset_recent(self) -> list:
        """wave25: QSettings 快捷记忆 — 最近用过的 UPH 预设."""
        try:
            raw = str(self._uph_settings().value('prod/uphPresetRecent', '') or '')
        except Exception:
            raw = ''
        out = []
        for part in raw.replace(';', ',').split(','):
            part = part.strip()
            if not part:
                continue
            try:
                v = int(part)
            except ValueError:
                continue
            if v in (8, 16, 24, 32, 48) and v not in out:
                out.append(v)
        return out[:5]

    def _remember_uph_preset(self, n: int):
        """wave25: 把本次窗口值写入预设快捷记忆（最近优先）."""
        try:
            n = int(n)
        except (TypeError, ValueError):
            return
        if n not in (8, 16, 24, 32, 48):
            return
        recent = [x for x in self._load_uph_preset_recent() if x != n]
        recent.insert(0, n)
        recent = recent[:5]
        try:
            self._uph_settings().setValue(
                'prod/uphPresetRecent', ','.join(str(x) for x in recent))
            self._uph_settings().setValue('prod/uphPresetLast', int(n))
        except Exception:
            pass

    def uph_preset_recent(self) -> list:
        """Public snapshot for smoke / HMI."""
        return self._load_uph_preset_recent()

    def restore_uph_preset_recent(self) -> bool:
        """wave26: 一键还原常用 UPH（优先 Last，否则 recent[0]）."""
        n = None
        try:
            last = self._uph_settings().value('prod/uphPresetLast', None)
            if last is not None:
                n = int(last)
        except Exception:
            n = None
        if n not in (8, 16, 24, 32, 48):
            recent = self._load_uph_preset_recent()
            n = recent[0] if recent else None
        if n not in (8, 16, 24, 32, 48):
            try:
                self.append_log('UPH 常用还原 · 无记忆')
            except Exception:
                pass
            return False
        self.set_uph_window(int(n))
        try:
            self.append_log(f'UPH 常用还原 · {n}')
        except Exception:
            pass
        return True

    def _on_uph_window_changed(self, value: int):
        self.set_uph_window(value)



class OperatorHmiView(QWidget):
    """Operator surface shown in 运行模式; driven by document.project['runUi']."""

    triggerCommands = Signal(object)  # list[dict]
    designRequested = Signal()
    backToDesign = Signal()
    runUiChanged = Signal(object)  # dict patch, e.g. {'fixedBars': {...}}
    pauseToggled = Signal(bool)  # bridge 生产统计 暂停计数 ↔ ContinuousRun / 运行全部
    filmLocateRequested = Signal(object)  # 细妆⑳：结果表行 → 胶片定位 {path,index,seq}
    filmCompareRequested = Signal(object)  # wave21: dblclick → compare overlay
    filmStampRequest = Signal(object)  # wave21: missing path → manual stamp

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('runModePane')
        self._image_views = []  # ImageView instances to mirror results into
        self._status_lamps = []
        self._device_chrome_labels = []  # StatusLamp needing runtime OK/NG
        self._run_status_labels = []
        self._log_panes = []
        self._clock_labels = []
        self._stats_panels = []
        self._trend_sparks = []  # QLabel live elapsed spark
        self._trend_ok_sparks = []  # QLabel OK/NG sequence
        self._yield_bars = []  # (bar_ok, bar_ng) tuples
        self._result_history=[]; self._result_tables = []; self._gate_hist=[]; self._gate_spark_labs=[]; self._gate_filter_mode='all'  # all|pass|fail
        self._recipe_filter_labs = []; self._recipe_filter_active = False
        self._last_module_name = '流程'  # 结果表「模块」列跟末次步骤名
        self._pending_film_stamp = {}  # 细妆⑳：{path,index} stamped into next history row
        self._pending_trial_backfill = False  # 细妆⑳：试跑完成后回填判定/配方徽章
        self._alarm_was_on = False  # 细妆⑳：Alarm→恢复动画边沿
        self._trial_fail_alarm = False  # wave21: trial-fail Alarm → clear restore
        self._trend_uph_sparks = []  # wave21 UPH trend labs
        self._film_row_wired = False
        self._layout_fp = None
        self._clock_timer = QTimer(self)
        self._clock_timer.setInterval(1000)
        self._clock_timer.timeout.connect(self._tick_clocks)

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        # Header chrome
        header = QHBoxLayout()
        title = QLabel('运行模式 · 操作员界面')
        title.setObjectName('dialogTitle')
        header.addWidget(title)
        self._recipe_badge = QLabel('配方 · —')
        self._recipe_badge.setObjectName('hmiRecipeBadge')
        self._recipe_badge.setStyleSheet(
            f'background:{CARD};color:{TEXT_MUTED};border:1px solid {LINE};'
            f'border-radius:3px;padding:3px 8px;font-size:11px;font-weight:600;'
        )
        self._recipe_badge.setToolTip('当前产线配方 / 产品变体。点击：结果表按本配方筛选开/关')
        self._recipe_badge.setCursor(Qt.CursorShape.PointingHandCursor)
        self._recipe_badge.mousePressEvent = lambda e: self._toggle_recipe_filter()
        self._recipe_filter_active = False
        header.addWidget(self._recipe_badge)
        # wave23: 换型失败码 HMI 徽章
        self._fail_code_badge = QLabel('')
        self._fail_code_badge.setObjectName('hmiFailCodeBadge')
        self._fail_code_badge.setStyleSheet(
            'background:#3a1c1c;color:#ffb4b4;border:1px solid #e35d6a;'
            'border-radius:3px;padding:3px 8px;font-size:11px;font-weight:700;'
        )
        self._fail_code_badge.setToolTip(
            '换型失败码（VARIANT_/APPLY_/ENTER_/TRIAL_）· 单击跳报警历史 · 右键清除'
        )
        self._fail_code_badge.setCursor(Qt.CursorShape.PointingHandCursor)
        self._fail_code_badge.mousePressEvent = lambda e: self._on_fail_code_badge_click(e)
        self._fail_code_badge.hide()
        header.addWidget(self._fail_code_badge)
        header.addStretch(1)
        self._state_badge = QLabel('空闲')
        self._state_badge.setObjectName('modeBadge')
        self._state_badge.setProperty('runMode', 'true')
        header.addWidget(self._state_badge)
        self._host_state = 'Idle'
        b = QPushButton('运行界面设计')
        b.clicked.connect(self.designRequested.emit)
        header.addWidget(b)
        b = QPushButton('返回设计态')
        b.setObjectName('primaryButton')
        b.clicked.connect(self.backToDesign.emit)
        header.addWidget(b)
        root.addLayout(header)

        # Visible Idle/Run/Pause/Alarm/Stop chrome (p41–43)
        self._state_rail = QWidget()
        self._state_rail.setObjectName('hostStateRail')
        rail = QHBoxLayout(self._state_rail)
        rail.setContentsMargins(0, 0, 0, 2)
        rail.setSpacing(4)
        self._state_rail_labels = {}
        try:
            from desktop.host_state_machine import STATES, STATE_ZH
        except Exception:
            STATES = ('Idle', 'Running', 'Paused', 'Alarm', 'Stopped')
            STATE_ZH = {s: s for s in STATES}
        for st in STATES:
            lab = QLabel(STATE_ZH.get(st, st))
            lab.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lab.setMinimumWidth(52)
            lab.setProperty('hostState', st)
            self._state_rail_labels[st] = lab
            rail.addWidget(lab)
        rail.addStretch(1)
        # Alarm rail click → 状态·清除报警 (via eventFilter)
        alarm_lab = self._state_rail_labels.get('Alarm')
        if alarm_lab is not None:
            alarm_lab.installEventFilter(self)
            alarm_lab.setObjectName('hostAlarmRail')
        root.addWidget(self._state_rail)
        self._paint_machine_chrome('Idle')

        # Page-level production chrome banner (recipe/status binding; not prop chips)
        self._page_chrome_banner = QLabel('页铬 · 配方 — · 状态 — · 未绑定生产任务')
        self._page_chrome_banner.setObjectName('hmiPageChromeBanner')
        self._page_chrome_banner.setWordWrap(True)
        self._page_chrome_banner.setStyleSheet(
            'background:#1a2430;color:#9ec9f0;border:1px solid #3a5a7a;'
            'border-radius:3px;padding:6px 10px;font-size:12px;font-weight:700;'
        )
        self._page_chrome_banner.setToolTip(
            '生产任务 ↔ 操作员页级铬：配方/状态/statusVar 一次绑定到页眉·状态轨·固定栏'
        )
        root.addWidget(self._page_chrome_banner)

        # Page-level trial→result strip (co-update with OK-NG dashboard; not chips)
        self._trial_result_strip = QLabel('试跑→结果 · 待命')
        self._trial_result_strip.setObjectName('hmiTrialResultStrip')
        self._trial_result_strip.setWordWrap(True)
        self._trial_result_strip.setStyleSheet(
            f'background:{CARD};color:{TEXT_MUTED};border:1px solid {LINE};'
            f'border-radius:3px;padding:5px 10px;font-size:11px;font-weight:600;'
        )
        self._trial_result_strip.setToolTip(
            'production_task ▶试跑 → 页铬 + OK-NG 看板联更（trial→result）'
        )
        root.addWidget(self._trial_result_strip)
        self._page_chrome_locked = False
        self._page_chrome_lock_recipe = ''

        self._hint = QLabel('')
        self._hint.setObjectName('dialogHint')
        self._hint.setWordWrap(True)
        root.addWidget(self._hint)

        # Fixed bars + grid host
        self._fix_top = QLabel('')
        self._fix_top.setObjectName('runFixedBar')
        self._fix_top.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._fix_top.hide()
        root.addWidget(self._fix_top)

        mid = QHBoxLayout()
        mid.setSpacing(4)
        self._fix_left = QLabel('')
        self._fix_left.setObjectName('runFixedBarSide')
        self._fix_left.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._fix_left.setFixedWidth(28)
        self._fix_left.hide()
        mid.addWidget(self._fix_left)

        self._grid_host = QWidget()
        self._grid_host.setObjectName('operatorGridHost')
        self._grid_layout = QGridLayout(self._grid_host)
        self._grid_layout.setContentsMargins(0, 0, 0, 0)
        self._grid_layout.setSpacing(6)
        mid.addWidget(self._grid_host, 1)

        self._fix_right = QLabel('')
        self._fix_right.setObjectName('runFixedBarSide')
        self._fix_right.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._fix_right.setFixedWidth(28)
        self._fix_right.hide()
        mid.addWidget(self._fix_right)
        root.addLayout(mid, 1)

        self._fix_bottom = QLabel('')
        self._fix_bottom.setObjectName('runFixedBar')
        self._fix_bottom.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._fix_bottom.hide()
        root.addWidget(self._fix_bottom)

        # Alarm / OK-NG dashboard soft strip (page-level; not micro chips)
        self._okng_dashboard_strip = QLabel(
            '看板 · OK —  NG —  良率 —  ·  判定 —  ·  报警开 —  ·  状态 空闲'
        )
        self._okng_dashboard_strip.setObjectName('hmiOkNgDashboardStrip')
        self._okng_dashboard_strip.setWordWrap(True)
        self._okng_dashboard_strip.setStyleSheet(
            f'background:{CARD};color:{TEXT_MUTED};border:1px solid {LINE};'
            f'border-radius:3px;padding:6px 10px;font-size:12px;font-weight:700;'
        )
        self._okng_dashboard_strip.setToolTip(
            'Alarm/OK-NG 看板软条：累计 OK/NG/良率 + 末次判定 + 未清报警 + 上位机状态'
        )
        root.addWidget(self._okng_dashboard_strip)

        # Always-available default run strip (also used when layout has no 运行控制)
        self._default_strip = QWidget()
        self._default_strip.setObjectName('hmiDefaultStrip')
        strip = QHBoxLayout(self._default_strip)
        strip.setContentsMargins(2, 2, 2, 2)
        strip.setSpacing(4)
        self._strip_recipe_lab = QLabel('配方 —')
        self._strip_recipe_lab.setObjectName('hmiStripRecipe')
        self._strip_recipe_lab.setStyleSheet(
            f'color:{TEXT_MUTED};font-size:11px;padding:0 6px;font-weight:600;'
        )
        strip.addWidget(self._strip_recipe_lab)
        def _sep():
            s = QFrame()
            s.setFrameShape(QFrame.Shape.VLine)
            s.setStyleSheet(f'color:{LINE};')
            s.setFixedWidth(2)
            strip.addWidget(s)
        _sep()
        self._strip_btns = {}
        groups = [
            (
                ('once', '▶ 单次', DEFAULT_RUN_COMMANDS, True),
                ('cont', '↻ 连续', DEFAULT_CONT_COMMANDS, False),
                ('pause', '⏸ 暂停', DEFAULT_PAUSE_COMMANDS, False),
                ('resume', '▶ 继续', DEFAULT_RESUME_COMMANDS, False),
                ('stop', '■ 停止', DEFAULT_STOP_COMMANDS, False),
            ),
            (
                ('clear', '清除报警', DEFAULT_CLEAR_ALARM_COMMANDS, False),
            ),
            (
                ('inj_run', '注入 RUN', DEFAULT_INJECT_RUN_COMMANDS, False),
                ('inj_stop', '注入 STOP', DEFAULT_INJECT_STOP_COMMANDS, False),
            ),
        ]
        for gi, group in enumerate(groups):
            if gi:
                _sep()
            for key, label, cmds, primary in group:
                btn = QPushButton(label)
                if primary:
                    btn.setObjectName('primaryButton')
                if key == 'clear':
                    btn.setObjectName('hmiClearAlarmBtn')
                    btn.setToolTip('清除上位机报警 → 空闲（状态·清除报警）')
                btn.clicked.connect(lambda _=False, c=cmds: self.triggerCommands.emit(deepcopy(c)))
                strip.addWidget(btn)
                self._strip_btns[key] = btn
        strip.addStretch(1)
        root.addWidget(self._default_strip)
        self._sync_strip_buttons('Idle')

        self.reload_layout({})

    # ----- public API -----
    def reload_layout(self, project: dict | None):
        """Rebuild cells from project['runUi']. Safe to call repeatedly."""
        project = project or {}
        ui = project.get('runUi') or {}
        fp = (
            ui.get('split'),
            tuple(
                (p.get('name'), p.get('page'), p.get('cell'), p.get('category'))
                for p in (ui.get('placements') or [])
            ),
            tuple(sorted((ui.get('fixedBars') or {}).items())),
            tuple(
                (
                    name,
                    tuple(
                        (c.get('type'), c.get('config'))
                        for c in (st.get('commands') or [])
                    ),
                    st.get('binding'),
                )
                for name, st in sorted((ui.get('controls') or {}).items())
            ),
        )
        if fp == self._layout_fp and self._grid_layout.count():
            # Still refresh fixed-bar text (bindings may change without placement change)
                        # 细妆⑱：从工程刷配方徽章
            try:
                from desktop import recipe_library as _rl
                self.set_recipe_chrome(
                    _rl.active_recipe_name(project) or '',
                    str(project.get('activeRecipeVariant') or ''),
                )
            except Exception:
                pass
            self._apply_fixed_bars(ui.get('fixedBars') or {})
            return
        self._layout_fp = fp
        self._clear_grid()
        self._image_views = []
        self._status_lamps = []
        self._run_status_labels = []
        self._log_panes = []
        self._clock_labels = []
        self._stats_panels = []
        self._trend_sparks = []
        self._trend_ok_sparks = []
        self._trend_uph_sparks = []
        self._yield_bars = []
        self._result_tables = []
        self._gate_spark_labs = []
        # keep _gate_hist across rebuild so spark survives layout refresh
        self._gate_hist = getattr(self, '_gate_hist', []) or []
        self._host_sm = None

        placements = list(ui.get('placements') or [])
        controls = ui.get('controls') or {}
        split = ui.get('split') or '1'
        # Designer stores page index matching SPLIT_PRESETS; only current split page is active
        page_idx = SPLIT_PRESETS.index(split) if split in SPLIT_PRESETS else 0
        active = [p for p in placements if int(p.get('page') or 0) == page_idx]
        has_run_control = any(p.get('name') in ('运行控制',) for p in active)

        if not active:
            self._hint.setText(
                '尚未配置运行界面布局 — 显示默认操作员壳（单次/连续/停止 + 图像）。'
                '打开「运行界面设计」可放置控件。'
            )
            self._build_default_grid()
            self._default_strip.setVisible(True)
        else:
            self._hint.setText(
                f'布局分割 · {split} · {len(active)} 个控件'
                + (' · 画布已锁定' if True else '')
            )
            self._build_from_placements(split, active, controls)
            self._default_strip.setVisible(not has_run_control)

        self._apply_fixed_bars(ui.get('fixedBars') or {})
        if self._clock_labels:
            self._clock_timer.start()
            self._tick_clocks()
        else:
            self._clock_timer.stop()

    def set_pause_owner_badge(self, mode):
        """Propagate filmstrip pause-owner mode tip to 生产统计 panels + header badge."""
        mode = mode if mode in ('continuous', 'run_all') else None
        for panel in getattr(self, '_stats_panels', None) or []:
            try:
                if hasattr(panel, 'set_pause_owner_badge'):
                    panel.set_pause_owner_badge(mode)
            except Exception:
                pass
        # Header state badge soft-hint when idle-ish
        try:
            if hasattr(self, '_state_badge') and mode and self._state_badge.text() in (
                '空闲', '完成', '已停止',
            ):
                hint = '连续运行' if mode == 'continuous' else '运行全部'
                self._state_badge.setToolTip(f'暂停控件归属：{hint}（与胶片条共用）')
            elif hasattr(self, '_state_badge'):
                if not mode:
                    self._state_badge.setToolTip('')
        except Exception:
            pass

    def set_runtime(self, result: dict | None, image=None, annotated=None):
        """Push last run result / preview into image panes and lamps."""
        result = result or {}
        state = result.get('state')
        if state == 'completed':
            self._state_badge.setText('完成')
            ok = True
        elif state == 'failed':
            self._state_badge.setText('失败')
            ok = False
        elif state == 'cancelled':
            self._state_badge.setText('已停止')
            ok = None
        else:
            self._state_badge.setText('运行中' if state else '空闲')
            ok = None

        for lamp in self._status_lamps:
            lamp.set_state(ok if state in ('completed', 'failed') else None)

        for lab in self._run_status_labels:
            elapsed = result.get('elapsedMs')
            text = {
                'completed': '运行完成',
                'cancelled': '已停止',
                'failed': '运行失败',
            }.get(state, state or '空闲')
            if elapsed is not None:
                text = f'{text} · {elapsed} ms'
            if result.get('error'):
                text = f"{text} · {result['error']}"
            lab.setText(text)

        # Prefer annotated frame; fall back to source image
        frame = annotated
        if not frame and result:
            for record in reversed(result.get('results') or []):
                frame = (record.get('output') or {}).get('annotatedImage')
                if frame:
                    break
        if not frame:
            frame = image or ''
        for view in self._image_views:
            try:
                view.show_data(frame or '')
            except Exception:
                pass

        for log in self._log_panes:
            if state:
                log.appendPlainText(
                    f"[{datetime.now().strftime('%H:%M:%S')}] "
                    f"{state} · {result.get('elapsedMs', '')} ms"
                )

        host = getattr(self, '_host_sm', None)
        if host is not None:
            try:
                keep = bool(getattr(self, '_keep_host_running', False))
                host.sync_from_runtime(result, keep_running=keep)
                self._paint_machine_chrome(getattr(host, 'state', None) or self._host_state)
            except Exception:
                pass
        elif state in ('completed', 'failed', 'cancelled', 'running', 'pending'):
            # No embedded SM — still mirror chrome from engine state
            mapped = {
                'completed': 'Idle',
                'failed': 'Alarm',
                'cancelled': 'Stopped',
                'running': 'Running',
                'pending': 'Running',
            }.get(state)
            if mapped:
                self._paint_machine_chrome(mapped)

        # 结果表「模块」列：跟末次步骤名（非硬编码「流程」）
        try:
            recs = list(result.get('results') or [])
            if recs:
                last = recs[-1]
                nm = last.get('name') or last.get('operation') or last.get('id')
                if not nm:
                    out = (last.get('output') or {})
                    nm = out.get('operation') or out.get('name')
                if nm:
                    self._last_module_name = str(nm)
        except Exception:
            pass

        # Production counters / history / alarm
        if state in ('completed', 'failed'):
            detail = ''
            if state == 'failed':
                detail = str(result.get('error') or 'failed')
            else:
                # Prefer explicit gate variables (panel gateKey / fixedBars.gateKey / auto)
                vars_bag = (result.get('variables') or {})
                flow_vars = vars_bag.get('flow') if isinstance(vars_bag, dict) else {}
                if isinstance(flow_vars, dict):
                    preferred = []
                    for panel in getattr(self, '_stats_panels', []) or []:
                        gk = getattr(panel, 'gate_key', lambda: None)()
                        if gk:
                            preferred.append(gk)
                    fb_gate = (getattr(self, '_fixed_bars_cache', {}) or {}).get('gateKey')
                    if fb_gate:
                        preferred.append(str(fb_gate))
                    auto = ('passGate', 'commOk', 'passed', 'ok', 'ResultOK')
                    seen = set(); keys = []
                    for k in list(preferred) + list(auto):
                        if k and k not in seen:
                            seen.add(k); keys.append(k)
                    for gate_key in keys:
                        if gate_key in flow_vars:
                            val = flow_vars.get(gate_key)
                            truthy = val not in (0, 0.0, False, None, '', '0', 'false', 'False')
                            ok = bool(truthy)
                            detail = f'{gate_key}={val}'
                            self._last_gate_detail = detail
                            self._last_gate_key = gate_key
                            self._last_gate_value = val
                            break
                # Prefer last step status if present
                for record in reversed(result.get('results') or []):
                    out = (record.get('output') or {}).get('result') or {}
                    st = out.get('status')
                    if st and st not in ('ok', 'completed', 'pass'):
                        detail = f"{record.get('name') or record.get('id')}:{st}"
                        ok = False
                        break
                    # Nested group/comm gate
                    if 'commOk' in out and out.get('commOk') in (0, False, '0'):
                        ok = False; detail = 'commOk=0'; break
                    if 'passGate' in out and out.get('passGate') in (0, False, '0'):
                        ok = False; detail = 'passGate=0'
                        self._last_gate_detail = detail
                        self._last_gate_key = 'passGate'
                        self._last_gate_value = out.get('passGate')
                        break
            for panel in getattr(self, '_stats_panels', []) or []:
                try:
                    panel.record(ok if state == 'completed' else False,
                                 elapsed_ms=result.get('elapsedMs'),
                                 detail=detail)
                except Exception:
                    pass
        elif state == 'cancelled':
            for panel in getattr(self, '_stats_panels', []) or []:
                try:
                    panel.set_alarm('已停止')
                except Exception:
                    pass


        try:
            # 细妆：固定栏实况 OK/NG · 计数
            okng = '—'
            counters = None
            for lamp in getattr(self, '_status_lamps', []) or []:
                try:
                    st = getattr(lamp, 'state', None) or getattr(lamp, '_state', None)
                    if st:
                        okng = str(st).upper()
                        break
                except Exception:
                    pass
            for panel in getattr(self, '_stats_panels', []) or []:
                try:
                    ok_n = getattr(panel, 'ok_count', None)
                    ng_n = getattr(panel, 'ng_count', None)
                    if callable(ok_n):
                        ok_n = ok_n()
                    if callable(ng_n):
                        ng_n = ng_n()
                    if ok_n is not None and ng_n is not None:
                        counters = f'OK {ok_n} / NG {ng_n}'
                        break
                except Exception:
                    pass
            self.update_fixed_bar_live(okng=okng, counters=counters)
        except Exception:
            pass
        try:
            if state in ('completed', 'failed'):
                self.update_gate_column_live(result.get('variables') or {})
        except Exception:
            pass

    def apply_display(self, *, fit_mode=None, image=None, channel=None):
        """Live-apply Display fitMode (+ optional pre-channelled image) on HMI panes."""
        fit = fit_mode if fit_mode in ('contain', 'cover', 'actual') else None
        for view in getattr(self, '_image_views', None) or []:
            try:
                if fit and hasattr(view, 'set_fit_mode'):
                    view.set_fit_mode(fit)
                if image:
                    view.show_data(image)
                elif fit and hasattr(view, 'fit') and not getattr(view, 'bounds', None).isEmpty():
                    view.fit()
            except Exception:
                pass

    def set_preview_image(self, data):
        """Live / source preview hook (e.g. after capture, before run)."""
        if not data:
            return
        for view in self._image_views:
            try:
                # Only fill empty panes so we don't clobber annotated results mid-view
                if not getattr(view, 'bounds', None) or view.bounds.isEmpty():
                    view.show_data(data)
            except Exception:
                pass

    def append_log(self, message: str):
        for log in self._log_panes:
            try:
                log.appendPlainText(str(message))
            except Exception:
                pass
        for lv in getattr(self, '_log_views', []) or []:
            try:
                lv.appendPlainText(str(message))
            except Exception:
                pass
        if not getattr(self, '_mirroring_host_info', False):
            host = getattr(self, '_host_sm', None)
            if host is not None:
                try:
                    host.append_info(str(message))
                except Exception:
                    pass

    def eventFilter(self, obj, event):
        """Alarm rail click → 状态·清除报警 when Alarm active."""
        try:
            from PySide6.QtCore import QEvent
            if (obj is (getattr(self, '_state_rail_labels', None) or {}).get('Alarm')
                    and event.type() == QEvent.Type.MouseButtonPress
                    and getattr(self, '_host_state', None) == 'Alarm'):
                self.triggerCommands.emit(deepcopy(DEFAULT_CLEAR_ALARM_COMMANDS))
                return True
        except Exception:
            pass
        return super().eventFilter(obj, event)

    def _sync_strip_buttons(self, state: str):
        """Enable Pause/Resume/Clear on default strip from host state."""
        st = state or 'Idle'
        btns = getattr(self, '_strip_btns', None) or {}
        mapping = {
            'pause': st == 'Running',
            'resume': st == 'Paused',
            'clear': st == 'Alarm',
            'cont': st in ('Idle', 'Stopped'),
            'once': st in ('Idle', 'Stopped', 'Paused'),
            'stop': st in ('Running', 'Paused', 'Alarm'),
        }
        for key, enabled in mapping.items():
            b = btns.get(key)
            if b is None:
                continue
            b.setEnabled(enabled)
            if key == 'clear':
                if st == 'Alarm':
                    b.setStyleSheet(
                        'background:#3a1c1c;color:#e35d6a;border:1px solid #e35d6a;'
                        'border-radius:3px;font-weight:700;'
                    )
                else:
                    b.setStyleSheet('')

    def _wire_host_sm(self, host):
        """Connect HostStateMachineWidget → triggerCommands + chrome mirror."""
        self._host_sm = host
        try:
            host.triggerCommands.connect(self.triggerCommands.emit)
        except Exception:
            pass
        try:
            host.stateChanged.connect(self._on_host_state_changed)
        except Exception:
            pass
        try:
            # Host 信息栏 → HMI「信息提示栏」单向镜像（避免与 append_log 递归）
            host.infoLogged.connect(self._on_host_info_logged)
        except Exception:
            pass
        try:
            # wave23: 联调条 → 固定栏短闪
            host.liaisonPushed.connect(self._on_liaison_pushed)
        except Exception:
            pass
        try:
            # wave26: 报警高亮首条双击 → 胶片定位
            host.alarmFilmLocateRequested.connect(self.filmLocateRequested.emit)
        except Exception:
            pass
        try:
            self._paint_machine_chrome(getattr(host, 'state', None) or 'Idle')
        except Exception:
            pass

    def _on_host_info_logged(self, line: str):
        """Mirror Host SM info bar into HMI 信息提示栏 / 界面日志 panes only."""
        if getattr(self, '_mirroring_host_info', False):
            return
        self._mirroring_host_info = True
        try:
            text = str(line or '')
            for log in getattr(self, '_log_panes', []) or []:
                try:
                    log.appendPlainText(text)
                except Exception:
                    pass
            for lv in getattr(self, '_log_views', []) or []:
                if lv in (getattr(self, '_log_panes', None) or []):
                    continue
                try:
                    lv.appendPlainText(text)
                except Exception:
                    pass
        finally:
            self._mirroring_host_info = False

    def set_host_machine_state(self, state: str, reason: str = ''):
        """MainWindow / triggers push Idle|Running|Paused|Alarm|Stopped."""
        host = getattr(self, '_host_sm', None)
        if host is not None and hasattr(host, 'set_state'):
            try:
                host.set_state(state, reason)
                return
            except Exception:
                pass
        self._paint_machine_chrome(state)

    def set_bound_flow(self, name: str = '', steps: int = 0, path: str = '', reason: str = ''):
        """Proxy → Host SM 信息栏流程绑定芯片（开始绑流程 §6 P0）。"""
        host = getattr(self, '_host_sm', None)
        if host is not None and hasattr(host, 'set_bound_flow'):
            try:
                host.set_bound_flow(name, steps=steps, path=path, reason=reason)
            except Exception:
                pass

    def set_keep_host_running(self, keep: bool):
        """Continuous / run-all active → cycle completes stay Running on SM."""
        self._keep_host_running = bool(keep)

    def _on_host_state_changed(self, state: str):
        self._paint_machine_chrome(state)

    def _paint_machine_chrome(self, state: str):
        """Header badge + Idle/Run/Pause/Alarm/Stop rail + 运行状态 labels."""
        try:
            from desktop.host_state_machine import STATE_ZH, STATE_COLOR, STATES
        except Exception:
            STATE_ZH = {
                'Idle': '空闲', 'Running': '运行中', 'Paused': '已暂停',
                'Alarm': '报警', 'Stopped': '已停止',
            }
            STATE_COLOR = {
                'Idle': ('#2a3340', '#8a9bb0'),
                'Running': ('#1c3a2a', '#3ecf8e'),
                'Paused': ('#3a3420', '#e0b84a'),
                'Alarm': ('#3a1c1c', '#e35d6a'),
                'Stopped': ('#2a3340', '#8a9bb0'),
            }
            STATES = tuple(STATE_ZH.keys())
        st = state if state in STATE_ZH else (state or 'Idle')
        if st not in STATE_ZH:
            st = 'Idle'
        self._host_state = st
        zh = STATE_ZH[st]
        bg, fg = STATE_COLOR.get(st, STATE_COLOR['Idle'])
        badge = getattr(self, '_state_badge', None)
        if badge is not None:
            badge.setText(zh)
            badge.setStyleSheet(
                f'background:{bg};color:{fg};border:1px solid {fg};'
                f'border-radius:3px;padding:3px 10px;font-weight:700;font-size:12px;'
            )
            badge.setToolTip(f'上位机状态：{zh} ({st})')
        for key, lab in (getattr(self, '_state_rail_labels', None) or {}).items():
            active = key == st
            abg, afg = STATE_COLOR.get(key, STATE_COLOR['Idle'])
            if active:
                lab.setStyleSheet(
                    f'background:{abg};color:{afg};border:1px solid {afg};'
                    f'border-radius:3px;padding:3px 6px;font-weight:700;font-size:11px;'
                )
            else:
                lab.setStyleSheet(
                    'background:transparent;color:#5a6a7a;border:1px solid #2a3340;'
                    'border-radius:3px;padding:3px 6px;font-size:11px;'
                )
            # Alarm cell: click to clear when active
            if key == 'Alarm':
                lab.setCursor(Qt.CursorShape.PointingHandCursor if st == 'Alarm'
                              else Qt.CursorShape.ArrowCursor)
                lab.setToolTip('点击清除报警' if st == 'Alarm' else '报警')
        self._sync_strip_buttons(st)
        for lab in getattr(self, '_run_status_labels', None) or []:
            try:
                lab.setText(zh)
                lab.setStyleSheet(
                    f'color:{fg};font-size:13px;font-weight:600;padding:8px;'
                    f'background:{bg};border-radius:3px;'
                )
            except Exception:
                pass
        # 细妆⑰：生产统计面板镜像上位机状态 + Host SM 生产条
        ok_n = ng_n = None
        for panel in getattr(self, '_stats_panels', None) or []:
            try:
                if hasattr(panel, 'set_host_state_mirror'):
                    panel.set_host_state_mirror(st, zh)
                if ok_n is None and hasattr(panel, 'ok_count'):
                    ok_n = panel.ok_count()
                    ng_n = panel.ng_count()
            except Exception:
                pass
        host = getattr(self, '_host_sm', None)
        if host is not None and hasattr(host, 'set_production_snapshot'):
            try:
                host.set_production_snapshot(ok_n, ng_n, host_state=st)
            except Exception:
                pass
        # 细妆⑲：Host SM Alarm ↔ 固定栏色联动（代码级 polish，非人工签字）
        # 细妆⑳：Alarm 清除 → 固定栏恢复动画 / 短提示
        try:
            was = bool(getattr(self, '_alarm_was_on', False))
            now_alarm = (st == 'Alarm')
            self._live_host_alarm = now_alarm
            if now_alarm:
                self._live_run_status = zh  # 报警
            self._apply_fixed_bars(getattr(self, '_fixed_bars_cache', None) or {})
            if was and not now_alarm:
                self._pulse_alarm_cleared(st, zh)
            self._alarm_was_on = now_alarm
        except Exception:
            pass

    def push_production_snapshot(self):
        """Call after stats.record so Host SM strip tracks OK/NG live."""
        ok_n = ng_n = None
        for panel in getattr(self, '_stats_panels', None) or []:
            try:
                ok_n = panel.ok_count()
                ng_n = panel.ng_count()
                break
            except Exception:
                pass
        host = getattr(self, '_host_sm', None)
        if host is not None and hasattr(host, 'set_production_snapshot'):
            try:
                host.set_production_snapshot(ok_n, ng_n, host_state=getattr(self, '_host_state', None))
            except Exception:
                pass
        # Deepen Alarm/OK-NG dashboard soft strip
        try:
            self.refresh_okng_dashboard_strip(
                ok_n=ok_n, ng_n=ng_n,
                host_state=getattr(self, '_host_state', None),
            )
        except Exception:
            pass

    # ----- internals -----
    def _clear_grid(self):
        while self._grid_layout.count():
            item = self._grid_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()


    def _wire_stats_panel(self, panel: ProductionStatsPanel):
        """Connect 「判定门」 picks → persist into runUi.fixedBars.gateKey;
        re-emit pauseToggled so MainWindow can bridge ContinuousRun / 运行全部;
        feed HMI trend spark / 饼图 from elapsed + OK/NG history."""
        try:
            panel.gateKeyChanged.connect(self._on_stats_gate_key)
        except Exception:
            pass
        try:
            panel.pauseToggled.connect(self.pauseToggled.emit)
        except Exception:
            pass
        try:
            panel.add_trend_listener(lambda _p: self._refresh_trend_charts())
        except Exception:
            pass
        # initial paint if history already present
        try:
            self._refresh_trend_charts()
        except Exception:
            pass

    def _refresh_trend_charts(self):
        """Push ProductionStatsPanel elapsed/OK history into spark + yield bars."""
        try:
            self.push_production_snapshot()
        except Exception:
            pass
        panel = None
        for p in getattr(self, '_stats_panels', []) or []:
            panel = p
            break
        # elapsed spark
        for lab in getattr(self, '_trend_sparks', []) or []:
            try:
                if panel is None:
                    lab.setText(ProductionStatsPanel.sparkline([]))
                else:
                    lab.setText(panel.trend_elapsed_text())
            except Exception:
                pass
        for lab in getattr(self, '_trend_ok_sparks', []) or []:
            try:
                if panel is None:
                    lab.setText('· · ·  ·  判定序列等待')
                else:
                    lab.setText(panel.trend_ok_text())
            except Exception:
                pass
        for lab in getattr(self, '_trend_uph_sparks', []) or []:
            try:
                if panel is None or not hasattr(panel, 'trend_uph_text'):
                    lab.setText('UPH趋势 · · ·  ·  等待')
                else:
                    lab.setText(panel.trend_uph_text())
            except Exception:
                pass
        total = 0
        ok_n = 0
        ng_n = 0
        if panel is not None:
            try:
                ok_n = int(panel.ok_count())
                ng_n = int(panel.ng_count())
                total = ok_n + ng_n
            except Exception:
                pass
        for pair in getattr(self, '_yield_bars', []) or []:
            try:
                bar_ok, bar_ng = pair
                if total <= 0:
                    bar_ok.setValue(0); bar_ng.setValue(0)
                    bar_ok.setFormat('OK —'); bar_ng.setFormat('NG —')
                else:
                    yp = int(round(100.0 * ok_n / total))
                    np_ = 100 - yp
                    bar_ok.setValue(yp); bar_ng.setValue(np_)
                    bar_ok.setFormat(f'OK {yp}% ({ok_n})')
                    bar_ng.setFormat(f'NG {np_}% ({ng_n})')
            except Exception:
                pass
        # 结果表格：模块/耗时/OK/NG
        last_ms = '—'
        if panel is not None:
            try:
                hist = panel.elapsed_history()
                if hist:
                    last_ms = f'{hist[0]:.0f}'
            except Exception:
                pass
        mod_name = getattr(self, '_last_module_name', None) or '流程'
        # 判定列：跟末次 OK/NG 灯（有统计时）
        judge = '—'
        if ok_n or ng_n:
            # 末次：若最近一次 ok_hist 有值
            try:
                if panel is not None:
                    oh = panel.ok_history()
                    if oh:
                        judge = 'OK' if oh[0] else 'NG'
            except Exception:
                pass
        # 细妆⑬：追加一行历史（时间/序号/模块/耗时/判定/OK/NG/门限/备注）
        try:
            gate = ''
            # Prefer live passGate=/gateKey= value from last completed run
            live = getattr(self, '_last_gate_detail', None)
            if live:
                gate = str(live)
            else:
                fb = getattr(self, '_fixed_bars_cache', None) or {}
                if isinstance(fb, dict) and fb.get('gateKey'):
                    gate = str(fb.get('gateKey'))
                gk = getattr(self, '_last_gate_key', None)
                gv = getattr(self, '_last_gate_value', None)
                if gk is not None and gv is not None:
                    gate = f'{gk}={gv}'
            note = ''
            hist = getattr(self, '_result_history', None)
            if hist is None:
                self._result_history = []
                hist = self._result_history
            # Only append when we have a real run signal (elapsed or judge)
            if last_ms != '—' or judge in ('OK', 'NG'):
                entry = {
                    'ts': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'seq': len(hist) + 1,
                    'module': str(mod_name),
                    'elapsedMs': str(last_ms),
                    'judge': judge if judge != '—' else '—',
                    'ok': str(ok_n),
                    'ng': str(ng_n),
                    'gate': gate or '—',
                    'note': note or '—',
                    # 细妆⑯：供门限 spark 筛选（通/拒窗口）
                    'gatePass': (
                        True if str(judge or '').upper() in ('OK', 'PASS', '通')
                        else False if str(judge or '').upper() in ('NG', 'FAIL', '拒')
                        else None
                    ),
                    # 细妆⑲：配方徽章联动
                    'recipe': getattr(self, '_live_recipe', '') or '',
                    'variant': getattr(self, '_live_variant', '') or '',
                }
                # 细妆⑳：胶片路径/序号 stamp（结果表行点击定位）
                stamp = getattr(self, '_pending_film_stamp', None) or {}
                if stamp.get('path'):
                    entry['filmPath'] = str(stamp.get('path') or '')
                if stamp.get('index') is not None:
                    try:
                        entry['filmIndex'] = int(stamp.get('index'))
                    except Exception:
                        pass
                # de-dupe identical consecutive (same module+elapsed+judge within same second)
                if not hist or (hist[-1].get('module'), hist[-1].get('elapsedMs'), hist[-1].get('judge'), hist[-1].get('ts')) != (
                    entry['module'], entry['elapsedMs'], entry['judge'], entry['ts']):
                    hist.append(entry)
                    if len(hist) > 200:
                        del hist[:-200]
            self._refresh_result_tables_ui()
        except Exception:
            pass

    def _on_stats_gate_key(self, key):
        fb = dict(getattr(self, '_fixed_bars_cache', {}) or {})
        key = (key or '').strip() if key else ''
        if key:
            fb['gateKey'] = key
        else:
            fb.pop('gateKey', None)
        self._fixed_bars_cache = fb
        # Keep tip labels in sync
        try:
            self._apply_fixed_bars(fb)
        except Exception:
            pass
        try:
            self.runUiChanged.emit({'fixedBars': dict(fb)})
        except Exception:
            pass

    def result_history(self):
        """Public snapshot for smoke / CSV."""
        return list(getattr(self, '_result_history', []) or [])

    def result_history_csv(self) -> str:
        lines = ['timestamp,seq,module,elapsed_ms,judge,ok,ng,gate,note,recipe,variant']
        for e in self.result_history():
            ts = str(e.get('ts') or '').replace(',', ' ')
            mod = str(e.get('module') or '').replace('"', "'")
            note = str(e.get('note') or '').replace('"', "'").replace('\n', ' ')
            gate = str(e.get('gate') or '').replace('"', "'")
            recipe = str(e.get('recipe') or '').replace('"', "'")
            variant = str(e.get('variant') or '').replace('"', "'")
            lines.append(
                f'{ts},{e.get("seq","")},{mod},{e.get("elapsedMs","")},{e.get("judge","")},'
                f'{e.get("ok","")},{e.get("ng","")},"{gate}","{note}","{recipe}","{variant}"'
            )
        return '\n'.join(lines) + ('\n' if lines else '')

    def export_result_table_clipboard(self):
        try:
            QApplication.clipboard().setText(self.result_history_csv())
        except Exception:
            pass

    def export_result_table_file(self):
        path, _ = QFileDialog.getSaveFileName(
            self, '导出结果表', 'hmi-result-table.csv', 'CSV (*.csv);;All (*)')
        if not path:
            return
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(self.result_history_csv())
        except Exception:
            pass


    def update_gate_column_live(self, variables=None):
        """Refresh 门限 column on newest history row from live flow.passGate (or gateKey)."""
        try:
            vars_bag = variables or {}
            flow = vars_bag.get('flow') if isinstance(vars_bag, dict) else {}
            if not isinstance(flow, dict):
                flow = {}
            preferred = []
            fb = getattr(self, '_fixed_bars_cache', None) or {}
            if isinstance(fb, dict) and fb.get('gateKey'):
                preferred.append(str(fb.get('gateKey')))
            preferred.extend(['passGate', 'commOk', 'passed', 'ok', 'ResultOK'])
            detail = None
            truthy = None
            for k in preferred:
                if k in flow:
                    val = flow.get(k)
                    detail = f'{k}={val}'
                    self._last_gate_detail = detail
                    self._last_gate_key = k
                    self._last_gate_value = val
                    truthy = val not in (0, 0.0, False, None, '', '0', 'false', 'False')
                    break
            if detail:
                # 细妆⑮：passGate sequence hist for 门限 spark
                gh = getattr(self, '_gate_hist', None)
                if gh is None:
                    self._gate_hist = []
                    gh = self._gate_hist
                if truthy is not None:
                    gh.insert(0, bool(truthy))
                    del gh[48:]
                hist = getattr(self, '_result_history', None)
                if hist:
                    hist[-1]['gate'] = detail
                    # also stamp gatePass for spark consumers
                    hist[-1]['gatePass'] = bool(truthy) if truthy is not None else None
                self._refresh_gate_spark()
            self._refresh_result_tables_ui()
        except Exception:
            pass

    def gate_hist(self):
        return list(getattr(self, '_gate_hist', []) or [])

    def gate_spark_text(self, width=24):
        """Unicode spark of recent passGate truthiness (high=pass)."""
        gh = getattr(self, '_gate_hist', None) or []
        if not gh:
            return '· · ·  ·  门限序列等待'
        seq = list(reversed(gh[:width]))
        s = ''.join('▇' if v else '▁' for v in seq)
        passed = sum(1 for v in gh if v)
        return f'{s}  ·  门限 {passed}/{len(gh)} 通 (高=通)'


    def _make_gate_spark_click_handler(self, lab):
        def _handler(event):
            try:
                self._cycle_gate_filter()
            except Exception:
                pass
            # still accept
            try:
                QLabel.mousePressEvent(lab, event)
            except Exception:
                pass
        return _handler

    def _cycle_gate_filter(self):
        """细妆⑯：门限 spark 点击 → 结果表按通/拒窗口筛选."""
        order = ['all', 'pass', 'fail']
        cur = getattr(self, '_gate_filter_mode', 'all') or 'all'
        try:
            nxt = order[(order.index(cur) + 1) % len(order)]
        except ValueError:
            nxt = 'all'
        self._gate_filter_mode = nxt
        self._refresh_gate_spark()
        self._refresh_result_tables_ui()

    def _refresh_gate_spark(self):
        text = self.gate_spark_text()
        mode = getattr(self, '_gate_filter_mode', 'all') or 'all'
        mode_lab = {'all': '全部', 'pass': '仅通', 'fail': '仅拒'}.get(mode, mode)
        for lab in getattr(self, '_gate_spark_labs', []) or []:
            try:
                lab.setText(f'门限序列  {text}  ·  筛选:{mode_lab}')
                lab.setToolTip(
                    f'点击切换筛选（当前={mode_lab}）：全部 → 仅通 → 仅拒\n'
                    '最近 passGate / 判定门 真值序列（高=通 · 低=拒）'
                )
                color = {'all': TEXT_MUTED, 'pass': '#3ecf8e', 'fail': '#e35d6a'}.get(mode, TEXT_MUTED)
                lab.setStyleSheet(f'color:{color};font-size:11px;font-family:monospace;padding:2px 4px;')
            except Exception:
                pass

    def clear_result_history(self):
        self._result_history = []
        self._gate_hist = []
        self._refresh_gate_spark()
        self._refresh_result_tables_ui()

    def _refresh_result_tables_ui(self):
        hist = list(getattr(self, '_result_history', []) or [])
        live_recipe = (getattr(self, '_live_recipe', '') or '').strip()
        recipe_on = bool(getattr(self, '_recipe_filter_active', False)) and live_recipe and live_recipe != '—'
        for table in getattr(self, '_result_tables', []) or []:
            try:
                # 细妆⑲：ensure 配方 column exists
                if table.columnCount() < 10:
                    table.setColumnCount(10)
                    table.setHorizontalHeaderLabels(
                        ['时间', '序号', '模块', '耗时(ms)', '判定', 'OK累计', 'NG累计', '门限', '备注', '配方']
                    )
                table.setRowCount(0)
                if not hist:
                    table.setRowCount(1)
                    placeholders = ['—', '0', '等待运行', '—', '—', '0', '0', '—', '—', '—']
                    for c, val in enumerate(placeholders):
                        table.setItem(0, c, QTableWidgetItem(val))
                    continue
                # show newest first; 细妆⑯：gate filter window; 细妆⑲：配方筛选
                rows = list(reversed(hist[-50:]))
                mode = getattr(self, '_gate_filter_mode', 'all') or 'all'
                if mode == 'pass':
                    rows = [e for e in rows if e.get('gatePass') is True
                            or str(e.get('judge') or '').upper() in ('OK', 'PASS', '通')]
                elif mode == 'fail':
                    rows = [e for e in rows if e.get('gatePass') is False
                            or str(e.get('judge') or '').upper() in ('NG', 'FAIL', '拒')]
                if recipe_on:
                    rows = [e for e in rows if (e.get('recipe') or '').strip() == live_recipe]
                if not rows:
                    table.setRowCount(1)
                    tip = {'all': '无记录', 'pass': '无通窗口', 'fail': '无拒窗口'}.get(mode, '无记录')
                    if recipe_on:
                        tip = f'无配方「{live_recipe}」记录'
                    placeholders = ['—', '0', tip, '—', '—', '0', '0', '—', '—', live_recipe or '—']
                    for c, val in enumerate(placeholders):
                        table.setItem(0, c, QTableWidgetItem(val))
                    continue
                table.setRowCount(len(rows))
                for r, e in enumerate(rows):
                    recipe_txt = str(e.get('recipe') or '') or '—'
                    if e.get('variant'):
                        recipe_txt = f"{recipe_txt}/{e.get('variant')}"
                    vals = [
                        str(e.get('ts') or ''),
                        str(e.get('seq') or ''),
                        str(e.get('module') or ''),
                        str(e.get('elapsedMs') or ''),
                        str(e.get('judge') or ''),
                        str(e.get('ok') or ''),
                        str(e.get('ng') or ''),
                        str(e.get('gate') or ''),
                        str(e.get('note') or ''),
                        recipe_txt,
                    ]
                    for c, val in enumerate(vals):
                        it = QTableWidgetItem(val)
                        if c == 0:
                            # 细妆⑳：行元数据供点击定位胶片 / 反查高亮
                            it.setData(Qt.ItemDataRole.UserRole, {
                                'filmPath': e.get('filmPath') or '',
                                'filmIndex': e.get('filmIndex'),
                                'seq': e.get('seq'),
                            })
                            tip_bits = []
                            if e.get('filmPath'):
                                tip_bits.append(f"胶片 {Path(str(e.get('filmPath'))).name}")
                            elif e.get('filmIndex') is not None:
                                tip_bits.append(f"胶片#{e.get('filmIndex')}")
                            if tip_bits:
                                it.setToolTip(
                                    '单击定位 · 双击对比叠层 · ' + ' · '.join(tip_bits)
                                )
                            else:
                                it.setToolTip('缺胶片 path · 双击也可试对比 · 或点「补 stamp」')
                        table.setItem(r, c, it)
            except Exception:
                pass
        self._refresh_recipe_filter_labs()

    def _toggle_recipe_filter(self):
        """细妆⑲：配方徽章 / 配方筛选标签 → 结果表按当前配方开/关."""
        live = (getattr(self, '_live_recipe', '') or '').strip()
        if not live or live == '—':
            self._recipe_filter_active = False
        else:
            self._recipe_filter_active = not bool(getattr(self, '_recipe_filter_active', False))
        self._refresh_recipe_filter_labs()
        self._refresh_result_tables_ui()
        # also nudge filmstrip caption if present
        try:
            self._sync_filmstrip_recipe_hint()
        except Exception:
            pass

    def _refresh_recipe_filter_labs(self):
        on = bool(getattr(self, '_recipe_filter_active', False))
        live = (getattr(self, '_live_recipe', '') or '').strip() or '—'
        for lab in getattr(self, '_recipe_filter_labs', []) or []:
            try:
                if on:
                    lab.setText(f'配方筛选 · {live}')
                    lab.setStyleSheet(
                        f'color:#9ed9a8;background:#2a3a2a;border:1px solid #3ecf8e;'
                        f'border-radius:2px;font-size:10px;padding:1px 4px;'
                    )
                else:
                    lab.setText('配方筛选')
                    lab.setStyleSheet(f'color:{TEXT_MUTED};font-size:10px;padding:1px 4px;')
            except Exception:
                pass
        badge = getattr(self, '_recipe_badge', None)
        if badge is not None and live and live != '—':
            try:
                if on:
                    badge.setStyleSheet(
                        f'background:#1e3a28;color:#b8f0c4;border:2px solid #3ecf8e;'
                        f'border-radius:3px;padding:3px 8px;font-size:11px;font-weight:700;'
                    )
            except Exception:
                pass

    def _sync_filmstrip_recipe_hint(self):
        """细妆⑲：胶片条 / strip 配方标签跟筛选态同步."""
        on = bool(getattr(self, '_recipe_filter_active', False))
        live = (getattr(self, '_live_recipe', '') or '').strip()
        strip = getattr(self, '_strip_recipe_lab', None)
        if strip is not None:
            try:
                base = f'配方 {live or "—"}'
                var = getattr(self, '_live_variant', '') or ''
                if var:
                    base += f'/{var}'
                if on and live and live != '—':
                    strip.setText(base + ' · 筛选中')
                    strip.setStyleSheet(
                        f'color:#9ed9a8;font-size:10px;font-weight:700;padding:1px 4px;'
                    )
                else:
                    strip.setText(base)
                    strip.setStyleSheet(f'color:{TEXT_MUTED};font-size:10px;padding:1px 4px;')
            except Exception:
                pass


    def set_device_chrome(self, *, ip=None, port=None, conn=None):
        """细妆：刷新 HMI「IP地址/端口/连接状态」控件文案。"""
        for lab in getattr(self, '_device_chrome_labels', []) or []:
            kind = lab.property('sieansChrome') or ''
            try:
                if kind == 'ip' and ip is not None:
                    lab.setText(str(ip))
                elif kind == 'port' and port is not None:
                    lab.setText(str(port))
                elif kind == 'conn' and conn is not None:
                    lab.setText(str(conn))
            except Exception:
                pass


    def set_film_stamp(self, path: str = '', index=None):
        """细妆⑳：MainWindow.finished 推送当前胶片路径，供下一条结果表 stamp。"""
        bag = {}
        if path:
            bag['path'] = str(path)
        if index is not None:
            try:
                bag['index'] = int(index)
            except Exception:
                pass
        self._pending_film_stamp = bag

    def set_trial_backfill_pending(self, on: bool = True):
        """细妆⑳：换型/测量链 trialOnce 后等待实跑回填判定徽章。"""
        self._pending_trial_backfill = bool(on)

    def backfill_after_trial(self, result: dict | None = None):
        """细妆⑳：试跑完成后把判定/耗时回填到配方徽章 tip + 固定栏短提示。"""
        if not getattr(self, '_pending_trial_backfill', False):
            return False
        self._pending_trial_backfill = False
        result = result or {}
        state = result.get('state') or ''
        elapsed = result.get('elapsedMs')
        judge = '—'
        try:
            for panel in getattr(self, '_stats_panels', []) or []:
                oh = panel.ok_history() if hasattr(panel, 'ok_history') else None
                if oh:
                    judge = 'OK' if oh[0] else 'NG'
                    break
        except Exception:
            pass
        if judge == '—' and state == 'completed':
            judge = 'OK'
        elif judge == '—' and state == 'failed':
            judge = 'NG'
        recipe = getattr(self, '_live_recipe', '') or '—'
        variant = getattr(self, '_live_variant', '') or ''
        tip = f'试跑回填 · {judge}'
        if elapsed is not None:
            tip += f' · {elapsed} ms'
        tip += f' · 配方 {recipe}' + (f'/{variant}' if variant else '')
        badge = getattr(self, '_recipe_badge', None)
        if badge is not None:
            try:
                base = badge.text() or f'配方 · {recipe}'
                # flash judge into tooltip; briefly accent border by OK/NG
                badge.setToolTip(tip)
                if str(judge).upper() in ('OK', 'PASS', '通'):
                    badge.setStyleSheet(
                        'background:#1e3a28;color:#b8f0c4;border:2px solid #3ecf8e;'
                        'border-radius:3px;padding:3px 8px;font-size:11px;font-weight:700;'
                    )
                elif str(judge).upper() in ('NG', 'FAIL', '拒'):
                    badge.setStyleSheet(
                        'background:#3a1c1c;color:#ffb4b4;border:2px solid #e35d6a;'
                        'border-radius:3px;padding:3px 8px;font-size:11px;font-weight:700;'
                    )
                # restore accent after short pulse (keep recipe text)
                def _restore(b=badge, name=recipe, var=variant):
                    try:
                        self.set_recipe_chrome(name, var)
                    except Exception:
                        pass
                QTimer.singleShot(2200, _restore)
            except Exception:
                pass
        try:
            self.update_fixed_bar_live(okng=judge if judge != '—' else None)
        except Exception:
            pass
        try:
            self.append_log(tip)
        except Exception:
            pass
        # wave21: trial fail -> Alarm; clear restores 联调
        failed = (
            state == 'failed'
            or str(judge).upper() in ('NG', 'FAIL', '拒')
        )
        if failed:
            self._trial_fail_alarm = True
            try:
                self._paint_machine_chrome('Alarm')
            except Exception:
                pass
            try:
                self.append_log('试跑失败 · Alarm · 请清除报警恢复联调')
            except Exception:
                pass
            tip = tip + ' · 请清除报警恢复联调'
        # ephemeral tip label on strip recipe lab
        strip = getattr(self, '_strip_recipe_lab', None)
        if strip is not None:
            try:
                prev = strip.text()
                strip.setText(f'{prev} · 试跑{judge}' if prev else tip)
                def _rst(lab=strip, t=prev):
                    try:
                        lab.setText(t)
                    except Exception:
                        pass
                QTimer.singleShot(2400, _rst)
            except Exception:
                pass
        # Page-level trial→result co-update (banner + OK-NG dashboard)
        try:
            live = dict(getattr(self, '_live_page_chrome', None) or {})
            live.update({
                'trial': False,
                'okng': judge,
                'runStatus': 'completed' if not failed else 'failed',
                'hostState': 'Alarm' if failed else 'Idle',
                'banner': (
                    f"页铬 · 配方 {recipe} · 试跑结果 {judge}"
                    + (f' · {elapsed} ms' if elapsed is not None else '')
                ),
            })
            self.apply_trial_result_co_update(
                phase='result', snapshot=live, judge=judge, result=result,
            )
        except Exception:
            pass
        return True

    def _pulse_alarm_cleared(self, state: str, zh: str):
        """细妆⑳：离开 Alarm → 固定栏短暂恢复高亮 + 短提示。"""
        was_trial = bool(getattr(self, '_trial_fail_alarm', False))
        if was_trial:
            self._trial_fail_alarm = False
            tip = f'✓ 试跑失败已清除 · 联调已恢复 · {zh}'
        else:
            tip = f'✓ 报警已清除 · {zh}'
        # wave22: push Host SM Alarm 历史联调条
        try:
            host = getattr(self, '_host_sm', None)
            if host is not None and hasattr(host, 'push_liaison_event'):
                kind = '试跑清除' if was_trial else '报警清除'
                code = 'TRIAL_CLEAR' if was_trial else 'ALARM_CLEAR'
                host.push_liaison_event(tip, kind=kind, code=code)
        except Exception:
            pass
        try:
            self._live_run_status = zh
            # green restore flash
            flash_ss = (
                'background:#1c3a2a;color:#b8f0c4;border:2px solid #3ecf8e;'
                'border-radius:3px;padding:5px 10px;font-size:11px;font-weight:700;'
            )
            for bar in (getattr(self, '_fix_top', None), getattr(self, '_fix_bottom', None)):
                if bar is None:
                    continue
                try:
                    bar.setText(f'▬  {tip}')
                    bar.setStyleSheet(flash_ss)
                    bar.show()
                except Exception:
                    pass
            side_ss = (
                'background:#1c3a2a;color:#b8f0c4;border:2px solid #3ecf8e;'
                'border-radius:2px;padding:2px;font-size:10px;font-weight:700;'
            )
            for bar in (getattr(self, '_fix_left', None), getattr(self, '_fix_right', None)):
                if bar is None:
                    continue
                try:
                    if not bar.isHidden():
                        bar.setStyleSheet(side_ss)
                except Exception:
                    pass
            try:
                self.append_log(tip)
            except Exception:
                pass
            def _settle():
                try:
                    self._apply_fixed_bars(getattr(self, '_fixed_bars_cache', None) or {})
                except Exception:
                    pass
            QTimer.singleShot(1600, _settle)
        except Exception:
            pass

    def _filtered_result_rows(self):
        """当前结果表可见行（与 UI 门限/配方筛选一致，newest first）。"""
        hist = list(reversed(list(getattr(self, '_result_history', []) or [])[-50:]))
        mode = getattr(self, '_gate_filter_mode', 'all') or 'all'
        live_recipe = (getattr(self, '_live_recipe', '') or '').strip()
        recipe_on = bool(getattr(self, '_recipe_filter_active', False)) and live_recipe and live_recipe != '—'
        rows = hist
        if mode == 'pass':
            rows = [e for e in rows if e.get('gatePass') is True
                    or str(e.get('judge') or '').upper() in ('OK', 'PASS', '通')]
        elif mode == 'fail':
            rows = [e for e in rows if e.get('gatePass') is False
                    or str(e.get('judge') or '').upper() in ('NG', 'FAIL', '拒')]
        if recipe_on:
            rows = [e for e in rows if (e.get('recipe') or '').strip() == live_recipe]
        return rows

    def _result_row_payload(self, row: int):
        rows = self._filtered_result_rows()
        if row < 0 or row >= len(rows):
            return None
        e = rows[row]
        return {
            'path': e.get('filmPath') or '',
            'index': e.get('filmIndex'),
            'seq': e.get('seq'),
            'ts': e.get('ts'),
            'judge': e.get('judge'),
            'recipe': e.get('recipe'),
            'entry': e,
            'row': row,
        }

    def _on_result_row_clicked(self, row: int, _col: int = 0):
        """细妆⑳：结果表行点击 → 发 filmLocateRequested（胶片定位）。"""
        try:
            payload = self._result_row_payload(row)
            if not payload:
                return
            path = payload.get('path') or ''
            idx = payload.get('index')
            slim = {k: payload[k] for k in ('path', 'index', 'seq', 'ts', 'judge', 'recipe')}
            if path or idx is not None:
                self.filmLocateRequested.emit(slim)
                try:
                    self.append_log(
                        f"结果表定位胶片 · seq={payload.get('seq')} · "
                        f"{Path(path).name if path else f'#{idx}'}"
                    )
                except Exception:
                    pass
            else:
                try:
                    self.append_log(
                        f"结果表行缺胶片 path · seq={payload.get('seq')} · 可「补 stamp」"
                    )
                except Exception:
                    pass
        except Exception:
            pass

    def _on_result_row_double_clicked(self, row: int, _col: int = 0):
        """wave21: 结果表双击 → 定位胶片并打开该帧对比叠层；wave23: 多选时走多选对比。"""
        try:
            # wave23: if multiple rows selected, prefer multi compare
            try:
                table = self.sender() if hasattr(self, 'sender') else None
                if table is None:
                    for t0 in getattr(self, '_result_tables', []) or []:
                        if t0 is not None and t0.currentRow() == row:
                            table = t0
                            break
                if table is not None:
                    sel = sorted({ix.row() for ix in table.selectedIndexes()})
                    if len(sel) > 1:
                        self.request_multi_film_compare()
                        return
            except Exception:
                pass
            payload = self._result_row_payload(row)
            if not payload:
                return
            path = payload.get('path') or ''
            idx = payload.get('index')
            slim = {k: payload[k] for k in ('path', 'index', 'seq', 'ts', 'judge', 'recipe')}
            if path or idx is not None:
                try:
                    self.filmLocateRequested.emit(slim)
                except Exception:
                    pass
            self.filmCompareRequested.emit(slim)
            try:
                leaf = Path(path).name if path else (f'#{idx}' if idx is not None else '无path')
                self.append_log(f"结果表双击对比叠层 · seq={payload.get('seq')} · {leaf}")
            except Exception:
                pass
        except Exception:
            pass

    def request_manual_film_stamp(self):
        """wave21: 选中缺 path 行 → 请求 MW 用当前胶片补 stamp。"""
        try:
            table = None
            for t0 in getattr(self, '_result_tables', []) or []:
                if t0 is not None and t0.currentRow() >= 0:
                    table = t0
                    break
            if table is None and getattr(self, '_result_tables', None):
                table = self._result_tables[0]
            if table is None:
                return False
            row = table.currentRow()
            payload = self._result_row_payload(row)
            if not payload:
                try:
                    self.append_log('补 stamp：请先选中结果表行')
                except Exception:
                    pass
                return False
            if payload.get('path'):
                try:
                    self.append_log(
                        f"补 stamp：seq={payload.get('seq')} 已有 path · "
                        f"{Path(payload['path']).name}"
                    )
                except Exception:
                    pass
                return False
            self.filmStampRequest.emit({
                'seq': payload.get('seq'),
                'row': row,
                'ts': payload.get('ts'),
            })
            return True
        except Exception:
            return False

    def apply_manual_film_stamp(self, seq=None, path: str = '', index=None):
        """wave21: MW 回填当前胶片到指定 seq（或最新缺 path 行）。"""
        path = str(path or '').strip()
        if not path and index is None:
            return False
        hist = list(getattr(self, '_result_history', []) or [])
        target = None
        if seq is not None:
            for e in reversed(hist):
                if e.get('seq') == seq:
                    target = e
                    break
        if target is None:
            for e in reversed(hist):
                if not e.get('filmPath') and e.get('filmIndex') is None:
                    target = e
                    break
        if target is None and hist:
            target = hist[-1]
        if target is None:
            return False
        if path:
            target['filmPath'] = path
        if index is not None:
            try:
                target['filmIndex'] = int(index)
            except Exception:
                pass
        self._refresh_result_tables_ui()
        try:
            leaf = Path(path).name if path else f'#{index}'
            self.append_log(f"人工补 stamp · seq={target.get('seq')} · {leaf}")
        except Exception:
            pass
        return True

    def highlight_rows_for_film(self, path: str = '', index=None):
        """细妆⑳：胶片选中 → 反查结果表高亮匹配行（双向加深）。"""
        path = str(path or '').strip()
        try:
            target = str(Path(path).resolve()) if path else ''
        except Exception:
            target = path
        matched = []
        for table in getattr(self, '_result_tables', []) or []:
            try:
                table.clearSelection()
                for r in range(table.rowCount()):
                    it0 = table.item(r, 0)
                    if it0 is None:
                        continue
                    meta = it0.data(Qt.ItemDataRole.UserRole) or {}
                    if not isinstance(meta, dict):
                        meta = {}
                    hit = False
                    fp = str(meta.get('filmPath') or '')
                    if target and fp:
                        try:
                            hit = str(Path(fp).resolve()) == target or fp == path
                        except Exception:
                            hit = fp == path
                    if not hit and index is not None and meta.get('filmIndex') is not None:
                        try:
                            hit = int(meta.get('filmIndex')) == int(index)
                        except Exception:
                            pass
                    if hit:
                        table.selectRow(r)
                        matched.append(r)
                        try:
                            table.scrollToItem(table.item(r, 0))
                        except Exception:
                            pass
            except Exception:
                pass
        return matched

    def set_fail_code_badge(self, code: str = '', message: str = ''):
        """wave23: 换型失败码 HMI 徽章."""
        badge = getattr(self, '_fail_code_badge', None)
        if badge is None:
            return
        code = str(code or '').strip()
        if not code:
            self.clear_fail_code_badge()
            return
        msg = str(message or '').strip()
        tip = f'换型失败[{code}]'
        if msg:
            tip += f' · {msg}'
        badge.setText(f'⚠ {code}')
        badge.setToolTip(tip + ' · 单击跳报警历史 · 右键清除')
        self._fail_code_last = code
        self._fail_code_last_msg = msg
        badge.show()
        try:
            self.append_log(tip)
        except Exception:
            pass
        # auto-hide after 8s
        try:
            QTimer.singleShot(8000, lambda c=code: self._auto_hide_fail_badge(c))
        except Exception:
            pass

    def _auto_hide_fail_badge(self, code: str):
        badge = getattr(self, '_fail_code_badge', None)
        if badge is None or badge.isHidden():
            return
        if code and code not in (badge.text() or ''):
            return
        self.clear_fail_code_badge()

    def clear_fail_code_badge(self):
        badge = getattr(self, '_fail_code_badge', None)
        if badge is None:
            return
        badge.hide()
        badge.setText('')
        badge.setToolTip('换型失败码 · 单击跳报警历史 · 右键清除')
        self._fail_code_last = ''
        self._fail_code_last_msg = ''

    def _on_fail_code_badge_click(self, event):
        """wave24: 左键跳报警历史；右键清除."""
        try:
            btn = event.button() if event is not None else None
        except Exception:
            btn = None
        if btn == Qt.MouseButton.RightButton:
            self.clear_fail_code_badge()
            return
        self.jump_fail_code_to_alarm()

    def note_film_path(self, path: str = ''):
        """wave26: remember last film path for alarm→胶片定位."""
        self._last_film_path = str(path or '').strip()

    def jump_fail_code_to_alarm(self, code: str = ''):
        """wave24/26: 换型失败码 → Host SM 报警历史一键跳（可带胶片 path）."""
        code = str(code or getattr(self, '_fail_code_last', '') or '').strip()
        if not code:
            # parse from badge text "⚠ CODE"
            badge = getattr(self, '_fail_code_badge', None)
            raw = (badge.text() if badge is not None else '') or ''
            code = raw.replace('⚠', '').strip()
        host = getattr(self, '_host_sm', None)
        if host is None or not hasattr(host, 'jump_to_alarm_for_code'):
            try:
                self.append_log(f'跳报警历史失败：无 Host SM · {code}')
            except Exception:
                pass
            return False
        # wave26: 带上当前/最近胶片 path，供高亮首条双击定位
        film_path = ''
        try:
            film_path = str(getattr(self, '_last_film_path', '') or '').strip()
        except Exception:
            film_path = ''
        if not film_path:
            try:
                # result list first row UserRole filmPath if present
                lst = getattr(self, '_list', None)
                if lst is not None and lst.count() > 0:
                    it = lst.item(0)
                    data = it.data(Qt.ItemDataRole.UserRole) if it is not None else None
                    if isinstance(data, dict):
                        film_path = str(data.get('filmPath') or data.get('path') or '').strip()
                    elif isinstance(data, str):
                        film_path = data.strip()
            except Exception:
                pass
        try:
            host.jump_to_alarm_for_code(code, keyword=code, film_path=film_path)
        except Exception as err:
            try:
                self.append_log(f'跳报警历史失败：{err}')
            except Exception:
                pass
            return False
        try:
            self.append_log(f'已跳报警历史 · {code}')
        except Exception:
            pass
        return True

    def request_multi_film_compare(self):
        """wave23: 结果表多选行 → filmCompareRequested(paths=[...])."""
        try:
            table = None
            for t0 in getattr(self, '_result_tables', []) or []:
                if t0 is not None and t0.selectedIndexes():
                    table = t0
                    break
            if table is None and getattr(self, '_result_tables', None):
                table = self._result_tables[0]
            if table is None:
                return False
            rows = sorted({ix.row() for ix in table.selectedIndexes()})
            if not rows:
                try:
                    self.append_log('多选对比：请先多选结果表行（Ctrl/Shift）')
                except Exception:
                    pass
                return False
            paths, indices, seqs = [], [], []
            first = None
            for r in rows:
                payload = self._result_row_payload(r)
                if not payload:
                    continue
                if first is None:
                    first = payload
                p = str(payload.get('path') or '').strip()
                if p and p not in paths:
                    paths.append(p)
                if payload.get('index') is not None:
                    indices.append(payload.get('index'))
                if payload.get('seq') is not None:
                    seqs.append(payload.get('seq'))
            if not paths:
                try:
                    self.append_log('多选对比：所选行无胶片 path（可先补 stamp）')
                except Exception:
                    pass
                return False
            slim = {
                'path': paths[0],
                'paths': paths[:6],
                'indices': indices[:6],
                'seqs': seqs[:6],
                'multi': True,
                'seq': (first or {}).get('seq'),
                'index': (first or {}).get('index'),
            }
            try:
                self.filmLocateRequested.emit({
                    'path': paths[0], 'index': slim.get('index'), 'seq': slim.get('seq'),
                })
            except Exception:
                pass
            self.filmCompareRequested.emit(slim)
            try:
                self.append_log(
                    f"多选对比 · {len(paths[:6])} 帧 · "
                    + ', '.join(Path(x).name for x in paths[:6])
                )
            except Exception:
                pass
            return True
        except Exception:
            return False

    def _on_liaison_pushed(self, entry):
        """wave23/24: Host SM 联调条 → 固定栏短闪（颜色按严重度）."""
        entry = entry or {}
        kind = str(entry.get('kind') or '联调')
        code = str(entry.get('code') or '')
        text = str(entry.get('text') or '')
        sev = str(entry.get('severity') or '').strip().lower()
        if not sev:
            try:
                from desktop.host_state_machine import HostStateMachineWidget as _H
                sev = _H._liaison_severity(kind, code)
            except Exception:
                sev = 'info'
        tip = f'联调 · {kind}'
        if code:
            tip += f'[{code}]'
        if text:
            tip += ' · ' + text[:40]
        # wave24 severity palettes
        palettes = {
            'error': ('#3a1c1c', '#ffb4b4', '#e35d6a'),
            'warn':  ('#3a3420', '#f0d9a0', '#e0b84a'),
            'ok':    ('#1c3a2a', '#9ed9a8', '#3ecf8e'),
            'info':  ('#1c2a3a', '#b8d8f0', '#6eb6ff'),
        }
        bg, fg, bd = palettes.get(sev, palettes['info'])
        try:
            flash_ss = (
                f'background:{bg};color:{fg};border:2px solid {bd};'
                'border-radius:3px;padding:5px 10px;font-size:11px;font-weight:700;'
            )
            for bar in (getattr(self, '_fix_top', None), getattr(self, '_fix_bottom', None)):
                if bar is None:
                    continue
                try:
                    bar.setText(f'▬  {tip}')
                    bar.setStyleSheet(flash_ss)
                    bar.show()
                except Exception:
                    pass
            side_ss = (
                f'background:{bg};color:{fg};border:2px solid {bd};'
                'border-radius:2px;padding:2px;font-size:10px;font-weight:700;'
            )
            for bar in (getattr(self, '_fix_left', None), getattr(self, '_fix_right', None)):
                if bar is None:
                    continue
                try:
                    if not bar.isHidden():
                        bar.setStyleSheet(side_ss)
                except Exception:
                    pass
            try:
                self.append_log(tip + f' · sev={sev}')
            except Exception:
                pass
            def _settle():
                try:
                    self._apply_fixed_bars(getattr(self, '_fixed_bars_cache', None) or {})
                except Exception:
                    pass
            QTimer.singleShot(1400, _settle)
        except Exception:
            pass

    def apply_production_page_chrome(self, snapshot=None):
        """Page-level recipe/status chrome binding from production_task (not prop chips)."""
        snap = dict(snapshot or {})
        recipe = str(snap.get('recipe') or '').strip() or '—'
        variant = str(snap.get('variant') or '').strip()
        status = str(snap.get('status') or 'ready')
        sv = str(snap.get('statusVar') or 'taskStatus')
        scope = str(snap.get('scope') or 'global')
        task = str(snap.get('taskName') or '—')
        steps = snap.get('chainSteps', 0)
        banner = str(snap.get('banner') or '').strip() or (
            f'页铬 · 配方 {recipe} · 状态 {status} · {scope}.{sv} · 链 {steps} 步'
        )
        self._live_page_chrome = snap
        # Header recipe badge + strip recipe
        try:
            self.set_recipe_chrome(recipe, variant)
        except Exception:
            pass
        # Page chrome banner
        lab = getattr(self, '_page_chrome_banner', None)
        if lab is not None:
            trial = ' · 试跑待回填' if snap.get('trial') else ''
            lab.setText(banner + trial)
            lab.setToolTip(
                f'任务 {task} · {scope}.{sv}={status} · 链 {steps} 步 · '
                f'绑定目标：页眉徽章 / 状态轨 / 固定栏 / 默认条配方'
            )
            if status == 'running' or snap.get('trial'):
                lab.setStyleSheet(
                    'background:#1c3a2a;color:#9ed9a8;border:1px solid #3ecf8e;'
                    'border-radius:3px;padding:6px 10px;font-size:12px;font-weight:700;'
                )
            elif status == 'unconfigured':
                lab.setStyleSheet(
                    'background:#3a3420;color:#e0b84a;border:1px solid #e0b84a;'
                    'border-radius:3px;padding:6px 10px;font-size:12px;font-weight:700;'
                )
            else:
                lab.setStyleSheet(
                    'background:#1a2430;color:#9ec9f0;border:1px solid #3a5a7a;'
                    'border-radius:3px;padding:6px 10px;font-size:12px;font-weight:700;'
                )
        # Fixed-bar live + machine chrome
        try:
            self.update_fixed_bar_live(
                run_status=str(snap.get('runStatus') or status),
                okng=str(snap.get('okng') or '—'),
                counters=str(snap.get('counters') or f'链{steps}'),
                comm=str(snap.get('comm') or 'LocalBus'),
            )
        except Exception:
            pass
        host_state = str(snap.get('hostState') or '')
        if host_state:
            try:
                self._paint_machine_chrome(host_state)
            except Exception:
                pass
            try:
                for panel in getattr(self, '_stats_panels', []) or []:
                    if hasattr(panel, 'set_host_state_mirror'):
                        try:
                            from desktop.host_state_machine import STATE_ZH
                            zh = STATE_ZH.get(host_state, host_state)
                        except Exception:
                            zh = host_state
                        panel.set_host_state_mirror(host_state, zh)
            except Exception:
                pass
        # Refresh OK/NG dashboard soft strip with chrome context
        try:
            self.refresh_okng_dashboard_strip(
                recipe=recipe, status=status, status_var=f'{scope}.{sv}',
            )
        except Exception:
            pass
        return snap


    def apply_trial_result_co_update(self, *, phase='trial', snapshot=None, judge=None, result=None):
        """production_task ▶试跑 → live HMI page-chrome + OK-NG dashboard co-update."""
        snap = dict(snapshot or getattr(self, '_live_page_chrome', None) or {})
        result = result or {}
        phase = str(phase or 'trial')
        j = judge or snap.get('okng') or result.get('judge') or ('—' if phase == 'trial' else 'OK')
        recipe = str(snap.get('recipe') or getattr(self, '_live_recipe', '') or '—')
        if phase == 'trial':
            snap['trial'] = True
            snap['runStatus'] = '试跑'
            snap['okng'] = '试跑中'
            snap['hostState'] = 'Running'
            banner = str(snap.get('banner') or '') or f'页铬 · 配方 {recipe} · 试跑中'
            if '试跑' not in banner:
                banner = banner + ' · 试跑待回填'
            strip_txt = f'试跑→结果 · TRIAL · 配方 {recipe} · 看板待回填 · Running'
            strip_ss = (
                'background:#1c3a2a;color:#9ed9a8;border:1px solid #3ecf8e;'
                'border-radius:3px;padding:5px 10px;font-size:11px;font-weight:700;'
            )
        else:
            snap['trial'] = False
            snap['okng'] = j
            failed = str(j).upper() in ('NG', 'FAIL', '拒', '不良') or result.get('state') == 'failed'
            snap['runStatus'] = 'failed' if failed else 'completed'
            snap['hostState'] = 'Alarm' if failed else 'Idle'
            banner = (
                f'页铬 · 配方 {recipe} · 试跑结果 {j}'
                + (f" · {result.get('elapsedMs')} ms" if result.get('elapsedMs') is not None else '')
            )
            snap['banner'] = banner
            strip_txt = (
                f'试跑→结果 · RESULT {j} · 配方 {recipe} · '
                f'host={snap["hostState"]} · 页铬+看板已联更'
            )
            if failed:
                strip_ss = (
                    'background:#3a1c1c;color:#ffb4b4;border:1px solid #e35d6a;'
                    'border-radius:3px;padding:5px 10px;font-size:11px;font-weight:700;'
                )
            else:
                strip_ss = (
                    'background:#1c3a2a;color:#9ed9a8;border:1px solid #3ecf8e;'
                    'border-radius:3px;padding:5px 10px;font-size:11px;font-weight:700;'
                )
        # Respect recipe chrome lock (换型中不覆盖锁)
        if not getattr(self, '_page_chrome_locked', False):
            try:
                self.apply_production_page_chrome(snap)
            except Exception:
                pass
        lab = getattr(self, '_trial_result_strip', None)
        if lab is not None:
            lab.setText(strip_txt)
            lab.setStyleSheet(strip_ss)
            lab.setToolTip(banner)
        # Soft bump stats panel for OK-NG when result
        if phase == 'result':
            try:
                ok_ish = str(j).upper() in ('OK', 'PASS', '良', '通过')
                for panel in getattr(self, '_stats_panels', []) or []:
                    if hasattr(panel, 'record'):
                        panel.record(ok_ish, elapsed_ms=result.get('elapsedMs') or 0, detail=f'trial→{j}')
                        break
            except Exception:
                pass
            try:
                self.refresh_okng_dashboard_strip(
                    ok_n=snap.get('okCount'),
                    ng_n=snap.get('ngCount'),
                    judge=j,
                    host_state=snap.get('hostState'),
                    recipe=recipe,
                    status=snap.get('runStatus'),
                )
            except Exception:
                pass
        return snap

    def lock_page_chrome_for_recipe_switch(self, locked=True, *, recipe=None, reason='换型'):
        """Full-page chrome lock during recipe 换型 (page-level; not prop chips)."""
        self._page_chrome_locked = bool(locked)
        if recipe is not None:
            self._page_chrome_lock_recipe = str(recipe or '')
        lab = getattr(self, '_page_chrome_banner', None)
        name = self._page_chrome_lock_recipe or getattr(self, '_live_recipe', '') or '—'
        if lab is not None:
            if locked:
                lab.setText(f'页铬 · 锁 · 换型中 · 配方 {name} · 状态轨暂停手递')
                lab.setStyleSheet(
                    'background:#3a3420;color:#e0b84a;border:2px solid #e0b84a;'
                    'border-radius:3px;padding:6px 10px;font-size:12px;font-weight:700;'
                )
                lab.setToolTip(f'{reason} 页铬锁定中 · 配方 {name} · 完成后 Idle↔Running 软手递')
            else:
                lab.setText(f'页铬 · 配方 {name} · 换型锁已释 · 可手递')
                lab.setStyleSheet(
                    'background:#1a2430;color:#9ec9f0;border:1px solid #3a5a7a;'
                    'border-radius:3px;padding:6px 10px;font-size:12px;font-weight:700;'
                )
        # Dim state rail while locked
        rail = getattr(self, '_state_rail_labels', None) or {}
        for key, rl in rail.items():
            try:
                if locked:
                    rl.setStyleSheet(
                        'background:#2a2a2a;color:#666;border:1px solid #444;'
                        'border-radius:3px;padding:3px 8px;font-size:11px;'
                    )
                # unlock repaint happens in soft_handoff / _paint_machine_chrome
            except Exception:
                pass
        if not locked:
            try:
                self._paint_machine_chrome(getattr(self, '_host_state', None) or 'Idle')
            except Exception:
                pass
        return bool(locked)

    def soft_handoff_idle_running(self, *, recipe=None, to_running=True, note=''):
        """Status-rail Idle↔Running soft handoff after 换型 chrome unlock."""
        name = (recipe or self._page_chrome_lock_recipe
                or getattr(self, '_live_recipe', '') or '—')
        # Unlock first
        if getattr(self, '_page_chrome_locked', False):
            self.lock_page_chrome_for_recipe_switch(False, recipe=name, reason='换型完成')
        target = 'Running' if to_running else 'Idle'
        # Brief Idle flash then Running (or reverse) for visible soft handoff
        try:
            self._paint_machine_chrome('Idle' if to_running else 'Running')
        except Exception:
            pass
        lab = getattr(self, '_page_chrome_banner', None)
        if lab is not None:
            lab.setText(
                f'页铬 · 手递 Idle→{target} · 配方 {name}'
                + (f' · {note}' if note else '')
            )
            lab.setStyleSheet(
                'background:#1c3a2a;color:#9ed9a8;border:1px solid #3ecf8e;'
                'border-radius:3px;padding:6px 10px;font-size:12px;font-weight:700;'
            )
        tr = getattr(self, '_trial_result_strip', None)
        if tr is not None:
            tr.setText(f'换型手递 · Idle↔{target} · 配方 {name} · 页铬已解锁')
            tr.setStyleSheet(
                'background:#1a2430;color:#9ec9f0;border:1px solid #3a5a7a;'
                'border-radius:3px;padding:5px 10px;font-size:11px;font-weight:600;'
            )

        def _arrive(st=target, rname=name):
            try:
                self._paint_machine_chrome(st)
            except Exception:
                pass
            try:
                self.set_recipe_chrome(rname, getattr(self, '_live_variant', '') or '')
            except Exception:
                pass
            try:
                self.refresh_okng_dashboard_strip(
                    host_state=st, recipe=rname, status=st,
                )
            except Exception:
                pass
            ban = getattr(self, '_page_chrome_banner', None)
            if ban is not None:
                ban.setText(f'页铬 · 配方 {rname} · 状态 {st} · 换型手递完成')
        try:
            QTimer.singleShot(160, _arrive)
        except Exception:
            _arrive()
        return target


    def refresh_okng_dashboard_strip(self, *, ok_n=None, ng_n=None, judge=None,
                                     open_alarms=None, host_state=None,
                                     recipe=None, status=None, status_var=None,
                                     last_alarm=None):
        """Deepen Alarm/OK-NG dashboard soft strip (page-level; no micro chips)."""
        strip = getattr(self, '_okng_dashboard_strip', None)
        if strip is None:
            return
        # Pull live counters from first stats panel when not provided
        if ok_n is None or ng_n is None:
            for panel in getattr(self, '_stats_panels', []) or []:
                try:
                    ok_n = int(getattr(panel, '_ok', 0) if ok_n is None else ok_n)
                    ng_n = int(getattr(panel, '_ng', 0) if ng_n is None else ng_n)
                    break
                except Exception:
                    pass
        try:
            ok_i = int(ok_n) if ok_n is not None else 0
            ng_i = int(ng_n) if ng_n is not None else 0
        except (TypeError, ValueError):
            ok_i = ng_i = 0
        total = ok_i + ng_i
        ytxt = f'{(100.0 * ok_i / total):.1f}%' if total else '—'
        st = host_state or getattr(self, '_host_state', 'Idle') or 'Idle'
        try:
            from desktop.host_state_machine import STATE_ZH
            st_zh = STATE_ZH.get(st, st)
        except Exception:
            st_zh = st
        judge_txt = judge if judge is not None else getattr(self, '_live_okng', '—')
        # open alarms from host SM when available
        if open_alarms is None:
            open_alarms = 0
            last_alarm = last_alarm or ''
            host = getattr(self, '_host_sm', None) or getattr(self, 'host_state_machine', None)
            if host is None:
                # try embedded widgets
                for w in getattr(self, '_host_embeds', []) or []:
                    if hasattr(w, 'alarm_history'):
                        host = w
                        break
            if host is not None and hasattr(host, 'alarm_history'):
                try:
                    hist = list(host.alarm_history() or [])
                    open_alarms = sum(1 for e in hist if not e.get('cleared'))
                    if not last_alarm:
                        for e in reversed(hist):
                            if not e.get('cleared'):
                                last_alarm = str(e.get('reason') or e.get('detail') or '')
                                break
                except Exception:
                    pass
        # recent OK/NG sequence text (soft strip, not chip cascade)
        seq = ''
        for panel in getattr(self, '_stats_panels', []) or []:
            hist = list(getattr(panel, '_ok_hist', []) or [])
            if hist:
                # newest first → show left=old right=new for strip readability
                bits = [('O' if b else 'N') for b in reversed(hist[:24])]
                seq = ''.join(bits)
                break
        recipe_txt = recipe if recipe is not None else getattr(self, '_live_recipe', '') or '—'
        status_txt = status if status is not None else getattr(self, '_live_run_status', '') or '—'
        sv_txt = status_var or ''
        alarm_bit = f'报警开 {open_alarms}'
        if last_alarm:
            alarm_bit += f' · 末警 {last_alarm[:24]}'
        parts = [
            f'看板 · OK {ok_i}  NG {ng_i}  良率 {ytxt}',
            f'判定 {judge_txt}',
            alarm_bit,
            f'状态 {st_zh}',
        ]
        if seq:
            parts.append(f'序列 {seq}')
        if recipe_txt and recipe_txt != '—':
            parts.append(f'配方 {recipe_txt}')
        if sv_txt:
            parts.append(sv_txt)
        if status_txt and status_txt not in ('—', st_zh):
            parts.append(f'运行 {status_txt}')
        text = '  ·  '.join(parts)
        strip.setText(text)
        # color by alarm / NG dominance
        alarm_on = (st == 'Alarm') or bool(getattr(self, '_live_host_alarm', False)) or (open_alarms and int(open_alarms) > 0 and str(judge_txt).upper() in ('NG', 'FAIL', '不良'))
        low = str(judge_txt).strip().upper()
        if alarm_on or st == 'Alarm':
            strip.setStyleSheet(
                'background:#3a1c1c;color:#ffb4b4;border:1px solid #e35d6a;'
                'border-radius:3px;padding:6px 10px;font-size:12px;font-weight:700;'
            )
        elif low in ('NG', 'FAIL', '不良', '拒'):
            strip.setStyleSheet(
                'background:#3a1c1c;color:#ffb4b4;border:1px solid #e35d6a;'
                'border-radius:3px;padding:6px 10px;font-size:12px;font-weight:700;'
            )
        elif low in ('OK', 'PASS', '良', '通过') or (total and ok_i >= ng_i and st == 'Running'):
            strip.setStyleSheet(
                'background:#1c3a2a;color:#9ed9a8;border:1px solid #3ecf8e;'
                'border-radius:3px;padding:6px 10px;font-size:12px;font-weight:700;'
            )
        else:
            strip.setStyleSheet(
                f'background:{CARD};color:{TEXT_MUTED};border:1px solid {LINE};'
                f'border-radius:3px;padding:6px 10px;font-size:12px;font-weight:700;'
            )
        # Mirror into Host SM production strip when present
        host = None
        for attr in ('_host_sm', 'host_state_machine'):
            host = getattr(self, attr, None)
            if host is not None:
                break
        if host is not None and hasattr(host, 'set_production_snapshot'):
            try:
                host.set_production_snapshot(ok_i, ng_i, host_state=st)
            except Exception:
                pass
        if host is not None and hasattr(host, 'set_okng_dashboard_strip'):
            try:
                host.set_okng_dashboard_strip(text, alarm_on=bool(alarm_on or st == 'Alarm'))
            except Exception:
                pass
        return text

    def set_recipe_chrome(self, name: str = '', variant: str = ''):

        """细妆⑱：刷新运行态配方/变体徽章（换型闭环 → HMI 一目了然）."""
        name = (name or '').strip() or '—'
        variant = (variant or '').strip()
        self._live_recipe = name
        self._live_variant = variant
        badge = getattr(self, '_recipe_badge', None)
        if badge is not None:
            txt = f'配方 · {name}' + (f' · {variant}' if variant else '')
            badge.setText(txt)
            badge.setToolTip(f'当前产线配方：{name}' + (f' / 变体 {variant}' if variant else ''))
            # accent when a real recipe is active
            if name and name != '—':
                badge.setStyleSheet(
                    f'background:#2a3a2a;color:#9ed9a8;border:1px solid #3ecf8e;'
                    f'border-radius:3px;padding:3px 8px;font-size:11px;font-weight:700;'
                )
            else:
                badge.setStyleSheet(
                    f'background:{CARD};color:{TEXT_MUTED};border:1px solid {LINE};'
                    f'border-radius:3px;padding:3px 8px;font-size:11px;font-weight:600;'
                )
        strip_lab = getattr(self, '_strip_recipe_lab', None)
        if strip_lab is not None:
            strip_lab.setText(f'配方 {name}' + (f'/{variant}' if variant else ''))
        # re-paint fixed bars so tip includes recipe
        try:
            self._apply_fixed_bars(getattr(self, '_fixed_bars_cache', None) or {})
        except Exception:
            pass
        # 细妆⑲：换型后刷新结果表筛选态 / 胶片提示
        try:
            self._refresh_recipe_filter_labs()
            self._sync_filmstrip_recipe_hint()
            self._refresh_result_tables_ui()
        except Exception:
            pass

    def update_fixed_bar_live(self, *, run_status=None, okng=None, counters=None, camera=None, comm=None):
        """Refresh fixed-bar chrome with live run/OKNG/counters (细妆 · 固定栏实况)."""
        if run_status is not None:
            self._live_run_status = str(run_status)
        if okng is not None:
            self._live_okng = str(okng)
            # drive status lamps from OK/NG string
            low = str(okng).strip().upper()
            lamp_ok = True if low in ('OK', 'PASS', '良', '通过') else (
                False if low in ('NG', 'FAIL', '不良', '拒', 'NG/FAIL') else None
            )
            for lamp in getattr(self, '_status_lamps', []) or []:
                try:
                    lamp.set_state(lamp_ok)
                except Exception:
                    pass
        if counters is not None:
            self._live_counters = str(counters)
        fb = dict(getattr(self, '_fixed_bars_cache', None) or {})
        if camera is not None:
            fb['cameraBind'] = camera
        if comm is not None:
            fb['commBind'] = comm
        try:
            self._apply_fixed_bars(fb)
        except Exception:
            pass


    def _apply_fixed_bars(self, fb: dict):
        """细妆⑱：固定栏结构化 chip（相机/通讯/状态灯/配方）— 代码观感收束，非人工签字."""
        self._fixed_bars_cache = dict(fb or {})
        cam = fb.get('cameraBind') or CAMERA_BIND_OPTIONS[0]
        comm = fb.get('commBind') or COMM_BIND_OPTIONS[0]
        gate = (fb.get('gateKey') or '').strip()
        recipe = getattr(self, '_live_recipe', '') or ''
        variant = getattr(self, '_live_variant', '') or ''
        chips = [f'📷 {cam}', f'📡 {comm}']
        if gate:
            chips.append(f'门 flow.{gate}')
        if recipe and recipe != '—':
            chips.append(f'配方 {recipe}' + (f'/{variant}' if variant else ''))
        extras = []
        run_st = getattr(self, '_live_run_status', '空闲')
        okng = getattr(self, '_live_okng', '—')
        if fb.get('showRunStatus', True):
            extras.append(f'● {run_st}')
        if fb.get('showOkNg', True):
            extras.append(f'◆ {okng}')
        if fb.get('showCounters'):
            extras.append(f'＃ {getattr(self, "_live_counters", "0/0")}')
        tip = '  │  '.join(chips + extras)
        # colorize bar by OK/NG / Alarm-ish
        bar_bg, bar_fg, bar_bd = CARD, TEXT_MUTED, LINE
        low = str(okng).strip().upper()
        host = getattr(self, '_host_state', 'Idle')
        alarm_on = host == 'Alarm' or bool(getattr(self, '_live_host_alarm', False))
        if alarm_on:
            # Alarm dominates OK/NG paint so fixed bars mirror Host SM rail
            bar_bg, bar_fg, bar_bd = '#3a1c1c', '#ffb4b4', '#e35d6a'
            if '⚠' not in tip:
                tip = f'⚠ 报警  │  {tip}' if tip else '⚠ 报警'
        elif low in ('NG', 'FAIL', '不良', '拒'):
            bar_bg, bar_fg, bar_bd = '#3a1c1c', '#ffb4b4', '#e35d6a'
        elif low in ('OK', 'PASS', '良', '通过') or host == 'Running':
            bar_bg, bar_fg, bar_bd = '#1c3a2a', '#9ed9a8', '#3ecf8e'
        elif host == 'Paused':
            bar_bg, bar_fg, bar_bd = '#3a3420', '#e0b84a', '#e0b84a'
        bar_ss = (
            f'background:{bar_bg};color:{bar_fg};border:1px solid {bar_bd};'
            f'border-radius:3px;padding:5px 10px;font-size:11px;font-weight:600;'
        )
        for panel in getattr(self, '_stats_panels', []) or []:
            try:
                if gate and not panel.gate_key():
                    panel.set_gate_key(gate, notify=False)
            except Exception:
                pass
        if fb.get('top'):
            self._fix_top.setText(f'▬ 顶栏  {tip}')
            self._fix_top.setStyleSheet(bar_ss)
            self._fix_top.setToolTip(tip)
            self._fix_top.show()
        else:
            self._fix_top.hide()
        if fb.get('bottom'):
            self._fix_bottom.setText(f'▬ 底栏  {tip}')
            self._fix_bottom.setStyleSheet(bar_ss)
            self._fix_bottom.setToolTip(tip)
            self._fix_bottom.show()
        else:
            self._fix_bottom.hide()
        side_ss = (
            f'background:{bar_bg};color:{bar_fg};border:1px solid {bar_bd};'
            f'border-radius:2px;padding:2px;font-size:10px;font-weight:700;'
        )
        if fb.get('left'):
            self._fix_left.setText('左\n固\n定')
            self._fix_left.setToolTip(tip)
            self._fix_left.setStyleSheet(side_ss)
            self._fix_left.show()
        else:
            self._fix_left.hide()
        if fb.get('right'):
            self._fix_right.setText('右\n固\n定')
            self._fix_right.setToolTip(tip)
            self._fix_right.setStyleSheet(side_ss)
            self._fix_right.show()
        else:
            self._fix_right.hide()

    def _build_default_grid(self):
        """VM-style default: 图像+OK/NG | 上位机状态机 (p41–43)."""
        left = QVBoxLayout()
        left.setSpacing(6)
        cell = self._make_cell_frame('图像')
        view = ImageView()
        view.setMinimumHeight(200)
        self._image_views.append(view)
        cell.layout().addWidget(view, 1)
        left.addWidget(cell, 3)

        row = QHBoxLayout()
        lamp = StatusLamp('OK/NG')
        self._status_lamps.append(lamp)
        status = QLabel('空闲')
        status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status.setStyleSheet(f'color:{TEXT_MUTED};padding:3px;font-size:11px;')
        self._run_status_labels.append(status)
        row.addWidget(lamp, 1)
        row.addWidget(status, 1)
        left.addLayout(row)

        log_cell = self._make_cell_frame('界面日志')
        log = QPlainTextEdit()
        log.setReadOnly(True)
        log.setMaximumBlockCount(500)
        log.setPlaceholderText('运行日志…')
        log.setStyleSheet('font-size:11px;')
        self._log_views = getattr(self, '_log_views', [])
        self._log_views.append(log)
        self._log_panes.append(log)
        log_cell.layout().addWidget(log, 1)
        left.addWidget(log_cell, 1)

        stats_cell = self._make_cell_frame('生产统计')
        stats = ProductionStatsPanel()
        self._stats_panels.append(stats)
        self._wire_stats_panel(stats)
        stats_cell.layout().addWidget(stats, 1)
        left.addWidget(stats_cell, 1)

        left_w = QWidget()
        left_w.setLayout(left)
        self._grid_layout.addWidget(left_w, 0, 0)
        self._grid_layout.setColumnStretch(0, 3)
        self._grid_layout.setRowStretch(0, 1)

        from desktop.host_state_machine import HostStateMachineWidget
        host = HostStateMachineWidget(compact=True)
        self._wire_host_sm(host)
        self._grid_layout.addWidget(host, 0, 1)
        self._grid_layout.setColumnStretch(1, 2)

    def _build_from_placements(self, split, placements, controls):
        rows, cols = _split_rows_cols(split)
        # Map cell index → placement
        by_cell = {}
        for p in placements:
            by_cell[int(p.get('cell') or 0)] = p
        for r in range(rows):
            self._grid_layout.setRowStretch(r, 1)
            for c in range(cols):
                self._grid_layout.setColumnStretch(c, 1)
                idx = r * cols + c
                placement = by_cell.get(idx)
                if placement is None:
                    empty = QFrame()
                    empty.setObjectName('runPreviewCell')
                    empty.setFrameShape(QFrame.Shape.StyledPanel)
                    el = QVBoxLayout(empty)
                    lab = QLabel(f'窗格 {idx + 1}')
                    lab.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    lab.setStyleSheet(f'color:{TEXT_DIM};font-size:11px;')
                    el.addStretch(1)
                    el.addWidget(lab)
                    el.addStretch(1)
                    self._grid_layout.addWidget(empty, r, c)
                    continue
                name = placement.get('name') or ''
                st = controls.get(name) or {}
                widget = self._build_control(name, st)
                self._grid_layout.addWidget(widget, r, c)

    def _make_cell_frame(self, title: str):
        frame = QFrame()
        frame.setObjectName('runPreviewCell')
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(4)
        cap = QLabel(title)
        cap.setStyleSheet(f'color:{TEXT_MUTED};font-size:11px;font-weight:600;')
        lay.addWidget(cap)
        return frame

    def _build_control(self, name: str, state: dict) -> QWidget:
        commands = list(state.get('commands') or [])
        binding = state.get('binding') or ''

        if name in ('图像', '多图像', '图片'):
            cell = self._make_cell_frame(name + (f' · {binding}' if binding else ''))
            view = ImageView()
            view.setMinimumHeight(160)
            view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            self._image_views.append(view)
            cell.layout().addWidget(view, 1)
            return cell

        if name == '运行控制':
            cell = self._make_cell_frame('运行控制')
            row = QHBoxLayout()
            specs = [
                ('▶ 单次', commands or DEFAULT_RUN_COMMANDS, True),
                ('↻ 连续', DEFAULT_CONT_COMMANDS, False),
                ('■ 停止', DEFAULT_STOP_COMMANDS, False),
                ('注入 RUN', DEFAULT_INJECT_RUN_COMMANDS, False),
                ('注入 STOP', DEFAULT_INJECT_STOP_COMMANDS, False),
            ]
            # If designer configured multi-commands on 运行控制, first button uses them
            if commands:
                specs[0] = ('▶ 执行', commands, True)
            for label, cmds, primary in specs:
                btn = QPushButton(label)
                if primary:
                    btn.setObjectName('primaryButton')
                btn.clicked.connect(lambda _=False, c=cmds: self.triggerCommands.emit(deepcopy(c)))
                row.addWidget(btn)
            row.addStretch(1)
            cell.layout().addLayout(row)
            cell.layout().addStretch(1)
            return cell

        if name == '按钮':
            cell = self._make_cell_frame('按钮' + (f' · {binding}' if binding else ''))
            label = '执行'
            if commands:
                # Show first command type as label hint
                label = commands[0].get('type') or label
            btn = QPushButton(label)
            btn.setObjectName('primaryButton')
            btn.setMinimumHeight(36)
            cmds = commands or DEFAULT_RUN_COMMANDS
            btn.clicked.connect(lambda _=False, c=cmds: self.triggerCommands.emit(deepcopy(c)))
            cell.layout().addWidget(btn)
            if len(commands) > 1:
                tip = QLabel(' → '.join(c.get('type') or '?' for c in commands))
                tip.setObjectName('dialogHint')
                tip.setWordWrap(True)
                cell.layout().addWidget(tip)
            cell.layout().addStretch(1)
            return cell

        if name == '开关控制':
            cell = self._make_cell_frame('开关控制')
            row = QHBoxLayout()
            sw = OrangeSwitch(False)
            lab = QLabel('关')
            lab.setStyleSheet(f'color:{TEXT_MUTED};font-size:12px;')

            def _on_toggle(on, c=commands, l=lab):
                l.setText('开' if on else '关')
                if on and c:
                    self.triggerCommands.emit(deepcopy(c))

            sw.toggled.connect(_on_toggle)
            row.addWidget(sw)
            row.addWidget(lab)
            row.addStretch(1)
            cell.layout().addLayout(row)
            cell.layout().addStretch(1)
            return cell

        if name in ('OK/NG', '信号灯', '条件信号灯'):
            cell = self._make_cell_frame(name + (f' · {binding}' if binding else ''))
            lamp = StatusLamp(name)
            self._status_lamps.append(lamp)
            cell.layout().addWidget(lamp, 1)
            return cell

        if name == '运行状态':
            cell = self._make_cell_frame('运行状态')
            lab = QLabel('空闲')
            lab.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lab.setStyleSheet(f'color:{TEXT};font-size:13px;font-weight:600;padding:8px;')
            self._run_status_labels.append(lab)
            cell.layout().addWidget(lab, 1)
            return cell

        if name in ('文本框', '字符设置', '设置变量', '参数设置'):
            cell = self._make_cell_frame(name + (f' · {binding}' if binding else ''))
            tip = QLabel({
                '文本框': '只读绑定文本（⛓ 变量/结果）',
                '字符设置': '可写字符参数 → 流程变量',
                '设置变量': '写入全局/流程变量',
                '参数设置': '打开参数编辑 / 写入参数槽',
            }.get(name, ''))
            tip.setStyleSheet(f'color:{TEXT_MUTED};font-size:11px;')
            tip.setWordWrap(True)
            edit = QLineEdit()
            edit.setPlaceholderText(binding or CONTROL_STUB_HINTS.get(name, name))
            edit.setObjectName('hmiVarEdit')
            if name == '文本框':
                edit.setReadOnly(True)
                edit.setText(binding or '—')
            else:
                edit.setText(str(state.get('value') or ''))
                # live: emit as set-variable command when edited+enter
                def _commit(_=None, n=name, e=edit, c=commands, b=binding):
                    val = e.text()
                    cmds = list(c) or [dict(type='模块动作', config=f'{n}:{b or "var"}={val}')]
                    self.triggerCommands.emit(deepcopy(cmds))
                edit.editingFinished.connect(_commit)
            cell.layout().addWidget(tip)
            cell.layout().addWidget(edit)
            if name == '参数设置':
                btn = QPushButton('打开参数…')
                btn.setObjectName('hmiParamOpen')
                btn.clicked.connect(lambda *_: self.triggerCommands.emit(
                    list(commands) or [dict(type='参数配置', config=binding or '')]))
                cell.layout().addWidget(btn)
            cell.layout().addStretch(1)
            return cell

        if name == '界面日志':
            cell = self._make_cell_frame('界面日志')
            log = QPlainTextEdit()
            log.setReadOnly(True)
            log.setMaximumBlockCount(200)
            log.setPlaceholderText('运行日志…')
            self._log_panes.append(log)
            cell.layout().addWidget(log, 1)
            return cell

        if name == '世界时钟':
            cell = self._make_cell_frame('世界时钟')
            lab = QLabel('--:--:--')
            lab.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lab.setStyleSheet(f'color:{TEXT};font-size:20px;font-weight:700;padding:8px;')
            self._clock_labels.append(lab)
            cell.layout().addWidget(lab, 1)
            return cell

        if name in ('上位机状态机', '状态机面板', '上位机'):
            from desktop.host_state_machine import HostStateMachineWidget
            host = HostStateMachineWidget(compact=False)
            self._wire_host_sm(host)
            return host

        # p41 host-chrome stubs (no robot SDK)
        if name in ('IP地址', '端口'):
            cell = self._make_cell_frame(name)
            edit = QLineEdit(str(state.get('value') or ('192.168.1.109' if name == 'IP地址' else '5001')))
            edit.setPlaceholderText(name)
            edit.setProperty('sieansChrome', 'ip' if name == 'IP地址' else 'port')
            self._device_chrome_labels = getattr(self, '_device_chrome_labels', [])
            self._device_chrome_labels.append(edit)
            cell.layout().addWidget(edit)
            cell.layout().addStretch(1)
            return cell
        if name == '连接状态':
            cell = self._make_cell_frame('连接状态')
            row = QHBoxLayout()
            val = str(state.get('value') or '未连接')
            connected = val not in ('未连接', '断开', 'offline', 'OFF', '关', '')
            dot = QLabel('●')
            dot.setFixedWidth(22)
            dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
            dot.setStyleSheet(f'color:{"#3ecf8e" if connected else "#e35d6a"};font-size:16px;')
            dot.setProperty('sieansChrome', 'connLamp')
            lab = QLabel(val)
            lab.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lab.setStyleSheet(f'color:{"#3ecf8e" if connected else TEXT_MUTED};padding:8px;font-weight:600;')
            lab.setProperty('sieansChrome', 'conn')
            self._device_chrome_labels = getattr(self, '_device_chrome_labels', [])
            self._device_chrome_labels.append(lab)
            self._device_chrome_labels.append(dot)
            row.addStretch(1)
            row.addWidget(dot)
            row.addWidget(lab)
            row.addStretch(1)
            cell.layout().addLayout(row, 1)
            return cell
        if name == '信息提示栏':
            cell = self._make_cell_frame('信息提示栏')
            log = QPlainTextEdit()
            log.setReadOnly(True)
            log.setPlaceholderText('信息提示栏…')
            log.setMaximumBlockCount(200)
            self._log_panes.append(log)
            self._log_views = getattr(self, '_log_views', [])
            self._log_views.append(log)
            cell.layout().addWidget(log, 1)
            return cell
        if name in ('生产统计', '产量统计', '计数器'):
            cell = self._make_cell_frame(name)
            panel = ProductionStatsPanel()
            self._stats_panels.append(panel)
            self._wire_stats_panel(panel)
            cell.layout().addWidget(panel, 1)
            return cell

        # 细妆：表格 / 简单图表可视化（非纯 stub）
        if name in ('表格', '结果表'):
            cell = self._make_cell_frame(name + (f' · {binding}' if binding else ''))
            # 细妆⑬：多列历史结果表 + CSV 导出（时间/序号/模块/耗时/判定/OK/NG/门限/备注）
            table = QTableWidget(0, 10)
            table.setHorizontalHeaderLabels(
                ['时间', '序号', '模块', '耗时(ms)', '判定', 'OK累计', 'NG累计', '门限', '备注', '配方']
            )
            table.horizontalHeader().setStretchLastSection(True)
            table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
            table.verticalHeader().setVisible(False)
            table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            table.setObjectName('hmiResultTable')
            table.setMinimumHeight(120)
            table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
            table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)  # wave23 多选对比
            try:
                table.cellClicked.connect(self._on_result_row_clicked)
                table.cellDoubleClicked.connect(self._on_result_row_double_clicked)
            except Exception:
                pass
            self._result_tables = getattr(self, '_result_tables', [])
            self._result_tables.append(table)
            self._result_history = getattr(self, '_result_history', [])
            # 细妆⑮：门限列 spark of recent passGate sequence
            spark_lab = QLabel('门限序列  · · ·  ·  门限序列等待')
            spark_lab.setObjectName('hmiGateSpark')
            spark_lab.setStyleSheet(f'color:{TEXT_MUTED};font-size:11px;font-family:monospace;padding:2px 4px;')
            spark_lab.setToolTip('点击切换筛选：全部 → 仅通 → 仅拒 · 最近 passGate 真值序列（高=通 · 低=拒）')
            try:
                from PySide6.QtCore import Qt as _Qt
                spark_lab.setCursor(_Qt.CursorShape.PointingHandCursor)
            except Exception:
                pass
            spark_lab.mousePressEvent = self._make_gate_spark_click_handler(spark_lab)
            self._gate_spark_labs = getattr(self, '_gate_spark_labs', [])
            self._gate_spark_labs.append(spark_lab)
            filt_row = QHBoxLayout(); filt_row.setSpacing(6)
            filt_row.addWidget(spark_lab, 1)
            lab_rf = QLabel('配方筛选')
            lab_rf.setObjectName('hmiRecipeFilterLab')
            lab_rf.setCursor(Qt.CursorShape.PointingHandCursor)
            lab_rf.setStyleSheet(f'color:{TEXT_MUTED};font-size:10px;padding:1px 4px;')
            lab_rf.setToolTip('只看当前配方徽章对应的判定行（再点取消）；与顶部配方徽章联动')
            lab_rf.mousePressEvent = (lambda e: self._toggle_recipe_filter())
            filt_row.addWidget(lab_rf)
            self._recipe_filter_labs = getattr(self, '_recipe_filter_labs', [])
            self._recipe_filter_labs.append(lab_rf)
            btn_multi = QPushButton('多选对比')
            btn_multi.setObjectName('hmiMultiCompareBtn')
            btn_multi.setToolTip('结果表多选行 → 胶片多帧对比叠层（最多 6 帧）；再点同组或 ESC 清除')
            btn_multi.clicked.connect(self.request_multi_film_compare)
            filt_row.addWidget(btn_multi)
            cell.layout().addLayout(filt_row)
            cell.layout().addWidget(table, 1)
            btn_row = QHBoxLayout()
            b_copy = QPushButton('复制CSV')
            b_copy.setObjectName('hmiResultCopyCsvBtn')
            b_copy.setToolTip('复制结果表历史为 CSV')
            b_copy.clicked.connect(self.export_result_table_clipboard)
            btn_row.addWidget(b_copy)
            b_save = QPushButton('导出CSV…')
            b_save.setObjectName('hmiResultExportCsvBtn')
            b_save.setToolTip('导出结果表历史 CSV 文件')
            b_save.clicked.connect(self.export_result_table_file)
            btn_row.addWidget(b_save)
            b_clear = QPushButton('清空')
            b_clear.setObjectName('hmiResultClearBtn')
            b_clear.clicked.connect(self.clear_result_history)
            btn_row.addWidget(b_clear)
            b_stamp = QPushButton('补 stamp')
            b_stamp.setObjectName('hmiResultStampBtn')
            b_stamp.setToolTip('选中缺胶片 path 的结果行，用当前胶片人工补 stamp')
            b_stamp.clicked.connect(self.request_manual_film_stamp)
            btn_row.addWidget(b_stamp)
            btn_row.addStretch(1)
            cell.layout().addLayout(btn_row)
            # seed empty state row
            self._refresh_result_tables_ui()
            return cell
        if name in ('饼图',):
            cell = self._make_cell_frame(name)
            bar_ok = QProgressBar(); bar_ok.setRange(0, 100); bar_ok.setValue(0)
            bar_ok.setFormat('OK %p%'); bar_ok.setStyleSheet('QProgressBar::chunk{background:#3ecf8e;}')
            bar_ok.setObjectName('hmiYieldOkBar')
            bar_ng = QProgressBar(); bar_ng.setRange(0, 100); bar_ng.setValue(0)
            bar_ng.setFormat('NG %p%'); bar_ng.setStyleSheet('QProgressBar::chunk{background:#e35d6a;}')
            bar_ng.setObjectName('hmiYieldNgBar')
            tip = QLabel('良率（跟生产统计 OK/NG；运行后刷新）')
            tip.setStyleSheet(f'color:{TEXT_MUTED};font-size:11px;')
            cell.layout().addWidget(tip)
            cell.layout().addWidget(bar_ok)
            cell.layout().addWidget(bar_ng)
            cell.layout().addStretch(1)
            self._yield_bars = getattr(self, '_yield_bars', [])
            self._yield_bars.append((bar_ok, bar_ng))
            return cell
        if name in ('多数据线图', '线图阵列'):
            cell = self._make_cell_frame(name)
            tip = QLabel('趋势：周期耗时 spark + OK/NG + UPH（跟生产统计；每次 RUN 完成刷新）')
            tip.setWordWrap(True)
            tip.setStyleSheet(f'color:{TEXT_MUTED};font-size:11px;')
            spark = QLabel(ProductionStatsPanel.sparkline([]))
            spark.setAlignment(Qt.AlignmentFlag.AlignCenter)
            spark.setObjectName('hmiTrendSpark')
            spark.setStyleSheet(f'color:{TEXT};font-size:16px;letter-spacing:1px;padding:8px;')
            spark.setWordWrap(True)
            ok_spark = QLabel('· · ·  ·  判定序列等待')
            ok_spark.setAlignment(Qt.AlignmentFlag.AlignCenter)
            ok_spark.setObjectName('hmiTrendOkSpark')
            ok_spark.setStyleSheet(f'color:{TEXT_MUTED};font-size:14px;letter-spacing:1px;padding:4px;')
            uph_spark = QLabel('UPH趋势 · · ·  ·  等待')
            uph_spark.setAlignment(Qt.AlignmentFlag.AlignCenter)
            uph_spark.setObjectName('hmiTrendUphSpark')
            uph_spark.setStyleSheet(
                f'color:#6eb6ff;font-size:13px;font-family:monospace;'
                f'letter-spacing:1px;padding:4px;'
            )
            uph_spark.setToolTip('产线 UPH 趋势看板')
            cell.layout().addWidget(tip)
            cell.layout().addWidget(spark, 1)
            cell.layout().addWidget(ok_spark)
            cell.layout().addWidget(uph_spark)
            self._trend_sparks = getattr(self, '_trend_sparks', [])
            self._trend_ok_sparks = getattr(self, '_trend_ok_sparks', [])
            self._trend_uph_sparks = getattr(self, '_trend_uph_sparks', [])
            self._trend_sparks.append(spark)
            self._trend_ok_sparks.append(ok_spark)
            self._trend_uph_sparks.append(uph_spark)
            return cell
        if name in ('组合框', '参数组合', '文本框组合'):
            cell = self._make_cell_frame(name)
            tip = QLabel('容器组合：下拉切换嵌套页（QStackedWidget）；页内可挂判定灯/表格/约束提示')
            tip.setWordWrap(True)
            tip.setStyleSheet(f'color:{TEXT_MUTED};font-size:11px;')
            combo = QComboBox()
            combo.setObjectName('hmiComboContainer')
            stack = QStackedWidget()
            stack.setObjectName('hmiComboStack')
            # Page A · 外观
            pa = QWidget(); la = QVBoxLayout(pa); la.setContentsMargins(4, 4, 4, 4)
            lamp_a = StatusLamp('外观'); lamp_a.set_state(True); lamp_a.setObjectName('hmiComboLamp')
            sum_a = QLabel('外观检测 · 边缘/色差\n约束：方案页互斥，切页不丢控件状态')
            sum_a.setWordWrap(True); sum_a.setAlignment(Qt.AlignmentFlag.AlignCenter)
            sum_a.setObjectName('hmiComboSummary')
            la.addWidget(lamp_a); la.addWidget(sum_a, 1)
            # Page B · 尺寸
            pb = QWidget(); lb = QVBoxLayout(pb); lb.setContentsMargins(4, 4, 4, 4)
            tbl = QTableWidget(3, 2); tbl.setObjectName('hmiComboTable')
            tbl.setHorizontalHeaderLabels(['项', '值'])
            tbl.horizontalHeader().setStretchLastSection(True)
            tbl.verticalHeader().setVisible(False)
            for r, (k, v) in enumerate([('宽', '—'), ('高', '—'), ('公差', '±0.1')]):
                tbl.setItem(r, 0, QTableWidgetItem(k)); tbl.setItem(r, 1, QTableWidgetItem(v))
            tbl.setMaximumHeight(110)
            lamp_b = StatusLamp('尺寸'); lamp_b.set_state(False)
            lb.addWidget(lamp_b); lb.addWidget(tbl, 1)
            # Page C · 综合
            pc = QWidget(); lc = QVBoxLayout(pc); lc.setContentsMargins(4, 4, 4, 4)
            lamp_c = StatusLamp('综合'); lamp_c.set_state(None)
            drop_tip = QLabel('拖放约束：容器页只接受同布局控件；跨页绑定走 ⛓ 变量')
            drop_tip.setWordWrap(True)
            drop_tip.setObjectName('hmiComboDropHint')
            drop_tip.setStyleSheet(f'color:{TEXT_MUTED};font-size:11px;padding:6px;border:1px dashed {TEXT_MUTED};border-radius:4px;')
            lc.addWidget(lamp_c); lc.addWidget(drop_tip, 1)
            for lab, page in (('方案 A · 外观', pa), ('方案 B · 尺寸', pb), ('方案 C · 综合', pc)):
                combo.addItem(lab)
                stack.addWidget(page)
            combo.currentIndexChanged.connect(stack.setCurrentIndex)
            cell.layout().addWidget(tip)
            cell.layout().addWidget(combo)
            cell.layout().addWidget(stack, 1)
            return cell
        if name == 'Tab页':
            cell = self._make_cell_frame(name)
            tip = QLabel('多页签容器：页内可再嵌套组合框；拖放约束=同页栅格，跨页用变量绑定')
            tip.setWordWrap(True)
            tip.setStyleSheet(f'color:{TEXT_MUTED};font-size:11px;')
            tabs = QTabWidget()
            tabs.setObjectName('hmiTabContainer')
            # 检测页 · 嵌套小组合
            p1 = QWidget(); l1 = QVBoxLayout(p1); l1.setContentsMargins(8, 8, 8, 8)
            lamp1 = StatusLamp('检测判定'); lamp1.set_state(True); lamp1.setObjectName('hmiTabDetectLamp')
            nest = QComboBox(); nest.setObjectName('hmiTabNestedCombo')
            nest.addItems(['相机 A', '相机 B', '本地图'])
            nest_lab = QLabel('嵌套下拉 · 当前源：相机 A')
            nest_lab.setObjectName('hmiTabNestedLab')
            nest.currentTextChanged.connect(lambda s, lab=nest_lab: lab.setText(f'嵌套下拉 · 当前源：{s}'))
            l1.addWidget(QLabel('页 · 检测'))
            l1.addWidget(lamp1)
            l1.addWidget(nest)
            l1.addWidget(nest_lab)
            l1.addStretch(1)
            tabs.addTab(p1, '检测')
            # 统计页
            p2 = QWidget(); l2 = QVBoxLayout(p2); l2.setContentsMargins(8, 8, 8, 8)
            bar = QProgressBar(); bar.setRange(0, 100); bar.setValue(92)
            bar.setFormat('良率 %p%'); bar.setObjectName('hmiTabYieldBar')
            l2.addWidget(QLabel('页 · 统计'))
            l2.addWidget(bar)
            l2.addWidget(QLabel('约束：统计页只读产量，不接受运行按钮拖入'))
            l2.addStretch(1)
            tabs.addTab(p2, '统计')
            # 通讯页
            p3 = QWidget(); l3 = QVBoxLayout(p3); l3.setContentsMargins(8, 8, 8, 8)
            row = QHBoxLayout()
            dot = QLabel('●'); dot.setStyleSheet('color:#3ecf8e;font-size:16px;')
            dot.setObjectName('hmiTabCommDot')
            row.addWidget(dot); row.addWidget(QLabel('主机已连接（示意）')); row.addStretch(1)
            l3.addLayout(row)
            l3.addWidget(QLabel('页 · 通讯 / 日志入口'))
            l3.addWidget(QLabel('跨页绑定示例：flow.commState → 连接状态'))
            l3.addStretch(1)
            tabs.addTab(p3, '通讯')
            cell.layout().addWidget(tip)
            cell.layout().addWidget(tabs, 1)
            return cell
        if name == '子界面':
            cell = self._make_cell_frame(name)
            tip = QLabel('嵌套子界面：标题栏 + 判定灯 + 内嵌分区；可再放组合框栈/Tab/连接灯')
            tip.setWordWrap(True)
            tip.setStyleSheet(f'color:{TEXT_MUTED};font-size:11px;')
            inner = QFrame()
            inner.setObjectName('hmiSubUiShell')
            inner.setStyleSheet(
                f'QFrame#hmiSubUiShell{{border:1px solid {TEXT_MUTED};border-radius:8px;background:rgba(0,0,0,0.04);}}'
            )
            il = QVBoxLayout(inner)
            head_row = QHBoxLayout()
            head = QLabel('子界面 · 标题栏')
            head.setStyleSheet(f'font-weight:600;color:{TEXT};padding:4px 8px;')
            head_row.addWidget(head)
            head_row.addStretch(1)
            mini = StatusLamp('子')
            mini.setFixedHeight(36)
            mini.set_state(True)
            mini.setObjectName('hmiSubUiLamp')
            head_row.addWidget(mini)
            body = QLabel('内嵌区：可再挂载图像窗 / 表格 / 按钮行')
            body.setAlignment(Qt.AlignmentFlag.AlignCenter)
            body.setWordWrap(True)
            body.setStyleSheet(f'color:{TEXT_MUTED};padding:16px;')
            il.addLayout(head_row)
            il.addWidget(body, 1)
            cell.layout().addWidget(tip)
            cell.layout().addWidget(inner, 1)
            return cell

        # Fallback stub for remaining chart / exotic controls
        cell = self._make_cell_frame(name)
        hint = CONTROL_STUB_HINTS.get(name, '')
        body = QLabel(f'▣ {name}' + (f'\n{hint}' if hint else '') + (f'\n⛓ {binding}' if binding else ''))
        body.setAlignment(Qt.AlignmentFlag.AlignCenter)
        body.setStyleSheet(f'color:{TEXT_MUTED};font-weight:600;font-size:12px;')
        body.setWordWrap(True)
        cell.layout().addStretch(1)
        cell.layout().addWidget(body)
        cell.layout().addStretch(1)
        return cell

    def _tick_clocks(self):
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        for lab in self._clock_labels:
            lab.setText(now)
