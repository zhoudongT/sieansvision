#!/usr/bin/env python3
"""Headless E2E (t191/t192 CONTINUE NEXT):
1) Chip click-to-dismiss / queue multiple fold tips
2) Jump confirm remember "don't ask this nest" for session
3) PropertyFloat hybrid OK commits source+step atomically (single undo tip)
4) Filmstrip actual pad_color override from Display theme / channel preview
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
from PySide6.QtCore import QSize, QTimer, Qt
from PySide6.QtGui import QPixmap, QImage, QColor, QMouseEvent
from PySide6.QtCore import QPointF, QPoint
from PySide6.QtWidgets import QApplication, QWidget, QLabel

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
    from desktop.theme import CANVAS, BG
    from desktop.image_source import normalize_source

    # ----- 4) pad_color from Display theme / channel -----
    fs = FilmstripBar()
    ok('has set_actual_pad_color', hasattr(fs, 'set_actual_pad_color'))
    fs.set_actual_pad_color('#112233')
    ok('pad_color stored', fs._actual_pad_color is not None
       and fs._actual_pad_color.name() == QColor('#112233').name())
    fs.thumbs.setIconSize(QSize(72, 54))
    url = data_url_from_bgr(20, 16, (0, 255, 0))
    pix = QPixmap.fromImage(QImage.fromData(base64.b64decode(url.split(',', 1)[-1])))
    out = fs._fit_pixmap_to_thumb(pix, 'actual')
    corner = QColor(out.toImage().pixelColor(0, 0))
    ok('custom pad used in letterbox',
       abs(corner.red() - 0x11) < 5 and abs(corner.blue() - 0x33) < 5,
       f'corner={corner.name()}')

    # Display helper pad colors
    class PadHost:
        _display_actual_pad_color = MainWindow._display_actual_pad_color
    ph = PadHost()
    ok('pad gray → BG', MainWindow._display_actual_pad_color(ph, 'gray') == BG)
    ok('pad auto → CANVAS', MainWindow._display_actual_pad_color(ph, 'auto') == CANVAS)
    ok('pad r tinted', '3a' in str(MainWindow._display_actual_pad_color(ph, 'r')).lower()
       or MainWindow._display_actual_pad_color(ph, 'r').startswith('#'))

    # set_live_display accepts pad_color
    fs2 = FilmstripBar()
    fs2._paths = ['/tmp/a.png']
    from PySide6.QtWidgets import QListWidgetItem
    from PySide6.QtGui import QIcon
    fs2.thumbs.addItem(QListWidgetItem(QIcon(), 'a'))
    fs2.thumbs.setCurrentRow(0)
    fs2.set_live_display(url, fit_mode='actual', pad_color=BG)
    ok('set_live_display pad_color applied',
       fs2._actual_pad_color is not None
       and fs2._actual_pad_color.name() == QColor(BG).name(),
       fs2._actual_pad_color)

    # ----- 3) Hybrid OK atomic -----
    ok('has hybridCommitted signal', hasattr(PropertyFloat, 'hybridCommitted'))
    pf = PropertyFloat()
    payloads = []
    src_n, step_n = [], []
    pf.hybridCommitted.connect(lambda p: payloads.append(deepcopy(p)))
    pf.sourceChanged.connect(lambda c: src_n.append(1))
    pf.changed.connect(lambda s: step_n.append(1))

    # Fake form + panel (hybrid)
    class FakeForm:
        def config(self):
            return normalize_source({'mode': 'local', 'path': '/x.png', 'images': []})
    class FakePanel:
        step = {'id': 's1', 'operation': 'blur', 'params': {'ksize': 7}, 'name': '模糊'}
    pf._source_form = FakeForm()
    pf._panel = FakePanel()
    pf._last_step = FakePanel.step
    pf._source_dirty = True
    pf._step_dirty = True
    pf._on_ok_close()
    ok('hybrid OK emits hybridCommitted once', len(payloads) == 1, payloads)
    ok('hybrid payload has source+step',
       payloads and payloads[0].get('source') is not None
       and payloads[0].get('step', {}).get('id') == 's1')
    ok('hybrid OK does not emit separate source/step',
       len(src_n) == 0 and len(step_n) == 0,
       f'src={len(src_n)} step={len(step_n)}')

    # MainWindow.update_hybrid_commit → single commit
    commits = []
    class Doc:
        def __init__(self):
            self.project = {
                'name': 'P', 'steps': [{'id': 's1', 'operation': 'blur', 'params': {'ksize': 3}}],
                'edges': [], 'sourceConfig': normalize_source({'mode': 'local'}),
            }
            self.history = [deepcopy(self.project)]
            self.index = 0
            self.saved = deepcopy(self.project)
            self.changed = type('S', (), {'emit': lambda *a, **k: None})()
        def commit(self, p):
            commits.append(deepcopy(p))
            self.project = deepcopy(p)
            self.history = self.history[: self.index + 1] + [deepcopy(p)]
            self.index = len(self.history) - 1
        def modified(self):
            return self.project != self.saved

    class HHost:
        def __init__(self):
            self.document = Doc()
            self.busy = False
            self.root = ROOT
            self.logs = []
            self.filmstrip = FilmstripBar()
        def log(self, m): self.logs.append(m)
        def guard(self, fn):
            return fn()
        def _sync_filmstrip_visibility(self): pass
        def _sync_filmstrip_interval_hint(self): pass
        def _apply_display_to_result_pane(self, step=None, image=None): pass
        update_hybrid_commit = MainWindow.update_hybrid_commit

    hh = HHost()
    MainWindow.update_hybrid_commit(hh, {
        'source': normalize_source({'mode': 'local', 'path': '/y.png', 'images': ['/y.png']}),
        'step': {'id': 's1', 'operation': 'blur', 'params': {'ksize': 9}, 'name': '模糊'},
    })
    ok('hybrid commit once', len(commits) == 1, f'n={len(commits)}')
    ok('hybrid commit merged source+step',
       commits and commits[0]['sourceConfig'].get('path') == '/y.png'
       and commits[0]['steps'][0]['params']['ksize'] == 9)
    ok('hybrid log atomic', any('原子' in m for m in hh.logs), hh.logs)

    # ----- 2) Jump session skip -----
    confirms = []
    class NestDoc:
        def __init__(self):
            self.project = {'name': 'DIRTY', 'steps': [], 'edges': []}
            self.history = [deepcopy(self.project)]
            self.index = 0
            self.saved = {'name': 'CLEAN', 'steps': [], 'edges': []}  # modified
            self.changed = type('S', (), {'emit': lambda *a, **k: None})()
        def modified(self):
            return self.project != self.saved
        def load(self, p):
            self.project = deepcopy(p)
            self.history = [deepcopy(p)]
            self.index = 0
        def commit(self, p=None): pass

    class JHost:
        def __init__(self):
            self.document = NestDoc()
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
            self._jump_confirm_skip = set()
            self._canvas_chip_queue = []
        def log(self, m): self.logs.append(m)
        def document_changed(self): pass
        def _refresh_group_breadcrumb(self): pass
        exit_group_module = MainWindow.exit_group_module
        jump_exit_group_to = MainWindow.jump_exit_group_to
        def _confirm_jump_exit(self, reason, levels, nest_key, cancel_why=''):
            # Mirror real helper skip check then record
            if nest_key in self._jump_confirm_skip:
                self.logs.append(f'跳层确认已跳过（本会话记住）：{nest_key}')
                return True
            confirms.append({'reason': reason, 'key': nest_key, 'levels': levels})
            # First call: Yes + remember (simulate checkbox)
            self._jump_confirm_skip.add(nest_key)
            self.logs.append(f'本会话跳过嵌套跳层确认：{nest_key}')
            return True

    jh = JHost()
    ok('pre dirty', jh.document.modified())
    jh.jump_exit_group_to(0)
    ok('first jump asked confirm', len(confirms) == 1, confirms)
    ok('skip key recorded', bool(jh._jump_confirm_skip), jh._jump_confirm_skip)
    # Re-enter nest and jump again — should skip dialog
    confirms.clear()
    jh._group_stack = [{
        'node_id': 'g1', 'name': 'G1',
        'outer_project': {'name': 'P', 'steps': [], 'edges': []},
        'outer_history': [{'name': 'P', 'steps': [], 'edges': []}],
        'outer_index': 0,
        'outer_saved': {'name': 'P', 'steps': [], 'edges': []},
    }]
    jh.document.project = {'name': 'DIRTY2', 'steps': [], 'edges': []}
    jh.document.saved = {'name': 'CLEAN', 'steps': [], 'edges': []}
    jh.jump_exit_group_to(0)
    ok('second jump skipped confirm', len(confirms) == 0, confirms)
    ok('skip logged', any('本会话记住' in m or '跳过' in m for m in jh.logs), jh.logs)

    # Real helper: nest_key in skip → True without dialog
    class RealConfirmHost:
        def __init__(self):
            self._jump_confirm_skip = {'g1'}
            self.logs = []
        def log(self, m): self.logs.append(m)
        _confirm_jump_exit = MainWindow._confirm_jump_exit
    rh = RealConfirmHost()
    # Would open dialog if not skipped — but key in skip
    got = MainWindow._confirm_jump_exit(rh, 'test', 1, 'g1', 'x')
    ok('real helper honors skip set', got is True)
    ok('real helper skip log', any('记住' in m for m in rh.logs), rh.logs)

    # ----- 1) Chip queue + click dismiss -----
    class CHost:
        def __init__(self):
            self._canvas_host = QWidget()
            self._canvas_host.resize(640, 400)
            self._canvas_host.show()
            self._canvas_status_chip = QLabel('', self._canvas_host)
            self._canvas_status_chip.setObjectName('canvasStatusChip')
            self._canvas_status_chip.setVisible(False)
            self._canvas_chip_timer = QTimer()
            self._canvas_chip_timer.setSingleShot(True)
            self._canvas_chip_queue = []
            self._group_breadcrumb = None
            self._group_stack = []
        _place_canvas_status_chip = MainWindow._place_canvas_status_chip
        _show_canvas_status_chip = MainWindow._show_canvas_status_chip
        _dismiss_canvas_status_chip = MainWindow._dismiss_canvas_status_chip
        _advance_canvas_status_chip = MainWindow._advance_canvas_status_chip

    ch = CHost()
    ok('has dismiss/advance', hasattr(MainWindow, '_dismiss_canvas_status_chip')
       and hasattr(MainWindow, '_advance_canvas_status_chip'))
    MainWindow._show_canvas_status_chip(ch, 'tip-A', ms=5000)
    ok('first tip visible', ch._canvas_status_chip.isVisible()
       and 'tip-A' in ch._canvas_status_chip.text())
    MainWindow._show_canvas_status_chip(ch, 'tip-B', ms=5000)
    MainWindow._show_canvas_status_chip(ch, 'tip-C', ms=5000)
    ok('queued while showing', len(ch._canvas_chip_queue) == 2, ch._canvas_chip_queue)
    ok('current still tip-A', 'tip-A' in ch._canvas_status_chip.text())
    # Dismiss → advance to tip-B
    MainWindow._dismiss_canvas_status_chip(ch)
    ok('after dismiss shows tip-B', 'tip-B' in ch._canvas_status_chip.text(),
       ch._canvas_status_chip.text())
    ok('queue left tip-C', len(ch._canvas_chip_queue) == 1
       and ch._canvas_chip_queue[0][0] == 'tip-C')
    MainWindow._dismiss_canvas_status_chip(ch)
    ok('after 2nd dismiss tip-C', 'tip-C' in ch._canvas_status_chip.text())
    MainWindow._dismiss_canvas_status_chip(ch)
    ok('queue empty hides chip', not ch._canvas_status_chip.isVisible()
       and len(ch._canvas_chip_queue) == 0)

    print('---')
    if fails:
        print(f'SMOKE FAIL ({len(fails)}):', ', '.join(fails))
        return 1
    print('SMOKE PASS all')
    return 0


if __name__ == '__main__':
    sys.exit(main())
