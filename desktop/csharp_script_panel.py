"""C# / 脚本模块壳 — VisionMaster p=12 细妆.

设计态编辑器：语言切换 C#/Python、代码区、超时、输入参数提示、
变量注入/输出写回、Host 实况结果。
C# 不在本机执行（status=unsupported）；Python + allowScripts 可真实执行。
"""
from copy import deepcopy
from datetime import datetime

from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QFont, QColor, QTextCharFormat, QSyntaxHighlighter
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTabWidget, QFormLayout, QLineEdit,
    QComboBox, QPlainTextEdit, QSpinBox, QScrollArea, QFrame, QHBoxLayout,
    QPushButton, QCheckBox, QGroupBox, QSplitter, QTextEdit,
)

DEFAULT_CS = (
    "// VisionMaster-style C# script shell (CLR not executed locally)\n"
    "// Placeholder API:\n"
    '//   var img = Vm.GetImage("source1");\n'
    '//   var x = Vm.GetGlobal("var0");\n'
    "//   Vm.SetResult(\"passed\", true);\n"
    "public class Script {\n"
    "  public void Run(VmContext ctx) {\n"
    "    // TODO — design-time only; switch language to Python for soft run\n"
    "  }\n"
    "}\n"
)

DEFAULT_PY = (
    "def run(ctx):\n"
    '    """Python 脚本（对齐 VM C# 脚本位）。OpenCV 可用：import cv2。\n'
    "    ctx['params'] = 注入输入；ctx['vars'] = {global,flow,module}。\n"
    '    """\n'
    "    import base64\n"
    "    import cv2\n"
    "    import numpy as np\n"
    "    inj = ctx.get('params') or {}\n"
    "    flow = ((ctx.get('vars') or {}).get('flow')) or {}\n"
    "    img = ctx.get('image') or ''\n"
    "    result = dict(passed=True, opencv=cv2.__version__, injected=dict(inj), flowKeys=list(flow.keys())[:12])\n"
    "    # soft readback: echo first inject key as out0 if present\n"
    "    for k, v in inj.items():\n"
    "        result[k] = v\n"
    "        break\n"
    "    annotated = None\n"
    "    if img:\n"
    "        raw = base64.b64decode(img.split(',', 1)[-1])\n"
    "        arr = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)\n"
    "        if arr is not None:\n"
    "            gray = cv2.cvtColor(arr, cv2.COLOR_BGR2GRAY)\n"
    "            edges = cv2.Canny(gray, 80, 160)\n"
    "            overlay = arr.copy()\n"
    "            overlay[edges > 0] = (0, 165, 255)\n"
    "            ok, buf = cv2.imencode('.png', overlay)\n"
    "            if ok:\n"
    "                annotated = 'data:image/png;base64,' + base64.b64encode(buf).decode()\n"
    "            result['width'] = int(arr.shape[1])\n"
    "            result['height'] = int(arr.shape[0])\n"
    "            result['edges'] = int((edges > 0).sum())\n"
    "    out = dict(result=result)\n"
    "    if annotated:\n"
    "        out['annotatedImage'] = annotated\n"
    "        out['image'] = annotated\n"
    "    return out\n"
)


