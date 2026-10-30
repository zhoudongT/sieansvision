#pragma once
#include <QString>

namespace sieans_qt {
namespace theme {

inline constexpr const char* BG = "#2a2c30";
inline constexpr const char* PANEL = "#32353a";
inline constexpr const char* CARD = "#3a3d42";
inline constexpr const char* LINE = "#4a4e54";
inline constexpr const char* ACCENT = "#e67a2e";
inline constexpr const char* ACCENT_DEEP = "#c45f18";
inline constexpr const char* TEXT = "#e8e8e8";
inline constexpr const char* TEXT_MUTED = "#a8a8a8";
inline constexpr const char* TEXT_DIM = "#787878";
inline constexpr const char* OK = "#2d9b6c";
inline constexpr const char* WARN = "#d4a017";
inline constexpr const char* HOVER = "#3d4046";
inline constexpr const char* SELECTED = "#3d2e1f";
inline constexpr const char* HEADER = "#232528";
inline constexpr const char* CANVAS = "#2d2f33";
inline constexpr const char* CANVAS_DOT = "#4e5258";
inline constexpr const char* RAIL_BG = "#1a1b1d";
inline constexpr const char* STATUS_BG = "#151617";

inline QString workbenchStyleSheet() {
  return QStringLiteral(
R"(
QMainWindow, QWidget {
  font-family: "Microsoft YaHei UI", "Microsoft YaHei", "Noto Sans CJK SC", "Source Han Sans SC", sans-serif;
  font-size: 12px;
  color: #e8e8e8;
}
QMainWindow { background: #2a2c30; }
QMenuBar {
  background: #232528; border-bottom: 1px solid #4a4e54; color: #e8e8e8;
  spacing: 4px; padding: 2px 4px;
}
QMenuBar::item { padding: 4px 8px; }
QMenuBar::item:selected { background: #3d4046; color: #e67a2e; }
QMenu {
  background: #3a3d42; border: 1px solid #4a4e54; color: #e8e8e8; padding: 2px;
}
QMenu::item { padding: 5px 24px 5px 12px; }
QMenu::item:selected { background: #3d2e1f; color: #e67a2e; }
QMenu::separator { height: 1px; background: #4a4e54; margin: 3px 8px; }
QToolBar {
  background: #232528; border-bottom: 1px solid #4a4e54; spacing: 2px; padding: 2px 4px;
}
QToolBar#mainToolBar QToolButton {
  padding: 4px 8px; margin: 0 1px; border-radius: 2px; color: #a8a8a8; background: transparent;
}
QToolBar#mainToolBar QToolButton:hover { background: #3d4046; color: #e8e8e8; }
QToolBar#mainToolBar QToolButton:pressed { background: #3d2e1f; color: #e67a2e; }
QToolBar#mainToolBar QToolButton:checked { background: #3d2e1f; color: #e67a2e; }
QToolBar::separator { background: #4a4e54; width: 1px; margin: 4px 5px; }
QStatusBar { background: #151617; color: #a8a8a8; border-top: 1px solid #4a4e54; }
QDockWidget { color: #e8e8e8; titlebar-close-icon: none; }
QDockWidget::title {
  background: #232528; padding: 5px 8px; border-bottom: 1px solid #4a4e54;
  font-weight: 600;
}
QTreeWidget, QListWidget, QPlainTextEdit, QTableWidget, QTextEdit {
  background: #1a1b1d; color: #e8e8e8; border: 1px solid #4a4e54;
  selection-background-color: #3d2e1f; selection-color: #e67a2e;
  alternate-background-color: #222326;
}
QHeaderView::section {
  background: #32353a; color: #a8a8a8; padding: 4px 6px;
  border: none; border-right: 1px solid #4a4e54; border-bottom: 1px solid #4a4e54;
}
QPushButton {
  background: #3a3d42; color: #e8e8e8; border: 1px solid #4a4e54;
  padding: 4px 12px; border-radius: 2px;
}
QPushButton:hover { background: #3d4046; border-color: #e67a2e; }
QPushButton:pressed { background: #3d2e1f; color: #e67a2e; }
QPushButton:disabled { color: #787878; background: #2a2c30; }
QPushButton#accentBtn {
  background: #e67a2e; color: #ffffff; border: 1px solid #c45f18; font-weight: 600;
}
QPushButton#accentBtn:hover { background: #f08a3e; }
QPushButton#accentBtn:pressed { background: #c45f18; }
QPushButton#dangerBtn { background: #5a3030; border-color: #8a4040; }
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
  background: #1a1b1d; color: #e8e8e8; border: 1px solid #4a4e54;
  padding: 3px 6px; border-radius: 2px; selection-background-color: #3d2e1f;
}
QComboBox::drop-down { border: none; width: 18px; }
QComboBox QAbstractItemView {
  background: #3a3d42; color: #e8e8e8; selection-background-color: #3d2e1f;
  border: 1px solid #4a4e54;
}
QSplitter::handle { background: #4a4e54; width: 1px; height: 1px; }
QTabWidget::pane { border: 1px solid #4a4e54; background: #2a2c30; }
QTabBar::tab {
  background: #232528; color: #a8a8a8; padding: 5px 12px;
  border: 1px solid #4a4e54; border-bottom: none; margin-right: 1px;
}
QTabBar::tab:selected {
  background: #2a2c30; color: #e67a2e;
  border-bottom: 2px solid #e67a2e;
}
QScrollBar:vertical {
  background: #1a1b1d; width: 10px; margin: 0;
}
QScrollBar::handle:vertical { background: #55585e; min-height: 24px; border-radius: 3px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QLabel#sectionTitle { color: #e67a2e; font-weight: 600; padding: 2px 0; }
QLabel#muted { color: #a8a8a8; }
QFrame#rail {
  background: #1a1b1d; border-right: 1px solid #4a4e54;
}
QToolTip {
  background: #3a3d42; color: #e8e8e8; border: 1px solid #e67a2e; padding: 4px;
}
)");
}

}  // namespace theme
}  // namespace sieans_qt
