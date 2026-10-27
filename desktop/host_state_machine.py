"""上位机状态机 HMI — VisionMaster p41–43 可点击壳（无机械手 SDK）。

手动控制：IP/端口/连接(示意)/回原点 · 运动 X/Y/Z/角/速 · 吸嘴
自动运行：正常生产 / 九点标定 / 旋转标定 · 开始/暂停/继续/停止
状态：Idle / Running / Paused / Alarm / Stopped — 开始/停止接到流程触发。
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QTabWidget, QFormLayout, QLineEdit, QGroupBox, QPlainTextEdit,
    QGridLayout, QSizePolicy, QComboBox, QDoubleSpinBox, QSpinBox,
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


class HostStateMachineWidget(QWidget):
    """Clickable host HMI chrome (p42/p43). Emits triggerCommands like OperatorHmiView."""

    triggerCommands = Signal(object)  # list[dict]
    stateChanged = Signal(str)
    infoLogged = Signal(str)

    def __init__(self, parent=None, compact=False):
        super().__init__(parent)
        self.setObjectName('hostStateMachine')
        self._state = 'Idle'
        self._connected = False
        self._mode = '正常生产'
        self._compact = compact

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

        self.tabs = QTabWidget()
        self.tabs.setObjectName('hostHmiTabs')
        root.addWidget(self.tabs, 1)

        self.tabs.addTab(self._build_manual(), '手动控制')
        self.tabs.addTab(self._build_auto(), '自动运行')

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
        if state != prev:
            self.stateChanged.emit(state)
            msg = f'状态 {STATE_ZH.get(prev, prev)} → {STATE_ZH[state]}'
            if reason:
                msg += f' · {reason}'
            self._log_line(msg)

    def sync_from_runtime(self, result: dict | None):
        """Map engine job state → host state (without fighting Pause/Alarm)."""
        result = result or {}
        st = result.get('state')
        if self._state == 'Paused' and st not in ('completed', 'failed', 'cancelled'):
            return
        if self._state == 'Alarm' and st not in ('completed',):
            if st == 'failed':
                return
        if st == 'completed':
            self.set_state('Idle', '流程完成')
        elif st == 'failed':
            self.set_state('Alarm', str(result.get('error') or '流程失败'))
        elif st == 'cancelled':
            self.set_state('Stopped', '用户停止')
        elif st in ('running', 'pending'):
            if self._state not in ('Running', 'Paused'):
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
        b_alarm.clicked.connect(lambda: self.set_state('Alarm', '手动模拟'))
        b_clear = QPushButton('清除报警→空闲')
        b_clear.clicked.connect(lambda: self.set_state('Idle', '清除报警'))
        alarm_row.addWidget(b_alarm)
        alarm_row.addWidget(b_clear)
        alarm_row.addStretch(1)
        lay.addLayout(alarm_row)

        tip = QLabel(
            '「开始」→ 执行·连续；「停止」→ 执行·停止。'
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
        for mode, btns in self._mode_buttons.items():
            btns['start'].setEnabled(st in ('Idle', 'Stopped'))
            btns['pause'].setEnabled(st == 'Running')
            btns['resume'].setEnabled(st == 'Paused')
            btns['stop'].setEnabled(st in ('Running', 'Paused', 'Alarm'))

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

    def _auto_start(self, mode: str):
        self.mode_combo.setCurrentText(mode)
        self._mode = mode
        if self._state == 'Alarm':
            self._log_line('报警中，请先清除报警')
            return
        self.set_state('Running', f'{mode} · 开始')
        # Continuous run for production feel; single also available via 运行控制
        self.triggerCommands.emit([dict(type='执行·连续', config=mode)])

    def _auto_pause(self, mode: str):
        if self._state != 'Running':
            return
        self.set_state('Paused', mode)
        # Soft pause: stop continuous without clearing
        self.triggerCommands.emit([dict(type='执行·停止', config=f'pause:{mode}')])

    def _auto_resume(self, mode: str):
        if self._state != 'Paused':
            return
        self.set_state('Running', f'{mode} · 继续')
        self.triggerCommands.emit([dict(type='执行·连续', config=mode)])

    def _auto_stop(self, mode: str):
        self.set_state('Stopped', mode)
        self.triggerCommands.emit([dict(type='执行·停止', config=mode)])
