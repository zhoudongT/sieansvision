#!/usr/bin/env python3
"""wave148: docs/menu catalog parity + triggers/vars denser chrome — soft closeout."""
from __future__ import annotations
import os, sys, ast, re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / '.pydeps'))
os.chdir(ROOT)
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

fails, passes = [], []


def ok(n, c, d=''):
    if c:
        passes.append(n)
        print(f'PASS  {n}')
    else:
        fails.append(n)
        print(f'FAIL  {n}  {d}')


def main():
    from desktop.open_and_run_catalog import (
        OPEN_AND_RUN_ENTRIES, TEMPLATE_EXTRAS, EXAMPLE_EXTRAS,
        new_from_template_entries, open_example_rels, expected_sample_files,
    )

    entries = OPEN_AND_RUN_ENTRIES
    ok('catalog ≥24 open-and-run', len(entries) >= 24, len(entries))
    must = [
        'open-and-run-match-locate-chrome.sieans',
        'open-and-run-geom-script.sieans',
        'open-and-run-fixture-preprocess.sieans',
        'open-and-run-ocr-defect-chrome.sieans',
        'open-and-run-ninepoint.sieans',
        'open-and-run-barcode.sieans',
        'open-and-run-measure-caliper-chrome.sieans',
        'open-and-run-contour-color.sieans',
        'open-and-run-fixture-pose-chain.sieans',
        'open-and-run-geom-find-match.sieans',
        'open-and-run-format-protocol.sieans',
        'open-and-run-format-protocol-demo.sieans',
        'open-and-run-demo.sieans',
        'open-and-run-script.sieans',
        'open-and-run-group-comm.sieans',
        'open-and-run-comm-multiproto.sieans',
        'default-platform.sieans',
    ]
    rels = {rel for _, rel in entries}
    for m in must:
        hit = any(m in r for r in rels)
        ok(f'catalog has {m}', hit)

    missing_files = []
    for rel in expected_sample_files():
        if not (ROOT / rel).is_file():
            missing_files.append(rel)
        else:
            ok(f'file {Path(rel).name}', True)
    ok('all catalog files exist', not missing_files, missing_files)

    tpl = new_from_template_entries()
    ex = open_example_rels()
    ok('template menu uses catalog', any('ocr-defect-chrome' in r for _, r in tpl))
    ok('template has demo', any('open-and-run-demo' in r for _, r in tpl))
    ok('template has script', any('open-and-run-script' in r for _, r in tpl))
    ok('template has format-protocol', any('format-protocol.sieans' in r for _, r in tpl))
    ok('example has match-locate', any('match-locate-chrome' in r for r in ex))
    ok('example has ocr-defect', any('ocr-defect-chrome' in r for r in ex))
    ok('example has geom-script', any('geom-script' in r for r in ex))
    ok('example has format-protocol-demo', any('format-protocol-demo' in r for r in ex))
    ok('example extras has mv-camera', any('mv-camera-ocr' in r for r in ex))
    ok('template extras blank', any('blank-inspection' in r for _, r in TEMPLATE_EXTRAS))

    mw = (ROOT / 'desktop/mainwindow.py').read_text(encoding='utf-8')
    ok('mainwindow imports catalog', 'open_and_run_catalog' in mw)
    ok('mainwindow new_from_template_entries', 'new_from_template_entries' in mw)
    ok('mainwindow open_example_rels', 'open_example_rels' in mw)
    # stale hardcoded open-example list must be gone
    ok('no stale hardcoded open-example list',
       "for rel in (\n            'projects/default-platform.sieans'" not in mw)
    ast.parse(mw); ok('mainwindow AST', True)

    docs = (ROOT / 'docs/open-and-run-samples.md').read_text(encoding='utf-8')
    ok('docs wave148', 'wave148' in docs)
    ok('docs mentions catalog', 'open_and_run_catalog' in docs)
    ok('docs OCR/defect', 'ocr-defect-chrome' in docs)
    ok('docs ninepoint', 'ninepoint' in docs)
    ok('docs format-protocol', 'format-protocol' in docs)
    ok('docs 变N/触N', '变N' in docs and '触N' in docs)

    readme = (ROOT / 'projects/README-open-and-run.md').read_text(encoding='utf-8')
    ok('README wave148', 'wave148' in readme)
    for name in ('match-locate-chrome', 'ocr-defect-chrome', 'format-protocol',
                 'geom-script', 'fixture-pose-chain', 'ninepoint', 'barcode'):
        ok(f'README lists {name}', name in readme)

    # --- triggers denser chrome ---
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)

    from desktop.model import Document
    from desktop.global_triggers import GlobalTriggersDialog, ensure_triggers

    class _Doc:
        def __init__(self):
            self.project = {
                'globalTriggers': {
                    'events': [],
                    'strings': [
                        {'pattern': 'RUN', 'commandType': '执行·单次', 'config': ''},
                        {'pattern': 'STOP', 'commandType': '执行·停止', 'config': ''},
                    ],
                }
            }
        def commit(self, p):
            self.project = p

    dlg = GlobalTriggersDialog(_Doc(), parent=None, execute_commands=None)
    ok('triggers has result_badge', hasattr(dlg, 'result_badge'))
    ok('triggers has hit_table', hasattr(dlg, 'hit_table'))
    ok('hit_table 4 cols', dlg.hit_table.columnCount() == 4, dlg.hit_table.columnCount())
    dlg.test_input.setText('hello RUN world')
    dlg._test_match()
    badge = dlg.result_badge.text()
    ok('badge 触N on hit', badge.startswith('触') and '0' not in badge[:3], badge)
    ok('hit_table rows ≥1', dlg.hit_table.rowCount() >= 1, dlg.hit_table.rowCount())
    chrome = dlg.result_chrome.text()
    ok('chrome mentions 命中', '命中' in chrome, chrome)

    dlg.test_input.setText('NOMATCH')
    dlg._test_match()
    ok('badge 触0✗ on miss', dlg.result_badge.text() == '触0✗', dlg.result_badge.text())

    # --- variables denser badge ---
    from desktop.variables_dialog import VariablesDialog
    # VariablesDialog needs more deps; smoke the refresh helper via a light stub if possible.
    # Instead: source-level + optional import of method body markers.
    vd = (ROOT / 'desktop/variables_dialog.py').read_text(encoding='utf-8')
    ok('vars result_badge', 'varsResultBadge' in vd and 'result_badge' in vd)
    ok('vars 变N badge text', "变{n}✓" in vd or '变{n}✓' in vd or "f'变{n}✓'" in vd)
    ok('vars AST', True)
    ast.parse(vd)
    ast.parse((ROOT / 'desktop/global_triggers.py').read_text(encoding='utf-8'))
    ok('triggers AST', True)

    # soft parity: catalog count matches README claim ballpark
    open_n = len([r for r in expected_sample_files() if 'open-and-run' in r or 'default-platform' in r])
    ok(f'open sample count {open_n}≥20', open_n >= 20, open_n)

    print(f'\n{len(passes)} PASS / {len(fails)} FAIL')
    if fails:
        print('FAILED:', ', '.join(fails))
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
