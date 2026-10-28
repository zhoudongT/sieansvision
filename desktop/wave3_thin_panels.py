"""Wave3 薄壳：格式化 / 输出图像 / 协议解析 / 文本保存 / 预处理 / 图像显示 — 设计态可用."""
from copy import deepcopy

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTabWidget, QFormLayout, QLineEdit,
    QComboBox, QScrollArea, QFrame, QPlainTextEdit, QSpinBox, QHBoxLayout,
    QPushButton, QFileDialog,
)

from desktop.widgets.switch import OrangeSwitch


def normalize_format_data_params(params=None):
    p = deepcopy(params or {})
    p.setdefault('template', '{0}')
    p.setdefault('args', '')
    p.setdefault('targetVar', 'formatted')
    p.setdefault('scope', 'flow')
    p.setdefault('encoding', 'utf-8')
    p.setdefault('trim', False)
    p.setdefault('onEmpty', 'keep')  # keep | skip | default
    p.setdefault('emptyDefault', '')
    return p


def normalize_output_image_params(params=None):
    p = deepcopy(params or {})
    p.setdefault('path', '')
    p.setdefault('format', 'png')
    p.setdefault('quality', 95)
    p.setdefault('useTimestamp', True)
    p.setdefault('onlyOnOk', False)
    p.setdefault('okVar', 'passGate')
    p.setdefault('filePrefix', 'img')
    p.setdefault('createDir', True)
    p.setdefault('overwrite', True)
    return p


def normalize_protocol_parse_params(params=None):
    p = deepcopy(params or {})
    p.setdefault('sourceVar', 'recvData')
    p.setdefault('sourceScope', 'flow')
    p.setdefault('protocol', 'delimited')  # delimited | fixed | json | regex
    p.setdefault('delimiter', ',')
    p.setdefault('pattern', '')
    p.setdefault('fields', 'f0,f1,f2')
    p.setdefault('fixedWidths', '8,8,16')
    p.setdefault('targetPrefix', 'parsed_')
    p.setdefault('sample', '')
    return p


def normalize_text_save_params(params=None):
    p = deepcopy(params or {})
    p.setdefault('path', '')
    p.setdefault('content', '')
    p.setdefault('sourceVar', '')
    p.setdefault('append', True)
    p.setdefault('encoding', 'utf-8')
    p.setdefault('newline', True)
    p.setdefault('bom', False)
    p.setdefault('timestampPrefix', False)
    return p


class _ShellBase(QWidget):
    changed = Signal(dict)

    def __init__(self, step, project, title, hint, normalize, parent=None):
        super().__init__(parent)
        self.step = deepcopy(step)
        self.project = project or {}
        self.params = normalize(step.get('params'))
        self.step['params'] = self.params
        self._title = title
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        lab = QLabel(hint)
        lab.setWordWrap(True)
        lab.setStyleSheet('color:#666;padding:8px 10px 4px;')
        root.addWidget(lab)
        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)
        self.tabs.addTab(self._wrap(self._basic_tab()), '基本参数')
        self.tabs.addTab(self._wrap(self._result_tab()), '结果显示')

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


    # ---- incomplete banner (parity with OutputImage / config_status) ----
    def _missing_fields(self):
        """Override in subclasses: list of Chinese labels for incomplete fields."""
        return []

    def _ensure_incomplete_banner(self, form):
        self._incomplete_banner = QLabel()
        self._incomplete_banner.setWordWrap(True)
        form.addRow(self._incomplete_banner)
        self._refresh_incomplete_banner()

    def _refresh_incomplete_banner(self):
        if not hasattr(self, '_incomplete_banner') or self._incomplete_banner is None:
            return
        from desktop.config_status import step_incomplete, step_incomplete_reason
        bang = step_incomplete(self.step, self.project)
        if bang:
            why = step_incomplete_reason(self.step, self.project) or ''
            missing = self._missing_fields()
            detail = why or ('、'.join(missing) if missing else '请检查必填项')
            self._incomplete_banner.setText(
                '⚠ 组件参数未配置完整：' + detail
            )
            self._incomplete_banner.setStyleSheet(
                'color:#c62828;background:#ffebee;padding:6px 8px;border-radius:3px;'
            )
        else:
            self._incomplete_banner.setText('组件配置完成')
            self._incomplete_banner.setStyleSheet('color:#2e7d32;padding:4px 8px;')
        self._incomplete_banner.setObjectName('incompleteBanner')
        self._incomplete_banner.setVisible(True)

    def _name_row(self, form, default):
        name = QLineEdit(self.step.get('name') or default)
        name.setMaxLength(80)
        name.editingFinished.connect(lambda: self._set_top('name', name.text()))
        form.addRow('模块名称', name)

    def _basic_tab(self):
        raise NotImplementedError

    def _result_tab(self):
        w = QWidget()
        form = QFormLayout(w)
        form.setContentsMargins(10, 10, 10, 10)
        tip = QLabel('设计态配置已保存；运行结果见引擎字段 / 模块结果图。')
        tip.setStyleSheet('color:#888;')
        form.addRow(tip)
        keys = QLabel(
            'format_data → formatted/status；output_image → path/status(skipped_ng)；'
            'protocol_parse → fields；text_save → bytes/bom/timestampPrefix。'
        )
        keys.setWordWrap(True)
        form.addRow('输出字段', keys)
        return w


