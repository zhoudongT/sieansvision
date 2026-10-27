"""SIEANS Vision industrial UI tokens — VisionMaster-aligned Dark + orange active."""

# Palette — charcoal Dark workbench, orange = active
BG = '#1a1f26'
PANEL = '#222831'
CARD = '#2b333d'
LINE = '#3a4552'
LINE_SOFT = '#323a45'
ACCENT = '#e67a2e'
ACCENT_DEEP = '#c45f18'
TEXT = '#e8edf2'
TEXT_MUTED = '#9aa7b5'
TEXT_DIM = '#6b7684'
OK = '#2d9b6c'
WARN = '#d4a017'
HOVER = '#2f3844'
SELECTED = '#3a2a1c'
HEADER = '#252c35'
CANVAS = '#1e242c'
CANVAS_DOT = '#2a323c'

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
  font-family: "Microsoft YaHei UI", "Noto Sans CJK SC", "Source Han Sans SC", sans-serif;
  font-size: 13px;
  color: {TEXT};
}}
QMainWindow {{ background: {BG}; }}
QMenuBar {{
  background: {HEADER};
  border-bottom: 1px solid {LINE};
  color: {TEXT};
  spacing: 6px;
  padding: 4px 6px;
}}
QMenuBar::item:selected {{ background: {HOVER}; color: {ACCENT}; }}
QMenu {{
  background: {CARD};
  border: 1px solid {LINE};
  color: {TEXT};
}}
QMenu::item:selected {{ background: {SELECTED}; color: {ACCENT}; }}
QToolBar {{
  background: {HEADER};
  border-bottom: 1px solid {LINE};
  spacing: 6px;
  padding: 4px 8px;
}}
QToolButton {{
  padding: 6px 10px;
  border-radius: 4px;
  color: {TEXT};
  background: transparent;
}}
QToolButton:hover {{ background: {HOVER}; }}
QToolButton:checked {{ background: {SELECTED}; color: {ACCENT}; }}
QPushButton {{
  background: {CARD};
  border: 1px solid {LINE};
  border-radius: 4px;
  padding: 6px 12px;
  min-height: 22px;
  color: {TEXT};
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
  border-radius: 4px;
  padding: 5px 8px;
  color: {TEXT};
  selection-background-color: {SELECTED};
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus, QPlainTextEdit:focus {{
  border: 1px solid {ACCENT};
}}
QComboBox::drop-down {{ border: 0; width: 22px; }}
QComboBox QAbstractItemView {{
  background: {CARD};
  border: 1px solid {LINE};
  selection-background-color: {SELECTED};
  color: {TEXT};
}}
QTreeWidget, QTableWidget, QListWidget {{
  background: {CARD};
  border: 1px solid {LINE_SOFT};
  border-radius: 4px;
  alternate-background-color: {PANEL};
  outline: 0;
  color: {TEXT};
}}
QHeaderView::section {{
  background: {HEADER};
  color: {TEXT_MUTED};
  padding: 7px 8px;
  border: 0;
  border-bottom: 1px solid {LINE};
  font-weight: 600;
}}
QTabWidget::pane {{
  border: 1px solid {LINE};
  background: {PANEL};
  border-radius: 0 0 4px 4px;
  top: -1px;
}}
QTabBar::tab {{
  background: {HEADER};
  padding: 8px 14px;
  margin-right: 2px;
  border-top-left-radius: 4px;
  border-top-right-radius: 4px;
  color: {TEXT_MUTED};
}}
QTabBar::tab:selected {{
  background: {PANEL};
  color: {ACCENT};
  font-weight: 600;
  border-bottom: 2px solid {ACCENT};
}}
QSplitter::handle {{ background: {LINE_SOFT}; width: 3px; height: 3px; }}
QStatusBar, QStatusBar#workbenchStatus {{
  background: #12161c;
  color: {TEXT_MUTED};
  border-top: 1px solid {LINE};
}}
QLabel#statusConfig, QLabel#statusTiming, QLabel#statusLog, QLabel#statusVersion {{
  color: {TEXT_MUTED};
  padding: 0 4px;
}}
QLabel#statusConfig[error="true"] {{ color: #e05555; }}
QLabel#brand {{ color: {ACCENT}; font-size: 18px; font-weight: 700; padding: 4px 10px; }}
QScrollBar:vertical {{
  background: transparent; width: 10px; margin: 2px;
}}
QScrollBar::handle:vertical {{
  background: #4a5562; border-radius: 4px; min-height: 28px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{
  background: transparent; height: 10px; margin: 2px;
}}
QScrollBar::handle:horizontal {{
  background: #4a5562; border-radius: 4px; min-width: 28px;
}}

/* —— Left rail + library —— */
QWidget#operatorRail {{
  background: #151a20;
  border-right: 1px solid {LINE};
}}
QToolButton#railButton {{
  background: transparent;
  border: 0;
  border-radius: 6px;
  padding: 6px;
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
  background: {CARD};
  border: 1px solid {LINE};
  border-radius: 6px;
  padding: 7px 12px;
  font-size: 13px;
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
  background: #1a1f26;
  border: 1px solid {LINE};
  border-radius: 4px;
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
QLabel#filmstripCount {{
  color: {TEXT_MUTED};
  font-weight: 600;
}}
QListWidget#filmstripThumbs {{
  background: transparent;
  border: 0;
}}
QListWidget#filmstripThumbs::item:selected {{
  background: {SELECTED};
  border: 1px solid {ACCENT};
}}

/* —— Property / settings inspector (docked fallback) —— */
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
  color: {ACCENT};
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
  border-radius: 6px;
  margin-top: 12px;
  padding: 10px 8px 8px 8px;
  font-weight: 600;
  color: {TEXT};
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
  background: #3a2a1c;
  color: {ACCENT};
  border: 1px solid {ACCENT_DEEP};
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
QPushButton#bindButton {{
  background: {HEADER};
  border: 1px solid {LINE};
  padding: 2px;
  min-height: 18px;
}}

/* —— Dialogs —— */
QDialog {{
  background: {BG};
  color: {TEXT};
}}
QDialog QGroupBox {{
  background: {CARD};
  border: 1px solid {LINE_SOFT};
  border-radius: 6px;
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
QMessageBox {{
  background: {PANEL};
}}
"""

TOOLBOX_QSS = f"""
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
  border-color: {ACCENT_DEEP};
}}
QToolButton#categoryHeader:checked {{
  background: {SELECTED};
  border-color: {ACCENT};
  color: {ACCENT};
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
"""
