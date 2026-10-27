"""SIEANS Vision industrial UI tokens — VisionMaster 4.x-aligned Dark + light property float.

Visual targets (VM V4.2/4.3 frames):
- Workbench: neutral charcoal (not blue-gray), dense chrome, radius 0–2px
- Font: Microsoft YaHei / YaHei UI, ~12px body / 11px secondary
- Tabs: flat + orange underline when selected
- Property float: light gray body, dark title + orange hairline, orange ON toggles
Keep sieans brand/accent; do not copy HIKROBOT logo.
"""

# —— Dark workbench (neutral charcoal, less blue) ——
BG = '#2a2c30'
PANEL = '#32353a'
CARD = '#3a3d42'
LINE = '#4a4e54'
LINE_SOFT = '#3f4348'
ACCENT = '#e67a2e'
ACCENT_DEEP = '#c45f18'
TEXT = '#e8e8e8'
TEXT_MUTED = '#a8a8a8'
TEXT_DIM = '#787878'
OK = '#2d9b6c'
WARN = '#d4a017'
HOVER = '#3d4046'
SELECTED = '#3d2e1f'
HEADER = '#232528'
CANVAS = '#2d2f33'
CANVAS_DOT = '#4e5258'
RAIL_BG = '#1a1b1d'
STATUS_BG = '#151617'
SCROLL = '#55585e'

# —— Light property float (VM 属性浮窗 / extra/01_t200.jpg) ——
FLOAT_BG = '#f0f0f0'
FLOAT_BG_ALT = '#e8e8e8'
FLOAT_CARD = '#ffffff'
FLOAT_LINE = '#d0d0d0'
FLOAT_LINE_SOFT = '#e0e0e0'
FLOAT_TITLE_BG = '#2b2d30'
FLOAT_TEXT = '#222222'
FLOAT_TEXT_MUTED = '#666666'
FLOAT_INPUT_BG = '#ffffff'
FLOAT_BTN_BG = '#e8e8e8'
FLOAT_SWITCH_OFF = '#c0c0c0'

CATEGORY_COLORS = {
    '相机采集': '#e67a2e',
    '图像处理': '#3b9db8',
    '定位与测量': '#2d9b6c',
    '识别': '#8a6bc8',
    '3D 点云': '#4a7fc5',
    '工业通信': '#b8893d',
    '流程控制': '#6a7a90',
    '变量与数据': '#6a8090',
    '扩展算子': '#6a8090',
}


def category_color(name: str) -> str:
    return CATEGORY_COLORS.get(name, ACCENT)