class FormatDataPanel(_ShellBase):
    def __init__(self, step, definition, project, parent=None):
        super().__init__(
            step, project, '格式化',
            '对齐 VisionMaster「格式化（发出数据）」：模板字符串 + 参数 → 写入变量。',
            normalize_format_data_params, parent,
        )

    def _missing_fields(self):
        missing = []
        if not str(self.params.get('template') or '').strip():
            missing.append('模板')
        return missing

    def _set_param(self, key, value):
        super()._set_param(key, value)
        if key == 'template':
            self._refresh_incomplete_banner()

    def _basic_tab(self):
        w = QWidget(); form = QFormLayout(w); form.setContentsMargins(10, 10, 10, 10)
        self._name_row(form, '格式化')
        self._ensure_incomplete_banner(form)
        tpl = QPlainTextEdit(); tpl.setPlainText(str(self.params.get('template') or '{0}'))
        tpl.setMaximumHeight(80)
        def _live_tpl():
            self.params['template'] = tpl.toPlainText()
            self.step['params'] = self.params
            self._refresh_incomplete_banner()
            self._emit()
        tpl.textChanged.connect(_live_tpl)
        form.addRow('模板', tpl)
        args = QLineEdit(str(self.params.get('args') or ''))
        args.setPlaceholderText('参数列表，逗号分隔或变量名')
        args.editingFinished.connect(lambda: self._set_param('args', args.text().strip()))
        from desktop.upstream_field_picker import fill_line_from_picker
        _args_row = QHBoxLayout()
        _args_pick = QPushButton('插入上游字段')
        _args_pick.clicked.connect(lambda *_: fill_line_from_picker(
            self, self.project, self.step.get('id'), args, self._set_param, 'args'))
        _args_row.addWidget(args, 1)
        _args_row.addWidget(_args_pick)
        form.addRow('参数', _args_row)
        var = QLineEdit(str(self.params.get('targetVar') or 'formatted'))
        var.editingFinished.connect(lambda: self._set_param('targetVar', var.text().strip() or 'formatted'))
        from desktop.upstream_field_picker import fill_line_from_picker
        _var_row = QHBoxLayout()
        _var_pick = QPushButton('插入上游字段')
        _var_pick.clicked.connect(lambda *_: fill_line_from_picker(
            self, self.project, self.step.get('id'), var, self._set_param, 'targetVar'))
        _var_row.addWidget(var, 1)
        _var_row.addWidget(_var_pick)
        form.addRow('目标变量', _var_row)
        scope = QComboBox()
        for v, lab in (('flow', '流程'), ('global', '全局'), ('module', '模块')):
            scope.addItem(lab, v)
        scope.setCurrentIndex(max(0, scope.findData(self.params.get('scope') or 'flow')))
        scope.currentIndexChanged.connect(lambda _: self._set_param('scope', scope.currentData()))
        form.addRow('变量作用域', scope)
        enc = QComboBox()
        for e in ('utf-8', 'gbk', 'ascii'):
            enc.addItem(e, e)
        enc.setCurrentIndex(max(0, enc.findData(self.params.get('encoding') or 'utf-8')))
        enc.currentIndexChanged.connect(lambda _: self._set_param('encoding', enc.currentData()))
        form.addRow('编码', enc)
        trim = OrangeSwitch(bool(self.params.get('trim', False)))
        trim.toggled.connect(lambda c: self._set_param('trim', bool(c)))
        form.addRow('去空白', trim)
        empty = QComboBox()
        for v, lab in (('keep', '保留空'), ('skip', '跳过写入'), ('default', '用默认值')):
            empty.addItem(lab, v)
        empty.setCurrentIndex(max(0, empty.findData(self.params.get('onEmpty') or 'keep')))
        empty.currentIndexChanged.connect(lambda _: self._set_param('onEmpty', empty.currentData()))
        form.addRow('空结果', empty)
        ed = QLineEdit(str(self.params.get('emptyDefault') or ''))
        ed.editingFinished.connect(lambda: self._set_param('emptyDefault', ed.text()))
        form.addRow('空默认值', ed)
        prev = QLabel()
        prev.setWordWrap(True)
        prev.setStyleSheet('color:#555;background:#f5f5f5;padding:6px;border-radius:2px;')
        def _preview():
            tpl = str(self.params.get('template') or '')
            args = [a.strip() for a in str(self.params.get('args') or '').split(',') if a.strip()]
            try:
                if args:
                    try:
                        text = tpl.format(*args)
                    except Exception:
                        text = tpl.format(**{f'{i}': a for i, a in enumerate(args)})
                else:
                    text = tpl
            except Exception as exc:
                text = f'(预览失败: {exc})'
            prev.setText('预览：' + text)
        _preview()
        # refresh when template/args change — hook via existing edits already emit; button for force
        btn = QPushButton('刷新预览')
        btn.clicked.connect(_preview)
        form.addRow(prev)
        form.addRow(btn)
        tip = QLabel('模板支持 {0}/{name}；未填模板时节点红叹号。')
        tip.setStyleSheet('color:#888;')
        form.addRow(tip)
        return w


