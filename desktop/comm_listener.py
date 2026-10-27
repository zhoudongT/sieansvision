"""Live Comm recvEvents listener — TCP Server / UDP / LocalBus inbox → fire_string_trigger.

Beyond CommManager「试收」: binds sockets for enabled TCP Server / UDP devices and
forwards payloads into project variables (recvEvents) + MainWindow.fire_string_trigger.
"""
from __future__ import annotations

import socket
import threading
from copy import deepcopy

from PySide6.QtCore import QObject, Signal, Slot, QTimer
from PySide6.QtNetwork import QTcpServer, QTcpSocket, QUdpSocket, QHostAddress

from desktop.comm_manager import ensure_comm_manager, write_project_variable


class CommRecvListener(QObject):
    """Owns live sockets for project.commManager; emits received(device, payload)."""

    received = Signal(str, str)  # device_name, payload_text
    status = Signal(str)

    def __init__(self, host=None, parent=None):
        super().__init__(parent)
        self._host = host  # MainWindow
        self._tcp_servers = []  # list[(QTcpServer, device_name)]
        self._udp_sockets = []  # list[(QUdpSocket, device_name)]
        self._clients = []  # keep QTcpSocket refs
        self._serial_stop = threading.Event()
        self._serial_threads = []
        self._device_map = {}  # name -> device dict
        self._recv_events = []
        self.received.connect(self._on_received)

    def set_host(self, host):
        self._host = host

    def stop(self):
        self._serial_stop.set()
        for th in self._serial_threads:
            try:
                th.join(timeout=0.4)
            except Exception:
                pass
        self._serial_threads = []
        self._serial_stop = threading.Event()
        for server, _ in self._tcp_servers:
            try:
                server.close()
            except Exception:
                pass
        self._tcp_servers = []
        for sock, _ in self._udp_sockets:
            try:
                sock.close()
            except Exception:
                pass
        self._udp_sockets = []
        for c in self._clients:
            try:
                c.close()
            except Exception:
                pass
        self._clients = []

    def reload(self, project):
        """(Re)bind listeners from project.commManager."""
        self.stop()
        cm = ensure_comm_manager(deepcopy(project) if isinstance(project, dict) else {})
        devices = [d for d in (cm.get('devices') or []) if isinstance(d, dict) and d.get('enabled', True)]
        self._device_map = {(d.get('name') or ''): d for d in devices if d.get('name')}
        self._recv_events = [e for e in (cm.get('recvEvents') or []) if isinstance(e, dict)]
        started = []
        for d in devices:
            name = d.get('name') or ''
            proto = str(d.get('protocol') or '')
            host = str(d.get('host') or '127.0.0.1').strip() or '127.0.0.1'
            try:
                port = int(d.get('port') or 0)
            except (TypeError, ValueError):
                port = 0
            if proto == 'TCP Server' and port > 0:
                if self._start_tcp_server(name, host, port):
                    started.append(f'TCP Server {name} :{port}')
            elif proto == 'UDP' and port > 0:
                if self._start_udp(name, host, port):
                    started.append(f'UDP {name} :{port}')
            elif proto == 'Serial':
                path = host or str(d.get('path') or '')
                if path and self._start_serial(name, path, int(d.get('baud') or d.get('baudrate') or 115200)):
                    started.append(f'Serial {name} {path}')
            # Local Bus: no socket; use push_local() / inject
        msg = '通信监听：' + ('、'.join(started) if started else '无 TCP Server/UDP/Serial 需监听')
        self.status.emit(msg)
        return started

    def push_local(self, device_name, payload):
        """In-process Local Bus / toolbar inject path into the same recv pipeline."""
        text = '' if payload is None else str(payload)
        self.received.emit(str(device_name or 'LocalLoop'), text)

    def _start_tcp_server(self, device_name, host, port):
        server = QTcpServer(self)

        def on_pending():
            while server.hasPendingConnections():
                client = server.nextPendingConnection()
                if client is None:
                    break
                self._clients.append(client)
                client.readyRead.connect(lambda c=client, n=device_name: self._read_tcp(c, n))
                client.disconnected.connect(lambda c=client: self._drop_client(c))

        server.newConnection.connect(on_pending)
        addr = QHostAddress.SpecialAddress.AnyIPv4
        if host not in ('0.0.0.0', '', '127.0.0.1', 'localhost'):
            parsed = QHostAddress(host)
            if not parsed.isNull():
                addr = parsed
        if not server.listen(addr, port):
            # retry localhost only
            if not server.listen(QHostAddress.SpecialAddress.LocalHost, port):
                self.status.emit(f'TCP Server {device_name}:{port} 监听失败：{server.errorString()}')
                return False
        self._tcp_servers.append((server, device_name))
        return True

    def _read_tcp(self, client: QTcpSocket, device_name: str):
        try:
            data = bytes(client.readAll()).decode('utf-8', errors='replace')
        except Exception:
            return
        for line in data.splitlines() or ([data] if data else []):
            text = line.strip('\r\n')
            if text != '':
                self.received.emit(device_name, text)

    def _drop_client(self, client):
        try:
            self._clients = [c for c in self._clients if c is not client]
            client.deleteLater()
        except Exception:
            pass

    def _start_udp(self, device_name, host, port):
        sock = QUdpSocket(self)

        def on_ready():
            while sock.hasPendingDatagrams():
                size = sock.pendingDatagramSize()
                data, _addr, _port = sock.readDatagram(size)
                try:
                    text = bytes(data).decode('utf-8', errors='replace').strip('\r\n')
                except Exception:
                    continue
                if text != '':
                    self.received.emit(device_name, text)

        sock.readyRead.connect(on_ready)
        addr = QHostAddress.SpecialAddress.AnyIPv4
        if not sock.bind(addr, port):
            if not sock.bind(QHostAddress.SpecialAddress.LocalHost, port):
                self.status.emit(f'UDP {device_name}:{port} 绑定失败')
                return False
        self._udp_sockets.append((sock, device_name))
        return True

    def _start_serial(self, device_name, path, baud):
        stop = self._serial_stop

        def worker():
            try:
                import serial as pyserial
            except Exception:
                return
            try:
                with pyserial.Serial(path, baudrate=baud, timeout=0.5) as ser:
                    buf = ''
                    while not stop.is_set():
                        chunk = ser.read(256)
                        if not chunk:
                            continue
                        buf += chunk.decode('utf-8', errors='replace')
                        while '\n' in buf or '\r' in buf:
                            for sep in ('\n', '\r'):
                                if sep in buf:
                                    line, buf = buf.split(sep, 1)
                                    line = line.strip('\r\n')
                                    if line:
                                        # marshal to Qt thread
                                        self.received.emit(device_name, line)
                                    break
            except Exception:
                return

        th = threading.Thread(target=worker, name=f'sieans-ser-{device_name}', daemon=True)
        th.start()
        self._serial_threads.append(th)
        return True

    @Slot(str, str)
    def _on_received(self, device_name, payload):
        host = self._host
        if host is None:
            return
        text = '' if payload is None else str(payload)
        # Write matching recvEvents variables
        try:
            matched = [
                e for e in self._recv_events
                if not e.get('device') or e.get('device') == device_name
            ]
            if matched:
                p = deepcopy(host.document.project)
                written = []
                for e in matched:
                    var = (e.get('variable') or e.get('var') or '').strip()
                    if not var:
                        continue
                    scope, name = write_project_variable(p, var, text)
                    if name:
                        written.append(f'{scope}.{name}')
                if written:
                    host.document.commit(p)
                    if hasattr(host, 'log'):
                        host.log(f'通信接收 [{device_name}] → 变量 {", ".join(written)} · {text[:48]}')
            elif hasattr(host, 'log'):
                host.log(f'通信接收 [{device_name}] · {text[:48]}')
        except Exception as err:
            if hasattr(host, 'log'):
                host.log(f'通信接收写变量失败：{err}')
        # Always forward to string triggers (live RUN etc.)
        try:
            if hasattr(host, 'fire_string_trigger'):
                host.fire_string_trigger(text, reason=f'通信监听/{device_name}')
        except Exception as err:
            if hasattr(host, 'log'):
                host.log(f'通信接收触发失败：{err}')