WORKBENCH_QSS = f"""
QMainWindow, QWidget {{
  font-family: "Microsoft YaHei UI", "Microsoft YaHei", "Noto Sans CJK SC", "Source Han Sans SC", sans-serif;
  font-size: 12px;
  color: {TEXT};
}}
QMainWindow {{ background: {BG}; }}
QMenuBar {{
  background: {HEADER};
  border-bottom: 1px solid {LINE};
  color: {TEXT};
  spacing: 4px;
  padding: 2px 4px;
  font-size: 12px;
}}
QMenuBar::item {{ padding: 4px 8px; }}
QMenuBar::item:selected {{ background: {HOVER}; color: {ACCENT}; }}
QMenu {{
  background: {CARD};
  border: 1px solid {LINE};
  color: {TEXT};
  font-size: 12px;
  padding: 2px;
}}
QMenu::item {{ padding: 5px 24px 5px 12px; }}
QMenu::item:selected {{ background: {SELECTED}; color: {ACCENT}; }}
QToolBar {{
  background: {HEADER};
  border-bottom: 1px solid {LINE};
  spacing: 4px;
  padding: 2px 6px;
}}
QToolButton {{
  padding: 4px 8px;
  border-radius: 2px;
  color: {TEXT};
  background: transparent;
  font-size: 12px;
}}
QToolButton:hover {{ background: {HOVER}; }}
QToolButton:checked {{ background: {SELECTED}; color: {ACCENT}; }}
QPushButton {{
  background: {CARD};
  border: 1px solid {LINE};
  border-radius: 2px;
  padding: 4px 10px;
  min-height: 20px;
  color: {TEXT};
  font-size: 12px;
}}
QPushButton:hover {{ background: {HOVER}; }}
QPushButton:pressed {{ background: {SELECTED}; }}
QPushButton:disabled, QToolButton:disabled {{ color: {TEXT_DIM}; }}
QPushButton#primaryButton {{
  background: {ACCENT};
  color: white;
  border: 1px solid {ACCENT_DEEP};
  font-weight: 600;
}}
QPushButton#primaryButton:hover {{ background: {ACCENT_DEEP}; }}
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QPlainTextEdit {{
  background: {CARD};
  border: 1px solid {LINE};
  border-radius: 2px;
  padding: 3px 6px;
  color: {TEXT};
  selection-background-color: {SELECTED};
  font-size: 12px;
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus, QPlainTextEdit:focus {{
  border: 1px solid {ACCENT};
}}
QComboBox::drop-down {{ border: 0; width: 18px; }}
QComboBox QAbstractItemView {{
  background: {CARD};
  border: 1px solid {LINE};
  selection-background-color: {SELECTED};
  color: {TEXT};
}}
QTreeWidget#resultTree {{
  background: {CARD};
  border: 0;
  alternate-background-color: {PANEL};
  color: {TEXT};
}}
QTreeWidget, QTableWidget, QListWidget {{
  background: {CARD};
  border: 1px solid {LINE_SOFT};
  border-radius: 2px;
  alternate-background-color: {PANEL};
  outline: 0;
  color: {TEXT};
  font-size: 12px;
}}
QHeaderView::section {{
  background: {HEADER};
  color: {TEXT_MUTED};
  padding: 5px 6px;
  border: 0;
  border-bottom: 1px solid {LINE};
  font-weight: 600;
  font-size: 11px;
}}
QTabWidget::pane {{
  border: 1px solid {LINE};
  background: {PANEL};
  border-radius: 0;
  top: -1px;
}}
QTabBar::tab {{
  background: transparent;
  padding: 6px 12px;
  margin-right: 0;
  border: 0;
  border-bottom: 2px solid transparent;
  border-radius: 0;
  color: {TEXT_MUTED};
  font-size: 12px;
}}
QTabBar::tab:hover {{ color: {TEXT}; background: {HOVER}; }}
QTabBar::tab:selected {{
  background: transparent;
  color: {ACCENT};
  font-weight: 600;
  border-bottom: 2px solid {ACCENT};
}}
QSplitter::handle {{ background: {LINE_SOFT}; width: 2px; height: 2px; }}
QStatusBar, QStatusBar#workbenchStatus {{
  background: {STATUS_BG};
  color: {TEXT_MUTED};
  border-top: 1px solid {LINE};
  font-size: 11px;
  min-height: 22px;
  max-height: 26px;
}}
QLabel#statusConfig, QLabel#statusTiming, QLabel#statusLog, QLabel#statusVersion {{
  color: {TEXT_MUTED};
  padding: 0 3px;
  font-size: 11px;
}}
QLabel#statusConfig[error="true"] {{ color: #e05555; }}
QLabel#brand {{
  color: {ACCENT};
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.3px;
  padding: 0 6px 0 2px;
}}
QScrollBar:vertical {{
  background: transparent; width: 8px; margin: 1px;
}}
QScrollBar::handle:vertical {{
  background: {SCROLL}; border-radius: 2px; min-height: 24px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{
  background: transparent; height: 8px; margin: 1px;
}}
QScrollBar::handle:horizontal {{
  background: {SCROLL}; border-radius: 2px; min-width: 24px;
}}

/* —— Left rail + library —— */
QWidget#operatorRail {{
  background: {RAIL_BG};
  border-right: 1px solid {LINE};
}}
QToolButton#railButton {{
  background: transparent;
  border: 0;
  border-radius: 2px;
  padding: 4px;
  margin: 0;
}}
QToolButton#railButton:hover {{ background: {HOVER}; }}
QToolButton#railButton:checked {{
  background: {SELECTED};
  border: 1px solid {ACCENT_DEEP};
}}
QWidget#libraryPane {{
  background: {PANEL};
  border-right: 1px solid {LINE_SOFT};
}}
QLabel#libraryTitle {{
  color: {TEXT_MUTED};
  font-size: 11px;
  font-weight: 600;
  padding: 0 2px;
}}
QLabel#libraryHint {{
  color: {TEXT_DIM};
  font-size: 10px;
  padding: 0 2px 2px 2px;
}}
QLineEdit#operatorSearch {{
  background: {CARD};
  border: 1px solid {LINE};
  border-radius: 2px;
  padding: 3px 6px;
  font-size: 11px;
}}
QLineEdit#operatorSearch:focus {{ border: 1px solid {ACCENT}; }}

/* —— Flow canvas host —— */
QWidget#flowPane {{
  background: {CANVAS};
}}
QWidget#flowTabBar {{
  background: {HEADER};
  border-bottom: 1px solid {LINE};
}}
QGraphicsView {{
  background: {CANVAS};
  border: 0;
}}
QWidget#flowMinimap {{
  background: {RAIL_BG};
  border: 1px solid {LINE};
  border-radius: 2px;
}}

/* —— Right image + filmstrip —— */
QWidget#imagePane {{
  background: {PANEL};
  border-left: 1px solid {LINE_SOFT};
}}
QWidget#filmstripBar {{
  background: {HEADER};
  border-top: 1px solid {LINE};
}}
QPushButton#filmstripRun {{
  background: {CARD};
  color: {TEXT};
  border: 1px solid {LINE};
  border-radius: 2px;
  padding: 2px 10px;
  min-height: 20px;
  font-size: 11px;
  font-weight: 500;
}}
QPushButton#filmstripRun:hover {{
  background: {HOVER};
  border-color: {ACCENT};
  color: {ACCENT};
}}
QLabel#filmstripCount {{
  color: {TEXT_MUTED};
  font-weight: 600;
  font-size: 11px;
}}
QListWidget#filmstripThumbs {{
  background: transparent;
  border: 0;
}}
QListWidget#filmstripThumbs::item:selected {{
  background: {SELECTED};
  border: 1px solid {ACCENT};
}}

/* —— Property / settings inspector (docked fallback, dark) —— */
QWidget#propertyPanel {{
  background: {PANEL};
  border-left: 1px solid {LINE_SOFT};
}}
QLabel#panelTitle {{
  color: {TEXT};
  font-size: 13px;
  font-weight: 700;
  padding: 4px 2px 0 2px;
}}
QLabel#operatorSignature {{
  color: {ACCENT};
  font-size: 11px;
  padding: 0 2px;
}}
QLabel#panelDescription {{
  color: {TEXT_MUTED};
  font-size: 11px;
  padding: 0 2px 4px 2px;
}}
QGroupBox#propertySection {{
  background: {CARD};
  border: 1px solid {LINE_SOFT};
  border-radius: 2px;
  margin-top: 10px;
  padding: 8px 6px 6px 6px;
  font-weight: 600;
  color: {TEXT};
}}
QGroupBox#propertySection::title {{
  subcontrol-origin: margin;
  subcontrol-position: top left;
  left: 8px;
  padding: 0 4px;
  color: {TEXT};
  background: {CARD};
}}
QLabel#sectionHint {{
  color: {TEXT_DIM};
  font-size: 11px;
}}
QLabel#typeMark {{
  background: {SELECTED};
  color: {ACCENT};
  border: 1px solid {ACCENT_DEEP};
  border-radius: 2px;
  font-size: 11px;
  font-weight: 600;
  padding: 2px;
}}
QComboBox#valueMode {{
  max-width: 100px;
  font-size: 11px;
  padding: 3px 5px;
  background: {HEADER};
}}
QScrollArea#propertyScroll {{
  background: transparent;
  border: 0;
}}
QPushButton#bindButton {{
  background: {HEADER};
  border: 1px solid {LINE};
  padding: 1px;
  min-height: 18px;
  border-radius: 2px;
}}

/* —— Dialogs —— */
QDialog {{
  background: {BG};
  color: {TEXT};
}}
QDialog QGroupBox {{
  background: {CARD};
  border: 1px solid {LINE_SOFT};
  border-radius: 2px;
  margin-top: 10px;
  padding-top: 6px;
  font-weight: 600;
}}
QDialog QGroupBox::title {{
  subcontrol-origin: margin;
  left: 8px;
  padding: 0 4px;
}}
QDialog QLabel#dialogTitle {{
  font-size: 14px;
  font-weight: 700;
  color: {TEXT};
}}
QDialog QLabel#dialogHint {{
  color: {TEXT_MUTED};
  font-size: 11px;
}}
QMessageBox {{
  background: {PANEL};
}}

/* —— Multi-flow tabs / 全流程 / 运行界面 —— */
QPushButton#flowAllButton, QPushButton#flowAddButton, QPushButton#flowTabName, QPushButton#flowTabRun {{
  background: transparent;
  border: 0;
  border-bottom: 2px solid transparent;
  border-radius: 0;
  padding: 5px 10px;
  min-height: 18px;
  color: {TEXT_MUTED};
  font-size: 12px;
}}
QPushButton#flowAllButton:checked, QPushButton#flowTabName:checked {{
  background: transparent;
  color: {ACCENT};
  border-bottom: 2px solid {ACCENT};
  font-weight: 600;
}}
QPushButton#flowAllButton:hover, QPushButton#flowTabName:hover, QPushButton#flowAddButton:hover {{
  color: {TEXT};
  background: {HOVER};
}}
QPushButton#flowTabRun {{
  padding: 4px 5px;
  color: {TEXT_MUTED};
}}
QFrame#flowCard {{
  background: {CARD};
  border: 1px solid {LINE};
  border-radius: 2px;
  border-top: 3px solid {ACCENT};
}}
QLabel#flowCardTitle {{
  font-weight: 700;
  font-size: 13px;
  color: {TEXT};
}}
QLabel#flowCardStats {{
  color: {TEXT_MUTED};
  font-size: 11px;
}}
QWidget#allFlowsPanel {{
  background: {CANVAS};
}}
QWidget#runModePane {{
  background: {PANEL};
}}
QLabel#runFixedBar {{
  background: {CARD};
  color: {TEXT_MUTED};
  border: 1px solid {LINE};
  border-radius: 2px;
  padding: 3px 6px;
  font-size: 11px;
}}
QLabel#runFixedBarSide {{
  background: {CARD};
  color: {TEXT_MUTED};
  border: 1px solid {LINE};
  border-radius: 2px;
  font-size: 11px;
  padding: 3px 2px;
}}
QFrame#runPreviewCell {{
  background: {CARD};
  border: 1px dashed {LINE};
  border-radius: 2px;
}}
QWidget#operatorGridHost {{
  background: {PANEL};
}}
QWidget#runModePane QPushButton {{
  min-height: 26px;
}}
QLabel#modeBadge {{
  background: {SELECTED};
  color: {ACCENT};
  border: 1px solid {ACCENT_DEEP};
  border-radius: 2px;
  padding: 2px 6px;
  font-weight: 700;
  font-size: 11px;
}}
QLabel#modeBadge[runMode="true"] {{
  background: #1c3a2a;
  color: {OK};
  border: 1px solid {OK};
}}
QFrame#groupBreadcrumb {{
  background: {CARD};
  border: 1px solid {LINE};
  border-radius: 2px;
}}
"""

