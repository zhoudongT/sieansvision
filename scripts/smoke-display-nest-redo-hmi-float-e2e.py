#!/usr/bin/env python3
"""Headless E2E (t191/t192 CONTINUE NEXT):
1) Display fitMode/channel live apply on 模块结果 pane
2) Nest redo stack after multi-exit (depth≥3 redo chain)
3) HMI pause owner badge mirrors filmstrip mode tip
4) PropertyFloat non-source panels: Esc discard vs commit-on-change
Exit 0 on PASS. No robot SDK. No push.
"""
import os, sys
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from copy import deepcopy
from PySide6.QtWidgets import QApplication
import base64
import numpy as np
import cv2

app = QApplication.instance() or QApplication([])

fails = []
def ok(name, cond, detail=''):
    if cond:
        print(f'PASS  {name}')
    else:
        fails.append(name)
        print(f'FAIL  {name}  {detail}')

# ---------- 1. ImageView fitMode + live apply ----------
from desktop.image_view import ImageView
iv = ImageView()
iv.set_fit_mode('cover')
ok('ImageView.set_fit_mode cover', getattr(iv, '_fit_mode') == 'cover')
iv.set_fit_mode('actual')
ok('ImageView.set_fit_mode actual', getattr(iv, '_fit_mode') == 'actual')
iv.set_fit_mode('contain')
ok('ImageView.set_fit_mode contain', getattr(iv, '_fit_mode') == 'contain')

img = np.zeros((8, 8, 3), dtype=np.uint8)
img[:, :] = (0, 0, 255)
ok_enc, enc = cv2.imencode('.png', img)
data_url = 'data:image/png;base64,' + base64.b64encode(enc.tobytes()).decode()

from desktop.mainwindow import MainWindow
mw_src = open('desktop/mainwindow.py', encoding='utf-8').read()
ok('mainwindow has _apply_display_to_result_pane', '_apply_display_to_result_pane' in mw_src)
ok('mainwindow has _client_channel_preview', '_client_channel_preview' in mw_src)
ok('update_step applies display', "operation') == 'display'" in mw_src)

class FakeMW:
    def __init__(self):
        self.output_view = ImageView()
        self.images = type('T', (), {'setCurrentIndex': lambda *a, **k: None})()
        self._last_display_image = None
    _apply_display_to_result_pane = MainWindow._apply_display_to_result_pane
    _client_channel_preview = MainWindow._client_channel_preview

fake = FakeMW()
step = {'operation': 'display', 'params': {'fitMode': 'cover', 'channel': 'gray'}}
fake._apply_display_to_result_pane(step, image=data_url)
ok('live fitMode applied cover', getattr(fake.output_view, '_fit_mode') == 'cover')
ok('live channel cached', fake._last_display_image == data_url)
prev = fake._client_channel_preview(data_url, 'gray')
ok('client channel gray returns data-url', isinstance(prev, str) and prev.startswith('data:image'))
prev_r = fake._client_channel_preview(data_url, 'r')
ok('client channel r returns data-url', isinstance(prev_r, str) and prev_r.startswith('data:image'))
dp_src = open('desktop/wave3_thin_panels.py', encoding='utf-8').read()
ok('DisplayPanel channel combo', "findData(self.params.get('channel')" in dp_src)
ok('engine writes channel', "'channel': ch" in open('vision/engine.py', encoding='utf-8').read())

# ---------- 2. Nest redo stack depth≥3 ----------
from desktop.mainwindow import MainWindow as MW

class NestDoc:
    class _Sig:
        def emit(self, *a, **k): pass
    def __init__(self, project):
        self.project = project
        self.history = [deepcopy(project)]
        self.index = 0
        self.saved = deepcopy(project)
        self.changed = NestDoc._Sig()
    def load(self, p):
        self.project = deepcopy(p)
        self.history = [deepcopy(p)]
        self.index = 0
    def commit(self, p):
        self.history = self.history[: self.index + 1]
        self.history.append(deepcopy(p))
        self.index = len(self.history) - 1
        self.project = deepcopy(p)

class NestHost:
    def __init__(self, project):
        self.document = NestDoc(deepcopy(project))
        self._group_stack = []
        self.selected = None
        self.scene = type('S', (), {'rebuild': lambda *a, **k: None})()
    def log(self, *a, **k): pass
    def document_changed(self): pass
    def _refresh_group_breadcrumb(self): pass

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
    'steps': [make_group('g1', '组合A', [])],
    'edges': [],
    'sourcePosition': {'x': 300, 'y': 40},
}
host = NestHost(outer)
pre = deepcopy(host.document.project)
nest0 = {'name': '方案 / 组合A', 'steps': [], 'edges': [], 'sourcePosition': {'x': 300, 'y': 40}}
nest1 = deepcopy(nest0); nest1['steps'] = [{'id': 'a', 'name': 'A', 'operation': 'display', 'params': {}}]
nest2 = deepcopy(nest1); nest2['steps'].append({'id': 'b', 'name': 'B', 'operation': 'display', 'params': {}})
nest3 = deepcopy(nest2); nest3['steps'].append({'id': 'c', 'name': 'C', 'operation': 'display', 'params': {}})
host.document.history = [nest0, nest1, nest2, nest3]
host.document.index = 3
host.document.project = deepcopy(nest3)
host._group_stack = [{
    'node_id': 'g1', 'name': '组合A',
    'outer_project': deepcopy(pre),
    'outer_history': [deepcopy(pre)],
    'outer_index': 0,
    'outer_saved': deepcopy(pre),
}]
MW.exit_group_module(host)
ok('exit leaves empty stack', len(host._group_stack) == 0)
ok('outer hist length ≥ 4 (pre + 3 tips)', len(host.document.history) >= 4,
   f'len={len(host.document.history)}')
