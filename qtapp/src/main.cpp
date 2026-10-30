#include "MainWindow.hpp"

#include <QApplication>
#include <QFile>
#include <QFont>
#include <QStyleFactory>

static void applyIndustrialDark(QApplication& app) {
  app.setStyle(QStyleFactory::create(QStringLiteral("Fusion")));
  QPalette pal;
  pal.setColor(QPalette::Window, QColor(32, 36, 42));
  pal.setColor(QPalette::WindowText, QColor(220, 224, 230));
  pal.setColor(QPalette::Base, QColor(24, 27, 32));
  pal.setColor(QPalette::AlternateBase, QColor(40, 44, 52));
  pal.setColor(QPalette::Text, QColor(220, 224, 230));
  pal.setColor(QPalette::Button, QColor(45, 50, 58));
  pal.setColor(QPalette::ButtonText, QColor(220, 224, 230));
  pal.setColor(QPalette::Highlight, QColor(0, 150, 136));
  pal.setColor(QPalette::HighlightedText, Qt::white);
  pal.setColor(QPalette::ToolTipBase, QColor(45, 50, 58));
  pal.setColor(QPalette::ToolTipText, QColor(220, 224, 230));
  app.setPalette(pal);

  app.setStyleSheet(QStringLiteral(
      "QToolBar { background: #2a2f38; spacing: 6px; padding: 4px; border: none; }"
      "QStatusBar { background: #1c2026; color: #b0b6c0; }"
      "QMenuBar { background: #2a2f38; color: #dce0e6; }"
      "QMenuBar::item:selected { background: #009688; }"
      "QMenu { background: #2a2f38; color: #dce0e6; }"
      "QMenu::item:selected { background: #009688; }"
      "QDockWidget::title { background: #2a2f38; padding: 4px; }"
      "QTreeWidget, QListWidget, QPlainTextEdit, QTableWidget {"
      "  background: #181b20; color: #dce0e6; border: 1px solid #3a404a; }"
      "QHeaderView::section { background: #2a2f38; color: #dce0e6; padding: 4px; }"
      "QPushButton { background: #3a424e; color: #dce0e6; border: 1px solid #4a5260;"
      "  padding: 4px 10px; border-radius: 3px; }"
      "QPushButton:hover { background: #009688; }"
      "QPushButton:pressed { background: #00796b; }"));
}

int main(int argc, char* argv[]) {
  QApplication app(argc, argv);
  QApplication::setApplicationName(QStringLiteral("SIEANS Vision Qt"));
  QApplication::setOrganizationName(QStringLiteral("SIEANS"));
  QApplication::setApplicationVersion(QStringLiteral("0.1.0-framework"));

  applyIndustrialDark(app);

  sieans_qt::MainWindow win;
  win.show();
  return app.exec();
}