TOOLBOX_QSS = f"""
Toolbox {{
  border: 0;
  background: {PANEL};
}}
Toolbox > QWidget {{
  background: {PANEL};
}}
QWidget#toolboxContent {{
  background: {PANEL};
}}
QScrollArea {{
  background: {PANEL};
  border: 0;
}}
QAbstractScrollArea::viewport {{
  background: {PANEL};
}}
QToolButton#categoryHeader {{
  text-align: left;
  font-weight: 600;
  font-size: 11px;
  color: {TEXT};
  border: 1px solid {LINE_SOFT};
  border-radius: 2px;
  padding: 3px 6px;
  background: {CARD};
  margin: 0 1px;
}}
QToolButton#categoryHeader:hover {{
  background: {HOVER};
  border-color: {ACCENT_DEEP};
}}
QToolButton#categoryHeader:checked {{
  background: {SELECTED};
  border-color: {ACCENT};
  color: {ACCENT};
}}
QListWidget#operatorTiles {{
  background: {PANEL};
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
QListWidget#operatorTiles QWidget {{
  background: {PANEL};
}}
QLabel#emptyOps {{
  color: {TEXT_DIM};
  background: {PANEL};
  padding: 20px 8px;
  font-size: 11px;
}}
"""

# Light property float — applied on PropertyFloat dialog only
PROPERTY_FLOAT_QSS = f"""
QDialog#propertyFloat {{
  background: {FLOAT_BG};
  border: 1px solid {FLOAT_LINE};
  border-radius: 2px;
  font-family: "Microsoft YaHei UI", "Microsoft YaHei", sans-serif;
  font-size: 12px;
  color: {FLOAT_TEXT};
}}
QFrame#propertyFloatTitle {{
  background: {FLOAT_TITLE_BG};
  border: 0;
  border-bottom: 2px solid {ACCENT};
  border-top-left-radius: 2px;
  border-top-right-radius: 2px;
}}
QLabel#propertyFloatTitleLabel {{
  color: #ffffff;
  font-size: 13px;
  font-weight: 700;
  font-family: "Microsoft YaHei UI", "Microsoft YaHei", sans-serif;
}}
QLabel#propertyFloatSubtitle {{
  color: #b0b0b0;
  font-size: 10px;
  font-weight: 400;
  padding-top: 1px;
}}
QWidget#propertyFloatBody QTabWidget::pane {{
  border: 1px solid {FLOAT_LINE};
  background: {FLOAT_BG};
  top: -1px;
}}
QWidget#propertyFloatBody QTabBar::tab {{
  background: {FLOAT_CARD};
  color: {FLOAT_TEXT};
  border: 1px solid {FLOAT_LINE};
  border-bottom: none;
  padding: 5px 12px;
  margin-right: 2px;
  font-size: 12px;
}}
QWidget#propertyFloatBody QTabBar::tab:selected {{
  background: {FLOAT_BG};
  color: {ACCENT};
  font-weight: 600;
  border-bottom: 2px solid {ACCENT};
}}
QWidget#propertyFloatBody QTabBar::tab:hover {{
  color: {ACCENT};
}}
QWidget#propertyFloatBody QTableWidget {{
  background: {FLOAT_INPUT_BG};
  border: 1px solid {FLOAT_LINE};
  gridline-color: {FLOAT_LINE};
  font-size: 12px;
}}
QWidget#propertyFloatBody QHeaderView::section {{
  background: {FLOAT_CARD};
  color: {FLOAT_TEXT};
  padding: 4px 6px;
  border: 0;
  border-right: 1px solid {FLOAT_LINE};
  border-bottom: 1px solid {FLOAT_LINE};
  font-weight: 600;
}}
QPushButton#propertyFloatClose {{
  background: transparent;
  color: #c8c8c8;
  border: 0;
  font-size: 13px;
  border-radius: 2px;
}}
QPushButton#propertyFloatClose:hover {{
  color: #ffffff;
  background: #4a4a4a;
}}
QWidget#propertyFloatBody {{
  background: {FLOAT_BG};
  color: {FLOAT_TEXT};
}}
QWidget#propertyFloatBody QLabel {{
  color: {FLOAT_TEXT};
  font-size: 12px;
}}
QWidget#propertyFloatBody QGroupBox {{
  background: {FLOAT_CARD};
  border: 1px solid {FLOAT_LINE};
  border-radius: 2px;
  margin-top: 10px;
  padding: 8px 6px 6px 6px;
  font-weight: 600;
  color: {FLOAT_TEXT};
}}
QWidget#propertyFloatBody QGroupBox::title {{
  subcontrol-origin: margin;
  left: 8px;
  padding: 0 4px;
  background: {FLOAT_CARD};
  color: {FLOAT_TEXT};
}}
QWidget#propertyFloatBody QLineEdit,
QWidget#propertyFloatBody QSpinBox,
QWidget#propertyFloatBody QDoubleSpinBox,
QWidget#propertyFloatBody QComboBox,
QWidget#propertyFloatBody QPlainTextEdit {{
  background: {FLOAT_INPUT_BG};
  border: 1px solid {FLOAT_LINE};
  border-radius: 2px;
  padding: 3px 6px;
  color: {FLOAT_TEXT};
  selection-background-color: #ffe0c8;
  font-size: 12px;
}}
QWidget#propertyFloatBody QLineEdit:focus,
QWidget#propertyFloatBody QSpinBox:focus,
QWidget#propertyFloatBody QDoubleSpinBox:focus,
QWidget#propertyFloatBody QComboBox:focus {{
  border: 1px solid {ACCENT};
}}
QWidget#propertyFloatBody QComboBox QAbstractItemView {{
  background: {FLOAT_CARD};
  border: 1px solid {FLOAT_LINE};
  selection-background-color: #ffe0c8;
  color: {FLOAT_TEXT};
}}
QWidget#propertyFloatBody QPushButton {{
  background: {FLOAT_BTN_BG};
  border: 1px solid {FLOAT_LINE};
  border-radius: 2px;
  padding: 4px 10px;
  min-height: 20px;
  color: {FLOAT_TEXT};
}}
QWidget#propertyFloatBody QPushButton:hover {{
  background: #dedede;
}}
QWidget#propertyFloatBody QPushButton#bindButton {{
  background: {FLOAT_BTN_BG};
  border: 1px solid {FLOAT_LINE};
  padding: 1px;
  min-height: 18px;
  max-width: 28px;
}}
QWidget#propertyFloatBody QScrollArea {{
  background: transparent;
  border: 0;
}}
QWidget#propertyFloatBody QWidget#propertyPanel {{
  background: {FLOAT_BG};
  border: 0;
}}
QWidget#propertyFloatBody QGroupBox#propertySection {{
  background: {FLOAT_CARD};
  border: 1px solid {FLOAT_LINE};
  border-radius: 2px;
  margin-top: 10px;
  padding: 8px 6px 6px 6px;
  font-weight: 600;
  color: {FLOAT_TEXT};
}}
QWidget#propertyFloatBody QGroupBox#propertySection::title {{
  background: {FLOAT_CARD};
  color: {FLOAT_TEXT};
}}
QWidget#propertyFloatBody QLabel#panelTitle,
QWidget#propertyFloatBody QLabel#panelDescription,
QWidget#propertyFloatBody QLabel#sectionHint {{
  color: {FLOAT_TEXT_MUTED};
}}
QFrame#propertyFloatFooter {{
  background: {FLOAT_BG_ALT};
  border-top: 1px solid {FLOAT_LINE};
  border-bottom-left-radius: 2px;
  border-bottom-right-radius: 2px;
}}
QFrame#propertyFloatFooter QPushButton {{
  background: {FLOAT_BTN_BG};
  border: 1px solid {FLOAT_LINE};
  border-radius: 2px;
  padding: 5px 14px;
  color: {FLOAT_TEXT};
  font-size: 12px;
}}
QFrame#propertyFloatFooter QPushButton:hover {{
  background: #dedede;
}}
QFrame#propertyFloatFooter QPushButton#primaryButton {{
  background: {ACCENT};
  color: white;
  border: 1px solid {ACCENT_DEEP};
  font-weight: 600;
}}
QFrame#propertyFloatFooter QPushButton#primaryButton:hover {{
  background: {ACCENT_DEEP};
}}
"""
