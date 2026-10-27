"""Workbench status bar: config text · 流程/工具/算法 ms · param audit log."""
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QStatusBar, QLabel, QWidget, QHBoxLayout, QSizePolicy


class WorkbenchStatusBar(QStatusBar):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('workbenchStatus')
        self.config_label = QLabel('组件配置完成')
        self.config_label.setObjectName('statusConfig')
        self.timing_label = QLabel('流程 — ms  |  工具 — ms  |  算法 — ms')
        self.timing_label.setObjectName('statusTiming')
        self.log_label = QLabel('')
        self.log_label.setObjectName('statusLog')
        self.log_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.version_label = QLabel('SIEANS Vision')
        self.version_label.setObjectName('statusVersion')
        self.addWidget(self.config_label, 0)
        self.addWidget(self._sep(), 0)
        self.addWidget(self.timing_label, 0)
        self.addWidget(self._sep(), 0)
        self.addWidget(self.log_label, 1)
        self.addPermanentWidget(self.version_label)

    def _sep(self):
        sep = QLabel('│')
        sep.setStyleSheet('color:#5a6572;padding:0 6px;')
        return sep

    def set_config(self, text, ok=True):
        self.config_label.setText(text or '组件配置完成')
        self.config_label.setProperty('error', not ok)
        self.config_label.style().unpolish(self.config_label)
        self.config_label.style().polish(self.config_label)

    def set_timing(self, process_ms=None, tool_ms=None, algo_ms=None):
        def fmt(v):
            if v is None:
                return '—'
            try:
                return f'{float(v):.2f}'
            except (TypeError, ValueError):
                return str(v)
        self.timing_label.setText(
            f'流程 {fmt(process_ms)}ms  |  工具 {fmt(tool_ms)}ms  |  算法 {fmt(algo_ms)}ms'
        )

    def push_log(self, message):
        stamp = datetime.now().strftime('%H:%M:%S')
        self.log_label.setText(f'{stamp}  {message}')
        self.log_label.setToolTip(message)

    def log_param_change(self, flow, module, param, old, new):
        msg = f'{flow}.{module}.{param} 参数已修改, 旧值:{old}, 新值:{new}'
        self.push_log(msg)
        return msg
