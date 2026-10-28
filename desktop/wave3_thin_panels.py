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
    p.setdefault('dateSubdir', False)       # YYYY-MM-DD under path
    p.setdefault('ngSubdir', 'NG')          # when onlyOnOk and NG: optional side folder name (soft)
    p.setdefault('saveAnnotated', True)    # prefer annotated if upstream has it (soft hint)
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
    p.setdefault('createDir', True)
    p.setdefault('maxLinesSoft', 0)   # 0=unlimited; design-time tip only
    p.setdefault('separator', '\t')  # between timestamp and body when timestampPrefix
    return p



def soft_format_preview(params, env=None):
    """Design-time format_data preview (mirrors engine soft path; no hardware)."""
    p = params or {}
    tpl = str(p.get('template') or '')
    args = [a.strip() for a in str(p.get('args') or '').split(',') if a.strip()]
    env = dict(env or {})
    values = []
    for tok in args:
        if tok in env:
            values.append(env[tok])
        else:
            try:
                values.append(float(tok) if '.' in tok else int(tok))
            except Exception:
                values.append(tok)
    try:
        if values:
            try:
                text = tpl.format(*values)
            except Exception:
                try:
                    text = tpl.format(**{str(i): v for i, v in enumerate(values)})
                except Exception:
                    text = tpl
                    for i, v in enumerate(values):
                        text = text.replace('{' + str(i) + '}', str(v))
                    import re as _re
                    def _named(m):
                        name = m.group(1)
                        if name in env:
                            return str(env[name])
                        # also map arg names positionally when args are identifiers
                        if name in args:
                            return str(values[args.index(name)])
                        return m.group(0)
                    text = _re.sub(r'\{([A-Za-z_][A-Za-z0-9_]*)\}', _named, text)
        else:
            text = tpl
    except Exception as exc:
        text = f'(预览失败: {exc})'
    if bool(p.get('trim')):
        text = str(text).strip()
    return str(text)


def soft_protocol_parse_preview(params, sample=None):
    """Design-time protocol_parse preview → list of 'prefix+field = value' lines."""
    p = params or {}
    sample = str(sample if sample is not None else (p.get('sample') or ''))
    proto = str(p.get('protocol') or 'delimited')
    delim = str(p.get('delimiter') or ',')
    fields = [f.strip() for f in str(p.get('fields') or '').split(',') if f.strip()]
    prefix = str(p.get('targetPrefix') or 'parsed_')
    lines = []
    parsed = {}
    try:
        if not sample.strip():
            lines.append('(无样例报文 — 在基本参数填写「样例」)')
        elif proto == 'json':
            import json as _json
            obj = _json.loads(sample)
            if isinstance(obj, dict):
                for k, v in obj.items():
                    parsed[k] = v
                    lines.append(f'{prefix}{k} = {v!r}')
            else:
                parsed['value'] = obj
                lines.append(f'{prefix}value = {obj!r}')
        elif proto == 'fixed':
            widths = [int(x) for x in str(p.get('fixedWidths') or '8,8,16').split(',') if str(x).strip()]
            pos = 0
            for i, wdt in enumerate(widths):
                chunk = sample[pos:pos + wdt]
                name = fields[i] if i < len(fields) else f'f{i}'
                parsed[name] = chunk
                lines.append(f'{prefix}{name} = {chunk!r}')
                pos += wdt
        elif proto == 'regex':
            import re as _re
            pat = str(p.get('pattern') or '')
            m = _re.search(pat, sample) if pat else None
            if not pat:
                lines.append('(未填正则)')
            elif not m:
                lines.append('(样例未匹配正则)')
            else:
                if m.groupdict():
                    for k, v in m.groupdict().items():
                        parsed[k] = v
                        lines.append(f'{prefix}{k} = {v!r}')
                else:
                    for i, g in enumerate(m.groups(), 1):
                        name = fields[i - 1] if i - 1 < len(fields) else f'g{i}'
                        parsed[name] = g
                        lines.append(f'{prefix}{name} = {g!r}')
        else:
            parts = sample.split(delim)
            for i, part in enumerate(parts):
                name = fields[i] if i < len(fields) else f'f{i}'
                parsed[name] = part
                lines.append(f'{prefix}{name} = {part!r}')
    except Exception as exc:
        lines = [f'(解析失败: {exc})']
    return lines, parsed


