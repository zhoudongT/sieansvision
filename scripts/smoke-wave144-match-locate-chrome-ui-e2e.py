#!/usr/bin/env python3
"""wave144 UI: match/locate denser score + candidate result chrome."""
from __future__ import annotations
import os, sys, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / '.pydeps'))
os.chdir(ROOT)
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

fails = []
passes = []


def ok(n, c, d=''):
    if c:
        passes.append(n)
        print(f'PASS  {n}')
    else:
        fails.append(n)
        print(f'FAIL  {n}  {d}')


def main():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)

    from desktop.match_locate_chrome import (
        chrome_badge, score_margin, soft_demo_match_result, soft_demo_matches,
        summarize_match_locate, build_candidate_rows, format_row_cells,
        CANDIDATE_COLUMNS, build_match_overlays, overlay_flags,
        chrome_map_from_film_cache, okng_map_from_film_cache,
        strip_summary_from_film_cache, extract_match_candidates,
    )
    ok('badge 配3✓', chrome_badge(True, 'OK', count=3) == '配3✓')
    ok('badge 配2✗', chrome_badge(False, 'NG', count=2) == '配2✗')
    ok('badge 配·', chrome_badge(None, '', count=None) == '配·')
    ok('CANDIDATE_COLUMNS 10', len(CANDIDATE_COLUMNS) == 10, CANDIDATE_COLUMNS)
    ok('cols has 分数/判定/Δmin', '分数' in CANDIDATE_COLUMNS and '判定' in CANDIDATE_COLUMNS and 'Δmin' in CANDIDATE_COLUMNS)

    sm = score_margin(0.82, 0.55, 1.0)
    ok('score_margin inBand', bool(sm.get('inBand')), sm)
    ok('score_margin deltaLow~0.27', abs(float(sm.get('deltaLow') or 0) - 0.27) < 1e-6, sm)

    demo = soft_demo_match_result(n=5, ok=True)
    cands = extract_match_candidates(demo)
    ok('soft demo 5 candidates', len(cands) == 5, len(cands))
    params = {
        'minScore': 0.55, 'judgeMin': 0.55, 'judgeMax': 1.0,
        'maxMatches': 8, 'showMatchBox': True, 'showScore': True,
        'showCross': True, 'showRank': True, 'showMargin': True,
    }
    summ = summarize_match_locate(demo, params=params)
    ok('chrome 配5✓', summ.get('chrome') == '配5✓', summ.get('chrome'))
    ok('rows 5', len(summ.get('rows') or []) == 5)
    ok('judgeOk True', summ.get('judgeOk') is True, summ.get('judgeOk'))
    cells = format_row_cells((summ.get('rows') or [{}])[0])
    ok('format_row_cells 10', len(cells) == 10, cells)
    ok('top score OK', cells[-1] == 'OK' and float(cells[2]) > 0.9, cells)

    demo_ng = soft_demo_match_result(n=3, ok=False)
    summ_ng = summarize_match_locate(demo_ng, params=params)
    ok('chrome NG has ✗', '✗' in str(summ_ng.get('chrome') or ''), summ_ng.get('chrome'))
    ok('ng rows 3', len(summ_ng.get('rows') or []) == 3)

    rows = build_candidate_rows(soft_demo_matches(4, ok=True), params=params)
    ok('build_candidate_rows 4', len(rows) == 4)

    ov = build_match_overlays(demo, params)
    kinds = {o.get('type') for o in ov}
    ok('overlays denser', len(ov) >= 5, len(ov))
    ok('overlay kinds rect/cross/label', 'rect' in kinds and ('cross' in kinds or 'label' in kinds), kinds)
    flags = overlay_flags(params)
    ok('overlay_flags non-empty', len(flags) >= 2, flags)

    # film cache maps — path → {results: [rec...]}
    steps = [{'id': 's1', 'operation': 'locate', 'name': '多候选匹配·铬',
              'params': params}]
    cache = {
        '/tmp/a.png': {'results': [{'id': 's1', 'operation': 'locate', 'name': '多候选', 'result': demo}]},
        '/tmp/b.png': {'results': [{'id': 's1', 'operation': 'locate', 'name': '多候选', 'result': demo_ng}]},
    }
    cmap = chrome_map_from_film_cache(cache, project_steps=steps)
    omap = okng_map_from_film_cache(cache, project_steps=steps)
    ok('chrome_map paths', '/tmp/a.png' in cmap and '/tmp/b.png' in cmap, cmap)
    ok('chrome_map 配✓', '✓' in str(cmap.get('/tmp/a.png') or ''), cmap)
    ok('okng_map OK/NG', omap.get('/tmp/a.png') == 'OK' and omap.get('/tmp/b.png') == 'NG', omap)
    strip = strip_summary_from_film_cache(cache, current_path='/tmp/a.png', project_steps=steps)
    ok('strip_summary non-empty', bool(strip) and ('配' in strip or '匹配' in strip), strip)

    # STOP: no cascade markers
    src = (ROOT / 'desktop/match_locate_chrome.py').read_text(encoding='utf-8')
    forbidden = ['hostWatch', 'sparkSeek', 'blinkChip', 'commBind', 'recipeBind']
    ok('no Comm/HMI/spark cascade markers', not any(k in src for k in forbidden))

    # panel denser chrome
    from desktop.locate_match_panel import LocateMatchPanel
    step = {'id': 's1', 'operation': 'locate', 'name': '多候选匹配·铬', 'params': dict(params)}
    panel = LocateMatchPanel(step, {'id': 'locate'}, {'steps': [step]})
    ok('panel has density table', hasattr(panel, '_match_density_table'))
    ok('panel has chrome badge', hasattr(panel, '_match_chrome_badge'))
    if hasattr(panel, '_soft_demo_match_density'):
        panel._soft_demo_match_density()
        badge_txt = panel._match_chrome_badge.text() if panel._match_chrome_badge else ''
        ok('panel soft demo badge 配', '配' in badge_txt, badge_txt)
        nrows = panel._match_density_table.rowCount() if panel._match_density_table else 0
        ok('panel soft demo rows>=3', nrows >= 3, nrows)
        ncols = panel._match_density_table.columnCount() if panel._match_density_table else 0
        ok('panel table 10 cols', ncols == 10, ncols)
    else:
        ok('panel soft demo method', False, 'missing _soft_demo_match_density')

    # filmstrip match chrome API
    from desktop.widgets.filmstrip import FilmstripBar
    fs = FilmstripBar()
    ok('filmstrip match_strip', hasattr(fs, 'match_strip'))
    ok('filmstrip set_frame_match_chrome', hasattr(fs, 'set_frame_match_chrome'))
    ok('filmstrip push_match_summary', hasattr(fs, 'push_match_summary'))
    fs.set_frame_match_chrome({'/tmp/a.png': '配5✓'}, {'/tmp/a.png': 'OK'})
    bag = getattr(fs, '_frame_match_chrome', {}) or {}
    ok('filmstrip chrome bag', bag.get('/tmp/a.png') == '配5✓', bag)
    fs.push_match_summary('匹配定位 · 多候选匹配·铬 配5✓')
    strip_lab = fs.match_strip.text() if getattr(fs, 'match_strip', None) else ''
    ok('filmstrip strip visible text', '配' in strip_lab or '匹配' in strip_lab, strip_lab)

    # overlay density prefers denser
    from desktop.display_overlay_density import build_unified_overlays
    project = {'steps': [{'id': 's1', 'operation': 'locate', 'params': params}]}
    rec = {'id': 's1', 'operation': 'locate', 'result': demo}
    specs = build_unified_overlays([rec], project=project, max_specs=40, max_per_module=20)
    sk = {s.get('type') for s in specs}
    ok('unified overlays for locate', len(specs) >= 3, (len(specs), sk))

    # project
    proj_path = ROOT / 'projects/open-and-run-match-locate-chrome.sieans'
    ok('project exists', proj_path.is_file())
    if proj_path.is_file():
        proj = json.loads(proj_path.read_text(encoding='utf-8'))
        ops = [s.get('operation') for s in proj.get('steps') or []]
        ok('project locate→var_calc', ops and ops[0] == 'locate' and 'var_calc' in ops, ops)
        loc = next(s for s in proj['steps'] if s['operation'] == 'locate')
        ok('project maxMatches>=5', int((loc.get('params') or {}).get('maxMatches') or 0) >= 5)
        ok('project name 匹配定位', '匹配定位' in str(proj.get('name') or ''))

    # mainwindow symbols (import-light check)
    mw_src = (ROOT / 'desktop/mainwindow.py').read_text(encoding='utf-8')
    ok('mw _sync_filmstrip_match_chrome', '_sync_filmstrip_match_chrome' in mw_src)
    ok('mw menu sample', 'open-and-run-match-locate-chrome.sieans' in mw_src)

    print(f'\nwave144 UI {len(passes)}/{len(passes)+len(fails)}')
    return 0 if not fails else 1


if __name__ == '__main__':
    sys.exit(main())