class OutputImagePanel(_ShellBase):
    def __init__(self, step, definition, project, parent=None):
        super().__init__(
            step, project, '输出图像',
            '对齐 VisionMaster「输出(保存)图像」：保存上游图像到文件。',
            normalize_output_image_params, parent,
        )

    def _missing_fields(self):
        missing = []
        if not self.step.get('imageFrom'):
            missing.append('输入源(imageFrom)')
        if not str(self.params.get('path') or '').strip():
            missing.append('保存路径')
        return missing

    def _set_param(self, key, value):
        super()._set_param(key, value)
        if key == 'path':
            self._refresh_incomplete_banner()

    def _set_top(self, key, value):
        super()._set_top(key, value)
        if key == 'imageFrom':
            self._refresh_incomplete_banner()

    def _basic_tab(self):
        w = QWidget(); form = QFormLayout(w); form.setContentsMargins(10, 10, 10, 10)
        self._name_row(form, '输出图像')
        self._ensure_incomplete_banner(form)
        image_from = QComboBox()
        image_from.addItem('（无图像输入）', None)
        incoming = {e['from'] for e in self.project.get('edges', []) if e.get('to') == self.step.get('id')}
        index_map = {'source': 0}; names = {'source': '图像源1'}
        for i, s in enumerate(self.project.get('steps', []), start=1):
            index_map[s['id']] = i; names[s['id']] = s.get('name', s['id'])
        def _sub(n): return f"{index_map.get(n,'?')} {names.get(n,n)}.图像"
        for node in sorted(incoming, key=lambda n: (index_map.get(n, 999), n)):
            image_from.addItem(_sub(node), node)
        # Soft candidates: locate/geometry/preprocess even without edge (densify picker)
        soft_ops = ('locate', 'geometry_find', 'preprocess', 'pose_correct', 'distort_correct')
        for s in self.project.get('steps', []):
            if s.get('id') == self.step.get('id'):
                continue
            if s.get('operation') in soft_ops and image_from.findData(s['id']) < 0:
                image_from.addItem(_sub(s['id']) + '（可选）', s['id'])
        cur = self.step.get('imageFrom')
        if cur and image_from.findData(cur) < 0:
            image_from.addItem('已断开：'+_sub(cur), cur)
        image_from.setCurrentIndex(max(0, image_from.findData(cur)))
        image_from.currentIndexChanged.connect(lambda _: self._set_top('imageFrom', image_from.currentData()))
        self._image_from = image_from
        form.addRow('输入源', image_from)
        row = QHBoxLayout()
        path = QLineEdit(str(self.params.get('path') or ''))
        path.setPlaceholderText('保存目录或文件路径')
        path.editingFinished.connect(lambda: self._set_param('path', path.text().strip()))
        def _live_path(text):
            self.params['path'] = (text or '').strip()
            self.step['params'] = self.params
            self._refresh_incomplete_banner()
        path.textChanged.connect(_live_path)
        self._path_edit = path
        browse = QPushButton('浏览…')
        def _b():
            d = QFileDialog.getExistingDirectory(self, '选择保存目录')
            if d:
                path.setText(d); self._set_param('path', d)
        browse.clicked.connect(lambda *_: _b())
        row.addWidget(path, 1); row.addWidget(browse)
        form.addRow('保存路径', row)
        self._refresh_incomplete_banner()
        fmt = QComboBox()
        for f in ('png', 'jpg', 'bmp', 'tif'):
            fmt.addItem(f, f)
        fmt.setCurrentIndex(max(0, fmt.findData(self.params.get('format') or 'png')))
        fmt.currentIndexChanged.connect(lambda _: self._set_param('format', fmt.currentData()))
        form.addRow('格式', fmt)
        q = QSpinBox(); q.setRange(1, 100); q.setValue(int(self.params.get('quality') or 95))
        q.valueChanged.connect(lambda v: self._set_param('quality', int(v)))
        form.addRow('质量', q)
        ts = OrangeSwitch(bool(self.params.get('useTimestamp', True)))
        ts.toggled.connect(lambda c: self._set_param('useTimestamp', bool(c)))
        form.addRow('文件名加时间戳', ts)
        prefix = QLineEdit(str(self.params.get('filePrefix') or 'img'))
        prefix.editingFinished.connect(lambda: self._set_param('filePrefix', prefix.text().strip() or 'img'))
        form.addRow('文件名前缀', prefix)
        ok_only = OrangeSwitch(bool(self.params.get('onlyOnOk', False)))
        ok_only.toggled.connect(lambda c: self._set_param('onlyOnOk', bool(c)))
        form.addRow('仅 OK 时保存', ok_only)
        ok_var = QLineEdit(str(self.params.get('okVar') or 'passGate'))
        ok_var.editingFinished.connect(lambda: self._set_param('okVar', ok_var.text().strip() or 'passGate'))
        ok_var.setToolTip('仅 OK 时保存：读取流程/全局变量（默认 passGate）')
        form.addRow('OK 变量', ok_var)
        mkdir = OrangeSwitch(bool(self.params.get('createDir', True)))
        mkdir.toggled.connect(lambda c: self._set_param('createDir', bool(c)))
        form.addRow('自动建目录', mkdir)
        ow = OrangeSwitch(bool(self.params.get('overwrite', True)))
        ow.toggled.connect(lambda c: self._set_param('overwrite', bool(c)))
        form.addRow('允许覆盖', ow)
        tip = QLabel('未选输入源或路径为空时节点红叹号。')
        tip.setStyleSheet('color:#888;')
        form.addRow(tip)
        return w