class _SoftHighlighter(QSyntaxHighlighter):
    """Industrial soft highlight for C# / Python (no full lexer)."""

    def __init__(self, doc, language='csharp'):
        super().__init__(doc)
        self.language = language
        self._kw = QTextCharFormat(); self._kw.setForeground(QColor('#569cd6'))
        self._str = QTextCharFormat(); self._str.setForeground(QColor('#ce9178'))
        self._cmt = QTextCharFormat(); self._cmt.setForeground(QColor('#6a9955'))
        self._num = QTextCharFormat(); self._num.setForeground(QColor('#b5cea8'))

    def highlightBlock(self, text):
        import re
        if self.language == 'python':
            kws = r'\b(def|return|import|from|as|if|elif|else|for|while|in|not|and|or|True|False|None|class|with|try|except|pass|lambda)\b'
            cmt = r'#.*$'
        else:
            kws = r'\b(public|private|class|void|var|new|return|if|else|for|while|true|false|null|using|namespace|string|int|double|bool)\b'
            cmt = r'//.*$'
        for m in re.finditer(kws, text):
            self.setFormat(m.start(), m.end() - m.start(), self._kw)
        for m in re.finditer(r'"[^"\\]*(?:\\.[^"\\]*)*"', text):
            self.setFormat(m.start(), m.end() - m.start(), self._str)
        for m in re.finditer(r"'[^'\\]*(?:\\.[^'\\]*)*'", text):
            self.setFormat(m.start(), m.end() - m.start(), self._str)
        for m in re.finditer(cmt, text):
            self.setFormat(m.start(), m.end() - m.start(), self._cmt)
        for m in re.finditer(r'\b\d+(\.\d+)?\b', text):
            self.setFormat(m.start(), m.end() - m.start(), self._num)


def normalize_csharp_params(params=None):
    p = deepcopy(params or {})
    p.setdefault('language', 'csharp')
    if 'code' not in p or not str(p.get('code') or '').strip():
        p['code'] = DEFAULT_CS if p.get('language') != 'python' else DEFAULT_PY
    p.setdefault('timeoutMs', 5000)
    p.setdefault('entry', 'Script.Run')
    p.setdefault('references', '')
    p.setdefault('arguments', {})
    p.setdefault('inputs', [{'name': 'recStr', 'type': 'string', 'bind': ''}])
    p.setdefault('outputs', [{'name': 'out0', 'type': 'string'}, {'name': 'out1', 'type': 'string'}])
    p.setdefault('writeOutputVars', True)
    p.setdefault('injectGlobals', True)
    return p


