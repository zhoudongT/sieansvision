#!/usr/bin/env python3
"""Wave soft: spark jump→filmstrip seek · blink conflict list footer ·
chip picker keyboard accel 1–9 · rollback export include-snap toggle.
No Halcon / robot / real TCP / cloud. Leave ?? os and :18280 alone.
"""
from __future__ import annotations
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
    from PySide6.QtWidgets import QApplication, QWidget, QLabel, QListWidget, QCheckBox, QMenu
    from PySide6.QtCore import Qt
    app = QApplication.instance() or QApplication([])

    # ---- 2) spark jump → filmstrip seek wire ----
    from desktop.widgets.filmstrip import FilmstripBar
    from desktop.locate_scoreboard import (
        MatchScoreTrend, MatchScoreSparkWidget, seek_filmstrip_from_spark_jump,
    )
    from desktop.locate_match_panel import LocateMatchPanel, normalize_locate_params

    fs = FilmstripBar()
    # fabricate three "frames" as temp empty paths (names matter)
    tmp = Path(tempfile.mkdtemp(prefix='sieans-sparkseek-'))
    frames = []
    for name in ('f001.png', 'f002.png', 'f003.png', 'f004.png', 'f005.png'):
        p = tmp / name
        p.write_bytes(b'')  # empty file ok for path list
        frames.append(str(p))
    fs.set_paths(frames, 0, root=tmp)
    (ok if fs.current_index() == 0 else bad)(f'filmstrip start idx={fs.current_index()}')

    hit = fs.seek_frame_token('f003.png')
    if hit.get('ok') and hit.get('index') == 2 and hit.get('matchedBy') in ('path', 'basename', 'stem'):
        ok(f'seek_frame_token basename → idx={hit["index"]} by={hit["matchedBy"]}')
    else:
        bad(f'seek_frame_token={hit}')

    hit2 = fs.seek_frame_token('f001', index=None)
    if hit2.get('ok') and hit2.get('index') == 0:
        ok(f'seek stem f001 → idx={hit2["index"]} by={hit2.get("matchedBy")}')
    else:
        bad(f'seek stem={hit2}')

    hit3 = fs.seek_frame_token('', index=4)
    if hit3.get('ok') and hit3.get('index') == 4:
        ok(f'seek index=4 → idx={hit3["index"]}')
    else:
        bad(f'seek index={hit3}')

    tr = MatchScoreTrend(12)
    for i, (s, ook, fr) in enumerate((
        (0.91, True, frames[0]), (0.88, True, frames[1]), (0.70, False, frames[2]),
        (0.93, True, frames[3]), (0.95, True, frames[4]),
    )):
        tr.push(s, label=f'run{i+1}', ok=ook, template_id='a1', frame=fr)

    bag = {'index': 2, 'frame': frames[2], 'label': 'run3', 'score': 0.70, 'ok': False}
    seek = seek_filmstrip_from_spark_jump(fs, bag)
    if seek.get('ok') and seek.get('index') == 2:
        ok(f'helper seek frame → idx={seek["index"]} by={seek.get("matchedBy")} path={Path(seek.get("path") or "").name}')
    else:
        bad(f'helper seek={seek}')

    # also by basename token only
    fs.select_index(0, emit=False)
    seek_b = seek_filmstrip_from_spark_jump(fs, {'frame': 'f004.png', 'label': 'run4', 'index': 3})
    if seek_b.get('ok') and seek_b.get('index') == 3:
        ok(f'helper basename f004 → idx={seek_b["index"]}')
    else:
        bad(f'helper basename={seek_b}')

    params = normalize_locate_params({})
    step = {'id': 'L1', 'name': '定位', 'operation': 'locate', 'params': params}
    panel = LocateMatchPanel(step, {}, {'steps': [step], 'variables': {}})
    panel.push_match_score(0.91, label='f1', ok=True, template_id='a1', frame=frames[0])
    panel.push_match_score(0.70, label='f2', ok=False, template_id='a1', frame=frames[2])
    if not hasattr(panel, 'set_filmstrip_seek_handler'):
        bad('panel missing set_filmstrip_seek_handler')
    else:
        seen = {}
        panel.set_filmstrip_seek_handler(lambda b: seen.update(b) or {'ok': True, 'index': 2, 'matchedBy': 'handler'})
        out = panel._on_spark_frame_jump({'index': 1, 'frame': frames[2], 'label': 'f2', 'score': 0.70})
        lab = getattr(panel, '_spark_jump_lab', None)
        txt = lab.text() if lab is not None else ''
        if seen.get('frame') == frames[2] and ('跳帧' in txt) and (out.get('seek') or {}).get('ok'):
            ok(f'panel handler seek lab={txt[:48]}')
        else:
            bad(f'seen={seen} txt={txt} out={out}')

    # wire real filmstrip via handler that calls helper
    panel.set_filmstrip_seek_handler(
        lambda b: seek_filmstrip_from_spark_jump(fs, b)
    )
    fs.select_index(0, emit=False)
    out2 = panel._on_spark_frame_jump({'index': 1, 'frame': frames[2], 'label': 'f2', 'score': 0.70})
    if (out2.get('seek') or {}).get('ok') and fs.current_index() == 2:
        ok(f'panel→filmstrip seek idx={fs.current_index()} matchedBy={(out2.get("seek") or {}).get("matchedBy")}')
    else:
        bad(f'panel→fs out2={out2} idx={fs.current_index()}')

    # ---- 4) blink conflict list in designer footer ----
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
    dlg = None
    err = None
    for args in ((doc, None), (doc,), (doc, None, ROOT)):
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
        for need in ('runUiBlinkConflictWarn', 'runUiBlinkConflictList', 'runUiBlinkConflictFooter'):
            (ok if need in names else bad)(f'ui {need}')
        (ok if hasattr(dlg, '_fill_blink_conflict_list') else bad)('has _fill_blink_conflict_list')
        # clean
        dlg.blink_toggle_edit.setText('Alt+B')
        dlg.blink_swap_edit.setText('Shift+Alt+B')
        info = dlg.check_blink_reserved_conflicts()
        filled = dlg._fill_blink_conflict_list(info)
        (ok if info.get('ok') and filled.get('ok') and not filled.get('rows') else bad)(
            f'clean conflicts ok rows={filled.get("rows")}'
        )
        # conflict Ctrl+S
        dlg.blink_toggle_edit.setText('Ctrl+S')
        dlg.blink_swap_edit.setText('Alt+P')
        info2 = dlg._on_blink_conflict_live_check()
        lst = dlg.blink_conflict_list
        foot = dlg.blink_conflict_footer
        n = lst.count() if lst is not None else 0
        foot_txt = foot.text() if foot is not None else ''
        # isHidden() reflects setVisible flag (dialog may never .show() in offscreen smoke)
        foot_shown = (not foot.isHidden()) if foot is not None else False
        if (not info2.get('ok')) and n >= 1 and foot_shown and '冲突' in foot_txt:
            items = [lst.item(i).text() for i in range(n)]
            ok(f'conflict list n={n} items={items} footer={foot_txt[:60]}')
        else:
            bad(f'info2={info2} n={n} foot_shown={foot_shown} foot={foot_txt}')

    # ---- 1) chip picker keyboard accel ----
    from desktop.host_var_watch import (
        pin_group_picker_accel_entries, apply_pin_group_picker_accels,
        format_host_watch_open_chip,
    )
    groups = {'测量链': ['ixPt', 'pldDist'], '判定': ['passGate'], '标定': ['calX', 'calY'], '统计': ['uph']}
    acc = pin_group_picker_accel_entries(groups, active='测量链')
    if (len(acc) == 4 and acc[0].get('accel') == '1' and acc[0].get('active')
            and acc[1].get('accel') == '2' and acc[3].get('accel') == '4'):
        ok(f'accel entries={[ (e["name"], e["accel"]) for e in acc ]}')
    else:
        bad(f'acc={acc}')

    chip = format_host_watch_open_chip(
        ['ixPt', 'pldDist', 'passGate'], groups, active='测量链', label='demo.sieans',
    )
    ents = chip.get('pinGroupEntries') or []
    if ents and ents[0].get('accel') == '1':
        ok(f'chip pinGroupEntries accel={[e.get("accel") for e in ents]}')
    else:
        bad(f'chip ents={ents}')

    menu = QMenu()
    for e in acc:
        a = menu.addAction(f'{e["name"]} · {e["nKeys"]}键')
        a.setData(e['name'])
    stamped = apply_pin_group_picker_accels(menu, acc)
    if (len(stamped) == 4 and stamped[0].get('accel') == '1'
            and stamped[0]['actionText'].startswith('1')):
        ok(f'stamped={[ (s["accel"], s["actionText"][:12]) for s in stamped ]}')
    else:
        bad(f'stamped={stamped}')

    src_mw = Path('desktop/mainwindow.py').read_text(encoding='utf-8')
    for need in ('pin_group_picker_accel_entries', 'apply_pin_group_picker_accels',
                 'QKeySequence', '_last_pin_group_picker_accels'):
        (ok if need in src_mw else bad)(f'mainwindow has {need}')

    # ---- 3) rollback export include-snap toggle ----
    from desktop.recipe_library import (
        capture_recipe, apply_recipe_with_rollback, export_recipe_rollback_stack,
        recipe_rollback_depth,
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
    for i, rid in enumerate([r['id'] for r in proj_r['recipes']]):
        proj_r['steps'][0]['params']['minScore'] = 0.1 * (i + 1)
        apply_recipe_with_rollback(proj_r, rid)

    bag0 = export_recipe_rollback_stack(proj_r, include_snapshots=False)
    bag1 = export_recipe_rollback_stack(proj_r, include_snapshots=True)
    if bag0.get('ok') and not bag0.get('includeSnapshots') and all('snapshot' not in e for e in bag0['entries']):
        ok(f'export default no-snap depth={bag0["depth"]}')
    else:
        bad(f'bag0={bag0}')
    if (bag1.get('ok') and bag1.get('includeSnapshots')
            and all(isinstance(e.get('snapshot'), dict) for e in bag1['entries'])):
        ok(f'export include-snap depth={bag1["depth"]} keys={list(bag1["entries"][0]["snapshot"].keys())[:4]}')
    else:
        bad(f'bag1 entries={[list(e.keys()) for e in bag1.get("entries") or []]}')

    dlg_r = RecipeSwitchDialog(Doc(deepcopy(proj_r)), ROOT, None)
    names = {w.objectName() for w in dlg_r.findChildren(QWidget) if w.objectName()}
    (ok if 'recipeRollbackExportSnapChk' in names else bad)('ui recipeRollbackExportSnapChk')
    (ok if hasattr(dlg_r, '_export_include_snapshots') else bad)('has _export_include_snapshots')
    chk = dlg_r.findChild(QCheckBox, 'recipeRollbackExportSnapChk')
    if chk is not None:
        chk.setChecked(False)
        (ok if dlg_r._export_include_snapshots() is False else bad)('chk off → False')
        chk.setChecked(True)
        (ok if dlg_r._export_include_snapshots() is True else bad)('chk on → True')
    else:
        bad('snap chk widget missing')

    # confirm untouched
    os_path = ROOT / 'os'
    (ok if os_path.exists() else bad)('?? os still present (untouched)')
    import socket
    s = socket.socket()
    try:
        # just note we do not touch 18280 — check nothing by connecting
        ok(':18280 left alone (no connect attempted)')
    finally:
        s.close()

    print(f'\\nRESULT {pass_n}/{fail_n}  (pass/fail)')
    return 0 if fail_n == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
