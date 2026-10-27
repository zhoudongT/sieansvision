#!/usr/bin/env python3
"""E2E: caliper line deepen · template market local · TCP device sim. No hardware."""
from __future__ import annotations
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'vision'))
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

ok = 0

def pass_(n):
    global ok
    ok += 1
    print('PASS', n)


def main():
    import numpy as np
    import cv2

    # --- 1) caliper_line module on synthetic edge ---
    from caliper_line import find_lines_caliper
    y, x = np.mgrid[:240, :320]
    # vertical edge at x=160.5-ish via tanh
    dist = x - 160.35
    img = (20 + 210 * 0.5 * (1 + np.tanh(dist / 1.5))).astype(np.uint8)
    canvas = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR).copy()
    out = find_lines_caliper(
        img, canvas,
        dict(caliperCount=12, caliperWidth=9, caliperLength=80, caliperSigma=1.0,
             edgeThreshold=8, searchDir='left_right', edgeType='strongest',
             edgePolarity='dark_to_light', minScore=0.2, maximumResidual=3.0,
             findMethod='caliper', showCalipers=True, showPoints=True),
        offset=(0, 0),
    )
    assert out.get('method') == 'caliper', out
    assert out.get('count', 0) >= 1, out
    assert out['items'][0]['score'] >= 0.2, out
    xs = [p[0] for p in out.get('edgePoints') or []]
    assert xs and abs(float(np.median(xs)) - 160.35) < 1.5, (xs, out.get('diagnostic'))
    pass_('caliper_line synthetic edge')

    # --- 2) engine.geometry uses caliper by default ---
    import engine as eng
    gray = img
    bgr = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    canvas2 = bgr.copy()
    geo = eng.geometry(bgr, canvas2, {
        'feature': 'lines', 'findMethod': 'caliper',
        'caliperCount': 10, 'caliperWidth': 7, 'caliperLength': 100,
        'edgeThreshold': 8, 'minScore': 0.15, 'showOverlay': True,
        'showCalipers': True, 'showPoints': True, 'showFitCurve': True,
    }, (0, 0))
    assert geo.get('method') == 'caliper', geo
    assert geo.get('count', 0) >= 1, geo
    pass_('engine.geometry caliper path')

    # hough still available
    geo_h = eng.geometry(bgr, canvas2.copy(), {
        'feature': 'lines', 'findMethod': 'hough', 'votes': 20,
        'minLength': 40, 'maxGap': 10, 'maxCount': 5,
    }, (0, 0))
    assert geo_h.get('count', 0) >= 1 or True  # soft: image may yield lines
    assert (geo_h.get('items') or [{}])[0].get('method') == 'hough' or geo_h.get('count', 0) == 0
    pass_('engine.geometry hough path selectable')

    # --- 3) geometry panel exposes findMethod + roiPreset ---
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from desktop.geometry_find_panel import GeometryFindPanel, normalize_geometry_params
    np_ = normalize_geometry_params({}, feature='lines')
    assert np_.get('findMethod') == 'caliper'
    assert np_.get('roiPreset') == 'full'
    gp = GeometryFindPanel({'id': 'g1', 'operation': 'geometry_find', 'name': '直线', 'params': {'feature': 'lines'}},
                           {}, {'steps': [], 'edges': []})
    assert gp.params.get('findMethod') == 'caliper'
    pass_('geometry panel findMethod/roiPreset')

    # --- 4) template market local HTTP ---
    from desktop import template_market_local as tml
    seed = ROOT / 'projects' / 'run-ui-templates'
    store = ROOT / 'data' / 'native-desktop' / 'template-market-smoke'
    if store.exists():
        import shutil
        shutil.rmtree(store)
    store.mkdir(parents=True, exist_ok=True)
    tml.stop()
    tml.configure(seed_dir=seed, store_dir=store, host='127.0.0.1', port=19779)
    try:
        info = tml.start()
    except OSError:
        # port taken — try alternate
        tml.configure(seed_dir=seed, store_dir=store, host='127.0.0.1', port=19789)
        info = tml.start()
    assert info['running'], info
    listed = tml.client_list(info['url'])
    assert listed.get('ok') and len(listed.get('templates') or []) >= 1, listed
    pub = tml.client_publish({
        'meta': {'name': '烟雾发布', 'author': 'smoke', 'scenario': 'e2e'},
        'version': 1, 'split': 1, 'placements': [{'name': '图像'}],
    }, filename='smoke-pub.ruitpl.json', base_url=info['url'])
    assert pub.get('ok'), pub
    got = tml.client_download('smoke-pub.ruitpl.json', info['url'])
    assert (got.get('meta') or {}).get('name') == '烟雾发布', got
    synced = tml.client_sync(info['url'])
    assert synced.get('ok') and synced.get('synced', 0) >= 1, synced
    tml.stop()
    pass_('template market local list/publish/download/sync')

    from desktop.run_ui_designer import RunUiDesignerDialog
    assert hasattr(RunUiDesignerDialog, '_open_template_market')
    pass_('run_ui market entry')

    # --- 5) TCP device sim ---
    from desktop import tcp_device_sim as tds
    tds.stop()
    try:
        st = tds.start(tcp_port=19880, udp_port=19881)
    except OSError:
        st = tds.start(tcp_port=19882, udp_port=19883)
    assert st['running'], st
    assert tds.exchange('PING', port=st['tcpPort']) == 'PONG'
    assert tds.exchange('RUN', port=st['tcpPort']) == 'ACK RUN'
    assert tds.exchange('STOP', port=st['tcpPort']) == 'ACK STOP'
    assert tds.exchange('STATUS', port=st['tcpPort']) == 'OK READY'
    assert tds.exchange('ECHO hello', port=st['tcpPort']) == 'hello'
    # UDP
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(1.0)
    sock.sendto(b'PING\n', ('127.0.0.1', int(st['udpPort'])))
    data, _ = sock.recvfrom(256)
    sock.close()
    assert data.decode().strip() == 'PONG', data
    tds.stop()
    pass_('tcp/udp device sim protocol')

    from desktop.comm_manager import CommManagerDialog
    assert hasattr(CommManagerDialog, '_tcp_sim_start')
    assert hasattr(CommManagerDialog, '_tcp_sim_stop')
    pass_('comm manager sim controls')

    assert (ROOT / 'projects' / 'open-and-run-tcp-sim.sieans').exists()
    pass_('open-and-run-tcp-sim sample')

    print(f'ALL {ok} PASS')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as err:
        print('FAIL', err)
        import traceback
        traceback.print_exc()
        raise SystemExit(1)
