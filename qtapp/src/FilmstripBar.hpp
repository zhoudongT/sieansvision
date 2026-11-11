#pragma once

#include <QWidget>
#include <QStringList>
#include <QVariantMap>
#include <QVariant>
#include <QHash>
#include <QString>

class QLabel;
class QListWidget;
class QListWidgetItem;
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
  void setPaths(const QStringList& paths);
  void clearPaths();
  void setAutoSwitch(bool on);
  void setStatus(const QString& text);
  QString currentPath() const;
  int count() const;
  int index() const;
  void setCurrentIndex(int index, bool emitSignal = true);
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
  void pastePathsFromClipboard();
  void cutSelectedPaths();
  void exportSelectedPathList();
  void gotoIndexDialog();
  void copyAllBasenames();
  void revealCurrent();
  void removeDuplicatePaths();
  void moveSelectedToFront();
  void moveSelectedToEnd();
  void moveSelectedBy(int delta);
  void reversePaths();

  /** 按完整路径或文件名选中缩略图。找不到返回 false。 */
  bool selectPath(const QString& path, bool emitSignal = true);
  /** 火花线跳帧：显式下标 → 路径/基名 → stem/子串 → 数字 token。 */
  QVariantMap seekFrameToken(const QString& token, int index = -1,
                             bool emitSignal = true, bool flash = true);
  /** 短暂高亮定位到的缩略图（软反馈，无硬件）。 */
  QVariantMap flashSeekThumb(int index, const QString& path = QString(),
                             int ms = 480);
  /** 把火花跳帧 bag（frame/label/index）对到胶片条，对齐 PySide seek_filmstrip_from_spark_jump。 */
  static QVariantMap seekFromSparkJump(FilmstripBar* bar, const QVariantMap& bag,
                                       bool flash = true);
  /** 路径/下标/基名跳帧与 flash 标记。空列表表示通过。需要 QApplication。 */
  static QStringList jumpSelfTest();

  /** Annotate thumbs with OK/NG measure tags (runtime-only, does not change paths). */
  void setFrameMeasureBadges(const QHash<QString, QString>& badges);
  QString frameMeasureBadge(const QString& path) const;
  void clearFrameMeasureBadges();
  /** Normalize a badge token to OK, NG, or empty. */
  static QString normalizeMeasureBadge(const QVariant& value);
  /** Derive OK/NG from measure/caliper/geom (then locate/passGate) flow vars. */
  static QString measureBadgeFromVars(const QVariantMap& vars);
  QString thumbLabel(const QString& path) const;
  /** Isolated OK/NG thumb label/color checks. Empty list = pass. Needs QApplication. */
  static QStringList measureBadgeSelfTest();

 protected:
  void keyPressEvent(QKeyEvent* event) override;
  bool eventFilter(QObject* obj, QEvent* event) override;

 signals:
  void imageSelected(const QString& path);
  void addImagesRequested();
  void addFolderRequested();
  void runAllRequested();
  void pathsChanged();
  void autoSwitchChanged(bool on);

 private:
  void selectIndex(int index, bool emitSignal);
  void refreshCount();
  void rebuildThumbs();
  void notifyPathsChanged();
  QIcon makeThumb(const QString& path) const;
  /** Apply OK/NG text, tooltip, and color onto one thumb item. */
  void applyThumbMeasureChrome(QListWidgetItem* item, const QString& path) const;

  QLabel* countLabel_ = nullptr;
  QLabel* status_ = nullptr;
  QCheckBox* autoSwitch_ = nullptr;
  QListWidget* list_ = nullptr;
  QStringList paths_;
  QHash<QString, QString> measure_badges_;
  int index_ = -1;
  bool rebuilding_ = false;
  class QTimer* seekFlashTimer_ = nullptr;
  int seekFlashIndex_ = -1;
  QString thumbsBaseStyle_;
  /** 清除上一次跳帧高亮。 */
  void clearSeekFlash();
};

}  // namespace sieans_qt
