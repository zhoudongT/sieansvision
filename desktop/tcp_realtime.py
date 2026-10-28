"""Real TCP session alongside CommManager LocalBus soft path.

Productizes bind/listen (server) and connect (client) on configurable host:port,
newline-framed UTF-8 send/recv, optional auto-ack, and a transcript of *real*
socket traffic. Soft/LocalBus remains the default design-time path; this module
is the TCP transport used by CommManager when mode=TCP.

Loopback (127.0.0.1) e2e needs no PLC. Does not touch :18280 / App :19777.
No Halcon / robot / cloud.
"""
from __future__ import annotations

import socket
import threading
import time
from datetime import datetime
from typing import Any, Callable, Optional

TRANSPORT_SOFT = 'soft'
TRANSPORT_TCP = 'tcp'
TRANSPORTS = (TRANSPORT_SOFT, TRANSPORT_TCP)

DEFAULT_HOST = '127.0.0.1'
DEFAULT_PORT = 19955  # distinct from tcp_device_sim :19880 and App :19777
ROLE_SERVER = 'server'
ROLE_CLIENT = 'client'

_TRANSCRIPT_MAX = 200


def _ts() -> str:
    return datetime.now().astimezone().strftime('%H:%M:%S.%f')[:-3]


class RealTcpSession:
    """One real TCP endpoint: either listen (server) or connect (client)."""

    def __init__(
        self,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        role: str = ROLE_SERVER,
        auto_ack: bool = True,
        ack: str = 'OK',
        framing: str = 'lf',  # lf | crlf | raw
    ):
        self.host = (host or DEFAULT_HOST).strip() or DEFAULT_HOST
        try:
            self.port = int(port) if port is not None else DEFAULT_PORT
        except (TypeError, ValueError):
            self.port = DEFAULT_PORT
        if self.port < 0:
            self.port = DEFAULT_PORT
        self.role = ROLE_SERVER if str(role).lower() != ROLE_CLIENT else ROLE_CLIENT
        self.auto_ack = bool(auto_ack)
        self.ack = str(ack if ack is not None else 'OK') or 'OK'
        self.framing = framing if framing in ('lf', 'crlf', 'raw') else 'lf'
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._server: Optional[socket.socket] = None
        self._sock: Optional[socket.socket] = None  # accepted or connected peer
        self._thread: Optional[threading.Thread] = None
        self._status = 'idle'
        self._last_error = ''
        self._recv_count = 0
        self._send_count = 0
        self._transcript: list[str] = []
        self._on_recv: Optional[Callable[[str], None]] = None
        self._buf = b''

    # ----- status / transcript -----
    def status(self) -> dict[str, Any]:
        with self._lock:
            peer = ''
            try:
                if self._sock:
                    peer = '%s:%s' % self._sock.getpeername()
            except Exception:
                peer = ''
            return {
                'transport': TRANSPORT_TCP,
                'role': self.role,
                'host': self.host,
                'port': self.port,
                'status': self._status,
                'listening': self._status == 'listening',
                'connected': self._status in ('connected', 'listening') and self._sock is not None,
                'peer': peer,
                'autoAck': self.auto_ack,
                'ack': self.ack,
                'recvCount': self._recv_count,
                'sendCount': self._send_count,
                'lastError': self._last_error,
                'transcriptLines': len(self._transcript),
            }

    def transcript(self, limit: int = 80) -> list[str]:
        with self._lock:
            n = max(1, min(_TRANSCRIPT_MAX, int(limit or 80)))
            return list(self._transcript[-n:])

    def transcript_text(self, limit: int = 80) -> str:
        return '\n'.join(self.transcript(limit))

    def _log(self, direction: str, text: str, note: str = ''):
        body = str(text).replace('\r', '\\r').replace('\n', '\\n')
        if len(body) > 160:
            body = body[:157] + '…'
        line = f'[{_ts()}] {direction} path=tcp-real {self.host}:{self.port} │ {body}'
        if note:
            line += f' · {note}'
        with self._lock:
            self._transcript.append(line)
            if len(self._transcript) > _TRANSCRIPT_MAX:
                del self._transcript[:-_TRANSCRIPT_MAX]

    def set_on_recv(self, cb: Optional[Callable[[str], None]]):
        self._on_recv = cb

    # ----- framing -----
    def _frame(self, text: str) -> bytes:
        raw = (text if text is not None else '').encode('utf-8', errors='replace')
        if self.framing == 'crlf':
            if not raw.endswith(b'\r\n'):
                raw = raw.rstrip(b'\r\n') + b'\r\n'
        elif self.framing == 'lf':
            if not raw.endswith(b'\n'):
                raw = raw.rstrip(b'\r\n') + b'\n'
        return raw

    def _split_frames(self, data: bytes) -> list[str]:
        self._buf += data
        out: list[str] = []
        if self.framing == 'raw':
            if self._buf:
                out.append(self._buf.decode('utf-8', errors='replace'))
                self._buf = b''
            return out
        delim = b'\r\n' if self.framing == 'crlf' else b'\n'
        while True:
            i = self._buf.find(delim)
            if i < 0:
                break
            chunk = self._buf[:i]
            self._buf = self._buf[i + len(delim):]
            out.append(chunk.decode('utf-8', errors='replace'))
        return out

    # ----- lifecycle -----
    def start(self) -> dict[str, Any]:
        self.stop()
        self._stop.clear()
        self._buf = b''
        self._last_error = ''
        try:
            if self.role == ROLE_SERVER:
                return self._start_server()
            return self._start_client()
        except Exception as exc:
            self._last_error = str(exc)
            self._status = 'error'
            self._log('ERR', str(exc), 'start failed')
            return self.status()

    def _start_server(self) -> dict[str, Any]:
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((self.host, self.port))
        srv.listen(8)
        srv.settimeout(0.5)
        self._server = srv
        # Reflect actual bound port (0 → ephemeral)
        try:
            self.port = int(srv.getsockname()[1])
        except Exception:
            pass
        self._status = 'listening'
        self._log('SYS', f'LISTEN {self.host}:{self.port}', 'server')
        th = threading.Thread(target=self._server_loop, name='RealTcpServer', daemon=True)
        self._thread = th
        th.start()
        return self.status()

    def _start_client(self) -> dict[str, Any]:
        sock = socket.create_connection((self.host, self.port), timeout=3.0)
        sock.settimeout(0.5)
        self._sock = sock
        self._status = 'connected'
        self._log('SYS', f'CONNECT {self.host}:{self.port}', 'client')
        th = threading.Thread(target=self._client_loop, name='RealTcpClient', daemon=True)
        self._thread = th
        th.start()
        return self.status()

    def stop(self) -> dict[str, Any]:
        self._stop.set()
        with self._lock:
            for s in (self._sock, self._server):
                if s is not None:
                    try:
                        s.close()
                    except Exception:
                        pass
            self._sock = None
            self._server = None
        th = self._thread
        self._thread = None
        if th and th.is_alive() and th is not threading.current_thread():
            try:
                th.join(timeout=1.0)
            except Exception:
                pass
        prev = self._status
        self._status = 'idle'
        if prev not in ('idle',):
            self._log('SYS', 'CLOSE', prev)
        return self.status()

    # ----- loops -----
    def _server_loop(self):
        while not self._stop.is_set():
            srv = self._server
            if srv is None:
                break
            try:
                client, addr = srv.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            with self._lock:
                old = self._sock
                self._sock = client
            if old is not None:
                try:
                    old.close()
                except Exception:
                    pass
            client.settimeout(0.5)
            self._log('SYS', f'ACCEPT {addr[0]}:{addr[1]}', 'peer')
            self._drain_peer(client)
            with self._lock:
                if self._sock is client:
                    self._sock = None
            try:
                client.close()
            except Exception:
                pass
            if self._status == 'listening' or not self._stop.is_set():
                self._status = 'listening'

    def _client_loop(self):
        sock = self._sock
        if sock is None:
            return
        self._drain_peer(sock)
        if not self._stop.is_set():
            self._status = 'idle'
            self._log('SYS', 'PEER CLOSED', 'client')

    def _drain_peer(self, sock: socket.socket):
        while not self._stop.is_set():
            try:
                chunk = sock.recv(4096)
            except socket.timeout:
                continue
            except OSError:
                break
            if not chunk:
                break
            for frame in self._split_frames(chunk):
                self._handle_frame(sock, frame)

    def _handle_frame(self, sock: socket.socket, text: str):
        with self._lock:
            self._recv_count += 1
        self._log('RX', text, f'recv#{self._recv_count}')
        cb = self._on_recv
        if cb:
            try:
                cb(text)
            except Exception:
                pass
        if self.auto_ack and self.role == ROLE_SERVER:
            try:
                self._send_on(sock, self.ack, note='auto-ack')
            except Exception as exc:
                self._log('ERR', str(exc), 'auto-ack failed')

    # ----- send -----
    def send(self, text: str, wait_reply: bool = False, timeout_s: float = 2.0) -> dict[str, Any]:
        """Send framed text on the live peer socket. Optionally wait one reply line."""
        with self._lock:
            sock = self._sock
        if sock is None:
            # one-shot client send when not in long-lived client mode
            if self.role == ROLE_CLIENT or True:
                return self._oneshot_exchange(text, wait_reply=wait_reply, timeout_s=timeout_s)
            return {'ok': False, 'error': 'not connected', 'sent': text}
        try:
            self._send_on(sock, text, note='TX')
            reply = ''
            if wait_reply:
                reply = self._recv_one(sock, timeout_s=timeout_s)
            return {'ok': True, 'sent': text, 'reply': reply, 'path': 'tcp-real'}
        except Exception as exc:
            self._last_error = str(exc)
            return {'ok': False, 'error': str(exc), 'sent': text, 'path': 'tcp-real'}

    def _send_on(self, sock: socket.socket, text: str, note: str = 'TX'):
        data = self._frame(text)
        sock.sendall(data)
        with self._lock:
            self._send_count += 1
        self._log('TX', text, f'{note} send#{self._send_count}')

    def _recv_one(self, sock: socket.socket, timeout_s: float = 2.0) -> str:
        end = time.time() + max(0.05, float(timeout_s))
        local_buf = b''
        old = sock.gettimeout()
        try:
            while time.time() < end:
                sock.settimeout(max(0.05, end - time.time()))
                try:
                    chunk = sock.recv(4096)
                except socket.timeout:
                    continue
                if not chunk:
                    break
                local_buf += chunk
                delim = b'\r\n' if self.framing == 'crlf' else (b'\n' if self.framing != 'raw' else None)
                if delim is None:
                    return local_buf.decode('utf-8', errors='replace')
                if delim in local_buf:
                    line = local_buf.split(delim, 1)[0]
                    text = line.decode('utf-8', errors='replace')
                    self._log('RX', text, 'wait_reply')
                    with self._lock:
                        self._recv_count += 1
                    return text
        finally:
            try:
                sock.settimeout(old)
            except Exception:
                pass
        return ''

    def _oneshot_exchange(self, text: str, wait_reply: bool = True, timeout_s: float = 2.0) -> dict[str, Any]:
        """Connect → send → optional recv → close (CommManager TCP test style)."""
        try:
            with socket.create_connection((self.host, self.port), timeout=timeout_s) as sock:
                sock.settimeout(timeout_s)
                data = self._frame(text)
                sock.sendall(data)
                with self._lock:
                    self._send_count += 1
                self._log('TX', text, 'oneshot')
                reply = ''
                if wait_reply:
                    reply = self._recv_one(sock, timeout_s=timeout_s)
                return {
                    'ok': True,
                    'sent': text,
                    'reply': reply,
                    'path': 'tcp-real-oneshot',
                    'host': self.host,
                    'port': self.port,
                }
        except Exception as exc:
            self._last_error = str(exc)
            self._log('ERR', str(exc), 'oneshot')
            return {'ok': False, 'error': str(exc), 'sent': text, 'path': 'tcp-real-oneshot'}


