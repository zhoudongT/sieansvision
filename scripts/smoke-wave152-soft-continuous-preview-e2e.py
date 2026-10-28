#!/usr/bin/env python3
"""wave152: soft continuous-preview timing — gate drop-old + ImageView live path."""
from __future__ import annotations
import os, sys, ast, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / '.pydeps'))
os.chdir(ROOT)
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

fails, passes = [], []


def ok(n, c, d=''):
    if c:
        passes.append(n)
        print(f'PASS  {n}')
    else:
        fails.append(n)
        print(f'FAIL  {n}  {d}')


def main():
    from desktop.soft_acquisition_chrome import (
        LIVE_PREVIEW_POLICY, PreviewFrameGate,
        live_preview_interval_ms, live_preview_ui_min_interval_ms,
        live_capture_frame_policy, live_preview_drop_old,
        session_stat_rows, summarize_session,
    )

    ok('policy dropOldFrame', LIVE_PREVIEW_POLICY.get('dropOldFrame') is True)
    ok('policy framePolicy latest', LIVE_PREVIEW_POLICY.get('framePolicy') == 'latest')
    ok('policy uiMinIntervalMs', int(LIVE_PREVIEW_POLICY.get('uiMinIntervalMs') or 0) >= 16)
    ok('antiFlicker still in_place', LIVE_PREVIEW_POLICY.get('antiFlicker') == 'in_place_pixmap')
    ok('interval helpers', live_preview_interval_ms() == 50 and live_preview_interval_ms(manager=True) == 120)
    ok('ui min helper', live_preview_ui_min_interval_ms() == int(LIVE_PREVIEW_POLICY['uiMinIntervalMs']))
    ok('frame policy helper', live_capture_frame_policy() == 'latest')
    ok('drop old helper', live_preview_drop_old() is True)

    # Gate: rapid offers → drop old + throttle paints
    gate = PreviewFrameGate(min_interval_ms=40)
    t0 = 1000.0
    first = gate.offer('frame-0', seq=0, now_ms=t0)
    ok('first offer paints', first == 'frame-0', first)
    # burst within interval — all coalesced, only latest pending
    for i in range(1, 12):
        r = gate.offer(f'frame-{i}', seq=i, now_ms=t0 + i * 2)  # 2ms apart
        ok(f'burst {i} throttled', r is None, r)
    ok('pending after burst', gate.has_pending() is True)
    st = gate.stats()
    ok('offered ≥12', st['offered'] >= 12, st)
    ok('dropped ≥1', st['dropped'] >= 1, st)
    ok('painted ==1 so far', st['painted'] == 1, st)
    # flush after interval
    due = gate.flush_due(now_ms=t0 + 50)
    ok('flush paints latest', due == 'frame-11', due)
    st2 = gate.stats()
    ok('painted ==2 after flush', st2['painted'] == 2, st2)
    ok('no pending after flush', gate.has_pending() is False)

    # N-frame continuous soft sim: no exception, stats sane
    gate2 = PreviewFrameGate(min_interval_ms=10)
    N = 30
    painted_payloads = []
    for i in range(N):
        now = 2000.0 + i * 5  # 5ms offers → many drops at 10ms min
        out = gate2.offer(f'sim-{i}', seq=i, now_ms=now)
        if out is not None:
            painted_payloads.append(out)
        elif gate2.has_pending() and gate2.ms_until_due(now_ms=now) == 0:
            flushed = gate2.flush_due(now_ms=now)
            if flushed:
                painted_payloads.append(flushed)
    # drain
    end = 2000.0 + N * 5 + 20
    while gate2.has_pending():
        f = gate2.flush_due(now_ms=end)
        if f:
            painted_payloads.append(f)
        else:
            end += 10
            if end > 2000 + N * 5 + 200:
                break
    st3 = gate2.stats()
    ok(f'continuous N={N} no crash', True)
    ok('continuous painted < offered', st3['painted'] < st3['offered'], st3)
    ok('continuous dropped > 0', st3['dropped'] > 0, st3)
    ok('continuous painted ≥1', st3['painted'] >= 1, st3)
    ok('last payload is latest-ish', painted_payloads[-1].startswith('sim-') if painted_payloads else False, painted_payloads[-1:] )

    sess = summarize_session({
        'state': 'running', 'received': 20, 'frameAgeMs': 12,
        'config': {'params': {'driver': 'simulator', 'deviceId': 'synthetic-parts'}},
    })
    rows = session_stat_rows(sess)
    labels = [r[0] for r in rows]
    ok('stat has 丢旧帧', '丢旧帧' in labels, labels)
    ok('stat has UI节流', 'UI节流 ms' in labels, labels)

    # AST wiring
    for rel, needles in (
        ('desktop/soft_acquisition_chrome.py', ('PreviewFrameGate', 'dropOldFrame', 'uiMinIntervalMs')),
        ('desktop/image_view.py', ('show_live_frame', '_set_live_pixmap', '_live_pixmap_item')),
        ('desktop/camera_manager.py', ('PreviewFrameGate', '_paint_live_preview', 'live_capture_frame_policy')),
        ('desktop/device_dialogs.py', ('PreviewFrameGate', '_paint_live_preview', 'wave152')),
        ('desktop/mainwindow.py', ('show_live_frame', 'set_live_preview_image')),
        ('desktop/operator_hmi.py', ('set_live_preview_image', 'show_live_frame')),
        ('desktop/image_source.py', ('live_preview_ui_min_interval_ms', 'wave152')),
    ):
        src = (ROOT / rel).read_text(encoding='utf-8')
        ok(f'AST {rel}', isinstance(ast.parse(src), ast.AST))
        for n in needles:
            ok(f'{Path(rel).name} has {n}', n in src)

    docs = (ROOT / 'docs/open-and-run-samples.md').read_text(encoding='utf-8')
    ok('docs mention wave152', 'wave152' in docs)

    # Qt: ImageView continuous live frames update widget, no exception
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QImage, QPainter, QColor
    import base64
    from io import BytesIO

    app = QApplication.instance() or QApplication(sys.argv)
    from desktop.image_view import ImageView

    def make_frame(i, w=64, h=48):
        img = QImage(w, h, QImage.Format.Format_RGB32)
        img.fill(QColor(20 + (i * 7) % 200, 40, 80 + (i * 3) % 150))
        painter = QPainter(img)
        painter.setPen(QColor('white'))
        painter.drawText(8, 24, f'#{i}')
        painter.end()
        ba = __import__('PySide6.QtCore', fromlist=['QByteArray']).QByteArray()
        buf = __import__('PySide6.QtCore', fromlist=['QBuffer']).QBuffer(ba)
        buf.open(__import__('PySide6.QtCore', fromlist=['QIODevice']).QIODevice.OpenModeFlag.WriteOnly)
        img.save(buf, 'PNG')
        buf.close()
        b64 = bytes(ba.data()).decode('latin1')
        # QByteArray.data() is bytes — use toBase64
        from PySide6.QtCore import QByteArray
        ba2 = QByteArray()
        from PySide6.QtCore import QBuffer, QIODevice
        buf2 = QBuffer(ba2)
        buf2.open(QIODevice.OpenModeFlag.WriteOnly)
        img.save(buf2, 'PNG')
        buf2.close()
        return 'data:image/png;base64,' + bytes(ba2.toBase64()).decode()

    view = ImageView()
    view.resize(320, 240)
    view.show()
    app.processEvents()
    frames = [make_frame(i) for i in range(8)]
    ok('synthetic frames ready', all(f.startswith('data:image') for f in frames))
    item_ids = []
    for i, fr in enumerate(frames):
        ok(f'live frame {i} no exc', view.show_live_frame(fr) is True)
        app.processEvents()
        item_ids.append(id(view._live_pixmap_item) if view._live_pixmap_item else None)
    ok('pixmap item stable after first', len(set(item_ids[1:])) == 1 and item_ids[0] is not None, item_ids)
    ok('bounds non-empty', not view.bounds.isEmpty())
    ok('live pixmap non-null', not view._live_pixmap.isNull())

    # Gate + view together for N frames
    gate3 = PreviewFrameGate(min_interval_ms=15)
    painted = 0
    t = time.monotonic() * 1000
    for i in range(20):
        now = t + i * 4
        out = gate3.offer(frames[i % len(frames)], seq=i, now_ms=now)
        if out:
            view.show_live_frame(out)
            painted += 1
            app.processEvents()
    # drain
    for _ in range(5):
        f = gate3.flush_due(now_ms=t + 500)
        if f:
            view.show_live_frame(f)
            painted += 1
            app.processEvents()
    ok('gate+view painted ≥1', painted >= 1, painted)
    ok('gate+view dropped', gate3.stats()['dropped'] >= 1, gate3.stats())
    ok('widget still has pixmap item', view._live_pixmap_item is not None)

    print()
    print(f'PASS {len(passes)}  FAIL {len(fails)}')
    if fails:
        print('Failed:', *fails, sep='\n  ')
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
