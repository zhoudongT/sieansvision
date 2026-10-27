#!/usr/bin/env python3
"""细妆 smoke: filmstrip format filter · alarm filter · group display · Host infoLogged."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from PySide6.QtWidgets import QApplication
app = QApplication.instance() or QApplication([])
fails = []

def check(name, cond, detail=''):
    if cond:
        print(f'PASS: {name}')
    else:
        print(f'FAIL: {name} {detail}')
        fails.append(name)

from desktop.widgets.filmstrip import FilmstripBar
fs = FilmstripBar()
check('filmstrip format_filter', hasattr(fs, 'format_filter'))
fs.set_format_filter('.png')
check('set_format_filter png', fs._format_filter_key == '.png')
fs.set_format_filter('全部')
check('set_format_filter 全部', fs._format_filter_key == '全部')

from desktop.host_state_machine import HostStateMachineWidget
h = HostStateMachineWidget()
h._record_alarm('通信超时 TCP')
h._record_alarm('流程失败 NG')
check('alarm filter widget', hasattr(h, '_alarm_filter'))
h._alarm_filter.setText('TCP')
h._refresh_alarm_history_ui()
check('alarm filter TCP', h._alarm_list.count() == 1, str(h._alarm_list.count()))
h._alarm_filter.setText('')
h._refresh_alarm_history_ui()
check('alarm filter clear', h._alarm_list.count() == 2)

from desktop.group_module import GroupParamPanel
panel = GroupParamPanel({'id': 'g1', 'operation': 'group', 'name': 'G', 'params': {}}, {'steps': [], 'edges': []})
check('group show_inner', hasattr(panel, '_show_inner'))
check('group show_roi', hasattr(panel, '_show_roi'))
panel._show_inner.setChecked(False)
panel._emit()
check('group display persist', panel.params['io']['display'].get('showInnerImage') is False)

from desktop.operator_hmi import OperatorHmiView
check('HMI host info mirror', hasattr(OperatorHmiView, '_on_host_info_logged'))

seen = []
h.infoLogged.connect(lambda s: seen.append(s))
h.append_info('镜像探测')
check('infoLogged emit', any('镜像探测' in x for x in seen))

# enter_group tip source
mw = (ROOT / 'desktop/mainwindow.py').read_text(encoding='utf-8')
check('enter_group 组内红叹号 tip', '组内红叹号' in mw)

print('---')
print(f'{10 - len(fails)} PASS / {len(fails)} FAIL' if False else f'{10 - len(fails)} checks; {len(fails)} FAIL')
# recount
total = 10
print(f'{total - len(fails)} PASS / {len(fails)} FAIL')
sys.exit(1 if fails else 0)
