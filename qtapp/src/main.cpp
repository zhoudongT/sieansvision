#include "MainWindow.hpp"
#include "Theme.hpp"

#include <QApplication>
#include <QFont>
#include <QStyleFactory>

int main(int argc, char* argv[]) {
  QApplication app(argc, argv);
  QApplication::setApplicationName(QStringLiteral("SIEANS Vision Qt"));
  QApplication::setOrganizationName(QStringLiteral("SIEANS"));
  QApplication::setApplicationVersion(QStringLiteral("0.2.0-parity"));

  app.setStyle(QStyleFactory::create(QStringLiteral("Fusion")));
  QFont font(QStringLiteral("Noto Sans CJK SC"));
  if (font.family() != QStringLiteral("Noto Sans CJK SC"))
    font = QFont(QStringLiteral("Microsoft YaHei UI"));
  font.setPointSize(10);
  app.setFont(font);

  QPalette pal;
  pal.setColor(QPalette::Window, QColor(QStringLiteral("#2a2c30")));
  pal.setColor(QPalette::WindowText, QColor(QStringLiteral("#e8e8e8")));
  pal.setColor(QPalette::Base, QColor(QStringLiteral("#1a1b1d")));
  pal.setColor(QPalette::AlternateBase, QColor(QStringLiteral("#32353a")));
  pal.setColor(QPalette::Text, QColor(QStringLiteral("#e8e8e8")));
  pal.setColor(QPalette::Button, QColor(QStringLiteral("#3a3d42")));
  pal.setColor(QPalette::ButtonText, QColor(QStringLiteral("#e8e8e8")));
  pal.setColor(QPalette::Highlight, QColor(QStringLiteral("#e67a2e")));
  pal.setColor(QPalette::HighlightedText, Qt::white);
  pal.setColor(QPalette::ToolTipBase, QColor(QStringLiteral("#3a3d42")));
  pal.setColor(QPalette::ToolTipText, QColor(QStringLiteral("#e8e8e8")));
  pal.setColor(QPalette::PlaceholderText, QColor(QStringLiteral("#787878")));
  app.setPalette(pal);
  app.setStyleSheet(sieans_qt::theme::workbenchStyleSheet());

  sieans_qt::MainWindow win;
  win.show();
  return app.exec();
}
