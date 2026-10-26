"""Qt grid HMI designer and live native preview using the existing HMI schema."""
import base64
from copy import deepcopy
import datetime
import json
import math
import re
import uuid

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (QComboBox, QDialog, QFormLayout, QGraphicsItem,
    QGraphicsRectItem, QGraphicsScene, QGraphicsView, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QPushButton, QScrollArea, QSpinBox, QSplitter, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget)

from desktop.variables_dialog import (DataTree, FORBIDDEN, MISSING, NAME,
    TypedValueDialog, type_matches, value_kind, value_summary)
from desktop.cloud_view import CloudView

TYPES = {'text': '文本标题', 'value': '数值显示', 'lamp': '状态指示灯', 'image': '图像窗口',
         'cloud': '3D 点云', 'table': '数据表格', 'button': '操作按钮', 'input': '变量输入',
         'alarm': '报警列表', 'trend': '趋势曲线'}
SOURCES = {'flow': '流程变量', 'global': '全局变量', 'module': '模块变量', 'result': '模块结果',
           'source': '输入图像', 'status': '运行状态'}
COL_WIDTH = 80


def empty_page(title='运行监控'):
    return dict(version=1, title=title, rows=10, rowHeight=60, components=[])


def pages(layout):
    return layout['pages'] if layout.get('version') == 2 else [layout]


def page_id(page, layout):
    return page['id'] if layout.get('version') == 2 else 'main'


def new_component(kind, project):
    wide = kind in ('image', 'cloud', 'table', 'alarm', 'trend')
    c = dict(id='hmi-' + uuid.uuid4().hex[:16], type=kind, label=TYPES[kind], x=0, y=0,
             w=6 if wide or kind == 'text' else 3, h=4 if wide else 2, color='#1095bd', fontSize=24)
    if kind in ('value', 'lamp', 'table', 'input', 'alarm', 'trend'):
        c['binding'] = dict(source='flow', path='setpoint' if kind == 'input' else 'passed' if kind == 'lamp' else 'count')
    last = project.get('steps', [])[-1]['id'] if project.get('steps') else None
    if kind == 'image': c['binding'] = dict(source='result', path='', nodeId=last) if last else dict(source='source', path='')
    if kind == 'cloud': c.update(binding=dict(source='result', path='', nodeId=last or 'missing'), maxPoints=12000, pointSize=2, initialView='iso')
    if kind in ('value', 'trend'): c.update(precision=2, unit='')
    if kind == 'trend': c['capacity'] = 120
    if kind == 'alarm': c.update(comparison='gte', threshold=10, hysteresis=0, stableSamples=1, severity='warning')
    if kind == 'button': c.update(action='run', label='运行检测')
    if kind == 'input': c.update(dataType='number', minimum=-1000000, maximum=1000000)
    return c


def read_binding(binding, state):
    if not binding: return MISSING
    source = binding.get('source'); variables = state.get('variables', {})
    if source == 'module': value = variables.get('modules', {}).get(binding.get('nodeId'), MISSING)
    elif source == 'result':
        row = next((r for r in state.get('results', []) if r.get('id') == binding.get('nodeId') and not r.get('error') and not r.get('skipped')), None)
        value = row.get('output', {}).get('result', MISSING) if row else MISSING
    elif source == 'status': value = state.get('status', {})
    else: value = variables.get(source, MISSING)
    for key in binding.get('path', '').split('.') if binding.get('path') else []:
        if key in FORBIDDEN: return MISSING
        if isinstance(value, dict): value = value.get(key, MISSING)
        elif isinstance(value, list) and key.isdigit() and int(key) < len(value): value = value[int(key)]
        else: return MISSING
    return value


