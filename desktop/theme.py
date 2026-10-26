"""SIEANS Vision industrial UI tokens (VisionMaster / Halcon workbench tone)."""

# Palette — cool industrial cyan on slate
BG = '#e8eef3'
PANEL = '#f5f8fb'
CARD = '#ffffff'
LINE = '#c5d6e4'
LINE_SOFT = '#d9e6ef'
ACCENT = '#0a8eb8'
ACCENT_DEEP = '#067a9e'
TEXT = '#1a3550'
TEXT_MUTED = '#5a7188'
TEXT_DIM = '#7a90a3'
OK = '#1f8a5b'
WARN = '#b7791f'
HOVER = '#eef8fc'
SELECTED = '#d9f0f8'
HEADER = '#edf3f8'

# Category accent strip colors (subtle)
CATEGORY_COLORS = {
    '相机采集': '#0a8eb8',
    '图像处理': '#3b82a0',
    '定位与测量': '#1f7a6c',
    '识别': '#7a5ca8',
    '3D 点云': '#4a6fa5',
    '工业通信': '#8a6b3d',
    '流程控制': '#5a7088',
    '变量与数据': '#6a7a90',
    '扩展算子': '#6a8090',
}


def category_color(name: str) -> str:
    return CATEGORY_COLORS.get(name, ACCENT)


