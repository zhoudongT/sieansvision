#pragma once

#include <QString>
#include <QStringList>
#include <memory>

class QSettings;

namespace sieans_qt {

/**
 * Short recently-opened/saved scheme list (PySide recentSchemes, cap 12).
 * Backed by QSettings; FORCE_SEED / headless / SIEANS_QT_RECENT_PATH use a
 * temp or injected ini so the user's SIEANS/VisionDesktop store is not written.
 */
class RecentFiles {
 public:
  static constexpr int kCap = 12;

  /** Empty path uses resolvedIniPath(). */
  explicit RecentFiles(const QString& iniPath = QString());
  ~RecentFiles();

  QString iniPath() const { return ini_path_; }
  /** Recent paths, newest first, existing-or-not (caller may drop missing). */
  QStringList paths() const;
  /** Move path to the front (absolute), cap kCap. */
  void remember(const QString& path);
  void remove(const QString& path);
  void clear();

  /** Native user QSettings file (SIEANS/VisionDesktop); may not exist. */
  static QString nativeUserFile();
  /**
   * SIEANS_QT_RECENT_PATH if set; otherwise a process-temp ini when
   * FORCE_SEED or headless; otherwise empty (native org/app store).
   */
  static QString resolvedIniPath();
  /** Isolated remember/order/cap/remove/clear and user-store isolation checks. */
  static QStringList recentFilesSelfTest();

 private:
  QSettings& store() const;
  mutable std::unique_ptr<QSettings> settings_;
  QString ini_path_;
};

}  // namespace sieans_qt
