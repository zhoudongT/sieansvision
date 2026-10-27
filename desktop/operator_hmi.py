"""Run-mode operator HMI — live widgets from project.runUi (VisionMaster-style)."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QPlainTextEdit, QGridLayout, QSizePolicy, QLineEdit, QListWidget,
    QTableWidget, QTableWidgetItem, QProgressBar, QHeaderView,
    QComboBox, QTabWidget, QStackedWidget,
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
    """Simple round-ish status lamp (OK/NG / 信号灯)."""

    def __init__(self, caption='状态', parent=None):
        super().__init__(parent)
        self._caption = caption or '状态'
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumHeight(48)
        self.set_state(None)

    def set_state(self, ok):
        if ok is True:
            color, text = '#1c3a2a', f'{self._caption}\nOK'
            border = '#3ecf8e'
        elif ok is False:
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
        self._gate_btn = QPushButton('判定门')
        self._gate_btn.setToolTip('选择 flow 变量作为 OK/NG 判定门（默认自动探测 passGate/commOk/…）')
        self._gate_btn.clicked.connect(self._pick_gate_key)
        btn_row.addWidget(self._gate_btn)
        btn_row.addStretch(1)
        root.addLayout(btn_row)
        self._gate_lab = QLabel('判定门：自动')
        self._gate_lab.setStyleSheet(f'color:{TEXT_MUTED};font-size:11px;')
        root.addWidget(self._gate_lab)

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



class OperatorHmiView(QWidget):
    """Operator surface shown in 运行模式; driven by document.project['runUi']."""

    triggerCommands = Signal(object)  # list[dict]
    designRequested = Signal()
    backToDesign = Signal()
    runUiChanged = Signal(object)  # dict patch, e.g. {'fixedBars': {...}}
    pauseToggled = Signal(bool)  # bridge 生产统计 暂停计数 ↔ ContinuousRun / 运行全部

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

        # Always-available default run strip (also used when layout has no 运行控制)
        self._default_strip = QWidget()
        strip = QHBoxLayout(self._default_strip)
        strip.setContentsMargins(0, 0, 0, 0)
        self._strip_btns = {}
        for key, label, cmds, primary in (
            ('once', '▶ 单次', DEFAULT_RUN_COMMANDS, True),
            ('cont', '↻ 连续', DEFAULT_CONT_COMMANDS, False),
            ('pause', '⏸ 暂停', DEFAULT_PAUSE_COMMANDS, False),
            ('resume', '▶ 继续', DEFAULT_RESUME_COMMANDS, False),
            ('stop', '■ 停止', DEFAULT_STOP_COMMANDS, False),
            ('clear', '清除报警', DEFAULT_CLEAR_ALARM_COMMANDS, False),
            ('inj_run', '注入 RUN', DEFAULT_INJECT_RUN_COMMANDS, False),
            ('inj_stop', '注入 STOP', DEFAULT_INJECT_STOP_COMMANDS, False),
        ):
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
        self._yield_bars = []
        self._result_tables = []
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
                        ok = False; detail = 'passGate=0'; break
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
        rows = [
            ('模块', '流程', '—'),
            ('耗时(ms)', str(last_ms), '—'),
            ('OK计数', str(ok_n), '—'),
            ('NG计数', str(ng_n), '—'),
        ]
        for table in getattr(self, '_result_tables', []) or []:
            try:
                for r, row in enumerate(rows):
                    for c, val in enumerate(row):
                        item = table.item(r, c)
                        if item is None:
                            from PySide6.QtWidgets import QTableWidgetItem
                            item = QTableWidgetItem(val)
                            table.setItem(r, c, item)
                        else:
                            item.setText(str(val))
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


    def update_fixed_bar_live(self, *, run_status=None, okng=None, counters=None, camera=None, comm=None):
        """Refresh fixed-bar chrome with live run/OKNG/counters (细妆 · 固定栏实况)."""
        if run_status is not None:
            self._live_run_status = str(run_status)
        if okng is not None:
            self._live_okng = str(okng)
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
        self._fixed_bars_cache = dict(fb or {})
        cam = fb.get('cameraBind') or CAMERA_BIND_OPTIONS[0]
        comm = fb.get('commBind') or COMM_BIND_OPTIONS[0]
        gate = (fb.get('gateKey') or '').strip()
        tip = f'相机:{cam} · 通讯:{comm}' + (f' · 判定门:flow.{gate}' if gate else '')
        extras = []
        if fb.get('showRunStatus', True):
            extras.append(f'状态:{getattr(self, "_live_run_status", "空闲")}')
        if fb.get('showOkNg', True):
            extras.append(f'判定:{getattr(self, "_live_okng", "—")}')
        if fb.get('showCounters'):
            extras.append(f'计数:{getattr(self, "_live_counters", "0/0")}')
        if extras:
            tip = tip + ' · ' + ' · '.join(extras)
        for panel in getattr(self, '_stats_panels', []) or []:
            try:
                if gate and not panel.gate_key():
                    panel.set_gate_key(gate, notify=False)
            except Exception:
                pass
        if fb.get('top'):
            self._fix_top.setText(f'顶部固定栏 · {tip}')
            self._fix_top.show()
        else:
            self._fix_top.hide()
        if fb.get('bottom'):
            self._fix_bottom.setText(f'底部固定栏 · {tip}')
            self._fix_bottom.show()
        else:
            self._fix_bottom.hide()
        if fb.get('left'):
            self._fix_left.setText('左\n固\n定\n栏')
            self._fix_left.setToolTip(tip)
            self._fix_left.show()
        else:
            self._fix_left.hide()
        if fb.get('right'):
            self._fix_right.setText('右\n固\n定\n栏')
            self._fix_right.setToolTip(tip)
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
            table = QTableWidget(4, 3)
            table.setHorizontalHeaderLabels(['项', '值', '判定'])
            table.horizontalHeader().setStretchLastSection(True)
            table.verticalHeader().setVisible(False)
            table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            demos = [('模块', '—', '—'), ('耗时(ms)', '—', '—'), ('OK计数', '—', '—'), ('NG计数', '—', '—')]
            for r, row in enumerate(demos):
                for c, val in enumerate(row):
                    table.setItem(r, c, QTableWidgetItem(val))
            table.setObjectName('hmiResultTable')
            self._result_tables = getattr(self, '_result_tables', [])
            self._result_tables.append(table)
            cell.layout().addWidget(table, 1)
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
            tip = QLabel('趋势：周期耗时 spark + OK/NG 序列（跟生产统计 elapsed；每次 RUN 完成刷新）')
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
            cell.layout().addWidget(tip)
            cell.layout().addWidget(spark, 1)
            cell.layout().addWidget(ok_spark)
            self._trend_sparks = getattr(self, '_trend_sparks', [])
            self._trend_ok_sparks = getattr(self, '_trend_ok_sparks', [])
            self._trend_sparks.append(spark)
            self._trend_ok_sparks.append(ok_spark)
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
