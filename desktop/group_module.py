"""组合模块 Group — 嵌套 Tab / 进组 + 四参数 Tab（含循环设置）壳。"""
from copy import deepcopy

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTabWidget,
    QTableWidget, QTableWidgetItem, QHeaderView, QFormLayout, QLineEdit,
    QComboBox, QMessageBox, QFrame,
)

from desktop.theme import CARD, LINE, TEXT, ACCENT
from desktop.widgets.switch import OrangeSwitch


def default_group_inner():
    return dict(steps=[], edges=[], sourcePosition=dict(x=300, y=40), localVariables={})


def normalize_group_params(params=None):
    p = deepcopy(params or {})
    p.setdefault('imageData', '')      # binding label ImageData
    p.setdefault('inputRoi', '')       # binding label InputROI
    p.setdefault('loopEnabled', False)
    p.setdefault('loopCount', 1)
    p.setdefault('loopIntervalMs', 0)
    p.setdefault('inner', default_group_inner())
    inner = p['inner']
    inner.setdefault('steps', [])
    inner.setdefault('edges', [])
    inner.setdefault('sourcePosition', dict(x=300, y=40))
    inner.setdefault('localVariables', {})
    p.setdefault('io', dict(inputs=[], outputs=[], display={}))
    return p


def group_bindings_ready(params):
    p = normalize_group_params(params)
    return bool(str(p.get('imageData') or '').strip()) and bool(str(p.get('inputRoi') or '').strip())


