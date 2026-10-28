#!/usr/bin/env python3
"""Wave soft: hostWatch chip click→var-watch · recipe rollback stack panel ·
painted MatchScoreSparkWidget · runUi designer blink chords.
No Halcon / robot / real TCP / cloud. Leave ?? os and :18280 alone.
"""
from __future__ import annotations
import os
import sys
from pathlib import Path
from copy import deepcopy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

pass_n = fail_n = 0

def ok(m):
    global pass_n; pass_n += 1; print('PASS:', m)
def bad(m):
    global fail_n; fail_n += 1; print('FAIL:', m)

def main():
    from PySide6.QtWidgets import QApplication, QWidget, QPushButton, QLabel, QListWidget, QSpinBox, QLineEdit
    app = QApplication.instance() or QApplication([])

    # ---- 1) hostWatch chip click → open var-watch on restored group ----
    from desktop.host_var_watch import (
        format_host_watch_open_chip, open_var_watch_on_restored_group,
        HostVarWatchBoard, write_pin_groups_to_project, pin_groups_from_project,
        HostVarWatchDialog,
    )
    chip = format_host_watch_open_chip(
        ['ixPt', 'pldDist', 'passGate'],
        {'测量链': ['ixPt', 'pldDist'], '判定': ['passGate']},
        active='测量链', label='demo.sieans',
    )
    if (chip.get('kind') == 'hostWatch' and chip.get('clickAction') == 'openVarWatch'
            and chip.get('restored') and chip.get('active') == '测量链'):
        ok(f'chip click payload kind={chip["kind"]} action={chip["clickAction"]}')
    else:
        bad(f'chip={chip}')

    board = HostVarWatchBoard()
    proj = {'name': 'demo', 'hostWatch': {}}
    write_pin_groups_to_project(
        proj, {'测量链': ['ixPt', 'pldDist'], '判定': ['passGate']},
        active='判定', watch_keys=['ixPt', 'pldDist', 'passGate'],
    )
    out = open_var_watch_on_restored_group(board, chip, project=proj, label='demo')
    if out.get('ok') and board.active_pin_group() == '测量链' and out.get('nGroups') >= 2:
        ok(f'open restored group active={board.active_pin_group()} n={out.get("nKeys")} g={out.get("nGroups")}')
    else:
        bad(f'out={out} active={board.active_pin_group()}')

    # activate_pin_group API
    if hasattr(board, 'activate_pin_group'):
        board.activate_pin_group('判定')
        (ok if board.active_pin_group() == '判定' else bad)(f'activate_pin_group → {board.active_pin_group()}')
    else:
        bad('missing activate_pin_group')

    # dialog shell + mainwindow helpers exist
    class Doc:
        def __init__(self, p): self.project = p
        def commit(self, p): self.project = p
        def mark_dirty(self): pass
        changed = type('S', (), {'emit': staticmethod(lambda *a, **k: None)})()
    dlg = HostVarWatchDialog(Doc(proj), None, None)
    out2 = open_var_watch_on_restored_group(dlg.board, chip, project=proj)
    (ok if out2.get('ok') and dlg.board.active_pin_group() == '测量链' else bad)(
        f'dialog restored active={dlg.board.active_pin_group()}'
    )

    src_mw = Path('desktop/mainwindow.py').read_text(encoding='utf-8')
    for need in ('_open_host_watch_from_chip', '_host_watch_open_chip', 'open_var_watch_on_restored_group'):
        (ok if need in src_mw else bad)(f'mainwindow has {need}')

    # ---- 2) recipe rollback stack panel pick / n-step ----
    from desktop.recipe_library import (
        capture_recipe, apply_recipe_with_rollback, list_recipe_rollback_stack,
        recipe_rollback_depth, rollback_recipe_n_steps, rollback_recipe_to_index,
        has_recipe_rollback,
    )
    from desktop.recipe_switch_dialog import RecipeSwitchDialog

    proj_r = {
        'name': 'stack',
        'steps': [
            {'id': 'a', 'name': '定位', 'operation': 'locate', 'params': {'minScore': 0.80}},
            {'id': 'b', 'name': '卡尺', 'operation': 'geometry', 'params': {'caliperCount': 4}},
        ],
        'variables': {'flow': {'x': 1}},
        'recipes': [],
    }
    capture_recipe(proj_r, '配方甲', variant='A')
    capture_recipe(proj_r, '配方乙', variant='B')
    capture_recipe(proj_r, '配方丙', variant='C')
    rids = [r['id'] for r in proj_r['recipes']]
    for i, rid in enumerate(rids):
        proj_r['steps'][0]['params']['minScore'] = 0.1 * (i + 1)
        apply_recipe_with_rollback(proj_r, rid)
    depth = recipe_rollback_depth(proj_r)
    hist = list_recipe_rollback_stack(proj_r)
    if depth == 3 and len(hist) == 3:
        ok(f'stack depth={depth} names={[h.get("name") for h in hist]}')
    else:
        bad(f'depth={depth} hist={hist}')

    # to_index keep 1
    p2 = deepcopy(proj_r)
    to1 = rollback_recipe_to_index(p2, 1)
    if to1.get('ok') and to1.get('steps') == 2 and recipe_rollback_depth(p2) == 1:
        ok(f'to_index keep1 steps={to1.get("steps")} rem={to1.get("remaining")}')
    else:
        bad(f'to1={to1} depth={recipe_rollback_depth(p2)}')

    # n-step
    p3 = deepcopy(proj_r)
    n2 = rollback_recipe_n_steps(p3, 2)
    if n2.get('ok') and n2.get('steps') == 2 and recipe_rollback_depth(p3) == 1:
        ok(f'n_steps=2 rem={n2.get("remaining")} rolled={n2.get("rolledBack")}')
    else:
        bad(f'n2={n2}')

    dlg_r = RecipeSwitchDialog(Doc(deepcopy(proj_r)), ROOT, None)
    names = {w.objectName() for w in dlg_r.findChildren(QWidget) if w.objectName()}
    for need in (
        'recipeRollbackStackList', 'recipeRollbackNBtn', 'recipeRollbackPickBtn',
        'recipeRollbackNSpin', 'recipeRollbackStackBox',
    ):
        (ok if need in names else bad)(f'ui {need}' if need in names else f'missing {need}')
    dlg_r.document.project = deepcopy(proj_r)
    dlg_r._sync_rollback_btn()
    lst = dlg_r.findChild(QListWidget, 'recipeRollbackStackList')
    if lst is not None and lst.count() == 3:
        ok(f'stack list count={lst.count()} top={lst.item(0).text()[:40]}')
    else:
        bad(f'list count={lst.count() if lst else None}')
    # pick top (newest) → fromTop=1
    if lst is not None and lst.count():
        lst.setCurrentRow(0)
        data = lst.currentItem().data(0x0100)  # UserRole
        # Qt.ItemDataRole.UserRole == 256
        from PySide6.QtCore import Qt as _Qt
        data = lst.currentItem().data(_Qt.ItemDataRole.UserRole) or {}
        if data.get('fromTop') == 1 and data.get('name') == '配方丙':
            ok(f'pick data={data}')
        else:
            bad(f'pick data={data}')
    # exercise _rollback_n_steps without modal: call library path already covered;
    # ensure handlers exist
    for need in ('_rollback_n_steps', '_rollback_to_selected', '_refresh_rollback_stack_list'):
        (ok if hasattr(dlg_r, need) else bad)(f'dialog has {need}')

    # ---- 4) painted spark mini-widget ----
    from desktop.locate_scoreboard import MatchScoreTrend, MatchScoreSparkWidget, spark_bar_heights
    tr = MatchScoreTrend(12)
    for s, ook in ((0.91, True), (0.88, True), (0.70, False), (0.93, True), (0.95, True)):
        tr.push(s, label='run', ok=ook, template_id='a1')
    heights = spark_bar_heights(tr.values(), width=16, relative=True)
    if len(heights) == 5 and min(heights) >= 0 and max(heights) <= 1:
        ok(f'bar heights n={len(heights)} lo={min(heights):.2f} hi={max(heights):.2f}')
    else:
        bad(f'heights={heights}')
    spark_w = MatchScoreSparkWidget(None, width=128, height=28)
    info = spark_w.set_from_trend(tr)
    uni = tr.sparkline(width=16, relative=True)
    if (info.get('n') == 5 and info.get('unicode') == uni
            and len(spark_w.heights()) == 5 and hasattr(spark_w, 'paintEvent')):
        ok(f'painted spark n={info["n"]} unicode={info["unicode"]} painted={info.get("painted")}')
    else:
        bad(f'info={info} uni={uni} type={type(spark_w)}')

    # locate panel embeds spark
    from desktop.locate_match_panel import LocateMatchPanel, normalize_locate_params
    params = normalize_locate_params({})
    step = {'id': 'L1', 'name': '定位', 'operation': 'locate', 'params': params}
    panel = LocateMatchPanel(step, {}, {'steps': [step], 'variables': {}})
    (ok if getattr(panel, '_tpl_trend_spark', None) is not None else bad)('panel has _tpl_trend_spark')
    panel.push_match_score(0.91, label='f1', ok=True, template_id='a1')
    panel.push_match_score(0.70, label='f2', ok=False, template_id='a1')
    sp = panel._tpl_trend_spark
    if sp is not None and len(sp.heights()) >= 2:
        ok(f'panel spark heights={sp.heights()} uni={sp.unicode_spark()}')
    else:
        bad(f'panel spark={sp}')

    # ---- 3) runUi designer blink fields ----
    from desktop.run_ui_designer import RunUiDesignerDialog
    from desktop.widgets.filmstrip import FilmstripBar
    doc = Doc({'name': 'ui', 'runUi': {'split': '2', 'filmstrip': {
        'blinkToggle': 'Alt+M', 'blinkSwap': 'Shift+Alt+M', 'blinkMs': 600,
    }}})
    # RunUiDesignerDialog needs document with project
    class Doc2:
        def __init__(self, p):
            self.project = p
        def commit(self, p):
            self.project = p
            try:
                self.changed.emit()
            except Exception:
                pass
        class _Ch:
            def emit(self, *a, **k): pass
        def __init__(self, p):  # noqa: F811 — redefine
            self.project = p
            self.changed = type('S', (), {'emit': staticmethod(lambda *a, **k: None)})()
        def commit(self, p):
            self.project = p

    # fix Doc2 properly
    class DocUi:
        def __init__(self, p):
            self.project = p
            self.changed = type('Sig', (), {'emit': staticmethod(lambda *a, **k: None)})()
        def commit(self, p):
            self.project = p

    doc_ui = DocUi({'name': 'ui', 'runUi': {'split': '2', 'filmstrip': {
        'blinkToggle': 'Alt+M', 'blinkSwap': 'Shift+Alt+M', 'blinkMs': 600,
    }, 'controls': {}, 'placements': [], 'fixedBars': {}}})
    designer = RunUiDesignerDialog(doc_ui, None)
    names_d = {w.objectName() for w in designer.findChildren(QWidget) if w.objectName()}
    for need in ('runUiFilmstripBlinkBox', 'runUiBlinkToggleEdit', 'runUiBlinkSwapEdit', 'runUiBlinkMsSpin'):
        (ok if need in names_d else bad)(f'designer {need}' if need in names_d else f'missing {need}')
    te = designer.findChild(QLineEdit, 'runUiBlinkToggleEdit')
    se = designer.findChild(QLineEdit, 'runUiBlinkSwapEdit')
    ms = designer.findChild(QSpinBox, 'runUiBlinkMsSpin')
    if te and te.text() == 'Alt+M' and se and se.text() == 'Shift+Alt+M' and ms and ms.value() == 600:
        ok(f'designer loaded toggle={te.text()} swap={se.text()} ms={ms.value()}')
    else:
        bad(f'te={te.text() if te else None} se={se.text() if se else None} ms={ms.value() if ms else None}')
    # edit + persist
    te.setText('Alt+Q')
    se.setText('Shift+Alt+Q')
    ms.setValue(700)
    designer._persist()
    bag = (doc_ui.project.get('runUi') or {}).get('filmstrip') or {}
    if bag.get('blinkToggle') == 'Alt+Q' and bag.get('blinkSwap') == 'Shift+Alt+Q' and bag.get('blinkMs') == 700:
        ok(f'persist runUi.filmstrip={bag}')
    else:
        bad(f'bag={bag}')
    # filmstrip apply still works
    fs = FilmstripBar()
    applied = fs.apply_blink_prefs_from_run_ui(doc_ui.project.get('runUi'))
    if applied.get('fromRunUi') and applied.get('toggle') == 'Alt+Q' and applied.get('blinkMs') == 700:
        ok(f'filmstrip apply_from_run_ui={applied}')
    else:
        bad(f'applied={applied}')

    # reserved refuse still
    bad_out = fs.set_blink_shortcuts('Ctrl+S', 'Alt+Q')
    (ok if not bad_out.get('ok') else bad)(f'reserved reject conflict={bad_out.get("conflict")}')

    print(f'\nTOTAL pass={pass_n} fail={fail_n}')
    return 0 if fail_n == 0 else 1

if __name__ == '__main__':
    sys.exit(main())
