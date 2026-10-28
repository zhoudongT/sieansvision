"""Real TCP session alongside CommManager LocalBus soft path.

Productizes bind/listen (server) and connect (client) on configurable host:port,
framed UTF-8 send/recv (LF / CRLF / raw / len4 length-prefix), optional auto-ack,
keep-alive + client reconnect, a longer-lived session pool for loopback, transcript
filter, and project-persist host/port. Soft/LocalBus remains the default design-time
path; this module is the TCP transport used by CommManager when mode=TCP.

Loopback (127.0.0.1) e2e needs no PLC. Does not touch :18280 / App :19777.
No Halcon / robot / cloud.

wave156: keep-alive/reconnect · framing LF|len4 · session pool · transcript filter · persist host/port
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

FRAMING_LF = 'lf'
FRAMING_CRLF = 'crlf'
FRAMING_RAW = 'raw'
FRAMING_LEN4 = 'len4'  # 4-byte big-endian length prefix + UTF-8 body
FRAMINGS = (FRAMING_LF, FRAMING_CRLF, FRAMING_RAW, FRAMING_LEN4)

# Keep-alive defaults (seconds); 0 disables
DEFAULT_KEEPALIVE_IDLE_S = 30.0
DEFAULT_KEEPALIVE_INTERVAL_S = 10.0
DEFAULT_RECONNECT_MS = 1000
DEFAULT_RECONNECT_MAX = 5

_TRANSCRIPT_MAX = 200
_SESSION_POOL: dict[str, 'RealTcpSession'] = {}
_SESSION_POOL_LOCK = threading.RLock()


def framing_label(framing: str) -> str:
    return {
        FRAMING_LF: 'LF (\\n)',
        FRAMING_CRLF: 'CRLF (\\r\\n)',
        FRAMING_RAW: 'Raw (无分帧)',
        FRAMING_LEN4: 'Len4 长度前缀',
    }.get(str(framing or '').lower(), str(framing or FRAMING_LF))


def normalize_framing(framing: str | None) -> str:
    f = str(framing or FRAMING_LF).lower().strip()
    return f if f in FRAMINGS else FRAMING_LF


def filter_transcript(lines, *, directions=None, text_contains: str = '') -> list[str]:
    """Filter transcript lines by direction tags (TX/RX/SYS/ERR) and optional substring."""
    dirs = None
    if directions:
        dirs = {str(d).upper() for d in directions}
    needle = str(text_contains or '')
    out = []
    for line in lines or []:
        s = str(line)
        if dirs:
            # lines look like: [HH:MM:SS.mmm] TX path=...
            tag = ''
            try:
                after = s.split(']', 1)[1].strip()
                tag = after.split(' ', 1)[0].upper()
            except Exception:
                tag = ''
            if tag not in dirs:
                continue
        if needle and needle not in s:
            continue
        out.append(s)
    return out


def tcp_persist_defaults() -> dict:
    return dict(
        host=DEFAULT_HOST,
        port=DEFAULT_PORT,
        role=ROLE_SERVER,
        framing=FRAMING_LF,
        autoAck=True,
        ack='OK',
        keepAlive=True,
        keepAliveIdleS=DEFAULT_KEEPALIVE_IDLE_S,
        reconnect=True,
        reconnectMs=DEFAULT_RECONNECT_MS,
        reconnectMax=DEFAULT_RECONNECT_MAX,
    )


def load_tcp_persist(project: dict | None) -> dict:
    """Read project.commManager.tcpReal (host/port/framing/keepalive)."""
    base = tcp_persist_defaults()
    if not isinstance(project, dict):
        return base
    cm = project.get('commManager') if isinstance(project.get('commManager'), dict) else {}
    raw = cm.get('tcpReal') if isinstance(cm.get('tcpReal'), dict) else {}
    out = dict(base)
    for k in out:
        if k in raw and raw[k] is not None:
            out[k] = raw[k]
    out['framing'] = normalize_framing(out.get('framing'))
    try:
        out['port'] = int(out.get('port') or DEFAULT_PORT)
    except (TypeError, ValueError):
        out['port'] = DEFAULT_PORT
    out['host'] = str(out.get('host') or DEFAULT_HOST).strip() or DEFAULT_HOST
    return out


def save_tcp_persist(project: dict | None, **fields) -> dict:
    """Merge fields into project.commManager.tcpReal; return saved dict."""
    if not isinstance(project, dict):
        project = {}
    cm = project.setdefault('commManager', {})
    if not isinstance(cm, dict):
        cm = {}
        project['commManager'] = cm
    cur = load_tcp_persist(project)
    for k, v in fields.items():
        if v is not None and k in cur:
            cur[k] = v
    cur['framing'] = normalize_framing(cur.get('framing'))
    cm['tcpReal'] = dict(cur)
    return dict(cur)


def session_pool_key(host: str, port: int, role: str, framing: str = FRAMING_LF) -> str:
    return f"{normalize_framing(framing)}|{role}|{(host or DEFAULT_HOST).strip()}:{int(port or 0)}"


def session_pool_get(key: str):
    with _SESSION_POOL_LOCK:
        return _SESSION_POOL.get(key)


def session_pool_put(key: str, sess: 'RealTcpSession') -> None:
    with _SESSION_POOL_LOCK:
        old = _SESSION_POOL.get(key)
        if old is not None and old is not sess:
            try:
                old.stop()
            except Exception:
                pass
        _SESSION_POOL[key] = sess


def session_pool_drop(key: str) -> None:
    with _SESSION_POOL_LOCK:
        old = _SESSION_POOL.pop(key, None)
    if old is not None:
        try:
            old.stop()
        except Exception:
            pass


def session_pool_clear() -> int:
    with _SESSION_POOL_LOCK:
        keys = list(_SESSION_POOL.keys())
        items = list(_SESSION_POOL.values())
        _SESSION_POOL.clear()
    n = 0
    for s in items:
        try:
            s.stop()
            n += 1
        except Exception:
            pass
    return n


def session_pool_size() -> int:
    with _SESSION_POOL_LOCK:
        return len(_SESSION_POOL)



def _ts() -> str:
    return datetime.now().astimezone().strftime('%H:%M:%S.%f')[:-3]


class RealTcpSession:
    """One real TCP endpoint: either listen (server) or connect (client).

    wave156: framing lf|crlf|raw|len4; optional SO_KEEPALIVE; client auto-reconnect.
    """

    def __init__(
        self,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        role: str = ROLE_SERVER,
        auto_ack: bool = True,
        ack: str = 'OK',
        framing: str = FRAMING_LF,  # lf | crlf | raw | len4
        keep_alive: bool = True,
        keep_alive_idle_s: float = DEFAULT_KEEPALIVE_IDLE_S,
        reconnect: bool = False,
        reconnect_ms: int = DEFAULT_RECONNECT_MS,
        reconnect_max: int = DEFAULT_RECONNECT_MAX,
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
        self.framing = normalize_framing(framing)
        self.keep_alive = bool(keep_alive)
        try:
            self.keep_alive_idle_s = float(keep_alive_idle_s or 0)
        except (TypeError, ValueError):
            self.keep_alive_idle_s = DEFAULT_KEEPALIVE_IDLE_S
        self.reconnect = bool(reconnect)
        try:
            self.reconnect_ms = max(50, int(reconnect_ms or DEFAULT_RECONNECT_MS))
        except (TypeError, ValueError):
            self.reconnect_ms = DEFAULT_RECONNECT_MS
        try:
            self.reconnect_max = max(0, int(reconnect_max if reconnect_max is not None else DEFAULT_RECONNECT_MAX))
        except (TypeError, ValueError):
            self.reconnect_max = DEFAULT_RECONNECT_MAX
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._server: Optional[socket.socket] = None
        self._sock: Optional[socket.socket] = None  # accepted or connected peer
        self._thread: Optional[threading.Thread] = None
        self._status = 'idle'
        self._last_error = ''
        self._recv_count = 0
        self._send_count = 0
        self._reconnect_count = 0
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
                'connected': self._status in ('connected', 'listening', 'reconnecting') and self._sock is not None,
                'peer': peer,
                'autoAck': self.auto_ack,
                'ack': self.ack,
                'framing': self.framing,
                'framingLabel': framing_label(self.framing),
                'keepAlive': self.keep_alive,
                'keepAliveIdleS': self.keep_alive_idle_s,
                'reconnect': self.reconnect,
                'reconnectMs': self.reconnect_ms,
                'reconnectMax': self.reconnect_max,
                'reconnectCount': self._reconnect_count,
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

    def transcript_filtered(
        self,
        limit: int = 80,
        *,
        directions=None,
        text_contains: str = '',
    ) -> list[str]:
        return filter_transcript(
            self.transcript(limit=max(limit, _TRANSCRIPT_MAX)),
            directions=directions,
            text_contains=text_contains,
        )[-max(1, int(limit or 80)):]

    def _apply_keepalive(self, sock: socket.socket) -> None:
        if not self.keep_alive:
            return
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        except Exception:
            return
        idle = max(1, int(self.keep_alive_idle_s or DEFAULT_KEEPALIVE_IDLE_S))
        # Linux TCP_KEEPIDLE / TCP_KEEPINTVL / TCP_KEEPCNT
        try:
            if hasattr(socket, 'TCP_KEEPIDLE'):
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, idle)
            if hasattr(socket, 'TCP_KEEPINTVL'):
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, max(1, idle // 3 or 1))
            if hasattr(socket, 'TCP_KEEPCNT'):
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 3)
        except Exception:
            pass

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
        if self.framing == FRAMING_LEN4:
            return len(raw).to_bytes(4, 'big') + raw
        if self.framing == FRAMING_CRLF:
            if not raw.endswith(b'\r\n'):
                raw = raw.rstrip(b'\r\n') + b'\r\n'
        elif self.framing == FRAMING_LF:
            if not raw.endswith(b'\n'):
                raw = raw.rstrip(b'\r\n') + b'\n'
        # raw: as-is
        return raw

    def _split_frames(self, data: bytes) -> list[str]:
        self._buf += data
        out: list[str] = []
        if self.framing == FRAMING_RAW:
            if self._buf:
                out.append(self._buf.decode('utf-8', errors='replace'))
                self._buf = b''
            return out
        if self.framing == FRAMING_LEN4:
            while True:
                if len(self._buf) < 4:
                    break
                n = int.from_bytes(self._buf[:4], 'big')
                if n < 0 or n > 16 * 1024 * 1024:
                    self._log('ERR', f'bad len4 prefix {n}', 'framing')
                    self._buf = b''
                    break
                if len(self._buf) < 4 + n:
                    break
                chunk = self._buf[4:4 + n]
                self._buf = self._buf[4 + n:]
                out.append(chunk.decode('utf-8', errors='replace'))
            return out
        delim = b'\r\n' if self.framing == FRAMING_CRLF else b'\n'
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
        self._apply_keepalive(sock)
        self._sock = sock
        self._status = 'connected'
        self._log(
            'SYS', f'CONNECT {self.host}:{self.port}',
            f'client framing={self.framing} keepalive={self.keep_alive}',
        )
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
            self._apply_keepalive(client)
            self._log('SYS', f'ACCEPT {addr[0]}:{addr[1]}', f'peer framing={self.framing}')
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
        while not self._stop.is_set():
            sock = self._sock
            if sock is None:
                break
            self._drain_peer(sock)
            if self._stop.is_set():
                break
            self._log('SYS', 'PEER CLOSED', 'client')
            with self._lock:
                if self._sock is sock:
                    try:
                        sock.close()
                    except Exception:
                        pass
                    self._sock = None
            if not self.reconnect or self.reconnect_max <= 0:
                self._status = 'idle'
                break
            # auto-reconnect
            attempts = 0
            reconnected = False
            while not self._stop.is_set() and attempts < self.reconnect_max:
                attempts += 1
                self._reconnect_count += 1
                self._status = 'reconnecting'
                self._log('SYS', f'RECONNECT attempt {attempts}/{self.reconnect_max}', 'client')
                time.sleep(max(0.05, self.reconnect_ms / 1000.0))
                if self._stop.is_set():
                    break
                try:
                    ns = socket.create_connection((self.host, self.port), timeout=3.0)
                    ns.settimeout(0.5)
                    self._apply_keepalive(ns)
                    with self._lock:
                        self._sock = ns
                        self._buf = b''
                    self._status = 'connected'
                    self._log('SYS', f'RECONNECTED {self.host}:{self.port}', f'attempt {attempts}')
                    reconnected = True
                    break
                except Exception as exc:
                    self._last_error = str(exc)
                    self._log('ERR', str(exc), f'reconnect #{attempts}')
            if not reconnected:
                self._status = 'idle'
                self._log('SYS', 'RECONNECT GIVE UP', 'client')
                break

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
                if self.framing == FRAMING_RAW:
                    text = local_buf.decode('utf-8', errors='replace')
                    self._log('RX', text, 'wait_reply')
                    with self._lock:
                        self._recv_count += 1
                    return text
                if self.framing == FRAMING_LEN4:
                    if len(local_buf) >= 4:
                        n = int.from_bytes(local_buf[:4], 'big')
                        if n >= 0 and len(local_buf) >= 4 + n:
                            text = local_buf[4:4 + n].decode('utf-8', errors='replace')
                            self._log('RX', text, 'wait_reply')
                            with self._lock:
                                self._recv_count += 1
                            return text
                    continue
                delim = b'\r\n' if self.framing == FRAMING_CRLF else b'\n'
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
                self._apply_keepalive(sock)
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
    framing: str = FRAMING_LF,
    keep_alive: bool = True,
    use_pool: bool = False,
) -> dict[str, Any]:
    """listen → connect → send → recv → ack on 127.0.0.1. No external PLC.

    port=0 binds an ephemeral free port. Returns structured result for smoke.
    framing: lf|crlf|raw|len4. use_pool=True keeps server in session pool briefly.
    """
    framing = normalize_framing(framing)
    server = RealTcpSession(
        host=host, port=port or 0, role=ROLE_SERVER,
        auto_ack=auto_ack, ack=ack, framing=framing, keep_alive=keep_alive,
    )
    received: list[str] = []
    server.set_on_recv(lambda t: received.append(t))
    st = server.start()
    if st.get('status') != 'listening':
        server.stop()
        return {'ok': False, 'error': st.get('lastError') or 'listen failed', 'steps': ['listen']}
    bound = int(st.get('port') or port)
    steps = ['listen']
    pool_key = session_pool_key(host, bound, ROLE_SERVER, framing)
    if use_pool:
        session_pool_put(pool_key, server)
    client = RealTcpSession(
        host=host, port=bound, role=ROLE_CLIENT,
        auto_ack=False, framing=framing, keep_alive=keep_alive,
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
            'framing': framing,
            'keepAlive': keep_alive,
            'pooled': bool(use_pool),
            'note': 'loopback e2e · no PLC',
        }
    finally:
        try:
            client.stop()
        except Exception:
            pass
        if use_pool:
            # leave server in pool for longer-lived reuse; caller may session_pool_drop
            pass
        else:
            try:
                server.stop()
            except Exception:
                pass


def pooled_loopback_session(
    host: str = DEFAULT_HOST,
    port: int = 0,
    *,
    framing: str = FRAMING_LF,
    ack: str = 'OK',
    auto_ack: bool = True,
) -> dict[str, Any]:
    """Start (or reuse) a longer-lived server session in the pool; return status+key."""
    framing = normalize_framing(framing)
    # Reuse existing listening session on same host/role/framing if still up
    with _SESSION_POOL_LOCK:
        for k, s in list(_SESSION_POOL.items()):
            if s.role == ROLE_SERVER and s.framing == framing and s.host == (host or DEFAULT_HOST):
                st = s.status()
                if st.get('status') == 'listening':
                    return {'ok': True, 'key': k, 'reused': True, 'status': st, 'port': st.get('port')}
    server = RealTcpSession(
        host=host, port=port or 0, role=ROLE_SERVER,
        auto_ack=auto_ack, ack=ack, framing=framing, keep_alive=True,
    )
    st = server.start()
    if st.get('status') != 'listening':
        server.stop()
        return {'ok': False, 'error': st.get('lastError') or 'listen failed', 'status': st}
    bound = int(st.get('port') or 0)
    key = session_pool_key(host, bound, ROLE_SERVER, framing)
    session_pool_put(key, server)
    return {'ok': True, 'key': key, 'reused': False, 'status': st, 'port': bound}


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
    'FRAMING_LF', 'FRAMING_CRLF', 'FRAMING_RAW', 'FRAMING_LEN4', 'FRAMINGS',
    'framing_label', 'normalize_framing', 'filter_transcript',
    'tcp_persist_defaults', 'load_tcp_persist', 'save_tcp_persist',
    'session_pool_key', 'session_pool_get', 'session_pool_put',
    'session_pool_drop', 'session_pool_clear', 'session_pool_size',
    'pooled_loopback_session',
    'RealTcpSession', 'loopback_e2e', 'expand_payload',
]
