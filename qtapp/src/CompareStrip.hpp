#pragma once

#include <QWidget>
#include <QStringList>
#include <QVector>

class QListWidget;
class QLabel;
class QPushButton;

namespace sieans_qt {

/** PySide CompareThumbStrip subset: side-rail thumbs for multi-frame compare. */
class CompareStrip : public QWidget {
  Q_OBJECT
 public:
  explicit CompareStrip(QWidget* parent = nullptr);

  /** Replace the compare path list (capped at 6). Hidden when empty. */
  void setPaths(const QStringList& paths, const QString& active = QString());
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
  /** Lock or unlock drag/programmatic reorder (runtime-only, not written to the project). */
  void setOrderLocked(bool locked);
  /** Move a thumb; no-op and false when locked or indices are invalid. */
  bool moveRow(int from, int to);
  /** Restore the set_paths baseline order (pushes undo first). */
  bool resetOrder();
  /** Pop the reorder/reset undo stack. */
  bool undoOrder();
  int orderUndoDepth() const { return order_undo_.size(); }

  /** Offscreen path/thumb/activate/cap plus lock/undo/reorder checks. Empty list = pass. Needs QApplication. */
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

  QListWidget* list_ = nullptr;
  QLabel* title_ = nullptr;
  QPushButton* clearBtn_ = nullptr;
  QPushButton* lockBtn_ = nullptr;
  QPushButton* resetBtn_ = nullptr;
  QPushButton* undoBtn_ = nullptr;
  QLabel* undoDepth_ = nullptr;
  QStringList paths_;
  QStringList baseline_paths_;
  QVector<QStringList> order_undo_;
  QString active_;
  bool order_locked_ = false;
  bool suppress_reorder_ = false;
};

}  // namespace sieans_qt
