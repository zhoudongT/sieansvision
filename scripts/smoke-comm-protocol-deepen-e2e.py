#!/usr/bin/env python3
"""Comm protocol deepen beyond loopback PING — sim GET/SET/VARS/MEAS/JSON + UI presets + writeback parse.
No field hardware / no robot SDK / no push.
"""
from __future__ import annotations
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
pass_n = fail_n = 0

def ok(m):
    global pass_n; pass_n += 1; print('PASS:', m)

def bad(m):
    global fail_n; fail_n += 1; print('FAIL:', m)

def main():
    from desktop import tcp_device_sim as tds
    assert tds.respond('PING') == 'PONG'; ok('PING→PONG')
    st = tds.respond('STATUS')
    assert 'sim=1' in st; ok(f'STATUS {st}')
    assert tds.respond('SET foo bar') == 'ACK SET foo'
    assert tds.respond('GET foo') == 'VALUE foo=bar'; ok('SET/GET KV')
    assert 'foo=bar' in tds.respond('VARS'); ok('VARS dump')
    m = tds.respond('MEAS')
    assert m.startswith('MEAS {') and '"sim":true' in m; ok(f'MEAS stub {m[:60]}…')
    j = tds.respond('JSON {"cmd":"GET","key":"foo"}')
    assert '"value":"bar"' in j; ok(f'JSON GET {j}')
    assert 'MEAS' in tds.respond('HELP') and 'GET' in tds.respond('HELP'); ok('HELP lists new verbs')

    # Live TCP roundtrip on ephemeral? Use start/stop if ports free
    try:
        tds.stop()
    except Exception:
        pass
    try:
        st = tds.start()
        import socket
        port = int(st.get('tcpPort') or 19880)
        with socket.create_connection(('127.0.0.1', port), timeout=2) as sock:
            sock.sendall(b'MEAS\n')
            buf = b''
            sock.settimeout(2)
            while b'\n' not in buf:
                chunk = sock.recv(1024)
                if not chunk: break
                buf += chunk
        reply = buf.decode().strip()
        assert reply.startswith('MEAS {'); ok(f'TCP live MEAS → {reply[:50]}…')
        with socket.create_connection(('127.0.0.1', port), timeout=2) as sock:
            sock.sendall(b'SET live 1\n')
            buf = b''; sock.settimeout(2)
            while b'\n' not in buf:
                chunk = sock.recv(1024)
                if not chunk: break
                buf += chunk
        assert buf.decode().strip() == 'ACK SET live'; ok('TCP live SET')
    except OSError as e:
        bad(f'TCP live sim {e}')
    finally:
        try: tds.stop()
        except Exception: pass

    cm = (ROOT / 'desktop/comm_manager.py').read_text(encoding='utf-8')
    if 'tcpProtocolPreset' in cm and 'MEAS (假量测)' in cm: ok('Comm UI protocol presets')
    else: bad('Comm UI presets missing')
    if '_parse_protocol_writeback_extras' in cm and 'measX' in cm: ok('structured writeback parser')
    else: bad('writeback parser missing')
    if '_tcp_preset_apply' in cm: ok('preset apply hook')
    else: bad('preset apply missing')

    from desktop.comm_manager import CommManagerDialog
    r = CommManagerDialog._parse_protocol_writeback_extras('VALUE ok=1')
    assert r == [('ok', '1')]; ok('parse VALUE')
    r2 = CommManagerDialog._parse_protocol_writeback_extras('MEAS {"ok":1,"x":3.0,"y":4.0,"score":0.8,"seq":1,"ts":1}')
    assert ('measX', 3.0) in r2; ok('parse MEAS')

    # docs mention
    readme = (ROOT / 'projects/README-open-and-run.md').read_text(encoding='utf-8')
    # soft: may add section below
    sim = (ROOT / 'desktop/tcp_device_sim.py').read_text(encoding='utf-8')
    if 'GET <key>' in sim or 'GET <k>' in sim: ok('sim docstring lists GET')
    else: bad('sim docstring weak')

    print(f"\n{'FAIL' if fail_n else 'PASS'} {pass_n} ok / {fail_n} fail")
    return 1 if fail_n else 0

if __name__ == '__main__':
    raise SystemExit(main())
