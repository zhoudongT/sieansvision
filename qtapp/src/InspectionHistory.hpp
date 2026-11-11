#pragma once

#include <QString>
#include <QStringList>
#include <QVector>

namespace sieans_qt {

/** One inspection-run row persisted outside the .sieans project. */
struct InspectionRecord {
  QString id;
  QString startedAt;
  QString projectName;
  QString flowName;
  QString recipeName;
  QString verdict;  // OK | NG
  qint64 elapsedMs = 0;
  QString detail;
};

/**
 * Bounded local inspection history (检测历史).
 * Stored under the workbench user-data path, never inside the live .sieans
 * unless a caller points the file there. FORCE_SEED / headless smoke is
 * redirected away from the user's real file.
 */
class InspectionHistory {
 public:
  static constexpr int kCap = 200;

  explicit InspectionHistory(const QString& path = QString());

  /** Switch the backing file and reload (empty path uses resolvedPath()). */
  void setPath(const QString& path);
  QString path() const { return path_; }

  bool load();
  bool save() const;
  /** Append a finished run; fills id/time when missing. Newest first, cap kCap. */
  InspectionRecord append(InspectionRecord rec);
  QVector<InspectionRecord> records() const { return items_; }
  int count() const { return items_.size(); }
  void clear();

  /** Interactive user file: $USER_DATA/inspection-history.json. */
  static QString defaultUserPath();
  /**
   * SIEANS_QT_HISTORY_PATH if set; otherwise a process-temp file when
   * FORCE_SEED or headless, else defaultUserPath().
   */
  static QString resolvedPath();
  /** Isolated append/persist/reload/cap and user-file isolation checks. */
  static QStringList historySelfTest();

 private:
  QString path_;
  QVector<InspectionRecord> items_;
};

}  // namespace sieans_qt
