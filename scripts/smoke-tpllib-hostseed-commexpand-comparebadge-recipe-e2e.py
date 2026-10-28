#!/usr/bin/env python3
"""Wave soft platform:
1) locate/match template-library add/remove/preview/select
2) Host watch auto-seed from sample watchKeys/resultVar
3) Comm ${} live expand in watch
4) filmstrip/compare measure OK/NG badges
5) recipe apply→run loop banner / goto-run
No Halcon / robot / real TCP / cloud. Leave ?? os and :18280 alone.
"""
from __future__ import annotations
import json
import os
import sys
from pathlib import Path

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
    from PySide6.QtWidgets import QApplication, QWidget, QLabel, QListWidget, QPushButton
    app = QApplication.instance() or QApplication([])

    # ---------- 1) locate template library ----------
    from desktop.locate_match_panel import LocateMatchPanel, normalize_locate_params
    p = normalize_locate_params({})
    assert isinstance(p.get('templateLibrary'), list)
    ok('normalize templateLibrary default')
    step = {'id': 'L1', 'name': '定位', 'operation': 'locate', 'params': p}
    panel = LocateMatchPanel(step, {}, {'steps': [step], 'variables': {}})
    names = {w.objectName() for w in panel.findChildren(QWidget) if w.objectName()}
    for need in (
        'locateTemplateLibraryList', 'locateTplLibAddBtn', 'locateTplLibSelectBtn',
        'locateTplLibPreviewBtn', 'locateTplLibRemoveBtn', 'locateTplLibPreview',
        'locateTemplateStatus', 'locateTemplatePath',
    ):
        (ok if need in names else bad)(f'tpl {need}' if need in names else f'missing {need}')
    # add via params + refresh
    panel.params['templatePath'] = '/tmp/sieans_tpl_demo.png'
    panel.params['hasTemplate'] = True
    panel.params['templateLibrary'] = [
        {'id': 'a1', 'name': '基准A', 'path': '/tmp/sieans_tpl_demo.png', 'note': 'demo'},
        {'id': 'b2', 'name': '基准B', 'path': '/tmp/other.png', 'note': ''},
    ]
    panel.params['activeTemplateId'] = 'a1'
    panel._refresh_tpl_library_list()
    lw = panel.findChild(QListWidget, 'locateTemplateLibraryList')
    if lw and lw.count() == 2:
        ok(f'tpl library list count={lw.count()}')
    else:
        bad(f'tpl library list count={getattr(lw,"count",lambda:None)()}')
    lw.setCurrentRow(1)
    panel._tpl_lib_select()
    if panel.params.get('templatePath') == '/tmp/other.png' and panel.params.get('activeTemplateId') == 'b2':
        ok('tpl library select applies path+id')
    else:
        bad(f'tpl select path={panel.params.get("templatePath")} id={panel.params.get("activeTemplateId")}')
    panel._tpl_lib_preview()
    prev = panel.findChild(QLabel, 'locateTplLibPreview')
    pt = prev.text() if prev else ''
    if prev and ('基准B' in pt or 'other.png' in pt or '已选用' in pt):
        ok(f'tpl preview={pt[:60]}')
    else:
        bad(f'tpl preview={pt!r}')
    before = len(panel.params['templateLibrary'])
    # remove without dialog: call list remove via params
    panel.params['templateLibrary'] = [e for e in panel.params['templateLibrary'] if e.get('id') != 'b2']
    panel._refresh_tpl_library_list()
    if lw.count() == before - 1:
        ok('tpl library remove shrinks list')
    else:
        bad(f'tpl remove count={lw.count()} expected {before-1}')

    # ---------- 2) Host watch seed from sample ----------
    from desktop.host_var_watch import (
        collect_watch_keys_from_project, HostVarWatchBoard, HostVarWatchDialog,
        expand_watch_value, collect_flow_entries, classify_watch_key,
    )
    sample = ROOT / 'projects/open-and-run-caliper-measure.sieans'
    proj = json.loads(sample.read_text(encoding='utf-8'))
    keys = collect_watch_keys_from_project(proj)
    for k in ('ixPt', 'pldDist', 'passGate', 'ixPt_judgeOk', 'pldDist_judgeOk'):
        (ok if k in keys else bad)(f'seed key {k}' if k in keys else f'missing seed {k}')
    board = HostVarWatchBoard()
    class Doc:
        project = proj
    board.bind(Doc(), None)
    seeded = board.seed_from_project(proj, label='caliper-measure')
    if len(seeded) >= 5 and board.pinned_keys():
        ok(f'seed_from_project n={len(seeded)} pinned={len(board.pinned_keys())}')
    else:
        bad(f'seed_from_project seeded={seeded!r}')
    if '已种子' in board.seed_lab.text():
        ok(f'seed label={board.seed_lab.text()}')
    else:
        bad(f'seed label={board.seed_lab.text()!r}')
    # measure preset auto
    if board.preset.currentData() == 'measure':
        ok('auto measure preset')
    else:
        bad(f'preset={board.preset.currentData()}')
    # table shows pending rows
    board.render()
    if board.table.rowCount() >= 3:
        ok(f'watch rows after seed={board.table.rowCount()} cols={board.table.columnCount()}')
    else:
        bad(f'watch rows={board.table.rowCount()}')
    if board.table.columnCount() >= 5:
        ok('watch has 展开 column')
    else:
        bad(f'watch cols={board.table.columnCount()}')

    # ---------- 3) Comm ${} live expand ----------
    proj2 = {
        'variables': {'score': '0.91', 'payload': 'HELLO'},
        'commManager': {
            'sendEvents': [
                {'name': '报OK', 'message': 'SCORE=${score} PAY=${payload}'},
                {'name': '空', 'message': 'plain'},
            ]
        },
    }
    class Doc2:
        project = proj2
    board2 = HostVarWatchBoard()
    board2.bind(Doc2(), {'variables': {'flow': {'score': '0.95', 'payload': 'LIVE'}}})
    board2.preset.setCurrentIndex(board2.preset.findData('comm'))
    board2.render()
    # find expanded cell
    found_exp = False
    found_tpl = False
    for r in range(board2.table.rowCount()):
        name = board2.table.item(r, 1).text() if board2.table.item(r, 1) else ''
        val = board2.table.item(r, 2).text() if board2.table.item(r, 2) else ''
        exp = board2.table.item(r, 3).text() if board2.table.item(r, 3) else ''
        if 'commSend:报OK' in name and '0.95' in val:
            found_exp = True
        if '${' in name or '${' in val:
            found_tpl = True
        if '0.95' in exp or 'LIVE' in exp:
            found_exp = True
    (ok if found_exp else bad)('comm live expand shows runtime value' if found_exp else 'comm expand missing')
    (ok if found_tpl or board2.table.rowCount() >= 1 else bad)(
        f'comm/${{}} rows={board2.table.rowCount()}' if board2.table.rowCount() else 'no comm rows'
    )
    expanded, did = expand_watch_value(proj2, 'x=${score}', {'variables': {'flow': {'score': '1.2'}}})
    if did and '1.2' in str(expanded):
        ok(f'expand_watch_value={expanded}')
    else:
        bad(f'expand_watch_value did={did} val={expanded}')

    # ---------- 4) compare / filmstrip measure badges ----------
    from desktop.widgets.filmstrip import FilmstripBar, CompareThumbStrip
    strip = CompareThumbStrip()
    # fake paths (no need real images)
    strip._path_badges = {}
    strip.set_path_badges({'/tmp/a.png': 'OK', '/tmp/b.png': False, '/tmp/c.png': 'NG'})
    bag = strip.path_badges()
    print('DBG badges', bag)
    if bag.get('/tmp/a.png') == 'OK' and bag.get('/tmp/b.png') == 'NG' and bag.get('/tmp/c.png') == 'NG':
        ok(f'compare set_path_badges={bag}')
    else:
        bad(f'compare badges={bag}')
    strip.set_paths(['/tmp/a.png', '/tmp/b.png'], active='/tmp/a.png')
    # after set_paths, labels should carry badges
    texts = [strip._list.item(i).text() for i in range(strip._list.count())]
    if any('[OK]' in t for t in texts) and any('[NG]' in t for t in texts):
        ok(f'compare thumb labels={texts}')
    else:
        bad(f'compare thumb labels={texts}')
    fs = FilmstripBar()
    fs.set_paths(['/tmp/a.png', '/tmp/b.png'], 0)
    fs.set_frame_measure_badges({'/tmp/a.png': True, '/tmp/b.png': 'NG'})
    ftexts = [fs.thumbs.item(i).text() for i in range(fs.thumbs.count())]
    if any('[OK]' in t for t in ftexts) and any('[NG]' in t for t in ftexts):
        ok(f'filmstrip measure badges={ftexts}')
    else:
        bad(f'filmstrip measure badges={ftexts}')
    # mainwindow helper presence (import module, don't construct full window)
    import desktop.mainwindow as mwmod
    src = Path(mwmod.__file__).read_text(encoding='utf-8')
    for name in (
        '_seed_host_var_watch_from_project',
        '_sync_filmstrip_measure_badges',
        '_measure_badge_for_result',
    ):
        (ok if f'def {name}' in src else bad)(f'mainwindow {name}' if f'def {name}' in src else f'missing {name}')

    # ---------- 5) recipe apply→run banner ----------
    from desktop.recipe_switch_dialog import RecipeSwitchDialog
    from desktop import recipe_library as rl
    from copy import deepcopy
    proj_r = {
        'name': 'loop',
        'steps': [
            {'id': 'a', 'name': '卡尺1', 'operation': 'geometry', 'params': {'caliperCount': 10}},
            {'id': 'b', 'name': '生产任务1', 'operation': 'production_task', 'params': {'taskName': 'T', 'recipe': ''}},
        ],
        'variables': {},
        'runUi': {},
        'recipes': [],
    }
    class DocR:
        def __init__(self, p):
            self.project = p
        def commit(self, p):
            self.project = p
        def mark_dirty(self):
            pass
    doc = DocR(proj_r)
    e = rl.capture_recipe(doc.project, '线体A', variant='A型')
    dlg = RecipeSwitchDialog(doc, ROOT, None)
    assert hasattr(dlg, '_post_banner') and hasattr(dlg, '_goto_run_btn')
    ok('recipe post banner + goto-run btn')
    names = {w.objectName() for w in dlg.findChildren(QWidget) if w.objectName()}
    for need in ('recipePostApplyBanner', 'recipeGotoRunBtn', 'recipeEnterRunChk', 'recipeTrialOnceChk'):
        (ok if need in names else bad)(f'recipe {need}' if need in names else f'missing {need}')
    stamped = dlg._stamp_post_apply({'name': '线体A', 'applied': 1, 'skipped': 0})
    dlg._update_post_banner(stamped)
    bt = dlg._post_banner.text()
    if '已套用' in bt and ('运行' in bt or '试跑' in bt or '下一步' in bt):
        ok(f'post banner={bt[:80]}')
    else:
        bad(f'post banner unexpected={bt!r}')
    dlg._chk_enter_run.setChecked(True)
    dlg._chk_trial_once.setChecked(True)
    stamped2 = dlg._stamp_post_apply({'name': '线体A', 'applied': 2, 'skipped': 1})
    dlg._update_post_banner(stamped2)
    if '试跑' in dlg._post_banner.text() or '运行' in dlg._post_banner.text():
        ok(f'post banner enter+trial={dlg._post_banner.text()[:80]}')
    else:
        bad(f'banner={dlg._post_banner.text()!r}')

    # dialog HostVarWatchDialog auto-seed
    dlgw = HostVarWatchDialog(Doc(), None, None)
    if dlgw.board.pinned_keys():
        ok(f'dialog auto-seed pinned={len(dlgw.board.pinned_keys())}')
    else:
        bad('dialog auto-seed empty')

    print(f'\\nTOTAL pass={pass_n} fail={fail_n}')
    return 0 if fail_n == 0 else 1

if __name__ == '__main__':
    sys.exit(main())
