"""Run-mode operator HMI — live widgets from project.runUi (VisionMaster-style)."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QPlainTextEdit, QGridLayout, QSizePolicy, QLineEdit, QListWidget,
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
        self._gate_key = None  # None → auto probe flow vars
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
        self._list.clear()
        self.clear_alarm()
        self._refresh_labels()

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
        self._list.insertItem(0, line)
        while self._list.count() > 40:
            self._list.takeItem(self._list.count() - 1)
        self._refresh_labels()

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
        self._status_lamps = []  # StatusLamp needing runtime OK/NG
        self._run_status_labels = []
        self._log_panes = []
        self._clock_labels = []
        self._stats_panels = []
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
        b = QPushButton('运行界面设计')
        b.clicked.connect(self.designRequested.emit)
        header.addWidget(b)
        b = QPushButton('返回设计态')
        b.setObjectName('primaryButton')
        b.clicked.connect(self.backToDesign.emit)
        header.addWidget(b)
        root.addLayout(header)

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
        for label, cmds, primary in (
            ('▶ 单次', DEFAULT_RUN_COMMANDS, True),
            ('↻ 连续', DEFAULT_CONT_COMMANDS, False),
            ('■ 停止', DEFAULT_STOP_COMMANDS, False),
            ('注入 RUN', DEFAULT_INJECT_RUN_COMMANDS, False),
            ('注入 STOP', DEFAULT_INJECT_STOP_COMMANDS, False),
        ):
            btn = QPushButton(label)
            if primary:
                btn.setObjectName('primaryButton')
            btn.clicked.connect(lambda _=False, c=cmds: self.triggerCommands.emit(deepcopy(c)))
            strip.addWidget(btn)
        strip.addStretch(1)
        root.addWidget(self._default_strip)

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
                host.sync_from_runtime(result)
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
        host = getattr(self, '_host_sm', None)
        if host is not None:
            try:
                host.append_info(str(message))
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
        re-emit pauseToggled so MainWindow can bridge ContinuousRun / 运行全部."""
        try:
            panel.gateKeyChanged.connect(self._on_stats_gate_key)
        except Exception:
            pass
        try:
            panel.pauseToggled.connect(self.pauseToggled.emit)
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

    def _apply_fixed_bars(self, fb: dict):
        self._fixed_bars_cache = dict(fb or {})
        cam = fb.get('cameraBind') or CAMERA_BIND_OPTIONS[0]
        comm = fb.get('commBind') or COMM_BIND_OPTIONS[0]
        gate = (fb.get('gateKey') or '').strip()
        tip = f'相机:{cam} · 通讯:{comm}' + (f' · 判定门:flow.{gate}' if gate else '')
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
        host.triggerCommands.connect(self.triggerCommands.emit)
        self._host_sm = host
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
            lab = QLabel('OFF')
            lab.setStyleSheet(f'color:{TEXT_MUTED};font-size:12px;')

            def _on_toggle(on, c=commands, l=lab):
                l.setText('ON' if on else 'OFF')
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
            edit = QLineEdit()
            edit.setPlaceholderText(binding or CONTROL_STUB_HINTS.get(name, name))
            if name == '文本框':
                edit.setReadOnly(True)
                edit.setText(binding or '—')
            cell.layout().addWidget(edit)
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
            host.triggerCommands.connect(self.triggerCommands.emit)
            self._host_sm = host
            return host

        # p41 host-chrome stubs (no robot SDK)
        if name in ('IP地址', '端口'):
            cell = self._make_cell_frame(name)
            edit = QLineEdit(str(state.get('value') or ('192.168.1.109' if name == 'IP地址' else '5001')))
            edit.setPlaceholderText(name)
            cell.layout().addWidget(edit)
            cell.layout().addStretch(1)
            return cell
        if name == '连接状态':
            cell = self._make_cell_frame('连接状态')
            lab = QLabel(str(state.get('value') or '未连接'))
            lab.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lab.setStyleSheet(f'color:{TEXT_MUTED};padding:8px;font-weight:600;')
            cell.layout().addWidget(lab, 1)
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

        # Fallback stub for charts / layout containers etc.
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
