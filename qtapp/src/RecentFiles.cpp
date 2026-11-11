#include "RecentFiles.hpp"

#include "WorkbenchPaths.hpp"

#include <QCoreApplication>
#include <QDateTime>
#include <QDir>
#include <QFileInfo>
#include <QSettings>
#include <QTemporaryDir>

namespace sieans_qt {
namespace {

const char kOrg[] = "SIEANS";
const char kApp[] = "VisionDesktop";
const char kKey[] = "recentSchemes";

QString processSmokeRecentPath() {
  static QString path;
  if (path.isEmpty()) {
    const QString dir = QDir::temp().filePath(
        QStringLiteral("sieans-qt-recent-%1").arg(QCoreApplication::applicationPid()));
    QDir().mkpath(dir);
    path = dir + QStringLiteral("/recent.ini");
  }
  return path;
}

QStringList uniqueCap(const QStringList& in) {
  QStringList out;
  for (const QString& raw : in) {
    const QString s = raw.trimmed();
    if (s.isEmpty() || out.contains(s)) continue;
    out.append(s);
    if (out.size() >= RecentFiles::kCap) break;
  }
  return out;
}

}  // namespace

RecentFiles::RecentFiles(const QString& iniPath) {
  ini_path_ = iniPath.trimmed().isEmpty() ? resolvedIniPath() : iniPath;
}

RecentFiles::~RecentFiles() = default;

QSettings& RecentFiles::store() const {
  if (!settings_) {
    if (ini_path_.isEmpty())
      settings_.reset(new QSettings(QString::fromLatin1(kOrg), QString::fromLatin1(kApp)));
    else
      settings_.reset(new QSettings(ini_path_, QSettings::IniFormat));
  }
  return *settings_;
}

QStringList RecentFiles::paths() const {
  const QVariant raw = store().value(QLatin1String(kKey));
  QStringList items;
  if (raw.typeId() == QMetaType::QString)
    items = raw.toString().isEmpty() ? QStringList{} : QStringList{raw.toString()};
  else
    items = raw.toStringList();
  return uniqueCap(items);
}

void RecentFiles::remember(const QString& path) {
  QString abs = path.trimmed();
  if (abs.isEmpty()) return;
  const QFileInfo fi(abs);
  if (fi.exists()) abs = fi.canonicalFilePath();
  else abs = fi.absoluteFilePath();
  if (abs.isEmpty()) return;
  QStringList items = paths();
  items.removeAll(abs);
  items.prepend(abs);
  store().setValue(QLatin1String(kKey), uniqueCap(items));
  store().sync();
}

void RecentFiles::remove(const QString& path) {
  QStringList items = paths();
  const QFileInfo fi(path);
  const QString abs = fi.exists() ? fi.canonicalFilePath() : fi.absoluteFilePath();
  items.removeAll(path);
  items.removeAll(abs);
  store().setValue(QLatin1String(kKey), uniqueCap(items));
  store().sync();
}

void RecentFiles::clear() {
  store().setValue(QLatin1String(kKey), QStringList{});
  store().sync();
}

QString RecentFiles::nativeUserFile() {
  QSettings s(QString::fromLatin1(kOrg), QString::fromLatin1(kApp));
  return s.fileName();
}

QString RecentFiles::resolvedIniPath() {
  const QByteArray env = qgetenv("SIEANS_QT_RECENT_PATH");
  if (!env.isEmpty()) return QString::fromUtf8(env);
  if (qgetenv("SIEANS_QT_FORCE_SEED") == "1" || workbenchIsHeadless())
    return processSmokeRecentPath();
  return {};
}

QStringList RecentFiles::recentFilesSelfTest() {
  QStringList fails;
  auto check = [&](const char* name, bool ok, const QString& detail = QString()) {
    if (!ok)
      fails << (detail.isEmpty() ? QString::fromUtf8(name)
                                 : QStringLiteral("%1: %2").arg(QString::fromUtf8(name), detail));
  };

  const QString userFile = nativeUserFile();
  const bool userExisted = QFileInfo::exists(userFile);
  const qint64 userSize = userExisted ? QFileInfo(userFile).size() : 0;
  const QDateTime userMtime = userExisted ? QFileInfo(userFile).lastModified() : QDateTime();

  QTemporaryDir tmp;
  check("tmpdir", tmp.isValid());
  if (!tmp.isValid()) return fails;
  const QString ini = tmp.filePath(QStringLiteral("recent.ini"));
  RecentFiles rec(ini);
  check("empty", rec.paths().isEmpty());

  rec.remember(tmp.filePath(QStringLiteral("a.sieans")));
  rec.remember(tmp.filePath(QStringLiteral("b.prc")));
  rec.remember(tmp.filePath(QStringLiteral("c.sieans")));
  QStringList p = rec.paths();
  check("order", p.size() == 3 && p.first().endsWith(QStringLiteral("c.sieans")) &&
                     p.at(1).endsWith(QStringLiteral("b.prc")) &&
                     p.at(2).endsWith(QStringLiteral("a.sieans")),
        p.join(QLatin1Char('|')));

  rec.remember(tmp.filePath(QStringLiteral("b.prc")));
  p = rec.paths();
  check("move-front", p.size() == 3 && p.first().endsWith(QStringLiteral("b.prc")));

  RecentFiles loaded(ini);
  check("reload", loaded.paths().size() == 3 &&
                      loaded.paths().first().endsWith(QStringLiteral("b.prc")));

  for (int i = 0; i < RecentFiles::kCap + 4; ++i)
    rec.remember(tmp.filePath(QStringLiteral("n%1.sieans").arg(i)));
  check("cap", rec.paths().size() == RecentFiles::kCap,
        QString::number(rec.paths().size()));

  const QString missing = tmp.filePath(QStringLiteral("missing.sieans"));
  rec.remember(missing);
  check("remember-missing-ok", rec.paths().first().endsWith(QStringLiteral("missing.sieans")));
  rec.remove(missing);
  check("drop-missing", !rec.paths().contains(QFileInfo(missing).absoluteFilePath()) &&
                            rec.paths().filter(QStringLiteral("missing.sieans")).isEmpty());

  rec.clear();
  check("clear", rec.paths().isEmpty());
  RecentFiles again(ini);
  check("clear-persist", again.paths().isEmpty());

  const bool userNow = QFileInfo::exists(userFile);
  if (!userExisted)
    check("user-untouched-absent", !userNow, userFile);
  else
    check("user-untouched-same",
          userNow && QFileInfo(userFile).size() == userSize &&
              QFileInfo(userFile).lastModified() == userMtime,
          userFile);
  return fails;
}

}  // namespace sieans_qt
