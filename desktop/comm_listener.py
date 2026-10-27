"""Live Comm recvEvents listener — TCP Server / UDP / Serial / LocalBus → fire_string_trigger.

Also ticks CommManager heartbeat (outbound keepalive) and auto-acks TCP clients when
response.enabled. Beyond CommManager「试收」: binds sockets for enabled devices.
"""
from __future__ import annotations

import socket
import queue
import threading
import time
from copy import deepcopy

from PySide6.QtCore import QObject, Signal, Slot, QTimer
from PySide6.QtNetwork import QTcpServer, QTcpSocket, QUdpSocket, QHostAddress

from desktop.comm_manager import ensure_comm_manager, write_project_variable


class CommRecvListener(QObject):
    """Owns live sockets for project.commManager; emits received(device, payload)."""

    received = Signal(str, str)  # device_name, payload_text
    status = Signal(str)
    listeningChanged = Signal(bool, str)  # active, summary
    heartbeatTick = Signal(str)  # payload sent this tick

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
        self._tcp_client_targets = []  # list[(name, host, port)]
        self._serial_ports = {}  # device_name -> pyserial.Serial (worker-owned; ack via queue)
        self._serial_ack_queues = {}  # device_name -> queue.Queue of ack strings
        self._heartbeat = dict(enabled=False, intervalMs=5000, payload='HB')
        self._response = dict(enabled=False, timeoutMs=3000, ack='OK')
        self._hb_timer = QTimer(self)
        self._hb_timer.timeout.connect(self._on_heartbeat)
        self._started = []
        self._listening = False
        self._last_hb_ms = 0
        self.received.connect(self._on_received)

    def set_host(self, host):
        self._host = host

    @property
    def listening(self):
        return bool(self._listening)

    @property
    def started_summary(self):
        return list(self._started)

    def stop(self):
        try:
            self._hb_timer.stop()
        except Exception:
            pass
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
        self._tcp_client_targets = []
        self._serial_ack_queues = {}
        self._serial_ports = {}
        was = self._listening
        self._listening = False
        self._started = []
        if was:
            self.listeningChanged.emit(False, '监听·关')

    def reload(self, project):
        """(Re)bind listeners from project.commManager + start heartbeat if enabled."""
        self.stop()
        cm = ensure_comm_manager(deepcopy(project) if isinstance(project, dict) else {})
        devices = [d for d in (cm.get('devices') or []) if isinstance(d, dict) and d.get('enabled', True)]
        self._device_map = {(d.get('name') or ''): d for d in devices if d.get('name')}
        self._recv_events = [e for e in (cm.get('recvEvents') or []) if isinstance(e, dict)]
        hb = cm.get('heartbeat') if isinstance(cm.get('heartbeat'), dict) else {}
        resp = cm.get('response') if isinstance(cm.get('response'), dict) else {}
        self._heartbeat = dict(
            enabled=bool(hb.get('enabled', False)),
            intervalMs=max(200, int(hb.get('intervalMs') or 5000)),
            payload=str(hb.get('payload') if hb.get('payload') is not None else 'HB'),
        )
        self._response = dict(
            enabled=bool(resp.get('enabled', False)),
            timeoutMs=max(100, int(resp.get('timeoutMs') or 3000)),
            ack=str(resp.get('ack') if resp.get('ack') is not None else 'OK'),
        )
        started = []
        self._tcp_client_targets = []
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
            elif proto == 'TCP Client' and port > 0:
                self._tcp_client_targets.append((name, host, port))
                started.append(f'TCP Client {name} →{host}:{port}')
            elif proto == 'UDP' and port > 0:
                if self._start_udp(name, host, port):
                    started.append(f'UDP {name} :{port}')
            elif proto == 'Serial':
                path = host or str(d.get('path') or '')
                if path and self._start_serial(name, path, int(d.get('baud') or d.get('baudrate') or 115200)):
                    started.append(f'Serial {name} {path}')
            # Local Bus: no socket; use push_local() / inject
        # Seed flow.heartbeatTick so Vars panel can show it immediately
        if self._heartbeat.get('enabled') and self._host is not None and hasattr(self._host, 'document'):
            try:
                write_project_variable(self._host.document.project, 'flow.heartbeatTick',
                                       str(self._heartbeat.get('payload') or 'HB'))
                write_project_variable(self._host.document.project, 'flow.heartbeatAt', '0')
            except Exception:
                pass
        self._started = started
        self._listening = bool(started) or True  # LocalBus always available after reload
        if self._heartbeat.get('enabled'):
            interval = int(self._heartbeat.get('intervalMs') or 5000)
            self._hb_timer.start(interval)
            started.append(f'心跳 {interval}ms')
            # immediate first tick so UI shows life
            QTimer.singleShot(0, self._on_heartbeat)
        summary = '、'.join(started) if started else 'LocalBus 就绪'
        msg = '通信监听：' + summary
        self.status.emit(msg)
        badge = f'监听·开 ({len(self._started)}路)' if self._started else '监听·LocalBus'
        if self._heartbeat.get('enabled'):
            badge += ' · HB'
        if self._response.get('enabled'):
            badge += ' · ACK'
        self.listeningChanged.emit(True, badge)
        return started

    def push_local(self, device_name, payload):
        """In-process Local Bus / toolbar inject path into the same recv pipeline."""
        text = '' if payload is None else str(payload)
        self.received.emit(str(device_name or 'LocalLoop'), text)

    def _on_heartbeat(self):
        payload = str(self._heartbeat.get('payload') or 'HB')
        self._last_hb_ms = int(time.time() * 1000)
        # Write flow.heartbeatTick variable (best-effort, no fire_string — avoid RUN loops)
        host = self._host
        try:
            if host is not None and hasattr(host, 'document'):
                # In-place write — no commit (heartbeat must not spam undo history)
                proj = host.document.project
                write_project_variable(proj, 'flow.heartbeatTick', payload)
                write_project_variable(proj, 'flow.heartbeatAt', str(self._last_hb_ms))
        except Exception:
            pass
        # Keepalive to connected TCP Server clients (inbound peers)
        sent = 0
        blob = (payload + '\n').encode('utf-8', errors='replace')
        for c in list(self._clients):
            try:
                if c.state() == QTcpSocket.SocketState.ConnectedState:
                    c.write(blob)
                    sent += 1
            except Exception:
                pass
        # Outbound heartbeat to TCP Client devices (short connect-send-close)
        out_ok = 0
        for name, host, port in list(self._tcp_client_targets):
            try:
                sock = socket.create_connection((host, int(port)), timeout=0.4)
                try:
                    sock.sendall(blob)
                    out_ok += 1
                finally:
                    sock.close()
            except Exception:
                pass
        # Serial outbound HB via ack queues (worker writes)
        for name, q in list(self._serial_ack_queues.items()):
            try:
                q.put_nowait(payload)
            except Exception:
                pass
        # Status tick (rate-limit log via signal only)
        self.heartbeatTick.emit(payload)
        detail = []
        if sent:
            detail.append(f'{sent}入站客户端')
        if out_ok:
            detail.append(f'{out_ok}出站TCP')
        self.status.emit(f'心跳 · {payload}' + ((' → ' + '、'.join(detail)) if detail else ''))

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
                # Auto-ack when response.enabled
                if self._response.get('enabled'):
                    try:
                        ack = str(self._response.get('ack') or 'OK')
                        client.write((ack + '\n').encode('utf-8', errors='replace'))
                    except Exception:
                        pass

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
                data, addr, rport = sock.readDatagram(size)
                try:
                    text = bytes(data).decode('utf-8', errors='replace').strip('\r\n')
                except Exception:
                    continue
                if text != '':
                    self.received.emit(device_name, text)
                    if self._response.get('enabled') and addr is not None:
                        try:
                            ack = str(self._response.get('ack') or 'OK')
                            sock.writeDatagram(
                                (ack + '\n').encode('utf-8', errors='replace'),
                                addr, rport,
                            )
                        except Exception:
                            pass

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
        ack_q = queue.Queue()
        self._serial_ack_queues[device_name] = ack_q

        def worker():
            try:
                import serial as pyserial
            except Exception:
                return
            try:
                with pyserial.Serial(path, baudrate=baud, timeout=0.5) as ser:
                    self._serial_ports[device_name] = ser
                    buf = ''
                    while not stop.is_set():
                        # Drain outbound ACK / heartbeat writes
                        try:
                            while True:
                                msg = ack_q.get_nowait()
                                ser.write((str(msg) + '\n').encode('utf-8', errors='replace'))
                        except queue.Empty:
                            pass
                        except Exception:
                            pass
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
                                        self.received.emit(device_name, line)
                                        # Serial response ACK
                                        if self._response.get('enabled'):
                                            try:
                                                ack = str(self._response.get('ack') or 'OK')
                                                ser.write((ack + '\n').encode('utf-8', errors='replace'))
                                            except Exception:
                                                pass
                                    break
            except Exception:
                return
            finally:
                self._serial_ports.pop(device_name, None)

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