ok('index at tip after exit', host.document.index == len(host.document.history) - 1,
   f'idx={host.document.index} len={len(host.document.history)}')
for _ in range(3):
    if host.document.index > 0:
        host.document.index -= 1
        host.document.project = deepcopy(host.document.history[host.document.index])
ok('3 undos reach pre-enter', host.document.index == 0, f'idx={host.document.index}')
for _ in range(3):
    if host.document.index < len(host.document.history) - 1:
        host.document.index += 1
        host.document.project = deepcopy(host.document.history[host.document.index])
inner_after = None
for s in host.document.project.get('steps') or []:
    if s.get('id') == 'g1':
        inner_after = (s.get('params') or {}).get('inner') or {}
        break
n_steps = len((inner_after or {}).get('steps') or [])
ok('3 redos restore 3 nest steps', n_steps == 3, f'n_steps={n_steps}')

# Multi-exit depth≥3
outer2 = {
    'name': '方案',
    'steps': [make_group('g1', 'G1', [make_group('g2', 'G2', [make_group('g3', 'G3', [])])])],
    'edges': [], 'sourcePosition': {'x': 300, 'y': 40},
}
n0 = {'name': '…/G3', 'steps': [], 'edges': [], 'sourcePosition': {'x': 300, 'y': 40}}
n1 = deepcopy(n0); n1['steps'] = [{'id': 'x1', 'name': 'X1', 'operation': 'display', 'params': {}}]
n2 = deepcopy(n1); n2['steps'].append({'id': 'x2', 'name': 'X2', 'operation': 'display', 'params': {}})
n3 = deepcopy(n2); n3['steps'].append({'id': 'x3', 'name': 'X3', 'operation': 'display', 'params': {}})
g2_view = {
    'name': '…/G2',
    'steps': [make_group('g3', 'G3', [])],
    'edges': [], 'sourcePosition': {'x': 300, 'y': 40},
}
g1_view = {
    'name': '…/G1',
    'steps': [make_group('g2', 'G2', [make_group('g3', 'G3', [])])],
    'edges': [], 'sourcePosition': {'x': 300, 'y': 40},
}
host2 = NestHost(outer2)
host2.document.history = [n0, n1, n2, n3]
host2.document.index = 3
host2.document.project = deepcopy(n3)
host2._group_stack = [
    {
        'node_id': 'g1', 'name': 'G1',
        'outer_project': deepcopy(outer2),
        'outer_history': [deepcopy(outer2)],
        'outer_index': 0, 'outer_saved': deepcopy(outer2),
    },
    {
        'node_id': 'g2', 'name': 'G2',
        'outer_project': deepcopy(g1_view),
        'outer_history': [deepcopy(g1_view)],
        'outer_index': 0, 'outer_saved': deepcopy(g1_view),
    },
    {
        'node_id': 'g3', 'name': 'G3',
        'outer_project': deepcopy(g2_view),
        'outer_history': [deepcopy(g2_view)],
        'outer_index': 0, 'outer_saved': deepcopy(g2_view),
    },
]
MW.exit_group_module(host2)
ok('after exit g3 stack depth 2', len(host2._group_stack) == 2)
ok('g2-level hist has redo tips', len(host2.document.history) >= 4,
   f'len={len(host2.document.history)}')
MW.exit_group_module(host2)
ok('after exit g2 stack depth 1', len(host2._group_stack) == 1)
MW.exit_group_module(host2)
ok('after exit g1 stack empty', len(host2._group_stack) == 0)
ok('top-level hist length ≥ 4 after multi-exit', len(host2.document.history) >= 4,
   f'len={len(host2.document.history)}')
top_tip = host2.document.index
for _ in range(3):
    if host2.document.index > 0:
        host2.document.index -= 1
ok('multi-exit 3 undos from tip', host2.document.index <= top_tip - 3 or host2.document.index == 0,
   f'idx={host2.document.index} tip={top_tip}')
for _ in range(3):
    if host2.document.index < len(host2.document.history) - 1:
        host2.document.index += 1
        host2.document.project = deepcopy(host2.document.history[host2.document.index])