WORKBENCH_QSS = f'''
QMainWindow, QWidget {{
  font-family: "Microsoft YaHei UI", "Noto Sans CJK SC", "Source Han Sans SC", sans-serif;
  font-size: 13px;
  color: {TEXT};
}}
QMainWindow {{ background: {BG}; }}
QMenuBar, QToolBar {{
  background: #ffffff;
  border-bottom: 1px solid {LINE};
  spacing: 8px;
  padding: 6px 8px;
}}
QMenuBar::item:selected, QToolButton:hover, QPushButton:hover {{
  background: {HOVER};
}}
QToolButton {{
  padding: 6px 10px;
  border-radius: 5px;
}}
QPushButton {{
  background: #ffffff;
  border: 1px solid {LINE};
  border-radius: 5px;
  padding: 6px 12px;
  min-height: 22px;
}}
QPushButton:pressed {{ background: {SELECTED}; }}
QPushButton:disabled, QToolButton:disabled {{ color: #9aabb7; }}
QPushButton#primaryButton {{
  background: {ACCENT};
  color: white;
  border: 1px solid {ACCENT_DEEP};
  font-weight: 600;
}}
QPushButton#primaryButton:hover {{ background: {ACCENT_DEEP}; }}
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QPlainTextEdit {{
  background: #ffffff;
  border: 1px solid {LINE};
  border-radius: 5px;
  padding: 5px 8px;
  selection-background-color: {SELECTED};
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus, QPlainTextEdit:focus {{
  border: 1px solid {ACCENT};
}}
QComboBox::drop-down {{ border: 0; width: 22px; }}
QTreeWidget, QTableWidget, QListWidget {{
  background: #ffffff;
  border: 1px solid {LINE_SOFT};
  border-radius: 6px;
  alternate-background-color: {PANEL};
  outline: 0;
}}
QHeaderView::section {{
  background: {HEADER};
  color: #355a74;
  padding: 7px 8px;
  border: 0;
  border-bottom: 1px solid {LINE};
  font-weight: 600;
}}
QTabWidget::pane {{
  border: 1px solid {LINE};
  background: #ffffff;
  border-radius: 0 0 6px 6px;
  top: -1px;
}}
QTabBar::tab {{
  background: {HEADER};
  padding: 8px 14px;
  margin-right: 2px;
  border-top-left-radius: 5px;
  border-top-right-radius: 5px;
  color: {TEXT_MUTED};
}}
QTabBar::tab:selected {{
  background: #ffffff;
  color: {ACCENT};
  font-weight: 600;
  border-bottom: 2px solid {ACCENT};
}}
QSplitter::handle {{ background: {LINE_SOFT}; width: 3px; height: 3px; }}
QStatusBar {{ background: #092552; color: white; }}
QLabel#brand {{ color: {ACCENT}; font-size: 20px; font-weight: 700; padding: 4px 10px; }}
QScrollBar:vertical {{
  background: transparent; width: 10px; margin: 2px;
}}
QScrollBar::handle:vertical {{
  background: #b7c9d6; border-radius: 4px; min-height: 28px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}

/* —— Operator library —— */
QWidget#libraryPane {{
  background: {PANEL};
  border-right: 1px solid {LINE_SOFT};
}}
QLabel#libraryTitle {{
  color: {TEXT};
  font-size: 14px;
  font-weight: 700;
  padding: 2px 2px 0 2px;
}}
QLabel#libraryHint {{
  color: {TEXT_DIM};
  font-size: 11px;
  padding: 0 2px 4px 2px;
}}
QLineEdit#operatorSearch {{
  background: #ffffff;
  border: 1px solid {LINE};
  border-radius: 8px;
  padding: 7px 12px 7px 12px;
  font-size: 13px;
}}
QLineEdit#operatorSearch:focus {{ border: 1px solid {ACCENT}; }}

/* —— Property / settings inspector —— */
QWidget#propertyPanel {{
  background: {PANEL};
  border-left: 1px solid {LINE_SOFT};
}}
QLabel#panelTitle {{
  color: {TEXT};
  font-size: 15px;
  font-weight: 700;
  padding: 4px 2px 0 2px;
}}
QLabel#operatorSignature {{
  color: {ACCENT_DEEP};
  font-size: 11px;
  padding: 0 2px;
}}
QLabel#panelDescription {{
  color: {TEXT_MUTED};
  font-size: 12px;
  padding: 0 2px 4px 2px;
}}
QGroupBox#propertySection {{
  background: {CARD};
  border: 1px solid {LINE_SOFT};
  border-radius: 8px;
  margin-top: 12px;
  padding: 10px 8px 8px 8px;
  font-weight: 600;
}}
QGroupBox#propertySection::title {{
  subcontrol-origin: margin;
  subcontrol-position: top left;
  left: 10px;
  padding: 0 6px;
  color: {TEXT};
  background: {CARD};
}}
QLabel#sectionHint {{
  color: {TEXT_DIM};
  font-size: 11px;
}}
QLabel#typeMark {{
  background: #e8f4fb;
  color: {ACCENT_DEEP};
  border: 1px solid #b7d9ea;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
  padding: 2px;
}}
QComboBox#valueMode {{
  max-width: 100px;
  font-size: 12px;
  padding: 4px 6px;
  background: {HEADER};
}}
QScrollArea#propertyScroll {{
  background: transparent;
  border: 0;
}}

/* —— Dialogs (device / settings) —— */
QDialog {{
  background: {BG};
}}
QDialog QGroupBox {{
  background: {CARD};
  border: 1px solid {LINE_SOFT};
  border-radius: 8px;
  margin-top: 12px;
  padding-top: 8px;
  font-weight: 600;
}}
QDialog QGroupBox::title {{
  subcontrol-origin: margin;
  left: 10px;
  padding: 0 6px;
}}
QDialog QLabel#dialogTitle {{
  font-size: 16px;
  font-weight: 700;
  color: {TEXT};
}}
QDialog QLabel#dialogHint {{
  color: {TEXT_MUTED};
  font-size: 12px;
}}
'''

TOOLBOX_QSS = f'''
Toolbox {{
  border: 0;
  background: transparent;
}}
QToolButton#categoryHeader {{
  text-align: left;
  font-weight: 650;
  font-size: 12px;
  color: {TEXT};
  border: 1px solid {LINE_SOFT};
  border-radius: 6px;
  padding: 8px 10px;
  background: {CARD};
  margin: 0 2px;
}}
QToolButton#categoryHeader:hover {{
  background: {HOVER};
  border-color: #9ecfe0;
}}
QToolButton#categoryHeader:checked {{
  background: {SELECTED};
  border-color: #7cc0d8;
}}
QListWidget#operatorTiles {{
  background: transparent;
  border: 0;
  outline: 0;
  padding: 2px 0 6px 0;
}}
QListWidget#operatorTiles::item {{
  background: transparent;
  border: 0;
  padding: 0;
  margin: 0;
}}
QLabel#emptyOps {{
  color: {TEXT_DIM};
  padding: 24px 8px;
  font-size: 12px;
}}
'''