class ProtocolParsePanel(_ShellBase):
    def __init__(self, step, definition, project, parent=None):
        super().__init__(
            step, project, '协议解析',
            '对齐 VisionMaster「协议解析」：从接收变量解析字段。',
            normalize_protocol_parse_params, parent,
        )

    def _missing_fields(self):
        missing = []
        if not str(self.params.get('sourceVar') or '').strip():
            missing.append('源变量')
        return missing

    def _set_param(self, key, value):
        super()._set_param(key, value)
        if key == 'sourceVar':
            self._refresh_incomplete_banner()

    def _basic_tab(self):
        w = QWidget(); form = QFormLayout(w); form.setContentsMargins(10, 10, 10, 10)
        self._name_row(form, '协议解析')
        self._ensure_incomplete_banner(form)
        src = QLineEdit(str(self.params.get('sourceVar') or ''))
        src.setPlaceholderText('接收数据变量名，如 recvData')
        src.editingFinished.connect(lambda: self._set_param('sourceVar', src.text().strip()))
        def _live_src(text):
            self.params['sourceVar'] = (text or '').strip()
            self.step['params'] = self.params
            self._refresh_incomplete_banner()
        src.textChanged.connect(_live_src)
        self._source_var_edit = src
        from desktop.upstream_field_picker import fill_line_from_picker
        _src_row = QHBoxLayout()
        _src_pick = QPushButton('插入上游字段')
        _src_pick.clicked.connect(lambda *_: fill_line_from_picker(
            self, self.project, self.step.get('id'), src, self._set_param, 'sourceVar'))
        _src_row.addWidget(src, 1)
        _src_row.addWidget(_src_pick)
        form.addRow('源变量', _src_row)
        proto = QComboBox()
        for v, lab in (('delimited', '分隔符'), ('fixed', '定长'), ('json', 'JSON'), ('regex', '正则')):
            proto.addItem(lab, v)
        proto.setCurrentIndex(max(0, proto.findData(self.params.get('protocol') or 'delimited')))
        proto.currentIndexChanged.connect(lambda _: self._set_param('protocol', proto.currentData()))
        form.addRow('协议类型', proto)
        delim = QLineEdit(str(self.params.get('delimiter') or ','))
        delim.editingFinished.connect(lambda: self._set_param('delimiter', delim.text()))
        form.addRow('分隔符', delim)
        fields = QLineEdit(str(self.params.get('fields') or 'f0,f1,f2'))
        fields.editingFinished.connect(lambda: self._set_param('fields', fields.text().strip()))
        form.addRow('字段名', fields)
        pat = QLineEdit(str(self.params.get('pattern') or ''))
        pat.setPlaceholderText('正则模式（protocol=regex）')
        pat.editingFinished.connect(lambda: self._set_param('pattern', pat.text()))
        form.addRow('正则', pat)
        widths = QLineEdit(str(self.params.get('fixedWidths') or '8,8,16'))
        widths.setPlaceholderText('定长宽度，逗号分隔')
        widths.editingFinished.connect(lambda: self._set_param('fixedWidths', widths.text().strip()))
        form.addRow('定长宽度', widths)
        prefix = QLineEdit(str(self.params.get('targetPrefix') or 'parsed_'))
        prefix.editingFinished.connect(lambda: self._set_param('targetPrefix', prefix.text()))
        form.addRow('字段前缀', prefix)
        scope = QComboBox()
        for v, lab in (('flow', '流程'), ('global', '全局')):
            scope.addItem(lab, v)
        scope.setCurrentIndex(max(0, scope.findData(self.params.get('sourceScope') or 'flow')))
        scope.currentIndexChanged.connect(lambda _: self._set_param('sourceScope', scope.currentData()))
        form.addRow('源作用域', scope)
        sample = QPlainTextEdit()
        sample.setPlainText(str(self.params.get('sample') or ''))
        sample.setMaximumHeight(70)
        sample.setPlaceholderText('样例报文（仅设计态预览）')
        sample.textChanged.connect(lambda: self._set_param('sample', sample.toPlainText()))
        form.addRow('样例', sample)
        tip = QLabel('源变量为空时节点红叹号。运行写回 parsed_* 字段。')
        tip.setStyleSheet('color:#888;')
        form.addRow(tip)
        return w


