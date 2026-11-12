#include "WorkbenchPaths.hpp"

#include "SieansDocument.hpp"

#include <QCoreApplication>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QStandardPaths>
#include <QTemporaryDir>

namespace sieans_qt {
namespace {

const char kLegacyRoot[] = "/home/allen/文档/sieansvision";

/** 判断 dir 是否像本仓库根（构建脚本与启动脚本都在）。 */
bool looksLikeRepo(const QString& dir) {
  if (dir.isEmpty()) return false;
  if (QFileInfo::exists(dir + QStringLiteral("/RELEASE.json")) &&
      QFileInfo::exists(dir + QStringLiteral("/qtapp/build/sieans_qt"))) return true;
  return QFileInfo::exists(dir + QStringLiteral("/qtapp/scripts/build.sh")) &&
         QFileInfo::exists(dir + QStringLiteral("/scripts/launch-sieans-qt.sh"));
}

/** 从 start 向上最多 8 层寻找仓库根，避免在根分区无限爬升。 */
QString walkUpForRepo(const QString& start) {
  if (start.isEmpty()) return {};
  QDir d(start);
  QStringList seen;
  for (int i = 0; i < 8; ++i) {
    const QString p = d.exists() ? d.canonicalPath() : d.absolutePath();
    if (p.isEmpty() || seen.contains(p)) break;
    seen << p;
    if (looksLikeRepo(p)) return p;
    if (!d.cdUp()) break;
  }
  return {};
}

/** 确保目录存在；创建失败仍返回原路径，由调用方再判断。 */
QString ensureDir(const QString& path) {
  if (path.isEmpty()) return {};
  QDir().mkpath(path);
  return path;
}

}  // namespace

QString workbenchRepoRoot() {
  const QByteArray env = qgetenv("SIEANS_REPO");
  if (!env.isEmpty()) {
    const QString root = QFileInfo(QString::fromUtf8(env)).absoluteFilePath();
    if (looksLikeRepo(root)) return QFileInfo(root).canonicalFilePath();
  }
  QStringList starts;
  const QString appDir = QCoreApplication::applicationDirPath();
  if (!appDir.isEmpty()) starts << appDir;
  starts << QDir::currentPath();
  for (const QString& start : starts) {
    if (const QString hit = walkUpForRepo(start); !hit.isEmpty()) return hit;
  }
  const QString legacy = QString::fromUtf8(kLegacyRoot);
  if (looksLikeRepo(legacy)) return QFileInfo(legacy).canonicalFilePath();
  return {};
}

QString workbenchProjectsDir() {
  const QString root = workbenchRepoRoot();
  if (!root.isEmpty()) return ensureDir(root + QStringLiteral("/projects"));
  const QString home = QDir::home().filePath(QStringLiteral("sieansvision-projects"));
  return ensureDir(home);
}

QString workbenchArtifactsDir() {
  const QByteArray overrideDir = qgetenv("SIEANS_QT_ARTIFACTS");
  if (!overrideDir.isEmpty()) return ensureDir(QString::fromUtf8(overrideDir));
  const QString root = workbenchRepoRoot();
  if (!root.isEmpty()) return ensureDir(root + QStringLiteral("/artifacts"));
  const QString home = QDir::home().filePath(QStringLiteral("sieansvision-artifacts"));
  return ensureDir(home);
}

QString workbenchUserDataDir() {
  const QByteArray env = qgetenv("SIEANS_QT_USER_DATA");
  if (!env.isEmpty()) return ensureDir(QString::fromUtf8(env));
  return ensureDir(QDir::home().filePath(QStringLiteral(".local/share/sieans")));
}

QString workbenchTemplatesDir() {
  return ensureDir(workbenchArtifactsDir() + QStringLiteral("/qt-templates"));
}

QString workbenchResolveArtifactsDir(const QString& requested) {
  const QString fallback = workbenchArtifactsDir();
  const QString trim = requested.trimmed();
  if (trim.isEmpty()) return fallback;
  if (trim.contains(QString::fromUtf8(kLegacyRoot) + QStringLiteral("/artifacts")))
    return fallback;
  return trim;
}

QStringList workbenchSampleQrCandidates() {
  QStringList cands;
  auto add = [&](const QString& p) {
    if (!p.isEmpty() && !cands.contains(p)) cands << p;
  };
  const QString app = QCoreApplication::applicationDirPath();
  add(app + QStringLiteral("/resources/sample-qr.png"));
  add(app + QStringLiteral("/sample-qr.png"));
  add(QDir(app).absoluteFilePath(QStringLiteral("../resources/sample-qr.png")));
  const QString root = workbenchRepoRoot();
  if (!root.isEmpty()) {
    add(root + QStringLiteral("/qtapp/resources/sample-qr.png"));
    add(root + QStringLiteral("/qtapp/build/resources/sample-qr.png"));
  }
  add(QDir::currentPath() + QStringLiteral("/qtapp/resources/sample-qr.png"));
  add(QDir::currentPath() + QStringLiteral("/resources/sample-qr.png"));
  add(QString::fromUtf8(kLegacyRoot) + QStringLiteral("/qtapp/resources/sample-qr.png"));
  return cands;
}

QString workbenchFirstExistingSampleQr() {
  for (const QString& p : workbenchSampleQrCandidates()) {
    if (QFileInfo::exists(p)) return p;
  }
  return {};
}

bool workbenchIsHeadless() {
  const QByteArray plat = qgetenv("QT_QPA_PLATFORM");
  if (plat == "offscreen" || plat == "minimal" || plat == "minimalegl") return true;
  if (qgetenv("SIEANS_QT_HEADLESS") == "1") return true;
  if (qgetenv("SIEANS_QT_SCREENSHOT_QUIT") == "1") return true;
  // 自检退出路径不弹模态框。
  if (qgetenv("SIEANS_QT_PROJECT_SELFTEST") == "1") return true;
  return false;
}

QStringList workbenchPathsSelfTest() {
  QStringList fails;
  const QString root = workbenchRepoRoot();
  if (root.isEmpty())
    fails << QStringLiteral("repo root not found");
  else if (!looksLikeRepo(root))
    fails << QStringLiteral("repo root invalid: %1").arg(root);

  const QString proj = workbenchProjectsDir();
  if (proj.isEmpty() || !QFileInfo::exists(proj))
    fails << QStringLiteral("projects dir missing: %1").arg(proj);
  const QString art = workbenchArtifactsDir();
  if (art.isEmpty() || !QFileInfo::exists(art))
    fails << QStringLiteral("artifacts dir missing: %1").arg(art);
  const QString tpl = workbenchTemplatesDir();
  if (tpl.isEmpty() || !QFileInfo::exists(tpl))
    fails << QStringLiteral("templates dir missing: %1").arg(tpl);

  const QString resolved = workbenchResolveArtifactsDir(
      QString::fromUtf8(kLegacyRoot) + QStringLiteral("/artifacts"));
  if (resolved != art)
    fails << QStringLiteral("legacy artifacts not remapped: %1").arg(resolved);

  QTemporaryDir tmp;
  if (!tmp.isValid()) {
    fails << QStringLiteral("temp dir");
    return fails;
  }
  SieansDocument doc;
  doc.seedGentlQrDemo();
  const int steps = doc.steps().size();
  if (steps < 3) fails << QStringLiteral("seed steps %1").arg(steps);
  const QString path = tmp.filePath(QStringLiteral("roundtrip.sieans"));
  QString err;
  if (!doc.saveToFile(path, &err))
    fails << QStringLiteral("save: %1").arg(err);
  SieansDocument loaded;
  if (!loaded.loadFromFile(path, &err))
    fails << QStringLiteral("load: %1").arg(err);
  if (loaded.steps().size() != steps)
    fails << QStringLiteral("roundtrip steps %1 != %2").arg(loaded.steps().size()).arg(steps);
  if (loaded.path() != path && QFileInfo(loaded.path()).canonicalFilePath() !=
                                   QFileInfo(path).canonicalFilePath())
    fails << QStringLiteral("loaded path %1").arg(loaded.path());
  if (loaded.name().isEmpty()) fails << QStringLiteral("loaded name empty");
  if (!workbenchIsHeadless() && qgetenv("QT_QPA_PLATFORM") == "offscreen")
    fails << QStringLiteral("offscreen should be headless");
  return fails;
}

}  // namespace sieans_qt