class CsharpScriptPanel(QWidget):
    changed = Signal(dict)

    def __init__(self, step, definition, project, parent=None):
        super().__init__(parent)
        self.step = deepcopy(step)
        self.definition = definition or {}
        self.project = project or {}
        self.params = normalize_csharp_params(step.get('params'))
        self.step['params'] = self.params

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        hint = QLabel(
            '对齐 VisionMaster「C# 脚本」(p12) 与「C#脚本使用 OpenCV」(p62–63)：工业壳编辑器。'
            'C# = unsupported（无 CLR）。切语言为 Python 且运行时勾选「允许脚本」即可真实执行（含 OpenCV）；'
            '输入绑定 → ctx.params 注入；输出名写回 flow / flow.script_*。'
        )
        hint.setWordWrap(True)
        hint.setStyleSheet('color:#666;padding:8px 10px 4px;')
        root.addWidget(hint)

        # status chrome bar
        chrome = QHBoxLayout()
        self._status_chip = QLabel('● 设计态')
        self._status_chip.setObjectName('csharpScriptStatusChip')
        self._status_chip.setStyleSheet(
            'color:#9ad;background:#1e2228;border-radius:4px;padding:3px 8px;font-size:11px;'
        )
        chrome.addWidget(self._status_chip)
        self._lang_chip = QLabel('')
        self._lang_chip.setObjectName('csharpScriptLangChip')
        self._lang_chip.setStyleSheet(
            'color:#ccc;background:#2a2f38;border-radius:4px;padding:3px 8px;font-size:11px;'
        )
        chrome.addWidget(self._lang_chip)
        chrome.addStretch(1)
        self._bytes_lab = QLabel('')
        self._bytes_lab.setStyleSheet('color:#888;font-size:11px;')
        chrome.addWidget(self._bytes_lab)
        root.addLayout(chrome)
        self._refresh_chrome()

        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)
        self.tabs.addTab(self._wrap(self._basic_tab()), '基本参数')
        self.tabs.addTab(self._wrap(self._io_tab()), '输入输出')
        self.tabs.addTab(self._code_tab(), '脚本代码')
        self.tabs.addTab(self._wrap(self._inject_tab()), '变量注入')
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
        self._refresh_chrome()

    def _set_param(self, key, value):
        if self.params.get(key) != value:
            self.params[key] = deepcopy(value)
            self._emit()

    def _set_top(self, key, value):
        if self.step.get(key) != value:
            self.step[key] = deepcopy(value)
            self._emit()

    def _refresh_chrome(self):
        lang = self.params.get('language') or 'csharp'
        code = str(self.params.get('code') or '')
        self._lang_chip.setText(f'语言 · {"Python" if lang == "python" else "C#"}')
        self._bytes_lab.setText(f'{len(code.encode("utf-8"))} bytes · {code.count(chr(10))+1} 行')
        if lang == 'csharp':
            self._status_chip.setText('● C# 壳 · unsupported')
            self._status_chip.setStyleSheet(
                'color:#e8a;background:#2a1e28;border-radius:4px;padding:3px 8px;font-size:11px;'
            )
        else:
            self._status_chip.setText('● Python · 需允许脚本')
            self._status_chip.setStyleSheet(
                'color:#8d8;background:#1e2a22;border-radius:4px;padding:3px 8px;font-size:11px;'
            )

    def _basic_tab(self):
        w = QWidget()
        form = QFormLayout(w)
        form.setContentsMargins(10, 10, 10, 10)
        name = QLineEdit(self.step.get('name') or 'C#脚本')
        name.setMaxLength(80)
        name.editingFinished.connect(lambda: self._set_top('name', name.text()))
        form.addRow('模块名称', name)
        lang = QComboBox()
        lang.setObjectName('csharpScriptLangCombo')
        lang.addItem('C#（设计态壳）', 'csharp')
        lang.addItem('Python（可执行）', 'python')
        lang.setCurrentIndex(max(0, lang.findData(self.params.get('language') or 'csharp')))

        def _lang():
            new = lang.currentData()
            old = self.params.get('language')
            self._set_param('language', new)
            code = str(self.params.get('code') or '')
            if old != new and (
                not code.strip()
                or 'VisionMaster' in code
                or 'VmContext' in code
                or code.strip().startswith('def run')
                or 'ctx.get("image")' in code
                or "ctx.get('image')" in code
            ):
                self.params['code'] = DEFAULT_PY if new == 'python' else DEFAULT_CS
                if hasattr(self, 'editor'):
                    self.editor.blockSignals(True)
                    self.editor.setPlainText(self.params['code'])
                    self.editor.blockSignals(False)
                if hasattr(self, '_highlighter'):
                    self._highlighter.language = new
                    self._highlighter.rehighlight()
                self._emit()

        lang.currentIndexChanged.connect(lambda _: _lang())
        form.addRow('语言', lang)
        entry = QLineEdit(str(self.params.get('entry') or 'Script.Run'))
        entry.editingFinished.connect(lambda: self._set_param('entry', entry.text().strip()))
        form.addRow('入口', entry)
        refs = QLineEdit(str(self.params.get('references') or ''))
        refs.setPlaceholderText('程序集引用，逗号分隔（占位；C# 壳）')
        refs.editingFinished.connect(lambda: self._set_param('references', refs.text().strip()))
        form.addRow('引用', refs)
        to = QSpinBox()
        to.setRange(100, 120000)
        to.setValue(int(self.params.get('timeoutMs') or 5000))
        to.valueChanged.connect(lambda v: self._set_param('timeoutMs', int(v)))
        form.addRow('超时 (ms)', to)
        wob = QCheckBox('输出写回 flow / flow.script_*')
        wob.setObjectName('csharpScriptWriteOutputVars')
        wob.setChecked(bool(self.params.get('writeOutputVars', True)))
        wob.toggled.connect(lambda v: self._set_param('writeOutputVars', bool(v)))
        form.addRow(wob)
        ig = QCheckBox('注入全局/流程变量到脚本 ctx.vars')
        ig.setObjectName('csharpScriptInjectGlobals')
        ig.setChecked(bool(self.params.get('injectGlobals', True)))
        ig.toggled.connect(lambda v: self._set_param('injectGlobals', bool(v)))
        form.addRow(ig)
        return w

    def _io_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.addWidget(QLabel('输入 / 输出变量（设计态；对齐 VM 脚本左右栏）'))
        tip = QLabel('绑定列可填 results.<模块>.字段 / flow.x / global.y；点「插入上游字段」从最近运行结果挑选。')
        tip.setWordWrap(True)
        tip.setStyleSheet('color:#888;font-size:11px;')
        lay.addWidget(tip)
        bar = QHBoxLayout()
        pick = QPushButton('插入上游字段 → 输入绑定')
        pick.setObjectName('csharpScriptPickUpstreamBtn')
        pick.setToolTip('挑选上游字段，写入下方输入表第一空绑定格')
        pick.clicked.connect(self._pick_upstream_into_inputs)
        bar.addWidget(pick)
        add_in = QPushButton('+ 输入行')
        add_in.setObjectName('csharpScriptAddInputBtn')
        add_in.clicked.connect(lambda: self._add_io_row('inputs'))
        bar.addWidget(add_in)
        add_out = QPushButton('+ 输出行')
        add_out.setObjectName('csharpScriptAddOutputBtn')
        add_out.clicked.connect(lambda: self._add_io_row('outputs'))
        bar.addWidget(add_out)
        bar.addStretch(1)
        lay.addLayout(bar)
        from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView
        self._io_tables = {}
        for title, key, cols in (
            ('输入变量', 'inputs', ['名称', '类型', '绑定']),
            ('输出变量', 'outputs', ['名称', '类型']),
        ):
            lay.addWidget(QLabel(title))
            rows = list(self.params.get(key) or [])
            table = QTableWidget(max(1, len(rows)), len(cols))
            table.setObjectName(f'csharpScriptIoTable_{key}')
            table.setHorizontalHeaderLabels(cols)
            table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            table.setEditTriggers(QAbstractItemView.EditTrigger.AllEditTriggers)
            for r, row in enumerate(rows or [{'name': '', 'type': 'string', 'bind': ''}]):
                table.setItem(r, 0, QTableWidgetItem(str(row.get('name') or '')))
                table.setItem(r, 1, QTableWidgetItem(str(row.get('type') or 'string')))
                if key == 'inputs':
                    table.setItem(r, 2, QTableWidgetItem(str(row.get('bind') or '')))

            def _save(table=table, key=key):
                out = []
                for r in range(table.rowCount()):
                    name = (table.item(r, 0).text() if table.item(r, 0) else '').strip()
                    typ = (table.item(r, 1).text() if table.item(r, 1) else 'string').strip() or 'string'
                    if not name:
                        continue
                    item = {'name': name, 'type': typ}
                    if key == 'inputs':
                        item['bind'] = (table.item(r, 2).text() if table.item(r, 2) else '').strip()
                    out.append(item)
                self._set_param(key, out)

            table.cellChanged.connect(lambda *_: _save())
            self._io_tables[key] = table
            lay.addWidget(table)
        tip2 = QLabel('预编译 / CLR 执行未接入；Python 路径经 script_worker。保存工程即可保留脚本与 IO 定义。')
        tip2.setStyleSheet('color:#888;')
        lay.addWidget(tip2)
        lay.addStretch(1)
        return w

    def _add_io_row(self, key):
        from PySide6.QtWidgets import QTableWidgetItem
        table = self._io_tables.get(key)
        if table is None:
            return
        r = table.rowCount()
        table.insertRow(r)
        n = f'{"in" if key == "inputs" else "out"}{r}'
        table.setItem(r, 0, QTableWidgetItem(n))
        table.setItem(r, 1, QTableWidgetItem('string'))
        if key == 'inputs':
            table.setItem(r, 2, QTableWidgetItem(''))
        rows = list(self.params.get(key) or [])
        item = {'name': n, 'type': 'string'}
        if key == 'inputs':
            item['bind'] = ''
        rows.append(item)
        self._set_param(key, rows)

    def _code_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(8, 8, 8, 8)
        bar = QHBoxLayout()
        reset = QPushButton('恢复模板')
        reset.setObjectName('csharpScriptResetBtn')

        def _reset():
            tmpl = DEFAULT_PY if self.params.get('language') == 'python' else DEFAULT_CS
            self.editor.setPlainText(tmpl)
            self._set_param('code', tmpl)

        reset.clicked.connect(_reset)
        bar.addWidget(reset)
        snip = QComboBox()
        snip.setObjectName('csharpScriptSnippetCombo')
        snip.addItem('插入片段…', '')
        snip.addItem('读 flow 变量', 'flow_get')
        snip.addItem('写结果键', 'result_set')
        snip.addItem('OpenCV Canny', 'canny')
        snip.addItem('回显注入输入', 'echo_inject')

        def _snip(i):
            kind = snip.itemData(i)
            snip.setCurrentIndex(0)
            if not kind:
                return
            lang = self.params.get('language') or 'csharp'
            pieces = {
                'flow_get': {
                    'python': "    val = ((ctx.get('vars') or {}).get('flow') or {}).get('myVar')\n",
                    'csharp': '    var val = ctx.Flow["myVar"];\n',
                },
                'result_set': {
                    'python': "    result['out0'] = val\n",
                    'csharp': '    Vm.SetResult("out0", val);\n',
                },
                'canny': {
                    'python': (
                        "    gray = cv2.cvtColor(arr, cv2.COLOR_BGR2GRAY)\n"
                        "    edges = cv2.Canny(gray, 80, 160)\n"
                    ),
                    'csharp': '    // OpenCV Canny — use Python language for soft OpenCV path\n',
                },
                'echo_inject': {
                    'python': (
                        "    inj = ctx.get('params') or {}\n"
                        "    for k, v in inj.items():\n"
                        "        result[k] = v\n"
                    ),
                    'csharp': '    // echo inject — use Python language\n',
                },
            }
            text = pieces.get(kind, {}).get(lang) or pieces.get(kind, {}).get('python') or ''
            if text:
                self.editor.insertPlainText(text)
                self._set_param('code', self.editor.toPlainText())

        snip.currentIndexChanged.connect(_snip)
        bar.addWidget(snip)
        bar.addStretch(1)
        self._cursor_lab = QLabel('Ln 1, Col 1')
        self._cursor_lab.setStyleSheet('color:#888;font-size:11px;')
        bar.addWidget(self._cursor_lab)
        lay.addLayout(bar)
        self.editor = QPlainTextEdit()
        self.editor.setObjectName('csharpScriptEditor')
        self.editor.setPlainText(str(self.params.get('code') or ''))
        font = QFont('Menlo')
        font.setStyleHint(QFont.StyleHint.Monospace)
        font.setPointSize(11)
        self.editor.setFont(font)
        self.editor.setStyleSheet(
            'QPlainTextEdit{background:#1e1e1e;color:#d4d4d4;border:1px solid #333;selection-background-color:#264f78;}'
        )
        self.editor.setTabStopDistance(self.editor.fontMetrics().horizontalAdvance(' ') * 4)
        self.editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.editor.textChanged.connect(lambda: self._set_param('code', self.editor.toPlainText()))
        self.editor.cursorPositionChanged.connect(self._on_cursor)
        self._highlighter = _SoftHighlighter(self.editor.document(), self.params.get('language') or 'csharp')
        lay.addWidget(self.editor, 1)
        return w

    def _on_cursor(self):
        cur = self.editor.textCursor()
        self._cursor_lab.setText(f'Ln {cur.blockNumber()+1}, Col {cur.columnNumber()+1}')

    def _inject_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(10, 10, 10, 10)
        g = QGroupBox('变量注入 / 读回（软壳）')
        g.setObjectName('csharpScriptInjectGroup')
        form = QFormLayout(g)
        tip = QLabel(
            '运行时：inputs.bind → ctx.params[name]；outputs.name ← result[name] → flow / flow.script_*。'
            '下方显示最近一次 Host 运行的 injected / written 快照。'
        )
        tip.setWordWrap(True)
        tip.setStyleSheet('color:#888;font-size:11px;')
        form.addRow(tip)
        self._inject_preview = QTextEdit()
        self._inject_preview.setObjectName('csharpScriptInjectPreview')
        self._inject_preview.setReadOnly(True)
        self._inject_preview.setMaximumHeight(160)
        self._inject_preview.setStyleSheet(
            'background:#1e2228;color:#9ad;font-family:Menlo,monospace;font-size:11px;'
        )
        form.addRow(self._inject_preview)
        btn = QPushButton('刷新注入/写回快照')
        btn.setObjectName('csharpScriptInjectRefreshBtn')
        btn.clicked.connect(self._refresh_inject_preview)
        form.addRow(btn)
        lay.addWidget(g)
        # quick map of declared IO
        self._io_summary = QLabel('')
        self._io_summary.setObjectName('csharpScriptIoSummary')
        self._io_summary.setWordWrap(True)
        self._io_summary.setStyleSheet('color:#aaa;font-size:11px;padding:6px;')
        lay.addWidget(self._io_summary)
        self._refresh_inject_preview()
        lay.addStretch(1)
        return w

    def _refresh_inject_preview(self):
        ins = self.params.get('inputs') or []
        outs = self.params.get('outputs') or []
        lines = [f'声明输入 {len(ins)} · 输出 {len(outs)} · writeOutputVars={self.params.get("writeOutputVars", True)}']
        for r in ins:
            if isinstance(r, dict):
                lines.append(f'  in  {r.get("name")} ← {r.get("bind") or "(无绑定)"}')
        for r in outs:
            if isinstance(r, dict):
                lines.append(f'  out {r.get("name")} → flow.{r.get("name")} / flow.script_{r.get("name")}')
        if hasattr(self, '_io_summary'):
            self._io_summary.setText('\n'.join(lines))
        # Host live
        snap = '（尚无运行快照）'
        try:
            from desktop.upstream_field_picker import host_last_result
            lr = host_last_result(self) or {}
            sid = self.step.get('id')
            hit = None
            for rec in (lr.get('results') or []):
                if isinstance(rec, dict) and rec.get('id') == sid:
                    hit = rec
                    break
            if not hit and isinstance(lr.get('results'), dict):
                hit = lr['results'].get(sid)
            if hit:
                res = (hit.get('output') or {}).get('result') or hit.get('result') or {}
                inj = res.get('injected') or {}
                written = res.get('written') or {}
                snap = (
                    f'status={res.get("status")} language={res.get("language")} via={res.get("via")}\n'
                    f'injected={inj}\nwritten={written}\n'
                    f'keys={list(res.keys())[:24]}'
                )
        except Exception as e:
            snap = f'（读取失败：{e}）'
        if hasattr(self, '_inject_preview'):
            self._inject_preview.setPlainText(snap)

    def _result_tab(self):
        w = QWidget()
        form = QFormLayout(w)
        form.setContentsMargins(10, 10, 10, 10)
        tip = QLabel('运行结果：language / entry / bytes / status（csharp→unsupported；python→ok|error）。')
        tip.setWordWrap(True)
        tip.setStyleSheet('color:#888;')
        form.addRow(tip)
        self._live_lab = QLabel('实况：尚未运行')
        self._live_lab.setObjectName('csharpScriptLiveBind')
        self._live_lab.setWordWrap(True)
        self._live_lab.setStyleSheet(
            'color:#9ad;font-size:11px;padding:6px;background:#1e2228;border-radius:4px;'
        )
        form.addRow('Host 实况', self._live_lab)
        self._result_box = QTextEdit()
        self._result_box.setObjectName('csharpScriptResultBox')
        self._result_box.setReadOnly(True)
        self._result_box.setMinimumHeight(180)
        self._result_box.setStyleSheet(
            'background:#141820;color:#cde;font-family:Menlo,monospace;font-size:11px;'
        )
        form.addRow(self._result_box)
        bar = QHBoxLayout()
        b_ref = QPushButton('刷新实况')
        b_ref.setObjectName('csharpScriptLiveRefreshBtn')
        b_ref.clicked.connect(self._refresh_live_bind)
        bar.addWidget(b_ref)
        b_both = QPushButton('同步注入快照')
        b_both.setObjectName('csharpScriptSyncInjectBtn')
        b_both.clicked.connect(lambda: (self._refresh_live_bind(), self._refresh_inject_preview()))
        bar.addWidget(b_both)
        bar.addStretch(1)
        form.addRow(bar)
        # auto once
        try:
            self._refresh_live_bind()
        except Exception:
            pass
        return w

    def _refresh_live_bind(self):
        lab = getattr(self, '_live_lab', None)
        box = getattr(self, '_result_box', None)
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
        if not hit and isinstance(lr.get('results'), dict):
            hit = lr['results'].get(sid)
        lang = self.params.get('language') or 'csharp'
        if not hit:
            lab.setText(
                f'实况：尚无本模块运行结果 · language={lang} · '
                f'inputs={len(self.params.get("inputs") or [])} · '
                f'outputs={len(self.params.get("outputs") or [])}'
            )
            if box is not None:
                box.setPlainText('（等待流程运行）')
            return
        res = (hit.get('output') or {}).get('result') or hit.get('result') or {}
        elapsed = (hit.get('output') or {}).get('elapsedMs') or hit.get('elapsedMs')
        bits = [f'status={res.get("status")}', f'language={res.get("language") or lang}']
        if res.get('via'):
            bits.append(f'via={res.get("via")}')
        if elapsed is not None:
            bits.append(f'elapsedMs={elapsed}')
        for k in ('bytes', 'entry', 'note', 'error', 'passed', 'edges', 'width', 'height'):
            if k in res and res[k] is not None:
                bits.append(f'{k}={res[k]}')
        lab.setText('实况：' + ' · '.join(bits))
        if box is not None:
            import json
            try:
                box.setPlainText(json.dumps(res, ensure_ascii=False, indent=2, default=str)[:8000])
            except Exception:
                box.setPlainText(str(res)[:8000])
        # stamp
        lab.setToolTip(f'刷新于 {datetime.now().strftime("%H:%M:%S")}')

    def _pick_upstream_into_inputs(self):
        from desktop.upstream_field_picker import pick_upstream_field, host_last_result
        from PySide6.QtWidgets import QMessageBox, QTableWidgetItem
        picked = pick_upstream_field(
            self, self.project, step_id=self.step.get('id'),
            last_result=host_last_result(self),
        )
        if not picked:
            return
        _nid, _field, token = picked
        rows = list(self.params.get('inputs') or [])
        placed = False
        for r in rows:
            if isinstance(r, dict) and not str(r.get('bind') or '').strip():
                r['bind'] = token
                placed = True
                break
        if not placed:
            rows.append({'name': _field or 'in0', 'type': 'string', 'bind': token})
        self._set_param('inputs', rows)
        # refresh table if present
        table = self._io_tables.get('inputs') if hasattr(self, '_io_tables') else None
        if table is not None:
            table.blockSignals(True)
            table.setRowCount(max(1, len(rows)))
            for i, row in enumerate(rows):
                table.setItem(i, 0, QTableWidgetItem(str(row.get('name') or '')))
                table.setItem(i, 1, QTableWidgetItem(str(row.get('type') or 'string')))
                table.setItem(i, 2, QTableWidgetItem(str(row.get('bind') or '')))
            table.blockSignals(False)
        QMessageBox.information(self, '脚本输入', f'已写入绑定：{token}')