class TextSavePanel(_ShellBase):
    def __init__(self, step, definition, project, parent=None):
        super().__init__(
            step, project, '文本保存',
            '对齐 VisionMaster「文本保存」：写入/追加文本到文件。',
            normalize_text_save_params, parent,
        )

    def _missing_fields(self):
        missing = []
        if not str(self.params.get('path') or '').strip():
            missing.append('文件路径')
        return missing

    def _set_param(self, key, value):
        super()._set_param(key, value)
        if key == 'path':
            self._refresh_incomplete_banner()

    def _basic_tab(self):
        w = QWidget(); form = QFormLayout(w); form.setContentsMargins(10, 10, 10, 10)
        self._name_row(form, '文本保存')
        self._ensure_incomplete_banner(form)
        row = QHBoxLayout()
        path = QLineEdit(str(self.params.get('path') or ''))
        path.setPlaceholderText('文件路径')
        path.editingFinished.connect(lambda: self._set_param('path', path.text().strip()))
        def _live_path(text):
            self.params['path'] = (text or '').strip()
            self.step['params'] = self.params
            self._refresh_incomplete_banner()
        path.textChanged.connect(_live_path)
        browse = QPushButton('浏览…')
        def _b():
            f, _ = QFileDialog.getSaveFileName(self, '文本文件', '', '文本 (*.txt *.csv *.log);;全部 (*)')
            if f:
                path.setText(f); self._set_param('path', f)
        browse.clicked.connect(_b)
        row.addWidget(path, 1); row.addWidget(browse)
        form.addRow('文件路径', row)
        content = QPlainTextEdit(); content.setPlainText(str(self.params.get('content') or ''))
        content.setMaximumHeight(100)
        content.textChanged.connect(lambda: self._set_param('content', content.toPlainText()))
        form.addRow('内容', content)
        svar = QLineEdit(str(self.params.get('sourceVar') or ''))
        svar.setPlaceholderText('若填写则优先用变量内容')
        svar.editingFinished.connect(lambda: self._set_param('sourceVar', svar.text().strip()))
        from desktop.upstream_field_picker import fill_line_from_picker
        _svar_row = QHBoxLayout()
        _svar_pick = QPushButton('插入上游字段')
        _svar_pick.clicked.connect(lambda *_: fill_line_from_picker(
            self, self.project, self.step.get('id'), svar, self._set_param, 'sourceVar'))
        _svar_row.addWidget(svar, 1)
        _svar_row.addWidget(_svar_pick)
        form.addRow('源变量', _svar_row)
        ap = OrangeSwitch(bool(self.params.get('append', True)))
        ap.toggled.connect(lambda c: self._set_param('append', bool(c)))
        form.addRow('追加写入', ap)
        enc = QComboBox()
        for e in ('utf-8', 'gbk', 'ascii'):
            enc.addItem(e, e)
        enc.setCurrentIndex(max(0, enc.findData(self.params.get('encoding') or 'utf-8')))
        enc.currentIndexChanged.connect(lambda _: self._set_param('encoding', enc.currentData()))
        form.addRow('编码', enc)
        nl = OrangeSwitch(bool(self.params.get('newline', True)))
        nl.toggled.connect(lambda c: self._set_param('newline', bool(c)))
        form.addRow('末尾换行', nl)
        bom = OrangeSwitch(bool(self.params.get('bom', False)))
        bom.toggled.connect(lambda c: self._set_param('bom', bool(c)))
        form.addRow('写 BOM', bom)
        tsp = OrangeSwitch(bool(self.params.get('timestampPrefix', False)))
        tsp.toggled.connect(lambda c: self._set_param('timestampPrefix', bool(c)))
        form.addRow('行首时间戳', tsp)
        tip = QLabel('路径为空时节点红叹号。')
        tip.setStyleSheet('color:#888;')
        form.addRow(tip)
        return w


