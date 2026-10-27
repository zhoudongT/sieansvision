"""上位机状态机 HMI — VisionMaster p41–43 可点击壳（无机械手 SDK）。

手动控制：IP/端口/连接(示意)/回原点 · 运动 X/Y/Z/角/速 · 吸嘴
自动运行：正常生产 / 九点标定 / 旋转标定 · 开始/暂停/继续/停止
状态：Idle / Running / Paused / Alarm / Stopped — 开始/停止接到流程触发。
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta

from PySide6.QtCore import (
    Qt, Signal, QTimer, QSettings, QPoint, QUrl,
    QPropertyAnimation, QEasingCurve,
)
from PySide6.QtGui import (
    QAction, QKeySequence, QShortcut, QDesktopServices,
    QPainter, QPen, QColor, QIcon, QPixmap, QPainterPath, QFont,
)
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QTabWidget, QFormLayout, QLineEdit, QGroupBox, QPlainTextEdit,
    QGridLayout, QSizePolicy, QComboBox, QDoubleSpinBox, QSpinBox, QListWidget, QListWidgetItem, QFileDialog, QApplication,
    QMenu,
    QToolTip,
    QMessageBox,
    QProgressBar,
    QDialog,
    QDialogButtonBox,
    QColorDialog,
    QAbstractItemView,
    QGraphicsOpacityEffect,
    QWidgetAction,
    QInputDialog,
)

from desktop.theme import TEXT, TEXT_MUTED, TEXT_DIM, OK, PANEL, LINE

STATES = ('Idle', 'Running', 'Paused', 'Alarm', 'Stopped')
STATE_ZH = {
    'Idle': '空闲',
    'Running': '运行中',
    'Paused': '已暂停',
    'Alarm': '报警',
    'Stopped': '已停止',
}
STATE_COLOR = {
    'Idle': ('#2a3340', '#8a9bb0'),
    'Running': ('#1c3a2a', '#3ecf8e'),
    'Paused': ('#3a3420', '#e0b84a'),
    'Alarm': ('#3a1c1c', '#e35d6a'),
    'Stopped': ('#2a3340', '#8a9bb0'),
}

MODES = ('正常生产', '九点标定', '旋转标定')

# Alarm auto-clear policy (practical UX)
ALARM_CLEAR_OFF = 'off'
ALARM_CLEAR_ON_OK = 'on_ok'
ALARM_CLEAR_TIMEOUT = 'timeout'
ALARM_CLEAR_POLICIES = (ALARM_CLEAR_OFF, ALARM_CLEAR_ON_OK, ALARM_CLEAR_TIMEOUT)
ALARM_CLEAR_ZH = {
    ALARM_CLEAR_OFF: '关闭（需手动清除）',
    ALARM_CLEAR_ON_OK: '下次运行成功清除',
    ALARM_CLEAR_TIMEOUT: '超时自动清除',
}



class _SevChipPinProgressArc(QWidget):
    """wave37–38: 芯片长按落钉进度弧 overlay；色可配."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._p = 0.0
        self._color = '#f0c040'
        self.setFixedSize(24, 24)
        self.setObjectName('hostSevChipPinArc')
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.hide()

    def set_progress(self, p: float):
        self._p = max(0.0, min(1.0, float(p or 0.0)))
        self.update()

    def set_color(self, color: str):
        c = str(color or '').strip() or '#f0c040'
        if not c.startswith('#'):
            c = '#' + c
        self._color = c
        self.update()

    def color(self) -> str:
        return str(getattr(self, '_color', '#f0c040') or '#f0c040')

    def paintEvent(self, event):  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        track = QPen(QColor('#3a3d42'), 2)
        p.setPen(track)
        rect = self.rect().adjusted(2, 2, -2, -2)
        p.drawEllipse(rect)
        if self._p <= 0:
            return
        arc = QPen(QColor(self.color()), 2)
        p.setPen(arc)
        p.drawArc(rect, 90 * 16, -int(self._p * 360 * 16))


class HostStateMachineWidget(QWidget):
    """Clickable host HMI chrome (p42/p43). Emits triggerCommands like OperatorHmiView."""

    triggerCommands = Signal(object)  # list[dict]
    stateChanged = Signal(str)
    infoLogged = Signal(str)
    liaisonPushed = Signal(object)  # wave23: 联调条事件 → HMI 固定栏短闪
    alarmFilmLocateRequested = Signal(object)  # wave26: 报警双击 → 胶片定位

    def __init__(self, parent=None, compact=False):
        super().__init__(parent)
        self.setObjectName('hostStateMachine')
        self._state = 'Idle'
        self._connected = False
        self._mode = '正常生产'
        self._compact = compact
        self._alarm_auto_clear = ALARM_CLEAR_ON_OK
        self._alarm_timeout_sec = 8
        self._alarm_timer = QTimer(self)
        self._alarm_timer.setSingleShot(True)
        self._alarm_timer.timeout.connect(self._on_alarm_timeout)
        self._alarm_history = []  # list[{ts, reason, cleared}]
        self._alarm_history_max = 40
        self._current_film_path = ''  # wave27: 运行报警自动带 filmPath
        self._liaison_events = []  # wave22: 联调条 [{ts, kind, code, text}]
        self._liaison_events_max = 12

        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(6)

        # Title + state badge
        head = QHBoxLayout()
        title = QLabel('上位机控制程序')
        title.setStyleSheet(f'color:{TEXT};font-weight:700;font-size:13px;')
        head.addWidget(title)
        head.addStretch(1)
        self._badge = QLabel(STATE_ZH['Idle'])
        self._badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._badge.setMinimumWidth(72)
        head.addWidget(self._badge)
        root.addLayout(head)
        self._paint_badge()

        # Always-visible live controls (p41–43): drive SM + engine via triggerCommands
        self._quick = QWidget()
        self._quick.setObjectName('hostSmQuickBar')
        qrow = QHBoxLayout(self._quick)
        qrow.setContentsMargins(0, 0, 0, 0)
        qrow.setSpacing(4)
        self._q_start = QPushButton('▶ 开始')
        self._q_start.setObjectName('primaryButton')
        self._q_start.setToolTip('开始连续运行（正常生产）')
        self._q_start.clicked.connect(lambda: self._auto_start(self._mode or '正常生产'))
        self._q_pause = QPushButton('⏸ 暂停')
        self._q_pause.setToolTip('软暂停连续/运行全部')
        self._q_pause.clicked.connect(lambda: self._auto_pause(self._mode or '正常生产'))
        self._q_resume = QPushButton('▶ 继续')
        self._q_resume.setToolTip('从暂停继续')
        self._q_resume.clicked.connect(lambda: self._auto_resume(self._mode or '正常生产'))
        self._q_stop = QPushButton('■ 停止')
        self._q_stop.setToolTip('硬停止流程')
        self._q_stop.clicked.connect(lambda: self._auto_stop(self._mode or '正常生产'))
        self._q_clear = QPushButton('清除报警')
        self._q_clear.setToolTip('清除报警 → 空闲（状态·清除报警）')
        self._q_clear.clicked.connect(self._clear_alarm)
        for b in (self._q_start, self._q_pause, self._q_resume, self._q_stop, self._q_clear):
            b.setMinimumHeight(28)
            qrow.addWidget(b)
        qrow.addStretch(1)
        root.addWidget(self._quick)

        self.tabs = QTabWidget()
        self.tabs.setObjectName('hostHmiTabs')
        root.addWidget(self.tabs, 1)

        self.tabs.addTab(self._build_manual(), '手动控制')
        self.tabs.addTab(self._build_auto(), '自动运行')
        self.tabs.addTab(self._build_alarm_history(), '报警历史')
        if compact:
            # Live-point: auto controls visible without digging into 手动
            try:
                self.tabs.setCurrentIndex(1)
            except Exception:
                pass

        # Info bar
        info_cap = QLabel('信息显示栏')
        info_cap.setStyleSheet(f'color:{TEXT_MUTED};font-size:11px;font-weight:600;')
        root.addWidget(info_cap)
        self._log = QPlainTextEdit()
        self._log.setReadOnly(True)
        self._log.setMaximumBlockCount(300)
        self._log.setPlaceholderText('连接 / 运动 / 生产状态…')
        self._log.setMaximumHeight(110 if compact else 140)
        self._log.setStyleSheet('font-size:11px;')
        root.addWidget(self._log)

        self._log_line('上位机状态机就绪（无机械手 SDK · UI 示意）')

    # ----- public -----
    @property
    def state(self) -> str:
        return self._state

    def set_state(self, state: str, reason: str = ''):
        if state not in STATES:
            return
        prev = self._state
        self._state = state
        self._paint_badge()
        self._sync_auto_buttons()
        if state == 'Alarm' and prev != 'Alarm':
            self._record_alarm(
                reason or '报警',
                film_path=getattr(self, '_current_film_path', '') or '',
            )
            self._arm_alarm_timeout()
        elif state != 'Alarm':
            self._cancel_alarm_timeout()
        if state != prev:
            self.stateChanged.emit(state)
            msg = f'状态 {STATE_ZH.get(prev, prev)} → {STATE_ZH[state]}'
            if reason:
                msg += f' · {reason}'
            self._log_line(msg)
            # Keep production strip state label in sync
            try:
                self.set_production_snapshot(host_state=state)
            except Exception:
                pass

    def sync_from_runtime(self, result: dict | None, *, keep_running: bool = False):
        """Map engine job state → host state (without fighting Pause/Alarm).

        keep_running: continuous/run-all still active — cycle completed stays Running.
        Alarm + completed: honor alarm_auto_clear policy (off | on_ok | timeout).
        """
        result = result or {}
        st = result.get('state')
        if self._state == 'Paused' and st not in ('completed', 'failed', 'cancelled'):
            return
        if self._state == 'Alarm' and st not in ('completed',):
            if st == 'failed':
                return
        if st == 'completed':
            if self._state == 'Alarm':
                if self._alarm_auto_clear == ALARM_CLEAR_ON_OK:
                    self._clear_alarm_auto('下次运行成功')
                else:
                    self._log_line('运行成功 · 报警仍保持（自动清除策略）')
                return
            # Continuous production: stay Running across cycles (only Stop→Stopped)
            if keep_running or self._state == 'Running':
                elapsed = result.get('elapsedMs')
                tip = f'周期完成 · {elapsed} ms' if elapsed is not None else '周期完成'
                self._log_line(tip)
                return
            self.set_state('Idle', '流程完成')
        elif st == 'failed':
            self.set_state('Alarm', str(result.get('error') or '流程失败'))
        elif st == 'cancelled':
            self.set_state('Stopped', '用户停止')
        elif st in ('running', 'pending'):
            if self._state not in ('Running', 'Paused', 'Alarm'):
                self.set_state('Running', '流程执行中')

    def append_info(self, message: str):
        self._log_line(str(message))

    # ----- build -----
    def _build_manual(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(8)

        # Connect
        g = QGroupBox('连接（示意 · 无机械手协议）')
        gf = QFormLayout(g)
        self.ip_edit = QLineEdit('192.168.1.109')
        self.port_edit = QSpinBox()
        self.port_edit.setRange(1, 65535)
        self.port_edit.setValue(5001)
        gf.addRow('IP', self.ip_edit)
        gf.addRow('端口', self.port_edit)
        brow = QHBoxLayout()
        self.btn_connect = QPushButton('连接')
        self.btn_connect.setObjectName('primaryButton')
        self.btn_connect.clicked.connect(self._on_connect)
        self.btn_home = QPushButton('回原点')
        self.btn_home.clicked.connect(lambda: self._ui_action('回原点'))
        self.conn_lab = QLabel('未连接')
        self.conn_lab.setStyleSheet(f'color:{TEXT_MUTED};')
        brow.addWidget(self.btn_connect)
        brow.addWidget(self.btn_home)
        brow.addWidget(self.conn_lab, 1)
        gf.addRow(brow)
        lay.addWidget(g)

        # Motion
        g2 = QGroupBox('运动控制')
        grid = QGridLayout(g2)
        self.spin_x = self._dspin(100)
        self.spin_y = self._dspin(100)
        self.spin_z = self._dspin(80)
        self.spin_ang = self._dspin(0, lo=-360, hi=360)
        self.spin_spd = QSpinBox(); self.spin_spd.setRange(1, 100000); self.spin_spd.setValue(3000)
        for i, (lab, wdg) in enumerate((
            ('X', self.spin_x), ('Y', self.spin_y), ('Z', self.spin_z),
            ('角度', self.spin_ang), ('速度', self.spin_spd),
        )):
            grid.addWidget(QLabel(lab), i // 3, (i % 3) * 2)
            grid.addWidget(wdg, i // 3, (i % 3) * 2 + 1)
        btn_move = QPushButton('运动')
        btn_move.setObjectName('primaryButton')
        btn_move.clicked.connect(self._on_move)
        grid.addWidget(btn_move, 2, 0, 1, 6)
        lay.addWidget(g2)

        # Suction
        g3 = QGroupBox('吸嘴控制')
        srow = QHBoxLayout(g3)
        srow.addWidget(QLabel('吸力'))
        self.spin_vac = QSpinBox(); self.spin_vac.setRange(0, 99999); self.spin_vac.setValue(9000)
        srow.addWidget(self.spin_vac)
        b_on = QPushButton('开启')
        b_on.clicked.connect(lambda: self._ui_action(f'吸嘴开启 · 吸力={self.spin_vac.value()}'))
        b_off = QPushButton('关闭')
        b_off.clicked.connect(lambda: self._ui_action('吸嘴关闭'))
        srow.addWidget(b_on)
        srow.addWidget(b_off)
        srow.addStretch(1)
        lay.addWidget(g3)

        tip = QLabel('运动/吸嘴仅写日志与界面状态，不发送厂商机械手协议。')
        tip.setWordWrap(True)
        tip.setStyleSheet(f'color:{TEXT_DIM};font-size:11px;')
        lay.addWidget(tip)
        lay.addStretch(1)
        return w

    def _build_auto(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(8)

        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel('当前模式'))
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(list(MODES))
        self.mode_combo.currentTextChanged.connect(self._on_mode)
        mode_row.addWidget(self.mode_combo, 1)
        lay.addLayout(mode_row)

        grid = QGridLayout()
        self._mode_buttons = {}
        for col, mode in enumerate(MODES):
            box = QGroupBox(mode)
            bl = QVBoxLayout(box)
            btns = {}
            for key, label, slot in (
                ('start', '开始运行', lambda m=mode: self._auto_start(m)),
                ('pause', '暂停运行', lambda m=mode: self._auto_pause(m)),
                ('resume', '继续运行', lambda m=mode: self._auto_resume(m)),
                ('stop', '停止运行', lambda m=mode: self._auto_stop(m)),
            ):
                b = QPushButton(label)
                if key == 'start':
                    b.setObjectName('primaryButton')
                b.clicked.connect(slot)
                bl.addWidget(b)
                btns[key] = b
            if mode == '旋转标定':
                fr = QFormLayout()
                self.rot_x = self._dspin(200)
                self.rot_y = self._dspin(-20)
                self.rot_z = self._dspin(40)
                fr.addRow('X', self.rot_x)
                fr.addRow('Y', self.rot_y)
                fr.addRow('Z', self.rot_z)
                bl.addLayout(fr)
            self._mode_buttons[mode] = btns
            grid.addWidget(box, 0, col)
        lay.addLayout(grid)

        alarm_row = QHBoxLayout()
        b_alarm = QPushButton('模拟报警')
        b_alarm.clicked.connect(self._raise_alarm)
        b_clear = QPushButton('清除报警→空闲')
        b_clear.setObjectName('hostClearAlarmBtn')
        b_clear.clicked.connect(self._clear_alarm)
        self._btn_clear_alarm_tab = b_clear
        alarm_row.addWidget(b_alarm)
        alarm_row.addWidget(b_clear)
        alarm_row.addStretch(1)
        lay.addLayout(alarm_row)

        policy_row = QHBoxLayout()
        policy_row.addWidget(QLabel('报警自动清除'))
        self._alarm_policy_combo = QComboBox()
        for key in ALARM_CLEAR_POLICIES:
            self._alarm_policy_combo.addItem(ALARM_CLEAR_ZH[key], key)
        self._alarm_policy_combo.currentIndexChanged.connect(self._on_alarm_policy_changed)
        policy_row.addWidget(self._alarm_policy_combo, 1)
        policy_row.addWidget(QLabel('超时秒'))
        self._alarm_timeout_spin = QSpinBox()
        self._alarm_timeout_spin.setRange(1, 600)
        self._alarm_timeout_spin.setValue(int(self._alarm_timeout_sec))
        self._alarm_timeout_spin.setToolTip('仅「超时自动清除」生效')
        self._alarm_timeout_spin.valueChanged.connect(self._on_alarm_timeout_sec_changed)
        policy_row.addWidget(self._alarm_timeout_spin)
        lay.addLayout(policy_row)
        self._load_alarm_policy_settings()

        tip = QLabel(
            '「开始」→ 连续；「暂停/继续」→ 软暂停；「停止」→ 硬停止。'
            '报警可手动清除，或按策略：下次成功 / 超时自动清除。'
            '九点/旋转标定模式仅切换 UI 上下文（无厂商标定 SDK）。'
        )
        tip.setWordWrap(True)
        tip.setStyleSheet(f'color:{TEXT_DIM};font-size:11px;')
        lay.addWidget(tip)
        lay.addStretch(1)
        self._sync_auto_buttons()
        return w

    def _dspin(self, value, lo=-1e6, hi=1e6):
        s = QDoubleSpinBox()
        s.setRange(lo, hi)
        s.setDecimals(3)
        s.setValue(float(value))
        s.setMaximumWidth(110)
        return s

    def _paint_badge(self):
        bg, fg = STATE_COLOR.get(self._state, STATE_COLOR['Idle'])
        self._badge.setText(STATE_ZH.get(self._state, self._state))
        self._badge.setStyleSheet(
            f'background:{bg};color:{fg};border:1px solid {fg};'
            f'border-radius:3px;padding:4px 10px;font-weight:700;font-size:12px;'
        )

    def _sync_auto_buttons(self):
        st = self._state
        for mode, btns in (getattr(self, '_mode_buttons', None) or {}).items():
            btns['start'].setEnabled(st in ('Idle', 'Stopped'))
            btns['pause'].setEnabled(st == 'Running')
            btns['resume'].setEnabled(st == 'Paused')
            btns['stop'].setEnabled(st in ('Running', 'Paused', 'Alarm'))
        # Quick bar (always visible)
        for attr, enabled in (
            ('_q_start', st in ('Idle', 'Stopped')),
            ('_q_pause', st == 'Running'),
            ('_q_resume', st == 'Paused'),
            ('_q_stop', st in ('Running', 'Paused', 'Alarm')),
            ('_q_clear', st == 'Alarm'),
        ):
            btn = getattr(self, attr, None)
            if btn is not None:
                btn.setEnabled(enabled)
        # Highlight clear when Alarm
        clear = getattr(self, '_q_clear', None)
        if clear is not None:
            if st == 'Alarm':
                clear.setStyleSheet(
                    'background:#3a1c1c;color:#e35d6a;border:1px solid #e35d6a;'
                    'border-radius:3px;font-weight:700;'
                )
                clear.setVisible(True)
            else:
                clear.setStyleSheet('')
                # Keep visible but disabled when not Alarm so layout stable
                clear.setVisible(True)
        tab_clear = getattr(self, '_btn_clear_alarm_tab', None)
        if tab_clear is not None:
            tab_clear.setEnabled(st == 'Alarm')
            if st == 'Alarm':
                tab_clear.setStyleSheet(
                    'background:#3a1c1c;color:#e35d6a;border:1px solid #e35d6a;'
                    'font-weight:700;'
                )
            else:
                tab_clear.setStyleSheet('')

    def _log_line(self, text: str):
        ts = datetime.now().strftime('%H:%M:%S')
        line = f'[{ts}] {text}'
        self._log.appendPlainText(line)
        self.infoLogged.emit(line)

    def _ui_action(self, text: str):
        self._log_line(text)

    def _on_connect(self):
        ip = (self.ip_edit.text() or '').strip() or '127.0.0.1'
        port = int(self.port_edit.value())
        # Soft TCP probe — UI only; failure stays as "示意已连接" toggle for demo
        ok = False
        err = ''
        try:
            import socket
            s = socket.create_connection((ip, port), timeout=0.4)
            s.close()
            ok = True
        except Exception as e:
            err = str(e)
        self._connected = True  # UI demo: mark connected even if probe fails
        if ok:
            self.conn_lab.setText(f'已连接 {ip}:{port}')
            self.conn_lab.setStyleSheet(f'color:{OK};font-weight:600;')
            self.btn_connect.setText('断开')
            self._log_line(f'TCP 探测成功 {ip}:{port}')
        else:
            self.conn_lab.setText(f'示意连接 {ip}:{port}')
            self.conn_lab.setStyleSheet(f'color:#e0b84a;font-weight:600;')
            self.btn_connect.setText('断开示意')
            self._log_line(f'TCP 探测失败（仍标记示意连接）：{err or "unreachable"}')
        # Toggle disconnect on next click
        self.btn_connect.clicked.disconnect()
        self.btn_connect.clicked.connect(self._on_disconnect)

    def _on_disconnect(self):
        self._connected = False
        self.conn_lab.setText('未连接')
        self.conn_lab.setStyleSheet(f'color:{TEXT_MUTED};')
        self.btn_connect.setText('连接')
        self._log_line('已断开（示意）')
        self.btn_connect.clicked.disconnect()
        self.btn_connect.clicked.connect(self._on_connect)

    def _on_move(self):
        self._log_line(
            f'运动指令（示意） X={self.spin_x.value()} Y={self.spin_y.value()} '
            f'Z={self.spin_z.value()} 角={self.spin_ang.value()} 速={self.spin_spd.value()}'
        )

    def _on_mode(self, mode: str):
        self._mode = mode or '正常生产'
        self._log_line(f'切换模式 → {self._mode}')

    @property
    def alarm_auto_clear(self) -> str:
        return self._alarm_auto_clear

    def set_alarm_auto_clear(self, policy: str, timeout_sec: int | None = None):
        """Public: off | on_ok | timeout (+ optional seconds)."""
        if policy in ALARM_CLEAR_POLICIES:
            self._alarm_auto_clear = policy
        if timeout_sec is not None:
            try:
                self._alarm_timeout_sec = max(1, min(600, int(timeout_sec)))
            except (TypeError, ValueError):
                pass
        self._sync_alarm_policy_widgets()
        if self._state == 'Alarm':
            self._arm_alarm_timeout()
        self._save_alarm_policy_settings()

    def holds_alarm_on_ok(self) -> bool:
        """True when OK run must NOT force Idle (policy=off or timeout waiting)."""
        return self._state == 'Alarm' and self._alarm_auto_clear != ALARM_CLEAR_ON_OK

    def _sync_alarm_policy_widgets(self):
        combo = getattr(self, '_alarm_policy_combo', None)
        spin = getattr(self, '_alarm_timeout_spin', None)
        if combo is not None:
            combo.blockSignals(True)
            idx = combo.findData(self._alarm_auto_clear)
            if idx < 0:
                idx = combo.findData(ALARM_CLEAR_ON_OK)
            if idx >= 0:
                combo.setCurrentIndex(idx)
            combo.blockSignals(False)
        if spin is not None:
            spin.blockSignals(True)
            spin.setValue(int(self._alarm_timeout_sec))
            spin.setEnabled(self._alarm_auto_clear == ALARM_CLEAR_TIMEOUT)
            spin.blockSignals(False)

    def _on_alarm_policy_changed(self, *_):
        combo = getattr(self, '_alarm_policy_combo', None)
        if combo is None:
            return
        key = combo.currentData()
        if key in ALARM_CLEAR_POLICIES:
            self._alarm_auto_clear = key
        spin = getattr(self, '_alarm_timeout_spin', None)
        if spin is not None:
            spin.setEnabled(self._alarm_auto_clear == ALARM_CLEAR_TIMEOUT)
        if self._state == 'Alarm':
            self._arm_alarm_timeout()
        self._save_alarm_policy_settings()
        self._log_line(f'报警自动清除 → {ALARM_CLEAR_ZH.get(self._alarm_auto_clear, self._alarm_auto_clear)}')

    def _on_alarm_timeout_sec_changed(self, value):
        try:
            self._alarm_timeout_sec = max(1, min(600, int(value)))
        except (TypeError, ValueError):
            return
        if self._state == 'Alarm' and self._alarm_auto_clear == ALARM_CLEAR_TIMEOUT:
            self._arm_alarm_timeout()
        self._save_alarm_policy_settings()

    def _load_alarm_policy_settings(self):
        try:
            from PySide6.QtCore import QSettings
            s = QSettings('SIEANS', 'VisionDesktop')
            pol = str(s.value('hostAlarmAutoClear', ALARM_CLEAR_ON_OK) or ALARM_CLEAR_ON_OK)
            if pol not in ALARM_CLEAR_POLICIES:
                pol = ALARM_CLEAR_ON_OK
            self._alarm_auto_clear = pol
            try:
                self._alarm_timeout_sec = max(1, min(600, int(s.value('hostAlarmAutoClearSec', 8) or 8)))
            except (TypeError, ValueError):
                self._alarm_timeout_sec = 8
        except Exception:
            pass
        self._sync_alarm_policy_widgets()

    def _save_alarm_policy_settings(self):
        try:
            from PySide6.QtCore import QSettings
            s = QSettings('SIEANS', 'VisionDesktop')
            s.setValue('hostAlarmAutoClear', self._alarm_auto_clear)
            s.setValue('hostAlarmAutoClearSec', int(self._alarm_timeout_sec))
        except Exception:
            pass

    def _arm_alarm_timeout(self):
        self._cancel_alarm_timeout()
        if self._alarm_auto_clear != ALARM_CLEAR_TIMEOUT or self._state != 'Alarm':
            return
        ms = max(1, int(self._alarm_timeout_sec)) * 1000
        self._alarm_timer.start(ms)
        self._log_line(f'报警超时清除已启动 · {self._alarm_timeout_sec}s')

    def _cancel_alarm_timeout(self):
        try:
            if self._alarm_timer.isActive():
                self._alarm_timer.stop()
        except Exception:
            pass

    def _on_alarm_timeout(self):
        if self._state != 'Alarm' or self._alarm_auto_clear != ALARM_CLEAR_TIMEOUT:
            return
        self._clear_alarm_auto(f'超时 {self._alarm_timeout_sec}s')

    def _clear_alarm_auto(self, reason: str = ''):
        """Policy-driven clear (same emit path as manual clear)."""
        if self._state != 'Alarm':
            return
        tip = reason or '自动清除'
        if self._alarm_history:
            self._alarm_history[-1]['cleared'] = True
            self._alarm_history[-1]['cleared_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            self._refresh_alarm_history_ui()
        self.set_state('Idle', tip)
        self.triggerCommands.emit([dict(type='状态·清除报警', config=tip)])
        self._log_line(f'报警已自动清除 · {tip}')

    def _build_alarm_history(self):
        """Alarm history toward VM run-mode: filter / severity / spark / duration."""
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(8, 8, 8, 8)
        tip = QLabel('最近报警记录（进入 Alarm 时追加；不含机械手/厂商标定 SDK）。')
        tip.setWordWrap(True)
        tip.setStyleSheet(f'color:{TEXT_DIM};font-size:11px;')
        lay.addWidget(tip)
        # Production snapshot strip (fed by OperatorHmiView / MainWindow)
        self._prod_strip = QLabel('生产 · OK —  NG —  良率 —  ·  状态 空闲')
        self._prod_strip.setObjectName('hostProdStrip')
        self._prod_strip.setStyleSheet(
            f'background:{PANEL};color:{TEXT};border:1px solid {LINE};'
            f'border-radius:2px;padding:4px 8px;font-size:11px;font-weight:600;'
        )
        lay.addWidget(self._prod_strip)
        # wave22: Alarm 历史联调条（试跑清除 / 换型失败 / 报警清除）
        self._liaison_strip = QLabel('联调 · 等待事件（试跑清除 / 换型失败 / 报警清除）')
        self._liaison_strip.setObjectName('hostLiaisonStrip')
        self._liaison_strip.setWordWrap(True)
        self._liaison_strip.setStyleSheet(
            f'background:#1c2a3a;color:#9ec9f0;border:1px solid #3a5a7a;'
            f'border-radius:2px;padding:4px 8px;font-size:11px;'
        )
        self._liaison_strip.setToolTip(
            '联调事件条：试跑失败清除、换型失败码、报警清除等写入此处（最近 12 条）'
        )
        lay.addWidget(self._liaison_strip)
        self._alarm_spark = QLabel('报警序列 · · ·')
        self._alarm_spark.setObjectName('hostAlarmSpark')
        self._alarm_spark.setStyleSheet(f'color:{TEXT_MUTED};font-size:12px;font-family:monospace;')
        self._alarm_spark.setToolTip(
            '最近报警：▇=未清除 ▁=已清除；颜色=严重度 · 单击循环筛严重度'
        )
        self._alarm_spark.setCursor(Qt.CursorShape.PointingHandCursor)
        self._alarm_spark.mousePressEvent = lambda e: self._on_alarm_spark_clicked(e)
        lay.addWidget(self._alarm_spark)
        filt_row = QHBoxLayout()
        filt_row.addWidget(QLabel('筛选'))
        self._alarm_filter = QLineEdit()
        self._alarm_filter.setObjectName('hostAlarmHistoryFilter')
        self._alarm_filter.setPlaceholderText('按原因关键字筛选…')
        self._alarm_filter.setClearButtonEnabled(True)
        self._alarm_filter.textChanged.connect(lambda *_: self._refresh_alarm_history_ui())
        filt_row.addWidget(self._alarm_filter, 1)
        self._alarm_status_filter = QComboBox()
        self._alarm_status_filter.setObjectName('hostAlarmStatusFilter')
        self._alarm_status_filter.addItem('全部', 'all')
        self._alarm_status_filter.addItem('未清除', 'open')
        self._alarm_status_filter.addItem('已清除', 'cleared')
        self._alarm_status_filter.addItem('联调', 'liaison')
        self._alarm_status_filter.currentIndexChanged.connect(lambda *_: self._refresh_alarm_history_ui())
        filt_row.addWidget(self._alarm_status_filter)
        # wave26: 严重度筛（spark 点击同步）
        self._alarm_sev_filter = QComboBox()
        self._alarm_sev_filter.setObjectName('hostAlarmSevFilter')
        self._alarm_sev_filter.setToolTip('按严重度筛选（亦可点 spark 循环）')
        for lab, key in (
            ('严重度·全部', 'all'),
            ('错 error', 'error'),
            ('警 warning', 'warning'),
            ('讯 info', 'info'),
        ):
            self._alarm_sev_filter.addItem(lab, key)
        # wave27: 严重度筛持久
        try:
            saved_sev = str(self._host_settings().value('host/alarmSevFilter', 'all') or 'all').lower()
        except Exception:
            saved_sev = 'all'
        if saved_sev in ('warn',):
            saved_sev = 'warning'
        for i in range(self._alarm_sev_filter.count()):
            if str(self._alarm_sev_filter.itemData(i) or '') == saved_sev:
                self._alarm_sev_filter.setCurrentIndex(i)
                break
        self._alarm_sev_filter.currentIndexChanged.connect(self._on_alarm_sev_filter_changed)
        filt_row.addWidget(self._alarm_sev_filter)
        lay.addLayout(filt_row)
        # wave28: 严重度筛芯片条
        chip_row = QHBoxLayout()
        chip_row.setSpacing(4)
        self._alarm_sev_chips = {}
        self._alarm_sev_chip_labels = {}
        self._alarm_sev_count_bubbles = {}
        for lab, key in (
            ('全部', 'all'),
            ('错', 'error'),
            ('警', 'warning'),
            ('讯', 'info'),
        ):
            b = QPushButton(lab)
            b.setObjectName(f'hostAlarmSevChip_{key}')
            b.setCheckable(True)
            b.setFixedHeight(20)
            b.setMinimumWidth(36)
            b.setMaximumWidth(64)
            b.setToolTip(f'严重度筛 · {lab}')
            # wave36: 短按筛 · 长按落钉（预览钉可落）
            b.mousePressEvent = (lambda e, k=key: self._on_sev_chip_press(e, k))
            b.mouseReleaseEvent = (lambda e, k=key: self._on_sev_chip_release(e, k))
            b.enterEvent = (lambda e, k=key: self._on_sev_chip_enter(e, k))
            b.leaveEvent = (lambda e, k=key: self._on_sev_chip_leave(e, k))
            chip_row.addWidget(b)
            self._alarm_sev_chips[key] = b
            self._alarm_sev_chip_labels[key] = lab
            # wave29–32: 计数气泡 · 单击筛 · 长按钉住
            bubble = QLabel('0')
            bubble.setObjectName(f'hostAlarmSevCount_{key}')
            bubble.setFixedHeight(16)
            bubble.setMinimumWidth(14)
            bubble.setAlignment(Qt.AlignmentFlag.AlignCenter)
            bubble.setCursor(Qt.CursorShape.PointingHandCursor)
            bubble.setToolTip(f'左键筛 · 长按钉住 · 右键仅看{lab} · 中键清筛/取消钉')
            bubble.setStyleSheet(
                'background:#2a2c30;color:#6a7078;border:1px solid #3a3d42;'
                'border-radius:7px;padding:0 3px;font-size:9px;font-weight:700;'
            )
            bubble.mousePressEvent = (
                lambda e, k=key: self._on_sev_bubble_press(e, k)
            )
            bubble.mouseReleaseEvent = (
                lambda e, k=key: self._on_sev_bubble_release(e, k)
            )
            chip_row.addWidget(bubble)
            self._alarm_sev_count_bubbles[key] = bubble
        # wave32: sev 筛钉住
        self._alarm_sev_pinned = False
        self._alarm_sev_pinned_key = ''
        self._sev_bubble_pin_timer = QTimer(self)
        self._sev_bubble_pin_timer.setSingleShot(True)
        self._sev_bubble_pin_timer.timeout.connect(self._on_sev_bubble_long_press)
        self._sev_bubble_pin_key = None
        self._sev_bubble_long_fired = False
        self._sev_bubble_pin_ms = 550  # wave39: synced from chip ms below
        self._sev_bubble_pin_press_ms = 0
        self._sev_bubble_pin_tick = QTimer(self)
        self._sev_bubble_pin_tick.setInterval(40)
        self._sev_bubble_pin_tick.timeout.connect(self._on_sev_bubble_pin_tick)
        # wave40: bubble arc alias set after chip arc singleton created
        self._sev_bubble_pin_arc = None
        try:
            raw_pin = str(self._host_settings().value('host/alarmSevPinned', '') or '').strip().lower()
            if raw_pin in ('all', 'error', 'warning', 'info'):
                self._alarm_sev_pinned = True
                self._alarm_sev_pinned_key = raw_pin
                # align combo to pinned key (force)
                for i in range(self._alarm_sev_filter.count()):
                    if str(self._alarm_sev_filter.itemData(i) or '') == raw_pin:
                        self._alarm_sev_filter.setCurrentIndex(i)
                        break
        except Exception:
            pass
        chip_row.addStretch(1)
        # wave33: pin badge on sev chip row
        self._alarm_sev_pin_badge = QLabel('')
        self._alarm_sev_pin_badge.setObjectName('hostAlarmSevPinBadge')
        self._alarm_sev_pin_badge.setFixedHeight(18)
        self._alarm_sev_pin_badge.setMinimumWidth(18)
        self._alarm_sev_pin_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._alarm_sev_pin_badge.setCursor(Qt.CursorShape.PointingHandCursor)
        self._alarm_sev_pin_badge.setToolTip('钉住徽章 · 悬停见解钉 tip · 单击取消钉 · Alt+P')
        self._alarm_sev_pin_badge.setStyleSheet(
            'background:transparent;color:#f0c040;border:1px solid transparent;'
            'border-radius:3px;font-size:11px;font-weight:700;padding:0 3px;'
        )
        self._alarm_sev_pin_badge.mousePressEvent = (
            lambda e: self._on_sev_pin_badge_clicked(e)
        )
        self._alarm_sev_pin_badge.enterEvent = (
            lambda e: self._on_sev_pin_badge_enter(e)
        )
        self._alarm_sev_pin_badge.leaveEvent = (
            lambda e: self._on_sev_pin_badge_leave(e)
        )
        self._sev_pin_badge_pulse_on = False
        self._sev_pin_badge_pulse_timer = QTimer(self)
        self._sev_pin_badge_pulse_timer.setInterval(280)
        self._sev_pin_badge_pulse_timer.timeout.connect(self._on_sev_pin_badge_pulse)
        # wave35: 解钉确认 tip 驻留
        self._sev_pin_confirm_tip_timer = QTimer(self)
        self._sev_pin_confirm_tip_timer.setSingleShot(True)
        self._sev_pin_confirm_tip_timer.timeout.connect(self._hide_sev_pin_confirm_tip)
        self._sev_chip_hover_key = ''
        self._alarm_sev_pin_badge.hide()
        chip_row.addWidget(self._alarm_sev_pin_badge)
        chip_hint = QLabel('芯片')
        chip_hint.setStyleSheet(f'color:{TEXT_MUTED};font-size:10px;')
        chip_hint.setToolTip('严重度芯片 · 悬停预览 · 长按落钉 · Alt+P / Shift+Alt+P')
        chip_row.addWidget(chip_hint)
        lay.addLayout(chip_row)
        # wave33–36: Alt+P 钉住/切档 · Shift+Alt+P 回退切档
        try:
            self._sev_pin_shortcut = QShortcut(QKeySequence('Alt+P'), self)
            self._sev_pin_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            self._sev_pin_shortcut.activated.connect(self._on_sev_pin_hotkey)
        except Exception:
            self._sev_pin_shortcut = None
        try:
            self._sev_pin_back_shortcut = QShortcut(QKeySequence('Shift+Alt+P'), self)
            self._sev_pin_back_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            self._sev_pin_back_shortcut.activated.connect(
                lambda: self._on_sev_pin_hotkey(reverse=True)
            )
        except Exception:
            self._sev_pin_back_shortcut = None
        # wave36: Alt+H 容量菜单快捷键
        try:
            self._toast_hist_cap_shortcut = QShortcut(QKeySequence('Alt+H'), self)
            self._toast_hist_cap_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            self._toast_hist_cap_shortcut.activated.connect(self._on_toast_hist_cap_hotkey)
        except Exception:
            self._toast_hist_cap_shortcut = None
        # wave36–38: chip 长按落钉计时 + 进度弧（时长/色可配）
        self._sev_chip_pin_timer = QTimer(self)
        self._sev_chip_pin_timer.setSingleShot(True)
        self._sev_chip_pin_timer.timeout.connect(self._on_sev_chip_long_press)
        self._sev_chip_pin_key = None
        self._sev_chip_long_fired = False
        self._sev_chip_pin_ms = 550
        try:
            raw_ms = int(self._host_settings().value('host/sevChipPinMs', 550) or 550)
            if raw_ms not in (300, 550, 800):
                # clamp to nearest preset
                raw_ms = min((300, 550, 800), key=lambda x: abs(x - raw_ms))
            self._sev_chip_pin_ms = int(raw_ms)
        except Exception:
            self._sev_chip_pin_ms = 550
        self._sev_chip_pin_press_ms = 0
        self._sev_chip_pin_tick = QTimer(self)
        self._sev_chip_pin_tick.setInterval(40)
        self._sev_chip_pin_tick.timeout.connect(self._on_sev_chip_pin_tick)
        # wave40: 芯片/气泡共享进度弧单例
        self._sev_pin_arc = _SevChipPinProgressArc(self)
        self._sev_pin_arc.setObjectName('hostSevPinArc')
        self._sev_chip_pin_arc = self._sev_pin_arc  # alias
        self._sev_bubble_pin_arc = self._sev_pin_arc  # alias — 减双实例
        self._sev_pin_arc_owner = ''  # 'chip' | 'bubble'
        self._last_sev_pin_arc_seize = {}
        self._sev_pin_arc_seize_timer = None
        try:
            raw_sc = str(self._host_settings().value(
                'host/sevPinArcSeizeColor', '#ffffff') or '#ffffff').strip()
            if raw_sc and not raw_sc.startswith('#'):
                raw_sc = '#' + raw_sc
            self._sev_pin_arc_seize_color = raw_sc or '#ffffff'
        except Exception:
            self._sev_pin_arc_seize_color = '#ffffff'
        try:
            raw_ss = self._host_settings().value('host/sevPinArcSeizeSound', True)
            if isinstance(raw_ss, str):
                self._sev_pin_arc_seize_sound = raw_ss.strip().lower() not in (
                    '0', 'false', 'no', 'off')
            else:
                self._sev_pin_arc_seize_sound = bool(raw_ss)
        except Exception:
            self._sev_pin_arc_seize_sound = True
        # wave44: 最近自定义抢占色
        self._sev_pin_arc_seize_recent = []
        try:
            raw_rc = self._host_settings().value('host/sevPinArcSeizeRecentColors', [])
            if isinstance(raw_rc, str):
                raw_rc = [x for x in raw_rc.split(',') if x.strip()]
            self._sev_pin_arc_seize_recent = [
                (c if str(c).startswith('#') else '#' + str(c)).lower()
                for c in (raw_rc or []) if str(c).strip()
            ][:6]
        except Exception:
            self._sev_pin_arc_seize_recent = []
        # wave44: 保持退出 tip 可关（默认开）
        try:
            raw_ket = self._host_settings().value('host/toastHistCapKeepExitTip', True)
            if isinstance(raw_ket, str):
                self._toast_hist_cap_keep_exit_tip = raw_ket.strip().lower() not in (
                    '0', 'false', 'no', 'off')
            else:
                self._toast_hist_cap_keep_exit_tip = bool(raw_ket)
        except Exception:
            self._toast_hist_cap_keep_exit_tip = True
        # wave44: 中键父目录失败回退本级可配（默认开）
        try:
            raw_pf = self._host_settings().value('host/pathCopyBadgeParentFallback', True)
            if isinstance(raw_pf, str):
                self._path_copy_badge_parent_fallback = raw_pf.strip().lower() not in (
                    '0', 'false', 'no', 'off')
            else:
                self._path_copy_badge_parent_fallback = bool(raw_pf)
        except Exception:
            self._path_copy_badge_parent_fallback = True
        # wave47: tip 热更动画可关（默认开）
        try:
            raw_ta = self._host_settings().value('host/toastHistCapTipAnim', True)
            if isinstance(raw_ta, str):
                self._toast_hist_cap_tip_anim = raw_ta.strip().lower() not in (
                    '0', 'false', 'no', 'off')
            else:
                self._toast_hist_cap_tip_anim = bool(raw_ta)
        except Exception:
            self._toast_hist_cap_tip_anim = True
        # wave48: tip 动画时长可配（ms）
        try:
            self._toast_hist_cap_tip_anim_ms = int(
                self._host_settings().value('host/toastHistCapTipAnimMs', 320) or 320)
            self._toast_hist_cap_tip_anim_ms = max(
                80, min(2000, int(self._toast_hist_cap_tip_anim_ms)))
        except Exception:
            self._toast_hist_cap_tip_anim_ms = 320
        # wave49: tip 动画 easing 可配
        try:
            _ez = str(self._host_settings().value(
                'host/toastHistCapTipAnimEasing', 'OutCubic') or 'OutCubic').strip()
            if _ez not in ('OutCubic', 'InOutQuad', 'OutBounce', 'Linear'):
                _ez = 'OutCubic'
            self._toast_hist_cap_tip_anim_easing = _ez
        except Exception:
            self._toast_hist_cap_tip_anim_easing = 'OutCubic'
        # wave49: 失败历史排序 time|path
        try:
            _sm = str(self._host_settings().value(
                'host/mergeDiffBatchFailHistorySort', 'time') or 'time').strip().lower()
            self._merge_diff_batch_fail_history_sort = (
                _sm if _sm in ('time', 'path') else 'time')
        except Exception:
            self._merge_diff_batch_fail_history_sort = 'time'
        # wave48: undo 延长步进（0=重置为全长，兼容㊼）
        try:
            self._stale_prune_undo_extend_step_ms = int(
                self._host_settings().value('host/stalePruneUndoExtendStepMs', 0) or 0)
            self._stale_prune_undo_extend_step_ms = max(
                0, min(30000, int(self._stale_prune_undo_extend_step_ms)))
        except Exception:
            self._stale_prune_undo_extend_step_ms = 0
        # wave52–53: undo 色阶预设 traffic|cool|mono|sunset|custom
        try:
            _cs = str(self._host_settings().value(
                'host/stalePruneUndoColorScale', 'traffic') or 'traffic').strip().lower()
            if _cs not in ('traffic', 'cool', 'mono', 'sunset', 'custom'):
                _cs = 'traffic'
            self._stale_prune_undo_color_scale = _cs
        except Exception:
            self._stale_prune_undo_color_scale = 'traffic'
        # wave53: custom RGB hi/mid/lo
        try:
            self._stale_prune_undo_color_custom = {
                'hi': str(self._host_settings().value(
                    'host/stalePruneUndoColorCustomHi', '#3ecf8e') or '#3ecf8e'),
                'mid': str(self._host_settings().value(
                    'host/stalePruneUndoColorCustomMid', '#f0c040') or '#f0c040'),
                'lo': str(self._host_settings().value(
                    'host/stalePruneUndoColorCustomLo', '#e35d6a') or '#e35d6a'),
            }
        except Exception:
            self._stale_prune_undo_color_custom = {
                'hi': '#3ecf8e', 'mid': '#f0c040', 'lo': '#e35d6a'}
        # wave53: 徽章清历史撤销倒计时
        self._path_copy_badge_fail_history_undo_left_ms = 0
        self._path_copy_badge_fail_history_undo_ms = 8000
        self._path_copy_badge_fail_history_can_undo = False
        self._path_copy_badge_fail_history_undo = None
        self._path_copy_badge_fail_hist_undo_timer = QTimer(self)
        self._path_copy_badge_fail_hist_undo_timer.setInterval(250)
        self._path_copy_badge_fail_hist_undo_timer.timeout.connect(
            self._on_path_copy_badge_fail_history_undo_tick)
        # wave47: 失败清单持久化 / 历史
        self._merge_diff_batch_fail_history = []
        self._last_merge_diff_batch_fail = []
        try:
            raw_fh = self._host_settings().value('host/mergeDiffBatchFailHistory', [])
            hist = []
            if isinstance(raw_fh, str):
                import json as _json
                try:
                    raw_fh = _json.loads(raw_fh) if raw_fh.strip() else []
                except Exception:
                    raw_fh = []
            for ent in list(raw_fh or [])[:24]:
                if isinstance(ent, dict):
                    paths = [str(x).strip() for x in (ent.get('paths') or []) if str(x).strip()]
                    if paths:
                        hist.append({
                            'ts': str(ent.get('ts') or ''),
                            'paths': paths[:48],
                        })
                elif isinstance(ent, (list, tuple)):
                    paths = [str(x).strip() for x in ent if str(x).strip()]
                    if paths:
                        hist.append({'ts': '', 'paths': paths[:48]})
            self._merge_diff_batch_fail_history = hist[:20]
            if hist:
                self._last_merge_diff_batch_fail = list(hist[0].get('paths') or [])
        except Exception:
            self._merge_diff_batch_fail_history = []
        try:
            raw_lf = self._host_settings().value('host/mergeDiffBatchFailLast', [])
            if isinstance(raw_lf, str):
                raw_lf = [x for x in raw_lf.split('\n') if x.strip()] if raw_lf else []
            last = [str(x).strip() for x in (raw_lf or []) if str(x).strip()]
            if last:
                self._last_merge_diff_batch_fail = last[:48]
        except Exception:
            pass
        self._stale_prune_can_undo = False
        self._stale_prune_undo_dirs = []
        self._stale_prune_undo_ms = 8000
        self._stale_prune_undo_left_ms = 0
        self._stale_prune_undo_timer = QTimer(self)
        self._stale_prune_undo_timer.setInterval(250)
        self._stale_prune_undo_timer.timeout.connect(self._on_stale_prune_undo_tick)
        self._last_merge_stats = {}
        self._last_merge_diff = {}
        try:
            raw_c = str(self._host_settings().value('host/sevChipPinArcColor', '#f0c040') or '#f0c040').strip()
            if raw_c and not raw_c.startswith('#'):
                raw_c = '#' + raw_c
            self._sev_pin_arc.set_color(raw_c or '#f0c040')
        except Exception:
            pass
        # wave39–40: 气泡长按与芯片同色/时长（共享弧）
        try:
            self._sev_bubble_pin_ms = int(self._sev_chip_pin_ms)
        except Exception:
            pass
        self._host_toast_click_action = 'open'  # wave38: open | review
        self._host_toast_review_path = ''
        # wave39: 路径回看复制确认徽章
        self._path_copy_badge = QLabel('', self)
        self._path_copy_badge.setObjectName('hostPathCopyBadge')
        self._path_copy_badge.setFixedHeight(20)
        self._path_copy_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._path_copy_badge.setCursor(Qt.CursorShape.PointingHandCursor)
        self._path_copy_badge.setToolTip('左键打开 · 右键菜单 · 中键父目录')
        self._path_copy_badge.setStyleSheet(
            'background:#1c3a2a;color:#9ed9a8;border:1px solid #3ecf8e;'
            'border-radius:3px;padding:1px 8px;font-size:10px;font-weight:700;'
        )
        self._path_copy_badge.hide()
        self._path_copy_badge_path = ''
        self._path_copy_badge.mousePressEvent = (
            lambda e: self._on_path_copy_badge_clicked(e)
        )
        # wave43: 失效清理 undo 倒计时进度条
        self._stale_prune_undo_bar = QProgressBar(self)
        self._stale_prune_undo_bar.setObjectName('hostStalePruneUndoBar')
        self._stale_prune_undo_bar.setFixedHeight(10)
        self._stale_prune_undo_bar.setTextVisible(False)
        self._stale_prune_undo_bar.setRange(0, 1000)
        self._stale_prune_undo_bar.setValue(0)
        self._stale_prune_undo_bar.setCursor(Qt.CursorShape.PointingHandCursor)
        self._stale_prune_undo_bar.setToolTip(
            '左键撤销 · 中键延长 · 右键步进预设（±1s/±3s）')
        self._stale_prune_undo_bar.setStyleSheet(
            'QProgressBar{background:#2a2d32;border:1px solid #3a3d42;'
            'border-radius:2px;}'
            'QProgressBar::chunk{background:#f0c040;border-radius:2px;}'
        )
        self._stale_prune_undo_bar.hide()
        # wave44: 进度条可点撤销
        self._stale_prune_undo_bar.mousePressEvent = (
            lambda e: self._on_stale_prune_undo_bar_clicked(e)
        )
        # wave45: 悬停放大
        self._stale_prune_undo_bar_base_h = 10
        self._stale_prune_undo_bar_hover_h = 16
        self._stale_prune_undo_bar_hovered = False
        self._stale_prune_undo_bar.enterEvent = (
            lambda e: self._on_stale_prune_undo_bar_enter(e)
        )
        self._stale_prune_undo_bar.leaveEvent = (
            lambda e: self._on_stale_prune_undo_bar_leave(e)
        )
        self._path_copy_badge_timer = QTimer(self)
        self._path_copy_badge_timer.setSingleShot(True)
        self._path_copy_badge_timer.timeout.connect(self._hide_path_copy_badge)
        # wave40: Alt+H 长按 H 保持菜单不关
        self._toast_hist_cap_keep_open = False
        self._toast_hist_cap_hold_timer = QTimer(self)
        self._toast_hist_cap_hold_timer.setSingleShot(True)
        self._toast_hist_cap_hold_timer.setInterval(450)
        self._toast_hist_cap_hold_timer.timeout.connect(self._on_toast_hist_cap_hold_fire)
        self._toast_hist_cap_h_down = False
        # wave37: 多档另存上限可配
        self._alarm_film_csv_dirs_max = 5
        try:
            raw_dm = int(self._host_settings().value('host/alarmFilmCsvDirsMax', 5) or 5)
            self._alarm_film_csv_dirs_max = max(3, min(8, raw_dm))
        except Exception:
            self._alarm_film_csv_dirs_max = 5
        self._sync_alarm_sev_chips()
        self._alarm_list = QListWidget()
        self._alarm_list.setObjectName('hostAlarmHistoryList')
        self._alarm_list.setStyleSheet('font-size:11px;')
        self._alarm_list.setToolTip('双击或右键：若带胶片 path 则定位胶片')
        self._alarm_list.itemDoubleClicked.connect(self._on_alarm_item_double_clicked)
        self._alarm_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._alarm_list.customContextMenuRequested.connect(self._on_alarm_list_context_menu)
        lay.addWidget(self._alarm_list, 1)
        row = QHBoxLayout()
        b_clear = QPushButton('清空历史')
        b_clear.setObjectName('hostAlarmHistoryClearBtn')
        b_clear.clicked.connect(self.clear_alarm_history)
        row.addWidget(b_clear)
        b_copy = QPushButton('复制CSV')
        b_copy.setObjectName('hostAlarmHistoryCopyBtn')
        b_copy.setToolTip('复制报警历史为 CSV 到剪贴板')
        b_copy.clicked.connect(self.export_alarm_history_clipboard)
        row.addWidget(b_copy)
        b_save = QPushButton('导出…')
        b_save.setObjectName('hostAlarmHistoryExportBtn')
        b_save.setToolTip('导出报警历史 CSV 文件')
        b_save.clicked.connect(self.export_alarm_history_file)
        row.addWidget(b_save)
        # wave24: 联调 CSV 时段过滤
        row.addWidget(QLabel('联调时段'))
        self._liaison_window = QComboBox()
        self._liaison_window.setObjectName('hostLiaisonWindow')
        self._liaison_window.setToolTip('导出/复制联调 CSV 的时段窗口（持久）')
        for lab, sec in (
            ('全部', 0), ('近5分', 300), ('近15分', 900), ('近1时', 3600), ('近24时', 86400),
        ):
            self._liaison_window.addItem(lab, sec)
        self._liaison_window.setMaximumWidth(88)
        # wave25: 联调时段持久
        try:
            saved = int(self._host_settings().value('host/liaisonWindowSec', 0) or 0)
        except (TypeError, ValueError):
            saved = 0
        idx = 0
        for i in range(self._liaison_window.count()):
            if int(self._liaison_window.itemData(i) or 0) == saved:
                idx = i
                break
        self._liaison_window.setCurrentIndex(idx)
        self._liaison_window.currentIndexChanged.connect(self._on_liaison_window_changed)
        row.addWidget(self._liaison_window)
        # wave26: 联调时段徽章
        self._liaison_window_badge = QLabel('')
        self._liaison_window_badge.setObjectName('hostLiaisonWindowBadge')
        self._liaison_window_badge.setStyleSheet(
            'background:#1c2a3a;color:#9ec9f0;border:1px solid #3a5a7a;'
            'border-radius:3px;padding:2px 6px;font-size:10px;font-weight:700;'
        )
        self._liaison_window_badge.setCursor(Qt.CursorShape.PointingHandCursor)
        self._liaison_window_badge.setToolTip('单击循环切换联调时段')
        self._liaison_window_badge.mousePressEvent = lambda e: self._on_liaison_badge_clicked(e)
        row.addWidget(self._liaison_window_badge)
        self._sync_liaison_window_badge()
        # wave28: 联调切窗快捷键 Alt+L
        # wave29: Alt+L 全局态提示 — overlay on host (not tab-bound)
        # wave30: toast 历史条（最近 N 次切窗）
        self._liaison_toast_history = []
        # wave34: 容量可配（3–12，默认 5）
        self._liaison_toast_history_max = 5
        try:
            raw_cap = int(self._host_settings().value('host/liaisonToastHistMax', 5) or 5)
            self._liaison_toast_history_max = max(3, min(12, raw_cap))
        except Exception:
            self._liaison_toast_history_max = 5
        self._liaison_hotkey_toast = QLabel(self)
        self._liaison_hotkey_toast.setObjectName('hostLiaisonHotkeyToast')
        self._liaison_hotkey_toast.setStyleSheet(
            'background:#1c3a2a;color:#9ed9a8;border:1px solid #3ecf8e;'
            'border-radius:3px;padding:4px 10px;font-size:11px;font-weight:700;'
        )
        self._liaison_hotkey_toast.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._liaison_hotkey_toast.setCursor(Qt.CursorShape.ArrowCursor)
        self._liaison_hotkey_toast.mousePressEvent = (
            lambda e: self._on_host_toast_clicked(e)
        )
        self._host_toast_open_path = ''
        self._liaison_hotkey_toast.hide()
        self._liaison_toast_history_bar = QLabel(self)
        self._liaison_toast_history_bar.setObjectName('hostLiaisonToastHistory')
        self._liaison_toast_history_bar.setStyleSheet(
            'background:#1c2a3a;color:#9ec9f0;border:1px solid #3a5a7a;'
            'border-radius:3px;padding:2px 8px;font-size:10px;font-weight:600;'
        )
        self._liaison_toast_history_bar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._liaison_toast_history_bar.setCursor(Qt.CursorShape.PointingHandCursor)
        self._liaison_toast_history_bar.setToolTip(
            f'单击回切 · 右键/Alt+H 容量菜单 · 中键循环（当前 {self._liaison_toast_history_max}）'
        )
        self._liaison_toast_history_bar.mousePressEvent = (
            lambda e: self._on_liaison_toast_history_clicked(e)
        )
        self._liaison_toast_history_bar.hide()
        # wave31: parallel sec list for click-restore
        self._liaison_toast_history_secs = []
        try:
            self._liaison_cycle_shortcut = QShortcut(QKeySequence('Alt+L'), self)
            self._liaison_cycle_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            self._liaison_cycle_shortcut.activated.connect(self._on_liaison_hotkey)
            self._liaison_window.setToolTip(
                (self._liaison_window.toolTip() or '联调 CSV 时段') + ' · Alt+L 循环'
            )
            self._liaison_window_badge.setToolTip(
                (self._liaison_window_badge.toolTip() or '') + ' · Alt+L'
            )
        except Exception:
            self._liaison_cycle_shortcut = None
        b_lia_copy = QPushButton('复制联调CSV')
        b_lia_copy.setObjectName('hostLiaisonCopyBtn')
        b_lia_copy.setToolTip('复制联调条事件为 CSV 到剪贴板（按时段）')
        b_lia_copy.clicked.connect(self.export_liaison_clipboard)
        row.addWidget(b_lia_copy)
        b_lia_save = QPushButton('导出联调…')
        b_lia_save.setObjectName('hostLiaisonExportBtn')
        b_lia_save.setToolTip('导出联调条事件 CSV 文件（按时段）')
        b_lia_save.clicked.connect(self.export_liaison_file)
        row.addWidget(b_lia_save)
        self._alarm_hist_count = QLabel('0 条')
        self._alarm_hist_count.setStyleSheet(f'color:{TEXT_MUTED};font-size:11px;')
        row.addWidget(self._alarm_hist_count)
        row.addStretch(1)
        lay.addLayout(row)
        return w

    def alarm_history(self):
        """Public snapshot for smoke / HMI."""
        return list(self._alarm_history)

    def alarm_history_csv(self) -> str:
        """CSV text for clipboard / file export."""
        lines = ['timestamp,cleared,cleared_at,severity,reason']
        for e in self._alarm_history:
            ts = str(e.get('ts') or '').replace(',', ' ')
            cleared = '1' if e.get('cleared') else '0'
            cleared_at = str(e.get('cleared_at') or '').replace(',', ' ')
            sev = str(e.get('severity') or 'info')
            reason = str(e.get('reason') or '').replace('"', "'").replace('\n', ' ')
            lines.append(f'{ts},{cleared},{cleared_at},{sev},"{reason}"')
        return '\n'.join(lines) + ('\n' if lines else '')

    def export_alarm_history_clipboard(self):
        csv = self.alarm_history_csv()
        try:
            QApplication.clipboard().setText(csv)
            self._log_line(f'报警历史已复制 CSV · {len(self._alarm_history)} 条')
        except Exception as err:
            self._log_line(f'复制失败：{err}')

    def export_alarm_history_file(self):
        path, _ = QFileDialog.getSaveFileName(
            self, '导出报警历史', 'alarm-history.csv', 'CSV (*.csv);;All (*)')
        if not path:
            return
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(self.alarm_history_csv())
            self._log_line(f'报警历史已导出 · {path}')
        except Exception as err:
            self._log_line(f'导出失败：{err}')


    @staticmethod
    def _liaison_severity(kind: str = '', code: str = '') -> str:
        """wave24: info|warn|error|ok for flash / CSV."""
        code_u = str(code or '').upper()
        kind_s = str(kind or '')
        if any(x in code_u for x in (
            'FAIL', 'ERROR', 'EMPTY', 'MISSING', 'VARIANT_', 'APPLY_', 'ENTER_',
        )) or '失败' in kind_s:
            return 'error'
        if 'CLEAR' in code_u or '清除' in kind_s or kind_s in ('试跑清除', '报警清除'):
            return 'ok'
        if 'TRIAL' in code_u or '试跑' in kind_s or '换型' in kind_s:
            return 'warn'
        return 'info'

    def liaison_window_sec(self) -> int:
        """wave24: 0=全部; else last N seconds."""
        combo = getattr(self, '_liaison_window', None)
        if combo is None:
            return 0
        try:
            return int(combo.currentData() or 0)
        except Exception:
            return 0

    @staticmethod
    def _host_settings():
        return QSettings('SIEANS', 'VisionDesktop')

    def _save_liaison_window_pref(self, sec: int):
        try:
            self._host_settings().setValue('host/liaisonWindowSec', int(sec or 0))
        except Exception:
            pass

    def _on_liaison_window_changed(self, *_):
        try:
            self._save_liaison_window_pref(self.liaison_window_sec())
        except Exception:
            pass
        try:
            self._sync_liaison_window_badge()
        except Exception:
            pass

    def _sync_liaison_window_badge(self):
        """wave26: 联调时段徽章文案."""
        badge = getattr(self, '_liaison_window_badge', None)
        if badge is None:
            return
        sec = self.liaison_window_sec()
        combo = getattr(self, '_liaison_window', None)
        lab = ''
        if combo is not None:
            try:
                lab = combo.currentText() or ''
            except Exception:
                lab = ''
        if not lab:
            if sec <= 0:
                lab = '全部'
            elif sec < 3600:
                lab = f'近{sec // 60}分'
            else:
                lab = f'近{sec // 3600}时'
        badge.setText(f'⏱ {lab}')
        base_tip = f'联调 CSV 时段：{lab}（{sec}s）' if sec else f'联调 CSV 时段：{lab}'
        badge.setToolTip(base_tip + ' · 单击循环切换')
        if sec <= 0:
            badge.setStyleSheet(
                'background:#2a2c30;color:#9aa0a6;border:1px solid #3a3d42;'
                'border-radius:3px;padding:2px 6px;font-size:10px;font-weight:600;'
            )
        else:
            badge.setStyleSheet(
                'background:#1c2a3a;color:#9ec9f0;border:1px solid #6eb6ff;'
                'border-radius:3px;padding:2px 6px;font-size:10px;font-weight:700;'
            )

    def _on_liaison_badge_clicked(self, event=None):
        """wave27: 联调徽章单击循环切窗."""
        try:
            if event is not None and hasattr(event, 'button'):
                if event.button() not in (Qt.MouseButton.LeftButton,):
                    return
        except Exception:
            pass
        return self.cycle_liaison_window()

    def cycle_liaison_window(self, *, from_hotkey: bool = False) -> int:
        """wave27–29: 循环全部→5分→15分→1时→24时→全部（徽章/Alt+L）；返回新 sec."""
        combo = getattr(self, '_liaison_window', None)
        if combo is None or combo.count() <= 0:
            return self.liaison_window_sec()
        nxt = (combo.currentIndex() + 1) % combo.count()
        combo.setCurrentIndex(nxt)
        sec = self.liaison_window_sec()
        lab = ''
        try:
            lab = combo.currentText() or ''
        except Exception:
            lab = ''
        try:
            src = 'Alt+L' if from_hotkey else '徽章'
            self._log_line(f'联调{src}切窗 · {lab}')
        except Exception:
            pass
        if from_hotkey:
            try:
                self._flash_liaison_hotkey_toast(lab or str(sec))
            except Exception:
                pass
        return sec

    def _on_liaison_hotkey(self):
        """wave29: Alt+L → 切窗 + 全局态提示."""
        self.cycle_liaison_window(from_hotkey=True)

    def _flash_liaison_hotkey_toast(self, lab: str = ''):
        """wave29–30: Alt+L 全局态短提示 + 历史条."""
        toast = getattr(self, '_liaison_hotkey_toast', None)
        if toast is None:
            return
        lab = (lab or '').strip()
        # wave30: push history
        hist = getattr(self, '_liaison_toast_history', None)
        if hist is None:
            self._liaison_toast_history = []
            hist = self._liaison_toast_history
        if lab:
            hist.append(lab)
            secs = getattr(self, '_liaison_toast_history_secs', None)
            if secs is None:
                self._liaison_toast_history_secs = []
                secs = self._liaison_toast_history_secs
            try:
                secs.append(int(self.liaison_window_sec()))
            except Exception:
                secs.append(0)
            max_n = int(getattr(self, '_liaison_toast_history_max', 5) or 5)
            if len(hist) > max_n:
                del hist[:-max_n]
            if len(secs) > max_n:
                del secs[:-max_n]
        text = f'Alt+L · 联调 {lab}'.strip()
        toast.setText(text)
        toast.setToolTip(text)
        toast.adjustSize()
        try:
            tw = max(toast.sizeHint().width() + 8, 160)
            th = max(toast.sizeHint().height() + 4, 22)
            x = max(8, (self.width() - tw) // 2)
            toast.setGeometry(x, 8, tw, th)
        except Exception:
            tw = 160
            th = 22
            x = 8
        toast.raise_()
        toast.show()
        # history bar under toast
        hbar = getattr(self, '_liaison_toast_history_bar', None)
        if hbar is not None and hist:
            # newest last: show oldest → newest with arrows
            htext = ' → '.join(hist)
            hbar.setText(f'切窗史 · {htext}')
            max_n = int(getattr(self, '_liaison_toast_history_max', 5) or 5)
            hbar.setToolTip(
                f'容量 {len(hist)}/{max_n} · 单击回切 · 右键/Alt+H 容量菜单 · 中键循环'
            )
            hbar.adjustSize()
            try:
                hw = max(hbar.sizeHint().width() + 8, tw)
                hh = max(hbar.sizeHint().height() + 2, 18)
                hx = max(8, (self.width() - hw) // 2)
                hbar.setGeometry(hx, 8 + th + 4, hw, hh)
            except Exception:
                pass
            hbar.raise_()
            hbar.show()
        try:
            self.setStatusTip(text)
            self.setToolTip(f'Host SM · {text}')
        except Exception:
            pass
        timer = getattr(self, '_liaison_hotkey_toast_timer', None)
        if timer is None:
            timer = QTimer(self)
            timer.setSingleShot(True)
            timer.timeout.connect(self._hide_liaison_hotkey_toast)
            self._liaison_hotkey_toast_timer = timer
        timer.start(2200)

    def _hide_liaison_hotkey_toast(self):
        toast = getattr(self, '_liaison_hotkey_toast', None)
        if toast is not None:
            toast.hide()
            try:
                toast.setCursor(Qt.CursorShape.ArrowCursor)
            except Exception:
                pass
        self._host_toast_open_path = ''
        hbar = getattr(self, '_liaison_toast_history_bar', None)
        if hbar is not None:
            hbar.hide()

    def liaison_toast_history(self):
        """wave30: 最近 N 次 Alt+L 切窗标签."""
        return list(getattr(self, '_liaison_toast_history', None) or [])

    def liaison_toast_history_capacity(self) -> tuple:
        """wave33: (used, max) for toast hist capacity tip."""
        used = len(getattr(self, '_liaison_toast_history', None) or [])
        max_n = int(getattr(self, '_liaison_toast_history_max', 5) or 5)
        return (used, max_n)

    def set_liaison_toast_history_max(self, n: int, *, persist: bool = True) -> int:
        """wave34: 配置 toast 切窗史容量（3–12）."""
        n = max(3, min(12, int(n or 5)))
        self._liaison_toast_history_max = n
        hist = getattr(self, '_liaison_toast_history', None)
        secs = getattr(self, '_liaison_toast_history_secs', None)
        if hist is not None and len(hist) > n:
            del hist[:-n]
        if secs is not None and len(secs) > n:
            del secs[:-n]
        if persist:
            try:
                self._host_settings().setValue('host/liaisonToastHistMax', n)
            except Exception:
                pass
        hbar = getattr(self, '_liaison_toast_history_bar', None)
        if hbar is not None:
            used = len(hist or [])
            try:
                hbar.setToolTip(
                    f'容量 {used}/{n} · 单击回切 · 右键/Alt+H 容量菜单 · 中键循环'
                )
            except Exception:
                pass
        return n

    def cycle_liaison_toast_history_max(self) -> int:
        """wave34: 中键循环容量 3/5/8/12."""
        presets = (3, 5, 8, 12)
        cur = int(getattr(self, '_liaison_toast_history_max', 5) or 5)
        try:
            nxt = presets[(presets.index(cur) + 1) % len(presets)]
        except ValueError:
            nxt = 5
        return self.set_liaison_toast_history_max(nxt)

    def _flash_host_toast(
        self, text: str = '', *, ms: int = 1800, kind: str = 'ok',
        open_path: str = '', animate: bool = False,
    ) -> bool:
        """wave34–46: 通用主机短 toast；open_path 时单击开目录；animate 淡入脉冲."""
        toast = getattr(self, '_liaison_hotkey_toast', None)
        if toast is None:
            return False
        text = (text or '').strip()
        if not text:
            return False
        styles = {
            'ok': (
                'background:#1c3a2a;color:#9ed9a8;border:1px solid #3ecf8e;'
                'border-radius:3px;padding:4px 10px;font-size:11px;font-weight:700;'
            ),
            'pin': (
                'background:#3a3420;color:#f0c040;border:1px solid #f0c040;'
                'border-radius:3px;padding:4px 10px;font-size:11px;font-weight:700;'
            ),
            'info': (
                'background:#1c2a3a;color:#9ec9f0;border:1px solid #3a5a7a;'
                'border-radius:3px;padding:4px 10px;font-size:11px;font-weight:700;'
            ),
            'csv': (
                'background:#1c3a2a;color:#9ed9a8;border:1px solid #3ecf8e;'
                'border-radius:3px;padding:4px 10px;font-size:11px;font-weight:700;'
                'text-decoration:underline;'
            ),
        }
        path = (open_path or '').strip()
        self._host_toast_open_path = path
        tip = text
        if path:
            tip = f'{text} · 单击打开目录'
            try:
                toast.setCursor(Qt.CursorShape.PointingHandCursor)
            except Exception:
                pass
            if kind == 'ok':
                kind = 'csv'
        else:
            try:
                toast.setCursor(Qt.CursorShape.ArrowCursor)
            except Exception:
                pass
        try:
            toast.setStyleSheet(styles.get(kind, styles['ok']))
            toast.setText(text)
            toast.setToolTip(tip)
            toast.adjustSize()
            tw = max(toast.sizeHint().width() + 8, 140)
            th = max(toast.sizeHint().height() + 4, 22)
            x = max(8, (self.width() - tw) // 2)
            toast.setGeometry(x, 8, tw, th)
            toast.raise_()
            toast.show()
        except Exception:
            return False
        timer = getattr(self, '_liaison_hotkey_toast_timer', None)
        if timer is None:
            timer = QTimer(self)
            timer.setSingleShot(True)
            timer.timeout.connect(self._hide_liaison_hotkey_toast)
            self._liaison_hotkey_toast_timer = timer
        timer.start(int(ms or 1800))
        if animate:
            try:
                self._pulse_host_toast()
            except Exception:
                pass
        return True

    def _pulse_host_toast(self, duration_ms: int = None) -> bool:
        """wave46–48: tip 热更脉冲；可关；时长可配."""
        if not self.toast_hist_cap_tip_anim_enabled():
            self._last_host_toast_pulsed = False
            self._last_host_toast_pulse_skipped = True
            return False
        toast = getattr(self, '_liaison_hotkey_toast', None)
        if toast is None or toast.isHidden():
            return False
        self._last_host_toast_pulse_skipped = False
        if duration_ms is None:
            duration_ms = self.toast_hist_cap_tip_anim_ms()
        try:
            eff = getattr(self, '_host_toast_opacity_eff', None)
            if eff is None or eff.parent() is not toast:
                eff = QGraphicsOpacityEffect(toast)
                toast.setGraphicsEffect(eff)
                self._host_toast_opacity_eff = eff
            anim = QPropertyAnimation(eff, b'opacity', self)
            anim.setDuration(max(80, int(duration_ms or 320)))
            anim.setStartValue(0.22)
            anim.setKeyValueAt(0.45, 1.0)
            anim.setEndValue(1.0)
            anim.setEasingCurve(self._toast_tip_anim_easing_curve())
            # keep ref so GC won't kill mid-run
            self._host_toast_pulse_anim = anim
            anim.start()
            self._last_host_toast_pulsed = True
            return True
        except Exception:
            self._last_host_toast_pulsed = False
            return False

    def _flash_open_dir_fail_tip(self, reason: str = ''):
        """wave36: 开目录失败 tip / toast."""
        msg = f'打开目录失败' + (f' · {reason}' if reason else '')
        try:
            self._flash_host_toast(msg, kind='info', ms=2400)
        except Exception:
            pass
        try:
            self._log_line(msg)
        except Exception:
            pass
        toast = getattr(self, '_liaison_hotkey_toast', None)
        if toast is not None:
            try:
                QToolTip.showText(
                    toast.mapToGlobal(QPoint(0, toast.height())),
                    msg,
                    toast,
                    toast.rect(),
                    2400,
                )
            except Exception:
                try:
                    QToolTip.showText(
                        toast.mapToGlobal(QPoint(0, toast.height())),
                        msg,
                        toast,
                    )
                except Exception:
                    pass

    def _flash_open_dir_ok_tip(self, directory: str = '', *, soft: bool = False):
        """wave37–38: 开目录成功 tip；绑定路径，可点回看."""
        directory = str(directory or '').strip()
        try:
            from pathlib import Path as _P
            name = _P(directory).name or str(directory)
        except Exception:
            name = str(directory or '')
        if soft:
            msg = f'目录已就绪 · {name}（系统未打开）· 单击回看路径'
            kind = 'info'
        else:
            msg = f'已打开目录 · {name} · 单击回看路径'
            kind = 'ok'
        self._host_toast_review_path = directory
        self._host_toast_click_action = 'review' if directory else 'open'
        try:
            self._flash_host_toast(msg, kind=kind, ms=2800, open_path=directory)
        except Exception:
            pass
        try:
            self._log_line(msg)
        except Exception:
            pass
        toast = getattr(self, '_liaison_hotkey_toast', None)
        if toast is not None:
            try:
                tip = f'{msg}\n{directory}' if directory else msg
                QToolTip.showText(
                    toast.mapToGlobal(QPoint(0, toast.height())),
                    tip,
                    toast,
                    toast.rect(),
                    2800,
                )
            except Exception:
                pass

    def review_host_toast_path(self) -> str:
        """wave38: 回看 toast 绑定路径（全路径 tip）；返回路径."""
        path = str(
            getattr(self, '_host_toast_review_path', '')
            or getattr(self, '_host_toast_open_path', '')
            or ''
        ).strip()
        if not path:
            try:
                self._flash_host_toast('无绑定路径可回看', kind='info', ms=1600)
            except Exception:
                pass
            return ''
        short = path if len(path) <= 64 else ('…' + path[-60:])
        msg = f'路径回看 · {short}'
        # after review, next click opens
        self._host_toast_click_action = 'open'
        self._host_toast_open_path = path
        self._host_toast_review_path = path
        try:
            self._flash_host_toast(msg, kind='info', ms=3200, open_path=path)
            self._log_line(f'路径回看 · {path}')
        except Exception:
            pass
        toast = getattr(self, '_liaison_hotkey_toast', None)
        if toast is not None:
            try:
                QToolTip.showText(
                    toast.mapToGlobal(QPoint(0, toast.height())),
                    path,
                    toast,
                    toast.rect(),
                    3200,
                )
            except Exception:
                pass
        # clipboard for convenience + wave39 复制确认徽章
        copied = False
        try:
            clip = QApplication.clipboard()
            if clip is not None:
                clip.setText(path)
                copied = True
        except Exception:
            copied = False
        if copied:
            try:
                self.flash_path_copy_badge(path)
            except Exception:
                pass
        return path

    def flash_path_copy_badge(self, path: str = '', *, ms: int = 1800) -> bool:
        """wave39–40: 路径回看复制确认徽章「✓ 已复制」；再点打开目录."""
        badge = getattr(self, '_path_copy_badge', None)
        path = str(path or '').strip()
        self._path_copy_badge_path = path
        if path:
            self._host_toast_open_path = path
        if badge is None:
            try:
                self._flash_host_toast('✓ 已复制路径', kind='ok', ms=ms, open_path=path)
            except Exception:
                pass
            return False
        short = ''
        try:
            from pathlib import Path as _P
            short = _P(path).name if path else ''
        except Exception:
            short = ''
        text = '✓ 已复制' + (f' · {short}' if short else '路径') + ' · 再点打开'
        try:
            badge.setText(text)
            badge.setToolTip(f'{path}\n左键打开 · 右键菜单(再复制/回退) · 中键父目录' if path else '左键打开 · 右键菜单 · 中键父目录')
            badge.adjustSize()
            bw = max(badge.sizeHint().width() + 10, 88)
            bh = max(badge.sizeHint().height() + 2, 20)
            toast = getattr(self, '_liaison_hotkey_toast', None)
            if toast is not None and toast.isVisible():
                gx = toast.x() + max(0, (toast.width() - bw) // 2)
                gy = toast.y() + toast.height() + 4
            else:
                gx = max(8, (self.width() - bw) // 2)
                gy = 36
            badge.setGeometry(gx, gy, bw, bh)
            badge.raise_()
            badge.show()
        except Exception:
            return False
        timer = getattr(self, '_path_copy_badge_timer', None)
        if timer is not None:
            # longer stay so user can click
            timer.start(max(int(ms or 1800), 3200))
        self._last_path_copy_badge_text = text
        try:
            self._log_line(text)
        except Exception:
            pass
        return True

    def _path_copy_badge_menu_icon(self, kind: str = 'copy') -> QIcon:
        """wave47: 徽章菜单标准图标."""
        try:
            style = self.style()
            sp = style.StandardPixmap
            if kind == 'fallback':
                return style.standardIcon(sp.SP_ArrowBack)
            if kind == 'history':
                return style.standardIcon(sp.SP_FileDialogDetailedView)
            if kind == 'clear':
                return style.standardIcon(sp.SP_DialogResetButton)
            return style.standardIcon(sp.SP_FileDialogContentsView)
        except Exception:
            return QIcon()

    def _path_copy_badge_fail_history_icon(self, count: int = 0) -> QIcon:
        """wave50: 失败历史图标；count>0 叠加红点，零时无红点."""
        base = self._path_copy_badge_menu_icon('history')
        try:
            count = int(count or 0)
        except Exception:
            count = 0
        if count <= 0:
            self._last_path_copy_badge_fail_history_red_dot = False
            return base
        try:
            pm = base.pixmap(16, 16)
            if pm.isNull():
                pm = QPixmap(16, 16)
                pm.fill(QColor(0, 0, 0, 0))
            else:
                pm = pm.copy()
            painter = QPainter(pm)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setBrush(QColor('#e35d6a'))
            painter.setPen(QPen(QColor('#3a1c1c'), 1))
            painter.drawEllipse(9, 0, 7, 7)
            painter.end()
            self._last_path_copy_badge_fail_history_red_dot = True
            return QIcon(pm)
        except Exception:
            self._last_path_copy_badge_fail_history_red_dot = False
            return base

    def _build_path_copy_badge_menu(self, parent=None):
        """wave45–47: 徽章菜单 · 再复制 + 中键回退开关 + 图标."""
        menu = QMenu(parent or self)
        menu.setObjectName('hostPathCopyBadgeMenu')
        act_copy = QAction('再复制路径', menu)
        act_copy.setProperty('isPathCopyBadgeCopy', True)
        act_copy.setObjectName('hostPathCopyBadgeCopyAct')
        try:
            act_copy.setIcon(self._path_copy_badge_menu_icon('copy'))
            act_copy.setIconVisibleInMenu(True)
        except Exception:
            pass
        try:
            act_copy.setShortcut(QKeySequence('C'))
            act_copy.setShortcutVisibleInContextMenu(True)
        except Exception:
            pass
        act_copy.setToolTip('快捷键 C · 再复制当前徽章路径')
        act_copy.triggered.connect(lambda *_: self.copy_path_copy_badge_path())
        menu.addAction(act_copy)
        menu.addSeparator()
        fb_on = self.path_copy_badge_parent_fallback_enabled()
        act_fb = QAction(
            ('✓ ' if fb_on else '') + '中键失败回退本级', menu)
        act_fb.setCheckable(True)
        act_fb.setChecked(fb_on)
        act_fb.setProperty('isPathCopyBadgeFallbackToggle', True)
        act_fb.setObjectName('hostPathCopyBadgeFallbackToggle')
        try:
            act_fb.setIcon(self._path_copy_badge_menu_icon('fallback'))
            act_fb.setIconVisibleInMenu(True)
        except Exception:
            pass
        try:
            act_fb.setShortcut(QKeySequence('F'))
            act_fb.setShortcutVisibleInContextMenu(True)
        except Exception:
            pass
        act_fb.setToolTip('快捷键 F · 中键失败是否回退本级')
        act_fb.triggered.connect(
            lambda *_: self.set_path_copy_badge_parent_fallback_enabled(
                not self.path_copy_badge_parent_fallback_enabled())
        )
        menu.addAction(act_fb)
        menu.addSeparator()
        fail_n = 0
        try:
            fail_n = len(self.merge_diff_batch_fail_history() or [])
        except Exception:
            fail_n = 0
        hist_lab = (
            f'打开历史失败 · {fail_n}' if fail_n > 0 else '打开历史失败')
        act_hist = QAction(hist_lab, menu)
        act_hist.setProperty('isPathCopyBadgeFailHistory', True)
        act_hist.setProperty('failHistoryCount', int(fail_n))
        act_hist.setProperty(
            'isPathCopyBadgeFailHistoryBadge', bool(fail_n > 0))
        act_hist.setObjectName('hostPathCopyBadgeFailHistoryAct')
        try:
            act_hist.setIcon(
                self._path_copy_badge_fail_history_icon(fail_n))
            act_hist.setIconVisibleInMenu(True)
        except Exception:
            pass
        # wave50: 零时隐藏角标（无红点 · 无 ·N）
        if fail_n <= 0:
            act_hist.setText('打开历史失败')
            act_hist.setProperty('isPathCopyBadgeFailHistoryBadge', False)
            act_hist.setProperty('failHistoryCount', 0)
        try:
            act_hist.setShortcut(QKeySequence('H'))
            act_hist.setShortcutVisibleInContextMenu(True)
        except Exception:
            pass
        act_hist.setToolTip(
            f'快捷键 H · 打开失败清单历史（{fail_n}）'
            if fail_n > 0 else '快捷键 H · 打开失败清单历史')
        act_hist.triggered.connect(
            lambda *_: self.show_merge_diff_batch_fail_history())
        menu.addAction(act_hist)
        act_clr = QAction('清除失败历史', menu)
        act_clr.setProperty('isPathCopyBadgeFailHistoryClear', True)
        act_clr.setObjectName('hostPathCopyBadgeFailHistoryClearAct')
        act_clr.setEnabled(bool(fail_n > 0))
        try:
            act_clr.setIcon(self._path_copy_badge_menu_icon('clear'))
            act_clr.setIconVisibleInMenu(True)
        except Exception:
            pass
        try:
            act_clr.setShortcut(QKeySequence('X'))
            act_clr.setShortcutVisibleInContextMenu(True)
        except Exception:
            pass
        act_clr.setToolTip(
            f'快捷键 X · 清除失败清单历史（{fail_n}）'
            if fail_n > 0 else '无失败历史可清')
        act_clr.triggered.connect(
            lambda *_: self.clear_path_copy_badge_fail_history())
        menu.addAction(act_clr)
        can_undo = False
        try:
            can_undo = self.can_undo_path_copy_badge_fail_history_clear()
        except Exception:
            can_undo = False
        undo_left = 0
        try:
            undo_left = int(self.path_copy_badge_fail_history_undo_left_ms() or 0)
        except Exception:
            undo_left = 0
        undo_lbl = '撤销清除失败历史'
        if can_undo and undo_left > 0:
            undo_lbl = f'撤销清除失败历史 · {max(1, int(round(undo_left / 1000.0)))}s'
        act_undo = QAction(undo_lbl, menu)
        act_undo.setProperty('isPathCopyBadgeFailHistoryUndo', True)
        act_undo.setObjectName('hostPathCopyBadgeFailHistoryUndoAct')
        act_undo.setEnabled(bool(can_undo))
        try:
            act_undo.setShortcut(QKeySequence('Z'))
            act_undo.setShortcutVisibleInContextMenu(True)
        except Exception:
            pass
        act_undo.setToolTip(
            (f'快捷键 Z · 撤销最近一次清除 · 剩 {max(1, int(round(undo_left / 1000.0)))}s'
             if undo_left > 0 else '快捷键 Z · 撤销最近一次清除')
            if can_undo else '无清除可撤销')
        self._last_path_copy_badge_fail_history_undo_left_ms = undo_left
        act_undo.triggered.connect(
            lambda *_: self.undo_path_copy_badge_fail_history_clear())
        menu.addAction(act_undo)
        self._last_path_copy_badge_menu_shortcuts = ('C', 'F', 'H', 'X', 'Z')
        self._last_path_copy_badge_menu_icons = True
        self._last_path_copy_badge_fail_history_count = int(fail_n)
        self._last_path_copy_badge_fail_history_red_dot = bool(fail_n > 0)
        self._last_path_copy_badge_fail_history_clear_enabled = bool(fail_n > 0)
        self._last_path_copy_badge_fail_history_undo_enabled = bool(can_undo)
        self._last_path_copy_badge_menu = menu
        return menu

    def clear_path_copy_badge_fail_history(self, *, confirm: bool = True) -> list:
        """wave51–52: 徽章菜单 · 清除失败历史（可确认；可撤销）."""
        hist = []
        try:
            hist = list(self.merge_diff_batch_fail_history() or [])
        except Exception:
            hist = []
        if not hist:
            self._last_path_copy_badge_fail_history_cleared = []
            try:
                self._flash_host_toast('无失败历史可清', kind='info', ms=1200)
            except Exception:
                pass
            return []
        do_it = True
        if confirm and not getattr(self, '_path_copy_badge_fail_hist_clear_no_confirm', False):
            try:
                ans = QMessageBox.question(
                    self, '清除失败历史',
                    f'确认清除 {len(hist)} 条失败清单历史？',
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No)
                do_it = ans == QMessageBox.StandardButton.Yes
            except Exception:
                do_it = True
        if not do_it:
            self._last_path_copy_badge_fail_history_cleared = None
            return hist
        # snapshot for undo
        import copy as _copy
        snap = _copy.deepcopy(hist)
        self._path_copy_badge_fail_history_undo = snap
        self._path_copy_badge_fail_history_can_undo = True
        # wave53: 撤销倒计时
        undo_ms = int(getattr(self, '_path_copy_badge_fail_history_undo_ms', 8000) or 8000)
        undo_ms = max(1000, min(60000, undo_ms))
        self._path_copy_badge_fail_history_undo_left_ms = undo_ms
        try:
            t = getattr(self, '_path_copy_badge_fail_hist_undo_timer', None)
            if t is not None:
                t.start()
        except Exception:
            pass
        n_before = len(snap)
        cleared = self.clear_merge_diff_batch_fail_history()
        self._last_path_copy_badge_fail_history_cleared = list(snap)
        self._last_path_copy_badge_fail_history_undo_countdown_ms = undo_ms
        try:
            sec = max(1, int(round(undo_ms / 1000.0)))
            self._flash_host_toast(
                f'已清除失败历史 · {n_before} · {sec}s 内可撤销',
                kind='ok', ms=1800)
        except Exception:
            pass
        return list(snap)

    def _on_path_copy_badge_fail_history_undo_tick(self):
        """wave53: 徽章清历史撤销倒计时 tick."""
        left = int(getattr(self, '_path_copy_badge_fail_history_undo_left_ms', 0) or 0)
        left = max(0, left - 250)
        self._path_copy_badge_fail_history_undo_left_ms = left
        self._last_path_copy_badge_fail_history_undo_left_ms = left
        if left <= 0:
            self._expire_path_copy_badge_fail_history_undo()

    def _expire_path_copy_badge_fail_history_undo(self):
        """wave53: 倒计时结束 · 失效撤销."""
        try:
            t = getattr(self, '_path_copy_badge_fail_hist_undo_timer', None)
            if t is not None and t.isActive():
                t.stop()
        except Exception:
            pass
        had = bool(getattr(self, '_path_copy_badge_fail_history_can_undo', False))
        self._path_copy_badge_fail_history_can_undo = False
        self._path_copy_badge_fail_history_undo = None
        self._path_copy_badge_fail_history_undo_left_ms = 0
        self._last_path_copy_badge_fail_history_undo_expired = True
        if had:
            try:
                self._flash_host_toast('撤销窗口已过期', kind='info', ms=1000)
            except Exception:
                pass

    def path_copy_badge_fail_history_undo_left_ms(self) -> int:
        """wave53: 剩余撤销毫秒."""
        if not self.can_undo_path_copy_badge_fail_history_clear():
            return 0
        return max(0, int(getattr(
            self, '_path_copy_badge_fail_history_undo_left_ms', 0) or 0))

    def can_undo_path_copy_badge_fail_history_clear(self) -> bool:
        """wave52–53: 是否可撤销徽章清历史（含倒计时）."""
        if not (bool(getattr(self, '_path_copy_badge_fail_history_can_undo', False))
                and bool(getattr(self, '_path_copy_badge_fail_history_undo', None))):
            return False
        left = int(getattr(self, '_path_copy_badge_fail_history_undo_left_ms', 0) or 0)
        # wave53: 倒计时归零即失效
        if left <= 0:
            return False
        return True

    def undo_path_copy_badge_fail_history_clear(self) -> list:
        """wave52–53: 撤销徽章清除失败历史."""
        if not self.can_undo_path_copy_badge_fail_history_clear():
            self._last_path_copy_badge_fail_history_undo_restored = []
            try:
                self._flash_host_toast('无可撤销的清除', kind='info', ms=1200)
            except Exception:
                pass
            return []
        import copy as _copy
        snap = _copy.deepcopy(
            getattr(self, '_path_copy_badge_fail_history_undo', None) or [])
        self._merge_diff_batch_fail_history = list(snap)[:20]
        try:
            self._host_settings().setValue(
                'host/mergeDiffBatchFailHistory', list(snap)[:20])
            if snap:
                last = list((snap[0] or {}).get('paths') or [])
                self._last_merge_diff_batch_fail = last
                self._host_settings().setValue(
                    'host/mergeDiffBatchFailLast', last)
        except Exception:
            pass
        try:
            t = getattr(self, '_path_copy_badge_fail_hist_undo_timer', None)
            if t is not None and t.isActive():
                t.stop()
        except Exception:
            pass
        self._path_copy_badge_fail_history_can_undo = False
        self._path_copy_badge_fail_history_undo = None
        self._path_copy_badge_fail_history_undo_left_ms = 0
        self._last_path_copy_badge_fail_history_undo_expired = False
        self._last_path_copy_badge_fail_history_undo_restored = list(snap)
        try:
            self._flash_host_toast(
                f'已撤销清除 · 恢复 {len(snap)}', kind='ok', ms=1400)
        except Exception:
            pass
        return list(snap)

    def _show_path_copy_badge_menu(self, global_pos=None):
        """wave45: 弹出徽章菜单."""
        menu = self._build_path_copy_badge_menu()
        self._last_path_copy_badge_menu_shown = True
        if getattr(self, '_path_copy_badge_menu_no_exec', False):
            return menu
        try:
            if global_pos is None:
                badge = getattr(self, '_path_copy_badge', None)
                if badge is not None:
                    global_pos = badge.mapToGlobal(badge.rect().bottomLeft())
            if global_pos is not None:
                menu.exec(global_pos)
            else:
                menu.exec()
        except Exception:
            pass
        return menu

    def _on_path_copy_badge_clicked(self, event=None):
        """wave40–45: 左键打开；右键菜单（再复制/回退开关）；中键父目录."""
        btn = None
        try:
            if event is not None and hasattr(event, 'button'):
                btn = event.button()
        except Exception:
            btn = None
        if btn == Qt.MouseButton.RightButton:
            pos = None
            try:
                if event is not None and hasattr(event, 'globalPosition'):
                    pos = event.globalPosition().toPoint()
                elif event is not None and hasattr(event, 'globalPos'):
                    pos = event.globalPos()
            except Exception:
                pos = None
            return self._show_path_copy_badge_menu(pos)
        if btn == Qt.MouseButton.MiddleButton:
            return self.open_path_copy_badge_parent()
        if btn is not None and btn not in (Qt.MouseButton.LeftButton,):
            return False
        path = str(getattr(self, '_path_copy_badge_path', '') or '').strip()
        if path:
            self._host_toast_open_path = path
        got = self.open_host_toast_path()
        self._last_path_copy_badge_opened = got
        return got

    def path_copy_badge_parent_fallback_enabled(self) -> bool:
        """wave44: 中键父目录失败是否回退本级（默认开）."""
        v = getattr(self, '_path_copy_badge_parent_fallback', None)
        if v is None:
            try:
                raw = self._host_settings().value(
                    'host/pathCopyBadgeParentFallback', True)
                if isinstance(raw, str):
                    v = raw.strip().lower() not in ('0', 'false', 'no', 'off')
                else:
                    v = bool(raw)
            except Exception:
                v = True
            self._path_copy_badge_parent_fallback = bool(v)
        return bool(self._path_copy_badge_parent_fallback)

    def set_path_copy_badge_parent_fallback_enabled(
            self, enabled: bool = True, *, persist: bool = True) -> bool:
        """wave44–45: 配置中键失败回退本级；热更徽章菜单勾."""
        self._path_copy_badge_parent_fallback = bool(enabled)
        if persist:
            try:
                self._host_settings().setValue(
                    'host/pathCopyBadgeParentFallback', bool(enabled))
            except Exception:
                pass
        menu = getattr(self, '_last_path_copy_badge_menu', None)
        if menu is not None:
            for act in menu.actions():
                try:
                    if act.property('isPathCopyBadgeFallbackToggle'):
                        act.setChecked(bool(enabled))
                        act.setText(
                            ('✓ ' if enabled else '') + '中键失败回退本级')
                except Exception:
                    continue
        return self._path_copy_badge_parent_fallback

    def open_path_copy_badge_parent(self) -> str:
        """wave42–44: 徽章中键开父目录；失败可配回退本级."""
        path = str(getattr(self, '_path_copy_badge_path', '') or '').strip()
        if not path:
            try:
                self._flash_host_toast('无路径可开父目录', kind='info', ms=1200)
            except Exception:
                pass
            self._last_path_copy_badge_parent = ''
            self._last_path_copy_badge_parent_fallback = False
            return ''
        allow_fb = self.path_copy_badge_parent_fallback_enabled()
        try:
            from pathlib import Path as _P
            p = _P(path)
            parent = p if p.is_dir() else p.parent
            if p.is_dir() and p.parent and str(p.parent) not in ('', str(p)):
                parent = p.parent
            parent_s = str(parent)
        except Exception:
            parent_s = ''

        def _parent_openable(ps: str) -> bool:
            if not ps:
                return False
            try:
                from pathlib import Path as _P
                pp = _P(ps)
                return pp.exists() and (pp.is_dir() or pp.parent.exists())
            except Exception:
                return False

        used_fallback = False
        target_s = parent_s
        if not _parent_openable(parent_s):
            if allow_fb:
                target_s = path
                used_fallback = True
                self._last_path_copy_badge_parent_fallback = True
            else:
                self._last_path_copy_badge_parent_fallback = False
                self._last_path_copy_badge_parent = ''
                try:
                    self._flash_host_toast(
                        '父目录失败 · 回退已关', kind='info', ms=1600)
                    self._log_line(f'徽章中键父目录失败 · 回退已关 · {parent_s}')
                except Exception:
                    pass
                return ''
        else:
            self._last_path_copy_badge_parent_fallback = False

        self._host_toast_open_path = target_s
        got = self.open_host_toast_path()
        if not got and not used_fallback:
            if allow_fb:
                used_fallback = True
                self._last_path_copy_badge_parent_fallback = True
                self._host_toast_open_path = path
                got = self.open_host_toast_path()
                target_s = path
            else:
                self._last_path_copy_badge_parent_fallback = False
                self._last_path_copy_badge_parent = ''
                try:
                    self._flash_host_toast(
                        '父目录失败 · 回退已关', kind='info', ms=1600)
                    self._log_line(f'徽章中键父目录失败 · 回退已关 · {parent_s}')
                except Exception:
                    pass
                return ''

        self._last_path_copy_badge_parent = got or target_s
        try:
            from pathlib import Path as _P
            lab = _P(target_s).name or target_s
            if used_fallback:
                self._flash_host_toast(
                    f'父目录失败 · 已回退本级 · {lab}', kind='info', ms=1600)
                self._log_line(f'徽章中键父目录失败 · 回退本级 · {target_s}')
            else:
                self._flash_host_toast(f'已开父目录 · {lab}', kind='ok', ms=1200)
                self._log_line(f'徽章中键开父目录 · {target_s}')
        except Exception:
            pass
        return self._last_path_copy_badge_parent

    def copy_path_copy_badge_path(self) -> bool:
        """wave41: 徽章右键 — 再复制路径到剪贴板."""
        path = str(getattr(self, '_path_copy_badge_path', '') or '').strip()
        if not path:
            try:
                self._flash_host_toast('无路径可复制', kind='info', ms=1200)
            except Exception:
                pass
            self._last_path_copy_badge_recopied = False
            return False
        try:
            clip = QApplication.clipboard()
            if clip is not None:
                clip.setText(path)
        except Exception:
            self._last_path_copy_badge_recopied = False
            return False
        short = ''
        try:
            from pathlib import Path as _P
            short = _P(path).name
        except Exception:
            short = path[-24:]
        try:
            self._flash_host_toast(f'已再复制 · {short}', kind='ok', ms=1200)
            self._log_line(f'徽章右键再复制路径 · {path}')
        except Exception:
            pass
        # refresh badge text briefly
        badge = getattr(self, '_path_copy_badge', None)
        if badge is not None:
            try:
                badge.setText(f'✓ 已再复制 · {short}' if short else '✓ 已再复制')
                badge.show()
                badge.raise_()
                timer = getattr(self, '_path_copy_badge_timer', None)
                if timer is not None:
                    timer.start(1800)
            except Exception:
                pass
        self._last_path_copy_badge_recopied = True
        return True

    def _hide_path_copy_badge(self):
        badge = getattr(self, '_path_copy_badge', None)
        if badge is not None:
            try:
                badge.hide()
                badge.setText('')
            except Exception:
                pass

    def _on_host_toast_clicked(self, event=None):
        """wave35–41: CSV/开目录 tip 单击；回看 / 开目录 / 撤销清理."""
        try:
            if event is not None and hasattr(event, 'button'):
                if event.button() not in (Qt.MouseButton.LeftButton,):
                    return
        except Exception:
            pass
        action = str(getattr(self, '_host_toast_click_action', 'open') or 'open')
        if action == 'review':
            self.review_host_toast_path()
            return
        if action == 'undo_prune':
            self.undo_prune_stale_alarm_film_csv_dirs()
            return
        if action == 'merge_diff':
            self.show_last_merge_diff()
            return
        if action == 'retry_merge_diff_fails':
            # wave46: 失败 tip 可点 → 失败项清单重开
            self.show_merge_diff_batch_fails()
            return
        self.open_host_toast_path()

    def open_host_toast_path(self) -> str:
        """wave35–36/45: 打开 toast 绑定目录；失败 tip；silent 可抑 tip."""
        silent = bool(getattr(self, '_open_host_toast_path_silent', False))
        path = str(getattr(self, '_host_toast_open_path', '') or '').strip()
        if not path:
            if not silent:
                self._flash_open_dir_fail_tip('无绑定路径')
            return ''
        try:
            from pathlib import Path as _P
            p = _P(path)
            if p.is_dir():
                target = p
            elif p.is_file():
                target = p.parent
            elif p.suffix and p.parent.exists():
                # missing file but parent dir ok
                target = p.parent
            else:
                if not silent:
                    self._flash_open_dir_fail_tip('目录不存在')
                return ''
            if not target.exists():
                if not silent:
                    self._flash_open_dir_fail_tip('目录不存在')
                return ''
            ok = QDesktopServices.openUrl(QUrl.fromLocalFile(str(target.resolve())))
            resolved = str(target.resolve())
            if not ok:
                # headless：目录有效但系统未打开 → 成功软 tip（非失败）
                if not silent:
                    self._flash_open_dir_ok_tip(resolved, soft=True)
                return resolved
            if not silent:
                self._flash_open_dir_ok_tip(resolved, soft=False)
            return resolved
        except Exception as err:
            if not silent:
                self._flash_open_dir_fail_tip(str(err))
            return ''

    def set_liaison_window_sec(self, sec: int, *, persist: bool = True):
        combo = getattr(self, '_liaison_window', None)
        if combo is None:
            return
        sec = int(sec or 0)
        for i in range(combo.count()):
            if int(combo.itemData(i) or 0) == sec:
                try:
                    combo.blockSignals(True)
                    combo.setCurrentIndex(i)
                    combo.blockSignals(False)
                except Exception:
                    combo.setCurrentIndex(i)
                if persist:
                    self._save_liaison_window_pref(sec)
                try:
                    self._sync_liaison_window_badge()
                except Exception:
                    pass
                return

    def filtered_liaison_events(self, window_sec: int | None = None):
        """wave24: 联调条按时段过滤."""
        if window_sec is None:
            window_sec = self.liaison_window_sec()
        window_sec = int(window_sec or 0)
        evs = list(self._liaison_events)
        if window_sec <= 0:
            return evs
        try:
            cutoff = datetime.now().timestamp() - window_sec
        except Exception:
            return evs
        out = []
        for e in evs:
            ep = e.get('epoch')
            if ep is None:
                # legacy HH:MM:SS — keep
                out.append(e)
                continue
            try:
                if float(ep) >= cutoff:
                    out.append(e)
            except Exception:
                out.append(e)
        return out

    def liaison_events_csv(self, window_sec: int | None = None) -> str:
        """wave23/24: 联调条 CSV（clipboard / file）；可选时段过滤."""
        lines = ['timestamp,kind,code,severity,text']
        for e in self.filtered_liaison_events(window_sec):
            ts = str(e.get('ts_full') or e.get('ts') or '').replace(',', ' ')
            kind = str(e.get('kind') or '').replace(',', ' ')
            code = str(e.get('code') or '').replace(',', ' ')
            sev = str(e.get('severity') or self._liaison_severity(kind, code)).replace(',', ' ')
            text = str(e.get('text') or '').replace('"', "'").replace('\n', ' ')
            lines.append(f'{ts},{kind},{code},{sev},"{text}"')
        return '\n'.join(lines) + ('\n' if lines else '')

    def export_liaison_clipboard(self):
        win = self.liaison_window_sec()
        evs = self.filtered_liaison_events(win)
        csv = self.liaison_events_csv(win)
        try:
            QApplication.clipboard().setText(csv)
            tip = f'联调条已复制 CSV · {len(evs)} 条'
            if win:
                tip += f'（近 {win // 60} 分）' if win >= 60 else f'（近 {win}s）'
            self._log_line(tip)
        except Exception as err:
            self._log_line(f'联调复制失败：{err}')

    def export_liaison_file(self):
        path, _ = QFileDialog.getSaveFileName(
            self, '导出联调条', 'liaison-events.csv', 'CSV (*.csv);;All (*)')
        if not path:
            return
        win = self.liaison_window_sec()
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(self.liaison_events_csv(win))
            self._log_line(f'联调条已导出 · {path} · {len(self.filtered_liaison_events(win))} 条')
        except Exception as err:
            self._log_line(f'联调导出失败：{err}')

    def jump_to_alarm_for_code(self, code: str = '', *, keyword: str = '',
                                 film_path: str = ''):
        """wave24/26: 换型失败码 → 报警历史一键跳（切 tab + 筛关键字/联调）."""
        code = str(code or '').strip()
        keyword = str(keyword or code or '').strip()
        self._jump_film_path = str(film_path or '').strip()
        try:
            # tab index 2 = 报警历史
            if hasattr(self, 'tabs') and self.tabs is not None:
                for i in range(self.tabs.count()):
                    if '报警' in (self.tabs.tabText(i) or ''):
                        self.tabs.setCurrentIndex(i)
                        break
                else:
                    self.tabs.setCurrentIndex(min(2, self.tabs.count() - 1))
        except Exception:
            pass
        try:
            filt = getattr(self, '_alarm_filter', None)
            if filt is not None:
                filt.setText(keyword)
        except Exception:
            pass
        try:
            sf = getattr(self, '_alarm_status_filter', None)
            if sf is not None:
                for i in range(sf.count()):
                    if sf.itemData(i) == 'liaison':
                        sf.setCurrentIndex(i)
                        break
        except Exception:
            pass
        try:
            self._refresh_alarm_history_ui()
        except Exception:
            pass
        # wave25/26: 跳后列表高亮首条（可带胶片 path）
        try:
            self._highlight_alarm_list_first(
                keyword=keyword,
                film_path=getattr(self, '_jump_film_path', '') or '',
            )
        except Exception:
            pass
        try:
            self._log_line(f'已跳转报警历史 · 筛选 {keyword or "联调"}')
        except Exception:
            pass
        return True

    def _highlight_alarm_list_first(self, *, keyword: str = '', film_path: str = ''):
        """wave25/26: select + flash-style first visible alarm row after jump."""
        lst = getattr(self, '_alarm_list', None)
        if lst is None or lst.count() <= 0:
            return False
        lst.setCurrentRow(0)
        item = lst.item(0)
        if item is None:
            return False
        try:
            item.setSelected(True)
            lst.scrollToItem(item)
        except Exception:
            pass
        # wave26: stash film path on item for double-click locate
        fp = str(film_path or '').strip()
        if not fp:
            try:
                data = item.data(Qt.ItemDataRole.UserRole) or {}
                if isinstance(data, dict):
                    fp = str(data.get('filmPath') or '').strip()
            except Exception:
                fp = ''
        if fp:
            try:
                payload = item.data(Qt.ItemDataRole.UserRole) or {}
                if not isinstance(payload, dict):
                    payload = {}
                payload = dict(payload)
                payload['filmPath'] = fp
                item.setData(Qt.ItemDataRole.UserRole, payload)
                tip = item.toolTip() or item.text() or ''
                item.setToolTip((tip + f'\n双击定位胶片 · {fp}').strip())
            except Exception:
                pass
        # brief accent via stylesheet on list
        try:
            base = lst.styleSheet() or ''
            flash = (
                'QListWidget::item:selected{'
                'background:#3a1c1c;color:#ffb4b4;border:1px solid #e35d6a;}'
            )
            lst.setStyleSheet(base + flash)
            from PySide6.QtCore import QTimer
            def _settle(prev=base):
                try:
                    lst.setStyleSheet(prev)
                except Exception:
                    pass
            QTimer.singleShot(1800, _settle)
        except Exception:
            pass
        try:
            tip = item.text()
            self._log_line(f'高亮首条 · {(tip or "")[:60]}')
        except Exception:
            pass
        return True

    def set_alarm_severity_filter(self, key: str = 'all', *, persist: bool = True, force: bool = False) -> bool:
        """wave26/27/32: 设严重度筛；钉住时非 force 拒绝切换."""
        combo = getattr(self, '_alarm_sev_filter', None)
        if combo is None:
            return False
        key = str(key or 'all').strip().lower()
        if key in ('warn',):
            key = 'warning'
        if (not force) and getattr(self, '_alarm_sev_pinned', False):
            pinned = str(getattr(self, '_alarm_sev_pinned_key', '') or '')
            if pinned and key != pinned:
                try:
                    self._log_line(f'严重度已钉住 · {pinned}（长按气泡解锁）')
                except Exception:
                    pass
                return False
        for i in range(combo.count()):
            if str(combo.itemData(i) or '') == key:
                if combo.currentIndex() != i:
                    combo.setCurrentIndex(i)
                else:
                    self._refresh_alarm_history_ui()
                if persist:
                    self._save_alarm_sev_filter_pref(key)
                return True
        return False

    def _on_alarm_sev_filter_changed(self, *_):
        try:
            self._refresh_alarm_history_ui()
        except Exception:
            pass
        try:
            self._save_alarm_sev_filter_pref(self.alarm_severity_filter())
        except Exception:
            pass

    def _save_alarm_sev_filter_pref(self, key: str = 'all'):
        key = str(key or 'all').strip().lower()
        if key in ('warn',):
            key = 'warning'
        try:
            self._host_settings().setValue('host/alarmSevFilter', key)
        except Exception:
            pass
        try:
            self._sync_alarm_sev_chips()
        except Exception:
            pass

    def _alarm_severity_counts(self) -> dict:
        """wave29: 历史按严重度计数（供芯片气泡）."""
        counts = {'all': 0, 'error': 0, 'warning': 0, 'info': 0}
        for e in getattr(self, '_alarm_history', None) or []:
            counts['all'] += 1
            sev = str(e.get('severity') or 'info')
            if sev in ('warn', 'warning'):
                sev = 'warning'
            if sev not in ('error', 'warning', 'info'):
                sev = 'info'
            counts[sev] = counts.get(sev, 0) + 1
        return counts

    def _sync_alarm_sev_chips(self):
        """wave28/29: 严重度筛芯片条高亮 + 计数气泡."""
        chips = getattr(self, '_alarm_sev_chips', None) or {}
        if not chips:
            return
        cur = self.alarm_severity_filter()
        counts = self._alarm_severity_counts()
        labels = getattr(self, '_alarm_sev_chip_labels', None) or {
            'all': '全部', 'error': '错', 'warning': '警', 'info': '讯',
        }
        styles = {
            'all': ('#2a3340', '#9aa0a6', '#3a3d42'),
            'error': ('#3a1c1c', '#e35d6a', '#e35d6a'),
            'warning': ('#3a3420', '#e0b84a', '#e0b84a'),
            'info': ('#1c2a3a', '#6eb6ff', '#6eb6ff'),
        }
        bubbles = getattr(self, '_alarm_sev_count_bubbles', None) or {}
        for key, b in chips.items():
            on = (key == cur)
            bg, fg, bd = styles.get(key, styles['all'])
            n = int(counts.get(key, 0) or 0)
            base = labels.get(key, key)
            pinned = bool(getattr(self, '_alarm_sev_pinned', False))
            pinned_key = str(getattr(self, '_alarm_sev_pinned_key', '') or '')
            pin_here = pinned and pinned_key == key
            try:
                # wave33: pin badge glyph on sev chip
                b.setText(('📌' + base) if pin_here else base)
            except Exception:
                pass
            if pin_here:
                b.setChecked(True)
                b.setStyleSheet(
                    f'background:{bg};color:{fg};border:2px solid #f0c040;'
                    f'border-radius:3px;font-size:10px;font-weight:700;padding:1px 4px;'
                )
                b.setToolTip(f'严重度筛 · {base} · 已钉住（Alt+P / 徽章取消）')
            elif on:
                b.setChecked(True)
                b.setStyleSheet(
                    f'background:{bg};color:{fg};border:1px solid {bd};'
                    f'border-radius:3px;font-size:10px;font-weight:700;padding:1px 4px;'
                )
                b.setToolTip(f'严重度筛 · {base} · Alt+P 钉住')
            else:
                b.setChecked(False)
                b.setStyleSheet(
                    'background:#2a2c30;color:#6a7078;border:1px solid #3a3d42;'
                    'border-radius:3px;font-size:10px;padding:1px 4px;'
                )
                b.setToolTip(f'严重度筛 · {base} · Alt+P 钉住')
            bubble = bubbles.get(key)
            if bubble is not None:
                bubble.setText(str(n))
                pinned = bool(getattr(self, '_alarm_sev_pinned', False))
                pinned_key = str(getattr(self, '_alarm_sev_pinned_key', '') or '')
                pin_here = pinned and pinned_key == key
                tip = f'{base} · {n} 条'
                if pin_here:
                    tip += ' · 钉住（长按/中键取消）'
                else:
                    tip += ' · 左键筛 · 长按钉住 · 右键仅看 · 中键清筛'
                bubble.setToolTip(tip)
                if pin_here:
                    bubble.setStyleSheet(
                        f'background:{bg};color:{fg};border:2px solid #f0c040;'
                        f'border-radius:7px;padding:0 3px;font-size:9px;font-weight:700;'
                    )
                elif n > 0:
                    bubble.setStyleSheet(
                        f'background:{bg};color:{fg};border:1px solid {bd};'
                        f'border-radius:7px;padding:0 3px;font-size:9px;font-weight:700;'
                    )
                else:
                    bubble.setStyleSheet(
                        'background:#2a2c30;color:#6a7078;border:1px solid #3a3d42;'
                        'border-radius:7px;padding:0 3px;font-size:9px;font-weight:700;'
                    )
        # wave33: pin badge widget
        badge = getattr(self, '_alarm_sev_pin_badge', None)
        if badge is not None:
            pinned = bool(getattr(self, '_alarm_sev_pinned', False))
            pk = str(getattr(self, '_alarm_sev_pinned_key', '') or '')
            if pinned and pk:
                lab = (getattr(self, '_alarm_sev_chip_labels', None) or {}).get(pk, pk)
                badge.setText(f'📌{lab}')
                badge.setToolTip(f'已钉住 · {lab} · 单击取消 · Alt+P')
                badge.show()
            else:
                badge.setText('')
                badge.setToolTip('钉住徽章 · Alt+P 钉住当前筛')
                badge.hide()

    def alarm_severity_filter(self) -> str:
        combo = getattr(self, '_alarm_sev_filter', None)
        if combo is None:
            return 'all'
        try:
            return str(combo.currentData() or 'all')
        except Exception:
            return 'all'

    def _on_alarm_spark_clicked(self, event=None):
        """wave26: spark 单击循环筛严重度 all→error→warning→info→all."""
        try:
            if event is not None and hasattr(event, 'button'):
                from PySide6.QtCore import Qt as _Qt
                if event.button() not in (_Qt.MouseButton.LeftButton,):
                    return
        except Exception:
            pass
        order = ['all', 'error', 'warning', 'info']
        cur = self.alarm_severity_filter()
        try:
            nxt = order[(order.index(cur) + 1) % len(order)]
        except ValueError:
            nxt = 'all'
        ok = self.set_alarm_severity_filter(nxt)
        labels = {'all': '全部', 'error': '错', 'warning': '警', 'info': '讯'}
        try:
            self._log_line(f'spark 筛严重度 · {labels.get(nxt, nxt)}')
        except Exception:
            pass
        # refresh spark tooltip to show active filter
        spark = getattr(self, '_alarm_spark', None)
        if spark is not None:
            try:
                spark.setToolTip(
                    f'筛严重度：{labels.get(nxt, nxt)} · 单击再循环 · ▇未清 ▁已清；色=严重度'
                )
            except Exception:
                pass
        return ok

    def _on_alarm_item_double_clicked(self, item):
        """wave26: 高亮首条/条目双击 → 若有 filmPath 则定位胶片."""
        self._locate_film_from_alarm_item(item, source='alarm_dblclick')

    def _on_alarm_list_context_menu(self, pos):
        """wave28: 报警列表右键 → 定位胶片."""
        menu = self._build_alarm_list_context_menu(pos)
        if menu is None:
            return
        lst = getattr(self, '_alarm_list', None)
        if lst is None:
            return
        if getattr(self, '_alarm_ctx_menu_no_exec', False):
            self._last_alarm_ctx_menu = menu
            return menu
        try:
            menu.exec(lst.mapToGlobal(pos))
        except Exception:
            pass

    def _build_alarm_list_context_menu(self, pos=None):
        """Build (no exec) context menu for smoke / right-click."""
        lst = getattr(self, '_alarm_list', None)
        if lst is None:
            return None
        item = None
        if pos is not None:
            try:
                item = lst.itemAt(pos)
            except Exception:
                item = None
        if item is None:
            item = lst.currentItem()
        menu = QMenu(self)
        act = QAction('定位胶片', self)
        fp = self._film_path_from_alarm_item(item)
        act.setEnabled(bool(fp))
        if fp:
            act.setToolTip(fp)
            act.setText(f'定位胶片 · {fp.rsplit("/", 1)[-1]}')
        else:
            act.setText('定位胶片（无 path）')
        act.triggered.connect(
            lambda *_: self._locate_film_from_alarm_item(item, source='alarm_context')
        )
        menu.addAction(act)
        # wave29: 复制 path
        act_copy = QAction('复制 path', self)
        act_copy.setEnabled(bool(fp))
        if fp:
            act_copy.setToolTip(fp)
            act_copy.setText(f'复制 path · {fp.rsplit("/", 1)[-1]}')
        else:
            act_copy.setText('复制 path（无 path）')
        act_copy.triggered.connect(lambda *_: self.copy_alarm_film_path(item))
        menu.addAction(act_copy)
        # wave30: 复制全部 paths
        act_all = QAction('复制全部 paths CSV', self)
        all_rows = self._collect_alarm_film_rows()
        act_all.setEnabled(bool(all_rows))
        if all_rows:
            act_all.setToolTip(f'{len(all_rows)} 条 · ts,cleared,cleared_at,severity,path,reason')
            act_all.setText(f'复制全部 paths CSV（{len(all_rows)}）')
        else:
            act_all.setText('复制全部 paths CSV（无）')
        act_all.triggered.connect(lambda *_: self.copy_all_alarm_film_paths(as_csv=True))
        menu.addAction(act_all)
        # wave32: 另存 CSV 文件（含 cleared）
        act_save = QAction('另存 paths CSV…', self)
        act_save.setEnabled(bool(all_rows))
        if all_rows:
            act_save.setToolTip(f'{len(all_rows)} 条 · 含 cleared/cleared_at')
            act_save.setText(f'另存 paths CSV…（{len(all_rows)}）')
        else:
            act_save.setText('另存 paths CSV…（无）')
        act_save.triggered.connect(lambda *_: self.save_all_alarm_film_paths_csv())
        menu.addAction(act_save)
        # wave36–39: 多档另存 · 置顶/删 · 失效灰显 · 导入导出 · 清档
        recent = self.alarm_film_csv_dirs()
        stale = self.stale_alarm_film_csv_dirs()
        sub = QMenu('最近另存目录', menu)
        if recent:
            for i, d in enumerate(recent):
                from pathlib import Path as _P
                try:
                    lab = _P(d).name or d
                except Exception:
                    lab = d
                exists = self.alarm_film_csv_dir_exists(d)
                title = f'{i+1}. {lab}' if exists else f'{i+1}. {lab}（失效）'
                item_m = QMenu(title, sub)
                item_m.setToolTip(d if exists else f'失效 · {d}')
                item_m.setProperty('isStaleDir', not exists)
                act_save = QAction('另存到此目录', item_m)
                act_save.setData(d)
                act_save.setProperty('isRecentSave', True)
                act_save.setEnabled(bool(all_rows) and exists)
                act_save.setToolTip(d if exists else '目录不存在')
                act_save.triggered.connect(
                    lambda *_a, dd=d: self.save_all_alarm_film_paths_csv_to_dir(dd)
                )
                item_m.addAction(act_save)
                act_top = QAction('置顶', item_m)
                act_top.setData(d)
                act_top.setProperty('isRecentPromote', True)
                act_top.setEnabled(i > 0)
                act_top.triggered.connect(
                    lambda *_a, dd=d: self.promote_alarm_film_csv_dir(dd)
                )
                item_m.addAction(act_top)
                act_del = QAction('删除此项', item_m)
                act_del.setData(d)
                act_del.setProperty('isRecentRemove', True)
                act_del.setObjectName('hostAlarmFilmCsvDirRemove')
                act_del.triggered.connect(
                    lambda *_a, dd=d: self.remove_alarm_film_csv_dir(dd)
                )
                item_m.addAction(act_del)
                # gray stale title via disabled empty action marker
                if not exists:
                    act_stale = QAction('（目录已失效）', item_m)
                    act_stale.setEnabled(False)
                    act_stale.setProperty('isStaleMarker', True)
                    item_m.insertAction(act_save, act_stale)
                sub.addMenu(item_m)
            sub.addSeparator()
        else:
            act_empty = QAction('（无最近目录）', sub)
            act_empty.setEnabled(False)
            sub.addAction(act_empty)
            sub.addSeparator()
        cur_max = self.alarm_film_csv_dirs_max()
        for n in (3, 5, 8):
            mark = '✓ ' if n == cur_max else ''
            def_mark = '（默认）' if n == 5 else ''
            act_m = QAction(f'{mark}记忆上限 {n}{def_mark}', sub)
            act_m.setData(n)
            act_m.setProperty('isDirsMax', True)
            act_m.setCheckable(True)
            act_m.setChecked(n == cur_max)
            act_m.triggered.connect(
                lambda *_a, nn=n: self._apply_alarm_film_csv_dirs_max(nn)
            )
            sub.addAction(act_m)
        sub.addSeparator()
        act_prune = QAction(f'清理失效目录（{len(stale)}）…', sub)
        act_prune.setEnabled(bool(stale))
        act_prune.setObjectName('hostAlarmFilmCsvDirsPrune')
        act_prune.setProperty('isPruneStale', True)
        act_prune.setToolTip('预览清单确认后清理')
        act_prune.triggered.connect(lambda *_: self.prune_stale_alarm_film_csv_dirs(confirm=True))
        sub.addAction(act_prune)
        can_undo = self.can_undo_prune_stale_alarm_film_csv_dirs()
        act_undo = QAction('撤销上次清理', sub)
        act_undo.setEnabled(bool(can_undo))
        act_undo.setObjectName('hostAlarmFilmCsvDirsPruneUndo')
        act_undo.setProperty('isPruneUndo', True)
        act_undo.setToolTip('恢复清理前的多档记忆')
        act_undo.triggered.connect(lambda *_: self.undo_prune_stale_alarm_film_csv_dirs())
        sub.addAction(act_undo)
        act_export = QAction('导出记忆 JSON…', sub)
        act_export.setProperty('isDirsExport', True)
        act_export.setObjectName('hostAlarmFilmCsvDirsExport')
        act_export.triggered.connect(lambda *_: self.export_alarm_film_csv_dirs_json())
        sub.addAction(act_export)
        act_import = QAction('导入记忆 JSON…', sub)
        act_import.setProperty('isDirsImport', True)
        act_import.setObjectName('hostAlarmFilmCsvDirsImport')
        act_import.triggered.connect(lambda *_: self.import_alarm_film_csv_dirs_json())
        sub.addAction(act_import)
        act_merge = QAction('合并导入 JSON…', sub)
        act_merge.setProperty('isDirsMergeImport', True)
        act_merge.setObjectName('hostAlarmFilmCsvDirsMergeImport')
        act_merge.triggered.connect(lambda *_: self.merge_import_alarm_film_csv_dirs_json())
        sub.addAction(act_merge)
        sub.addSeparator()
        seize_menu = self._build_sev_pin_arc_seize_color_menu(sub)
        seize_act = sub.addMenu(seize_menu)
        seize_act.setObjectName('hostSevPinArcSeizeColorMenuAct')
        seize_act.setProperty('isSeizeColorMenu', True)
        act_clear = QAction('清空最近另存', sub)
        act_clear.setEnabled(bool(recent))
        act_clear.setObjectName('hostAlarmFilmCsvDirsClear')
        act_clear.triggered.connect(self.clear_alarm_film_csv_dirs)
        sub.addAction(act_clear)
        menu.addMenu(sub)
        self._last_alarm_ctx_item = item
        return menu

    def _apply_alarm_film_csv_dirs_max(self, n: int) -> int:
        nn = self.set_alarm_film_csv_dirs_max(int(n))
        try:
            self._flash_host_toast(f'另存记忆上限 → {nn}', kind='info')
            self._log_line(f'另存记忆上限 → {nn}')
        except Exception:
            pass
        return nn

    def _on_sev_bubble_press(self, event=None, key: str = 'all'):
        """wave32: 左键按下启动长按钉住计时；右/中立即处理."""
        btn = None
        try:
            if event is not None and hasattr(event, 'button'):
                btn = event.button()
        except Exception:
            btn = None
        if btn == Qt.MouseButton.RightButton:
            self.set_alarm_severity_filter(key if key else 'all', force=True)
            try:
                self._log_line(f'气泡右键仅看 · {key}')
            except Exception:
                pass
            return
        if btn == Qt.MouseButton.MiddleButton:
            # 中键：若钉住则取消钉；否则清筛
            if getattr(self, '_alarm_sev_pinned', False):
                self.pin_alarm_severity_filter(False)
            else:
                self.set_alarm_severity_filter('all', force=True)
                try:
                    self._log_line('气泡中键清筛 · all')
                except Exception:
                    pass
            return
        # left: arm long-press pin（wave39: 与芯片同色/时长 + 进度弧）
        self._sev_bubble_pin_key = key
        self._sev_bubble_long_fired = False
        self._sev_bubble_pin_press_ms = 0
        self.sync_sev_bubble_pin_from_chip()
        ms = int(getattr(self, '_sev_bubble_pin_ms', 550) or 550)
        timer = getattr(self, '_sev_bubble_pin_timer', None)
        if timer is not None:
            timer.start(ms)
        tick = getattr(self, '_sev_bubble_pin_tick', None)
        if tick is not None and not tick.isActive():
            tick.start()
        self._show_sev_bubble_pin_arc(0.0)

    def _on_sev_bubble_release(self, event=None, key: str = 'all'):
        """wave32–39: 短按筛；长按已钉则跳过；收弧."""
        btn = None
        try:
            if event is not None and hasattr(event, 'button'):
                btn = event.button()
        except Exception:
            btn = None
        if btn is not None and btn != Qt.MouseButton.LeftButton:
            return
        timer = getattr(self, '_sev_bubble_pin_timer', None)
        if timer is not None and timer.isActive():
            timer.stop()
        self._hide_sev_bubble_pin_arc()
        if getattr(self, '_sev_bubble_long_fired', False):
            return
        self.set_alarm_severity_filter(key)

    def _on_sev_bubble_long_press(self):
        """wave32–39: 长按满弧钉住当前气泡 sev（再长按同键取消）."""
        self._sev_bubble_long_fired = True
        self._show_sev_bubble_pin_arc(1.0)
        self._hide_sev_bubble_pin_arc()
        key = str(getattr(self, '_sev_bubble_pin_key', '') or 'all')
        if getattr(self, '_alarm_sev_pinned', False) and str(
            getattr(self, '_alarm_sev_pinned_key', '') or ''
        ) == key:
            self.pin_alarm_severity_filter(False)
        else:
            self.pin_alarm_severity_filter(True, key=key)

    def sync_sev_bubble_pin_from_chip(self):
        """wave39: 气泡长按时长/色与芯片进度弧同步."""
        try:
            ms = int(self.sev_chip_pin_ms())
        except Exception:
            ms = int(getattr(self, '_sev_chip_pin_ms', 550) or 550)
        self._sev_bubble_pin_ms = ms
        color = '#f0c040'
        try:
            color = self.sev_chip_pin_arc_color()
        except Exception:
            pass
        arc = getattr(self, '_sev_bubble_pin_arc', None)
        if arc is not None and hasattr(arc, 'set_color'):
            try:
                arc.set_color(color)
            except Exception:
                pass
        return ms

    def _on_sev_bubble_pin_tick(self):
        """wave39: 气泡进度弧推进（同芯片时长）."""
        tick = getattr(self, '_sev_bubble_pin_tick', None)
        interval = int(tick.interval()) if tick is not None else 40
        self._sev_bubble_pin_press_ms = int(getattr(self, '_sev_bubble_pin_press_ms', 0) or 0) + interval
        ms = max(1, int(getattr(self, '_sev_bubble_pin_ms', 550) or 550))
        p = min(1.0, float(self._sev_bubble_pin_press_ms) / float(ms))
        self._show_sev_bubble_pin_arc(p)


    def claim_sev_pin_arc(self, owner: str, *, flash: bool = True) -> str:
        """wave41: 共享弧互斥抢占；返回前 owner；可视化闪一下."""
        owner = str(owner or '').strip()
        prev = str(getattr(self, '_sev_pin_arc_owner', '') or '')
        if prev and prev != owner:
            # stop previous owner's tick
            if prev == 'chip':
                tick = getattr(self, '_sev_chip_pin_tick', None)
                if tick is not None and tick.isActive():
                    tick.stop()
            elif prev == 'bubble':
                tick = getattr(self, '_sev_bubble_pin_tick', None)
                if tick is not None and tick.isActive():
                    tick.stop()
            self._last_sev_pin_arc_seize = {'from': prev, 'to': owner}
            if flash:
                try:
                    self._flash_sev_pin_arc_seize(prev, owner)
                except Exception:
                    pass
        self._sev_pin_arc_owner = owner
        return prev

    def sev_pin_arc_seize_color(self) -> str:
        """wave42: 抢占闪色（默认 #ffffff）."""
        c = str(getattr(self, '_sev_pin_arc_seize_color', '') or '').strip()
        if not c:
            try:
                c = str(self._host_settings().value(
                    'host/sevPinArcSeizeColor', '#ffffff') or '#ffffff').strip()
            except Exception:
                c = '#ffffff'
        if c and not c.startswith('#'):
            c = '#' + c
        return c or '#ffffff'

    def set_sev_pin_arc_seize_color(self, color: str, *, persist: bool = True) -> str:
        """wave42: 配置抢占闪色."""
        c = str(color or '').strip() or '#ffffff'
        if not c.startswith('#'):
            c = '#' + c
        self._sev_pin_arc_seize_color = c
        if persist:
            try:
                self._host_settings().setValue('host/sevPinArcSeizeColor', c)
            except Exception:
                pass
        return c

    def sev_pin_arc_seize_sound(self) -> bool:
        """wave42: 抢占是否蜂鸣."""
        v = getattr(self, '_sev_pin_arc_seize_sound', None)
        if v is None:
            try:
                raw = self._host_settings().value('host/sevPinArcSeizeSound', True)
                if isinstance(raw, str):
                    v = raw.strip().lower() not in ('0', 'false', 'no', 'off')
                else:
                    v = bool(raw)
            except Exception:
                v = True
            self._sev_pin_arc_seize_sound = bool(v)
        return bool(self._sev_pin_arc_seize_sound)

    def set_sev_pin_arc_seize_sound(self, enabled: bool = True, *, persist: bool = True) -> bool:
        """wave42: 配置抢占蜂鸣开关."""
        self._sev_pin_arc_seize_sound = bool(enabled)
        if persist:
            try:
                self._host_settings().setValue(
                    'host/sevPinArcSeizeSound', bool(enabled))
            except Exception:
                pass
        return self._sev_pin_arc_seize_sound

    def sev_pin_arc_seize_color_presets(self) -> list:
        """wave43: 抢占闪色预设色板."""
        return [
            ('#ffffff', '白'),
            ('#f0c040', '金'),
            ('#3ecf8e', '绿'),
            ('#4fc3f7', '青'),
            ('#ff66aa', '粉'),
            ('#ff7043', '橙'),
            ('#e57373', '红'),
            ('#b39ddb', '紫'),
        ]

    def sev_pin_arc_seize_recent_colors(self) -> list:
        """wave44: 最近使用的抢占色（最多 6）."""
        recent = list(getattr(self, '_sev_pin_arc_seize_recent', None) or [])
        out = []
        for c in recent:
            c = str(c or '').strip()
            if not c:
                continue
            if not c.startswith('#'):
                c = '#' + c
            c = c.lower()
            if c not in out:
                out.append(c)
        return out[:6]

    def remember_sev_pin_arc_seize_color(self, color: str, *, persist: bool = True) -> list:
        """wave44: 记入最近色."""
        c = str(color or '').strip() or '#ffffff'
        if not c.startswith('#'):
            c = '#' + c
        c = c.lower()
        recent = [x for x in self.sev_pin_arc_seize_recent_colors() if x != c]
        recent.insert(0, c)
        recent = recent[:6]
        self._sev_pin_arc_seize_recent = recent
        if persist:
            try:
                self._host_settings().setValue(
                    'host/sevPinArcSeizeRecentColors', recent)
            except Exception:
                pass
        return list(recent)

    def clear_sev_pin_arc_seize_recent_color(
            self, color: str = '', *, persist: bool = True) -> list:
        """wave45: 清除一条或全部最近色."""
        color = str(color or '').strip()
        if color:
            if not color.startswith('#'):
                color = '#' + color
            color = color.lower()
            recent = [
                c for c in self.sev_pin_arc_seize_recent_colors() if c != color]
            self._last_sev_pin_arc_seize_recent_cleared = color
        else:
            recent = []
            self._last_sev_pin_arc_seize_recent_cleared = '*'
        self._sev_pin_arc_seize_recent = recent
        if persist:
            try:
                self._host_settings().setValue(
                    'host/sevPinArcSeizeRecentColors', recent)
            except Exception:
                pass
        try:
            if color:
                self._flash_host_toast(f'已清除最近色 · {color}', kind='info', ms=1200)
            else:
                self._flash_host_toast('已清空最近色', kind='info', ms=1200)
            self._log_line(
                f'清除最近色 · {color or "全部"}')
        except Exception:
            pass
        return list(recent)

    def clear_sev_pin_arc_seize_recent_colors(self, *, persist: bool = True) -> list:
        """wave45: 清空全部最近色."""
        return self.clear_sev_pin_arc_seize_recent_color('', persist=persist)

    def reorder_sev_pin_arc_seize_recent_colors(
            self, order=None, *, persist: bool = True) -> list:
        """wave46: 按给定顺序重排最近色（拖拽排序落盘）."""
        cur = self.sev_pin_arc_seize_recent_colors()
        if order is None:
            return list(cur)
        seen = set()
        out = []
        for c in list(order or []):
            c = str(c or '').strip()
            if not c:
                continue
            if not c.startswith('#'):
                c = '#' + c
            c = c.lower()
            if c in seen:
                continue
            if c not in cur:
                continue
            seen.add(c)
            out.append(c)
        # append leftovers keeping relative order
        for c in cur:
            if c not in seen:
                out.append(c)
        out = out[:6]
        self._sev_pin_arc_seize_recent = out
        if persist:
            try:
                self._host_settings().setValue(
                    'host/sevPinArcSeizeRecentColors', out)
            except Exception:
                pass
        self._last_sev_pin_arc_seize_recent_reordered = list(out)
        try:
            self._log_line(f'最近色拖拽排序 · {len(out)}')
        except Exception:
            pass
        return list(out)

    def move_sev_pin_arc_seize_recent_color(
            self, color: str, to_index: int = 0, *, persist: bool = True) -> list:
        """wave46: 将一条最近色移到 to_index."""
        color = str(color or '').strip()
        if color and not color.startswith('#'):
            color = '#' + color
        color = color.lower()
        cur = self.sev_pin_arc_seize_recent_colors()
        if color not in cur:
            return list(cur)
        cur = [c for c in cur if c != color]
        try:
            to_index = int(to_index)
        except Exception:
            to_index = 0
        to_index = max(0, min(len(cur), to_index))
        cur.insert(to_index, color)
        return self.reorder_sev_pin_arc_seize_recent_colors(cur, persist=persist)

    def show_sev_pin_arc_seize_recent_reorder_dialog(self) -> list:
        """wave46: 最近色拖拽排序对话框（InternalMove）."""
        recent = self.sev_pin_arc_seize_recent_colors()
        if not recent:
            try:
                self._flash_host_toast('无最近色可排序', kind='info', ms=1200)
            except Exception:
                pass
            self._last_sev_pin_arc_seize_recent_reorder_shown = False
            return []
        try:
            dlg = QDialog(self)
            dlg.setWindowTitle('拖拽排序最近色')
            dlg.setObjectName('hostSevPinArcSeizeRecentReorderDialog')
            dlg.setMinimumWidth(320)
            lay = QVBoxLayout(dlg)
            tip = QLabel('拖拽条目调整顺序 · 确定后写入最近色', dlg)
            tip.setStyleSheet('color:#9aa0a6;font-size:11px;')
            lay.addWidget(tip)
            lst = QListWidget(dlg)
            lst.setObjectName('hostSevPinArcSeizeRecentReorderList')
            try:
                lst.setDragDropMode(
                    QAbstractItemView.DragDropMode.InternalMove)
                lst.setDefaultDropAction(Qt.DropAction.MoveAction)
                lst.setDragEnabled(True)
                lst.setAcceptDrops(True)
            except Exception:
                pass
            for c in recent:
                it = QListWidgetItem(c)
                it.setData(Qt.ItemDataRole.UserRole, c)
                it.setToolTip(f'{c}\n拖拽调整顺序')
                lst.addItem(it)
            lay.addWidget(lst)
            btns = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Ok
                | QDialogButtonBox.StandardButton.Cancel, parent=dlg)
            btns.accepted.connect(dlg.accept)
            btns.rejected.connect(dlg.reject)
            lay.addWidget(btns)
            self._last_sev_pin_arc_seize_recent_reorder_dialog = dlg
            self._last_sev_pin_arc_seize_recent_reorder_list = lst
            self._last_sev_pin_arc_seize_recent_reorder_shown = True
            if getattr(self, '_seize_recent_reorder_no_exec', False):
                return list(recent)

            def _apply_from_list() -> list:
                order = []
                for i in range(lst.count()):
                    it = lst.item(i)
                    if it is None:
                        continue
                    c = str(it.data(Qt.ItemDataRole.UserRole) or it.text() or '').strip()
                    if c:
                        order.append(c)
                return self.reorder_sev_pin_arc_seize_recent_colors(order)

            if dlg.exec() == QDialog.DialogCode.Accepted:
                out = _apply_from_list()
                try:
                    self._flash_host_toast(
                        f'最近色已排序 · {len(out)}', kind='ok', ms=1200, animate=True)
                except Exception:
                    pass
                # live rebuild open color menu if any
                menu = getattr(self, '_last_sev_pin_arc_seize_color_menu', None)
                if menu is not None:
                    try:
                        self._rebuild_sev_pin_arc_seize_recent_section(menu)
                    except Exception:
                        pass
                return out
            return list(recent)
        except Exception as err:
            try:
                self._flash_host_toast(f'排序对话框失败 · {err}', kind='info')
            except Exception:
                pass
            self._last_sev_pin_arc_seize_recent_reorder_shown = False
            return list(recent)

    def pick_sev_pin_arc_seize_custom_color(self, color: str = '') -> str:
        """wave44: 自定义抢占色；smoke 可传 color 或设 _seize_color_no_dialog."""
        color = str(color or '').strip()
        if not color and not getattr(self, '_seize_color_no_dialog', False):
            try:
                cur = QColor(self.sev_pin_arc_seize_color())
                picked = QColorDialog.getColor(cur, self, '自定义抢占闪色')
                if picked is not None and picked.isValid():
                    color = picked.name()
            except Exception:
                color = ''
        if not color and getattr(self, '_seize_color_no_dialog', False):
            # smoke default custom
            color = str(getattr(self, '_seize_color_smoke_pick', '') or '#aabbcc')
        if not color:
            self._last_sev_pin_arc_seize_custom = ''
            return ''
        c = self._apply_sev_pin_arc_seize_color_preset(color)
        self._last_sev_pin_arc_seize_custom = c
        return c

    def _on_sev_pin_arc_seize_color_menu_event(self, obj, event):
        """wave45–47: 最近色右键清除；Alt+↑/↓ 微调顺序."""
        try:
            from PySide6.QtCore import QEvent
            menu = getattr(self, '_last_sev_pin_arc_seize_color_menu', None)
            if menu is None or obj is not menu:
                return False
            et = event.type()
            # wave47: Alt+Up/Down reorder active/recent under cursor
            if et == QEvent.Type.KeyPress:
                mods = event.modifiers()
                alt = bool(mods & Qt.KeyboardModifier.AltModifier)
                if not alt:
                    return False
                key = event.key()
                delta = 0
                if key in (Qt.Key.Key_Up, getattr(Qt, 'Key_Up', 16777235)):
                    delta = -1
                elif key in (Qt.Key.Key_Down, getattr(Qt, 'Key_Down', 16777237)):
                    delta = 1
                else:
                    return False
                act = None
                try:
                    act = menu.activeAction()
                except Exception:
                    act = None
                color = ''
                if act is not None and act.property('isSeizeColorRecent'):
                    color = str(act.data() or '').strip()
                if not color:
                    # wave48: 菜单内拖拽列表当前项
                    lst = getattr(self, '_last_sev_pin_arc_seize_recent_drag_list', None)
                    if lst is not None:
                        try:
                            it = lst.currentItem()
                            if it is not None:
                                color = str(it.data(Qt.ItemDataRole.UserRole) or '').strip()
                        except Exception:
                            pass
                if not color:
                    for a in menu.actions():
                        try:
                            if a.property('isSeizeColorRecent') and a.isChecked():
                                color = str(a.data() or '').strip()
                                if color:
                                    break
                        except Exception:
                            continue
                if not color:
                    return False
                recent = self.sev_pin_arc_seize_recent_colors()
                try:
                    idx = recent.index(color if color.startswith('#') else '#' + color.lower())
                except ValueError:
                    c = color.lower() if color.startswith('#') else ('#' + color.lower())
                    try:
                        idx = recent.index(c)
                        color = c
                    except ValueError:
                        return False
                new_idx = max(0, min(len(recent) - 1, idx + delta))
                if new_idx == idx:
                    self._last_sev_pin_arc_seize_recent_alt_moved = color
                    return True
                self.move_sev_pin_arc_seize_recent_color(color, new_idx)
                try:
                    self._rebuild_sev_pin_arc_seize_recent_section(menu)
                    for a in menu.actions():
                        if a.property('isSeizeColorRecent') and str(a.data() or '').lower() == color.lower():
                            menu.setActiveAction(a)
                            break
                    lst = getattr(self, '_last_sev_pin_arc_seize_recent_drag_list', None)
                    if lst is not None:
                        for i in range(lst.count()):
                            it = lst.item(i)
                            if it and str(it.data(Qt.ItemDataRole.UserRole) or '').lower() == color.lower():
                                lst.setCurrentRow(i)
                                break
                except Exception:
                    pass
                self._last_sev_pin_arc_seize_recent_alt_moved = color
                self._last_sev_pin_arc_seize_recent_alt_delta = delta
                return True
            if et != QEvent.Type.MouseButtonPress:
                return False
            if event.button() != Qt.MouseButton.RightButton:
                return False
            try:
                act = menu.actionAt(event.pos())
            except Exception:
                act = None
            if act is None or not act.property('isSeizeColorRecent'):
                return False
            color = str(act.data() or '').strip()
            if not color:
                return False
            self.clear_sev_pin_arc_seize_recent_color(color)
            # rebuild live menu if still open
            try:
                self._rebuild_sev_pin_arc_seize_recent_section(menu)
            except Exception:
                pass
            self._last_sev_pin_arc_seize_recent_rmb_cleared = color
            return True
        except Exception:
            return False

    def _make_sev_pin_arc_seize_recent_drag_list(self, parent=None):
        """wave48: 菜单内最近色拖拽列表（InternalMove）."""
        lst = QListWidget(parent)
        lst.setObjectName('hostSevPinArcSeizeRecentDragList')
        lst.setMaximumHeight(132)
        lst.setMinimumWidth(180)
        try:
            lst.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
            lst.setDefaultDropAction(Qt.DropAction.MoveAction)
            lst.setDragEnabled(True)
            lst.setAcceptDrops(True)
            lst.setSpacing(1)
            lst.setSelectionMode(
                QAbstractItemView.SelectionMode.ExtendedSelection)
        except Exception:
            pass
        cur = self.sev_pin_arc_seize_color().lower()
        for color in self.sev_pin_arc_seize_recent_colors()[:6]:
            mark = '✓ ' if color == cur else ''
            it = QListWidgetItem(f'{mark}最近  {color}')
            it.setData(Qt.ItemDataRole.UserRole, color)
            it.setToolTip(
                f'{color}\n拖拽调序 · 单击应用 · 右键置顶/删除 · Del多选删除 · Home置顶 · Ctrl+A全选 · Shift连选'
            )
            lst.addItem(it)

        def _apply_order():
            order = []
            for i in range(lst.count()):
                it = lst.item(i)
                if it is None:
                    continue
                c = str(it.data(Qt.ItemDataRole.UserRole) or '').strip()
                if c:
                    order.append(c)
            if order:
                self.reorder_sev_pin_arc_seize_recent_colors(order)
                self._last_sev_pin_arc_seize_recent_menu_dragged = list(order)

        def _on_rows_moved(*_a):
            _apply_order()

        try:
            lst.model().rowsMoved.connect(lambda *_: _apply_order())
        except Exception:
            pass

        def _on_click(item):
            if item is None:
                return
            c = str(item.data(Qt.ItemDataRole.UserRole) or '').strip()
            if c:
                self._apply_sev_pin_arc_seize_color_preset(c)

        lst.itemClicked.connect(_on_click)

        def _rebuild_parent_menu():
            menu = getattr(self, '_last_sev_pin_arc_seize_color_menu', None)
            if menu is not None:
                try:
                    self._rebuild_sev_pin_arc_seize_recent_section(menu)
                except Exception:
                    pass

        def _on_list_context(pos):
            it = lst.itemAt(pos)
            if it is None:
                return
            c = str(it.data(Qt.ItemDataRole.UserRole) or '').strip()
            if not c:
                return
            cm = QMenu(lst)
            cm.setObjectName('hostSevPinArcSeizeRecentDragCtx')
            act_top = cm.addAction('置顶')
            act_top.setProperty('isSeizeRecentPinTop', True)
            act_top.setData(c)
            act_del = cm.addAction('删除单项')
            act_del.setProperty('isSeizeRecentDeleteOne', True)
            act_del.setData(c)
            self._last_sev_pin_arc_seize_recent_drag_ctx = cm
            self._last_sev_pin_arc_seize_recent_drag_ctx_color = c
            if getattr(self, '_sev_pin_arc_seize_recent_drag_ctx_no_exec', False):
                return
            chosen = cm.exec(lst.mapToGlobal(pos))
            if chosen is act_top:
                self.move_sev_pin_arc_seize_recent_color(c, 0)
                self._last_sev_pin_arc_seize_recent_pinned = c
                _rebuild_parent_menu()
            elif chosen is act_del:
                self.clear_sev_pin_arc_seize_recent_color(c)
                self._last_sev_pin_arc_seize_recent_deleted = c
                _rebuild_parent_menu()

        lst.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        lst.customContextMenuRequested.connect(_on_list_context)

        _orig_key = lst.keyPressEvent

        def _on_list_key(event):
            try:
                key = event.key()
            except Exception:
                return _orig_key(event)
            it = lst.currentItem()
            c = ''
            if it is not None:
                c = str(it.data(Qt.ItemDataRole.UserRole) or '').strip()
            if key in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
                selected = []
                for sit in lst.selectedItems():
                    sc = str(sit.data(Qt.ItemDataRole.UserRole) or '').strip()
                    if sc and sc not in selected:
                        selected.append(sc)
                if not selected and c:
                    selected = [c]
                if selected:
                    for sc in selected:
                        self.clear_sev_pin_arc_seize_recent_color(sc)
                    self._last_sev_pin_arc_seize_recent_key_deleted = list(selected)
                    self._last_sev_pin_arc_seize_recent_key_deleted_n = len(selected)
                    _rebuild_parent_menu()
                    try:
                        event.accept()
                    except Exception:
                        pass
                    return
            if c and key == Qt.Key.Key_Home:
                self.move_sev_pin_arc_seize_recent_color(c, 0)
                self._last_sev_pin_arc_seize_recent_key_pinned = c
                _rebuild_parent_menu()
                try:
                    event.accept()
                except Exception:
                    pass
                return
            # wave52: Ctrl+A 全选
            try:
                mods = event.modifiers()
            except Exception:
                mods = Qt.KeyboardModifier.NoModifier
            if (key == Qt.Key.Key_A and (
                    mods & Qt.KeyboardModifier.ControlModifier)):
                try:
                    lst.selectAll()
                    self._last_sev_pin_arc_seize_recent_key_select_all = True
                    self._last_sev_pin_arc_seize_recent_key_select_all_n = len(
                        lst.selectedItems())
                    event.accept()
                except Exception:
                    pass
                return
            # wave53: Shift 按下时提示连选
            if key in (Qt.Key.Key_Shift,):
                try:
                    self._show_sev_pin_arc_seize_recent_shift_hint(lst)
                except Exception:
                    pass
            return _orig_key(event)

        lst.keyPressEvent = _on_list_key

        def _on_sel_changed():
            try:
                mods = QApplication.keyboardModifiers()
            except Exception:
                mods = Qt.KeyboardModifier.NoModifier
            n = 0
            try:
                n = len(lst.selectedItems())
            except Exception:
                n = 0
            if mods & Qt.KeyboardModifier.ShiftModifier:
                try:
                    self._show_sev_pin_arc_seize_recent_shift_hint(lst, n=n)
                except Exception:
                    pass
            self._last_sev_pin_arc_seize_recent_sel_n = n

        try:
            lst.itemSelectionChanged.connect(_on_sel_changed)
        except Exception:
            pass
        try:
            lst.setStatusTip('Shift 连选 · Ctrl+A 全选 · Del 多删 · 拖拽调序')
            lst.setWhatsThis(
                '最近色拖拽列表：Shift 按住后点选可连选区间；'
                'Ctrl+A 全选；Del/Backspace 删除选中；Home 置顶当前。')
        except Exception:
            pass
        self._last_sev_pin_arc_seize_recent_drag_list = lst
        self._last_sev_pin_arc_seize_recent_shift_hint = True
        return lst

    def _show_sev_pin_arc_seize_recent_shift_hint(self, lst=None, n: int = None):
        """wave53: Shift 连选浮动提示."""
        if lst is None:
            lst = getattr(self, '_last_sev_pin_arc_seize_recent_drag_list', None)
        if n is None:
            try:
                n = len(lst.selectedItems()) if lst is not None else 0
            except Exception:
                n = 0
        msg = f'Shift 连选 · 已选 {int(n)} 项' if n else 'Shift 连选 · 按住 Shift 点选区间'
        self._last_sev_pin_arc_seize_recent_shift_hint_text = msg
        self._last_sev_pin_arc_seize_recent_shift_hint_n = int(n or 0)
        try:
            if lst is not None:
                gp = lst.mapToGlobal(lst.rect().bottomLeft())
                QToolTip.showText(gp, msg, lst, lst.rect(), 1800)
            else:
                QToolTip.showText(
                    self.mapToGlobal(self.rect().center()), msg, self)
        except Exception:
            pass
        return msg

    def _rebuild_sev_pin_arc_seize_recent_section(self, menu):
        """wave45–48: 右键清除后热更最近区；含菜单内拖拽列表."""
        if menu is None:
            return
        # remove old recent actions + header + clear-all + drag widget
        for act in list(menu.actions()):
            try:
                if (act.property('isSeizeColorRecent')
                        or act.property('isSeizeRecentHeader')
                        or act.property('isSeizeRecentClearAll')
                        or act.property('isSeizeRecentReorder')
                        or act.property('isSeizeRecentDrag')
                        or act.property('isSeizeRecentSep')):
                    menu.removeAction(act)
            except Exception:
                continue
        # find insert point: before custom or sound
        before = None
        for act in menu.actions():
            try:
                if (act.property('isSeizeColorCustom')
                        or act.property('isSeizeSoundToggle')):
                    before = act
                    break
            except Exception:
                continue
        recent = self.sev_pin_arc_seize_recent_colors()
        cur = self.sev_pin_arc_seize_color().lower()
        def _ins(a):
            if before is not None:
                menu.insertAction(before, a)
            else:
                menu.addAction(a)
        if recent:
            sep = menu.insertSeparator(before) if before is not None else menu.addSeparator()
            try:
                sep.setProperty('isSeizeRecentSep', True)
            except Exception:
                pass
            act_hdr = QAction('最近（菜单内拖拽 · 右键清除 · Alt↑↓）', menu)
            act_hdr.setEnabled(False)
            act_hdr.setProperty('isSeizeRecentHeader', True)
            _ins(act_hdr)
            try:
                drag_act = QWidgetAction(menu)
                drag_act.setProperty('isSeizeRecentDrag', True)
                drag_lst = self._make_sev_pin_arc_seize_recent_drag_list(menu)
                drag_act.setDefaultWidget(drag_lst)
                _ins(drag_act)
            except Exception:
                for color in recent[:6]:
                    mark = '✓ ' if color == cur else ''
                    act = QAction(f'{mark}最近  {color}', menu)
                    act.setData(color)
                    act.setProperty('isSeizeColorRecent', True)
                    act.setCheckable(True)
                    act.setChecked(color == cur)
                    act.setToolTip('左键应用 · 右键清除 · Alt↑↓调序')
                    act.triggered.connect(
                        lambda *_a, c=color: self._apply_sev_pin_arc_seize_color_preset(c)
                    )
                    _ins(act)
            # keep invisible recent actions for Alt↑↓ / eventFilter compatibility
            for color in recent[:6]:
                act = QAction(color, menu)
                act.setData(color)
                act.setProperty('isSeizeColorRecent', True)
                act.setVisible(False)
                act.setCheckable(True)
                act.setChecked(color == cur)
                act.triggered.connect(
                    lambda *_a, c=color: self._apply_sev_pin_arc_seize_color_preset(c)
                )
                _ins(act)
            act_clear = QAction('清除全部最近色', menu)
            act_clear.setProperty('isSeizeRecentClearAll', True)
            act_clear.triggered.connect(
                lambda *_: self.clear_sev_pin_arc_seize_recent_colors())
            _ins(act_clear)
            act_ord = QAction('拖拽排序最近色…', menu)
            act_ord.setProperty('isSeizeRecentReorder', True)
            act_ord.triggered.connect(
                lambda *_: self.show_sev_pin_arc_seize_recent_reorder_dialog())
            _ins(act_ord)

    def _build_sev_pin_arc_seize_color_menu(self, parent=None):
        """wave43–45: 抢占色板 · 预设 + 最近(右键清除) + 自定义."""
        menu = QMenu('进度弧抢占色', parent or self)
        menu.setObjectName('hostSevPinArcSeizeColorMenu')
        cur = self.sev_pin_arc_seize_color().lower()
        for color, name in self.sev_pin_arc_seize_color_presets():
            mark = '✓ ' if color.lower() == cur else ''
            act = QAction(f'{mark}{name}  {color}', menu)
            act.setData(color)
            act.setProperty('isSeizeColorPreset', True)
            act.setCheckable(True)
            act.setChecked(color.lower() == cur)
            act.triggered.connect(
                lambda *_a, c=color: self._apply_sev_pin_arc_seize_color_preset(c)
            )
            menu.addAction(act)
        recent = self.sev_pin_arc_seize_recent_colors()
        preset_set = {c.lower() for c, _ in self.sev_pin_arc_seize_color_presets()}
        recent_extra = [c for c in recent if c not in preset_set]
        if recent:
            sep = menu.addSeparator()
            try:
                sep.setProperty('isSeizeRecentSep', True)
            except Exception:
                pass
            act_hdr = QAction('最近（菜单内拖拽 · 右键清除 · Alt↑↓）', menu)
            act_hdr.setEnabled(False)
            act_hdr.setProperty('isSeizeRecentHeader', True)
            menu.addAction(act_hdr)
            try:
                drag_act = QWidgetAction(menu)
                drag_act.setProperty('isSeizeRecentDrag', True)
                drag_act.setObjectName('hostSevPinArcSeizeRecentDragAct')
                drag_lst = self._make_sev_pin_arc_seize_recent_drag_list(menu)
                drag_act.setDefaultWidget(drag_lst)
                menu.addAction(drag_act)
            except Exception:
                for color in recent[:6]:
                    mark = '✓ ' if color == cur else ''
                    act = QAction(f'{mark}最近  {color}', menu)
                    act.setData(color)
                    act.setProperty('isSeizeColorRecent', True)
                    act.setCheckable(True)
                    act.setChecked(color == cur)
                    act.setToolTip('左键应用 · 右键清除 · Alt↑↓调序')
                    act.triggered.connect(
                        lambda *_a, c=color: self._apply_sev_pin_arc_seize_color_preset(c)
                    )
                    menu.addAction(act)
            for color in recent[:6]:
                act = QAction(color, menu)
                act.setData(color)
                act.setProperty('isSeizeColorRecent', True)
                act.setVisible(False)
                act.setCheckable(True)
                act.setChecked(color == cur)
                act.triggered.connect(
                    lambda *_a, c=color: self._apply_sev_pin_arc_seize_color_preset(c)
                )
                menu.addAction(act)
            act_clear = QAction('清除全部最近色', menu)
            act_clear.setProperty('isSeizeRecentClearAll', True)
            act_clear.setObjectName('hostSevPinArcSeizeRecentClearAll')
            act_clear.triggered.connect(
                lambda *_: self.clear_sev_pin_arc_seize_recent_colors())
            menu.addAction(act_clear)
            act_ord = QAction('拖拽排序最近色…', menu)
            act_ord.setProperty('isSeizeRecentReorder', True)
            act_ord.setObjectName('hostSevPinArcSeizeRecentReorder')
            act_ord.setToolTip('打开列表 · 拖拽调整最近色顺序')
            act_ord.triggered.connect(
                lambda *_: self.show_sev_pin_arc_seize_recent_reorder_dialog())
            menu.addAction(act_ord)
        menu.addSeparator()
        act_custom = QAction('自定义…', menu)
        act_custom.setObjectName('hostSevPinArcSeizeCustomColor')
        act_custom.setProperty('isSeizeColorCustom', True)
        act_custom.triggered.connect(
            lambda *_: self.pick_sev_pin_arc_seize_custom_color())
        menu.addAction(act_custom)
        snd = self.sev_pin_arc_seize_sound()
        act_snd = QAction(('✓ ' if snd else '') + '抢占蜂鸣', menu)
        act_snd.setCheckable(True)
        act_snd.setChecked(snd)
        act_snd.setProperty('isSeizeSoundToggle', True)
        act_snd.triggered.connect(
            lambda *_: self.set_sev_pin_arc_seize_sound(
                not self.sev_pin_arc_seize_sound())
        )
        menu.addAction(act_snd)
        # wave45: 安装右键清除过滤器
        try:
            menu.installEventFilter(self)
            self._sev_pin_arc_seize_color_menu_filter = True
        except Exception:
            pass
        self._last_sev_pin_arc_seize_color_menu = menu
        self._last_sev_pin_arc_seize_recent_extra = recent_extra
        return menu

    def _apply_sev_pin_arc_seize_color_preset(self, color: str) -> str:
        """wave43–44: 应用色板预设/自定义并记入最近."""
        c = self.set_sev_pin_arc_seize_color(color, persist=True)
        try:
            self.remember_sev_pin_arc_seize_color(c, persist=True)
        except Exception:
            pass
        try:
            self._flash_host_toast(f'抢占闪色 → {c}', kind='ok', ms=1200)
            self._log_line(f'抢占闪色 → {c}')
        except Exception:
            pass
        self._last_sev_pin_arc_seize_preset = c
        return c

    def _flash_sev_pin_arc_seize(self, prev: str, owner: str):
        """wave41–42: 抢占可视化 — 可配闪色/蜂鸣 + tip."""
        arc = getattr(self, '_sev_pin_arc', None)
        if arc is None:
            return
        saved = ''
        try:
            saved = arc.color()
        except Exception:
            saved = '#f0c040'
        flash_c = self.sev_pin_arc_seize_color()
        try:
            arc.set_color(flash_c)
            arc.update()
        except Exception:
            pass
        if self.sev_pin_arc_seize_sound():
            try:
                QApplication.beep()
                self._last_sev_pin_arc_seize_beeped = True
            except Exception:
                self._last_sev_pin_arc_seize_beeped = False
        else:
            self._last_sev_pin_arc_seize_beeped = False
        tip = f'进度弧抢占 · {prev}→{owner}'
        try:
            self._flash_host_toast(tip, kind='info', ms=900)
            self._log_line(tip)
        except Exception:
            pass
        self._last_sev_pin_arc_seize_tip = tip
        self._last_sev_pin_arc_seize_flash_color = flash_c
        timer = getattr(self, '_sev_pin_arc_seize_timer', None)
        if timer is None:
            timer = QTimer(self)
            timer.setSingleShot(True)
            self._sev_pin_arc_seize_timer = timer

            def _restore():
                a = getattr(self, '_sev_pin_arc', None)
                c = getattr(self, '_sev_pin_arc_seize_restore', '') or saved
                if a is not None:
                    try:
                        a.set_color(c)
                    except Exception:
                        pass

            timer.timeout.connect(_restore)
        self._sev_pin_arc_seize_restore = saved
        timer.start(180)

    def _show_sev_bubble_pin_arc(self, p: float):
        """wave39–41: 气泡弧（共享单例 overlay）；抢占可视化."""
        arc = getattr(self, '_sev_pin_arc', None) or getattr(self, '_sev_bubble_pin_arc', None)
        key = str(getattr(self, '_sev_bubble_pin_key', '') or '')
        bubbles = getattr(self, '_alarm_sev_count_bubbles', None) or {}
        bubble = bubbles.get(key)
        if arc is None or bubble is None:
            return
        try:
            self.claim_sev_pin_arc('bubble', flash=True)
            gp = bubble.mapTo(self, QPoint(0, 0))
            ax = gp.x() + max(0, (bubble.width() - arc.width()) // 2)
            ay = gp.y() + max(0, (bubble.height() - arc.height()) // 2)
            arc.move(ax, ay)
            arc.set_progress(p)
            arc.show()
            arc.raise_()
        except Exception:
            pass

    def _hide_sev_bubble_pin_arc(self):
        tick = getattr(self, '_sev_bubble_pin_tick', None)
        if tick is not None and tick.isActive():
            tick.stop()
        # only hide if we own the shared arc
        if str(getattr(self, '_sev_pin_arc_owner', '') or '') in ('bubble', ''):
            arc = getattr(self, '_sev_pin_arc', None) or getattr(self, '_sev_bubble_pin_arc', None)
            if arc is not None:
                try:
                    arc.set_progress(0.0)
                    arc.hide()
                except Exception:
                    pass
            self._sev_pin_arc_owner = ''
        self._sev_bubble_pin_press_ms = 0

    def pin_alarm_severity_filter(self, pinned: bool = True, key: str = '', *, persist: bool = True) -> bool:
        """wave32: 钉住/取消严重度筛."""
        pinned = bool(pinned)
        if pinned:
            k = str(key or getattr(self, '_sev_bubble_pin_key', '') or self.alarm_severity_filter() or 'all').strip().lower()
            if k in ('warn',):
                k = 'warning'
            if k not in ('all', 'error', 'warning', 'info'):
                k = 'all'
            self._alarm_sev_pinned = True
            self._alarm_sev_pinned_key = k
            self.set_alarm_severity_filter(k, persist=True, force=True)
            try:
                self._log_line(f'严重度已钉住 · {k}')
            except Exception:
                pass
        else:
            self._alarm_sev_pinned = False
            self._alarm_sev_pinned_key = ''
            try:
                self._log_line('严重度钉住已取消')
            except Exception:
                pass
        if persist:
            try:
                val = self._alarm_sev_pinned_key if self._alarm_sev_pinned else ''
                self._host_settings().setValue('host/alarmSevPinned', val)
            except Exception:
                pass
        try:
            self._sync_alarm_sev_chips()
        except Exception:
            pass
        return True

    def _on_sev_chip_enter(self, event=None, key: str = 'all'):
        """wave35–36: sev chip 悬停预览钉；可长按落钉."""
        key = str(key or 'all').strip().lower()
        self._sev_chip_hover_key = key
        chips = getattr(self, '_alarm_sev_chips', None) or {}
        b = chips.get(key)
        if b is None:
            return
        pinned = bool(getattr(self, '_alarm_sev_pinned', False))
        pinned_key = str(getattr(self, '_alarm_sev_pinned_key', '') or '')
        if pinned and pinned_key == key:
            return  # already real-pinned
        labels = getattr(self, '_alarm_sev_chip_labels', None) or {}
        base = labels.get(key, key)
        styles = {
            'all': ('#2a3340', '#9aa0a6'),
            'error': ('#3a1c1c', '#e35d6a'),
            'warning': ('#3a3420', '#e0b84a'),
            'info': ('#1c2a3a', '#6eb6ff'),
        }
        bg, fg = styles.get(key, styles['all'])
        try:
            b.setText('📍' + base)
            b.setStyleSheet(
                f'background:{bg};color:{fg};border:1px dashed #f0c040;'
                f'border-radius:3px;font-size:10px;font-weight:700;padding:1px 4px;'
            )
            b.setToolTip(f'悬停预览钉 · {base} · 长按落钉 · Alt+P')
            QToolTip.showText(
                b.mapToGlobal(QPoint(0, b.height())),
                f'预览钉 · {base} · 长按落钉',
                b,
            )
        except Exception:
            pass

    def _on_sev_chip_leave(self, event=None, key: str = 'all'):
        """wave35–37: 离开芯片 → 取消预览钉；停长按/收弧."""
        timer = getattr(self, '_sev_chip_pin_timer', None)
        if timer is not None and timer.isActive():
            timer.stop()
        self._hide_sev_chip_pin_arc()
        if str(getattr(self, '_sev_chip_hover_key', '') or '') == str(key or ''):
            self._sev_chip_hover_key = ''
        try:
            QToolTip.hideText()
        except Exception:
            pass
        try:
            self._sync_alarm_sev_chips()
        except Exception:
            pass

    def _on_sev_chip_press(self, event=None, key: str = 'all'):
        """wave36–37: 芯片按下 — 长按计时 + 进度弧."""
        try:
            if event is not None and hasattr(event, 'button'):
                if event.button() not in (Qt.MouseButton.LeftButton,):
                    return
        except Exception:
            pass
        self._sev_chip_pin_key = str(key or 'all')
        self._sev_chip_long_fired = False
        self._sev_chip_pin_press_ms = 0
        ms = int(getattr(self, '_sev_chip_pin_ms', 550) or 550)
        timer = getattr(self, '_sev_chip_pin_timer', None)
        if timer is not None:
            timer.start(ms)
        tick = getattr(self, '_sev_chip_pin_tick', None)
        if tick is not None and not tick.isActive():
            tick.start()
        self._show_sev_chip_pin_arc(0.0)

    def _on_sev_chip_pin_tick(self):
        """wave37: 进度弧推进."""
        tick = getattr(self, '_sev_chip_pin_tick', None)
        interval = int(tick.interval()) if tick is not None else 40
        self._sev_chip_pin_press_ms = int(getattr(self, '_sev_chip_pin_press_ms', 0) or 0) + interval
        ms = max(1, int(getattr(self, '_sev_chip_pin_ms', 550) or 550))
        p = min(1.0, float(self._sev_chip_pin_press_ms) / float(ms))
        self._show_sev_chip_pin_arc(p)

    def _show_sev_chip_pin_arc(self, p: float):
        """wave37–41: 芯片弧（共享单例 overlay）；抢占可视化."""
        arc = getattr(self, '_sev_pin_arc', None) or getattr(self, '_sev_chip_pin_arc', None)
        key = str(getattr(self, '_sev_chip_pin_key', '') or '')
        chips = getattr(self, '_alarm_sev_chips', None) or {}
        chip = chips.get(key)
        if arc is None or chip is None:
            return
        try:
            self.claim_sev_pin_arc('chip', flash=True)
            gp = chip.mapTo(self, QPoint(0, 0))
            ax = gp.x() + max(0, (chip.width() - arc.width()) // 2)
            ay = gp.y() + max(0, (chip.height() - arc.height()) // 2)
            arc.move(ax, ay)
            arc.set_progress(p)
            arc.show()
            arc.raise_()
        except Exception:
            pass

    def _hide_sev_chip_pin_arc(self):
        tick = getattr(self, '_sev_chip_pin_tick', None)
        if tick is not None and tick.isActive():
            tick.stop()
        if str(getattr(self, '_sev_pin_arc_owner', '') or '') in ('chip', ''):
            arc = getattr(self, '_sev_pin_arc', None) or getattr(self, '_sev_chip_pin_arc', None)
            if arc is not None:
                try:
                    arc.set_progress(0.0)
                    arc.hide()
                except Exception:
                    pass
            self._sev_pin_arc_owner = ''
        self._sev_chip_pin_press_ms = 0

    def _on_sev_chip_release(self, event=None, key: str = 'all'):
        """wave36–37: 短按筛档；长按已落钉则跳过；收弧."""
        timer = getattr(self, '_sev_chip_pin_timer', None)
        if timer is not None and timer.isActive():
            timer.stop()
        self._hide_sev_chip_pin_arc()
        if getattr(self, '_sev_chip_long_fired', False):
            return
        try:
            if event is not None and hasattr(event, 'button'):
                if event.button() not in (Qt.MouseButton.LeftButton,):
                    return
        except Exception:
            pass
        self.set_alarm_severity_filter(key)

    def _on_sev_chip_long_press(self):
        """wave36–37: 预览钉长按满弧 → 真正落钉."""
        self._sev_chip_long_fired = True
        self._show_sev_chip_pin_arc(1.0)
        self._hide_sev_chip_pin_arc()
        key = str(getattr(self, '_sev_chip_pin_key', '') or 'all').strip().lower()
        if key not in ('all', 'error', 'warning', 'info'):
            key = 'all'
        self.pin_alarm_severity_filter(True, key=key)
        try:
            self.set_alarm_severity_filter(key, force=True)
        except Exception:
            pass
        labels = {'all': '全部', 'error': '错', 'warning': '警', 'info': '讯'}
        lab = labels.get(key, key)
        msg = f'长按落钉 · {lab}'
        try:
            self._log_line(msg)
            self._flash_host_toast(msg, kind='pin')
        except Exception:
            pass

    def _on_sev_pin_hotkey(self, reverse: bool = False):
        """wave33–36: Alt+P 钉住/切档；Shift+Alt+P 回退切档 + toast."""
        labels = {'all': '全部', 'error': '错', 'warning': '警', 'info': '讯'}
        order = ['all', 'error', 'warning', 'info']
        if getattr(self, '_alarm_sev_pinned', False):
            cur = str(getattr(self, '_alarm_sev_pinned_key', '') or 'all')
            try:
                idx = order.index(cur)
                nxt = order[(idx - 1) % len(order)] if reverse else order[(idx + 1) % len(order)]
            except ValueError:
                nxt = 'all'
            self.pin_alarm_severity_filter(True, key=nxt)
            try:
                self.set_alarm_severity_filter(nxt, force=True)
            except Exception:
                pass
            lab = labels.get(nxt, nxt)
            arrow = '←' if reverse else '→'
            tag = 'Shift+Alt+P' if reverse else 'Alt+P'
            msg = f'{tag} · 切档 {arrow} {lab}'
        else:
            self.pin_alarm_severity_filter(True, key=self.alarm_severity_filter())
            lab = labels.get(self._alarm_sev_pinned_key, self._alarm_sev_pinned_key)
            tag = 'Shift+Alt+P' if reverse else 'Alt+P'
            msg = f'{tag} · 钉住 {lab}'
        try:
            self._log_line(msg)
        except Exception:
            pass
        try:
            self._flash_host_toast(msg, kind='pin')
        except Exception:
            pass

    def _on_sev_pin_badge_clicked(self, event=None):
        """wave33–35: 钉住徽章单击取消钉 + 确认 tip 驻留."""
        try:
            if event is not None and hasattr(event, 'button'):
                if event.button() not in (Qt.MouseButton.LeftButton,):
                    return
        except Exception:
            pass
        if getattr(self, '_alarm_sev_pinned', False):
            prev = str(getattr(self, '_alarm_sev_pinned_key', '') or '')
            self.pin_alarm_severity_filter(False)
            try:
                self._flash_host_toast('徽章 · 取消钉住', kind='pin')
            except Exception:
                pass
            self._show_sev_pin_confirm_tip(prev)

    def _show_sev_pin_confirm_tip(self, prev_key: str = ''):
        """wave35: 解钉确认 tip 驻留 ~2.2s."""
        badge = getattr(self, '_alarm_sev_pin_badge', None)
        labels = {'all': '全部', 'error': '错', 'warning': '警', 'info': '讯'}
        lab = labels.get(prev_key, prev_key or '—')
        msg = f'已解钉 · 原 {lab}'
        # keep badge visible briefly for tip anchor
        if badge is not None:
            try:
                badge.setText('✓')
                badge.setToolTip(msg)
                badge.show()
                QToolTip.showText(
                    badge.mapToGlobal(QPoint(0, badge.height())),
                    msg,
                    badge,
                    badge.rect(),
                    2200,
                )
            except Exception:
                try:
                    QToolTip.showText(
                        badge.mapToGlobal(QPoint(0, badge.height())),
                        msg,
                        badge,
                    )
                except Exception:
                    pass
        timer = getattr(self, '_sev_pin_confirm_tip_timer', None)
        if timer is not None:
            timer.start(2200)

    def _hide_sev_pin_confirm_tip(self):
        """wave35: 确认 tip 驻留结束 → 复位徽章."""
        try:
            QToolTip.hideText()
        except Exception:
            pass
        if getattr(self, '_alarm_sev_pinned', False):
            try:
                self._sync_alarm_sev_chips()
            except Exception:
                pass
            return
        badge = getattr(self, '_alarm_sev_pin_badge', None)
        if badge is not None:
            try:
                badge.setText('')
                badge.hide()
            except Exception:
                pass

    def _on_sev_pin_badge_enter(self, event=None):
        """wave34: 悬停解钉 tip + 脉冲动画."""
        badge = getattr(self, '_alarm_sev_pin_badge', None)
        if badge is None or not getattr(self, '_alarm_sev_pinned', False):
            return
        try:
            QToolTip.showText(
                badge.mapToGlobal(QPoint(0, badge.height())),
                '单击解钉 · Alt+P',
                badge,
            )
        except Exception:
            pass
        self._sev_pin_badge_pulse_on = False
        timer = getattr(self, '_sev_pin_badge_pulse_timer', None)
        if timer is not None and not timer.isActive():
            timer.start()
        self._on_sev_pin_badge_pulse()

    def _on_sev_pin_badge_leave(self, event=None):
        """wave34: 离开停止脉冲."""
        timer = getattr(self, '_sev_pin_badge_pulse_timer', None)
        if timer is not None and timer.isActive():
            timer.stop()
        badge = getattr(self, '_alarm_sev_pin_badge', None)
        if badge is not None:
            try:
                badge.setStyleSheet(
                    'background:transparent;color:#f0c040;border:1px solid transparent;'
                    'border-radius:3px;font-size:11px;font-weight:700;padding:0 3px;'
                )
            except Exception:
                pass
        try:
            QToolTip.hideText()
        except Exception:
            pass

    def _on_sev_pin_badge_pulse(self):
        """wave34: 悬停脉冲边框."""
        badge = getattr(self, '_alarm_sev_pin_badge', None)
        if badge is None:
            return
        on = not bool(getattr(self, '_sev_pin_badge_pulse_on', False))
        self._sev_pin_badge_pulse_on = on
        try:
            if on:
                badge.setStyleSheet(
                    'background:#3a3420;color:#ffe08a;border:1px solid #f0c040;'
                    'border-radius:3px;font-size:11px;font-weight:700;padding:0 3px;'
                )
            else:
                badge.setStyleSheet(
                    'background:transparent;color:#f0c040;border:1px solid #806020;'
                    'border-radius:3px;font-size:11px;font-weight:700;padding:0 3px;'
                )
        except Exception:
            pass

    def _on_sev_bubble_clicked(self, event=None, key: str = 'all'):
        """兼容冒烟/旧 API：按键路由到 press（无 release）."""
        self._on_sev_bubble_press(event, key)
        btn = None
        try:
            if event is not None and hasattr(event, 'button'):
                btn = event.button()
        except Exception:
            btn = None
        if btn is None or btn == Qt.MouseButton.LeftButton:
            # emulate short click if long-press not fired
            if not getattr(self, '_sev_bubble_long_fired', False):
                timer = getattr(self, '_sev_bubble_pin_timer', None)
                if timer is not None and timer.isActive():
                    timer.stop()
                self.set_alarm_severity_filter(key)

    def _collect_alarm_film_paths(self) -> list:
        """wave30: 报警历史中去重 filmPath（保序）."""
        seen = set()
        out = []
        for entry in list(getattr(self, '_alarm_history', None) or []):
            if not isinstance(entry, dict):
                continue
            fp = str(entry.get('filmPath') or '').strip()
            if not fp or fp in seen:
                continue
            seen.add(fp)
            out.append(fp)
        return out

    def _collect_alarm_film_rows(self) -> list:
        """wave31: 带时间戳/严重度的 path 行（按 path 去重，留首次）."""
        seen = set()
        rows = []
        for entry in list(getattr(self, '_alarm_history', None) or []):
            if not isinstance(entry, dict):
                continue
            fp = str(entry.get('filmPath') or '').strip()
            if not fp or fp in seen:
                continue
            seen.add(fp)
            rows.append({
                'ts': str(entry.get('ts') or ''),
                'cleared': '1' if entry.get('cleared') else '0',
                'cleared_at': str(entry.get('cleared_at') or ''),
                'severity': str(entry.get('severity') or ''),
                'path': fp,
                'reason': str(entry.get('reason') or ''),
            })
        return rows

    def copy_all_alarm_film_paths(self, *, as_csv: bool = True) -> bool:
        """wave30–31: 全部唯一 filmPath → 剪贴板；默认含时间戳 CSV."""
        rows = self._collect_alarm_film_rows()
        if not rows:
            try:
                self._log_line('复制全部 paths · 无胶片 path')
            except Exception:
                pass
            return False
        if as_csv:
            lines = ['ts,cleared,cleared_at,severity,path,reason']
            for r in rows:
                # minimal CSV escape
                def esc(v):
                    s = str(v or '')
                    if any(c in s for c in ',"\n'):
                        return '"' + s.replace('"', '""') + '"'
                    return s
                lines.append(','.join(esc(r[k]) for k in ('ts', 'cleared', 'cleared_at', 'severity', 'path', 'reason')))
            text = chr(10).join(lines)
        else:
            text = chr(10).join(r['path'] for r in rows)
        try:
            QApplication.clipboard().setText(text)
            self._log_line(f'已复制全部胶片 path CSV · {len(rows)}')
        except Exception:
            return False
        return True


    def _format_alarm_film_csv(self, rows=None) -> str:
        """wave32: filmPath CSV text（含 cleared）."""
        if rows is None:
            rows = self._collect_alarm_film_rows()
        lines = ['ts,cleared,cleared_at,severity,path,reason']

        def esc(v):
            s = str(v or '')
            if any(c in s for c in (',', '"', chr(10))):
                return '"' + s.replace('"', '""') + '"'
            return s

        for r in rows:
            lines.append(','.join(esc(r.get(k, '')) for k in (
                'ts', 'cleared', 'cleared_at', 'severity', 'path', 'reason')))
        return chr(10).join(lines)

    def alarm_film_csv_dir(self) -> str:
        """wave33–36: 最近另存目录（多档之首）."""
        dirs = self.alarm_film_csv_dirs()
        if dirs:
            return dirs[0]
        try:
            raw = str(self._host_settings().value('host/alarmFilmCsvDir', '') or '').strip()
        except Exception:
            raw = ''
        return raw

    def alarm_film_csv_dirs_max(self) -> int:
        """wave37: 多档另存上限（3–8，默认 5）."""
        return int(getattr(self, '_alarm_film_csv_dirs_max', 5) or 5)

    def set_alarm_film_csv_dirs_max(self, n: int, *, persist: bool = True) -> int:
        """wave37: 配置多档另存上限；超限裁剪."""
        n = max(3, min(8, int(n or 5)))
        self._alarm_film_csv_dirs_max = n
        dirs = self.alarm_film_csv_dirs(max_n=n)
        if len(dirs) > n:
            dirs = dirs[:n]
            try:
                self._host_settings().setValue('host/alarmFilmCsvDirs', dirs)
            except Exception:
                pass
        if persist:
            try:
                self._host_settings().setValue('host/alarmFilmCsvDirsMax', n)
            except Exception:
                pass
        return n

    def cycle_alarm_film_csv_dirs_max(self) -> int:
        """wave37: 循环多档上限 3/5/8."""
        presets = (3, 5, 8)
        cur = self.alarm_film_csv_dirs_max()
        try:
            nxt = presets[(presets.index(cur) + 1) % len(presets)]
        except ValueError:
            nxt = 5
        return self.set_alarm_film_csv_dirs_max(nxt)

    def clear_alarm_film_csv_dirs(self) -> bool:
        """wave37: 清空最近另存多档记忆."""
        try:
            self._host_settings().setValue('host/alarmFilmCsvDirs', [])
            self._host_settings().setValue('host/alarmFilmCsvDir', '')
        except Exception:
            pass
        try:
            self._log_line('最近另存已清档')
            self._flash_host_toast('最近另存已清档', kind='info')
        except Exception:
            pass
        return True

    def remove_alarm_film_csv_dir(self, directory: str) -> list:
        """wave38: 最近另存单项删除."""
        directory = str(directory or '').strip()
        dirs = [d for d in self.alarm_film_csv_dirs() if d != directory]
        try:
            self._host_settings().setValue('host/alarmFilmCsvDirs', dirs)
            self._host_settings().setValue('host/alarmFilmCsvDir', dirs[0] if dirs else '')
        except Exception:
            pass
        try:
            from pathlib import Path as _P
            lab = _P(directory).name if directory else ''
        except Exception:
            lab = directory
        try:
            self._log_line(f'最近另存已删单项 · {lab or directory}')
            self._flash_host_toast(f'已删单项 · {lab or directory}', kind='info')
        except Exception:
            pass
        return list(dirs)

    def promote_alarm_film_csv_dir(self, directory: str) -> list:
        """wave38: 多档记忆置顶."""
        directory = str(directory or '').strip()
        if not directory:
            return self.alarm_film_csv_dirs()
        dirs = self.alarm_film_csv_dirs()
        if directory not in dirs:
            return dirs
        dirs = [directory] + [d for d in dirs if d != directory]
        try:
            self._host_settings().setValue('host/alarmFilmCsvDirs', dirs)
            self._host_settings().setValue('host/alarmFilmCsvDir', dirs[0])
        except Exception:
            pass
        try:
            from pathlib import Path as _P
            lab = _P(directory).name or directory
        except Exception:
            lab = directory
        try:
            self._log_line(f'最近另存已置顶 · {lab}')
            self._flash_host_toast(f'已置顶 · {lab}', kind='ok')
        except Exception:
            pass
        return list(dirs)

    def move_alarm_film_csv_dir(self, from_idx: int, to_idx: int) -> list:
        """wave38: 多档记忆拖序（按下标移动）."""
        dirs = list(self.alarm_film_csv_dirs())
        n = len(dirs)
        if n == 0:
            return dirs
        fi = max(0, min(n - 1, int(from_idx)))
        ti = max(0, min(n - 1, int(to_idx)))
        if fi == ti:
            return dirs
        item = dirs.pop(fi)
        dirs.insert(ti, item)
        return self.reorder_alarm_film_csv_dirs(dirs)

    def reorder_alarm_film_csv_dirs(self, order) -> list:
        """wave38: 按给定顺序重排多档记忆（去重保序，裁剪上限）."""
        max_n = self.alarm_film_csv_dirs_max()
        seen = []
        for d in list(order or []):
            s = str(d or '').strip()
            if s and s not in seen:
                seen.append(s)
            if len(seen) >= max_n:
                break
        # keep any existing not in new order (append)
        for d in self.alarm_film_csv_dirs(max_n=max_n):
            if d not in seen and len(seen) < max_n:
                seen.append(d)
        try:
            self._host_settings().setValue('host/alarmFilmCsvDirs', seen)
            self._host_settings().setValue('host/alarmFilmCsvDir', seen[0] if seen else '')
        except Exception:
            pass
        return list(seen)

    def alarm_film_csv_dir_exists(self, directory: str) -> bool:
        """wave39: 另存目录是否仍存在."""
        directory = str(directory or '').strip()
        if not directory:
            return False
        try:
            from pathlib import Path as _P
            return _P(directory).is_dir()
        except Exception:
            return False

    def stale_alarm_film_csv_dirs(self) -> list:
        """wave39: 失效（不存在）的最近另存目录."""
        return [d for d in self.alarm_film_csv_dirs() if not self.alarm_film_csv_dir_exists(d)]

    def preview_stale_alarm_film_csv_dirs(self) -> list:
        """wave40: 失效清理预览清单（不改动）."""
        return list(self.stale_alarm_film_csv_dirs())

    def prune_stale_alarm_film_csv_dirs(self, *, confirm: bool = True) -> list:
        """wave39–40: 清理失效另存；confirm 时先预览清单确认."""
        stale = self.preview_stale_alarm_film_csv_dirs()
        if not stale:
            try:
                self._flash_host_toast('无失效目录', kind='info')
            except Exception:
                pass
            return list(self.alarm_film_csv_dirs())
        self._last_stale_prune_preview = list(stale)
        do_it = True
        if confirm and not getattr(self, '_prune_stale_no_confirm', False):
            # preview list in message box
            lines = []
            for i, d in enumerate(stale[:12], 1):
                try:
                    from pathlib import Path as _P
                    lab = _P(d).name or d
                except Exception:
                    lab = d
                lines.append(f'{i}. {lab}\n   {d}')
            extra = '' if len(stale) <= 12 else f'\n…另有 {len(stale)-12} 项'
            body = '将删除以下失效目录记忆：\n\n' + '\n'.join(lines) + extra
            try:
                ret = QMessageBox.question(
                    self,
                    '清理失效目录',
                    body,
                    QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
                    QMessageBox.StandardButton.Ok,
                )
                do_it = ret == QMessageBox.StandardButton.Ok
            except Exception:
                do_it = True
            self._last_stale_prune_confirmed = do_it
        else:
            self._last_stale_prune_confirmed = True
        if not do_it:
            try:
                self._flash_host_toast('已取消清理失效', kind='info')
                self._log_line('清理失效另存 · 已取消')
            except Exception:
                pass
            return list(self.alarm_film_csv_dirs())
        before = list(self.alarm_film_csv_dirs())
        kept = [d for d in before if d not in set(stale)]
        # also drop any still-missing
        kept = [d for d in kept if self.alarm_film_csv_dir_exists(d)]
        removed_n = len(stale)
        # wave41: snapshot for undo
        self._stale_prune_undo_dirs = list(before)
        self._stale_prune_undo_removed = list(stale)
        self._stale_prune_can_undo = True
        try:
            self._host_settings().setValue('host/alarmFilmCsvDirs', kept)
            self._host_settings().setValue('host/alarmFilmCsvDir', kept[0] if kept else '')
        except Exception:
            pass
        try:
            ms = int(getattr(self, '_stale_prune_undo_ms', 8000) or 8000)
            self._stale_prune_undo_left_ms = ms
            self._log_line(f'已清理失效另存 · {removed_n} 项（可撤销 {ms//1000}s）')
            self._flash_host_toast(
                f'已清理失效 · {removed_n} · 点此撤销（{ms//1000}s）',
                kind='info',
                ms=ms + 400,
            )
            self._host_toast_click_action = 'undo_prune'
            timer = getattr(self, '_stale_prune_undo_timer', None)
            if timer is not None:
                timer.start()
            try:
                self._show_stale_prune_undo_bar()
            except Exception:
                pass
        except Exception:
            pass
        return list(kept)

    def set_stale_prune_undo_ms(self, ms: int = 8000) -> int:
        """wave42: 失效清理 undo 倒计时时长（ms）."""
        try:
            ms = max(1500, min(30000, int(ms)))
        except Exception:
            ms = 8000
        self._stale_prune_undo_ms = ms
        return ms

    def stale_prune_undo_left_ms(self) -> int:
        """wave42: 剩余可撤销毫秒；0 表示已失效."""
        if not getattr(self, '_stale_prune_can_undo', False):
            return 0
        return max(0, int(getattr(self, '_stale_prune_undo_left_ms', 0) or 0))

    def _refresh_stale_prune_undo_bar_hover_sec(self) -> int:
        """wave46: 悬停时刷新剩余秒 tip / 条内文案."""
        bar = getattr(self, '_stale_prune_undo_bar', None)
        left = self.stale_prune_undo_left_ms()
        sec = max(0, (left + 999) // 1000) if left > 0 else 0
        self._last_stale_prune_undo_bar_hover_sec = sec
        if bar is None:
            return sec
        try:
            if getattr(self, '_stale_prune_undo_bar_hovered', False) and left > 0:
                tip = f'左键撤销 · 中/右键延长 · 剩余 {sec}s'
                bar.setToolTip(tip)
                bar.setFormat(f'剩余 {sec}s')
                bar.setTextVisible(True)
            else:
                bar.setToolTip('左键撤销 · 中/右键延长倒计时')
                bar.setTextVisible(False)
                bar.setFormat('%p%')
        except Exception:
            pass
        return sec

    def _on_stale_prune_undo_bar_enter(self, event=None):
        """wave45–46: 悬停放大 undo 条 + 显示剩余秒."""
        bar = getattr(self, '_stale_prune_undo_bar', None)
        if bar is None:
            return
        self._stale_prune_undo_bar_hovered = True
        try:
            h = int(getattr(self, '_stale_prune_undo_bar_hover_h', 16) or 16)
            bar.setFixedHeight(h)
            self._place_stale_prune_undo_bar()
            bar.raise_()
        except Exception:
            pass
        try:
            self._refresh_stale_prune_undo_bar_hover_sec()
        except Exception:
            pass
        self._last_stale_prune_undo_bar_hovered = True

    def _on_stale_prune_undo_bar_leave(self, event=None):
        """wave45–46: 离开恢复 undo 条高度并隐藏秒数."""
        bar = getattr(self, '_stale_prune_undo_bar', None)
        if bar is None:
            return
        self._stale_prune_undo_bar_hovered = False
        try:
            h = int(getattr(self, '_stale_prune_undo_bar_base_h', 10) or 10)
            bar.setFixedHeight(h)
            self._place_stale_prune_undo_bar()
        except Exception:
            pass
        try:
            self._refresh_stale_prune_undo_bar_hover_sec()
        except Exception:
            pass
        self._last_stale_prune_undo_bar_hovered = False

    def stale_prune_undo_extend_step_ms(self) -> int:
        """wave48: undo 延长步进 ms；0=重置为全长（兼容㊼）."""
        v = getattr(self, '_stale_prune_undo_extend_step_ms', None)
        if v is None:
            try:
                v = int(self._host_settings().value(
                    'host/stalePruneUndoExtendStepMs', 0) or 0)
            except Exception:
                v = 0
            self._stale_prune_undo_extend_step_ms = max(0, min(30000, int(v)))
        return int(self._stale_prune_undo_extend_step_ms)

    def set_stale_prune_undo_extend_step_ms(
            self, ms: int = 0, *, persist: bool = True) -> int:
        """wave48: 配置 undo 延长步进；0 表示延长=重置全长."""
        try:
            ms = max(0, min(30000, int(ms)))
        except Exception:
            ms = 0
        self._stale_prune_undo_extend_step_ms = ms
        if persist:
            try:
                self._host_settings().setValue(
                    'host/stalePruneUndoExtendStepMs', int(ms))
            except Exception:
                pass
        self._last_stale_prune_undo_extend_step_ms = ms
        return ms

    def adjust_stale_prune_undo_extend_step_ms(
            self, delta_ms: int = 1000, *, persist: bool = True) -> int:
        """wave49: 步进 ±delta（钳制 0..30000）."""
        try:
            delta_ms = int(delta_ms)
        except Exception:
            delta_ms = 1000
        cur = self.stale_prune_undo_extend_step_ms()
        return self.set_stale_prune_undo_extend_step_ms(
            cur + delta_ms, persist=persist)

    def extend_stale_prune_undo_by(self, delta_ms: int = 1000) -> int:
        """wave49: 按相对量延长/缩短 undo 剩余（±1s/±3s 预设）."""
        if not self.can_undo_prune_stale_alarm_film_csv_dirs():
            self._last_stale_prune_undo_extended_by = 0
            try:
                self._flash_host_toast('无可延长的清理倒计时', kind='info', ms=1200)
            except Exception:
                pass
            return 0
        try:
            delta_ms = int(delta_ms)
        except Exception:
            delta_ms = 1000
        left = max(0, int(getattr(self, '_stale_prune_undo_left_ms', 0) or 0))
        total = max(1500, min(30000, left + delta_ms))
        self._last_stale_prune_undo_extended_by = int(delta_ms)
        return self.extend_stale_prune_undo(total)

    def _build_stale_prune_undo_step_menu(self, parent=None):
        """wave49: undo 步进/延长快捷预设（±1s/±3s）."""
        menu = QMenu(parent or self)
        menu.setObjectName('hostStalePruneUndoStepMenu')
        for delta, lab in (
            (1000, '延长 +1s'),
            (3000, '延长 +3s'),
            (-1000, '缩短 −1s'),
            (-3000, '缩短 −3s'),
        ):
            act = QAction(lab, menu)
            act.setProperty('isUndoExtendBy', True)
            act.setData(int(delta))
            act.triggered.connect(
                lambda *_a, d=delta: self.extend_stale_prune_undo_by(d))
            menu.addAction(act)
        menu.addSeparator()
        cur = self.stale_prune_undo_extend_step_ms()
        for ms, lab in (
            (1000, '步进设为 1s'),
            (3000, '步进设为 3s'),
            (0, '步进 0（重置全长）'),
        ):
            mark = '✓ ' if int(ms) == int(cur) else ''
            act = QAction(f'{mark}{lab}', menu)
            act.setCheckable(True)
            act.setChecked(int(ms) == int(cur))
            act.setProperty('isUndoStepPreset', True)
            act.setData(int(ms))
            act.triggered.connect(
                lambda *_a, nn=ms: self.set_stale_prune_undo_extend_step_ms(nn))
            menu.addAction(act)
        menu.addSeparator()
        for delta, lab in ((1000, '步进 +1s'), (-1000, '步进 −1s')):
            act = QAction(lab, menu)
            act.setProperty('isUndoStepAdjust', True)
            act.setData(int(delta))
            act.triggered.connect(
                lambda *_a, d=delta: self.adjust_stale_prune_undo_extend_step_ms(d))
            menu.addAction(act)
        menu.addSeparator()
        act_custom_step = QAction('自定义步进 ms…', menu)
        act_custom_step.setProperty('isUndoStepCustom', True)
        act_custom_step.setObjectName('hostStalePruneUndoStepCustom')
        act_custom_step.triggered.connect(
            lambda *_: self.prompt_stale_prune_undo_extend_step_ms())
        menu.addAction(act_custom_step)
        act_custom_ext = QAction('自定义延长 ms…', menu)
        act_custom_ext.setProperty('isUndoExtendCustom', True)
        act_custom_ext.setObjectName('hostStalePruneUndoExtendCustom')
        act_custom_ext.triggered.connect(
            lambda *_: self.prompt_stale_prune_undo_extend_ms())
        menu.addAction(act_custom_ext)
        menu.addSeparator()
        cur_cs = self.stale_prune_undo_color_scale_preset()
        for key, lab in (
            ('traffic', '色阶 · 红绿灯'),
            ('cool', '色阶 · 冷色'),
            ('mono', '色阶 · 单色琥珀'),
            ('sunset', '色阶 · 日落'),
            ('custom', '色阶 · 自定义 RGB'),
        ):
            mark = '✓ ' if key == cur_cs else ''
            act = QAction(f'{mark}{lab}', menu)
            act.setCheckable(True)
            act.setChecked(key == cur_cs)
            act.setProperty('isUndoColorScalePreset', True)
            act.setData(key)
            act.triggered.connect(
                lambda *_a, nn=key: self.set_stale_prune_undo_color_scale_preset(nn))
            menu.addAction(act)
        act_rgb = QAction('自定义 RGB…', menu)
        act_rgb.setProperty('isUndoColorScaleCustomRgb', True)
        act_rgb.setObjectName('hostStalePruneUndoColorCustomRgb')
        act_rgb.triggered.connect(
            lambda *_: self.prompt_stale_prune_undo_color_custom_rgb())
        menu.addAction(act_rgb)
        self._last_stale_prune_undo_step_menu = menu
        return menu

    def prompt_stale_prune_undo_extend_step_ms(self, ms: int = None) -> int:
        """wave50: 自定义步进 ms 输入."""
        cur = self.stale_prune_undo_extend_step_ms()
        if ms is None and not getattr(
                self, '_stale_prune_undo_custom_no_dialog', False):
            try:
                ms, ok = QInputDialog.getInt(
                    self, '自定义 undo 步进',
                    '步进毫秒（0=重置全长）:',
                    int(cur), 0, 30000, 100)
                if not ok:
                    self._last_stale_prune_undo_step_custom = None
                    return cur
            except Exception:
                ms = cur
        if ms is None:
            ms = getattr(self, '_stale_prune_undo_custom_step_ms', cur)
        got = self.set_stale_prune_undo_extend_step_ms(int(ms))
        self._last_stale_prune_undo_step_custom = got
        return got

    def prompt_stale_prune_undo_extend_ms(self, ms: int = None) -> int:
        """wave50: 自定义延长到指定 ms 输入."""
        left = max(0, int(getattr(self, '_stale_prune_undo_left_ms', 0) or 0))
        if ms is None and not getattr(
                self, '_stale_prune_undo_custom_no_dialog', False):
            try:
                ms, ok = QInputDialog.getInt(
                    self, '自定义 undo 延长',
                    '延长至毫秒:',
                    max(1500, left), 1500, 30000, 100)
                if not ok:
                    self._last_stale_prune_undo_extend_custom = None
                    return 0
            except Exception:
                ms = max(1500, left)
        if ms is None:
            ms = getattr(self, '_stale_prune_undo_custom_extend_ms', max(1500, left))
        got = self.extend_stale_prune_undo(int(ms))
        self._last_stale_prune_undo_extend_custom = got
        return got

    def extend_stale_prune_undo(self, ms: int = None) -> int:
        """wave47–48: 延长 undo；ms 优先；否则步进可配（0=重置全长）."""
        if not self.can_undo_prune_stale_alarm_film_csv_dirs():
            self._last_stale_prune_undo_extended = 0
            try:
                self._flash_host_toast('无可延长的清理倒计时', kind='info', ms=1200)
            except Exception:
                pass
            return 0
        full = int(getattr(self, '_stale_prune_undo_ms', 8000) or 8000)
        if ms is not None:
            try:
                total = max(1500, min(30000, int(ms)))
            except Exception:
                total = full
        else:
            step = self.stale_prune_undo_extend_step_ms()
            if step <= 0:
                total = max(1500, min(30000, full))
            else:
                left = max(0, int(getattr(self, '_stale_prune_undo_left_ms', 0) or 0))
                total = max(1500, min(30000, left + int(step)))
        self._stale_prune_undo_left_ms = total
        timer = getattr(self, '_stale_prune_undo_timer', None)
        if timer is not None and not timer.isActive():
            timer.start()
        try:
            self._show_stale_prune_undo_bar()
            self._update_stale_prune_undo_bar()
        except Exception:
            pass
        sec = max(1, (total + 999) // 1000)
        try:
            self._flash_host_toast(
                f'已延长撤销 · {sec}s', kind='ok', ms=1000)
            self._log_line(f'undo 延长倒计时 · {total}ms')
        except Exception:
            pass
        if getattr(self, '_stale_prune_undo_bar_hovered', False):
            try:
                self._refresh_stale_prune_undo_bar_hover_sec()
            except Exception:
                pass
        self._last_stale_prune_undo_extended = total
        return total

    def _on_stale_prune_undo_bar_clicked(self, event=None):
        """wave44–49: 左键撤销；中键延长；右键步进/延长预设菜单."""
        try:
            btn = event.button() if event is not None else Qt.MouseButton.LeftButton
        except Exception:
            btn = Qt.MouseButton.LeftButton
        if btn == Qt.MouseButton.RightButton:
            try:
                menu = self._build_stale_prune_undo_step_menu()
                self._last_stale_prune_undo_step_menu = menu
                if getattr(self, '_stale_prune_undo_step_menu_no_exec', False):
                    self._last_stale_prune_undo_bar_step_menu = True
                    return True
                gp = None
                try:
                    gp = event.globalPosition().toPoint()
                except Exception:
                    try:
                        gp = event.globalPos()
                    except Exception:
                        gp = None
                if gp is not None:
                    menu.exec(gp)
                else:
                    menu.exec()
                self._last_stale_prune_undo_bar_step_menu = True
                return True
            except Exception:
                got = self.extend_stale_prune_undo()
                self._last_stale_prune_undo_bar_extend_clicked = bool(got)
                return bool(got)
        if btn == Qt.MouseButton.MiddleButton:
            got = self.extend_stale_prune_undo()
            self._last_stale_prune_undo_bar_extend_clicked = bool(got)
            return bool(got)
        if btn not in (Qt.MouseButton.LeftButton,):
            return False
        if not self.can_undo_prune_stale_alarm_film_csv_dirs():
            try:
                self._flash_host_toast('无可撤销的清理', kind='info', ms=1200)
            except Exception:
                pass
            self._last_stale_prune_undo_bar_clicked = False
            return False
        self._last_stale_prune_undo_bar_clicked = True
        try:
            self.undo_prune_stale_alarm_film_csv_dirs()
        except Exception:
            self._last_stale_prune_undo_bar_clicked = False
            return False
        return True

    def _place_stale_prune_undo_bar(self):
        """wave43: 进度条贴在 toast 下方."""
        bar = getattr(self, '_stale_prune_undo_bar', None)
        toast = getattr(self, '_liaison_hotkey_toast', None)
        if bar is None:
            return
        try:
            if toast is not None and not toast.isHidden():
                tw = max(120, toast.width())
                bar.setFixedWidth(tw)
                bar.move(toast.x(), toast.y() + toast.height() + 2)
            else:
                bar.setFixedWidth(160)
                bar.move(12, max(40, self.height() - 28))
            bar.raise_()
        except Exception:
            pass

    def _show_stale_prune_undo_bar(self):
        """wave43: 显示 undo 进度条."""
        bar = getattr(self, '_stale_prune_undo_bar', None)
        if bar is None:
            return False
        total = max(1, int(getattr(self, '_stale_prune_undo_ms', 8000) or 8000))
        left = max(0, int(getattr(self, '_stale_prune_undo_left_ms', 0) or 0))
        try:
            bar.setMaximum(1000)
            bar.setValue(int(1000 * left / total))
            self._place_stale_prune_undo_bar()
            bar.show()
            bar.raise_()
        except Exception:
            return False
        self._last_stale_prune_undo_bar_visible = True
        return True

    def stale_prune_undo_color_scale_preset(self) -> str:
        """wave52–53: undo 色阶预设名（含 custom）."""
        v = getattr(self, '_stale_prune_undo_color_scale', None)
        if v not in ('traffic', 'cool', 'mono', 'sunset', 'custom'):
            try:
                v = str(self._host_settings().value(
                    'host/stalePruneUndoColorScale', 'traffic') or 'traffic').strip().lower()
            except Exception:
                v = 'traffic'
            if v not in ('traffic', 'cool', 'mono', 'sunset', 'custom'):
                v = 'traffic'
            self._stale_prune_undo_color_scale = v
        return str(self._stale_prune_undo_color_scale)

    def set_stale_prune_undo_color_scale_preset(
            self, name: str = 'traffic', *, persist: bool = True) -> str:
        """wave52–53: 配置 undo 色阶预设并热刷进度条."""
        name = str(name or 'traffic').strip().lower()
        if name not in ('traffic', 'cool', 'mono', 'sunset', 'custom'):
            name = 'traffic'
        self._stale_prune_undo_color_scale = name
        if persist:
            try:
                self._host_settings().setValue(
                    'host/stalePruneUndoColorScale', name)
            except Exception:
                pass
        try:
            self._apply_stale_prune_undo_bar_color_scale()
        except Exception:
            pass
        self._last_stale_prune_undo_color_scale = name
        return name

    def stale_prune_undo_color_custom_rgb(self) -> dict:
        """wave53: 自定义 RGB hi/mid/lo."""
        d = getattr(self, '_stale_prune_undo_color_custom', None)
        if not isinstance(d, dict):
            d = {'hi': '#3ecf8e', 'mid': '#f0c040', 'lo': '#e35d6a'}
            self._stale_prune_undo_color_custom = d
        out = {
            'hi': str(d.get('hi') or '#3ecf8e'),
            'mid': str(d.get('mid') or '#f0c040'),
            'lo': str(d.get('lo') or '#e35d6a'),
        }
        return out

    def set_stale_prune_undo_color_custom_rgb(
            self, hi: str = None, mid: str = None, lo: str = None,
            *, persist: bool = True, apply: bool = True) -> dict:
        """wave53: 写入自定义 RGB 并可选切到 custom 预设."""
        cur = self.stale_prune_undo_color_custom_rgb()

        def _norm(v, fallback):
            s = str(v or fallback).strip()
            if not s.startswith('#'):
                s = '#' + s
            if len(s) not in (4, 7):
                return fallback
            return s.lower()

        cur['hi'] = _norm(hi if hi is not None else cur['hi'], '#3ecf8e')
        cur['mid'] = _norm(mid if mid is not None else cur['mid'], '#f0c040')
        cur['lo'] = _norm(lo if lo is not None else cur['lo'], '#e35d6a')
        self._stale_prune_undo_color_custom = dict(cur)
        if persist:
            try:
                s = self._host_settings()
                s.setValue('host/stalePruneUndoColorCustomHi', cur['hi'])
                s.setValue('host/stalePruneUndoColorCustomMid', cur['mid'])
                s.setValue('host/stalePruneUndoColorCustomLo', cur['lo'])
            except Exception:
                pass
        if apply:
            try:
                self.set_stale_prune_undo_color_scale_preset('custom')
            except Exception:
                pass
        self._last_stale_prune_undo_color_custom = dict(cur)
        return dict(cur)

    def prompt_stale_prune_undo_color_custom_rgb(
            self, hi: str = None, mid: str = None, lo: str = None) -> dict:
        """wave53: 交互/直传设置自定义 RGB."""
        cur = self.stale_prune_undo_color_custom_rgb()
        if (hi is None and mid is None and lo is None
                and not getattr(self, '_stale_prune_undo_custom_rgb_no_dialog', False)):
            try:
                c_hi = QColorDialog.getColor(
                    QColor(cur['hi']), self, '自定义色阶 · 高位 (hi)')
                if not c_hi.isValid():
                    self._last_stale_prune_undo_color_custom = None
                    return cur
                hi = c_hi.name()
                c_mid = QColorDialog.getColor(
                    QColor(cur['mid']), self, '自定义色阶 · 中位 (mid)')
                if not c_mid.isValid():
                    self._last_stale_prune_undo_color_custom = None
                    return cur
                mid = c_mid.name()
                c_lo = QColorDialog.getColor(
                    QColor(cur['lo']), self, '自定义色阶 · 低位 (lo)')
                if not c_lo.isValid():
                    self._last_stale_prune_undo_color_custom = None
                    return cur
                lo = c_lo.name()
            except Exception:
                hi = hi or cur['hi']
                mid = mid or cur['mid']
                lo = lo or cur['lo']
        if hi is None:
            hi = getattr(self, '_stale_prune_undo_custom_rgb_hi', cur['hi'])
        if mid is None:
            mid = getattr(self, '_stale_prune_undo_custom_rgb_mid', cur['mid'])
        if lo is None:
            lo = getattr(self, '_stale_prune_undo_custom_rgb_lo', cur['lo'])
        got = self.set_stale_prune_undo_color_custom_rgb(hi, mid, lo)
        try:
            self._flash_host_toast(
                f'自定义色阶 · {got["hi"]}/{got["mid"]}/{got["lo"]}',
                kind='ok', ms=1400)
        except Exception:
            pass
        return got

    def _stale_prune_undo_bar_chunk_color(self, ratio: float = 1.0) -> str:
        """wave51–52: 倒计时色阶（按预设）."""
        try:
            r = max(0.0, min(1.0, float(ratio)))
        except Exception:
            r = 1.0
        preset = self.stale_prune_undo_color_scale_preset()
        if preset == 'cool':
            if r >= 0.55:
                color = '#5b9cff' if r >= 0.75 else '#6ec8ff'
            elif r >= 0.25:
                color = '#7ad7c7'
            else:
                color = '#4a6fa5'
        elif preset == 'mono':
            if r >= 0.55:
                color = '#f0c040'
            elif r >= 0.25:
                color = '#c9a030'
            else:
                color = '#8a7020'
        elif preset == 'sunset':
            if r >= 0.55:
                color = '#ff9f43' if r >= 0.75 else '#f0c040'
            elif r >= 0.25:
                color = '#e67e22'
            else:
                color = '#e35d6a'
        elif preset == 'custom':
            rgb = self.stale_prune_undo_color_custom_rgb()
            if r >= 0.55:
                color = rgb.get('hi') or '#3ecf8e'
            elif r >= 0.25:
                color = rgb.get('mid') or '#f0c040'
            else:
                color = rgb.get('lo') or '#e35d6a'
        else:  # traffic
            if r >= 0.55:
                t = (r - 0.55) / 0.45
                color = '#3ecf8e' if t >= 0.5 else '#8fd46a'
            elif r >= 0.25:
                color = '#f0c040'
            else:
                color = '#e35d6a'
        self._last_stale_prune_undo_bar_chunk_color = color
        self._last_stale_prune_undo_bar_ratio = round(r, 3)
        self._last_stale_prune_undo_color_scale_used = preset
        return color

    def _apply_stale_prune_undo_bar_color_scale(self, ratio: float = None) -> str:
        """wave51: 按剩余比例刷进度条 chunk 色."""
        bar = getattr(self, '_stale_prune_undo_bar', None)
        if ratio is None:
            total = max(1, int(getattr(self, '_stale_prune_undo_ms', 8000) or 8000))
            left = max(0, int(getattr(self, '_stale_prune_undo_left_ms', 0) or 0))
            ratio = left / total
        color = self._stale_prune_undo_bar_chunk_color(ratio)
        if bar is not None:
            try:
                bar.setStyleSheet(
                    'QProgressBar{background:#2a2d32;border:1px solid #3a3d42;'
                    'border-radius:2px;}'
                    f'QProgressBar::chunk{{background:{color};border-radius:2px;}}'
                )
            except Exception:
                pass
        return color

    def _update_stale_prune_undo_bar(self):
        """wave43–51: 刷新 undo 进度；悬停秒；色阶."""
        bar = getattr(self, '_stale_prune_undo_bar', None)
        if bar is None or bar.isHidden():
            return
        total = max(1, int(getattr(self, '_stale_prune_undo_ms', 8000) or 8000))
        left = max(0, int(getattr(self, '_stale_prune_undo_left_ms', 0) or 0))
        ratio = left / total
        try:
            bar.setValue(int(1000 * ratio))
            self._apply_stale_prune_undo_bar_color_scale(ratio)
            self._place_stale_prune_undo_bar()
        except Exception:
            pass
        if getattr(self, '_stale_prune_undo_bar_hovered', False):
            try:
                self._refresh_stale_prune_undo_bar_hover_sec()
            except Exception:
                pass

    def _hide_stale_prune_undo_bar(self):
        bar = getattr(self, '_stale_prune_undo_bar', None)
        if bar is not None:
            try:
                bar.hide()
                bar.setValue(0)
                h = int(getattr(self, '_stale_prune_undo_bar_base_h', 10) or 10)
                bar.setFixedHeight(h)
            except Exception:
                pass
        self._stale_prune_undo_bar_hovered = False
        self._last_stale_prune_undo_bar_hovered = False
        self._last_stale_prune_undo_bar_visible = False

    def _on_stale_prune_undo_tick(self):
        """wave42–43: undo 倒计时 tick；刷新进度条；到期失效."""
        if not getattr(self, '_stale_prune_can_undo', False):
            timer = getattr(self, '_stale_prune_undo_timer', None)
            if timer is not None and timer.isActive():
                timer.stop()
            self._hide_stale_prune_undo_bar()
            return
        left = int(getattr(self, '_stale_prune_undo_left_ms', 0) or 0)
        step = 250
        left = max(0, left - step)
        self._stale_prune_undo_left_ms = left
        self._update_stale_prune_undo_bar()
        if left > 0 and left % 1000 < step:
            try:
                n = len(getattr(self, '_stale_prune_undo_removed', None) or [])
                sec = max(1, (left + 999) // 1000)
                toast = getattr(self, '_liaison_hotkey_toast', None)
                if toast is not None and not toast.isHidden():
                    toast.setText(f'已清理失效 · {n} · 点此撤销（{sec}s）')
                    self._place_stale_prune_undo_bar()
            except Exception:
                pass
        if left <= 0:
            self.expire_stale_prune_undo(silent=False)

    def expire_stale_prune_undo(self, *, silent: bool = False) -> bool:
        """wave42: 使 undo 倒计时失效."""
        had = bool(getattr(self, '_stale_prune_can_undo', False))
        self._stale_prune_can_undo = False
        self._stale_prune_undo_left_ms = 0
        timer = getattr(self, '_stale_prune_undo_timer', None)
        if timer is not None and timer.isActive():
            timer.stop()
        if getattr(self, '_host_toast_click_action', '') == 'undo_prune':
            self._host_toast_click_action = 'open'
        self._last_stale_prune_undo_expired = True
        try:
            self._hide_stale_prune_undo_bar()
        except Exception:
            pass
        if had and not silent:
            try:
                self._flash_host_toast('撤销已失效', kind='info', ms=1400)
                self._log_line('失效清理撤销 · 已超时')
            except Exception:
                pass
        return had

    def undo_prune_stale_alarm_film_csv_dirs(self) -> list:
        """wave41–42: 撤销最近一次失效清理（倒计时内）."""
        if not getattr(self, '_stale_prune_can_undo', False):
            try:
                self._flash_host_toast('无可撤销的清理', kind='info')
            except Exception:
                pass
            return list(self.alarm_film_csv_dirs())
        snap = list(getattr(self, '_stale_prune_undo_dirs', None) or [])
        if not snap and snap != []:
            snap = []
        try:
            max_n = self.alarm_film_csv_dirs_max()
            snap = snap[:max_n]
            self._host_settings().setValue('host/alarmFilmCsvDirs', snap)
            self._host_settings().setValue('host/alarmFilmCsvDir', snap[0] if snap else '')
        except Exception:
            pass
        self._stale_prune_can_undo = False
        self._stale_prune_undo_left_ms = 0
        self._last_stale_prune_undone = True
        timer = getattr(self, '_stale_prune_undo_timer', None)
        if timer is not None and timer.isActive():
            timer.stop()
        try:
            self._hide_stale_prune_undo_bar()
        except Exception:
            pass
        try:
            self._log_line(f'已撤销失效清理 · 恢复 {len(snap)} 档')
            self._flash_host_toast(f'已撤销清理 · {len(snap)} 档', kind='ok')
            self._host_toast_click_action = 'open'
        except Exception:
            pass
        return list(snap)

    def can_undo_prune_stale_alarm_film_csv_dirs(self) -> bool:
        """wave41–42: 是否可撤销失效清理（倒计时未失效）."""
        if not bool(getattr(self, '_stale_prune_can_undo', False)):
            return False
        left = int(getattr(self, '_stale_prune_undo_left_ms', 0) or 0)
        # left==0 with flag still set → treat as expired
        if left <= 0:
            try:
                self.expire_stale_prune_undo(silent=True)
            except Exception:
                self._stale_prune_can_undo = False
            return False
        return True

    def export_alarm_film_csv_dirs_json(self, path: str = '') -> str:
        """wave39: 导出多档另存记忆为 JSON；空 path 弹存盘框."""
        import json
        from datetime import datetime as _dt
        payload = {
            'version': 1,
            'kind': 'sieans.alarmFilmCsvDirs',
            'exportedAt': _dt.now().isoformat(timespec='seconds'),
            'max': self.alarm_film_csv_dirs_max(),
            'dirs': list(self.alarm_film_csv_dirs()),
        }
        text = json.dumps(payload, ensure_ascii=False, indent=2)
        if not path:
            path, _ = QFileDialog.getSaveFileName(
                self,
                '导出另存记忆 JSON',
                str(__import__('pathlib').Path.home() / 'sieans-alarm-film-csv-dirs.json'),
                'JSON (*.json);;All (*)',
            )
            path = str(path or '').strip()
        if not path:
            return ''
        try:
            __import__('pathlib').Path(path).write_text(text + '\n', encoding='utf-8')
        except Exception as err:
            try:
                self._flash_host_toast(f'导出失败 · {err}', kind='info')
            except Exception:
                pass
            return ''
        try:
            self._log_line(f'另存记忆已导出 · {path}')
            self._flash_host_toast(f'已导出记忆 · {__import__("pathlib").Path(path).name}', kind='ok')
        except Exception:
            pass
        self._last_alarm_film_csv_dirs_export = path
        return path

    def import_alarm_film_csv_dirs_json(self, path_or_text: str = '', *, merge: bool = False) -> list:
        """wave39–40: 导入多档另存记忆 JSON；merge=True 去重并集（非覆盖）."""
        import json
        raw = str(path_or_text or '').strip()
        text = ''
        if not raw:
            path, _ = QFileDialog.getOpenFileName(
                self,
                '合并导入另存记忆 JSON' if merge else '导入另存记忆 JSON',
                str(__import__('pathlib').Path.home()),
                'JSON (*.json);;All (*)',
            )
            path = str(path or '').strip()
            if not path:
                return self.alarm_film_csv_dirs()
            raw = path
        try:
            from pathlib import Path as _P
            p = _P(raw)
            if p.is_file() and not raw.lstrip().startswith('{'):
                text = p.read_text(encoding='utf-8')
            else:
                text = raw
        except Exception:
            text = raw
        try:
            data = json.loads(text)
        except Exception as err:
            try:
                self._flash_host_toast('导入失败 · JSON 无效', kind='info')
                self._log_line(f'另存记忆导入失败 · {err}')
            except Exception:
                pass
            return self.alarm_film_csv_dirs()
        if isinstance(data, list):
            dirs = [str(x).strip() for x in data if str(x).strip()]
            max_n = self.alarm_film_csv_dirs_max()
        elif isinstance(data, dict):
            dirs = [str(x).strip() for x in (data.get('dirs') or []) if str(x).strip()]
            try:
                max_n = int(data.get('max') or self.alarm_film_csv_dirs_max())
            except Exception:
                max_n = self.alarm_film_csv_dirs_max()
        else:
            try:
                self._flash_host_toast('导入失败 · 格式不符', kind='info')
            except Exception:
                pass
            return self.alarm_film_csv_dirs()
        if merge:
            # 去重并集：导入项置前，再接现有，裁剪上限
            existing = self.alarm_film_csv_dirs()
            # max takes the larger of current and imported (capped 8)
            try:
                max_n = max(int(max_n), int(self.alarm_film_csv_dirs_max()))
            except Exception:
                pass
            max_n = max(3, min(8, int(max_n or 5)))
            try:
                self.set_alarm_film_csv_dirs_max(max_n, persist=True)
            except Exception:
                pass
            out = self.merge_alarm_film_csv_dirs(dirs)
            stats = getattr(self, '_last_merge_stats', {}) or {}
            c_n = int(stats.get('conflict', 0) or 0)
            n_n = int(stats.get('new', 0) or 0)
            t_n = int(stats.get('trimmed', 0) or 0)
            tip = f'已合并导入 · {len(out)} 档'
            bits = []
            if c_n:
                bits.append(f'冲突{c_n}')
            if n_n:
                bits.append(f'新增{n_n}')
            if t_n:
                bits.append(f'裁剪{t_n}')
            if bits:
                tip += ' · ' + ' · '.join(bits)
            if c_n or n_n or t_n:
                tip += ' · 点开清单'
            try:
                self._log_line(f'另存记忆已合并导入 · {len(out)} 档 · 冲突{c_n} 新增{n_n} 裁剪{t_n}')
                self._flash_host_toast(tip, kind='ok', ms=4200)
                self._host_toast_click_action = 'merge_diff'
            except Exception:
                pass
            self._last_alarm_film_csv_dirs_import_mode = 'merge'
            self._last_merge_import_tip = tip
            return out
        # overwrite mode (wave39–40): 覆盖写入（非并集）
        try:
            self.set_alarm_film_csv_dirs_max(max_n, persist=True)
        except Exception:
            pass
        max_n = self.alarm_film_csv_dirs_max()
        seen = []
        for d in list(dirs or []):
            s = str(d or '').strip()
            if s and s not in seen:
                seen.append(s)
            if len(seen) >= max_n:
                break
        try:
            self._host_settings().setValue('host/alarmFilmCsvDirs', seen)
            self._host_settings().setValue('host/alarmFilmCsvDir', seen[0] if seen else '')
        except Exception:
            pass
        out = list(seen)
        try:
            self._log_line(f'另存记忆已导入 · {len(out)} 档')
            self._flash_host_toast(f'已导入记忆 · {len(out)} 档', kind='ok')
        except Exception:
            pass
        self._last_alarm_film_csv_dirs_import_mode = 'replace'
        return out

    def merge_alarm_film_csv_dirs(self, dirs) -> list:
        """wave40–42: 多档记忆去重并集；记录冲突/新增/裁剪与 diff 清单."""
        max_n = self.alarm_film_csv_dirs_max()
        existing = list(self.alarm_film_csv_dirs(max_n=max_n))
        existing_set = set(existing)
        incoming = []
        for d in list(dirs or []):
            s = str(d or '').strip()
            if s and s not in incoming:
                incoming.append(s)
        conflicts = [d for d in incoming if d in existing_set]
        news = [d for d in incoming if d not in existing_set]
        conflict_n = len(conflicts)
        new_n = len(news)
        full = []
        for d in incoming:
            if d not in full:
                full.append(d)
        for d in existing:
            if d not in full:
                full.append(d)
        trimmed = full[max_n:] if len(full) > max_n else []
        trimmed_n = len(trimmed)
        seen = full[:max_n]
        try:
            self._host_settings().setValue('host/alarmFilmCsvDirs', seen)
            self._host_settings().setValue('host/alarmFilmCsvDir', seen[0] if seen else '')
        except Exception:
            pass
        self._last_merge_conflict_n = int(conflict_n)
        self._last_merge_new_n = int(new_n)
        self._last_merge_trimmed_n = int(trimmed_n)
        self._last_merge_diff = {
            'conflict': list(conflicts),
            'new': list(news),
            'trimmed': list(trimmed),
            'out': list(seen),
            'incoming': list(incoming),
            'existing': list(existing),
        }
        self._last_merge_stats = {
            'conflict': int(conflict_n),
            'new': int(new_n),
            'trimmed': int(trimmed_n),
            'out': len(seen),
        }
        return list(seen)

    def show_last_merge_diff(self, *, interactive: bool = True) -> bool:
        """wave42–43: 点开合并 tip → diff 清单；可点开目录."""
        diff = getattr(self, '_last_merge_diff', None) or {}
        if not diff:
            try:
                self._flash_host_toast('无合并 diff 可看', kind='info')
            except Exception:
                pass
            return False
        def _lab(d):
            try:
                from pathlib import Path as _P
                return _P(d).name or d
            except Exception:
                return d
        out_n = len(diff.get('out') or [])
        if not interactive:
            # text-only fallback for smoke / headless preference
            sections = []
            for key, title in (
                ('new', '新增'),
                ('conflict', '冲突（已存在）'),
                ('trimmed', '裁剪（超上限丢弃）'),
            ):
                items = list(diff.get(key) or [])
                if not items:
                    continue
                lines = [f'【{title} · {len(items)}】']
                for i, d in enumerate(items[:12], 1):
                    lines.append(f'  {i}. {_lab(d)}\n     {d}')
                sections.append('\n'.join(lines))
            body = '\n\n'.join(sections) if sections else '（无差异项）'
            try:
                QMessageBox.information(
                    self, f'合并导入 diff · 结果 {out_n} 档', body)
            except Exception:
                pass
            self._last_merge_diff_shown = True
            return True
        try:
            dlg = QDialog(self)
            dlg.setWindowTitle(f'合并导入 diff · 结果 {out_n} 档')
            dlg.setObjectName('hostMergeDiffDialog')
            dlg.setMinimumWidth(420)
            lay = QVBoxLayout(dlg)
            tip = QLabel(
                '多选后点「打开选中」批量开目录 · Ctrl/Shift 多选 · 双击单项', dlg)
            tip.setStyleSheet('color:#9aa0a6;font-size:11px;')
            lay.addWidget(tip)
            lst = QListWidget(dlg)
            lst.setObjectName('hostMergeDiffList')
            try:
                lst.setSelectionMode(
                    QListWidget.SelectionMode.ExtendedSelection)
            except Exception:
                pass
            for key, title in (
                ('new', '新增'),
                ('conflict', '冲突（已存在）'),
                ('trimmed', '裁剪（超上限丢弃）'),
            ):
                items = list(diff.get(key) or [])
                if not items:
                    continue
                hdr = QListWidgetItem(f'【{title} · {len(items)}】')
                hdr.setFlags(Qt.ItemFlag.NoItemFlags)
                lst.addItem(hdr)
                for d in items[:24]:
                    it = QListWidgetItem(f'  {_lab(d)}  —  {d}')
                    it.setData(Qt.ItemDataRole.UserRole, d)
                    it.setToolTip(d + '\n双击打开 · 多选后批量打开')
                    lst.addItem(it)
            lay.addWidget(lst)

            def _open_selected() -> list:
                return self.open_merge_diff_selected(lst)

            lst.itemDoubleClicked.connect(
                lambda *_: self.open_merge_diff_path(
                    str((lst.currentItem().data(Qt.ItemDataRole.UserRole)
                         if lst.currentItem() else '') or '').strip())
            )
            btns = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Close, parent=dlg)
            btn_open = btns.addButton(
                '打开选中', QDialogButtonBox.ButtonRole.ActionRole)
            btn_open.setObjectName('hostMergeDiffOpenBtn')
            btn_open.clicked.connect(lambda *_: _open_selected())
            btns.rejected.connect(dlg.reject)
            btns.accepted.connect(dlg.accept)
            lay.addWidget(btns)
            self._last_merge_diff_dialog = dlg
            self._last_merge_diff_list = lst
            if getattr(self, '_merge_diff_no_exec', False):
                # smoke: build only
                self._last_merge_diff_shown = True
                return True
            dlg.exec()
        except Exception as err:
            try:
                self._flash_host_toast(f'diff 清单失败 · {err}', kind='info')
            except Exception:
                pass
            return self.show_last_merge_diff(interactive=False)
        self._last_merge_diff_shown = True
        return True

    def open_merge_diff_path(self, path: str = '', *, quiet: bool = False) -> str:
        """wave43–45: 从 diff 清单打开目录；失败返回 ''."""
        path = str(path or '').strip()
        if not path:
            if not quiet:
                try:
                    self._flash_host_toast('无路径可开', kind='info')
                except Exception:
                    pass
            self._last_merge_diff_opened = ''
            return ''
        self._host_toast_open_path = path
        prev_silent = getattr(self, '_open_host_toast_path_silent', False)
        if quiet:
            self._open_host_toast_path_silent = True
        try:
            got = self.open_host_toast_path()
        finally:
            self._open_host_toast_path_silent = prev_silent
        # wave45: 真实成败（不再 got or path）
        self._last_merge_diff_opened = got or ''
        try:
            from pathlib import Path as _P
            lab = _P(path).name or path
            if got:
                self._log_line(f'diff 清单打开 · {path}')
                if not quiet:
                    self._flash_host_toast(f'已打开 · {lab}', kind='ok', ms=1200)
            else:
                self._log_line(f'diff 清单打开失败 · {path}')
                if not quiet:
                    self._flash_host_toast(f'打开失败 · {lab}', kind='info', ms=1400)
        except Exception:
            pass
        return self._last_merge_diff_opened

    def open_merge_diff_paths(self, paths=None) -> list:
        """wave44–45: 批量打开 diff 路径；失败汇总 tip."""
        out = []
        fails = []
        seen = set()
        for p in list(paths or []):
            p = str(p or '').strip()
            if not p or p in seen:
                continue
            seen.add(p)
            got = self.open_merge_diff_path(p, quiet=True)
            if got:
                out.append(got)
            else:
                fails.append(p)
        self._last_merge_diff_opened_batch = list(out)
        self._last_merge_diff_batch_fail = list(fails)
        self._last_merge_diff_batch_ok_n = len(out)
        self._last_merge_diff_batch_fail_n = len(fails)
        if fails:
            try:
                self.remember_merge_diff_batch_fails(fails)
            except Exception:
                pass
        try:
            n_ok, n_fail = len(out), len(fails)
            if n_ok == 0 and n_fail == 0:
                tip = '无选中路径可开'
                self._flash_host_toast(tip, kind='info', ms=1200)
            elif n_fail == 0:
                tip = f'已批量打开 · {n_ok} 个目录'
                self._flash_host_toast(tip, kind='ok', ms=1400)
            elif n_ok == 0:
                try:
                    from pathlib import Path as _P
                    lab = _P(fails[0]).name or fails[0]
                except Exception:
                    lab = fails[0]
                tip = f'批量打开失败 · {n_fail} · {lab} · 点此重开失败'
                self._host_toast_click_action = 'retry_merge_diff_fails'
                try:
                    toast = getattr(self, '_liaison_hotkey_toast', None)
                    if toast is not None:
                        toast.setCursor(Qt.CursorShape.PointingHandCursor)
                except Exception:
                    pass
                self._flash_host_toast(tip, kind='info', ms=2200)
            else:
                try:
                    from pathlib import Path as _P
                    lab = _P(fails[0]).name or fails[0]
                except Exception:
                    lab = fails[0]
                tip = f'已开 {n_ok} · 失败 {n_fail} · {lab} · 点此重开失败'
                self._host_toast_click_action = 'retry_merge_diff_fails'
                try:
                    toast = getattr(self, '_liaison_hotkey_toast', None)
                    if toast is not None:
                        toast.setCursor(Qt.CursorShape.PointingHandCursor)
                except Exception:
                    pass
                self._flash_host_toast(tip, kind='info', ms=2200)
            self._last_merge_diff_batch_tip = tip
            self._log_line(f'diff 批量打开 · ok={n_ok} fail={n_fail}')
        except Exception:
            pass
        return list(out)

    def merge_diff_batch_fail_history(self) -> list:
        """wave47: 失败清单历史（新→旧）."""
        return list(getattr(self, '_merge_diff_batch_fail_history', None) or [])

    def merge_diff_batch_fail_history_sort_mode(self) -> str:
        """wave49: 失败历史排序 time|path."""
        v = getattr(self, '_merge_diff_batch_fail_history_sort', None)
        if v not in ('time', 'path'):
            try:
                v = str(self._host_settings().value(
                    'host/mergeDiffBatchFailHistorySort', 'time') or 'time'
                ).strip().lower()
            except Exception:
                v = 'time'
            v = v if v in ('time', 'path') else 'time'
            self._merge_diff_batch_fail_history_sort = v
        return str(self._merge_diff_batch_fail_history_sort)

    def set_merge_diff_batch_fail_history_sort_mode(
            self, mode: str = 'time', *, persist: bool = True) -> str:
        """wave49: 设置失败历史排序 time|path."""
        mode = str(mode or 'time').strip().lower()
        if mode not in ('time', 'path'):
            mode = 'time'
        self._merge_diff_batch_fail_history_sort = mode
        if persist:
            try:
                self._host_settings().setValue(
                    'host/mergeDiffBatchFailHistorySort', mode)
            except Exception:
                pass
        self._last_merge_diff_batch_fail_history_sort = mode
        return mode

    def sorted_merge_diff_batch_fail_history(self, mode: str = None) -> list:
        """wave49: 按 time（新→旧）或 path（首路径）排序失败历史."""
        hist = list(self.merge_diff_batch_fail_history())
        mode = str(mode or self.merge_diff_batch_fail_history_sort_mode()
                   or 'time').strip().lower()
        if mode == 'path':
            hist.sort(key=lambda e: (
                (list(e.get('paths') or []) or [''])[0].lower(),
                str(e.get('ts') or ''),
            ))
        else:
            hist.sort(key=lambda e: str(e.get('ts') or ''), reverse=True)
        self._last_merge_diff_batch_fail_history_sorted = list(hist)
        self._last_merge_diff_batch_fail_history_sort_applied = mode
        return list(hist)

    def filter_merge_diff_batch_fail_history(self, query: str = '') -> list:
        """wave48–49: 按路径/时间子串过滤失败历史（尊重排序）."""
        q = str(query or '').strip().lower()
        hist = self.sorted_merge_diff_batch_fail_history()
        if not q:
            self._last_merge_diff_batch_fail_history_filtered = list(hist)
            return list(hist)
        out = []
        for ent in hist:
            paths = list(ent.get('paths') or [])
            blob = (str(ent.get('ts') or '') + ' ' + ' '.join(paths)).lower()
            if q in blob:
                out.append(ent)
        self._last_merge_diff_batch_fail_history_filtered = list(out)
        return list(out)

    def remember_merge_diff_batch_fails(
            self, paths=None, *, persist: bool = True) -> list:
        """wave47: 记入失败清单历史并持久化最近一次."""
        paths = [str(p).strip() for p in list(paths or []) if str(p).strip()]
        if not paths:
            return self.merge_diff_batch_fail_history()
        import time as _time
        ts = _time.strftime('%Y-%m-%d %H:%M:%S')
        ent = {'ts': ts, 'paths': paths[:48]}
        hist = [ent] + [
            h for h in self.merge_diff_batch_fail_history()
            if list(h.get('paths') or []) != paths
        ]
        hist = hist[:20]
        self._merge_diff_batch_fail_history = hist
        self._last_merge_diff_batch_fail = list(paths)
        if persist:
            try:
                self._host_settings().setValue(
                    'host/mergeDiffBatchFailLast', list(paths))
                # store as list of dicts
                self._host_settings().setValue(
                    'host/mergeDiffBatchFailHistory', hist)
            except Exception:
                pass
        self._last_merge_diff_batch_fail_remembered = list(paths)
        return list(hist)

    def clear_merge_diff_batch_fail_history(self, *, persist: bool = True) -> list:
        """wave47: 清空失败清单历史."""
        self._merge_diff_batch_fail_history = []
        self._last_merge_diff_batch_fail = []
        if persist:
            try:
                self._host_settings().setValue('host/mergeDiffBatchFailHistory', [])
                self._host_settings().setValue('host/mergeDiffBatchFailLast', [])
            except Exception:
                pass
        try:
            self._flash_host_toast('已清空失败清单历史', kind='info', ms=1200)
        except Exception:
            pass
        self._last_merge_diff_batch_fail_history_cleared = True
        return []

    def collapse_merge_diff_batch_fail_history_groups(self) -> set:
        """wave52: 失败历史组头全折."""
        keys = set()
        for ent in self.sorted_merge_diff_batch_fail_history():
            ts = str((ent or {}).get('ts') or '').strip()
            if len(ts) >= 10 and ts[4] == '-' and ts[7] == '-':
                keys.add(ts[:10])
            elif ts:
                keys.add(ts[:10] if len(ts) >= 10 else ts)
            else:
                keys.add('未知日期')
        self._merge_diff_fail_hist_collapsed = set(keys)
        self._last_merge_diff_batch_fail_history_all_collapsed = True
        self._last_merge_diff_batch_fail_history_collapsed = set(keys)
        return set(keys)

    def expand_merge_diff_batch_fail_history_groups(self) -> set:
        """wave52: 失败历史组头全展."""
        self._merge_diff_fail_hist_collapsed = set()
        self._last_merge_diff_batch_fail_history_all_expanded = True
        self._last_merge_diff_batch_fail_history_collapsed = set()
        return set()

    def _merge_diff_fail_hist_group_count_badge_icon(
            self, n: int = 0) -> QIcon:
        """wave53: 失败历史组头计数徽章图标."""
        try:
            n = max(0, int(n))
        except Exception:
            n = 0
        label = '99+' if n > 99 else str(n)
        pm = QPixmap(22, 22)
        pm.fill(QColor(0, 0, 0, 0))
        p = QPainter(pm)
        try:
            p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            bg = QColor('#e35d6a') if n >= 5 else (
                QColor('#f0c040') if n >= 2 else QColor('#5b9cff'))
            p.setBrush(bg)
            p.setPen(QPen(QColor('#1e2126'), 1))
            p.drawEllipse(1, 1, 20, 20)
            p.setPen(QColor('#ffffff'))
            f = QFont()
            f.setBold(True)
            f.setPixelSize(9 if len(label) >= 3 else 11)
            p.setFont(f)
            p.drawText(pm.rect(), int(Qt.AlignmentFlag.AlignCenter), label)
        finally:
            p.end()
        self._last_merge_diff_fail_hist_group_badge_icon_n = n
        return QIcon(pm)

    def show_merge_diff_batch_fail_history(self, *, interactive: bool = True) -> bool:
        """wave47: 失败清单历史对话框 · 可选批次重开."""
        hist = self.merge_diff_batch_fail_history()
        if not hist:
            try:
                self._flash_host_toast('无失败清单历史', kind='info', ms=1200)
            except Exception:
                pass
            self._last_merge_diff_batch_fail_history_shown = False
            return False

        def _lab(d):
            try:
                from pathlib import Path as _P
                return _P(d).name or d
            except Exception:
                return d

        if not interactive:
            lines = []
            for i, ent in enumerate(hist[:12], 1):
                paths = list(ent.get('paths') or [])
                ts = ent.get('ts') or ''
                lines.append(f'#{i} {ts} · {len(paths)}')
                for p in paths[:6]:
                    lines.append(f'  · {_lab(p)}')
            try:
                QMessageBox.information(
                    self, f'失败清单历史 · {len(hist)}', '\n'.join(lines) or '（空）')
            except Exception:
                pass
            self._last_merge_diff_batch_fail_history_shown = True
            return True
        try:
            dlg = QDialog(self)
            dlg.setWindowTitle(f'失败清单历史 · {len(hist)}')
            dlg.setObjectName('hostMergeDiffBatchFailHistoryDialog')
            dlg.setMinimumWidth(440)
            lay = QVBoxLayout(dlg)
            tip = QLabel(
                '全展/全折 · 分组折叠 · 搜索/排序 · 多选重开/导出 · 清空', dlg)
            tip.setStyleSheet('color:#9aa0a6;font-size:11px;')
            lay.addWidget(tip)
            if not hasattr(self, '_merge_diff_fail_hist_collapsed'):
                self._merge_diff_fail_hist_collapsed = set()
            row = QHBoxLayout()
            filt = QLineEdit(dlg)
            filt.setObjectName('hostMergeDiffBatchFailHistoryFilter')
            filt.setPlaceholderText('搜索/过滤失败历史…')
            filt.setClearButtonEnabled(True)
            row.addWidget(filt, 1)
            sort_box = QComboBox(dlg)
            sort_box.setObjectName('hostMergeDiffBatchFailHistorySort')
            sort_box.addItem('按时间', 'time')
            sort_box.addItem('按路径', 'path')
            cur_sort = self.merge_diff_batch_fail_history_sort_mode()
            sort_box.setCurrentIndex(1 if cur_sort == 'path' else 0)
            row.addWidget(sort_box)
            btn_exp = QPushButton('全展', dlg)
            btn_exp.setObjectName('hostMergeDiffBatchFailHistoryExpandAll')
            btn_exp.setFixedWidth(48)
            btn_exp.setToolTip('展开全部分组')
            btn_col = QPushButton('全折', dlg)
            btn_col.setObjectName('hostMergeDiffBatchFailHistoryCollapseAll')
            btn_col.setFixedWidth(48)
            btn_col.setToolTip('折叠全部分组')
            row.addWidget(btn_exp)
            row.addWidget(btn_col)
            lay.addLayout(row)
            lst = QListWidget(dlg)
            lst.setObjectName('hostMergeDiffBatchFailHistoryList')
            try:
                lst.setSelectionMode(
                    QAbstractItemView.SelectionMode.ExtendedSelection)
            except Exception:
                pass

            def _ent_blob(ent):
                paths = list(ent.get('paths') or [])
                ts = str(ent.get('ts') or '')
                return (ts + ' ' + ' '.join(paths)).lower()

            def _group_key(ent):
                ts = str((ent or {}).get('ts') or '').strip()
                if len(ts) >= 10 and ts[4] == '-' and ts[7] == '-':
                    return ts[:10]
                if ts:
                    return ts[:10] if len(ts) >= 10 else ts
                return '未知日期'

            def _refill(query: str = None):
                if query is None:
                    query = filt.text()
                q = str(query or '').strip().lower()
                mode = str(sort_box.currentData() or 'time')
                self.set_merge_diff_batch_fail_history_sort_mode(mode)
                ordered = self.sorted_merge_diff_batch_fail_history(mode)
                collapsed = getattr(
                    self, '_merge_diff_fail_hist_collapsed', None)
                if not isinstance(collapsed, set):
                    collapsed = set()
                    self._merge_diff_fail_hist_collapsed = collapsed
                # bucket
                buckets = []
                seen_g = {}
                for ent in ordered:
                    if q and q not in _ent_blob(ent):
                        continue
                    gk = _group_key(ent)
                    if gk not in seen_g:
                        seen_g[gk] = []
                        buckets.append((gk, seen_g[gk]))
                    seen_g[gk].append(ent)
                lst.clear()
                shown = 0
                group_n = 0
                for gk, ents in buckets:
                    group_n += 1
                    is_col = gk in collapsed
                    mark = '▸' if is_col else '▾'
                    n_ents = len(ents)
                    hdr = QListWidgetItem(
                        f'{mark} {gk} · {n_ents} 批')
                    hdr.setData(Qt.ItemDataRole.UserRole + 2, gk)
                    hdr.setData(Qt.ItemDataRole.UserRole + 3, True)  # isGroup
                    hdr.setData(Qt.ItemDataRole.UserRole + 4, int(n_ents))
                    hdr.setFlags(
                        Qt.ItemFlag.ItemIsEnabled
                        | Qt.ItemFlag.ItemIsSelectable)
                    try:
                        hdr.setBackground(QColor('#2a2d32'))
                        hdr.setForeground(QColor('#c8ccd0'))
                    except Exception:
                        pass
                    # wave53: 组头计数徽章
                    try:
                        hdr.setIcon(
                            self._merge_diff_fail_hist_group_count_badge_icon(
                                n_ents))
                    except Exception:
                        pass
                    hdr.setToolTip(
                        f'单击折叠/展开该日分组 · {n_ents} 批' + (
                            '（已折叠）' if is_col else '（已展开）'))
                    lst.addItem(hdr)
                    self._last_merge_diff_batch_fail_history_group_badge_n = int(
                        n_ents)
                    if is_col:
                        continue
                    for ent in ents:
                        paths = list(ent.get('paths') or [])
                        ts = ent.get('ts') or ''
                        lab0 = _lab(paths[0]) if paths else ''
                        it = QListWidgetItem(
                            f'   {ts} · {len(paths)} · {lab0}')
                        it.setData(Qt.ItemDataRole.UserRole, paths)
                        it.setData(Qt.ItemDataRole.UserRole + 1, ent)
                        it.setData(Qt.ItemDataRole.UserRole + 3, False)
                        it.setToolTip('\n'.join(paths))
                        lst.addItem(it)
                        shown += 1
                self._last_merge_diff_batch_fail_history_filter = q
                self._last_merge_diff_batch_fail_history_filter_n = shown
                self._last_merge_diff_batch_fail_history_sort = mode
                self._last_merge_diff_batch_fail_history_groups = group_n
                self._last_merge_diff_batch_fail_history_collapsed = set(
                    collapsed)
                zh = '路径' if mode == 'path' else '时间'
                dlg.setWindowTitle(
                    f'失败清单历史 · {shown}/{len(hist)} · {group_n}组 · {zh}'
                    + (f' · 过滤「{q}」' if q else ''))
                return shown

            def _on_item_clicked(item):
                if item is None:
                    return
                if not item.data(Qt.ItemDataRole.UserRole + 3):
                    return
                gk = str(item.data(Qt.ItemDataRole.UserRole + 2) or '')
                if not gk:
                    return
                collapsed = getattr(
                    self, '_merge_diff_fail_hist_collapsed', None)
                if not isinstance(collapsed, set):
                    collapsed = set()
                    self._merge_diff_fail_hist_collapsed = collapsed
                if gk in collapsed:
                    collapsed.discard(gk)
                    self._last_merge_diff_batch_fail_history_group_toggled = (
                        gk, False)
                else:
                    collapsed.add(gk)
                    self._last_merge_diff_batch_fail_history_group_toggled = (
                        gk, True)
                _refill()

            def _expand_all():
                self.expand_merge_diff_batch_fail_history_groups()
                _refill()

            def _collapse_all():
                # collapse currently visible groups from buckets
                self.collapse_merge_diff_batch_fail_history_groups()
                _refill()

            btn_exp.clicked.connect(lambda *_: _expand_all())
            btn_col.clicked.connect(lambda *_: _collapse_all())

            _refill('')
            filt.textChanged.connect(lambda t: _refill(t))
            sort_box.currentIndexChanged.connect(lambda *_: _refill())
            lst.itemClicked.connect(_on_item_clicked)
            lay.addWidget(lst)
            self._last_merge_diff_batch_fail_history_filter_edit = filt
            self._last_merge_diff_batch_fail_history_sort_box = sort_box
            self._last_merge_diff_batch_fail_history_expand_btn = btn_exp
            self._last_merge_diff_batch_fail_history_collapse_btn = btn_col

            def _load_current(item=None):
                it = item or lst.currentItem()
                if it is None:
                    return []
                if it.data(Qt.ItemDataRole.UserRole + 3):
                    return []
                paths = list(it.data(Qt.ItemDataRole.UserRole) or [])
                self._last_merge_diff_batch_fail = list(paths)
                self._last_merge_diff_batch_fail_n = len(paths)
                return paths

            def _selected_entries():
                out = []
                for it in lst.selectedItems():
                    if it.data(Qt.ItemDataRole.UserRole + 3):
                        continue
                    ent = it.data(Qt.ItemDataRole.UserRole + 1)
                    if isinstance(ent, dict):
                        out.append(ent)
                    else:
                        paths = list(it.data(Qt.ItemDataRole.UserRole) or [])
                        if paths:
                            out.append({'ts': '', 'paths': paths})
                return out

            def _selected_paths_union():
                seen = set()
                paths = []
                for ent in _selected_entries():
                    for pth in list(ent.get('paths') or []):
                        pth = str(pth).strip()
                        if pth and pth not in seen:
                            seen.add(pth)
                            paths.append(pth)
                return paths

            def _retry_batch():
                paths = _load_current()
                return self.open_merge_diff_paths(paths) if paths else []

            def _retry_selected():
                paths = _selected_paths_union()
                if not paths:
                    try:
                        self._flash_host_toast('未选中失败批次', kind='info', ms=1200)
                    except Exception:
                        pass
                    self._last_merge_diff_batch_fail_history_multi_retry = []
                    return []
                self._last_merge_diff_batch_fail = list(paths)
                self._last_merge_diff_batch_fail_n = len(paths)
                out = self.open_merge_diff_paths(paths)
                self._last_merge_diff_batch_fail_history_multi_retry = list(out)
                return list(out)

            def _export_selected():
                ents = _selected_entries()
                if not ents:
                    # export all shown if none selected
                    ents = []
                    for i in range(lst.count()):
                        it = lst.item(i)
                        if it is None:
                            continue
                        ent = it.data(Qt.ItemDataRole.UserRole + 1)
                        if isinstance(ent, dict):
                            ents.append(ent)
                return self.export_merge_diff_batch_fail_history(ents)

            lst.itemDoubleClicked.connect(lambda it: _load_current(it))
            btns = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Close, parent=dlg)
            btn_retry = btns.addButton(
                '重开该批', QDialogButtonBox.ButtonRole.ActionRole)
            btn_retry.setObjectName('hostMergeDiffBatchFailHistoryRetry')
            btn_retry.clicked.connect(lambda *_: _retry_batch())
            btn_multi = btns.addButton(
                '批量重开选中', QDialogButtonBox.ButtonRole.ActionRole)
            btn_multi.setObjectName('hostMergeDiffBatchFailHistoryMultiRetry')
            btn_multi.clicked.connect(lambda *_: _retry_selected())
            btn_export = btns.addButton(
                '导出选中', QDialogButtonBox.ButtonRole.ActionRole)
            btn_export.setObjectName('hostMergeDiffBatchFailHistoryExport')
            btn_export.clicked.connect(lambda *_: _export_selected())
            btn_clear = btns.addButton(
                '清空历史', QDialogButtonBox.ButtonRole.ActionRole)
            btn_clear.setObjectName('hostMergeDiffBatchFailHistoryClear')
            btn_clear.clicked.connect(
                lambda *_: (self.clear_merge_diff_batch_fail_history(), lst.clear()))
            btns.rejected.connect(dlg.reject)
            lay.addWidget(btns)
            self._last_merge_diff_batch_fail_history_dialog = dlg
            self._last_merge_diff_batch_fail_history_list = lst
            self._last_merge_diff_batch_fail_history_multi_btn = btn_multi
            self._last_merge_diff_batch_fail_history_export_btn = btn_export
            self._last_merge_diff_batch_fail_history_shown = True
            if getattr(self, '_merge_diff_fail_hist_no_exec', False):
                return True
            dlg.exec()
        except Exception as err:
            try:
                self._flash_host_toast(f'失败历史失败 · {err}', kind='info')
            except Exception:
                pass
            return self.show_merge_diff_batch_fail_history(interactive=False)
        return True

    def export_merge_diff_batch_fail_history(
            self, entries=None, path: str = '', *, interactive: bool = True) -> str:
        """wave50: 导出失败历史（选中或全部）为 JSON 文本文件."""
        import json as _json
        if entries is None:
            entries = self.sorted_merge_diff_batch_fail_history()
        entries = list(entries or [])
        payload = []
        for ent in entries:
            if not isinstance(ent, dict):
                continue
            payload.append({
                'ts': str(ent.get('ts') or ''),
                'paths': [str(p) for p in list(ent.get('paths') or [])],
            })
        if not path and interactive and not getattr(
                self, '_merge_diff_fail_hist_export_no_dialog', False):
            try:
                path, _flt = QFileDialog.getSaveFileName(
                    self, '导出失败清单历史',
                    'merge-diff-fail-history.json',
                    'JSON (*.json);;Text (*.txt)')
            except Exception:
                path = ''
        if not path:
            # non-interactive / smoke: write to temp
            if getattr(self, '_merge_diff_fail_hist_export_path', None):
                path = str(self._merge_diff_fail_hist_export_path)
            else:
                path = '/tmp/sieans-merge-diff-fail-history.json'
        try:
            Path = __import__('pathlib').Path
            Path(path).write_text(
                _json.dumps(payload, ensure_ascii=False, indent=2),
                encoding='utf-8')
            self._last_merge_diff_batch_fail_history_export_path = str(path)
            self._last_merge_diff_batch_fail_history_export_n = len(payload)
            try:
                self._flash_host_toast(
                    f'已导出失败历史 · {len(payload)}', kind='ok', ms=1400)
            except Exception:
                pass
            return str(path)
        except Exception as err:
            try:
                self._flash_host_toast(f'导出失败 · {err}', kind='info', ms=1400)
            except Exception:
                pass
            self._last_merge_diff_batch_fail_history_export_path = ''
            return ''

    def retry_merge_diff_batch_fail_history_selected(
            self, entries=None) -> list:
        """wave50: 多选批次路径并集重开."""
        if entries is None:
            entries = []
        seen = set()
        paths = []
        for ent in list(entries or []):
            for pth in list((ent or {}).get('paths') or []):
                pth = str(pth).strip()
                if pth and pth not in seen:
                    seen.add(pth)
                    paths.append(pth)
        if not paths:
            self._last_merge_diff_batch_fail_history_multi_retry = []
            return []
        self._last_merge_diff_batch_fail = list(paths)
        out = self.open_merge_diff_paths(paths)
        self._last_merge_diff_batch_fail_history_multi_retry = list(out)
        return list(out)

    def retry_merge_diff_batch_fails(self) -> list:
        """wave46: 重开上次批量失败项."""
        fails = list(getattr(self, '_last_merge_diff_batch_fail', None) or [])
        if not fails:
            try:
                self._flash_host_toast('无失败项可重开', kind='info', ms=1200)
            except Exception:
                pass
            self._last_merge_diff_batch_retry = []
            return []
        out = self.open_merge_diff_paths(fails)
        self._last_merge_diff_batch_retry = list(out)
        return list(out)

    def show_merge_diff_batch_fails(self, *, interactive: bool = True) -> bool:
        """wave46: 失败项清单 · 可点/多选重开."""
        fails = list(getattr(self, '_last_merge_diff_batch_fail', None) or [])
        if not fails:
            hist = self.merge_diff_batch_fail_history()
            if hist:
                fails = list(hist[0].get('paths') or [])
                self._last_merge_diff_batch_fail = list(fails)
            if not fails:
                try:
                    self._flash_host_toast('无失败项可重开', kind='info', ms=1200)
                except Exception:
                    pass
                self._last_merge_diff_batch_fails_shown = False
                return False

        def _lab(d):
            try:
                from pathlib import Path as _P
                return _P(d).name or d
            except Exception:
                return d

        if not interactive:
            body = '\n'.join(f'{i}. {_lab(d)}\n   {d}' for i, d in enumerate(fails[:24], 1))
            try:
                QMessageBox.information(
                    self, f'批量打开失败 · {len(fails)}', body or '（空）')
            except Exception:
                pass
            self._last_merge_diff_batch_fails_shown = True
            return True
        try:
            dlg = QDialog(self)
            dlg.setWindowTitle(f'批量打开失败 · {len(fails)} · 可点重开')
            dlg.setObjectName('hostMergeDiffBatchFailsDialog')
            dlg.setMinimumWidth(420)
            lay = QVBoxLayout(dlg)
            tip = QLabel(
                '双击单项重开 · 多选后「重开选中」· 或「重开全部」', dlg)
            tip.setStyleSheet('color:#9aa0a6;font-size:11px;')
            lay.addWidget(tip)
            lst = QListWidget(dlg)
            lst.setObjectName('hostMergeDiffBatchFailsList')
            try:
                lst.setSelectionMode(
                    QListWidget.SelectionMode.ExtendedSelection)
            except Exception:
                pass
            for d in fails:
                it = QListWidgetItem(f'  {_lab(d)}  —  {d}')
                it.setData(Qt.ItemDataRole.UserRole, d)
                it.setToolTip(d + '\n双击重开')
                lst.addItem(it)
            lay.addWidget(lst)

            def _retry_selected() -> list:
                paths = []
                for it in lst.selectedItems():
                    p = str(it.data(Qt.ItemDataRole.UserRole) or '').strip()
                    if p:
                        paths.append(p)
                if not paths and lst.currentItem() is not None:
                    p = str(lst.currentItem().data(Qt.ItemDataRole.UserRole) or '').strip()
                    if p:
                        paths = [p]
                return self.open_merge_diff_paths(paths) if paths else []

            def _retry_one(item=None):
                it = item or lst.currentItem()
                if it is None:
                    return ''
                p = str(it.data(Qt.ItemDataRole.UserRole) or '').strip()
                return self.open_merge_diff_path(p) if p else ''

            lst.itemDoubleClicked.connect(lambda it: _retry_one(it))
            btns = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Close, parent=dlg)
            btn_sel = btns.addButton(
                '重开选中', QDialogButtonBox.ButtonRole.ActionRole)
            btn_sel.setObjectName('hostMergeDiffBatchFailsRetrySel')
            btn_sel.clicked.connect(lambda *_: _retry_selected())
            btn_all = btns.addButton(
                '重开全部', QDialogButtonBox.ButtonRole.ActionRole)
            btn_all.setObjectName('hostMergeDiffBatchFailsRetryAll')
            btn_all.clicked.connect(lambda *_: self.retry_merge_diff_batch_fails())
            btn_hist = btns.addButton(
                '失败历史', QDialogButtonBox.ButtonRole.ActionRole)
            btn_hist.setObjectName('hostMergeDiffBatchFailsHistory')
            btn_hist.clicked.connect(
                lambda *_: self.show_merge_diff_batch_fail_history())
            btns.rejected.connect(dlg.reject)
            lay.addWidget(btns)
            self._last_merge_diff_batch_fails_dialog = dlg
            self._last_merge_diff_batch_fails_list = lst
            self._last_merge_diff_batch_fails_shown = True
            if getattr(self, '_merge_diff_fails_no_exec', False):
                return True
            dlg.exec()
        except Exception as err:
            try:
                self._flash_host_toast(f'失败清单失败 · {err}', kind='info')
            except Exception:
                pass
            return self.show_merge_diff_batch_fails(interactive=False)
        return True

    def open_merge_diff_selected(self, lst=None) -> list:
        """wave44: 打开 diff 清单当前多选."""
        lst = lst if lst is not None else getattr(self, '_last_merge_diff_list', None)
        paths = []
        if lst is not None:
            try:
                items = lst.selectedItems()
            except Exception:
                items = []
            if not items:
                try:
                    cur = lst.currentItem()
                    items = [cur] if cur is not None else []
                except Exception:
                    items = []
            for it in items:
                try:
                    path = str(it.data(Qt.ItemDataRole.UserRole) or '').strip()
                except Exception:
                    path = ''
                if path:
                    paths.append(path)
        return self.open_merge_diff_paths(paths)

    def merge_import_alarm_film_csv_dirs_json(self, path_or_text: str = '') -> list:
        """wave40: 合并导入 JSON（去重并集）."""
        return self.import_alarm_film_csv_dirs_json(path_or_text, merge=True)


    def sev_chip_pin_ms(self) -> int:
        """wave38: 长按落钉时长 ms."""

        return int(getattr(self, '_sev_chip_pin_ms', 550) or 550)

    def set_sev_chip_pin_ms(self, ms: int, *, persist: bool = True) -> int:
        """wave38–39: 配置长按落钉时长（预设 300/550/800）；气泡同步."""
        ms = int(ms or 550)
        presets = (300, 550, 800)
        if ms not in presets:
            ms = min(presets, key=lambda x: abs(x - ms))
        self._sev_chip_pin_ms = ms
        self._sev_bubble_pin_ms = ms
        if persist:
            try:
                self._host_settings().setValue('host/sevChipPinMs', ms)
            except Exception:
                pass
        return ms

    def cycle_sev_chip_pin_ms(self) -> int:
        """wave38: 循环长按时长 300/550/800."""
        presets = (300, 550, 800)
        cur = self.sev_chip_pin_ms()
        try:
            nxt = presets[(presets.index(cur) + 1) % len(presets)]
        except ValueError:
            nxt = 550
        return self.set_sev_chip_pin_ms(nxt)

    def sev_chip_pin_arc_color(self) -> str:
        """wave38: 进度弧颜色."""
        arc = getattr(self, '_sev_chip_pin_arc', None)
        if arc is not None and hasattr(arc, 'color'):
            return arc.color()
        return '#f0c040'

    def set_sev_chip_pin_arc_color(self, color: str, *, persist: bool = True) -> str:
        """wave38–40: 配置进度弧颜色（共享单例）."""
        c = str(color or '').strip() or '#f0c040'
        if not c.startswith('#'):
            c = '#' + c
        arc = getattr(self, '_sev_pin_arc', None) or getattr(self, '_sev_chip_pin_arc', None)
        if arc is not None and hasattr(arc, 'set_color'):
            try:
                arc.set_color(c)
            except Exception:
                pass
        if persist:
            try:
                self._host_settings().setValue('host/sevChipPinArcColor', c)
            except Exception:
                pass
        return c

    def alarm_film_csv_dirs(self, *, max_n: int = None) -> list:
        """wave36–37: 多档另存目录记忆（新→旧，最多 max_n）."""
        if max_n is None:
            max_n = self.alarm_film_csv_dirs_max()
        max_n = max(1, min(8, int(max_n or 5)))
        out = []
        try:
            raw = self._host_settings().value('host/alarmFilmCsvDirs', [])
            if isinstance(raw, str):
                # legacy comma / newline
                parts = [p.strip() for p in raw.replace('\n', ',').split(',') if p.strip()]
                raw = parts
            if not isinstance(raw, (list, tuple)):
                raw = []
            for d in raw:
                s = str(d or '').strip()
                if s and s not in out:
                    out.append(s)
                if len(out) >= max_n:
                    break
        except Exception:
            out = []
        if not out:
            try:
                one = str(self._host_settings().value('host/alarmFilmCsvDir', '') or '').strip()
            except Exception:
                one = ''
            if one:
                out = [one]
        return out

    def set_alarm_film_csv_dir(self, directory: str) -> str:
        """Persist last CSV save directory（并推入多档）."""
        return self.remember_alarm_film_csv_dir(directory)[0] if directory else ''

    def remember_alarm_film_csv_dir(self, directory: str, *, max_n: int = None) -> list:
        """wave36–37: 推入多档另存记忆（去重置顶；上限可配）."""
        directory = str(directory or '').strip()
        if max_n is None:
            max_n = self.alarm_film_csv_dirs_max()
        max_n = max(1, min(8, int(max_n or 5)))
        dirs = self.alarm_film_csv_dirs(max_n=max_n)
        if directory:
            dirs = [directory] + [d for d in dirs if d != directory]
            dirs = dirs[:max_n]
        try:
            self._host_settings().setValue('host/alarmFilmCsvDirs', dirs)
            if dirs:
                self._host_settings().setValue('host/alarmFilmCsvDir', dirs[0])
        except Exception:
            pass
        return list(dirs)

    def save_all_alarm_film_paths_csv(self, path: str = '') -> str:
        """wave32–33: 另存全部 filmPath CSV；空 path 弹对话框并记住目录."""
        rows = self._collect_alarm_film_rows()
        if not rows:
            try:
                self._log_line('另存 paths CSV · 无胶片 path')
            except Exception:
                pass
            return ''
        if not path:
            from pathlib import Path as _P
            remembered = self.alarm_film_csv_dir()
            start = 'alarm-film-paths.csv'
            if remembered:
                try:
                    start = str(_P(remembered) / 'alarm-film-paths.csv')
                except Exception:
                    start = 'alarm-film-paths.csv'
            path, _ = QFileDialog.getSaveFileName(
                self, '另存胶片 paths CSV', start,
                'CSV (*.csv);;All (*)')
        if not path:
            return ''
        try:
            text = self._format_alarm_film_csv(rows)
            with open(path, 'w', encoding='utf-8') as f:
                f.write(text)
                if not text.endswith(chr(10)):
                    f.write(chr(10))
            # remember parent dir
            try:
                from pathlib import Path as _P
                parent = str(_P(path).resolve().parent)
                self.set_alarm_film_csv_dir(parent)
            except Exception:
                pass
            self._log_line(f'已另存胶片 path CSV · {len(rows)} · {path}')
            try:
                from pathlib import Path as _P2
                name = _P2(path).name
            except Exception:
                name = path
            try:
                from pathlib import Path as _P3
                open_dir = str(_P3(path).resolve().parent)
            except Exception:
                open_dir = ''
            try:
                self._flash_host_toast(
                    f'已另存 CSV · {len(rows)} · {name}',
                    kind='ok', open_path=open_dir or path, ms=3200)
            except Exception:
                pass
        except Exception as err:
            try:
                self._log_line(f'另存失败：{err}')
            except Exception:
                pass
            try:
                self._flash_host_toast(f'另存失败 · {err}', kind='info')
            except Exception:
                pass
            return ''
        return path

    def save_all_alarm_film_paths_csv_to_dir(self, directory: str) -> str:
        """wave36: 另存到指定记忆目录（文件名自动）."""
        directory = str(directory or '').strip()
        if not directory:
            return self.save_all_alarm_film_paths_csv()
        try:
            from pathlib import Path as _P
            from datetime import datetime as _dt
            _P(directory).mkdir(parents=True, exist_ok=True)
            name = f"alarm-film-paths-{_dt.now().strftime('%Y%m%d-%H%M%S')}.csv"
            path = str(_P(directory) / name)
        except Exception:
            path = ''
        if not path:
            return ''
        return self.save_all_alarm_film_paths_csv(path)

    def clear_liaison_toast_history(self) -> bool:
        """wave32: 清空联调 toast 切窗史."""
        hist = getattr(self, '_liaison_toast_history', None)
        secs = getattr(self, '_liaison_toast_history_secs', None)
        if hist is not None:
            hist.clear()
        if secs is not None:
            secs.clear()
        hbar = getattr(self, '_liaison_toast_history_bar', None)
        if hbar is not None:
            try:
                hbar.setText('')
                hbar.hide()
            except Exception:
                pass
        try:
            self._log_line('切窗史已清空')
        except Exception:
            pass
        return True

    def _build_liaison_toast_capacity_menu(self):
        """wave35–41: 切窗史容量菜单；长按H时显示「保持」徽标."""
        menu = QMenu(self)
        cur = int(getattr(self, '_liaison_toast_history_max', 5) or 5)
        keep = bool(getattr(self, '_toast_hist_cap_keep_open', False))
        if keep:
            act_keep = QAction('◉ 保持中 · 点此退出', menu)
            act_keep.setEnabled(True)
            act_keep.setObjectName('hostToastHistCapKeepBadge')
            act_keep.setProperty('isKeepBadge', True)
            act_keep.setProperty('isKeepExit', True)
            act_keep.setToolTip('点击退出保持；Esc 亦可')
            act_keep.triggered.connect(lambda *_: self.exit_toast_hist_cap_keep())
            menu.addAction(act_keep)
            menu.addSeparator()
            self._last_toast_hist_cap_keep_badge = True
        else:
            self._last_toast_hist_cap_keep_badge = False
        # wave36: 数字快捷 1–4 对应 3/5/8/12（菜单内）
        key_map = {3: '1', 5: '2', 8: '3', 12: '4'}
        for n in (3, 5, 8, 12):
            mark = '✓ ' if n == cur else ''
            def_mark = '（默认）' if n == 5 else ''
            sc = key_map.get(n, '')
            sc_lab = f'  [{sc}]' if sc else ''
            act = QAction(f'{mark}容量 {n}{def_mark}{sc_lab}', self)
            act.setData(n)
            act.setProperty('isDefault', n == 5)
            act.setCheckable(True)
            act.setChecked(n == cur)
            if sc:
                try:
                    act.setShortcut(QKeySequence(sc))
                    act.setShortcutVisibleInContextMenu(True)
                except Exception:
                    pass
            act.triggered.connect(
                lambda *_a, nn=n: self._apply_toast_hist_capacity(nn)
            )
            menu.addAction(act)
        menu.addSeparator()
        tip_on = self.toast_hist_cap_keep_exit_tip_enabled()
        act_tip = QAction(
            ('✓ ' if tip_on else '') + '退出保持提示', menu)
        act_tip.setCheckable(True)
        act_tip.setChecked(tip_on)
        act_tip.setProperty('isKeepExitTipToggle', True)
        act_tip.setObjectName('hostToastHistCapKeepExitTipToggle')
        act_tip.triggered.connect(
            lambda *_: self.set_toast_hist_cap_keep_exit_tip_enabled(
                not self.toast_hist_cap_keep_exit_tip_enabled())
        )
        menu.addAction(act_tip)
        anim_on = self.toast_hist_cap_tip_anim_enabled()
        act_anim = QAction(
            ('✓ ' if anim_on else '') + 'tip 热更动画', menu)
        act_anim.setCheckable(True)
        act_anim.setChecked(anim_on)
        act_anim.setProperty('isTipAnimToggle', True)
        act_anim.setObjectName('hostToastHistCapTipAnimToggle')
        act_anim.setToolTip('关闭后 tip 热更不再脉冲淡入')
        act_anim.triggered.connect(
            lambda *_: self.set_toast_hist_cap_tip_anim_enabled(
                not self.toast_hist_cap_tip_anim_enabled())
        )
        menu.addAction(act_anim)
        cur_ms = self.toast_hist_cap_tip_anim_ms()
        for ms, lab in ((200, '动画 200ms'), (320, '动画 320ms（默认）'),
                        (500, '动画 500ms'), (800, '动画 800ms')):
            mark = '✓ ' if ms == cur_ms else ''
            act_ms = QAction(f'{mark}{lab}', menu)
            act_ms.setCheckable(True)
            act_ms.setChecked(ms == cur_ms)
            act_ms.setData(ms)
            act_ms.setProperty('isTipAnimMs', True)
            act_ms.setProperty('tipAnimMsLabel', lab)
            act_ms.triggered.connect(
                lambda *_a, nn=ms: self.set_toast_hist_cap_tip_anim_ms(nn))
            menu.addAction(act_ms)
        cur_ez = self.toast_hist_cap_tip_anim_easing()
        for ez, lab in (
            ('OutCubic', '缓动 OutCubic（默认）'),
            ('InOutQuad', '缓动 InOutQuad'),
            ('OutBounce', '缓动 OutBounce'),
            ('Linear', '缓动 Linear'),
        ):
            mark = '✓ ' if ez == cur_ez else ''
            act_ez = QAction(f'{mark}{lab}', menu)
            act_ez.setCheckable(True)
            act_ez.setChecked(ez == cur_ez)
            act_ez.setData(ez)
            act_ez.setProperty('isTipAnimEasing', True)
            act_ez.setProperty('tipAnimEasingLabel', lab)
            act_ez.triggered.connect(
                lambda *_a, nn=ez: self.set_toast_hist_cap_tip_anim_easing(nn))
            menu.addAction(act_ez)
        act_clear = QAction('清空切窗史', self)
        act_clear.triggered.connect(self.clear_liaison_toast_history)
        menu.addAction(act_clear)
        return menu

    def _focus_toast_hist_cap_menu(self, menu: QMenu):
        """wave37–38: 容量菜单焦点落在当前项；装 Esc/方向键导航."""
        if menu is None:
            return None
        cur = int(getattr(self, '_liaison_toast_history_max', 5) or 5)
        focus = None
        for act in menu.actions():
            try:
                if act.isSeparator():
                    continue
                if int(act.data() or 0) == cur:
                    focus = act
                    break
            except Exception:
                continue
        if focus is not None:
            try:
                menu.setActiveAction(focus)
                focus.setChecked(True)
            except Exception:
                pass
        self._last_toast_hist_cap_focus = focus
        self._install_toast_hist_cap_menu_nav(menu)
        return focus

    def _toast_hist_cap_selectable_actions(self, menu: QMenu):
        """wave38: 容量菜单可选（非分隔）项."""
        out = []
        if menu is None:
            return out
        for act in menu.actions():
            try:
                if act.isSeparator():
                    continue
                if not act.isEnabled():
                    continue
                out.append(act)
            except Exception:
                continue
        return out

    def navigate_toast_hist_cap_menu(self, menu: QMenu = None, delta: int = 1):
        """wave38: 方向键导航容量菜单；返回新焦点 action."""
        menu = menu or getattr(self, '_last_toast_hist_cap_menu', None)
        if menu is None:
            return None
        acts = self._toast_hist_cap_selectable_actions(menu)
        if not acts:
            return None
        cur = menu.activeAction()
        try:
            idx = acts.index(cur) if cur in acts else 0
        except ValueError:
            idx = 0
        nxt = acts[(idx + int(delta or 0)) % len(acts)]
        try:
            menu.setActiveAction(nxt)
        except Exception:
            pass
        self._last_toast_hist_cap_focus = nxt
        return nxt

    def toast_hist_cap_menu_key(self, key, menu: QMenu = None):
        """wave38–39: Esc/↑↓/回车；数字键 1–4 直达容量后自动关."""
        from PySide6.QtCore import Qt as _Qt
        menu = menu or getattr(self, '_last_toast_hist_cap_menu', None)
        if menu is None:
            return None
        # normalize key
        try:
            k = int(key)
        except Exception:
            k = key
        if k in (_Qt.Key.Key_Escape, getattr(_Qt, 'Key_Escape', 16777216)):
            try:
                menu.close()
            except Exception:
                pass
            self._toast_hist_cap_keep_open = False
            self._last_toast_hist_cap_closed_by = 'esc'
            return 'esc'
        # wave40: H 键 — 开始/标记长按保持（smoke 可直接 set_toast_hist_cap_keep_open）
        if k in (_Qt.Key.Key_H, getattr(_Qt, 'Key_H', 72)):
            self.begin_toast_hist_cap_hold()
            return 'hold-begin'
        if k in (_Qt.Key.Key_Up, getattr(_Qt, 'Key_Up', 16777235)):
            act = self.navigate_toast_hist_cap_menu(menu, -1)
            return act
        if k in (_Qt.Key.Key_Down, getattr(_Qt, 'Key_Down', 16777237)):
            act = self.navigate_toast_hist_cap_menu(menu, 1)
            return act
        # wave39: digit 1–4 → capacity 3/5/8/12 then auto-close
        digit_map = {
            int(_Qt.Key.Key_1): 3,
            int(_Qt.Key.Key_2): 5,
            int(_Qt.Key.Key_3): 8,
            int(_Qt.Key.Key_4): 12,
        }
        if k in digit_map:
            n = digit_map[k]
            focus = None
            for act in menu.actions():
                try:
                    if act.isSeparator():
                        continue
                    if int(act.data() or 0) == n:
                        focus = act
                        break
                except Exception:
                    continue
            if focus is not None:
                try:
                    menu.setActiveAction(focus)
                except Exception:
                    pass
            # wave40: 长按 H 保持菜单不关 — 仍应用容量
            keep = bool(getattr(self, '_toast_hist_cap_keep_open', False))
            self._apply_toast_hist_capacity(n)
            self._last_toast_hist_cap_digit = n
            if keep:
                self._last_toast_hist_cap_closed_by = 'digit-hold'
                try:
                    self._flash_host_toast(
                        f'容量 → {n} · 长按H保持菜单', kind='info', ms=1000)
                except Exception:
                    pass
                return ('digit-hold', n)
            try:
                menu.close()
            except Exception:
                pass
            self._last_toast_hist_cap_closed_by = 'digit'
            return ('digit', n)
        if k in (
            _Qt.Key.Key_Return, _Qt.Key.Key_Enter,
            getattr(_Qt, 'Key_Return', 16777220),
            getattr(_Qt, 'Key_Enter', 16777221),
        ):
            act = menu.activeAction()
            if act is not None and act.isEnabled():
                try:
                    act.trigger()
                except Exception:
                    pass
            try:
                menu.close()
            except Exception:
                pass
            self._last_toast_hist_cap_closed_by = 'return'
            return act
        return None

    def _install_toast_hist_cap_menu_nav(self, menu: QMenu):
        """wave38: 给容量菜单装 key 导航（Esc/方向/回车）."""
        if menu is None:
            return
        # avoid double-install
        if getattr(menu, '_sieans_cap_nav', False):
            return
        try:
            menu._sieans_cap_nav = True
        except Exception:
            pass

        def _filter(obj, event):
            try:
                from PySide6.QtCore import QEvent
                if event.type() == QEvent.Type.KeyPress:
                    key = event.key()
                    result = self.toast_hist_cap_menu_key(key, menu)
                    if result is not None:
                        return True
            except Exception:
                pass
            return False

        try:
            menu.installEventFilter(self)
            # store bound filter via attribute; host eventFilter dispatches
            self._toast_hist_cap_nav_menu = menu
        except Exception:
            pass
        # also accept shortcuts on menu itself
        try:
            menu.setProperty('sieansCapNav', True)
        except Exception:
            pass

    def eventFilter(self, obj, event):  # noqa: N802
        """wave38–45: 容量菜单键控；色板最近色右键清除."""
        try:
            if self._on_sev_pin_arc_seize_color_menu_event(obj, event):
                return True
        except Exception:
            pass
        try:
            from PySide6.QtCore import QEvent, Qt as _Qt
            nav_menu = getattr(self, '_toast_hist_cap_nav_menu', None)
            if nav_menu is not None and obj is nav_menu:
                et = event.type()
                if et == QEvent.Type.KeyPress:
                    key = event.key()
                    if key in (_Qt.Key.Key_H, getattr(_Qt, 'Key_H', 72)):
                        if not getattr(self, '_toast_hist_cap_h_down', False):
                            self.begin_toast_hist_cap_hold()
                        return True
                    result = self.toast_hist_cap_menu_key(key, nav_menu)
                    if result is not None:
                        return True
                elif et == QEvent.Type.KeyRelease:
                    key = event.key()
                    if key in (_Qt.Key.Key_H, getattr(_Qt, 'Key_H', 72)):
                        self.end_toast_hist_cap_hold()
                        return True
        except Exception:
            pass
        try:
            return super().eventFilter(obj, event)
        except Exception:
            return False

    def set_toast_hist_cap_keep_open(self, keep: bool = True) -> bool:
        """wave40: 长按 H 对照 — 保持容量菜单不因数字键关闭."""
        self._toast_hist_cap_keep_open = bool(keep)
        return self._toast_hist_cap_keep_open

    def begin_toast_hist_cap_hold(self) -> bool:
        """wave40: 开始长按 H（启动 hold 计时）."""
        self._toast_hist_cap_h_down = True
        timer = getattr(self, '_toast_hist_cap_hold_timer', None)
        if timer is not None:
            timer.start()
        return True

    def end_toast_hist_cap_hold(self) -> bool:
        """wave40: 松开 H；若尚未触发长按则取消计时."""
        self._toast_hist_cap_h_down = False
        timer = getattr(self, '_toast_hist_cap_hold_timer', None)
        if timer is not None and timer.isActive():
            timer.stop()
        # release clears keep_open only if we want momentary; keep until Esc
        return True

    def _on_toast_hist_cap_hold_fire(self):
        """wave40–41: 长按 H 满时 → 保持菜单不关 + 徽标."""
        if not getattr(self, '_toast_hist_cap_h_down', False):
            return
        self._toast_hist_cap_keep_open = True
        try:
            self._flash_host_toast('长按H · 菜单保持不关', kind='info', ms=1200)
            self._log_line('长按H · 容量菜单保持')
        except Exception:
            pass
        self._last_toast_hist_cap_hold = True
        try:
            self._ensure_toast_hist_cap_keep_badge()
        except Exception:
            pass

    def toast_hist_cap_keep_exit_tip_enabled(self) -> bool:
        """wave44: 退出保持是否闪 tip（默认开）."""
        v = getattr(self, '_toast_hist_cap_keep_exit_tip', None)
        if v is None:
            try:
                raw = self._host_settings().value(
                    'host/toastHistCapKeepExitTip', True)
                if isinstance(raw, str):
                    v = raw.strip().lower() not in ('0', 'false', 'no', 'off')
                else:
                    v = bool(raw)
            except Exception:
                v = True
            self._toast_hist_cap_keep_exit_tip = bool(v)
        return bool(self._toast_hist_cap_keep_exit_tip)

    def set_toast_hist_cap_keep_exit_tip_enabled(
            self, enabled: bool = True, *, persist: bool = True) -> bool:
        """wave44–45: 配置退出保持 tip 开关；热更菜单勾."""
        self._toast_hist_cap_keep_exit_tip = bool(enabled)
        if persist:
            try:
                self._host_settings().setValue(
                    'host/toastHistCapKeepExitTip', bool(enabled))
            except Exception:
                pass
        try:
            self._refresh_toast_hist_cap_keep_exit_tip_action()
        except Exception:
            pass
        return self._toast_hist_cap_keep_exit_tip

    def toast_hist_cap_tip_anim_enabled(self) -> bool:
        """wave47: tip 热更脉冲动画开关（默认开）."""
        v = getattr(self, '_toast_hist_cap_tip_anim', None)
        if v is None:
            try:
                raw = self._host_settings().value('host/toastHistCapTipAnim', True)
                if isinstance(raw, str):
                    v = raw.strip().lower() not in ('0', 'false', 'no', 'off')
                else:
                    v = bool(raw)
            except Exception:
                v = True
            self._toast_hist_cap_tip_anim = bool(v)
        return bool(self._toast_hist_cap_tip_anim)

    def set_toast_hist_cap_tip_anim_enabled(
            self, enabled: bool = True, *, persist: bool = True) -> bool:
        """wave47: 配置 tip 热更动画；热更菜单勾."""
        self._toast_hist_cap_tip_anim = bool(enabled)
        if persist:
            try:
                self._host_settings().setValue(
                    'host/toastHistCapTipAnim', bool(enabled))
            except Exception:
                pass
        try:
            self._refresh_toast_hist_cap_tip_anim_action()
        except Exception:
            pass
        return self._toast_hist_cap_tip_anim

    def toast_hist_cap_tip_anim_ms(self) -> int:
        """wave48: tip 热更动画时长 ms（默认 320）."""
        v = getattr(self, '_toast_hist_cap_tip_anim_ms', None)
        if v is None:
            try:
                v = int(self._host_settings().value(
                    'host/toastHistCapTipAnimMs', 320) or 320)
            except Exception:
                v = 320
            self._toast_hist_cap_tip_anim_ms = max(80, min(2000, int(v)))
        return int(self._toast_hist_cap_tip_anim_ms)

    def set_toast_hist_cap_tip_anim_ms(
            self, ms: int = 320, *, persist: bool = True) -> int:
        """wave48: 配置 tip 动画时长；热更菜单标记."""
        try:
            ms = max(80, min(2000, int(ms)))
        except Exception:
            ms = 320
        self._toast_hist_cap_tip_anim_ms = ms
        if persist:
            try:
                self._host_settings().setValue(
                    'host/toastHistCapTipAnimMs', int(ms))
            except Exception:
                pass
        try:
            self._refresh_toast_hist_cap_tip_anim_ms_action()
        except Exception:
            pass
        self._last_toast_hist_cap_tip_anim_ms = ms
        return ms

    def toast_hist_cap_tip_anim_easing(self) -> str:
        """wave49: tip 动画 easing 名（OutCubic/InOutQuad/OutBounce/Linear）."""
        v = getattr(self, '_toast_hist_cap_tip_anim_easing', None)
        if v not in ('OutCubic', 'InOutQuad', 'OutBounce', 'Linear'):
            try:
                v = str(self._host_settings().value(
                    'host/toastHistCapTipAnimEasing', 'OutCubic') or 'OutCubic'
                ).strip()
            except Exception:
                v = 'OutCubic'
            if v not in ('OutCubic', 'InOutQuad', 'OutBounce', 'Linear'):
                v = 'OutCubic'
            self._toast_hist_cap_tip_anim_easing = v
        return str(self._toast_hist_cap_tip_anim_easing)

    def set_toast_hist_cap_tip_anim_easing(
            self, name: str = 'OutCubic', *, persist: bool = True) -> str:
        """wave49: 配置 tip 动画 easing；热更菜单勾选."""
        name = str(name or 'OutCubic').strip()
        if name not in ('OutCubic', 'InOutQuad', 'OutBounce', 'Linear'):
            name = 'OutCubic'
        self._toast_hist_cap_tip_anim_easing = name
        if persist:
            try:
                self._host_settings().setValue(
                    'host/toastHistCapTipAnimEasing', name)
            except Exception:
                pass
        try:
            self._refresh_toast_hist_cap_tip_anim_easing_action()
        except Exception:
            pass
        self._last_toast_hist_cap_tip_anim_easing = name
        if not getattr(self, '_toast_hist_cap_tip_anim_easing_quiet', False):
            try:
                self.preview_toast_hist_cap_tip_anim_easing(name)
            except Exception:
                pass
        return name

    def preview_toast_hist_cap_tip_anim_easing(self, name: str = None) -> bool:
        """wave50–51: 切换 easing 后预览脉冲 tip + 曲线小窗."""
        if name:
            self._toast_hist_cap_tip_anim_easing = str(name)
        try:
            self.set_toast_hist_cap_tip_anim_enabled(True)
        except Exception:
            pass
        try:
            self._flash_host_toast(
                f'缓动预览 · {self.toast_hist_cap_tip_anim_easing()}',
                kind='info', ms=700, animate=True)
            pulsed = bool(getattr(self, '_last_host_toast_pulsed', False))
        except Exception:
            pulsed = False
        try:
            if not getattr(self, '_toast_hist_cap_tip_anim_curve_quiet', False):
                self.show_toast_hist_cap_tip_anim_easing_curve(
                    self.toast_hist_cap_tip_anim_easing())
        except Exception:
            pass
        self._last_toast_hist_cap_tip_anim_easing_previewed = pulsed
        return pulsed

    def _toast_tip_anim_easing_curve_samples(
            self, name: str = None, n: int = 48) -> list:
        """wave51: 采样 easing 曲线点 [(t,y),...]."""
        if name:
            prev = getattr(self, '_toast_hist_cap_tip_anim_easing', None)
            self._toast_hist_cap_tip_anim_easing = str(name)
        try:
            curve = self._toast_tip_anim_easing_curve()
            pts = []
            steps = max(8, int(n or 48))
            for i in range(steps + 1):
                t = i / steps
                try:
                    y = float(curve.valueForProgress(t))
                except Exception:
                    y = t
                pts.append((t, y))
            self._last_toast_hist_cap_tip_anim_curve_samples = list(pts)
            return pts
        finally:
            if name and 'prev' in locals() and prev is not None:
                # keep name if intentionally set; only restore if we temporarily swapped
                # when name was passed for sampling alone — leave as set for preview consistency
                pass

    def show_toast_hist_cap_tip_anim_easing_curve(
            self, name: str = None, compare: str = None, *,
            interactive: bool = True) -> bool:
        """wave51–52: tip easing 曲线小窗；可选对比双缓动."""
        name = str(name or self.toast_hist_cap_tip_anim_easing() or 'OutCubic')
        pts = self._toast_tip_anim_easing_curve_samples(name, 64)
        pts_b = None
        name_b = None
        if compare:
            name_b = str(compare).strip()
            if name_b and name_b != name:
                # sample without permanently changing current easing
                cur = self.toast_hist_cap_tip_anim_easing()
                pts_b = self._toast_tip_anim_easing_curve_samples(name_b, 64)
                try:
                    self._toast_hist_cap_tip_anim_easing = cur
                except Exception:
                    pass
            else:
                name_b = None

        class _CurvePane(QWidget):
            def __init__(self, parent=None):
                super().__init__(parent)
                self._pts = list(pts)
                self._pts_b = list(pts_b) if pts_b else None
                self._name = name
                self._name_b = name_b
                self.setMinimumSize(240, 150)
                self.setObjectName('hostToastTipAnimEasingCurvePane')

            def paintEvent(self, event):
                p = QPainter(self)
                try:
                    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
                    p.fillRect(self.rect(), QColor('#1e2126'))
                    m = 18
                    w = max(1, self.width() - 2 * m)
                    h = max(1, self.height() - 2 * m)
                    p.setPen(QPen(QColor('#3a3d42'), 1))
                    p.drawRect(m, m, w, h)
                    p.setPen(QPen(QColor('#3a3d42'), 1, Qt.PenStyle.DashLine))
                    p.drawLine(m, m + h, m + w, m)

                    def _draw(pts_local, color, width=2):
                        path = QPainterPath()
                        first = True
                        for t, y in pts_local:
                            x = m + t * w
                            yy = m + (1.0 - max(0.0, min(1.2, y)) / 1.2) * h
                            if first:
                                path.moveTo(x, yy)
                                first = False
                            else:
                                path.lineTo(x, yy)
                        p.setPen(QPen(QColor(color), width))
                        p.drawPath(path)

                    _draw(self._pts, '#5b9cff', 2)
                    if self._pts_b:
                        _draw(self._pts_b, '#e35d6a', 2)
                    p.setPen(QColor('#9aa0a6'))
                    if self._name_b:
                        p.drawText(
                            8, 14,
                            f'蓝 {self._name}  ·  红 {self._name_b}')
                    else:
                        p.drawText(8, 14, f'缓动 · {self._name}')
                finally:
                    p.end()

        try:
            dlg = QDialog(self)
            title = (
                f'缓动对比 · {name} vs {name_b}' if name_b
                else f'缓动曲线 · {name}')
            dlg.setWindowTitle(title)
            dlg.setObjectName('hostToastTipAnimEasingCurveDialog')
            dlg.setMinimumSize(300, 240)
            lay = QVBoxLayout(dlg)
            # compare controls
            crow = QHBoxLayout()
            crow.addWidget(QLabel('主:', dlg))
            box_a = QComboBox(dlg)
            box_a.setObjectName('hostToastTipAnimEasingCurvePrimary')
            crow.addWidget(QLabel('对比:', dlg))
            box_b = QComboBox(dlg)
            box_b.setObjectName('hostToastTipAnimEasingCurveCompare')
            for ez in ('OutCubic', 'InOutQuad', 'OutBounce', 'Linear'):
                box_a.addItem(ez, ez)
                box_b.addItem(ez, ez)
            box_b.insertItem(0, '（无）', '')
            ia = max(0, box_a.findData(name))
            box_a.setCurrentIndex(ia)
            if name_b:
                ib = box_b.findData(name_b)
                box_b.setCurrentIndex(ib if ib >= 0 else 0)
            else:
                box_b.setCurrentIndex(0)
            crow.addWidget(box_a, 1)
            crow.addWidget(box_b, 1)
            lay.addLayout(crow)
            pane = _CurvePane(dlg)
            lay.addWidget(pane, 1)

            def _refresh_pane():
                na = str(box_a.currentData() or 'OutCubic')
                nb = str(box_b.currentData() or '') or None
                cur = self.toast_hist_cap_tip_anim_easing()
                pane._pts = self._toast_tip_anim_easing_curve_samples(na, 64)
                if nb and nb != na:
                    pane._pts_b = self._toast_tip_anim_easing_curve_samples(nb, 64)
                    pane._name_b = nb
                else:
                    pane._pts_b = None
                    pane._name_b = None
                pane._name = na
                try:
                    self._toast_hist_cap_tip_anim_easing = cur
                except Exception:
                    pass
                self._last_toast_hist_cap_tip_anim_curve_name = na
                self._last_toast_hist_cap_tip_anim_curve_compare = pane._name_b
                dlg.setWindowTitle(
                    f'缓动对比 · {na} vs {pane._name_b}' if pane._name_b
                    else f'缓动曲线 · {na}')
                pane.update()

            box_a.currentIndexChanged.connect(lambda *_: _refresh_pane())
            box_b.currentIndexChanged.connect(lambda *_: _refresh_pane())
            tip = QLabel(
                '横轴时间 · 纵轴进度 · 蓝=主 / 红=对比（虚线=线性） · 可导出 PNG', dlg)
            tip.setStyleSheet('color:#9aa0a6;font-size:11px;')
            lay.addWidget(tip)
            brow = QHBoxLayout()
            btn_png = QPushButton('导出 PNG', dlg)
            btn_png.setObjectName('hostToastTipAnimEasingCurveExportPng')
            btn_png.setToolTip('将当前曲线面板导出为 PNG')
            btn_png.clicked.connect(
                lambda *_: self.export_toast_hist_cap_tip_anim_easing_curve_png())
            brow.addWidget(btn_png)
            brow.addStretch(1)
            btns = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Close, parent=dlg)
            btns.rejected.connect(dlg.reject)
            btns.accepted.connect(dlg.accept)
            brow.addWidget(btns)
            lay.addLayout(brow)
            self._last_toast_hist_cap_tip_anim_curve_dialog = dlg
            self._last_toast_hist_cap_tip_anim_curve_pane = pane
            self._last_toast_hist_cap_tip_anim_curve_name = name
            self._last_toast_hist_cap_tip_anim_curve_compare = name_b
            self._last_toast_hist_cap_tip_anim_curve_box_a = box_a
            self._last_toast_hist_cap_tip_anim_curve_box_b = box_b
            self._last_toast_hist_cap_tip_anim_curve_export_btn = btn_png
            self._last_toast_hist_cap_tip_anim_curve_shown = True
            if getattr(self, '_toast_hist_cap_tip_anim_curve_no_exec', False) or not interactive:
                return True
            dlg.exec()
            return True
        except Exception as err:
            self._last_toast_hist_cap_tip_anim_curve_shown = False
            try:
                self._flash_host_toast(f'曲线预览失败 · {err}', kind='info', ms=1200)
            except Exception:
                pass
            return False

    def export_toast_hist_cap_tip_anim_easing_curve_png(
            self, path: str = None) -> str:
        """wave53: 导出缓动曲线面板为 PNG."""
        pane = getattr(self, '_last_toast_hist_cap_tip_anim_curve_pane', None)
        if pane is None:
            # build quietly if needed
            try:
                quiet = getattr(self, '_toast_hist_cap_tip_anim_curve_no_exec', False)
                self._toast_hist_cap_tip_anim_curve_no_exec = True
                self.show_toast_hist_cap_tip_anim_easing_curve(interactive=False)
                self._toast_hist_cap_tip_anim_curve_no_exec = quiet
            except Exception:
                pass
            pane = getattr(self, '_last_toast_hist_cap_tip_anim_curve_pane', None)
        if pane is None:
            self._last_toast_hist_cap_tip_anim_curve_png = ''
            try:
                self._flash_host_toast('无曲线可导出', kind='info', ms=1200)
            except Exception:
                pass
            return ''
        try:
            pane.resize(max(pane.width(), 320), max(pane.height(), 200))
            pane.update()
            pm = pane.grab()
        except Exception as err:
            self._last_toast_hist_cap_tip_anim_curve_png = ''
            try:
                self._flash_host_toast(f'曲线抓取失败 · {err}', kind='info', ms=1200)
            except Exception:
                pass
            return ''
        if path is None and not getattr(
                self, '_toast_hist_cap_tip_anim_curve_png_no_dialog', False):
            try:
                name = getattr(
                    self, '_last_toast_hist_cap_tip_anim_curve_name', None) or 'easing'
                cmp = getattr(
                    self, '_last_toast_hist_cap_tip_anim_curve_compare', None)
                sug = f'sieans-easing-{name}'
                if cmp:
                    sug += f'-vs-{cmp}'
                sug += '.png'
                path, _ = QFileDialog.getSaveFileName(
                    self, '导出缓动曲线 PNG', sug, 'PNG (*.png)')
            except Exception:
                path = None
        if not path:
            path = getattr(self, '_toast_hist_cap_tip_anim_curve_png_path', '') or ''
        if not path:
            self._last_toast_hist_cap_tip_anim_curve_png = ''
            return ''
        if not str(path).lower().endswith('.png'):
            path = str(path) + '.png'
        try:
            ok = pm.save(str(path), 'PNG')
        except Exception as err:
            ok = False
            try:
                self._flash_host_toast(f'PNG 保存失败 · {err}', kind='info', ms=1200)
            except Exception:
                pass
            self._last_toast_hist_cap_tip_anim_curve_png = ''
            return ''
        if not ok:
            self._last_toast_hist_cap_tip_anim_curve_png = ''
            try:
                self._flash_host_toast('PNG 保存失败', kind='info', ms=1200)
            except Exception:
                pass
            return ''
        self._last_toast_hist_cap_tip_anim_curve_png = str(path)
        try:
            from pathlib import Path as _P
            lab = _P(path).name
        except Exception:
            lab = str(path)
        try:
            self._flash_host_toast(f'已导出曲线 PNG · {lab}', kind='ok', ms=1600)
        except Exception:
            pass
        return str(path)

    def show_toast_hist_cap_tip_anim_easing_curve_compare(
            self, name_a: str = None, name_b: str = 'Linear',
            *, interactive: bool = True) -> bool:
        """wave52: 双缓动对比曲线小窗."""
        name_a = str(name_a or self.toast_hist_cap_tip_anim_easing() or 'OutCubic')
        name_b = str(name_b or 'Linear')
        ok = self.show_toast_hist_cap_tip_anim_easing_curve(
            name_a, compare=name_b, interactive=interactive)
        self._last_toast_hist_cap_tip_anim_curve_compare_shown = bool(ok)
        return ok

    def _toast_tip_anim_easing_curve(self) -> QEasingCurve:
        """wave49: 名 → QEasingCurve."""
        name = self.toast_hist_cap_tip_anim_easing()
        mapping = {
            'OutCubic': QEasingCurve.Type.OutCubic,
            'InOutQuad': QEasingCurve.Type.InOutQuad,
            'OutBounce': QEasingCurve.Type.OutBounce,
            'Linear': QEasingCurve.Type.Linear,
        }
        return QEasingCurve(mapping.get(name, QEasingCurve.Type.OutCubic))

    def _refresh_toast_hist_cap_tip_anim_easing_action(self) -> bool:
        """wave49: 热更容量菜单 tip easing 勾选."""
        cur = self.toast_hist_cap_tip_anim_easing()
        updated = False
        for menu in (
            getattr(self, '_last_toast_hist_cap_menu', None),
            getattr(self, '_toast_hist_cap_nav_menu', None),
        ):
            if menu is None:
                continue
            for act in menu.actions():
                try:
                    if not act.property('isTipAnimEasing'):
                        continue
                    name = str(act.data() or '')
                    on = name == cur
                    act.setChecked(on)
                    base = str(act.property('tipAnimEasingLabel') or act.text())
                    lab = base.lstrip('✓ ').strip()
                    act.setProperty('tipAnimEasingLabel', lab)
                    act.setText(('✓ ' if on else '') + lab)
                    updated = True
                except Exception:
                    continue
        self._last_toast_hist_cap_tip_anim_easing_refreshed = updated
        return updated

    def _refresh_toast_hist_cap_tip_anim_ms_action(self) -> bool:
        """wave48: 热更容量菜单 tip 动画时长勾选."""
        cur = self.toast_hist_cap_tip_anim_ms()
        updated = False
        for menu in (
            getattr(self, '_last_toast_hist_cap_menu', None),
            getattr(self, '_toast_hist_cap_nav_menu', None),
        ):
            if menu is None:
                continue
            for act in menu.actions():
                try:
                    if not act.property('isTipAnimMs'):
                        continue
                    ms = int(act.data() or 0)
                    on = ms == cur
                    act.setChecked(on)
                    base = str(act.property('tipAnimMsLabel') or act.text())
                    # strip leading check
                    lab = base.lstrip('✓ ').strip()
                    act.setProperty('tipAnimMsLabel', lab)
                    act.setText(('✓ ' if on else '') + lab)
                    updated = True
                except Exception:
                    continue
        self._last_toast_hist_cap_tip_anim_ms_refreshed = updated
        return updated

    def _refresh_toast_hist_cap_tip_anim_action(self) -> bool:
        """wave47: 热更容量菜单「tip 动画」勾选/文案."""
        on = self.toast_hist_cap_tip_anim_enabled()
        updated = False
        for menu in (
            getattr(self, '_last_toast_hist_cap_menu', None),
            getattr(self, '_toast_hist_cap_nav_menu', None),
        ):
            if menu is None:
                continue
            for act in menu.actions():
                try:
                    if not act.property('isTipAnimToggle'):
                        continue
                    act.setChecked(on)
                    act.setText(('✓ ' if on else '') + 'tip 热更动画')
                    updated = True
                except Exception:
                    continue
        self._last_toast_hist_cap_tip_anim_refreshed = updated
        return updated

    def _refresh_toast_hist_cap_keep_exit_tip_action(self) -> bool:
        """wave45–46: 热更容量菜单「退出保持提示」勾选/文案 + 脉冲动画."""
        on = self.toast_hist_cap_keep_exit_tip_enabled()
        updated = False
        for menu in (
            getattr(self, '_last_toast_hist_cap_menu', None),
            getattr(self, '_toast_hist_cap_nav_menu', None),
        ):
            if menu is None:
                continue
            for act in menu.actions():
                try:
                    if not act.property('isKeepExitTipToggle'):
                        continue
                    act.setChecked(on)
                    act.setText(('✓ ' if on else '') + '退出保持提示')
                    updated = True
                except Exception:
                    continue
        self._last_toast_hist_cap_keep_exit_tip_refreshed = updated
        if updated and not getattr(self, '_toast_hist_cap_keep_exit_tip_quiet', False):
            try:
                self._flash_host_toast(
                    f'退出保持提示 · {"开" if on else "关"}',
                    kind='info', ms=900, animate=True)
                self._last_toast_hist_cap_keep_exit_tip_animated = True
            except Exception:
                self._last_toast_hist_cap_keep_exit_tip_animated = False
        return updated

    def exit_toast_hist_cap_keep(self) -> bool:
        """wave42–44: 保持徽标一键退出；tip 可关."""
        was = bool(getattr(self, '_toast_hist_cap_keep_open', False))
        self._toast_hist_cap_keep_open = False
        self._toast_hist_cap_h_down = False
        self._last_toast_hist_cap_keep_exited = True
        # remove badge actions from open menu
        menu = getattr(self, '_last_toast_hist_cap_menu', None) or getattr(
            self, '_toast_hist_cap_nav_menu', None)
        if menu is not None:
            for act in list(menu.actions()):
                try:
                    if act.property('isKeepBadge') or act.property('isKeepExit'):
                        menu.removeAction(act)
                except Exception:
                    continue
        self._last_toast_hist_cap_keep_badge = False
        if was:
            tip = '✓ 已退出保持 · 数字键将关闭菜单'
            if self.toast_hist_cap_keep_exit_tip_enabled():
                try:
                    self._flash_host_toast(tip, kind='ok', ms=1400)
                except Exception:
                    pass
                self._last_toast_hist_cap_keep_exit_tip = tip
            else:
                self._last_toast_hist_cap_keep_exit_tip = ''
            try:
                self._log_line('容量菜单保持 · 已退出')
            except Exception:
                pass
        return was

    def _ensure_toast_hist_cap_keep_badge(self) -> bool:
        """wave41–42: 若容量菜单已开且保持中，注入可点退出的「保持」徽标."""
        menu = getattr(self, '_last_toast_hist_cap_menu', None) or getattr(
            self, '_toast_hist_cap_nav_menu', None)
        if menu is None or not bool(getattr(self, '_toast_hist_cap_keep_open', False)):
            return False
        for act in menu.actions():
            try:
                if act.property('isKeepBadge'):
                    # upgrade disabled legacy badge
                    try:
                        act.setEnabled(True)
                        act.setText('◉ 保持中 · 点此退出')
                        act.setProperty('isKeepExit', True)
                        act.triggered.disconnect()
                    except Exception:
                        pass
                    try:
                        act.triggered.connect(
                            lambda *_: self.exit_toast_hist_cap_keep())
                    except Exception:
                        pass
                    self._last_toast_hist_cap_keep_badge = True
                    return True
            except Exception:
                continue
        act_keep = QAction('◉ 保持中 · 点此退出', menu)
        act_keep.setEnabled(True)
        act_keep.setObjectName('hostToastHistCapKeepBadge')
        act_keep.setProperty('isKeepBadge', True)
        act_keep.setProperty('isKeepExit', True)
        act_keep.setToolTip('点击退出保持；Esc 亦可')
        act_keep.triggered.connect(lambda *_: self.exit_toast_hist_cap_keep())
        before = menu.actions()[0] if menu.actions() else None
        if before is not None:
            menu.insertAction(before, act_keep)
            menu.insertSeparator(before)
        else:
            menu.addAction(act_keep)
        self._last_toast_hist_cap_keep_badge = True
        return True

    def _on_toast_hist_cap_hotkey(self):
        """wave36–37: Alt+H → 容量菜单（焦点键选当前项）."""
        # wave40: 新开菜单时默认不保持（除非已在长按 H）
        if not getattr(self, '_toast_hist_cap_h_down', False):
            self._toast_hist_cap_keep_open = False
            self._last_toast_hist_cap_hold = False
        menu = self._build_liaison_toast_capacity_menu()
        focus = self._focus_toast_hist_cap_menu(menu)
        if getattr(self, '_toast_hist_cap_menu_no_exec', False):
            self._last_toast_hist_cap_menu = menu
            try:
                lab = focus.text() if focus is not None else ''
                self._flash_host_toast(
                    f'Alt+H · 容量菜单焦点 {lab}'.strip(), kind='info', ms=1200)
            except Exception:
                pass
            return menu
        try:
            hbar = getattr(self, '_liaison_toast_history_bar', None)
            if hbar is not None and hbar.isVisible():
                pos = hbar.mapToGlobal(QPoint(0, hbar.height()))
            else:
                pos = self.mapToGlobal(QPoint(max(8, self.width() // 2 - 40), 36))
            menu.exec(pos)
        except Exception:
            try:
                menu.exec()
            except Exception:
                pass
        try:
            self._flash_host_toast('Alt+H · 容量菜单', kind='info', ms=1000)
        except Exception:
            pass
        return menu

    def _apply_toast_hist_capacity(self, n: int):
        """wave35–40: 应用容量；数字触发后关菜单（长按H保持则不关）."""
        nn = self.set_liaison_toast_history_max(int(n))
        try:
            self._flash_host_toast(f'切窗史容量 → {nn}', kind='info')
            self._log_line(f'切窗史容量 → {nn}')
        except Exception:
            pass
        if bool(getattr(self, '_toast_hist_cap_keep_open', False)):
            return nn
        menu = getattr(self, '_last_toast_hist_cap_menu', None) or getattr(
            self, '_toast_hist_cap_nav_menu', None)
        if menu is not None and not getattr(self, '_toast_hist_cap_menu_no_exec', False):
            try:
                menu.close()
            except Exception:
                pass
            self._last_toast_hist_cap_closed_by = getattr(
                self, '_last_toast_hist_cap_closed_by', '') or 'apply'
        return nn

    def _on_liaison_toast_history_clicked(self, event=None):
        """wave31–35: 左键回切 · 右键容量菜单 · 中键循环."""
        try:
            if event is not None and hasattr(event, 'button'):
                if event.button() == Qt.MouseButton.RightButton:
                    menu = self._build_liaison_toast_capacity_menu()
                    self._focus_toast_hist_cap_menu(menu)
                    if getattr(self, '_toast_hist_cap_menu_no_exec', False):
                        self._last_toast_hist_cap_menu = menu
                        return menu
                    try:
                        hbar = self._liaison_toast_history_bar
                        pos = hbar.mapToGlobal(event.position().toPoint()) if hasattr(event, 'position') else hbar.mapToGlobal(event.pos())
                        menu.exec(pos)
                    except Exception:
                        try:
                            menu.exec()
                        except Exception:
                            pass
                    return
                if event.button() == Qt.MouseButton.MiddleButton:
                    n = self.cycle_liaison_toast_history_max()
                    try:
                        self._flash_host_toast(f'切窗史容量 → {n}', kind='info')
                        self._log_line(f'切窗史容量 → {n}')
                    except Exception:
                        pass
                    return
                if event.button() not in (Qt.MouseButton.LeftButton,):
                    return
        except Exception:
            pass
        hist = list(getattr(self, '_liaison_toast_history', None) or [])
        secs = list(getattr(self, '_liaison_toast_history_secs', None) or [])
        if not hist or not secs:
            return
        # pick segment by x ratio
        idx = len(hist) - 1
        try:
            hbar = self._liaison_toast_history_bar
            x = float(event.position().x()) if hasattr(event, 'position') else float(event.x())
            w = max(1.0, float(hbar.width()))
            # account for prefix "切窗史 · "
            prefix = '切窗史 · '
            # approximate: split evenly across hist entries
            idx = int(x / w * len(hist))
            idx = max(0, min(len(hist) - 1, idx))
        except Exception:
            idx = len(hist) - 1
        sec = int(secs[idx]) if idx < len(secs) else int(secs[-1])
        lab = hist[idx] if idx < len(hist) else hist[-1]
        self.set_liaison_window_sec(sec, persist=True)
        try:
            self._sync_liaison_window_badge()
        except Exception:
            pass
        try:
            self._log_line(f'切窗史回切 · {lab}')
            self.setStatusTip(f'切窗史回切 · {lab}')
        except Exception:
            pass
        # flash toast without pushing new history noise? still flash
        toast = getattr(self, '_liaison_hotkey_toast', None)
        if toast is not None:
            toast.setText(f'回切 · {lab}')
            toast.show()
            toast.raise_()

    def copy_alarm_film_path(self, item=None) -> bool:
        """wave29: 报警条目 filmPath → 剪贴板."""
        if item is None:
            lst = getattr(self, '_alarm_list', None)
            item = lst.currentItem() if lst is not None else None
        fp = self._film_path_from_alarm_item(item)
        if not fp:
            try:
                self._log_line('复制 path · 无胶片 path')
            except Exception:
                pass
            return False
        try:
            QApplication.clipboard().setText(fp)
            self._log_line(f'已复制胶片 path · {fp}')
        except Exception:
            return False
        return True

    def _film_path_from_alarm_item(self, item) -> str:
        if item is None:
            return ''
        fp = ''
        try:
            data = item.data(Qt.ItemDataRole.UserRole) or {}
            if isinstance(data, dict):
                fp = str(data.get('filmPath') or '').strip()
        except Exception:
            fp = ''
        if not fp:
            fp = str(getattr(self, '_jump_film_path', '') or '').strip()
        if not fp:
            fp = str(getattr(self, '_current_film_path', '') or '').strip()
        return fp

    def _locate_film_from_alarm_item(self, item, *, source: str = 'alarm'):
        fp = self._film_path_from_alarm_item(item)
        if not fp:
            try:
                self._log_line('报警定位胶片 · 无 path')
            except Exception:
                pass
            return False
        try:
            self.alarmFilmLocateRequested.emit({'path': fp, 'source': source})
            self._log_line(f'报警定位胶片 · {fp}')
        except Exception:
            return False
        return True

    def push_liaison_event(self, text: str, *, kind: str = '', code: str = ''):
        """wave22: append 联调条 event (试跑清除 / 换型失败 / 报警清除)."""
        now = datetime.now()
        entry = {
            'ts': now.strftime('%H:%M:%S'),
            'ts_full': now.strftime('%Y-%m-%d %H:%M:%S'),
            'epoch': now.timestamp(),
            'kind': str(kind or '联调'),
            'code': str(code or ''),
            'text': str(text or ''),
            'severity': self._liaison_severity(kind, code),
        }
        self._liaison_events.append(entry)
        if len(self._liaison_events) > self._liaison_events_max:
            self._liaison_events = self._liaison_events[-self._liaison_events_max:]
        try:
            if self._alarm_history and ('清除' in entry['kind'] or 'CLEAR' in entry['code']):
                self._alarm_history[-1]['liaison'] = True
        except Exception:
            pass
        self._refresh_liaison_strip()
        try:
            self._log_line(
                f"联调 · {entry['kind']}"
                + (f"[{entry['code']}]" if entry['code'] else '')
                + f" · {entry['text'][:80]}"
            )
        except Exception:
            pass
        try:
            self.liaisonPushed.emit(dict(entry))
        except Exception:
            pass

    def liaison_events(self):
        return list(self._liaison_events)

    def _refresh_liaison_strip(self):
        strip = getattr(self, '_liaison_strip', None)
        if strip is None:
            return
        if not self._liaison_events:
            strip.setText('联调 · 等待事件（试跑清除 / 换型失败 / 报警清除）')
            return
        bits = []
        for e in reversed(self._liaison_events[-4:]):
            bit = f"{e.get('ts', '')} {e.get('kind', '')}"
            if e.get('code'):
                bit += f"[{e['code']}]"
            txt = str(e.get('text') or '')
            if txt:
                bit += ' · ' + (txt[:48] + ('…' if len(txt) > 48 else ''))
            bits.append(bit)
        strip.setText('联调 · ' + '  ‖  '.join(bits))

    def clear_alarm_history(self):
        self._alarm_history.clear()
        self._liaison_events.clear()
        self._refresh_alarm_history_ui()
        self._refresh_liaison_strip()
        self._log_line('报警历史已清空')

    @staticmethod
    def _classify_alarm_severity(reason: str) -> str:
        r = (reason or '').lower()
        ru = (reason or '').upper()
        if any(k in r for k in ('fail', '失败', 'error', '错误', '急停', 'e-stop', 'estop')):
            return 'error'
        if any(k in ru for k in ('VARIANT_', 'APPLY_', 'ENTER_', 'TRIAL_FIRE', 'RECIPE_MISSING')):
            return 'error'
        if any(k in r for k in ('ng', '超时', 'timeout', 'warn', '警告', '换型')):
            return 'warning'
        if any(k in r for k in ('清除', 'clear', '试跑')):
            return 'info'
        return 'info'

    def note_film_path(self, path: str = ''):
        """wave27: 记住当前胶片 path，供运行报警自动写入 filmPath."""
        self._current_film_path = str(path or '').strip()

    def current_film_path(self) -> str:
        return str(getattr(self, '_current_film_path', '') or '')

    def _record_alarm(self, reason: str = '', *, film_path: str = ''):
        reason_s = str(reason or '报警')
        is_liaison = any(k in reason_s for k in ('试跑', '联调', '换型失败', 'VARIANT_', 'TRIAL_'))
        entry = {
            'ts': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'reason': reason_s,
            'cleared': False,
            'cleared_at': '',
            'severity': self._classify_alarm_severity(reason_s),
            'state_at': self._state,
            'liaison': bool(is_liaison),
        }
        fp = str(film_path or '').strip()
        if fp:
            entry['filmPath'] = fp
        self._alarm_history.append(entry)
        if len(self._alarm_history) > self._alarm_history_max:
            self._alarm_history = self._alarm_history[-self._alarm_history_max:]
        self._refresh_alarm_history_ui()

    def _refresh_alarm_history_ui(self):
        lst = getattr(self, '_alarm_list', None)
        if lst is None:
            return
        needle = ''
        filt = getattr(self, '_alarm_filter', None)
        if filt is not None:
            needle = (filt.text() or '').strip().lower()
        status = 'all'
        sf = getattr(self, '_alarm_status_filter', None)
        if sf is not None:
            status = sf.currentData() or 'all'
        lst.clear()
        shown = 0
        for e in reversed(self._alarm_history):
            reason = str(e.get('reason', '') or '')
            cleared = bool(e.get('cleared'))
            if status == 'open' and cleared:
                continue
            if status == 'cleared' and not cleared:
                continue
            if status == 'liaison' and not e.get('liaison'):
                continue
            sev_f = 'all'
            sfv = getattr(self, '_alarm_sev_filter', None)
            if sfv is not None:
                try:
                    sev_f = sfv.currentData() or 'all'
                except Exception:
                    sev_f = 'all'
            sev = e.get('severity') or 'info'
            if sev_f and sev_f != 'all':
                sev_norm = 'warning' if sev in ('warn', 'warning') else sev
                want = 'warning' if sev_f in ('warn', 'warning') else sev_f
                if sev_norm != want:
                    continue
            if needle and needle not in reason.lower() and needle not in str(e.get('ts') or '').lower():
                continue
            sev_zh = {'error': '错', 'warning': '警', 'info': '讯'}.get(sev, '讯')
            mark = '·' if not cleared else '✓'
            dur = ''
            if cleared and e.get('cleared_at') and e.get('ts'):
                try:
                    t0 = datetime.strptime(e['ts'], '%Y-%m-%d %H:%M:%S')
                    t1 = datetime.strptime(e['cleared_at'], '%Y-%m-%d %H:%M:%S')
                    secs = max(0, int((t1 - t0).total_seconds()))
                    dur = f' · {secs}s'
                except Exception:
                    dur = ''
            lia = ' ·联调' if e.get('liaison') else ''
            text = f"{e.get('ts', '')}  [{sev_zh}] {mark}  {reason}{dur}{lia}"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, dict(e))
            fp = str(e.get('filmPath') or '').strip()
            if fp:
                item.setToolTip(f'{reason}\n双击定位胶片 · {fp}')
            else:
                item.setToolTip(reason)
            lst.addItem(item)
            shown += 1
        lab = getattr(self, '_alarm_hist_count', None)
        if lab is not None:
            total = len(self._alarm_history)
            open_n = sum(1 for e in self._alarm_history if not e.get('cleared'))
            lab.setText(f'{shown}/{total} 条 · 未清 {open_n}' if (needle or status != 'all') else f'{total} 条 · 未清 {open_n}')
        spark = getattr(self, '_alarm_spark', None)
        if spark is not None:
            seq = self._alarm_history[-24:]
            if not seq:
                spark.setText('报警序列 · · ·')
                spark.setToolTip('最近报警：▇=未清除 ▁=已清除（左旧右新）；颜色=严重度')
            else:
                # wave25: 严重度染色（富文本）
                sev_color = {
                    'error': '#e35d6a',
                    'warning': '#e0b84a',
                    'warn': '#e0b84a',
                    'info': '#6eb6ff',
                    'ok': '#3ecf8e',
                }
                bits = []
                for e in seq:
                    cleared = bool(e.get('cleared'))
                    sev = str(e.get('severity') or 'info').lower()
                    # also map liaison events that may have been recorded with reason codes
                    if sev not in sev_color:
                        sev = 'info'
                    ch = '▁' if cleared else '▇'
                    if cleared:
                        color = '#5a6068'
                    else:
                        color = sev_color.get(sev, '#6eb6ff')
                    bits.append(f'<span style="color:{color}">{ch}</span>')
                open_n = sum(1 for e in self._alarm_history if not e.get('cleared'))
                err_n = sum(1 for e in self._alarm_history
                            if not e.get('cleared') and e.get('severity') == 'error')
                html = (
                    f'<span style="color:#9aa0a6">报警序列</span> '
                    + ''.join(bits)
                    + f'  ·  <span style="color:#9aa0a6">未清 {open_n}/{len(self._alarm_history)}'
                    + (f' · 错 {err_n}' if err_n else '')
                    + '</span>'
                )
                spark.setTextFormat(Qt.TextFormat.RichText)
                spark.setText(html)
                spark.setToolTip(
                    '最近报警：▇=未清除 ▁=已清除（左旧右新）；'
                    '红=error · 琥珀=warning · 蓝=info · 灰=已清除'
                )

        try:
            self._sync_alarm_sev_chips()
        except Exception:
            pass

    def set_production_snapshot(self, ok_n=None, ng_n=None, *, host_state: str | None = None):
        """Feed OK/NG/yield into alarm-tab production strip (VM run-mode feel)."""
        strip = getattr(self, '_prod_strip', None)
        if strip is None:
            return
        try:
            ok_i = int(ok_n) if ok_n is not None else None
            ng_i = int(ng_n) if ng_n is not None else None
        except (TypeError, ValueError):
            ok_i = ng_i = None
        st = host_state or self._state
        st_zh = STATE_ZH.get(st, st)
        if ok_i is None or ng_i is None:
            strip.setText(f'生产 · OK —  NG —  良率 —  ·  状态 {st_zh}')
            return
        total = ok_i + ng_i
        if total:
            y = 100.0 * ok_i / total
            ytxt = f'{y:.1f}%'
        else:
            ytxt = '—'
        strip.setText(f'生产 · OK {ok_i}  NG {ng_i}  良率 {ytxt}  ·  状态 {st_zh}')


    def _raise_alarm(self):
        """Simulate alarm + emit 状态·报警 so MainWindow / chrome stay in sync."""
        self.set_state('Alarm', '手动模拟')
        self.triggerCommands.emit([dict(type='状态·报警', config='手动模拟')])

    def _clear_alarm(self):
        """Visible clear UX → Idle + 状态·清除报警 (engine/chrome path)."""
        if self._state != 'Alarm':
            self._log_line('当前无报警，无需清除')
            return
        if self._alarm_history:
            self._alarm_history[-1]['cleared'] = True
            self._alarm_history[-1]['cleared_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            self._refresh_alarm_history_ui()
        self.set_state('Idle', '清除报警')
        self.triggerCommands.emit([dict(type='状态·清除报警', config='清除报警')])
        self._log_line('已清除报警 → 空闲')

    def _auto_start(self, mode: str):
        try:
            self.mode_combo.setCurrentText(mode)
        except Exception:
            pass
        self._mode = mode
        if self._state == 'Alarm':
            self._log_line('报警中，请先清除报警')
            return
        if self._state == 'Running':
            self._log_line('已在运行中')
            return
        if self._state == 'Paused':
            # Prefer resume rather than re-start
            self._auto_resume(mode)
            return
        self.set_state('Running', f'{mode} · 开始')
        # Continuous run for production feel; single also available via 运行控制
        self.triggerCommands.emit([dict(type='执行·连续', config=mode)])

    def _auto_pause(self, mode: str):
        if self._state != 'Running':
            return
        self.set_state('Paused', mode)
        # Soft pause continuous (MainWindow.pause_continuous) — not hard stop
        self.triggerCommands.emit([dict(type='执行·暂停', config=f'pause:{mode}')])

    def _auto_resume(self, mode: str):
        if self._state != 'Paused':
            return
        self.set_state('Running', f'{mode} · 继续')
        self.triggerCommands.emit([dict(type='执行·继续', config=mode)])

    def _auto_stop(self, mode: str):
        self.set_state('Stopped', mode)
        self.triggerCommands.emit([dict(type='执行·停止', config=mode)])
