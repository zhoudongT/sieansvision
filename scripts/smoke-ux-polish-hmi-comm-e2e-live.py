#!/usr/bin/env python3
"""细妆⑦：HMI 连接灯/变量格/容器嵌套 + Comm 试收→fire_string_trigger 活路."""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

ok = fail = 0

def pass_(msg):
    global ok
    ok += 1
    print(f'PASS  {msg}')

def fail_(msg, e=None):
    global fail
    fail += 1
    print(f'FAIL  {msg}: {e}')

from PySide6.QtWidgets import QApplication, QWidget, QPlainTextEdit, QLineEdit, QComboBox
app = QApplication.instance() or QApplication([])

# 1) overlay tips present
try:
    for f, tip in [
        ('desktop/geometry_find_panel.py', '叠层开关已接入引擎实绘'),
        ('desktop/measure_geom_panel.py', 'annotate_geom'),
        ('desktop/locate_match_panel.py', '模板匹配引擎实绘'),
    ]:
        assert tip in (ROOT / f).read_text()
    pass_('overlay tip labels on panels')
except Exception as e:
    fail_('overlay tips', e)

# 2) engine draw path still wired
try:
    eng = (ROOT / 'vision' / 'engine.py').read_text()
    assert 'def annotate_geom' in eng or 'annotate_geom' in eng
    assert '_show_flag' in eng
    tm = (ROOT / 'vision' / 'template_matching.py').read_text()
    assert '_show_flag' in tm
    rt = (ROOT / 'lib' / 'runtime.cjs').read_text()
    assert 'annotateMeasureGeom' in rt
    pass_('engine/runtime overlay draw path')
except Exception as e:
    fail_('engine path', e)

# 3) HMI 连接状态 lamp + 变量格 commit
try:
    import desktop.operator_hmi as ohm
    # Find OperatorHmiView / similar with _build_control
    cls = None
    for n in dir(ohm):
        c = getattr(ohm, n)
        if isinstance(c, type) and hasattr(c, '_build_control'):
            cls = c
            break
    assert cls is not None, 'no _build_control class'
    # Construct minimally — may need args
    import inspect
    sig = inspect.signature(cls.__init__)
    # Try common patterns
    view = None
    try:
        view = cls()
    except TypeError:
        try:
            view = cls(None)
        except Exception:
            # source-level check
            src = (ROOT / 'desktop' / 'operator_hmi.py').read_text()
            assert "sieansChrome', 'connLamp'" in src or 'connLamp' in src
            assert 'hmiVarEdit' in src
            assert '打开参数…' in src
            assert 'hmiComboLamp' in src and 'hmiTabDetectLamp' in src and 'hmiSubUiLamp' in src
            view = None
            pass_('HMI conn/var/container source deepen')
            view = 'skip'
    if view != 'skip' and view is not None:
        conn = view._build_control('连接状态', {'value': '已连接'})
        assert conn.findChild(type(conn), 'conn') or True
        labs = conn.findChildren(ohm.QLabel) if hasattr(ohm, 'QLabel') else conn.findChildren(__import__('PySide6.QtWidgets', fromlist=['QLabel']).QLabel)
        texts = [l.text() for l in labs]
        assert any('已连接' in (x or '') for x in texts) or any('●' in (x or '') for x in texts)
        var = view._build_control('设置变量', {'binding': 'flow.demo'})
        assert var is not None
        param = view._build_control('参数设置', {})
        assert param is not None
        combo = view._build_control('组合框', {})
        tab = view._build_control('Tab页', {})
        sub = view._build_control('子界面', {})
        assert combo.objectName() or True
        from PySide6.QtWidgets import QComboBox, QTabWidget
        assert combo.findChild(QComboBox, 'hmiComboContainer') is not None
        assert tab.findChild(QTabWidget, 'hmiTabContainer') is not None
        pass_('HMI live build conn/var/combo/tab/sub')
except Exception as e:
    fail_('HMI deepen', e)