def normalize_preprocess_params(params=None):
    p = deepcopy(params or {})
    p.setdefault('method', 'grayscale')
    p.setdefault('threshold', 127)
    p.setdefault('kernel', 3)
    p.setdefault('cannyLow', 50)
    p.setdefault('cannyHigh', 150)
    p.setdefault('invert', False)
    p.setdefault('blur', 1)
    return p


def normalize_display_params(params=None):
    """图像显示（薄壳）：订阅上游图像并可选标注开关 — 对齐 VM 图像显示组."""
    p = deepcopy(params or {})
    p.setdefault('showOverlay', True)
    p.setdefault('showName', True)
    p.setdefault('fitMode', 'contain')  # contain | cover | actual
    p.setdefault('channel', 'auto')  # auto | r | g | b | gray
    return p


class PreprocessPanel(_ShellBase):
    def __init__(self, step, definition, project, parent=None):
        super().__init__(
            step, project, '图像预处理',
            '对齐 VisionMaster「图像预处理」：灰度 / 模糊 / 二值 / Canny / 形态学。',
            normalize_preprocess_params, parent,
        )

    def _missing_fields(self):
        missing = []
        if not self.step.get('imageFrom'):
            missing.append('输入源(imageFrom)')
        return missing

    def _set_top(self, key, value):
        super()._set_top(key, value)
        if key == 'imageFrom':
            self._refresh_incomplete_banner()

    def _basic_tab(self):
        w = QWidget(); form = QFormLayout(w); form.setContentsMargins(10, 10, 10, 10)
        self._name_row(form, '图像预处理')
        self._ensure_incomplete_banner(form)
        image_from = QComboBox()
        image_from.addItem('（无图像输入）', None)
        incoming = {e['from'] for e in self.project.get('edges', []) if e.get('to') == self.step.get('id')}
        index_map = {'source': 0}; names = {'source': '图像源1'}
        for i, s in enumerate(self.project.get('steps', []), start=1):
            index_map[s['id']] = i; names[s['id']] = s.get('name', s['id'])
        def _sub(n): return f"{index_map.get(n,'?')} {names.get(n,n)}.图像"
        for node in sorted(incoming, key=lambda n: (index_map.get(n, 999), n)):
            image_from.addItem(_sub(node), node)
        soft_ops = ('locate', 'geometry', 'preprocess', 'pose_correct', 'distort_correct', 'output_image')
        for s in self.project.get('steps', []):
            if s.get('id') == self.step.get('id'):
                continue
            if s.get('operation') in soft_ops and image_from.findData(s['id']) < 0:
                image_from.addItem(_sub(s['id']) + '（可选）', s['id'])
        # Always offer source
        if image_from.findData('source') < 0:
            image_from.addItem(_sub('source') + '（可选）', 'source')
        cur = self.step.get('imageFrom')
        if cur and image_from.findData(cur) < 0:
            image_from.addItem('已断开：' + _sub(cur), cur)
        image_from.setCurrentIndex(max(0, image_from.findData(cur)))
        image_from.currentIndexChanged.connect(lambda _: self._set_top('imageFrom', image_from.currentData()))
        self._image_from = image_from
        form.addRow('输入源', image_from)

        method = QComboBox()
        for val, lab in (
            ('grayscale', '灰度化'), ('blur', '高斯模糊'), ('threshold', '二值化'),
            ('canny', '边缘提取'), ('open', '开运算'), ('close', '闭运算'),
        ):
            method.addItem(lab, val)
        method.setCurrentIndex(max(0, method.findData(self.params.get('method') or 'grayscale')))
        method.currentIndexChanged.connect(lambda _: self._set_param('method', method.currentData()))
        form.addRow('处理方法', method)

        thr = QSpinBox(); thr.setRange(0, 255); thr.setValue(int(self.params.get('threshold') or 127))
        thr.valueChanged.connect(lambda v: self._set_param('threshold', int(v)))
        form.addRow('二值阈值', thr)

        ker = QSpinBox(); ker.setRange(1, 51); ker.setSingleStep(2)
        ker.setValue(int(self.params.get('kernel') or 3))
        ker.valueChanged.connect(lambda v: self._set_param('kernel', int(v) if int(v) % 2 else int(v) + 1))
        form.addRow('核大小（奇数）', ker)

        lo = QSpinBox(); lo.setRange(0, 255); lo.setValue(int(self.params.get('cannyLow') or 50))
        lo.valueChanged.connect(lambda v: self._set_param('cannyLow', int(v)))
        form.addRow('Canny 低阈值', lo)
        hi = QSpinBox(); hi.setRange(0, 255); hi.setValue(int(self.params.get('cannyHigh') or 150))
        hi.valueChanged.connect(lambda v: self._set_param('cannyHigh', int(v)))
        form.addRow('Canny 高阈值', hi)

        inv = OrangeSwitch(bool(self.params.get('invert', False)))
        inv.toggled.connect(lambda c: self._set_param('invert', bool(c)))
        form.addRow('反色', inv)

        tip = QLabel('未选输入源时节点红叹号（config_status.preprocess）。')
        tip.setStyleSheet('color:#888;')
        form.addRow(tip)
        self._refresh_incomplete_banner()
        return w


