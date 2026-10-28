#!/usr/bin/env python3
"""Headless E2E (CONTINUE wave):
1) CommManager 收发 ↔ 流程变量：expand ${}/resolve_send_event_payload / 试发 writeback
2) N4 红叹号扫盲：uncovered ops + reason tips
3) 胶片/图像源：imageFormatFilter DEFAULT + form combo
4) 上位机运行壳模板：pause/continue/alarm commands
Exit 0 on PASS. No robot SDK / real TCP / push.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtWidgets import QApplication

fails = []


def ok(name, cond, detail=''):
    if cond:
        print(f'PASS  {name}')
    else:
        fails.append(name)
        print(f'FAIL  {name}  {detail}')


def main():
    app = QApplication.instance() or QApplication(sys.argv)

    from desktop.comm_manager import (
        expand_payload_placeholders, resolve_send_event_payload,
        write_project_variable, read_project_variable, ensure_comm_manager,
    )
    from desktop.config_status import (
        step_incomplete, step_incomplete_reason, source_incomplete_reason,
        node_incomplete_reason, project_incomplete_summary,
    )
    from desktop.image_source import DEFAULT_SOURCE, normalize_source, ImageSourceForm
    from desktop.run_ui_designer import default_host_run_ui
    from desktop.catalog import all_definitions
    from desktop.model import Document
    
    # ----- Comm var resolve -----
    p = {'variables': {'payload': 'HELLO', 'score': '0.91'}, 'globalVariables': {}}
    ok('expand ${score}', expand_payload_placeholders(p, 'x=${score}') == 'x=0.91')
    ok('expand unknown kept', '${missing}' in expand_payload_placeholders(p, 'a=${missing}'))
    pay, src = resolve_send_event_payload(p, {'variable': 'flow.payload', 'message': 'fallback'})
    ok('resolve prefers variable', pay == 'HELLO' and src == 'variable', (pay, src))
    pay2, src2 = resolve_send_event_payload(p, {'message': 'hi ${score}'})
    ok('resolve expands message', pay2 == 'hi 0.91' and src2 == 'message', (pay2, src2))
    pay3, src3 = resolve_send_event_payload(p, {})
    ok('resolve empty', pay3 == '' and src3 == 'empty')

    # JS mirror
    import subprocess, json
    js = subprocess.check_output([
        'node', '-e',
        "const b=require('./lib/comm-bus.cjs');"
        "const v={flow:{score:'0.91',payload:'HI'},global:{}};"
        "console.log(JSON.stringify({"
        "a:b.expandPlaceholders('x=${score}',v),"
        "b:b.resolveSendMessage({device:'LocalLoop'},'',"
        "{commManager:{sendEvents:[{device:'LocalLoop',variable:'flow.payload'}]}},v),"
        "c:b.resolveSendMessage({},'hi ${score}',{},v)"
        "}));"
    ], cwd=str(ROOT), text=True).strip()
    j = json.loads(js)
    ok('js expand', j['a'] == 'x=0.91', j)
    ok('js sendEvents var', j['b'] == 'HI', j)
    ok('js message expand', j['c'] == 'hi 0.91', j)

    # ----- N4 coverage -----
    defs = all_definitions([])
    uncovered = []
    for op in sorted(defs.keys()):
        step = {'id': 'x', 'operation': op, 'params': {}, 'imageFrom': None}
        if not step_incomplete(step) and op not in ('delay', 'branch_merge'):
            uncovered.append(op)
    ok('all catalog ops bang-or-exempt', uncovered == [], uncovered)
    ok('yolo_segment reason', '图像' in step_incomplete_reason({'id': 'x', 'operation': 'yolo_segment', 'params': {}, 'imageFrom': None}))
    ok('opcua_read reason', 'OPC' in step_incomplete_reason({'id': 'x', 'operation': 'opcua_read', 'params': {}, 'imageFrom': None}))
    ok('cloud_filter reason', '点云' in step_incomplete_reason({'id': 'x', 'operation': 'cloud_filter', 'params': {}, 'imageFrom': None}))
    ok('variables reason', '变量名' in step_incomplete_reason({'id': 'x', 'operation': 'variables', 'params': {}, 'imageFrom': None}))
    ok('source local empty', '本地' in source_incomplete_reason({'mode': 'local', 'images': []}))
    ok('source local ok', source_incomplete_reason({'mode': 'local', 'images': ['a.bmp']}) == '')

    # Graph tip includes reason
    src_g = open('desktop/graph.py', encoding='utf-8').read()
    ok('graph imports reason', 'node_incomplete_reason' in src_g)
    ok('graph tip has why', '组件参数未配置完整：' in src_g)
    ok('port invalid tip', '同向端口' in src_g or '无效' in src_g)

    # ----- Filmstrip / source -----
    ok('DEFAULT has imageFormatFilter', DEFAULT_SOURCE.get('imageFormatFilter') == '全部')
    cfg = normalize_source({'mode': 'local', 'images': ['a.bmp'], 'imageFormatFilter': '.png'})
    ok('normalize keeps format filter', cfg.get('imageFormatFilter') == '.png')
    form = ImageSourceForm({'mode': 'local', 'images': ['a.bmp'], 'imageFormatFilter': '.jpg'})
    ok('form has fmt_filter', hasattr(form, 'fmt_filter'))
    ok('form fmt selected', form.fmt_filter.currentData() == '.jpg', form.fmt_filter.currentData())

    # ----- Host template -----
    ui = default_host_run_ui()
    cmds = [c.get('type') for c in (ui.get('controls') or {}).get('上位机状态机', {}).get('commands') or []]
    ok('host tpl has 连续', '执行·连续' in cmds, cmds)
    ok('host tpl has 暂停', '执行·暂停' in cmds, cmds)
    ok('host tpl has 继续', '执行·继续' in cmds, cmds)
    ok('host tpl has 清除报警', '状态·清除报警' in cmds, cmds)
    ok('host tpl version>=2', int((ui.get('meta') or {}).get('version') or 0) >= 2)

    # ----- Live Document + EventTable trial + FlowScene tip -----
    from copy import deepcopy
    from desktop.comm_manager import _EventTable
    from desktop.graph import FlowScene

    src_mw = open('desktop/mainwindow.py', encoding='utf-8').read()
    ok('mw has apply_host_run_ui_template', 'def apply_host_run_ui_template' in src_mw)
    ok('mw filmstrip format handler', 'def _on_filmstrip_format_filter' in src_mw)

    doc = Document()
    proj = __import__('copy').deepcopy(doc.project)
    ensure_comm_manager(proj)
    write_project_variable(proj, 'flow.demoOut', 'DEMO-OUT')
    doc.commit(proj)

    table = _EventTable(var_role='read')
    table.bind_document(doc)
    table.set_rows([
        {'name': 'E1', 'device': 'LocalLoop', 'message': '', 'variable': 'flow.demoOut'},
        {'name': 'E2', 'device': 'LocalLoop', 'message': 'raw ${demoOut}', 'variable': ''},
    ], ['LocalLoop'])
    # Avoid modal QMessageBox blocking headless: stub information
    from PySide6.QtWidgets import QMessageBox
    _orig = QMessageBox.information
    QMessageBox.information = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
    try:
        table._trial_send_from_variables()
    finally:
        QMessageBox.information = _orig
    last = read_project_variable(doc.project, 'flow.lastSendPayload', '')
    ok('trial wrote lastSendPayload', last in ('DEMO-OUT', 'raw DEMO-OUT'), last)
    ok('trial wrote lastSendDevice', read_project_variable(doc.project, 'flow.lastSendDevice', '') == 'LocalLoop')

    # Add locate via catalog so Document graph stays valid
    from desktop.catalog import all_definitions as _defs
    defs = _defs([])
    loc_def = defs.get('locate')
    ok('locate in catalog', loc_def is not None)
    nid = doc.add(loc_def, parent='source') if loc_def else None
    p2 = deepcopy(doc.project)
    for s in p2['steps']:
        if s['id'] == nid:
            # strip imageFrom / template to force bang
            s.pop('imageFrom', None)
            s['params'] = {}
            s['reference'] = None
            break
    doc.commit(p2)
    scene = FlowScene(doc)
    scene.rebuild()
    loc1 = nid
    node = scene.nodes.get(loc1) if loc1 else None
    ok('locate needs_config', node is not None and bool(getattr(node, 'needs_config', False)))
    tip = node.toolTip() if node else ''
    ok('locate tip has reason', '模板' in tip or '图像' in tip, tip)

    summary_ok, summary_msg, bad = project_incomplete_summary(doc.project)
    ok('project summary lists incomplete', not summary_ok and loc1 in bad, (summary_ok, summary_msg, bad))

    print('DONE', 'fails=', len(fails))
    return 0 if not fails else 1


if __name__ == '__main__':
    sys.exit(main())
