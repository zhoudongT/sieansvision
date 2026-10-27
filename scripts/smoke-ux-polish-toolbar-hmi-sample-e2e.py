#!/usr/bin/env python3
"""细妆⑧：单色工具栏图标 · HMI 栈页 · 行业读码模板."""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

ok = fail = 0

def pass_(m):
    global ok; ok += 1; print(f'PASS  {m}')

def fail_(m, e=None):
    global fail; fail += 1; print(f'FAIL  {m}: {e}')

from PySide6.QtWidgets import QApplication, QToolBar, QLabel
from PySide6.QtCore import Qt, QSize
app = QApplication.instance() or QApplication([])

# 1) mono icons render
try:
    from desktop.toolbar_icons import mono_icon, TOOLBAR_SPEC, apply_toolbar_action
    from PySide6.QtGui import QAction
    assert len(TOOLBAR_SPEC) >= 16
    for k in TOOLBAR_SPEC:
        ic = mono_icon(TOOLBAR_SPEC[k][0], size=18)
        assert not ic.isNull(), k
        # grab pixmap for smoke artifact
    pix = mono_icon('run_once', 18).pixmap(QSize(18, 18))
    out = ROOT / 'artifacts' / 'toolbar-icon-run.png'
    out.parent.mkdir(parents=True, exist_ok=True)
    pix.save(str(out))
    pass_('mono icons render + artifact')
except Exception as e:
    fail_('mono icons', e)

# 2) apply_toolbar_action sets tip CN
try:
    from PySide6.QtGui import QAction
    from PySide6.QtWidgets import QWidget
    w = QWidget()
    a = QAction('单次', w)
    apply_toolbar_action(a, 'run_once')
    assert a.toolTip() and '单次' in a.toolTip()
    assert not a.icon().isNull()
    pass_('apply_toolbar_action CN tip')
except Exception as e:
    fail_('apply tip', e)

# 3) theme has brandStrip / mainToolBar icon button rules
try:
    from desktop.theme import WORKBENCH_QSS
    assert 'brandStrip' in WORKBENCH_QSS
    assert 'QToolBar#mainToolBar QToolButton' in WORKBENCH_QSS
    assert 'mainToolBar::separator' in WORKBENCH_QSS
    pass_('theme brandStrip + toolbar QSS')
except Exception as e:
    fail_('theme', e)

# 4) mainwindow wires apply_toolbar_action
try:
    src = (ROOT / 'desktop' / 'mainwindow.py').read_text()
    assert 'apply_toolbar_action' in src
    assert 'brandStrip' in src
    assert '📷' not in src  # emoji stripped from toolbar cam
    assert "self.action('▶ 单次'" not in src
    pass_('mainwindow mono toolbar wiring')
except Exception as e:
    fail_('mainwindow', e)

# 5) HMI stacked combo + nested tab
try:
    import desktop.operator_hmi as ohm
    src = (ROOT / 'desktop' / 'operator_hmi.py').read_text()
    assert 'QStackedWidget' in src and 'hmiComboStack' in src
    assert 'hmiComboDropHint' in src and 'hmiTabNestedCombo' in src
    cls = next(getattr(ohm, n) for n in dir(ohm) if isinstance(getattr(ohm, n), type) and hasattr(getattr(ohm, n), '_build_control'))
    view = cls()
    combo = view._build_control('组合框', {})
    from PySide6.QtWidgets import QComboBox, QStackedWidget, QTabWidget
    assert combo.findChild(QComboBox, 'hmiComboContainer')
    assert combo.findChild(QStackedWidget, 'hmiComboStack')
    tab = view._build_control('Tab页', {})
    assert tab.findChild(QTabWidget, 'hmiTabContainer')
    assert tab.findChild(QComboBox, 'hmiTabNestedCombo')
    pass_('HMI stacked combo + nested Tab')
except Exception as e:
    fail_('HMI deepen', e)

# 6) OCR industry sample
try:
    path = ROOT / 'projects' / 'run-ui-templates' / '行业-印刷字符读码.ruitpl.json'
    assert path.exists()
    import json
    data = json.loads(path.read_text())
    assert '印刷' in (data.get('meta') or {}).get('name', '')
    src = (ROOT / 'desktop' / 'run_ui_designer.py').read_text()
    assert '行业-印刷字符读码.ruitpl.json' in src
    pass_('industry OCR sample + market seed')
except Exception as e:
    fail_('sample', e)

# 7) docs 收口
try:
    for doc in ['docs/VM-UX对照要点.md', 'docs/VisionMaster完整功能与设计总览.md']:
        txt = (ROOT / doc).read_text()
        assert '代码细妆已收口' in txt
        assert '外依赖未做' in txt
        assert '真机 TCP' in txt or '现场设备' in txt
        assert 'Halcon' in txt
        assert 'robot' in txt.lower() or '机械手' in txt
    pass_('docs 收口 vs 外依赖')
except Exception as e:
    fail_('docs', e)

print(f'ALL {ok} PASS / {fail} FAIL')
sys.exit(1 if fail else 0)
