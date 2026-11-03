#pragma once

#include <QWidget>
#include <QStringList>

class QLabel;
class QListWidget;
class QCheckBox;
class QKeyEvent;
class QEvent;

namespace sieans_qt {

/** VM 本地图像胶片条：图像源 (n/N)、自动切换、运行全部、添加/文件夹/删除。 */
class FilmstripBar : public QWidget {
  Q_OBJECT
 public:
  explicit FilmstripBar(QWidget* parent = nullptr);

  void addPaths(const QStringList& paths);
  void clearPaths();
  void setStatus(const QString& text);
  QString currentPath() const;
  int count() const;
  int index() const;
  bool autoSwitch() const;
  void advance();
  QStringList paths() const { return paths_; }
  void selectPrev();
  void selectNext();
  void copySelectedPaths();
  void copySelectedBasenames();
  void duplicateSelected();
  void invertSelection();
  void sortByName();
  void removeMissing();
  void shufflePaths();
  void keepOnlySelected();
  void exportPathList();
  void exportSelectedPathList();
  void gotoIndexDialog();
  void copyAllBasenames();

 protected:
  void keyPressEvent(QKeyEvent* event) override;
  bool eventFilter(QObject* obj, QEvent* event) override;

 signals:
  void imageSelected(const QString& path);
  void addImagesRequested();
  void addFolderRequested();
  void runAllRequested();

 private:
  void selectIndex(int index, bool emitSignal);
  void refreshCount();
  void rebuildThumbs();
  QIcon makeThumb(const QString& path) const;

  QLabel* countLabel_ = nullptr;
  QLabel* status_ = nullptr;
  QCheckBox* autoSwitch_ = nullptr;
  QListWidget* list_ = nullptr;
  QStringList paths_;
  int index_ = -1;
  bool rebuilding_ = false;
};

}  // namespace sieans_qt