def validate_layout(layout):
    """Validate schema fields without normalizing away extension fields."""
    def check(condition, message):
        if not condition: raise ValueError(message)
    def integer(v, low, high): return type(v) is int and low <= v <= high
    def finite(v): return type(v) in (int, float) and math.isfinite(v)
    def identifier(v): return isinstance(v, str) and re.fullmatch(r'[A-Za-z0-9_-]{1,80}', v) and v not in FORBIDDEN
    check(layout.get('version') in (1, 2), '运行画面版本无效')
    check(isinstance(layout.get('title'), str) and len(layout['title']) <= 100, '画面标题最多 100 字')
    all_pages = pages(layout); check(1 <= len(all_pages) <= 20, '需要 1–20 页')
    ids = [page_id(p, layout) for p in all_pages]
    check(all(identifier(i) for i in ids) and len(ids) == len(set(ids)), '页面编号无效或重复')
    if layout['version'] == 2: check(layout.get('defaultPageId') in ids, '默认页不存在')
    component_ids = set(); monitor_count = 0
    for page in all_pages:
        check(isinstance(page.get('title'), str) and len(page['title']) <= 100 and page['title'].strip(), '页面标题须为 1–100 字')
        check(integer(page.get('rows'), 4, 40) and integer(page.get('rowHeight'), 40, 120), '画面行数 4–40，行高 40–120')
        components = page.get('components', []); check(len(components) <= 50, '每页最多 50 个组件')
        for c in components:
            check(identifier(c.get('id')) and c['id'] not in component_ids, '组件编号无效或重复'); component_ids.add(c['id'])
            kind = c.get('type'); check(kind in TYPES, '不支持的组件类型：' + str(kind))
            check(isinstance(c.get('label'), str) and len(c['label']) <= 200, '组件标题最多 200 字')
            check(integer(c.get('x'), 0, 11) and integer(c.get('y'), 0, page['rows'] - 1) and integer(c.get('w'), 1, 12) and integer(c.get('h'), 1, page['rows']) and c['x'] + c['w'] <= 12 and c['y'] + c['h'] <= page['rows'], '组件超出网格边界')
            check(isinstance(c.get('color'), str) and re.fullmatch(r'#[a-fA-F0-9]{6}', c['color']) and integer(c.get('fontSize'), 12, 64), '颜色须为 #RRGGBB；字号 12–64')
            if kind not in ('text', 'button'):
                b = c.get('binding', {}); source = b.get('source'); path = b.get('path')
                check(source in SOURCES and isinstance(path, str) and len(path) <= 200 and (not path or all(k and k not in FORBIDDEN for k in path.split('.'))), '数据来源或字段路径无效')
                if source in ('module', 'result'): check(isinstance(b.get('nodeId'), str) and 0 < len(b['nodeId']) <= 80 and b['nodeId'] not in FORBIDDEN, '请选择绑定模块')
                if kind == 'image': check(source in ('source', 'result'), '图像只能绑定输入图像或模块结果')
                if kind == 'cloud': check(source == 'result' and not path, '点云只能绑定模块输出点云通道')
                if kind == 'input':
                    check(source in ('flow', 'global', 'module') and NAME.fullmatch(path) and path not in FORBIDDEN, '输入框只能绑定单个变量名称')
                    check(c.get('dataType') in ('number', 'string', 'boolean'), '输入类型无效')
                    if c['dataType'] == 'number': check(finite(c.get('minimum')) and finite(c.get('maximum')) and c['minimum'] <= c['maximum'], '变量输入范围无效')
            if kind in ('value', 'trend'): check(integer(c.get('precision'), 0, 6) and isinstance(c.get('unit'), str) and len(c['unit']) <= 20, '小数位 0–6，单位最多 20 字')
            if kind == 'button':
                check(c.get('action') in ('run', 'stop', 'navigate'), '按钮动作无效')
                if c['action'] == 'navigate': check(c.get('targetPageId') in ids, '跳转目标页不存在')
            if kind == 'cloud': check(integer(c.get('maxPoints'), 100, 30000) and integer(c.get('pointSize'), 1, 6) and c.get('initialView') in ('iso', 'top', 'front'), '点云预览参数无效')
            if kind in ('alarm', 'trend'):
                monitor_count += 1; check(c['binding']['source'] != 'source', '报警与趋势不能绑定输入图像')
            if kind == 'trend': check(integer(c.get('capacity'), 20, 1000), '趋势样本数须为 20–1000')
            if kind == 'alarm':
                comparison = c.get('comparison'); check(comparison in ('gt', 'gte', 'lt', 'lte', 'eq', 'ne', 'is_true', 'is_false'), '报警比较方式无效')
                check(c.get('severity') in ('info', 'warning', 'critical') and integer(c.get('stableSamples'), 1, 100), '报警级别或稳定样本数无效')
                check(finite(c.get('hysteresis')) and 0 <= c['hysteresis'] <= 1e12, '报警回差范围无效')
                check(c['hysteresis'] == 0 or comparison in ('gt', 'gte', 'lt', 'lte'), '仅大小比较可使用回差')
                if comparison in ('gt', 'gte', 'lt', 'lte'): check(finite(c.get('threshold')), '大小比较阈值必须为有限数值')
                elif comparison in ('eq', 'ne'): check(c.get('threshold') is None or isinstance(c.get('threshold'), (str, bool)) or finite(c.get('threshold')), '报警阈值须为标量')
                if isinstance(c.get('threshold'), str): check(len(c['threshold']) <= 200, '报警阈值最多 200 字')
    check(len(component_ids) <= 200 and monitor_count <= 50, '合计最多 200 个组件，其中报警和趋势最多 50 个')


class ComponentItem(QGraphicsRectItem):
    def __init__(self, component, page, dialog):
        super().__init__(0, 0, component['w'] * COL_WIDTH - 6, component['h'] * page['rowHeight'] - 6)
        self.component, self.page, self.dialog = component, page, dialog
        self.setPos(component['x'] * COL_WIDTH, component['y'] * page['rowHeight'])
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsMovable | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable | QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.setEnabled(not dialog.busy)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange and self.scene():
            x = min(12 - self.component['w'], max(0, math.floor(value.x() / COL_WIDTH + .5)))
            y = min(self.page['rows'] - self.component['h'], max(0, math.floor(value.y() / self.page['rowHeight'] + .5)))
            return QPointF(x * COL_WIDTH, y * self.page['rowHeight'])
        return super().itemChange(change, value)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        self.component['x'] = round(self.pos().x() / COL_WIDTH); self.component['y'] = round(self.pos().y() / self.page['rowHeight'])
        self.dialog.properties()

    def paint(self, painter, option, widget=None):
        c = self.component; rect = self.rect(); color = QColor(c.get('color', '#1095bd'))
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(color if self.isSelected() else QColor('#c6d7e2'), 3 if self.isSelected() else 1))
        painter.setBrush(QColor('#ffffff')); painter.drawRoundedRect(rect, 5, 5)
        painter.fillRect(QRectF(2, 2, rect.width() - 4, 5), color)
        if rect.height() < 85:
            font = QFont('Microsoft YaHei UI'); font.setPixelSize(min(c.get('fontSize', 24), 22))
            painter.setFont(font); painter.setPen(color)
            painter.drawText(rect.adjusted(10, 8, -10, -5), Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, c.get('label', ''))
            return
        painter.setPen(QColor('#21415b')); font = QFont('Microsoft YaHei UI'); font.setPixelSize(13); painter.setFont(font)
        painter.drawText(rect.adjusted(10, 9, -8, -8), Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap, c.get('label', ''))
        painter.setPen(color); font.setPixelSize(min(c.get('fontSize', 24), 32)); painter.setFont(font)
        value = read_binding(c.get('binding'), self.dialog.state)
        text = c['label'] if c['type'] == 'text' else value_summary(value) if c['type'] in ('value', 'lamp') else TYPES.get(c['type'], c['type'])
        painter.drawText(rect.adjusted(10, 36, -10, -8), Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, text)


class GridScene(QGraphicsScene):
    def __init__(self, parent=None): super().__init__(parent); self.row_height = 60; self.editing = True

    def drawBackground(self, painter, rect):
        painter.fillRect(rect, QColor('#edf3f8'))
        if self.editing:
            painter.setPen(QPen(QColor('#d7e3ed'), 1))
            for x in range(0, 12 * COL_WIDTH + 1, COL_WIDTH): painter.drawLine(x, 0, x, int(self.sceneRect().height()))
            for y in range(0, int(self.sceneRect().height()) + 1, self.row_height): painter.drawLine(0, y, 12 * COL_WIDTH, y)