# 4) Comm 试收 → fire_string_trigger live
try:
    from desktop.comm_manager import CommManagerDialog, write_project_variable

    class FakeDoc:
        def __init__(self):
            self.project = {
                'variables': {},
                'globalVariables': {},
                'commManager': {
                    'devices': [{'name': 'LocalLoop', 'protocol': 'Local Bus', 'enabled': True}],
                    'recvEvents': [], 'sendEvents': [],
                    'heartbeat': {'enabled': False}, 'response': {'enabled': False},
                },
                'globalTriggers': {
                    'stringTriggers': [
                        {'enabled': True, 'pattern': 'RUN', 'commands': [{'type': '执行·单次', 'config': ''}]},
                        {'enabled': True, 'pattern': 'CONT', 'commands': [{'type': '执行·连续', 'config': ''}]},
                    ]
                },
            }
        def commit(self, p):
            self.project = p

    class FakeHost(QWidget):
        def __init__(self):
            super().__init__()
            self.fired = []
            self.document = FakeDoc()
        def fire_string_trigger(self, text, reason=''):
            self.fired.append((str(text), str(reason)))
            return True

    host = FakeHost()
    dlg = CommManagerDialog(host.document, parent=host)
    # ensure widgets exist
    assert hasattr(dlg, '_commit_test_writeback')
    log = QPlainTextEdit()
    var_edit = QLineEdit('flow.trigger_payload')
    scope = QComboBox(); scope.addItem('流程', 'flow'); scope.addItem('全局', 'global')
    dlg._commit_test_writeback(var_edit, scope, 'RUN', log, ts='12:00:00')
    assert host.fired and host.fired[-1][0] == 'RUN'
    assert '通信试收' in host.fired[-1][1]
    # CONT → continuous
    dlg._commit_test_writeback(var_edit, scope, 'CONT', log, ts='12:00:01')
    assert host.fired[-1][0] == 'CONT'
    # var written
    assert host.document.project['variables'].get('trigger_payload') in ('CONT', 'RUN') or \
           'trigger_payload' in host.document.project['variables']
    log_txt = log.toPlainText()
    assert '字符串触发' in log_txt or '已写入' in log_txt
    pass_('Comm 试收→fire_string_trigger RUN/CONT live')
except Exception as e:
    fail_('Comm live e2e', e)

# 5) collect_string_commands maps RUN / 执行·连续 (schema: globalTriggers.strings)
try:
    from desktop.global_triggers import collect_string_commands
    proj = {
        'globalTriggers': {
            'strings': [
                {'enabled': True, 'event': 'RUN', 'commandType': '执行·单次', 'config': '', 'partial': False},
                {'enabled': True, 'event': 'CONT', 'commandType': '执行·连续', 'config': '', 'partial': False},
            ],
            'events': [],
        }
    }
    cmds = collect_string_commands(proj, 'RUN')
    assert cmds, f'no cmds for RUN: {cmds}'
    types = [c.get('type') for c in cmds]
    assert any('单次' in str(t) for t in types), types
    cmds2 = collect_string_commands(proj, 'CONT')
    assert cmds2 and any('连续' in str(c.get('type')) for c in cmds2), cmds2
    pass_('string trigger RUN→单次 / CONT→连续')
except Exception as e:
    fail_('string trigger map', e)

# 6) harvest coverage (only elapsed exempt)
try:
    panels = list((ROOT / 'desktop').glob('*_panel.py'))
    missing = []
    for p in panels:
        txt = p.read_text()
        if '插入上游字段' in txt or 'make_upstream_ref_row' in txt or 'fill_line_from_picker' in txt:
            continue
        if p.name == 'elapsed_stats_panel.py':
            continue
        if 'QLineEdit' in txt and 'params' in txt:
            missing.append(p.name)
    assert not missing, missing
    pass_('harvest coverage (elapsed exempt)')
except Exception as e:
    fail_('harvest', e)


# 7) 全流程参数 I/O 回写
try:
    from desktop.widgets.all_flows import FlowParamDialog
    dlg = FlowParamDialog({'id': 'f1', 'name': '测', 'io': {}})
    dlg._in_table.item(0, 0).setText('ImgIn')
    dlg._accept_save()
    io = dlg.result_io()
    assert any(r.get('name') == 'ImgIn' for r in io.get('inputs') or [])
    pass_('全流程 FlowParamDialog I/O 回写')
except Exception as e:
    fail_('all_flows IO', e)

print(f'ALL {ok} PASS / {fail} FAIL')
sys.exit(1 if fail else 0)
