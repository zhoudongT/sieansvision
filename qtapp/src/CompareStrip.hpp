#pragma once

#include <QWidget>
#include <QStringList>

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

  /** Offscreen path/thumb/activate/cap checks. Empty list = pass. Needs QApplication. */
  static QStringList compareSelfTest();

 signals:
  void pathActivated(const QString& path);
  void clearRequested();
  void pathsChanged();

 private:
  /** Rebuild list items and show/hide the rail. */
  void rebuild();
  QListWidget* list_ = nullptr;
  QLabel* title_ = nullptr;
  QPushButton* clearBtn_ = nullptr;
  QStringList paths_;
  QString active_;
};

}  // namespace sieans_qt
