"""TCP / UDP loopback device simulator for Comm 联调 without field hardware.

Protocol (line-oriented, UTF-8, \\n terminated):
  PING          → PONG
  RUN / CONT / STOP / PAUSE / RESUME → ACK <CMD>
  STATUS        → OK READY
  ECHO <text>   → <text>
  HELP          → list of verbs
  anything else → ACK <raw>   (echo-ack so fire_string_trigger can see payload)

Default binds 127.0.0.1:19880 (TCP) and :19881 (UDP) — matches open-and-run-comm-multiproto.
Does not touch checker :18280 or app :19777.
"""
from __future__ import annotations

import socket
import threading
from datetime import datetime
from typing import Optional

DEFAULT_HOST = '127.0.0.1'
DEFAULT_TCP_PORT = 19880
DEFAULT_UDP_PORT = 19881

_lock = threading.Lock()
_state = {
    'tcp_sock': None,
    'udp_sock': None,
    'threads': [],
    'stop': None,
    'host': DEFAULT_HOST,
    'tcp_port': DEFAULT_TCP_PORT,
    'udp_port': DEFAULT_UDP_PORT,
    'clients': 0,
    'recv_count': 0,
    'last_payload': '',
    'last_at': '',
    'log': [],
}


def _ts():
    return datetime.now().astimezone().strftime('%H:%M:%S')


def _log(msg: str):
    line = f'[{_ts()}] {msg}'
    buf = _state['log']
    buf.append(line)
    if len(buf) > 200:
        del buf[:-200]


def respond(raw: str) -> str:
    text = (raw or '').strip()
    if not text:
        return 'ACK EMPTY'
    upper = text.upper()
    if upper == 'PING':
        return 'PONG'
    if upper == 'STATUS':
        return 'OK READY'
    if upper == 'HELP':
        return 'VERBS: PING STATUS RUN CONT STOP PAUSE RESUME ECHO <text> HELP'
    if upper in ('RUN', 'CONT', 'STOP', 'PAUSE', 'RESUME'):
        return f'ACK {upper}'
    if upper.startswith('ECHO '):
        return text[5:]
    # Pass-through ACK so Comm 试收 → fire_string_trigger(RUN/…) still works
    # when client sends the trigger word alone we already handled; else wrap.
    first = text.split()[0].upper()
    if first in ('RUN', 'CONT', 'STOP', 'PAUSE', 'RESUME'):
        return f'ACK {first}'
    return f'ACK {text}'


def _handle_client(conn: socket.socket, addr):
    _state['clients'] += 1
    _log(f'TCP accept {addr[0]}:{addr[1]}')
    try:
        conn.settimeout(60.0)
        buf = b''
        while not _state['stop'].is_set():
            try:
                chunk = conn.recv(4096)
            except socket.timeout:
                continue
            if not chunk:
                break
            buf += chunk
            while b'\n' in buf or b'\r' in buf:
                if b'\n' in buf:
                    line, buf = buf.split(b'\n', 1)
                else:
                    line, buf = buf.split(b'\r', 1)
                text = line.decode('utf-8', errors='replace').strip('\r')
                _state['recv_count'] += 1
                _state['last_payload'] = text
                _state['last_at'] = _ts()
                reply = respond(text) + '\n'
                try:
                    conn.sendall(reply.encode('utf-8'))
                except OSError:
                    return
                _log(f'TCP ← {text!r} → {reply.strip()!r}')
    finally:
        try:
            conn.close()
        except OSError:
            pass
        _state['clients'] = max(0, _state['clients'] - 1)
        _log(f'TCP close {addr[0]}:{addr[1]}')


def _tcp_accept_loop():
    sock = _state['tcp_sock']
    while sock and not _state['stop'].is_set():
        try:
            sock.settimeout(0.5)
            conn, addr = sock.accept()
        except socket.timeout:
            continue
        except OSError:
            break
        th = threading.Thread(target=_handle_client, args=(conn, addr), daemon=True)
        th.start()
        _state['threads'].append(th)