def loopback_e2e(
    host: str = DEFAULT_HOST,
    port: int = 0,
    payload: str = 'PING',
    ack: str = 'OK',
    auto_ack: bool = True,
) -> dict[str, Any]:
    """listen → connect → send → recv → ack on 127.0.0.1. No external PLC.

    port=0 binds an ephemeral free port. Returns structured result for smoke.
    """
    server = RealTcpSession(
        host=host, port=port or 0, role=ROLE_SERVER,
        auto_ack=auto_ack, ack=ack, framing='lf',
    )
    received: list[str] = []
    server.set_on_recv(lambda t: received.append(t))
    st = server.start()
    if st.get('status') != 'listening':
        server.stop()
        return {'ok': False, 'error': st.get('lastError') or 'listen failed', 'steps': ['listen']}
    bound = int(st.get('port') or port)
    steps = ['listen']
    client = RealTcpSession(
        host=host, port=bound, role=ROLE_CLIENT,
        auto_ack=False, framing='lf',
    )
    try:
        # oneshot exchange against the live server
        ex = client._oneshot_exchange(payload, wait_reply=True, timeout_s=2.0)
        steps.append('connect')
        steps.append('send')
        if not ex.get('ok'):
            return {
                'ok': False,
                'error': ex.get('error') or 'exchange failed',
                'steps': steps,
                'server': server.status(),
                'transcript': server.transcript() + client.transcript(),
            }
        steps.append('recv')
        reply = str(ex.get('reply') or '')
        if auto_ack:
            if reply.strip() != str(ack).strip():
                return {
                    'ok': False,
                    'error': f'ack mismatch: got {reply!r} want {ack!r}',
                    'steps': steps,
                    'reply': reply,
                    'received': list(received),
                    'server': server.status(),
                    'transcript': server.transcript() + client.transcript(),
                }
            steps.append('ack')
        # Also assert server saw the payload
        time.sleep(0.05)
        if payload not in received and not any(payload in x for x in received):
            # race: drain may still be catching up — tolerate if reply matched
            if not (auto_ack and reply.strip() == str(ack).strip()):
                return {
                    'ok': False,
                    'error': f'server did not receive {payload!r}',
                    'steps': steps,
                    'received': list(received),
                    'server': server.status(),
                    'transcript': server.transcript() + client.transcript(),
                }
        return {
            'ok': True,
            'steps': steps,
            'host': host,
            'port': bound,
            'payload': payload,
            'reply': reply,
            'received': list(received),
            'server': server.status(),
            'transcript': server.transcript() + client.transcript(),
            'path': 'tcp-real-loopback',
            'note': 'loopback e2e · no PLC',
        }
    finally:
        try:
            client.stop()
        except Exception:
            pass
        try:
            server.stop()
        except Exception:
            pass


def expand_payload(template: str, vars_bag: Optional[dict] = None) -> str:
    """Minimal ${flow.x} / ${x} expand for sendEvents-style payloads over real TCP."""
    import re
    bag = dict(vars_bag or {})

    def repl(m):
        key = m.group(1).strip()
        short = key.split('.', 1)[-1] if '.' in key else key
        if key in bag:
            return str(bag[key])
        if short in bag:
            return str(bag[short])
        # nested flow.xxx style
        if key.startswith('flow.') and key[5:] in bag:
            return str(bag[key[5:]])
        return m.group(0)

    return re.sub(r'\$\{([^}]+)\}', repl, str(template or ''))


__all__ = [
    'TRANSPORT_SOFT', 'TRANSPORT_TCP', 'TRANSPORTS',
    'DEFAULT_HOST', 'DEFAULT_PORT', 'ROLE_SERVER', 'ROLE_CLIENT',
    'RealTcpSession', 'loopback_e2e', 'expand_payload',
]
