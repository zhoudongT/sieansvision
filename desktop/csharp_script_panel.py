"""C# / 脚本模块壳 — VisionMaster p=12.

设计态编辑器：语言切换 C#/Python、代码区、超时、输入参数提示。
C# 不在本机执行（status=unsupported）；Python 示意。真实执行请用 script 算子。
"""
from copy import deepcopy

from PySide6.QtCore import Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTabWidget, QFormLayout, QLineEdit,
    QComboBox, QPlainTextEdit, QSpinBox, QScrollArea, QFrame, QHBoxLayout,
    QPushButton,
)

DEFAULT_CS = (
    "// VisionMaster-style C# script shell (CLR not executed locally)\n"
    "// Placeholder API:\n"
    '//   var img = Vm.GetImage("source1");\n'
    '//   var x = Vm.GetGlobal("var0");\n'
    "//   Vm.SetResult(\"passed\", true);\n"
    "public class Script {\n"
    "  public void Run(VmContext ctx) {\n"
    "    // TODO\n"
    "  }\n"
    "}\n"
)

DEFAULT_PY = (
    "def run(ctx):\n"
    '    """Python 脚本（对齐 VM C# 脚本位）。OpenCV 可用：import cv2。"""\n'
    "    import base64\n"
    "    import cv2\n"
    "    import numpy as np\n"
    "    img = ctx.get(\"image\") or \"\"\n"
    "    result = dict(passed=True, opencv=cv2.__version__)\n"
    "    annotated = None\n"
    "    if img:\n"
    "        raw = base64.b64decode(img.split(\",\", 1)[-1])\n"
    "        arr = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)\n"
    "        if arr is not None:\n"
    "            gray = cv2.cvtColor(arr, cv2.COLOR_BGR2GRAY)\n"
    "            edges = cv2.Canny(gray, 80, 160)\n"
    "            overlay = arr.copy()\n"
    "            overlay[edges > 0] = (0, 165, 255)  # sieans orange-ish\n"
    "            ok, buf = cv2.imencode(\".png\", overlay)\n"
    "            if ok:\n"
    "                annotated = \"data:image/png;base64,\" + base64.b64encode(buf).decode()\n"
    "            result[\"width\"] = int(arr.shape[1])\n"
    "            result[\"height\"] = int(arr.shape[0])\n"
    "            result[\"edges\"] = int((edges > 0).sum())\n"
    "    out = dict(result=result)\n"
    "    if annotated:\n"
    "        out[\"annotatedImage\"] = annotated\n"
    "        out[\"image\"] = annotated\n"
    "    return out\n"
)


def normalize_csharp_params(params=None):
    p = deepcopy(params or {})
    p.setdefault('language', 'csharp')
    if 'code' not in p or not str(p.get('code') or '').strip():
        p['code'] = DEFAULT_CS if p.get('language') != 'python' else DEFAULT_PY
    p.setdefault('timeoutMs', 5000)
    p.setdefault('entry', 'Script.Run')
    p.setdefault('references', '')
    p.setdefault('arguments', {})
    p.setdefault('inputs', [{'name':'recStr','type':'string','bind':''}])
    p.setdefault('outputs', [{'name':'out0','type':'string'},{'name':'out1','type':'string'}])
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
            '对齐 VisionMaster「C# 脚本」：设计态编辑器。'
            'C# = unsupported（无 CLR）。切语言为 Python 且运行时勾选允许脚本即可真实执行（含 OpenCV）；'
            '也可改用「Python 自定义脚本」算子。'
        )
        hint.setWordWrap(True)
        hint.setStyleSheet('color:#666;padding:8px 10px 4px;')
        root.addWidget(hint)
        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)
        self.tabs.addTab(self._wrap(self._basic_tab()), '基本参数')
        self.tabs.addTab(self._wrap(self._io_tab()), '输入输出')
        self.tabs.addTab(self._code_tab(), '脚本代码')
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

    def _basic_tab(self):
        w = QWidget()
        form = QFormLayout(w)
        form.setContentsMargins(10, 10, 10, 10)
        name = QLineEdit(self.step.get('name') or 'C#脚本')
        name.setMaxLength(80)
        name.editingFinished.connect(lambda: self._set_top('name', name.text()))
        form.addRow('模块名称', name)
        lang = QComboBox()
        lang.addItem('C#（设计态）', 'csharp')
        lang.addItem('Python（示意）', 'python')
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
            ):
                self.params['code'] = DEFAULT_PY if new == 'python' else DEFAULT_CS
                if hasattr(self, 'editor'):
                    self.editor.blockSignals(True)
                    self.editor.setPlainText(self.params['code'])
                    self.editor.blockSignals(False)
                self._emit()

        lang.currentIndexChanged.connect(lambda _: _lang())
        form.addRow('语言', lang)
        entry = QLineEdit(str(self.params.get('entry') or 'Script.Run'))
        entry.editingFinished.connect(lambda: self._set_param('entry', entry.text().strip()))
        form.addRow('入口', entry)
        refs = QLineEdit(str(self.params.get('references') or ''))
        refs.setPlaceholderText('程序集引用，逗号分隔（占位）')
        refs.editingFinished.connect(lambda: self._set_param('references', refs.text().strip()))
        form.addRow('引用', refs)
        to = QSpinBox()
        to.setRange(100, 120000)
        to.setValue(int(self.params.get('timeoutMs') or 5000))
        to.valueChanged.connect(lambda v: self._set_param('timeoutMs', int(v)))
        form.addRow('超时 (ms)', to)
        return w

    def _io_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.addWidget(QLabel('输入 / 输出变量（设计态；对齐 VM 脚本左右栏）'))
        from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView
        for title, key, cols in (
            ('输入变量', 'inputs', ['名称', '类型', '绑定']),
            ('输出变量', 'outputs', ['名称', '类型']),
        ):
            lay.addWidget(QLabel(title))
            rows = list(self.params.get(key) or [])
            table = QTableWidget(max(1, len(rows)), len(cols))
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
            lay.addWidget(table)
        tip = QLabel('预编译 / CLR 执行未接入；保存工程即可保留脚本与 IO 定义。')
        tip.setStyleSheet('color:#888;')
        lay.addWidget(tip)
        lay.addStretch(1)
        return w

    def _code_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(8, 8, 8, 8)
        bar = QHBoxLayout()
        reset = QPushButton('恢复模板')

        def _reset():
            tmpl = DEFAULT_PY if self.params.get('language') == 'python' else DEFAULT_CS
            self.editor.setPlainText(tmpl)
            self._set_param('code', tmpl)

        reset.clicked.connect(_reset)
        bar.addWidget(reset)
        bar.addStretch(1)
        lay.addLayout(bar)
        self.editor = QPlainTextEdit()
        self.editor.setPlainText(str(self.params.get('code') or ''))
        font = QFont('Menlo')
        font.setStyleHint(QFont.StyleHint.Monospace)
        font.setPointSize(11)
        self.editor.setFont(font)
        self.editor.textChanged.connect(lambda: self._set_param('code', self.editor.toPlainText()))
        lay.addWidget(self.editor, 1)
        return w

    def _result_tab(self):
        w = QWidget()
        form = QFormLayout(w)
        form.setContentsMargins(10, 10, 10, 10)
        tip = QLabel('运行结果：language / entry / bytes / status（csharp→unsupported）。')
        tip.setWordWrap(True)
        tip.setStyleSheet('color:#888;')
        form.addRow(tip)
        return w
