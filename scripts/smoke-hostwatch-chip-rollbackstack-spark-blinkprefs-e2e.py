#!/usr/bin/env python3
"""Wave soft: hostWatch open chip · recipe rollback history stack ·
scoreboard trend sparkline polish · filmstrip blink prefs in runUi.
No Halcon / robot / real TCP / cloud. Leave ?? os and :18280 alone.
"""
from __future__ import annotations
import json
import os
import sys
import tempfile
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
    # ---- 1) hostWatch open chip ----
    from desktop.host_var_watch import (
        format_host_watch_open_chip, write_pin_groups_to_project,
        pin_groups_from_project, HostVarWatchBoard,
    )
    empty = format_host_watch_open_chip([], {}, label='x')
    (ok if not empty.get('restored') and empty.get('text') == '' else bad)(
        f'empty chip restored={empty.get("restored")}'
    )
    chip = format_host_watch_open_chip(
        ['ixPt', 'pldDist', 'passGate', 'extra1', 'extra2'],
        {'测量链': ['ixPt', 'pldDist'], '判定': ['passGate']},
        active='测量链', label='demo.sieans',
    )
    if (chip.get('restored') and chip.get('nGroups') == 2 and chip.get('nKeys') == 5
            and '监视已恢复' in chip.get('text', '') and '钉组×2' in chip.get('text', '')
            and chip.get('active') == '测量链' and 'demo.sieans' in chip.get('text', '')):
        ok(f'open chip text={chip["text"][:80]}')
    else:
        bad(f'chip={chip}')

    # ---- 2) recipe rollback multi-step stack ----
    from desktop.recipe_library import (
        capture_recipe, apply_recipe_with_rollback, rollback_last_recipe_apply,
        has_recipe_rollback, recipe_rollback_depth, list_recipe_rollback_stack,
        rollback_recipe_n_steps, preview_apply_recipe,
    )
    proj = {
        'name': 'stack',
        'steps': [
            {'id': 'a', 'name': '定位', 'operation': 'locate', 'params': {'minScore': 0.80}},
            {'id': 'b', 'name': '卡尺', 'operation': 'geometry', 'params': {'caliperCount': 4}},
        ],
        'variables': {'flow': {'x': 1}},
        'recipes': [],
    }
    capture_recipe(proj, '配方甲', variant='A')
    capture_recipe(proj, '配方乙', variant='B')
    rids = [r['id'] for r in proj['recipes']]
    # mutate then apply A
    proj['steps'][0]['params']['minScore'] = 0.11
    s1 = apply_recipe_with_rollback(proj, rids[0])
    if s1.get('rollbackReady') and s1.get('rollbackDepth') == 1 and has_recipe_rollback(proj):
        ok(f'apply1 depth={s1.get("rollbackDepth")}')
    else:
        bad(f's1={s1}')
    # mutate again + apply B → stack depth 2
    proj['steps'][0]['params']['minScore'] = 0.22
    proj['steps'][1]['params']['caliperCount'] = 99
    s2 = apply_recipe_with_rollback(proj, rids[1])
    depth = recipe_rollback_depth(proj)
    hist = list_recipe_rollback_stack(proj)
    if depth == 2 and len(hist) == 2 and hist[-1].get('name') == '配方乙':
        ok(f'stack depth={depth} hist={[h.get("name") for h in hist]}')
    else:
        bad(f'depth={depth} hist={hist}')
    # one-shot mirror still present
    if isinstance(proj.get('_recipeRollbackSnap'), dict) and proj['_recipeRollbackSnap'].get('name') == '配方乙':
        ok('top mirror _recipeRollbackSnap=配方乙')
    else:
        bad(f'mirror={proj.get("_recipeRollbackSnap")}')
    # pop one
    rb1 = rollback_last_recipe_apply(proj)
    if rb1.get('ok') and rb1.get('rolledBack') == '配方乙' and rb1.get('remaining') == 1:
        ok(f'pop1 rolled={rb1.get("rolledBack")} rem={rb1.get("remaining")}')
    else:
        bad(f'rb1={rb1}')
    # n-step on a fresh project (clean stack)
    proj2 = {
        'name': 'stack2',
        'steps': [
            {'id': 'a', 'name': '定位', 'operation': 'locate', 'params': {'minScore': 0.80}},
        ],
        'variables': {'flow': {}},
        'recipes': [],
    }
    capture_recipe(proj2, '甲')
    capture_recipe(proj2, '乙')
    r2 = [r['id'] for r in proj2['recipes']]
    proj2['steps'][0]['params']['minScore'] = 0.33
    apply_recipe_with_rollback(proj2, r2[0])
    proj2['steps'][0]['params']['minScore'] = 0.44
    apply_recipe_with_rollback(proj2, r2[1])
    if recipe_rollback_depth(proj2) == 2:
        ok(f'refilled depth={recipe_rollback_depth(proj2)}')
    else:
        bad(f'refill depth={recipe_rollback_depth(proj2)}')
    multi = rollback_recipe_n_steps(proj2, 2)
    if multi.get('ok') and multi.get('steps') == 2 and multi.get('remaining') == 0:
        ok(f'rollback_n steps={multi.get("steps")} rolled={multi.get("rolledBack")}')
    else:
        bad(f'multi={multi}')
    if not has_recipe_rollback(proj2):
        ok('stack empty after n-rollback')
    else:
        bad('stack still present')
    # preview still non-mutating
    capture_recipe(proj, '配方丙')
    rid3 = proj['recipes'][-1]['id']
    snap = deepcopy(proj.get('steps'))
    bag = preview_apply_recipe(proj, rid3)
    if bag.get('mutatedLive') is False and proj.get('steps') == snap:
        ok('preview_apply still non-mutating')
    else:
        bad('preview mutated')

    # ---- 3) sparkline polish ----
    from desktop.locate_scoreboard import MatchScoreTrend
    tr = MatchScoreTrend(12)
    for s, ook in ((0.91, True), (0.88, True), (0.70, False), (0.93, True), (0.95, True)):
        tr.push(s, label='run', ok=ook, template_id='a1')
    sm = tr.summary(industrial=True)
    spark = tr.sparkline(width=16, relative=True)
    dlt = tr.delta()
    rich = tr.summary_rich()
    if ('n=5' in sm and '末=0.950' in sm and 'Δ' in sm and 'OK' in sm
            and spark and len(spark) >= 4 and dlt is not None and dlt > 0
            and '近点' in rich and '✓' in sm):
        ok(f'spark polish sm={sm} spark={spark}')
    else:
        bad(f'sm={sm!r} spark={spark!r} dlt={dlt} rich={rich[:100]!r}')
    # relative: flat series still produces chars
    tr2 = MatchScoreTrend(4)
    for _ in range(4):
        tr2.push(0.85, ok=True)
    sp2 = tr2.sparkline(relative=True)
    if sp2 and len(set(sp2)) == 1:
        ok(f'relative flat spark={sp2}')
    else:
        bad(f'flat spark={sp2}')

    # ---- 4) filmstrip blink prefs ↔ runUi ----
    from PySide6.QtWidgets import QApplication, QWidget, QPushButton, QLabel
    app = QApplication.instance() or QApplication([])
    from desktop.widgets.filmstrip import FilmstripBar
    fs = FilmstripBar()
    prefs0 = fs.blink_prefs_dict()
    if prefs0.get('blinkToggle') == 'Alt+B' and 'blinkSwap' in prefs0:
        ok(f'default prefs={prefs0}')
    else:
        bad(f'prefs0={prefs0}')
    # write into runUi
    runUi = {'split': '2', 'meta': {'template': 'x'}}
    FilmstripBar.write_blink_prefs_to_run_ui(runUi, {
        'blinkToggle': 'Alt+M', 'blinkSwap': 'Shift+Alt+M', 'blinkMs': 600,
    })
    if (runUi.get('filmstrip') or {}).get('blinkToggle') == 'Alt+M':
        ok(f'write runUi.filmstrip={runUi["filmstrip"]}')
    else:
        bad(f'runUi={runUi}')
    # apply from runUi
    out = fs.apply_blink_prefs_from_run_ui(runUi)
    if (out.get('fromRunUi') and out.get('ok') and out.get('toggle') == 'Alt+M'
            and out.get('blinkMs') == 600):
        ok(f'apply_from_run_ui={out}')
    else:
        bad(f'apply out={out}')
    # reserved conflict
    bad_out = fs.set_blink_shortcuts('Ctrl+S', 'Alt+M')
    if not bad_out.get('ok') and bad_out.get('conflict') in ('Ctrl+S',):
        ok(f'reserved reject={bad_out.get("conflict")}')
    else:
        bad(f'bad_out={bad_out}')
    # toggle should stay Alt+M (previous good)
    if fs.blink_toggle_shortcut_key() == 'Alt+M':
        ok(f'toggle stays {fs.blink_toggle_shortcut_key()}')
    else:
        bad(f'toggle now {fs.blink_toggle_shortcut_key()}')
    # round-trip prefs dict
    bag2 = fs.blink_prefs_dict()
    fs2 = FilmstripBar()
    fs2.apply_blink_prefs(bag2)
    if fs2.blink_toggle_shortcut_key() == 'Alt+M':
        ok(f'roundtrip prefs={bag2}')
    else:
        bad(f'fs2={fs2.blink_toggle_shortcut_key()}')
    # context menu object exists as method
    (ok if hasattr(fs, '_on_blink_prefs_menu') else bad)('_on_blink_prefs_menu')
    (ok if hasattr(fs, 'apply_blink_prefs_from_run_ui') else bad)('apply_blink_prefs_from_run_ui')

    # ---- locate panel industrial trend ----
    from desktop.locate_match_panel import LocateMatchPanel, normalize_locate_params
    p = normalize_locate_params({})
    step = {'id': 'L1', 'name': '定位', 'operation': 'locate', 'params': p}
    panel = LocateMatchPanel(step, {}, {'steps': [step], 'variables': {}})
    tsum = panel.push_match_score(0.91, label='f1', ok=True, template_id='a1')
    tsum2 = panel.push_match_score(0.70, label='f2', ok=False, template_id='a1')
    lab = panel._tpl_trend_lab.text()
    if 'Δ' in lab and ('↑' in lab or '↓' in lab) and panel._tpl_trend_lab.toolTip():
        ok(f'panel trend lab={lab[:70]} tip_len={len(panel._tpl_trend_lab.toolTip())}')
    else:
        bad(f'lab={lab!r} tip={panel._tpl_trend_lab.toolTip()!r}')

    # ---- recipe dialog rollback depth lab ----
    from desktop.recipe_switch_dialog import RecipeSwitchDialog
    class Doc:
        def __init__(self, p): self.project = p
        def commit(self, p): self.project = p
        def mark_dirty(self): pass
    proj_ui = {
        'name': 'ui',
        'steps': [{'id': 'a', 'name': '定位', 'operation': 'locate', 'params': {'minScore': 0.8}}],
        'variables': {'flow': {}},
        'recipes': [],
    }
    capture_recipe(proj_ui, '线体A')
    capture_recipe(proj_ui, '线体B')
    dlg = RecipeSwitchDialog(Doc(proj_ui), ROOT, None)
    names = {w.objectName() for w in dlg.findChildren(QWidget) if w.objectName()}
    for need in ('recipeRollbackBtn', 'recipeRollbackDepthLab', 'recipePreviewApplyBtn'):
        (ok if need in names else bad)(f'ui {need}' if need in names else f'missing {need}')
    rids_ui = [r['id'] for r in proj_ui['recipes']]
    apply_recipe_with_rollback(proj_ui, rids_ui[0])
    apply_recipe_with_rollback(proj_ui, rids_ui[1])
    dlg.document.project = proj_ui
    dlg._sync_rollback_btn()
    depth_txt = dlg._rollback_depth_lab.text()
    if dlg._rollback_btn.isEnabled() and '栈×2' in depth_txt:
        ok(f'rollback depth lab={depth_txt} btn={dlg._rollback_btn.text()}')
    else:
        bad(f'depth_txt={depth_txt!r} enabled={dlg._rollback_btn.isEnabled()} btn={dlg._rollback_btn.text()}')

    # ---- mainwindow helpers exist (import without full GUI launch) ----
    import desktop.mainwindow as mwmod
    src = Path('desktop/mainwindow.py').read_text(encoding='utf-8')
    for need in (
        '_show_host_watch_open_chip',
        '_sync_filmstrip_blink_prefs_from_project',
        '_persist_filmstrip_blink_prefs',
        'set_filmstrip_blink_shortcuts',
        'format_host_watch_open_chip',
    ):
        (ok if need in src else bad)(f'mainwindow has {need}')

    # pin group round-trip still ok
    board = HostVarWatchBoard()
    board.set_pin_groups({'测量链': ['ixPt'], '判定': ['passGate']}, active='判定')
    proj_pins = {'name': 'p'}
    board.persist_pin_groups_to_project(proj_pins)
    g, a = pin_groups_from_project(proj_pins)
    chip2 = format_host_watch_open_chip(
        board.pinned_keys(), g, active=a, label='round.sieans'
    )
    if chip2.get('restored') and a == '判定':
        ok(f'roundtrip chip short={chip2.get("short")}')
    else:
        bad(f'chip2={chip2} a={a}')

    print(f'\nTOTAL pass={pass_n} fail={fail_n}')
    return 0 if fail_n == 0 else 1

if __name__ == '__main__':
    sys.exit(main())
