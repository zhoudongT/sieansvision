#pragma once
#include <QString>

namespace sieans_qt {
namespace theme {

inline constexpr const char* BG = "#2a2c30";
inline constexpr const char* PANEL = "#32353a";
inline constexpr const char* CARD = "#3a3d42";
inline constexpr const char* LINE = "#4a4e54";
inline constexpr const char* LINE_SOFT = "#3f4348";
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
  spacing: 4px; padding: 2px 4px; font-size: 12px;
}
QMenuBar::item { padding: 4px 8px; }
QMenuBar::item:selected { background: #3d4046; color: #e67a2e; }
QMenu {
  background: #3a3d42; border: 1px solid #4a4e54; color: #e8e8e8; padding: 2px; font-size: 12px;
}
QMenu::item { padding: 5px 24px 5px 12px; }
QMenu::item:selected { background: #3d2e1f; color: #e67a2e; }
QMenu::separator { height: 1px; background: #4a4e54; margin: 3px 8px; }
QToolBar {
  background: #232528; border-bottom: 1px solid #4a4e54; spacing: 1px; padding: 1px 4px;
}
QToolBar#mainToolBar {
  min-height: 30px; spacing: 1px; padding: 2px 4px 2px 0;
}
QToolBar#mainToolBar QToolButton {
  padding: 3px; margin: 0 1px; border-radius: 2px; min-width: 24px; min-height: 24px;
  color: #a8a8a8; background: transparent;
}
QToolBar#mainToolBar QToolButton:hover { background: #3d4046; color: #e8e8e8; }
QToolBar#mainToolBar QToolButton:pressed { background: #3d2e1f; }
QToolBar#mainToolBar QToolButton:checked { background: #3d2e1f; color: #e67a2e; }
QToolBar#mainToolBar::separator { background: #4a4e54; width: 1px; margin: 4px 5px; }
QLabel#brand {
  color: #e67a2e; font-size: 11px; font-weight: 700; letter-spacing: 0.8px; padding: 0 8px 0 6px;
}
QLabel#modeBadge {
  color: #a8a8a8; padding: 0 8px; font-size: 11px;
}
QLabel#modeBadge[runMode="true"] { color: #2d9b6c; font-weight: 600; }
QLabel#commListenBadge { color: #888; padding: 0 8px; font-size: 11px; }
QToolTip {
  background: #3a3d42; color: #e8e8e8; border: 1px solid #4a4e54; padding: 4px 8px; font-size: 11px;
}
QToolButton {
  padding: 3px 7px; border-radius: 2px; color: #e8e8e8; background: transparent; font-size: 12px;
}
QToolButton:hover { background: #3d4046; }
QToolButton:checked { background: #3d2e1f; color: #e67a2e; }
QPushButton {
  background: #3a3d42; border: 1px solid #4a4e54; border-radius: 2px;
  padding: 4px 10px; min-height: 20px; color: #e8e8e8; font-size: 12px;
}
QPushButton:hover { background: #3d4046; }
QPushButton:pressed { background: #3d2e1f; }
QPushButton:disabled { color: #787878; }
QPushButton#accentBtn, QPushButton#primaryButton {
  background: #e67a2e; color: white; border: 1px solid #c45f18; font-weight: 600;
}
QPushButton#accentBtn:hover, QPushButton#primaryButton:hover { background: #c45f18; }
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QPlainTextEdit {
  background: #3a3d42; border: 1px solid #4a4e54; border-radius: 2px;
  padding: 3px 6px; color: #e8e8e8; selection-background-color: #3d2e1f; font-size: 12px;
}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus, QPlainTextEdit:focus {
  border: 1px solid #e67a2e;
}
QComboBox::drop-down { border: 0; width: 18px; }
QComboBox QAbstractItemView {
  background: #3a3d42; border: 1px solid #4a4e54; selection-background-color: #3d2e1f; color: #e8e8e8;
}
QTreeWidget, QTableWidget, QListWidget {
  background: #3a3d42; border: 1px solid #3f4348; border-radius: 2px;
  alternate-background-color: #32353a; outline: 0; color: #e8e8e8; font-size: 12px;
}
QHeaderView::section {
  background: #232528; color: #a8a8a8; padding: 5px 6px; border: 0;
  border-bottom: 1px solid #4a4e54; font-weight: 600; font-size: 11px;
}
QTabWidget::pane {
  border: 1px solid #4a4e54; background: #32353a; border-radius: 0; top: -1px;
}
QTabBar::tab {
  background: transparent; padding: 6px 12px; margin-right: 0; border: 0;
  border-bottom: 2px solid transparent; border-radius: 0; color: #a8a8a8; font-size: 12px;
}
QTabBar::tab:hover { color: #e8e8e8; background: #3d4046; }
QTabBar::tab:selected {
  background: transparent; color: #e67a2e; font-weight: 600; border-bottom: 2px solid #e67a2e;
}
QSplitter::handle { background: #3f4348; width: 2px; height: 2px; }
QStatusBar, QStatusBar#workbenchStatus {
  background: #151617; color: #a8a8a8; border-top: 1px solid #4a4e54;
  font-size: 11px; min-height: 22px; max-height: 26px;
}
QScrollBar:vertical { background: #1a1b1d; width: 10px; margin: 0; }
QScrollBar::handle:vertical { background: #55585e; min-height: 24px; border-radius: 3px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QLabel#sectionTitle, QLabel#libraryTitle { color: #e67a2e; font-weight: 600; padding: 4px 6px; font-size: 12px; }
QLabel#muted { color: #a8a8a8; font-size: 11px; }
QFrame#rail, QWidget#operatorRail {
  background: #1a1b1d; border-right: 1px solid #4a4e54;
}
QWidget#libraryPane {
  background: #32353a; border-right: 1px solid #4a4e54;
}
QWidget#flowPane { background: #2a2c30; }
QWidget#imagePane { background: #2a2c30; }
QLineEdit#operatorSearch {
  margin: 0 4px 4px 4px;
}
)");
}

inline QString propertyFloatStyleSheet() {
  return QStringLiteral(
R"(
QDialog#propertyFloat {
  background: #f0f0f0; border: 1px solid #d0d0d0; border-radius: 2px;
  font-family: "Microsoft YaHei UI", "Microsoft YaHei", sans-serif;
  font-size: 12px; color: #222222;
}
QFrame#propertyFloatTitle {
  background: #2b2d30; border: 0; border-bottom: 2px solid #e67a2e;
}
QLabel#propertyFloatTitleLabel {
  color: #ffffff; font-size: 13px; font-weight: 700;
}
QLabel#propertyFloatSubtitle {
  color: #b0b0b0; font-size: 10px; font-weight: 400; padding-top: 1px;
}
QPushButton#propertyFloatClose {
  background: transparent; color: #e8e8e8; border: 0; font-size: 14px; font-weight: 700;
  border-radius: 4px; min-width: 28px; min-height: 28px; padding: 0;
}
QPushButton#propertyFloatClose:hover { background: #c62828; color: #ffffff; }
QWidget#propertyFloatBody { background: #f0f0f0; color: #222222; }
QWidget#propertyFloatBody QLabel { color: #222222; font-size: 12px; }
QWidget#propertyFloatBody QLabel#sectionTitle { color: #c45f18; }
QWidget#propertyFloatBody QLabel#muted { color: #666666; }
QWidget#propertyFloatBody QLineEdit, QWidget#propertyFloatBody QSpinBox,
QWidget#propertyFloatBody QDoubleSpinBox, QWidget#propertyFloatBody QComboBox,
QWidget#propertyFloatBody QPlainTextEdit {
  background: #ffffff; border: 1px solid #d0d0d0; border-radius: 2px;
  padding: 3px 6px; color: #222222; selection-background-color: #ffe0c0;
}
QWidget#propertyFloatBody QLineEdit:focus {
  border: 1px solid #e67a2e;
}
QFrame#propertyFloatFooter {
  background: #e8e8e8; border-top: 1px solid #d0d0d0;
}
QPushButton#propertyFloatOk {
  background: #e67a2e; color: white; border: 1px solid #c45f18; font-weight: 600;
  padding: 5px 16px;
}
QPushButton#propertyFloatOk:hover { background: #c45f18; }
QPushButton#propertyFloatRun, QPushButton#propertyFloatRunContinuous {
  background: #ffffff; border: 1px solid #d0d0d0; color: #222222; padding: 5px 12px;
}
QPushButton#propertyFloatRun:hover, QPushButton#propertyFloatRunContinuous:hover {
  border-color: #e67a2e; color: #e67a2e;
}
)");
}

}  // namespace theme
}  // namespace sieans_qt
