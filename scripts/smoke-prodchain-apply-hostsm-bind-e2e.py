#!/usr/bin/env python3
"""CONTINUE after open-and-use: production_task apply-chain polish + Host SM 开始绑流程.

1) chain_to_operations prefers var_calc for 物理坐标
2) seed_chain_step_params covers locate/pose/geometry/display/physical
3) apply_production_chain (+trial) + LocalLoop ensure
4) Host SM set_bound_flow chip + start logs 执行·连续
No robot SDK / no Halcon / no push.
"""
from __future__ import annotations
import os, sys, subprocess
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); os.chdir(ROOT)
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

fails = []
def ok(n, c, d=''):
    if c: print(f'PASS  {n}')
    else: fails.append(n); print(f'FAIL  {n}  {d}')

def main():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)

    from desktop.production_task_panel import (
        DEFAULT_CHAIN, chain_to_operations, seed_chain_step_params, ProductionTaskPanel,
    )
    from desktop.host_state_machine import HostStateMachineWidget
    from desktop.catalog import all_definitions
    from desktop.model import Document

    ops = chain_to_operations(DEFAULT_CHAIN)
    ok('ops non-empty', len(ops) >= 8, str(len(ops)))
    kinds = [o['operation'] for o in ops]
    ok('has locate', 'locate' in kinds)
    ok('has geometry', 'geometry' in kinds)
    ok('has format+send', 'format_data' in kinds and 'send_data' in kinds)
    phys = [o for o in ops if '物理' in o.get('name', '')]
    ok('physical → var_calc', bool(phys) and all(o['operation'] == 'var_calc' for o in phys), str(phys))
    ok('no nine_point in default demo', 'nine_point' not in kinds, str(kinds))

    loc = seed_chain_step_params('locate', '模板匹配', '')
    ok('seed locate', isinstance(loc, dict) and loc.get('showMatchBox') is True, str(loc)[:120])
    geo = seed_chain_step_params('geometry', '圆/特征查找', 'target_X, target_Y')
    ok('seed geometry circles', bool(geo) and geo.get('feature') == 'circles' and geo.get('caliperCount') == 12, str(geo)[:120])
    pose = seed_chain_step_params('pose_correct', '位置修正', '')
    ok('seed pose auto', bool(pose) and pose.get('fixtureSource') == 'auto', str(pose)[:120])
    disp = seed_chain_step_params('display', '结果显示', '')
    ok('seed display', bool(disp) and disp.get('showOverlay') is True, str(disp)[:120])
    start_m = seed_chain_step_params('var_calc', '基准→物理坐标', 'start_X_M, start_Y_M')
    exprs = {e['name']: e['expression'] for e in (start_m or {}).get('expressions') or []}
    ok('seed start_X_M locate_x', exprs.get('start_X_M') == 'locate_x * 0.1', str(exprs))
    tgt = seed_chain_step_params('var_calc', '目标→物理坐标', 'target_X_M, target_Y_M')
    exprs2 = {e['name']: e['expression'] for e in (tgt or {}).get('expressions') or []}
    ok('seed target_X_M geometry_x', exprs2.get('target_X_M') == 'geometry_x * 0.1', str(exprs2))

    panel = ProductionTaskPanel({'id': 't1', 'operation': 'production_task', 'params': {}}, {}, {})
    ok('panel applyFlow', hasattr(panel, 'applyFlow'))
    ok('panel applyFlowAndRun', hasattr(panel, 'applyFlowAndRun'))
    got = []
    panel.applyFlowAndRun.connect(lambda o: got.extend(o))
    panel._apply_chain_and_run()
    ok('trial emits ops', len(got) >= 8, str(len(got)))

    sm = HostStateMachineWidget(compact=True)
    ok('flow bind chip', hasattr(sm, '_flow_bind_chip'))
    ok('set_bound_flow', callable(getattr(sm, 'set_bound_flow', None)))
    sm.set_bound_flow('Demo方案', steps=5, path='/tmp/demo.sieans', reason='smoke')
    ok('bound name', sm.bound_flow_name == 'Demo方案', sm.bound_flow_name)
    chip_txt = sm._flow_bind_chip.text()
    ok('chip shows bind', '已绑' in chip_txt and 'Demo方案' in chip_txt, chip_txt)

    cmds = []
    sm.triggerCommands.connect(lambda c: cmds.extend(c))
    sm._auto_start('正常生产')
    ok('start → Running', sm.state == 'Running', sm.state)
    ok('start emits 执行·连续', any(c.get('type') == '执行·连续' for c in cmds), str(cmds))
    log_txt = sm._log.toPlainText()
    ok('start logs 绑流程', '开始绑流程' in log_txt and 'Demo方案' in log_txt, log_txt[-240:])

    src = open('desktop/mainwindow.py', encoding='utf-8').read()
    ok('mw apply trial_run', 'trial_run' in src and 'apply_production_chain_and_run' in src)
    ok('mw _sync_host_sm_bound_flow', '_sync_host_sm_bound_flow' in src)
    chunk = src.split('def apply_production_chain')[1].split('def apply_production_chain_and_run')[0]
    ok('mw ensure LocalLoop on apply', 'ensure_comm_manager' in chunk)

    src_pf = open('desktop/property_float.py', encoding='utf-8').read()
    ok('pf AndRun signal', 'applyProductionChainAndRun' in src_pf)

    src_hmi = open('desktop/operator_hmi.py', encoding='utf-8').read()
    ok('hmi set_bound_flow', 'def set_bound_flow' in src_hmi)

    src_fc = open('lib/flow-control.cjs', encoding='utf-8').read()
    ok('varCalc zero-fill locate_x', "env[k]===undefined" in src_fc and "'locate_x'" in src_fc)

    defs = all_definitions([])
    doc = Document()
    parent = 'source'
    added = []
    for item in ops:
        key = item['operation']
        if key not in defs:
            continue
        nid = doc.add(defs[key], parent=parent)
        proj = __import__('copy').deepcopy(doc.project)
        for s in proj['steps']:
            if s['id'] == nid:
                s['name'] = item['name']
                seeded = seed_chain_step_params(
                    key, item['name'], item.get('vars') or '',
                    project=proj, existing=s.get('params') or {},
                )
                if seeded:
                    s['params'] = seeded
                break
        doc.commit(proj)
        added.append(nid)
        parent = nid
    ok('doc apply nodes', len(added) >= 8, str(len(added)))
    by_id = {s['id']: s for s in doc.project['steps']}
    linked = sum(1 for nid in added if by_id[nid].get('imageFrom'))
    ok('imageFrom mostly linked', linked >= len(added) - 1, f'{linked}/{len(added)}')

    src_loc = open('desktop/locate_match_panel.py', encoding='utf-8').read()
    ok('locate showMatchIndex', 'showMatchIndex' in src_loc)
    src_geo = open('desktop/geometry_find_panel.py', encoding='utf-8').read()
    ok('geometry caliper hint', 'geometryCaliperHint' in src_geo)

    js = (
        "const fc=require('./lib/flow-control.cjs');"
        "const ctx={global:{},flow:{},module:{},results:{},steps:[]};"
        "const r=fc.varCalc({scope:'flow',expressions:["
        "{name:'start_X_M',expression:'locate_x * 0.1',initial:0,outType:'number',initOnRun:true},"
        "{name:'target_X_M',expression:'geometry_x * 0.1',initial:0,outType:'number',initOnRun:true},"
        "{name:'dx',expression:'target_X_M - start_X_M',initial:0,outType:'number'}"
        "]},ctx);"
        "if(r.status!=='ok'){console.error(r);process.exit(1);}"
        "if(ctx.flow.start_X_M!==0||ctx.flow.dx!==0){console.error(ctx.flow);process.exit(1);}"
        "console.log('PASS varCalc zero-fill demo');"
    )
    r = subprocess.run(['node', '-e', js], cwd=str(ROOT), capture_output=True, text=True)
    ok('js varCalc zero-fill', r.returncode == 0, (r.stdout + r.stderr)[-300:])

    if fails:
        print(f'\n{len(fails)} FAIL')
        return 1
    print('\nALL PASS')
    return 0

if __name__ == '__main__':
    sys.exit(main() or 0)
