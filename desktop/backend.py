"""Asynchronous Qt client for the app-owned Node stdio engine."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import sys
import uuid

from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, QTimer, Signal


def _python_executable(root: Path) -> str | None:
    """A frozen desktop executable is not a Python command-line interpreter."""
    configured = os.environ.get("VISION_PYTHON")
    if configured:
        return configured
    local = root / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if local.is_file():
        return str(local)
    if not getattr(sys, "frozen", False):
        return sys.executable
    return shutil.which("python3") or shutil.which("python")


class Backend(QObject):
    ready = Signal()
    result = Signal(str, object)
    error = Signal(str, str)
    progress = Signal(object)
    stopped = Signal()

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.SeparateChannels)
        self.process.readyReadStandardOutput.connect(self._read_stdout)
        self.process.readyReadStandardError.connect(self._read_stderr)
        self.process.errorOccurred.connect(self._process_error)
        self.process.finished.connect(self._finished)
        self.process.started.connect(self._started)
        self._deadline = QTimer(self)
        self._deadline.setSingleShot(True)
        self._deadline.timeout.connect(self._force_stop)
        self._buffer = bytearray()
        self._logs = ""
        self._pending: set[str] = set()
        self._ready = False
        self._closing = False
        self._shutdown_sent = False
        self._stopped_emitted = True
        self.info: dict = {}

    @property
    def is_ready(self) -> bool:
        return self._ready and not self._closing

    def start(self, root: Path, data: Path) -> None:
        if self.process.state() != QProcess.ProcessState.NotRunning:
            return
        self._buffer.clear()
        self._logs = ""
        self._pending.clear()
        self._ready = False
        self._closing = False
        self._shutdown_sent = False
        self._stopped_emitted = False
        self.info = {}
        root, data = Path(root).resolve(), Path(data).resolve()
        engine = root / "desktop" / "engine-host.cjs"
        node = shutil.which("node")
        if not node or not engine.is_file():
            reason = "找不到 Node.js，请先安装 Node.js。" if not node else f"找不到原生引擎：{engine}"
            QTimer.singleShot(0, lambda: self._start_failed(reason))
            return
        python = _python_executable(root)
        if not python:
            QTimer.singleShot(0, lambda: self._start_failed("找不到视觉引擎的 Python，请安装项目 .venv 或设置 VISION_PYTHON。"))
            return
        environment = QProcessEnvironment.systemEnvironment()
        environment.insert("MACHINE_DATA_DIR", str(data))
        environment.insert("YOLO_CONFIG_DIR", str(data / "yolo-config"))
        environment.insert("VISION_PYTHON", python)
        self.process.setProcessEnvironment(environment)
        self.process.setWorkingDirectory(str(root))
        self.process.start(node, [str(engine), "--data", str(data)])

    def request(self, method: str, params: dict | None = None) -> str:
        request_id = str(uuid.uuid4())
        if not self.is_ready:
            QTimer.singleShot(0, lambda: self.error.emit(request_id, "原生运行引擎尚未就绪或正在关闭"))
            return request_id
        self._send(request_id, method, params)
        return request_id

    def _send(self, request_id: str, method: str, params: dict | None = None) -> None:
        try:
            payload = json.dumps({"id": request_id, "method": method, "params": params or {}},
                                 ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8") + b"\n"
            if len(payload) > 80_000_000:
                raise ValueError("原生请求超过 80 MB")
        except (TypeError, ValueError) as exc:
            message = str(exc)
            QTimer.singleShot(0, lambda: self.error.emit(request_id, message))
            return
        self._pending.add(request_id)
        if self.process.write(payload) < 0:
            self._pending.discard(request_id)
            QTimer.singleShot(0, lambda: self.error.emit(request_id, "无法写入原生引擎控制通道"))

    def shutdown(self) -> None:
        """Request cooperative shutdown; wait for stopped before closing the UI."""
        if self._closing:
            return
        self._closing = True
        self._ready = False
        if self.process.state() == QProcess.ProcessState.NotRunning:
            QTimer.singleShot(0, self._emit_stopped)
            return
        self._deadline.start(10000)
        if self.process.state() == QProcess.ProcessState.Running:
            self._send_shutdown()

    def _started(self) -> None:
        if self._closing:
            self._send_shutdown()

    def _send_shutdown(self) -> None:
        if not self._shutdown_sent:
            self._shutdown_sent = True
            self._send(str(uuid.uuid4()), "shutdown")

    def _read_stdout(self) -> None:
        self._buffer.extend(bytes(self.process.readAllStandardOutput()))
        while b"\n" in self._buffer:
            line, _, rest = self._buffer.partition(b"\n")
            self._buffer = bytearray(rest)
            if not line.strip():
                continue
            try:
                message = json.loads(line)
                if not isinstance(message, dict):
                    raise ValueError("消息必须是对象")
            except (UnicodeDecodeError, ValueError) as exc:
                self.error.emit("", f"原生引擎协议错误：{exc}")
                self.shutdown()
                return
            event = message.get("event")
            if event == "ready":
                self.info = message.get("data", {})
                self._ready = not self._closing
                if self._ready:
                    self.ready.emit()
            elif event == "progress":
                self.progress.emit(message.get("data", {}))
            elif "id" in message:
                request_id = str(message["id"] or "")
                self._pending.discard(request_id)
                if "error" in message:
                    self.error.emit(request_id, str(message["error"]))
                else:
                    self.result.emit(request_id, message.get("result"))
        if len(self._buffer) > 160_000_000:
            self.error.emit("", "原生引擎响应超过 160 MB 或缺少换行")
            self.shutdown()

    def _read_stderr(self) -> None:
        self._logs = (self._logs + bytes(self.process.readAllStandardError()).decode("utf-8", errors="replace"))[-8000:]

    def _process_error(self, process_error: QProcess.ProcessError) -> None:
        if process_error == QProcess.ProcessError.FailedToStart:
            self._start_failed("无法启动原生引擎：" + self.process.errorString())

    def _start_failed(self, reason: str) -> None:
        self._ready = False
        self.error.emit("", reason)
        self._emit_stopped()

    def _finished(self, exit_code: int, _exit_status: QProcess.ExitStatus) -> None:
        self._deadline.stop()
        self._read_stdout()
        self._read_stderr()
        self._ready = False
        message = self._logs.strip() or f"原生引擎已退出（{exit_code}）"
        pending, self._pending = self._pending, set()
        for request_id in pending:
            self.error.emit(request_id, message)
        if not self._closing and not pending:
            self.error.emit("", message)
        self._emit_stopped()

    def _force_stop(self) -> None:
        if self.process.state() != QProcess.ProcessState.NotRunning:
            self.error.emit("", "原生引擎关闭超时，正在结束本窗口创建的引擎进程")
            self.process.kill()

    def _emit_stopped(self) -> None:
        self._deadline.stop()
        if not self._stopped_emitted:
            self._stopped_emitted = True
            self.stopped.emit()
