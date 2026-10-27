#!/usr/bin/env python3
"""细妆⑰：measure_geom 绑定制导 — slots / wizard UI / apply writes params.
No Halcon / no robot SDK / no push.
"""
from __future__ import annotations
import os, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); os.chdir(ROOT)
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

fails = []
def ok(n, c, d=''):
    if c: print(f'PASS  {n}')
    else: fails.append(n); print(f'FAIL  {n}  {d}')

def main():
    from PySide6.QtWidgets import QApplication, QPushButton, QDialog, QProgressBar, QMessageBox
    app = QApplication.instance() or QApplication(sys.argv)
    QMessageBox.information = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)

    from desktop.measure_geom_panel import MeasureGeomPanel

    project = {
        'steps': [
            dict(id='s1', name='卡尺直线', operation='geometry'),
            dict(id='s2', name='定位', operation='locate'),
            dict(id='s3', name='两线交点', operation='line_intersect', params={}),
        ]
    }
    step = project['steps'][2]
    panel = MeasureGeomPanel(step, {}, project)
    btns = [b for b in panel.findChildren(QPushButton) if b.objectName() == 'measureGeomBindWizardBtn']
    ok('wizard button found', len(btns) == 1, len(btns))
    ok('_bind_slots', hasattr(panel, '_bind_slots'))
    slots = panel._bind_slots()
    ok('line_intersect 2 slots', len(slots) == 2 and slots[0][0] == '直线1' and slots[1][0] == '直线2', slots)

    panel2 = MeasureGeomPanel(
        dict(id='pd', name='点距', operation='point_distance', params={}),
        {},
        {'steps': [dict(id='loc', name='定位', operation='locate')]},
    )
    s2 = panel2._bind_slots()
    ok('point_distance slots', len(s2) == 2 and '点1' in s2[0][0], s2)

    panel3 = MeasureGeomPanel(
        dict(id='pl', name='点线距', operation='point_line_distance', params={}),
        {},
        {'steps': []},
    )
    s3 = panel3._bind_slots()
    ok('point_line_distance slots', len(s3) == 2 and s3[0][1] == 'pointFrom', s3)

    panel._set_param('line1From', 's1')
    panel._set_param('line1Field', 'lines[0]')
    panel._set_param('line2From', 's1')
    panel._set_param('line2Field', 'lines[1]')
    ok('params line1From', panel.params.get('line1From') == 's1')
    ok('params line2Field', panel.params.get('line2Field') == 'lines[1]')

    opened = {'v': False}
    real_exec = QDialog.exec
    def fake_exec(self):
        opened['v'] = True
        ok('wizard has progress', self.findChild(QProgressBar) is not None)
        names = {b.text() for b in self.findChildren(QPushButton)}
        ok('wizard has 下一步', '下一步' in names, names)
        ok('wizard has 画布点选', '画布点选' in names, names)
        ok('wizard has 跳过', '跳过' in names, names)
        ok('wizard has 插入上游字段', '插入上游字段' in names, names)
        self.reject()
        return 0
    QDialog.exec = fake_exec
    try:
        panel._run_bind_wizard()
    finally:
        QDialog.exec = real_exec
    ok('wizard dialog opened', opened['v'])

    src = open('desktop/measure_geom_panel.py', encoding='utf-8').read()
    ok('source has 绑定制导', '绑定制导' in src and 'def _run_bind_wizard' in src)

    print('----')
    if fails:
        print(f'{len(fails)} FAIL'); sys.exit(1)
    print('ALL PASS'); sys.exit(0)

if __name__ == '__main__':
    main()
