#!/usr/bin/env python3
"""Wave soft: chip RMB pin-group picker · spark hover tip + click-jump ·
rollback stack export/clear · designer blink reserved-conflict live warn.
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
    from PySide6.QtWidgets import QApplication, QWidget, QPushButton, QLabel, QListWidget, QLineEdit
    from PySide6.QtCore import Qt, QPoint
    from PySide6.QtGui import QMouseEvent
    app = QApplication.instance() or QApplication([])

    # ---- 1) chip RMB pin-group picker ----
    from desktop.host_var_watch import (
        format_host_watch_open_chip, pin_group_picker_entries,
        resolve_pin_group_from_chip, open_var_watch_on_restored_group,
        HostVarWatchBoard, write_pin_groups_to_project,
    )
    groups = {'测量链': ['ixPt', 'pldDist'], '判定': ['passGate'], '标定': ['calX', 'calY']}
    chip = format_host_watch_open_chip(
        ['ixPt', 'pldDist', 'passGate'], groups, active='测量链', label='demo.sieans',
    )
    if (chip.get('rmbAction') == 'pickPinGroup' and chip.get('pinGroupEntries')
            and len(chip['pinGroupEntries']) == 3 and '右键' in (chip.get('clickHint') or '')):
        ok(f'chip rmb payload entries={len(chip["pinGroupEntries"])} hint={chip["clickHint"][:24]}')
    else:
        bad(f'chip={chip}')

    entries = pin_group_picker_entries(groups, active='测量链')
    if entries and entries[0].get('active') and entries[0].get('name') == '测量链':
        ok(f'picker active-first name={entries[0]["name"]} nKeys={entries[0]["nKeys"]}')
    else:
        bad(f'entries={entries}')

    proj = {'name': 'demo', 'hostWatch': {}}
    write_pin_groups_to_project(proj, groups, active='测量链', watch_keys=['ixPt', 'pldDist', 'passGate'])
    resolved = resolve_pin_group_from_chip(chip, name='判定', project=proj)
    if resolved.get('ok') and resolved.get('active') == '判定':
        ok(f'resolve pick active={resolved["active"]} nGroups={resolved["nGroups"]}')
    else:
        bad(f'resolved={resolved}')

    board = HostVarWatchBoard()
    out = open_var_watch_on_restored_group(board, resolved['chip'], project=proj)
    if out.get('ok') and board.active_pin_group() == '判定':
        ok(f'open after pick active={board.active_pin_group()} keys={board.pinned_keys()}')
    else:
        bad(f'out={out} active={board.active_pin_group()}')

    src_mw = Path('desktop/mainwindow.py').read_text(encoding='utf-8')
    for need in ('_on_host_watch_chip_context_menu', '_open_host_watch_pin_group',
                 'CustomContextMenu', 'RightButton'):
        (ok if need in src_mw else bad)(f'mainwindow has {need}')

    # ---- 3) spark hover tip + click-jump ----
    from desktop.locate_scoreboard import MatchScoreTrend, MatchScoreSparkWidget
    tr = MatchScoreTrend(12)
    frames = []
    for i, (s, ook, fr) in enumerate((
        (0.91, True, 'f001'), (0.88, True, 'f002'), (0.70, False, 'f003'),
        (0.93, True, 'f004'), (0.95, True, 'f005'),
    )):
        tr.push(s, label=f'run{i+1}', ok=ook, template_id='a1', frame=fr)
        frames.append(fr)
    tip = tr.hover_tip_at(2)
    if 'f003' in tip and '点击跳到该帧' in tip and '0.700' in tip:
        ok(f'trend hover_tip_at #2 → {tip[:60]}')
    else:
        bad(f'tip={tip}')
    idx = tr.index_at_fraction(0.5, bar_count=5)
    if 0 <= idx < 5:
        ok(f'index_at_fraction mid → {idx} frame={tr.point_at(idx).get("frame")}')
    else:
        bad(f'idx={idx}')

    jumped = {}
    spark = MatchScoreSparkWidget(None, width=128, height=28)
    spark.set_from_trend(tr)
    if hasattr(spark, 'set_jump_handler'):
        spark.set_jump_handler(lambda bag: jumped.update(bag))
    tip_l = spark.hover_tip_for_local(2) if hasattr(spark, 'hover_tip_for_local') else ''
    if '点击跳到该帧' in tip_l:
        ok(f'spark hover local2 → {tip_l[:60]}')
    else:
        bad(f'tip_l={tip_l}')
    bag = spark.jump_to_local(2) if hasattr(spark, 'jump_to_local') else {}
    if bag.get('frame') == 'f003' and jumped.get('frame') == 'f003':
        ok(f'spark jump frame={bag.get("frame")} index={bag.get("index")} score={bag.get("score")}')
    else:
        bad(f'bag={bag} jumped={jumped}')

    from desktop.locate_match_panel import LocateMatchPanel, normalize_locate_params
    params = normalize_locate_params({})
    step = {'id': 'L1', 'name': '定位', 'operation': 'locate', 'params': params}
    panel = LocateMatchPanel(step, {}, {'steps': [step], 'variables': {}})
    panel.push_match_score(0.91, label='f1', ok=True, template_id='a1', frame='f001')
    panel.push_match_score(0.70, label='f2', ok=False, template_id='a1', frame='f003')
    sp = getattr(panel, '_tpl_trend_spark', None)
    if sp is not None and hasattr(panel, '_on_spark_frame_jump'):
        panel._on_spark_frame_jump({'index': 1, 'frame': 'f003', 'label': 'f2', 'score': 0.70})
        lab = getattr(panel, '_spark_jump_lab', None)
        txt = lab.text() if lab is not None else ''
        (ok if 'f003' in txt or 'f2' in txt or '跳帧' in txt else bad)(f'panel jump lab={txt}')
    else:
        bad('panel missing spark jump wire')

    # ---- 2) rollback stack export/clear ----
    from desktop.recipe_library import (
        capture_recipe, apply_recipe_with_rollback, list_recipe_rollback_stack,
        recipe_rollback_depth, export_recipe_rollback_stack, clear_recipe_rollback_stack,
        rollback_stack_export_csv_rows,
    )
    from desktop.recipe_switch_dialog import RecipeSwitchDialog

    class Doc:
        def __init__(self, p): self.project = p
        def commit(self, p): self.project = p
        def mark_dirty(self): pass
        changed = type('S', (), {'emit': staticmethod(lambda *a, **k: None)})()

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
    for i, rid in enumerate([r['id'] for r in proj_r['recipes']]):
        proj_r['steps'][0]['params']['minScore'] = 0.1 * (i + 1)
        apply_recipe_with_rollback(proj_r, rid)
    depth = recipe_rollback_depth(proj_r)
    bag = export_recipe_rollback_stack(proj_r)
    if bag.get('ok') and bag.get('depth') == 3 and len(bag.get('entries') or []) == 3:
        ok(f'export depth={bag["depth"]} names={[e.get("name") for e in bag["entries"]]}')
    else:
        bad(f'bag={bag}')
    # no snapshots by default
    if all('snapshot' not in e for e in bag['entries']):
        ok('export strips snapshots by default')
    else:
        bad('snapshots leaked')
    rows = rollback_stack_export_csv_rows(bag)
    if rows and rows[0][0] == 'ordinal' and len(rows) == 4:
        ok(f'csv rows={len(rows)} header={rows[0][:3]}')
    else:
        bad(f'rows={rows}')

    p_clear = deepcopy(proj_r)
    cleared = clear_recipe_rollback_stack(p_clear)
    if cleared.get('ok') and cleared.get('cleared') == 3 and recipe_rollback_depth(p_clear) == 0:
        ok(f'clear cleared={cleared["cleared"]} rem={recipe_rollback_depth(p_clear)}')
    else:
        bad(f'cleared={cleared} depth={recipe_rollback_depth(p_clear)}')

    dlg_r = RecipeSwitchDialog(Doc(deepcopy(proj_r)), ROOT, None)
    names = {w.objectName() for w in dlg_r.findChildren(QWidget) if w.objectName()}
    for need in ('recipeRollbackExportBtn', 'recipeRollbackClearBtn', 'recipeRollbackStackList'):
        (ok if need in names else bad)(f'ui {need}')
    for need in ('_export_rollback_stack', '_clear_rollback_stack'):
        (ok if hasattr(dlg_r, need) else bad)(f'dialog has {need}')

    # ---- 4) designer blink reserved-conflict live warn ----
    from desktop.run_ui_designer import RunUiDesignerDialog
    class Doc2:
        def __init__(self, p):
            self.project = p
        def commit(self, p):
            self.project = p
        def mark_dirty(self): pass
    doc = Doc2({'name': 'ui', 'runUi': {'split': '2', 'filmstrip': {
        'blinkToggle': 'Alt+B', 'blinkSwap': 'Shift+Alt+B', 'blinkMs': 450,
    }}})
    # RunUiDesignerDialog signature varies — try common shapes
    dlg = None
    err = None
    for args in (
        (doc, ROOT, None),
        (doc, None),
        (doc,),
    ):
        try:
            dlg = RunUiDesignerDialog(*args)
            break
        except TypeError as e:
            err = e
            continue
    if dlg is None:
        bad(f'RunUiDesignerDialog init failed: {err}')
    else:
        names = {w.objectName() for w in dlg.findChildren(QWidget) if w.objectName()}
        (ok if 'runUiBlinkConflictWarn' in names else bad)('ui runUiBlinkConflictWarn')
        (ok if hasattr(dlg, 'check_blink_reserved_conflicts') else bad)('has check_blink_reserved_conflicts')
        # clean chords
        if hasattr(dlg, 'blink_toggle_edit'):
            dlg.blink_toggle_edit.setText('Alt+B')
            dlg.blink_swap_edit.setText('Shift+Alt+B')
        info = dlg.check_blink_reserved_conflicts()
        (ok if info.get('ok') else bad)(f'clean chords ok={info.get("ok")} warn={info.get("warn")}')
        # reserved conflict
        dlg.blink_toggle_edit.setText('Ctrl+S')
        info2 = dlg.check_blink_reserved_conflicts()
        if (not info2.get('ok') and info2.get('conflicts')
                and 'Ctrl+S' in (info2.get('warn') or '')):
            ok(f'live conflict warn={info2["warn"][:50]}')
        else:
            bad(f'info2={info2}')
        # live label
        dlg._on_blink_conflict_live_check()
        lab = dlg.findChild(QLabel, 'runUiBlinkConflictWarn')
        shown = lab is not None and (not lab.isHidden()) and bool(lab.text())
        if shown and ('冲突' in lab.text() or 'Ctrl+S' in lab.text()):
            ok(f'warn label visible text={lab.text()[:40]}')
        else:
            bad(f'lab text={lab.text() if lab else None} hidden={lab.isHidden() if lab else None}')
        # refuse persist path: conflict should not crash
        try:
            dlg._on_blink_prefs_changed()
            ok('prefs_changed refuses conflict without crash')
        except Exception as e:
            bad(f'prefs_changed err={e}')
        # restore clean
        dlg.blink_toggle_edit.setText('Alt+M')
        info3 = dlg._on_blink_conflict_live_check()
        (ok if info3.get('ok') else bad)(f'restored ok={info3.get("ok")}')

    print(f'\\nRESULT pass={pass_n} fail={fail_n}')
    return 0 if fail_n == 0 else 1

if __name__ == '__main__':
    sys.exit(main())
