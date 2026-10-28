"""九点标定（nine_point）属性浮窗 — VisionMaster p=20 壳.

像素点 ↔ 机械点对照表；运行时若 ≥3 点则估简易仿射，否则仅回显表。
"""
from copy import deepcopy

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTabWidget, QFormLayout,
    QLineEdit, QComboBox, QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QScrollArea, QFrame, QDoubleSpinBox,
)


def _empty_row(i=0):
    return dict(index=i + 1, pixelX=0.0, pixelY=0.0, worldX=0.0, worldY=0.0, enabled=True)


def normalize_nine_point_params(params=None):
    p = deepcopy(params or {})
    p.setdefault('coordSystem', '机械坐标系')
    p.setdefault('unit', 'mm')
    points = p.get('points')
    if not isinstance(points, list) or len(points) < 1:
        points = [_empty_row(i) for i in range(9)]
    # pad / trim soft to at least 9 for VM look
    while len(points) < 9:
        points.append(_empty_row(len(points)))
    for i, row in enumerate(points):
        if not isinstance(row, dict):
            points[i] = _empty_row(i)
            continue
        row.setdefault('index', i + 1)
        for k in ('pixelX', 'pixelY', 'worldX', 'worldY'):
            try:
                row[k] = float(row.get(k) or 0)
            except (TypeError, ValueError):
                row[k] = 0.0
        row['enabled'] = bool(row.get('enabled', True))
    p['points'] = points
    p.setdefault('method', 'affine')  # affine | perspective
    p.setdefault('resultVar', 'calibTransform')
    p.setdefault('showPoints', True)
    p.setdefault('showOverlay', True)
    p.setdefault('showIndex', True)
    p.setdefault('showResiduals', True)
    p.setdefault('judgeEnable', True)
    p.setdefault('rmsGate', 0.5)
    p.setdefault('judgeMinPoints', 9)
    p.setdefault('rms', None)
    return p