def count_deep(proj):
    def walk(steps):
        n = 0
        for s in steps or []:
            if str(s.get('id', '')).startswith('x'):
                n += 1
            if s.get('operation') == 'group':
                inn = (s.get('params') or {}).get('inner') or {}
                n += walk(inn.get('steps'))
        return n
    return walk(proj.get('steps'))
ok('multi-exit redo restores nested x* steps', count_deep(host2.document.project) >= 3,
   f'count={count_deep(host2.document.project)} idx={host2.document.index} hist={len(host2.document.history)}')

# ---------- 3. HMI pause owner badge ----------
from desktop.operator_hmi import ProductionStatsPanel, OperatorHmiView
psp = ProductionStatsPanel()
ok('ProductionStatsPanel has badge', hasattr(psp, '_pause_owner_badge'))
psp.set_pause_owner_badge('continuous')
ok('badge text continuous', psp._pause_owner_badge.text() == '模式·连续运行')
ok('badge tip mirrors filmstrip continuous',
   '与运行全部共用同一暂停控件' in (psp._pause_btn.toolTip() or ''))
psp.set_pause_owner_badge('run_all')
ok('badge text run_all', psp._pause_owner_badge.text() == '模式·运行全部')
ok('badge tip mirrors filmstrip run_all',
   '与连续运行共用同一暂停控件' in (psp._pause_btn.toolTip() or ''))
psp.set_pause_owner_badge(None)
ok('badge hidden when None', not psp._pause_owner_badge.isVisible())

hmi = OperatorHmiView()
hmi._stats_panels = [psp]
hmi.set_pause_owner_badge('continuous')
ok('HMI fan-out continuous', psp._pause_owner_badge.text() == '模式·连续运行')

from desktop.widgets.filmstrip import FilmstripBar
fs = FilmstripBar()
fs.set_pause_owner('continuous')
psp.set_pause_owner_badge('continuous')
ok('HMI tip == filmstrip tip (continuous)',
   fs.pause_btn.toolTip() == psp._pause_btn.toolTip(),
   f'fs={fs.pause_btn.toolTip()!r} hmi={psp._pause_btn.toolTip()!r}')
fs.set_pause_owner('run_all')
psp.set_pause_owner_badge('run_all')
ok('HMI tip == filmstrip tip (run_all)',
   fs.pause_btn.toolTip() == psp._pause_btn.toolTip(),
   f'fs={fs.pause_btn.toolTip()!r} hmi={psp._pause_btn.toolTip()!r}')

# ---------- 4. PropertyFloat non-source Esc discard ----------
from desktop.property_float import PropertyFloat
pf = PropertyFloat()
ok('has _step_baseline', hasattr(pf, '_step_baseline'))
step0 = {'id': 's1', 'name': '模糊', 'operation': 'blur', 'params': {'ksize': 3}}
try:
    pf.show_step(deepcopy(step0), {'name': '模糊', 'category': '图像'}, {'steps': []}, index=1)
    ok('show_step sets baseline', pf._step_baseline is not None and pf._step_baseline['params']['ksize'] == 3)
    ok('show_step subtitle has Esc tip', 'Esc' in (pf.subtitle.text() or ''))
except Exception as e:
    print('show_step err', e)
    pf._step_baseline = deepcopy(step0)
    pf._step_dirty = False
    pf._source_form = None
    ok('show_step sets baseline', False, str(e))
    ok('show_step subtitle has Esc tip', 'Esc·✕·取消放弃' in open('desktop/property_float.py', encoding='utf-8').read())

received = []
pf.changed.connect(lambda s: received.append(deepcopy(s)))
dirty = deepcopy(step0); dirty['params']['ksize'] = 9
pf._on_step_changed(dirty)
ok('step dirty after change', pf._step_dirty is True)
ok('live commit-on-change emitted', received and received[-1]['params']['ksize'] == 9)
received.clear()
pf._on_cancel_close()
ok('Esc discard restores baseline', received and received[-1]['params']['ksize'] == 3,
   f'received={received}')
ok('dirty cleared after cancel', pf._step_dirty is False)

pf2 = PropertyFloat()
try:
    pf2.show_step(deepcopy(step0), {'name': '模糊', 'category': '图像'}, {'steps': []}, index=1)
except Exception:
    pf2._step_baseline = deepcopy(step0)
    pf2._step_dirty = False
    pf2._source_form = None
dirty2 = deepcopy(step0); dirty2['params']['ksize'] = 5
pf2._on_step_changed(dirty2)
recv2 = []
pf2.changed.connect(lambda s: recv2.append(deepcopy(s)))
pf2._on_ok_close()
ok('OK clears baseline', pf2._step_baseline is None)
ok('OK does not emit baseline restore', not any(r.get('params', {}).get('ksize') == 3 for r in recv2))

print('---')
if fails:
    print(f'SMOKE FAIL ({len(fails)}):', ', '.join(fails))
    sys.exit(1)
print('SMOKE PASS all')
sys.exit(0)
