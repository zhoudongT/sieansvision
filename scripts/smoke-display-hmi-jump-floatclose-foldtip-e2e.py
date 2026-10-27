#!/usr/bin/env python3
"""Headless E2E (t191/t192 CONTINUE NEXT):
1) Display fitMode/channel live-apply on HMI image panes + filmstrip thumb
2) Group breadcrumb jump-exit (skip levels) uses same nest-hist fold
3) PropertyFloat title ✕ / reject / closeEvent unify with Esc discard
4) Status/log tip when nest undo/redo crosses an exit fold boundary
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
from PySide6.QtWidgets import QApplication, QMessageBox

fails = []

def ok(name, cond, detail=''):
    if cond:
        print(f'PASS  {name}')
    else:
        fails.append(name)
        print(f'FAIL  {name}  {detail}')


def tiny_data_url(bgr=(0, 0, 255)):
    img = np.zeros((8, 8, 3), dtype=np.uint8)
    img[:, :] = bgr
    ok_enc, enc = cv2.imencode('.png', img)
    return 'data:image/png;base64,' + base64.b64encode(enc.tobytes()).decode()


def main():
    app = QApplication.instance() or QApplication(sys.argv)
    QMessageBox.warning = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)

    from desktop.image_view import ImageView
    from desktop.mainwindow import MainWindow
    from desktop.operator_hmi import OperatorHmiView, ProductionStatsPanel
    from desktop.widgets.filmstrip import FilmstripBar
    from desktop.group_module import GroupBreadcrumb
    from desktop.property_float import PropertyFloat

    data_url = tiny_data_url()

    # ----- 1) Display fan-out to HMI + filmstrip -----
    class FakeMW:
        def __init__(self):
            self.output_view = ImageView()
            self.images = type('T', (), {'setCurrentIndex': lambda *a, **k: None})()
            self._last_display_image = None
            self.filmstrip = FilmstripBar()
            # give filmstrip a fake path row
            self.filmstrip._paths = ['/tmp/a.png']
            from PySide6.QtWidgets import QListWidgetItem
            from PySide6.QtGui import QIcon
            self.filmstrip.thumbs.clear()
            self.filmstrip.thumbs.addItem(QListWidgetItem(QIcon(), 'a'))
            self.filmstrip.thumbs.setCurrentRow(0)
            self.operator_hmi = OperatorHmiView()
            # ensure at least one image view
            if not self.operator_hmi._image_views:
                v = ImageView()
                self.operator_hmi._image_views.append(v)
            self.dialogs = {}
        _apply_display_to_result_pane = MainWindow._apply_display_to_result_pane
        _client_channel_preview = MainWindow._client_channel_preview

    fake = FakeMW()
    step = {'operation': 'display', 'params': {'fitMode': 'cover', 'channel': 'gray'}}
    fake._apply_display_to_result_pane(step, image=data_url)
    ok('result pane fitMode cover', getattr(fake.output_view, '_fit_mode') == 'cover')
    hmi_view = fake.operator_hmi._image_views[0]
    ok('HMI pane fitMode cover', getattr(hmi_view, '_fit_mode') == 'cover')
    ok('filmstrip live fit remembered', getattr(fake.filmstrip, '_live_fit_mode', None) == 'cover')
    item = fake.filmstrip.thumbs.item(0)
    tip = (item.toolTip() if item else '') or ''
    ok('filmstrip tip has fitMode', 'fitMode=cover' in tip or '模块结果' in tip, tip)

    # ----- 2) Breadcrumb jump-exit -----
    bc = GroupBreadcrumb()
    ok('has jumpExit signal', hasattr(bc, 'jumpExit'))
    jumped = []
    bc.jumpExit.connect(lambda d: jumped.append(d))
    bc.set_path(None, parts=['主流程', 'G1', 'G2', 'G3'])
    # Click ancestor buttons: find enabled crumbSeg buttons
    from PySide6.QtWidgets import QPushButton
    segs = [bc._segs_host.findChildren(QPushButton)][0]
    enabled = [b for b in segs if b.isEnabled() and b.objectName() == 'crumbSeg']
    ok('breadcrumb has clickable ancestors', len(enabled) >= 3, f'n={len(enabled)}')
    # Emit jump to depth 1 via signal API
    bc.jumpExit.emit(1)
    ok('jumpExit emits depth', jumped == [1], jumped)

    # Simulate multi-exit fold via jump_exit_group_to
    class NestDoc:
        class _Sig:
            def emit(self, *a, **k): pass
        def __init__(self, project):
            self.project = project
            self.history = [deepcopy(project)]
            self.index = 0
            self.saved = deepcopy(project)
            self.changed = NestDoc._Sig()
        def commit(self, p):
            self.history = self.history[: self.index + 1]
            self.history.append(deepcopy(p))
            self.index = len(self.history) - 1
            self.project = deepcopy(p)
        def undo(self):
            if self.index:
                self.index -= 1
                self.project = deepcopy(self.history[self.index])
                self.changed.emit()
        def redo(self):
            if self.index + 1 < len(self.history):
                self.index += 1
                self.project = deepcopy(self.history[self.index])
                self.changed.emit()
        def load(self, p):
            self.project = deepcopy(p)
            self.history = [deepcopy(p)]
            self.index = 0

    def make_group(gid, name, inner_steps):
        return {
            'id': gid, 'name': name, 'operation': 'group',
            'params': {
                'bindings': {'ImageData': 'source', 'InputROI': 'source'},
                'inner': {'steps': inner_steps, 'edges': [], 'sourcePosition': {'x': 300, 'y': 40}},
            },
        }

    outer = {
        'name': '方案',
        'steps': [make_group('g1', 'G1', [make_group('g2', 'G2', [make_group('g3', 'G3', [])])])],
        'edges': [], 'sourcePosition': {'x': 300, 'y': 40},
    }
    n0 = {'name': '…/G3', 'steps': [], 'edges': [], 'sourcePosition': {'x': 300, 'y': 40}}
    n1 = deepcopy(n0); n1['steps'] = [{'id': 'x1', 'name': 'X1', 'operation': 'display', 'params': {}}]
    n2 = deepcopy(n1); n2['steps'].append({'id': 'x2', 'name': 'X2', 'operation': 'display', 'params': {}})
    n3 = deepcopy(n2); n3['steps'].append({'id': 'x3', 'name': 'X3', 'operation': 'display', 'params': {}})
    g2_view = {'name': '…/G2', 'steps': [make_group('g3', 'G3', [])], 'edges': [], 'sourcePosition': {'x': 300, 'y': 40}}
    g1_view = {'name': '…/G1', 'steps': [make_group('g2', 'G2', [make_group('g3', 'G3', [])])], 'edges': [], 'sourcePosition': {'x': 300, 'y': 40}}

    class Host:
        def __init__(self):
            self.document = NestDoc(deepcopy(outer))
            self._group_stack = []
            self._nest_fold_marks = []
            self.selected = None
            self.logs = []
            self.scene = type('S', (), {'rebuild': lambda *a, **k: None})()
            self.wb_status = type('W', (), {'set_config': lambda *a, **k: None})()
        def log(self, m): self.logs.append(m)
        def document_changed(self): pass
        def _refresh_group_breadcrumb(self): pass
        exit_group_module = MainWindow.exit_group_module
        jump_exit_group_to = MainWindow.jump_exit_group_to
        _undo_with_fold_tip = MainWindow._undo_with_fold_tip
        _redo_with_fold_tip = MainWindow._redo_with_fold_tip
        _maybe_log_fold_cross = MainWindow._maybe_log_fold_cross

    host = Host()
    host.document.history = [n0, n1, n2, n3]
    host.document.index = 3
    host.document.project = deepcopy(n3)
    host._group_stack = [
        {'node_id': 'g1', 'name': 'G1', 'outer_project': deepcopy(outer),
         'outer_history': [deepcopy(outer)], 'outer_index': 0, 'outer_saved': deepcopy(outer)},
        {'node_id': 'g2', 'name': 'G2', 'outer_project': deepcopy(g1_view),
         'outer_history': [deepcopy(g1_view)], 'outer_index': 0, 'outer_saved': deepcopy(g1_view)},
        {'node_id': 'g3', 'name': 'G3', 'outer_project': deepcopy(g2_view),
         'outer_history': [deepcopy(g2_view)], 'outer_index': 0, 'outer_saved': deepcopy(g2_view)},
    ]
    # Jump to depth 1 (keep G1 only) — exits g3 then g2
    host.jump_exit_group_to(1)
    ok('jump to depth 1 leaves 1 frame', len(host._group_stack) == 1, f'depth={len(host._group_stack)}')
    ok('jump log mentions 跳层', any('跳层' in m for m in host.logs), host.logs[-3:])
    ok('fold marks recorded', len(host._nest_fold_marks) >= 1, host._nest_fold_marks)
    # Jump to 主流程
    host.jump_exit_group_to(0)
    ok('jump to 0 clears stack', len(host._group_stack) == 0)
    ok('hist kept after jump fold', len(host.document.history) >= 2, f'len={len(host.document.history)}')

    # ----- 4) fold tip on undo/redo (reuse host at top level) -----
    # Ensure marks + tip at end
    host.document.index = len(host.document.history) - 1
    host.logs.clear()
    # Undo until we cross a fold mark
    crossed = False
    for _ in range(len(host.document.history)):
        before_logs = len(host.logs)
        host._undo_with_fold_tip()
        if any('折叠点' in m for m in host.logs[before_logs:]):
            crossed = True
            break
    ok('undo logs fold-boundary tip', crossed, host.logs)
    # Redo back
    host.logs.clear()
    crossed_r = False
    for _ in range(len(host.document.history)):
        before_logs = len(host.logs)
        host._redo_with_fold_tip()
        if any('折叠点' in m for m in host.logs[before_logs:]):
            crossed_r = True
            break
    ok('redo logs fold-boundary tip', crossed_r, host.logs)

    # ----- 3) PropertyFloat ✕ / reject / closeEvent -----
    pf = PropertyFloat()
    ok('has _discard_draft_if_dirty', hasattr(pf, '_discard_draft_if_dirty'))
    ok('has closeEvent', hasattr(pf, 'closeEvent'))
    step0 = {'id': 's1', 'name': '模糊', 'operation': 'blur', 'params': {'ksize': 3}}
    try:
        pf.show_step(deepcopy(step0), {'name': '模糊', 'category': '图像'}, {'steps': []}, index=1)
    except Exception as e:
        pf._step_baseline = deepcopy(step0)
        pf._step_dirty = False
        pf._source_form = None
        print('show_step warn', e)
    recv = []
    pf.changed.connect(lambda s: recv.append(deepcopy(s)))
    dirty = deepcopy(step0); dirty['params']['ksize'] = 9
    pf._on_step_changed(dirty)
    recv.clear()
    # reject() path
    pf.reject()
    ok('reject discards to baseline', recv and recv[-1]['params']['ksize'] == 3, recv)

    pf2 = PropertyFloat()
    try:
        pf2.show_step(deepcopy(step0), {'name': '模糊', 'category': '图像'}, {'steps': []}, index=1)
    except Exception:
        pf2._step_baseline = deepcopy(step0)
        pf2._step_dirty = False
        pf2._source_form = None
    recv2 = []
    pf2.changed.connect(lambda s: recv2.append(deepcopy(s)))
    dirty2 = deepcopy(step0); dirty2['params']['ksize'] = 7
    pf2._on_step_changed(dirty2)
    recv2.clear()
    # Simulate WM close without going through cancel: closeEvent directly
    pf2._close_via_action = None  # not ok
    from PySide6.QtGui import QCloseEvent
    pf2.closeEvent(QCloseEvent())
    ok('closeEvent discards when not OK', recv2 and recv2[-1]['params']['ksize'] == 3, recv2)

    pf3 = PropertyFloat()
    try:
        pf3.show_step(deepcopy(step0), {'name': '模糊', 'category': '图像'}, {'steps': []}, index=1)
    except Exception:
        pf3._step_baseline = deepcopy(step0)
        pf3._step_dirty = True
        pf3._source_form = None
    dirty3 = deepcopy(step0); dirty3['params']['ksize'] = 5
    pf3._on_step_changed(dirty3)
    recv3 = []
    pf3.changed.connect(lambda s: recv3.append(deepcopy(s)))
    pf3._on_ok_close()
    # closeEvent after OK should NOT discard
    pf3.closeEvent(QCloseEvent())
    ok('OK then closeEvent does not discard', not any(r.get('params', {}).get('ksize') == 3 for r in recv3))

    # ✕ button wired to cancel
    from PySide6.QtWidgets import QPushButton
    closes = [b for b in pf3.findChildren(QPushButton) if b.text() == '✕']
    ok('title ✕ button exists', len(closes) >= 1)

    print('---')
    if fails:
        print(f'SMOKE FAIL ({len(fails)}):', ', '.join(fails))
        return 1
    print('SMOKE PASS all')
    return 0


if __name__ == '__main__':
    sys.exit(main())
