#!/usr/bin/env python3
"""wave155: real TCP alongside LocalBus soft — loopback listen→connect→send→recv→ack.

No PLC / Halcon / robot / cloud. Soft path remains; TCP is productized on 127.0.0.1.
PASS/FAIL counters; exit 1 on any FAIL.
"""
from __future__ import annotations
import ast
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / '.pydeps'))
os.chdir(ROOT)
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

fails, passes = [], []


def ok(name, cond, detail=''):
    if cond:
        passes.append(name)
        print(f'PASS  {name}')
    else:
        fails.append(name)
        print(f'FAIL  {name}  {detail}')


def main():
    # --- module contracts ---
    from desktop import tcp_realtime as rt
    ok('transports soft+tcp', rt.TRANSPORTS == (rt.TRANSPORT_SOFT, rt.TRANSPORT_TCP))
    ok('expand ${flow.x}', rt.expand_payload('OK=${flow.okng} n=${n}', {'okng': 'OK', 'n': 3}) == 'OK=OK n=3')
    ok('expand unknown kept', '${missing}' in rt.expand_payload('x=${missing}', {}))

    # --- pure loopback e2e (ephemeral port) ---
    r = rt.loopback_e2e(host='127.0.0.1', port=0, payload='PING', ack='OK', auto_ack=True)
    ok('loopback ok', r.get('ok') is True, r)
    ok('loopback steps', r.get('steps') == ['listen', 'connect', 'send', 'recv', 'ack'], r.get('steps'))
    ok('loopback reply OK', r.get('reply') == 'OK', r.get('reply'))
    ok('loopback port>0', int(r.get('port') or 0) > 0, r.get('port'))
    ok('loopback path', r.get('path') == 'tcp-real-loopback')
    ok('loopback transcript', isinstance(r.get('transcript'), list) and len(r['transcript']) >= 2)

    # --- custom ack + ${} payload via session ---
    r2 = rt.loopback_e2e(
        host='127.0.0.1', port=0,
        payload=rt.expand_payload('RESULT okng=${okng}', {'okng': 'OK'}),
        ack='ACK-OK', auto_ack=True,
    )
    ok('custom ack', r2.get('ok') and r2.get('reply') == 'ACK-OK', r2)
    ok('payload expanded', (r2.get('payload') or '').endswith('okng=OK'), r2.get('payload'))

    # --- server listen + client send (API) ---
    srv = rt.RealTcpSession(host='127.0.0.1', port=0, role=rt.ROLE_SERVER, auto_ack=True, ack='PONG')
    got = []
    srv.set_on_recv(lambda t: got.append(t))
    st = srv.start()
    ok('server listening', st.get('status') == 'listening', st)
    port = int(st.get('port') or 0)
    ok('server bound port', port > 0, port)
    cli = rt.RealTcpSession(host='127.0.0.1', port=port, role=rt.ROLE_CLIENT)
    ex = cli.send('PING', wait_reply=True, timeout_s=2.0)
    ok('client send ok', ex.get('ok') is True, ex)
    ok('client got PONG', ex.get('reply') == 'PONG', ex)
    import time; time.sleep(0.05)
    ok('server recv PING', 'PING' in got, got)
    ok('server transcript has RX', any('RX' in x and 'PING' in x for x in srv.transcript()), srv.transcript()[-5:])
    ok('client transcript has TX', any('TX' in x for x in cli.transcript()), cli.transcript())
    srv.stop(); cli.stop()
    ok('server stopped idle', srv.status().get('status') == 'idle')

    # --- CommManager UI presence + Soft vs TCP + loopback button ---
    src = (ROOT / 'desktop/comm_manager.py').read_text(encoding='utf-8')
    ok('UI transport combo', 'commTcpTransport' in src)
    ok('UI transcript', 'commTcpRealTranscript' in src)
    ok('UI loopback btn', 'commTcpRealLoopback' in src)
    ok('UI Soft label', 'Soft / LocalBus' in src)
    ok('methods present', all(m in src for m in (
        '_tcp_real_listen', '_tcp_real_connect', '_tcp_real_send',
        '_tcp_real_loopback', '_tcp_transport_changed',
    )))
    tree = ast.parse(src)
    ok('comm_manager AST', True)

    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from desktop.comm_manager import CommManagerDialog, default_comm_manager

    class Doc:
        project = {'commManager': default_comm_manager()}

    dlg = CommManagerDialog(Doc())
    ok('dialog has transport', hasattr(dlg, 'tcp_transport'))
    soft_i = dlg.tcp_transport.findData('soft')
    tcp_i = dlg.tcp_transport.findData('tcp')
    ok('soft+tcp items', soft_i >= 0 and tcp_i >= 0)
    dlg.tcp_transport.setCurrentIndex(soft_i)
    ok('soft disables listen', not dlg.tcp_real_listen_btn.isEnabled())
    dlg.tcp_transport.setCurrentIndex(tcp_i)
    ok('tcp enables listen', dlg.tcp_real_listen_btn.isEnabled())
    ui_r = dlg._tcp_real_loopback()
    ok('UI loopback PASS', ui_r.get('ok') is True and 'ack' in (ui_r.get('steps') or []), ui_r)
    ok('UI transcript filled', bool(dlg.tcp_real_transcript.toPlainText().strip()))
    ok('lastRealTcpE2e saved', (Doc.project.get('commManager') or {}).get('lastRealTcpE2e', {}).get('ok') is True)

    # --- docs / catalog note ---
    docs = (ROOT / 'docs/open-and-run-samples.md').read_text(encoding='utf-8')
    ok('docs wave155 note', 'wave155' in docs and 'TCP' in docs)
    cat = (ROOT / 'desktop/open_and_run_catalog.py').read_text(encoding='utf-8')
    ok('catalog mentions real TCP or tcp-sim', 'tcp' in cat.lower())

    print()
    print(f'SUMMARY  PASS {len(passes)}  FAIL {len(fails)}')
    if fails:
        print('FAILED:', ', '.join(fails))
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
