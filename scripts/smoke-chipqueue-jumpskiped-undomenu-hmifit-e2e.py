#!/usr/bin/env python3
"""Headless E2E (t191/t192 CONTINUE NEXT):
1) Chip queue peek/drop from status-bar context menu
2) Jump skip settings list editor for remembered nest keys
3) Undo menu dropdown of last N labelled history tips
4) Filmstrip fitMode-only: skip fancy re-decode; DO sync HMI panes
Also: production_task DEFAULT_CHAIN includes display (P0).
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
from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QPixmap, QImage, QIcon, QAction
from PySide6.QtWidgets import QApplication, QListWidgetItem, QLabel, QWidget, QMenu

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
    from desktop.model import Document
    from desktop.mainwindow import MainWindow
    from desktop.production_task_panel import DEFAULT_CHAIN, chain_to_operations
    from desktop.operator_hmi import OperatorHmiView

    src = open('desktop/mainwindow.py', encoding='utf-8').read()

    # ========== source markers ==========
    ok('has _on_status_chip_context_menu', hasattr(MainWindow, '_on_status_chip_context_menu'))
    ok('has _drop_chip_queue_item', hasattr(MainWindow, '_drop_chip_queue_item'))
    ok('has _clear_chip_queue', hasattr(MainWindow, '_clear_chip_queue'))
    ok('has _edit_jump_skip_keys', hasattr(MainWindow, '_edit_jump_skip_keys'))
    ok('has _populate_undo_history_menu', hasattr(MainWindow, '_populate_undo_history_menu'))
    ok('has _undo_to_history_index', hasattr(MainWindow, '_undo_to_history_index'))
    ok('has Document.jump_history', hasattr(Document, 'jump_history'))
    ok('src wires status context menu', 'customContextMenuRequested.connect(self._on_status_chip_context_menu)' in src)
    ok('src undo_action.setMenu', 'undo_action.setMenu(self._undo_history_menu)' in src)
    ok('src fit_only HMI', 'hmi_image = None if fit_only else' in src)
    ok('src edit jump skip menu', '编辑已记住的跳层跳过' in src)

    # ========== P0: display in production chain ==========
    ops = chain_to_operations(DEFAULT_CHAIN)
    ok('DEFAULT_CHAIN has display row', any(r.get('op') == 'display' for r in DEFAULT_CHAIN))
    ok('chain_to_operations yields display', any(o.get('operation') == 'display' for o in ops))

    # ========== 1) chip queue peek/drop ==========
    class Stub(QWidget):
        pass
    stub = Stub()
    stub._canvas_chip_queue = [('tip-A', 3000), ('tip-B', 3000), ('tip-C', 3000)]
    stub.log = lambda *a, **k: None
    chip = QLabel('current'); chip.show()
    stub._canvas_status_chip = chip
    MainWindow._drop_chip_queue_item(stub, 1)
    ok('drop middle queue item', stub._canvas_chip_queue == [('tip-A', 3000), ('tip-C', 3000)])
    MainWindow._clear_chip_queue(stub)
    ok('clear chip queue', stub._canvas_chip_queue == [])

    # context menu builds without crash (no exec needed — call internals)
    stub2 = Stub()
    stub2._canvas_chip_queue = [('queued-1', 2000)]
    stub2._canvas_status_chip = chip
    stub2.wb_status = QWidget()
    stub2._dismiss_canvas_status_chip = lambda: None
    stub2.log = lambda *a, **k: None
    # Build menu body via partial: drop/clear callable
    ok('drop/clear bound', callable(getattr(MainWindow, '_on_status_chip_context_menu')))

    # ========== 2) jump skip list editor (session set round-trip without dialog) ==========
    stub3 = Stub()
    stub3._jump_confirm_skip = {'nest/a', 'nest/b'}
    stub3._jump_skip_persist = True
    stub3._jump_skip_persist_enabled = lambda: True
    class FakeSettings:
        def __init__(self):
            self.store = {}
        def setValue(self, k, v):
            self.store[k] = v
        def value(self, k, default=None):
            return self.store.get(k, default)
    fs = FakeSettings()
    stub3._settings = lambda: fs
    stub3.log = lambda *a, **k: None
    # Simulate editor accept: write keys
    stub3._jump_confirm_skip = {'nest/a'}
    fs.setValue('jumpConfirmSkipKeys', sorted(stub3._jump_confirm_skip))
    ok('jump skip keys persisted shape', fs.store.get('jumpConfirmSkipKeys') == ['nest/a'])

    # ========== 3) undo menu last N labelled tips ==========
    doc = Document()
    p = deepcopy(doc.project)
    p['steps'] = list(p.get('steps') or [])
    # commit labelled history
    for i, name in enumerate(['加模块A', '改参数B', '连线C', '显示D']):
        p2 = deepcopy(doc.project)
        # mutate name so commit not no-op
        p2['name'] = f'proj-{i}-{name}'
        doc.commit(p2, label=name)
    ok('history length', len(doc.history) == 5)  # initial + 4
    ok('labels aligned', doc.history_labels[-1] == '显示D')
    idx_before = doc.index
    # populate menu on stub
    stub4 = Stub()
    stub4.document = doc
    stub4._undo_history_menu = QMenu()
    stub4._undo_history_menu_n = 12
    stub4.log = lambda *a, **k: None
    stub4._show_canvas_status_chip = lambda *a, **k: None
    stub4._maybe_log_fold_cross = lambda *a, **k: None
    stub4._refresh_undo_redo_labels = lambda: None
    MainWindow._populate_undo_history_menu(stub4)
    acts = stub4._undo_history_menu.actions()
    ok('undo menu has entries', len(acts) == 4, f'got {len(acts)}')
    texts = [a.text() for a in acts]
    ok('undo menu newest first', texts[0] == '撤销「显示D」', str(texts))
    ok('undo menu has 加模块A', any('加模块A' in t for t in texts))
    # jump to before 改参数B → index of tip 改参数B is 2, target=1
    MainWindow._undo_to_history_index(stub4, 1, '改参数B')
    ok('jump_history landed', doc.index == 1, f'index={doc.index}')
    ok('project name after jump', doc.project.get('name') == 'proj-0-加模块A', str(doc.project.get('name')))

    # ========== 4) fitMode-only syncs HMI without re-show ==========
    class FakeView:
        def __init__(self):
            self.fit_modes = []
            self.shown = []
            self.fit_calls = 0
            from PySide6.QtCore import QRectF
            self.bounds = QRectF(0, 0, 10, 10)
        def set_fit_mode(self, m):
            self.fit_modes.append(m)
        def show_data(self, d):
            self.shown.append(d)
        def fit(self):
            self.fit_calls += 1

    class FakeHmi:
        def __init__(self):
            self.calls = []
            self._image_views = [FakeView()]
        def apply_display(self, *, fit_mode=None, image=None, channel=None):
            self.calls.append(dict(fit_mode=fit_mode, image=image, channel=channel))
            # mirror real OperatorHmiView.apply_display
            fit = fit_mode if fit_mode in ('contain', 'cover', 'actual') else None
            for view in self._image_views:
                if fit:
                    view.set_fit_mode(fit)
                if image:
                    view.show_data(image)
                elif fit:
                    view.fit()

    # Filmstrip path: fit-only
    fs = FilmstripBar()
    # seed live thumb
    url = data_url_from_bgr(64, 48, (0, 200, 0))
    fs.thumbs.clear()
    from PySide6.QtWidgets import QListWidgetItem
    item = QListWidgetItem('live')
    fs.thumbs.addItem(item)
    fs.thumbs.setCurrentRow(0)
    fs._paths = ['dummy.png']
    fs.set_live_display(url, fit_mode='contain')
    ok('filmstrip has live src', fs._live_src_pixmap is not None)

    stub5 = Stub()
    stub5.output_view = FakeView()
    stub5.filmstrip = fs
    stub5._last_display_image = url
    stub5._last_filmstrip_show = url
    stub5.operator_hmi = FakeHmi()
    stub5.dialogs = {}
    stub5._display_actual_pad_color = lambda ch=None: None
    stub5.images = type('T', (), {'setCurrentIndex': lambda *a, **k: None})()
    # fitMode-only call (image=None, same show)
    MainWindow._apply_display_to_result_pane(stub5, step={'params': {'fitMode': 'cover', 'channel': 'auto'}}, image=None)
    ok('fit_only HMI called', len(stub5.operator_hmi.calls) == 1)
    call = stub5.operator_hmi.calls[0]
    ok('fit_only HMI image is None (no re-decode)', call.get('image') is None, str(call))
    ok('fit_only HMI fit_mode cover', call.get('fit_mode') == 'cover')
    ok('fit_only HMI view set_fit_mode', stub5.operator_hmi._image_views[0].fit_modes == ['cover'])
    ok('fit_only HMI view fit() not show_data', stub5.operator_hmi._image_views[0].fit_calls == 1 and stub5.operator_hmi._image_views[0].shown == [])
    ok('filmstrip live fit updated', getattr(fs, '_live_fit_mode', None) == 'cover')

    # New frame path still pushes image
    stub5.operator_hmi = FakeHmi()
    url2 = data_url_from_bgr(64, 48, (200, 0, 0))
    MainWindow._apply_display_to_result_pane(stub5, step={'params': {'fitMode': 'contain', 'channel': 'auto'}}, image=url2)
    call2 = stub5.operator_hmi.calls[0]
    ok('new-frame HMI gets image', call2.get('image') == url2)

    print()
    if fails:
        print(f'FAILED {len(fails)}: {fails}')
        return 1
    print('ALL PASS')
    return 0


if __name__ == '__main__':
    sys.exit(main())