class TrendChart(QWidget):
    def __init__(self, component, parent=None):
        super().__init__(parent); self.component = component; self.samples = []; self.setMinimumHeight(130)

    def set_samples(self, samples): self.samples = samples; self.update()

    def paintEvent(self, event):
        painter = QPainter(self); painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor('#ffffff'))
        valid = [s for s in self.samples if s.get('quality') == 'good' and type(s.get('value')) in (int, float) and math.isfinite(s['value'])]
        painter.setPen(QColor('#547186'))
        if not valid: painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, '暂无有效数值样本'); return
        low, high = min(s['value'] for s in valid), max(s['value'] for s in valid)
        if low == high: low -= max(1, abs(low) * .05); high += max(1, abs(high) * .05)
        area = QRectF(64, 12, max(1, self.width() - 80), max(1, self.height() - 39))
        start = self.samples[0].get('time', 0); end = self.samples[-1].get('time', start + 1); span = max(1, end - start)
        for fraction in [0, .5, 1]:
            y = area.top() + fraction * area.height(); painter.setPen(QColor('#dbe5ec'))
            painter.drawLine(QPointF(area.left(), y), QPointF(area.right(), y)); painter.setPen(QColor('#547186'))
            painter.drawText(QRectF(0, y - 8, 60, 20), Qt.AlignmentFlag.AlignRight, f"{high - fraction * (high - low):.{self.component.get('precision', 2)}f}")
        path = QPainterPath(); connected = False; points = []
        for sample in self.samples:
            if sample not in valid: connected = False; continue
            point = QPointF(area.left() + (sample.get('time', start) - start) / span * area.width(), area.bottom() - (sample['value'] - low) / (high - low) * area.height())
            path.lineTo(point) if connected else path.moveTo(point); connected = True; points.append(point)
        painter.setPen(QPen(QColor(self.component['color']), 2)); painter.drawPath(path)
        for point in points: painter.drawEllipse(point, 2, 2)
        painter.setPen(QColor('#547186')); painter.drawText(QRectF(area.left(), area.bottom() + 4, area.width(), 20), Qt.AlignmentFlag.AlignLeft, time_text(start))


def time_text(value):
    if not value: return '—'
    try: return datetime.datetime.fromtimestamp(value / 1000).strftime('%m-%d %H:%M:%S')
    except (TypeError, ValueError, OSError): return '—'


class RecordTable(QWidget):
    """Flat record columns with nested-cell inspection, bounded like the web table."""
    def __init__(self, parent=None):
        super().__init__(parent); layout = QVBoxLayout(self); layout.setContentsMargins(0, 0, 0, 0)
        self.table = QTableWidget(); self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.cellDoubleClicked.connect(self.inspect); layout.addWidget(self.table, 1)
        self.note = QLabel(); layout.addWidget(self.note); self.values = {}

    def set_value(self, value):
        self.values = {}
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, (dict, list)): value = parsed
            except (ValueError, TypeError): pass
        if value is MISSING:
            self.table.setRowCount(0); self.table.setColumnCount(0); self.note.setText('尚无当前值'); return
        rows = value if isinstance(value, list) else [value]
        keys = list(dict.fromkeys(k for row in rows[:100] for k in (row if isinstance(row, dict) else ['值'])))[:20]
        self.table.setColumnCount(len(keys)); self.table.setHorizontalHeaderLabels([str(k) for k in keys]); self.table.setRowCount(min(len(rows), 100))
        for r, row in enumerate(rows[:100]):
            for col, key in enumerate(keys):
                cell = row.get(key, MISSING) if isinstance(row, dict) else row if key == '值' else MISSING
                item = QTableWidgetItem(value_summary(cell)); item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(r, col, item); self.values[(r, col)] = cell
        self.note.setText(('显示前 100 行 · ' if len(rows) > 100 else '') + ('暂无数据' if not rows else '双击单元格查看嵌套内容'))

    def inspect(self, row, column):
        value = self.values.get((row, column), MISSING)
        dialog = QDialog(self); dialog.setWindowTitle('单元格内容'); dialog.resize(600, 430)
        QVBoxLayout(dialog).addWidget(DataTree(value)); dialog.exec()


