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
        tip = QLabel('运行结果：transform（3×3）/ rms / usedPoints / unit。设计态保存对照表即可。')
        tip.setWordWrap(True)
        tip.setStyleSheet('color:#888;')
        form.addRow(tip)
        out_var = QLineEdit(str(self.params.get('resultVar') or 'calibTransform'))
        out_var.editingFinished.connect(lambda: self._set_param('resultVar', out_var.text().strip() or 'calibTransform'))
        from desktop.upstream_field_picker import fill_line_from_picker
        from PySide6.QtWidgets import QHBoxLayout, QPushButton
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
        tip2 = QLabel('至少填入一组非零像素/世界坐标，否则节点红叹号。无机械手 SDK。')
        tip2.setWordWrap(True)
        tip2.setStyleSheet('color:#888;')
        form.addRow(tip2)
        # 细妆⑯：live bind 实况（跟 last_result）
        self._live_lab = QLabel('实况：尚未运行')
        self._live_lab.setObjectName('ninePointLiveBind')
        self._live_lab.setWordWrap(True)
        self._live_lab.setStyleSheet('color:#9ad;font-size:11px;padding:4px;background:#1e2228;border-radius:4px;')
        form.addRow(self._live_lab)
        brow = QHBoxLayout()
        b_ref = QPushButton('刷新实况')
        b_ref.setObjectName('ninePointLiveRefreshBtn')
        b_ref.setToolTip('从最近一次运行结果读取 rms / usedPoints / transform')
        b_ref.clicked.connect(self._refresh_live_bind)
        brow.addWidget(b_ref)
        brow.addStretch(1)
        form.addRow(brow)
        try:
            self._refresh_live_bind()
        except Exception:
            pass
        return w

    def _refresh_live_bind(self):
        """细妆⑯：九点 last_result live bind."""
        lab = getattr(self, '_live_lab', None)
        if lab is None:
            return
        try:
            from desktop.upstream_field_picker import host_last_result
            lr = host_last_result(self) or {}
        except Exception:
            lr = {}
        sid = self.step.get('id')
        hit = None
        for rec in (lr.get('results') or []):
            if isinstance(rec, dict) and rec.get('id') == sid:
                hit = rec
                break
        if not hit:
            lab.setText('实况：尚无本模块运行结果（先 ▶ 单次运行）')
            return
        res = (hit.get('output') or {}).get('result') or {}
        rms = res.get('rms')
        used = res.get('usedPoints')
        ok = res.get('ok', res.get('status'))
        tf = res.get('transform')
        bits = []
        if rms is not None:
            bits.append(f'rms={rms}')
        if used is not None:
            bits.append(f'used={used}')
        if ok is not None:
            bits.append(f'ok={ok}')
        if isinstance(tf, (list, tuple)) and tf:
            bits.append(f'transform[{len(tf)}]')
        elif isinstance(tf, dict):
            bits.append('transform=dict')
        # also flow vars often mirrored
        flow = ((lr.get('variables') or {}).get('flow') or {})
        for k in ('nine_point_rms', 'nine_point_count', 'nine_point_ok'):
            if k in flow:
                bits.append(f'{k}={flow[k]}')
        lab.setText('实况：' + (' · '.join(bits) if bits else str(list(res.keys())[:8])))

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
        """P3 九点验证 UI 三步示意（无臂测）：采点 → 求解 → 验残差."""
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(10, 10, 10, 10)
        title = QLabel('九点标定验证 · 三步示意（无机械手 SDK）')
        title.setStyleSheet('font-weight:600;font-size:13px;')
        lay.addWidget(title)
        steps = [
            ('① 采点', '在「基本参数」填满至少 9 组 pixel↔world；可用「填充 3×3 示意」生成格子，再改世界坐标。'),
            ('② 求解', '▶ 单次运行九点模块：引擎拟合仿射/相似变换，写出 transform / rms / usedPoints。'),
            ('③ 验残差', '看「结果显示」与流程变量 nine_point_rms / _count / _ok；门限示例：点数≥9 且 rms<0.5 → passGate。'),
        ]
        for head, body in steps:
            box = QLabel(f'<b>{head}</b><br/>{body}')
            box.setWordWrap(True)
            box.setStyleSheet(
                'background:#f7f8fa;border:1px solid #dde1e6;border-radius:6px;'
                'padding:10px 12px;margin:4px 0;color:#333;'
            )
            lay.addWidget(box)
        foot = QLabel(
            '对照 VM p36 叙事；现场手臂测点不在本产品范围。打开即跑样例 '
            '<code>open-and-run-ninepoint.sieans</code> 已带 OK/NG。'
        )
        foot.setWordWrap(True)
        foot.setStyleSheet('color:#666;padding-top:8px;')
        lay.addWidget(foot)
        lay.addStretch(1)
        return w


    def _fill_grid(self):
        # 3x3 pixel grid demo at 100px spacing centered around 0
        pts = []
        i = 0
        for gy in range(3):
            for gx in range(3):
                row = _empty_row(i)
                row['pixelX'] = float(gx * 100)
                row['pixelY'] = float(gy * 100)
                row['worldX'] = float(gx * 10)  # mm demo
                row['worldY'] = float(gy * 10)
                pts.append(row)
                i += 1
        self.params['points'] = pts
        self._reload_table()
        self._emit()
