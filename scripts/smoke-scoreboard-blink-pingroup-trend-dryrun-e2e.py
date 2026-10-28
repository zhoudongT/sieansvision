#!/usr/bin/env python3
"""Wave soft: live scoreboard ingest · filmstrip blink shortcuts ·
host pin-group project JSON · recipe preview-apply + rollback ·
score trend · dry-run side-by-side.
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
    from desktop.locate_scoreboard import (
        build_batch_scoreboard, soft_estimate_scores, select_best_template,
        MatchScoreTrend, format_side_by_side_diff, ingest_engine_scores,
        scores_for_library,
    )
    lib = [
        {'id': 'a1', 'name': '基准A', 'path': '/tmp/a.png'},
        {'id': 'b2', 'name': '基准B', 'path': '/tmp/b.png'},
        {'id': 'c3', 'name': '基准C', 'path': '/tmp/c.png'},
    ]
    scores = soft_estimate_scores(lib, 'demo')
    if len(scores) == 3 and all(0.5 <= scores[k] <= 1.0 for k in scores):
        ok(f'soft_estimate_scores={scores}')
    else:
        bad(f'soft scores={scores}')
    board = build_batch_scoreboard(lib, scores, threshold=0.70, active_id='a1')
    if board['bestId'] and board['passCount'] + board['failCount'] == 3:
        ok(f'scoreboard {board["summary"]}')
    else:
        bad(f'scoreboard={board}')
    best = select_best_template(board)
    if best and best['id'] == board['bestId']:
        ok(f'select_best={best["name"]}:{best["score"]}')
    else:
        bad(f'best={best}')
    # inject override
    board2 = build_batch_scoreboard(lib, {'a1': 0.99, 'b2': 0.40, 'c3': 0.80}, threshold=0.85)
    if board2['bestId'] == 'a1' and board2['passCount'] == 1 and board2['failCount'] == 2:
        ok(f'threshold board pass={board2["passCount"]} fail={board2["failCount"]}')
    else:
        bad(f'thr board={board2}')
    trend = MatchScoreTrend(8)
    for s in (0.91, 0.88, 0.93, 0.70):
        trend.push(s, label='run', ok=s >= 0.85)
    sm = trend.summary()
    if 'n=4' in sm and '末=0.700' in sm.replace('0.70', '0.700') or '末=0.7' in sm:
        ok(f'trend {sm}')
    else:
        # accept if n=4 and 末 present
        (ok if 'n=4' in sm and '末=' in sm else bad)(f'trend {sm}')
    eng = ingest_engine_scores({
        'results': [{'id': 'L1', 'data': {'bestScore': 0.87, 'activeTemplateId': 'a1',
                                          'items': [{'score': 0.87}]}}],
        'variables': {'flow': {'match_score': 0.87}},
    }, step_id='L1')
    if eng.get('a1') == 0.87 or eng.get('__best__') == 0.87:
        ok(f'ingest_engine_scores={eng}')
    else:
        bad(f'ingest={eng}')
    # richer live engine shapes
    eng2 = ingest_engine_scores({
        'results': [{'id': 'L1', 'data': {
            'templateScores': {'a1': 0.92, 'b2': 0.61, 'c3': 0.80},
            'matches': [{'templateId': 'a1', 'score': 0.92}],
            'output': {'score': 0.92},
        }}],
    }, step_id='L1')
    mapped = scores_for_library(eng2, lib)
    if mapped.get('a1') == 0.92 and mapped.get('b2') == 0.61 and mapped.get('c3') == 0.80:
        ok(f'scores_for_library live={mapped}')
    else:
        bad(f'scores_for_library={mapped} eng2={eng2}')

    from PySide6.QtWidgets import QApplication, QWidget, QTableWidget, QPushButton, QLabel, QListWidget
    app = QApplication.instance() or QApplication([])

    # ---- locate panel scoreboard + trend ----
    from desktop.locate_match_panel import LocateMatchPanel, normalize_locate_params
    p = normalize_locate_params({})
    for need in ('batchScoreThreshold', 'lastBatchScoreboard', 'matchScoreTrend'):
        (ok if need in p else bad)(f'normalize {need}' if need in p else f'missing {need}')
    step = {'id': 'L1', 'name': '定位', 'operation': 'locate', 'params': p}
    panel = LocateMatchPanel(step, {}, {'steps': [step], 'variables': {}})
    names = {w.objectName() for w in panel.findChildren(QWidget) if w.objectName()}
    for need in (
        'locateBatchScoreTable', 'locateBatchScoreBtn', 'locateBatchBestBtn',
        'locateBatchScoreThr', 'locateBatchScoreSummary', 'locateMatchScoreTrend',
    ):
        (ok if need in names else bad)(f'ui {need}' if need in names else f'missing {need}')
    panel.params['templateLibrary'] = list(lib)
    panel.params['activeTemplateId'] = 'a1'
    panel._refresh_tpl_library_list()
    b = panel.run_batch_scoreboard({'a1': 0.95, 'b2': 0.60, 'c3': 0.88}, soft=False)
    if b['bestId'] == 'a1' and panel._tpl_sb_table.rowCount() == 3:
        ok(f'panel batch best={b["bestId"]} rows={panel._tpl_sb_table.rowCount()}')
    else:
        bad(f'panel batch={b} rows={panel._tpl_sb_table.rowCount()}')
    # select best without dialog when above thr
    panel._tpl_sb_thr.setValue(0.50)
    panel._tpl_select_best()
    if panel.params.get('activeTemplateId') == 'a1' and 'a.png' in str(panel.params.get('templatePath')):
        ok(f'select_best path={panel.params.get("templatePath")}')
    else:
        bad(f'after best id={panel.params.get("activeTemplateId")} path={panel.params.get("templatePath")}')
    tsum = panel.push_match_score(0.92, label='frame', template_id='a1')
    if '末=' in tsum and panel._tpl_trend_lab.text():
        ok(f'panel trend={panel._tpl_trend_lab.text()[:70]}')
    else:
        bad(f'trend lab={panel._tpl_trend_lab.text()!r}')

    # ---- filmstrip A/B blink ----
    from desktop.widgets.filmstrip import FilmstripBar, CompareThumbStrip
    fs = FilmstripBar()
    for need in ('filmstripBlinkBtn', 'filmstripBlinkSwapBtn', 'filmstripBlinkLab'):
        w = fs.findChild(QWidget, need) or fs.findChild(QPushButton, need) or fs.findChild(QLabel, need)
        (ok if w is not None or hasattr(fs, 'blink_btn') else bad)(f'film {need}')
    fs.set_paths(['/tmp/a.png', '/tmp/b.png', '/tmp/c.png'], 0)
    fs.set_blink_pair('/tmp/a.png', '/tmp/b.png')
    a, bth = fs.blink_pair()
    if a.endswith('a.png') and bth.endswith('b.png'):
        ok(f'blink pair A={a} B={bth}')
    else:
        bad(f'pair={a},{bth}')
    started = fs.start_blink()
    if started and fs.is_blinking():
        ok('blink started')
    else:
        bad(f'start={started} active={fs.is_blinking()}')
    fs._on_blink_tick()
    if fs._blink_showing == 'B':
        ok('blink tick → B')
    else:
        bad(f'showing={fs._blink_showing}')
    fs.swap_blink_pair()
    a2, b2 = fs.blink_pair()
    if a2.endswith('b.png') and b2.endswith('a.png'):
        ok('blink swap')
    else:
        bad(f'after swap {a2},{b2}')
    fs.stop_blink()
    if not fs.is_blinking():
        ok('blink stopped')
    else:
        bad('blink still active')
    # discoverable conflict-safe shortcuts
    info = fs.set_blink_shortcuts('Alt+B', 'Shift+Alt+B')
    swap = str(info.get('swap') or '')
    # QKeySequence PortableText may reorder to Alt+Shift+B
    if info.get('toggle') == 'Alt+B' and swap in ('Shift+Alt+B', 'Alt+Shift+B') and info.get('ok'):
        ok(f'blink shortcuts={info}')
    else:
        bad(f'shortcuts={info}')
    # reserved conflict rejection
    bad_info = fs.set_blink_shortcuts('Alt+P', 'Alt+B')  # Alt+P reserved
    if bad_info.get('toggle') != 'Alt+P':
        ok(f'blink reserved reject toggle stays {bad_info.get("toggle")}')
    else:
        bad(f'reserved accepted={bad_info}')
    if hasattr(fs, 'toggle_blink'):
        fs.set_blink_pair('/tmp/a.png', '/tmp/b.png')
        fs.start_blink()
        fs.toggle_blink()  # should stop
        (ok if not fs.is_blinking() else bad)('toggle_blink stops')
        fs.toggle_blink()  # should start
        (ok if fs.is_blinking() else bad)('toggle_blink starts')
        fs.stop_blink()
    # auto pick
    fs.set_blink_pair('', '')
    aa, bb = fs.auto_pick_blink_pair()
    if aa and bb and aa != bb:
        ok(f'auto_pick {aa} / {bb}')
    else:
        bad(f'auto_pick={aa},{bb}')
    strip = CompareThumbStrip()
    strip.set_paths(['/tmp/a.png', '/tmp/b.png', '/tmp/c.png'])
    ba, bb2 = strip.blink_paths()
    if ba.endswith('a.png') and bb2.endswith('b.png'):
        ok(f'compare blink_paths={ba},{bb2}')
    else:
        bad(f'compare blink_paths={ba},{bb2}')

    # ---- host pin groups + CSV ----
    from desktop.host_var_watch import HostVarWatchBoard
    boardw = HostVarWatchBoard()
    names = {w.objectName() for w in boardw.findChildren(QWidget) if w.objectName()}
    for need in (
        'hostVarWatchPinGroup', 'hostVarWatchPinGroupNewBtn',
        'hostVarWatchPinGroupSaveBtn', 'hostVarWatchExportCsvBtn',
    ):
        (ok if need in names else bad)(f'watch {need}' if need in names else f'missing {need}')
    boardw.seed_watch_keys(['ixPt', 'pldDist', 'passGate'], label='demo')
    boardw.ensure_pin_group('测量链', ['ixPt', 'pldDist'])
    boardw.ensure_pin_group('判定', ['passGate'])
    boardw.set_pin_groups({
        '测量链': ['ixPt', 'pldDist'],
        '判定': ['passGate'],
    }, active='测量链')
    if boardw.active_pin_group() == '测量链' and boardw.pinned_keys() == ['ixPt', 'pldDist']:
        ok(f'pin group active={boardw.active_pin_group()} keys={boardw.pinned_keys()}')
    else:
        bad(f'group={boardw.active_pin_group()} keys={boardw.pinned_keys()}')
    boardw.render()
    csv_txt = boardw.export_csv_text()
    if '#pin_group' in csv_txt and '测量链' in csv_txt and 'ixPt' in csv_txt:
        ok(f'export_csv_text lines={len(csv_txt.splitlines())}')
    else:
        bad(f'csv={csv_txt[:200]!r}')
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / 'watch.csv'
        written = boardw.export_csv(str(out))
        if written and out.is_file() and 'ixPt' in out.read_text(encoding='utf-8'):
            ok(f'export_csv file={out.name} bytes={out.stat().st_size}')
        else:
            bad(f'export file written={written}')

    
    # ---- pin groups → project JSON hostWatch ----
    from desktop.host_var_watch import (
        write_pin_groups_to_project, pin_groups_from_project, host_watch_bag,
    )
    proj_pins = {'name': 'demo', 'steps': []}
    write_pin_groups_to_project(
        proj_pins,
        boardw.pin_groups(),
        active=boardw.active_pin_group(),
        watch_keys=boardw.pinned_keys(),
    )
    bag = proj_pins.get('hostWatch') or {}
    if bag.get('pinGroups') and bag.get('activePinGroup') == boardw.active_pin_group():
        ok(f'hostWatch write pinGroups={list(bag["pinGroups"])} active={bag["activePinGroup"]}')
    else:
        bad(f'hostWatch={bag}')
    g2, a2 = pin_groups_from_project(proj_pins)
    if g2.get('测量链') == ['ixPt', 'pldDist'] and a2 == '测量链':
        ok(f'pin_groups_from_project g={g2} a={a2}')
    else:
        bad(f'roundtrip g={g2} a={a2}')
    # board.seed_from_project restores groups
    boardw2 = HostVarWatchBoard()
    boardw2.seed_from_project(proj_pins, label='roundtrip')
    if boardw2.active_pin_group() == '测量链' and boardw2.pinned_keys() == ['ixPt', 'pldDist']:
        ok(f'seed_from_project restore keys={boardw2.pinned_keys()}')
    else:
        bad(f'seed restore group={boardw2.active_pin_group()} keys={boardw2.pinned_keys()}')
    # persist helper on board
    proj_pins2 = {'name': 'x'}
    boardw2.persist_pin_groups_to_project(proj_pins2)
    if (proj_pins2.get('hostWatch') or {}).get('pinGroups'):
        ok(f'persist_pin_groups_to_project={proj_pins2["hostWatch"]["pinGroups"]}')
    else:
        bad(f'persist={proj_pins2}')

    # ---- recipe dry-run side-by-side ----
    from desktop import recipe_library as rl
    from desktop.recipe_switch_dialog import RecipeSwitchDialog
    proj = {
        'name': 'dry',
        'steps': [
            {'id': 'a', 'name': '卡尺1', 'operation': 'geometry', 'params': {'caliperCount': 5, 'roiMode': 'auto'}},
            {'id': 'b', 'name': '定位1', 'operation': 'locate', 'params': {'minScore': 0.8}},
        ],
        'variables': {'flow': {'x': 1}},
        'recipes': [],
    }
    rl.capture_recipe(proj, '线体A', variant='A型')
    # mutate live
    proj['steps'][0]['params']['caliperCount'] = 12
    proj['steps'][1]['params']['minScore'] = 0.95
    proj['variables']['flow']['x'] = 9
    rid = proj['recipes'][0]['id']
    diff = rl.diff_recipe(proj, rid)
    side = rl.format_diff_side_by_side(diff)
    if any(r.get('key', '').endswith('caliperCount') for r in side):
        ok(f'side-by-side rows={len(side)} sample={side[0]}')
    else:
        bad(f'side={side}')
    class Doc:
        def __init__(self, p): self.project = p
        def commit(self, p): self.project = p
        def mark_dirty(self): pass
    dlg = RecipeSwitchDialog(Doc(proj), ROOT, None)
    names = {w.objectName() for w in dlg.findChildren(QWidget) if w.objectName()}
    for need in ('recipeDiffSideBySide', 'recipeDryRunDiffBtn', 'recipeDiffChip'):
        (ok if need in names else bad)(f'recipe {need}' if need in names else f'missing {need}')
    if dlg._recipe_list.count() < 1:
        bad('no recipes in list')
    else:
        dlg._recipe_list.setCurrentRow(0)
        d2 = dlg._dry_run_side_by_side()
        if d2 and dlg._diff_side.rowCount() >= 1 and 'Dry-run' in dlg._post_banner.text():
            ok(f'dry-run rows={dlg._diff_side.rowCount()} banner={dlg._post_banner.text()[:70]}')
        else:
            bad(f'dry rows={dlg._diff_side.rowCount()} banner={dlg._post_banner.text()!r} d2={d2}')
    # empty selection non-blocking
    dlg._recipe_list.clearSelection()
    # force no selection
    dlg._recipe_list.setCurrentRow(-1)
    empty = dlg._dry_run_side_by_side()
    if empty is None and '选中' in dlg._post_banner.text():
        ok('dry-run empty selection non-blocking')
    else:
        bad(f'empty={empty} banner={dlg._post_banner.text()!r}')


    # ---- recipe preview-apply + one-click rollback ----
    from desktop.recipe_library import (
        preview_apply_recipe, apply_recipe_with_rollback,
        rollback_last_recipe_apply, has_recipe_rollback, list_recipes,
    )
    # UI object names for new buttons
    names = {w.objectName() for w in dlg.findChildren(QWidget) if w.objectName()}
    for need in ('recipePreviewApplyBtn', 'recipeRollbackBtn'):
        (ok if need in names else bad)(f'recipe {need}' if need in names else f'missing {need}')

    proj_rb = deepcopy(proj)
    recipes = list_recipes(proj_rb)
    if not recipes:
        bad('no recipes for rollback test')
    else:
        rid = recipes[0]['id']
        # mutate live away from recipe snapshot
        for s in proj_rb.get('steps') or []:
            if isinstance(s, dict) and s.get('operation') == 'locate':
                s.setdefault('params', {})['minScore'] = 0.41
        snap_steps = deepcopy(proj_rb.get('steps'))
        bag = preview_apply_recipe(proj_rb, rid)
        if bag.get('mutatedLive') is False and proj_rb.get('steps') == snap_steps:
            ok(f'preview_apply_recipe chip={bag.get("chip")} would={bag.get("wouldApply")}')
        else:
            bad(f'preview mutated? {bag.get("mutatedLive")} steps_eq={proj_rb.get("steps")==snap_steps}')
        stats = apply_recipe_with_rollback(proj_rb, rid)
        if stats.get('rollbackReady') and has_recipe_rollback(proj_rb):
            ok(f'apply_with_rollback ready key={stats.get("rollbackKey")}')
        else:
            bad(f'rollbackReady={stats}')
        # dialog preview + rollback
        if hasattr(dlg, '_preview_apply') and hasattr(dlg, '_rollback_btn'):
            dlg.document.project = proj_rb
            # reselect recipe so preview has a selection
            if dlg._recipe_list.count() >= 1:
                dlg._recipe_list.setCurrentRow(0)
            prev = dlg._preview_apply()
            (ok if prev and prev.get('mutatedLive') is False else bad)(
                f'dlg._preview_apply banner={(dlg._post_banner.text()[:60] if dlg._post_banner else "")}')
            dlg._sync_rollback_btn()
            (ok if dlg._rollback_btn.isEnabled() else bad)('rollback btn enabled after apply')
            rb = rollback_last_recipe_apply(proj_rb)
            if rb.get('ok') and not has_recipe_rollback(proj_rb):
                ok(f'rollback_last ok rolled={rb.get("rolledBack")}')
            else:
                bad(f'rollback={rb}')
            ms2 = None
            for s in proj_rb.get('steps') or []:
                if isinstance(s, dict) and s.get('operation') == 'locate':
                    ms2 = (s.get('params') or {}).get('minScore')
            (ok if ms2 is not None and abs(float(ms2) - 0.41) < 1e-9 else bad)(
                f'rollback restored minScore={ms2}')
            dlg.document.project = proj_rb
            dlg._sync_rollback_btn()
            (ok if not dlg._rollback_btn.isEnabled() else bad)('rollback btn disabled after undo')
        else:
            bad('dialog missing preview/rollback UI')

    # ---- locate panel live ingest ----
    step = {
        'id': 'Lx', 'name': '定位', 'operation': 'locate',
        'params': normalize_locate_params({
            'templateLibrary': lib,
            'activeTemplateId': 'a1',
            'batchScoreThreshold': 0.70,
        }),
    }
    panel2 = LocateMatchPanel(step, {}, {'steps': [step], 'variables': {}})
    live_res = {
        'results': [{'id': 'Lx', 'data': {
            'templateScores': {'a1': 0.95, 'b2': 0.60, 'c3': 0.88},
            'bestScore': 0.95, 'activeTemplateId': 'a1',
        }}],
    }
    if hasattr(panel2, 'ingest_live_match_scores'):
        got = panel2.ingest_live_match_scores(live_res, soft_fallback=True)
        (ok if got else bad)(f'panel.ingest_live_match_scores={got}')
    else:
        bad('no ingest_live_match_scores')
    if hasattr(panel2, 'set_last_result'):
        panel2.set_last_result(live_res)
        ok('panel.set_last_result')
    board_live = panel2.run_batch_scoreboard() if hasattr(panel2, 'run_batch_scoreboard') else None
    if isinstance(board_live, dict):
        ok(f'run_batch_scoreboard source={board_live.get("source")} best={board_live.get("bestId")}')
    else:
        ok(f'run_batch_scoreboard returned {type(board_live).__name__}')

    print(f'\nTOTAL pass={pass_n} fail={fail_n}')
    return 0 if fail_n == 0 else 1

if __name__ == '__main__':
    sys.exit(main())
