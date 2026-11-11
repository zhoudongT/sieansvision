#include "ExprEval.hpp"
#include "ConditionEval.hpp"
#include "SubflowExec.hpp"
#include "DefectDetect.hpp"
#include "FixturePose.hpp"
#include "GeometryFind.hpp"
#include "MeasureDim.hpp"
#include "SerialExchange.hpp"
#include "ModbusClient.hpp"
#include "S7Client.hpp"
#include "OpcUaClient.hpp"
#include "MqttClient.hpp"
#include "YoloInfer.hpp"
#include "CloudOps.hpp"
#include "SocketExchange.hpp"
#include "FlowExtras.hpp"
#include "PythonExt.hpp"
#include "SoftFrame.hpp"
#include "MainWindow.hpp"
#include "WorkbenchPaths.hpp"
#include "SieansDocument.hpp"
#include "FilmstripBar.hpp"
#include "CommHub.hpp"
#include "ProtocolNet.hpp"
#include "Theme.hpp"

#include <QApplication>
#include <QGuiApplication>
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

  if (qEnvironmentVariable("SIEANS_QT_DEFECTS_SELFTEST") == QLatin1String("1") &&
      qEnvironmentVariable("SIEANS_QT_DEFECTS_SELFTEST_QUIT") == QLatin1String("1")) {
    const QStringList fails = sieans_qt::defectsSelfTest();
    if (fails.isEmpty()) {
      std::fprintf(stdout, "defects-selftest ok\n");
      return 0;
    }
    for (const QString& line : fails)
      std::fprintf(stderr, "defects-selftest FAIL %s\n", line.toUtf8().constData());
    return 1;
  }

  if (qEnvironmentVariable("SIEANS_QT_LOCATE_SELFTEST") == QLatin1String("1") &&
      qEnvironmentVariable("SIEANS_QT_LOCATE_SELFTEST_QUIT") == QLatin1String("1")) {
    const QStringList fails = sieans_qt::locateSelfTest();
    if (fails.isEmpty()) {
      std::fprintf(stdout, "locate-selftest ok\n");
      return 0;
    }
    for (const QString& line : fails)
      std::fprintf(stderr, "locate-selftest FAIL %s\n", line.toUtf8().constData());
    return 1;
  }

  if (qEnvironmentVariable("SIEANS_QT_GEOMETRY_SELFTEST") == QLatin1String("1") &&
      qEnvironmentVariable("SIEANS_QT_GEOMETRY_SELFTEST_QUIT") == QLatin1String("1")) {
    const QStringList fails = sieans_qt::geometrySelfTest();
    if (fails.isEmpty()) {
      std::fprintf(stdout, "geometry-selftest ok\n");
      return 0;
    }
    for (const QString& line : fails)
      std::fprintf(stderr, "geometry-selftest FAIL %s\n", line.toUtf8().constData());
    return 1;
  }

  if (qEnvironmentVariable("SIEANS_QT_MEASURE_SELFTEST") == QLatin1String("1") &&
      qEnvironmentVariable("SIEANS_QT_MEASURE_SELFTEST_QUIT") == QLatin1String("1")) {
    const QStringList fails = sieans_qt::measureSelfTest();
    if (fails.isEmpty()) {
      std::fprintf(stdout, "measure-selftest ok\n");
      return 0;
    }
    for (const QString& line : fails)
      std::fprintf(stderr, "measure-selftest FAIL %s\n", line.toUtf8().constData());
    return 1;
  }

  if (qEnvironmentVariable("SIEANS_QT_SERIAL_SELFTEST") == QLatin1String("1") &&
      qEnvironmentVariable("SIEANS_QT_SERIAL_SELFTEST_QUIT") == QLatin1String("1")) {
    const QStringList fails = sieans_qt::serialSelfTest();
    if (fails.isEmpty()) {
      std::fprintf(stdout, "serial-selftest ok\n");
      return 0;
    }
    for (const QString& line : fails)
      std::fprintf(stderr, "serial-selftest FAIL %s\n", line.toUtf8().constData());
    return 1;
  }

  if (qEnvironmentVariable("SIEANS_QT_MODBUS_SELFTEST") == QLatin1String("1") &&
      qEnvironmentVariable("SIEANS_QT_MODBUS_SELFTEST_QUIT") == QLatin1String("1")) {
    const QStringList fails = sieans_qt::modbusSelfTest();
    if (fails.isEmpty()) {
      std::fprintf(stdout, "modbus-selftest ok\n");
      return 0;
    }
    for (const QString& line : fails)
      std::fprintf(stderr, "modbus-selftest FAIL %s\n", line.toUtf8().constData());
    return 1;
  }

  if (qEnvironmentVariable("SIEANS_QT_S7_SELFTEST") == QLatin1String("1") &&
      qEnvironmentVariable("SIEANS_QT_S7_SELFTEST_QUIT") == QLatin1String("1")) {
    const QStringList fails = sieans_qt::s7SelfTest();
    if (fails.isEmpty()) {
      std::fprintf(stdout, "s7-selftest ok\n");
      return 0;
    }
    for (const QString& line : fails)
      std::fprintf(stderr, "s7-selftest FAIL %s\n", line.toUtf8().constData());
    return 1;
  }

  if (qEnvironmentVariable("SIEANS_QT_OPCUA_SELFTEST") == QLatin1String("1") &&
      qEnvironmentVariable("SIEANS_QT_OPCUA_SELFTEST_QUIT") == QLatin1String("1")) {
    const QStringList fails = sieans_qt::opcUaSelfTest();
    if (fails.isEmpty()) {
      std::fprintf(stdout, "opcua-selftest ok\n");
      return 0;
    }
    for (const QString& line : fails)
      std::fprintf(stderr, "opcua-selftest FAIL %s\n", line.toUtf8().constData());
    return 1;
  }

  if (qEnvironmentVariable("SIEANS_QT_MQTT_SELFTEST") == QLatin1String("1") &&
      qEnvironmentVariable("SIEANS_QT_MQTT_SELFTEST_QUIT") == QLatin1String("1")) {
    const QStringList fails = sieans_qt::mqttSelfTest();
    if (fails.isEmpty()) {
      std::fprintf(stdout, "mqtt-selftest ok\n");
      return 0;
    }
    for (const QString& line : fails)
      std::fprintf(stderr, "mqtt-selftest FAIL %s\n", line.toUtf8().constData());
    return 1;
  }

  if (qEnvironmentVariable("SIEANS_QT_YOLO_SELFTEST") == QLatin1String("1") &&
      qEnvironmentVariable("SIEANS_QT_YOLO_SELFTEST_QUIT") == QLatin1String("1")) {
    QGuiApplication app(argc, argv);
    const QStringList fails = sieans_qt::yoloSelfTest();
    if (fails.isEmpty()) {
      std::fprintf(stdout, "yolo-selftest ok\n");
      return 0;
    }
    for (const QString& line : fails)
      std::fprintf(stderr, "yolo-selftest FAIL %s\n", line.toUtf8().constData());
    return 1;
  }

  if (qEnvironmentVariable("SIEANS_QT_CLOUD_SELFTEST") == QLatin1String("1") &&
      qEnvironmentVariable("SIEANS_QT_CLOUD_SELFTEST_QUIT") == QLatin1String("1")) {
    const QStringList fails = sieans_qt::cloudSelfTest();
    if (fails.isEmpty()) {
      std::fprintf(stdout, "cloud-selftest ok\n");
      return 0;
    }
    for (const QString& line : fails)
      std::fprintf(stderr, "cloud-selftest FAIL %s\n", line.toUtf8().constData());
    return 1;
  }

  if (qEnvironmentVariable("SIEANS_QT_SOCKET_SELFTEST") == QLatin1String("1") &&
      qEnvironmentVariable("SIEANS_QT_SOCKET_SELFTEST_QUIT") == QLatin1String("1")) {
    QCoreApplication app(argc, argv);
    const QStringList fails = sieans_qt::socketExchangeSelfTest();
    if (fails.isEmpty()) {
      std::fprintf(stdout, "socket-selftest ok\n");
      return 0;
    }
    for (const QString& line : fails)
      std::fprintf(stderr, "socket-selftest FAIL %s\n", line.toUtf8().constData());
    return 1;
  }

  if (qEnvironmentVariable("SIEANS_QT_FLOWEXTRAS_SELFTEST") == QLatin1String("1") &&
      qEnvironmentVariable("SIEANS_QT_FLOWEXTRAS_SELFTEST_QUIT") == QLatin1String("1")) {
    const QStringList fails = sieans_qt::flowExtrasSelfTest();
    if (fails.isEmpty()) {
      std::fprintf(stdout, "flowextras-selftest ok\n");
      return 0;
    }
    for (const QString& line : fails)
      std::fprintf(stderr, "flowextras-selftest FAIL %s\n", line.toUtf8().constData());
    return 1;
  }

  if (qEnvironmentVariable("SIEANS_QT_PROTOCOL_ROBUST_SELFTEST") == QLatin1String("1") &&
      qEnvironmentVariable("SIEANS_QT_PROTOCOL_ROBUST_SELFTEST_QUIT") == QLatin1String("1")) {
    QCoreApplication app(argc, argv);
    const QStringList fails = sieans_qt::protocolRobustnessSelfTest();
    if (fails.isEmpty()) {
      std::fprintf(stdout, "protocol-robust-selftest ok\n");
      return 0;
    }
    for (const QString& line : fails)
      std::fprintf(stderr, "protocol-robust-selftest FAIL %s\n", line.toUtf8().constData());
    return 1;
  }

  if (qEnvironmentVariable("SIEANS_QT_IO_RESOLVE_SELFTEST") == QLatin1String("1") &&
      qEnvironmentVariable("SIEANS_QT_IO_RESOLVE_SELFTEST_QUIT") == QLatin1String("1")) {
    const QStringList fails = sieans_qt::CommHub::ioResolveSelfTest();
    if (fails.isEmpty()) {
      std::fprintf(stdout, "io-resolve-selftest ok\n");
      return 0;
    }
    for (const QString& line : fails)
      std::fprintf(stderr, "io-resolve-selftest FAIL %s\n", line.toUtf8().constData());
    return 1;
  }

  if (qEnvironmentVariable("SIEANS_QT_PIN_GROUP_SELFTEST") == QLatin1String("1") &&
      qEnvironmentVariable("SIEANS_QT_PIN_GROUP_SELFTEST_QUIT") == QLatin1String("1")) {
    QApplication app(argc, argv);
    QStringList fails = sieans_qt::SieansDocument::pinGroupSelfTest();
    fails << sieans_qt::HostStrip::pinGroupChromeSelfTest();
    if (fails.isEmpty()) {
      std::fprintf(stdout, "pin-group-selftest ok\n");
      return 0;
    }
    for (const QString& line : fails)
      std::fprintf(stderr, "pin-group-selftest FAIL %s\n", line.toUtf8().constData());
    return 1;
  }

  if (qEnvironmentVariable("SIEANS_QT_COMPARE_STRIP_SELFTEST") == QLatin1String("1") &&
      qEnvironmentVariable("SIEANS_QT_COMPARE_STRIP_SELFTEST_QUIT") == QLatin1String("1")) {
    QApplication app(argc, argv);
    const QStringList fails = sieans_qt::CompareStrip::compareSelfTest();
    if (fails.isEmpty()) {
      std::fprintf(stdout, "compare-strip-selftest ok\n");
      return 0;
    }
    for (const QString& line : fails)
      std::fprintf(stderr, "compare-strip-selftest FAIL %s\n", line.toUtf8().constData());
    return 1;
  }

  if (qEnvironmentVariable("SIEANS_QT_GEOM_OVERLAY_SELFTEST") == QLatin1String("1") &&
      qEnvironmentVariable("SIEANS_QT_GEOM_OVERLAY_SELFTEST_QUIT") == QLatin1String("1")) {
    QApplication app(argc, argv);
    const QStringList fails = sieans_qt::geomOverlaySelfTest();
    if (fails.isEmpty()) {
      std::fprintf(stdout, "geom-overlay-selftest ok\n");
      return 0;
    }
    for (const QString& line : fails)
      std::fprintf(stderr, "geom-overlay-selftest FAIL %s\n", line.toUtf8().constData());
    return 1;
  }

  if (qEnvironmentVariable("SIEANS_QT_FILMSTRIP_JUMP_SELFTEST") == QLatin1String("1") &&
      qEnvironmentVariable("SIEANS_QT_FILMSTRIP_JUMP_SELFTEST_QUIT") == QLatin1String("1")) {
    QApplication app(argc, argv);
    const QStringList fails = sieans_qt::FilmstripBar::jumpSelfTest();
    if (fails.isEmpty()) {
      std::fprintf(stdout, "filmstrip-jump-selftest ok\n");
      return 0;
    }
    for (const QString& line : fails)
      std::fprintf(stderr, "filmstrip-jump-selftest FAIL %s\n", line.toUtf8().constData());
    return 1;
  }

  if (qEnvironmentVariable("SIEANS_QT_SCHEME_SELFTEST") == QLatin1String("1") &&
      qEnvironmentVariable("SIEANS_QT_SCHEME_SELFTEST_QUIT") == QLatin1String("1")) {
    QCoreApplication app(argc, argv);
    const QStringList fails = sieans_qt::SieansDocument::schemeSelfTest();
    if (fails.isEmpty()) {
      std::fprintf(stdout, "scheme-selftest ok\n");
      return 0;
    }
    for (const QString& line : fails)
      std::fprintf(stderr, "scheme-selftest FAIL %s\n", line.toUtf8().constData());
    return 1;
  }

  if (qEnvironmentVariable("SIEANS_QT_PROJECT_SELFTEST") == QLatin1String("1") &&
      qEnvironmentVariable("SIEANS_QT_PROJECT_SELFTEST_QUIT") == QLatin1String("1")) {
    QCoreApplication app(argc, argv);
    const QStringList fails = sieans_qt::workbenchPathsSelfTest();
    if (fails.isEmpty()) {
      std::fprintf(stdout, "project-selftest ok\n");
      return 0;
    }
    for (const QString& line : fails)
      std::fprintf(stderr, "project-selftest FAIL %s\n", line.toUtf8().constData());
    return 1;
  }

  if (qEnvironmentVariable("SIEANS_QT_PYEXT_SELFTEST") == QLatin1String("1") &&
      qEnvironmentVariable("SIEANS_QT_PYEXT_SELFTEST_QUIT") == QLatin1String("1")) {
    QCoreApplication app(argc, argv);
    const QStringList fails = sieans_qt::pythonExtSelfTest();
    if (fails.isEmpty()) {
      std::fprintf(stdout, "pyext-selftest ok\n");
      return 0;
    }
    for (const QString& line : fails)
      std::fprintf(stderr, "pyext-selftest FAIL %s\n", line.toUtf8().constData());
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
