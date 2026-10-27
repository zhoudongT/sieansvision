"""组合模块 Group — 嵌套 Tab / 进组 + 四参数 Tab（含循环设置）壳。"""
from copy import deepcopy

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTabWidget,
    QTableWidget, QTableWidgetItem, QHeaderView, QFormLayout, QLineEdit,
    QComboBox, QMessageBox, QFrame, QInputDialog, QAbstractItemView,
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
            edit.textChanged.connect(lambda *_: self._sync_enter_enabled())
        root.addLayout(bind_row)

        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)
        self.tabs.addTab(self._io_tab('inputs'), '输入设置')
        self.tabs.addTab(self._io_tab('outputs'), '输出设置')
        self.tabs.addTab(self._display_tab(), '显示设置')
        self.tabs.addTab(self._loop_tab(), '循环设置')

        self.enter_btn = QPushButton('进入组合模块')
        self.enter_btn.setObjectName('primaryButton')
        self.enter_btn.setToolTip('嵌套画布 Tab；未绑定 ImageData/InputROI 时不可进入（按钮灰显）')
        self.enter_btn.clicked.connect(lambda *_: self._try_enter())
        root.addWidget(self.enter_btn)

        tip = QLabel('组内可再放模块与连线；出组后对外暴露组级 I/O。循环使能与主流程单次/连续分层。')
        tip.setWordWrap(True)
        tip.setObjectName('dialogHint')
        root.addWidget(tip)
        self._sync_enter_enabled()

    def _pick_binding(self, key):
        """Prefer shared upstream_field_picker; fall back to BindSourceDialog."""
        from PySide6.QtWidgets import QInputDialog
        choice = ''
        try:
            from desktop.upstream_field_picker import pick_upstream_field, host_last_result
            picked = pick_upstream_field(
                self, self.project, step_id=self.step.get('id'),
                last_result=host_last_result(self),
            )
            if picked:
                choice = picked[2]
            else:
                from desktop.bind_dialog import BindSourceDialog
                current = self.image_data.text() if key == 'imageData' else self.input_roi.text()
                dlg = BindSourceDialog(self.project, current=current, group_step=self.step, parent=self)
                if not dlg.exec():
                    return
                choice = dlg.selected or ''
        except Exception:
            try:
                from desktop.bind_dialog import BindSourceDialog
                current = self.image_data.text() if key == 'imageData' else self.input_roi.text()
                dlg = BindSourceDialog(self.project, current=current, group_step=self.step, parent=self)
                if not dlg.exec():
                    return
                choice = dlg.selected or ''
            except Exception:
                options = ['', '0 图像源1.图像', '0 图像源1.ImageData', '0 图像源1.ROI']
                for i, s in enumerate(self.project.get('steps') or [], start=1):
                    name = s.get('name') or s.get('operation') or s['id']
                    options.extend([f'{i} {name}.图像', f'{i} {name}.ROI', f'{i} {name}.Output'])
                choice, ok = QInputDialog.getItem(self, '订阅绑定', f'选择 {key} 订阅源', options, 0, True)
                if not ok:
                    return
        if key == 'imageData':
            self.image_data.setText(choice or '0 图像源1.图像')
        else:
            self.input_roi.setText(choice or '0 图像源1.ROI')
        self._emit()

    def _io_tab(self, kind):
        w = QWidget()
        v = QVBoxLayout(w)
        table = QTableWidget(0, 4)
        table.setHorizontalHeaderLabels(['参数名称', '类型', '订阅关系', '操作'])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setAlternatingRowColors(True)
        io = (self.params.get('io') or {}).get(kind) or []
        defaults = [
            ('ImageData', 'IMAGE', self.params.get('imageData') or ''),
            ('InputROI', 'ROI', self.params.get('inputRoi') or ''),
            ('Result', 'JSON', ''),
        ] if kind == 'inputs' else [
            ('ImageData', 'IMAGE', '组内输出'),
            ('Output', 'ANY', ''),
            ('Status', 'BOOL', ''),
        ]
        rows = io if io else [{'name': a, 'type': b, 'binding': c} for a, b, c in defaults]
        for row in rows:
            if isinstance(row, dict):
                vals = [row.get('name', ''), row.get('type', ''), row.get('binding', '')]
            else:
                vals = list(row)[:3]
            self._io_append_row(table, kind, vals)
        table.itemChanged.connect(lambda *_: self._emit())
        v.addWidget(table, 1)
        bar = QHBoxLayout()
        add = QPushButton('添加行')
        add.clicked.connect(lambda *_ , t=table, k=kind: self._io_add_row(t, k))
        bar.addWidget(add)
        bar.addStretch(1)
        v.addLayout(bar)
        note = QLabel('I/O 可编辑并随方案保存；⛓ 订阅源、↑ 上游字段、复 复制行；也可手填 results./flow. 路径。')
        note.setWordWrap(True)
        note.setObjectName('dialogHint')
        v.addWidget(note)
        setattr(self, f'_{kind}_table', table)
        return w

    def _io_append_row(self, table, kind, vals=None):
        vals = list(vals or ['', 'ANY', ''])
        while len(vals) < 3:
            vals.append('')
        r = table.rowCount()
        table.blockSignals(True)
        table.insertRow(r)
        for c, val in enumerate(vals[:3]):
            table.setItem(r, c, QTableWidgetItem(str(val)))
        ops = QWidget()
        ol = QHBoxLayout(ops)
        ol.setContentsMargins(2, 0, 2, 0)
        chain = QPushButton('⛓')
        chain.setFixedWidth(28)
        chain.setToolTip('挑选订阅源')
        rm = QPushButton('删')
        rm.setFixedWidth(28)
        ol.addWidget(chain)
        ol.addWidget(rm)
        table.setCellWidget(r, 3, ops)
        table.blockSignals(False)
        self._io_rebind_ops(table, kind)

    def _io_rebind_ops(self, table, kind):
        """Rebuild ⛓/插入/删 widgets so row indices stay correct after add/delete/reorder."""
        for r in range(table.rowCount()):
            ops = QWidget()
            ol = QHBoxLayout(ops)
            ol.setContentsMargins(2, 0, 2, 0)
            ol.setSpacing(2)
            chain = QPushButton('⛓')
            chain.setFixedWidth(28)
            chain.setToolTip('挑选订阅源（Bind 对话框 / 上游字段）')
            ins = QPushButton('↑')
            ins.setFixedWidth(28)
            ins.setToolTip('插入上游字段 token（results.<模块>.字段）')
            dup = QPushButton('复')
            dup.setFixedWidth(28)
            dup.setToolTip('复制本行')
            rm = QPushButton('删')
            rm.setFixedWidth(28)
            chain.clicked.connect(lambda *_, t=table, rr=r, k=kind: self._io_bind_row(t, rr, k))
            ins.clicked.connect(lambda *_, t=table, rr=r, k=kind: self._io_insert_upstream(t, rr, k))
            dup.clicked.connect(lambda *_, t=table, rr=r, k=kind: self._io_dup_row(t, rr, k))
            rm.clicked.connect(lambda *_, t=table, rr=r, k=kind: self._io_remove_row(t, rr, k))
            ol.addWidget(chain)
            ol.addWidget(ins)
            ol.addWidget(dup)
            ol.addWidget(rm)
            table.setCellWidget(r, 3, ops)

    def _io_add_row(self, table, kind):
        self._io_append_row(table, kind, ['NewParam', 'ANY', ''])
        self._emit()

    def _io_remove_row(self, table, row, kind=None):
        if 0 <= row < table.rowCount():
            table.removeRow(row)
            if kind is None:
                kind = 'inputs' if table is getattr(self, '_inputs_table', None) else 'outputs'
            self._io_rebind_ops(table, kind)
            self._emit()

    def _io_bind_row(self, table, row, kind):
        if row < 0 or row >= table.rowCount():
            return
        current_item = table.item(row, 2)
        current = current_item.text() if current_item else ''
        choice = ''
        try:
            from desktop.upstream_field_picker import pick_upstream_field, host_last_result
            picked = pick_upstream_field(
                self, self.project, step_id=self.step.get('id'),
                last_result=host_last_result(self),
            )
            if picked:
                choice = picked[2]
            else:
                from desktop.bind_dialog import BindSourceDialog
                dlg = BindSourceDialog(self.project, current=current, group_step=self.step, parent=self)
                if not dlg.exec():
                    return
                choice = dlg.selected or ''
        except Exception:
            try:
                from desktop.bind_dialog import BindSourceDialog
                dlg = BindSourceDialog(self.project, current=current, group_step=self.step, parent=self)
                if not dlg.exec():
                    return
                choice = dlg.selected or ''
            except Exception:
                options = ['', '0 图像源1.图像', '0 图像源1.ROI', 'flow.passGate', 'flow.circleCount']
                for i, s in enumerate(self.project.get('steps') or [], start=1):
                    name = s.get('name') or s.get('operation') or s['id']
                    options.extend([f'{i} {name}.图像', f'{i} {name}.ROI', f'{i} {name}.Output'])
                choice, ok = QInputDialog.getItem(self, '订阅绑定', '选择订阅源', options, 0, True)
                if not ok:
                    return
        table.blockSignals(True)
        table.setItem(row, 2, QTableWidgetItem(choice))
        table.blockSignals(False)
        name_item = table.item(row, 0)
        name = (name_item.text() if name_item else '').strip()
        if kind == 'inputs' and name == 'ImageData':
            self.image_data.setText(choice)
        elif kind == 'inputs' and name == 'InputROI':
            self.input_roi.setText(choice)
        self._emit()


    def _io_insert_upstream(self, table, row, kind):
        """Direct upstream_field_picker into binding cell (density shortcut)."""
        if row < 0 or row >= table.rowCount():
            return
        try:
            from desktop.upstream_field_picker import pick_upstream_field, host_last_result
            picked = pick_upstream_field(
                self, self.project, step_id=self.step.get('id'),
                last_result=host_last_result(self),
            )
        except Exception as exc:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, '插入上游字段', f'挑选失败：{exc}')
            return
        if not picked:
            return
        choice = picked[2]
        table.blockSignals(True)
        table.setItem(row, 2, QTableWidgetItem(choice))
        table.blockSignals(False)
        name_item = table.item(row, 0)
        name = (name_item.text() if name_item else '').strip()
        if kind == 'inputs' and name == 'ImageData':
            self.image_data.setText(choice)
        elif kind == 'inputs' and name == 'InputROI':
            self.input_roi.setText(choice)
        self._emit()

    def _io_dup_row(self, table, row, kind):
        if row < 0 or row >= table.rowCount():
            return
        vals = []
        for c in range(3):
            it = table.item(row, c)
            vals.append(it.text() if it else '')
        if vals[0]:
            vals[0] = vals[0] + '_copy'
        self._io_append_row(table, kind, vals)
        self._emit()


    def _read_io_table(self, kind):
        table = getattr(self, f'_{kind}_table', None)
        if table is None:
            return list((self.params.get('io') or {}).get(kind) or [])
        out = []
        for r in range(table.rowCount()):
            def cell(c):
                it = table.item(r, c)
                return it.text().strip() if it else ''
            name, typ, binding = cell(0), cell(1), cell(2)
            if not name and not binding:
                continue
            out.append(dict(name=name or f'param{r+1}', type=typ or 'ANY', binding=binding))
        return out

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
        io = dict(self.params.get('io') or {})
        io['inputs'] = self._read_io_table('inputs')
        io['outputs'] = self._read_io_table('outputs')
        io.setdefault('display', {})
        # Line edits are authoritative: push ImageData/InputROI into named IO rows
        # (↑ insert writes both cell + line edit; clearing a line edit must clear the row).
        for row in io['inputs']:
            if row.get('name') == 'ImageData':
                row['binding'] = self.params.get('imageData') or ''
            elif row.get('name') == 'InputROI':
                row['binding'] = self.params.get('inputRoi') or ''
        # Mirror into table cells so IO tab matches top binds
        for kind, key, name in (
            ('inputs', 'imageData', 'ImageData'),
            ('inputs', 'inputRoi', 'InputROI'),
        ):
            table = getattr(self, f'_{kind}_table', None)
            if table is None:
                continue
            val = self.params.get(key) or ''
            for r in range(table.rowCount()):
                it = table.item(r, 0)
                if it and it.text().strip() == name:
                    table.blockSignals(True)
                    table.setItem(r, 2, QTableWidgetItem(val))
                    table.blockSignals(False)
                    break
        self.params['io'] = io
        step = deepcopy(self.step)
        step['params'] = deepcopy(self.params)
        self.changed.emit(step)
        self._sync_enter_enabled()

    def _sync_enter_enabled(self):
        # Grey out enter until ImageData + InputROI both bound.
        if not hasattr(self, 'enter_btn') or self.enter_btn is None:
            return
        img = (self.image_data.text() if hasattr(self, 'image_data') else '') or ''
        roi = (self.input_roi.text() if hasattr(self, 'input_roi') else '') or ''
        ready = bool(img.strip()) and bool(roi.strip())
        if not ready:
            ready = group_bindings_ready(self.params)
        self.enter_btn.setEnabled(bool(ready))

    def _try_enter(self):
        self._emit()
        if not group_bindings_ready(self.params):
            self._sync_enter_enabled()
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
            f'QFrame#groupBreadcrumb{{background:{CARD};border:1px solid {LINE};border-radius:2px;}}'
        )

    def set_path(self, flow_name, group_name=None, *, parts=None):
        """Breadcrumb: 主流程 › G1 › G2 …（嵌套编辑）.

        Accepts legacy (flow_name, group_name) or parts=['主流程','G1','G2'].
        """
        if parts:
            segs = [str(p).strip() for p in parts if str(p).strip()]
        else:
            segs = [str(flow_name or '主流程').strip()]
            if group_name:
                segs.append(str(group_name).strip())
        if len(segs) <= 1:
            text = (segs[0] if segs else '主流程') + '（嵌套编辑）'
        else:
            text = '  ›  '.join(segs) + '（嵌套编辑）'
        self.label.setText(text)
        self.setToolTip(' / '.join(segs))
