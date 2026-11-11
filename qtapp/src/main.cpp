#include "ExprEval.hpp"
#include "ConditionEval.hpp"
#include "SubflowExec.hpp"
#include "SoftFrame.hpp"
#include "MainWindow.hpp"
#include "Theme.hpp"

#include <QApplication>
#include <QFont>
#include <QFileInfo>
#include <QCoreApplication>
#include <QStyleFactory>

#include <cstdio>

int main(int argc, char* argv[]) {
  if (qEnvironmentVariable("SIEANS_QT_EXPR_SELFTEST") == QLatin1String("1") &&
      qEnvironmentVariable("SIEANS_QT_EXPR_SELFTEST_QUIT") == QLatin1String("1")) {
    const QStringList fails = sieans_qt::exprSelfTest();
    if (fails.isEmpty()) {
      std::fprintf(stdout, "expr-selftest ok\n");
      return 0;
    }
    for (const QString& line : fails)
      std::fprintf(stderr, "expr-selftest FAIL %s\n", line.toUtf8().constData());
    return 1;
  }

  if (qEnvironmentVariable("SIEANS_QT_CONDITION_SELFTEST") == QLatin1String("1") &&
      qEnvironmentVariable("SIEANS_QT_CONDITION_SELFTEST_QUIT") == QLatin1String("1")) {
    const QStringList fails = sieans_qt::conditionSelfTest();
    if (fails.isEmpty()) {
      std::fprintf(stdout, "condition-selftest ok\n");
      return 0;
    }
    for (const QString& line : fails)
      std::fprintf(stderr, "condition-selftest FAIL %s\n", line.toUtf8().constData());
    return 1;
  }

  if (qEnvironmentVariable("SIEANS_QT_SUBFLOW_SELFTEST") == QLatin1String("1") &&
      qEnvironmentVariable("SIEANS_QT_SUBFLOW_SELFTEST_QUIT") == QLatin1String("1")) {
    const QStringList fails = sieans_qt::subflowSelfTest();
    if (fails.isEmpty()) {
      std::fprintf(stdout, "subflow-selftest ok\n");
      return 0;
    }
    for (const QString& line : fails)
      std::fprintf(stderr, "subflow-selftest FAIL %s\n", line.toUtf8().constData());
    return 1;
  }

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


  // Prefer packaged sample-qr for soft/GenTL-fallback open-and-run decode.
  {
    const QString beside = QCoreApplication::applicationDirPath() +
                           QStringLiteral("/resources/sample-qr.png");
    if (QFileInfo::exists(beside))
      sieans_qt::setSoftQrSamplePath(beside);
  }
  sieans_qt::MainWindow win;
  win.show();
  return app.exec();
}
