#include "InspectionHistory.hpp"

#include "WorkbenchPaths.hpp"

#include <QCoreApplication>
#include <QDateTime>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QTemporaryDir>
#include <QUuid>

namespace sieans_qt {
namespace {

QString processSmokeHistoryPath() {
  static QString path;
  if (path.isEmpty()) {
    const QString dir = QDir::temp().filePath(
        QStringLiteral("sieans-qt-hist-%1").arg(QCoreApplication::applicationPid()));
    QDir().mkpath(dir);
    path = dir + QStringLiteral("/inspection-history.json");
  }
  return path;
}

InspectionRecord recordFromJson(const QJsonObject& o) {
  InspectionRecord r;
  r.id = o.value(QStringLiteral("id")).toString();
  r.startedAt = o.value(QStringLiteral("startedAt")).toString();
  r.projectName = o.value(QStringLiteral("projectName")).toString();
  r.flowName = o.value(QStringLiteral("flowName")).toString();
  r.recipeName = o.value(QStringLiteral("recipeName")).toString();
  r.verdict = o.value(QStringLiteral("verdict")).toString();
  r.elapsedMs = qint64(o.value(QStringLiteral("elapsedMs")).toDouble());
  r.detail = o.value(QStringLiteral("detail")).toString();
  return r;
}

QJsonObject recordToJson(const InspectionRecord& r) {
  QJsonObject o;
  o.insert(QStringLiteral("id"), r.id);
  o.insert(QStringLiteral("startedAt"), r.startedAt);
  o.insert(QStringLiteral("projectName"), r.projectName);
  o.insert(QStringLiteral("flowName"), r.flowName);
  o.insert(QStringLiteral("recipeName"), r.recipeName);
  o.insert(QStringLiteral("verdict"), r.verdict);
  o.insert(QStringLiteral("elapsedMs"), r.elapsedMs);
  o.insert(QStringLiteral("detail"), r.detail);
  return o;
}

}  // namespace

InspectionHistory::InspectionHistory(const QString& path) {
  setPath(path);
}

void InspectionHistory::setPath(const QString& path) {
  path_ = path.trimmed().isEmpty() ? resolvedPath() : path;
  load();
}

bool InspectionHistory::load() {
  items_.clear();
  if (path_.isEmpty()) return false;
  QFile f(path_);
  if (!f.exists()) return true;
  if (!f.open(QIODevice::ReadOnly)) return false;
  QJsonParseError pe;
  const QJsonDocument doc = QJsonDocument::fromJson(f.readAll(), &pe);
  if (pe.error != QJsonParseError::NoError || !doc.isObject()) return false;
  const QJsonArray arr = doc.object().value(QStringLiteral("items")).toArray();
  for (const QJsonValue& v : arr) {
    InspectionRecord r = recordFromJson(v.toObject());
    if (r.id.isEmpty() && r.startedAt.isEmpty()) continue;
    items_.push_back(r);
  }
  return true;
}

bool InspectionHistory::save() const {
  if (path_.isEmpty()) return false;
  QDir().mkpath(QFileInfo(path_).absolutePath());
  QJsonArray arr;
  for (const InspectionRecord& r : items_) arr.append(recordToJson(r));
  QJsonObject root;
  root.insert(QStringLiteral("version"), 1);
  root.insert(QStringLiteral("items"), arr);
  QFile f(path_);
  if (!f.open(QIODevice::WriteOnly | QIODevice::Truncate)) return false;
  f.write(QJsonDocument(root).toJson(QJsonDocument::Compact));
  f.write("\n");
  return true;
}

InspectionRecord InspectionHistory::append(InspectionRecord rec) {
  if (rec.id.isEmpty()) rec.id = QUuid::createUuid().toString(QUuid::WithoutBraces);
  if (rec.startedAt.isEmpty())
    rec.startedAt = QDateTime::currentDateTime().toString(QStringLiteral("yyyy-MM-dd HH:mm:ss"));
  if (rec.verdict != QLatin1String("OK") && rec.verdict != QLatin1String("NG"))
    rec.verdict = rec.verdict.trimmed().toUpper() == QLatin1String("OK")
                      ? QStringLiteral("OK")
                      : QStringLiteral("NG");
  items_.prepend(rec);
  while (items_.size() > kCap) items_.removeLast();
  save();
  return rec;
}

void InspectionHistory::clear() {
  items_.clear();
  save();
}

QString InspectionHistory::defaultUserPath() {
  return workbenchUserDataDir() + QStringLiteral("/inspection-history.json");
}

QString InspectionHistory::resolvedPath() {
  const QByteArray env = qgetenv("SIEANS_QT_HISTORY_PATH");
  if (!env.isEmpty()) return QString::fromUtf8(env);
  if (qgetenv("SIEANS_QT_FORCE_SEED") == "1" || workbenchIsHeadless())
    return processSmokeHistoryPath();
  return defaultUserPath();
}

QStringList InspectionHistory::historySelfTest() {
  QStringList fails;
  auto check = [&](const char* name, bool ok, const QString& detail = QString()) {
    if (!ok)
      fails << (detail.isEmpty() ? QString::fromUtf8(name)
                                 : QStringLiteral("%1: %2").arg(QString::fromUtf8(name), detail));
  };

  const QString userPath = defaultUserPath();
  const bool userExisted = QFileInfo::exists(userPath);
  const qint64 userSize = userExisted ? QFileInfo(userPath).size() : 0;
  const QDateTime userMtime = userExisted ? QFileInfo(userPath).lastModified() : QDateTime();

  QTemporaryDir tmp;
  check("tmpdir", tmp.isValid());
  if (!tmp.isValid()) return fails;
  const QString path = tmp.filePath(QStringLiteral("inspection-history.json"));
  InspectionHistory hist(path);
  check("empty", hist.count() == 0);
  check("path", hist.path() == path, hist.path());

  InspectionRecord a;
  a.projectName = QStringLiteral("测工程");
  a.flowName = QStringLiteral("流程1");
  a.recipeName = QStringLiteral("A型");
  a.verdict = QStringLiteral("OK");
  a.elapsedMs = 12;
  a.detail = QStringLiteral("passGate=1");
  const InspectionRecord stored = hist.append(a);
  check("append-id", !stored.id.isEmpty() && !stored.startedAt.isEmpty());
  check("append-count", hist.count() == 1);

  InspectionRecord b;
  b.projectName = QStringLiteral("测工程");
  b.flowName = QStringLiteral("流程1");
  b.verdict = QStringLiteral("NG");
  b.elapsedMs = 33;
  hist.append(b);
  check("count2", hist.count() == 2);
  check("newest-first", hist.records().first().verdict == QLatin1String("NG") &&
                            hist.records().at(1).verdict == QLatin1String("OK"));

  InspectionHistory loaded(path);
  check("reload-count", loaded.count() == 2, QString::number(loaded.count()));
  check("reload-ok", loaded.records().at(1).recipeName == QStringLiteral("A型") &&
                         loaded.records().at(1).elapsedMs == 12);
  check("reload-ng", loaded.records().first().verdict == QLatin1String("NG"));

  for (int i = 0; i < InspectionHistory::kCap + 5; ++i) {
    InspectionRecord r;
    r.verdict = (i % 2) == 0 ? QStringLiteral("OK") : QStringLiteral("NG");
    r.elapsedMs = i;
    loaded.append(r);
  }
  check("cap", loaded.count() == InspectionHistory::kCap,
        QString::number(loaded.count()));

  loaded.clear();
  check("clear", loaded.count() == 0);
  InspectionHistory again(path);
  check("clear-persist", again.count() == 0);

  // must not create or mutate the real user history file
  const bool userNow = QFileInfo::exists(userPath);
  if (!userExisted)
    check("user-untouched-absent", !userNow, userPath);
  else
    check("user-untouched-same",
          userNow && QFileInfo(userPath).size() == userSize &&
              QFileInfo(userPath).lastModified() == userMtime,
          userPath);

  check("default-not-temp", !defaultUserPath().contains(QStringLiteral("sieans-qt-hist-")),
        defaultUserPath());
  return fails;
}

}  // namespace sieans_qt
