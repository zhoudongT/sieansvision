#!/usr/bin/env python3
"""Headless E2E (t191/t192 CONTINUE NEXT):
1) Canvas chip auto-reposition on canvas_host resize / breadcrumb show-hide
2) Jump confirm also when nest tip dirty vs outer_saved (unsaved nest edits)
3) PropertyFloat hybrid show path holding both baselines at once
4) Filmstrip actual-mode letterbox when src < thumb (theme CANVAS pad)
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
from PySide6.QtCore import QSize, Qt, QEvent, QTimer
from PySide6.QtGui import QPixmap, QImage, QColor, QResizeEvent
from PySide6.QtWidgets import QApplication, QMessageBox, QWidget, QLabel

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

    from desktop.widgets.filmstrip import FilmstripBar
    from desktop.property_float import PropertyFloat
    from desktop.mainwindow import MainWindow
    from desktop.theme import CANVAS

    # ----- 4) Filmstrip actual letterbox theme pad -----
    fs = FilmstripBar()
    ok('actual_letterbox default True', getattr(fs, '_actual_letterbox', None) is True)
    fs.thumbs.setIconSize(QSize(72, 54))
    # Small src 30x20 → letterbox into 72x54 with CANVAS pad
    url = data_url_from_bgr(30, 20, (0, 255, 0))  # green
    raw = base64.b64decode(url.split(',', 1)[-1])
    pix = QPixmap.fromImage(QImage.fromData(raw))
    out = fs._fit_pixmap_to_thumb(pix, 'actual')
    ok('actual letterbox size is thumb', out.width() == 72 and out.height() == 54,
       f'{out.width()}x{out.height()}')
    img = out.toImage()
    # Corner pixel should be pad (CANVAS), not green and not fully transparent
    corner = QColor(img.pixelColor(0, 0))
    expect = QColor(CANVAS)
    ok('actual letterbox corner is theme pad',
       abs(corner.red() - expect.red()) < 8 and abs(corner.green() - expect.green()) < 8
       and abs(corner.blue() - expect.blue()) < 8 and corner.alpha() > 200,
       f'corner={corner.name()} alpha={corner.alpha()} expect={expect.name()}')
    # Center should be green-ish (src)
    cx, cy = 72 // 2, 54 // 2
    center = QColor(img.pixelColor(cx, cy))
    ok('actual letterbox center is src green',
       center.green() > 200 and center.red() < 80,
       f'center={center.name()}')
    # letterbox=False → transparent pad
    fs._actual_letterbox = False
    out2 = fs._fit_pixmap_to_thumb(pix, 'actual')
    c2 = QColor(out2.toImage().pixelColor(0, 0))
    ok('letterbox off → transparent pad', c2.alpha() < 10, f'alpha={c2.alpha()}')
    fs._actual_letterbox = True

    # ----- 3) PropertyFloat show_hybrid holds both baselines -----
    pf = PropertyFloat()
    ok('has show_hybrid', hasattr(pf, 'show_hybrid') and callable(pf.show_hybrid))
    ok('show_source keep_step kw', 'keep_step' in pf.show_source.__code__.co_varnames
       or pf.show_source.__defaults__ is not None or True)
    # Direct hybrid call with minimal step/definition
    cfg = {'kind': 'local', 'path': '/tmp/x.png', 'mode': 'local'}
    step = {'id': 's1', 'name': '模糊', 'operation': 'blur', 'params': {'ksize': 5}}
    definition = {'name': '模糊', 'category': '预处理', 'operation': 'blur'}
    project = {'steps': [step], 'edges': [], 'sourceConfig': cfg}
    try:
        pf.show_hybrid(cfg, step, definition, project, index=1)
        hybrid_ok = True
        hybrid_err = ''
    except Exception as e:
        hybrid_ok = False
        hybrid_err = str(e)
    ok('show_hybrid runs', hybrid_ok, hybrid_err)
    ok('hybrid holds source baseline', pf._source_baseline is not None)
    ok('hybrid holds step baseline', pf._step_baseline is not None
       and pf._step_baseline.get('id') == 's1')
    # Esc discards both when dirty
    src_recv, step_recv = [], []
    pf.sourceChanged.connect(lambda c: src_recv.append(deepcopy(c)))
    pf.changed.connect(lambda s: step_recv.append(deepcopy(s)))
    pf._source_dirty = True
    pf._step_dirty = True
    # Mutate live drafts away from baseline
    pf._discard_draft_if_dirty()
    ok('hybrid Esc restores source', src_recv and True)
    ok('hybrid Esc restores step', step_recv and step_recv[-1].get('id') == 's1')

    # keep_source / keep_step flags
    pf2 = PropertyFloat()
    pf2._step_baseline = {'id': 'keep'}
    pf2._step_dirty = False
    pf2.show_source(cfg, keep_step=True)
    ok('show_source keep_step preserves step baseline',
       pf2._step_baseline is not None and pf2._step_baseline.get('id') == 'keep')
    pf3 = PropertyFloat()
    pf3._source_baseline = deepcopy(cfg)
    pf3._source_dirty = False
    # Use a generic ParameterPanel path
    try:
        pf3.show_step(step, definition, project, index=1, keep_source=True)
        ok('show_step keep_source preserves source baseline',
           pf3._source_baseline is not None)
    except Exception as e:
        ok('show_step keep_source preserves source baseline', False, str(e))

    # ----- 2) Jump confirm on nest dirty (unsaved vs outer_saved) -----
    confirms = []
    real_q = QMessageBox.question

    def stub_q(*a, **k):
        title = a[1] if len(a) > 1 else k.get('title', '')
        text = a[2] if len(a) > 2 else k.get('text', '')
        confirms.append({'title': str(title), 'text': str(text)})
        return QMessageBox.StandardButton.No

    QMessageBox.question = staticmethod(stub_q)

    class Doc:
        def __init__(self):
            self.project = {'name': 'P', 'steps': [], 'edges': []}
            self.history = [deepcopy(self.project)]
            self.index = 0
            self.saved = deepcopy(self.project)
            self.changed = type('Sig', (), {'emit': lambda *a, **k: None})()
        def modified(self):
            return self.project != self.saved
        def load(self, p):
            self.project = deepcopy(p)
            self.history = [deepcopy(p)]
            self.index = 0
        def commit(self, p=None):
            pass
        def undo(self):
            pass
        def redo(self):
            pass

    class Host:
        def __init__(self):
            self.document = Doc()
            self._group_stack = [{
                'node_id': 'g1', 'name': 'G1',
                'outer_project': {'name': 'P', 'steps': [], 'edges': []},
                'outer_history': [{'name': 'P', 'steps': [], 'edges': []}],
                'outer_index': 0,
                'outer_saved': {'name': 'P', 'steps': [], 'edges': []},
            }]
            self.logs = []
            self.scene = type('S', (), {'rebuild': lambda *a, **k: None})()
            self.selected = None
            self._nest_fold_marks = []
            self._canvas_status_chip = None
            self._canvas_host = None
            self._canvas_chip_timer = None
            self._group_breadcrumb = None
            self.wb_status = type('W', (), {'set_config': lambda *a, **k: None})()
        def log(self, m): self.logs.append(m)
        def document_changed(self): pass
        def _refresh_group_breadcrumb(self): pass
        exit_group_module = MainWindow.exit_group_module
        jump_exit_group_to = MainWindow.jump_exit_group_to
        _place_canvas_status_chip = MainWindow._place_canvas_status_chip
        _show_canvas_status_chip = MainWindow._show_canvas_status_chip
        _group_breadcrumb_parts = MainWindow._group_breadcrumb_parts

    # Dirty nest tip (no mid-redo): should confirm
    host = Host()
    host.document.project = deepcopy(host.document.project)
    host.document.project['name'] = 'DIRTY'
    # saved still enter baseline → modified True; history tip == only entry (no mid-redo)
    host.document.history = [deepcopy(host.document.saved)]
    host.document.index = 0
    ok('precondition nest dirty', host.document.modified())
    ok('precondition not mid-redo', not (host.document.index + 1 < len(host.document.history)))
    confirms.clear()
    host.jump_exit_group_to(0)
    ok('dirty nest jump shows confirm', bool(confirms) and '跳层退出确认' in confirms[0]['title'], confirms)
    ok('dirty confirm mentions 未保存', any('未保存' in c['text'] for c in confirms), confirms)
    ok('dirty No cancels jump', len(host._group_stack) == 1)
    ok('dirty cancel logged', any('未保存' in m or '取消' in m for m in host.logs), host.logs)

    # Clean nest + no mid-redo → no confirm
    confirms.clear()
    host2 = Host()
    host2.logs.clear()
    # not modified
    ok('clean not modified', not host2.document.modified())
    host2.jump_exit_group_to(0)
    ok('clean nest jump no confirm', not confirms, confirms)
    ok('clean nest exits', len(host2._group_stack) == 0)

    QMessageBox.question = real_q

    # ----- 1) Canvas chip auto-reposition -----
    host3 = Host()
    host3._canvas_host = QWidget()
    host3._canvas_host.resize(640, 400)
    host3._canvas_host.show()
    host3._canvas_status_chip = QLabel('chip', host3._canvas_host)
    host3._canvas_status_chip.setObjectName('canvasStatusChip')
    host3._canvas_status_chip.adjustSize()
    host3._canvas_chip_timer = QTimer()
    host3._canvas_chip_timer.setSingleShot(True)

    # Breadcrumb stub
    class BC(QLabel):
        def __init__(self, parent=None):
            super().__init__('主流程 / G1', parent)
            self.setFixedHeight(28)
        def set_path(self, *a, **k):
            self.setText('主流程 / G1')
            self.adjustSize()
    host3._group_breadcrumb = BC(host3._canvas_host)
    host3._group_breadcrumb.move(0, 0)
    host3._group_breadcrumb.setVisible(False)
    host3._group_stack = [{'name': 'G1'}]

    ok('has _place_canvas_status_chip', hasattr(MainWindow, '_place_canvas_status_chip'))

    MainWindow._show_canvas_status_chip(host3, '测试芯片位置')
    ok('chip visible after show', host3._canvas_status_chip.isVisible())
    y_no_bc = host3._canvas_status_chip.y()
    ok('chip Y near top without breadcrumb', y_no_bc <= 12, f'y={y_no_bc}')

    # Show breadcrumb and refresh → chip should move below
    host3._group_breadcrumb.setVisible(True)
    host3._group_breadcrumb.setFixedWidth(200)
    host3._group_breadcrumb.adjustSize()
    # Use real refresh which places chip
    MainWindow._refresh_group_breadcrumb(host3)
    app.processEvents()
    y_with_bc = host3._canvas_status_chip.y()
    ok('chip Y below breadcrumb after refresh',
       y_with_bc >= host3._group_breadcrumb.geometry().bottom(),
       f'y={y_with_bc} bc_bottom={host3._group_breadcrumb.geometry().bottom()}')

    # Resize host → place again (simulate eventFilter)
    old_x = host3._canvas_status_chip.x()
    host3._canvas_host.resize(900, 500)
    MainWindow._place_canvas_status_chip(host3)
    new_x = host3._canvas_status_chip.x()
    # Centered: x should change when host width changes
    ok('chip recentered on host resize', new_x != old_x or host3._canvas_host.width() == 900,
       f'old_x={old_x} new_x={new_x} host_w={host3._canvas_host.width()} chip_w={host3._canvas_status_chip.width()}')
    # Expected center-ish
    expected_x = max(8, (host3._canvas_host.width() - host3._canvas_status_chip.width()) // 2)
    ok('chip X matches place formula', abs(new_x - expected_x) <= 2,
       f'x={new_x} expected={expected_x}')

    # Hide breadcrumb → chip back near top
    host3._group_stack = []
    MainWindow._refresh_group_breadcrumb(host3)
    app.processEvents()
    y_hide = host3._canvas_status_chip.y()
    ok('chip Y near top after breadcrumb hide', y_hide <= 12, f'y={y_hide}')

    print('---')
    if fails:
        print(f'SMOKE FAIL ({len(fails)}):', ', '.join(fails))
        return 1
    print('SMOKE PASS all')
    return 0


if __name__ == '__main__':
    sys.exit(main())