def _udp_loop():
    sock = _state['udp_sock']
    while sock and not _state['stop'].is_set():
        try:
            sock.settimeout(0.5)
            data, addr = sock.recvfrom(4096)
        except socket.timeout:
            continue
        except OSError:
            break
        text = data.decode('utf-8', errors='replace').strip()
        _state['recv_count'] += 1
        _state['last_payload'] = text
        _state['last_at'] = _ts()
        reply = (respond(text) + '\n').encode('utf-8')
        try:
            sock.sendto(reply, addr)
        except OSError:
            pass
        _log(f'UDP ← {text!r} from {addr[0]}:{addr[1]}')


def _status_unlocked() -> dict:
    running = _state['tcp_sock'] is not None
    return {
        'running': running,
        'host': _state['host'],
        'tcpPort': _state['tcp_port'],
        'udpPort': _state['udp_port'],
        'clients': _state['clients'],
        'recvCount': _state['recv_count'],
        'lastPayload': _state['last_payload'],
        'lastAt': _state['last_at'],
        'logTail': list(_state['log'][-20:]),
    }


def status() -> dict:
    with _lock:
        return _status_unlocked()


def start(host: str = DEFAULT_HOST, tcp_port: int = DEFAULT_TCP_PORT,
          udp_port: int = DEFAULT_UDP_PORT) -> dict:
    with _lock:
        if _state['tcp_sock'] is not None:
            return _status_unlocked()
        stop_evt = threading.Event()
        _state['stop'] = stop_evt
        _state['host'] = host
        _state['tcp_port'] = int(tcp_port)
        _state['udp_port'] = int(udp_port)
        _state['recv_count'] = 0
        _state['clients'] = 0
        tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tcp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        tcp.bind((host, int(tcp_port)))
        tcp.listen(16)
        udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        udp.bind((host, int(udp_port)))
        _state['tcp_sock'] = tcp
        _state['udp_sock'] = udp
        th_tcp = threading.Thread(target=_tcp_accept_loop, name='tcp-sim-accept', daemon=True)
        th_udp = threading.Thread(target=_udp_loop, name='udp-sim', daemon=True)
        _state['threads'] = [th_tcp, th_udp]
        th_tcp.start()
        th_udp.start()
        _log(f'started TCP :{tcp_port} UDP :{udp_port}')
        return _status_unlocked()


def stop() -> dict:
    with _lock:
        if _state['stop'] is not None:
            _state['stop'].set()
        for key in ('tcp_sock', 'udp_sock'):
            sock = _state.get(key)
            if sock is not None:
                try:
                    sock.close()
                except OSError:
                    pass
                _state[key] = None
        _state['threads'] = []
        _log('stopped')
        return _status_unlocked()


def exchange(payload: str, host: str = None, port: int = None, timeout: float = 2.0) -> str:
    """One-shot client helper for smokes / Comm test."""
    host = host or _state['host'] or DEFAULT_HOST
    port = int(port or _state['tcp_port'] or DEFAULT_TCP_PORT)
    with socket.create_connection((host, port), timeout=timeout) as sock:
        sock.settimeout(timeout)
        sock.sendall((payload.rstrip('\n') + '\n').encode('utf-8'))
        buf = b''
        while b'\n' not in buf and len(buf) < 4096:
            chunk = sock.recv(1024)
            if not chunk:
                break
            buf += chunk
        return buf.decode('utf-8', errors='replace').strip()


if __name__ == '__main__':
    import argparse
    import json
    import time
    ap = argparse.ArgumentParser()
    ap.add_argument('--host', default=DEFAULT_HOST)
    ap.add_argument('--tcp-port', type=int, default=DEFAULT_TCP_PORT)
    ap.add_argument('--udp-port', type=int, default=DEFAULT_UDP_PORT)
    args = ap.parse_args()
    print(json.dumps(start(args.host, args.tcp_port, args.udp_port), ensure_ascii=False, indent=2))
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print(json.dumps(stop(), ensure_ascii=False))
