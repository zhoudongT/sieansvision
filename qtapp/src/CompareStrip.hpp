#pragma once

#include <QWidget>
#include <QStringList>
#include <QVector>
#include <QHash>

class QListWidget;
class QLabel;
class QPushButton;
class QSettings;
class QTimer;
class QEvent;

namespace sieans_qt {

/** PySide CompareThumbStrip subset: side-rail thumbs for multi-frame compare. */
class CompareStrip : public QWidget {
  Q_OBJECT
 public:
  explicit CompareStrip(QWidget* parent = nullptr);

  /** Replace the compare path list (capped at 6). Hidden when empty. */
  void setPaths(const QStringList& paths, const QString& active = QString(),
                bool asBaseline = true);
  QStringList paths() const { return paths_; }
  QString activePath() const { return active_; }
  int count() const { return paths_.size(); }
  bool isEmpty() const { return paths_.isEmpty(); }

  /** Append a path if new and under the cap; activate if already present. */
  bool addPath(const QString& path);
  /** Select a path already on the strip by full path or basename. */
  bool activatePath(const QString& path, bool emitSignal = false);
  void clear();

  QStringList baselinePaths() const { return baseline_paths_; }
  bool isOrderLocked() const { return order_locked_; }
  /** Lock or unlock reorder. persist writes film/compareOrderLocked (not the project). */
  void setOrderLocked(bool locked, bool persist = false);
  /** Move a thumb; no-op and false when locked or indices are invalid. */
  bool moveRow(int from, int to);
  /** Restore the set_paths baseline order (pushes undo first). */
  bool resetOrder();
  /** Pop the reorder/reset undo stack (may restore lock after a badge double-click). */
  bool undoOrder();
  int orderUndoDepth() const { return order_undo_.size(); }

  /** Inject settings for tests; nullptr uses QSettings(SIEANS, VisionDesktop). */
  void setCompareSettings(QSettings* settings);
  /** Load film/compareOrderLocked and film/undoClearLongMs from settings. */
  bool loadComparePrefs();
  void saveOrderLockPref(bool locked);
  bool loadOrderLockPref();

  /** Headless stand-in for lock-badge single click (toggles lock, persists). */
  void lockBadgeClick();
  /** Headless stand-in for lock-badge double click: reset order, unlock, undo can relock. */
  void lockBadgeDoubleClick();

  /** Empty the reorder undo stack (long-press ⊘). Returns false if already empty. */
  bool clearOrderUndo();
  /** Headless stand-in for a completed long-press on the undo-clear button. */
  bool fireUndoClearLongPress();
  /** Headless stand-in for a short press (records a tip, does not clear). */
  QString undoClearShortPress();
  int setUndoClearLongMs(int ms, bool persist = true);
  int undoClearLongMs() const { return undo_clear_long_ms_; }
  QString lastUndoClearTip() const { return last_undo_clear_tip_; }
  QString lockBadgeText() const;

  /** OK/NG measure tags on compare thumbs (runtime-only). */
  void setPathBadges(const QHash<QString, QString>& badges);
  QString pathBadge(const QString& path) const;

  /** Offscreen path/thumb/activate/cap plus lock/undo/reorder/pref checks. Empty list = pass. Needs QApplication. */
  static QStringList compareSelfTest();

 signals:
  void pathActivated(const QString& path);
  void clearRequested();
  void pathsChanged();
  void pathsReordered(const QStringList& paths);
  void lockChanged(bool locked);

 private:
  /** Rebuild list items and show/hide the rail. */
  void rebuild();
  /** Push the current order onto the undo stack (cap 16). */
  void pushOrderUndo();
  /** Apply lock chrome and enable/disable list drag. */
  void applyLockChrome();
  /** Read list widget order after an internal drag and emit if it changed. */
  void onRowsMoved();
  QSettings* compareSettings() const;
  QString thumbLabelFor(const QString& path) const;

 protected:
  bool eventFilter(QObject* obj, QEvent* event) override;

 private:
  QListWidget* list_ = nullptr;
  QLabel* title_ = nullptr;
  QPushButton* clearBtn_ = nullptr;
  QPushButton* lockBtn_ = nullptr;
  QPushButton* resetBtn_ = nullptr;
  QPushButton* undoBtn_ = nullptr;
  QLabel* undoDepth_ = nullptr;
  QLabel* lockBadge_ = nullptr;
  QPushButton* undoClearBtn_ = nullptr;
  QTimer* lock_badge_timer_ = nullptr;
  QTimer* undo_clear_timer_ = nullptr;
  QSettings* settings_ = nullptr;
  QStringList paths_;
  QStringList baseline_paths_;
  QVector<QStringList> order_undo_;
  QHash<QString, QString> path_badges_;
  QString active_;
  QString last_undo_clear_tip_;
  bool order_locked_ = false;
  bool suppress_reorder_ = false;
  bool undo_should_relock_ = false;
  int undo_clear_long_ms_ = 650;
};

}  // namespace sieans_qt
