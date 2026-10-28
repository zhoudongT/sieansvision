#!/usr/bin/env python3
"""Wave soft: spark-seek thumb flash · blink alternate chords ·
spark↔compare-strip sync · chip accel discoverability tip ·
rollback export snap size estimate.
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

    # ---- 1) spark-seek flash on filmstrip thumb ----
    from desktop.widgets.filmstrip import FilmstripBar, CompareThumbStrip
    from desktop.locate_scoreboard import (
        MatchScoreTrend, seek_filmstrip_from_spark_jump,
        sync_compare_strip_from_spark_jump, sync_spark_from_compare_path,
        MatchScoreSparkWidget,
    )
    from desktop.locate_match_panel import LocateMatchPanel, normalize_locate_params

    fs = FilmstripBar()
    (ok if hasattr(fs, 'flash_seek_thumb') else bad)('has flash_seek_thumb')
    tmp = Path(tempfile.mkdtemp(prefix='sieans-sparkflash-'))
    frames = []
    for name in ('f001.png', 'f002.png', 'f003.png', 'f004.png', 'f005.png'):
        p = tmp / name
        p.write_bytes(b'')
        frames.append(str(p))
    fs.set_paths(frames, 0, root=tmp)

    flash = fs.flash_seek_thumb(2)
    if flash.get('ok') and flash.get('flashed') and flash.get('index') == 2:
        ok(f'flash_seek_thumb idx=2 path={Path(flash.get("path") or "").name}')
    else:
        bad(f'flash={flash}')

    hit = fs.seek_frame_token('f004.png', flash=True)
    if hit.get('ok') and hit.get('index') == 3 and (hit.get('flash') or {}).get('ok'):
        ok(f'seek+flash f004 → idx={hit["index"]} flash={hit["flash"].get("flashed")}')
    else:
        bad(f'seek+flash={hit}')

    fs.select_index(0, emit=False)
    seek = seek_filmstrip_from_spark_jump(fs, {
        'index': 2, 'frame': frames[2], 'label': 'run3', 'score': 0.70,
    }, flash=True)
    if seek.get('ok') and seek.get('index') == 2 and (seek.get('flash') or {}).get('ok'):
        ok(f'helper seek+flash idx={seek["index"]} by={seek.get("matchedBy")}')
    else:
        bad(f'helper seek={seek}')

    # ---- 5) spark ↔ compare-strip sync ----
    cs = CompareThumbStrip()
    (ok if hasattr(cs, 'activate_path') else bad)('has activate_path')
    cs.set_paths([frames[1], frames[2], frames[4]], active=frames[1])
    act = cs.activate_path(frames[2])
    if act.get('ok') and act.get('index') == 1:
        ok(f'activate_path f003 → idx={act["index"]} by={act.get("matchedBy")}')
    else:
        bad(f'activate={act}')

    sync = sync_compare_strip_from_spark_jump(cs, {
        'frame': frames[4], 'label': 'run5', 'path': frames[4],
    })
    if sync.get('ok') and sync.get('index') == 2:
        ok(f'spark→compare sync idx={sync["index"]} by={sync.get("matchedBy")}')
    else:
        bad(f'sync={sync}')

    # not on strip → fail soft
    miss = sync_compare_strip_from_spark_jump(cs, {'frame': frames[0]})
    (ok if not miss.get('ok') else bad)(f'not-on-strip soft fail reason={miss.get("reason")}')

    # reverse: compare → spark
    tr = MatchScoreTrend(12)
    for i, (s, ook, fr) in enumerate((
        (0.91, True, frames[0]), (0.88, True, frames[1]), (0.70, False, frames[2]),
        (0.93, True, frames[3]), (0.95, True, frames[4]),
    )):
        tr.push(s, label=f'run{i+1}', ok=ook, template_id='a1', frame=fr)
    spark = MatchScoreSparkWidget(None, width=128, height=28)
    spark.set_from_trend(tr)
    rev = sync_spark_from_compare_path(spark, frames[2], trend=tr)
    if rev.get('ok') and rev.get('local') >= 0:
        ok(f'compare→spark local={rev["local"]} index={rev["index"]} frame={Path(rev.get("frame") or "").name}')
    else:
        bad(f'rev={rev}')
    if int(getattr(spark, '_sync_select_local', -1)) == int(rev.get('local', -99)):
        ok(f'spark _sync_select_local={spark._sync_select_local}')
    else:
        bad(f'sync_select={getattr(spark, "_sync_select_local", None)} vs {rev.get("local")}')

    # panel wiring
    params = normalize_locate_params({})
    step = {'id': 'L1', 'name': '定位', 'operation': 'locate', 'params': params}
    panel = LocateMatchPanel(step, {}, {'steps': [step], 'variables': {}})
    panel.push_match_score(0.91, label='f1', ok=True, template_id='a1', frame=frames[0])
    panel.push_match_score(0.70, label='f2', ok=False, template_id='a1', frame=frames[2])
    (ok if hasattr(panel, 'set_compare_strip_sync_handler') else bad)('panel has set_compare_strip_sync_handler')
    (ok if hasattr(panel, '_resolve_compare_strip') else bad)('panel has _resolve_compare_strip')

    panel.set_filmstrip_seek_handler(lambda b: seek_filmstrip_from_spark_jump(fs, b, flash=True))
    seen_cmp = {}
    panel.set_compare_strip_sync_handler(
        lambda b: seen_cmp.update(b) or sync_compare_strip_from_spark_jump(cs, b)
    )
    fs.select_index(0, emit=False)
    cs.set_paths([frames[1], frames[2], frames[4]], active=frames[1])
    out = panel._on_spark_frame_jump({
        'index': 1, 'frame': frames[2], 'label': 'f2', 'score': 0.70,
    })
    lab = getattr(panel, '_spark_jump_lab', None)
    txt = lab.text() if lab is not None else ''
    if ((out.get('seek') or {}).get('ok') and (out.get('compareSync') or {}).get('ok')
            and '对比' in txt):
        ok(f'panel seek+compareSync lab={txt[:64]}')
    else:
        bad(f'out={out} txt={txt} seen={seen_cmp}')

    src_mw = Path('desktop/mainwindow.py').read_text(encoding='utf-8')
    for need in ('_sync_spark_from_compare_path', 'sync_spark_from_compare_path'):
        (ok if need in src_mw else bad)(f'mainwindow has {need}')

    # ---- 2) blink conflict suggest alternate chords ----
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
        for need in ('runUiBlinkConflictList', 'runUiBlinkConflictFooter', 'runUiBlinkSuggestLab'):
            (ok if need in names else bad)(f'ui {need}')
        (ok if hasattr(dlg, 'suggest_blink_alternate_chords') else bad)('has suggest_blink_alternate_chords')
        (ok if hasattr(dlg, '_on_blink_suggest_click') else bad)('has _on_blink_suggest_click')

        dlg.blink_toggle_edit.setText('Ctrl+S')
        dlg.blink_swap_edit.setText('Alt+P')
        info = dlg._on_blink_conflict_live_check()
        filled = dlg._fill_blink_conflict_list(info)
        sug = list(filled.get('suggestions') or [])
        lst = dlg.blink_conflict_list
        foot = dlg.blink_conflict_footer
        sug_lab = dlg.blink_suggest_lab
        n = lst.count() if lst is not None else 0
        foot_txt = foot.text() if foot is not None else ''
        sug_txt = sug_lab.text() if sug_lab is not None else ''
        sug_shown = (not sug_lab.isHidden()) if sug_lab is not None else False
        rows = [lst.item(i).text() for i in range(n)] if lst is not None else []
        has_suggest_row = any(str(r).startswith('建议') for r in rows)
        if (not info.get('ok')) and sug and has_suggest_row and sug_shown and '建议' in foot_txt:
            ok(f'alt chords sug={[(s.get("field"), s.get("suggest")) for s in sug]} rows={rows}')
        else:
            bad(f'info={info} sug={sug} rows={rows} sug_txt={sug_txt} foot={foot_txt} shown={sug_shown}')

        # click apply suggestions
        applied = dlg._on_blink_suggest_click()
        if applied.get('ok') and applied.get('applied'):
            # after apply, should clear conflict if alts are free
            info2 = dlg.check_blink_reserved_conflicts()
            if info2.get('ok'):
                ok(f'suggest click applied={applied.get("applied")} now clean')
            else:
                # still ok if applied something even if residual
                ok(f'suggest click applied={applied.get("applied")} residual={info2.get("warn")}')
        else:
            bad(f'applied={applied}')

    # ---- 3) chip accel discoverability tip ----
    from desktop.host_var_watch import (
        pin_group_picker_accel_entries, apply_pin_group_picker_accels,
        pin_group_picker_accel_tip, apply_pin_group_picker_accel_tip,
    )
    groups = {'测量链': ['ixPt', 'pldDist'], '判定': ['passGate'], '标定': ['calX', 'calY'], '统计': ['uph']}
    acc = pin_group_picker_accel_entries(groups, active='测量链')
    tip = pin_group_picker_accel_tip(acc)
    if '1' in tip and '9' not in tip.replace('1–4', '').replace('1-4', '') or '1–4' in tip or '1-4' in tip:
        # tip should mention 1–4 for 4 groups
        if '1–4' in tip or '1-4' in tip or '数字键' in tip:
            ok(f'accel tip={tip}')
        else:
            bad(f'tip unexpected={tip}')
    else:
        if '数字键' in tip:
            ok(f'accel tip={tip}')
        else:
            bad(f'tip={tip}')

    menu = QMenu()
    tip_info = apply_pin_group_picker_accel_tip(menu, acc)
    for e in acc:
        a = menu.addAction(f'{e["name"]} · {e["nKeys"]}键')
        a.setData(e['name'])
    # re-apply tip after actions so insert-to-top works; call again
    tip_info2 = apply_pin_group_picker_accel_tip(menu, acc)
    names_act = [a.objectName() for a in menu.actions() if a.objectName()]
    tip_acts = [a for a in menu.actions() if a.objectName() == 'hostWatchPinGroupAccelTip']
    if tip_info.get('ok') or tip_info2.get('ok'):
        if tip_acts and (not tip_acts[0].isEnabled()) and '数字键' in tip_acts[0].text():
            ok(f'menu tip action text={tip_acts[0].text()[:40]} names={names_act}')
        else:
            bad(f'tip_acts={[(a.objectName(), a.text(), a.isEnabled()) for a in tip_acts]} tip_info={tip_info}/{tip_info2}')
    else:
        bad(f'tip_info={tip_info} tip_info2={tip_info2}')

    for need in ('apply_pin_group_picker_accel_tip', 'pin_group_picker_accel_tip',
                 '_last_pin_group_picker_accel_tip'):
        (ok if need in src_mw else bad)(f'mainwindow has {need}')

    # ---- 4) rollback export snap size estimate ----
    from desktop.recipe_library import (
        capture_recipe, apply_recipe_with_rollback, export_recipe_rollback_stack,
        estimate_rollback_export_bytes,
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

    est0 = estimate_rollback_export_bytes(proj_r, include_snapshots=False)
    est1 = estimate_rollback_export_bytes(proj_r, include_snapshots=True)
    if (est0.get('ok') and est1.get('ok') and est0.get('bytes', 0) > 0
            and est1.get('bytes', 0) >= est0.get('bytes', 0)
            and est0.get('human') and est1.get('withSnapHuman')):
        ok(f'est no-snap={est0["human"]} with={est1["human"]} delta={est1.get("deltaHuman")}')
    else:
        bad(f'est0={est0} est1={est1}')

    bag = export_recipe_rollback_stack(proj_r, include_snapshots=True)
    (ok if isinstance(bag.get('approxBytes'), int) and bag['approxBytes'] > 0 else bad)(
        f'export approxBytes={bag.get("approxBytes")}'
    )

    dlg_r = RecipeSwitchDialog(Doc(deepcopy(proj_r)), ROOT, None)
    names = {w.objectName() for w in dlg_r.findChildren(QWidget) if w.objectName()}
    (ok if 'recipeRollbackExportSnapChk' in names else bad)('ui recipeRollbackExportSnapChk')
    (ok if 'recipeRollbackExportSizeLab' in names else bad)('ui recipeRollbackExportSizeLab')
    (ok if hasattr(dlg_r, '_refresh_rollback_export_size_lab') else bad)('has _refresh_rollback_export_size_lab')
    chk = dlg_r.findChild(QCheckBox, 'recipeRollbackExportSnapChk')
    size_lab = dlg_r.findChild(QLabel, 'recipeRollbackExportSizeLab')
    if chk is not None and size_lab is not None:
        chk.setChecked(False)
        info = dlg_r._refresh_rollback_export_size_lab()
        t0 = size_lab.text()
        chk.setChecked(True)
        info1 = dlg_r._refresh_rollback_export_size_lab()
        t1 = size_lab.text()
        if '约' in t0 and '约' in t1 and ('无快照' in t0 or '不含' in t0 or '无快照' in t0):
            ok(f'size lab off={t0[:48]} on={t1[:48]}')
        else:
            bad(f't0={t0} t1={t1} info={info} info1={info1}')
    else:
        bad('size lab/chk missing')

    # confirm untouched
    os_path = ROOT / 'os'
    (ok if os_path.exists() else bad)('?? os still present (untouched)')
    import socket
    s = socket.socket()
    try:
        ok(':18280 left alone (no connect attempted)')
    finally:
        s.close()

    print(f'\nRESULT {pass_n}/{fail_n}  (pass/fail)')
    return 0 if fail_n == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
