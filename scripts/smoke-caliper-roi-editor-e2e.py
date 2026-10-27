#!/usr/bin/env python3
"""多卡尺 ROI 编辑器：canvas ROI + caliper preview → params patch."""
from __future__ import annotations
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
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from desktop.caliper_roi_editor import CaliperRoiEditorDialog, _search_vectors
    scan, cross = _search_vectors('left_right', 0)
    assert abs(scan[0] - 1) < 1e-6 and abs(cross[1] - 1) < 1e-6
    ok('search vectors L→R')

    sample = ROOT / 'public/vision/samples/caliper-line.png'
    params = {'caliperCount': 8, 'caliperWidth': 12, 'caliperLength': 50,
              'roi': [40, 40, 200, 120], 'searchDir': 'left_right'}
    dlg = CaliperRoiEditorDialog(params, sample_fallback=str(sample) if sample.is_file() else None)
    assert dlg.roi_item is not None
    assert len(dlg._caliper_items) >= 8  # poly+line per probe at least
    ok(f'editor probes drawn n_items={len(dlg._caliper_items)}')
    dlg.sp_count.setValue(12)
    assert len(dlg._caliper_items) >= 12
    ok('count spin redraws')
    patch = dlg.result_params()
    assert patch['roiPreset'] == 'draw' and patch['caliperCount'] == 12
    assert len(patch['roi']) == 4
    ok(f'result_params roi={patch["roi"]} count={patch["caliperCount"]}')

    gp = (ROOT / 'desktop/geometry_find_panel.py').read_text(encoding='utf-8')
    if 'caliperRoiEditorBtn' in gp and '_open_caliper_roi_editor' in gp:
        ok('geometry panel button wired')
    else:
        bad('geometry panel missing editor button')

    print(f"\n{'FAIL' if fail_n else 'PASS'} {pass_n} ok / {fail_n} fail")
    return 1 if fail_n else 0

if __name__ == '__main__':
    raise SystemExit(main())
