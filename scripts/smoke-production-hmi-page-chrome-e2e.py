#!/usr/bin/env python3
"""production_task ↔ operator HMI page-level recipe/status chrome binding — no robot SDK."""
from __future__ import annotations
import ast
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / '.pydeps'))
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('SIEANS_SMOKE', '1')

pass_n = fail_n = 0

def ok(m):
    global pass_n; pass_n += 1; print('PASS:', m)

def bad(m):
    global fail_n; fail_n += 1; print('FAIL:', m)

def main():
    for rel in (
        'desktop/production_task_panel.py',
        'desktop/operator_hmi.py',
        'lib/flow-control.cjs',
    ):
        src = (ROOT / rel).read_text(encoding='utf-8')
        if rel.endswith('.py'):
            ast.parse(src)
        ok(f'ast/parse {rel}')

    prod = (ROOT / 'desktop/production_task_panel.py').read_text(encoding='utf-8')
    for needle in (
        'productionTaskPageChrome', 'productionTaskPageChromeMeta',
        'productionTaskPageChromeBindBtn', '_soft_bind_hmi_page_chrome',
        '_page_chrome_snapshot', 'hmiPageChromeBanner', 'apply_production_page_chrome',
    ):
        (ok if needle in prod else bad)(
            f'panel has {needle}' if needle in prod else f'missing {needle}'
        )

    hmi = (ROOT / 'desktop/operator_hmi.py').read_text(encoding='utf-8')
    for needle in (
        'hmiPageChromeBanner', 'apply_production_page_chrome',
        'hmiOkNgDashboardStrip', 'refresh_okng_dashboard_strip',
    ):
        (ok if needle in hmi else bad)(
            f'hmi has {needle}' if needle in hmi else f'missing {needle}'
        )

    fc = (ROOT / 'lib/flow-control.cjs').read_text(encoding='utf-8')
    for needle in ('hmiPageChrome', 'hmiPageChromeBanner', '页铬'):
        (ok if needle in fc else bad)(
            f'flow-control has {needle}' if needle in fc else f'missing {needle}'
        )

    js = r'''
const control = require('./lib/flow-control.cjs');
const ctx = {global:{}, flow:{}, module:{}};
const r = control.productionTask({
  taskName: '对位贴合任务1',
  recipe: '配方A',
  statusVar: 'taskStatus',
  scope: 'global',
  autoStart: false,
  chain: [
    {step:'读取图像', op:'图像源'},
    {step:'模板匹配', op:'locate'},
    {step:'发送上位机', op:'send_data / format_data'},
  ],
}, ctx);
if (!r.hmiPageChrome) throw new Error('no hmiPageChrome');
if (r.hmiPageChrome.recipe !== '配方A') throw new Error('recipe '+JSON.stringify(r.hmiPageChrome));
if (!String(r.hmiPageChrome.banner||'').includes('页铬')) throw new Error('banner '+r.hmiPageChrome.banner);
if (ctx.global.hmiPageChromeBanner !== r.hmiPageChrome.banner) throw new Error('bag banner');
if (!r.writeback.hmiPageChromeBanner) throw new Error('writeback banner');
console.log('ENGINE_OK', r.hmiPageChrome.banner);
'''
    r = subprocess.run(['node', '-e', js], cwd=str(ROOT), capture_output=True, text=True)
    if r.returncode == 0 and 'ENGINE_OK' in r.stdout:
        ok(f'engine productionTask page chrome · {r.stdout.strip()}')
    else:
        bad(f'engine failed rc={r.returncode} out={r.stdout!r} err={r.stderr!r}')

    from PySide6.QtWidgets import QApplication, QPlainTextEdit, QLabel, QPushButton
    app = QApplication.instance() or QApplication([])
    from desktop.production_task_panel import ProductionTaskPanel
    from desktop.operator_hmi import OperatorHmiView

    step = {
        'id': 'pt1', 'operation': 'production_task', 'name': '生产任务',
        'params': {
            'taskName': '对位贴合任务1',
            'recipe': '配方A',
            'statusVar': 'taskStatus',
            'scope': 'global',
            'autoStart': False,
            'note': '',
            'chain': [
                {'step': '读取图像', 'op': '图像源', 'vars': ''},
                {'step': '模板匹配', 'op': 'locate', 'vars': ''},
                {'step': '发送上位机', 'op': 'send_data / format_data', 'vars': 'MoveX,MoveY'},
            ],
        },
    }
    project = {'steps': [step], 'edges': [], 'variables': {}}
    panel = ProductionTaskPanel(step, {}, project)
    ok('ProductionTaskPanel constructed')

    assert isinstance(panel._prod_page_chrome, QPlainTextEdit)
    assert panel._prod_page_chrome.objectName() == 'productionTaskPageChrome'
    snap = panel._soft_bind_hmi_page_chrome(trial=False, push_live=False)
    assert snap['recipe'] == '配方A'
    assert '页铬' in snap['banner']
    assert 'taskStatus' in snap['banner']
    txt = panel._prod_page_chrome.toPlainText()
    assert 'banner' in txt and '配方A' in txt and 'targets' in txt, txt
    ok(f'page chrome preview · {txt.splitlines()[0]}')
    assert project.get('hmiPageChrome', {}).get('recipe') == '配方A'
    ok('project.hmiPageChrome persisted')

    assert panel.findChild(QPushButton, 'productionTaskPageChromeBindBtn') is not None
    ok('page chrome bind button wired')

    view = OperatorHmiView()
    assert view.findChild(QLabel, 'hmiPageChromeBanner') is not None
    applied = view.apply_production_page_chrome(snap)
    banner = view._page_chrome_banner.text()
    assert '配方A' in banner and '页铬' in banner, banner
    ok(f'HMI page chrome banner · {banner}')
    assert getattr(view, '_live_recipe', '') == '配方A'
    ok('HMI recipe badge synced via page chrome')

    panel._set('recipe', '配方B')
    snap2 = panel._page_chrome_snapshot()
    assert snap2['recipe'] == '配方B'
    view.apply_production_page_chrome(snap2)
    assert '配方B' in view._page_chrome_banner.text()
    ok('live page chrome rebind on recipe change')

    print(f'\n=== {pass_n} passed, {fail_n} failed ===')
    return 0 if fail_n == 0 else 1

if __name__ == '__main__':
    rc = main()
    # Qt offscreen teardown can SIGSEGV after green asserts
    import os as _os
    _os._exit(rc)