class NinePointPanel(QWidget):
    """两 Tab：基本参数（九点表） / 结果显示."""
    changed = Signal(dict)

    def __init__(self, step, definition, project, parent=None):
        super().__init__(parent)
        self.step = deepcopy(step)
        self.definition = definition or {}
        self.project = project or {}
        self.params = normalize_nine_point_params(step.get('params'))
        self.step['params'] = self.params
        self._syncing = False

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        hint = QLabel(
            '对齐 VisionMaster（含 p54 九点平移行业复述，复用本算子）「平移九点标定」：填写像素点与世界坐标对照表；'
            '运行时对启用点估仿射（≥3 点），输出 transform / rms。'
        )
        hint.setWordWrap(True)
        hint.setStyleSheet('color:#666;padding:8px 10px 4px;')
        root.addWidget(hint)

        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)
        self.tabs.addTab(self._wrap(self._basic_tab()), '基本参数')
        self.tabs.addTab(self._wrap(self._result_tab()), '结果显示')
        self.tabs.addTab(self._wrap(self._verify_tab()), '验证示意')

    def _wrap(self, inner):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(inner)
        return scroll

    def _emit(self):
        self.step['params'] = deepcopy(self.params)
        self.changed.emit(deepcopy(self.step))

    def _set_param(self, key, value):
        if self.params.get(key) != value:
            self.params[key] = deepcopy(value)
            self._emit()

    def _set_top(self, key, value):
        if self.step.get(key) != value:
            self.step[key] = deepcopy(value)
            self._emit()

    def _basic_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(10, 10, 10, 10)
        form = QFormLayout()
        name = QLineEdit(self.step.get('name') or '九点标定')
        name.setMaxLength(80)
        name.editingFinished.connect(lambda: self._set_top('name', name.text()))
        form.addRow('模块名称', name)

        image_from = QComboBox()
        image_from.addItem('（无图像输入）', None)
        incoming = {e['from'] for e in self.project.get('edges', []) if e.get('to') == self.step.get('id')}
        index_map = {'source': 0}
        names = {'source': '图像源1'}
        for i, s in enumerate(self.project.get('steps', []), start=1):
            index_map[s['id']] = i
            names[s['id']] = s.get('name', s['id'])
        def _sub(n):
            return f"{index_map.get(n, '?')} {names.get(n, n)}.图像"
        for node in sorted(incoming, key=lambda n: (index_map.get(n, 999), n)):
            image_from.addItem(_sub(node), node)
        cur = self.step.get('imageFrom')
        if cur and image_from.findData(cur) < 0:
            image_from.addItem('已断开：' + _sub(cur), cur)
        image_from.setCurrentIndex(max(0, image_from.findData(cur)))
        image_from.currentIndexChanged.connect(lambda _: self._set_top('imageFrom', image_from.currentData()))
        form.addRow('输入源', image_from)

        cs = QLineEdit(str(self.params.get('coordSystem') or '机械坐标系'))
        cs.editingFinished.connect(lambda: self._set_param('coordSystem', cs.text().strip()))
        form.addRow('坐标系', cs)
        unit = QComboBox()
        for u in ('mm', 'cm', 'm', 'px'):
            unit.addItem(u, u)
        unit.setCurrentIndex(max(0, unit.findData(self.params.get('unit') or 'mm')))
        unit.currentIndexChanged.connect(lambda _: self._set_param('unit', unit.currentData()))
        form.addRow('单位', unit)
        method = QComboBox()
        method.addItem('仿射 (≥3 点)', 'affine')
        method.addItem('透视 (≥4 点)', 'perspective')
        method.setCurrentIndex(max(0, method.findData(self.params.get('method') or 'affine')))
        method.currentIndexChanged.connect(lambda _: self._set_param('method', method.currentData()))
        form.addRow('求解方法', method)

        from desktop.upstream_field_picker import make_upstream_ref_row
        uref_row, self._upstream_ref = make_upstream_ref_row(
            self, self.project, self.step.get('id'), self.params, self._set_param,
        )
        form.addRow('上游参考', uref_row)
        lay.addLayout(form)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(['序号', '像素X', '像素Y', '世界X', '世界Y', '启用'])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.itemChanged.connect(self._on_item)
        lay.addWidget(self.table, 1)

        bar = QHBoxLayout()
        add = QPushButton('添加点')
        add.clicked.connect(self._add_row)
        rem = QPushButton('删除选中')
        rem.clicked.connect(self._remove_rows)
        reset = QPushButton('重置 9 点')
        reset.clicked.connect(self._reset9)
        fill = QPushButton('填充 3×3 示意')
        fill.setToolTip('按像素间距生成示意点（世界坐标需现场改）')
        fill.clicked.connect(self._fill_grid)
        bar.addWidget(add)
        bar.addWidget(rem)
        bar.addWidget(reset)
        bar.addWidget(fill)
        bar.addStretch(1)
        lay.addLayout(bar)
        self._reload_table()
        return w

    def _result_tab(self):
        w = QWidget()
        form = QFormLayout(w)
        form.setContentsMargins(10, 10, 10, 10)
        tip = QLabel('工业结果显示：九N✓ 徽标 / RMS 门限 / 残差表 / 3×3 变换。无机械手 SDK。')
        tip.setWordWrap(True)
        tip.setStyleSheet('color:#888;')
        form.addRow(tip)
        out_var = QLineEdit(str(self.params.get('resultVar') or 'calibTransform'))
        out_var.setObjectName('ninePointResultVar')
        out_var.editingFinished.connect(lambda: self._set_param('resultVar', out_var.text().strip() or 'calibTransform'))
        from desktop.upstream_field_picker import fill_line_from_picker
        ovrow = QHBoxLayout()
        ovpick = QPushButton('插入上游字段')
        ovpick.setToolTip('也可挑选上游字段写入参考；结果变量名仍可手填')
        ovpick.clicked.connect(
            lambda *_: fill_line_from_picker(
                self, self.project, self.step.get('id'), out_var, self._set_param, 'resultVar')
        )
        ovrow.addWidget(out_var, 1)
        ovrow.addWidget(ovpick)
        form.addRow('结果变量', ovrow)

        gate = QDoubleSpinBox()
        gate.setObjectName('ninePointRmsGate')
        gate.setDecimals(4)
        gate.setRange(0.0, 100.0)
        gate.setSingleStep(0.05)
        gate.setValue(float(self.params.get('rmsGate') or 0.5))
        gate.valueChanged.connect(lambda v: self._set_param('rmsGate', float(v)))
        form.addRow('RMS 门限', gate)

        self._chrome_lab = QLabel('九·')
        self._chrome_lab.setObjectName('ninePointChromeBadge')
        self._chrome_lab.setStyleSheet(
            'color:#0d0;font-size:14px;font-weight:600;padding:4px 8px;'
            'background:#1a2220;border-radius:4px;'
        )
        form.addRow('结果徽标', self._chrome_lab)

        self._live_lab = QLabel('实况：尚未运行')
        self._live_lab.setObjectName('ninePointLiveBind')
        self._live_lab.setWordWrap(True)
        self._live_lab.setStyleSheet('color:#9ad;font-size:11px;padding:4px;background:#1e2228;border-radius:4px;')
        form.addRow(self._live_lab)

        self._density_table = QTableWidget(0, 2)
        self._density_table.setObjectName('ninePointDensityTable')
        self._density_table.setHorizontalHeaderLabels(['字段', '值'])
        self._density_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self._density_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._density_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._density_table.setMaximumHeight(140)
        form.addRow('密度摘要', self._density_table)

        from desktop.nine_point_var_gate_chrome import RESIDUAL_COLUMNS, TRANSFORM_COLUMNS
        self._residual_table = QTableWidget(0, len(RESIDUAL_COLUMNS))
        self._residual_table.setObjectName('ninePointResidualTable')
        self._residual_table.setHorizontalHeaderLabels(list(RESIDUAL_COLUMNS))
        self._residual_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._residual_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._residual_table.setMinimumHeight(160)
        form.addRow('残差工业表', self._residual_table)

        self._transform_table = QTableWidget(0, len(TRANSFORM_COLUMNS))
        self._transform_table.setObjectName('ninePointTransformTable')
        self._transform_table.setHorizontalHeaderLabels(list(TRANSFORM_COLUMNS))
        self._transform_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._transform_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._transform_table.setMaximumHeight(110)
        form.addRow('变换矩阵', self._transform_table)

        brow = QHBoxLayout()
        b_ref = QPushButton('刷新实况')
        b_ref.setObjectName('ninePointLiveRefreshBtn')
        b_ref.setToolTip('从最近一次运行结果读取 rms / usedPoints / transform')
        b_ref.clicked.connect(self._refresh_live_bind)
        b_demo = QPushButton('软演示密度')
        b_demo.setObjectName('ninePointSoftDemoBtn')
        b_demo.setToolTip('不经流程：注入九点软演示残差/门限铬')
        b_demo.clicked.connect(self._soft_demo_nine_density)
        brow.addWidget(b_ref)
        brow.addWidget(b_demo)
        brow.addStretch(1)
        form.addRow(brow)
        try:
            self._refresh_live_bind()
        except Exception:
            pass
        return w

    def set_last_result(self, result):
        """Ingest host last_result for denser nine-point chrome."""
        self._host_last_result = result if isinstance(result, dict) else None
        try:
            self._refresh_live_bind()
        except Exception:
            pass

    def _soft_demo_nine_density(self):
        from desktop.nine_point_var_gate_chrome import (
            soft_demo_nine_point_result, summarize_nine_point,
        )
        demo = soft_demo_nine_point_result(ok=True, n=9)
        # merge demo points into params for overlay/residual lookup without overwrite persist
        params = dict(self.params)
        params.setdefault('points', demo.get('points'))
        params.setdefault('rmsGate', 0.5)
        self._apply_nine_density(summarize_nine_point(demo, params=params), source='soft-demo')

    def _apply_nine_density(self, summ, *, source: str = ''):
        chrome = summ.get('chrome') or '九·'
        lab = getattr(self, '_chrome_lab', None)
        if lab is not None:
            lab.setText(str(chrome))
            jok = summ.get('judgeOk')
            color = '#00d250' if jok is True else ('#ff5252' if jok is False else '#ffb400')
            lab.setStyleSheet(
                f'color:{color};font-size:14px;font-weight:600;padding:4px 8px;'
                'background:#1a2220;border-radius:4px;'
            )
        live = getattr(self, '_live_lab', None)
        if live is not None:
            src = f' [{source}]' if source else ''
            live.setText(f"实况：[{chrome}] {summ.get('summary')}{src}")
        dt = getattr(self, '_density_table', None)
        if dt is not None:
            from desktop.nine_point_var_gate_chrome import density_summary_rows_nine
            rows = density_summary_rows_nine(summ)
            dt.setRowCount(len(rows))
            for i, r in enumerate(rows):
                dt.setItem(i, 0, QTableWidgetItem(str(r.get('key') or '')))
                dt.setItem(i, 1, QTableWidgetItem(str(r.get('value') if r.get('value') is not None else '—')))
        rt = getattr(self, '_residual_table', None)
        if rt is not None:
            from desktop.nine_point_var_gate_chrome import format_residual_cells, RESIDUAL_COLUMNS
            rows = summ.get('rows') or []
            rt.setColumnCount(len(RESIDUAL_COLUMNS))
            rt.setHorizontalHeaderLabels(list(RESIDUAL_COLUMNS))
            rt.setRowCount(len(rows))
            for i, row in enumerate(rows):
                for c, cell in enumerate(format_residual_cells(row)):
                    item = QTableWidgetItem(cell)
                    if c == len(RESIDUAL_COLUMNS) - 1:
                        st = str(row.get('judgeStatus') or '')
                        if st == 'OK':
                            item.setForeground(__import__('PySide6.QtGui', fromlist=['QColor']).QColor('#00d250'))
                        elif st == 'NG':
                            item.setForeground(__import__('PySide6.QtGui', fromlist=['QColor']).QColor('#ff5252'))
                    rt.setItem(i, c, item)
        tt = getattr(self, '_transform_table', None)
        if tt is not None:
            from desktop.nine_point_var_gate_chrome import TRANSFORM_COLUMNS
            trows = summ.get('transformRows') or []
            tt.setColumnCount(len(TRANSFORM_COLUMNS))
            tt.setHorizontalHeaderLabels(list(TRANSFORM_COLUMNS))
            tt.setRowCount(len(trows))
            for i, row in enumerate(trows):
                tt.setItem(i, 0, QTableWidgetItem(str(row.get('row'))))
                tt.setItem(i, 1, QTableWidgetItem(str(row.get('c0'))))
                tt.setItem(i, 2, QTableWidgetItem(str(row.get('c1'))))
                tt.setItem(i, 3, QTableWidgetItem(str(row.get('c2'))))

    def _refresh_live_bind(self):
        """Denser nine-point last_result live bind + industrial tables."""
        lab = getattr(self, '_live_lab', None)
        if lab is None:
            return
        try:
            from desktop.upstream_field_picker import host_last_result
            lr = getattr(self, '_host_last_result', None) or host_last_result(self) or {}
        except Exception:
            lr = getattr(self, '_host_last_result', None) or {}
        sid = self.step.get('id')
        hit = None
        for rec in (lr.get('results') or []):
            if isinstance(rec, dict) and rec.get('id') == sid:
                hit = rec
                break
        if not hit:
            lab.setText('实况：尚无本模块运行结果（先 ▶ 单次运行或点软演示密度）')
            return
        res = (hit.get('output') or {}).get('result') or {}
        try:
            from desktop.nine_point_var_gate_chrome import summarize_nine_point
            self._apply_nine_density(summarize_nine_point(res, params=self.params), source='engine')
        except Exception as exc:
            lab.setText(f'实况：解析失败 {exc}')

    def _reload_table(self):
        self._syncing = True
        pts = self.params.get('points') or []
        self.table.setRowCount(len(pts))
        for r, row in enumerate(pts):
            vals = [
                str(row.get('index', r + 1)),
                f"{float(row.get('pixelX') or 0):.4f}",
                f"{float(row.get('pixelY') or 0):.4f}",
                f"{float(row.get('worldX') or 0):.4f}",
                f"{float(row.get('worldY') or 0):.4f}",
                '是' if row.get('enabled', True) else '否',
            ]
            for c, text in enumerate(vals):
                item = QTableWidgetItem(text)
                if c == 0:
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(r, c, item)
        self._syncing = False

    def _on_item(self, item):
        if self._syncing:
            return
        r, c = item.row(), item.column()
        pts = self.params.setdefault('points', [])
        while len(pts) <= r:
            pts.append(_empty_row(len(pts)))
        row = pts[r]
        text = (item.text() or '').strip()
        if c == 5:
            row['enabled'] = text not in ('否', '0', 'false', 'False', 'N', 'n')
        elif c in (1, 2, 3, 4):
            key = ('pixelX', 'pixelY', 'worldX', 'worldY')[c - 1]
            try:
                row[key] = float(text)
            except ValueError:
                row[key] = 0.0
        self._emit()
        try:
            self._refresh_verify_checklist()
        except Exception:
            pass

    def _add_row(self):
        pts = self.params.setdefault('points', [])
        pts.append(_empty_row(len(pts)))
        self._reload_table()
        self._emit()

    def _remove_rows(self):
        rows = sorted({i.row() for i in self.table.selectedIndexes()}, reverse=True)
        pts = self.params.setdefault('points', [])
        for r in rows:
            if 0 <= r < len(pts):
                pts.pop(r)
        for i, row in enumerate(pts):
            row['index'] = i + 1
        self._reload_table()
        self._emit()

    def _reset9(self):
        self.params['points'] = [_empty_row(i) for i in range(9)]
        self._reload_table()
        self._emit()

    def _verify_tab(self):
        """P3 九点验证 UI：采点 → 示意求解 → 验残差（无机械手 SDK）。"""
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(10, 10, 10, 10)
        title = QLabel('九点标定验证 · 三步（无机械手 SDK）')
        title.setStyleSheet('font-weight:600;font-size:13px;')
        lay.addWidget(title)

        self._verify_checklist = QLabel('')
        self._verify_checklist.setObjectName('ninePointVerifyChecklist')
        self._verify_checklist.setWordWrap(True)
        self._verify_checklist.setStyleSheet(
            'background:#1e2228;color:#9ad;border-radius:6px;padding:10px 12px;font-size:12px;'
        )
        lay.addWidget(self._verify_checklist)

        steps = [
            ('① 采点', '在「基本参数」填满至少 3（建议 9）组非零 pixel↔world；可用「填充 3×3 示意」。'),
            ('② 求解', '点下方「示意求解」本地估仿射（或 ▶ 单次运行写入 transform / rms）。'),
            ('③ 验残差', '看 rms / residuals；门限示例：点数≥9 且 rms<0.5 → passGate。'),
        ]
        for head, body in steps:
            box = QLabel(f'<b>{head}</b><br/>{body}')
            box.setWordWrap(True)
            box.setStyleSheet(
                'background:#f7f8fa;border:1px solid #dde1e6;border-radius:6px;'
                'padding:10px 12px;margin:4px 0;color:#333;'
            )
            lay.addWidget(box)

        brow = QHBoxLayout()
        b_solve = QPushButton('示意求解（本地仿射）')
        b_solve.setObjectName('ninePointDemoSolveBtn')
        b_solve.setToolTip('不经流程运行：对当前表估 2D 仿射并显示 rms / 残差（无臂 SDK）')
        b_solve.clicked.connect(self._demo_solve)
        b_ref = QPushButton('刷新清单')
        b_ref.setObjectName('ninePointVerifyRefreshBtn')
        b_ref.clicked.connect(self._refresh_verify_checklist)
        brow.addWidget(b_solve)
        brow.addWidget(b_ref)
        brow.addStretch(1)
        lay.addLayout(brow)

        self._verify_result = QLabel('尚未示意求解')
        self._verify_result.setObjectName('ninePointVerifyResult')
        self._verify_result.setWordWrap(True)
        self._verify_result.setStyleSheet(
            'background:#f0f4f8;border:1px solid #c8d0da;border-radius:6px;'
            'padding:10px 12px;color:#234;font-family:monospace;font-size:11px;'
        )
        lay.addWidget(self._verify_result)

        foot = QLabel(
            '对照 VM p36 叙事；现场手臂测点不在本产品范围。样例 '
            '<code>open-and-run-ninepoint.sieans</code> 已带 OK/NG。'
        )
        foot.setWordWrap(True)
        foot.setStyleSheet('color:#666;padding-top:8px;')
        lay.addWidget(foot)
        lay.addStretch(1)
        try:
            self._refresh_verify_checklist()
        except Exception:
            pass
        return w

    def _used_points(self):
        pts = self.params.get('points') or []
        used = []
        for r in pts:
            if not isinstance(r, dict) or r.get('enabled') is False:
                continue
            vals = [abs(float(r.get(k) or 0)) for k in ('pixelX', 'pixelY', 'worldX', 'worldY')]
            if sum(vals) > 0:
                used.append(r)
        return used

    def _refresh_verify_checklist(self):
        lab = getattr(self, '_verify_checklist', None)
        if lab is None:
            return
        used = self._used_points()
        n = len(used)
        step1 = '✅' if n >= 3 else ('⚠️' if n >= 1 else '⬜')
        step2 = '✅' if self.params.get('rms') is not None else '⬜'
        rms = self.params.get('rms')
        step3 = '✅' if (rms is not None and float(rms) < 0.5 and n >= 9) else (
            '⚠️' if rms is not None else '⬜'
        )
        lab.setText(
            ('\n').join([
                f'{step1} 采点：启用非零对照 {n}/9（≥3 可解，≥9 推荐）',
                f'{step2} 求解：{"rms="+str(rms) if rms is not None else "尚未求解（点「示意求解」或 ▶ 运行）"}',
                f'{step3} 验残差：{"passGate 示意达标" if step3 == "✅" else ("有 rms，按现场门限判" if rms is not None else "待求解")}',
            ])
        )

    def _demo_solve(self):
        """本地 2D 仿射示意求解（与 flow-control ninePoint 同构；无臂 SDK）。"""
        used = self._used_points()
        res_lab = getattr(self, '_verify_result', None)
        if len(used) < 3:
            if res_lab is not None:
                res_lab.setText(f'需要 ≥3 个非零对照点（当前 {len(used)}）')
            self._refresh_verify_checklist()
            return
        try:
            import numpy as np
            src = np.array([[float(r['pixelX']), float(r['pixelY'])] for r in used], dtype=float)
            dst = np.array([[float(r['worldX']), float(r['worldY'])] for r in used], dtype=float)
            # Least-squares affine: [X Y] = [x y 1] @ [[a,c],[b,d],[tx,ty]]
            A = np.column_stack([src, np.ones(len(src))])
            # Solve separately for X and Y
            sol_x, _, _, _ = np.linalg.lstsq(A, dst[:, 0], rcond=None)
            sol_y, _, _, _ = np.linalg.lstsq(A, dst[:, 1], rcond=None)
            a, b, tx = sol_x
            c, d, ty = sol_y
            mapped = np.column_stack([
                a * src[:, 0] + b * src[:, 1] + tx,
                c * src[:, 0] + d * src[:, 1] + ty,
            ])
            errs = np.linalg.norm(mapped - dst, axis=1)
            rms = float(np.sqrt(np.mean(errs ** 2)))
            transform = [float(a), float(b), float(tx), float(c), float(d), float(ty), 0.0, 0.0, 1.0]
            self.params['rms'] = rms
            self.params['lastDemoTransform'] = transform
            self.params['lastDemoUsed'] = len(used)
            self._emit()
            lines = [
                f'status=ok · used={len(used)} · rms={rms:.6f}',
                f'transform=[{", ".join(f"{v:.4g}" for v in transform[:6])} …]',
            ]
            for i, (r, e) in enumerate(zip(used[:9], errs[:9])):
                lines.append(
                    f'  #{r.get("index", i+1)} err={e:.4f}  '
                    f'px=({r["pixelX"]:.1f},{r["pixelY"]:.1f})→'
                    f'({mapped[i,0]:.2f},{mapped[i,1]:.2f}) '
                    f'world=({r["worldX"]:.2f},{r["worldY"]:.2f})'
                )
            if res_lab is not None:
                res_lab.setText('\n'.join(lines))
        except Exception as exc:
            if res_lab is not None:
                res_lab.setText(f'示意求解失败：{exc}')
        self._refresh_verify_checklist()


    def _fill_grid(self):
        # 3x3 pixel grid demo at 100px spacing centered around 0
        pts = []
        i = 0
        for gy in range(3):
            for gx in range(3):
                row = _empty_row(i)
                # offset so (0,0) cell is non-zero (used_points filters all-zero)
                row['pixelX'] = float(100 + gx * 100)
                row['pixelY'] = float(100 + gy * 100)
                row['worldX'] = float(10 + gx * 10)  # mm demo
                row['worldY'] = float(10 + gy * 10)
                pts.append(row)
                i += 1
        self.params['points'] = pts
        self._reload_table()
        self._emit()
        try:
            self._refresh_verify_checklist()
        except Exception:
            pass
