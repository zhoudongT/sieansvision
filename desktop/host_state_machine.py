"""上位机状态机 HMI — VisionMaster p41–43 可点击壳（无机械手 SDK）。

手动控制：IP/端口/连接(示意)/回原点 · 运动 X/Y/Z/角/速 · 吸嘴
自动运行：正常生产 / 九点标定 / 旋转标定 · 开始/暂停/继续/停止
状态：Idle / Running / Paused / Alarm / Stopped — 开始/停止接到流程触发。
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta

from PySide6.QtCore import Qt, Signal, QTimer, QSettings
from PySide6.QtGui import QAction, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QTabWidget, QFormLayout, QLineEdit, QGroupBox, QPlainTextEdit,
    QGridLayout, QSizePolicy, QComboBox, QDoubleSpinBox, QSpinBox, QListWidget, QListWidgetItem, QFileDialog, QApplication,
    QMenu,
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
            b.setMaximumWidth(40)
            b.setToolTip(f'严重度筛 · {lab}')
            b.clicked.connect(lambda *_a, k=key: self.set_alarm_severity_filter(k))
            chip_row.addWidget(b)
            self._alarm_sev_chips[key] = b
        chip_row.addStretch(1)
        chip_hint = QLabel('芯片')
        chip_hint.setStyleSheet(f'color:{TEXT_MUTED};font-size:10px;')
        chip_row.addWidget(chip_hint)
        lay.addLayout(chip_row)
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
        try:
            self._liaison_cycle_shortcut = QShortcut(QKeySequence('Alt+L'), self)
            self._liaison_cycle_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            self._liaison_cycle_shortcut.activated.connect(self.cycle_liaison_window)
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

    def cycle_liaison_window(self) -> int:
        """wave27/28: 循环全部→5分→15分→1时→24时→全部（徽章/Alt+L）；返回新 sec."""
        combo = getattr(self, '_liaison_window', None)
        if combo is None or combo.count() <= 0:
            return self.liaison_window_sec()
        nxt = (combo.currentIndex() + 1) % combo.count()
        combo.setCurrentIndex(nxt)
        sec = self.liaison_window_sec()
        try:
            self._log_line(f'联调徽章切窗 · {combo.currentText()}')
        except Exception:
            pass
        return sec

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

    def set_alarm_severity_filter(self, key: str = 'all', *, persist: bool = True) -> bool:
        """wave26/27: 设严重度筛（spark / 外部）；可持久."""
        combo = getattr(self, '_alarm_sev_filter', None)
        if combo is None:
            return False
        key = str(key or 'all').strip().lower()
        if key in ('warn',):
            key = 'warning'
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

    def _sync_alarm_sev_chips(self):
        """wave28: 严重度筛芯片条高亮当前."""
        chips = getattr(self, '_alarm_sev_chips', None) or {}
        if not chips:
            return
        cur = self.alarm_severity_filter()
        styles = {
            'all': ('#2a3340', '#9aa0a6', '#3a3d42'),
            'error': ('#3a1c1c', '#e35d6a', '#e35d6a'),
            'warning': ('#3a3420', '#e0b84a', '#e0b84a'),
            'info': ('#1c2a3a', '#6eb6ff', '#6eb6ff'),
        }
        for key, b in chips.items():
            on = (key == cur)
            bg, fg, bd = styles.get(key, styles['all'])
            if on:
                b.setChecked(True)
                b.setStyleSheet(
                    f'background:{bg};color:{fg};border:1px solid {bd};'
                    f'border-radius:3px;font-size:10px;font-weight:700;padding:1px 4px;'
                )
            else:
                b.setChecked(False)
                b.setStyleSheet(
                    'background:#2a2c30;color:#6a7078;border:1px solid #3a3d42;'
                    'border-radius:3px;font-size:10px;padding:1px 4px;'
                )

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
        self._last_alarm_ctx_item = item
        return menu

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