class PreviewCard(QWidget):
    def __init__(self, component, dialog):
        super().__init__(); self.c, self.dialog = component, dialog; self.pending = False; self.saving = False; self.signature = None; self.paused = False
        c = component; self.setObjectName('hmiCard')
        self.setStyleSheet('QWidget#hmiCard{background:white;border:1px solid #c8d8e4;border-top:4px solid ' + c['color'] + ';}')
        layout = QVBoxLayout(self); layout.setContentsMargins(8, 6, 8, 6); layout.setSpacing(4)
        self.heading = QLabel(c['label']); layout.addWidget(self.heading)
        kind = c['type']; self.content = None
        if kind == 'button':
            self.content = QPushButton(c['label']); self.content.clicked.connect(lambda: dialog.component_action(c)); layout.addWidget(self.content, 1)
        elif kind == 'input':
            self.field = QComboBox() if c['dataType'] == 'boolean' else QLineEdit()
            if c['dataType'] == 'boolean':
                self.field.addItem('否', False); self.field.addItem('是', True); self.field.activated.connect(self.mark_pending)
            else: self.field.textEdited.connect(self.mark_pending)
            layout.addWidget(self.field); row = QHBoxLayout(); layout.addLayout(row)
            self.write_button = QPushButton('写入'); self.write_button.clicked.connect(lambda: dialog.write_input(self)); row.addWidget(self.write_button)
            self.discard = QPushButton('放弃待写值'); self.discard.clicked.connect(self.discard_input); row.addWidget(self.discard)
            self.note = QLabel(); self.note.setWordWrap(True); layout.addWidget(self.note); layout.addStretch()
        elif kind in ('table', 'value'):
            self.content = RecordTable() if kind == 'table' else DataTree(); self.scalar = QLabel(); self.scalar.setWordWrap(True); self.scalar.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.scalar.setStyleSheet(f"font-size:{c['fontSize']}px;color:{c['color']};")
            layout.addWidget(self.scalar); layout.addWidget(self.content, 1)
        elif kind == 'cloud':
            self.content = CloudView(); layout.addWidget(self.content, 1)
            self.content.max_points = c.get('maxPoints', 12000); self.content.point_size = c.get('pointSize', 2)
            if c.get('initialView') == 'top': self.content.pitch = 1.55; self.content.yaw = 0
            elif c.get('initialView') == 'front': self.content.pitch = 0; self.content.yaw = 0
        elif kind in ('alarm', 'trend'):
            self.note = QLabel(); self.note.setWordWrap(True); layout.addWidget(self.note)
            if kind == 'trend':
                self.pause = QPushButton('暂停显示'); self.pause.clicked.connect(self.toggle_pause); layout.addWidget(self.pause)
                self.chart = TrendChart(c); layout.addWidget(self.chart, 1)
                self.content = RecordTable(); self.content.setMaximumHeight(140); layout.addWidget(self.content)
            else:
                self.comment = QLineEdit(); self.comment.setMaxLength(200); self.comment.setPlaceholderText('确认备注（可选）'); layout.addWidget(self.comment)
                self.content = QTableWidget(0, 7); self.content.setHorizontalHeaderLabels(['状态', '触发值', '发生', '恢复', '确认', '备注', '操作'])
                self.content.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents); layout.addWidget(self.content, 1)
        else:
            self.content = QLabel(); self.content.setWordWrap(True); self.content.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.content.setStyleSheet(f"font-size:{c['fontSize']}px;color:{c['color']};"); layout.addWidget(self.content, 1)

    def mark_pending(self, *_): self.pending = True; self.refresh()
    def discard_input(self): self.pending = False; self.refresh()
    def toggle_pause(self): self.paused = not self.paused; self.pause.setText('继续显示' if self.paused else '暂停显示'); self.refresh()

    def refresh(self):
        c, state = self.c, self.dialog.state; kind = c['type']; value = MISSING if self.dialog.runtime_error else read_binding(c.get('binding'), state)
        busy = self.dialog.busy or state.get('status', {}).get('state') == 'running'
        if kind == 'button':
            self.content.setEnabled((c['action'] == 'navigate') or (not busy if c['action'] == 'run' else busy)); return
        if kind == 'input':
            ready = type(state.get('variables', {}).get('revision')) is int
            self.field.setEnabled(not busy and not self.saving); self.write_button.setEnabled(ready and not busy and not self.saving and not self.dialog.runtime_error)
            self.discard.setEnabled(self.pending and not self.saving)
            if not self.pending and not self.saving:
                if c['dataType'] == 'boolean' and isinstance(value, bool): self.field.setCurrentIndex(int(value))
                elif c['dataType'] != 'boolean': self.field.setText('' if value is MISSING else value_summary(value))
            self.note.setText('当前值：' + value_summary(value) + (' · 待写入' if self.pending else '')); return
        if kind == 'text': self.content.setText(c['label']); return
        if kind == 'image':
            row = self.dialog.result_row(c); data = self.dialog.source_image if c['binding']['source'] == 'source' else row.get('output', {}).get('annotatedImage', '')
            if self.dialog.runtime_error: data = ''
            if data != self.signature:
                self.signature = data; pixmap = QPixmap()
                if isinstance(data, str) and data.startswith('data:image/'):
                    try: pixmap.loadFromData(base64.b64decode(data.split(',', 1)[1]))
                    except (ValueError, IndexError): pass
                self.image = pixmap
            pixmap = getattr(self, 'image', QPixmap())
            if pixmap.isNull(): self.content.setText('等待图像')
            else: self.content.setPixmap(pixmap.scaled(max(1, self.width() - 20), max(1, self.height() - 46), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            return
        if kind == 'cloud':
            cloud = None if self.dialog.runtime_error else self.dialog.result_row(c).get('output', {}).get('cloud')
            if cloud != self.signature:
                self.signature = deepcopy(cloud)
                self.content.set_cloud(cloud)
            return
        if kind == 'lamp':
            text, color = ('通过', '#1b9c67') if value is True else ('未通过', '#d14949') if value is False else ('未知', '#8799a6')
            self.content.setText('● ' + text); self.content.setStyleSheet(f"font-size:{c['fontSize']}px;color:{color};"); return
        if kind in ('alarm', 'trend'): self.refresh_monitor(); return
        if kind in ('value', 'table'):
            structured = isinstance(value, (dict, list)) or kind == 'table'
            self.content.setVisible(structured); self.scalar.setVisible(not structured)
            if structured:
                if value is MISSING or value != self.signature: self.content.set_value(value); self.signature = deepcopy(value) if value is not MISSING else None
            else:
                text = f"{value:.{c.get('precision', 2)}f}" if type(value) in (int, float) else value_summary(value)
                self.scalar.setText(text + (' ' + c.get('unit', '') if c.get('unit') else ''))

    def refresh_monitor(self):
        if self.paused: return
        monitor = self.dialog.state.get('monitor', {}); widget = monitor.get('widgets', {}).get(self.c['id'])
        expected = {k: v for k, v in self.c.items() if k not in ('x', 'y', 'w', 'h', 'fontSize', 'color')}
        try: compatible = widget and json.loads(widget.get('signature', '{}')) == expected
        except (ValueError, TypeError): compatible = False
        error = self.dialog.runtime_error or monitor.get('error')
        if error or not compatible:
            self.note.setText(error or '配置将在下一轮运行或变量写入后启用，尚无当前配置样本。')
            if self.c['type'] == 'trend': self.chart.set_samples([]); self.content.set_value([])
            else: self.content.setRowCount(0)
            return
        if self.c['type'] == 'trend':
            samples = widget.get('samples', []); self.chart.set_samples(samples)
            self.note.setText(f"{len(samples)} 个保留样本 · {self.c.get('unit', '')} · 无效样本处断开")
            if samples != self.signature:
                self.signature = deepcopy(samples)
                self.content.set_value([{'时间': time_text(s.get('time')), '数值': s.get('value') if s.get('quality') == 'good' else None, '质量': '有效' if s.get('quality') == 'good' else '缺口', '说明': s.get('reason', '')} for s in reversed(samples)])
        else:
            self.note.setText(('数据未知 · 保留原报警状态' if widget.get('quality') == 'invalid' else '报警中' if widget.get('active') else '当前未报警') + (' · ' + widget['reason'] if widget.get('reason') else ''))
            events = [e for e in monitor.get('events', []) if e.get('componentId') == self.c['id']][:30]
            if events == self.signature: return
            self.signature = deepcopy(events); self.content.setRowCount(len(events))
            for row, event in enumerate(events):
                status = ('已恢复' if event.get('returnedAt') else '报警中') + (' · 已确认' if event.get('acknowledgedAt') else ' · 待确认')
                for col, value in enumerate([status, value_summary(event.get('value')), time_text(event.get('startedAt')), time_text(event.get('returnedAt')), time_text(event.get('acknowledgedAt')), event.get('comment', '')]):
                    item = QTableWidgetItem(value); item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable); self.content.setItem(row, col, item)
                button = QPushButton('确认'); button.setEnabled(not event.get('acknowledgedAt')); button.clicked.connect(lambda _, e=event: self.dialog.acknowledge(e, self.comment.text()))
                self.content.setCellWidget(row, 6, button)


class HmiDialog(QDialog):
    run_requested = Signal()
    stop_requested = Signal()

    def __init__(self, document, backend, parent=None):
        super().__init__(parent)
        self.document, self.backend = document, backend
        self.project_id = document.project['id']; self.original = deepcopy(document.project.get('hmi'))
        self.draft = deepcopy(self.original) if self.original else empty_page()
        self.active_page = self.draft.get('defaultPageId', 'main'); self.selection = None
        self.pending = {}; self.cards = []; self.busy = False; self.runtime_error = ''; self.source_image = ''; self.stale = False; self._applying = False; self._rendering = False; self.epoch = 0
        self.state = dict(variables={}, results=[], status={'state': 'idle'})
        self.setWindowTitle('原生运行画面组态'); self.resize(1350, 830)
        layout = QVBoxLayout(self)
        row = QHBoxLayout(); layout.addLayout(row)
        self.preview = QComboBox(); self.preview.addItem('编辑网格', False); self.preview.addItem('运行画面', True); row.addWidget(self.preview)
        self.page_select = QComboBox(); row.addWidget(self.page_select, 1)
        self.page_buttons = []
        for label, callback in [('新增页', self.add_page), ('复制页', self.copy_page), ('删除页', self.remove_page), ('前移', lambda: self.move_page(-1)), ('后移', lambda: self.move_page(1)), ('设为默认', self.set_default)]:
            button = QPushButton(label); button.clicked.connect(lambda checked=False, cb=callback: self.guard(cb)); row.addWidget(button); self.page_buttons.append(button)
        self.palette = QComboBox()
        for key, label in TYPES.items(): self.palette.addItem(label, key)
        self.add_button = QPushButton('添加组件'); self.add_button.clicked.connect(lambda: self.guard(self.add_component))
        self.copy_button = QPushButton('复制组件'); self.copy_button.clicked.connect(lambda: self.guard(self.copy_component))
        self.delete_button = QPushButton('删除组件'); self.delete_button.clicked.connect(lambda: self.guard(self.remove_component))
        bar = QHBoxLayout(); layout.addLayout(bar)
        for control in [self.palette, self.add_button, self.copy_button, self.delete_button]: bar.addWidget(control)
        bar.addStretch(); self.fit_button = QPushButton('适应画布'); self.fit_button.clicked.connect(self.fit); bar.addWidget(self.fit_button)
        self.hint = QLabel('编辑网格中拖动组件；运行画面中的按钮与写入会操作本机工程。更改初始定义请使用变量管理。'); self.hint.setWordWrap(True); layout.addWidget(self.hint)
        split = QSplitter(); layout.addWidget(split, 1)
        self.scene = GridScene(self); self.view = QGraphicsView(self.scene); self.view.setRenderHint(QPainter.RenderHint.Antialiasing); split.addWidget(self.view)
        self.properties_scroll = QScrollArea(); self.properties_scroll.setWidgetResizable(True); self.properties_scroll.setMinimumWidth(290); split.addWidget(self.properties_scroll); split.setSizes([1000, 320])
        bottom = QHBoxLayout(); layout.addLayout(bottom)
        self.message = QLabel(); self.message.setWordWrap(True); bottom.addWidget(self.message, 1)
        self.apply_button = QPushButton('应用画面到工程'); self.apply_button.clicked.connect(lambda: self.guard(self.apply_layout)); bottom.addWidget(self.apply_button)
        close = QPushButton('关闭'); close.clicked.connect(self.reject); bottom.addWidget(close)
        self.scene.selectionChanged.connect(self.selected)
        self.preview.currentIndexChanged.connect(self.render)
        self.page_select.currentIndexChanged.connect(self.select_page)
        self.backend.result.connect(self._result); self.backend.error.connect(self._error); self.document.changed.connect(self._document_changed)
        self.finished.connect(self._disconnect)
        self.timer = QTimer(self); self.timer.setInterval(1000); self.timer.timeout.connect(self.refresh); self.timer.start()
        self.render(); QTimer.singleShot(0, self.refresh)

    def guard(self, callback):
        try: callback()
        except (ValueError, KeyError, TypeError) as error: self.message.setText(str(error))

    def current_page(self):
        return next((p for p in pages(self.draft) if page_id(p, self.draft) == self.active_page), pages(self.draft)[0])

    def current_component(self): return next((c for c in self.current_page()['components'] if c['id'] == self.selection), None)

    def is_running(self): return self.busy or self.state.get('status', {}).get('state') == 'running'

    def _disconnect(self, *_):
        self.timer.stop(); self.pending.clear()
        for signal, slot in [(self.backend.result, self._result), (self.backend.error, self._error), (self.document.changed, self._document_changed)]:
            try: signal.disconnect(slot)
            except (RuntimeError, TypeError): pass

    def _document_changed(self):
        if self._applying: return
        if self.document.project['id'] != self.project_id or self.document.project.get('hmi') != self.original:
            self.stale = True; self.message.setText('工程或运行画面已在其他位置变更，请关闭后重新打开组态。'); self.set_busy(self.busy)

    def set_busy(self, busy):
        starting = bool(busy) and not self.busy; self.busy = bool(busy)
        if starting: self.state['results'] = []; self.state['status'] = {'state': 'running'}; self.epoch += 1
        editing = not self.preview.currentData() and not self.is_running() and not self.stale
        for control in [*self.page_buttons, self.add_button, self.copy_button, self.delete_button, self.palette]: control.setEnabled(editing)
        self.properties_scroll.setEnabled(editing); self.apply_button.setEnabled(not self.is_running() and not self.stale)
        for item in self.scene.items():
            if isinstance(item, ComponentItem): item.setEnabled(editing)
        self.update_cards()

    def set_source_image(self, image): self.source_image = image or ''; self.update_cards()

    def set_runtime(self, job, source_image=None):
        if source_image is not None: self.source_image = source_image
        if 'status' in job:
            self.state.update({k: deepcopy(v) for k, v in job.items() if k != 'results'})
            if 'results' in job: self.state['results'] = deepcopy(job['results'])
        else:
            job_id = job.get('id')
            if job_id and job_id != self.state.get('status', {}).get('id'): self.state['results'] = []
            current = {r['id']: r for r in self.state.get('results', [])}
            for result in job.get('results', []): current[result['id']] = deepcopy(result)
            self.state['results'] = list(current.values())
            self.state['status'] = {k: deepcopy(v) for k, v in job.items() if k not in ('results', 'variables', 'monitor')}
            for key in ('variables', 'monitor'):
                if job.get(key) is not None: self.state[key] = deepcopy(job[key])
        self.runtime_error = ''; self.set_busy(self.busy)

    def result_row(self, c):
        return next((r for r in self.state.get('results', []) if r.get('id') == c.get('binding', {}).get('nodeId') and not r.get('error') and not r.get('skipped')), {})

    def refresh(self):
        if self.stale or any(item[0] == 'view' for item in self.pending.values()): return
        if not self.isVisible() and self.pending: return
        params = {'project': deepcopy(self.document.project)}
        if 'version' in self.state: params['since'] = self.state['version']
        self.pending[self.backend.request('runtime/view', params)] = ('view', self.epoch)

    def _result(self, request_id, result):
        pending = self.pending.pop(request_id, None)
        if pending is None or self.stale: return
        tag, card = pending
        if tag == 'view':
            if card != self.epoch: return
            self.set_runtime(result)
        elif tag == 'write':
            self.state['variables'] = deepcopy(result); card.pending = False; card.saving = False
            self.message.setText('变量已写入。'); self.refresh(); self.update_cards()
        elif tag == 'ack': self.state['monitor'] = deepcopy(result); self.message.setText('报警已确认；仍存在的报警条件继续显示。'); self.update_cards()

    def _error(self, request_id, message):
        pending = self.pending.pop(request_id, None)
        if pending is None: return
        tag, card = pending
        if tag == 'view': self.runtime_error = message
        if tag == 'write': card.saving = False
        self.message.setText(message); self.update_cards()

    def update_cards(self):
        for card in self.cards: card.refresh()
        for item in self.scene.items():
            if isinstance(item, ComponentItem): item.update()

    def selected(self):
        if self._rendering: return
        items = [i for i in self.scene.selectedItems() if isinstance(i, ComponentItem)]
        self.selection = items[0].component['id'] if items else None; self.properties()

    def select_page(self, *_):
        if self._rendering: return
        target = self.page_select.currentData()
        if target == self.active_page: return
        if any(c.pending or c.saving for c in self.cards):
            self.message.setText('当前页有待写入值，请先写入或放弃。'); self.page_select.blockSignals(True); self.page_select.setCurrentIndex(self.page_select.findData(self.active_page)); self.page_select.blockSignals(False); return
        self.active_page = target; self.selection = None; self.render()

    def render(self, *_):
        if self._rendering: return
        if any(c.pending or c.saving for c in self.cards):
            self.message.setText('请先写入或放弃当前页待写值，再切换视图。')
            self.preview.blockSignals(True); self.preview.setCurrentIndex(int(getattr(self, '_rendered_preview', True))); self.preview.blockSignals(False)
            return
        self._rendering = True
        try:
            self.page_select.blockSignals(True); self.page_select.clear()
            default = self.draft.get('defaultPageId', 'main')
            for p in pages(self.draft):
                pid = page_id(p, self.draft); self.page_select.addItem(p['title'] + (' · 默认' if pid == default else ''), pid)
            self.page_select.setCurrentIndex(max(0, self.page_select.findData(self.active_page))); self.active_page = self.page_select.currentData(); self.page_select.blockSignals(False)
            page = self.current_page(); self.scene.clear(); self.cards = []; self.scene.row_height = page['rowHeight']; self.scene.editing = not self.preview.currentData()
            self.scene.setSceneRect(0, 0, 12 * COL_WIDTH, page['rows'] * page['rowHeight'])
            for c in page['components']:
                if self.preview.currentData():
                    card = PreviewCard(c, self); card.resize(c['w'] * COL_WIDTH - 6, c['h'] * page['rowHeight'] - 6)
                    proxy = self.scene.addWidget(card); proxy.setPos(c['x'] * COL_WIDTH, c['y'] * page['rowHeight']); self.cards.append(card)
                else:
                    item = ComponentItem(c, page, self); self.scene.addItem(item); item.setSelected(c['id'] == self.selection)
            self._rendered_preview = bool(self.preview.currentData()); self.properties(); self.set_busy(self.busy); self.fit()
        finally: self._rendering = False

    def fit(self): self.view.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def showEvent(self, event):
        super().showEvent(event); QTimer.singleShot(0, self.fit)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'view'): QTimer.singleShot(0, self.fit)

    def _upgrade(self):
        if self.draft.get('version') == 2: return
        old = self.draft; old['id'] = 'main'
        self.draft = dict(version=2, title=old['title'], defaultPageId='main', pages=[old]); self.active_page = 'main'

    def add_page(self):
        if self.is_running(): return
        if len(pages(self.draft)) >= 20: raise ValueError('最多 20 页')
        self._upgrade(); page = empty_page('新页面 ' + str(len(pages(self.draft)) + 1)); page['id'] = 'page-' + uuid.uuid4().hex[:12]
        self.draft['pages'].append(page); self.active_page = page['id']; self.selection = None; self.render()

    def copy_page(self):
        if self.is_running(): return
        if len(pages(self.draft)) >= 20: raise ValueError('最多 20 页')
        self._upgrade(); source = self.current_page(); page = deepcopy(source); page['id'] = 'page-' + uuid.uuid4().hex[:12]; page['title'] = page['title'][:94] + ' 副本'
        for c in page['components']:
            c['id'] = 'hmi-' + uuid.uuid4().hex[:16]
            if c.get('action') == 'navigate' and c.get('targetPageId') == source['id']: c['targetPageId'] = page['id']
        candidate = deepcopy(self.draft); candidate['pages'].append(page); validate_layout(candidate)
        self.draft = candidate; self.active_page = page['id']; self.selection = None; self.render()

    def remove_page(self):
        if self.is_running(): return
        if len(pages(self.draft)) == 1: raise ValueError('至少保留一个页面')
        if any(c.get('action') == 'navigate' and c.get('targetPageId') == self.active_page for p in pages(self.draft) if p['id'] != self.active_page for c in p['components']): raise ValueError('其他页面按钮仍引用此页，请先修改跳转目标')
        self.draft['pages'] = [p for p in pages(self.draft) if p['id'] != self.active_page]
        if self.draft['defaultPageId'] == self.active_page: self.draft['defaultPageId'] = self.draft['pages'][0]['id']
        self.active_page = self.draft['defaultPageId']; self.selection = None; self.render()

    def move_page(self, offset):
        if self.is_running() or self.draft['version'] != 2: return
        all_pages = self.draft['pages']; index = next(i for i, p in enumerate(all_pages) if p['id'] == self.active_page); target = index + offset
        if 0 <= target < len(all_pages): all_pages[index], all_pages[target] = all_pages[target], all_pages[index]; self.render()

    def set_default(self):
        if self.is_running(): return
        if self.draft['version'] == 2: self.draft['defaultPageId'] = self.active_page; self.render()

    def add_component(self):
        if self.is_running(): return
        page = self.current_page(); c = new_component(self.palette.currentData(), self.document.project)
        c['h'] = min(c['h'], page['rows']); c['y'] = min(len(page['components']) * 2, page['rows'] - c['h'])
        page['components'].append(c)
        try: validate_layout(self.draft)
        except ValueError: page['components'].pop(); raise
        self.selection = c['id']; self.render()

    def copy_component(self):
        if self.is_running(): return
        c = self.current_component()
        if not c: return
        copy = deepcopy(c); copy['id'] = 'hmi-' + uuid.uuid4().hex[:16]; copy['label'] = copy['label'][:195] + ' 副本'; copy['y'] = min(copy['y'] + 1, self.current_page()['rows'] - copy['h'])
        self.current_page()['components'].append(copy)
        try: validate_layout(self.draft)
        except ValueError: self.current_page()['components'].pop(); raise
        self.selection = copy['id']; self.render()

    def remove_component(self):
        if self.is_running(): return
        self.current_page()['components'] = [c for c in self.current_page()['components'] if c['id'] != self.selection]; self.selection = None; self.render()

    def properties(self):
        container = QWidget(); form = QFormLayout(container); form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        def field(label, target, key, kind='text', options=None, low=None, high=None, rebuild=False):
            value = target.get(key, '')
            if options is not None:
                control = QComboBox()
                for raw, text in options: control.addItem(text, raw)
                index = control.findData(value)
                if index < 0: control.addItem('已有：' + str(value), value); index = control.count() - 1
                control.setCurrentIndex(index); control.currentIndexChanged.connect(lambda _: self.guard(lambda: self.change_property(target, key, control.currentData(), rebuild)))
            elif kind == 'integer':
                control = QSpinBox(); control.setRange(low, high); control.setValue(value); control.setKeyboardTracking(False)
                control.valueChanged.connect(lambda v: self.guard(lambda: self.change_property(target, key, v, rebuild)))
            else:
                control = QLineEdit(str(value)); control.setMaxLength(200 if key == 'label' else 100 if key == 'title' else 200)
                control.editingFinished.connect(lambda: self.guard(lambda: self.change_property(target, key, float(control.text()) if kind == 'number' else control.text(), rebuild)))
            control.setObjectName('hmiProperty:' + key); form.addRow(label, control); return control
        page = self.current_page()
        if self.draft['version'] == 2: field('运行画面总标题', self.draft, 'title')
        field('页面标题', page, 'title'); field('网格行数', page, 'rows', 'integer', low=4, high=40); field('行高', page, 'rowHeight', 'integer', low=40, high=120)
        c = self.current_component()
        if not c: form.addRow(QLabel('选择组件后编辑其位置、样式和绑定。'))
        else:
            form.addRow(QLabel(TYPES.get(c['type'], c['type']))); field('组件标题', c, 'label')
            for key, label, low, high in [('x', '列位置', 0, 12 - c['w']), ('y', '行位置', 0, page['rows'] - c['h']), ('w', '宽度（列）', 1, 12 - c['x']), ('h', '高度（行）', 1, page['rows'] - c['y'])]: field(label, c, key, 'integer', low=low, high=high)
            field('颜色 #RRGGBB', c, 'color'); field('字号', c, 'fontSize', 'integer', low=12, high=64)
            kind = c['type']
            if kind in ('value', 'trend'): field('小数位', c, 'precision', 'integer', low=0, high=6); field('单位', c, 'unit')
            if kind == 'button':
                field('按钮动作', c, 'action', options=[('run', '运行整个流程'), ('stop', '停止流程'), ('navigate', '跳转页面')], rebuild=True)
                if c.get('action') == 'navigate': field('目标页面', c, 'targetPageId', options=[(page_id(p, self.draft), p['title']) for p in pages(self.draft)])
            if kind == 'input':
                field('输入类型', c, 'dataType', options=[('number', '数值'), ('string', '文本'), ('boolean', '开关')], rebuild=True)
                if c['dataType'] == 'number': field('最小值', c, 'minimum', 'number'); field('最大值', c, 'maximum', 'number')
            if kind == 'cloud':
                field('预览点数', c, 'maxPoints', 'integer', low=100, high=30000); field('点大小', c, 'pointSize', 'integer', low=1, high=6)
                field('初始视角', c, 'initialView', options=[('iso', '等轴测'), ('top', '俯视'), ('front', '正视')])
            if kind == 'trend': field('保留样本数', c, 'capacity', 'integer', low=20, high=1000)
            if kind == 'alarm':
                field('判断方式', c, 'comparison', options=[('gte', '大于等于'), ('gt', '大于'), ('lte', '小于等于'), ('lt', '小于'), ('eq', '等于'), ('ne', '不等于'), ('is_true', '开关为是'), ('is_false', '开关为否')], rebuild=True)
                if c['comparison'] not in ('is_true', 'is_false'):
                    threshold = QPushButton(value_summary(c.get('threshold'))); threshold.clicked.connect(lambda: self.edit_threshold(c)); form.addRow('报警阈值', threshold)
                if c['comparison'] in ('gt', 'gte', 'lt', 'lte'): field('恢复回差', c, 'hysteresis', 'number')
                field('稳定样本数', c, 'stableSamples', 'integer', low=1, high=100); field('报警级别', c, 'severity', options=[('info', '提示'), ('warning', '警告'), ('critical', '严重')])
            if 'binding' in c:
                binding = c['binding']; sources = ['result'] if kind == 'cloud' else ['source', 'result'] if kind == 'image' else ['flow', 'global', 'module'] if kind == 'input' else ['flow', 'global', 'module', 'result', 'status']
                field('数据来源', binding, 'source', options=[(s, SOURCES[s]) for s in sources], rebuild=True)
                if binding.get('source') in ('module', 'result'): field('绑定模块', binding, 'nodeId', options=[(s['id'], s.get('name', s['id'])) for s in self.document.project['steps']])
                if kind not in ('image', 'cloud'): field('变量 / 字段路径', binding, 'path')
            if len(pages(self.draft)) > 1:
                target = QComboBox()
                for p in pages(self.draft): target.addItem(p['title'], page_id(p, self.draft))
                target.setCurrentIndex(target.findData(self.active_page)); form.addRow('组件目标页', target)
                move = QPushButton('移动组件到所选页面'); move.clicked.connect(lambda: self.guard(lambda: self.move_component(target.currentData()))); form.addRow(move)
        old = self.properties_scroll.takeWidget(); self.properties_scroll.setWidget(container)
        if old: old.deleteLater()
        self.properties_scroll.setEnabled(not self.preview.currentData() and not self.is_running() and not self.stale)

    def change_property(self, target, key, value, rebuild=False):
        if self.is_running() or self.stale or self.preview.currentData() or self._rendering: return
        old = deepcopy(target); target[key] = value
        c = self.current_component()
        if c:
            if key == 'action' and value == 'navigate': c.setdefault('targetPageId', self.active_page)
            if key == 'dataType' and value == 'number': c.setdefault('minimum', -1000000); c.setdefault('maximum', 1000000)
            if key == 'comparison':
                if value in ('is_true', 'is_false', 'eq', 'ne'): c['hysteresis'] = 0
                if value in ('gt', 'gte', 'lt', 'lte') and not type_matches(c.get('threshold'), 'number'): c['threshold'] = 0
            if key == 'source':
                if value in ('module', 'result'): target.setdefault('nodeId', self.document.project['steps'][0]['id'] if self.document.project['steps'] else 'missing')
                if c['type'] in ('image', 'cloud'): target['path'] = ''
                elif value == 'status': target['path'] = 'state'
        try: validate_layout(self.draft)
        except ValueError:
            target.clear(); target.update(old); self.properties(); raise
        self.message.setText('草稿已修改；应用后保存工程。'); self.render()

    def edit_threshold(self, c):
        dialog = TypedValueDialog(c.get('threshold'), self)
        if dialog.exec() == QDialog.DialogCode.Accepted: self.guard(lambda: self.change_property(c, 'threshold', dialog.value))

    def move_component(self, target_id):
        if target_id == self.active_page or self.is_running(): return
        c = self.current_component()
        if not c: return
        target = next(p for p in pages(self.draft) if page_id(p, self.draft) == target_id)
        if len(target['components']) >= 50 or c['h'] > target['rows']: raise ValueError('目标页组件已满或组件高度超过目标页')
        self.current_page()['components'].remove(c); c['y'] = min(c['y'], target['rows'] - c['h']); target['components'].append(c); self.active_page = target_id; self.render()

    def apply_layout(self):
        if self.is_running() or self.stale: raise ValueError('运行中或工程已变更，不能应用组态')
        validate_layout(self.draft)
        project = deepcopy(self.document.project); project['hmi'] = deepcopy(self.draft)
        self._applying = True
        try: self.document.commit(project)
        finally: self._applying = False
        self.original = deepcopy(self.draft); self.message.setText('运行画面已应用，请保存工程。')

    def component_action(self, c):
        def execute():
            if c['action'] == 'navigate':
                if any(card.pending or card.saving for card in self.cards): raise ValueError('请先写入或放弃当前页待写值')
                self.active_page = c['targetPageId']; self.render()
            elif c['action'] == 'run':
                if self.busy or self.state.get('status', {}).get('state') == 'running': return
                self.apply_layout(); self.run_requested.emit()
            elif c['action'] == 'stop': self.stop_requested.emit()
        self.guard(execute)

    def write_input(self, card):
        def write():
            if self.busy or self.state.get('status', {}).get('state') == 'running': raise ValueError('运行中不可写入变量')
            c = card.c; binding = c['binding']; snapshot = deepcopy(self.state.get('variables', {}))
            if type(snapshot.get('revision')) is not int: raise ValueError('请等待读取运行变量')
            value = card.field.currentData() if c['dataType'] == 'boolean' else card.field.text()
            if c['dataType'] == 'number':
                try: value = float(value)
                except ValueError: raise ValueError('请输入有效数值') from None
                if not math.isfinite(value) or not c['minimum'] <= value <= c['maximum']: raise ValueError('数值超出输入范围')
            self.apply_layout()
            target = snapshot.get('modules', {}).get(binding.get('nodeId')) if binding['source'] == 'module' else snapshot.get(binding['source'])
            if not isinstance(target, dict): raise ValueError('绑定作用域或模块不存在')
            target[binding['path']] = value; card.saving = True; card.refresh()
            self.pending[self.backend.request('variables/set', {'project': deepcopy(self.document.project), 'state': snapshot, 'revision': snapshot['revision']})] = ('write', card)
        self.guard(write)

    def acknowledge(self, event, comment=''):
        if self.stale: return
        self.pending[self.backend.request('monitor/ack', {'projectId': self.project_id, 'id': event['id'], 'comment': comment})] = ('ack', None)
