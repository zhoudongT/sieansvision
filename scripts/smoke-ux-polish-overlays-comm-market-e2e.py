#!/usr/bin/env python3
"""细妆 e2e: measure/geom/locate overlays · Comm links · filmstrip · HMI market · float · settings."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtWidgets import QApplication
app = QApplication.instance() or QApplication([])
ok = 0
def pass_(n):
    global ok; ok += 1; print('PASS', n)

from desktop.measure_geom_panel import MeasureGeomPanel, normalize_measure_geom_params
p = normalize_measure_geom_params('point_distance', {})
assert all(p[k] for k in ('showPoints','showLines','showLabels','showDistanceText'))
MeasureGeomPanel({'id':'m1','operation':'point_distance','name':'距','params':{}}, {}, {'steps':[],'edges':[]})
pass_('measure overlays')

from desktop.geometry_find_panel import GeometryFindPanel
gp = GeometryFindPanel({'id':'g1','operation':'geometry_find','name':'几何','params':{'feature':'lines'}}, {}, {'steps':[],'edges':[]})
assert gp.params.get('showFitCurve', True) is True
pass_('geometry caliper overlays')

from desktop.locate_match_panel import LocateMatchPanel
lp = LocateMatchPanel({'id':'l1','operation':'locate_match','name':'定位','params':{}}, {}, {'steps':[],'edges':[]})
assert lp.params.get('traceFullCanvas') is False
pass_('locate canvas 描摹')

from desktop.comm_manager import CommManagerDialog
from desktop.global_triggers import GlobalTriggersDialog
assert hasattr(CommManagerDialog, '_open_global_triggers')
assert hasattr(CommManagerDialog, '_open_variables_hint')
assert hasattr(GlobalTriggersDialog, '_open_comm_manager')
pass_('Comm↔Triggers↔Vars')

import desktop.widgets.filmstrip as fs
cls = next(getattr(fs, n) for n in dir(fs) if n[0].isupper() and 'Film' in n)
w = cls(); assert hasattr(w, 'thumb_size')
pass_('filmstrip thumb size')

from desktop.run_ui_designer import RunUiDesignerDialog
assert hasattr(RunUiDesignerDialog, '_open_template_market')
assert Path('projects/run-ui-templates/行业-电子元件点检.ruitpl.json').exists()
pass_('HMI template market + seeds')

from desktop.elapsed_stats_panel import ElapsedStatsPanel, normalize_elapsed_stats_params
assert normalize_elapsed_stats_params({})['showTotal']
ElapsedStatsPanel({'id':'e1','operation':'elapsed_stats','name':'耗时','params':{}}, {}, {'steps':[],'edges':[]})
pass_('elapsed result switches')

from desktop.csharp_script_panel import CsharpScriptPanel
assert hasattr(CsharpScriptPanel, '_pick_upstream_into_inputs')
pass_('csharp upstream bind')

from desktop.property_float import PropertyFloat
pf = PropertyFloat()
assert pf.exec_btn.objectName() == 'propertyFloatRun'
pass_('float QSS objectNames')

assert 'def _settings_continuous_path_help' in Path('desktop/mainwindow.py').read_text()
pass_('settings continuous path help')

assert '进组后' in Path('desktop/group_module.py').read_text()
assert '细妆：进组时画布芯片' in Path('desktop/group_module.py').read_text()
pass_('nest group tip')

print(f'ALL {ok} PASS')
