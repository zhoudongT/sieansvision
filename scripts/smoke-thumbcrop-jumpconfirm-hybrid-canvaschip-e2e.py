#!/usr/bin/env python3
"""Headless E2E (t191/t192 CONTINUE NEXT):
1) Filmstrip thumb honor cover/actual crop when Display live
2) Breadcrumb jump confirm when dirty nest tip would drop mid-redo
3) PropertyFloat Esc hybrid: discard both source+step baselines
4) Fold-boundary tip also on canvas status chip
Exit 0 on PASS. No robot SDK. No push.
"""
from __future__ import annotations

import base64
import os
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import numpy as np
import cv2
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QPixmap, QImage, QIcon
from PySide6.QtWidgets import QApplication, QMessageBox, QListWidgetItem

fails = []

def ok(name, cond, detail=''):
    if cond:
        print(f'PASS  {name}')
    else:
        fails.append(name)
        print(f'FAIL  {name}  {detail}')


def data_url_from_bgr(w, h, color=(0, 0, 255)):
    img = np.zeros((h, w, 3), dtype=np.uint8)
    img[:, :] = color
    _, enc = cv2.imencode('.png', img)
    return 'data:image/png;base64,' + base64.b64encode(enc.tobytes()).decode()


def main():
    app = QApplication.instance() or QApplication(sys.argv)
    # Auto-Yes for confirm in some tests; we'll stub per-call
    from desktop.widgets.filmstrip import FilmstripBar
    from desktop.property_float import PropertyFloat
    from desktop.mainwindow import MainWindow

    # ----- 1) Filmstrip cover/actual crop -----
    fs = FilmstripBar()
    fs._paths = ['/tmp/wide.png']
    fs.thumbs.clear()
    fs.thumbs.addItem(QListWidgetItem(QIcon(), 'wide'))
    fs.thumbs.setCurrentRow(0)
    fs.thumbs.setIconSize(QSize(72, 54))
    # Wide image 200x40 — cover should fill 72x54 (crop sides), contain letterbox, actual crop center
    url = data_url_from_bgr(200, 40, (0, 255, 0))
    ok('has _fit_pixmap_to_thumb', hasattr(fs, '_fit_pixmap_to_thumb'))

    # Unit-test fit helper directly
    # Build pixmap 200x40
    raw = base64.b64decode(url.split(',', 1)[-1])
    img = QImage.fromData(raw)
    pix = QPixmap.fromImage(img)
    c_contain = fs._fit_pixmap_to_thumb(pix, 'contain')
    c_cover = fs._fit_pixmap_to_thumb(pix, 'cover')
    c_actual = fs._fit_pixmap_to_thumb(pix, 'actual')
    ok('contain height fits in thumb', c_contain.height() <= 54 and c_contain.width() <= 72,
       f'{c_contain.width()}x{c_contain.height()}')
    ok('cover fills thumb exactly', c_cover.width() == 72 and c_cover.height() == 54,
       f'{c_cover.width()}x{c_cover.height()}')
    ok('actual is thumb-sized crop/pad', c_actual.width() == 72 and c_actual.height() == 54,
       f'{c_actual.width()}x{c_actual.height()}')
    # cover vs contain should differ for wide image
    ok('cover != contain for wide src', c_cover.toImage().bits() != c_contain.toImage().bits()
       or c_cover.width() != c_contain.width() or c_cover.height() != c_contain.height())

    fs.set_live_display(url, fit_mode='cover')
    ok('live fit mode cover stored', fs._live_fit_mode == 'cover')
    item = fs.thumbs.item(0)
    ok('icon set after cover live', item is not None and not item.icon().isNull())
    tip = item.toolTip() or ''
    ok('tip mentions fitMode=cover', 'fitMode=cover' in tip, tip)

    fs.set_live_display(url, fit_mode='actual')
    ok('live fit mode actual stored', fs._live_fit_mode == 'actual')

    # ----- 2) Jump confirm mid-redo -----
    confirms = []
    real_q = QMessageBox.question

    def fake_q(parent, title, text, *a, **k):
        confirms.append({'title': title, 'text': text})
        return QMessageBox.StandardButton.No  # cancel jump

    QMessageBox.question = staticmethod(fake_q)

    class NestDoc:
        class _Sig:
            def emit(self, *a, **k): pass
        def __init__(self, project):
            self.project = project
            self.history = [deepcopy(project)]
            self.index = 0
            self.saved = deepcopy(project)
            self.changed = NestDoc._Sig()
        def undo(self):
            if self.index:
                self.index -= 1
                self.project = deepcopy(self.history[self.index])
        def redo(self):
            if self.index + 1 < len(self.history):
                self.index += 1
                self.project = deepcopy(self.history[self.index])

    def make_group(gid, name, inner):
        return {
            'id': gid, 'name': name, 'operation': 'group',
            'params': {'bindings': {'ImageData': 'source', 'InputROI': 'source'},
                       'inner': {'steps': inner, 'edges': [], 'sourcePosition': {'x': 300, 'y': 40}}},
        }

    outer = {'name': '方案', 'steps': [make_group('g1', 'G1', [])], 'edges': [],
             'sourcePosition': {'x': 300, 'y': 40}}
    nest0 = {'name': 'n', 'steps': [], 'edges': [], 'sourcePosition': {'x': 300, 'y': 40}}
    nest1 = deepcopy(nest0); nest1['steps'] = [{'id': 'a', 'operation': 'display', 'params': {}}]
    nest2 = deepcopy(nest1); nest2['steps'].append({'id': 'b', 'operation': 'display', 'params': {}})

    class Host:
        def __init__(self):
            self.document = NestDoc(deepcopy(outer))
            self._group_stack = [{
                'node_id': 'g1', 'name': 'G1',
                'outer_project': deepcopy(outer),
                'outer_history': [deepcopy(outer)],
                'outer_index': 0, 'outer_saved': deepcopy(outer),
            }]
            self._nest_fold_marks = []
            self.logs = []
            self.scene = type('S', (), {'rebuild': lambda *a, **k: None})()
            self._canvas_status_chip = None
            self._canvas_host = None
            self._canvas_chip_timer = None
            self.wb_status = type('W', (), {'set_config': lambda *a, **k: None})()
        def log(self, m): self.logs.append(m)
        def document_changed(self): pass
        def _refresh_group_breadcrumb(self): pass
        exit_group_module = MainWindow.exit_group_module
        jump_exit_group_to = MainWindow.jump_exit_group_to
        _show_canvas_status_chip = MainWindow._show_canvas_status_chip
        _undo_with_fold_tip = MainWindow._undo_with_fold_tip
        _redo_with_fold_tip = MainWindow._redo_with_fold_tip
        _maybe_log_fold_cross = MainWindow._maybe_log_fold_cross

    host = Host()
    host.document.history = [nest0, nest1, nest2]
    host.document.index = 1  # mid-redo (tip is 2)
    host.document.project = deepcopy(nest1)
    host.jump_exit_group_to(0)
    ok('mid-redo jump shows confirm', bool(confirms) and '跳层退出确认' in confirms[0]['title'], confirms)
    ok('mid-redo No cancels jump', len(host._group_stack) == 1, f'depth={len(host._group_stack)}')
    ok('cancel logged', any('取消' in m for m in host.logs), host.logs)

    # Accept Yes and ensure exit proceeds
    confirms.clear()
    QMessageBox.question = staticmethod(
        lambda *a, **k: QMessageBox.StandardButton.Yes
    )
    host.jump_exit_group_to(0)
    ok('mid-redo Yes exits to root', len(host._group_stack) == 0)

    QMessageBox.question = real_q

    # ----- 3) Hybrid discard both -----
    pf = PropertyFloat()
    src_recv, step_recv = [], []
    pf.sourceChanged.connect(lambda c: src_recv.append(deepcopy(c)))
    pf.changed.connect(lambda s: step_recv.append(deepcopy(s)))
    pf._source_baseline = {'kind': 'local', 'path': '/a.png'}
    pf._source_dirty = True
    pf._step_baseline = {'id': 's1', 'operation': 'blur', 'params': {'ksize': 3}}
    pf._step_dirty = True
    pf._source_form = object()  # hybrid-ish
    pf._discard_draft_if_dirty()
    ok('hybrid discards source', src_recv and src_recv[-1].get('path') == '/a.png', src_recv)
    ok('hybrid discards step', step_recv and step_recv[-1]['params']['ksize'] == 3, step_recv)
    ok('hybrid clears both dirty', not pf._source_dirty and not pf._step_dirty)

    # ----- 4) Canvas status chip -----
    from PySide6.QtWidgets import QWidget, QLabel
    from PySide6.QtCore import QTimer
    host2 = Host()
    host2._canvas_host = QWidget()
    host2._canvas_host.resize(640, 400)
    host2._canvas_host.show()  # so child isVisible() reflects setVisible
    host2._canvas_status_chip = QLabel('', host2._canvas_host)
    host2._canvas_status_chip.setObjectName('canvasStatusChip')
    host2._canvas_status_chip.setVisible(False)
    host2._canvas_chip_timer = QTimer()
    host2._canvas_chip_timer.setSingleShot(True)
    host2._nest_fold_marks = [{'index': 0, 'name': 'G1', 'tips': 2, 'depth_after': 0}]
    host2.document.history = [outer, deepcopy(outer), deepcopy(outer)]
    host2.document.index = 2
    # Cross fold via undo
    host2.logs.clear()
    chip_shown = []
    orig_show = host2._show_canvas_status_chip
    def wrap_show(self_or_msg, msg=None, ms=3200):
        # bound method style
        if msg is None:
            msg = self_or_msg
            MainWindow._show_canvas_status_chip(host2, msg, ms=ms)
        else:
            MainWindow._show_canvas_status_chip(host2, msg, ms=ms)
        chip_shown.append(msg if msg is not None else self_or_msg)
    # Call fold tip path
    MainWindow._maybe_log_fold_cross(host2, 1, 0, 'undo')
    ok('fold tip logged', any('折叠点' in m for m in host2.logs), host2.logs)
    ok('canvas chip visible after fold tip', host2._canvas_status_chip.isVisible())
    ok('canvas chip text has 折叠点', '折叠点' in (host2._canvas_status_chip.text() or ''),
       host2._canvas_status_chip.text())

    # Direct API
    host2._canvas_status_chip.setVisible(False)
    MainWindow._show_canvas_status_chip(host2, '测试芯片 · nest fold')
    ok('show_canvas_status_chip shows', host2._canvas_status_chip.isVisible())
    ok('chip text set', '测试芯片' in host2._canvas_status_chip.text())

    print('---')
    if fails:
        print(f'SMOKE FAIL ({len(fails)}):', ', '.join(fails))
        return 1
    print('SMOKE PASS all')
    return 0


if __name__ == '__main__':
    sys.exit(main())
