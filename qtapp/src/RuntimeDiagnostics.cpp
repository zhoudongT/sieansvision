#include "RuntimeDiagnostics.hpp"
#include "WorkbenchPaths.hpp"
#include "UvcCapture.hpp"
#include "sieans/ocr.hpp"
#include "sieans/gentl_capture.hpp"
#include <QCoreApplication>
#include <QDateTime>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QMutex>
#include <QMutexLocker>
#include <QDebug>
#include <cstdio>
#include <cstdlib>

namespace sieans_qt {
namespace {
QMutex logMutex;
QString logPath;
int minimumLevel = 1;
qint64 maxLogBytes = 2 * 1024 * 1024;

/** 用显式等级次序过滤；critical/fatal 始终记录，不隐藏失败。 */
int severity(QtMsgType type) {
  switch (type) {
    case QtDebugMsg: return 0;
    case QtInfoMsg: return 1;
    case QtWarningMsg: return 2;
    case QtCriticalMsg: return 3;
    case QtFatalMsg: return 4;
  }
  return 4;
}

/** Qt 全局回调只做文件 I/O，不递归调用 Qt 日志；多线程共享互斥锁。 */
void writeMessage(QtMsgType type, const QMessageLogContext& context, const QString& message) {
  if (severity(type) < minimumLevel) return;
  const QMutexLocker<QMutex> lock(&logMutex);
  const char* names[] = {"DEBUG", "INFO", "WARN", "ERROR", "FATAL"};
  const QByteArray bytes = QStringLiteral("%1 %2 [%3] %4\n")
      .arg(QDateTime::currentDateTime().toString(Qt::ISODateWithMs),
           QString::fromLatin1(names[severity(type)]),
           QString::fromUtf8(context.category ? context.category : "app"), message).toUtf8();
  if (QFileInfo(logPath).size() + bytes.size() > maxLogBytes) {
    QFile::remove(logPath + QStringLiteral(".2"));
    QFile::rename(logPath + QStringLiteral(".1"), logPath + QStringLiteral(".2"));
    QFile::rename(logPath, logPath + QStringLiteral(".1"));
  }
  QFile file(logPath);
  if (file.open(QIODevice::WriteOnly | QIODevice::Append)) {
    if (file.write(bytes) != bytes.size() || !file.flush()) {
      std::fputs("SIEANS persistent log write failed; stderr fallback\n", stderr);
      std::fwrite(bytes.constData(), 1, bytes.size(), stderr);
    }
  } else {
    std::fwrite(bytes.constData(), 1, bytes.size(), stderr);
  }
  // stderr 只镜像警告和错误，避免生产启动的重复无界 info 输出。
  if (severity(type) >= 2) std::fwrite(bytes.constData(), 1, bytes.size(), stderr);
  if (type == QtFatalMsg) std::abort();
}
}

void installRuntimeDiagnostics() {
  QString dir = QString::fromUtf8(qgetenv("SIEANS_QT_LOG_DIR"));
  if (dir.isEmpty()) dir = workbenchUserDataDir() + QStringLiteral("/logs");
  QDir().mkpath(dir);
  // 清理最多保留最近 20 个会话；不影响其它正在运行的 PID 文件。
  const QStringList sessions = QDir(dir).entryList({QStringLiteral("session-*.log")}, QDir::Files, QDir::Time);
  for (int i = 20; i < sessions.size(); ++i) {
    const QString name = sessions.at(i);
    const QString pid = name.mid(8).section(QLatin1Char('-'), 0, 0);
    if (QFileInfo::exists(QStringLiteral("/proc/") + pid)) continue;
    for (const QString& suffix : {QString(), QStringLiteral(".1"), QStringLiteral(".2")})
      QFile::remove(QDir(dir).filePath(name) + suffix);
  }
  logPath = QDir(dir).filePath(QStringLiteral("session-%1-%2.log")
      .arg(QCoreApplication::applicationPid()).arg(QDateTime::currentMSecsSinceEpoch()));
  const QByteArray level = qgetenv("SIEANS_QT_LOG_LEVEL").toLower();
  if (level == "debug") minimumLevel = 0;
  else if (level == "warning") minimumLevel = 2;
  else if (level == "error") minimumLevel = 3;
  const int requested = qEnvironmentVariableIntValue("SIEANS_QT_LOG_MAX_BYTES");
  if (requested >= 4096 && requested <= 16 * 1024 * 1024) maxLogBytes = requested;
  qInstallMessageHandler(writeMessage);
  qInfo().noquote() << "session-start pid=" << QCoreApplication::applicationPid() << "log=" << logPath;
  QObject::connect(QCoreApplication::instance(), &QCoreApplication::aboutToQuit, []() {
    qInfo() << "session-clean-exit";
  });
}

void logStartupDiagnostics() {
  qInfo().noquote() << "startup version=" << QCoreApplication::applicationVersion()
      << "Qt=" << qVersion() << "repo=" << workbenchRepoRoot()
      << "OCR=" << sieans::ocr_available()
      << "GenTL-built=" << sieans::GenTLCapture::available()
      << "UVC-count=" << UvcCapture::enumerate().size()
      << "official-model-and-real-PLC=NOT-ACCEPTED";
}
}