class GroupParamPanel(QWidget):
    """四 Tab：输入设置 / 输出设置 / 显示设置 / 循环设置 + 进入组合模块。"""
    changed = Signal(dict)
    enterGroup = Signal()
    bindRequested = Signal(str)  # field key

    def __init__(self, step, project, parent=None):
        super().__init__(parent)
        self.step = deepcopy(step)
        self.project = project
        self.params = normalize_group_params(step.get('params'))
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)

        warn = QLabel('进组前必须绑定 ImageData / InputROI（与订阅体系一致）。')
        warn.setObjectName('dialogHint')
        warn.setWordWrap(True)
        root.addWidget(warn)

        bind_row = QHBoxLayout()
        self.image_data = QLineEdit(str(self.params.get('imageData') or ''))
        self.image_data.setPlaceholderText('ImageData ← 如 0 图像源1.图像')
        self.input_roi = QLineEdit(str(self.params.get('inputRoi') or ''))
        self.input_roi.setPlaceholderText('InputROI ← 如 1 快速匹配1.ROI')
        for edit, key, label in (
            (self.image_data, 'imageData', 'ImageData'),
            (self.input_roi, 'inputRoi', 'InputROI'),
        ):
            box = QVBoxLayout()
            lab = QLabel(label)
            lab.setStyleSheet('font-weight:600;color:#1a3550;')
            box.addWidget(lab)
            row = QHBoxLayout()
            row.addWidget(edit, 1)
            chain = QPushButton('⛓')
            chain.setFixedWidth(32)
            chain.setToolTip('订阅 / 绑定')
            chain.clicked.connect(lambda *_ , k=key: self._pick_binding(k))
            row.addWidget(chain)
            box.addLayout(row)
            bind_row.addLayout(box, 1)
            edit.editingFinished.connect(self._emit)
        root.addLayout(bind_row)

        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)
        self.tabs.addTab(self._io_tab('inputs'), '输入设置')
        self.tabs.addTab(self._io_tab('outputs'), '输出设置')
        self.tabs.addTab(self._display_tab(), '显示设置')
        self.tabs.addTab(self._loop_tab(), '循环设置')

        enter = QPushButton('进入组合模块')
        enter.setObjectName('primaryButton')
        enter.setToolTip('嵌套画布 Tab；未绑定 ImageData/InputROI 时不可进入')
        enter.clicked.connect(self._try_enter)
        root.addWidget(enter)

        tip = QLabel('组内可再放模块与连线；出组后对外暴露组级 I/O。循环使能与主流程单次/连续分层。')
        tip.setWordWrap(True)
        tip.setObjectName('dialogHint')
        root.addWidget(tip)

    def _pick_binding(self, key):
        # Build simple upstream options: source + steps as VM labels
        options = ['']
        options.append('0 图像源1.图像')
        options.append('0 图像源1.ImageData')
        for i, s in enumerate(self.project.get('steps') or [], start=1):
            name = s.get('name') or s.get('operation') or s['id']
            options.append(f'{i} {name}.图像')
            options.append(f'{i} {name}.ROI')
            options.append(f'{i} {name}.Output')
        # Prefer combo dialog via QComboBox popup
        from PySide6.QtWidgets import QInputDialog
        choice, ok = QInputDialog.getItem(self, '订阅绑定', f'选择 {key} 订阅源', options, 0, True)
        if ok:
            if key == 'imageData':
                self.image_data.setText(choice)
            else:
                self.input_roi.setText(choice)
            self._emit()

    def _io_tab(self, kind):
        w = QWidget()
        v = QVBoxLayout(w)
        table = QTableWidget(3, 3)
        table.setHorizontalHeaderLabels(['参数名称', '类型', '订阅关系'])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        io = (self.params.get('io') or {}).get(kind) or []
        defaults = [
            ('ImageData', 'IMAGE', self.params.get('imageData') or '—'),
            ('InputROI', 'ROI', self.params.get('inputRoi') or '—'),
            ('Result', 'JSON', '—'),
        ] if kind == 'inputs' else [
            ('ImageData', 'IMAGE', '组内输出'),
            ('Output', 'ANY', '—'),
            ('Status', 'BOOL', '—'),
        ]
        rows = io if io else [{'name': a, 'type': b, 'binding': c} for a, b, c in defaults]
        for r, row in enumerate(rows[:3]):
            if isinstance(row, dict):
                vals = [row.get('name', ''), row.get('type', ''), row.get('binding', '')]
            else:
                vals = list(row)
            for c, val in enumerate(vals):
                table.setItem(r, c, QTableWidgetItem(str(val)))
        v.addWidget(table)
        note = QLabel('I/O 表为壳层；完整订阅接线与引擎侧 Group 展开见后续。')
        note.setWordWrap(True)
        v.addWidget(note)
        setattr(self, f'_{kind}_table', table)
        return w

    def _display_tab(self):
        w = QWidget()
        form = QFormLayout(w)
        form.addRow(QLabel('显示组内图像'), QLabel('开'))
        form.addRow(QLabel('说明'), QLabel('显示设置占位（对标 VM Group 显示设置）'))
        return w

    def _loop_tab(self):
        w = QWidget()
        form = QFormLayout(w)
        self.loop_sw = OrangeSwitch(bool(self.params.get('loopEnabled')))
        self.loop_sw.toggled.connect(lambda *_: self._emit())
        form.addRow(QLabel('循环使能'), self.loop_sw)
        self.loop_count = QLineEdit(str(self.params.get('loopCount') or 1))
        self.loop_count.editingFinished.connect(self._emit)
        form.addRow(QLabel('循环次数'), self.loop_count)
        self.loop_interval = QLineEdit(str(self.params.get('loopIntervalMs') or 0))
        self.loop_interval.editingFinished.connect(self._emit)
        form.addRow(QLabel('循环间隔(ms)'), self.loop_interval)
        tip = QLabel('与主流程「单次/连续」分层：组可按循环策略重复内部链路。')
        tip.setWordWrap(True)
        form.addRow(tip)
        return w

    def _emit(self):
        self.params['imageData'] = self.image_data.text().strip()
        self.params['inputRoi'] = self.input_roi.text().strip()
        self.params['loopEnabled'] = bool(self.loop_sw.isChecked())
        try:
            self.params['loopCount'] = max(1, int(self.loop_count.text() or 1))
        except ValueError:
            self.params['loopCount'] = 1
        try:
            self.params['loopIntervalMs'] = max(0, int(self.loop_interval.text() or 0))
        except ValueError:
            self.params['loopIntervalMs'] = 0
        step = deepcopy(self.step)
        step['params'] = deepcopy(self.params)
        self.changed.emit(step)

    def _try_enter(self):
        self._emit()
        if not group_bindings_ready(self.params):
            QMessageBox.warning(self, '组合模块', '进组前必须绑定 ImageData 与 InputROI。')
            return
        self.enterGroup.emit()


class GroupBreadcrumb(QFrame):
    """嵌套进组时的顶栏：流程 › 组合模块 · 返回"""
    exitGroup = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('groupBreadcrumb')
        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 4, 8, 4)
        self.label = QLabel('组合模块')
        self.label.setStyleSheet(f'color:{TEXT};font-weight:600;font-size:12px;')
        lay.addWidget(self.label, 1)
        back = QPushButton('返回上层')
        back.setObjectName('primaryButton')
        back.clicked.connect(self.exitGroup.emit)
        lay.addWidget(back)
        self.setStyleSheet(
            f'QFrame#groupBreadcrumb{background:{CARD};border:1px solid {LINE};border-radius:2px;}'
        )

    def set_path(self, flow_name, group_name):
        self.label.setText(f'{flow_name}  ›  组合模块 · {group_name}（嵌套编辑）')