def soft_format_protocol_roundtrip(fmt_params, proto_params, env=None):
    """open-and-run soft path: format_data → (LocalBus body) → protocol_parse preview."""
    formatted = soft_format_preview(fmt_params, env=env)
    # if protocol expects delimited/json etc., use formatted as sample
    proto = dict(proto_params or {})
    # prefer protocol sample when present for pure-parse demos; else round-trip formatted
    sample = str(proto.get('sample') or '').strip() or formatted
    lines, parsed = soft_protocol_parse_preview(proto, sample=sample)
    scope = (fmt_params or {}).get('scope') or 'flow'
    tvar = (fmt_params or {}).get('targetVar') or 'formatted'
    src_scope = proto.get('sourceScope') or 'flow'
    src_var = proto.get('sourceVar') or 'recvData'
    meta = (
        f'round-trip soft · {scope}.{tvar} → LocalBus → {src_scope}.{src_var}'
        f' · protocol={proto.get("protocol") or "delimited"} · fields={len(parsed)}'
        f' · out_len={len(formatted)}'
    )
    block = [
        f'── format → {formatted!r}',
        f'── LocalBus soft TX/RX (inprocess, no field TCP)',
        f'── protocol parse ({proto.get("protocol") or "delimited"}):',
        *lines,
    ]
    return '\n'.join(block), meta, formatted, parsed

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
        if key in ('template', 'args', 'trim', 'targetVar', 'scope', 'encoding', 'onEmpty') and hasattr(self, '_refresh_format_result'):
            try:
                self._refresh_format_result()
            except Exception:
                pass

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



    def _result_tab(self):
        """结果显示：设计态模板预览 + format→protocol round-trip soft（open-and-run 路径）。"""
        w = QWidget()
        form = QFormLayout(w)
        form.setContentsMargins(10, 10, 10, 10)
        tip = QLabel(
            '运行后引擎写回 formatted / status；下方为设计态预览 + '
            'format→LocalBus→protocol 软往返（对齐 open-and-run-format-protocol；无现场 TCP）。'
        )
        tip.setWordWrap(True)
        tip.setStyleSheet('color:#888;')
        form.addRow(tip)
        self._fmt_result_preview = QPlainTextEdit()
        self._fmt_result_preview.setObjectName('formatDataResultPreview')
        self._fmt_result_preview.setReadOnly(True)
        self._fmt_result_preview.setMaximumHeight(100)
        form.addRow('预览输出', self._fmt_result_preview)
        self._fmt_result_meta = QLabel()
        self._fmt_result_meta.setObjectName('formatDataResultMeta')
        self._fmt_result_meta.setWordWrap(True)
        form.addRow('写入摘要', self._fmt_result_meta)
        self._fmt_roundtrip = QPlainTextEdit()
        self._fmt_roundtrip.setObjectName('formatDataRoundtripPreview')
        self._fmt_roundtrip.setReadOnly(True)
        self._fmt_roundtrip.setMaximumHeight(160)
        self._fmt_roundtrip.setStyleSheet('font-family:monospace;font-size:11px;background:#1e1e1e;color:#ffe0b2;')
        form.addRow('软往返', self._fmt_roundtrip)
        self._fmt_roundtrip_meta = QLabel()
        self._fmt_roundtrip_meta.setObjectName('formatDataRoundtripMeta')
        self._fmt_roundtrip_meta.setWordWrap(True)
        self._fmt_roundtrip_meta.setStyleSheet('color:#666;font-size:11px;')
        form.addRow('往返摘要', self._fmt_roundtrip_meta)
        btn = QPushButton('刷新结果显示')
        btn.setObjectName('formatDataResultRefresh')
        btn.clicked.connect(self._refresh_format_result)
        form.addRow(btn)
        self._refresh_format_result()
        return w

    def _refresh_format_result(self):
        text = soft_format_preview(self.params)
        if hasattr(self, '_fmt_result_preview') and self._fmt_result_preview is not None:
            self._fmt_result_preview.setPlainText(text)
        scope = self.params.get('scope') or 'flow'
        var = self.params.get('targetVar') or 'formatted'
        enc = self.params.get('encoding') or 'utf-8'
        empty = self.params.get('onEmpty') or 'keep'
        meta = f'{scope}.{var} · 编码 {enc} · 空结果={empty} · 长度 {len(text)}'
        if hasattr(self, '_fmt_result_meta') and self._fmt_result_meta is not None:
            self._fmt_result_meta.setText(meta)
        # open-and-run soft round-trip: format → protocol_parse(delimited on formatted)
        proto = {
            'protocol': 'delimited',
            'delimiter': ',',
            'fields': 'f0,f1,f2,f3,f4,f5',
            'targetPrefix': 'parsed_',
            'sourceVar': 'recvData',
            'sourceScope': 'flow',
            'sample': text,
        }
        # Prefer a sibling protocol_parse step sample/fields from project when present
        try:
            for s in (self.project or {}).get('steps') or []:
                if (s or {}).get('operation') == 'protocol_parse':
                    pp = (s.get('params') or {})
                    proto['protocol'] = pp.get('protocol') or proto['protocol']
                    proto['delimiter'] = pp.get('delimiter') or proto['delimiter']
                    proto['fields'] = pp.get('fields') or proto['fields']
                    proto['targetPrefix'] = pp.get('targetPrefix') or proto['targetPrefix']
                    proto['sourceVar'] = pp.get('sourceVar') or proto['sourceVar']
                    proto['sourceScope'] = pp.get('sourceScope') or proto['sourceScope']
                    if str(pp.get('sample') or '').strip():
                        # still round-trip formatted as payload; keep field layout
                        pass
                    break
        except Exception:
            pass
        block, rmeta, _fmt, _parsed = soft_format_protocol_roundtrip(self.params, proto)
        if hasattr(self, '_fmt_roundtrip') and self._fmt_roundtrip is not None:
            self._fmt_roundtrip.setPlainText(block)
        if hasattr(self, '_fmt_roundtrip_meta') and self._fmt_roundtrip_meta is not None:
            self._fmt_roundtrip_meta.setText(rmeta)

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
        if key in (
            'path', 'format', 'quality', 'useTimestamp', 'onlyOnOk', 'okVar',
            'filePrefix', 'createDir', 'overwrite', 'dateSubdir', 'ngSubdir', 'saveAnnotated',
        ) and hasattr(self, '_refresh_output_image_result'):
            try:
                self._refresh_output_image_result()
            except Exception:
                pass

    def _set_top(self, key, value):
        super()._set_top(key, value)
        if key == 'imageFrom':
            self._refresh_incomplete_banner()
            if hasattr(self, '_refresh_output_image_result'):
                try:
                    self._refresh_output_image_result()
                except Exception:
                    pass

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
        soft_ops = ('locate', 'geometry_find', 'preprocess', 'pose_correct', 'distort_correct', 'display')
        for s in self.project.get('steps', []):
            if s.get('id') == self.step.get('id'):
                continue
            if s.get('operation') in soft_ops and image_from.findData(s['id']) < 0:
                image_from.addItem(_sub(s['id']) + '（可选）', s['id'])
        if image_from.findData('source') < 0:
            image_from.addItem(_sub('source') + '（可选）', 'source')
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
            if hasattr(self, '_refresh_output_image_result'):
                try:
                    self._refresh_output_image_result()
                except Exception:
                    pass
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
        date_sub = OrangeSwitch(bool(self.params.get('dateSubdir', False)))
        date_sub.toggled.connect(lambda c: self._set_param('dateSubdir', bool(c)))
        form.addRow('按日期建子目录', date_sub)
        ng = QLineEdit(str(self.params.get('ngSubdir') or 'NG'))
        ng.setPlaceholderText('NG 旁路子目录名（软提示）')
        ng.editingFinished.connect(lambda: self._set_param('ngSubdir', ng.text().strip() or 'NG'))
        form.addRow('NG 子目录', ng)
        ann = OrangeSwitch(bool(self.params.get('saveAnnotated', True)))
        ann.toggled.connect(lambda c: self._set_param('saveAnnotated', bool(c)))
        form.addRow('优先保存标注图', ann)
        mkdir = OrangeSwitch(bool(self.params.get('createDir', True)))
        mkdir.toggled.connect(lambda c: self._set_param('createDir', bool(c)))
        form.addRow('自动建目录', mkdir)
        ow = OrangeSwitch(bool(self.params.get('overwrite', True)))
        ow.toggled.connect(lambda c: self._set_param('overwrite', bool(c)))
        form.addRow('允许覆盖', ow)
        tip = QLabel('未选输入源或路径为空时节点红叹号。结果显示页可预览目标文件名。')
        tip.setStyleSheet('color:#888;')
        form.addRow(tip)
        return w

    def _result_tab(self):
        """结果显示：设计态目标路径/文件名预览 + OK 门控摘要（无硬件）。"""
        w = QWidget()
        form = QFormLayout(w)
        form.setContentsMargins(10, 10, 10, 10)
        tip = QLabel('运行写回 path / status / bytes（skipped_ng / no_image / ok）；下方为设计态预览。')
        tip.setStyleSheet('color:#888;')
        form.addRow(tip)
        self._oi_result_preview = QPlainTextEdit()
        self._oi_result_preview.setObjectName('outputImageResultPreview')
        self._oi_result_preview.setReadOnly(True)
        self._oi_result_preview.setMaximumHeight(140)
        form.addRow('目标文件', self._oi_result_preview)
        self._oi_result_meta = QLabel()
        self._oi_result_meta.setObjectName('outputImageResultMeta')
        self._oi_result_meta.setWordWrap(True)
        form.addRow('摘要', self._oi_result_meta)
        btn = QPushButton('刷新结果显示')
        btn.setObjectName('outputImageResultRefresh')
        btn.clicked.connect(self._refresh_output_image_result)
        form.addRow(btn)
        self._refresh_output_image_result()
        return w

    def _refresh_output_image_result(self):
        from datetime import datetime
        path = str(self.params.get('path') or '').strip()
        fmt = str(self.params.get('format') or 'png').lower().lstrip('.')
        prefix = str(self.params.get('filePrefix') or 'img').strip() or 'img'
        use_ts = bool(self.params.get('useTimestamp', True))
        date_sub = bool(self.params.get('dateSubdir', False))
        only_ok = bool(self.params.get('onlyOnOk', False))
        ok_var = str(self.params.get('okVar') or 'passGate')
        img_from = self.step.get('imageFrom')
        lines = []
        if not path:
            lines.append('(未配置保存路径)')
        else:
            base = path.rstrip('/\\')
            if date_sub:
                base = f"{base}/{datetime.now().strftime('%Y-%m-%d')}"
            ts = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
            # Heuristic: no extension → directory mode
            import os as _os
            looks_dir = (not _os.path.splitext(path)[1]) or path.endswith(('/', '\\'))
            if looks_dir:
                name = f"{prefix}_{ts}.{fmt}" if use_ts else f"{prefix}.{fmt}"
                dest = f"{base}/{name}"
            else:
                root, ext = _os.path.splitext(path)
                if use_ts:
                    dest = f"{root}_{ts}{ext or ('.' + fmt)}"
                else:
                    dest = path
                if date_sub:
                    dest = f"{_os.path.dirname(base)}/{datetime.now().strftime('%Y-%m-%d')}/{_os.path.basename(dest)}"
            lines.append(dest)
            if only_ok:
                lines.append(f'门控: onlyOnOk → 变量 {ok_var} 非 OK 时 status=skipped_ng')
                ng = str(self.params.get('ngSubdir') or 'NG')
                lines.append(f'NG 旁路提示目录: {base}/{ng}/…（软提示，引擎仍跳过写入）')
        text = '\n'.join(lines) if lines else '(无预览)'
        if hasattr(self, '_oi_result_preview') and self._oi_result_preview is not None:
            self._oi_result_preview.setPlainText(text)
        src = img_from or '（未选）'
        meta = (
            f'输入源={src} · 格式={fmt} · 质量={int(self.params.get("quality") or 95)}'
            f' · 时间戳={"开" if use_ts else "关"} · 覆盖={"开" if self.params.get("overwrite", True) else "关"}'
            f' · 标注优先={"开" if self.params.get("saveAnnotated", True) else "关"}'
        )
        if hasattr(self, '_oi_result_meta') and self._oi_result_meta is not None:
            self._oi_result_meta.setText(meta)


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
        if key in ('sample', 'protocol', 'delimiter', 'fields', 'pattern', 'fixedWidths', 'targetPrefix', 'sourceVar', 'sourceScope') and hasattr(self, '_refresh_protocol_result'):
            try:
                self._refresh_protocol_result()
            except Exception:
                pass

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



    def _result_tab(self):
        """结果显示：样例报文解析预览 + format↔protocol soft round-trip（open-and-run）。"""
        w = QWidget()
        form = QFormLayout(w)
        form.setContentsMargins(10, 10, 10, 10)
        tip = QLabel(
            '运行写回 parsed_*；下方用「样例」报文做设计态解析预览，'
            '并给出 format→LocalBus→parse 软往返（对齐 open-and-run-format-protocol）。'
        )
        tip.setWordWrap(True)
        tip.setStyleSheet('color:#888;')
        form.addRow(tip)
        self._proto_result_preview = QPlainTextEdit()
        self._proto_result_preview.setObjectName('protocolParseResultPreview')
        self._proto_result_preview.setReadOnly(True)
        self._proto_result_preview.setMaximumHeight(120)
        form.addRow('解析字段', self._proto_result_preview)
        self._proto_result_meta = QLabel()
        self._proto_result_meta.setObjectName('protocolParseResultMeta')
        self._proto_result_meta.setWordWrap(True)
        form.addRow('摘要', self._proto_result_meta)
        self._proto_roundtrip = QPlainTextEdit()
        self._proto_roundtrip.setObjectName('protocolParseRoundtripPreview')
        self._proto_roundtrip.setReadOnly(True)
        self._proto_roundtrip.setMaximumHeight(160)
        self._proto_roundtrip.setStyleSheet('font-family:monospace;font-size:11px;background:#1e1e1e;color:#b3e5fc;')
        form.addRow('软往返', self._proto_roundtrip)
        self._proto_roundtrip_meta = QLabel()
        self._proto_roundtrip_meta.setObjectName('protocolParseRoundtripMeta')
        self._proto_roundtrip_meta.setWordWrap(True)
        self._proto_roundtrip_meta.setStyleSheet('color:#666;font-size:11px;')
        form.addRow('往返摘要', self._proto_roundtrip_meta)
        btn = QPushButton('刷新结果显示')
        btn.setObjectName('protocolParseResultRefresh')
        btn.clicked.connect(self._refresh_protocol_result)
        form.addRow(btn)
        self._refresh_protocol_result()
        return w

    def _refresh_protocol_result(self):
        lines, parsed = soft_protocol_parse_preview(self.params)
        text = '\n'.join(lines) if lines else '(无字段)'
        if hasattr(self, '_proto_result_preview') and self._proto_result_preview is not None:
            self._proto_result_preview.setPlainText(text)
        src_var = self.params.get('sourceVar') or 'recvData'
        scope = self.params.get('sourceScope') or 'flow'
        proto = str(self.params.get('protocol') or 'delimited')
        meta = f'源 {scope}.{src_var} · 协议={proto} · 字段 {len(parsed) if parsed else len(lines)}'
        if hasattr(self, '_proto_result_meta') and self._proto_result_meta is not None:
            self._proto_result_meta.setText(meta)
        # soft round-trip using sibling format_data when present
        fmt = {
            'template': '{0}',
            'args': 'sample',
            'targetVar': 'formatted',
            'scope': 'flow',
            'trim': False,
        }
        env = {'sample': str(self.params.get('sample') or '')}
        try:
            for s in (self.project or {}).get('steps') or []:
                if (s or {}).get('operation') == 'format_data':
                    fmt = dict(s.get('params') or fmt)
                    break
        except Exception:
            pass
        # If no sibling format, synthesize a format that re-emits sample as body
        if not str(fmt.get('template') or '').strip() or str(fmt.get('template')) == '{0}':
            sample = str(self.params.get('sample') or '')
            if sample:
                fmt = {
                    'template': sample.replace('{', '{{').replace('}', '}}'),
                    'args': '',
                    'targetVar': 'formatted',
                    'scope': 'flow',
                    'trim': False,
                }
        block, rmeta, _f, _p = soft_format_protocol_roundtrip(fmt, self.params, env=env)
        if hasattr(self, '_proto_roundtrip') and self._proto_roundtrip is not None:
            self._proto_roundtrip.setPlainText(block)
        if hasattr(self, '_proto_roundtrip_meta') and self._proto_roundtrip_meta is not None:
            self._proto_roundtrip_meta.setText(rmeta)


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
        if key in (
            'path', 'content', 'sourceVar', 'append', 'encoding', 'newline',
            'bom', 'timestampPrefix', 'createDir', 'maxLinesSoft', 'separator',
        ) and hasattr(self, '_refresh_text_save_result'):
            try:
                self._refresh_text_save_result()
            except Exception:
                pass

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
            if hasattr(self, '_refresh_text_save_result'):
                try:
                    self._refresh_text_save_result()
                except Exception:
                    pass
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
        content.setObjectName('textSaveContentEdit')
        def _live_content():
            self.params['content'] = content.toPlainText()
            self.step['params'] = self.params
            self._emit()
            if hasattr(self, '_refresh_text_save_result'):
                try:
                    self._refresh_text_save_result()
                except Exception:
                    pass
        content.textChanged.connect(_live_content)
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
        sep = QLineEdit(str(self.params.get('separator') if self.params.get('separator') is not None else '\t'))
        sep.setPlaceholderText('时间戳与正文分隔符')
        sep.editingFinished.connect(lambda: self._set_param('separator', sep.text()))
        form.addRow('时间戳分隔', sep)
        mkdir = OrangeSwitch(bool(self.params.get('createDir', True)))
        mkdir.toggled.connect(lambda c: self._set_param('createDir', bool(c)))
        form.addRow('自动建目录', mkdir)
        ml = QSpinBox(); ml.setRange(0, 1000000); ml.setSpecialValueText('不限')
        ml.setValue(int(self.params.get('maxLinesSoft') or 0))
        ml.setToolTip('软上限提示（0=不限）；引擎不截断，仅结果显示参考')
        ml.valueChanged.connect(lambda v: self._set_param('maxLinesSoft', int(v)))
        form.addRow('软行数上限', ml)
        tip = QLabel('路径为空时节点红叹号。源变量优先于「内容」；结果显示页预览将写入正文。')
        tip.setStyleSheet('color:#888;')
        form.addRow(tip)
        return w

    def _result_tab(self):
        """结果显示：设计态正文预览 + 字节/编码/模式摘要。"""
        w = QWidget()
        form = QFormLayout(w)
        form.setContentsMargins(10, 10, 10, 10)
        tip = QLabel('运行写回 path / bytes / bom / timestampPrefix / status；下方为设计态预览。')
        tip.setStyleSheet('color:#888;')
        form.addRow(tip)
        self._ts_result_preview = QPlainTextEdit()
        self._ts_result_preview.setObjectName('textSaveResultPreview')
        self._ts_result_preview.setReadOnly(True)
        self._ts_result_preview.setMaximumHeight(140)
        form.addRow('将写入', self._ts_result_preview)
        self._ts_result_meta = QLabel()
        self._ts_result_meta.setObjectName('textSaveResultMeta')
        self._ts_result_meta.setWordWrap(True)
        form.addRow('摘要', self._ts_result_meta)
        btn = QPushButton('刷新结果显示')
        btn.setObjectName('textSaveResultRefresh')
        btn.clicked.connect(self._refresh_text_save_result)
        form.addRow(btn)
        self._refresh_text_save_result()
        return w

    def _refresh_text_save_result(self):
        from datetime import datetime
        path = str(self.params.get('path') or '').strip()
        body = str(self.params.get('content') or '')
        svar = str(self.params.get('sourceVar') or '').strip()
        if svar:
            # design-time: show variable placeholder; runtime resolves
            body = f'${{{svar}}}' + (f'  # fallback content len={len(self.params.get("content") or "")}' if self.params.get('content') else '')
            preview_note = f'(运行时取变量 {svar})'
        else:
            preview_note = '(使用内容字段)'
        if bool(self.params.get('timestampPrefix')):
            ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            sep = self.params.get('separator')
            if sep is None:
                sep = '\t'
            body = f'{ts}{sep}{body}'
        if bool(self.params.get('newline', True)) and body and not str(body).endswith('\n'):
            body = str(body) + '\n'
        enc = str(self.params.get('encoding') or 'utf-8')
        try:
            nbytes = len(str(body).encode(enc if enc != 'gbk' else 'utf-8', errors='replace'))
        except Exception:
            nbytes = len(str(body).encode('utf-8', errors='replace'))
        if bool(self.params.get('bom')) and not bool(self.params.get('append', True)):
            nbytes += 3
        lines = str(body).splitlines()
        soft = int(self.params.get('maxLinesSoft') or 0)
        soft_note = ''
        if soft > 0 and len(lines) > soft:
            soft_note = f' · ⚠ 超过软行数上限 {soft}（当前 {len(lines)}）'
        text = body if body else '(空正文)'
        if hasattr(self, '_ts_result_preview') and self._ts_result_preview is not None:
            self._ts_result_preview.setPlainText(text)
        mode = '追加' if self.params.get('append', True) else '覆盖'
        meta = (
            f'路径={path or "（未填）"} · {mode} · 编码 {enc} · 约 {nbytes} 字节'
            f' · BOM={"开" if self.params.get("bom") else "关"}'
            f' · 时间戳={"开" if self.params.get("timestampPrefix") else "关"}'
            f' · {preview_note}{soft_note}'
        )
        if hasattr(self, '_ts_result_meta') and self._ts_result_meta is not None:
            self._ts_result_meta.setText(meta)


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
