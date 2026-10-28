#!/usr/bin/env python3
"""TextSave / OutputImage / condition / elapsed_stats / soft IO result-tab deepen — no hardware."""
from __future__ import annotations
import ast
import os
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
    files = [
        'desktop/wave3_thin_panels.py',
        'desktop/condition_branch_panel.py',
        'desktop/elapsed_stats_panel.py',
        'desktop/data_io_panel.py',
        'lib/flow-control.cjs',
        'lib/runtime.cjs',
    ]
    for rel in files:
        src = (ROOT / rel).read_text(encoding='utf-8')
        if rel.endswith('.py'):
            ast.parse(src)
        ok(f'ast/parse {rel}')

    wave = (ROOT / 'desktop/wave3_thin_panels.py').read_text(encoding='utf-8')
    for needle in (
        'outputImageResultPreview', 'outputImageResultMeta', 'outputImageResultRefresh',
        '_refresh_output_image_result', 'dateSubdir', 'saveAnnotated',
        'textSaveResultPreview', 'textSaveResultMeta', 'textSaveResultRefresh',
        '_refresh_text_save_result', 'maxLinesSoft', 'separator',
    ):
        (ok if needle in wave else bad)(f'wave3 has {needle}' if needle in wave else f'missing {needle}')

    cond = (ROOT / 'desktop/condition_branch_panel.py').read_text(encoding='utf-8')
    for needle in ('conditionResultPreview', 'conditionResultMeta', 'conditionResultRefresh', '_eval_one_design', '_refresh_condition_result'):
        (ok if needle in cond else bad)(f'condition has {needle}' if needle in cond else f'missing {needle}')

    el = (ROOT / 'desktop/elapsed_stats_panel.py').read_text(encoding='utf-8')
    for needle in ('elapsedStatsResultPreview', 'elapsedStatsResultMeta', 'elapsedStatsResultRefresh', 'warnMs', 'targetVar'):
        (ok if needle in el else bad)(f'elapsed has {needle}' if needle in el else f'missing {needle}')

    dio = (ROOT / 'desktop/data_io_panel.py').read_text(encoding='utf-8')
    for needle in ('dataIoResultPreview', 'dataIoResultMeta', 'dataIoResultRefresh', 'samplePayload', 'prefix', 'suffix'):
        (ok if needle in dio else bad)(f'data_io has {needle}' if needle in dio else f'missing {needle}')

    rt = (ROOT / 'lib/runtime.cjs').read_text(encoding='utf-8')
    (ok if 'params.prefix' in rt and 'params.suffix' in rt else bad)('runtime send prefix/suffix')
    fc = (ROOT / 'lib/flow-control.cjs').read_text(encoding='utf-8')
    (ok if 'dateSubdir' in fc else bad)('flow-control dateSubdir')
    (ok if 'p.separator' in fc else bad)('flow-control textSave separator')

    from PySide6.QtWidgets import QApplication, QPlainTextEdit, QLabel
    app = QApplication.instance() or QApplication([])

    from desktop.wave3_thin_panels import TextSavePanel, OutputImagePanel
    from desktop.condition_branch_panel import ConditionBranchPanel
    from desktop.elapsed_stats_panel import ElapsedStatsPanel
    from desktop.data_io_panel import DataIoPanel

    # ---- TextSave ----
    ts_step = {
        'id': 'ts1', 'operation': 'text_save', 'name': '文本保存',
        'params': {
            'path': '/tmp/sieans-smoke-text.txt',
            'content': 'hello,score=0.99',
            'append': True,
            'encoding': 'utf-8',
            'newline': True,
            'bom': False,
            'timestampPrefix': True,
            'separator': '|',
        },
    }
    ts = TextSavePanel(ts_step, {}, {'steps': [ts_step], 'edges': []})
    ok('TextSavePanel constructed')
    assert isinstance(ts._ts_result_preview, QPlainTextEdit)
    ttext = ts._ts_result_preview.toPlainText()
    assert 'hello,score=0.99' in ttext, ttext
    assert '|' in ttext, ttext
    ok(f'text_save preview has body+sep → {ttext[:60]!r}…')
    tmeta = ts._ts_result_meta.text()
    assert '/tmp/sieans-smoke-text.txt' in tmeta and '追加' in tmeta, tmeta
    ok(f'text_save meta → {tmeta}')
    ts._set_param('sourceVar', 'formatted')
    ts._refresh_text_save_result()
    assert '${formatted}' in ts._ts_result_preview.toPlainText()
    ok('text_save sourceVar placeholder')

    # ---- OutputImage ----
    oi_step = {
        'id': 'oi1', 'operation': 'output_image', 'name': '输出图像',
        'imageFrom': 'source',
        'params': {
            'path': '/tmp/sieans-out',
            'format': 'png',
            'filePrefix': 'shot',
            'useTimestamp': True,
            'onlyOnOk': True,
            'okVar': 'passGate',
            'dateSubdir': True,
            'saveAnnotated': True,
        },
    }
    oi = OutputImagePanel(oi_step, {}, {'steps': [oi_step], 'edges': []})
    ok('OutputImagePanel constructed')
    otext = oi._oi_result_preview.toPlainText()
    assert 'shot_' in otext and '.png' in otext, otext
    assert 'passGate' in otext or 'onlyOnOk' in otext, otext
    ok(f'output_image preview → {otext.replace(chr(10), " | ")[:120]}')
    ometa = oi._oi_result_meta.text()
    assert '输入源=source' in ometa and 'png' in ometa, ometa
    ok(f'output_image meta → {ometa}')

    # ---- condition ----
    c_step = {
        'id': 'c1', 'operation': 'condition', 'name': '条件',
        'params': {
            'logic': 'and',
            'rules': [
                {'left': '1', 'comparison': 'gt', 'right': '0', 'enabled': True},
                {'left': '2', 'comparison': 'eq', 'right': '2', 'enabled': True},
            ],
        },
    }
    cp = ConditionBranchPanel(c_step, {}, {'steps': [c_step], 'edges': []})
    ok('ConditionBranchPanel constructed')
    ctext = cp._cond_result_preview.toPlainText()
    assert '✓' in ctext, ctext
    cmeta = cp._cond_result_meta.text()
    assert 'passed=True' in cmeta and 'when=true' in cmeta, cmeta
    ok(f'condition design eval → {cmeta}')

    # ---- elapsed ----
    steps = [
        {'id': 'a', 'operation': 'locate', 'name': '定位'},
        {'id': 'b', 'operation': 'geometry', 'name': '几何'},
        {'id': 'e1', 'operation': 'elapsed_stats', 'name': '耗时', 'params': {
            'startStepId': 'a', 'endStepId': 'b', 'warnMs': 50, 'targetVar': 'elapsedTotalMs',
        }},
    ]
    ep = ElapsedStatsPanel(steps[2], {}, {'steps': steps, 'edges': []})
    ok('ElapsedStatsPanel constructed')
    etext = ep._elapsed_result_preview.toPlainText()
    assert '定位' in etext and '几何' in etext, etext
    emeta = ep._elapsed_result_meta.text()
    assert '区间 2 步' in emeta and 'soft' not in emeta.lower()
    assert '50 ms' in emeta and 'flow.elapsedTotalMs' in emeta, emeta
    ok(f'elapsed span → {emeta}')

    # ---- soft IO receive/send ----
    recv = {
        'id': 'r1', 'operation': 'receive_data', 'name': '接收',
        'params': {
            'device': 'LocalLoop', 'targetVar': 'recvData', 'targetScope': 'flow',
            'samplePayload': 'A,0.9,1', 'encoding': 'utf-8', 'timeoutMs': 500,
        },
    }
    rp = DataIoPanel(recv, {}, {'steps': [recv], 'edges': [], 'commManager': {'devices': [{'name': 'LocalLoop'}]}})
    ok('DataIoPanel receive constructed')
    assert 'A,0.9,1' in rp._io_result_preview.toPlainText()
    assert 'LocalLoop' in rp._io_result_meta.text() and 'flow.recvData' in rp._io_result_meta.text()
    ok(f'receive preview meta → {rp._io_result_meta.text()}')

    send = {
        'id': 's1', 'operation': 'send_data', 'name': '发送',
        'params': {
            'device': 'LocalLoop', 'sourceMode': 'text', 'message': 'OK',
            'prefix': '[', 'suffix': ']', 'appendCrLf': True, 'encoding': 'utf-8',
        },
    }
    sp = DataIoPanel(send, {}, {'steps': [send], 'edges': [], 'commManager': {'devices': [{'name': 'LocalLoop'}]}})
    ok('DataIoPanel send constructed')
    sbody = sp._io_result_preview.toPlainText()
    assert sbody.startswith('[OK]'), sbody
    assert '\r\n' in sbody or sbody.endswith('\n') or 'CRLF' in sp._io_result_meta.text()
    ok(f'send preview → {sbody!r} · {sp._io_result_meta.text()}')

    # engine unit: textSave / outputImage / dateSubdir via node
    import subprocess, json, tempfile
    with tempfile.TemporaryDirectory() as td:
        out_js = Path(td) / 't.js'
        out_js.write_text(
            "const c=require('./lib/flow-control.cjs');\n"
            f"const r=c.textSave({{path:{json.dumps(str(Path(td)/'a.txt'))},content:'x',append:false,timestampPrefix:true,separator:'|'}},{{}});\n"
            "console.log(JSON.stringify(r));\n"
            f"const img='data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==';\n"
            f"const o=c.outputImage({{path:{json.dumps(str(Path(td)/'imgs'))},format:'png',filePrefix:'p',useTimestamp:false,dateSubdir:true,createDir:true}},{{image:img}},{{}});\n"
            "console.log(JSON.stringify(o));\n",
            encoding='utf-8',
        )
        # require path: run from ROOT
        r = subprocess.run(['node', '-e', out_js.read_text(encoding='utf-8')], cwd=str(ROOT), capture_output=True, text=True)
        if r.returncode != 0:
            bad(f'node engine smoke fail: {r.stderr}')
        else:
            lines = [ln for ln in r.stdout.strip().splitlines() if ln.strip()]
            ok(f'engine textSave/outputImage → {lines}')
            try:
                tr = json.loads(lines[0]); or_ = json.loads(lines[1])
                assert tr.get('status') == 'ok', tr
                assert '|' in Path(tr['path']).read_text(encoding='utf-8')
                ok('textSave wrote separator')
                assert or_.get('status') == 'ok', or_
                assert Path(or_['path']).exists()
                # date subdir in path
                assert any(ch.isdigit() for ch in or_['path']), or_
                ok(f'outputImage dateSubdir path → {or_["path"]}')
            except Exception as exc:
                bad(f'engine assert: {exc} :: {r.stdout}')

    print(f'\\nSUMMARY {pass_n} pass / {fail_n} fail')
    return 0 if fail_n == 0 else 1

if __name__ == '__main__':
    sys.exit(main())
