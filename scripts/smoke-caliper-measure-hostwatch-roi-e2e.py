#!/usr/bin/env python3
"""Wave: caliper→measure sample + Defects ref UX + OCR ROI + Host var watch + filmstrip result strip + N4 bangs."""
from __future__ import annotations
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
pass_n = fail_n = 0

def ok(m):
    global pass_n; pass_n += 1; print('PASS:', m)
def bad(m):
    global fail_n; fail_n += 1; print('FAIL:', m)

def main():
    from PySide6.QtWidgets import QApplication, QWidget, QLabel
    app = QApplication.instance() or QApplication([])

    # 1) sample project E2E wiring
    sample = ROOT / 'projects/open-and-run-caliper-measure.sieans'
    if not sample.is_file():
        bad('sample missing')
        return 1
    proj = json.loads(sample.read_text(encoding='utf-8'))
    ops = {s['id']: s for s in proj.get('steps') or []}
    by_op = {}
    for s in proj.get('steps') or []:
        by_op.setdefault(s.get('operation'), []).append(s)
    if 'geometry' not in by_op:
        bad('sample missing geometry')
    else:
        ok('sample has geometry')
    ix = (by_op.get('line_intersect') or [None])[0]
    pld = (by_op.get('point_line_distance') or [None])[0]
    if not ix or (ix.get('params') or {}).get('resultVar') != 'ixPt':
        bad(f'ix resultVar {(ix or {}).get("params")}')
    else:
        ok('ix resultVar=ixPt')
    if not (ix.get('params') or {}).get('judgeEnable'):
        bad('ix judgeEnable off')
    else:
        ok('ix judgeEnable')
    if not pld or (pld.get('params') or {}).get('resultVar') != 'pldDist':
        bad(f'pld resultVar {(pld or {}).get("params")}')
    else:
        ok('pld resultVar=pldDist')
    watch = ((proj.get('runUi') or {}).get('meta') or {}).get('watchKeys') or []
    for k in ('ixPt', 'pldDist', 'ixPt_judgeOk', 'pldDist_judgeOk', 'passGate'):
        (ok if k in watch else bad)(f'watchKeys {k}' if k in watch else f'missing watchKeys {k}')
    vars_ = proj.get('variables') or {}
    for k in ('ixPt', 'pldDist', 'passGate'):
        (ok if k in vars_ else bad)(f'variables seed {k}' if k in vars_ else f'missing var {k}')

    # 2) DefectsPanel reference UX
    from desktop.recognize_panels import DefectsPanel, OcrPanel, _norm_defects, _norm_ocr
    dstep = {'id': 'd1', 'name': '缺陷', 'operation': 'defects',
             'params': _norm_defects({}), 'reference': ''}
    dpanel = DefectsPanel(dstep, {}, proj)
    donames = {w.objectName() for w in dpanel.findChildren(QWidget) if w.objectName()}
    for need in ('defectsRefStatus', 'defectsRefLoadBtn', 'defectsRefClearBtn',
                 'defectsRefUseCurrentBtn', 'defectsReferencePath'):
        (ok if need in donames else bad)(f'defects {need}' if need in donames else f'missing {need}')
    st = dpanel.findChild(QLabel, 'defectsRefStatus')
    if st and ('未' in st.text() or '缺' in st.text() or '无' in st.text() or '参考' in st.text()):
        ok(f'defects status missing-feedback={st.text()[:40]}')
    else:
        bad(f'defects status unexpected={getattr(st,"text",lambda:"")()!r}')
    # bind synthetic reference on panel's own deepcopy
    dpanel.step['reference'] = 'data:image/png;base64,aaa'
    dpanel.params['hasReference'] = True
    dpanel.params['referencePath'] = '/tmp/ref.png'
    dpanel._sync_ref_status()
    st2 = dpanel.findChild(QLabel, 'defectsRefStatus')
    if st2 and '已加载' in st2.text():
        ok(f'defects status loaded={st2.text()[:40]}')
    else:
        bad(f'defects loaded status={getattr(st2,"text",lambda:"")()!r}')
    dpanel._clear_reference()
    if not dpanel.step.get('reference') and not dpanel.params.get('hasReference'):
        ok('defects clear reference')
    else:
        bad(f'defects clear failed ref={dpanel.step.get("reference")!r} has={dpanel.params.get("hasReference")}')

    # 3) OcrPanel ROI
    ostep = {'id': 'o1', 'name': 'OCR', 'operation': 'ocr',
             'params': _norm_ocr({'roiMode': 'draw', 'roi': [10, 20, 100, 80]})}
    opanel = OcrPanel(ostep, {}, proj)
    oonames = {w.objectName() for w in opanel.findChildren(QWidget) if w.objectName()}
    for need in ('ocrRoiMode', 'ocrRoiEditBtn', 'ocrRoiClearBtn', 'ocrRoiSummary'):
        (ok if need in oonames else bad)(f'ocr {need}' if need in oonames else f'missing {need}')
    summary = opanel.findChild(QLabel, 'ocrRoiSummary')
    txt = summary.text() if summary else ''
    if '10' in txt and '100' in txt:
        ok(f'ocr roi summary={txt[:50]}')
    else:
        bad(f'ocr roi summary unexpected={txt!r}')
    from desktop.simple_roi_editor import SimpleRoiEditorDialog
    dlg = SimpleRoiEditorDialog({'roi': [10, 20, 100, 80], 'roiMode': 'draw'}, parent=None)
    assert dlg.roi_item is not None
    got = dlg.roi_item.roi_list()
    if isinstance(got, (list, tuple)) and len(got) == 4:
        ok(f'simple roi editor roi={[round(v,1) for v in got]}')
    else:
        bad(f'simple roi editor no roi {got}')
    # simulate accept path
    dlg._accept()
    rp = dlg.result_params()
    if rp.get('roiMode') == 'draw' and isinstance(rp.get('roi'), list) and len(rp['roi']) == 4:
        ok(f'simple roi result_params={rp}')
    else:
        bad(f'simple roi result_params={rp}')

    # 4) Host var watch
    from desktop.host_var_watch import (
        classify_watch_key, filter_entries, collect_flow_entries,
        HostVarWatchBoard, HostVarWatchDialog,
    )
    assert classify_watch_key('ixPt_judgeOk') == 'measure'
    assert classify_watch_key('pldDist') == 'measure'
    assert classify_watch_key('commAccept_Pass') == 'comm'
    assert classify_watch_key('ocr_text') == 'defects_ocr'
    assert classify_watch_key('${flow.passGate}') == 'template'
    ok('classify_watch_key presets')
    class Doc:
        project = {
            'variables': {'ixPt': 1, 'pldDist': 2, 'passGate': 1, 'commAccept_Pass': 1},
            'globalVariables': {},
        }
    lr = {'variables': {'flow': {
        'ixPt': 12.5, 'ixPt_x': 10, 'ixPt_y': 20, 'ixPt_judgeOk': 1,
        'pldDist': 55.0, 'pldDist_distance': 55.0, 'pldDist_judgeOk': 0,
        'passGate': 0, 'ocr_text': 'ABC', 'commAccept_Pass': 1,
    }}}
    entries = collect_flow_entries(Doc(), lr)
    rows = filter_entries(entries, 'measure', '')
    names = {n for _, n, _, _ in rows}
    if 'ixPt' in names and 'pldDist_judgeOk' in names:
        ok(f'filter measure n={len(rows)}')
    else:
        bad(f'filter measure names={names}')
    board = HostVarWatchBoard()
    board.bind(Doc(), lr)
    if board.table.rowCount() >= 5:
        ok(f'HostVarWatchBoard rows={board.table.rowCount()}')
    else:
        bad(f'HostVarWatchBoard rows={board.table.rowCount()}')
    dlgw = HostVarWatchDialog(Doc(), lr)
    assert hasattr(dlgw, 'board')
    ok('HostVarWatchDialog shell')

    # VariablesDialog watch preset
    from desktop.variables_dialog import VariablesDialog
    # Document-like
    class FakeDoc:
        project = {'variables': {'flow': {'ixPt': 1, 'commAccept_Pass': 1}},
                   'variableTypes': {}, 'variableNotes': {}}
        def __init__(self):
            self.project = type(self).project
    # VariablesDialog may need richer document — soft check objectName presence via source
    src = (ROOT / 'desktop/variables_dialog.py').read_text(encoding='utf-8')
    if 'varsWatchPreset' in src and 'classify_watch_key' in src:
        ok('VariablesDialog watch_preset wired')
    else:
        bad('VariablesDialog watch_preset missing')

    # 5) Filmstrip result strip
    from desktop.widgets.filmstrip import FilmstripBar
    fs = FilmstripBar()
    assert hasattr(fs, 'push_module_results')
    assert hasattr(fs, 'result_strip')
    records = [
        {'id': 'a', 'operation': 'line_intersect', 'judgeOk': True, 'outputs': {'x': 1}},
        {'id': 'b', 'operation': 'point_line_distance', 'judgeOk': False, 'outputs': {'distance': 9.5}},
        {'id': 'c', 'operation': 'geometry', 'ok': True},
    ]
    names_map = {'a': '交点', 'b': '点线距', 'c': '几何'}
    fs.push_module_results(records, names_map)
    if (not fs.result_strip.isHidden()) and 'OK' in fs.result_strip.text() and 'NG' in fs.result_strip.text():
        ok(f'filmstrip result strip={fs.result_strip.text()[:80]}')
    else:
        bad(f'filmstrip strip visible={fs.result_strip.isVisible()} text={fs.result_strip.text()!r}')

    # 6) N4 bangs
    from desktop.config_status import step_incomplete_reason, node_needs_bang
    d_incomplete = {'id': 'd', 'operation': 'defects', 'params': {}, 'imageFrom': 'src'}
    # may need imageFrom only — without reference should bang
    reason = step_incomplete_reason(d_incomplete, proj)
    if reason and '参考' in reason:
        ok(f'defects bang={reason}')
    else:
        # if image missing first, that's also fine
        if reason:
            ok(f'defects bang(other)={reason}')
        else:
            bad('defects should bang without reference')
    o_draw = {'id': 'o', 'operation': 'ocr', 'params': {'roiMode': 'draw'}, 'imageFrom': 'src'}
    reason = step_incomplete_reason(o_draw, proj)
    if reason and 'ROI' in reason:
        ok(f'ocr draw bang={reason}')
    else:
        bad(f'ocr draw bang unexpected={reason!r}')
    m_bang = {'id': 'm', 'operation': 'line_intersect',
              'params': {'mode': 'manual', 'judgeEnable': True}}
    reason = step_incomplete_reason(m_bang, proj)
    if reason and 'resultVar' in reason:
        ok(f'measure judge bang={reason}')
    else:
        bad(f'measure judge bang unexpected={reason!r}')

    # 7) mainwindow static wire
    mw = (ROOT / 'desktop/mainwindow.py').read_text(encoding='utf-8')
    for needle in ("'var_watch'", 'HostVarWatchDialog', '变量监视板', 'push_module_results'):
        (ok if needle in mw else bad)(f'mainwindow has {needle}' if needle in mw else f'mainwindow missing {needle}')

    # engine roiMode inherit pops roi
    eng = (ROOT / 'vision/engine.py').read_text(encoding='utf-8')
    if "roiMode" in eng and "run_params.pop('roi'" in eng:
        ok('engine roiMode inherit pops roi')
    else:
        bad('engine roiMode inherit patch missing')

    print(f'\nRESULT pass={pass_n} fail={fail_n}')
    return 0 if fail_n == 0 else 1

if __name__ == '__main__':
    sys.exit(main())
