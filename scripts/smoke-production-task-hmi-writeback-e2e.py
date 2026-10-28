#!/usr/bin/env python3
"""production_task HMI recipe/statusVar write-back + trial-run result strip — no robot SDK."""
from __future__ import annotations
import ast
import json
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
    for rel in ('desktop/production_task_panel.py', 'lib/flow-control.cjs'):
        src = (ROOT / rel).read_text(encoding='utf-8')
        if rel.endswith('.py'):
            ast.parse(src)
        ok(f'ast/parse {rel}')

    prod = (ROOT / 'desktop/production_task_panel.py').read_text(encoding='utf-8')
    for needle in (
        'productionTaskWritebackPreview', 'productionTaskHmiStrip', 'productionTaskTrialStrip',
        'productionTaskResultMeta', 'productionTaskWritebackBtn', 'productionTaskHmiPushBtn',
        '_soft_writeback_status_vars', '_soft_push_hmi_recipe', '_record_trial_strip',
        '_refresh_production_result', 'hmiRecipe',
    ):
        (ok if needle in prod else bad)(f'panel has {needle}' if needle in prod else f'missing {needle}')

    fc = (ROOT / 'lib/flow-control.cjs').read_text(encoding='utf-8')
    for needle in ('hmiRecipe', 'hmiStrip', 'writeback', 'hmiTaskStatus'):
        (ok if needle in fc else bad)(f'flow-control has {needle}' if needle in fc else f'missing {needle}')

    # Engine productionTask writeback
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
if (r.status !== 'ready') throw new Error('status '+r.status);
if (r.hmiRecipe !== '配方A') throw new Error('hmiRecipe '+r.hmiRecipe);
if (!r.hmiStrip || !r.hmiStrip.includes('配方')) throw new Error('hmiStrip '+r.hmiStrip);
if (!r.writeback || r.writeback.taskStatus !== 'ready') throw new Error('writeback '+JSON.stringify(r.writeback));
if (ctx.global.taskStatus !== 'ready') throw new Error('bag status');
if (ctx.global.taskStatus_recipe !== '配方A') throw new Error('bag recipe');
if (ctx.global.hmiRecipe !== '配方A') throw new Error('bag hmiRecipe');
if (ctx.global.hmiTaskStatus !== 'ready') throw new Error('bag hmiTaskStatus');
console.log('ENGINE_OK', r.chainSteps, r.hmiStrip);
'''
    r = subprocess.run(['node', '-e', js], cwd=str(ROOT), capture_output=True, text=True)
    if r.returncode == 0 and 'ENGINE_OK' in r.stdout:
        ok(f'engine productionTask HMI writeback · {r.stdout.strip()}')
    else:
        bad(f'engine failed rc={r.returncode} out={r.stdout!r} err={r.stderr!r}')

    from PySide6.QtWidgets import QApplication, QPlainTextEdit, QLabel, QPushButton
    app = QApplication.instance() or QApplication([])
    from desktop.production_task_panel import ProductionTaskPanel, OCR_GATE_COMM_CHAIN, chain_to_operations

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
    assert isinstance(panel._prod_writeback, QPlainTextEdit)
    assert panel._prod_writeback.objectName() == 'productionTaskWritebackPreview'
    wb = panel._prod_writeback.toPlainText()
    assert 'global.taskStatus' in wb and 'ready' in wb, wb
    assert 'taskStatus_recipe' in wb and '配方A' in wb, wb
    assert 'hmiRecipe' in wb, wb
    ok(f'writeback preview · {wb.replace(chr(10), " | ")}')

    assert isinstance(panel._prod_hmi_strip, QLabel)
    strip = panel._prod_hmi_strip.text()
    assert '配方 · 配方A' in strip and 'ready' in strip and '链' in strip, strip
    ok(f'HMI strip · {strip}')

    assert isinstance(panel._prod_trial_strip, QPlainTextEdit)
    assert '尚无试跑' in panel._prod_trial_strip.toPlainText() or panel._prod_trial_strip.toPlainText()
    ok('trial strip placeholder')

    mapping = panel._soft_writeback_status_vars(trial=False)
    assert mapping['global.taskStatus'] == 'ready'
    assert project['variables']['global']['taskStatus'] == 'ready'
    assert project['variables']['global']['hmiRecipe'] == '配方A'
    assert project.get('activeRecipeName') == '配方A'
    ok('soft writeback into project.variables')

    ops = chain_to_operations(OCR_GATE_COMM_CHAIN)
    panel._record_trial_strip('OCR链并试跑', ops)
    trial = panel._prod_trial_strip.toPlainText()
    assert 'OCR链并试跑' in trial and 'status=ready' in trial, trial
    ok(f'trial strip recorded · {trial.splitlines()[-1][:80]}')

    panel._set('recipe', '配方B')
    assert '配方B' in panel._prod_hmi_strip.text()
    assert '配方B' in panel._prod_writeback.toPlainText()
    ok('live refresh on recipe change')

    meta = panel._prod_result_meta.text()
    assert 'statusVar=taskStatus' in meta and 'writebackKeys=' in meta, meta
    ok(f'result meta · {meta}')

    # objectName hooks
    assert panel.findChild(QPushButton, 'productionTaskWritebackBtn') is not None
    assert panel.findChild(QPushButton, 'productionTaskHmiPushBtn') is not None
    ok('writeback/HMI push buttons wired')

    print(f'\n=== {pass_n} passed, {fail_n} failed ===')
    return 0 if fail_n == 0 else 1

if __name__ == '__main__':
    sys.exit(main())