class DisplayPanel(_ShellBase):
    """图像显示薄壳 — incompleteBanner harvest 与预处理/输出图像对齐."""

    def __init__(self, step, definition, project, parent=None):
        super().__init__(
            step, project, '图像显示',
            '对齐 VisionMaster「图像显示」：订阅上游图像，设计态预览开关。',
            normalize_display_params, parent,
        )

    def _missing_fields(self):
        missing = []
        if not self.step.get('imageFrom'):
            missing.append('输入源(imageFrom)')
        return missing

    def _set_top(self, key, value):
        super()._set_top(key, value)
        if key == 'imageFrom':
            self._refresh_incomplete_banner()

    def _basic_tab(self):
        w = QWidget(); form = QFormLayout(w); form.setContentsMargins(10, 10, 10, 10)
        self._name_row(form, '图像显示')
        self._ensure_incomplete_banner(form)
        image_from = QComboBox()
        image_from.addItem('（无图像输入）', None)
        incoming = {e['from'] for e in self.project.get('edges', []) if e.get('to') == self.step.get('id')}
        index_map = {'source': 0}; names = {'source': '图像源1'}
        for i, s in enumerate(self.project.get('steps', []), start=1):
            index_map[s['id']] = i; names[s['id']] = s.get('name', s['id'])
        def _sub(n): return f"{index_map.get(n,'?')} {names.get(n,n)}.图像"
        for node in sorted(incoming, key=lambda n: (index_map.get(n, 999), n)):
            image_from.addItem(_sub(node), node)
        soft_ops = ('locate', 'geometry', 'preprocess', 'pose_correct', 'output_image')
        for s in self.project.get('steps', []):
            if s.get('id') == self.step.get('id'):
                continue
            if s.get('operation') in soft_ops and image_from.findData(s['id']) < 0:
                image_from.addItem(_sub(s['id']) + '（可选）', s['id'])
        if image_from.findData('source') < 0:
            image_from.addItem(_sub('source') + '（可选）', 'source')
        cur = self.step.get('imageFrom')
        if cur and image_from.findData(cur) < 0:
            image_from.addItem('已断开：' + _sub(cur), cur)
        image_from.setCurrentIndex(max(0, image_from.findData(cur)))
        image_from.currentIndexChanged.connect(lambda _: self._set_top('imageFrom', image_from.currentData()))
        self._image_from = image_from
        form.addRow('输入源', image_from)

        ov = OrangeSwitch(bool(self.params.get('showOverlay', True)))
        ov.toggled.connect(lambda c: self._set_param('showOverlay', bool(c)))
        form.addRow('显示叠加', ov)
        sn = OrangeSwitch(bool(self.params.get('showName', True)))
        sn.toggled.connect(lambda c: self._set_param('showName', bool(c)))
        form.addRow('显示名称', sn)
        fit = QComboBox()
        for val, lab in (('contain', '适应'), ('cover', '铺满'), ('actual', '实际像素')):
            fit.addItem(lab, val)
        fit.setCurrentIndex(max(0, fit.findData(self.params.get('fitMode') or 'contain')))
        fit.currentIndexChanged.connect(lambda _: self._set_param('fitMode', fit.currentData()))
        form.addRow('适应模式', fit)
        ch = QComboBox()
        for val, lab in (
            ('auto', '自动'), ('r', 'R 红'), ('g', 'G 绿'), ('b', 'B 蓝'), ('gray', '灰度'),
        ):
            ch.addItem(lab, val)
        ch.setCurrentIndex(max(0, ch.findData(self.params.get('channel') or 'auto')))
        ch.currentIndexChanged.connect(lambda _: self._set_param('channel', ch.currentData()))
        form.addRow('通道', ch)
        tip = QLabel('适应模式/通道 → 模块结果即时生效；未选输入源时红叹号。')
        tip.setStyleSheet('color:#888;')
        form.addRow(tip)
        self._refresh_incomplete_banner()
        return w
